import asyncio
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from uvicorn.logging import DefaultFormatter

from api.actions import router as actions_router
from api.clock import router as clock_router
from api.events import router as events_router
from api.messages import router as messages_router
from api.panel import router as panel_router
from api.plugs import router as plugs_router
from services.kasa_poller import poll_forever

# uvicorn only configures its own loggers; reuse its colored formatter for ours
_handler = logging.StreamHandler()
_handler.setFormatter(DefaultFormatter(fmt="%(levelprefix)s %(message)s"))
logging.basicConfig(level=logging.INFO, handlers=[_handler])

# --- LIFESPAN AND APP SETUP ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(poll_forever())
    try:
        yield
    finally:
        task.cancel()

# Create the application instance named 'api'
api = FastAPI(lifespan=lifespan)

# Demo: allow any origin (e.g. a Lovable app). Set CORS_ORIGINS=a,b to restrict.
api.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)

@api.get("/v1", response_class=PlainTextResponse)
def get_hello():
    return "Hello from Judy API!\n"

api.include_router(plugs_router, prefix="/v1")
api.include_router(clock_router, prefix="/v1")
api.include_router(messages_router, prefix="/v1")
api.include_router(events_router, prefix="/v1")
api.include_router(actions_router, prefix="/v1")
api.include_router(panel_router)
