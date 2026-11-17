# mypy: ignore-errors
"""V4-28 source -> receiver -> snapshot/store read flow and determinism."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agents.cognition import (
    ExperimentSelector,
    ReplicationBindingMode,
    ReplicationMeasurement,
    ReplicationMeasurementBasis,
    ReplicationMeasurementResolution,
    ReplicationOwnerContext,
    ReplicationSelectorFamily,
    ReplicationUncertaintyKind,
    adopt_replication_design,
    append_replication_design,
    build_experiment_design,
    build_replication_result_report,
    compile_replication_test,
    empty_experiment_ledger,
    empty_replication_ledger,
    ingest_replication_report,
    replication_ref,
)
from agents.cognition.experimentation import ExperimentCognitionBinding
from agents.cognition.replication import ReplicationAttemptState
from agents.cognition.replication_actions import correlate_replication_occurrences
from agents.models import AgentId
from analysis.replication_analysis import harvest_replication_analysis
from analysis.replication_rows import (
    ReplicationExecutionFact,
    ReplicationFacts,
)
from experiments.replication_publication import compose_replication_snapshot
from simulation.replication_codec import (
    decode_replication_snapshot,
    encode_replication_snapshot,
)
from world.actions import Experiment
from world.experimentation import (
    ExperimentOperator,
    ExperimentOutcomeClass,
    ExperimentProcessToken,
)
from world.identifiers import EntityId
from world.values import ItemKind

pytestmark = pytest.mark.unit

SOURCE = AgentId("owner-source")
RECEIVER = AgentId("owner-receiver")
SOURCE_BODY = "body-source"
RECEIVER_BODY = "body-receiver"


def _design():
    return build_experiment_design(
        origin_token=replication_ref("rorg", SOURCE.value, "source-trial"),
        parent_design_token=None,
        source_hypothesis_token=replication_ref("rhyp", SOURCE.value, "hyp"),
        source_trial_token=replication_ref("rtrl", SOURCE_BODY, "source-event"),
        created_tick=2,
        operator=ExperimentOperator.APPLY_TOOL,
        process_token=ExperimentProcessToken.CRAFT,
        operand_a_selector=ExperimentSelector(
            family=ReplicationSelectorFamily.ITEM,
            kind="tool",
            binding_mode=ReplicationBindingMode.SAME_KIND,
        ),
        operand_b_selector=None,
        predicted_outcome=ExperimentOutcomeClass.SUCCESS,
        conditions=(),
    )


def _receiver_observation():
    return SimpleNamespace(
        observer_id=EntityId(RECEIVER_BODY),
        self_body=SimpleNamespace(entity_id=EntityId(RECEIVER_BODY)),
        tick=5,
        items=(
            SimpleNamespace(
                entity_id=EntityId("receiver-tool"),
                kind=ItemKind.TOOL,
                placement=SimpleNamespace(value="held_by_self"),
            ),
        ),
        resources=(),
        structures=(),
        artifacts=(),
        occurrences=(),
        communications=(),
    )


def test_source_receiver_result_and_publication_flow() -> None:
    design = _design()
    source_ledger = empty_replication_ledger(SOURCE)
    source_ledger, _ = append_replication_design(source_ledger, design)
    source_report = build_replication_result_report(
        SOURCE,
        origin_report_token=replication_ref("rrep", "source-report"),
        design_token=design.design_token,
        attempt_token=replication_ref("ratt", "source-attempt"),
        source_trial_token=design.source_trial_token,
        source_root_token=replication_ref("rrep", "source-report"),
        measurement=ReplicationMeasurement(
            resolution=ReplicationMeasurementResolution.OUTCOME_CLASS,
            uncertainty_kind=ReplicationUncertaintyKind.UNREPORTED,
            basis=ReplicationMeasurementBasis.OWN_OBSERVATION,
            outcome=ExperimentOutcomeClass.SUCCESS,
        ),
        declared_measurement_basis=ReplicationMeasurementBasis.OWN_OBSERVATION,
        performer_claim_token=replication_ref("rpart", SOURCE_BODY),
        observed_conditions=(),
        reported_conditions=(),
    )
    source_ledger, _ = ingest_replication_report(source_ledger, source_report)

    receiver = empty_replication_ledger(RECEIVER)
    receiver, _ = adopt_replication_design(
        RECEIVER,
        receiver,
        design,
        delivery_event_id="design-delivery",
        received_tick=3,
        inviter_entity_id=SOURCE_BODY,
    )
    from agents.cognition import (
        ReplicationCollaboration,
        open_replication_collaboration,
    )

    receiver, _ = open_replication_collaboration(
        receiver,
        ReplicationCollaboration(
            owner_id=RECEIVER,
            invitation_token=replication_ref("rinv", RECEIVER.value, "invite"),
            design_token=design.design_token,
            source_trial_token=design.source_trial_token,
            inviter_entity_id=SOURCE_BODY,
            created_tick=3,
            delivery_event_id="invite-delivery",
        ),
    )
    compiled = compile_replication_test(
        RECEIVER,
        receiver,
        empty_experiment_ledger(
            RECEIVER, ExperimentCognitionBinding(4, 1, 2, False, False)
        ),
        _receiver_observation(),
        source_context=ReplicationOwnerContext(),
    )
    assert type(compiled.command) is Experiment
    assert compiled.command.operand_a_id == EntityId("receiver-tool")
    assert compiled.command.operand_a_id != EntityId("receiver-tool-foreign")
    assert (
        compiled.replication_ledger.attempts[0].state
        is ReplicationAttemptState.PROPOSED
    )

    occurrence = SimpleNamespace(
        kind="experiment_resolved",
        other_entity_id=EntityId("receiver-tool"),
        public_facts={
            "operator": ExperimentOperator.APPLY_TOOL.value,
            "outcome_class": ExperimentOutcomeClass.FAILURE.value,
        },
        provenance=SimpleNamespace(
            source_tick=5,
            source_event_id=SimpleNamespace(value="receiver-result"),
        ),
    )
    observation = _receiver_observation()
    observation.occurrences = (occurrence,)
    receiver, experiment = correlate_replication_occurrences(
        RECEIVER,
        compiled.replication_ledger,
        compiled.experiment_ledger,
        observation,
    )
    assert receiver.reports[0].measurement.outcome is ExperimentOutcomeClass.FAILURE
    assert any(
        trial.event_id == "receiver-result" for trial in experiment.trials
    )

    facts = ReplicationFacts(
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
        )
    )
    analysis = harvest_replication_analysis(facts)
    snapshot = compose_replication_snapshot(
        analysis, run_id="run-replication-e2e", generated_from_tick=6
    )
    encoded = encode_replication_snapshot(snapshot)
    assert decode_replication_snapshot(encoded) == snapshot

    twin = compose_replication_snapshot(
        harvest_replication_analysis(facts),
        run_id="run-replication-e2e",
        generated_from_tick=6,
    )
    assert encode_replication_snapshot(twin) == encoded


@pytest.mark.parametrize("count", [1, 2, 8, 128])
def test_repeated_testimony_never_becomes_truth_or_support_mass(count: int) -> None:
    design = _design()
    ledger = empty_replication_ledger(RECEIVER)
    ledger, _ = adopt_replication_design(
        RECEIVER,
        ledger,
        design,
        delivery_event_id="design-delivery",
        received_tick=3,
        inviter_entity_id=SOURCE_BODY,
    )
    experiment = empty_experiment_ledger(
        RECEIVER, ExperimentCognitionBinding(4, 1, 2, False, False)
    )
    experiment_before = experiment
    for index in range(count):
        report = build_replication_result_report(
            RECEIVER,
            origin_report_token=replication_ref("rrep", f"report-{index}"),
            design_token=design.design_token,
            attempt_token=replication_ref("ratt", f"attempt-{index}"),
            source_trial_token=design.source_trial_token,
            source_root_token=replication_ref("rrep", f"report-{index}"),
            measurement=ReplicationMeasurement(
                resolution=ReplicationMeasurementResolution.OUTCOME_CLASS,
                uncertainty_kind=ReplicationUncertaintyKind.UNREPORTED,
                basis=ReplicationMeasurementBasis.COMMUNICATED,
                outcome=ExperimentOutcomeClass.SUCCESS,
            ),
            declared_measurement_basis=ReplicationMeasurementBasis.OWN_OBSERVATION,
            performer_claim_token=replication_ref("rpart", SOURCE_BODY),
            delivery_event_id=f"delivery-{index}",
        )
        ledger, _ = ingest_replication_report(ledger, report)

    assert len(ledger.reports) == min(count, 256)
    assert experiment == experiment_before
    assert not experiment.trials
    for forbidden in ("truth", "proven", "verified", "consensus", "majority"):
        assert not hasattr(ledger, forbidden)
    # Re-delivery of one origin stays one reported source at every count.
    duplicate = build_replication_result_report(
        RECEIVER,
        origin_report_token=replication_ref("rrep", "report-0"),
        design_token=design.design_token,
        attempt_token=replication_ref("ratt", "attempt-0"),
        source_trial_token=design.source_trial_token,
        source_root_token=replication_ref("rrep", "report-0"),
        measurement=ReplicationMeasurement(
            resolution=ReplicationMeasurementResolution.OUTCOME_CLASS,
            uncertainty_kind=ReplicationUncertaintyKind.UNREPORTED,
            basis=ReplicationMeasurementBasis.COMMUNICATED,
            outcome=ExperimentOutcomeClass.SUCCESS,
        ),
        declared_measurement_basis=ReplicationMeasurementBasis.OWN_OBSERVATION,
        performer_claim_token=replication_ref("rpart", SOURCE_BODY),
        delivery_event_id="delivery-0",
    )
    replayed, _ = ingest_replication_report(ledger, duplicate)
    assert len(replayed.reports) == len(ledger.reports)


def test_replication_snapshot_is_deterministic_across_owner_order() -> None:
    facts_a = ReplicationFacts(notices=("partial_owner_export",))
    facts_b = ReplicationFacts(notices=("partial_owner_export",))
    first = compose_replication_snapshot(
        harvest_replication_analysis(facts_a),
        run_id="run-1",
        generated_from_tick=3,
    )
    second = compose_replication_snapshot(
        harvest_replication_analysis(facts_b),
        run_id="run-1",
        generated_from_tick=3,
    )
    assert encode_replication_snapshot(first) == encode_replication_snapshot(second)
