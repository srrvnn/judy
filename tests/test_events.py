import asyncio
import json
import threading

from judy.run import run
from judy.trigger import Trigger
from models import Household, Message, Plug
from services.events import Broadcaster, event_stream, format_event, mock_message


def payload(id_, title="t"):
    return {"id": id_, "title": title, "actions": []}


def parse(chunk: str) -> dict:
    fields = dict(line.split(": ", 1) for line in chunk.strip().splitlines())
    return {"id": int(fields["id"]), "event": fields["event"], "data": json.loads(fields["data"])}


def test_format_event_is_valid_sse():
    chunk = format_event(payload(7, "Heater"))
    assert chunk.endswith("\n\n")
    event = parse(chunk)
    assert event["id"] == 7 and event["event"] == "message" and event["data"]["title"] == "Heater"


def test_stream_replays_then_streams_live_without_duplicates():
    async def scenario():
        bus = Broadcaster()
        queue = bus.subscribe()
        stream = event_stream(queue, replay=[payload(1), payload(2)], heartbeat=5, bus=bus)
        assert (await anext(stream)).startswith("retry:")
        assert parse(await anext(stream))["id"] == 1
        assert parse(await anext(stream))["id"] == 2
        bus.publish(payload(2))  # also arrived during replay: must be skipped
        bus.publish(payload(3))
        await asyncio.sleep(0)
        assert parse(await anext(stream))["id"] == 3
        await stream.aclose()
        return bus.subscriber_count

    assert asyncio.run(scenario()) == 0


def test_stream_sends_keepalive_when_idle():
    async def scenario():
        bus = Broadcaster()
        stream = event_stream(bus.subscribe(), replay=[], heartbeat=0.05, bus=bus)
        await anext(stream)  # retry hint
        chunk = await anext(stream)
        await stream.aclose()
        return chunk

    assert asyncio.run(scenario()).startswith(": keep-alive")


def test_publish_from_another_thread_reaches_subscriber():
    async def scenario():
        bus = Broadcaster()
        queue = bus.subscribe()
        threading.Thread(target=bus.publish, args=(payload(9),)).start()
        return await asyncio.wait_for(queue.get(), timeout=2)

    assert asyncio.run(scenario()) == ("message", payload(9))


def test_publish_with_no_subscribers_is_a_noop():
    Broadcaster().publish(payload(1))


def test_events_endpoint_streams_with_sse_headers(client, monkeypatch):
    async def finite_stream(queue, replay, **kwargs):
        yield format_event(payload(1, "hello"))

    monkeypatch.setattr("api.events.event_stream", finite_stream)
    response = client.get("/v1/events")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache"
    assert "hello" in response.text


def test_events_endpoint_replays_messages_after_last_event_id(client, session, monkeypatch):
    household = Household(name="Default household")
    session.add(household)
    session.flush()
    for title in ("one", "two", "three"):
        session.add(Message(household_id=household.id, kind="k", title=title, body="b"))
    session.commit()

    seen = {}

    async def capture(queue, replay, **kwargs):
        seen["titles"] = [p["title"] for p in replay]
        yield ""

    monkeypatch.setattr("api.events.event_stream", capture)
    client.get("/v1/events", headers={"Last-Event-ID": "1"})
    assert seen["titles"] == ["two", "three"]

    client.get("/v1/events")
    assert seen["titles"] == []  # no id given: live messages only

    client.get("/v1/events?after=2")
    assert seen["titles"] == ["three"]


def test_judy_run_publishes_saved_messages(session, stub_claude, monkeypatch):
    household = Household(name="Default household")
    session.add(household)
    session.flush()
    plug = Plug(household_id=household.id, device_id="a", name="Heater", model="EP25", host="h")
    session.add(plug)
    session.commit()
    stub_claude.decision["messages"] = [{
        "plug_id": plug.id, "kind": "left_on", "title": "Heater left on", "body": "b",
        "actions": [{"label": "Turn off", "description": "d", "type": "turn_off", "plug_id": plug.id}],
    }]
    published = []
    monkeypatch.setattr("judy.run.broadcaster.publish", published.append)
    run(session, Trigger(kind="time_changed", detail="x"))
    assert [p["title"] for p in published] == ["Heater left on"]
    assert published[0]["actions"][0]["label"] == "Turn off"


def test_publish_survives_a_closed_event_loop():
    bus = Broadcaster()

    async def subscribe_then_exit():
        bus.subscribe()

    asyncio.run(subscribe_then_exit())  # loop is closed once this returns
    bus.publish(payload(1))  # must not raise
    assert bus.subscriber_count == 0


def test_mock_message_is_sent_first_without_an_id():
    async def scenario():
        bus = Broadcaster()
        stream = event_stream(bus.subscribe(), replay=[payload(5)], heartbeat=5, bus=bus, mock=mock_message())
        await anext(stream)  # retry hint
        mock_chunk = await anext(stream)
        real_chunk = await anext(stream)
        await stream.aclose()
        return mock_chunk, real_chunk

    mock_chunk, real_chunk = asyncio.run(scenario())
    assert "id:" not in mock_chunk  # must not become the browser's Last-Event-ID
    data = json.loads(mock_chunk.split("data: ", 1)[1])
    assert data["mock"] is True and data["actions"][0]["label"] == "Turn off"
    assert data["severity"] == "critical"
    assert parse(real_chunk)["id"] == 5


def test_mock_does_not_suppress_real_messages_with_low_ids():
    async def scenario():
        bus = Broadcaster()
        queue = bus.subscribe()
        stream = event_stream(queue, replay=[], heartbeat=5, bus=bus, mock=mock_message())
        await anext(stream)
        await anext(stream)  # mock
        bus.publish(payload(1))
        await asyncio.sleep(0)
        chunk = await anext(stream)
        await stream.aclose()
        return chunk

    assert parse(asyncio.run(scenario()))["id"] == 1


def test_endpoint_passes_mock_unless_disabled(client, monkeypatch):
    seen = []

    async def capture(queue, replay, mock=None, **kwargs):
        seen.append(mock)
        yield ""

    monkeypatch.setattr("api.events.event_stream", capture)
    client.get("/v1/events")
    monkeypatch.setattr("api.events.MOCK_ON_CONNECT", False)
    client.get("/v1/events")
    assert seen[0]["mock"] is True and seen[1] is None


def test_update_events_are_streamed_without_an_id():
    async def scenario():
        bus = Broadcaster()
        stream = event_stream(bus.subscribe(), replay=[], heartbeat=5, bus=bus)
        await anext(stream)
        bus.publish(payload(4, "handled"), event="message_updated")
        await asyncio.sleep(0)
        chunk = await anext(stream)
        bus.publish(payload(5))  # a later new message must still arrive
        await asyncio.sleep(0)
        following = await anext(stream)
        await stream.aclose()
        return chunk, following

    chunk, following = asyncio.run(scenario())
    assert chunk.startswith("event: message_updated")
    assert "id:" not in chunk  # must not become the browser's Last-Event-ID
    assert parse(following)["id"] == 5
