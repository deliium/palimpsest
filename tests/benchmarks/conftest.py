"""Reuse disposable PostgreSQL fixtures from the integration suite."""

from __future__ import annotations

pytest_plugins = ["tests.integration.conftest"]
