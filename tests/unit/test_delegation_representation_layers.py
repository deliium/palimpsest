"""V4-09 detached layers and researcher-only scope alignment."""

from __future__ import annotations

import pytest

from agents.cognition import (
    RepresentationDurationKind,
    RepresentationPrincipalKind,
    RepresentationProvenance,
    RepresentationScopeKind,
    default_representation_policy,
)
from agents.cognition.delegation_representation import apply_representation_update
from agents.cognition.delegation_representation_communication import (
    RepresentationAct,
    RepresentationFrame,
)
from analysis.delegation_representation_alignment import (
    RepresentationAlignmentStatus,
    classify_representation_scope_alignment,
    summarize_representation,
)
from analysis.delegation_representation_contract import (
    RepresentationAnalysisError,
    RepresentationCoverage,
)
from analysis.delegation_representation_identity import derive_representation_lineage
from analysis.delegation_representation_layers import (
    RepresentationAnalyticalRow,
    RepresentationLayerView,
    RepresentationObjectiveRow,
    RepresentationSubjectiveRow,
    assert_representation_layer_separation,
    project_representation_layers,
)
from analysis.delegation_representation_objective import (
    RepresentationObjectiveAnchorKind,
    RepresentationObjectiveAnchorRow,
    build_representation_windows,
)
from analysis.delegation_representation_rows import (
    RepresentationHarvestRows,
    harvest_representation_rows,
)

pytestmark = pytest.mark.unit

_OWNER = "agent-owner"
_PRINCIPAL = "agent-principal"
_REP = "agent-representative"


def _frame(
    scope_kind: RepresentationScopeKind = RepresentationScopeKind.SPEAK_FOR,
) -> RepresentationFrame:
    return RepresentationFrame(
        act=RepresentationAct.CLAIM,
        principal_kind=RepresentationPrincipalKind.AGENT,
        principal_ref=_PRINCIPAL,
        representative_ref=_REP,
        scope_kind=scope_kind,
        scope_subject="border",
        duration_kind=RepresentationDurationKind.UNTIL_REVOKED,
        provenance=RepresentationProvenance.SELF_DECLARED,
        actor_ref=_REP,
    )


def _rows(*frames: RepresentationFrame) -> RepresentationHarvestRows:
    ledger = apply_representation_update(
        owner_id=_OWNER,
        tick=1,
        observation=None,
        prior=None,
        frames=frames,
        policy=default_representation_policy(),
    )
    return harvest_representation_rows([ledger], entity_to_agent={})


def _anchor(tick: int, actor: str = _REP) -> RepresentationObjectiveAnchorRow:
    from analysis.delegation_representation_objective import _anchor

    return _anchor(
        RepresentationObjectiveAnchorKind.COMMUNICATION,
        tick,
        actor=actor,
        subject="comm",
    )


def test_layer_separation_rejects_leaks() -> None:
    rows = _rows(_frame())
    analysis = derive_representation_lineage(rows)
    summary = summarize_representation(rows, analysis)
    windows = build_representation_windows(rows)
    view = project_representation_layers(rows, analysis, summary, windows=windows)
    assert view.objective == RepresentationObjectiveRow(window_count=len(windows))
    assert view.subjective[0].owner_token != _OWNER
    assert view.analytical[0].candidate_id.startswith("rep-")
    assert_representation_layer_separation(view)

    with pytest.raises(RepresentationAnalysisError):
        assert_representation_layer_separation(
            RepresentationLayerView(
                objective=RepresentationObjectiveRow(),
                subjective=(
                    RepresentationSubjectiveRow(owner_token="rep-" + "0" * 16),
                ),
            )
        )
    from dataclasses import fields

    assert "owner_token" not in {
        field.name for field in fields(RepresentationAnalyticalRow)
    }
    assert "owner_token" not in {
        field.name for field in fields(RepresentationObjectiveRow)
    }


def test_alignment_statuses() -> None:
    rows = _rows(_frame())
    mandate = rows.mandates[0]
    assert (
        classify_representation_scope_alignment(mandate, [_anchor(1)])
        is RepresentationAlignmentStatus.CONSISTENT
    )
    assert (
        classify_representation_scope_alignment(mandate, [_anchor(0)])
        is RepresentationAlignmentStatus.INCONSISTENT
    )
    assert (
        classify_representation_scope_alignment(mandate, [])
        is RepresentationAlignmentStatus.UNRESOLVED
    )
    assert (
        classify_representation_scope_alignment(
            mandate, [_anchor(1, actor="agent-other")]
        )
        is RepresentationAlignmentStatus.UNRESOLVED
    )

    transaction = _rows(_frame(RepresentationScopeKind.TRANSACT)).mandates[0]
    assert (
        classify_representation_scope_alignment(transaction, [_anchor(1)])
        is RepresentationAlignmentStatus.NOT_APPLICABLE
    )


def test_not_applicable_never_counts_as_consistent() -> None:
    rows = _rows(_frame(RepresentationScopeKind.DECIDE))
    analysis = derive_representation_lineage(rows)
    summary = summarize_representation(rows, analysis, anchors=(_anchor(1),))
    assert summary.consistent_count == 0
    assert summary.not_applicable_count == 1
    assert summary.aligned_mandate_count == 0


def test_summary_and_coverage_are_explicit() -> None:
    rows = _rows(_frame())
    analysis = derive_representation_lineage(rows)
    windows = build_representation_windows(rows, window_ticks=1)
    summary = summarize_representation(rows, analysis, windows=windows)
    assert summary.mandate_count == 1
    assert summary.candidate_count == 1
    assert summary.coverage in {
        RepresentationCoverage.COMPLETE,
        RepresentationCoverage.PARTIAL,
    }
