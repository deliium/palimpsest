# mypy: ignore-errors
"""Optional PALIMPSEST_INTER_SOCIETY_RELATIONS_* settings and safe status."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import SecretStr

from infrastructure.settings import Settings

pytestmark = pytest.mark.unit


def test_inter_society_relations_root_and_cursor_key_are_optional() -> None:
    settings = Settings()
    assert settings.inter_society_relations_root is None
    assert settings.inter_society_relations_cursor_key is None
    assert settings.bootstrap_fields()["inter_society_relations_enabled"] is False


def test_cursor_key_requires_32_bytes() -> None:
    with pytest.raises(ValueError):
        Settings(inter_society_relations_cursor_key=SecretStr("short"))
    settings = Settings(inter_society_relations_cursor_key=SecretStr("k" * 32))
    assert settings.inter_society_relations_cursor_key is not None


def test_safe_status_fields_are_booleans() -> None:
    settings = Settings(
        inter_society_relations_root=Path("/tmp/isr"),
        inter_society_relations_cursor_key=SecretStr("k" * 32),
    )
    status = settings.bootstrap_fields()
    for name in (
        "has_inter_society_relations_root",
        "has_inter_society_relations_cursor_key",
        "inter_society_relations_enabled",
        "inter_society_relations_cursor_enabled",
    ):
        assert type(status[name]) is bool
    assert status["inter_society_relations_enabled"] is True
