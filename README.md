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
./run.sh            # or ./run.sh --reload while editing
```

`run.sh` runs `uvicorn server:api --timeout-graceful-shutdown 3`. Without that flag,
Ctrl+C can hang while live `/v1/events` streams are open.

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
to an exact time, or reset. Moving or resetting the clock is the only thing that calls `judy.run`
(`judy/run.py`), which asks Claude whether to send the household a message with
suggested actions. Set `ANTHROPIC_API_KEY` in `.env`. Claude's instructions are in
`judy/prompt.md` (edit it, then restart). If Claude can't be reached, nothing is sent.
`JUDY_USE_CLAUDE=0` skips Claude. A plug drawing power after being off is detected and
logged, but no message is sent for it.

At 9 pm Claude turns plugs back on by itself, but only plugs that were switched off through one of
Judy's own suggested actions in the last 24 hours (`switched_off_by_judy`). It sends an `info`
message afterwards, resolved by Judy. Anything it marks `automatic` that isn't a `turn_on` of one
of those plugs is refused and left as a normal suggestion. The clock offset is kept in
memory and resets when the server restarts.

## Live messages (SSE)

`GET /v1/events` streams new messages as server-sent events (`event: message`,
`id:` = message id, `data:` = the same JSON as `GET /v1/messages`). A keep-alive
comment is sent every 15 seconds. On reconnect the browser sends `Last-Event-ID`
and anything newer is replayed; `?after=<id>` does the same manually.
Choosing an action sends nothing over the stream; the app gets the updated message from the
response to `POST /v1/actions/{id}/choose`.

```bash
curl -N http://127.0.0.1:8000/v1/events
```
