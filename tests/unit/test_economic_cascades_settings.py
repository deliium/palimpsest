# mypy: ignore-errors
"""Dual-gated economic-cascade settings tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import SecretStr

from infrastructure.settings import Settings


def test_defaults_are_disabled() -> None:
    data = Settings().bootstrap_fields()
    assert data["has_economic_cascades_root"] is False
    assert data["has_economic_cascades_cursor_key"] is False
    assert data["economic_cascades_enabled"] is False
    assert data["economic_cascades_cursor_enabled"] is False


def test_each_gate_alone_stays_disabled() -> None:
    root_only = Settings(economic_cascades_root=Path("/tmp/cascades"))
    assert root_only.bootstrap_fields()["economic_cascades_enabled"] is False
    cursor_only = Settings(economic_cascades_cursor_key=SecretStr("x" * 32))
    assert cursor_only.bootstrap_fields()["economic_cascades_enabled"] is False
    both = Settings(
        economic_cascades_root=Path("/tmp/cascades"),
        economic_cascades_cursor_key=SecretStr("x" * 32),
    )
    assert both.bootstrap_fields()["economic_cascades_enabled"] is True


def test_blank_root_is_unset() -> None:
    settings = Settings(economic_cascades_root="   ")
    assert settings.economic_cascades_root is None
    assert settings.bootstrap_fields()["has_economic_cascades_root"] is False


def test_short_cursor_key_rejected() -> None:
    with pytest.raises(ValueError):
        Settings(economic_cascades_cursor_key=SecretStr("short"))
