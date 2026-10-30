"""V4 context registry: authority, doc parity, and dependency invariants."""

from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path

import pytest

from simulation.v4_architecture import (
    V4_ANALYSIS_CAPTURE_SEAM,
    V4_ANALYSIS_ONLY_CONTEXTS,
    V4_CAPABILITY_FLAGS,
    V4_CONTEXT_BY_ID,
    V4_CONTEXT_MAP_VERSION,
    V4_CONTEXTS,
    V4Authority,
    V4ContextId,
    V4ContextSpec,
    v4_context_for_flag,
    v4_owner_packages,
    validate_v4_contexts,
)

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "v4-architecture.md"
REGISTRY_MODULE = ROOT / "src" / "simulation" / "v4_architecture.py"

DECLARED_ORDER = (
    V4ContextId.ORGANIZATIONS,
    V4ContextId.FORMAL_RULES,
    V4ContextId.LEGAL_DISPUTES,
    V4ContextId.DIPLOMACY,
    V4ContextId.ORGANIZED_CONFLICT,
    V4ContextId.INFRASTRUCTURE_NETWORKS,
    V4ContextId.SUPPLY_CHAINS,
    V4ContextId.MARKETS_CREDIT,
    V4ContextId.SCIENCE,
    V4ContextId.EPIDEMICS,
    V4ContextId.ECOLOGICAL_FEEDBACK,
    V4ContextId.DISASTERS,
    V4ContextId.SOCIETAL_RESILIENCE,
)

DECLARED_PREREQUISITES = {
    V4ContextId.ORGANIZATIONS: frozenset(),
    V4ContextId.FORMAL_RULES: frozenset(),
    V4ContextId.LEGAL_DISPUTES: frozenset({V4ContextId.FORMAL_RULES}),
    V4ContextId.DIPLOMACY: frozenset({V4ContextId.ORGANIZATIONS}),
    V4ContextId.ORGANIZED_CONFLICT: frozenset({V4ContextId.DIPLOMACY}),
    V4ContextId.INFRASTRUCTURE_NETWORKS: frozenset(),
    V4ContextId.SUPPLY_CHAINS: frozenset({V4ContextId.INFRASTRUCTURE_NETWORKS}),
    V4ContextId.MARKETS_CREDIT: frozenset(
        {V4ContextId.SUPPLY_CHAINS, V4ContextId.ORGANIZATIONS}
    ),
    V4ContextId.SCIENCE: frozenset({V4ContextId.FORMAL_RULES}),
    V4ContextId.EPIDEMICS: frozenset({V4ContextId.INFRASTRUCTURE_NETWORKS}),
    V4ContextId.ECOLOGICAL_FEEDBACK: frozenset({V4ContextId.SUPPLY_CHAINS}),
    V4ContextId.DISASTERS: frozenset({V4ContextId.ECOLOGICAL_FEEDBACK}),
    V4ContextId.SOCIETAL_RESILIENCE: frozenset(),
}

REQUIRED_SECTIONS = (
    "## Status and scope",
    "## Authority model",
    "## Context map",
    "## Cross-context contracts",
    "## Scale model",
    "## Version surfaces",
    "## Compatibility and deprecation policy",
    "## Migration posture",
    "## Presentation policy",
    "## Non-goals",
    "## Downstream V4 plan checklist",
)

FORBIDDEN_REGISTRY_IMPORTS = (
    "experiments",
    "analysis",
    "api",
    "persistence",
    "infrastructure",
    "observer",
)


def _candidate(target: V4ContextId, **changes: object) -> tuple[V4ContextSpec, ...]:
    """Return the registry with ``target`` replaced by an invalid variant."""
    return tuple(
        replace(spec, **changes) if spec.context_id is target else spec
        for spec in V4_CONTEXTS
    )


def test_registry_validates_and_declares_thirteen_contexts() -> None:
    validate_v4_contexts()
    assert V4_CONTEXT_MAP_VERSION == "v4-context-map-v1"
    assert len(V4_CONTEXTS) == 13
    assert len(V4_CAPABILITY_FLAGS) == 12
    assert len(set(V4_CAPABILITY_FLAGS)) == 12
    assert tuple(spec.context_id for spec in V4_CONTEXTS) == DECLARED_ORDER
    assert set(V4_CONTEXT_BY_ID) == set(DECLARED_ORDER)


def test_only_resilience_is_analysis_only_and_carries_no_flag() -> None:
    assert V4_ANALYSIS_ONLY_CONTEXTS == frozenset({V4ContextId.SOCIETAL_RESILIENCE})
    spec = V4_CONTEXT_BY_ID[V4ContextId.SOCIETAL_RESILIENCE]
    assert spec.authority is V4Authority.DETACHED_ANALYSIS
    assert spec.capability_flag is None
    assert spec.owner_packages == ("analysis",)
    assert spec.required_config_seam == V4_ANALYSIS_CAPTURE_SEAM

    with pytest.raises(ValueError, match="v4_context_unknown_flag"):
        v4_context_for_flag("societal_resilience")
    with pytest.raises(ValueError, match="v4_context_unknown_flag"):
        v4_context_for_flag("not_a_v4_context")


def test_prerequisite_edges_match_the_declared_map() -> None:
    declared = {
        spec.context_id: frozenset(spec.prerequisite_contexts) for spec in V4_CONTEXTS
    }
    assert declared == DECLARED_PREREQUISITES


def test_every_flagged_context_seam_matches_its_flag() -> None:
    for spec in V4_CONTEXTS:
        if spec.capability_flag is None:
            assert spec.required_config_seam == V4_ANALYSIS_CAPTURE_SEAM
        else:
            assert (
                spec.required_config_seam
                == f"v4_capability_flags.{spec.capability_flag}"
            )
            assert v4_context_for_flag(spec.capability_flag) is spec


def test_world_ownership_requires_objective_world_authority() -> None:
    for spec in V4_CONTEXTS:
        owns_world = "world" in spec.owner_packages
        assert owns_world == (spec.authority is V4Authority.OBJECTIVE_WORLD), spec


def test_owner_packages_are_existing_bounded_packages() -> None:
    assert v4_owner_packages() == frozenset(
        {
            "world",
            "simulation",
            "agents.cognition",
            "social",
            "analysis",
        }
    )


def test_document_declares_every_context_and_required_section() -> None:
    text = DOC.read_text(encoding="utf-8")
    for context_id in DECLARED_ORDER:
        assert context_id.value in text, context_id
        assert f"### {context_id.value}" in text, context_id
    for section in REQUIRED_SECTIONS:
        assert section in text, section
    assert text.count("\n### ") == 13


def test_registry_module_imports_only_the_core_packages() -> None:
    tree = ast.parse(REGISTRY_MODULE.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            roots.add(node.module.split(".", 1)[0])
        elif isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
    assert roots & set(FORBIDDEN_REGISTRY_IMPORTS) == set()


def test_duplicate_context_id_is_rejected() -> None:
    candidate = _candidate(
        V4ContextId.ORGANIZATIONS, context_id=V4ContextId.FORMAL_RULES
    )
    with pytest.raises(ValueError, match="v4_context_duplicate"):
        validate_v4_contexts(candidate)


def test_duplicate_flag_is_rejected() -> None:
    candidate = _candidate(V4ContextId.ORGANIZATIONS, capability_flag="formal_rules")
    with pytest.raises(ValueError, match="v4_context_flag_duplicate"):
        validate_v4_contexts(candidate)


def test_unknown_owner_package_is_rejected() -> None:
    candidate = _candidate(
        V4ContextId.ORGANIZATIONS, owner_packages=("agents.cognition", "not_a_package")
    )
    with pytest.raises(ValueError, match="v4_context_unknown_owner"):
        validate_v4_contexts(candidate)


def test_owner_scoped_context_with_world_is_rejected() -> None:
    candidate = _candidate(
        V4ContextId.ORGANIZATIONS, owner_packages=("world", "agents.cognition")
    )
    with pytest.raises(ValueError, match="v4_context_world_authority"):
        validate_v4_contexts(candidate)


def test_analysis_context_with_world_is_rejected() -> None:
    candidate = _candidate(
        V4ContextId.SOCIETAL_RESILIENCE,
        owner_packages=("world", "analysis"),
    )
    with pytest.raises(ValueError, match="v4_context_analysis_authority"):
        validate_v4_contexts(candidate)


def test_analysis_context_with_flag_is_rejected() -> None:
    candidate = _candidate(
        V4ContextId.SOCIETAL_RESILIENCE,
        capability_flag="societal_resilience",
        required_config_seam="v4_capability_flags.societal_resilience",
    )
    with pytest.raises(ValueError, match="v4_context_analysis_flag"):
        validate_v4_contexts(candidate)


def test_prerequisite_cycle_is_rejected() -> None:
    candidate = _candidate(
        V4ContextId.ORGANIZATIONS, prerequisite_contexts=(V4ContextId.ORGANIZATIONS,)
    )
    with pytest.raises(ValueError, match="v4_context_prerequisite_cycle"):
        validate_v4_contexts(candidate)

    candidate = _candidate(
        V4ContextId.FORMAL_RULES,
        prerequisite_contexts=(V4ContextId.LEGAL_DISPUTES,),
    )
    with pytest.raises(ValueError, match="v4_context_prerequisite_cycle"):
        validate_v4_contexts(candidate)


def test_missing_non_goals_and_reserved_flag_are_rejected() -> None:
    with pytest.raises(ValueError, match="v4_context_missing_non_goals"):
        validate_v4_contexts(_candidate(V4ContextId.ORGANIZATIONS, non_goals=()))

    with pytest.raises(ValueError, match="v4_context_reserved_flag"):
        validate_v4_contexts(
            _candidate(
                V4ContextId.ORGANIZATIONS,
                capability_flag="generational_population",
                required_config_seam="v4_capability_flags.generational_population",
            )
        )


def test_context_count_is_enforced() -> None:
    with pytest.raises(ValueError, match="v4_context_count"):
        validate_v4_contexts(V4_CONTEXTS[:-1])
