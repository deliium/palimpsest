"""V4-07 dispute metric values, availability, and researcher-only alignment."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from analysis.dispute_evidence import (
    build_dispute_windows,
    dispute_objective_anchor_rows_from_events,
)
from analysis.dispute_layers import project_dispute_layers
from analysis.dispute_lineage import (
    derive_dispute_lineage,
    summarize_disputes,
)
from analysis.dispute_metrics import (
    compute_dispute_claim_structure,
    compute_dispute_resolution_alignment,
    compute_dispute_testimony_independence,
)
from analysis.disputes import harvest_dispute_rows
from analysis.models import MetricAvailability
from tests.unit.dispute_helpers import (
    OTHER,
    OWNER,
    make_case,
    make_claim,
    make_evidence,
    make_ledger,
    make_mediation_reference,
    make_resolution,
    make_response,
    make_rule_reference,
    make_testimony,
)

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
ENTITY_TO_AGENT = {"body-a": OWNER, "body-b": OTHER}


def _event(tick: int, actor: str, kind: str, **details: object) -> Any:
    return SimpleNamespace(
        tick=tick, actor_id=actor, details=SimpleNamespace(kind=kind, **details)
    )


def _documents(
    ledgers: tuple[Any, ...],
    *,
    events: tuple[Any, ...] = (),
) -> dict[str, Any]:
    rows = harvest_dispute_rows(ledgers)
    anchors = dispute_objective_anchor_rows_from_events(
        events, entity_to_agent=ENTITY_TO_AGENT
    )
    windows = build_dispute_windows(rows, window_ticks=100, objective_rows=anchors)
    analysis = derive_dispute_lineage(rows, windows, objective_rows=anchors)
    summary = summarize_disputes(rows, analysis)
    layers = project_dispute_layers(
        rows, analysis, summary, windows=windows, objective_rows=anchors
    )
    documents = (
        compute_dispute_claim_structure(
            summary, layers, run_id="run-dispute", input_revision="revision-1"
        ),
        compute_dispute_testimony_independence(
            summary, rows, run_id="run-dispute", input_revision="revision-1"
        ),
        compute_dispute_resolution_alignment(
            summary,
            analysis,
            layers,
            run_id="run-dispute",
            input_revision="revision-1",
        ),
    )
    return {document.metric_family: document for document in documents}


def test_absent_partial_present_availability() -> None:
    absent = (
        compute_dispute_claim_structure(
            None, None, run_id="run-absent", input_revision="revision-1"
        ),
        compute_dispute_testimony_independence(
            None, None, run_id="run-absent", input_revision="revision-1"
        ),
        compute_dispute_resolution_alignment(
            None, None, None, run_id="run-absent", input_revision="revision-1"
        ),
    )
    assert all(
        document.availability is MetricAvailability.ABSENT for document in absent
    )
    assert all(document.values == {} for document in absent)

    partial = _documents((make_ledger(pruned=2),))
    for document in partial.values():
        assert document.availability is MetricAvailability.PARTIAL
        assert document.coverage is not None
        assert document.coverage.observed == 0

    present = _documents((make_ledger(first_tick=2, last_tick=2),))
    for document in present.values():
        assert document.availability is MetricAvailability.PRESENT
        assert document.coverage is not None
        assert document.coverage.ratio is None


def test_claim_structure_values() -> None:
    case_one = make_case(subject="bread")
    claim = make_claim(case=case_one, subject="bread", evidence_ids=("ev-1",))
    evidence = make_evidence(claim=claim)
    counter = make_claim(
        case=case_one,
        subject="bread",
        claimant=OTHER,
        respondent=OWNER,
        role="counterclaim",
        polarity="deny",
        counters=claim.claim_ref,
    )
    case_two = make_case(subject="stone", parties=(OWNER, OTHER, "agent-3"))
    claim_two = make_claim(case=case_two, subject="stone", claim_kind="resource_taken")
    ledger = make_ledger(
        cases=(case_one, case_two),
        claims=(claim, counter, claim_two),
        evidence=(evidence,),
        rule_references=(make_rule_reference(claim=claim),),
    )
    document = _documents((ledger,))["dispute_claim_structure"]
    assert document.availability is MetricAvailability.PRESENT
    values = document.values
    assert values["candidate_count"] == 2
    assert values["case_count"] == 2
    assert values["claim_count"] == 3
    assert values["counterclaim_count"] == 1
    assert values["counterclaim_ratio"] == pytest.approx(1 / 3)
    assert values["evidence_backed_claim_ratio"] == pytest.approx(1 / 3)
    assert values["rule_referenced_case_ratio"] == pytest.approx(1 / 2)
    assert values["multi_party_case_ratio"] == pytest.approx(1 / 2)
    assert values["unresolved_case_ratio"] == pytest.approx(1.0)
    assert '"debt_owed":2' in str(values["claim_kind_histogram"])
    assert '"resource_taken":1' in str(values["claim_kind_histogram"])
    assert '"affirm":2' in str(values["polarity_histogram"])


def test_testimony_independence_excludes_shared_roots() -> None:
    case = make_case(subject="bread")
    claim = make_claim(case=case, subject="bread")
    contradictory = make_claim(
        case=case,
        subject="bread",
        claimant=OTHER,
        respondent=OWNER,
        role="counterclaim",
        polarity="deny",
        counters=claim.claim_ref,
    )
    testimony = (
        make_testimony(claim=claim, channel="direct", root="root-1"),
        make_testimony(
            claim=contradictory,
            speaker=OTHER,
            channel="direct",
            root="root-2",
            independently_evidenced=True,
        ),
        make_testimony(
            claim=claim,
            speaker=OTHER,
            channel="communicated",
            root="root-1",
        ),
    )
    ledger = make_ledger(
        cases=(case,), claims=(claim, contradictory), testimony=testimony
    )
    document = _documents((ledger,))["dispute_testimony_independence"]
    values = document.values
    assert values["testimony_count"] == 3
    assert values["direct_testimony_ratio"] == pytest.approx(2 / 3)
    assert values["communicated_testimony_ratio"] == pytest.approx(1 / 3)
    assert values["distinct_root_count"] == 2
    assert values["shared_root_duplicate_ratio"] == pytest.approx(1 / 3)
    assert values["independently_evidenced_ratio"] == pytest.approx(1 / 3)
    assert values["contradictory_testimony_ratio"] == pytest.approx(1.0)
    assert values["claim_without_testimony_ratio"] == pytest.approx(0.0)


def test_known_answer_two_direct_one_retold_and_one_inconsistent_claim() -> None:
    case = make_case(subject="bread")
    supported = make_claim(case=case, subject="bread", claim_kind="resource_taken")
    inconsistent = make_claim(
        case=case,
        subject="stone",
        claim_kind="resource_taken",
        polarity="deny",
    )
    testimony = (
        make_testimony(
            claim=supported,
            channel="direct",
            root="root-1",
            independently_evidenced=True,
        ),
        make_testimony(claim=supported, speaker=OTHER, channel="direct", root="root-2"),
        make_testimony(
            claim=supported,
            speaker=OTHER,
            channel="communicated",
            root="root-1",
        ),
    )
    ledger = make_ledger(
        cases=(case,), claims=(supported, inconsistent), testimony=testimony
    )
    events = (
        _event(2, "body-b", "take", item_id="bread", resulting_holder_id="body-b"),
        _event(2, "body-a", "take", item_id="stone", resulting_holder_id="body-a"),
    )
    documents = _documents((ledger,), events=events)
    testimony_values = documents["dispute_testimony_independence"].values
    assert testimony_values["testimony_count"] == 3
    assert testimony_values["direct_testimony_ratio"] == pytest.approx(2 / 3)
    assert testimony_values["shared_root_duplicate_ratio"] == pytest.approx(1 / 3)
    assert testimony_values["claim_without_testimony_ratio"] == pytest.approx(1 / 2)
    alignment_values = documents["dispute_resolution_alignment"].values
    assert alignment_values["objective_supported_claim_ratio"] == pytest.approx(1 / 2)
    assert alignment_values["objective_inconsistent_claim_ratio"] == pytest.approx(
        1 / 2
    )
    assert alignment_values["objective_unresolved_claim_ratio"] == pytest.approx(0.0)


def test_present_zero_counts_for_enabled_empty_ledger() -> None:
    documents = _documents((make_ledger(owner=OWNER),))
    for document in documents.values():
        assert document.availability is MetricAvailability.PRESENT
        assert document.coverage is not None
        assert (document.coverage.observed, document.coverage.expected) == (0, 0)
        assert document.coverage.ratio is None
        assert document.provenance.source_kind == "dispute_analysis"
    claim_values = documents["dispute_claim_structure"].values
    assert claim_values["claim_count"] == 0
    assert claim_values["counterclaim_ratio"] is None
    testimony_values = documents["dispute_testimony_independence"].values
    assert testimony_values["testimony_count"] == 0
    assert testimony_values["direct_testimony_ratio"] is None
    alignment_values = documents["dispute_resolution_alignment"].values
    assert alignment_values["resolution_count"] == 0
    assert alignment_values["accepted_party_ratio"] is None


def test_absent_when_no_dispute_channel() -> None:
    documents = (
        compute_dispute_claim_structure(
            None, None, run_id="run-none", input_revision="revision-1"
        ),
        compute_dispute_testimony_independence(
            None, None, run_id="run-none", input_revision="revision-1"
        ),
        compute_dispute_resolution_alignment(
            None, None, None, run_id="run-none", input_revision="revision-1"
        ),
    )
    assert [document.metric_family for document in documents] == [
        "dispute_claim_structure",
        "dispute_testimony_independence",
        "dispute_resolution_alignment",
    ]
    for document in documents:
        assert document.availability is MetricAvailability.ABSENT
        assert document.values == {}
        assert document.coverage is not None
        assert document.coverage.ratio is None


def test_resolution_alignment_values() -> None:
    case = make_case(subject="bread")
    claim = make_claim(case=case, subject="bread")
    first = make_resolution(
        case=case, proposer=OWNER, terms_digest="terms-1", status="proposed"
    )
    second = make_resolution(
        case=case, proposer=OWNER, terms_digest="terms-2", status="contested"
    )
    mirrored = make_resolution(
        owner=OTHER,
        case=case,
        proposer=OTHER,
        terms_digest="terms-1",
        status="proposed",
    )
    responses = (
        make_response(resolution=first, party=OWNER, kind="accept"),
        make_response(resolution=second, party=OTHER, kind="reject"),
    )
    documents = _documents(
        (
            make_ledger(
                cases=(case,),
                claims=(claim,),
                resolutions=(first, second),
                responses=responses,
                mediation_references=(make_mediation_reference(case=case),),
            ),
            make_ledger(
                owner=OTHER,
                cases=(make_case(owner=OTHER, subject="bread"),),
                resolutions=(mirrored,),
            ),
        )
    )
    values = documents["dispute_resolution_alignment"].values
    assert values["resolution_count"] == 3
    assert values["proposed_resolution_count"] == 2
    assert values["contested_resolution_count"] == 1
    assert values["apparently_accepted_resolution_count"] == 0
    assert values["accepted_party_ratio"] == pytest.approx(1 / 2)
    assert values["rejected_party_ratio"] == pytest.approx(1 / 2)
    assert values["mediation_linked_resolution_ratio"] == pytest.approx(1.0)
    assert values["agreement_alignment_ratio"] == pytest.approx(1.0)


def test_objective_alignment_is_researcher_only() -> None:
    for package in ("agents", "simulation", "world", "api", "observer", "memory"):
        for path in sorted((ROOT / "src" / package).rglob("*.py")):
            text = path.read_text(encoding="utf-8")
            assert "analysis.dispute" not in text, path
            assert "dispute_objective_anchor" not in text, path
    documents = _documents(
        (make_ledger(owner=OWNER),),
        events=(
            _event(2, "body-b", "take", item_id="bread", resulting_holder_id="body-b"),
        ),
    )
    for document in documents.values():
        for key in document.values:
            assert "verdict" not in key
            assert "guilty" not in key
            assert "liable" not in key
            assert "winner" not in key


def test_metrics_are_deterministic() -> None:
    evidence = _event(
        2, "body-b", "take", item_id="bread", resulting_holder_id="body-b"
    )
    case = make_case(subject="bread")
    claim = make_claim(case=case, subject="bread", claim_kind="resource_taken")
    ledger = make_ledger(cases=(case,), claims=(claim,))
    first = _documents((ledger,), events=(evidence,))
    second = _documents((ledger,), events=(evidence,))
    assert set(first) == set(second)
    for family, document in first.items():
        other = second[family]
        assert document.availability is other.availability
        assert dict(document.values) == dict(other.values)
        assert document.coverage == other.coverage
