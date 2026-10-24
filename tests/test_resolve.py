from models import Household, Message
from services.messages import resolve_message


def make_message(session, severity="critical"):
    household = Household(name="Default household")
    session.add(household)
    session.flush()
    message = Message(household_id=household.id, kind="left_on", severity=severity, title="Heater left on", body="b")
    session.add(message)
    session.commit()
    session.refresh(message)
    return message


def test_resolve_marks_message_info_and_records_who(session):
    message = make_message(session)
    resolved = resolve_message(session, message.id, by="judy")
    assert resolved.severity == "info"
    assert resolved.resolved_by == "judy"
    assert resolved.resolved_at is not None


def test_resolve_sends_nothing_over_the_stream(session, monkeypatch):
    message = make_message(session)
    published = []
    monkeypatch.setattr("services.events.broadcaster.publish", lambda payload, event="message": published.append(event))
    resolve_message(session, message.id, by="user")
    assert published == []


def test_resolving_twice_or_unknown_does_nothing(session):
    message = make_message(session)
    assert resolve_message(session, message.id, by="user") is not None
    assert resolve_message(session, message.id, by="judy") is None
    assert resolve_message(session, 999, by="user") is None
    assert session.get(Message, message.id).resolved_by == "user"


def test_messages_api_reports_resolution(client, session):
    message = make_message(session)
    resolve_message(session, message.id, by="judy")
    body = client.get("/v1/messages").json()[0]
    assert body["severity"] == "info" and body["resolved_by"] == "judy" and body["resolved_at"]

