"""
SQLAlchemy database engine, session factory, and declarative Base.

Uses SQLite by default. The engine is configured with `connect_args` to allow
SQLite usage from multiple threads (needed for background task processing).
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import DATABASE_URL

# SQLite needs check_same_thread=False when used across threads.
# This is safe because SQLAlchemy manages its own connection pooling.
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(DATABASE_URL, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a database session and closes it after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
