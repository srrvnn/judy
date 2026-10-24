"""judy.run: decide what to do about a trigger.

The hourly clock check and the control panel's clock changes both end up here. We hand
Claude the trigger plus the household's current picture (judy/prompt.md holds its
instructions) and it decides whether to send messages with suggested actions. Claude may
also mark an action `automatic`: the server runs it at once, but only to turn back on a
plug that Judy itself switched off. If Claude can't be reached, nothing is sent.
JUDY_USE_CLAUDE=0 skips Claude.
"""
import json
import logging
import os
from datetime import timedelta, timezone
from pathlib import Path

import anthropic
from sqlmodel import Session, select

from judy.trigger import Trigger
from models import Action, Household, Message, Plug, Reading
from services.clock import now
from services.events import broadcaster, message_payload
from services.messages import resolve_message
from services.plug_control import PlugControlError, PlugController, controller as default_controller

logger = logging.getLogger("judy.run")

MODEL = "claude-opus-5-5"
USE_CLAUDE = os.environ.get("JUDY_USE_CLAUDE", "1") != "0"
ACTION_TYPES = ["turn_off", "turn_on", "dismiss"]
SEVERITIES = ["critical", "info"]
DRAWING_THRESHOLD_W = 1.0
RESTORE_WINDOW = timedelta(hours=24)  # how far back a Judy turn-off is still eligible to be undone

PROMPT_PATH = Path(__file__).with_name("prompt.md")
SYSTEM_PROMPT = PROMPT_PATH.read_text()

DECISION_SCHEMA = {
    "type": "object",
    "properties": {
        "reasoning": {"type": "string", "description": "One or two sentences on why you did or did not send messages"},
        "messages": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "plug_id": {"type": ["integer", "null"]},
                    "kind": {"type": "string", "description": "short snake_case category, e.g. left_on, high_usage"},
                    "severity": {"type": "string", "enum": SEVERITIES,
                                 "description": "critical: something is off and the household must act; info: something was off and is already taken care of"},
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                    "actions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "label": {"type": "string", "description": "Short button text"},
                                "description": {"type": "string", "description": "One sentence on what this does and why"},
                                "type": {"type": "string", "enum": ACTION_TYPES},
                                "plug_id": {"type": ["integer", "null"]},
                                "automatic": {"type": "boolean",
                                              "description": "true: run this action right now without asking. Only allowed for turn_on of a plug listed in switched_off_by_judy."},
                            },
                            "required": ["label", "description", "type", "plug_id", "automatic"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["plug_id", "kind", "severity", "title", "body", "actions"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["reasoning", "messages"],
    "additionalProperties": False,
}


def _drawing_since(session: Session, plug: Plug):
    """Start of the unbroken run of readings where the plug was on and drawing power."""
    readings = session.exec(
        select(Reading).where(Reading.plug_id == plug.id).order_by(Reading.recorded_at.desc()).limit(5000)
    ).all()
    since = None
    for r in readings:
        drawing = r.was_on and (r.power_w is None or r.power_w >= DRAWING_THRESHOLD_W)
        if not drawing:
            break
        since = r.recorded_at
    return since, (readings[0] if readings else None)


def _local_iso(moment) -> str:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)  # SQLite hands back naive UTC
    return moment.astimezone().isoformat()


def switched_off_by_judy(session: Session, current) -> list[dict]:
    """Plugs a household member turned off through a Judy action in the last day and that have not been
    turned back on through an action since. Nothing else counts: a plug someone switched off by hand
    is never listed, so Judy never undoes it."""
    executed = session.exec(
        select(Action)
        .where(Action.status == "executed", Action.type.in_(["turn_off", "turn_on"]),
               Action.plug_id.is_not(None), Action.executed_at >= current - RESTORE_WINDOW)
        .order_by(Action.executed_at, Action.id)
    ).all()
    latest = {a.plug_id: a for a in executed}
    result = []
    for plug_id, action in latest.items():
        if action.type != "turn_off":
            continue
        plug = session.get(Plug, plug_id)
        if plug is None:
            continue
        result.append({
            "plug_id": plug_id,
            "name": plug.name,
            "switched_off_at_local": _local_iso(action.executed_at),
            "action_id": action.id,
        })
    return result


def build_context(session: Session, trigger: Trigger) -> dict:
    current = now()
    plugs = []
    for plug in session.exec(select(Plug).order_by(Plug.id)).all():
        since, latest = _drawing_since(session, plug)
        if since is not None and since.tzinfo is None:
            since = since.replace(tzinfo=current.tzinfo)
        plugs.append({
            "id": plug.id,
            "name": plug.name,
            "room": plug.room,
            "model": plug.model,
            "has_energy": plug.has_energy,
            "device_id": plug.device_id,
            "latest_reading": None if latest is None else {
                "recorded_at": latest.recorded_at.isoformat(),
                "was_on": latest.was_on,
                "power_w": latest.power_w,
            },
            "drawing_power_since": since.isoformat() if since else None,
            "drawing_power_minutes": round((current - since).total_seconds() / 60) if since else 0,
        })

    recent = session.exec(select(Message).order_by(Message.created_at.desc()).limit(10)).all()
    recent_messages = []
    for m in recent:
        actions = session.exec(select(Action).where(Action.message_id == m.id)).all()
        recent_messages.append({
            "kind": m.kind, "plug_id": m.plug_id, "title": m.title,
            "created_at_local": _local_iso(m.created_at),
            "action_statuses": [a.status for a in actions],
        })

    local = current.astimezone()
    return {
        "now": current.isoformat(),
        "local_time": local.strftime("%H:%M"),
        "local_date": local.date().isoformat(),
        "weekday": local.strftime("%A"),
        "timezone": local.tzname(),
        "trigger": {"kind": trigger.kind, "detail": trigger.detail, "device_id": trigger.device_id, "data": trigger.data},
        "plugs": plugs,
        "switched_off_by_judy": switched_off_by_judy(session, current),
        "recent_messages": recent_messages,
    }


def call_claude(context: dict) -> dict:
    """Ask Claude for a decision. Returns {"reasoning": str, "messages": [...]}."""
    client = anthropic.Anthropic()
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        system=SYSTEM_PROMPT,
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": DECISION_SCHEMA}},
        messages=[{"role": "user", "content": json.dumps(context, indent=2)}],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError(f"claude declined: {response.stop_details}")
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)


def decide(context: dict) -> dict:
    nothing = {"reasoning": "no decision", "messages": []}
    if not USE_CLAUDE:
        return nothing
    try:
        return call_claude(context)
    except Exception as exc:
        logger.error("claude failed, sending nothing: %r", exc)
        return nothing


def _plug_label(plug: Plug) -> str:
    return plug.name or plug.model


def _run_automatic(session: Session, action: Action, allowed_plug_ids: set[int], controller: PlugController) -> str | None:
    """Run an action Claude marked automatic. Returns None if it ran fine, an error text if it
    failed, and "skipped" if it isn't allowed (it then stays a normal suggestion)."""
    if action.type != "turn_on" or action.plug_id not in allowed_plug_ids:
        logger.warning("not running %s on plug %s automatically: only turning back on plugs Judy switched off is allowed",
                       action.type, action.plug_id)
        return "skipped"
    action.status = "chosen"
    action.chosen_at = now()
    try:
        action.result = controller.switch(session.get(Plug, action.plug_id), on=True)
    except PlugControlError as exc:
        action.status = "failed"
        action.result = str(exc)
        return str(exc)
    action.status = "executed"
    action.executed_at = now()
    return None


def _save_messages(session: Session, decision: dict, allowed_auto_plug_ids: set[int] = frozenset(),
                   controller: PlugController = default_controller) -> list[Message]:
    valid_plug_ids = {p.id: p for p in session.exec(select(Plug)).all()}
    default_household = session.exec(select(Household).order_by(Household.id)).first()
    created = []
    for item in decision.get("messages", []):
        plug = valid_plug_ids.get(item.get("plug_id"))
        household_id = plug.household_id if plug else (default_household.id if default_household else None)
        if household_id is None:
            logger.warning("dropping message %r: no household to send it to", item.get("title"))
            continue
        message = Message(
            household_id=household_id,
            plug_id=plug.id if plug else None,
            kind=item["kind"],
            severity=item.get("severity") if item.get("severity") in SEVERITIES else "info",
            title=item["title"],
            body=item["body"],
        )
        session.add(message)
        session.flush()
        automatic = []
        for a in item.get("actions", []):
            action_plug = valid_plug_ids.get(a.get("plug_id"))
            action = Action(
                message_id=message.id,
                label=a["label"],
                description=a["description"],
                type=a["type"] if a["type"] in ACTION_TYPES else "dismiss",
                plug_id=action_plug.id if action_plug else None,
            )
            session.add(action)
            if a.get("automatic"):
                automatic.append(action)
        session.flush()

        outcomes = [(action, _run_automatic(session, action, allowed_auto_plug_ids, controller)) for action in automatic]
        ran = [(action, error) for action, error in outcomes if error != "skipped"]
        failed = [(action, error) for action, error in ran if error]
        if failed:
            # What we said no longer matches what happened: say so, and leave the action to retry.
            action, error = failed[0]
            label = _plug_label(session.get(Plug, action.plug_id))
            message.severity = "critical"
            message.title = f"Couldn't turn {label} back on"
            message.body = f"I tried to turn {label} back on but it didn't work: {error}"
            session.add(message)
        session.commit()
        if ran and not failed:
            for other in session.exec(select(Action).where(Action.message_id == message.id)).all():
                if other.status == "suggested":
                    other.status = "expired"
                    session.add(other)
            session.commit()
            resolve_message(session, message.id, by="judy")
        created.append(message)
    for message in created:
        session.refresh(message)
        payload = message_payload(session, message)
        logger.info("sending message:\n%s", json.dumps(payload, indent=2))
        broadcaster.publish(payload)
    return created


def run(session: Session, trigger: Trigger, controller: PlugController | None = None) -> list[Message]:
    """Decide what to do about a trigger and save any messages. Never raises."""
    logger.info("judy.run called: %s (%s)", trigger.kind, trigger.detail)
    try:
        context = build_context(session, trigger)
        decision = decide(context)
        logger.info("claude returned:\n%s", json.dumps(decision, indent=2))
        allowed = {entry["plug_id"] for entry in context["switched_off_by_judy"]}
        created = _save_messages(session, decision, allowed, controller or default_controller)
    except Exception as exc:
        logger.error("run failed for %s: %r", trigger.kind, exc)
        return []
    logger.info("decided: %s (%d message(s))", decision.get("reasoning", ""), len(created))
    return created
