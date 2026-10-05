"""Unit tests for lifecycle denied_command_kinds allowlist."""

from __future__ import annotations

import logging

import pytest

from world.lifecycle import LifecycleStageId
from world.lifecycle_effects import (
    LIFECYCLE_DENIED_COMMAND_KINDS_ALLOWLIST,
    StageCapabilityEffect,
    require_lifecycle_denied_command_kinds,
)

_LOG = logging.getLogger("tests.lifecycle_denied_command_kinds")


def test_allowlist_membership_locked() -> None:
    _LOG.debug("case_id=allowlist_membership")
    assert LIFECYCLE_DENIED_COMMAND_KINDS_ALLOWLIST == frozenset(
        {
            "attack",
            "harvest",
            "craft",
            "build",
            "repair",
            "flee",
        }
    )
    # Teaching is a cognition mode — not a deny token.
    assert "teach" not in LIFECYCLE_DENIED_COMMAND_KINDS_ALLOWLIST
    assert "talk" not in LIFECYCLE_DENIED_COMMAND_KINDS_ALLOWLIST
    assert "help" not in LIFECYCLE_DENIED_COMMAND_KINDS_ALLOWLIST


def test_require_denied_kinds_accepts_allowlisted() -> None:
    _LOG.debug("case_id=denied_kinds_accept")
    kinds = require_lifecycle_denied_command_kinds(("attack", "flee"))
    assert kinds == ("attack", "flee")


def test_require_denied_kinds_rejects_unknown() -> None:
    _LOG.debug("case_id=denied_kinds_unknown")
    with pytest.raises(ValueError, match="lifecycle_denied_command_kind_unknown"):
        require_lifecycle_denied_command_kinds(("talk",))
    with pytest.raises(ValueError, match="lifecycle_denied_command_kind_unknown"):
        require_lifecycle_denied_command_kinds(("teach",))
    with pytest.raises(ValueError, match="lifecycle_denied_command_kind_unknown"):
        require_lifecycle_denied_command_kinds(("heavy_labor",))


def test_stage_effect_rejects_unknown_deny_kind() -> None:
    _LOG.debug("case_id=stage_effect_unknown_deny")
    with pytest.raises(ValueError, match="lifecycle_denied_command_kind_unknown"):
        StageCapabilityEffect(
            stage_id=LifecycleStageId("dependent"),
            physical_capacity_factor=1.0,
            learning_rate_factor=1.0,
            fatigue_accrual_factor=1.0,
            denied_command_kinds=("leader",),
        )
