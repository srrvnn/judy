"""judy.run: decide what to do about a trigger.

Heuristics (e.g. power drawn after being off) and the control panel's clock
changes both end up here. For now decisions are rule-based; set JUDY_USE_CLAUDE=1
to hand Claude the trigger plus the household's current picture instead and let
it decide whether to send messages with suggested actions.
"""
import json
import logging
import os

import anthropic
from sqlmodel import Session, select

from judy.trigger import Trigger
from models import Action, Household, Message, Plug, Reading
from services.clock import now
from services.events import broadcaster, message_payload

logger = logging.getLogger("judy.run")

MODEL = "claude-opus-5-5"
USE_CLAUDE = os.environ.get("JUDY_USE_CLAUDE", "0") == "1"
LEFT_ON_MINUTES = int(os.environ.get("LEFT_ON_MINUTES", "120"))
ACTION_TYPES = ["turn_off", "turn_on", "dismiss"]
SEVERITIES = ["critical", "info"]
DRAWING_THRESHOLD_W = 1.0

SYSTEM_PROMPT = """\
You are Judy, an assistant that helps households be judicious with power.

You are woken up when something happens: a heuristic fired on a smart plug (for \
example a plug drawing power after being off), or the clock was moved so time \
has changed. You are given the trigger, the current time, and the state of the \
household's plugs, including how long each has been drawing power.

Decide whether the household needs to hear about anything right now. If so, write \
one or more short, friendly messages, each with the actions the user could take \
(for example turning a plug off, or dismissing). Use the plug names and rooms. \
Reason about time: what is normal at this hour, and how long something has been on.

Set severity to "critical" when something is off and the household must act, and to \
"info" when something was off but has already been taken care of.

Be sparing. If nothing is worth interrupting the household for, return no messages. \
Do not repeat a message already sent recently (see recent_messages) unless the \
situation has clearly changed. Only reference plug ids that appear in the context. \
Always include a dismiss action alongside any other action.
"""

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
                            },
                            "required": ["label", "description", "type", "plug_id"],
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
            "created_at": m.created_at.isoformat(),
            "action_statuses": [a.status for a in actions],
        })

    return {
        "now": current.isoformat(),
        "trigger": {"kind": trigger.kind, "detail": trigger.detail, "device_id": trigger.device_id, "data": trigger.data},
        "plugs": plugs,
        "recent_messages": recent_messages,
    }


def call_claude(context: dict) -> dict:
    """Ask Claude for a decision. Returns {"reasoning": str, "messages": [...]}."""
    client = anthropic.Anthropic()
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=4096,
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


def _plug_label(plug: dict | None) -> str:
    return (plug and (plug["name"] or plug["model"])) or "A plug"


def _dismiss(plug_id: int | None) -> dict:
    return {"label": "Dismiss", "description": "Ignore this", "type": "dismiss", "plug_id": plug_id}


def rule_based_decision(context: dict) -> dict:
    """Template messages for the known triggers. No AI involved."""
    trigger = context["trigger"]
    messages = []

    if trigger["kind"] == "power_after_off":
        plug = next((p for p in context["plugs"] if p["device_id"] == trigger["device_id"]), None)
        label = _plug_label(plug)
        plug_id = plug["id"] if plug else None
        power = trigger["data"].get("power_w", 0)
        messages.append({
            "plug_id": plug_id,
            "kind": "power_after_off",
            "severity": "critical",
            "title": f"{label} just started drawing power",
            "body": f"{label} was off and is now drawing {power:.0f}W.",
            "actions": [
                {"label": "Turn off", "description": f"Switch {label} off", "type": "turn_off", "plug_id": plug_id},
                _dismiss(plug_id),
            ],
        })

    elif trigger["kind"] == "time_changed":
        already_sent = {(m["kind"], m["plug_id"]) for m in context["recent_messages"]}
        for plug in context["plugs"]:
            minutes = plug["drawing_power_minutes"]
            if minutes < LEFT_ON_MINUTES or ("left_on", plug["id"]) in already_sent:
                continue
            label = _plug_label(plug)
            hours = minutes / 60
            messages.append({
                "plug_id": plug["id"],
                "kind": "left_on",
                "severity": "critical",
                "title": f"{label} has been on for {hours:.0f}h",
                "body": f"{label} has been drawing power for about {hours:.1f} hours.",
                "actions": [
                    {"label": "Turn off", "description": f"Switch {label} off", "type": "turn_off", "plug_id": plug["id"]},
                    _dismiss(plug["id"]),
                ],
            })

    return {"reasoning": "rule-based", "messages": messages}


def decide(context: dict) -> dict:
    return call_claude(context) if USE_CLAUDE else rule_based_decision(context)


def _save_messages(session: Session, decision: dict) -> list[Message]:
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
        for a in item.get("actions", []):
            action_plug = valid_plug_ids.get(a.get("plug_id"))
            session.add(Action(
                message_id=message.id,
                label=a["label"],
                description=a["description"],
                type=a["type"] if a["type"] in ACTION_TYPES else "dismiss",
                plug_id=action_plug.id if action_plug else None,
            ))
        created.append(message)
    session.commit()
    for message in created:
        broadcaster.publish(message_payload(session, message))
    return created


def run(session: Session, trigger: Trigger) -> list[Message]:
    """Decide what to do about a trigger and save any messages. Never raises."""
    logger.info("run: %s", trigger.detail)
    try:
        decision = decide(build_context(session, trigger))
        created = _save_messages(session, decision)
    except Exception as exc:
        logger.error("run failed for %s: %r", trigger.kind, exc)
        return []
    logger.info("decided: %s (%d message(s))", decision.get("reasoning", ""), len(created))
    for m in created:
        logger.info("message: %s - %s", m.title, m.body)
    return created
