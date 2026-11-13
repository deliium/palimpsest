"""Dual-gated economic-inequality settings tests."""

# mypy: ignore-errors

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import SecretStr

from infrastructure.settings import Settings


def test_defaults_are_disabled() -> None:
    data = Settings().bootstrap_fields()
    assert data["has_economic_inequality_root"] is False
    assert data["has_economic_inequality_cursor_key"] is False
    assert data["economic_inequality_enabled"] is False
    assert data["economic_inequality_cursor_enabled"] is False


def test_each_gate_alone_stays_disabled() -> None:
    root_only = Settings(economic_inequality_root=Path("/tmp/inequality"))
    assert root_only.bootstrap_fields()["economic_inequality_enabled"] is False
    cursor_only = Settings(economic_inequality_cursor_key=SecretStr("x" * 32))
    assert cursor_only.bootstrap_fields()["economic_inequality_enabled"] is False
    both = Settings(
        economic_inequality_root=Path("/tmp/inequality"),
        economic_inequality_cursor_key=SecretStr("x" * 32),
    )
    assert both.bootstrap_fields()["economic_inequality_enabled"] is True


def test_blank_root_is_unset() -> None:
    settings = Settings(economic_inequality_root="   ")
    assert settings.economic_inequality_root is None
    assert settings.bootstrap_fields()["has_economic_inequality_root"] is False


def test_short_cursor_key_rejected() -> None:
    with pytest.raises(ValueError):
        Settings(economic_inequality_cursor_key=SecretStr("short"))
