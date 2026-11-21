# mypy: ignore-errors
"""V4-32 detached practice contract: windows, facts, coverage, caps, tokens."""

from __future__ import annotations

import pytest

from analysis.scientific_institutions_contract import (
    MAX_BOUNDARY_OWNERS,
    MAX_CUMULATIVE_EVENTS,
    MAX_ORGANIZATION_CONTRIBUTIONS,
    MAX_PRACTICE_WINDOWS,
    MAX_PUBLISHED_ROWS,
    MAX_WINDOW_ROWS,
    OPTIONAL_PRACTICE_LANES,
    PRACTICE_WINDOW_TICKS,
    PracticeCarrierAction,
    PracticeCarrierFact,
    PracticeCarrierKind,
    PracticeCoverage,
    PracticeCoverageStatus,
    PracticeExecutionFact,
    PracticeLane,
    PracticeLayer,
    PracticeOrganizationFact,
    PracticeOrganizationLink,
    PracticeSignalKind,
    PracticeStatus,
    PracticeSupplementFact,
    PracticeWindow,
    ScientificInstitutionsError,
    canonical_activity_keys,
    derive_practice_token,
    practice_activity_key,
    require_boundary_owner_cap,
    require_cumulative_event_cap,
    require_organization_contribution_cap,
    require_practice_token,
    require_practice_window_index,
    require_published_row_cap,
    require_window_row_cap,
)

pytestmark = pytest.mark.unit

RUN = "run-contract"
ORG = "org-0123456789abcdef"


def _token(domain: str, value: str) -> str:
    return derive_practice_token(domain, RUN, value)


def _coverage(
    index: int, lane: PracticeLane, status: PracticeCoverageStatus
) -> PracticeCoverage:
    return PracticeCoverage(
        run_id=RUN, window_index=index, lane=lane, status=status
    )


def _window(index: int = 0, *, complete: bool = True) -> PracticeWindow:
    start = index * PRACTICE_WINDOW_TICKS
    end = start + (PRACTICE_WINDOW_TICKS if complete else 4)
    return PracticeWindow(
        run_id=RUN,
        window_index=index,
        start_tick=start,
        end_tick_exclusive=end,
        complete=complete,
        coverage=(
            _coverage(index, PracticeLane.EXECUTION, PracticeCoverageStatus.COMPLETE),
            _coverage(index, PracticeLane.CARRIER, PracticeCoverageStatus.COMPLETE),
            _coverage(
                index, PracticeLane.ORGANIZATION, PracticeCoverageStatus.COMPLETE
            ),
        ),
    )


def test_constants_and_optional_lanes_are_exact() -> None:
    assert PRACTICE_WINDOW_TICKS == 32
    assert MAX_PRACTICE_WINDOWS == 16
    assert MAX_BOUNDARY_OWNERS == 64
    assert MAX_ORGANIZATION_CONTRIBUTIONS == 128
    assert MAX_CUMULATIVE_EVENTS == 32_768
    assert MAX_WINDOW_ROWS == 4_096
    assert MAX_PUBLISHED_ROWS == 8_192
    assert OPTIONAL_PRACTICE_LANES == (
        "archive",
        "institutional_memory",
        "instrument",
        "procedure",
        "record",
        "replication",
        "teaching",
    )
    assert tuple(item.value for item in PracticeStatus) == (
        "supported",
        "stable",
        "observed_only",
        "not_observed",
        "unavailable",
    )
    assert tuple(item.value for item in PracticeLayer) == (
        "objective_receipt",
        "owner_claim",
        "analytical_association",
    )


def test_window_interval_endpoints_are_half_open() -> None:
    first = _window(0)
    second = _window(1)
    assert (first.start, first.end_exclusive) == (0, 32)
    assert (second.start, second.end_exclusive) == (32, 64)
    assert first.covers(0) and first.covers(31)
    assert not first.covers(32)
    assert second.covers(32)
    assert first.lane_status(PracticeLane.EXECUTION) is PracticeCoverageStatus.COMPLETE


def test_incomplete_tail_is_reported_but_never_complete() -> None:
    tail = _window(3, complete=False)
    assert tail.complete is False
    assert tail.end_exclusive - tail.start_tick == 4
    with pytest.raises(ScientificInstitutionsError):
        PracticeWindow(
            run_id=RUN,
            window_index=3,
            start_tick=96,
            end_tick_exclusive=100,
            complete=True,
        )
    with pytest.raises(ScientificInstitutionsError):
        PracticeWindow(
            run_id=RUN,
            window_index=3,
            start_tick=96,
            end_tick_exclusive=128,
            complete=False,
        )


def test_window_rejects_wrong_anchor_and_duplicate_lane() -> None:
    with pytest.raises(ScientificInstitutionsError):
        PracticeWindow(
            run_id=RUN,
            window_index=1,
            start_tick=0,
            end_tick_exclusive=32,
            complete=True,
        )
    duplicate = _window(0)
    with pytest.raises(ScientificInstitutionsError):
        PracticeWindow(
            run_id=RUN,
            window_index=0,
            start_tick=0,
            end_tick_exclusive=32,
            complete=True,
            coverage=(
                duplicate.coverage[0],
                duplicate.coverage[0],
            ),
        )
    with pytest.raises(ScientificInstitutionsError):
        PracticeWindow(
            run_id="other-run",
            window_index=0,
            start_tick=0,
            end_tick_exclusive=32,
            complete=True,
            coverage=(duplicate.coverage[0],),
        )


@pytest.mark.parametrize(
    ("helper", "cap"),
    (
        (require_practice_window_index, MAX_PRACTICE_WINDOWS - 1),
        (require_boundary_owner_cap, MAX_BOUNDARY_OWNERS),
        (require_organization_contribution_cap, MAX_ORGANIZATION_CONTRIBUTIONS),
        (require_cumulative_event_cap, MAX_CUMULATIVE_EVENTS),
        (require_window_row_cap, MAX_WINDOW_ROWS),
        (require_published_row_cap, MAX_PUBLISHED_ROWS),
    ),
)
def test_caps_accept_n_and_reject_n_plus_one(helper: object, cap: int) -> None:
    assert helper(cap) == cap  # type: ignore[operator]
    with pytest.raises(ScientificInstitutionsError):
        helper(cap + 1)  # type: ignore[operator]


def test_caps_reject_boolean_counts() -> None:
    with pytest.raises(ScientificInstitutionsError):
        require_boundary_owner_cap(True)


def test_token_domains_do_not_collide_for_the_same_raw_value() -> None:
    actor = _token("actor", "agent-1")
    carrier = _token("carrier", "agent-1")
    assert actor != carrier
    assert require_practice_token(actor) == actor
    assert derive_practice_token("actor", RUN, "agent-1") == actor
    with pytest.raises(ScientificInstitutionsError):
        derive_practice_token("unknown", RUN, "agent-1")
    with pytest.raises(ScientificInstitutionsError):
        require_practice_token("agent-1")


def test_owner_local_tokens_are_qualified_by_owner() -> None:
    left_owner = _token("actor", "owner-a")
    right_owner = _token("actor", "owner-b")
    left = derive_practice_token("owner_local", RUN, left_owner, "office-1")
    right = derive_practice_token("owner_local", RUN, right_owner, "office-1")
    assert left != right


def test_execution_fact_keeps_closed_activity_key_and_layer() -> None:
    fact = PracticeExecutionFact(
        run_id=RUN,
        occurrence_token=_token("occurrence", "event-1"),
        actor_token=_token("actor", "agent-1"),
        tick=7,
        operator="vary_process",
        process_token="harvest",
    )
    assert fact.activity_key == ("vary_process", "harvest")
    assert canonical_activity_keys((fact, fact)) == (("vary_process", "harvest"),)
    assert practice_activity_key("vary_process", "harvest") == fact.activity_key
    with pytest.raises(ScientificInstitutionsError):
        PracticeExecutionFact(
            run_id=RUN,
            occurrence_token=_token("occurrence", "event-1"),
            actor_token=_token("actor", "agent-1"),
            tick=True,
            operator="vary_process",
            process_token="harvest",
        )
    with pytest.raises(ScientificInstitutionsError):
        PracticeExecutionFact(
            run_id=RUN,
            occurrence_token=_token("occurrence", "event-1"),
            actor_token=_token("actor", "agent-1"),
            tick=7,
            operator="vary_process",
            process_token="harvest",
            layer=PracticeLayer.OWNER_CLAIM,
        )


def test_carrier_fact_requires_consistent_kind_and_copy_parent() -> None:
    base = dict(
        run_id=RUN,
        occurrence_token=_token("occurrence", "event-2"),
        actor_token=_token("actor", "agent-1"),
        tick=8,
        source_root_token=_token("source_root", "artifact-1"),
    )
    record = PracticeCarrierFact(
        **base,
        carrier_kind=PracticeCarrierKind.RECORD,
        carrier_token=_token("carrier", "artifact-1"),
        action=PracticeCarrierAction.ANNOTATE,
    )
    assert record.member_token is None
    member = PracticeCarrierFact(
        **base,
        carrier_kind=PracticeCarrierKind.REPOSITORY_MEMBER,
        carrier_token=_token("carrier", "repo-1"),
        member_token=_token("carrier", "artifact-1"),
        action=PracticeCarrierAction.DEPOSIT,
    )
    assert member.member_token is not None
    with pytest.raises(ScientificInstitutionsError):
        PracticeCarrierFact(
            **base,
            carrier_kind=PracticeCarrierKind.REPOSITORY_MEMBER,
            carrier_token=_token("carrier", "repo-1"),
            action=PracticeCarrierAction.DEPOSIT,
        )
    with pytest.raises(ScientificInstitutionsError):
        PracticeCarrierFact(
            **base,
            carrier_kind=PracticeCarrierKind.RECORD,
            carrier_token=_token("carrier", "artifact-1"),
            action=PracticeCarrierAction.ANNOTATE,
            parent_token=_token("carrier", "parent"),
        )
    copy = PracticeCarrierFact(
        **base,
        carrier_kind=PracticeCarrierKind.RECORD,
        carrier_token=_token("carrier", "artifact-2"),
        parent_token=_token("carrier", "artifact-1"),
        action=PracticeCarrierAction.COPY,
    )
    assert copy.parent_token is not None


def test_organization_fact_sorts_and_rejects_duplicate_identities() -> None:
    actor_a = _token("actor", "agent-a")
    actor_b = _token("actor", "agent-b")
    link = PracticeOrganizationLink(
        actor_token=actor_a,
        execution_token=_token("occurrence", "event-1"),
        contribution_token=_token("occurrence", "project-1"),
        contribution_tick=4,
        carrier_kind=PracticeCarrierKind.RECORD,
        carrier_token=_token("carrier", "artifact-1"),
    )
    fact = PracticeOrganizationFact(
        run_id=RUN,
        window_index=0,
        organization_id=ORG,
        candidate_key="cand-0123456789abcdef",
        participant_tokens=(actor_b, actor_a),
        anchor_tokens=(
            ("goal", derive_practice_token("owner_local", RUN, actor_a, "goal-1")),
        ),
        procedure_tokens=(),
        record_tokens=(),
        claimant_tokens=(actor_a,),
        coverage=PracticeCoverageStatus.COMPLETE,
        links=(link,),
    )
    assert fact.participant_tokens == tuple(sorted((actor_a, actor_b)))
    with pytest.raises(ScientificInstitutionsError):
        PracticeOrganizationFact(
            run_id=RUN,
            window_index=0,
            organization_id=ORG,
            candidate_key="cand-0123456789abcdef",
            participant_tokens=(actor_a, actor_a),
            anchor_tokens=(),
            procedure_tokens=(),
            record_tokens=(),
            claimant_tokens=(),
            coverage=PracticeCoverageStatus.COMPLETE,
        )
    with pytest.raises(ScientificInstitutionsError):
        PracticeOrganizationFact(
            run_id=RUN,
            window_index=0,
            organization_id="org-not-a-token",
            candidate_key="cand-0123456789abcdef",
            participant_tokens=(actor_a,),
            anchor_tokens=(),
            procedure_tokens=(),
            record_tokens=(),
            claimant_tokens=(),
            coverage=PracticeCoverageStatus.COMPLETE,
        )
    with pytest.raises(ScientificInstitutionsError):
        PracticeOrganizationLink(
            actor_token=actor_a,
            contribution_token=_token("occurrence", "project-1"),
        )


def test_supplement_fact_is_contextual_and_rejects_empty_counts() -> None:
    fact = PracticeSupplementFact(
        run_id=RUN,
        window_index=0,
        organization_id=ORG,
        signal=PracticeSignalKind.TEACHER,
        actor_tokens=(_token("actor", "agent-a"),),
        carrier_tokens=(("record", _token("carrier", "artifact-1")),),
        tick=5,
        count=1,
    )
    assert fact.contextual is True
    assert fact.layer is PracticeLayer.ANALYTICAL_ASSOCIATION
    with pytest.raises(ScientificInstitutionsError):
        PracticeSupplementFact(
            run_id=RUN,
            window_index=0,
            organization_id=None,
            signal=PracticeSignalKind.TEACHER,
            actor_tokens=(),
            carrier_tokens=(),
            tick=5,
            count=0,
        )
    with pytest.raises(ScientificInstitutionsError):
        PracticeSupplementFact(
            run_id=RUN,
            window_index=0,
            organization_id=None,
            signal=PracticeSignalKind.TEACHER,
            actor_tokens=(),
            carrier_tokens=(),
            tick=5,
            count=1,
            layer=PracticeLayer.OBJECTIVE_RECEIPT,
        )
