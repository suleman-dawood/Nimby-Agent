"""Shared dependencies for FastAPI routes."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Generator

from sqlalchemy.orm import Session

from scraper.models import create_db_engine, create_session


@lru_cache
def _engine():
    return create_db_engine()


def get_session() -> Generator[Session, None, None]:
    session = create_session(_engine())
    try:
        yield session
    finally:
        session.close()


def configure_api_keys():
    """Load API keys from .env file if not already set."""
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip())
