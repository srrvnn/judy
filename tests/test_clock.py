from datetime import datetime, timedelta, timezone


def test_get_clock_real_time(client):
    body = client.get("/v1/clock").json()
    assert body["simulated"] is False
    assert body["offset_seconds"] == 0


def test_advance_moves_time_and_calls_judy(client, stub_claude):
    body = client.put("/v1/clock", json={"advance_minutes": 360}).json()
    assert body["simulated"] is True
    assert abs(body["offset_seconds"] - 6 * 3600) < 5
    assert len(stub_claude.calls) == 1
    assert stub_claude.calls[0]["trigger"]["kind"] == "time_changed"


def test_set_exact_time(client, stub_claude):
    target = datetime(2030, 1, 2, 3, 0, tzinfo=timezone.utc)
    body = client.put("/v1/clock", json={"now": target.isoformat()}).json()
    assert abs(datetime.fromisoformat(body["now"]) - target) < timedelta(seconds=5)
    assert stub_claude.calls[0]["now"].startswith("2030-01-02T03:00")


def test_reset_returns_to_real_time_and_calls_judy(client, stub_claude):
    client.put("/v1/clock", json={"advance_minutes": 60})
    body = client.post("/v1/clock/reset").json()
    assert body["simulated"] is False
    assert [c["trigger"]["kind"] for c in stub_claude.calls] == ["time_changed", "time_changed"]


def test_requires_exactly_one_field(client):
    assert client.put("/v1/clock", json={}).status_code == 422
    both = {"now": "2030-01-01T00:00:00Z", "advance_minutes": 5}
    assert client.put("/v1/clock", json=both).status_code == 422


def test_clock_failure_in_judy_does_not_break_endpoint(client, monkeypatch):
    def boom(context):
        raise RuntimeError("no api key")
    monkeypatch.setattr("judy.run.call_claude", boom)
    response = client.put("/v1/clock", json={"advance_minutes": 5})
    assert response.status_code == 200
    assert response.json()["messages_created"] == 0
