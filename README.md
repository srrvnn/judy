# Judy

Judy helps you be judicious with power.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Running the Server

```bash
uvicorn server:api --reload
```

The server starts on `http://127.0.0.1:8000`. Try `GET /v1`.
Interactive docs are at `/docs` and `/redoc`.

## Tests

```bash
pytest
```

## Kasa plug polling

On startup the server polls the local network for TP-Link Kasa plugs
(via [python-kasa](https://github.com/python-kasa/python-kasa)) every 5 seconds
and prints what it finds. Set `KASA_POLL_INTERVAL` (seconds) to change the interval.

## Control panel and judy.run

Open `/panel` for a control panel with a global clock you can move forward, set
to an exact time, or reset. Moving the clock, and any heuristic firing on a new
reading (e.g. a plug drawing power after being off), calls `judy.run`
(`judy/run.py`), which asks Claude whether to send the household a message with
suggested actions. Set `ANTHROPIC_API_KEY` in `.env`. The clock offset is kept in
memory and resets when the server restarts.

## Live messages (SSE)

`GET /v1/events` streams new messages as server-sent events (`event: message`,
`id:` = message id, `data:` = the same JSON as `GET /v1/messages`). A keep-alive
comment is sent every 15 seconds. On reconnect the browser sends `Last-Event-ID`
and anything newer is replayed; `?after=<id>` does the same manually.

```bash
curl -N http://127.0.0.1:8000/v1/events
```
