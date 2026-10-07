"""Off-gate Experiment AO catalog for knowledge repositories on v34."""

from __future__ import annotations

import logging
from dataclasses import replace

import pytest

from agents.models import AgentId
from analysis.knowledge_repository_metrics import (
    compute_knowledge_repository_access,
    compute_knowledge_repository_organization,
    compute_knowledge_repository_survival,
)
from experiments import (
    OFF_GATE_MATRIX_EXPERIMENT_IDS,
    experiment_ao_knowledge_repositories,
    knowledge_repositories_profile,
)
from experiments.catalog import base_runner_config_from_scenario
from experiments.composition import (
    knowledge_repository_harvest_from_run,
    repository_objective_rows_from_repositories,
)
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionResolutionStatus, ActionSubmission
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V33,
    RUNNER_SCHEMA_VERSION_V34,
    AgentCognitionSpec,
    AgentRunnerSpec,
    WorldScenarioSpec,
    example_durable_records_spec,
    example_knowledge_repositories_spec,
)
from tests.physical_helpers import physical_config, two_location_fixture
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.actions import (
    Attack,
    DamageRecord,
    DepositRecord,
    EstablishRepository,
    Inscribe,
    MaintainRepository,
    RetrieveRecord,
    Take,
    TransferArtifact,
    Wait,
)
from world.artifacts import (
    ArtifactContent,
    ArtifactKind,
    DurableRecordGenre,
    RecordIntegrity,
)
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import LifeStatus, default_physical_rules, non_lethal_physical_rules
from world.repositories import RepositoryStatus

_LOG = logging.getLogger("tests.experiment_ao_knowledge_repositories")

_AO_ARM_IDS = (
    "ao-channel-off",
    "ao-establish-deposit",
    "ao-creator-death",
    "ao-neglect-decay",
    "ao-inaccessible",
    "ao-missing-index",
    "ao-record-degrade",
    "ao-custody-block",
    "ao-subjective-frame",
    "ao-flags-off",
)

pytestmark = pytest.mark.unit


def _base():
    body_a = alive_body("body-a")
    body_b = alive_body("body-b")
    return base_runner_config_from_scenario(
        seed=221,
        stochastic_identity="cmp-ao-knowledge-repositories",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-ao-repositories"),
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


def test_ao_catalog_arms_and_profile(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="experiments.catalog")
    definition = experiment_ao_knowledge_repositories(_base())
    assert definition.experiment_id == "experiment-ao-knowledge-repositories"
    assert "experiment-ao-knowledge-repositories" in OFF_GATE_MATRIX_EXPERIMENT_IDS
    assert tuple(item.condition_id for item in definition.conditions) == _AO_ARM_IDS

    channel_off = _arm(definition, "ao-channel-off")
    assert channel_off.schema_version == RUNNER_SCHEMA_VERSION_V33
    assert channel_off.knowledge_repositories is None
    assert channel_off.durable_records is not None
    assert channel_off.cultural_feature_provenance is not None

    establish = _arm(definition, "ao-establish-deposit")
    assert establish.schema_version == RUNNER_SCHEMA_VERSION_V34
    knowledge_repositories_profile(establish)
    assert establish.knowledge_repositories is not None
    assert (
        establish.knowledge_repositories.access_policy.default_access_mode == "open"
    )

    creator_death = _arm(definition, "ao-creator-death")
    assert creator_death.population_lifecycle is not None
    assert creator_death.v3_capability_flags.generational_population is True

    neglect = _arm(definition, "ao-neglect-decay")
    assert neglect.knowledge_repositories is not None
    assert neglect.knowledge_repositories.maintenance_policy.neglect_ticks == 2

    subjective = _arm(definition, "ao-subjective-frame")
    assert subjective.cultural_feature_provenance is not None
    assert subjective.cultural_feature_provenance.uptake_compose.repositories is True

    flags_off = _arm(definition, "ao-flags-off")
    assert flags_off.schema_version == RUNNER_SCHEMA_VERSION_V4
    assert flags_off.knowledge_repositories is None
    assert flags_off.durable_records is None
    assert flags_off.v3_capability_flags.cultural_historical_memory is False

    assert "experiment_ao_built" in caplog.text
    _LOG.info("ao_catalog_ok arm_count=%s", len(_AO_ARM_IDS))


def test_knowledge_repositories_profile_rejects_wrong_schema() -> None:
    config = _arm(experiment_ao_knowledge_repositories(_base()), "ao-channel-off")
    with pytest.raises(ValueError, match="knowledge_repositories_profile_schema"):
        knowledge_repositories_profile(config)


def _engine(
    *,
    seed: int = 1,
    neglect_ticks: int = 24,
    lethal: bool = False,
) -> WorldEngine:
    rules = default_physical_rules()
    if lethal:
        rules = replace(
            rules,
            attack_hit_probability=1.0,
            attack_damage_min=100,
            attack_damage_max_exclusive=101,
        )
    return WorldEngine(
        config=physical_config(seed, rules=rules) if lethal else physical_config(seed),
        bootstrap=two_location_fixture().as_bootstrap(),
        artifacts_enabled=True,
        durable_records_spec=example_durable_records_spec(),
        knowledge_repositories_spec=example_knowledge_repositories_spec(
            neglect_ticks=neglect_ticks
        ),
    )


def _act(engine: WorldEngine, agent: str, command: object):
    batch = engine.observe()
    return engine.resolve_tick(
        (ActionSubmission(batch.token, AgentId(agent), command),)  # type: ignore[arg-type]
    )


def _establish_deposit(engine: WorldEngine) -> tuple[EntityId, EntityId]:
    established = _act(
        engine, "agent-1", EstablishRepository(location_id=EntityId("loc-1"))
    )
    assert established.resolutions[0].status is ActionResolutionStatus.APPLIED
    repository_id = next(iter(engine._snapshot.world.state.repositories))
    inscribed = _act(
        engine,
        "agent-1",
        Inscribe(
            kind=ArtifactKind.NOTE,
            content=ArtifactContent(marks=("memo", "token")),
            hold=True,
            record_genre=DurableRecordGenre.CHRONICLE,
        ),
    )
    assert inscribed.resolutions[0].status is ActionResolutionStatus.APPLIED
    artifact_id = next(
        aid
        for aid, art in engine._snapshot.world.state.artifacts.items()
        if art.record_genre is DurableRecordGenre.CHRONICLE
    )
    deposited = _act(
        engine,
        "agent-1",
        DepositRecord(repository_id=repository_id, artifact_id=artifact_id),
    )
    assert deposited.resolutions[0].status is ActionResolutionStatus.APPLIED
    return repository_id, artifact_id


def test_arm_establish_deposit_survival_family() -> None:
    arm_id = "ao-establish-deposit"
    engine = _engine()
    repository_id, artifact_id = _establish_deposit(engine)
    repo = engine._snapshot.world.state.repositories[repository_id]
    assert artifact_id in repo.member_artifact_ids, arm_id
    rows = repository_objective_rows_from_repositories(
        engine._snapshot.world.state.repositories
    )
    document = compute_knowledge_repository_survival(
        rows, run_id="ao-run", input_revision="rev-1"
    )
    assert document.values["repository_count"] == 1, arm_id
    assert document.values["intact_count"] == 1, arm_id


def test_arm_creator_death_repository_survives() -> None:
    arm_id = "ao-creator-death"
    engine = _engine(lethal=True)
    repository_id, artifact_id = _establish_deposit(engine)
    # Move attacker onto founder location then kill founder.
    from world.actions import Move

    _act(engine, "agent-2", Move(EntityId("loc-1")))
    killed = _act(engine, "agent-2", Attack(EntityId("body-1")))
    assert killed.resolutions[0].status is ActionResolutionStatus.APPLIED, arm_id
    assert (
        engine._snapshot.world.state.bodies[EntityId("body-1")].life_status
        is LifeStatus.DEAD
    ), arm_id
    repo = engine._snapshot.world.state.repositories[repository_id]
    assert repo.status is not RepositoryStatus.DESTROYED, arm_id
    assert artifact_id in repo.member_artifact_ids, arm_id
    rows = repository_objective_rows_from_repositories(
        engine._snapshot.world.state.repositories
    )
    document = compute_knowledge_repository_survival(
        rows,
        run_id="ao-run",
        input_revision="rev-1",
        founder_death_ticks={"body-1": engine.tick.value},
    )
    assert document.values["surviving_after_founder_death_count"] >= 1, arm_id
    assert document.values["orphaned_member_count"] >= 1, arm_id


def test_arm_neglect_decay_organization() -> None:
    arm_id = "ao-neglect-decay"
    engine = _engine(neglect_ticks=2)
    repository_id, artifact_id = _establish_deposit(engine)
    _act(
        engine,
        "agent-1",
        MaintainRepository(repository_id=repository_id, mode="maintain"),
    )
    from world.actions import IndexRepository

    _act(
        engine,
        "agent-1",
        IndexRepository(
            repository_id=repository_id,
            entries=({"entry_id": "e1", "artifact_id": artifact_id.value},),
        ),
    )
    _act(
        engine,
        "agent-1",
        MaintainRepository(repository_id=repository_id, mode="maintain"),
    )
    for _ in range(2):
        _act(engine, "agent-1", Wait())
    repo = engine._snapshot.world.state.repositories[repository_id]
    assert repo.status is RepositoryStatus.NEGLECTED, arm_id
    harvest = knowledge_repository_harvest_from_run(
        knowledge_repositories_spec=example_knowledge_repositories_spec(
            neglect_ticks=2
        ),
        repositories=engine._snapshot.world.state.repositories,
        events=(),
    )
    assert harvest is not None
    org = compute_knowledge_repository_organization(
        harvest["repository_objective_rows"],
        run_id="ao-run",
        input_revision="rev-1",
        event_rows=(
            {
                "event_kind": "repository_neglected",
                "index_entries_dropped": max(
                    0, 1 - len(repo.index_entries)
                ),
            },
        ),
    )
    assert org.values["member_count_total"] >= 1, arm_id


def test_arm_inaccessible_blocks_access_family() -> None:
    arm_id = "ao-inaccessible"
    engine = _engine()
    repository_id, artifact_id = _establish_deposit(engine)
    engine.mark_repository_inaccessible(repository_id)
    denied = _act(
        engine,
        "agent-1",
        RetrieveRecord(
            repository_id=repository_id, artifact_id=artifact_id, hold=True
        ),
    )
    assert denied.resolutions[0].status is ActionResolutionStatus.REJECTED, arm_id
    access = compute_knowledge_repository_access(
        (
            {
                "event_kind": "retrieve_denied",
                "reason_code": "repository_inaccessible",
            },
        ),
        run_id="ao-run",
        input_revision="rev-1",
        inaccessible_expectations=({"repository_id": repository_id.value},),
    )
    assert access.values["retrieve_deny_count"] == 1, arm_id
    assert access.values["inaccessible_block_count"] >= 1, arm_id


def test_arm_missing_index_coverage_zero() -> None:
    arm_id = "ao-missing-index"
    engine = _engine()
    repository_id, artifact_id = _establish_deposit(engine)
    repo = engine._snapshot.world.state.repositories[repository_id]
    assert len(repo.index_entries) == 0, arm_id
    retrieved = _act(
        engine,
        "agent-1",
        RetrieveRecord(
            repository_id=repository_id, artifact_id=artifact_id, hold=True
        ),
    )
    assert retrieved.resolutions[0].status is ActionResolutionStatus.APPLIED, arm_id
    rows = repository_objective_rows_from_repositories(
        {repository_id: repo}
    )
    org = compute_knowledge_repository_organization(
        rows, run_id="ao-run", input_revision="rev-1"
    )
    assert org.values["index_coverage_ratio"] == 0.0, arm_id


def test_arm_record_degrade_member_damaged_repo_intact() -> None:
    arm_id = "ao-record-degrade"
    engine = _engine()
    repository_id, artifact_id = _establish_deposit(engine)
    damaged = _act(engine, "agent-1", DamageRecord(artifact_id, "damage"))
    assert damaged.resolutions[0].status is ActionResolutionStatus.APPLIED, arm_id
    member = engine._snapshot.world.state.artifacts[artifact_id]
    assert member.integrity is RecordIntegrity.DAMAGED, arm_id
    assert member.custodian_repository_id == repository_id, arm_id
    repo = engine._snapshot.world.state.repositories[repository_id]
    assert repo.status is RepositoryStatus.INTACT, arm_id


def test_arm_custody_block_then_retrieve() -> None:
    arm_id = "ao-custody-block"
    engine = _engine()
    repository_id, artifact_id = _establish_deposit(engine)
    blocked = _act(
        engine,
        "agent-1",
        TransferArtifact(artifact_id=artifact_id, mode="claim"),
    )
    assert blocked.resolutions[0].status is ActionResolutionStatus.REJECTED, arm_id
    take_blocked = _act(engine, "agent-1", Take(artifact_id))
    assert take_blocked.resolutions[0].status is ActionResolutionStatus.REJECTED, (
        arm_id
    )
    retrieved = _act(
        engine,
        "agent-1",
        RetrieveRecord(
            repository_id=repository_id, artifact_id=artifact_id, hold=True
        ),
    )
    assert retrieved.resolutions[0].status is ActionResolutionStatus.APPLIED, arm_id


def test_arm_subjective_frame_no_observation_label() -> None:
    arm_id = "ao-subjective-frame"
    engine = _engine()
    _establish_deposit(engine)
    observation = engine.observe().observations[0]
    for repository in observation.repositories:
        payload = str(repository)
        assert "library" not in payload.lower(), arm_id
        assert "archive" not in payload.lower(), arm_id
        assert getattr(repository, "cultural_label", None) is None, arm_id


def test_arm_channel_off_rejects_establish() -> None:
    arm_id = "ao-channel-off"
    engine = WorldEngine(
        config=physical_config(1),
        bootstrap=two_location_fixture().as_bootstrap(),
        artifacts_enabled=True,
        durable_records_spec=example_durable_records_spec(),
    )
    result = _act(
        engine, "agent-1", EstablishRepository(location_id=EntityId("loc-1"))
    )
    assert result.resolutions[0].status is ActionResolutionStatus.REJECTED, arm_id
    assert engine._snapshot.world.state.repositories == {}, arm_id


def test_arm_flags_off_no_repository_object() -> None:
    arm_id = "ao-flags-off"
    flags_off = _arm(experiment_ao_knowledge_repositories(_base()), arm_id)
    assert flags_off.schema_version == RUNNER_SCHEMA_VERSION_V4, arm_id
    assert flags_off.knowledge_repositories is None, arm_id
    assert flags_off.durable_records is None, arm_id
    assert flags_off.v3_capability_flags.enabled_names() == (), arm_id
