"""V4-07 three-layer dispute projection and hard leakage checks."""

from __future__ import annotations

from dataclasses import fields
from types import SimpleNamespace
from typing import Any

import pytest

from analysis.dispute_contract import (
    DisputeAnalysisError,
    DisputeCoverage,
    DisputeLineageKind,
)
from analysis.dispute_evidence import (
    build_dispute_windows,
    dispute_objective_anchor_rows_from_events,
)
from analysis.dispute_layers import (
    DisputeAnalyticalRow,
    DisputeLayerView,
    DisputeObjectiveRow,
    DisputeSubjectiveRow,
    assert_dispute_layer_separation,
    dispute_layer_digest,
    project_dispute_layers,
    require_dispute_owner_token,
)
from analysis.dispute_lineage import (
    derive_dispute_lineage,
    summarize_disputes,
)
from analysis.disputes import harvest_dispute_rows
from tests.unit.dispute_helpers import (
    OTHER,
    OWNER,
    make_case,
    make_claim,
    make_ledger,
    make_mediation_reference,
    make_resolution,
    make_response,
    make_rule_reference,
    make_testimony,
)

pytestmark = pytest.mark.unit


def _event(tick: int, actor: str, kind: str, **details: object) -> Any:
    return SimpleNamespace(
        tick=tick, actor_id=actor, details=SimpleNamespace(kind=kind, **details)
    )


def _input() -> tuple[Any, ...]:
    case = make_case(subject="bread")
    claim = make_claim(case=case, subject="bread", evidence_ids=("ev-1",))
    counter = make_claim(
        case=case,
        subject="bread",
        claimant=OTHER,
        respondent=OWNER,
        role="counterclaim",
        polarity="deny",
        counters=claim.claim_ref,
    )
    testimony = make_testimony(claim=claim, root="root-1")
    resolution = make_resolution(case=case)
    response = make_response(resolution=resolution)
    ledger = make_ledger(
        cases=(case,),
        claims=(claim, counter),
        testimony=(testimony,),
        rule_references=(make_rule_reference(claim=claim),),
        mediation_references=(make_mediation_reference(case=case),),
        resolutions=(resolution,),
        responses=(response,),
    )
    rows = harvest_dispute_rows((ledger,))
    anchors = dispute_objective_anchor_rows_from_events(
        (_event(2, "body-a", "give", recipient_id="body-b", item_id="bread"),),
        entity_to_agent={"body-a": OWNER, "body-b": OTHER},
    )
    windows = build_dispute_windows(rows, window_ticks=100, objective_rows=anchors)
    analysis = derive_dispute_lineage(rows, windows, objective_rows=anchors)
    summary = summarize_disputes(rows, analysis)
    view = project_dispute_layers(
        rows,
        analysis,
        summary,
        windows=windows,
        objective_rows=anchors,
    )
    return rows, analysis, summary, view


def test_objective_rows_are_aggregate_counts_only() -> None:
    _, _, _, view = _input()
    assert view.objective
    assert {field.name for field in fields(DisputeObjectiveRow)} == {
        "tick",
        "observed_occurrence_count",
        "observed_transfer_count",
        "observed_harm_count",
        "observed_commitment_count",
        "observed_record_count",
        "observed_communication_count",
    }
    assert view.objective[0].observed_transfer_count == 1
    assert view.objective[0].observed_occurrence_count == 1
    for row in view.objective:
        for field in fields(DisputeObjectiveRow):
            assert type(getattr(row, field.name)) is int


def test_subjective_rows_never_expose_owner_local_ids_as_objective() -> None:
    rows, _, _, view = _input()
    assert view.subjective
    row = view.subjective[0]
    assert row.owner_token != OWNER
    require_dispute_owner_token(row.owner_token)
    assert row.case_ref == rows.cases[0].case_ref
    assert (row.claim_count, row.counterclaim_count) == (2, 1)
    assert row.testimony_count == 1
    assert row.rule_reference_count == 1
    assert row.resolution_count == 1
    for objective in view.objective:
        assert not hasattr(objective, "owner_id")
        assert not hasattr(objective, "owner_token")
        assert not hasattr(objective, "candidate_id")
    with pytest.raises(DisputeAnalysisError) as excinfo:
        require_dispute_owner_token(OWNER)
    assert excinfo.value.code == "dispute_owner_token"


def test_analytical_rows_use_candidate_ids_only() -> None:
    _, analysis, _, view = _input()
    assert view.analytical
    assert len(view.analytical) == len(analysis.candidates)
    for row in view.analytical:
        assert row.candidate_id.startswith("disp-")
        assert not row.candidate_id.startswith(
            ("frule-", "org-", "msoc-", "off-", "inst-", "med-")
        )
        assert row.objective_supported_count >= 0
        assert row.objective_inconsistent_count >= 0
    assert view.analytical[0].disagreement_count == 1


def test_layer_leakage_fails_closed() -> None:
    _, _, summary, view = _input()
    leaked = DisputeLayerView(
        objective=view.objective,
        subjective=view.subjective,
        analytical=(
            DisputeAnalyticalRow(
                candidate_id="disp-0123456789abcdef",
                kind="contested_debt",
                subject_token="dcl-0123456789abcdef",
                party_count=2,
                owner_count=1,
                claim_count=1,
                counterclaim_count=0,
                testimony_count=0,
                evidence_count=0,
                resolution_count=0,
                disagreement_count=0,
                objective_supported_count=0,
                objective_unresolved_count=0,
                objective_inconsistent_count=0,
                status="active",
                coverage=DisputeCoverage(observed=1, expected=1),
            ),
        ),
        digest="",
    )
    with pytest.raises(DisputeAnalysisError) as excinfo:
        assert_dispute_layer_separation(leaked)
    assert excinfo.value.code == "dispute_layer_leak"

    with pytest.raises(DisputeAnalysisError) as excinfo:
        DisputeAnalyticalRow(
            candidate_id="org-0123456789abcdef",
            kind="contested_debt",
            subject_token="bread",
            party_count=2,
            owner_count=1,
            claim_count=1,
            counterclaim_count=0,
            testimony_count=0,
            evidence_count=0,
            resolution_count=0,
            disagreement_count=0,
            objective_supported_count=0,
            objective_unresolved_count=0,
            objective_inconsistent_count=0,
            status="active",
            coverage=DisputeCoverage(observed=1, expected=1),
        )
    assert excinfo.value.code == "dispute_invalid_candidate"

    leaked_subjective = DisputeLayerView(
        objective=view.objective,
        subjective=(
            DisputeSubjectiveRow(
                owner_token="f" * 16,
                case_ref="dsc-0123456789abcdef",
                status="open",
                claim_count=1,
                counterclaim_count=0,
                testimony_count=0,
                evidence_count=0,
                rule_reference_count=0,
                resolution_count=0,
                coverage=DisputeCoverage(observed=1, expected=1),
            ),
        ),
        analytical=view.analytical,
        digest="",
    )
    with pytest.raises(DisputeAnalysisError) as excinfo:
        assert_dispute_layer_separation(leaked_subjective)
    assert excinfo.value.code == "dispute_layer_leak"
    assert summary.candidate_count == len(view.analytical)


def test_layer_digest_is_order_independent() -> None:
    _, _, _, view = _input()
    reordered = DisputeLayerView(
        objective=tuple(reversed(view.objective)),
        subjective=tuple(reversed(view.subjective)),
        analytical=tuple(reversed(view.analytical)),
        digest="",
    )
    assert dispute_layer_digest(view) == dispute_layer_digest(reordered)
    assert view.digest == reordered.digest


def test_lineage_has_no_dissolved_edge_identity() -> None:
    _, analysis, _, _ = _input()
    assert all(
        edge.kind
        in (
            DisputeLineageKind.CONTINUED,
            DisputeLineageKind.TRANSFORMED,
            DisputeLineageKind.SPLIT,
            DisputeLineageKind.MERGE,
        )
        for edge in analysis.edges
    )
