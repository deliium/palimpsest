# mypy: ignore-errors

"""runner-config-v58 disease seam and inherited family preservation."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from experiments.scientific_hypotheses_scenario import scientific_hypotheses_scenario
from simulation.disease_config import (
    DISEASE_POLICY_ID,
    DiseaseConfigError,
    DiseaseMechanicsSpec,
    decode_disease_mechanics,
    encode_disease_mechanics,
)
from simulation.measurement_config import MeasurementInstrumentsSpec
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V56,
    RUNNER_SCHEMA_VERSION_V57,
    RUNNER_SCHEMA_VERSION_V58,
    SUPPORTED_RUNNER_SCHEMA_VERSIONS,
    AgentCognitionSpec,
    AgentRunnerSpec,
    SimulationRunnerConfig,
    V3CapabilityFlags,
    V4CapabilityFlags,
    WorldScenarioSpec,
    example_collective_projects_spec,
)
from simulation.runner_serialization import (
    RunnerSerializationError,
    decode_runner_config,
    encode_runner_config,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import EntityId, WorldId, WorldRevision
from world.measurement import (
    CalibrationState,
    InstrumentState,
    MeasurementQuantity,
    MeasurementReference,
    MeasurementUnit,
    MeasurementUnitKind,
)
from world.models import Item, LifeStatus, default_physical_rules
from world.production import example_production_catalog
from world.regions import (
    CognitionMode,
    LocationRegion,
    RegionDefinition,
    RegionsMigrationSpec,
    RouteSpec,
)
from world.values import ItemKind, ItemLoad

pytestmark = pytest.mark.unit

_CELSIUS = MeasurementUnit(MeasurementUnitKind.CELSIUS)


def _disease_spec(
    *,
    founders: tuple[EntityId, ...] = (),
    exposure: int = 100,
    transmission: int = 200,
    symptom: int = 300,
    mortality: int = 50,
    latent_ticks: int = 2,
    active_ticks: int = 3,
    immunity: bool = True,
) -> DiseaseMechanicsSpec:
    return DiseaseMechanicsSpec(
        policy_id=DISEASE_POLICY_ID,
        initial_latent_entity_ids=founders,
        exposure_chance_milli=exposure,
        transmission_chance_milli=transmission,
        symptom_chance_milli=symptom,
        mortality_chance_milli=mortality,
        latent_ticks=latent_ticks,
        active_ticks=active_ticks,
        immunity_after_recovery=immunity,
    )


def _infra_base(*, with_travel: bool = False) -> SimulationRunnerConfig:
    body = alive_body("body-1", location_id="loc-a")
    agent_id = AgentId("agent-1")
    locations = (
        make_location("loc-a", adjacent=("loc-b",)),
        make_location("loc-b", adjacent=("loc-a",)),
    )
    weather = (make_weather("loc-a"), make_weather("loc-b"))
    base = base_runner_config_from_scenario(
        seed=34,
        stochastic_identity="disease-v58",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-disease-v58"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=locations,
            bodies=(body,),
            weather=weather,
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=agent_id,
                entity_id=body.entity_id,
                cognition=AgentCognitionSpec(agent_id=agent_id),
            ),
        ),
        max_ticks=32,
    )
    regions = None
    v3_flags = V3CapabilityFlags()
    if with_travel:
        regions = RegionsMigrationSpec(
            regions=(
                RegionDefinition("west", "West"),
                RegionDefinition("east", "East"),
            ),
            location_regions=(
                LocationRegion(EntityId("loc-a"), "west"),
                LocationRegion(EntityId("loc-b"), "east"),
            ),
            routes=(RouteSpec(EntityId("loc-a"), EntityId("loc-b"), 2, 3.0),),
            max_arrival_wait_ticks=2,
            residence_min_ticks=2,
            destination_memory_limit=2,
            destination_hop_limit=1,
            cognition_mode=CognitionMode.DISABLED,
        )
        v3_flags = V3CapabilityFlags(multi_polity_migration=True)
    catalog = example_production_catalog()
    return replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V56,
        v3_capability_flags=v3_flags,
        regions_migration=regions,
        collective_projects=example_collective_projects_spec(),
        v4_capability_flags=V4CapabilityFlags(infrastructure_networks=True),
        agents=tuple(
            replace(
                agent,
                cognition=replace(agent.cognition, production_catalog=catalog),
            )
            for agent in base.agents
        ),
    )


def _science_base() -> SimulationRunnerConfig:
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    base = base_runner_config_from_scenario(
        seed=11,
        stochastic_identity="disease-science-v58",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-disease-science-v58"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(make_location(),),
            bodies=(body,),
            weather=(make_weather(),),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=agent_id,
                entity_id=body.entity_id,
                cognition=AgentCognitionSpec(agent_id=agent_id),
            ),
        ),
        max_ticks=64,
    )
    definition = scientific_hypotheses_scenario(base, max_ticks=64)
    return next(
        condition.runner_config
        for condition in definition.conditions
        if condition.condition_id == "science-enabled"
    )


def _tool_bundle(
    config: SimulationRunnerConfig,
) -> tuple[WorldScenarioSpec, MeasurementInstrumentsSpec]:
    body = config.scenario.bodies[0]
    items = list(config.scenario.items)
    inventory = list(body.inventory)
    instrument_item = Item(
        entity_id=EntityId("item:thermometer"),
        name="thermometer",
        kind=ItemKind.TOOL,
        load=ItemLoad(1),
        holder_id=body.entity_id,
    )
    items.append(instrument_item)
    inventory.append(instrument_item.entity_id)
    reference_item = Item(
        entity_id=EntityId("item:reference"),
        name="reference",
        kind=ItemKind.TOOL,
        load=ItemLoad(1),
        holder_id=body.entity_id,
    )
    items.append(reference_item)
    inventory.append(reference_item.entity_id)
    scenario = replace(
        config.scenario,
        items=tuple(items),
        bodies=(replace(body, inventory=tuple(inventory)),),
    )
    instruments = MeasurementInstrumentsSpec(
        policy_version="measurement-instruments.v1",
        instruments=(
            InstrumentState(
                item_id=instrument_item.entity_id,
                quantity=MeasurementQuantity.AMBIENT_TEMPERATURE,
                unit=_CELSIUS,
                nominal_step_milli=1000,
                intrinsic_bias_milli=0,
                base_error_bound_milli=0,
                damage_milli=0,
                correction_milli=0,
                calibration_state=CalibrationState.NEVER_ADJUSTED,
                calibration_revision=0,
            ),
        ),
        references=(
            MeasurementReference(
                item_id=reference_item.entity_id,
                unit=_CELSIUS,
                nominal_value_milli=20000,
                physical_value_milli=21000,
            ),
        ),
    )
    return scenario, instruments


def _as_v58(
    config: SimulationRunnerConfig,
    *,
    founders: tuple[EntityId, ...] | None = None,
    with_instruments: bool = False,
) -> SimulationRunnerConfig:
    body_id = config.scenario.bodies[0].entity_id
    seed_founders = (body_id,) if founders is None else founders
    flags = replace(
        config.v4_capability_flags,
        epidemics=True,
        infrastructure_networks=True,
    )
    measurement = None
    scenario = config.scenario
    capability_flags = config.capability_flags
    if with_instruments:
        flags = replace(flags, science=True)
        scenario, measurement = _tool_bundle(config)
        capability_flags = replace(
            config.capability_flags, predictive_world_model=True
        )
    return replace(
        config,
        schema_version=RUNNER_SCHEMA_VERSION_V58,
        scenario=scenario,
        capability_flags=capability_flags,
        v4_capability_flags=flags,
        collective_projects=config.collective_projects
        or example_collective_projects_spec(),
        measurement_instruments=measurement,
        disease_mechanics=_disease_spec(founders=seed_founders),
    )


def test_v58_is_supported() -> None:
    assert RUNNER_SCHEMA_VERSION_V58 == "runner-config-v58"
    assert RUNNER_SCHEMA_VERSION_V58 in SUPPORTED_RUNNER_SCHEMA_VERSIONS


def test_disease_spec_round_trip_and_rejects_bad_shapes() -> None:
    spec = _disease_spec(founders=(EntityId("body-1"),), immunity=False)
    encoded = encode_disease_mechanics(spec)
    assert decode_disease_mechanics(encoded) == spec
    with pytest.raises(DiseaseConfigError) as excinfo:
        decode_disease_mechanics({**encoded, "extra": True})
    assert excinfo.value.code == "disease_spec_invalid"
    with pytest.raises(DiseaseConfigError):
        _disease_spec(exposure=1001)
    with pytest.raises(DiseaseConfigError):
        _disease_spec(latent_ticks=0)
    with pytest.raises(DiseaseConfigError):
        DiseaseMechanicsSpec(
            policy_id=DISEASE_POLICY_ID,
            initial_latent_entity_ids=(EntityId("body-2"), EntityId("body-1")),
            exposure_chance_milli=0,
            transmission_chance_milli=0,
            symptom_chance_milli=0,
            mortality_chance_milli=0,
            latent_ticks=1,
            active_ticks=1,
            immunity_after_recovery=True,
        )


def _assert_v58_round_trip(
    config: SimulationRunnerConfig, *, expect_instruments: bool
) -> None:
    payload = encode_runner_config(config)
    document = json.loads(payload)
    assert document["schema_version"] == RUNNER_SCHEMA_VERSION_V58
    assert "disease_mechanics" in document
    assert ("measurement_instruments" in document) is expect_instruments
    decoded = decode_runner_config(payload)
    assert decoded.schema_version == RUNNER_SCHEMA_VERSION_V58
    assert decoded.disease_mechanics == config.disease_mechanics
    assert decoded.v4_capability_flags.epidemics is True
    assert (decoded.measurement_instruments is not None) is expect_instruments
    assert encode_runner_config(decoded) == payload


def test_v58_round_trip_infrastructure_only() -> None:
    _assert_v58_round_trip(
        _as_v58(_infra_base(), founders=()),
        expect_instruments=False,
    )


def test_v58_round_trip_with_travel() -> None:
    _assert_v58_round_trip(
        _as_v58(_infra_base(with_travel=True), founders=()),
        expect_instruments=False,
    )


def _science_infra_base(*, with_travel: bool) -> SimulationRunnerConfig:
    science = _science_base()
    base = _infra_base(with_travel=with_travel)
    return replace(
        base,
        capability_flags=replace(base.capability_flags, predictive_world_model=True),
        v3_capability_flags=replace(
            base.v3_capability_flags,
            cultural_historical_memory=True,
        ),
        cultural_feature_provenance=science.cultural_feature_provenance,
        bounded_experimentation=science.bounded_experimentation,
        v4_capability_flags=V4CapabilityFlags(
            infrastructure_networks=True, science=True
        ),
    )


def test_v58_round_trip_with_instruments() -> None:
    _assert_v58_round_trip(
        _as_v58(_science_infra_base(with_travel=False), with_instruments=True),
        expect_instruments=True,
    )


def test_v58_round_trip_with_travel_and_instruments() -> None:
    _assert_v58_round_trip(
        _as_v58(_science_infra_base(with_travel=True), with_instruments=True),
        expect_instruments=True,
    )


def test_v58_empty_founder_list_is_valid() -> None:
    config = _as_v58(_infra_base(), founders=())
    assert config.disease_mechanics is not None
    assert config.disease_mechanics.initial_latent_entity_ids == ()
    payload = encode_runner_config(config)
    assert decode_runner_config(payload).disease_mechanics == config.disease_mechanics


def test_disease_rejects_nonliving_and_unknown_founders() -> None:
    from world.values import Health

    base = _infra_base()
    dead_body = replace(
        base.scenario.bodies[0],
        life_status=LifeStatus.DEAD,
        health=Health(0.0),
    )
    dead_scenario = replace(base.scenario, bodies=(dead_body,))
    with pytest.raises(ValueError, match="code=disease_founder_invalid"):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V58,
            scenario=dead_scenario,
            v4_capability_flags=V4CapabilityFlags(
                infrastructure_networks=True, epidemics=True
            ),
            disease_mechanics=_disease_spec(founders=(dead_body.entity_id,)),
        )
    with pytest.raises(ValueError, match="code=disease_founder_invalid"):
        _as_v58(base, founders=(EntityId("body-missing"),))


def test_disease_flag_and_schema_mismatches_fail_closed() -> None:
    base = _infra_base()
    with pytest.raises(ValueError, match="code=disease_schema_required"):
        replace(
            base,
            disease_mechanics=_disease_spec(),
            v4_capability_flags=V4CapabilityFlags(
                infrastructure_networks=True, epidemics=True
            ),
        )
    with pytest.raises(ValueError, match="code=disease_spec_required"):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V58,
            v4_capability_flags=V4CapabilityFlags(
                infrastructure_networks=True, epidemics=True
            ),
        )
    with pytest.raises(ValueError, match="code=disease_flag_spec_mismatch"):
        replace(
            base,
            v4_capability_flags=V4CapabilityFlags(
                infrastructure_networks=True, epidemics=True
            ),
        )
    with pytest.raises(ValueError, match="code=disease_flag_required"):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V58,
            v4_capability_flags=V4CapabilityFlags(infrastructure_networks=True),
            disease_mechanics=_disease_spec(),
        )
    with pytest.raises(ValueError, match="code=disease_infrastructure_required"):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V58,
            collective_projects=None,
            v4_capability_flags=V4CapabilityFlags(epidemics=True),
            disease_mechanics=_disease_spec(),
        )
    with pytest.raises(ValueError, match="code=disease_spec_required"):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V58,
            v4_capability_flags=V4CapabilityFlags(infrastructure_networks=True),
        )


def test_v56_rejects_disease_sibling_and_v57_unchanged() -> None:
    base = _infra_base()
    payload = encode_runner_config(base)
    document = json.loads(payload)
    document["disease_mechanics"] = encode_disease_mechanics(_disease_spec())
    with pytest.raises(RunnerSerializationError):
        decode_runner_config(
            json.dumps(document, separators=(",", ":"), sort_keys=True).encode("utf-8")
        )
    science_base = _science_base()
    scenario, instruments = _tool_bundle(science_base)
    science = replace(
        science_base,
        schema_version=RUNNER_SCHEMA_VERSION_V57,
        scenario=scenario,
        measurement_instruments=instruments,
        v4_capability_flags=replace(science_base.v4_capability_flags, science=True),
    )
    v57_payload = encode_runner_config(science)
    assert decode_runner_config(v57_payload).schema_version == RUNNER_SCHEMA_VERSION_V57
    assert "disease_mechanics" not in json.loads(v57_payload)


def test_legacy_v4_fingerprint_unchanged() -> None:
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    config = base_runner_config_from_scenario(
        seed=1,
        stochastic_identity="disease-legacy-v4",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-disease-legacy"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(make_location(),),
            bodies=(body,),
            weather=(make_weather(),),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=agent_id,
                entity_id=body.entity_id,
                cognition=AgentCognitionSpec(agent_id=agent_id),
            ),
        ),
        max_ticks=4,
    )
    assert config.schema_version == RUNNER_SCHEMA_VERSION_V4
    first = encode_runner_config(config)
    second = encode_runner_config(decode_runner_config(first))
    assert first == second
    assert b"disease_mechanics" not in first


@pytest.mark.asyncio
async def test_runner_bootstrap_snapshot_keeps_disease_and_artifacts_on_v22() -> None:
    """Runner `_engine_snapshot` must match service disease assembly with artifacts."""
    from simulation.disease_checkpoint import DiseaseCheckpointSection
    from simulation.journal import _decode_world_snapshot, _encode_world_snapshot
    from simulation.models import RunId
    from simulation.runner import RunnerDependencyFactories, SimulationRunner
    from simulation.versioning import (
        EPIDEMICS_WRITE_PAIR_CODEC,
        EPIDEMICS_WRITE_PAIR_EVENT,
    )
    from world.artifacts import ArtifactContent, ArtifactKind, InformationArtifact
    from world.events import EVENT_SCHEMA_REPLAY_V24

    body = alive_body("body-1", location_id="loc-a")
    artifact = InformationArtifact(
        artifact_id=EntityId("artifact-seed"),
        kind=ArtifactKind.MARK,
        author_id=body.entity_id,
        created_tick=0,
        content=ArtifactContent(marks=("seed",)),
        location_id=EntityId("loc-a"),
    )
    base = _infra_base()
    config = _as_v58(
        replace(
            base,
            scenario=replace(base.scenario, artifacts=(artifact,)),
        ),
        founders=(body.entity_id,),
    )
    assert config.disease_mechanics is not None
    runner = await SimulationRunner.from_config(
        config,
        run_id=RunId("run-disease-artifact-snapshot"),
        factories=RunnerDependencyFactories(),
    )
    snapshot = runner._bootstrap_checkpoint
    assert snapshot.persistence_codec_version == EPIDEMICS_WRITE_PAIR_CODEC == "v22"
    assert snapshot.event_schema_version == EPIDEMICS_WRITE_PAIR_EVENT
    assert snapshot.event_schema_version == EVENT_SCHEMA_REPLAY_V24
    assert type(snapshot.disease_mechanics) is DiseaseCheckpointSection
    assert snapshot.disease_mechanics.rows[0].body_id == body.entity_id
    assert snapshot.disease_mechanics.rows[0].phase == "latent"
    assert len(snapshot.artifacts) == 1
    assert snapshot.artifacts[0].artifact_id == artifact.artifact_id
    # Round-trip proves the inherited artifact allowlist accepts codec v22.
    encoded = _encode_world_snapshot(snapshot, include_integrity_hash=True)
    assert "disease_mechanics" in encoded
    assert encoded["artifacts"][0]["artifact_id"] == "artifact-seed"
    decoded = _decode_world_snapshot(encoded, path="$")
    assert type(decoded.disease_mechanics) is DiseaseCheckpointSection
    assert decoded.artifacts[0].artifact_id == artifact.artifact_id
    assert decoded.persistence_codec_version == "v22"
