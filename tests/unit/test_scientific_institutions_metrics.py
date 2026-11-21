# mypy: ignore-errors
"""V4-32 descriptive metric families: ids, keys, counts, and append-only."""

from __future__ import annotations

import pytest

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
    compute_scientific_institution_lineage,
    compute_scientific_institution_practice,
    compute_scientific_institution_roles_and_carriers,
)
from analysis.specifications import (
    METRIC_FAMILY_COUNT,
    all_metric_specifications,
    metric_specification,
)
from experiments.scientific_institutions_context import (
    ScientificInstitutionContextEvidence,
    ScientificInstitutionContextWindow,
)

pytestmark = pytest.mark.unit

RUN = "run-metrics"
REV = "rev-1"
ORG = "org-0123456789abcdef"


def _token(domain: str, value: str) -> str:
    return derive_practice_token(domain, RUN, value)


def _window(index: int, status: PracticeCoverageStatus):
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
                status=status,
            ),
            PracticeCoverage(
                run_id=RUN,
                window_index=index,
                lane=PracticeLane.CARRIER,
                status=status,
            ),
            PracticeCoverage(
                run_id=RUN,
                window_index=index,
                lane=PracticeLane.ORGANIZATION,
                status=status,
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
        execution_tokens=(_token("occurrence", f"exec-{index}"),),
        service_tokens=(_token("occurrence", f"svc-{index}"),),
        contribution_tokens=(),
        actor_tokens=(_token("actor", f"agent-{index}"),),
        carrier_tokens=(("record", _token("carrier", "artifact-1")),),
        surviving_carrier_tokens=(
            ("record", _token("carrier", "artifact-1")),
        ),
        coverage=PracticeCoverageStatus.COMPLETE,
    )


def _assessment() -> ScientificPracticeAssessment:
    return ScientificPracticeAssessment(
        run_id=RUN,
        policy_version=SCIENTIFIC_INSTITUTIONS_POLICY_VERSION,
        windows=(
            PracticeWindowAssessment(
                window_index=0,
                start_tick=0,
                end_tick_exclusive=32,
                complete=True,
                state=PracticeWindowState.COMPLETE,
                execution_coverage=PracticeCoverageStatus.COMPLETE,
                carrier_coverage=PracticeCoverageStatus.COMPLETE,
                organization_coverage=PracticeCoverageStatus.COMPLETE,
                row_count=2,
                unassigned=1,
                ambiguous=1,
            ),
            PracticeWindowAssessment(
                window_index=1,
                start_tick=32,
                end_tick_exclusive=64,
                complete=True,
                state=PracticeWindowState.COMPLETE_EMPTY,
                execution_coverage=PracticeCoverageStatus.COMPLETE,
                carrier_coverage=PracticeCoverageStatus.COMPLETE,
                organization_coverage=PracticeCoverageStatus.COMPLETE,
                row_count=0,
                unassigned=0,
                ambiguous=0,
            ),
            PracticeWindowAssessment(
                window_index=2,
                start_tick=64,
                end_tick_exclusive=96,
                complete=True,
                state=PracticeWindowState.PARTIAL,
                execution_coverage=PracticeCoverageStatus.PARTIAL,
                carrier_coverage=PracticeCoverageStatus.PARTIAL,
                organization_coverage=PracticeCoverageStatus.PARTIAL,
                row_count=1,
                unassigned=0,
                ambiguous=0,
            ),
        ),
        rows=(
            _row(0, PracticeStatus.STABLE),
            _row(0, PracticeStatus.SUPPORTED),
            _row(2, PracticeStatus.OBSERVED_ONLY),
        ),
        unassigned=1,
        ambiguous=1,
    )


def _lineage() -> ScientificPracticeLineage:
    episode = PracticeEpisode(
        episode_id="sci-inst-0123456789abcdef",
        organization_id=ORG,
        operator="vary_process",
        process_token="harvest",
        first_stable_window=0,
        last_stable_window=0,
        windows=(0,),
        carrier_tokens=(("record", _token("carrier", "artifact-1")),),
    )
    node = PracticeEpisodeNode(
        episode_id=episode.episode_id,
        window_index=0,
        organization_id=ORG,
        operator="vary_process",
        process_token="harvest",
        actor_tokens=(_token("actor", "agent-0"),),
        carrier_tokens=episode.carrier_tokens,
        known_at_window=0,
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
            kind=PracticeLineageKind.LAPSED,
            from_episode_id=episode.episode_id,
            to_episode_id=None,
            from_window=0,
            to_window=1,
            known_at_window=1,
            from_organization_id=ORG,
            to_organization_id=None,
        ),
    )
    return ScientificPracticeLineage(
        run_id=RUN,
        policy_version=SCIENTIFIC_INSTITUTIONS_POLICY_VERSION,
        episodes=(episode,),
        nodes=(node,),
        transitions=transitions,
    )


def _context() -> ScientificInstitutionContextEvidence:
    window = _window(0, PracticeCoverageStatus.COMPLETE)
    fact = PracticeOrganizationFact(
        run_id=RUN,
        window_index=0,
        organization_id=ORG,
        candidate_key="cand-0123456789abcdef",
        participant_tokens=(_token("actor", "agent-0"),),
        anchor_tokens=(),
        procedure_tokens=(),
        record_tokens=(),
        claimant_tokens=(),
        coverage=PracticeCoverageStatus.COMPLETE,
        links=(),
    )
    supplements = (
        PracticeSupplementFact(
            run_id=RUN,
            window_index=0,
            organization_id=ORG,
            signal=PracticeSignalKind.EXPERIMENTER,
            actor_tokens=(_token("actor", "agent-0"),),
            carrier_tokens=(),
            tick=1,
            count=1,
        ),
        PracticeSupplementFact(
            run_id=RUN,
            window_index=0,
            organization_id=ORG,
            signal=PracticeSignalKind.RECORD_KEEPER,
            actor_tokens=(_token("actor", "agent-1"),),
            carrier_tokens=(("record", _token("carrier", "artifact-1")),),
            tick=2,
            count=1,
        ),
    )
    return ScientificInstitutionContextEvidence(
        run_id=RUN,
        windows=(
            ScientificInstitutionContextWindow(
                window=window,
                executions=(),
                carriers=(),
                surviving_carriers=(),
                organizations=(fact,),
                supplements=supplements,
                unassigned=1,
                ambiguous=1,
            ),
        ),
    )


def _inputs() -> ScientificInstitutionsMetricInputs:
    return ScientificInstitutionsMetricInputs(
        assessment=_assessment(),
        lineage=_lineage(),
        context=_context(),
    )


def test_catalog_keeps_v4_32_families_at_their_absolute_indices() -> None:
    assert METRIC_FAMILY_COUNT == 275
    specs = all_metric_specifications()
    assert [spec.family_id.value for spec in specs[268:271]] == [
        "scientific_institution_practice",
        "scientific_institution_roles_and_carriers",
        "scientific_institution_lineage",
    ]
    assert [spec.family_id.value for spec in specs[271:275]] == [
        "science_diffusion_channels",
        "science_diffusion_fidelity",
        "science_diffusion_persistence",
        "science_diffusion_genealogy",
    ]
    legacy = metric_specification("scientific_model_comparison")
    assert legacy.value_keys


def test_practice_family_counts_statuses_and_denominators() -> None:
    document = compute_scientific_institution_practice(
        _inputs(), run_id=RUN, input_revision=REV
    )
    assert document.metric_family == "scientific_institution_practice"
    assert document.values["complete_window_count"] == 2
    assert document.values["complete_empty_window_count"] == 1
    assert document.values["partial_window_count"] == 1
    assert document.values["supported_row_count"] == 1
    assert document.values["stable_row_count"] == 1
    assert document.values["observed_only_row_count"] == 1
    assert document.values["eligible_row_count"] == 3
    assert document.values["unassigned_count"] == 1
    assert document.values["ambiguous_count"] == 1
    assert document.coverage.expected == 3


def test_roles_family_reports_signals_and_carriers() -> None:
    document = compute_scientific_institution_roles_and_carriers(
        _inputs(), run_id=RUN, input_revision=REV
    )
    assert document.values["experimenter_signal_count"] == 1
    assert document.values["record_keeper_signal_count"] == 1
    assert document.values["teacher_signal_count"] == 0
    assert document.values["distinct_linked_actor_count"] == 2
    assert document.values["distinct_carrier_count"] == 1


def test_lineage_family_reports_transitions_and_lengths() -> None:
    document = compute_scientific_institution_lineage(
        _inputs(), run_id=RUN, input_revision=REV
    )
    assert document.values["episode_count"] == 1
    assert document.values["node_count"] == 1
    assert document.values["emerged_count"] == 1
    assert document.values["lapsed_count"] == 1
    assert document.values["max_observed_length_windows"] == 1
    assert document.values["mean_observed_length_milli"] == 1000


def test_absent_input_emits_no_family() -> None:
    with pytest.raises(ValueError, match="scientific_institutions_analysis_invalid"):
        compute_scientific_institution_practice(
            object(), run_id=RUN, input_revision=REV
        )


def test_output_is_deterministic() -> None:
    first = compute_scientific_institution_practice(
        _inputs(), run_id=RUN, input_revision=REV
    )
    second = compute_scientific_institution_practice(
        _inputs(), run_id=RUN, input_revision=REV
    )
    assert first == second


def test_complete_empty_assessment_keeps_explicit_zero_denominator() -> None:
    empty = ScientificPracticeAssessment(
        run_id=RUN,
        policy_version=SCIENTIFIC_INSTITUTIONS_POLICY_VERSION,
        windows=(
            PracticeWindowAssessment(
                window_index=0,
                start_tick=0,
                end_tick_exclusive=32,
                complete=True,
                state=PracticeWindowState.COMPLETE_EMPTY,
                execution_coverage=PracticeCoverageStatus.COMPLETE,
                carrier_coverage=PracticeCoverageStatus.COMPLETE,
                organization_coverage=PracticeCoverageStatus.COMPLETE,
                row_count=0,
                unassigned=0,
                ambiguous=0,
            ),
        ),
        rows=(),
        unassigned=0,
        ambiguous=0,
    )
    document = compute_scientific_institution_practice(
        ScientificInstitutionsMetricInputs(
            assessment=empty, lineage=_lineage(), context=_context()
        ),
        run_id=RUN,
        input_revision=REV,
    )
    assert document.values["complete_empty_window_count"] == 1
    assert document.values["eligible_row_count"] == 0
