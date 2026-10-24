from types import SimpleNamespace

from sqlmodel import select

from kasa import Module
from models import Household, Plug, Reading, User
from services.store import save_plugs


def fake_device(alias, device_id="abc", is_on=True):
    energy = SimpleNamespace(
        current_consumption=40.0, voltage=120.0, current=0.3,
        consumption_today=0.5, consumption_total=12.0,
    )
    return SimpleNamespace(
        alias=alias, device_id=device_id, model="EP25", host="10.0.0.2",
        is_on=is_on, modules={Module.Energy: energy},
    )


def test_unnamed_plug_is_registered_without_readings(session):
    assert save_plugs(session, [fake_device("Kasa alias")]) == 0
    plug = session.exec(select(Plug)).one()
    assert plug.name is None
    assert len(session.exec(select(Household)).all()) == 1
    assert len(session.exec(select(User)).all()) == 1
    assert session.exec(select(Reading)).all() == []


def test_readings_start_once_plug_is_named(session):
    save_plugs(session, [fake_device(None)])
    plug = session.exec(select(Plug)).one()
    plug.name = "Heater"
    session.add(plug)
    session.commit()
    assert save_plugs(session, [fake_device(None)]) == 1
    assert len(session.exec(select(Reading)).all()) == 1
    assert session.exec(select(Plug)).one().name == "Heater"


def name_all_plugs(session, name="Heater"):
    for plug in session.exec(select(Plug)).all():
        plug.name = name
        session.add(plug)
    session.commit()


def test_new_plug_creates_household_user_plug(session):
    assert save_plugs(session, [fake_device("Heater")]) == 0
    plug = session.exec(select(Plug)).one()
    assert plug.name is None and plug.has_energy
    assert len(session.exec(select(Household)).all()) == 1
    assert len(session.exec(select(User)).all()) == 1
    name_all_plugs(session)
    save_plugs(session, [fake_device("Heater")])
    reading = session.exec(select(Reading)).one()
    assert reading.power_w == 40.0 and reading.was_on is True


def test_known_plug_adds_reading_without_new_household(session):
    save_plugs(session, [fake_device("Heater")])
    name_all_plugs(session)
    save_plugs(session, [fake_device("Heater")])
    save_plugs(session, [fake_device("Heater", is_on=False)])
    assert len(session.exec(select(Plug)).all()) == 1
    assert len(session.exec(select(Household)).all()) == 1
    assert len(session.exec(select(Reading)).all()) == 2


def test_new_plugs_share_one_household_and_user(session):
    save_plugs(session, [fake_device("Heater", "a"), fake_device("Lamp", "b")])
    assert len(session.exec(select(Plug)).all()) == 2
    assert len(session.exec(select(Household)).all()) == 1
    assert len(session.exec(select(User)).all()) == 1
    household_ids = {p.household_id for p in session.exec(select(Plug)).all()}
    assert len(household_ids) == 1
