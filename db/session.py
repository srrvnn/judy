import os
from dotenv import load_dotenv

load_dotenv()

from sqlmodel import create_engine, Session

# SQLite for now; set DATABASE_URL to a Postgres URL to migrate later
database_url = os.environ.get("DATABASE_URL", "sqlite:///judy.db")

# Render commonly uses postgres://; SQLAlchemy expects postgresql://
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

# Use psycopg (v3) driver if no driver is already specified
if database_url.startswith("postgresql://") and "+" not in database_url:
    database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)

connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
engine = create_engine(database_url, connect_args=connect_args)

def get_session():
    with Session(engine) as session:
        yield session
