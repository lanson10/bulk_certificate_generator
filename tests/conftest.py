"""
Shared test fixtures.

Key decisions:
  - Uses an in-memory SQLite database with StaticPool for isolation and speed.
    StaticPool ensures all connections share the same in-memory database so
    tables created in one connection are visible in others.
  - Overrides the FastAPI `get_db` dependency so every test gets a fresh DB.
  - Patches all modules that reference the engine or SessionLocal so that
    background processing and lifespan events also use the test DB.
  - Background tasks run synchronously in-process (via TestClient) so tests
    can assert on results immediately without polling.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app

# ── In-memory test database ─────────────────────────────────────────────────
# StaticPool reuses a single connection for all threads, which is necessary
# for in-memory SQLite — otherwise each connection would have its own DB.

TEST_ENGINE = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=TEST_ENGINE
)


def override_get_db():
    """Dependency override that provides a test DB session."""
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def setup_database():
    """Create fresh tables before each test, drop them after."""
    Base.metadata.create_all(bind=TEST_ENGINE)
    yield
    Base.metadata.drop_all(bind=TEST_ENGINE)


@pytest.fixture()
def db_session(setup_database):
    """Provide a raw DB session for direct model-level assertions."""
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def certificates_dir(tmp_path):
    """
    Provide a temporary directory for generated certificates and
    patch the config so the app writes there.
    """
    cert_dir = tmp_path / "certificates"
    cert_dir.mkdir()

    import app.config as config
    import app.services.job_processor as processor

    original_dir = config.CERTIFICATES_DIR
    config.CERTIFICATES_DIR = str(cert_dir)
    processor.CERTIFICATES_DIR = str(cert_dir)
    yield str(cert_dir)
    config.CERTIFICATES_DIR = original_dir
    processor.CERTIFICATES_DIR = original_dir


@pytest.fixture()
def client(setup_database):
    """
    HTTP test client with all database references patched to use the test DB.

    Patches:
    - get_db dependency → test session (for request handlers)
    - SessionLocal in job_processor → test session (for background tasks)
    - engine in database module → test engine (for lifespan table creation)
    """
    app.dependency_overrides[get_db] = override_get_db

    import app.services.job_processor as processor
    import app.database as database_module

    original_processor_session = processor.SessionLocal
    original_engine = database_module.engine

    processor.SessionLocal = TestSessionLocal
    database_module.engine = TEST_ENGINE

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
    processor.SessionLocal = original_processor_session
    database_module.engine = original_engine


@pytest.fixture()
def sample_request():
    """A valid job creation request payload."""
    return {
        "course_name": "Advanced Python Workshop",
        "issue_date": "2026-10-08",
        "recipients": [
            {"name": "Alice Johnson", "email": "alice@example.com"},
            {"name": "Bob Smith", "email": "bob@example.com"},
            {"name": "Charlie Brown", "email": "charlie@example.com"},
        ],
    }
