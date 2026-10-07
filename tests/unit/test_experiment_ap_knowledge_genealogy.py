"""Off-gate Experiment AP catalog for knowledge genealogy on v35."""

from __future__ import annotations

import logging

import pytest

from agents.models import AgentId
from experiments import (
    OFF_GATE_MATRIX_EXPERIMENT_IDS,
    experiment_ap_knowledge_genealogy,
    knowledge_genealogy_profile,
)
from experiments.catalog import base_runner_config_from_scenario
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V34,
    RUNNER_SCHEMA_VERSION_V35,
    AgentCognitionSpec,
    AgentRunnerSpec,
    WorldScenarioSpec,
    example_cultural_feature_provenance_spec,
    example_knowledge_genealogy_spec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import non_lethal_physical_rules

_LOG = logging.getLogger("tests.experiment_ap_knowledge_genealogy")

_AP_ARM_IDS = (
    "ap-channel-off",
    "ap-independent-discovery",
    "ap-teaching-lineage",
    "ap-multi-parent-dag",
    "ap-mutation-hop",
    "ap-dual-emergence",
    "ap-written-record",
    "ap-reconstruction",
    "ap-lifecycle-survival",
    "ap-capability-join",
    "ap-flags-off",
)

pytestmark = pytest.mark.unit


def _base():
    body_a = alive_body("body-a")
    body_b = alive_body("body-b")
    return base_runner_config_from_scenario(
        seed=231,
        stochastic_identity="cmp-ap-knowledge-genealogy",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-ap-genealogy"),
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
        max_ticks=10,
    )


def _arm(definition, arm_id: str):
    return next(
        item for item in definition.conditions if item.condition_id == arm_id
    ).runner_config


def test_ap_catalog_arms_and_profile(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="experiments.catalog")
    definition = experiment_ap_knowledge_genealogy(_base())
    assert definition.experiment_id == "experiment-ap-knowledge-genealogy"
    assert "experiment-ap-knowledge-genealogy" in OFF_GATE_MATRIX_EXPERIMENT_IDS
    assert tuple(c.condition_id for c in definition.conditions) == _AP_ARM_IDS
    assert "experiment_ap_built" in caplog.text

    on_arm = _arm(definition, "ap-independent-discovery")
    assert on_arm.schema_version == RUNNER_SCHEMA_VERSION_V35
    assert on_arm.knowledge_genealogy is not None
    assert on_arm.cultural_feature_provenance is not None
    assert on_arm.v3_capability_flags.cultural_historical_memory is True
    knowledge_genealogy_profile(on_arm)

    channel_off = _arm(definition, "ap-channel-off")
    assert channel_off.schema_version == RUNNER_SCHEMA_VERSION_V34
    assert channel_off.knowledge_genealogy is None
    assert channel_off.knowledge_repositories is not None

    flags_off = _arm(definition, "ap-flags-off")
    assert flags_off.schema_version == RUNNER_SCHEMA_VERSION_V4
    assert flags_off.knowledge_genealogy is None
    assert flags_off.v3_capability_flags.enabled_names() == ()

    teaching = _arm(definition, "ap-teaching-lineage")
    assert teaching.knowledge_genealogy.uptake_compose.teaching is True
    written = _arm(definition, "ap-written-record")
    assert written.durable_records is not None
    assert written.knowledge_genealogy.uptake_compose.written_record is True
    lifecycle = _arm(definition, "ap-lifecycle-survival")
    assert lifecycle.population_lifecycle is not None
    assert lifecycle.v3_capability_flags.generational_population is True


def test_profile_rejects_wrong_schema() -> None:
    from types import SimpleNamespace

    from simulation.runner_models import V3CapabilityFlags

    bad = SimpleNamespace(
        schema_version=RUNNER_SCHEMA_VERSION_V34,
        v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
        cultural_feature_provenance=example_cultural_feature_provenance_spec(),
        knowledge_genealogy=example_knowledge_genealogy_spec(),
        durable_records=None,
        knowledge_repositories=None,
    )
    with pytest.raises(ValueError, match="knowledge_genealogy_profile_schema"):
        knowledge_genealogy_profile(bad)  # type: ignore[arg-type]


def test_profile_rejects_missing_genealogy() -> None:
    from types import SimpleNamespace

    from simulation.runner_models import V3CapabilityFlags

    bad = SimpleNamespace(
        schema_version=RUNNER_SCHEMA_VERSION_V35,
        v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
        cultural_feature_provenance=example_cultural_feature_provenance_spec(),
        knowledge_genealogy=None,
        durable_records=None,
        knowledge_repositories=None,
    )
    with pytest.raises(
        ValueError, match="knowledge_genealogy_profile_missing_genealogy"
    ):
        knowledge_genealogy_profile(bad)  # type: ignore[arg-type]


def test_arm_independent_discovery_holders_and_hop_zero() -> None:
    from agents.cognition.practical_knowledge import (
        KnowledgeTransmissionOrigin,
        PracticalKnowledgeKind,
        empty_practical_knowledge_ledger,
        entry_to_audit,
        form_or_reinforce_practical_knowledge,
        practical_knowledge_content_key,
    )
    from analysis.knowledge_genealogy_metrics import compute_knowledge_genealogy_holders
    from analysis.models import MetricAvailability

    arm_id = "ap-independent-discovery"
    config = _arm(experiment_ap_knowledge_genealogy(_base()), arm_id)
    assert config.knowledge_genealogy is not None, arm_id
    assert (
        config.knowledge_genealogy.uptake_compose.independent_discovery is True
    ), arm_id
    owner = AgentId("agent-a")
    ledger = form_or_reinforce_practical_knowledge(
        empty_practical_knowledge_ledger(owner),
        kind=PracticalKnowledgeKind.FORAGING_METHOD,
        content_key=practical_knowledge_content_key("forage-exp"),
        content_fingerprint=("cue-a",),
        origin=KnowledgeTransmissionOrigin.INDEPENDENT_DISCOVERY,
        tick=1,
        enabled_kinds=("foraging_method",),
    )
    entry = ledger.entries[0]
    assert entry.hop_index == 0, arm_id
    audit = entry_to_audit(entry, tick=1, reason_code="formed")
    doc = compute_knowledge_genealogy_holders(
        (audit,), run_id="run-ap", input_revision="rev-1", as_of_tick=2
    )
    assert doc.availability is MetricAvailability.PRESENT, arm_id
    assert int(doc.values["active_entry_count"]) > 0, arm_id


def test_arm_teaching_lineage_who_taught() -> None:
    from agents.cognition.practical_knowledge import (
        KnowledgeTransmissionOrigin,
        PracticalKnowledgeKind,
        empty_practical_knowledge_ledger,
        entry_to_audit,
        form_or_reinforce_practical_knowledge,
        practical_knowledge_content_key,
    )
    from analysis.knowledge_genealogy import (
        build_knowledge_genealogy_graph,
        query_who_taught,
    )

    arm_id = "ap-teaching-lineage"
    config = _arm(experiment_ap_knowledge_genealogy(_base()), arm_id)
    assert config.knowledge_genealogy.uptake_compose.teaching is True, arm_id
    key = practical_knowledge_content_key("foraging")
    teacher = AgentId("agent-a")
    learner = AgentId("agent-b")
    teacher_ledger = form_or_reinforce_practical_knowledge(
        empty_practical_knowledge_ledger(teacher),
        kind=PracticalKnowledgeKind.FORAGING_METHOD,
        content_key=key,
        content_fingerprint=("cue-a",),
        origin=KnowledgeTransmissionOrigin.INDEPENDENT_DISCOVERY,
        tick=1,
        enabled_kinds=("foraging_method",),
    )
    learner_ledger = form_or_reinforce_practical_knowledge(
        empty_practical_knowledge_ledger(learner),
        kind=PracticalKnowledgeKind.FORAGING_METHOD,
        content_key=key,
        content_fingerprint=("cue-a",),
        origin=KnowledgeTransmissionOrigin.TEACHING,
        tick=2,
        enabled_kinds=("foraging_method",),
        source_agent_id=teacher,
        teacher_agent_id=teacher,
        evidence_refs=("teach:occ-1",),
    )
    audits = (
        entry_to_audit(teacher_ledger.entries[0], tick=1, reason_code="formed"),
        entry_to_audit(learner_ledger.entries[0], tick=2, reason_code="formed"),
    )
    graph = build_knowledge_genealogy_graph(audits, as_of_tick=3)
    taught = query_who_taught(graph, content_key=key, holder_agent_id="agent-b")
    assert taught.count > 0, arm_id
    assert "agent-a" in [agent for _, agent in taught.items], arm_id


def test_arm_multi_parent_dag_direct_ledger() -> None:
    from agents.cognition.practical_knowledge import (
        KnowledgeTransmissionOrigin,
        PracticalKnowledgeKind,
        combine_practical_knowledge,
        empty_practical_knowledge_ledger,
        entry_to_audit,
        form_or_reinforce_practical_knowledge,
        practical_knowledge_content_key,
    )
    from analysis.knowledge_genealogy_metrics import compute_knowledge_genealogy_lineage

    arm_id = "ap-multi-parent-dag"
    owner = AgentId("agent-a")
    ledger = empty_practical_knowledge_ledger(owner)
    ledger = form_or_reinforce_practical_knowledge(
        ledger,
        kind=PracticalKnowledgeKind.FORAGING_METHOD,
        content_key=practical_knowledge_content_key("a"),
        content_fingerprint=("cue-a", "cue-shared"),
        origin=KnowledgeTransmissionOrigin.INDEPENDENT_DISCOVERY,
        tick=1,
        enabled_kinds=("foraging_method",),
    )
    ledger = form_or_reinforce_practical_knowledge(
        ledger,
        kind=PracticalKnowledgeKind.FORAGING_METHOD,
        content_key=practical_knowledge_content_key("b"),
        content_fingerprint=("cue-b", "cue-shared"),
        origin=KnowledgeTransmissionOrigin.INDEPENDENT_DISCOVERY,
        tick=1,
        enabled_kinds=("foraging_method",),
    )
    p1, p2 = ledger.entries[0].entry_id, ledger.entries[1].entry_id
    ledger = combine_practical_knowledge(
        ledger,
        parent_entry_ids=(p1, p2),
        tick=2,
        allow_combination=True,
        allow_multi_parent=True,
        min_token_overlap=0.0,
        enabled_kinds=("foraging_method",),
    )
    audits = tuple(
        entry_to_audit(row, tick=2, reason_code="combined")
        for row in ledger.entries
    )
    doc = compute_knowledge_genealogy_lineage(
        audits, run_id="run-ap", input_revision="rev-1", as_of_tick=2
    )
    assert float(doc.values["multi_parent_share"]) > 0.0, arm_id


def test_arm_mutation_hop_direct_ledger() -> None:
    from agents.cognition.practical_knowledge import (
        KnowledgeTransmissionOrigin,
        PracticalKnowledgeKind,
        empty_practical_knowledge_ledger,
        entry_to_audit,
        form_or_reinforce_practical_knowledge,
        mutate_practical_knowledge,
        practical_knowledge_content_key,
    )
    from analysis.knowledge_genealogy_metrics import (
        compute_knowledge_genealogy_mutation,
    )

    arm_id = "ap-mutation-hop"
    owner = AgentId("agent-a")
    ledger = form_or_reinforce_practical_knowledge(
        empty_practical_knowledge_ledger(owner),
        kind=PracticalKnowledgeKind.FORAGING_METHOD,
        content_key=practical_knowledge_content_key("berry"),
        content_fingerprint=("cue-a", "cue-b", "cue-c"),
        origin=KnowledgeTransmissionOrigin.INDEPENDENT_DISCOVERY,
        tick=1,
        enabled_kinds=("foraging_method",),
    )
    prior = ledger.entries[0].entry_id
    ledger = mutate_practical_knowledge(
        ledger,
        entry_id=prior,
        tick=2,
        allow_mutation=True,
        mutation_requires_evidence=False,
        owner_evidence_present=False,
        max_token_edits=2,
        mutation_distance_threshold=0.01,
        rng_namespace="knowledge_genealogy",
        seed_material="seed-ap",
    )
    child = next(row for row in ledger.entries if prior in row.parent_entry_ids)
    assert child.hop_index == 1, arm_id
    assert child.mutated is True, arm_id
    audits = tuple(
        entry_to_audit(
            row,
            tick=2,
            reason_code="mutated" if row.mutated else "formed",
            fingerprint_distance_q=0.2 if row.mutated else 0.0,
        )
        for row in ledger.entries
    )
    doc = compute_knowledge_genealogy_mutation(
        audits, run_id="run-ap", input_revision="rev-1"
    )
    assert int(doc.values["mutated_count"]) > 0, arm_id


def test_arm_dual_emergence_count() -> None:
    from agents.cognition.practical_knowledge import (
        KnowledgeTransmissionOrigin,
        PracticalKnowledgeKind,
        empty_practical_knowledge_ledger,
        entry_to_audit,
        form_or_reinforce_practical_knowledge,
        practical_knowledge_content_key,
    )
    from analysis.knowledge_genealogy import (
        build_knowledge_genealogy_graph,
        query_independent_emergence_count,
    )

    arm_id = "ap-dual-emergence"
    key = practical_knowledge_content_key("shared-tech")
    audits = []
    for owner_token in ("agent-a", "agent-b"):
        ledger = form_or_reinforce_practical_knowledge(
            empty_practical_knowledge_ledger(AgentId(owner_token)),
            kind=PracticalKnowledgeKind.FORAGING_METHOD,
            content_key=key,
            content_fingerprint=("cue-a",),
            origin=KnowledgeTransmissionOrigin.INDEPENDENT_DISCOVERY,
            tick=1,
            enabled_kinds=("foraging_method",),
        )
        audits.append(entry_to_audit(ledger.entries[0], tick=1, reason_code="formed"))
    graph = build_knowledge_genealogy_graph(tuple(audits), as_of_tick=2)
    result = query_independent_emergence_count(graph, content_key=key)
    assert result.count >= 2, arm_id
    assert result.emerged_independently_twice is True, arm_id


def test_arm_lifecycle_survival_living_filter() -> None:
    from agents.cognition.practical_knowledge import (
        KnowledgeTransmissionOrigin,
        PracticalKnowledgeKind,
        empty_practical_knowledge_ledger,
        entry_to_audit,
        form_or_reinforce_practical_knowledge,
        practical_knowledge_content_key,
    )
    from analysis.knowledge_genealogy import (
        build_knowledge_genealogy_graph,
        query_who_currently_knows,
        query_who_taught,
    )

    arm_id = "ap-lifecycle-survival"
    config = _arm(experiment_ap_knowledge_genealogy(_base()), arm_id)
    assert config.population_lifecycle is not None, arm_id
    key = practical_knowledge_content_key("foraging")
    teacher = AgentId("agent-a")
    student = AgentId("agent-b")
    teacher_ledger = form_or_reinforce_practical_knowledge(
        empty_practical_knowledge_ledger(teacher),
        kind=PracticalKnowledgeKind.FORAGING_METHOD,
        content_key=key,
        content_fingerprint=("cue-a",),
        origin=KnowledgeTransmissionOrigin.INDEPENDENT_DISCOVERY,
        tick=1,
        enabled_kinds=("foraging_method",),
    )
    student_ledger = form_or_reinforce_practical_knowledge(
        empty_practical_knowledge_ledger(student),
        kind=PracticalKnowledgeKind.FORAGING_METHOD,
        content_key=key,
        content_fingerprint=("cue-a",),
        origin=KnowledgeTransmissionOrigin.TEACHING,
        tick=2,
        enabled_kinds=("foraging_method",),
        source_agent_id=teacher,
        teacher_agent_id=teacher,
    )
    audits = (
        entry_to_audit(teacher_ledger.entries[0], tick=1, reason_code="formed"),
        entry_to_audit(student_ledger.entries[0], tick=2, reason_code="formed"),
    )
    graph = build_knowledge_genealogy_graph(
        audits, as_of_tick=5, death_ticks={"agent-a": 3}
    )
    living = query_who_currently_knows(graph, content_key=key)
    assert [agent for _, agent in living.items] == ["agent-b"], arm_id
    teachers = query_who_taught(
        graph, content_key=key, holder_agent_id="agent-b", include_dead_holders=True
    )
    assert "agent-a" in [agent for _, agent in teachers.items], arm_id


def test_arm_capability_join_unmatched_anchor() -> None:
    from agents.cognition.practical_knowledge import (
        KnowledgeTransmissionOrigin,
        PracticalKnowledgeKind,
        empty_practical_knowledge_ledger,
        form_or_reinforce_practical_knowledge,
        practical_knowledge_content_key,
        resolve_capability_anchor,
    )

    arm_id = "ap-capability-join"
    config = _arm(experiment_ap_knowledge_genealogy(_base()), arm_id)
    assert any(
        agent.cognition.skill_learning_mode.value == "deterministic"
        for agent in config.agents
    ), arm_id
    anchor = resolve_capability_anchor(PracticalKnowledgeKind.FORAGING_METHOD)
    assert anchor == "foraging", arm_id
    ledger = form_or_reinforce_practical_knowledge(
        empty_practical_knowledge_ledger(AgentId("agent-a")),
        kind=PracticalKnowledgeKind.FORAGING_METHOD,
        content_key=practical_knowledge_content_key("forage"),
        content_fingerprint=("cue-a",),
        origin=KnowledgeTransmissionOrigin.INDEPENDENT_DISCOVERY,
        tick=1,
        enabled_kinds=("foraging_method",),
        capability_anchor=anchor,
    )
    # Knowledge entry never fabricates objective skill levels.
    assert ledger.entries[0].capability_anchor == "foraging", arm_id
    assert not hasattr(ledger, "objective_level"), arm_id


def test_arm_channel_off_and_flags_off_schemas() -> None:
    definition = experiment_ap_knowledge_genealogy(_base())
    channel_off = _arm(definition, "ap-channel-off")
    assert channel_off.schema_version == RUNNER_SCHEMA_VERSION_V34, "ap-channel-off"
    assert channel_off.knowledge_genealogy is None, "ap-channel-off"
    flags_off = _arm(definition, "ap-flags-off")
    assert flags_off.schema_version == RUNNER_SCHEMA_VERSION_V4, "ap-flags-off"
    assert flags_off.v3_capability_flags.enabled_names() == (), "ap-flags-off"
