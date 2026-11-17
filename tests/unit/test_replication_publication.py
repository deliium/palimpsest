# mypy: ignore-errors
"""V4-28 publication composes both result variants and reports safe outcomes."""

from __future__ import annotations

from pathlib import Path

import pytest

from analysis.replication_analysis import harvest_replication_analysis
from analysis.replication_rows import (
    ReplicationFacts,
    ReplicationMeasurementFact,
    ReplicationReportFact,
)
from experiments.replication_publication import (
    ReplicationHarvestResult,
    build_replication_harvest_result,
    compose_replication_snapshot,
    publish_replication_snapshot,
)
from persistence.replication_filesystem import replication_store_publisher
from simulation.replication_ports import (
    ReplicationPublicationError,
    ReplicationPublicationOptions,
)

pytestmark = pytest.mark.unit

RUN = "run-replication-publication"


def _facts() -> ReplicationFacts:
    from analysis.replication_rows import ReplicationExecutionFact

    return ReplicationFacts(
        executions=(
            ReplicationExecutionFact(
                execution_token="rpe-" + "a" * 32,
                result_root_token="rpt-" + "b" * 32,
                participant_token="rpp-" + "c" * 32,
                execution_tick=2,
                operator="apply_tool",
                process_token="craft",
                operand_a_token="rpen-" + "d" * 32,
                operand_b_token=None,
                outcome="success",
            ),
        ),
        reports=(
            ReplicationReportFact(
                local_report_token="rplr-" + "e" * 32,
                origin_report_token="rpr-" + "f" * 32,
                participant_token="rpp-" + "c" * 32,
                performer_claim_token="rpart-" + "g" * 32,
                design_token="rpd-" + "h" * 32,
                attempt_token="rpa-" + "i" * 32,
                source_trial_token="rpt-" + "j" * 32,
                result_root_token="rpt-" + "k" * 32,
                report_tick=4,
                measurement=ReplicationMeasurementFact(
                    outcome="failure",
                    resolution="outcome_class",
                    uncertainty_kind="unreported",
                    possible_outcomes=(),
                    basis="communicated",
                ),
                declared_measurement_basis="own_observation",
                condition_snapshot=(),
                collaboration_token=None,
                delivery_token="rpdl-" + "l" * 32,
                provenance_kind="communicated",
                claim_digest="m" * 64,
            ),
        ),
    )


def _analysis():
    return harvest_replication_analysis(_facts())


def test_results_are_a_tagged_union_of_executions_and_owner_reports() -> None:
    snapshot = compose_replication_snapshot(
        _analysis(), run_id=RUN, generated_from_tick=8
    )
    kinds = sorted(row["row_kind"] for row in snapshot.results)
    assert kinds == ["execution", "report"]
    layers = {row["row_kind"]: row["layer"] for row in snapshot.results}
    assert layers == {"execution": "objective", "report": "owner_scoped"}
    assert snapshot.summary["execution_count"] == 1
    assert snapshot.summary["report_count"] == 1


def test_composition_does_not_mutate_its_analysis_input() -> None:
    analysis = _analysis()
    before = (analysis.designs, analysis.executions, analysis.reports)
    compose_replication_snapshot(analysis, run_id=RUN, generated_from_tick=1)
    assert (analysis.designs, analysis.executions, analysis.reports) == before


def test_enabled_publisher_reports_published_with_independent_science_status(
    tmp_path: Path,
) -> None:
    snapshot = compose_replication_snapshot(
        _analysis(), run_id=RUN, generated_from_tick=2
    )
    publisher = replication_store_publisher(
        tmp_path, options=ReplicationPublicationOptions(enabled=True)
    )
    result = publish_replication_snapshot(snapshot, publisher=publisher)
    assert isinstance(result, ReplicationHarvestResult)
    assert result.status == "published"
    assert result.stored is True
    assert result.scientific_status == "complete"
    assert result.publication_id == snapshot.publication_id


def test_disabled_publisher_is_disabled_not_missing(tmp_path: Path) -> None:
    snapshot = compose_replication_snapshot(
        _analysis(), run_id=RUN, generated_from_tick=2
    )
    publisher = replication_store_publisher(
        tmp_path, options=ReplicationPublicationOptions(enabled=False)
    )
    result = build_replication_harvest_result(
        snapshot=snapshot, publisher=publisher
    )
    assert result.status == "disabled"
    assert result.stored is False


def test_quota_and_corruption_are_distinct_safe_outcomes(tmp_path: Path) -> None:
    first = compose_replication_snapshot(
        _analysis(), run_id=RUN, generated_from_tick=1
    )
    second = compose_replication_snapshot(
        _analysis(), run_id=RUN, generated_from_tick=2
    )
    publisher = replication_store_publisher(
        tmp_path,
        options=ReplicationPublicationOptions(enabled=True, max_publications=1),
    )
    assert publish_replication_snapshot(first, publisher=publisher).status == (
        "published"
    )
    assert publish_replication_snapshot(second, publisher=publisher).status == (
        "quota_exceeded"
    )

    path = tmp_path / RUN / f"{first.publication_id}.json"
    path.write_bytes(path.read_bytes() + b" ")
    corrupt = publish_replication_snapshot(first, publisher=publisher)
    assert corrupt.status == "corrupt"
    assert corrupt.stored is False


def test_absent_snapshot_is_missing_not_an_empty_publication() -> None:
    result = publish_replication_snapshot(None, publisher=object())
    assert result.status == "missing"
    assert result.stored is False


def test_publication_errors_never_escape_as_payloads() -> None:
    class _Broken:
        def publish(self, snapshot):
            raise ReplicationPublicationError("replication_store_corrupt")

    snapshot = compose_replication_snapshot(
        _analysis(), run_id=RUN, generated_from_tick=1
    )
    result = publish_replication_snapshot(snapshot, publisher=_Broken())
    assert result.status == "corrupt"
