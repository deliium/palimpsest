"""V4-06 exact compatibility pins and append-only surfaces."""

from __future__ import annotations

import pytest

from analysis.specifications import METRIC_FAMILY_COUNT
from api.routes.formal_rule import router as formal_rule_router
from api.routes.organization import router as organization_router
from observer import SUPPORTED_OBSERVER_PROTOCOLS
from simulation import (
    ALEMBIC_HEAD_REVISION,
    OBSERVER_LAYOUT_SCHEMA_VERSION,
    OBSERVER_PROTOCOL_VERSION,
)
from simulation.formal_rule_models import FORMAL_RULE_SNAPSHOT_SCHEMA
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION,
    RUNNER_SCHEMA_VERSION_V55,
    RUNNER_SCHEMA_VERSION_V56,
    SUPPORTED_RUNNER_SCHEMA_VERSIONS,
)
from simulation.runner_models import (
    V4CapabilityFlags as Flags,
)
from simulation.versioning import V4_WRITE_PAIR_RESERVATIONS
from world._rules import COMMAND_RULE_MATRIX
from world.events import EVENT_SCHEMA_REPLAY_V22

pytestmark = pytest.mark.unit


def test_exact_pins() -> None:
    assert RUNNER_SCHEMA_VERSION == "runner-config-v4"
    assert RUNNER_SCHEMA_VERSION_V55 == "runner-config-v55"
    assert RUNNER_SCHEMA_VERSION_V56 in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    assert EVENT_SCHEMA_REPLAY_V22 == 22
    assert len(COMMAND_RULE_MATRIX) == 43
    assert METRIC_FAMILY_COUNT == 212
    assert ALEMBIC_HEAD_REVISION == "0017"
    assert OBSERVER_PROTOCOL_VERSION == "observer-protocol-v1"
    assert OBSERVER_LAYOUT_SCHEMA_VERSION == "observer-layout-v1"
    assert SUPPORTED_OBSERVER_PROTOCOLS == ("observer-protocol-v1",)


def test_no_v57_runner_schema_exists() -> None:
    assert "runner-config-v57" not in SUPPORTED_RUNNER_SCHEMA_VERSIONS


def test_no_new_write_pair_reservation() -> None:
    assert len(V4_WRITE_PAIR_RESERVATIONS) == 4
    assert {item.context_id.value for item in V4_WRITE_PAIR_RESERVATIONS} == {
        "infrastructure_networks",
        "epidemics",
        "ecological_feedback",
        "disasters",
    }


def test_catalog_is_160_with_evidence_families_last() -> None:
    from analysis.specifications import all_metric_specifications

    specs = all_metric_specifications()
    assert len(specs) == 212
    assert [spec.family_id.value for spec in specs[148:151]] == [
        "formal_rule_development",
        "formal_rule_authority",
        "formal_rule_response",
    ]
    assert [spec.family_id.value for spec in specs[151:154]] == [
        "dispute_claim_structure",
        "dispute_testimony_independence",
        "dispute_resolution_alignment",
    ]
    assert [spec.family_id.value for spec in specs[154:157]] == [
        "evidence_source_structure",
        "evidence_provenance_continuity",
        "evidence_objective_alignment",
    ]


def test_formal_rules_flag_is_owned_and_five_flags_remain_unowned() -> None:
    assert Flags(formal_rules=True).owned_enabled_names() == ("formal_rules",)
    assert Flags(legal_disputes=True).owned_enabled_names() == ("legal_disputes",)
    assert (
        len(
            [
                name
                for name in (
                    "science",
                    "epidemics",
                    "ecological_feedback",
                    "disasters",
                )
                if Flags(**{name: True}).unimplemented_enabled_names()
            ]
        )
        == 4
    )


def test_six_formal_rule_routes_and_six_organization_routes() -> None:
    formal = [
        route
        for route in formal_rule_router.routes
        if getattr(route, "methods", None) is not None
    ]
    organization = [
        route
        for route in organization_router.routes
        if getattr(route, "methods", None) is not None
    ]
    assert len(formal) == 6
    assert len(organization) == 6
    assert all(
        getattr(route, "methods", None) == {"GET"} for route in formal + organization
    )


def test_formal_rule_snapshot_v1_and_store_v1() -> None:
    assert FORMAL_RULE_SNAPSHOT_SCHEMA == "formal-rule-snapshot-v1"
    assert "formal-rule-store-v1" in (
        __import__(
            "persistence.formal_rule_filesystem", fromlist=["_STORE_SCHEMA"]
        )._STORE_SCHEMA
    )
