"""Database engine and session management."""

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from .config import settings


engine = create_engine(settings.database_url, pool_pre_ping=True)


@event.listens_for(engine, "connect")
def set_search_path(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute(f"SET search_path TO {settings.db_schema}, public")
    cursor.execute("SET client_encoding TO 'UTF8'")
    cursor.close()


SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency that yields a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create the schema and all tables."""
    with engine.connect() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {settings.db_schema}"))
        conn.commit()
    Base.metadata.create_all(bind=engine)
