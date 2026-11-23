# mypy: ignore-errors

"""runner-config-v60 ecological-resources seam and inherited family preservation."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from simulation.compatibility import V4_OWNED_CAPABILITY_FLAGS
from simulation.ecological_resources_config import (
    ECOLOGICAL_RESOURCES_POLICY_ID,
    EcologicalResourceNodeSpec,
    EcologicalResourcesConfigError,
    EcologicalResourcesSpec,
    decode_ecological_resources,
    encode_ecological_resources,
    policy_sha256_for_ecological_resources,
)
from simulation.medical_beliefs_config import (
    MEDICAL_BELIEFS_POLICY_ID,
    MedicalBeliefsSpec,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V56,
    RUNNER_SCHEMA_VERSION_V59,
    RUNNER_SCHEMA_VERSION_V60,
    SUPPORTED_RUNNER_SCHEMA_VERSIONS,
    AgentCognitionSpec,
    AgentRunnerSpec,
    SimulationRunnerConfig,
    V4CapabilityFlags,
    WorldScenarioSpec,
)
from simulation.runner_serialization import (
    decode_runner_config,
    encode_runner_config,
)
from tests.simulation_helpers import (
    alive_body,
    make_location,
    make_resource,
    make_weather,
)
from tests.unit.test_disease_config import _as_v58, _infra_base, _science_infra_base
from tests.unit.test_medical_beliefs_config import _medical_spec
from world.environment import example_environmental_dynamics
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import default_physical_rules
from world.production import example_production_catalog
from world.supply_chain import supply_chain_production_catalog

pytestmark = pytest.mark.unit

_BASELINE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "runner_configs"
    / "bf_baseline_v4.json"
)


def _node(
    resource_id: str = "res-food",
    *,
    floor: int = 10,
    allowance: int = 0,
    recovery: int = 5,
) -> EcologicalResourceNodeSpec:
    return EcologicalResourceNodeSpec(
        resource_id=EntityId(resource_id),
        minimum_capacity_tenths=floor,
        withdrawal_allowance_tenths=allowance,
        recovery_tenths_per_idle_tick=recovery,
    )


def _ecology_spec(
    *resource_ids: str,
) -> EcologicalResourcesSpec:
    ids = resource_ids or ("res-food",)
    nodes = tuple(
        sorted(
            (_node(resource_id) for resource_id in ids),
            key=lambda n: n.resource_id.value,
        )
    )
    return EcologicalResourcesSpec(
        policy_id=ECOLOGICAL_RESOURCES_POLICY_ID,
        nodes=nodes,
    )


def _ecology_base() -> SimulationRunnerConfig:
    body = alive_body("body-1", location_id="loc-a")
    agent_id = AgentId("agent-1")
    food = make_resource(
        "res-food",
        name="Food",
        location_id="loc-a",
        quantity=4.0,
        maximum_quantity=4.0,
        regeneration_per_tick=1.0,
    )
    water = make_resource(
        "res-water",
        name="Water",
        location_id="loc-a",
        quantity=3.0,
        maximum_quantity=3.0,
        regeneration_per_tick=0.5,
    )
    catalog = supply_chain_production_catalog(example_production_catalog())
    base = base_runner_config_from_scenario(
        seed=60,
        stochastic_identity="ecology-v60",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-ecology-v60"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(make_location("loc-a"),),
            bodies=(body,),
            weather=(make_weather("loc-a"),),
            resources=(food, water),
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
    agent = base.agents[0]
    return replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V56,
        environmental_dynamics=example_environmental_dynamics(),
        v4_capability_flags=V4CapabilityFlags(supply_chains=True),
        agents=(
            replace(
                agent,
                cognition=replace(agent.cognition, production_catalog=catalog),
            ),
        ),
    )


def _as_v60(
    config: SimulationRunnerConfig,
    *,
    spec: EcologicalResourcesSpec | None = None,
    with_disease: bool = False,
    with_medical: bool = False,
    with_instruments: bool = False,
) -> SimulationRunnerConfig:
    flags = config.v4_capability_flags
    replacements: dict[str, object] = {
        "schema_version": RUNNER_SCHEMA_VERSION_V60,
        "ecological_resources": spec or _ecology_spec(),
        "environmental_dynamics": config.environmental_dynamics
        or example_environmental_dynamics(),
        "v4_capability_flags": replace(
            flags,
            supply_chains=True,
            ecological_feedback=True,
        ),
    }
    if with_disease or with_medical:
        disease_base = _as_v58(_infra_base(), founders=())
        replacements["disease_mechanics"] = disease_base.disease_mechanics
        replacements["collective_projects"] = disease_base.collective_projects
        replacements["v4_capability_flags"] = replace(
            replacements["v4_capability_flags"],
            epidemics=True,
            infrastructure_networks=True,
            supply_chains=True,
            ecological_feedback=True,
        )
        if with_instruments:
            instrumented = _as_v58(
                _science_infra_base(with_travel=False),
                with_instruments=True,
            )
            replacements["measurement_instruments"] = (
                instrumented.measurement_instruments
            )
            replacements["scenario"] = instrumented.scenario
            replacements["v4_capability_flags"] = replace(
                replacements["v4_capability_flags"],
                science=True,
            )
    if with_medical:
        replacements["medical_beliefs"] = _medical_spec()
        replacements["v4_capability_flags"] = replace(
            replacements["v4_capability_flags"],
            epidemics=True,
        )
    return replace(config, **replacements)


def test_v60_is_supported_and_flag_owned() -> None:
    assert RUNNER_SCHEMA_VERSION_V60 == "runner-config-v60"
    assert RUNNER_SCHEMA_VERSION_V60 in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    assert "ecological_feedback" in V4_OWNED_CAPABILITY_FLAGS
    assert len(V4_OWNED_CAPABILITY_FLAGS) == 11


def test_spec_round_trip_and_digest() -> None:
    spec = _ecology_spec("res-food", "res-water")
    encoded = encode_ecological_resources(spec)
    assert encoded["policy_id"] == ECOLOGICAL_RESOURCES_POLICY_ID
    assert [row["resource_id"] for row in encoded["nodes"]] == [
        "res-food",
        "res-water",
    ]
    assert decode_ecological_resources(encoded) == spec
    digest = policy_sha256_for_ecological_resources(spec)
    assert len(digest) == 64
    with pytest.raises(EcologicalResourcesConfigError) as excinfo:
        decode_ecological_resources({**encoded, "extra": True})
    assert excinfo.value.code == "ecological_resources_spec_invalid"


def test_rejects_unordered_and_duplicate_nodes() -> None:
    with pytest.raises(EcologicalResourcesConfigError) as excinfo:
        EcologicalResourcesSpec(
            policy_id=ECOLOGICAL_RESOURCES_POLICY_ID,
            nodes=(_node("res-water"), _node("res-food")),
        )
    assert excinfo.value.code == "ecological_resources_node_order_invalid"
    with pytest.raises(EcologicalResourcesConfigError) as excinfo:
        EcologicalResourcesSpec(
            policy_id=ECOLOGICAL_RESOURCES_POLICY_ID,
            nodes=(_node("res-food"), _node("res-food")),
        )
    assert excinfo.value.code == "ecological_resources_node_duplicate"


def test_rejects_non_int_and_out_of_range() -> None:
    with pytest.raises(EcologicalResourcesConfigError):
        EcologicalResourceNodeSpec(
            resource_id=EntityId("res-food"),
            minimum_capacity_tenths=True,  # type: ignore[arg-type]
            withdrawal_allowance_tenths=0,
            recovery_tenths_per_idle_tick=1,
        )
    with pytest.raises(EcologicalResourcesConfigError):
        EcologicalResourceNodeSpec(
            resource_id=EntityId("res-food"),
            minimum_capacity_tenths=0,
            withdrawal_allowance_tenths=0,
            recovery_tenths_per_idle_tick=1,
        )
    with pytest.raises(EcologicalResourcesConfigError):
        decode_ecological_resources(
            {
                "policy_id": ECOLOGICAL_RESOURCES_POLICY_ID,
                "nodes": [
                    {
                        "resource_id": "res-food",
                        "minimum_capacity_tenths": 1.5,
                        "withdrawal_allowance_tenths": 0,
                        "recovery_tenths_per_idle_tick": 1,
                    }
                ],
            }
        )


def test_bf_baseline_v4_unchanged() -> None:
    payload = _BASELINE.read_bytes()
    decoded = decode_runner_config(payload)
    assert decoded.schema_version == RUNNER_SCHEMA_VERSION_V4
    assert decoded.ecological_resources is None
    assert not decoded.v4_capability_flags.ecological_feedback
    assert encode_runner_config(decoded) == payload


def test_v60_round_trip() -> None:
    config = _as_v60(_ecology_base())
    payload = encode_runner_config(config)
    document = json.loads(payload)
    assert document["schema_version"] == RUNNER_SCHEMA_VERSION_V60
    assert "ecological_resources" in document
    assert "environmental_dynamics" in document
    assert "disease_mechanics" not in document
    assert "medical_beliefs" not in document
    decoded = decode_runner_config(payload)
    assert decoded.schema_version == RUNNER_SCHEMA_VERSION_V60
    assert decoded.ecological_resources == config.ecological_resources
    assert encode_runner_config(decoded) == payload


def test_v60_with_disease_and_medical_round_trip() -> None:
    config = _as_v60(_ecology_base(), with_disease=True, with_medical=True)
    payload = encode_runner_config(config)
    document = json.loads(payload)
    assert "disease_mechanics" in document
    assert document["medical_beliefs"] == {
        "policy_id": MEDICAL_BELIEFS_POLICY_ID
    }
    decoded = decode_runner_config(payload)
    assert decoded.disease_mechanics == config.disease_mechanics
    assert decoded.medical_beliefs == MedicalBeliefsSpec(
        policy_id=MEDICAL_BELIEFS_POLICY_ID
    )
    assert encode_runner_config(decoded) == payload


def test_activation_matrix_fails_closed() -> None:
    base = _ecology_base()
    with pytest.raises(ValueError, match="code=ecological_resources_spec_required"):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V60,
            v4_capability_flags=V4CapabilityFlags(
                supply_chains=True,
                ecological_feedback=True,
            ),
            environmental_dynamics=example_environmental_dynamics(),
        )
    with pytest.raises(ValueError, match="code=ecological_resources_schema_mismatch"):
        replace(
            base,
            ecological_resources=_ecology_spec(),
            v4_capability_flags=V4CapabilityFlags(
                supply_chains=True,
                ecological_feedback=True,
            ),
            environmental_dynamics=example_environmental_dynamics(),
        )
    with pytest.raises(ValueError, match="code=ecological_flag_required"):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V60,
            ecological_resources=_ecology_spec(),
            environmental_dynamics=example_environmental_dynamics(),
            v4_capability_flags=V4CapabilityFlags(supply_chains=True),
        )
    with pytest.raises(ValueError, match="code=ecological_supply_chains_required"):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V60,
            ecological_resources=_ecology_spec(),
            environmental_dynamics=example_environmental_dynamics(),
            v4_capability_flags=V4CapabilityFlags(ecological_feedback=True),
        )
    with pytest.raises(ValueError, match="code=ecological_environment_required"):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V60,
            ecological_resources=_ecology_spec(),
            environmental_dynamics=None,
            v4_capability_flags=V4CapabilityFlags(
                supply_chains=True,
                ecological_feedback=True,
            ),
        )
    with pytest.raises(ValueError, match="code=ecological_resources_node_unknown"):
        _as_v60(base, spec=_ecology_spec("res-missing"))
    nonrenewable = replace(
        base.scenario.resources[0],
        regeneration_per_tick=0.0,
    )
    scenario = replace(
        base.scenario,
        resources=(nonrenewable, base.scenario.resources[1]),
    )
    with pytest.raises(ValueError, match="code=ecological_resources_nonrenewable"):
        _as_v60(replace(base, scenario=scenario))
    with pytest.raises(ValueError, match="code=medical_beliefs_requires_epidemics"):
        replace(
            _as_v60(base),
            medical_beliefs=_medical_spec(),
        )


def test_earlier_roots_reject_ecology() -> None:
    base = _ecology_base()
    with pytest.raises(ValueError, match="code=ecological_resources_schema_mismatch"):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V59,
            ecological_resources=_ecology_spec(),
            medical_beliefs=_medical_spec(),
            disease_mechanics=_as_v58(_infra_base()).disease_mechanics,
            collective_projects=_as_v58(_infra_base()).collective_projects,
            v4_capability_flags=V4CapabilityFlags(
                supply_chains=True,
                ecological_feedback=True,
                epidemics=True,
                infrastructure_networks=True,
            ),
            environmental_dynamics=example_environmental_dynamics(),
        )
