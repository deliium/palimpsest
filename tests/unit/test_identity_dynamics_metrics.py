"""identity_dynamics@1 stays analysis-only and omits claim text."""

from __future__ import annotations

import logging

import pytest

from analysis.identity_dynamics_metrics import (
    IDENTITY_DYNAMICS_METRIC_VERSION,
    IdentityDissonanceInput,
    IdentityHeadInput,
    build_identity_audit,
    compute_identity_dynamics,
)
from analysis.models import MetricAvailability


def _head(
    owner: str, predicate: str, *, band: str = "low", value: bool = True
) -> IdentityHeadInput:
    return IdentityHeadInput(
        owner_id=owner,
        predicate=predicate,
        bool_value=value,
        stability_band=band,
    )


def test_missing_audit_is_absent(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="analysis.identity_dynamics_metrics")
    assert (
        build_identity_audit(
            run_id="run-1",
            heads=(
                _head("agent-1", "held.object.ball"),
                _head(
                    "agent-1",
                    "identity.ability.observed_outcome.search",
                    value=False,
                ),
            ),
        )
        is None
    )
    document = compute_identity_dynamics(
        None, input_revision="rev-1", run_id="run-1"
    )
    assert document.availability is MetricAvailability.ABSENT
    assert document.values == {}
    assert document.metric_family == "identity_dynamics"
    assert IDENTITY_DYNAMICS_METRIC_VERSION == "identity_dynamics@1"
    joined = " ".join(record.getMessage() for record in caplog.records)
    assert "family=absent" in joined
    assert "identity.ability" not in joined


def test_same_audit_is_deterministic_and_omits_claim_text() -> None:
    heads = (
        _head("agent-b", "identity.weakness.observed_outcome.search", band="low"),
        _head("agent-a", "identity.ability.observed_outcome.move", band="high"),
        _head("agent-a", "identity.ability.observed_outcome.search", band="high"),
    )
    report = build_identity_audit(
        run_id="run-1",
        heads=heads,
        dissonance=(
            IdentityDissonanceInput(
                owner_id="agent-a", conflict_code="commitment_command", count=2
            ),
        ),
    )
    assert report is not None
    first = compute_identity_dynamics(report, input_revision="rev-1")
    second = compute_identity_dynamics(report, input_revision="rev-1")
    assert first == second
    assert first.availability is MetricAvailability.PRESENT
    assert first.values["aspect_ability"] == 2
    assert first.values["aspect_weakness"] == 1
    assert first.values["stability_high"] == 2
    assert first.values["stability_low"] == 1
    assert first.values["dissonance_commitment_command"] == 2
    assert first.values["owner_divergence"] > 0
    rendered = str(first.values) + repr(report)
    assert "identity.ability" not in rendered
    assert "observed_outcome" not in rendered


def test_unknown_aspect_fails_closed() -> None:
    with pytest.raises(ValueError, match="unknown_aspect"):
        build_identity_audit(
            run_id="run-1",
            heads=(_head("agent-1", "identity.warrior.observed_outcome.move"),),
        )
