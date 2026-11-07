"""Focused V1-V4 regression gate for V4-04 organization operations."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from analysis.specifications import (
    METRIC_FAMILY_COUNT,
    MetricFamilyId,
    all_metric_specifications,
    metric_specification,
)
from simulation.organization_models import (
    ORGANIZATION_SNAPSHOT_SCHEMA_VERSION,
    ORGANIZATION_SNAPSHOT_SCHEMA_VERSION_V1,
    ORGANIZATION_SNAPSHOT_SCHEMA_VERSION_V2,
    SUPPORTED_ORGANIZATION_SNAPSHOT_SCHEMAS,
)
from simulation.runner_models import SUPPORTED_RUNNER_SCHEMA_VERSIONS
from simulation.v4_architecture import (
    V4_CAPABILITY_FLAGS,
    V4_CONTEXT_MAP_VERSION,
    V4_CONTEXTS,
    V4ContextId,
)

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
ROUTE_MODULE = ROOT / "src" / "api" / "routes" / "organization.py"

AUTHORITY_KEYS = {
    "as_of_tick",
    "authority_contest_count",
    "authority_decision_count",
    "authority_observation_count",
    "authority_procedure_count",
    "authority_role_count",
    "authority_self_authored_count",
    "authority_unknown_count",
    "mean_owner_support",
    "membership_contest_count",
    "orphaned_count",
    "procedure_contest_count",
    "resource_contest_count",
}


def test_catalog_is_154_with_formal_rule_families_last() -> None:
    assert METRIC_FAMILY_COUNT == 176
    assert len(all_metric_specifications()) == 176
    assert [spec.family_id for spec in all_metric_specifications()[-32:-30]] == [
        MetricFamilyId.ORGANIZATION_OPERATIONS,
        MetricFamilyId.ORGANIZATION_OPERATION_AUTHORITY,
    ]
    assert [spec.family_id for spec in all_metric_specifications()[-30:-28]] == [
        MetricFamilyId.ORGANIZATION_COLLECTIVE_AGENCY,
        MetricFamilyId.ORGANIZATION_COLLECTIVE_IMPLEMENTATION,
    ]


def test_authority_family_has_exact_value_keys() -> None:
    spec = metric_specification(MetricFamilyId.ORGANIZATION_OPERATION_AUTHORITY)
    assert set(spec.value_keys) == AUTHORITY_KEYS
    assert spec.version_identifier == "organization_operation_authority@1"


def test_operation_route_is_get_only_with_six_routes() -> None:
    tree = ast.parse(ROUTE_MODULE.read_text(encoding="utf-8"))
    routes = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and any(
            isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Attribute)
            and decorator.func.attr == "get"
            for decorator in node.decorator_list
        )
    ]
    assert len(routes) == 6
    source = ROUTE_MODULE.read_text(encoding="utf-8")
    assert "/organizations/operations" in source
    for verb in ("@router.post", "@router.put", "@router.patch", "@router.delete"):
        assert verb not in source


def test_snapshot_accepts_v1_v2_v3() -> None:
    assert SUPPORTED_ORGANIZATION_SNAPSHOT_SCHEMAS == (
        ORGANIZATION_SNAPSHOT_SCHEMA_VERSION_V1,
        ORGANIZATION_SNAPSHOT_SCHEMA_VERSION_V2,
        ORGANIZATION_SNAPSHOT_SCHEMA_VERSION,
    )
    assert ORGANIZATION_SNAPSHOT_SCHEMA_VERSION == "organization-snapshot-v3"


def test_no_v57_runner_schema_exists() -> None:
    assert "runner-config-v57" not in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    assert "runner-config-v56" in SUPPORTED_RUNNER_SCHEMA_VERSIONS


def test_v4_registry_is_unchanged() -> None:
    assert V4_CONTEXT_MAP_VERSION == "v4-context-map-v2"
    assert len(V4_CONTEXTS) == 14
    assert len(V4_CAPABILITY_FLAGS) == 12
    assert V4ContextId.ORGANIZATIONS in {context.context_id for context in V4_CONTEXTS}


def test_published_operation_ids_match_the_owner_side_grammar() -> None:
    from agents.cognition import organization_publication_operation_id as owner_side
    from simulation.organization_models import (
        organization_publication_operation_id as published_side,
    )

    arguments = (f"org-{'a' * 16}", "storage", 7, 2, "d" * 64)
    assert owner_side(*arguments) == published_side(*arguments)
    assert published_side(*arguments).startswith("orgop-")
