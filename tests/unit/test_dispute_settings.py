"""V4-07 settings: optional dispute root and cursor secret checks."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from infrastructure.settings import Settings

pytestmark = pytest.mark.unit


def test_blank_dispute_root_is_unset() -> None:
    assert Settings().dispute_root is None
    assert (
        Settings(dispute_root="   ").dispute_root  # type: ignore[arg-type]
        is None
    )
    assert Settings(
        dispute_root="/tmp/disputes"  # type: ignore[arg-type]
    ).dispute_root == Path("/tmp/disputes")


def test_cursor_key_requires_32_bytes() -> None:
    with pytest.raises(ValidationError):
        Settings(dispute_cursor_key=SecretStr("short"))
    with pytest.raises(ValidationError):
        Settings(dispute_cursor_key=SecretStr("é" * 10))
    settings = Settings(dispute_cursor_key=SecretStr("x" * 32))
    assert settings.dispute_cursor_key is not None
    assert settings.dispute_cursor_key.get_secret_value() == "x" * 32


def test_safe_summary_exposes_presence_only() -> None:
    settings = Settings(
        dispute_root=Path("/tmp/disputes"),
        dispute_cursor_key=SecretStr("y" * 32),
    )
    fields = settings.bootstrap_fields()
    assert fields["has_dispute_root"] is True
    assert fields["has_dispute_cursor_key"] is True
    assert "/tmp/disputes" not in repr(fields)
    assert "y" * 32 not in repr(fields)
    unset = Settings().bootstrap_fields()
    assert unset["has_dispute_root"] is False
    assert unset["has_dispute_cursor_key"] is False
