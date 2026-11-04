"""V4-08 optional evidence settings validation and health."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from infrastructure.settings import Settings

pytestmark = pytest.mark.unit


def test_evidence_settings_default_unset() -> None:
    settings = Settings()
    assert settings.evidence_root is None
    assert settings.evidence_cursor_key is None
    health = settings.bootstrap_fields()
    assert health["has_evidence_root"] is False
    assert health["has_evidence_cursor_key"] is False


def test_empty_root_is_rejected_or_unset() -> None:
    settings = Settings(evidence_root=None)
    assert settings.evidence_root is None


def test_short_cursor_key_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(evidence_cursor_key=SecretStr("short"))


def test_health_reports_presence_only() -> None:
    settings = Settings(
        evidence_root=Path("/tmp/evidence"),
        evidence_cursor_key=SecretStr("k" * 32),
    )
    health = settings.bootstrap_fields()
    assert health["has_evidence_root"] is True
    assert health["has_evidence_cursor_key"] is True
    assert "/tmp/evidence" not in str(health)
    assert "k" * 32 not in str(health)
