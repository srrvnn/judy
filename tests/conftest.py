import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

import models  # noqa: F401  (registers tables on SQLModel.metadata)
from db.session import get_session
from server import api


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    api.dependency_overrides[get_session] = lambda: session
    yield TestClient(api)
    api.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def stub_claude(monkeypatch):
    """Never call the real Claude API from tests. Contexts passed to call_claude land in `calls`."""
    calls = []
    decision = {"reasoning": "stub", "messages": []}

    def fake_call_claude(context):
        calls.append(context)
        return decision

    monkeypatch.setattr("judy.run.call_claude", fake_call_claude)
    fake_call_claude.calls = calls
    fake_call_claude.decision = decision
    return fake_call_claude


@pytest.fixture(autouse=True)
def reset_clock():
    from services.clock import clock
    clock.reset()
    yield
    clock.reset()


@pytest.fixture(autouse=True)
def clean_broadcaster():
    from services.events import broadcaster
    broadcaster._subscribers.clear()
    yield
    broadcaster._subscribers.clear()
