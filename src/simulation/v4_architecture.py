"""Machine-readable V4 bounded-context registry.

Scaffolding only. This module declares context identifiers, authority, owning
packages, prerequisites, and non-goals. It creates no behavior, no command, no
event, no observer semantic type, no metric family, and no world seam.

Validation codes are stable strings so later plans and tests can assert on them
without parsing messages:

- ``v4_context_count`` — not exactly thirteen contexts
- ``v4_context_duplicate`` — duplicate context id
- ``v4_context_flag_duplicate`` — two contexts share one capability flag
- ``v4_context_unknown_owner`` — empty or unknown owning package
- ``v4_context_analysis_authority`` — analysis rules violated
- ``v4_context_analysis_flag`` — analysis-only context carries a flag
- ``v4_context_world_authority`` — ``world`` ownership disagrees with authority
- ``v4_context_config_seam`` — config seam does not match the flag
- ``v4_context_unknown_prerequisite`` — prerequisite names an unknown context
- ``v4_context_prerequisite_cycle`` — self-reference or prerequisite cycle
- ``v4_context_missing_non_goals`` — a context declares no non-goals
- ``v4_context_reserved_flag`` — a flag reuses a reserved V3 name
- ``v4_context_unknown_flag`` — lookup by an unknown or analysis-only flag
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final, NoReturn

from simulation.compatibility import (
    V3_CAPABILITY_FLAG_NAMES,
    V4_CAPABILITY_FLAGS_WIRE_KEY,
)

V4_CONTEXT_MAP_VERSION: Final[str] = "v4-context-map-v2"
V4_ANALYSIS_CAPTURE_SEAM: Final[str] = "analysis_capture"

_ALLOWED_OWNER_PACKAGES: Final[frozenset[str]] = frozenset(
    {
        "world",
        "simulation",
        "agents.cognition",
        "memory",
        "social",
        "analysis",
        "experiments",
        "observer",
        "api",
        "persistence",
        "research_runner",
    }
)
_REQUIRED_CONTEXT_COUNT: Final[int] = 14
_RESERVED_V3_FLAGS: Final[frozenset[str]] = frozenset(V3_CAPABILITY_FLAG_NAMES)


class V4ContextId(StrEnum):
    """Closed V4 context vocabulary; values are the documented identifiers."""

    ORGANIZATIONS = "organizations"
    FORMAL_RULES = "formal_rules"
    LEGAL_DISPUTES = "legal_disputes"
    DIPLOMACY = "diplomacy"
    ORGANIZED_CONFLICT = "organized_conflict"
    INFRASTRUCTURE_NETWORKS = "infrastructure_networks"
    SUPPLY_CHAINS = "supply_chains"
    MARKETS_CREDIT = "markets_credit"
    SCIENCE = "science"
    EPIDEMICS = "epidemics"
    ECOLOGICAL_FEEDBACK = "ecological_feedback"
    DISASTERS = "disasters"
    SOCIETAL_RESILIENCE = "societal_resilience"
    MACRO_SOCIETY_IDENTITY = "macro_society_identity"


class V4Authority(StrEnum):
    """Which authority owns a context's state."""

    OBJECTIVE_WORLD = "objective_world"
    OWNER_SCOPED = "owner_scoped"
    DETACHED_ANALYSIS = "detached_analysis"
    PRESENTATION_ONLY = "presentation_only"


@dataclass(frozen=True, slots=True)
class V4ContextSpec:
    """One declared V4 context; declaration is not implementation.

    ``prerequisite_contexts`` declares planning order and dependency intent. It
    is never a runtime gate: a context may run with its prerequisite disabled and
    then leaves dependent anchors unresolved (for example ``diplomacy`` without
    ``organizations`` leaves organization/coalition party anchors unresolved).
    """

    context_id: V4ContextId
    capability_flag: str | None
    authority: V4Authority
    owner_packages: tuple[str, ...]
    existing_mechanism: str
    required_config_seam: str
    uses_existing_events: bool
    prerequisite_contexts: tuple[V4ContextId, ...]
    non_goals: tuple[str, ...]


V4_CONTEXTS: Final[tuple[V4ContextSpec, ...]] = (
    V4ContextSpec(
        context_id=V4ContextId.ORGANIZATIONS,
        capability_flag="organizations",
        authority=V4Authority.OWNER_SCOPED,
        owner_packages=("agents.cognition", "social", "simulation"),
        existing_mechanism=(
            "collective_projects, public_goods, mentorship, institution_concepts, "
            "offices, institutional_memory, collective_decisions, "
            "structured_commitments, group_formation"
        ),
        required_config_seam="v4_capability_flags.organizations",
        uses_existing_events=True,
        prerequisite_contexts=(),
        non_goals=(
            "no global organization actor or registry",
            "no automatic resource pool or treasury",
        ),
    ),
    V4ContextSpec(
        context_id=V4ContextId.FORMAL_RULES,
        capability_flag="formal_rules",
        authority=V4Authority.OWNER_SCOPED,
        owner_packages=("agents.cognition", "simulation"),
        existing_mechanism="norms, conventions, durable records",
        required_config_seam="v4_capability_flags.formal_rules",
        uses_existing_events=True,
        prerequisite_contexts=(),
        non_goals=(
            "no world-law object",
            "no automatic sanction or policy engine",
        ),
    ),
    V4ContextSpec(
        context_id=V4ContextId.LEGAL_DISPUTES,
        capability_flag="legal_disputes",
        authority=V4Authority.OWNER_SCOPED,
        owner_packages=("agents.cognition", "simulation"),
        existing_mechanism="mediation",
        required_config_seam="v4_capability_flags.legal_disputes",
        uses_existing_events=True,
        prerequisite_contexts=(V4ContextId.FORMAL_RULES,),
        non_goals=(
            "no court, verdict, or binding settlement",
            "no global dispute registry or forced transfer",
        ),
    ),
    V4ContextSpec(
        context_id=V4ContextId.DIPLOMACY,
        capability_flag="diplomacy",
        authority=V4Authority.OWNER_SCOPED,
        owner_packages=("agents.cognition", "social", "simulation"),
        existing_mechanism="cultural_contact, regions_migration, commitments",
        required_config_seam="v4_capability_flags.diplomacy",
        uses_existing_events=True,
        prerequisite_contexts=(V4ContextId.ORGANIZATIONS,),
        non_goals=(
            "no polity, border, or citizenship object",
            "no treaty store or treaty authority",
        ),
    ),
    V4ContextSpec(
        context_id=V4ContextId.ORGANIZED_CONFLICT,
        capability_flag="organized_conflict",
        authority=V4Authority.OBJECTIVE_WORLD,
        owner_packages=("world", "simulation", "agents.cognition"),
        existing_mechanism="physical harm and attack commands",
        required_config_seam="v4_capability_flags.organized_conflict",
        uses_existing_events=True,
        prerequisite_contexts=(V4ContextId.DIPLOMACY,),
        non_goals=(
            "no war state or conflict registry",
            "no army actor or automatic command hierarchy",
        ),
    ),
    V4ContextSpec(
        context_id=V4ContextId.INFRASTRUCTURE_NETWORKS,
        capability_flag="infrastructure_networks",
        authority=V4Authority.OBJECTIVE_WORLD,
        owner_packages=("world", "simulation"),
        existing_mechanism="new physical network graph",
        required_config_seam="v4_capability_flags.infrastructure_networks",
        uses_existing_events=False,
        prerequisite_contexts=(),
        non_goals=(
            "no abstract grid authority or planner",
            "no automatic maintenance policy",
        ),
    ),
    V4ContextSpec(
        context_id=V4ContextId.SUPPLY_CHAINS,
        capability_flag="supply_chains",
        authority=V4Authority.OBJECTIVE_WORLD,
        owner_packages=("world", "simulation"),
        existing_mechanism="production, storage, transport",
        required_config_seam="v4_capability_flags.supply_chains",
        uses_existing_events=True,
        prerequisite_contexts=(V4ContextId.INFRASTRUCTURE_NETWORKS,),
        non_goals=(
            "no central planner or quota",
            "no automatic allocation of items",
        ),
    ),
    V4ContextSpec(
        context_id=V4ContextId.MARKETS_CREDIT,
        capability_flag="markets_credit",
        authority=V4Authority.OWNER_SCOPED,
        owner_packages=("agents.cognition", "simulation"),
        existing_mechanism="resource_exchange_profile, commitments",
        required_config_seam="v4_capability_flags.markets_credit",
        uses_existing_events=True,
        prerequisite_contexts=(
            V4ContextId.SUPPLY_CHAINS,
            V4ContextId.ORGANIZATIONS,
        ),
        non_goals=(
            "no money object, price index, or ledger authority",
            "no central bank or enforced debt",
        ),
    ),
    V4ContextSpec(
        context_id=V4ContextId.SCIENCE,
        capability_flag="science",
        authority=V4Authority.OWNER_SCOPED,
        owner_packages=("agents.cognition", "simulation"),
        existing_mechanism=(
            "experimentation, practical knowledge, knowledge repositories"
        ),
        required_config_seam="v4_capability_flags.science",
        uses_existing_events=True,
        prerequisite_contexts=(V4ContextId.FORMAL_RULES,),
        non_goals=(
            "no objective truth registry or global encyclopedia",
            "no automatic discovery or scripted technology tree",
        ),
    ),
    V4ContextSpec(
        context_id=V4ContextId.EPIDEMICS,
        capability_flag="epidemics",
        authority=V4Authority.OBJECTIVE_WORLD,
        owner_packages=("world", "simulation", "agents.cognition"),
        existing_mechanism="new host and transmission state",
        required_config_seam="v4_capability_flags.epidemics",
        uses_existing_events=False,
        prerequisite_contexts=(V4ContextId.INFRASTRUCTURE_NETWORKS,),
        non_goals=(
            "no disease actor or outbreak registry",
            "no knowledge of infection outside perception and records",
        ),
    ),
    V4ContextSpec(
        context_id=V4ContextId.ECOLOGICAL_FEEDBACK,
        capability_flag="ecological_feedback",
        authority=V4Authority.OBJECTIVE_WORLD,
        owner_packages=("world", "simulation"),
        existing_mechanism="resource regeneration and depletion",
        required_config_seam="v4_capability_flags.ecological_feedback",
        uses_existing_events=False,
        prerequisite_contexts=(V4ContextId.SUPPLY_CHAINS,),
        non_goals=(
            "no ecological actor",
            "no automatic carrying-capacity policy",
        ),
    ),
    V4ContextSpec(
        context_id=V4ContextId.DISASTERS,
        capability_flag="disasters",
        authority=V4Authority.OBJECTIVE_WORLD,
        owner_packages=("world", "simulation"),
        existing_mechanism="environmental hazards",
        required_config_seam="v4_capability_flags.disasters",
        uses_existing_events=False,
        prerequisite_contexts=(V4ContextId.ECOLOGICAL_FEEDBACK,),
        non_goals=(
            "no disaster actor or scripted catastrophe",
            "no narrative event injection from analysis",
        ),
    ),
    V4ContextSpec(
        context_id=V4ContextId.SOCIETAL_RESILIENCE,
        capability_flag=None,
        authority=V4Authority.DETACHED_ANALYSIS,
        owner_packages=("analysis",),
        existing_mechanism="new detached classification",
        required_config_seam=V4_ANALYSIS_CAPTURE_SEAM,
        uses_existing_events=True,
        prerequisite_contexts=(),
        non_goals=(
            "no feedback into cognition, memory, prompts, or admission",
            "no mutable world seam or collapse-triggered world effect",
        ),
    ),
    V4ContextSpec(
        context_id=V4ContextId.MACRO_SOCIETY_IDENTITY,
        capability_flag=None,
        authority=V4Authority.DETACHED_ANALYSIS,
        owner_packages=("analysis",),
        existing_mechanism=(
            "candidate-community analysis, cultural/institutional evidence joins, "
            "group persistence"
        ),
        required_config_seam=V4_ANALYSIS_CAPTURE_SEAM,
        uses_existing_events=True,
        prerequisite_contexts=(),
        non_goals=(
            "no objective nation, state, polity, or civilization entity",
            "no global society registry or WorldEngine identity",
            "no exclusive partition of persons or forced single membership",
            "no feedback into cognition, memory, prompts, admission, or stop selectors",
        ),
    ),
)

V4_CONTEXT_BY_ID: Final[Mapping[V4ContextId, V4ContextSpec]] = MappingProxyType(
    {spec.context_id: spec for spec in V4_CONTEXTS}
)

V4_ANALYSIS_ONLY_CONTEXTS: Final[frozenset[V4ContextId]] = frozenset(
    {V4ContextId.SOCIETAL_RESILIENCE, V4ContextId.MACRO_SOCIETY_IDENTITY}
)

V4_CAPABILITY_FLAGS: Final[tuple[str, ...]] = tuple(
    spec.capability_flag for spec in V4_CONTEXTS if spec.capability_flag is not None
)


def _fail(code: str) -> NoReturn:
    raise ValueError(code)


def _require_acyclic(contexts: Sequence[V4ContextSpec]) -> None:
    known = {spec.context_id for spec in contexts}
    edges = {spec.context_id: spec.prerequisite_contexts for spec in contexts}
    for context_id, prerequisites in edges.items():
        for prerequisite in prerequisites:
            if prerequisite not in known:
                _fail("v4_context_unknown_prerequisite")
            if prerequisite == context_id:
                _fail("v4_context_prerequisite_cycle")

    visiting: set[V4ContextId] = set()
    settled: set[V4ContextId] = set()

    def visit(node: V4ContextId) -> None:
        if node in settled:
            return
        if node in visiting:
            _fail("v4_context_prerequisite_cycle")
        visiting.add(node)
        for prerequisite in edges.get(node, ()):
            visit(prerequisite)
        visiting.discard(node)
        settled.add(node)

    for context_id in edges:
        visit(context_id)


def validate_v4_contexts(
    contexts: Sequence[V4ContextSpec] = V4_CONTEXTS,
) -> None:
    """Validate the registry, or a candidate copy, with stable error codes."""
    if len(contexts) != _REQUIRED_CONTEXT_COUNT:
        _fail("v4_context_count")

    context_ids = [spec.context_id for spec in contexts]
    if len(set(context_ids)) != len(context_ids):
        _fail("v4_context_duplicate")

    flags = [
        spec.capability_flag for spec in contexts if spec.capability_flag is not None
    ]
    if len(set(flags)) != len(flags):
        _fail("v4_context_flag_duplicate")

    for spec in contexts:
        if not spec.owner_packages:
            _fail("v4_context_unknown_owner")
        if not set(spec.owner_packages) <= _ALLOWED_OWNER_PACKAGES:
            _fail("v4_context_unknown_owner")

        is_analysis = spec.authority is V4Authority.DETACHED_ANALYSIS
        if is_analysis:
            if spec.context_id not in V4_ANALYSIS_ONLY_CONTEXTS:
                _fail("v4_context_analysis_authority")
            if spec.owner_packages != ("analysis",):
                _fail("v4_context_analysis_authority")
            if spec.capability_flag is not None:
                _fail("v4_context_analysis_flag")
        elif "analysis" in spec.owner_packages:
            _fail("v4_context_analysis_authority")

        owns_world = "world" in spec.owner_packages
        if owns_world != (spec.authority is V4Authority.OBJECTIVE_WORLD):
            _fail("v4_context_world_authority")

        if spec.capability_flag is None:
            expected_seam = V4_ANALYSIS_CAPTURE_SEAM
        else:
            expected_seam = f"{V4_CAPABILITY_FLAGS_WIRE_KEY}.{spec.capability_flag}"
            if spec.capability_flag in _RESERVED_V3_FLAGS:
                _fail("v4_context_reserved_flag")
        if spec.required_config_seam != expected_seam:
            _fail("v4_context_config_seam")

        if not spec.non_goals:
            _fail("v4_context_missing_non_goals")

    _require_acyclic(contexts)


def v4_context_for_flag(flag: str) -> V4ContextSpec:
    """Return the context that declares ``flag``; analysis-only has no flag."""
    for spec in V4_CONTEXTS:
        if spec.capability_flag == flag:
            return spec
    raise ValueError("v4_context_unknown_flag")


def v4_owner_packages() -> frozenset[str]:
    """Every package named as an owner by the registry."""
    return frozenset(package for spec in V4_CONTEXTS for package in spec.owner_packages)


__all__ = [
    "V4_ANALYSIS_CAPTURE_SEAM",
    "V4_ANALYSIS_ONLY_CONTEXTS",
    "V4_CAPABILITY_FLAGS",
    "V4_CONTEXTS",
    "V4_CONTEXT_BY_ID",
    "V4_CONTEXT_MAP_VERSION",
    "V4Authority",
    "V4ContextId",
    "V4ContextSpec",
    "v4_context_for_flag",
    "v4_owner_packages",
    "validate_v4_contexts",
]
