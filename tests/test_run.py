from datetime import timedelta

from sqlmodel import select

from judy.run import build_context, run
from judy.trigger import Trigger
from models import Action, Household, Message, Plug, Reading
from services.clock import now


def make_plug(session, name="Heater"):
    household = Household(name="Default household")
    session.add(household)
    session.flush()
    plug = Plug(household_id=household.id, device_id="abc", name=name, model="EP25", host="10.0.0.2", has_energy=True)
    session.add(plug)
    session.commit()
    session.refresh(plug)
    return plug


def add_reading(session, plug, minutes_ago, power, was_on=True):
    session.add(Reading(plug_id=plug.id, recorded_at=now() - timedelta(minutes=minutes_ago), was_on=was_on, power_w=power))
    session.commit()


def test_context_reports_how_long_a_plug_has_been_drawing_power(session):
    plug = make_plug(session)
    add_reading(session, plug, 300, 0.0, was_on=False)
    add_reading(session, plug, 240, 40.0)
    add_reading(session, plug, 120, 41.0)
    add_reading(session, plug, 1, 42.0)
    context = build_context(session, Trigger(kind="time_changed", detail="x"))
    info = context["plugs"][0]
    assert info["name"] == "Heater"
    assert 239 <= info["drawing_power_minutes"] <= 241
    assert info["latest_reading"]["power_w"] == 42.0


def test_run_saves_messages_and_actions(session, stub_claude):
    plug = make_plug(session)
    stub_claude.decision["messages"] = [{
        "plug_id": plug.id, "kind": "left_on", "title": "Heater left on",
        "body": "The heater has been on for 4 hours.",
        "actions": [
            {"label": "Turn off", "description": "Switch the heater off", "type": "turn_off", "plug_id": plug.id},
            {"label": "Dismiss", "description": "Ignore this", "type": "dismiss", "plug_id": None},
        ],
    }]
    created = run(session, Trigger(kind="power_after_off", detail="heater drawing power", device_id="abc"))
    assert len(created) == 1
    message = session.exec(select(Message)).one()
    assert message.household_id == plug.household_id and message.plug_id == plug.id
    actions = session.exec(select(Action).order_by(Action.id)).all()
    assert [a.type for a in actions] == ["turn_off", "dismiss"]
    assert all(a.status == "suggested" for a in actions)


def test_run_with_no_messages_saves_nothing(session):
    make_plug(session)
    assert run(session, Trigger(kind="time_changed", detail="x")) == []
    assert session.exec(select(Message)).all() == []


def test_run_ignores_unknown_plug_ids(session, stub_claude):
    plug = make_plug(session)
    stub_claude.decision["messages"] = [{
        "plug_id": 999, "kind": "k", "title": "t", "body": "b",
        "actions": [{"label": "Turn off", "description": "d", "type": "turn_off", "plug_id": 999}],
    }]
    run(session, Trigger(kind="time_changed", detail="x"))
    message = session.exec(select(Message)).one()
    assert message.plug_id is None and message.household_id == plug.household_id
    assert session.exec(select(Action)).one().plug_id is None


def test_run_never_raises(session, monkeypatch):
    monkeypatch.setattr("judy.run.call_claude", lambda ctx: (_ for _ in ()).throw(RuntimeError("down")))
    assert run(session, Trigger(kind="time_changed", detail="x")) == []


def test_run_includes_recent_messages_in_context(session, stub_claude):
    plug = make_plug(session)
    session.add(Message(household_id=plug.household_id, plug_id=plug.id, kind="left_on", title="Heater left on", body="b"))
    session.commit()
    run(session, Trigger(kind="time_changed", detail="x"))
    assert stub_claude.calls[0]["recent_messages"][0]["title"] == "Heater left on"
