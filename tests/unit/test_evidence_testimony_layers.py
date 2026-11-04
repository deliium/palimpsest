"""V4-08 three-layer separation and researcher-only alignment."""

from __future__ import annotations

import ast
from dataclasses import dataclass, fields
from pathlib import Path

import pytest

from analysis.evidence_testimony_alignment import (
    EvidenceAnalysis,
    EvidenceAnalysisSummary,
    EvidenceCustodyAlignment,
    EvidenceObjectiveAlignment,
    classify_custody_alignment,
    classify_evidence_objective_alignment,
)
from analysis.evidence_testimony_contract import (
    EVIDENCE_FORBIDDEN_RESULT_FIELDS,
    EvidenceAnalysisError,
    EvidenceCandidateStatus,
)
from analysis.evidence_testimony_layers import (
    EvidenceAnalyticalRow,
    EvidenceLayerView,
    EvidenceObjectiveRow,
    EvidenceSubjectiveRow,
    project_evidence_layers,
)
from analysis.evidence_testimony_objective import (
    evidence_objective_anchor_rows_from_events,
)
from analysis.evidence_testimony_rows import (
    EvidenceCustodyRow,
    EvidenceSourceRow,
    harvest_evidence_rows,
)
from tests.unit.evidence_testimony_helpers import make_parts

pytestmark = pytest.mark.unit


@dataclass(frozen=True)
class _Entity:
    value: str


@dataclass(frozen=True)
class _Event:
    details: object
    tick: int
    event_id: _Entity


def _event(name: str, tick: int, event_id: str, **attributes: object) -> _Event:
    details = type(name, (), attributes)()
    return _Event(details, tick, _Entity(event_id))


def _source(**overrides: object) -> EvidenceSourceRow:
    values: dict[str, object] = {
        "owner_token": "0" * 16,
        "local_id": "evs-" + "0" * 16,
        "source_kind": "artifact",
        "reference_kind": "artifact",
        "provenance": "direct_observation",
        "confidence_band": "mid",
        "tick": 5,
        "subject_token": "artifact-1",
    }
    values.update(overrides)
    return EvidenceSourceRow(**values)  # type: ignore[arg-type]


def test_objective_rows_are_counts_only() -> None:
    kinds = {field.name for field in fields(EvidenceObjectiveRow)}
    assert kinds == {
        "source_count",
        "testimony_count",
        "record_count",
        "artifact_count",
        "custody_link_count",
        "contradiction_count",
        "evaluation_count",
        "window_count",
    }
    assert kinds.isdisjoint(EVIDENCE_FORBIDDEN_RESULT_FIELDS)

    parts = make_parts()
    rows = harvest_evidence_rows((parts.ledger(),))
    analysis = EvidenceAnalysis()
    view = project_evidence_layers(
        rows, analysis, EvidenceAnalysisSummary(source_count=1)
    )
    assert view.objective.source_count == 1
    assert view.analytical == ()
    assert view.subjective[0].owner_token == rows.sources[0].owner_token


def test_layers_reject_owner_and_candidate_leaks() -> None:
    with pytest.raises(EvidenceAnalysisError):
        EvidenceSubjectiveRow(owner_token="evid-" + "0" * 16)
    with pytest.raises(EvidenceAnalysisError):
        EvidenceAnalyticalRow(
            candidate_id="evid-" + "0" * 16,
            subject_token="evs-" + "0" * 16,
            status=EvidenceCandidateStatus.ISOLATED,
            owner_count=1,
            item_count=1,
        )

    view = EvidenceLayerView(
        objective=EvidenceObjectiveRow(),
        subjective=(EvidenceSubjectiveRow(owner_token="1" * 16),),
        analytical=(),
    )
    from analysis.evidence_testimony_layers import assert_evidence_layer_separation

    assert_evidence_layer_separation(view)


def test_forbidden_fields_are_absent_from_every_layer_type() -> None:
    for model in (
        EvidenceObjectiveRow,
        EvidenceSubjectiveRow,
        EvidenceAnalyticalRow,
        EvidenceLayerView,
    ):
        assert {field.name for field in fields(model)}.isdisjoint(
            EVIDENCE_FORBIDDEN_RESULT_FIELDS
        )


def test_alignment_classifies_each_source_kind() -> None:
    communication = evidence_objective_anchor_rows_from_events(
        (
            _event(
                "Talked",
                5,
                "event-1",
                speaker_id=_Entity("body-1"),
                listener_id=_Entity("body-2"),
                utterance=type(
                    "U",
                    (),
                    {
                        "declared": type(
                            "D", (), {"communication_id": _Entity("comm-1")}
                        )()
                    },
                )(),
            ),
        ),
        {"body-1": "agent-1", "body-2": "agent-2"},
    )
    witness = _source(
        source_kind="witness_testimony",
        subject_token="comm-1",
        tick=5,
        attributed_actor="agent-1",
    )
    assert (
        classify_evidence_objective_alignment(witness, communication)
        is EvidenceObjectiveAlignment.CONSISTENT
    )
    assert (
        classify_evidence_objective_alignment(
            _source(
                source_kind="witness_testimony",
                subject_token="comm-1",
                tick=5,
                attributed_actor="agent-3",
            ),
            communication,
        )
        is EvidenceObjectiveAlignment.INCONSISTENT
    )
    assert (
        classify_evidence_objective_alignment(
            _source(source_kind="witness_testimony", subject_token="missing"),
            communication,
        )
        is EvidenceObjectiveAlignment.UNRESOLVED
    )

    artifacts = evidence_objective_anchor_rows_from_events(
        (
            _event(
                "ArtifactCreated",
                3,
                "event-2",
                artifact_id="artifact-1",
                author_id=_Entity("body-1"),
            ),
        ),
        {"body-1": "agent-1"},
    )
    assert (
        classify_evidence_objective_alignment(
            _source(attributed_actor="agent-1"), artifacts
        )
        is EvidenceObjectiveAlignment.CONSISTENT
    )
    assert (
        classify_evidence_objective_alignment(
            _source(attributed_actor="agent-2"), artifacts
        )
        is EvidenceObjectiveAlignment.INCONSISTENT
    )

    destroyed = evidence_objective_anchor_rows_from_events(
        (
            _event(
                "ArtifactDestroyed",
                2,
                "event-3",
                artifact_id="artifact-1",
                actor_id=_Entity("body-1"),
            ),
        ),
        {"body-1": "agent-1"},
    )
    assert (
        classify_evidence_objective_alignment(_source(), destroyed)
        is EvidenceObjectiveAlignment.INCONSISTENT
    )

    physical = evidence_objective_anchor_rows_from_events(
        (
            _event(
                "Given",
                5,
                "event-4",
                giver_id=_Entity("body-1"),
                recipient_id=_Entity("body-2"),
                item_id="item-1",
                quantity=1,
            ),
        ),
        {"body-1": "agent-1", "body-2": "agent-2"},
    )
    assert (
        classify_evidence_objective_alignment(
            _source(source_kind="physical_state", subject_token="item-1"), physical
        )
        is EvidenceObjectiveAlignment.CONSISTENT
    )

    commitments = evidence_objective_anchor_rows_from_events(
        (
            _event(
                "CommitmentDeclared",
                5,
                "event-5",
                owner_id=_Entity("body-1"),
                commitment_id="commitment-1",
            ),
        ),
        {"body-1": "agent-1"},
    )
    assert (
        classify_evidence_objective_alignment(
            _source(source_kind="prior_agreement", subject_token="commitment-1"),
            commitments,
        )
        is EvidenceObjectiveAlignment.CONSISTENT
    )

    assert (
        classify_evidence_objective_alignment(
            _source(source_kind="reputation"), physical
        )
        is EvidenceObjectiveAlignment.NOT_APPLICABLE
    )
    assert (
        classify_evidence_objective_alignment(_source(source_kind="unknown"), physical)
        is EvidenceObjectiveAlignment.NOT_APPLICABLE
    )

    remembered = _source(
        source_kind="remembered_event",
        subject_token="subject-1",
        opaque_correlation="event-4",
        tick=5,
    )
    assert (
        classify_evidence_objective_alignment(remembered, physical)
        is EvidenceObjectiveAlignment.CONSISTENT
    )
    assert (
        classify_evidence_objective_alignment(
            _source(
                source_kind="remembered_event",
                subject_token="subject-1",
                opaque_correlation="event-4",
                tick=9,
            ),
            physical,
        )
        is EvidenceObjectiveAlignment.INCONSISTENT
    )


def test_custody_alignment_covers_all_statuses() -> None:
    parts = make_parts()
    chain = (
        EvidenceCustodyRow(
            owner_token=harvest_evidence_rows((parts.ledger(),)).sources[0].owner_token,
            local_id=parts.custody.custody_id,
            source_local_id=parts.source.source_id,
            role="holder",
            tick=1,
            holder_token="agent-1",
        ),
    )
    assert (
        classify_custody_alignment(chain, (), applicable=False)
        is EvidenceCustodyAlignment.NOT_APPLICABLE
    )
    assert (
        classify_custody_alignment((), (), applicable=True)
        is EvidenceCustodyAlignment.UNKNOWN
    )
    assert (
        classify_custody_alignment(chain, (), applicable=True)
        is EvidenceCustodyAlignment.UNKNOWN
    )

    anchors = evidence_objective_anchor_rows_from_events(
        (
            _event(
                "ArtifactMoved",
                1,
                "event-6",
                artifact_id="artifact-1",
                actor_id=_Entity("body-1"),
                location_id=_Entity("loc-1"),
            ),
        ),
        {"body-1": "agent-1"},
    )
    matching = evidence_objective_anchor_rows_from_events(
        (
            _event(
                "ArtifactMoved",
                1,
                "event-7",
                artifact_id="artifact-1",
                actor_id=_Entity("body-1"),
                location_id=_Entity("agent-1"),
            ),
        ),
        {},
    )
    assert (
        classify_custody_alignment(chain, matching, applicable=True)
        is EvidenceCustodyAlignment.MATCHES
    )
    assert (
        classify_custody_alignment(chain, anchors, applicable=True)
        is EvidenceCustodyAlignment.MISMATCHES
    )


def test_cognition_never_imports_alignment() -> None:
    root = Path(__file__).resolve().parents[2] / "src"
    for relative in (
        "agents/cognition/loop.py",
        "agents/cognition/evidence_testimony.py",
        "simulation/runner.py",
        "api/main.py",
        "observer/__init__.py",
    ):
        path = root / relative
        if not path.exists():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module is not None:
                imported.add(node.module)
        assert not any("evidence_testimony_alignment" in item for item in imported)
