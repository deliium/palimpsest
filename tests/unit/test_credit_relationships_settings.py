"""Dual-gated credit relationship settings fail closed."""

# mypy: ignore-errors


from __future__ import annotations

import pytest
from pydantic import SecretStr

from infrastructure.settings import Settings

pytestmark = pytest.mark.unit

_KEY = "y" * 32


def test_defaults_are_disabled() -> None:
    settings = Settings()
    assert settings.credit_relationships_root is None
    assert settings.credit_relationships_cursor_key is None
    fields = settings.bootstrap_fields()
    assert fields["credit_relationships_enabled"] is False
    assert fields["has_credit_relationships_root"] is False
    assert fields["has_credit_relationships_cursor_key"] is False


def test_root_only_is_not_enabled() -> None:
    settings = Settings(credit_relationships_root="/tmp/credit-store")
    fields = settings.bootstrap_fields()
    assert fields["has_credit_relationships_root"] is True
    assert fields["credit_relationships_enabled"] is False


def test_cursor_only_is_not_enabled() -> None:
    settings = Settings(credit_relationships_cursor_key=SecretStr(_KEY))
    fields = settings.bootstrap_fields()
    assert fields["has_credit_relationships_cursor_key"] is True
    assert fields["credit_relationships_enabled"] is False


def test_both_settings_enable_the_surface() -> None:
    settings = Settings(
        credit_relationships_root="/tmp/credit-store",
        credit_relationships_cursor_key=SecretStr(_KEY),
    )
    fields = settings.bootstrap_fields()
    assert fields["credit_relationships_enabled"] is True
    assert fields["credit_relationships_cursor_enabled"] is True


def test_short_cursor_key_is_rejected() -> None:
    with pytest.raises(ValueError):
        Settings(credit_relationships_cursor_key=SecretStr("short"))


def test_env_prefix_only() -> None:
    assert Settings.model_config.get("env_prefix") == "PALIMPSEST_"
