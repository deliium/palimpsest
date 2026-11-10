# mypy: ignore-errors
"""Dual-gated supply-chain settings."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import SecretStr

from infrastructure.settings import Settings

pytestmark = pytest.mark.unit


def test_root_and_key_enable_reader() -> None:
    settings = Settings(
        supply_chains_root=Path("/tmp/supply"),
        supply_chains_cursor_key=SecretStr("x" * 32),
    )
    diagnostics = settings.bootstrap_fields()
    assert diagnostics["supply_chains_enabled"] is True


def test_neither_disables() -> None:
    assert Settings().bootstrap_fields()["supply_chains_enabled"] is False


def test_root_only_disables() -> None:
    settings = Settings(supply_chains_root=Path("/tmp/supply"))
    assert settings.bootstrap_fields()["supply_chains_enabled"] is False


def test_key_only_disables() -> None:
    settings = Settings(supply_chains_cursor_key=SecretStr("x" * 32))
    assert settings.bootstrap_fields()["supply_chains_enabled"] is False


def test_short_key_rejected() -> None:
    with pytest.raises(ValueError):
        Settings(supply_chains_cursor_key=SecretStr("short"))


def test_env_names_are_prefixed() -> None:
    fields = Settings.model_fields
    assert "supply_chains_root" in fields
    assert "supply_chains_cursor_key" in fields


def test_secrets_not_in_diagnostics() -> None:
    key = "x" * 32
    settings = Settings(
        supply_chains_root=Path("/tmp/supply"),
        supply_chains_cursor_key=SecretStr(key),
    )
    assert key not in str(settings.bootstrap_fields())
