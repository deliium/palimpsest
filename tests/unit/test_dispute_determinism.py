"""V4-07 deterministic dispute rows, identities, layers, and metric values."""

from __future__ import annotations

import ast
import itertools
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from agents.cognition import (
    DisputeClaimKind,
    DisputeClaimPolarity,
    DisputeClaimRole,
    DisputeEvidenceChannel,
    DisputeEvidenceReferenceKind,
    DisputeSubjectKind,
    DisputeTestimonyChannel,
    dispute_case_id,
    dispute_case_ref,
    dispute_claim_id,
    dispute_claim_ref,
    dispute_evidence_id,
    dispute_ledger_digest,
    dispute_party_set_digest,
    dispute_subject_digest,
    dispute_testimony_id,
    empty_dispute_ledger,
)
from analysis.dispute_contract import DISPUTE_OWNER_LOCAL_PREFIXES
from analysis.dispute_evidence import (
    build_dispute_windows,
    dispute_objective_anchor_rows_from_events,
)
from analysis.dispute_layers import dispute_layer_digest, project_dispute_layers
from analysis.dispute_lineage import derive_dispute_lineage, summarize_disputes
from analysis.dispute_metrics import (
    compute_dispute_claim_structure,
    compute_dispute_resolution_alignment,
    compute_dispute_testimony_independence,
)
from analysis.disputes import harvest_dispute_rows
from tests.unit.dispute_helpers import (
    OTHER,
    OWNER,
    THIRD,
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
SRC = ROOT / "src"

DETERMINISTIC_MODULES: tuple[Path, ...] = (
    SRC / "agents" / "cognition" / "legal_disputes.py",
    SRC / "agents" / "cognition" / "legal_dispute_communication.py",
    *sorted((SRC / "analysis").glob("dispute_*.py")),
    SRC / "analysis" / "disputes.py",
    SRC / "simulation" / "dispute_models.py",
    SRC / "simulation" / "dispute_codec.py",
    SRC / "simulation" / "dispute_paging.py",
    SRC / "simulation" / "dispute_ports.py",
    SRC / "experiments" / "dispute_harvest.py",
    SRC / "experiments" / "dispute_publication.py",
    SRC / "persistence" / "dispute_filesystem.py",
    SRC / "research_runner" / "dispute_composition.py",
)

# The API cursor codec is the one intentional wall-clock/secret boundary: it
# signs pagination cursors and never contributes snapshot content or identity.
NONDETERMINISTIC_BY_DESIGN = SRC / "api" / "dispute_cursor.py"

ENTITY_TO_AGENT = {"body-a": OWNER, "body-b": OTHER, "body-c": THIRD}


def _event(tick: int, actor: str, kind: str, **details: object) -> Any:
    return SimpleNamespace(
        tick=tick,
        actor_id=actor,
        details=SimpleNamespace(kind=kind, **details),
    )


def _ledgers() -> tuple[Any, ...]:
    first_case = make_case(subject="bread")
    first_claim = make_claim(
        case=first_case,
        subject="bread",
        evidence_ids=("ev-1",),
    )
    counter = make_claim(
        case=first_case,
        subject="bread",
        claimant=OTHER,
        respondent=OWNER,
        role="counterclaim",
        polarity="deny",
        counters=first_claim.claim_ref,
    )
    second_case = make_case(
        subject="stone",
        parties=(OWNER, OTHER, THIRD),
        kind="resource_appropriation",
    )
    second_claim = make_claim(
        case=second_case,
        subject="stone",
        claim_kind="resource_taken",
    )
    testimony = (
        make_testimony(claim=first_claim, channel="direct", root="root-1"),
        make_testimony(
            claim=counter,
            speaker=OTHER,
            channel="communicated",
            root="root-1",
        ),
    )
    evidence = (
        make_evidence(claim=first_claim, reference_id="event-1"),
        make_evidence(
            claim=second_claim,
            reference_kind="memory_trace",
            reference_id="mem-1",
            channel="remembered",
        ),
    )
    resolution = make_resolution(case=first_case, terms_digest="terms-1")
    response = make_response(resolution=resolution, party=OWNER, kind="accept")
    owner = make_ledger(
        owner=OWNER,
        cases=(first_case, second_case),
        claims=(first_claim, counter, second_claim),
        testimony=testimony,
        evidence=evidence,
        rule_references=(make_rule_reference(claim=first_claim),),
        mediation_references=(make_mediation_reference(case=first_case),),
        resolutions=(resolution,),
        responses=(response,),
        last_tick=4,
    )
    other_case = make_case(owner=OTHER, subject="bread")
    other = make_ledger(
        owner=OTHER,
        cases=(other_case,),
        claims=(
            make_claim(
                owner=OTHER,
                case=other_case,
                subject="bread",
                claimant=OTHER,
                respondent=OWNER,
                role="counterclaim",
                polarity="deny",
                counters=first_claim.claim_ref,
            ),
        ),
        last_tick=4,
    )
    return owner, other


def _pipeline(ledgers: tuple[Any, ...], events: tuple[Any, ...] = ()) -> dict[str, Any]:
    rows = harvest_dispute_rows(tuple(ledgers), window_ticks=100)
    anchors = dispute_objective_anchor_rows_from_events(
        events, entity_to_agent=ENTITY_TO_AGENT
    )
    windows = build_dispute_windows(rows, window_ticks=100, objective_rows=anchors)
    analysis = derive_dispute_lineage(rows, windows, objective_rows=anchors)
    summary = summarize_disputes(rows, analysis)
    layers = project_dispute_layers(
        rows,
        analysis,
        summary,
        windows=windows,
        objective_rows=anchors,
    )
    documents = (
        compute_dispute_claim_structure(
            summary, layers, run_id="run-determinism", input_revision="revision-1"
        ),
        compute_dispute_testimony_independence(
            summary, rows, run_id="run-determinism", input_revision="revision-1"
        ),
        compute_dispute_resolution_alignment(
            summary,
            analysis,
            layers,
            run_id="run-determinism",
            input_revision="revision-1",
        ),
    )
    return {
        "rows": rows,
        "anchors": anchors,
        "windows": windows,
        "analysis": analysis,
        "summary": summary,
        "layers": layers,
        "documents": {document.metric_family: document for document in documents},
    }


def _shuffled_rows(rows: Any) -> Any:
    return replace(
        rows,
        owners=tuple(reversed(rows.owners)),
        cases=tuple(reversed(rows.cases)),
        claims=tuple(reversed(rows.claims)),
        testimony=tuple(reversed(rows.testimony)),
        evidence=tuple(reversed(rows.evidence)),
        rule_references=tuple(reversed(rows.rule_references)),
        authority_references=tuple(reversed(rows.authority_references)),
        mediation_references=tuple(reversed(rows.mediation_references)),
        resolutions=tuple(reversed(rows.resolutions)),
        responses=tuple(reversed(rows.responses)),
    )


def test_shuffled_ledgers_and_rows_are_deterministic() -> None:
    ledgers = _ledgers()
    baseline = _pipeline(ledgers)
    for permutation in itertools.permutations(ledgers):
        candidate = _pipeline(permutation)
        assert candidate["rows"] == baseline["rows"]
        assert candidate["windows"] == baseline["windows"]
        assert [item.candidate_id for item in candidate["analysis"].records] == [
            item.candidate_id for item in baseline["analysis"].records
        ]
        assert candidate["analysis"].edges == baseline["analysis"].edges
        assert candidate["summary"].determinism_digest == (
            baseline["summary"].determinism_digest
        )
        assert candidate["layers"].digest == baseline["layers"].digest
        for family, document in baseline["documents"].items():
            other = candidate["documents"][family]
            assert document.availability is other.availability
            assert dict(document.values) == dict(other.values)
            assert document.coverage == other.coverage


def test_shuffled_rows_windows_and_documents_are_deterministic() -> None:
    baseline = _pipeline(_ledgers())
    rows = baseline["rows"]
    shuffled = _shuffled_rows(rows)
    assert harvest_dispute_rows(_ledgers()) == rows
    windows = build_dispute_windows(shuffled, window_ticks=100)
    assert windows == baseline["windows"]
    analysis = derive_dispute_lineage(shuffled, tuple(reversed(windows)))
    assert [item.candidate_id for item in analysis.records] == [
        item.candidate_id for item in baseline["analysis"].records
    ]
    summary = summarize_disputes(shuffled, analysis)
    layers = project_dispute_layers(shuffled, analysis, summary, windows=windows)
    assert summary.determinism_digest == baseline["summary"].determinism_digest
    assert layers.digest == baseline["layers"].digest
    reordered_view = replace(
        baseline["layers"],
        objective=tuple(reversed(baseline["layers"].objective)),
        subjective=tuple(reversed(baseline["layers"].subjective)),
        analytical=tuple(reversed(baseline["layers"].analytical)),
        digest="",
    )
    assert dispute_layer_digest(reordered_view) == dispute_layer_digest(
        baseline["layers"]
    )


def test_content_addressed_ids_are_stable_across_permutations() -> None:
    subject_digest = dispute_subject_digest(DisputeSubjectKind.ITEM, "item-1")
    assert dispute_party_set_digest((OWNER, OTHER, THIRD)) == dispute_party_set_digest(
        (THIRD, OWNER, OTHER, THIRD)
    )
    case_ref = dispute_case_ref("item-1", (OWNER, OTHER))
    counter_ref = dispute_claim_ref(
        case_ref,
        OWNER,
        DisputeClaimRole.CLAIM,
        DisputeClaimKind.DEBT_OWED,
        DisputeClaimPolarity.AFFIRM,
        subject_digest,
    )
    assert dispute_case_ref("item-1", (OTHER, OWNER)) == case_ref
    assert dispute_case_id(OWNER, case_ref) == dispute_case_id(OWNER, case_ref)
    assert dispute_claim_id(OWNER, counter_ref) == dispute_claim_id(OWNER, counter_ref)
    assert dispute_testimony_id(
        OWNER,
        case_ref,
        counter_ref,
        OWNER,
        DisputeTestimonyChannel.DIRECT,
        "root-1",
        2,
    ) == dispute_testimony_id(
        OWNER,
        case_ref,
        counter_ref,
        OWNER,
        DisputeTestimonyChannel.DIRECT,
        "root-1",
        2,
    )
    assert dispute_evidence_id(
        OWNER,
        case_ref,
        counter_ref,
        DisputeEvidenceChannel.OBSERVED,
        DisputeEvidenceReferenceKind.OBSERVED_OCCURRENCE,
        "event-1",
        0,
    ) == dispute_evidence_id(
        OWNER,
        case_ref,
        counter_ref,
        DisputeEvidenceChannel.OBSERVED,
        DisputeEvidenceReferenceKind.OBSERVED_OCCURRENCE,
        "event-1",
        0,
    )
    assert dispute_ledger_digest(empty_dispute_ledger(OWNER)) == dispute_ledger_digest(
        empty_dispute_ledger(OWNER)
    )
    assert not any(
        counter_ref.startswith(prefix) for prefix in DISPUTE_OWNER_LOCAL_PREFIXES
    )


def test_analysis_never_uses_nondeterministic_sources() -> None:
    forbidden_imports = {"uuid", "random", "secrets", "time", "datetime"}
    forbidden_calls = {
        "hash",
        "uuid1",
        "uuid4",
        "random",
        "randint",
        "choice",
        "shuffle",
        "default_rng",
        "time",
        "now",
        "token_bytes",
    }
    offenders: list[tuple[str, str]] = []
    for path in DETERMINISTIC_MODULES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module is not None:
                if node.module.split(".", 1)[0] in forbidden_imports:
                    offenders.append((path.name, node.module))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".", 1)[0] in forbidden_imports:
                        offenders.append((path.name, alias.name))
            elif isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id in forbidden_calls:
                    offenders.append((path.name, func.id))
                if isinstance(func, ast.Attribute) and func.attr in {
                    "time",
                    "now",
                    "default_rng",
                    "Random",
                }:
                    offenders.append((path.name, func.attr))
    assert offenders == []

    cursor = NONDETERMINISTIC_BY_DESIGN.read_text(encoding="utf-8")
    assert "time.time" in cursor
    assert "secrets.token_bytes" in cursor
    for path in DETERMINISTIC_MODULES:
        assert "api.dispute_cursor" not in path.read_text(encoding="utf-8"), path.name
