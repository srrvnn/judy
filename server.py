import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

from services.kasa_poller import poll_forever

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

@api.get("/v1", response_class=PlainTextResponse)
def get_hello():
    return "Hello from Judy API!\n"
