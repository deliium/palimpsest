# mypy: ignore-errors
"""V4-32 persistent science-practice detection thresholds and coverage."""

from __future__ import annotations

import pytest

from analysis.scientific_institutions_contract import (
    PracticeCarrierAction,
    PracticeCarrierFact,
    PracticeCarrierKind,
    PracticeCoverage,
    PracticeCoverageStatus,
    PracticeExecutionFact,
    PracticeLane,
    PracticeOrganizationFact,
    PracticeOrganizationLink,
    PracticeSignalKind,
    PracticeStatus,
    PracticeSupplementFact,
    PracticeWindow,
    derive_practice_token,
)
from analysis.scientific_institutions_detection import (
    PracticeWindowState,
    detect_scientific_practice,
)
from experiments.scientific_institutions_completed_run import (
    PracticeCarrierSurvivalFact,
)
from experiments.scientific_institutions_context import (
    ScientificInstitutionContextEvidence,
    ScientificInstitutionContextWindow,
)

pytestmark = pytest.mark.unit

RUN = "run-detect"
ORG = "org-0123456789abcdef"
CARRIER = "artifact-1"
PROJECT = "project-1"


def _token(domain: str, value: str) -> str:
    return derive_practice_token(domain, RUN, value)


def _actor(value: str) -> str:
    return _token("actor", value)


def _window_parts(
    index: int,
    *,
    complete: bool = True,
    execution_status: PracticeCoverageStatus = PracticeCoverageStatus.COMPLETE,
    organization_status: PracticeCoverageStatus = PracticeCoverageStatus.COMPLETE,
    carrier_status: PracticeCoverageStatus = PracticeCoverageStatus.COMPLETE,
) -> PracticeWindow:
    start = index * 32
    end = start + (32 if complete else 4)
    return PracticeWindow(
        run_id=RUN,
        window_index=index,
        start_tick=start,
        end_tick_exclusive=end,
        complete=complete,
        coverage=(
            PracticeCoverage(
                run_id=RUN,
                window_index=index,
                lane=PracticeLane.EXECUTION,
                status=execution_status,
            ),
            PracticeCoverage(
                run_id=RUN,
                window_index=index,
                lane=PracticeLane.CARRIER,
                status=carrier_status,
            ),
            PracticeCoverage(
                run_id=RUN,
                window_index=index,
                lane=PracticeLane.ORGANIZATION,
                status=organization_status,
            ),
        ),
    )


def _execution(
    index: int, actor: str, *, tick: int | None = None
) -> PracticeExecutionFact:
    return PracticeExecutionFact(
        run_id=RUN,
        occurrence_token=_token("occurrence", f"exec-{index}-{actor}"),
        actor_token=_actor(actor),
        tick=index * 32 + 5 if tick is None else tick,
        operator="vary_process",
        process_token="harvest",
    )


def _service(
    index: int,
    actor: str,
    *,
    carrier: str = CARRIER,
    action: PracticeCarrierAction = PracticeCarrierAction.ANNOTATE,
    tick: int | None = None,
) -> PracticeCarrierFact:
    return PracticeCarrierFact(
        run_id=RUN,
        occurrence_token=_token("occurrence", f"service-{index}-{actor}"),
        actor_token=_actor(actor),
        tick=index * 32 + 6 if tick is None else tick,
        carrier_kind=PracticeCarrierKind.RECORD,
        carrier_token=_token("carrier", carrier),
        source_root_token=_token("source_root", carrier),
        action=action,
    )


def _survival(carrier: str = CARRIER) -> PracticeCarrierSurvivalFact:
    return PracticeCarrierSurvivalFact(
        carrier_kind=PracticeCarrierKind.RECORD,
        carrier_token=_token("carrier", carrier),
        source_root_token=_token("source_root", carrier),
    )


def _fact(
    index: int,
    *,
    actors: tuple[str, ...],
    execution: PracticeExecutionFact | None,
    service: PracticeCarrierFact | None,
    carrier: str = CARRIER,
) -> PracticeOrganizationFact:
    links: list[PracticeOrganizationLink] = []
    if execution is not None:
        links.append(
            PracticeOrganizationLink(
                actor_token=execution.actor_token,
                execution_token=execution.occurrence_token,
                contribution_token=_token("occurrence", f"contrib-{index}"),
                contribution_tick=index * 32 + 2,
            )
        )
    if service is not None:
        links.append(
            PracticeOrganizationLink(
                actor_token=service.actor_token,
                service_token=service.occurrence_token,
                contribution_token=_token("occurrence", f"contrib-{index}"),
                contribution_tick=index * 32 + 2,
                carrier_kind=service.carrier_kind,
                carrier_token=service.carrier_token,
            )
        )
    return PracticeOrganizationFact(
        run_id=RUN,
        window_index=index,
        organization_id=ORG,
        candidate_key=f"cand-{index:016x}",
        participant_tokens=tuple(_actor(value) for value in actors),
        anchor_tokens=(
            ("collective_project", _token("carrier", PROJECT)),
            ("record", _token("carrier", carrier)),
        ),
        procedure_tokens=(),
        record_tokens=(_token("carrier", carrier),),
        claimant_tokens=tuple(_actor(value) for value in actors),
        coverage=PracticeCoverageStatus.COMPLETE,
        links=tuple(links),
    )


def _context_window(
    index: int,
    *,
    actors: tuple[str, ...] = ("agent-a", "agent-b"),
    execution: PracticeExecutionFact | None = None,
    service: PracticeCarrierFact | None = None,
    surviving: tuple[PracticeCarrierSurvivalFact, ...] = (),
    complete: bool = True,
    execution_status: PracticeCoverageStatus = PracticeCoverageStatus.COMPLETE,
    organization_status: PracticeCoverageStatus = PracticeCoverageStatus.COMPLETE,
    unassigned: int = 0,
    ambiguous: int = 0,
) -> ScientificInstitutionContextWindow:
    window = _window_parts(
        index,
        complete=complete,
        execution_status=execution_status,
        organization_status=organization_status,
    )
    fact = _fact(
        index,
        actors=actors,
        execution=execution,
        service=service,
    )
    return ScientificInstitutionContextWindow(
        window=window,
        executions=(execution,) if execution is not None else (),
        carriers=(service,) if service is not None else (),
        surviving_carriers=surviving,
        organizations=(fact,),
        supplements=(),
        unassigned=unassigned,
        ambiguous=ambiguous,
    )


def _assessment(*windows: ScientificInstitutionContextWindow):
    return detect_scientific_practice(
        ScientificInstitutionContextEvidence(run_id=RUN, windows=windows)
    )


def test_two_adjacent_supported_windows_become_stable_on_the_second() -> None:
    first = _context_window(
        0,
        actors=("agent-a",),
        execution=_execution(0, "agent-a"),
        service=_service(0, "agent-a"),
        surviving=(_survival(),),
    )
    second = _context_window(
        1,
        actors=("agent-b",),
        execution=_execution(1, "agent-b"),
        service=_service(1, "agent-b"),
        surviving=(_survival(),),
    )
    assessment = _assessment(first, second)
    assert [row.status for row in assessment.rows] == [
        PracticeStatus.SUPPORTED,
        PracticeStatus.STABLE,
    ]
    assert assessment.rows[0].execution_tokens
    assert assessment.rows[1].service_tokens


def test_solo_repeat_is_supported_but_never_stable() -> None:
    first = _context_window(
        0,
        execution=_execution(0, "agent-a"),
        service=_service(0, "agent-a"),
        surviving=(_survival(),),
    )
    second = _context_window(
        1,
        execution=_execution(1, "agent-a"),
        service=_service(1, "agent-a"),
        surviving=(_survival(),),
    )
    assessment = _assessment(first, second)
    assert [row.status for row in assessment.rows] == [
        PracticeStatus.SUPPORTED,
        PracticeStatus.SUPPORTED,
    ]


def test_same_window_burst_does_not_make_a_stable_episode() -> None:
    first = _context_window(
        0,
        execution=_execution(0, "agent-a"),
        service=_service(0, "agent-b"),
        surviving=(_survival(),),
    )
    second = _context_window(1, surviving=(_survival(),))
    assessment = _assessment(first, second)
    statuses = [row.status for row in assessment.rows]
    assert statuses[0] is PracticeStatus.SUPPORTED
    assert PracticeStatus.STABLE not in statuses
    assert assessment.rows[-1].status is PracticeStatus.NOT_OBSERVED


def test_partial_window_is_unavailable_and_never_stable() -> None:
    first = _context_window(
        0,
        execution=_execution(0, "agent-a"),
        service=_service(0, "agent-a"),
        surviving=(_survival(),),
    )
    second = _context_window(
        1,
        execution=_execution(1, "agent-b"),
        service=_service(1, "agent-b"),
        surviving=(_survival(),),
        execution_status=PracticeCoverageStatus.PARTIAL,
    )
    assessment = _assessment(first, second)
    assert assessment.windows[1].state is PracticeWindowState.PARTIAL
    assert all(
        row.status is not PracticeStatus.STABLE for row in assessment.rows
    )


def test_different_activity_key_does_not_continue() -> None:
    first = _context_window(
        0,
        execution=_execution(0, "agent-a"),
        service=_service(0, "agent-a"),
        surviving=(_survival(),),
    )
    other = PracticeExecutionFact(
        run_id=RUN,
        occurrence_token=_token("occurrence", "exec-other"),
        actor_token=_actor("agent-b"),
        tick=37,
        operator="combine",
        process_token="harvest",
    )
    second = _context_window(
        1,
        execution=other,
        service=_service(1, "agent-b"),
        surviving=(_survival(),),
    )
    assessment = _assessment(first, second)
    assert all(
        row.status is not PracticeStatus.STABLE for row in assessment.rows
    )


def test_substituted_carrier_does_not_continue() -> None:
    first = _context_window(
        0,
        execution=_execution(0, "agent-a"),
        service=_service(0, "agent-a"),
        surviving=(_survival(),),
    )
    second = _context_window(
        1,
        execution=_execution(1, "agent-b"),
        service=_service(1, "agent-b", carrier="artifact-2"),
        surviving=(_survival("artifact-2"),),
    )
    assessment = _assessment(first, second)
    assert all(
        row.status is not PracticeStatus.STABLE for row in assessment.rows
    )


def test_end_of_window_destruction_yields_observed_only() -> None:
    first = _context_window(
        0,
        execution=_execution(0, "agent-a"),
        service=_service(0, "agent-a"),
        surviving=(_survival(),),
    )
    second = _context_window(
        1,
        execution=_execution(1, "agent-b"),
        service=_service(1, "agent-b"),
        surviving=(),
    )
    assessment = _assessment(first, second)
    assert assessment.rows[1].status is PracticeStatus.OBSERVED_ONLY


def test_complete_empty_window_is_distinct_from_unavailable() -> None:
    empty = _context_window(0, surviving=(_survival(),))
    assessment = _assessment(empty)
    assert assessment.windows[0].state is PracticeWindowState.COMPLETE_EMPTY
    assert assessment.rows == ()


def test_unassigned_and_ambiguous_counts_stay_outside_candidates() -> None:
    window = _context_window(
        0,
        execution=_execution(0, "agent-a"),
        service=_service(0, "agent-a"),
        surviving=(_survival(),),
        unassigned=3,
        ambiguous=2,
    )
    assessment = _assessment(window)
    assert assessment.unassigned == 3
    assert assessment.ambiguous == 2
    assert len(assessment.rows) == 1


def test_prefix_invariance_when_adding_a_future_window() -> None:
    first = _context_window(
        0,
        actors=("agent-a",),
        execution=_execution(0, "agent-a"),
        service=_service(0, "agent-a"),
        surviving=(_survival(),),
    )
    second = _context_window(
        1,
        actors=("agent-b",),
        execution=_execution(1, "agent-b"),
        service=_service(1, "agent-b"),
        surviving=(_survival(),),
    )
    third = _context_window(
        2,
        actors=("agent-a",),
        execution=_execution(2, "agent-a"),
        service=_service(2, "agent-a"),
        surviving=(_survival(),),
    )
    prefix = _assessment(first, second)
    extended = _assessment(first, second, third)
    assert [
        (row.window_index, row.status, row.organization_id)
        for row in prefix.rows
    ] == [
        (row.window_index, row.status, row.organization_id)
        for row in extended.rows
        if row.window_index < 2
    ]


def test_optional_signals_do_not_become_qualifying_votes() -> None:
    signal = PracticeSupplementFact(
        run_id=RUN,
        window_index=0,
        organization_id=ORG,
        signal=PracticeSignalKind.TEACHER,
        actor_tokens=(_actor("agent-a"), _actor("agent-b")),
        carrier_tokens=(),
        tick=5,
        count=1,
    )
    window = _context_window(
        0,
        execution=_execution(0, "agent-a"),
        service=_service(0, "agent-a"),
        surviving=(_survival(),),
    )
    window = ScientificInstitutionContextWindow(
        window=window.window,
        executions=window.executions,
        carriers=window.carriers,
        surviving_carriers=window.surviving_carriers,
        organizations=window.organizations,
        supplements=(signal,),
        unassigned=0,
        ambiguous=0,
    )
    assessment = _assessment(window)
    assert assessment.rows[0].status is PracticeStatus.SUPPORTED
