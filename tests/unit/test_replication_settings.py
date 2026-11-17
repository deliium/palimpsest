# mypy: ignore-errors
"""V4-28 replication settings stay optional, fail closed, and never leak keys."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from infrastructure.settings import Settings

pytestmark = pytest.mark.unit

KEY = "scientific-replication-key-" + "x" * 32


def test_absent_settings_keep_the_reader_disabled() -> None:
    settings = Settings(_env_file=None)
    assert settings.scientific_replication_root is None
    assert settings.scientific_replication_cursor_key is None


def test_root_without_key_is_valid_but_incomplete() -> None:
    settings = Settings(
        scientific_replication_root=Path("/tmp/replication-root"),
        _env_file=None,
    )
    assert settings.scientific_replication_root == Path("/tmp/replication-root")
    assert settings.scientific_replication_cursor_key is None


def test_key_shorter_than_32_utf8_bytes_fails_closed() -> None:
    with pytest.raises(ValidationError):
        Settings(
            scientific_replication_cursor_key=SecretStr("x" * 31),
            _env_file=None,
        )


def test_multibyte_key_is_measured_in_utf8_bytes() -> None:
    # 11 characters but 33 UTF-8 bytes.
    with pytest.raises(ValidationError):
        Settings(
            scientific_replication_cursor_key=SecretStr("щ" * 10 + "a"),
            _env_file=None,
        )
    settings = Settings(
        scientific_replication_cursor_key=SecretStr("щ" * 16),
        _env_file=None,
    )
    assert settings.scientific_replication_cursor_key is not None


def test_valid_key_never_appears_in_repr() -> None:
    settings = Settings(
        scientific_replication_cursor_key=SecretStr(KEY),
        _env_file=None,
    )
    assert KEY not in repr(settings)
