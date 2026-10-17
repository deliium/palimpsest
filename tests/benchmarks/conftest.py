"""Reuse disposable PostgreSQL fixtures from the integration suite."""

from __future__ import annotations

from tests.integration.conftest import (
    database_resources,
    migrated_test_database,
    test_database_settings,
)

__all__ = ["database_resources", "migrated_test_database", "test_database_settings"]
