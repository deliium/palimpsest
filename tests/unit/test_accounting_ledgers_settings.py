"""Dual-gated accounting settings tests."""

# mypy: ignore-errors

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import SecretStr

from infrastructure.settings import Settings


def test_defaults_are_disabled() -> None:
    settings = Settings()
    data = settings.bootstrap_fields()
    assert data["has_accounting_ledgers_root"] is False
    assert data["has_accounting_ledgers_cursor_key"] is False
    assert data["accounting_ledgers_enabled"] is False
    assert data["accounting_ledgers_cursor_enabled"] is False


def test_each_gate_alone_stays_disabled() -> None:
    root_only = Settings(accounting_ledgers_root=Path("/tmp/accounting"))
    assert root_only.bootstrap_fields()["accounting_ledgers_enabled"] is False
    cursor_only = Settings(
        accounting_ledgers_cursor_key=SecretStr("x" * 32)
    )
    assert cursor_only.bootstrap_fields()["accounting_ledgers_enabled"] is False
    both = Settings(
        accounting_ledgers_root=Path("/tmp/accounting"),
        accounting_ledgers_cursor_key=SecretStr("x" * 32),
    )
    assert both.bootstrap_fields()["accounting_ledgers_enabled"] is True


def test_short_cursor_key_rejected() -> None:
    with pytest.raises(ValueError):
        Settings(accounting_ledgers_cursor_key=SecretStr("short"))


def test_env_names_parse(monkeypatch) -> None:
    monkeypatch.setenv("PALIMPSEST_ACCOUNTING_LEDGERS_ROOT", "/tmp/accounting")
    monkeypatch.setenv("PALIMPSEST_ACCOUNTING_LEDGERS_CURSOR_KEY", "y" * 32)
    settings = Settings()
    assert settings.accounting_ledgers_root == Path("/tmp/accounting")
    assert settings.accounting_ledgers_cursor_key is not None
    assert settings.bootstrap_fields()["accounting_ledgers_enabled"] is True
