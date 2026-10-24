from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

PANEL_HTML = Path(__file__).with_name("panel.html")


@router.get("/panel", response_class=HTMLResponse)
def panel():
    return PANEL_HTML.read_text()
