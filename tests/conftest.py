import pytest
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

import models  # noqa: F401  (registers tables on SQLModel.metadata)


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
