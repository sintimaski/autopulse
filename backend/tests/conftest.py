from __future__ import annotations

import os

import pytest

from autopulse_backend.database import upgrade_to_head


@pytest.fixture(scope="session")
def backend_test_database_url() -> str:
    value = os.getenv("BACKEND_TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not value:
        pytest.skip("Set BACKEND_TEST_DATABASE_URL to run backend tests.")
    return value


@pytest.fixture(scope="session", autouse=True)
def configure_backend_database() -> None:
    """Run migrations when a test DB URL is configured; do not skip unrelated tests."""
    value = os.getenv("BACKEND_TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not value:
        return
    os.environ["DATABASE_URL"] = value
    os.environ.setdefault("INGEST_REQUIRE_HTTPS", "false")
    os.environ.setdefault("INTERNAL_METRICS_BEARER_TOKEN", "test-internal-metrics-token")
    upgrade_to_head()
