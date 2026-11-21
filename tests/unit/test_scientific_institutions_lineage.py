# mypy: ignore-errors
"""V4-32 forward-only scientific-practice episode lineage."""

from __future__ import annotations

import pytest

from analysis.organization_contract import OrganizationCoverage
from analysis.organization_identity import (
    OrganizationIdentityAssignment,
    OrganizationTransition,
)
from analysis.scientific_institutions_contract import (
    SCIENTIFIC_INSTITUTIONS_POLICY_VERSION,
    PracticeCoverageStatus,
    PracticeStatus,
    derive_practice_token,
)
from analysis.scientific_institutions_detection import (
    PracticeWindowAssessment,
    PracticeWindowState,
    ScientificPracticeAssessment,
    ScientificPracticeRow,
)
from analysis.scientific_institutions_lineage import (
    PracticeLineageKind,
    build_scientific_practice_lineage,
)

pytestmark = pytest.mark.unit

RUN = "run-lineage"
ORG_A = "org-aaaaaaaaaaaaaaaa"
ORG_B = "org-bbbbbbbbbbbbbbbb"
ORG_C = "org-cccccccccccccccc"
CARRIER = "artifact-1"
CARRIER_2 = "artifact-2"


def _token(domain: str, value: str) -> str:
    return derive_practice_token(domain, RUN, value)


def _actor(value: str) -> str:
    return _token("actor", value)


def _window(
    index: int,
    state: PracticeWindowState = PracticeWindowState.COMPLETE,
) -> PracticeWindowAssessment:
    start = index * 32
    coverage = (
        PracticeCoverageStatus.COMPLETE
        if state is PracticeWindowState.COMPLETE
        else PracticeCoverageStatus.PARTIAL
    )
    return PracticeWindowAssessment(
        window_index=index,
        start_tick=start,
        end_tick_exclusive=start + 32,
        complete=state is not PracticeWindowState.UNAVAILABLE,
        state=state,
        execution_coverage=coverage,
        carrier_coverage=coverage,
        organization_coverage=coverage,
        row_count=0,
        unassigned=0,
        ambiguous=0,
    )


def _row(
    index: int,
    *,
    organization_id: str = ORG_A,
    status: PracticeStatus = PracticeStatus.STABLE,
    carrier: str = CARRIER,
    actor: str = "agent-a",
    operator: str = "vary_process",
    process_token: str = "harvest",
) -> ScientificPracticeRow:
    token = _token("carrier", carrier)
    return ScientificPracticeRow(
        window_index=index,
        organization_id=organization_id,
        operator=operator,
        process_token=process_token,
        status=status,
        execution_tokens=(_token("occurrence", f"exec-{index}-{organization_id}"),),
        service_tokens=(_token("occurrence", f"svc-{index}-{organization_id}"),),
        contribution_tokens=(),
        actor_tokens=(_actor(actor),),
        carrier_tokens=(("record", token),),
        surviving_carrier_tokens=(("record", token),),
        coverage=PracticeCoverageStatus.COMPLETE,
    )


def _assessment(
    windows: tuple[PracticeWindowAssessment, ...],
    rows: tuple[ScientificPracticeRow, ...],
) -> ScientificPracticeAssessment:
    return ScientificPracticeAssessment(
        run_id=RUN,
        policy_version=SCIENTIFIC_INSTITUTIONS_POLICY_VERSION,
        windows=windows,
        rows=rows,
        unassigned=0,
        ambiguous=0,
    )


def _assignment(
    transitions: tuple[OrganizationTransition, ...] = (),
) -> OrganizationIdentityAssignment:
    return OrganizationIdentityAssignment(
        policy_version="organization-identity.v1",
        records=(),
        transitions=transitions,
        windows=(),
        coverage=OrganizationCoverage.of(0, 0),
    )


def _lineage(
    assessment: ScientificPracticeAssessment,
    transitions: tuple[OrganizationTransition, ...] = (),
):
    return build_scientific_practice_lineage(
        assessment, _assignment(transitions), transitions
    )


def test_same_org_adjacent_stability_continues_one_episode() -> None:
    assessment = _assessment(
        (_window(0), _window(1)),
        (_row(0, actor="agent-a"), _row(1, actor="agent-b")),
    )
    lineage = _lineage(assessment)
    assert len(lineage.episodes) == 1
    assert [node.window_index for node in lineage.nodes] == [0, 1]
    kinds = [item.kind for item in lineage.transitions]
    assert kinds == [PracticeLineageKind.EMERGED, PracticeLineageKind.CONTINUED]


def test_complete_boundary_without_continuation_lapses() -> None:
    assessment = _assessment(
        (_window(0), _window(1, PracticeWindowState.COMPLETE_EMPTY)),
        (_row(0),),
    )
    lineage = _lineage(assessment)
    lapse = next(
        item
        for item in lineage.transitions
        if item.kind is PracticeLineageKind.LAPSED
    )
    assert lapse.known_at_window == 1
    assert lapse.from_episode_id is not None


def test_incomplete_window_records_unknown_continuity() -> None:
    assessment = _assessment(
        (_window(0), _window(1, PracticeWindowState.PARTIAL)),
        (_row(0),),
    )
    lineage = _lineage(assessment)
    unknown = next(
        item
        for item in lineage.transitions
        if item.kind is PracticeLineageKind.CONTINUITY_UNKNOWN
    )
    assert unknown.known_at_window == 1
    assert not any(
        item.kind is PracticeLineageKind.LAPSED for item in lineage.transitions
    )


def test_reobserved_after_gap_starts_a_new_episode() -> None:
    assessment = _assessment(
        (_window(0), _window(1, PracticeWindowState.PARTIAL), _window(2)),
        (_row(0), _row(2)),
    )
    lineage = _lineage(assessment)
    assert len(lineage.episodes) == 2
    assert any(
        item.kind is PracticeLineageKind.REOBSERVED_AFTER_GAP
        for item in lineage.transitions
    )


def test_handoff_is_confirmed_only_at_w_plus_two() -> None:
    transition = OrganizationTransition(
        from_id=ORG_A,
        to_id=ORG_B,
        window_index=1,
        jaccard=0.5,
        anchor_shared=False,
    )
    assessment = _assessment(
        (_window(0), _window(1), _window(2)),
        (
            _row(0, organization_id=ORG_A),
            _row(1, organization_id=ORG_B, status=PracticeStatus.SUPPORTED),
            _row(2, organization_id=ORG_B),
        ),
    )
    lineage = _lineage(assessment, (transition,))
    handoff = next(
        item
        for item in lineage.transitions
        if item.kind is PracticeLineageKind.HANDOFF
    )
    assert handoff.known_at_window == 2
    assert len(handoff.organization_transition_refs) == 1
    early = lineage.known_through(1)
    assert not any(
        item.kind is PracticeLineageKind.HANDOFF for item in early.transitions
    )
    later = lineage.known_through(2)
    assert any(
        item.kind is PracticeLineageKind.HANDOFF for item in later.transitions
    )


def test_split_and_merge_use_confirmed_handoff_degrees() -> None:
    split_assessment = _assessment(
        (_window(0), _window(1), _window(2)),
        (
            _row(0, organization_id=ORG_A),
            _row(1, organization_id=ORG_B, status=PracticeStatus.SUPPORTED),
            _row(1, organization_id=ORG_C, status=PracticeStatus.SUPPORTED),
            _row(2, organization_id=ORG_B),
            _row(2, organization_id=ORG_C),
        ),
    )
    split = _lineage(
        split_assessment,
        (
            OrganizationTransition(
                from_id=ORG_A,
                to_id=ORG_B,
                window_index=1,
                jaccard=0.5,
                anchor_shared=False,
            ),
            OrganizationTransition(
                from_id=ORG_A,
                to_id=ORG_C,
                window_index=1,
                jaccard=0.5,
                anchor_shared=False,
            ),
        ),
    )
    split_kinds = [item.kind for item in split.transitions]
    assert split_kinds.count(PracticeLineageKind.SPLIT) == 2

    merge_assessment = _assessment(
        (_window(0), _window(1), _window(2)),
        (
            _row(0, organization_id=ORG_A),
            _row(0, organization_id=ORG_B),
            _row(1, organization_id=ORG_C, status=PracticeStatus.SUPPORTED),
            _row(2, organization_id=ORG_C),
        ),
    )
    merged = _lineage(
        merge_assessment,
        (
            OrganizationTransition(
                from_id=ORG_A,
                to_id=ORG_C,
                window_index=1,
                jaccard=0.5,
                anchor_shared=False,
            ),
            OrganizationTransition(
                from_id=ORG_B,
                to_id=ORG_C,
                window_index=1,
                jaccard=0.5,
                anchor_shared=False,
            ),
        ),
    )
    assert any(
        item.kind is PracticeLineageKind.MERGED for item in merged.transitions
    )


def test_name_or_member_overlap_without_carrier_is_not_a_handoff() -> None:
    transition = OrganizationTransition(
        from_id=ORG_A,
        to_id=ORG_B,
        window_index=1,
        jaccard=0.9,
        anchor_shared=True,
    )
    assessment = _assessment(
        (_window(0), _window(1), _window(2)),
        (
            _row(0, organization_id=ORG_A, carrier=CARRIER),
            _row(
                1,
                organization_id=ORG_B,
                carrier=CARRIER_2,
                status=PracticeStatus.SUPPORTED,
            ),
            _row(2, organization_id=ORG_B, carrier=CARRIER_2),
        ),
    )
    lineage = _lineage(assessment, (transition,))
    assert not any(
        item.kind
        in {
            PracticeLineageKind.HANDOFF,
            PracticeLineageKind.SPLIT,
            PracticeLineageKind.MERGED,
            PracticeLineageKind.SPLIT_MERGED,
        }
        for item in lineage.transitions
    )


def test_prefix_view_never_reveals_future_edges() -> None:
    transition = OrganizationTransition(
        from_id=ORG_A,
        to_id=ORG_B,
        window_index=1,
        jaccard=0.5,
        anchor_shared=False,
    )
    assessment = _assessment(
        (_window(0), _window(1), _window(2)),
        (
            _row(0, organization_id=ORG_A),
            _row(1, organization_id=ORG_B, status=PracticeStatus.SUPPORTED),
            _row(2, organization_id=ORG_B),
        ),
    )
    lineage = _lineage(assessment, (transition,))
    prefix = lineage.known_through(1)
    for item in prefix.transitions:
        assert item.known_at_window <= 1
    assert len(prefix.episodes) <= len(lineage.episodes)
    assert {
        (node.episode_id, node.window_index) for node in prefix.nodes
    }.issubset(
        {(node.episode_id, node.window_index) for node in lineage.nodes}
    )
