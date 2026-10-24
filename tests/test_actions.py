import pytest
from sqlmodel import select

from models import Action, Household, Message, Plug, User
from server import api
from services.plug_control import PlugControlError, get_controller


class FakeController:
    def __init__(self, error=None):
        self.calls = []
        self.error = error

    def switch(self, plug, on):
        self.calls.append((plug.id, on))
        if self.error:
            raise PlugControlError(self.error)
        return f"{plug.name} turned {'on' if on else 'off'}"


@pytest.fixture
def controller():
    fake = FakeController()
    api.dependency_overrides[get_controller] = lambda: fake
    yield fake
    api.dependency_overrides.pop(get_controller, None)


def make_message(session):
    household = Household(name="Default household")
    session.add(household)
    session.flush()
    session.add(User(household_id=household.id, name="Default user"))
    plug = Plug(household_id=household.id, device_id="abc", name="Heater", model="EP25", host="10.0.0.2")
    session.add(plug)
    session.flush()
    message = Message(household_id=household.id, plug_id=plug.id, kind="left_on", severity="critical", title="t", body="b")
    session.add(message)
    session.flush()
    off = Action(message_id=message.id, label="Turn off", description="d", type="turn_off", plug_id=plug.id)
    dismiss = Action(message_id=message.id, label="Dismiss", description="d", type="dismiss")
    session.add(off)
    session.add(dismiss)
    session.commit()
    return message, off, dismiss, plug


def by_id(body):
    return {a["id"]: a for a in body["actions"]}


def test_turn_off_switches_plug_and_resolves_message(client, session, controller):
    message, off, dismiss, plug = make_message(session)
    response = client.post(f"/v1/actions/{off.id}/choose")
    assert response.status_code == 200
    body = response.json()
    assert controller.calls == [(plug.id, False)]
    assert by_id(body)[off.id]["status"] == "executed"
    assert by_id(body)[off.id]["result"] == "Heater turned off"
    assert by_id(body)[dismiss.id]["status"] == "expired"
    assert body["severity"] == "info" and body["resolved_by"] == "user" and body["resolved_at"]
    session.expire_all()
    chosen = session.get(Action, off.id)
    assert chosen.chosen_by_user_id == session.exec(select(User)).one().id
    assert chosen.chosen_at and chosen.executed_at


def test_turn_on_calls_controller_with_on(client, session, controller):
    message, off, dismiss, plug = make_message(session)
    on = Action(message_id=message.id, label="Turn on", description="d", type="turn_on", plug_id=plug.id)
    session.add(on)
    session.commit()
    client.post(f"/v1/actions/{on.id}/choose")
    assert controller.calls == [(plug.id, True)]


def test_dismiss_resolves_without_touching_the_plug(client, session, controller):
    message, off, dismiss, plug = make_message(session)
    body = client.post(f"/v1/actions/{dismiss.id}/choose").json()
    assert controller.calls == []
    assert by_id(body)[dismiss.id]["status"] == "executed"
    assert body["severity"] == "info"


def test_failed_switch_keeps_message_open_and_can_retry(client, session):
    fake = FakeController(error="could not find Heater on the network")
    api.dependency_overrides[get_controller] = lambda: fake
    try:
        message, off, dismiss, plug = make_message(session)
        body = client.post(f"/v1/actions/{off.id}/choose").json()
        assert by_id(body)[off.id]["status"] == "failed"
        assert "could not find" in by_id(body)[off.id]["result"]
        assert body["severity"] == "critical" and body["resolved_at"] is None
        assert by_id(body)[dismiss.id]["status"] == "suggested"

        fake.error = None  # plug is reachable now
        retry = client.post(f"/v1/actions/{off.id}/choose").json()
        assert by_id(retry)[off.id]["status"] == "executed"
        assert retry["severity"] == "info"
    finally:
        api.dependency_overrides.pop(get_controller, None)


def test_choosing_twice_is_a_conflict(client, session, controller):
    message, off, dismiss, plug = make_message(session)
    assert client.post(f"/v1/actions/{off.id}/choose").status_code == 200
    assert client.post(f"/v1/actions/{off.id}/choose").status_code == 409
    assert client.post(f"/v1/actions/{dismiss.id}/choose").status_code == 409  # message already handled
    assert controller.calls == [(plug.id, False)]


def test_unknown_action_404(client, controller):
    assert client.post("/v1/actions/999/choose").status_code == 404


def test_action_without_a_plug_fails_cleanly(client, session, controller):
    message, off, dismiss, plug = make_message(session)
    off.plug_id = None
    session.add(off)
    session.commit()
    body = client.post(f"/v1/actions/{off.id}/choose").json()
    assert by_id(body)[off.id]["status"] == "failed"
    assert controller.calls == []


def test_choosing_an_action_sends_nothing_over_the_stream(client, session, controller, monkeypatch):
    message, off, dismiss, plug = make_message(session)
    published = []
    monkeypatch.setattr("services.events.broadcaster.publish", lambda payload, event="message": published.append(event))
    client.post(f"/v1/actions/{off.id}/choose")
    assert published == []


def test_dry_run_never_connects(monkeypatch):
    from services import plug_control

    monkeypatch.setattr(plug_control, "DRY_RUN", True)
    monkeypatch.setattr(plug_control, "_set_power", lambda *a, **k: (_ for _ in ()).throw(AssertionError("connected")))
    plug = Plug(id=1, household_id=1, device_id="abc", name="Heater", model="EP25", host="10.0.0.2")
    assert "dry run" in plug_control.PlugController().switch(plug, on=False)
