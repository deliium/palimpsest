"""Organization settings: roots, cursor keys, and secret-safe summaries."""

from __future__ import annotations

import pytest
from pydantic import SecretStr, ValidationError

from infrastructure.settings import Settings


def test_organization_root_is_optional_and_blank_is_unset() -> None:
    assert Settings().organization_root is None
    assert Settings(organization_root="").organization_root is None
    settings = Settings(organization_root="/tmp/organizations")
    assert str(settings.organization_root).endswith("organizations")


def test_cursor_key_requires_32_bytes() -> None:
    with pytest.raises(ValidationError):
        Settings(organization_cursor_key=SecretStr("short"))
    settings = Settings(organization_cursor_key=SecretStr("k" * 32))
    assert settings.organization_cursor_key is not None


def test_summary_flags_are_secret_safe() -> None:
    settings = Settings(
        organization_root="/tmp/organizations",
        organization_cursor_key=SecretStr("k" * 32),
    )
    summary = settings.bootstrap_fields()
    assert summary["has_organization_root"] is True
    assert summary["has_organization_cursor_key"] is True
    assert "k" * 32 not in str(summary)
