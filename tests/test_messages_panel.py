from models import Action, Household, Message


def test_list_messages_with_actions(client, session):
    household = Household(name="Default household")
    session.add(household)
    session.flush()
    message = Message(household_id=household.id, kind="left_on", title="Heater left on", body="b")
    session.add(message)
    session.flush()
    session.add(Action(message_id=message.id, label="Turn off", description="d", type="turn_off"))
    session.commit()
    body = client.get("/v1/messages").json()
    assert body[0]["title"] == "Heater left on"
    assert body[0]["actions"][0]["label"] == "Turn off"
    assert body[0]["actions"][0]["status"] == "suggested"


def test_panel_page_is_served(client):
    response = client.get("/panel")
    assert response.status_code == 200
    assert "Judy control panel" in response.text
