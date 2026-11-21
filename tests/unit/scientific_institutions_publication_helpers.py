# mypy: ignore-errors
"""Shared V4-32 snapshot fixtures for publication, store, and route tests."""

from __future__ import annotations

from analysis.scientific_institutions_contract import (
    SCIENTIFIC_INSTITUTIONS_POLICY_VERSION,
    PracticeCoverage,
    PracticeCoverageStatus,
    PracticeLane,
    PracticeOrganizationFact,
    PracticeSignalKind,
    PracticeStatus,
    PracticeSupplementFact,
    PracticeWindow,
    derive_practice_token,
)
from analysis.scientific_institutions_detection import (
    PracticeWindowAssessment,
    PracticeWindowState,
    ScientificPracticeAssessment,
    ScientificPracticeRow,
)
from analysis.scientific_institutions_lineage import (
    PracticeEpisode,
    PracticeEpisodeNode,
    PracticeLineageKind,
    PracticeLineageTransition,
    ScientificPracticeLineage,
)
from analysis.scientific_institutions_metrics import (
    ScientificInstitutionsMetricInputs,
)
from experiments.scientific_institutions_context import (
    ScientificInstitutionContextEvidence,
    ScientificInstitutionContextWindow,
)

RUN = "run-publication"
ORG = "org-0123456789abcdef"


def token(domain: str, value: str) -> str:
    return derive_practice_token(domain, RUN, value)


def _window(index: int) -> PracticeWindow:
    return PracticeWindow(
        run_id=RUN,
        window_index=index,
        start_tick=index * 32,
        end_tick_exclusive=index * 32 + 32,
        complete=True,
        coverage=(
            PracticeCoverage(
                run_id=RUN,
                window_index=index,
                lane=PracticeLane.EXECUTION,
                status=PracticeCoverageStatus.COMPLETE,
            ),
            PracticeCoverage(
                run_id=RUN,
                window_index=index,
                lane=PracticeLane.CARRIER,
                status=PracticeCoverageStatus.COMPLETE,
            ),
            PracticeCoverage(
                run_id=RUN,
                window_index=index,
                lane=PracticeLane.ORGANIZATION,
                status=PracticeCoverageStatus.COMPLETE,
            ),
        ),
    )


def _row(index: int, status: PracticeStatus) -> ScientificPracticeRow:
    return ScientificPracticeRow(
        window_index=index,
        organization_id=ORG,
        operator="vary_process",
        process_token="harvest",
        status=status,
        execution_tokens=(token("occurrence", f"exec-{index}"),),
        service_tokens=(token("occurrence", f"svc-{index}"),),
        contribution_tokens=(token("occurrence", f"contrib-{index}"),),
        actor_tokens=(token("actor", f"agent-{index}"),),
        carrier_tokens=(("record", token("carrier", "artifact-1")),),
        surviving_carrier_tokens=(
            ("record", token("carrier", "artifact-1")),
        ),
        coverage=PracticeCoverageStatus.COMPLETE,
    )


def assessment() -> ScientificPracticeAssessment:
    return ScientificPracticeAssessment(
        run_id=RUN,
        policy_version=SCIENTIFIC_INSTITUTIONS_POLICY_VERSION,
        windows=tuple(
            PracticeWindowAssessment(
                window_index=index,
                start_tick=index * 32,
                end_tick_exclusive=index * 32 + 32,
                complete=True,
                state=PracticeWindowState.COMPLETE,
                execution_coverage=PracticeCoverageStatus.COMPLETE,
                carrier_coverage=PracticeCoverageStatus.COMPLETE,
                organization_coverage=PracticeCoverageStatus.COMPLETE,
                row_count=1,
                unassigned=0,
                ambiguous=0,
            )
            for index in range(2)
        ),
        rows=(
            _row(0, PracticeStatus.STABLE),
            _row(1, PracticeStatus.STABLE),
        ),
        unassigned=0,
        ambiguous=0,
    )


def lineage() -> ScientificPracticeLineage:
    episode = PracticeEpisode(
        episode_id="sci-inst-0123456789abcdef",
        organization_id=ORG,
        operator="vary_process",
        process_token="harvest",
        first_stable_window=0,
        last_stable_window=1,
        windows=(0, 1),
        carrier_tokens=(("record", token("carrier", "artifact-1")),),
    )
    nodes = tuple(
        PracticeEpisodeNode(
            episode_id=episode.episode_id,
            window_index=index,
            organization_id=ORG,
            operator="vary_process",
            process_token="harvest",
            actor_tokens=(token("actor", f"agent-{index}"),),
            carrier_tokens=episode.carrier_tokens,
            known_at_window=index,
        )
        for index in range(2)
    )
    transitions = (
        PracticeLineageTransition(
            kind=PracticeLineageKind.EMERGED,
            from_episode_id=None,
            to_episode_id=episode.episode_id,
            from_window=None,
            to_window=0,
            known_at_window=0,
            from_organization_id=None,
            to_organization_id=ORG,
        ),
        PracticeLineageTransition(
            kind=PracticeLineageKind.CONTINUED,
            from_episode_id=episode.episode_id,
            to_episode_id=episode.episode_id,
            from_window=0,
            to_window=1,
            known_at_window=1,
            from_organization_id=ORG,
            to_organization_id=ORG,
            carrier_tokens=episode.carrier_tokens,
        ),
    )
    return ScientificPracticeLineage(
        run_id=RUN,
        policy_version=SCIENTIFIC_INSTITUTIONS_POLICY_VERSION,
        episodes=(episode,),
        nodes=nodes,
        transitions=transitions,
    )


def context() -> ScientificInstitutionContextEvidence:
    fact = PracticeOrganizationFact(
        run_id=RUN,
        window_index=0,
        organization_id=ORG,
        candidate_key="cand-0123456789abcdef",
        participant_tokens=(token("actor", "agent-0"),),
        anchor_tokens=(("record", token("carrier", "artifact-1")),),
        procedure_tokens=(),
        record_tokens=(token("carrier", "artifact-1"),),
        claimant_tokens=(token("actor", "agent-0"),),
        coverage=PracticeCoverageStatus.COMPLETE,
        links=(),
    )
    supplement = PracticeSupplementFact(
        run_id=RUN,
        window_index=0,
        organization_id=ORG,
        signal=PracticeSignalKind.EXPERIMENTER,
        actor_tokens=(token("actor", "agent-0"),),
        carrier_tokens=(),
        tick=1,
        count=1,
    )
    return ScientificInstitutionContextEvidence(
        run_id=RUN,
        windows=(
            ScientificInstitutionContextWindow(
                window=_window(0),
                executions=(),
                carriers=(),
                surviving_carriers=(),
                organizations=(fact,),
                supplements=(supplement,),
                unassigned=0,
                ambiguous=0,
            ),
        ),
    )


def metric_inputs() -> ScientificInstitutionsMetricInputs:
    return ScientificInstitutionsMetricInputs(
        assessment=assessment(),
        lineage=lineage(),
        context=context(),
    )
