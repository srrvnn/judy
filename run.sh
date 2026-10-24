#!/bin/sh
# Start the server. The graceful-shutdown timeout makes Ctrl+C work even while
# live SSE streams are open (otherwise uvicorn waits for them to close forever).
# Extra args pass through, e.g. ./run.sh --reload
cd "$(dirname "$0")" && . .venv/bin/activate && exec uvicorn server:api --timeout-graceful-shutdown 3 "$@"
