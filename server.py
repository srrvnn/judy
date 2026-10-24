import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from api.dashboard import router as dashboard_router
from api.plugs import router as plugs_router
from services.kasa_poller import poll_forever

WEB_DIR = Path(__file__).resolve().parent / "web"

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(poll_forever())
    try:
        yield
    finally:
        task.cancel()

api = FastAPI(title="Judy", description="Home energy monitoring API", lifespan=lifespan)

@api.get("/", include_in_schema=False)
def home():
    return FileResponse(WEB_DIR / "index.html")

@api.get("/manifest.webmanifest", include_in_schema=False)
def manifest():
    return FileResponse(WEB_DIR / "manifest.webmanifest", media_type="application/manifest+json")

@api.get("/service-worker.js", include_in_schema=True)
def service_worker():
    return FileResponse(WEB_DIR / "service-worker.js", media_type="application/javascript", headers={"Service-Worker-Allowed": "/"})

@api.get("/icon.svg", include_in_schema=False)
def app_icon():
    return FileResponse(WEB_DIR / "icon.svg", media_type="image/svg+xml")

@api.get("/v1", response_class=PlainTextResponse)
def get_hello():
    return "Hello from Judy API!\n"

api.include_router(plugs_router, prefix="/v1")
api.include_router(dashboard_router, prefix="/v1")
api.mount("/assets", StaticFiles(directory=WEB_DIR), name="assets")
