"""Required-mode gating for published-image acceptance lanes.

A required release run must fail when a prerequisite is missing; only optional
local runs may skip. The CI workflow additionally asserts zero skips, but the
pytest process itself must not report success for an unexecuted required lane.
"""

from __future__ import annotations

import pytest

from tests.compose.acceptance import (
    ACCEPTANCE_REQUIRED_ENV,
    acceptance_required,
    require_prerequisite,
)

pytestmark = pytest.mark.unit


def test_optional_run_skips_with_explicit_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(ACCEPTANCE_REQUIRED_ENV, raising=False)
    assert acceptance_required() is False
    with pytest.raises(pytest.skip.Exception):
        require_prerequisite("docker CLI is not available")


def test_required_run_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(ACCEPTANCE_REQUIRED_ENV, "1")
    assert acceptance_required() is True
    with pytest.raises(pytest.fail.Exception, match="cannot skip"):
        require_prerequisite("playwright is not installed")


def test_required_switch_accepts_only_canonical_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for value in ("", "0", "true", "yes", " 1x"):
        monkeypatch.setenv(ACCEPTANCE_REQUIRED_ENV, value)
        assert acceptance_required() is False
    monkeypatch.setenv(ACCEPTANCE_REQUIRED_ENV, " 1 ")
    assert acceptance_required() is True


def test_compose_helpers_use_required_gate() -> None:
    """Fixture helpers must not retain a bare skip path."""

    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "compose"
    for name in (
        "conftest.py",
        "test_stack.py",
        "test_observer_browser.py",
    ):
        text = (root / name).read_text(encoding="utf-8")
        assert "require_prerequisite(" in text, name
        assert 'pytest.skip("docker CLI is not available")' not in text, name
        assert 'pytest.skip("playwright is not installed")' not in text, name
        assert 'pytest.skip("PALIMPSEST_API_IMAGE is not set")' not in text, name
