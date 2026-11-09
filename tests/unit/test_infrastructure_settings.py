"""Optional PALIMPSEST_INFRASTRUCTURE_NETWORKS_* settings and safe status."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import SecretStr

from infrastructure.settings import Settings

pytestmark = pytest.mark.unit


def test_infrastructure_networks_root_and_cursor_key_are_optional() -> None:
    settings = Settings()
    assert settings.infrastructure_networks_root is None
    assert settings.infrastructure_networks_cursor_key is None
    assert settings.bootstrap_fields()["infrastructure_networks_enabled"] is False


def test_cursor_key_requires_32_bytes() -> None:
    with pytest.raises(ValueError):
        Settings(infrastructure_networks_cursor_key=SecretStr("short"))
    settings = Settings(infrastructure_networks_cursor_key=SecretStr("k" * 32))
    assert settings.infrastructure_networks_cursor_key is not None


def test_dual_gate_matrix() -> None:
    only_root = Settings(infrastructure_networks_root=Path("/tmp/infra"))
    assert only_root.bootstrap_fields()["infrastructure_networks_enabled"] is False
    only_key = Settings(infrastructure_networks_cursor_key=SecretStr("k" * 32))
    assert only_key.bootstrap_fields()["infrastructure_networks_enabled"] is False
    both = Settings(
        infrastructure_networks_root=Path("/tmp/infra"),
        infrastructure_networks_cursor_key=SecretStr("k" * 32),
    )
    status = both.bootstrap_fields()
    for name in (
        "has_infrastructure_networks_root",
        "has_infrastructure_networks_cursor_key",
        "infrastructure_networks_enabled",
        "infrastructure_networks_cursor_enabled",
    ):
        assert type(status[name]) is bool
    assert status["infrastructure_networks_enabled"] is True
    assert "cursor_key" not in repr(both)
    assert "k" * 8 not in repr(both)
