"""V4-08 detached evidence rows, anchors, candidates, and lineage."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from agents.cognition import EvidenceLedger, EvidenceTestimonyChannel
from analysis.evidence_testimony_contract import (
    EVIDENCE_ANALYSIS_POLICY_VERSION,
    EvidenceAnalysisError,
    EvidenceCandidateStatus,
    EvidenceCoverage,
    EvidenceLineageKind,
    evidence_owner_token,
)
from analysis.evidence_testimony_detection import detect_evidence_window_candidates
from analysis.evidence_testimony_identity import (
    EvidenceWindowSnapshot,
    assign_evidence_identities,
)
from analysis.evidence_testimony_objective import (
    EVIDENCE_MAX_WINDOWS,
    EvidenceObjectiveAnchorKind,
    EvidenceObjectiveAnchorRow,
    build_evidence_windows,
    evidence_objective_anchor_rows_from_events,
)
from analysis.evidence_testimony_rows import (
    EvidenceHarvestRows,
    EvidenceItemRow,
    EvidenceSourceRow,
    harvest_evidence_rows,
)
from tests.unit.evidence_testimony_helpers import (
    OWNER,
    make_item,
    make_parts,
    make_source,
)

pytestmark = pytest.mark.unit
OTHER = "agent-2"


@dataclass(frozen=True)
class _Event:
    details: object
    tick: int
    event_id: object


@dataclass(frozen=True)
class _Entity:
    value: str


class ArtifactCreated:
    def __init__(self) -> None:
        self.artifact_id = "artifact-1"
        self.author_id = _Entity("body-1")


class Given:
    def __init__(self) -> None:
        self.giver_id = _Entity("body-1")
        self.recipient_id = _Entity("body-2")
        self.item_id = "item-1"
        self.quantity = 1


class Talked:
    def __init__(self) -> None:
        self.speaker_id = _Entity("body-1")
        self.listener_id = _Entity("body-2")
        self.utterance = type(
            "Utterance",
            (),
            {
                "declared": type(
                    "Declared", (), {"communication_id": _Entity("comm-1")}
                )()
            },
        )()


class UnknownEventDetails:
    def __init__(self) -> None:
        self.artifact_id = "artifact-1"


def _ledger(
    owner: str, *, subject: str = "artifact-1", ordinal: int = 0
) -> EvidenceLedger:
    source = make_source(reference_id=subject, ordinal=ordinal, owner=owner)
    item = make_item(
        source_id=source.source_id,
        subject=subject,
        ordinal=ordinal,
        owner=owner,
    )
    ledger = EvidenceLedger(owner_id=owner, sources=(source,), items=(item,))
    return ledger


def test_harvest_dedupes_sorts_and_marks_partial() -> None:
    parts = make_parts()
    ledger = parts.ledger(
        pruned_source_count=1,
        notices=("evidence_truncated",),
    )
    rows = harvest_evidence_rows((ledger,), window_ticks=100)

    assert rows.policy_version == EVIDENCE_ANALYSIS_POLICY_VERSION
    assert rows.coverage is EvidenceCoverage.PARTIAL
    assert len(rows.sources) == 1
    assert rows.sources[0].owner_token == evidence_owner_token(OWNER)
    assert rows.sources[0].local_id.startswith("evs-")
    assert rows.window_start_tick is not None
    assert rows.window_end_tick is not None
    assert rows.window_start_tick <= rows.window_end_tick

    with pytest.raises(EvidenceAnalysisError) as error:
        harvest_evidence_rows((_ledger(OWNER), _ledger(OWNER)))
    assert error.value.code == "evidence_testimony_duplicate_owner"


def test_rows_carry_no_owner_id_or_free_text() -> None:
    rows = harvest_evidence_rows((_ledger(OWNER),))
    source = rows.sources[0]
    assert OWNER not in source.owner_token
    assert len(source.owner_token) == 16
    assert source.opaque_correlation is None or len(source.opaque_correlation) <= 128


def test_whitelisted_events_map_to_anchors() -> None:
    created = _Event(ArtifactCreated(), 3, _Entity("event-1"))
    given = _Event(Given(), 4, _Entity("event-2"))
    communication = _Event(Talked(), 5, _Entity("event-3"))
    ignored = _Event(UnknownEventDetails(), 6, _Entity("event-4"))
    anchors = evidence_objective_anchor_rows_from_events(
        (created, given, communication, ignored),
        {"body-1": "agent-1", "body-2": "agent-2"},
    )

    kinds = [anchor.kind for anchor in anchors]
    assert EvidenceObjectiveAnchorKind.ARTIFACT_CREATED in kinds
    assert EvidenceObjectiveAnchorKind.TRANSFER in kinds
    assert EvidenceObjectiveAnchorKind.COMMUNICATION in kinds
    assert len(anchors) == 3
    assert anchors == evidence_objective_anchor_rows_from_events(
        (created, given, communication, ignored),
        {"body-1": "agent-1", "body-2": "agent-2"},
    )
    communication_anchor = next(
        anchor
        for anchor in anchors
        if anchor.kind is EvidenceObjectiveAnchorKind.COMMUNICATION
    )
    assert communication_anchor.subject_token == "comm-1"
    assert communication_anchor.correlation_token == "event-3"
    assert communication_anchor.actor_token == "agent-1"
    assert communication_anchor.target_token == "agent-2"


def test_unresolvable_actor_drops_the_anchor() -> None:
    class Given:
        def __init__(self) -> None:
            self.giver_id = _Entity("body-1")
            self.recipient_id = _Entity("body-2")
            self.item_id = None
            self.quantity = 1

    anchors = evidence_objective_anchor_rows_from_events(
        (_Event(Given(), 1, _Entity("event-1")),),
        {"body-1": "agent-1", "body-2": "agent-2"},
    )
    assert anchors == ()


def test_windows_are_capped_and_empty_windows_are_partial() -> None:
    sources = tuple(
        EvidenceSourceRow(
            owner_token=evidence_owner_token(OWNER),
            local_id=f"evs-{index:016x}",
            source_kind="artifact",
            reference_kind="artifact",
            provenance="direct_observation",
            confidence_band="mid",
            tick=index * 1000,
            subject_token=f"artifact-{index}",
        )
        for index in range(3)
    )
    rows = EvidenceHarvestRows(sources=sources)
    windows = build_evidence_windows(rows, window_ticks=100)
    assert len(windows) <= EVIDENCE_MAX_WINDOWS
    assert any(window.partial for window in windows)
    assert build_evidence_windows(EvidenceHarvestRows()) == ()


def test_candidates_isolated_convergent_and_contested() -> None:
    single = harvest_evidence_rows((_ledger(OWNER),))
    isolated = detect_evidence_window_candidates(single)
    assert len(isolated) == 1
    assert isolated[0].status is EvidenceCandidateStatus.ISOLATED
    assert isolated[0].candidate_id.startswith("evid-")
    assert not isolated[0].candidate_id.startswith(("disp-", "frule-", "org-", "msoc-"))

    def rooted(owner: str, root: str, ordinal: int) -> EvidenceLedger:
        source = make_source(
            owner=owner, reference_id="artifact-1", ordinal=ordinal, root_ref=root
        )
        item = make_item(
            owner=owner,
            source_id=source.source_id,
            subject="artifact-1",
            ordinal=ordinal,
        )
        return EvidenceLedger(owner_id=owner, sources=(source,), items=(item,))

    two_owners = harvest_evidence_rows(
        (rooted(OWNER, "root-1", 0), rooted(OTHER, "root-2", 1))
    )
    convergent = detect_evidence_window_candidates(two_owners)
    assert len(convergent) == 1
    assert convergent[0].status is EvidenceCandidateStatus.CONVERGENT
    assert len(convergent[0].owner_tokens) == 2

    parts = make_parts()
    contested_rows = harvest_evidence_rows((parts.ledger(),))
    contested = detect_evidence_window_candidates(contested_rows)
    assert contested[0].status is EvidenceCandidateStatus.CONTESTED


def test_shared_roots_without_contradiction_are_fragmented() -> None:
    from tests.unit.evidence_testimony_helpers import make_testimony

    first = make_testimony(
        channel=EvidenceTestimonyChannel.COMMUNICATED,
        root_ref="root-1",
        subject="subject-1",
        ordinal=0,
    )
    items = tuple(
        EvidenceItemRow(
            owner_token=evidence_owner_token(owner),
            local_id=make_item(
                owner=owner,
                testimony_id=first.testimony_id,
                subject="subject-1",
                ordinal=index,
            ).item_id,
            anchor_local_id=first.testimony_id,
            source_kind="witness_testimony",
            interpretation="supports",
            subject_token="subject-1",
            provenance="communicated",
            confidence_band="mid",
            tick=1,
            status="active",
            root_ref="root-1",
        )
        for index, owner in enumerate((OWNER, OTHER))
    )
    rows = EvidenceHarvestRows(items=items)
    candidates = detect_evidence_window_candidates(rows)
    assert candidates[0].status is EvidenceCandidateStatus.FRAGMENTED


def test_identity_is_stable_and_forward_only() -> None:
    rows = harvest_evidence_rows((_ledger(OWNER), _ledger(OTHER)))
    candidates = detect_evidence_window_candidates(rows)
    first = EvidenceWindowSnapshot(window_index=0, candidates=candidates)
    second = EvidenceWindowSnapshot(window_index=1, candidates=candidates)
    assignment = assign_evidence_identities((second, first))

    assert [record.candidate_id for record in assignment.records] == [
        candidate.candidate_id for candidate in candidates
    ]
    assert any(
        edge.kind is EvidenceLineageKind.EMERGED for edge in assignment.transitions
    )
    assert any(
        edge.kind is EvidenceLineageKind.CONTINUED for edge in assignment.transitions
    )
    assert all(edge.window_index >= 0 for edge in assignment.transitions)
    assert assignment == assign_evidence_identities((first, second))


def test_identity_split_and_merge_transitions() -> None:
    rows = harvest_evidence_rows((_ledger(OWNER), _ledger(OTHER)))
    base = detect_evidence_window_candidates(rows)[0]
    from dataclasses import replace

    base = replace(base, subject_token="subject-1")
    split_a = replace(
        base,
        candidate_id="evid-" + "a" * 16,
        creation_digest="a" * 64,
    )
    split_b = replace(
        base,
        candidate_id="evid-" + "b" * 16,
        subject_token="subject-1",
        creation_digest="b" * 64,
    )
    merge_target = replace(
        base,
        candidate_id="evid-" + "c" * 16,
        subject_token="subject-1",
        creation_digest="c" * 64,
    )
    split = assign_evidence_identities(
        (
            EvidenceWindowSnapshot(window_index=0, candidates=(base,)),
            EvidenceWindowSnapshot(window_index=1, candidates=(split_a, split_b)),
        )
    )
    assert any(edge.kind is EvidenceLineageKind.SPLIT for edge in split.transitions)

    merge = assign_evidence_identities(
        (
            EvidenceWindowSnapshot(window_index=0, candidates=(split_a, split_b)),
            EvidenceWindowSnapshot(window_index=1, candidates=(merge_target,)),
        )
    )
    assert any(edge.kind is EvidenceLineageKind.MERGE for edge in merge.transitions)


def test_identity_rejects_duplicate_windows() -> None:
    with pytest.raises(EvidenceAnalysisError) as error:
        assign_evidence_identities(
            (
                EvidenceWindowSnapshot(window_index=0),
                EvidenceWindowSnapshot(window_index=0),
            )
        )
    assert error.value.code == "evidence_testimony_identity_conflict"


def test_anchor_rows_are_content_addressed() -> None:
    from dataclasses import replace

    anchor = evidence_objective_anchor_rows_from_events(
        (_Event(ArtifactCreated(), 3, _Entity("event-1")),), {}
    )[0]
    assert isinstance(anchor, EvidenceObjectiveAnchorRow)
    assert anchor.anchor_id.startswith("evid-")

    with pytest.raises(EvidenceAnalysisError):
        replace(anchor, anchor_id="evid-" + "0" * 16)
    with pytest.raises(EvidenceAnalysisError):
        replace(anchor, tick=4)
