from types import SimpleNamespace

from kasa import Module
from services.heuristics import PowerAfterOffDetector


def fake_device(power, is_on=True, device_id="abc"):
    energy = SimpleNamespace(current_consumption=power)
    return SimpleNamespace(
        alias="Heater", model="EP25", host="10.0.0.2",
        device_id=device_id, is_on=is_on, modules={Module.Energy: energy},
    )


def test_first_poll_never_fires():
    detector = PowerAfterOffDetector(threshold_w=1.0)
    assert detector.check([fake_device(50.0)]) == []


def test_fires_when_power_appears_after_off():
    detector = PowerAfterOffDetector(threshold_w=1.0)
    detector.check([fake_device(0.0, is_on=False)])
    triggers = detector.check([fake_device(50.0)])
    assert [t.kind for t in triggers] == ["power_after_off"]
    assert triggers[0].power_w == 50.0


def test_fires_once_per_transition():
    detector = PowerAfterOffDetector(threshold_w=1.0)
    detector.check([fake_device(0.0, is_on=False)])
    assert len(detector.check([fake_device(50.0)])) == 1
    assert detector.check([fake_device(55.0)]) == []


def test_idle_draw_below_threshold_does_not_fire():
    detector = PowerAfterOffDetector(threshold_w=1.0)
    detector.check([fake_device(0.0, is_on=False)])
    assert detector.check([fake_device(0.4)]) == []


def test_fires_again_after_another_off_cycle():
    detector = PowerAfterOffDetector(threshold_w=1.0)
    detector.check([fake_device(0.0, is_on=False)])
    detector.check([fake_device(50.0)])
    detector.check([fake_device(0.0, is_on=False)])
    assert len(detector.check([fake_device(50.0)])) == 1


def test_unmetered_plug_is_ignored():
    detector = PowerAfterOffDetector()
    device = SimpleNamespace(alias="x", model="HS103", host="h", device_id="z", is_on=True, modules={})
    assert detector.check([device]) == []
    assert detector.check([device]) == []
