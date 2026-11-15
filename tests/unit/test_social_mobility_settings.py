# mypy: ignore-errors
"""Dual-gated social-mobility settings tests."""

# mypy: ignore-errors

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import SecretStr

from infrastructure.settings import Settings


def test_defaults_are_disabled() -> None:
    data = Settings().bootstrap_fields()
    assert data["has_social_mobility_root"] is False
    assert data["has_social_mobility_cursor_key"] is False
    assert data["social_mobility_enabled"] is False
    assert data["social_mobility_cursor_enabled"] is False


def test_each_gate_alone_stays_disabled() -> None:
    root_only = Settings(social_mobility_root=Path("/tmp/mobility"))
    assert root_only.bootstrap_fields()["social_mobility_enabled"] is False
    cursor_only = Settings(social_mobility_cursor_key=SecretStr("x" * 32))
    assert cursor_only.bootstrap_fields()["social_mobility_enabled"] is False
    both = Settings(
        social_mobility_root=Path("/tmp/mobility"),
        social_mobility_cursor_key=SecretStr("x" * 32),
    )
    assert both.bootstrap_fields()["social_mobility_enabled"] is True


def test_blank_root_is_unset() -> None:
    settings = Settings(social_mobility_root="   ")
    assert settings.social_mobility_root is None
    assert settings.bootstrap_fields()["has_social_mobility_root"] is False


def test_short_cursor_key_rejected() -> None:
    with pytest.raises(ValueError):
        Settings(social_mobility_cursor_key=SecretStr("short"))


def test_cursor_secret_is_not_in_repr() -> None:
    settings = Settings(social_mobility_cursor_key=SecretStr("y" * 32))
    assert "y" * 32 not in repr(settings)
