from models import Household, Plug


def make_plug(session, name=None):
    household = Household(name="Default household")
    session.add(household)
    session.flush()
    plug = Plug(household_id=household.id, device_id="abc", name=name, model="EP25", host="10.0.0.2")
    session.add(plug)
    session.commit()
    session.refresh(plug)
    return plug


def test_list_plugs(client, session):
    make_plug(session)
    response = client.get("/v1/plugs")
    assert response.status_code == 200
    assert [p["device_id"] for p in response.json()] == ["abc"]


def test_get_plug(client, session):
    plug = make_plug(session)
    response = client.get(f"/v1/plugs/{plug.id}")
    assert response.status_code == 200
    assert response.json()["name"] is None


def test_get_missing_plug_404(client):
    assert client.get("/v1/plugs/999").status_code == 404


def test_patch_updates_only_name(client, session):
    plug = make_plug(session)
    response = client.patch(f"/v1/plugs/{plug.id}", json={"name": "  Heater "})
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Heater"
    assert body["host"] == "10.0.0.2" and body["model"] == "EP25"


def test_patch_ignores_other_fields(client, session):
    plug = make_plug(session)
    response = client.patch(f"/v1/plugs/{plug.id}", json={"name": "Heater", "host": "evil"})
    assert response.json()["host"] == "10.0.0.2"


def test_patch_rejects_empty_name(client, session):
    plug = make_plug(session)
    assert client.patch(f"/v1/plugs/{plug.id}", json={"name": "  "}).status_code == 422


def test_no_delete(client, session):
    plug = make_plug(session)
    assert client.delete(f"/v1/plugs/{plug.id}").status_code == 405
