"""V4-07 detached dispute rows, windows, candidates, identity, and lineage."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from analysis.dispute_contract import (
    DisputeAnalysisError,
    DisputeCandidateStatus,
    DisputeLineageKind,
)
from analysis.dispute_detection import detect_dispute_candidates
from analysis.dispute_evidence import (
    DisputeObjectiveAnchorKind,
    build_dispute_windows,
    dispute_objective_anchor_rows_from_events,
)
from analysis.dispute_identity import (
    DisputeWindowSnapshot,
    assign_dispute_identities,
)
from analysis.dispute_layers import project_dispute_layers
from analysis.dispute_lineage import (
    DisputeObjectiveAlignment,
    classify_dispute_objective_alignment,
    derive_dispute_lineage,
    summarize_disputes,
    validate_dispute_lineage,
)
from analysis.disputes import (
    DisputeOwnerRow,
    harvest_dispute_rows,
)
from tests.unit.dispute_helpers import (
    OTHER,
    OWNER,
    THIRD,
    make_candidate,
    make_case,
    make_claim,
    make_evidence,
    make_ledger,
    make_resolution,
    make_testimony,
)

pytestmark = pytest.mark.unit

SRC = Path(__file__).resolve().parents[2] / "src"
ENTITY_TO_AGENT = {
    "body-a": OWNER,
    "body-b": OTHER,
    "body-c": THIRD,
}


def _two_ledgers() -> tuple[Any, Any]:
    case_one = make_case(subject="bread")
    claim_one = make_claim(case=case_one, subject="bread", evidence_ids=("ev-1",))
    case_two = make_case(
        subject="stone", parties=(OWNER, OTHER, THIRD), kind="resource_appropriation"
    )
    claim_two = make_claim(
        case=case_two,
        subject="stone",
        claim_kind="resource_taken",
        evidence_ids=("ev-2",),
    )
    testimony = make_testimony(claim=claim_one, channel="direct", root="root-1")
    evidence = make_evidence(claim=claim_one, reference_id="event-1")
    resolution = make_resolution(case=case_one)
    return (
        make_ledger(
            owner=OWNER,
            cases=(case_one, case_two),
            claims=(claim_one, claim_two),
            testimony=(testimony,),
            evidence=(evidence,),
            resolutions=(resolution,),
        ),
        make_ledger(
            owner=OTHER,
            cases=(
                make_case(owner=OTHER, subject="stone", parties=(OWNER, OTHER, THIRD)),
            ),
            claims=(
                make_claim(
                    owner=OTHER,
                    case=make_case(
                        owner=OTHER, subject="stone", parties=(OWNER, OTHER, THIRD)
                    ),
                    subject="stone",
                    claimant=OTHER,
                    respondent=OWNER,
                    role="counterclaim",
                    claim_kind="resource_taken",
                    polarity="deny",
                ),
            ),
        ),
    )


def _event(tick: int, actor: str | None, kind: str, **details: object) -> Any:
    return SimpleNamespace(
        tick=tick,
        actor_id=actor,
        details=SimpleNamespace(kind=kind, **details),
    )


def test_harvest_is_order_independent_and_deduplicates() -> None:
    first, second = _two_ledgers()
    forward = harvest_dispute_rows((first, second))
    backward = harvest_dispute_rows((second, first))
    assert forward == backward
    assert [row.owner_id for row in forward.owners] == [OWNER, OTHER]
    assert list(forward.claims) == sorted(
        forward.claims, key=lambda row: (row.owner_id, row.claim_ref)
    )
    repeated_case = make_case(subject="bread")
    duplicated = harvest_dispute_rows(
        (make_ledger(cases=(repeated_case, repeated_case)),)
    )
    assert len(duplicated.cases) == 1
    assert duplicated.owners[0].claim_count == 0
    assert duplicated.owners[0].coverage == "complete"


def test_duplicate_owner_fails_closed() -> None:
    with pytest.raises(DisputeAnalysisError) as excinfo:
        harvest_dispute_rows((make_ledger(owner=OWNER), make_ledger(owner=OWNER)))
    assert excinfo.value.code == "dispute_duplicate_owner"

    with pytest.raises(DisputeAnalysisError) as excinfo:
        harvest_dispute_rows((object(),))
    assert excinfo.value.code == "dispute_invalid_row"


def test_pruned_rows_report_partial_coverage_and_counts() -> None:
    rows = harvest_dispute_rows((make_ledger(pruned=3),))
    owner_row = rows.owners[0]
    assert isinstance(owner_row, DisputeOwnerRow)
    assert owner_row.coverage == "partial"
    assert owner_row.pruned_count == 3
    assert owner_row.case_count == 0


def test_objective_anchors_map_give_take_attack_commitment_and_records() -> None:
    events = (
        _event(3, "body-a", "give", recipient_id="body-b", item_id="bread"),
        _event(4, "body-a", "take", item_id="stone", resulting_holder_id="body-a"),
        _event(5, "body-a", "attack", target_id="body-b", damage=2),
        _event(
            6,
            "body-a",
            "commitment_declared",
            actor_id="body-a",
            counterparty_id="body-b",
            item_kind="bread",
            quantity=1,
        ),
        _event(
            7,
            "body-a",
            "exchange_completed",
            actor_id="body-a",
            counterparty_id="body-b",
            give_item_ids=("bread",),
            give_item_kinds=("bread",),
        ),
        _event(
            8, "body-a", "artifact_created", author_id="body-a", artifact_id="art-1"
        ),
        _event(
            9,
            "body-a",
            "item_stored",
            structure_id="store-1",
            consumed_item_id="bread",
            resulting_stored_quantity=4,
        ),
        _event(10, "body-a", "wait"),
    )
    rows = dispute_objective_anchor_rows_from_events(
        events, entity_to_agent=ENTITY_TO_AGENT
    )
    kinds = [row.kind for row in rows]
    assert kinds == [
        DisputeObjectiveAnchorKind.ITEM_TRANSFER,
        DisputeObjectiveAnchorKind.RESOURCE_TAKEN,
        DisputeObjectiveAnchorKind.HARM,
        DisputeObjectiveAnchorKind.COMMITMENT_DECLARATION,
        DisputeObjectiveAnchorKind.EXCHANGE_COMPLETION,
        DisputeObjectiveAnchorKind.RECORD_CREATION,
        DisputeObjectiveAnchorKind.REPOSITORY_ENTRY,
    ]
    give, take, harm, commitment, exchange, record, repository = rows
    assert (give.actor_id, give.target_id, give.item_token) == (
        OWNER,
        OTHER,
        "bread",
    )
    assert (take.actor_id, take.item_token) == (OWNER, "stone")
    assert (harm.actor_id, harm.target_id, harm.quantity) == (OWNER, OTHER, 2)
    assert (commitment.actor_id, commitment.target_id) == (OWNER, OTHER)
    assert (exchange.actor_id, exchange.target_id) == (OWNER, OTHER)
    assert (record.actor_id, record.target_id) == (OWNER, "art-1")
    assert (repository.actor_id, repository.target_id) == (OWNER, "store-1")
    assert all(len(row.reference_id) == 64 for row in rows)
    assert rows == tuple(sorted(rows, key=lambda row: row.tick))


def test_missing_event_mapping_skips_without_fabricating() -> None:
    events = (
        _event(3, "body-unknown", "give", recipient_id="body-b", item_id="bread"),
        _event(4, "body-a", "give", recipient_id="body-unknown", item_id="bread"),
        _event(5, None, "attack", target_id="body-b", damage=1),
        _event(6, "body-a", "wait"),
        SimpleNamespace(tick=7, actor_id="body-a", details=SimpleNamespace()),
        SimpleNamespace(tick=8, actor_id="body-a", details=None),
    )
    rows = dispute_objective_anchor_rows_from_events(
        events, entity_to_agent=ENTITY_TO_AGENT
    )
    assert rows == ()


def test_windows_are_deterministic_and_mark_partial_coverage() -> None:
    case = make_case(subject="bread")
    claim = make_claim(case=case, subject="bread")
    evidence = make_evidence(claim=claim, tick=250)
    ledger = make_ledger(cases=(case,), claims=(claim,), evidence=(evidence,))
    rows = harvest_dispute_rows((ledger,), window_ticks=100)
    windows = build_dispute_windows(rows, window_ticks=100)
    assert build_dispute_windows(rows, window_ticks=100) == windows
    assert [window.start_tick for window in windows] == [0, 100, 200]
    assert windows[0].claim_count == 1
    assert windows[1].claim_count == 0
    assert windows[1].coverage.partial is True
    assert windows[1].coverage.coverage_fraction == 0.0
    assert windows[2].evidence_count == 1
    assert (
        build_dispute_windows(
            harvest_dispute_rows((make_ledger(),), window_ticks=100),
            window_ticks=100,
        )
        == ()
    )


def test_analysis_imports_no_cognition_or_live_service() -> None:
    allowed = {
        "__future__",
        "analysis",
        "collections",
        "dataclasses",
        "enum",
        "hashlib",
        "json",
        "logging",
        "re",
        "typing",
    }
    forbidden = {
        "agents",
        "api",
        "experiments",
        "infrastructure",
        "observer",
        "persistence",
        "simulation",
        "world",
    }
    paths = sorted(
        [*SRC.glob("analysis/dispute*.py"), SRC / "analysis" / "disputes.py"]
    )
    assert paths
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module is not None:
                imported.add(node.module.split(".", 1)[0])
            elif isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
        assert imported <= allowed, path
        assert not imported & forbidden, path


def test_candidates_group_by_subject_and_party_set() -> None:
    case_one = make_case(subject="bread")
    claim_one = make_claim(case=case_one, subject="bread")
    case_two = make_case(
        owner=OTHER, subject="bread", parties=(OWNER, OTHER), kind="injury"
    )
    claim_two = make_claim(
        owner=OTHER,
        case=case_two,
        subject="bread",
        claimant=OTHER,
        respondent=OWNER,
        role="counterclaim",
        claim_kind="harm_caused",
        polarity="deny",
    )
    rows = harvest_dispute_rows(
        (
            make_ledger(cases=(case_one,), claims=(claim_one,)),
            make_ledger(owner=OTHER, cases=(case_two,), claims=(claim_two,)),
        )
    )
    windows = build_dispute_windows(rows, window_ticks=100)
    candidates = detect_dispute_candidates(rows, windows)
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.party_ids == (OWNER, OTHER)
    assert candidate.owner_ids == (OWNER, OTHER)
    assert candidate.kind == "contested_debt"
    assert candidate.disagreement_count == 0


def test_overlapping_subjects_with_different_parties_stay_separate() -> None:
    case_two_party = make_case(subject="bread", parties=(OWNER, OTHER))
    case_three_party = make_case(subject="bread", parties=(OWNER, OTHER, THIRD))
    rows = harvest_dispute_rows(
        (
            make_ledger(
                cases=(case_two_party, case_three_party),
                claims=(
                    make_claim(case=case_two_party, subject="bread"),
                    make_claim(
                        case=case_three_party,
                        subject="bread",
                        claim_kind="item_owned",
                    ),
                ),
            ),
        )
    )
    windows = build_dispute_windows(rows, window_ticks=100)
    candidates = detect_dispute_candidates(rows, windows)
    assert len(candidates) == 2
    assert {candidate.party_ids for candidate in candidates} == {
        (OWNER, OTHER),
        (OWNER, OTHER, THIRD),
    }


def test_opposite_claims_increment_disagreement_without_merging() -> None:
    case = make_case(subject="bread")
    claim = make_claim(case=case, subject="bread")
    counter = make_claim(
        case=case,
        subject="bread",
        claimant=OTHER,
        respondent=OWNER,
        role="counterclaim",
        polarity="deny",
        counters=claim.claim_ref,
    )
    uncertain = make_claim(
        case=case,
        subject="bread",
        claimant=OTHER,
        respondent=OWNER,
        role="supplementary",
        claim_kind="term_meaning",
        polarity="uncertain",
    )
    rows = harvest_dispute_rows(
        (make_ledger(cases=(case,), claims=(claim, counter, uncertain)),)
    )
    windows = build_dispute_windows(rows, window_ticks=100)
    candidates = detect_dispute_candidates(rows, windows)
    assert len(candidates) == 1
    assert candidates[0].disagreement_count == 1
    assert candidates[0].claim_refs == tuple(
        sorted((claim.claim_ref, counter.claim_ref, uncertain.claim_ref))
    )


def test_candidate_identity_is_creation_evidence_stable() -> None:
    case = make_case(subject="bread")
    first_claim = make_claim(case=case, subject="bread")
    early = harvest_dispute_rows(
        (make_ledger(cases=(case,), claims=(first_claim,), last_tick=2),),
        window_ticks=100,
    )
    later_claim = make_claim(
        case=case,
        subject="bread",
        claim_kind="item_owned",
        first_tick=150,
        last_tick=150,
    )
    late = harvest_dispute_rows(
        (
            make_ledger(
                cases=(case,),
                claims=(first_claim, later_claim),
                last_tick=150,
            ),
        ),
        window_ticks=100,
    )
    early_windows = build_dispute_windows(early, window_ticks=100)
    late_windows = build_dispute_windows(late, window_ticks=100)
    early_analysis = derive_dispute_lineage(early, early_windows)
    late_analysis = derive_dispute_lineage(late, late_windows)
    assert early_analysis.records[0].candidate_id == (
        late_analysis.records[0].candidate_id
    )
    assert early_analysis.candidates[0].candidate_key.startswith("disp-")


def _snapshot(start: int, *candidates: Any) -> DisputeWindowSnapshot:
    return DisputeWindowSnapshot(
        start_tick=start, end_tick=start + 99, candidates=candidates
    )


def test_lineage_continued_transformed_split_merge_dissolved_emerged() -> None:
    stable = make_candidate(subject="bread")
    continued = assign_dispute_identities(
        (_snapshot(0, stable), _snapshot(100, stable))
    )
    assert {item.kind for item in continued.transitions} >= {
        DisputeLineageKind.EMERGED,
        DisputeLineageKind.CONTINUED,
    }
    assert len({record.candidate_id for record in continued.candidates}) == 1

    transformed = assign_dispute_identities(
        (
            _snapshot(0, make_candidate(subject="bread")),
            _snapshot(100, make_candidate(subject="stone")),
        )
    )
    assert DisputeLineageKind.TRANSFORMED in {
        item.kind for item in transformed.transitions
    }

    wide = make_candidate(subject="bread", parties=(OWNER, OTHER, THIRD, "agent-4"))
    left = make_candidate(subject="bread", parties=(OWNER, OTHER))
    right = make_candidate(subject="stone", parties=(THIRD, "agent-4"))
    split = assign_dispute_identities((_snapshot(0, wide), _snapshot(100, left, right)))
    assert DisputeLineageKind.SPLIT in {item.kind for item in split.transitions}

    merge = assign_dispute_identities((_snapshot(0, left, right), _snapshot(100, wide)))
    assert DisputeLineageKind.MERGE in {item.kind for item in merge.transitions}

    dissolved = assign_dispute_identities(
        (_snapshot(0, make_candidate(subject="bread")), _snapshot(100))
    )
    assert DisputeLineageKind.DISSOLVED in {item.kind for item in dissolved.transitions}


def test_objective_alignment_has_no_verdict_member() -> None:
    assert {member.value for member in DisputeObjectiveAlignment} == {
        "supported",
        "unresolved",
        "inconsistent",
        "not_applicable",
    }
    events = (
        _event(3, "body-b", "take", item_id="bread", resulting_holder_id="body-b"),
        _event(4, "body-a", "take", item_id="bread", resulting_holder_id="body-a"),
    )
    anchors = dispute_objective_anchor_rows_from_events(
        events, entity_to_agent=ENTITY_TO_AGENT
    )
    case = make_case(subject="bread")
    supported = make_claim(
        case=case,
        subject="bread",
        claim_kind="resource_taken",
    )
    promise = make_claim(
        case=case,
        subject="bread",
        claim_kind="promise_broken",
    )
    unresolved_case = make_case(subject="unknown-item")
    unresolved = make_claim(
        case=unresolved_case,
        subject="unknown-item",
        claim_kind="resource_taken",
    )
    rows = harvest_dispute_rows(
        (
            make_ledger(
                cases=(case, unresolved_case),
                claims=(supported, promise, unresolved),
            ),
        )
    )
    claim_rows = {row.claim_kind + ":" + row.subject_token: row for row in rows.claims}
    supported_row = claim_rows["resource_taken:bread"]
    promise_row = claim_rows["promise_broken:bread"]
    unresolved_row = claim_rows["resource_taken:unknown-item"]
    assert (
        classify_dispute_objective_alignment(supported_row, anchors[:1])
        is DisputeObjectiveAlignment.SUPPORTED
    )
    assert (
        classify_dispute_objective_alignment(supported_row, anchors[1:])
        is DisputeObjectiveAlignment.INCONSISTENT
    )
    assert (
        classify_dispute_objective_alignment(promise_row, anchors)
        is DisputeObjectiveAlignment.NOT_APPLICABLE
    )
    assert (
        classify_dispute_objective_alignment(unresolved_row, anchors)
        is DisputeObjectiveAlignment.UNRESOLVED
    )
    windows = build_dispute_windows(rows, window_ticks=100)
    analysis = derive_dispute_lineage(rows, windows, objective_rows=anchors[:1])
    summary = summarize_disputes(rows, analysis)
    assert summary.supported_claim_count == 1
    assert summary.inconsistent_claim_count == 0
    assert summary.not_applicable_claim_count == 1
    assert summary.objective_anchored_claim_count == 2
    for item in analysis.alignment:
        assert not hasattr(item, "verdict")
        assert not hasattr(item, "guilty")
        assert not hasattr(item, "liable")


def test_dispute_analysis_does_not_change_other_context_identities() -> None:
    rows = harvest_dispute_rows((_two_ledgers()[0],))
    windows = build_dispute_windows(rows, window_ticks=100)
    analysis = derive_dispute_lineage(rows, windows)
    assert analysis.records
    for record in analysis.records:
        assert record.candidate_id.startswith("disp-")
        assert not record.candidate_id.startswith(
            ("frule-", "org-", "msoc-", "off-", "inst-", "med-")
        )
    for edge in analysis.edges:
        assert edge.edge_id.startswith("disp-edge-")
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(SRC.glob("analysis/dispute*.py"))
    )
    for foreign in (
        "assign_formal_rule_identities",
        "assign_organization_identities",
        "assign_macro_society_identities",
        "formal_rule_edge_id",
        "organization_edge_id",
    ):
        assert foreign not in source


def test_summary_and_layers_are_deterministic() -> None:
    first, second = _two_ledgers()
    rows = harvest_dispute_rows((first, second))
    windows = build_dispute_windows(rows, window_ticks=100)
    analysis = derive_dispute_lineage(rows, windows)
    validate_dispute_lineage(analysis)
    summary = summarize_disputes(rows, analysis)
    layers = project_dispute_layers(rows, analysis, summary, windows=windows)
    reordered = harvest_dispute_rows((second, first))
    reordered_windows = build_dispute_windows(reordered, window_ticks=100)
    reordered_analysis = derive_dispute_lineage(reordered, reordered_windows)
    reordered_summary = summarize_disputes(reordered, reordered_analysis)
    assert summary.determinism_digest == reordered_summary.determinism_digest
    assert (
        layers.digest
        == project_dispute_layers(
            reordered,
            reordered_analysis,
            reordered_summary,
            windows=reordered_windows,
        ).digest
    )


def test_candidate_status_reflects_owner_disagreement() -> None:
    contested = make_case(subject="bread", status="contested")
    open_case = make_case(
        owner=OTHER, subject="bread", parties=(OWNER, OTHER), status="open"
    )
    rows = harvest_dispute_rows(
        (
            make_ledger(cases=(contested,)),
            make_ledger(owner=OTHER, cases=(open_case,)),
        )
    )
    windows = build_dispute_windows(rows, window_ticks=100)
    candidates = detect_dispute_candidates(rows, windows)
    assert candidates[0].status is DisputeCandidateStatus.CONTESTED
