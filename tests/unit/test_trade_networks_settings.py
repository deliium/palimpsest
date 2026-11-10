# mypy: ignore-errors
"""Trade-network root and cursor settings."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import SecretStr

from infrastructure.settings import Settings


def test_trade_networks_settings_are_disabled_by_default() -> None:
    settings = Settings()
    assert settings.trade_networks_root is None
    assert settings.trade_networks_cursor_key is None
    flags = settings.bootstrap_fields()
    assert flags["has_trade_networks_root"] is False
    assert flags["has_trade_networks_cursor_key"] is False
    assert flags["trade_networks_enabled"] is False
    assert flags["trade_networks_cursor_enabled"] is False


def test_cursor_key_requires_32_bytes() -> None:
    with pytest.raises(ValueError, match="trade_networks cursor key"):
        Settings(trade_networks_cursor_key=SecretStr("short"))
    settings = Settings(
        trade_networks_root=Path("/tmp/trade"),
        trade_networks_cursor_key=SecretStr("x" * 32),
    )
    assert settings.trade_networks_cursor_key is not None
    assert settings.bootstrap_fields()["trade_networks_enabled"] is True


def test_enabled_flags_do_not_expose_secret() -> None:
    secret = "y" * 32
    settings = Settings(
        trade_networks_root=Path("/tmp/trade"),
        trade_networks_cursor_key=SecretStr(secret),
    )
    flags = settings.bootstrap_fields()
    assert secret not in repr(flags)
    assert "trade_networks_cursor_key" not in flags
    assert flags["has_trade_networks_cursor_key"] is True
