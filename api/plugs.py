from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from db.session import get_session
from models import Plug
from schemas import PlugRead, PlugUpdate

router = APIRouter()


def _get_plug(plug_id: int, session: Session) -> Plug:
    plug = session.get(Plug, plug_id)
    if plug is None:
        raise HTTPException(status_code=404, detail="Plug not found")
    return plug


@router.get("/plugs", response_model=list[PlugRead])
def list_plugs(session: Session = Depends(get_session)):
    return session.exec(select(Plug).order_by(Plug.id)).all()


@router.get("/plugs/{plug_id}", response_model=PlugRead)
def get_plug(plug_id: int, session: Session = Depends(get_session)):
    return _get_plug(plug_id, session)


@router.patch("/plugs/{plug_id}", response_model=PlugRead)
def update_plug(plug_id: int, body: PlugUpdate, session: Session = Depends(get_session)):
    plug = _get_plug(plug_id, session)
    plug.name = body.name
    session.add(plug)
    session.commit()
    session.refresh(plug)
    return plug
