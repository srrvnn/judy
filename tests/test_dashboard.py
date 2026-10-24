from datetime import datetime, timedelta, timezone
from models import Household, Plug, Reading

def make_plug(session, name="Office heater", *, last_seen=None):
    household = Household(name="Default household")
    session.add(household)
    session.flush()
    plug = Plug(household_id=household.id, device_id="dashboard-device", name=name, model="EP25", host="10.0.0.2", has_energy=True, last_seen_at=last_seen or datetime.now(timezone.utc))
    session.add(plug)
    session.commit()
    session.refresh(plug)
    return plug

def test_dashboard_empty_inventory(client):
    response = client.get("/v1/dashboard")
    assert response.status_code == 200
    assert response.json()["source"] == "live"
    assert response.json()["devices"] == []
    assert response.json()["rate_per_kwh"] > 0

def test_dashboard_returns_latest_reading_and_hourly_cost(client, session, monkeypatch):
    monkeypatch.setenv("ENERGY_RATE_PER_KWH", "0.25")
    plug = make_plug(session)
    now = datetime.now(timezone.utc)
    session.add_all([Reading(plug_id=plug.id, recorded_at=now - timedelta(minutes=1), was_on=True, power_w=400), Reading(plug_id=plug.id, recorded_at=now, was_on=True, power_w=800, voltage_v=120, energy_today_kwh=1.2)])
    session.commit()
    response = client.get("/v1/dashboard")
    assert response.status_code == 200
    device = response.json()["devices"][0]
    assert device["name"] == "Office heater"
    assert device["online"] is True
    assert device["is_on"] is True
    assert device["power_w"] == 800
    assert device["voltage_v"] == 120
    assert device["energy_today_kwh"] == 1.2
    assert device["hourly_cost"] == 0.2

def test_dashboard_marks_stale_plug_offline(client, session):
    plug = make_plug(session, last_seen=datetime.now(timezone.utc) - timedelta(minutes=5))
    response = client.get("/v1/dashboard")
    assert response.status_code == 200
    assert response.json()["devices"][0]["id"] == plug.id
    assert response.json()["devices"][0]["online"] is False

def test_app_shell_and_assets_are_served(client):
    home = client.get("/")
    assert home.status_code == 200
    assert "Judy" in home.text
    assert client.get("/assets/app.js").status_code == 200
    assert client.get("/manifest.webmanifest").status_code == 200
    assert client.get("/service-worker.js").status_code == 200
