"""Locked infrastructure catalog and public-good membership pins."""

from __future__ import annotations

import pytest

from simulation.compatibility import V4_OWNED_CAPABILITY_FLAGS
from simulation.runner_models import (
    _V4_OWNED_CAPABILITY_FLAGS,
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V56,
    CollectiveProjectsSpec,
    V4CapabilityFlags,
)
from world.collective_projects import (
    COLLECTIVE_PROJECT_CATALOG,
    DRAW_PUBLIC_KINDS,
    PRESENCE_PUBLIC_KINDS,
    PUBLIC_GOOD_KINDS,
    CollectiveProjectKind,
)
from world.infrastructure import (
    INFRASTRUCTURE_CATALOG,
    INFRASTRUCTURE_FORBIDDEN_FIELDS,
    INFRASTRUCTURE_ID_PREFIX,
    INFRASTRUCTURE_NETWORKS_POLICY_ID,
    MAX_INFRA_BODY_BONUS,
    MAX_INFRA_ITEM_BONUS,
    MAX_INFRASTRUCTURE_ASSETS,
    REPAIR_INTEGRITY_DELTA,
    InfrastructureKind,
    InfrastructureStatus,
    InfrastructureTopology,
    catalog_row,
    effects_active,
)
from world.production import StructureKind

pytestmark = pytest.mark.unit

_EXPECTED_OWNED = frozenset(
    {
        "organizations",
        "formal_rules",
        "legal_disputes",
        "diplomacy",
        "organized_conflict",
        "infrastructure_networks",
        "supply_chains",
        "markets_credit",
    }
)

_SHARED_KIND_MAP = {
    InfrastructureKind.BRIDGE: CollectiveProjectKind.BRIDGE,
    InfrastructureKind.STORAGE: CollectiveProjectKind.STORAGE,
    InfrastructureKind.WELL: CollectiveProjectKind.WELL,
    InfrastructureKind.COMMUNICATION_MARKER: CollectiveProjectKind.WARNING_POST,
}


def test_owned_flag_frozensets_include_infrastructure() -> None:
    assert _V4_OWNED_CAPABILITY_FLAGS == _EXPECTED_OWNED
    assert V4_OWNED_CAPABILITY_FLAGS == _EXPECTED_OWNED
    assert _V4_OWNED_CAPABILITY_FLAGS == V4_OWNED_CAPABILITY_FLAGS
    flags = V4CapabilityFlags(infrastructure_networks=True)
    assert flags.owned_enabled_names() == ("infrastructure_networks",)
    assert flags.unimplemented_enabled_names() == ()


def test_policy_and_caps_are_locked() -> None:
    assert INFRASTRUCTURE_NETWORKS_POLICY_ID == "infrastructure-networks.v1"
    assert INFRASTRUCTURE_ID_PREFIX == "infra-"
    assert MAX_INFRASTRUCTURE_ASSETS == 64
    assert MAX_INFRA_BODY_BONUS == 8
    assert MAX_INFRA_ITEM_BONUS == 8
    assert REPAIR_INTEGRITY_DELTA == 0.15
    assert InfrastructureStatus.OPERATIONAL.value == "operational"
    assert set(InfrastructureStatus) == {
        InfrastructureStatus.OPERATIONAL,
        InfrastructureStatus.DAMAGED,
        InfrastructureStatus.DESTROYED,
    }
    assert "under_construction" not in {status.value for status in InfrastructureStatus}
    assert "score" in INFRASTRUCTURE_FORBIDDEN_FIELDS
    assert "auto_maintain" in INFRASTRUCTURE_FORBIDDEN_FIELDS
    assert "grid" in INFRASTRUCTURE_FORBIDDEN_FIELDS


def test_catalog_exact_constants() -> None:
    assert len(INFRASTRUCTURE_CATALOG) == 8
    expectations = {
        InfrastructureKind.ROAD: (
            InfrastructureTopology.EDGE,
            "road",
            StructureKind.ROAD,
            5,
            "stone",
            3,
            0.01,
            0.35,
        ),
        InfrastructureKind.BRIDGE: (
            InfrastructureTopology.NODE,
            "bridge",
            StructureKind.BRIDGE,
            4,
            "stone",
            2,
            0.01,
            0.35,
        ),
        InfrastructureKind.STORAGE: (
            InfrastructureTopology.NODE,
            "storage",
            StructureKind.STORE,
            2,
            "wood",
            1,
            0.01,
            0.35,
        ),
        InfrastructureKind.WELL: (
            InfrastructureTopology.NODE,
            "well",
            StructureKind.WELL,
            3,
            "stone",
            2,
            0.01,
            0.35,
        ),
        InfrastructureKind.IRRIGATION: (
            InfrastructureTopology.NODE,
            "irrigation",
            StructureKind.IRRIGATION,
            4,
            "stone",
            2,
            0.015,
            0.40,
        ),
        InfrastructureKind.COMMUNICATION_MARKER: (
            InfrastructureTopology.NODE,
            "warning_post",
            StructureKind.WARNING_POST,
            2,
            "wood",
            1,
            0.01,
            0.35,
        ),
        InfrastructureKind.TRADE_POST: (
            InfrastructureTopology.NODE,
            "trade_post",
            StructureKind.TRADE_POST,
            4,
            "wood",
            2,
            0.01,
            0.35,
        ),
        InfrastructureKind.LARGE_SHELTER: (
            InfrastructureTopology.NODE,
            "large_shelter",
            StructureKind.SHELTER,
            5,
            "wood",
            3,
            0.01,
            0.35,
        ),
    }
    for kind, expected in expectations.items():
        row = catalog_row(kind)
        assert (
            row.topology,
            row.collective_kind,
            row.structure_kind,
            row.labor_required,
            row.material_name,
            row.materials_required,
            row.decay_per_tick,
            row.operational_integrity_min,
        ) == expected

    road = catalog_row(InfrastructureKind.ROAD)
    assert road.travel_duration_delta == -1
    assert road.travel_fatigue_delta == -1.0
    assert catalog_row(InfrastructureKind.BRIDGE).bridge_fatigue_delta == -2.0
    assert catalog_row(InfrastructureKind.STORAGE).store_capacity_delta == 3
    assert catalog_row(InfrastructureKind.IRRIGATION).resource_regen_delta == 0.05
    marker = catalog_row(InfrastructureKind.COMMUNICATION_MARKER)
    assert marker.exposure_relief_coefficient == 0.5
    trade = catalog_row(InfrastructureKind.TRADE_POST)
    assert trade.item_capacity_delta == 2
    assert trade.store_capacity_delta == 2
    shelter = catalog_row(InfrastructureKind.LARGE_SHELTER)
    assert shelter.body_capacity_delta == 2
    assert shelter.exposure_relief_coefficient == 0.25


def test_public_good_sets_are_explicit_pre_v4_16() -> None:
    assert PUBLIC_GOOD_KINDS == frozenset(
        {
            CollectiveProjectKind.SHARED_SHELTER,
            CollectiveProjectKind.BRIDGE,
            CollectiveProjectKind.STORAGE,
            CollectiveProjectKind.WINTER_RESERVE,
            CollectiveProjectKind.WELL,
            CollectiveProjectKind.WARNING_POST,
        }
    )
    assert CollectiveProjectKind.RECORD_SITE not in PUBLIC_GOOD_KINDS
    for name in ("road", "irrigation", "trade_post", "large_shelter"):
        assert name not in {kind.value for kind in PUBLIC_GOOD_KINDS}
    assert DRAW_PUBLIC_KINDS == frozenset(
        {
            CollectiveProjectKind.WELL,
            CollectiveProjectKind.STORAGE,
            CollectiveProjectKind.WINTER_RESERVE,
        }
    )
    assert PRESENCE_PUBLIC_KINDS == frozenset(
        {
            CollectiveProjectKind.SHARED_SHELTER,
            CollectiveProjectKind.BRIDGE,
            CollectiveProjectKind.WARNING_POST,
        }
    )


def test_shared_catalog_labor_materials_align() -> None:
    for infra_kind, collective_kind in _SHARED_KIND_MAP.items():
        infra = catalog_row(infra_kind)
        collective = COLLECTIVE_PROJECT_CATALOG[collective_kind]
        assert infra.labor_required == collective.labor_required
        assert infra.material_name == collective.material_name
        assert infra.materials_required == collective.materials_required
        assert infra.structure_kind == collective.completion_structure_kind


def test_effects_active_requires_operational_floor() -> None:
    kind = InfrastructureKind.ROAD
    assert effects_active(
        status=InfrastructureStatus.OPERATIONAL, integrity=0.35, kind=kind
    )
    assert not effects_active(
        status=InfrastructureStatus.OPERATIONAL, integrity=0.34, kind=kind
    )
    assert not effects_active(
        status=InfrastructureStatus.DAMAGED, integrity=1.0, kind=kind
    )
    assert not effects_active(
        status=InfrastructureStatus.DESTROYED, integrity=0.0, kind=kind
    )


def test_infrastructure_flag_requires_collective_projects() -> None:
    from dataclasses import replace

    from agents.models import AgentId
    from experiments.catalog import base_runner_config_from_scenario
    from simulation.runner_models import (
        AgentCognitionSpec,
        AgentRunnerSpec,
        WorldScenarioSpec,
    )
    from tests.simulation_helpers import alive_body, make_location, make_weather
    from world.identifiers import WorldId, WorldRevision
    from world.models import default_physical_rules

    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    base = base_runner_config_from_scenario(
        seed=11,
        stochastic_identity="cmp-infra-contract",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-infra-contract"),
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
        max_ticks=2,
    )
    v56 = replace(base, schema_version=RUNNER_SCHEMA_VERSION_V56)
    with pytest.raises(
        ValueError, match="code=infrastructure_requires_collective_projects"
    ):
        replace(
            v56,
            v4_capability_flags=V4CapabilityFlags(infrastructure_networks=True),
        )
    accepted = replace(
        v56,
        collective_projects=CollectiveProjectsSpec(),
        v4_capability_flags=V4CapabilityFlags(infrastructure_networks=True),
    )
    assert accepted.v4_capability_flags.infrastructure_networks is True
    with pytest.raises(ValueError, match="code=v4_capability_requires_v56"):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V4,
            collective_projects=CollectiveProjectsSpec(),
            v4_capability_flags=V4CapabilityFlags(infrastructure_networks=True),
        )
