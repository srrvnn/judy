# Judy

Judy helps you be judicious with power.

## Judy prototype

The Judy dashboard is a responsive, installable web app for phone, tablet, and desktop browsers. It is served by the same FastAPI process as the Kasa device API, so it uses same-origin requests. The live API base is configured in the judy-api-base meta tag in web/index.html.

The app first reads the GET /v1/dashboard summary endpoint for current plug status, meter readings, and estimated hourly costs. Until that endpoint is deployed, it falls back to GET /v1/plugs and shows live device metadata; unavailable wattage and energy values remain blank rather than being invented. If no plugs are registered or the API is offline, clearly labeled sample data lets you explore Home, Devices, Usage, Messages, and Profile.

The demo alert and its pause buttons are visual previews only: the backend does not expose relay controls, and no real plug is switched by these buttons. Plug names can be edited through the existing PATCH /v1/plugs/{id} endpoint.

Set ENERGY_RATE_PER_KWH to your electricity price in dollars per kWh (defaults to 0.30). Displayed hourly costs are estimates based on the latest wattage reading and this configured rate. The online indicator uses the last-seen time with a window of at least 30 seconds.

## Setup

    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt

## Running the Server

    uvicorn server:api --reload

The server starts on http://127.0.0.1:8000. Open that URL for the Judy dashboard. The API hello endpoint is GET /v1; interactive API docs are at /docs and /redoc.

## Tests

    pytest

## Kasa plug polling

On startup the server polls the local network for TP-Link Kasa plugs (via python-kasa) every 5 seconds and prints what it finds. Set KASA_POLL_INTERVAL (seconds) to change the interval.
