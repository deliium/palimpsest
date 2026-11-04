"""V4-10 diplomacy settings defaults, env parsing, and health flags."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from infrastructure.settings import Settings

pytestmark = pytest.mark.unit


def test_defaults_are_disabled() -> None:
    settings = Settings()
    assert settings.diplomacy_root is None
    assert settings.diplomacy_cursor_key is None
    assert settings.bootstrap_fields()["diplomacy_enabled"] is False


def test_env_parsing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PALIMPSEST_DIPLOMACY_ROOT", str(tmp_path))
    monkeypatch.setenv("PALIMPSEST_DIPLOMACY_CURSOR_KEY", "k" * 32)
    settings = Settings()
    assert settings.diplomacy_root == tmp_path
    assert settings.diplomacy_cursor_key is not None
    flags = settings.bootstrap_fields()
    assert flags["has_diplomacy_root"] is True
    assert flags["diplomacy_enabled"] is True
    assert flags["diplomacy_cursor_enabled"] is True


def test_short_key_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(diplomacy_cursor_key=SecretStr("short"))
