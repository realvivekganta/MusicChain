"""Shared fixtures for isolated, offline tests.

Build a fresh database once per session, then point each test at that database
and disable tracing. The project's .env is not loaded by these fixtures.
"""

# --- Imports -----------------------------------------------------------------

import pytest

from scripts.build_database import build_database

# --- Session database --------------------------------------------------------


@pytest.fixture(scope="session")
def chinook_path(tmp_path_factory):
    """Build one fresh checksummed database for the test session, independent of Studio data."""
    return build_database(tmp_path_factory.mktemp("chinook") / "test.sqlite")


# --- Per-test environment isolation ------------------------------------------


@pytest.fixture(autouse=True)
def local_environment(monkeypatch, chinook_path, tmp_path):
    """Give each test a private support store and disable tracing without loading .env."""
    # Tests must neither spend provider tokens nor export sample traces.
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    monkeypatch.setenv("CHINOOK_DB_PATH", str(chinook_path))
    monkeypatch.setenv("SUPPORT_DB_PATH", str(tmp_path / "support.sqlite"))
