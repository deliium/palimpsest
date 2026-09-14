"""Test-harness isolation and logging bootstrap checks."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

import pytest

import tests.conftest as test_bootstrap

pytestmark = pytest.mark.unit


def test_application_logging_is_not_configured_during_collection() -> None:
    assert test_bootstrap.APPLICATION_LOG_LEVEL_ENV == "PALIMPSEST_LOG_LEVEL"
    assert test_bootstrap.APPLICATION_LOGGING_CONFIGURED_DURING_COLLECTION is False
    application_loggers = [
        logging.getLogger(name)
        for name in ("palimpsest", "world", "agents", "infrastructure")
    ]
    for logger in application_loggers:
        assert logger.handlers == []


def test_unit_tests_cannot_invoke_docker() -> None:
    with pytest.raises(RuntimeError, match="Docker is forbidden"):
        subprocess.run(["docker", "ps"], check=False)


def test_unit_tests_cannot_connect_to_postgres() -> None:
    asyncpg = pytest.importorskip("asyncpg")
    with pytest.raises(RuntimeError, match="cannot connect to PostgreSQL"):
        asyncpg.connect("postgresql://postgres@localhost/postgres")


def test_default_pytest_addopts_exclude_live_infrastructure() -> None:
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    assert "not integration and not compose" in text
    assert "--strict-markers" in text
