"""V4-06 settings: optional root and cursor secret checks."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from infrastructure.settings import Settings

pytestmark = pytest.mark.unit


def test_formal_rule_root_is_optional_and_blank_is_unset() -> None:
    assert Settings().formal_rule_root is None
    assert (
        Settings(formal_rule_root="   ").formal_rule_root  # type: ignore[arg-type]
        is None
    )
    assert Settings(
        formal_rule_root="/tmp/formal"  # type: ignore[arg-type]
    ).formal_rule_root == Path("/tmp/formal")


def test_short_formal_rule_cursor_key_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(formal_rule_cursor_key=SecretStr("short"))


def test_valid_formal_rule_cursor_key_is_accepted() -> None:
    settings = Settings(formal_rule_cursor_key=SecretStr("x" * 32))
    assert settings.formal_rule_cursor_key is not None
    assert settings.formal_rule_cursor_key.get_secret_value() == "x" * 32


def test_safe_summary_reports_root_and_secret_presence_without_values() -> None:
    settings = Settings(
        formal_rule_root=Path("/tmp/formal"),
        formal_rule_cursor_key=SecretStr("y" * 32),
    )
    fields = settings.bootstrap_fields()
    assert fields["has_formal_rule_root"] is True
    assert fields["has_formal_rule_cursor_key"] is True
    assert "/tmp/formal" not in repr(fields)
    assert "y" * 32 not in repr(fields)
