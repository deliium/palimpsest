# mypy: ignore-errors
"""Optional PALIMPSEST_MIGRATION_DISPLACEMENT_* settings and safe status."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from infrastructure.settings import Settings
from persistence.migration_displacement_filesystem import (
    create_migration_displacement_reader,
)


def test_root_and_cursor_key_default_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PALIMPSEST_MIGRATION_DISPLACEMENT_ROOT", raising=False)
    monkeypatch.delenv("PALIMPSEST_MIGRATION_DISPLACEMENT_CURSOR_KEY", raising=False)
    settings = Settings()
    assert settings.migration_displacement_root is None
    assert settings.migration_displacement_cursor_key is None
    status = settings.bootstrap_fields()
    assert status["has_migration_displacement_root"] is False
    assert status["has_migration_displacement_cursor_key"] is False
    assert status["migration_displacement_cursor_enabled"] is False


def test_env_prefix_and_non_empty_cursor_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PALIMPSEST_MIGRATION_DISPLACEMENT_ROOT", str(tmp_path))
    monkeypatch.setenv(
        "PALIMPSEST_MIGRATION_DISPLACEMENT_CURSOR_KEY", "cursor-key-value"
    )
    settings = Settings()
    assert settings.migration_displacement_root == tmp_path
    assert settings.migration_displacement_cursor_key is not None
    assert (
        settings.migration_displacement_cursor_key.get_secret_value()
        == "cursor-key-value"
    )
    with pytest.raises(ValidationError):
        Settings(migration_displacement_cursor_key=SecretStr(""))


def test_safe_summary_never_exposes_the_key(tmp_path: Path) -> None:
    settings = Settings(
        migration_displacement_root=tmp_path,
        migration_displacement_cursor_key=SecretStr("secret-cursor-key-value"),
    )
    status = settings.bootstrap_fields()
    serialized = repr(status) + json.dumps(status, default=str)
    assert "secret-cursor-key-value" not in serialized
    for name in (
        "has_migration_displacement_root",
        "has_migration_displacement_cursor_key",
        "migration_displacement_cursor_enabled",
    ):
        assert type(status[name]) is bool
    assert status["has_migration_displacement_root"] is True
    assert status["migration_displacement_cursor_enabled"] is True


def test_unset_root_disables_the_reader(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("PALIMPSEST_MIGRATION_DISPLACEMENT_ROOT", raising=False)
    monkeypatch.delenv("PALIMPSEST_MIGRATION_DISPLACEMENT_CURSOR_KEY", raising=False)
    settings = Settings()
    assert settings.migration_displacement_root is None
    reader = create_migration_displacement_reader(tmp_path)
    assert reader.read_summary("run-1") is None
