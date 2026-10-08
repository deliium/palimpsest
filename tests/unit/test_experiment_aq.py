"""Off-gate Experiment AQ catalog for bounded experimentation."""

from __future__ import annotations

import logging
from dataclasses import fields
from pathlib import Path
from types import SimpleNamespace

import pytest

from agents.cognition.experimentation import (
    ExperimentCognitionBinding,
    ExperimentHypothesis,
    ExperimentTrial,
    admit_hypothesis,
    commit_experiment_learning,
    empty_experiment_ledger,
    experiment_hypothesis_id,
    parse_experiment_draft,
    record_trial,
    score_remembered_experiment,
)
from agents.cognition.memory import build_direct_observation_memory_trace
from agents.cognition.practical_knowledge import (
    apply_practical_knowledge_from_independent_discovery,
    empty_practical_knowledge_ledger,
)
from agents.models import AgentId
from experiments import (
    OFF_GATE_MATRIX_EXPERIMENT_IDS,
    bounded_experimentation_profile,
    experiment_aq_bounded_experimentation,
)
from experiments.catalog import base_runner_config_from_scenario
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V35,
    RUNNER_SCHEMA_VERSION_V36,
    AgentCognitionSpec,
    AgentRunnerSpec,
    WorldScenarioSpec,
    example_cultural_feature_provenance_spec,
    example_knowledge_genealogy_spec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from tests.unit.test_experiment_resolution import _apply, _details, _state
from tests.unit.test_v1_regression_gate import _CATALOG_BUILDERS
from world._experiment_laws import catalog_from_rows
from world.actions import Experiment
from world.experimentation import ExperimentOperator, ExperimentProcessToken
from world.identifiers import EntityId, EventId, WorldId, WorldRevision
from world.models import default_physical_rules, non_lethal_physical_rules
from world.observations import (
    ObservationAudienceRole,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedOccurrence,
)
from world.production import example_production_catalog

_LOG = logging.getLogger("tests.experiment_aq")
_ROOT = Path(__file__).resolve().parents[2]
_ARM_IDS = (
    "aq-channel-off",
    "aq-failure-unlisted",
    "aq-success-not-knowledge",
    "aq-repeat-then-learn",
    "aq-harm",
    "aq-unexpected-accidental",
    "aq-llm-cannot-invent",
    "aq-teach-record",
    "aq-flags-off",
)
pytestmark = pytest.mark.unit


def _base():
    body_a = alive_body("body-a")
    body_b = alive_body("body-b")
    return base_runner_config_from_scenario(
        seed=361,
        stochastic_identity="cmp-aq-bounded-experimentation",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-aq-experiment"),
            revision=WorldRevision(0),
            physical_rules=non_lethal_physical_rules(),
            locations=(make_location(body_capacity=8),),
            bodies=(body_a, body_b),
            weather=(make_weather(),),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=AgentId("agent-a"),
                entity_id=body_a.entity_id,
                cognition=AgentCognitionSpec(agent_id=AgentId("agent-a")),
            ),
            AgentRunnerSpec(
                agent_id=AgentId("agent-b"),
                entity_id=body_b.entity_id,
                cognition=AgentCognitionSpec(agent_id=AgentId("agent-b")),
            ),
        ),
        max_ticks=4,
    )


def _arm(arm_id: str):
    definition = experiment_aq_bounded_experimentation(_base(), max_ticks=2)
    return next(
        item for item in definition.conditions if item.condition_id == arm_id
    ).runner_config


def _catalog(config):
    return catalog_from_rows(
        config.bounded_experimentation.laws, example_production_catalog()
    )


def test_aq_catalog_is_off_the_v1_gate(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="experiments.catalog")
    definition = experiment_aq_bounded_experimentation(_base(), max_ticks=2)
    assert definition.experiment_id == "experiment-aq-bounded-experimentation"
    assert definition.experiment_id in OFF_GATE_MATRIX_EXPERIMENT_IDS
    assert tuple(item.condition_id for item in definition.conditions) == _ARM_IDS
    assert "experiment_arm_start arm_id=aq-channel-off" in caplog.text
    gate = (_ROOT / "tests" / "unit" / "test_v1_regression_gate.py").read_text(
        encoding="utf-8"
    )
    assert "experiment-aq-bounded-experimentation" not in gate
    assert "experiment_aq_bounded_experimentation" not in gate
    assert definition.experiment_id not in {item[0] for item in _CATALOG_BUILDERS}
    bounded_experimentation_profile(_arm("aq-failure-unlisted"))


def test_aq_channel_off_matches_v35_genealogy_fixture() -> None:
    arm = _arm("aq-channel-off")
    assert arm.schema_version == RUNNER_SCHEMA_VERSION_V35
    assert arm.bounded_experimentation is None
    assert arm.knowledge_genealogy is not None
    assert arm.cultural_feature_provenance == example_cultural_feature_provenance_spec()
    assert arm.knowledge_genealogy == example_knowledge_genealogy_spec()


def test_aq_failure_unlisted_adds_no_item() -> None:
    applied = _apply(_state(), catalog=_catalog(_arm("aq-failure-unlisted")))
    details = _details(applied)
    assert details.outcome_class == "failure"
    assert details.delta == "none"
    assert len(applied.next_state.items) == 1


def test_aq_success_is_not_knowledge() -> None:
    config = _arm("aq-success-not-knowledge")
    assert config.knowledge_genealogy is None
    assert config.bounded_experimentation.learn_into_genealogy is False
    applied = _apply(_state(), catalog=_catalog(config))
    details = _details(applied)
    assert details.outcome_class == "success"
    occurrence = ObservedOccurrence(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.OCCURRENCE,
            source_tick=1,
            source_event_id=EventId("evt-success"),
        ),
        kind="experiment_resolved",
        audience_role=ObservationAudienceRole.ACTOR,
        actor_id=EntityId("body-1"),
        other_entity_id=EntityId("item-1"),
        public_facts={
            "kind": "experiment_resolved",
            "outcome_class": "success",
            "delta": details.delta,
            "operator": "combine",
            "discovery_mode": "deliberate",
        },
    )
    trace = build_direct_observation_memory_trace(
        owner_id=AgentId("agent-a"),
        observation_tick=1,
        observation_revision=WorldRevision(1),
        occurrence=occurrence,
        location_id=EntityId("loc-1"),
    )
    assert trace.provenance.observed_source_id == EventId("evt-success")
    assert empty_practical_knowledge_ledger(AgentId("agent-a")).entries == ()


def test_aq_repeat_then_learn_uses_the_gate() -> None:
    config = _arm("aq-repeat-then-learn")
    assert config.schema_version == RUNNER_SCHEMA_VERSION_V36
    assert config.bounded_experimentation.learn_into_genealogy is True
    assert config.knowledge_genealogy is not None
    owner = AgentId("agent-a")
    binding = ExperimentCognitionBinding(
        max_hypotheses=4,
        max_trials_per_tick=1,
        repeat_threshold=config.bounded_experimentation.repeat_threshold,
        learn_into_genealogy=True,
        allow_provider=False,
    )
    ledger = empty_experiment_ledger(owner, binding)
    hypothesis_id = experiment_hypothesis_id(
        owner,
        ExperimentOperator.COMBINE,
        "item-a",
        "item-b",
        ExperimentProcessToken.NONE,
    )
    ledger = admit_hypothesis(
        ledger,
        ExperimentHypothesis(
            owner_id=owner,
            hypothesis_id=hypothesis_id,
            operator=ExperimentOperator.COMBINE,
            operand_a_id="item-a",
            operand_b_id="item-b",
            process_token=ExperimentProcessToken.NONE,
            predicted_outcome="success",
        ),
    )
    ledger = record_trial(
        ledger,
        ExperimentTrial(
            tick=0,
            event_id="evt-0",
            outcome_class="success",
            discovery_mode="deliberate",
            hypothesis_id=hypothesis_id,
        ),
    )
    _kept, below = commit_experiment_learning(
        ledger,
        empty_practical_knowledge_ledger(owner),
        genealogy_active=True,
        enabled_kinds=("crafting_process",),
        tick=1,
    )
    assert below.entries == ()
    ledger = record_trial(
        ledger,
        ExperimentTrial(
            tick=1,
            event_id="evt-1",
            outcome_class="success",
            discovery_mode="deliberate",
            hypothesis_id=hypothesis_id,
        ),
    )
    _kept, learned = commit_experiment_learning(
        ledger,
        empty_practical_knowledge_ledger(owner),
        genealogy_active=True,
        enabled_kinds=("crafting_process",),
        tick=2,
    )
    assert len(learned.entries) == 1
    assert "evt:evt-1" in learned.entries[0].evidence_refs
    skipped, _audits = apply_practical_knowledge_from_independent_discovery(
        empty_practical_knowledge_ledger(owner),
        enabled_kinds=("crafting_process",),
        observation=SimpleNamespace(
            occurrences=(
                SimpleNamespace(
                    kind="experiment_resolved",
                    other_entity_id=None,
                    success=True,
                ),
            )
        ),
        tick=1,
        independent_compose_on=True,
    )
    assert skipped.entries == ()


def test_aq_harm_uses_the_predeclared_band() -> None:
    rules = default_physical_rules()
    applied = _apply(_state(), catalog=_catalog(_arm("aq-harm")))
    assert _details(applied).outcome_class == "harm"
    assert applied.next_state.bodies[EntityId("body-1")].health.value == pytest.approx(
        50.0 - rules.hunger_damage
    )
    assert empty_practical_knowledge_ledger(AgentId("agent-a")).entries == ()


def test_aq_unexpected_without_matching_prediction_is_accidental() -> None:
    applied = _apply(
        _state(),
        catalog=_catalog(_arm("aq-unexpected-accidental")),
        hypothesis_id="h1",
    )
    assert _details(applied).outcome_class == "unexpected"
    assert _details(applied).discovery_mode == "deliberate"
    owner = AgentId("agent-a")
    binding = ExperimentCognitionBinding(
        max_hypotheses=4,
        max_trials_per_tick=2,
        repeat_threshold=2,
        learn_into_genealogy=False,
        allow_provider=False,
    )
    ledger = admit_hypothesis(
        empty_experiment_ledger(owner, binding),
        ExperimentHypothesis(
            owner_id=owner,
            hypothesis_id="h1",
            operator=ExperimentOperator.COMBINE,
            operand_a_id="item-1",
            operand_b_id="res-1",
            process_token=ExperimentProcessToken.NONE,
            predicted_outcome="success",
        ),
    )
    occurrence = ObservedOccurrence(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.OCCURRENCE,
            source_tick=1,
            source_event_id=EventId("evt-odd"),
        ),
        kind="experiment_resolved",
        audience_role=ObservationAudienceRole.ACTOR,
        actor_id=EntityId("body-1"),
        other_entity_id=EntityId("item-1"),
        public_facts={
            "kind": "experiment_resolved",
            "outcome_class": "unexpected",
            "delta": "none",
            "operator": "combine",
            "discovery_mode": "deliberate",
        },
    )
    updated = score_remembered_experiment(ledger, occurrence, tick=1)
    assert updated.trials[0].discovery_mode == "accidental"
    _kept, knowledge = commit_experiment_learning(
        updated,
        empty_practical_knowledge_ledger(owner),
        genealogy_active=False,
        enabled_kinds=("crafting_process",),
        tick=1,
    )
    assert knowledge.entries == ()


def test_aq_llm_cannot_invent_physics() -> None:
    config = _arm("aq-llm-cannot-invent")
    assert config.bounded_experimentation.allow_provider is True
    draft, reason = parse_experiment_draft(
        {
            "operator": "combine",
            "operand_a_id": "item-1",
            "operand_b_id": "res-1",
            "process_token": "none",
            "predicted_outcome": "success",
            "product_id": "invented",
        }
    )
    assert draft is None
    assert reason == "experiment_draft_physics"
    assert "delta" not in {item.name for item in fields(Experiment)}
    applied = _apply(_state(), catalog=_catalog(config))
    assert _details(applied).outcome_class == "success"
    assert not hasattr(_details(applied), "predicted_outcome")


def test_aq_teach_record_cites_without_resolver_commands() -> None:
    config = _arm("aq-teach-record")
    assert config.durable_records is not None
    assert (
        config.agents[0].cognition.teaching_interaction_mode.value == "deterministic"
    )
    source = (_ROOT / "src" / "world" / "_experiment_apply.py").read_text(
        encoding="utf-8"
    )
    assert "Tell(" not in source
    assert "Inscribe(" not in source


def test_aq_flags_off_keeps_v4() -> None:
    arm = _arm("aq-flags-off")
    assert arm.schema_version == RUNNER_SCHEMA_VERSION_V4
    assert arm.v3_capability_flags.enabled_names() == ()
    assert arm.bounded_experimentation is None


def test_profile_rejects_missing_channel() -> None:
    arm = _arm("aq-channel-off")
    with pytest.raises(ValueError, match="bounded_experimentation_profile_schema"):
        bounded_experimentation_profile(arm)
