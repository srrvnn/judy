from datetime import timedelta

import pytest
from sqlmodel import select

from judy.run import rule_based_decision, run
from judy.trigger import Trigger
from models import Action, Household, Message, Plug, Reading
from services.clock import now


@pytest.fixture(autouse=True)
def rule_based(monkeypatch, stub_claude):
    monkeypatch.setattr("judy.run.USE_CLAUDE", False)


def make_plug(session, name="Heater"):
    household = Household(name="Default household")
    session.add(household)
    session.flush()
    plug = Plug(household_id=household.id, device_id="abc", name=name, model="EP25", host="h", has_energy=True)
    session.add(plug)
    session.commit()
    session.refresh(plug)
    return plug


def power_trigger():
    return Trigger(kind="power_after_off", detail="d", device_id="abc", data={"power_w": 42.3})


def test_power_after_off_sends_a_message_without_calling_claude(session, stub_claude):
    plug = make_plug(session)
    created = run(session, power_trigger())
    assert stub_claude.calls == []
    assert len(created) == 1
    message = session.exec(select(Message)).one()
    assert message.kind == "power_after_off" and message.plug_id == plug.id
    assert message.severity == "critical"
    assert "Heater" in message.title and "42W" in message.body
    actions = session.exec(select(Action).order_by(Action.id)).all()
    assert [a.type for a in actions] == ["turn_off", "dismiss"]
    assert actions[0].plug_id == plug.id


def test_unnamed_plug_falls_back_to_model_name(session):
    make_plug(session, name=None)
    run(session, power_trigger())
    assert "EP25" in session.exec(select(Message)).one().title


def test_unknown_device_still_sends_a_message(session):
    make_plug(session)
    trigger = Trigger(kind="power_after_off", detail="d", device_id="nope", data={"power_w": 5})
    assert len(run(session, trigger)) == 1


def test_time_change_flags_plug_that_has_been_on_a_long_time(session):
    plug = make_plug(session)
    session.add(Reading(plug_id=plug.id, recorded_at=now() - timedelta(hours=5), was_on=True, power_w=40.0))
    session.add(Reading(plug_id=plug.id, recorded_at=now() - timedelta(minutes=1), was_on=True, power_w=40.0))
    session.commit()
    created = run(session, Trigger(kind="time_changed", detail="x"))
    assert [m.kind for m in created] == ["left_on"]
    assert created[0].severity == "critical"
    assert "5h" in created[0].title


def test_time_change_does_not_repeat_left_on_message(session):
    plug = make_plug(session)
    session.add(Reading(plug_id=plug.id, recorded_at=now() - timedelta(hours=5), was_on=True, power_w=40.0))
    session.commit()
    run(session, Trigger(kind="time_changed", detail="x"))
    assert run(session, Trigger(kind="time_changed", detail="x")) == []


def test_time_change_ignores_plug_that_is_not_drawing_power(session):
    plug = make_plug(session)
    session.add(Reading(plug_id=plug.id, recorded_at=now() - timedelta(hours=5), was_on=False, power_w=0.0))
    session.commit()
    assert run(session, Trigger(kind="time_changed", detail="x")) == []


def test_rule_based_decision_is_pure_data():
    decision = rule_based_decision({"trigger": {"kind": "other", "data": {}}, "plugs": [], "recent_messages": []})
    assert decision["messages"] == []
