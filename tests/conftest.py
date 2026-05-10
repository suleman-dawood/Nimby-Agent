"""Test fixtures for Nimby Agent backend tests."""

import os
import pytest
from datetime import datetime, timedelta, timezone

import jwt
from fastapi.testclient import TestClient

# Ensure env vars are loaded before importing app
os.environ.setdefault("JWT_SECRET", "test-secret-key")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-client-id")

from api.main import app
from scraper.models import User, create_db_engine, create_session


@pytest.fixture(scope="session")
def db_session():
    """Session-scoped DB session using the configured DATABASE_URL."""
    engine = create_db_engine()
    session = create_session(engine)
    yield session
    session.close()


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def test_user(db_session):
    """Create or get a test user."""
    user = db_session.query(User).filter_by(email="test@nimby.dev").first()
    if not user:
        user = User(
            google_id="test-google-id-12345",
            email="test@nimby.dev",
            name="Test User",
            avatar_url=None,
            tokens_remaining=50,
            tokens_used=0,
            created_at=datetime.now(timezone.utc),
            last_login=datetime.now(timezone.utc),
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user):
    """JWT auth headers for test user."""
    secret = os.environ.get("JWT_SECRET", "test-secret-key")
    payload = {
        "user_id": test_user.id,
        "email": test_user.email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "iat": datetime.now(timezone.utc),
    }
    token = jwt.encode(payload, secret, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_pp_number(db_session):
    """Return a PP number that exists in the DB with chunks."""
    from scraper.models import Chunk
    result = db_session.query(Chunk.pp_number).first()
    if result:
        return result[0]
    pytest.skip("No PPs with chunks in database")


@pytest.fixture
def sample_pp_with_context(db_session):
    """Return a PP number that has SiteContext data."""
    from scraper.models import SiteContext
    result = db_session.query(SiteContext.pp_number).first()
    if result:
        return result[0]
    pytest.skip("No PPs with site context in database")
