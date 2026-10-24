from datetime import timedelta

import pytest
from sqlmodel import select

from judy.run import SYSTEM_PROMPT, build_context, run
from judy.trigger import Trigger
from models import Action, Household, Message, Plug, User
from services.actions import choose_action
from services.clock import now
from services.plug_control import PlugControlError


class FakeController:
    def __init__(self, error=None):
        self.calls = []
        self.error = error

    def switch(self, plug, on):
        self.calls.append((plug.id, on))
        if self.error:
            raise PlugControlError(self.error)
        return f"{plug.name} turned {'on' if on else 'off'}"


def make_plug(session, name="Laptop", device_id="abc"):
    household = session.exec(select(Household)).first()
    if household is None:
        household = Household(name="Default household")
        session.add(household)
        session.flush()
        session.add(User(household_id=household.id, name="Default user"))
    plug = Plug(household_id=household.id, device_id=device_id, name=name, model="EP25", host="h")
    session.add(plug)
    session.commit()
    session.refresh(plug)
    return plug


def record_action(session, plug, type_, hours_ago, status="executed"):
    message = Message(household_id=plug.household_id, plug_id=plug.id, kind="afternoon_power_down", title="t", body="b")
    session.add(message)
    session.flush()
    action = Action(message_id=message.id, label="x", description="d", type=type_, plug_id=plug.id, status=status,
                    executed_at=now() - timedelta(hours=hours_ago) if status == "executed" else None)
    session.add(action)
    session.commit()
    return action


def trigger():
    return Trigger(kind="time_changed", detail="the clock was moved to 21:00")


def evening_decision(plug_id, automatic=True, type_="turn_on"):
    return {"reasoning": "9 pm", "messages": [{
        "plug_id": plug_id, "kind": "evening_power_up", "severity": "info",
        "title": "It's 9 pm", "body": "I turned the Laptop back on.",
        "actions": [
            {"label": "Turn on Laptop", "description": "Back on", "type": type_, "plug_id": plug_id, "automatic": automatic},
            {"label": "Dismiss", "description": "Ignore", "type": "dismiss", "plug_id": None, "automatic": False},
        ],
    }]}


def listed(session):
    return [e["plug_id"] for e in build_context(session, trigger())["switched_off_by_judy"]]


# --- what Claude is told Judy switched off

def test_plug_turned_off_through_an_action_is_listed(session):
    plug = make_plug(session)
    record_action(session, plug, "turn_off", hours_ago=5)
    entries = build_context(session, trigger())["switched_off_by_judy"]
    assert [e["plug_id"] for e in entries] == [plug.id] and entries[0]["name"] == "Laptop"
    assert entries[0]["switched_off_at_local"]


def test_a_plug_nobody_switched_off_through_judy_is_not_listed(session):
    make_plug(session)  # off or on by hand: no executed action exists
    assert listed(session) == []


def test_plug_turned_back_on_is_no_longer_listed(session):
    plug = make_plug(session)
    record_action(session, plug, "turn_off", hours_ago=5)
    record_action(session, plug, "turn_on", hours_ago=2)
    assert listed(session) == []


def test_old_or_unfinished_turn_offs_are_not_listed(session):
    plug = make_plug(session)
    record_action(session, plug, "turn_off", hours_ago=30)  # older than a day
    other = make_plug(session, name="Lamp", device_id="def")
    record_action(session, other, "turn_off", hours_ago=1, status="failed")
    record_action(session, other, "turn_off", hours_ago=1, status="suggested")
    assert listed(session) == []


# --- running automatic actions

def test_automatic_turn_on_runs_and_resolves_the_message_as_judy(session, stub_claude):
    plug = make_plug(session)
    record_action(session, plug, "turn_off", hours_ago=5)
    stub_claude.decision.update(evening_decision(plug.id))
    fake = FakeController()
    created = run(session, trigger(), controller=fake)
    assert fake.calls == [(plug.id, True)]
    message = session.get(Message, created[0].id)
    assert message.kind == "evening_power_up"
    assert message.severity == "info" and message.resolved_by == "judy" and message.resolved_at
    actions = {a.type: a for a in session.exec(select(Action).where(Action.message_id == message.id)).all()}
    assert actions["turn_on"].status == "executed" and actions["turn_on"].result == "Laptop turned on"
    assert actions["dismiss"].status == "expired"
    assert stub_claude.calls[0]["switched_off_by_judy"][0]["plug_id"] == plug.id


def test_automatic_turn_on_for_a_plug_judy_did_not_switch_off_is_refused(session, stub_claude):
    plug = make_plug(session)  # never switched off through Judy
    stub_claude.decision.update(evening_decision(plug.id))
    fake = FakeController()
    created = run(session, trigger(), controller=fake)
    assert fake.calls == []
    turn_on = session.exec(select(Action).where(Action.type == "turn_on")).one()
    assert turn_on.status == "suggested"
    assert session.get(Message, created[0].id).resolved_at is None


def test_automatic_is_only_ever_allowed_for_turn_on(session, stub_claude):
    plug = make_plug(session)
    record_action(session, plug, "turn_off", hours_ago=5)
    stub_claude.decision.update(evening_decision(plug.id, type_="turn_off"))
    fake = FakeController()
    run(session, trigger(), controller=fake)
    assert fake.calls == []


def test_plain_suggestions_are_never_run_without_a_tap(session, stub_claude):
    plug = make_plug(session)
    record_action(session, plug, "turn_off", hours_ago=5)
    stub_claude.decision.update(evening_decision(plug.id, automatic=False))
    fake = FakeController()
    run(session, trigger(), controller=fake)
    assert fake.calls == []


def test_failed_automatic_turn_on_becomes_a_critical_message_that_can_be_retried(session, stub_claude):
    plug = make_plug(session)
    record_action(session, plug, "turn_off", hours_ago=5)
    stub_claude.decision.update(evening_decision(plug.id))
    created = run(session, trigger(), controller=FakeController(error="could not find Laptop on the network"))
    message = session.get(Message, created[0].id)
    assert message.severity == "critical" and message.resolved_at is None
    assert message.title == "Couldn't turn Laptop back on" and "could not find" in message.body
    turn_on = session.exec(select(Action).where(Action.type == "turn_on", Action.message_id == message.id)).one()
    assert turn_on.status == "failed"

    retry = FakeController()  # the plug is reachable now; the household taps the button
    body = choose_action(session, turn_on.id, retry)
    assert retry.calls == [(plug.id, True)]
    assert body["resolved_by"] == "user"


def test_automatic_run_is_published_as_a_resolved_info_message(session, stub_claude, monkeypatch):
    plug = make_plug(session)
    record_action(session, plug, "turn_off", hours_ago=5)
    stub_claude.decision.update(evening_decision(plug.id))
    published = []
    monkeypatch.setattr("judy.run.broadcaster.publish", published.append)
    run(session, trigger(), controller=FakeController())
    assert len(published) == 1
    assert published[0]["severity"] == "info" and published[0]["resolved_by"] == "judy"


def test_prompt_describes_the_nine_pm_rule():
    assert "evening_power_up" in SYSTEM_PROMPT and "21:00" in SYSTEM_PROMPT
    assert "switched_off_by_judy" in SYSTEM_PROMPT and "automatic" in SYSTEM_PROMPT
