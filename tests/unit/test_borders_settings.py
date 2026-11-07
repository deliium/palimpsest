# mypy: ignore-errors
"""Optional PALIMPSEST_BORDERS_* settings and safe status."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import SecretStr

from infrastructure.settings import Settings


def test_borders_root_and_cursor_key_are_optional() -> None:
    settings = Settings()
    assert settings.borders_root is None
    assert settings.borders_cursor_key is None
    assert settings.bootstrap_fields()["borders_enabled"] is False


def test_cursor_key_requires_32_bytes() -> None:
    with pytest.raises(ValueError):
        Settings(borders_cursor_key=SecretStr("short"))
    settings = Settings(borders_cursor_key=SecretStr("k" * 32))
    assert settings.borders_cursor_key is not None


def test_safe_status_fields_are_booleans() -> None:
    settings = Settings(
        borders_root=Path("/tmp/borders"),
        borders_cursor_key=SecretStr("k" * 32),
    )
    status = settings.bootstrap_fields()
    for name in (
        "has_borders_root",
        "has_borders_cursor_key",
        "borders_enabled",
        "borders_cursor_enabled",
    ):
        assert type(status[name]) is bool
    assert status["borders_enabled"] is True
