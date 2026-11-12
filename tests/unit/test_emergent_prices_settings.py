"""Dual-gated emergent-price settings fail closed."""

# mypy: ignore-errors


from __future__ import annotations

import pytest
from pydantic import SecretStr

from infrastructure.settings import Settings

pytestmark = pytest.mark.unit

_KEY = "x" * 32


def test_defaults_are_disabled() -> None:
    settings = Settings()
    assert settings.emergent_prices_root is None
    assert settings.emergent_prices_cursor_key is None
    fields = settings.bootstrap_fields()
    assert fields["emergent_prices_enabled"] is False
    assert fields["has_emergent_prices_root"] is False
    assert fields["has_emergent_prices_cursor_key"] is False


def test_both_settings_enable_the_surface() -> None:
    settings = Settings(
        emergent_prices_root="/tmp/price-store",
        emergent_prices_cursor_key=SecretStr(_KEY),
    )
    fields = settings.bootstrap_fields()
    assert fields["emergent_prices_enabled"] is True
    assert fields["emergent_prices_cursor_enabled"] is True


def test_short_cursor_key_is_rejected() -> None:
    with pytest.raises(ValueError):
        Settings(emergent_prices_cursor_key=SecretStr("short"))


def test_env_prefix_only() -> None:
    assert Settings.model_config.get("env_prefix") == "PALIMPSEST_"
