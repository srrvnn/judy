from datetime import datetime, timedelta

from sqlmodel import select

from judy.run import PROMPT_PATH, SYSTEM_PROMPT, build_context, run
from judy.trigger import Trigger
from models import Household, Message, Plug, Reading
from services.clock import clock, now


def make_plug(session, name="Lamp"):
    household = Household(name="Default household")
    session.add(household)
    session.flush()
    plug = Plug(household_id=household.id, device_id="abc", name=name, model="EP25", host="h", has_energy=True)
    session.add(plug)
    session.commit()
    session.refresh(plug)
    return plug


def test_prompt_is_loaded_from_the_markdown_file():
    assert PROMPT_PATH.name == "prompt.md"
    assert SYSTEM_PROMPT.startswith("# Judy")
    assert "afternoon_power_down" in SYSTEM_PROMPT and "16:00" in SYSTEM_PROMPT
    assert "power_after_off" not in SYSTEM_PROMPT  # the power-back-on message was only a test
    assert "drawing power after being off" not in SYSTEM_PROMPT


def test_context_carries_local_time_for_the_4pm_rule(session):
    make_plug(session)
    local = datetime(2030, 3, 4, 16, 5).astimezone()
    clock.set(local)
    context = build_context(session, Trigger(kind="time_changed", detail="x"))
    assert context["local_time"] == "16:05"
    assert context["local_date"] == "2030-03-04"
    assert context["weekday"] == "Monday"
    assert context["timezone"]


def test_recent_messages_use_local_time(session):
    plug = make_plug(session)
    session.add(Message(household_id=plug.household_id, kind="afternoon_power_down", title="t", body="b"))
    session.commit()
    context = build_context(session, Trigger(kind="time_changed", detail="x"))
    assert "created_at_local" in context["recent_messages"][0]


def test_claude_decides_the_message_and_actions(session, stub_claude):
    plug = make_plug(session, name="Desk lamp")
    session.add(Reading(plug_id=plug.id, recorded_at=now() - timedelta(minutes=90), was_on=True, power_w=9.0))
    session.commit()
    stub_claude.decision["messages"] = [{
        "plug_id": None, "kind": "afternoon_power_down", "severity": "critical",
        "title": "It's 4 pm", "body": "Desk lamp has been on for 90 minutes.",
        "actions": [
            {"label": "Turn off Desk lamp", "description": "Switch it off", "type": "turn_off", "plug_id": plug.id},
            {"label": "Dismiss", "description": "Ignore this", "type": "dismiss", "plug_id": None},
        ],
    }]
    created = run(session, Trigger(kind="time_changed", detail="the clock was moved to 16:00"))
    assert [m.kind for m in created] == ["afternoon_power_down"]
    assert stub_claude.calls[0]["trigger"]["kind"] == "time_changed"


def test_turning_claude_off_sends_nothing(session, stub_claude, monkeypatch):
    make_plug(session)
    monkeypatch.setattr("judy.run.USE_CLAUDE", False)
    assert run(session, Trigger(kind="time_changed", detail="x")) == []
    assert stub_claude.calls == []


def test_claude_failure_sends_nothing_for_time_triggers(session, monkeypatch):
    make_plug(session)
    monkeypatch.setattr("judy.run.call_claude", lambda ctx: (_ for _ in ()).throw(RuntimeError("down")))
    assert run(session, Trigger(kind="time_changed", detail="x")) == []
    assert session.exec(select(Message)).all() == []
