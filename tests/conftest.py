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
