"""V4-09 representation settings and health flags."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import SecretStr

from infrastructure.settings import Settings

pytestmark = pytest.mark.unit


def test_representation_root_and_cursor_are_optional(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PALIMPSEST_REPRESENTATION_ROOT", raising=False)
    monkeypatch.delenv("PALIMPSEST_REPRESENTATION_CURSOR_KEY", raising=False)
    settings = Settings()
    assert settings.representation_root is None
    assert settings.representation_cursor_key is None


def test_representation_env_is_parsed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PALIMPSEST_REPRESENTATION_ROOT", str(tmp_path))
    monkeypatch.setenv("PALIMPSEST_REPRESENTATION_CURSOR_KEY", "k" * 32)
    settings = Settings()
    assert settings.representation_root == tmp_path
    assert settings.representation_cursor_key is not None


def test_short_cursor_key_fails_closed() -> None:
    with pytest.raises(ValueError):
        Settings(representation_cursor_key=SecretStr("short"))


def test_health_flags_are_boolean_and_secret_safe() -> None:
    settings = Settings(
        representation_root=Path("root"),
        representation_cursor_key=SecretStr("k" * 32),
    )
    flags = settings.bootstrap_fields()
    assert flags["representation_enabled"] is True
    assert flags["representation_cursor_enabled"] is True
    assert flags["has_representation_root"] is True
    assert flags["has_representation_cursor_key"] is True
    assert "k" * 32 not in str(flags)
