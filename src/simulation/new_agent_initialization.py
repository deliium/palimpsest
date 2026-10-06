"""Closed NewAgentInitialization contracts for mid-run blank-slate bootstrap.

Pure domain types plus species-defaults / seeded-draw helpers. WorldEngine owns
objective admission; the runner owns post-admit blank subjective bind.
Never log distribution payloads, observations, or memory contents.
"""

from __future__ import annotations

import hashlib
import json
import logging
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from agents.models import AgentId, DriveKind, DriveProfile
from simulation.models import SimulationRunConfig
from simulation.randomness import StreamScope, create_named_stream
from simulation.runner_models import (
    AgentCognitionSpec,
    ArtifactInterpretationMode,
    CulturalNarrativeMode,
    DriveOverrideSpec,
    SemanticNamingMode,
    SkillLearningMode,
    SocialConventionMode,
    SocialNormMode,
    TeachingInteractionMode,
)
from world.identifiers import EntityId, require_stable_id

__all__ = [
    "ALLOWED_OBJECTIVE_INHERITANCE_KEYS",
    "BLANK_SLATE_SUBJECTIVE_STORES",
    "CREATION_REASON_CODES",
    "NEW_AGENT_INITIALIZATION_KEYS",
    "SPECIES_DEFAULT_DEVELOPMENTAL_V1",
    "SPECIES_DEFAULT_V1",
    "SUBJECTIVE_COPY_DENY_LIST",
    "BlankSlateStoreCounts",
    "CreationProvenance",
    "CreationReasonCode",
    "DependencyBindingPolicy",
    "InnateDrivePolicy",
    "NewAgentInitializationSpec",
    "ObjectiveInheritancePolicy",
    "OriginRef",
    "ParameterDistributionSpec",
    "ParameterDrawResult",
    "PhysicalConditionPolicy",
    "ProvenancePolicy",
    "SpawnLocationPolicy",
    "SpeciesDefaultsPack",
    "apply_drive_delta_to_overrides",
    "assert_blank_slate_subjective_state",
    "creation_config_fingerprint",
    "default_new_agent_initialization_spec",
    "draw_parameter_distribution",
    "new_agent_init_stream",
    "resolve_spawn_location",
    "species_defaults_for",
]

_LOG = logging.getLogger("simulation.new_agent_initialization")

SPECIES_DEFAULT_V1: Final[str] = "species_default_v1"
SPECIES_DEFAULT_DEVELOPMENTAL_V1: Final[str] = "species_default_developmental_v1"

_NEW_AGENT_INIT_KEYS: Final[frozenset[str]] = frozenset(
    {
        "species_defaults_id",
        "parameter_distributions",
        "innate_drive_policy",
        "physical_condition_policy",
        "spawn_location_policy",
        "dependency_binding",
        "objective_inheritance",
        "creation_reason_policy",
        "provenance_policy",
    }
)

_DISTRIBUTION_PARAM_KEYS: Final[Mapping[str, frozenset[str]]] = {
    "none": frozenset(),
    "uniform_drive_delta": frozenset({"drive_kind", "min_delta", "max_delta"}),
}

ALLOWED_OBJECTIVE_INHERITANCE_KEYS: Final[frozenset[str]] = frozenset(
    {"carry_capacity"}
)

# Forbidden subjective / cultural / kinship-shaped names (deny-list + inheritance).
SUBJECTIVE_COPY_DENY_LIST: Final[frozenset[str]] = frozenset(
    {
        "episodic_memory",
        "memory_service",
        "semantic_beliefs",
        "belief_history",
        "self_model",
        "extended_identity",
        "theory_of_mind",
        "social_inference",
        "goals",
        "goal_board",
        "initial_goals",
        "cultural_narratives",
        "narrative_ledger",
        "cognition_trace",
        "relationships",
        "relationship_profiles",
        "semantic_naming",
        "naming_ledger",
        "social_norms",
        "social_conventions",
        "skill_ledger",
        "skill_learning",
        "map_knowledge",
        "language_pack",
        "history_dump",
        "parent_id",
        "parent_ids",
        "kinship",
        "child_id",
        "child_ids",
        "developmental_knowledge",
        "society_download",
        "culture_pack",
        "encyclopedia",
    }
)

BLANK_SLATE_SUBJECTIVE_STORES: Final[tuple[str, ...]] = (
    "episodic_memory",
    "semantic_beliefs",
    "self_model",
    "theory_of_mind",
    "goals",
    "cultural_narratives",
    "cognition_trace",
    "relationships",
    "semantic_naming",
    "social_norms",
    "social_conventions",
    "skill_ledger",
    "developmental_knowledge",
)

CREATION_REASON_CODES: Final[frozenset[str]] = frozenset(
    {
        "demographic_policy",
        "external_entry",
        "experiment_inject",
    }
)

_KINSHIP_ORIGIN_ROLES: Final[frozenset[str]] = frozenset(
    {
        "parent",
        "mother",
        "father",
        "child",
        "sibling",
        "kin",
        "spouse",
        "mate",
    }
)

_PHYSICAL_POLICY_PARAM_KEYS: Final[Mapping[str, frozenset[str]]] = {
    "default_entrant": frozenset(),
}

_SPAWN_POLICY_PARAM_KEYS: Final[Mapping[str, frozenset[str]]] = {
    "defer_to_candidate": frozenset(),
    "fixed": frozenset({"location_id"}),
    "seeded_allowlist": frozenset({"location_ids"}),
    "allowlist": frozenset({"location_ids"}),
}

_INNATE_DRIVE_PARAM_KEYS: Final[Mapping[str, frozenset[str]]] = {
    "species_baseline": frozenset(),
}

_PROVENANCE_POLICY_KEYS: Final[frozenset[str]] = frozenset(
    {"record_origin_refs", "allowed_roles"}
)

_KNOWN_SPECIES_DEFAULT_IDS: Final[frozenset[str]] = frozenset(
    {SPECIES_DEFAULT_V1, SPECIES_DEFAULT_DEVELOPMENTAL_V1}
)


class CreationReasonCode(StrEnum):
    """Closed creation-reason identifiers for provenance."""

    DEMOGRAPHIC_POLICY = "demographic_policy"
    EXTERNAL_ENTRY = "external_entry"
    EXPERIMENT_INJECT = "experiment_inject"


def _unit_interval(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name}: not_unit_interval")
    number = float(value)
    if number < 0.0 or number > 1.0:
        raise ValueError(f"{name}: not_unit_interval")
    return number


def _exact_delta(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    number = float(value)
    if number != number:  # NaN
        raise ValueError(f"{name} must be a finite number")
    return number


def _require_exact_keys(
    *,
    path: str,
    actual: frozenset[str],
    expected: frozenset[str],
    code: str,
) -> None:
    if actual != expected:
        raise ValueError(
            f"{path} exact key set mismatch expected={sorted(expected)!r} "
            f"actual={sorted(actual)!r} (code={code})"
        )


def _freeze_str_mapping(
    path: str, value: Mapping[str, object]
) -> Mapping[str, object]:
    frozen: dict[str, object] = {}
    for key, item in value.items():
        if type(key) is not str:
            raise TypeError(f"{path} keys must be str")
        frozen[key] = item
    return MappingProxyType(frozen)


@dataclass(frozen=True, slots=True)
class OriginRef:
    """Experimental origin label (ids + role only — not a kinship edge)."""

    role: str
    agent_id: str | None = None
    body_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "role", require_stable_id("OriginRef.role", self.role))
        if self.role in _KINSHIP_ORIGIN_ROLES:
            raise ValueError(
                f"OriginRef.role forbids kinship-shaped role {self.role!r} "
                "(code=origin_ref_kinship_forbidden)"
            )
        if self.agent_id is None and self.body_id is None:
            raise ValueError(
                "OriginRef requires agent_id or body_id "
                "(code=origin_ref_identity_required)"
            )
        if self.agent_id is not None:
            object.__setattr__(
                self,
                "agent_id",
                require_stable_id("OriginRef.agent_id", self.agent_id),
            )
        if self.body_id is not None:
            object.__setattr__(
                self,
                "body_id",
                require_stable_id("OriginRef.body_id", self.body_id),
            )

    def canonical_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {"role": self.role}
        if self.agent_id is not None:
            payload["agent_id"] = self.agent_id
        if self.body_id is not None:
            payload["body_id"] = self.body_id
        return payload


@dataclass(frozen=True, slots=True)
class CreationProvenance:
    """Why a mid-run agent was created (origin refs optional, not kinship)."""

    creation_reason: CreationReasonCode
    origin_refs: tuple[OriginRef, ...] = ()
    creation_config_id: str | None = None

    def __post_init__(self) -> None:
        if type(self.creation_reason) is not CreationReasonCode:
            raise TypeError("creation_reason must be CreationReasonCode")
        if isinstance(self.origin_refs, (str, bytes)) or not isinstance(
            self.origin_refs, Sequence
        ):
            raise TypeError("origin_refs must be a sequence")
        refs = tuple(self.origin_refs)
        for ref in refs:
            if type(ref) is not OriginRef:
                raise TypeError("origin_refs entries must be OriginRef")
        object.__setattr__(self, "origin_refs", refs)
        if self.creation_config_id is not None:
            object.__setattr__(
                self,
                "creation_config_id",
                require_stable_id(
                    "CreationProvenance.creation_config_id",
                    self.creation_config_id,
                ),
            )


@dataclass(frozen=True, slots=True)
class ParameterDistributionSpec:
    """Exact distribution id + param key set for seeded innate draws."""

    distribution_id: str
    params: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "distribution_id",
            require_stable_id(
                "ParameterDistributionSpec.distribution_id", self.distribution_id
            ),
        )
        if self.distribution_id not in _DISTRIBUTION_PARAM_KEYS:
            raise ValueError(
                f"unknown distribution_id {self.distribution_id!r} "
                "(code=unknown_parameter_distribution_id)"
            )
        if isinstance(self.params, (str, bytes)) or not isinstance(
            self.params, Mapping
        ):
            raise TypeError("params must be a mapping")
        expected = _DISTRIBUTION_PARAM_KEYS[self.distribution_id]
        actual = frozenset(self.params.keys())
        forbidden = actual & SUBJECTIVE_COPY_DENY_LIST
        if forbidden:
            raise ValueError(
                f"parameter_distributions forbid subjective keys "
                f"{sorted(forbidden)!r} (code=subjective_copy_forbidden)"
            )
        _require_exact_keys(
            path="parameter_distributions.params",
            actual=actual,
            expected=expected,
            code="parameter_distribution_params_key_set",
        )
        frozen = dict(
            _freeze_str_mapping("parameter_distributions.params", self.params)
        )
        if self.distribution_id == "uniform_drive_delta":
            drive_raw = frozen["drive_kind"]
            if type(drive_raw) is not str:
                raise TypeError("params.drive_kind must be str")
            try:
                DriveKind(drive_raw)
            except ValueError as exc:
                raise ValueError(
                    f"unknown drive_kind {drive_raw!r} "
                    "(code=unknown_drive_kind)"
                ) from exc
            frozen["drive_kind"] = drive_raw
            min_delta = _exact_delta("params.min_delta", frozen["min_delta"])
            max_delta = _exact_delta("params.max_delta", frozen["max_delta"])
            if min_delta > max_delta:
                raise ValueError(
                    "params.min_delta must be <= max_delta "
                    "(code=parameter_distribution_delta_order)"
                )
            # Deltas themselves are unit-interval offsets applied to baseline.
            frozen["min_delta"] = _unit_interval("params.min_delta", min_delta)
            frozen["max_delta"] = _unit_interval("params.max_delta", max_delta)
        object.__setattr__(self, "params", MappingProxyType(frozen))

    def canonical_payload(self) -> dict[str, object]:
        return {
            "distribution_id": self.distribution_id,
            "params": {key: self.params[key] for key in sorted(self.params)},
        }


@dataclass(frozen=True, slots=True)
class InnateDrivePolicy:
    """Limited innate drive baseline policy (never copies another DriveProfile)."""

    policy_id: str
    params: Mapping[str, object] = MappingProxyType({})

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "policy_id",
            require_stable_id("InnateDrivePolicy.policy_id", self.policy_id),
        )
        if self.policy_id not in _INNATE_DRIVE_PARAM_KEYS:
            raise ValueError(
                f"unknown innate_drive_policy {self.policy_id!r} "
                "(code=unknown_innate_drive_policy_id)"
            )
        if isinstance(self.params, (str, bytes)) or not isinstance(
            self.params, Mapping
        ):
            raise TypeError("innate_drive_policy.params must be a mapping")
        expected = _INNATE_DRIVE_PARAM_KEYS[self.policy_id]
        actual = frozenset(self.params.keys())
        _require_exact_keys(
            path="innate_drive_policy.params",
            actual=actual,
            expected=expected,
            code="innate_drive_policy_params_key_set",
        )
        object.__setattr__(
            self,
            "params",
            _freeze_str_mapping("innate_drive_policy.params", self.params),
        )

    def canonical_payload(self) -> dict[str, object]:
        return {
            "policy_id": self.policy_id,
            "params": {key: self.params[key] for key in sorted(self.params)},
        }


@dataclass(frozen=True, slots=True)
class PhysicalConditionPolicy:
    """Objective body physiology policy at mid-run entry."""

    policy_id: str
    params: Mapping[str, object] = MappingProxyType({})

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "policy_id",
            require_stable_id("PhysicalConditionPolicy.policy_id", self.policy_id),
        )
        if self.policy_id not in _PHYSICAL_POLICY_PARAM_KEYS:
            raise ValueError(
                f"unknown physical_condition_policy {self.policy_id!r} "
                "(code=unknown_physical_condition_policy_id)"
            )
        if isinstance(self.params, (str, bytes)) or not isinstance(
            self.params, Mapping
        ):
            raise TypeError("physical_condition_policy.params must be a mapping")
        expected = _PHYSICAL_POLICY_PARAM_KEYS[self.policy_id]
        actual = frozenset(self.params.keys())
        _require_exact_keys(
            path="physical_condition_policy.params",
            actual=actual,
            expected=expected,
            code="physical_condition_policy_params_key_set",
        )
        object.__setattr__(
            self,
            "params",
            _freeze_str_mapping("physical_condition_policy.params", self.params),
        )

    def canonical_payload(self) -> dict[str, object]:
        return {
            "policy_id": self.policy_id,
            "params": {key: self.params[key] for key in sorted(self.params)},
        }


@dataclass(frozen=True, slots=True)
class SpawnLocationPolicy:
    """Spawn location resolution (see plan spawn-location precedence)."""

    policy_id: str
    params: Mapping[str, object] = MappingProxyType({})

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "policy_id",
            require_stable_id("SpawnLocationPolicy.policy_id", self.policy_id),
        )
        if self.policy_id not in _SPAWN_POLICY_PARAM_KEYS:
            raise ValueError(
                f"unknown spawn_location_policy {self.policy_id!r} "
                "(code=unknown_spawn_location_policy_id)"
            )
        if isinstance(self.params, (str, bytes)) or not isinstance(
            self.params, Mapping
        ):
            raise TypeError("spawn_location_policy.params must be a mapping")
        expected = _SPAWN_POLICY_PARAM_KEYS[self.policy_id]
        actual = frozenset(self.params.keys())
        _require_exact_keys(
            path="spawn_location_policy.params",
            actual=actual,
            expected=expected,
            code="spawn_location_policy_params_key_set",
        )
        frozen = dict(_freeze_str_mapping("spawn_location_policy.params", self.params))
        if self.policy_id == "fixed":
            frozen["location_id"] = require_stable_id(
                "spawn_location_policy.params.location_id",
                frozen["location_id"],
            )
        elif self.policy_id in {"seeded_allowlist", "allowlist"}:
            raw_ids = frozen["location_ids"]
            if isinstance(raw_ids, (str, bytes)) or not isinstance(raw_ids, Sequence):
                raise TypeError(
                    "spawn_location_policy.params.location_ids must be a sequence"
                )
            ids = tuple(
                require_stable_id(
                    "spawn_location_policy.params.location_ids[]", item
                )
                for item in raw_ids
            )
            if not ids:
                raise ValueError(
                    "spawn_location_policy.params.location_ids must be non-empty "
                    "(code=spawn_location_allowlist_empty)"
                )
            if len(set(ids)) != len(ids):
                raise ValueError(
                    "spawn_location_policy.params.location_ids must be unique "
                    "(code=spawn_location_allowlist_duplicate)"
                )
            frozen["location_ids"] = ids
        object.__setattr__(self, "params", MappingProxyType(frozen))

    def canonical_payload(self) -> dict[str, object]:
        params: dict[str, object] = {}
        for key in sorted(self.params):
            value = self.params[key]
            if key == "location_ids" and isinstance(value, tuple):
                params[key] = list(value)
            else:
                params[key] = value
        return {"policy_id": self.policy_id, "params": params}

    def allowlist_ids(self) -> frozenset[str] | None:
        """Return allowlist location ids when policy is allowlist-shaped."""
        if self.policy_id in {"seeded_allowlist", "allowlist"}:
            raw = self.params["location_ids"]
            assert isinstance(raw, tuple)
            return frozenset(str(item) for item in raw)
        if self.policy_id == "fixed":
            return frozenset({str(self.params["location_id"])})
        return None


@dataclass(frozen=True, slots=True)
class DependencyBindingPolicy:
    """Lifecycle dependency binding (locked to from_lifecycle_stage)."""

    policy_id: str = "from_lifecycle_stage"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "policy_id",
            require_stable_id("DependencyBindingPolicy.policy_id", self.policy_id),
        )
        if self.policy_id != "from_lifecycle_stage":
            raise ValueError(
                f"unknown dependency_binding {self.policy_id!r} "
                "(code=unknown_dependency_binding_id)"
            )

    def canonical_payload(self) -> dict[str, object]:
        return {"policy_id": self.policy_id}


@dataclass(frozen=True, slots=True)
class ObjectiveInheritancePolicy:
    """Objective-only attribute inheritance allowlist (default empty)."""

    allowed_keys: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if isinstance(self.allowed_keys, (str, bytes)) or not isinstance(
            self.allowed_keys, Sequence
        ):
            raise TypeError("objective_inheritance.allowed_keys must be a sequence")
        keys = tuple(self.allowed_keys)
        for key in keys:
            if type(key) is not str:
                raise TypeError(
                    "objective_inheritance.allowed_keys entries must be str"
                )
            if key in SUBJECTIVE_COPY_DENY_LIST:
                raise ValueError(
                    f"objective_inheritance forbids subjective key {key!r} "
                    "(code=subjective_copy_forbidden)"
                )
            if key not in ALLOWED_OBJECTIVE_INHERITANCE_KEYS:
                raise ValueError(
                    f"objective_inheritance.allowed_keys entry {key!r} not in "
                    f"closed set {sorted(ALLOWED_OBJECTIVE_INHERITANCE_KEYS)!r} "
                    "(code=objective_inheritance_key_forbidden)"
                )
        if len(set(keys)) != len(keys):
            raise ValueError(
                "objective_inheritance.allowed_keys must be unique "
                "(code=objective_inheritance_duplicate_key)"
            )
        object.__setattr__(self, "allowed_keys", keys)

    def canonical_payload(self) -> dict[str, object]:
        return {"allowed_keys": list(self.allowed_keys)}


@dataclass(frozen=True, slots=True)
class ProvenancePolicy:
    """Whether origin refs are recorded (ids + role labels only)."""

    record_origin_refs: bool = False
    allowed_roles: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.record_origin_refs) is not bool:
            raise TypeError("provenance_policy.record_origin_refs must be bool")
        if isinstance(self.allowed_roles, (str, bytes)) or not isinstance(
            self.allowed_roles, Sequence
        ):
            raise TypeError("provenance_policy.allowed_roles must be a sequence")
        roles = tuple(
            require_stable_id("provenance_policy.allowed_roles[]", role)
            for role in self.allowed_roles
        )
        for role in roles:
            if role in _KINSHIP_ORIGIN_ROLES:
                raise ValueError(
                    f"provenance_policy.allowed_roles forbids kinship role "
                    f"{role!r} (code=origin_ref_kinship_forbidden)"
                )
        if len(set(roles)) != len(roles):
            raise ValueError(
                "provenance_policy.allowed_roles must be unique "
                "(code=provenance_allowed_roles_duplicate)"
            )
        object.__setattr__(self, "allowed_roles", roles)

    def canonical_payload(self) -> dict[str, object]:
        return {
            "allowed_roles": list(self.allowed_roles),
            "record_origin_refs": self.record_origin_refs,
        }


@dataclass(frozen=True, slots=True)
class NewAgentInitializationSpec:
    """Closed run-level new-agent initialization (runner-config-v25)."""

    species_defaults_id: str
    parameter_distributions: ParameterDistributionSpec
    innate_drive_policy: InnateDrivePolicy
    physical_condition_policy: PhysicalConditionPolicy
    spawn_location_policy: SpawnLocationPolicy
    dependency_binding: DependencyBindingPolicy
    objective_inheritance: ObjectiveInheritancePolicy
    creation_reason_policy: tuple[str, ...]
    provenance_policy: ProvenancePolicy

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "species_defaults_id",
            require_stable_id(
                "NewAgentInitializationSpec.species_defaults_id",
                self.species_defaults_id,
            ),
        )
        if self.species_defaults_id not in _KNOWN_SPECIES_DEFAULT_IDS:
            raise ValueError(
                f"unknown species_defaults_id {self.species_defaults_id!r} "
                "(code=unknown_species_defaults_id)"
            )
        if type(self.parameter_distributions) is not ParameterDistributionSpec:
            raise TypeError(
                "parameter_distributions must be ParameterDistributionSpec"
            )
        if type(self.innate_drive_policy) is not InnateDrivePolicy:
            raise TypeError("innate_drive_policy must be InnateDrivePolicy")
        if type(self.physical_condition_policy) is not PhysicalConditionPolicy:
            raise TypeError(
                "physical_condition_policy must be PhysicalConditionPolicy"
            )
        if type(self.spawn_location_policy) is not SpawnLocationPolicy:
            raise TypeError("spawn_location_policy must be SpawnLocationPolicy")
        if type(self.dependency_binding) is not DependencyBindingPolicy:
            raise TypeError("dependency_binding must be DependencyBindingPolicy")
        if type(self.objective_inheritance) is not ObjectiveInheritancePolicy:
            raise TypeError(
                "objective_inheritance must be ObjectiveInheritancePolicy"
            )
        if type(self.provenance_policy) is not ProvenancePolicy:
            raise TypeError("provenance_policy must be ProvenancePolicy")
        if isinstance(self.creation_reason_policy, (str, bytes)) or not isinstance(
            self.creation_reason_policy, Sequence
        ):
            raise TypeError("creation_reason_policy must be a sequence")
        reasons = tuple(self.creation_reason_policy)
        if not reasons:
            raise ValueError(
                "creation_reason_policy must be non-empty "
                "(code=creation_reason_policy_empty)"
            )
        for reason in reasons:
            if type(reason) is not str:
                raise TypeError("creation_reason_policy entries must be str")
            if reason not in CREATION_REASON_CODES:
                raise ValueError(
                    f"unknown creation_reason {reason!r} "
                    "(code=unknown_creation_reason_code)"
                )
        if len(set(reasons)) != len(reasons):
            raise ValueError(
                "creation_reason_policy must be unique "
                "(code=creation_reason_policy_duplicate)"
            )
        object.__setattr__(self, "creation_reason_policy", reasons)

    def canonical_payload(self) -> dict[str, object]:
        """Exact wire object for runner-config-v25 ``new_agent_initialization``."""
        return {
            "creation_reason_policy": list(self.creation_reason_policy),
            "dependency_binding": self.dependency_binding.canonical_payload(),
            "innate_drive_policy": self.innate_drive_policy.canonical_payload(),
            "objective_inheritance": self.objective_inheritance.canonical_payload(),
            "parameter_distributions": self.parameter_distributions.canonical_payload(),
            "physical_condition_policy": (
                self.physical_condition_policy.canonical_payload()
            ),
            "provenance_policy": self.provenance_policy.canonical_payload(),
            "spawn_location_policy": self.spawn_location_policy.canonical_payload(),
            "species_defaults_id": self.species_defaults_id,
        }


def creation_config_fingerprint(
    spec: NewAgentInitializationSpec,
    *,
    demographic_policy_id: str | None = None,
) -> str:
    """Stable fingerprint suitable for ``creation_config_id``."""
    if type(spec) is not NewAgentInitializationSpec:
        raise TypeError("spec must be NewAgentInitializationSpec")
    payload: dict[str, object] = {
        "new_agent_initialization": spec.canonical_payload(),
    }
    if demographic_policy_id is not None:
        payload["demographic_policy_id"] = require_stable_id(
            "demographic_policy_id", demographic_policy_id
        )
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    return f"nai-{digest[:32]}"


def default_new_agent_initialization_spec() -> NewAgentInitializationSpec:
    """Closed synthesized default (v1-v24 lifecycle restore / AE green path)."""
    return NewAgentInitializationSpec(
        species_defaults_id=SPECIES_DEFAULT_V1,
        parameter_distributions=ParameterDistributionSpec(
            distribution_id="none", params={}
        ),
        innate_drive_policy=InnateDrivePolicy(policy_id="species_baseline"),
        physical_condition_policy=PhysicalConditionPolicy(policy_id="default_entrant"),
        spawn_location_policy=SpawnLocationPolicy(policy_id="defer_to_candidate"),
        dependency_binding=DependencyBindingPolicy(),
        objective_inheritance=ObjectiveInheritancePolicy(allowed_keys=()),
        creation_reason_policy=(
            CreationReasonCode.DEMOGRAPHIC_POLICY.value,
            CreationReasonCode.EXTERNAL_ENTRY.value,
            CreationReasonCode.EXPERIMENT_INJECT.value,
        ),
        provenance_policy=ProvenancePolicy(
            record_origin_refs=False, allowed_roles=()
        ),
    )


@dataclass(frozen=True, slots=True)
class BlankSlateStoreCounts:
    """Content counts for blank-slate assertion (modes may be enabled)."""

    episodic_memory: int = 0
    semantic_beliefs: int = 0
    self_model: int = 0
    theory_of_mind: int = 0
    goals: int = 0
    cultural_narratives: int = 0
    cognition_trace: int = 0
    relationships: int = 0
    semantic_naming: int = 0
    social_norms: int = 0
    social_conventions: int = 0
    skill_ledger: int = 0
    developmental_knowledge: int = 0


def assert_blank_slate_subjective_state(
    owner: AgentId,
    counts: BlankSlateStoreCounts,
) -> None:
    """Fail closed if any deny-listed subjective store has content for ``owner``.

    Mode-vs-content: learning modes may be enabled; ledger **content** must be
    empty. Never copies another owner's stores.
    """
    if type(owner) is not AgentId:
        raise TypeError("owner must be AgentId")
    if type(counts) is not BlankSlateStoreCounts:
        raise TypeError("counts must be BlankSlateStoreCounts")
    violations: list[str] = []
    for store in BLANK_SLATE_SUBJECTIVE_STORES:
        value = getattr(counts, store)
        if type(value) is not int or value < 0:
            raise TypeError(f"BlankSlateStoreCounts.{store} must be non-neg int")
        if value != 0:
            violations.append(store)
    if violations:
        _LOG.error(
            "blank_slate_violation owner_id=%s reason_code=subjective_copy_forbidden "
            "stores=%s",
            owner.value,
            ",".join(violations),
        )
        raise ValueError(
            "mid-run agent subjective stores must be empty "
            f"owner={owner.value!r} stores={violations!r} "
            "(code=subjective_copy_forbidden)"
        )
    _LOG.debug(
        "blank_slate_asserted owner_id=%s store_count=%s",
        owner.value,
        len(BLANK_SLATE_SUBJECTIVE_STORES),
    )


@dataclass(frozen=True, slots=True)
class SpeciesDefaultsPack:
    """Fresh cognition + innate drive baseline for a new owner (no live copy)."""

    species_defaults_id: str
    cognition: AgentCognitionSpec
    drive_profile: DriveProfile

    def __post_init__(self) -> None:
        if type(self.cognition) is not AgentCognitionSpec:
            raise TypeError("cognition must be AgentCognitionSpec")
        if type(self.drive_profile) is not DriveProfile:
            raise TypeError("drive_profile must be DriveProfile")
        if self.cognition.agent_id != self.drive_profile.owner_id:
            raise ValueError(
                "species defaults cognition.agent_id must match drive owner"
            )


def _species_default_v1(agent_id: AgentId) -> SpeciesDefaultsPack:
    cognition = AgentCognitionSpec(agent_id=agent_id)
    drive_profile = cognition.resolve_drive_profile()
    return SpeciesDefaultsPack(
        species_defaults_id=SPECIES_DEFAULT_V1,
        cognition=cognition,
        drive_profile=drive_profile,
    )


def _species_default_developmental_v1(agent_id: AgentId) -> SpeciesDefaultsPack:
    """Learner pack: modes on / content empty. Does not invent run-level V2 flags."""
    cognition = AgentCognitionSpec(
        agent_id=agent_id,
        skill_learning_mode=SkillLearningMode.DETERMINISTIC,
        teaching_interaction_mode=TeachingInteractionMode.DETERMINISTIC,
        semantic_naming_mode=SemanticNamingMode.DETERMINISTIC,
        social_norm_mode=SocialNormMode.DETERMINISTIC,
        social_convention_mode=SocialConventionMode.DETERMINISTIC,
        cultural_narrative_mode=CulturalNarrativeMode.DETERMINISTIC,
        artifact_interpretation_mode=ArtifactInterpretationMode.DETERMINISTIC,
    )
    drive_profile = cognition.resolve_drive_profile()
    return SpeciesDefaultsPack(
        species_defaults_id=SPECIES_DEFAULT_DEVELOPMENTAL_V1,
        cognition=cognition,
        drive_profile=drive_profile,
    )


_SPECIES_DEFAULTS: Final[Mapping[str, object]] = {
    SPECIES_DEFAULT_V1: _species_default_v1,
    SPECIES_DEFAULT_DEVELOPMENTAL_V1: _species_default_developmental_v1,
}


def species_defaults_for(
    species_defaults_id: str, *, agent_id: AgentId
) -> SpeciesDefaultsPack:
    """Resolve a closed species-defaults pack for ``agent_id`` (fresh each call)."""
    if type(agent_id) is not AgentId:
        raise TypeError("agent_id must be AgentId")
    object_id = require_stable_id("species_defaults_id", species_defaults_id)
    factory = _SPECIES_DEFAULTS.get(object_id)
    if factory is None:
        _LOG.error(
            "species_defaults_unknown species_defaults_id=%s "
            "reason_code=unknown_species_defaults_id",
            object_id,
        )
        raise ValueError(
            f"unknown species_defaults_id {object_id!r} "
            "(code=unknown_species_defaults_id)"
        )
    pack = factory(agent_id)  # type: ignore[operator]
    _LOG.debug(
        "species_defaults_resolved species_defaults_id=%s agent_id=%s",
        object_id,
        agent_id.value,
    )
    return pack


def new_agent_init_stream(
    run_config: SimulationRunConfig,
    *,
    run_id: str,
    agent_id: str,
    draw_name: str,
) -> random.Random:
    """Named RNG stream scoped under ``new_agent_init`` (never wall clock)."""
    if type(run_config) is not SimulationRunConfig:
        raise TypeError("run_config must be SimulationRunConfig")
    scope = StreamScope(
        namespace="new_agent_init",
        names=(
            require_stable_id("run_id", run_id),
            require_stable_id("agent_id", agent_id),
            require_stable_id("draw_name", draw_name),
        ),
    )
    _LOG.debug(
        "new_agent_init_stream namespace=%s draw_name=%s agent_id=%s",
        scope.namespace,
        draw_name,
        agent_id,
    )
    return create_named_stream(run_config, scope)


@dataclass(frozen=True, slots=True)
class ParameterDrawResult:
    """Deterministic draw outcome (drive delta optional)."""

    distribution_id: str
    drive_kind: DriveKind | None = None
    delta: float | None = None


def draw_parameter_distribution(
    run_config: SimulationRunConfig,
    *,
    run_id: str,
    agent_id: str,
    distribution: ParameterDistributionSpec,
    draw_name: str = "parameter_distribution",
) -> ParameterDrawResult:
    """Draw from ``parameter_distributions`` via named stream (same-seed stable)."""
    if type(distribution) is not ParameterDistributionSpec:
        raise TypeError("distribution must be ParameterDistributionSpec")
    if distribution.distribution_id == "none":
        _LOG.debug(
            "parameter_draw_skipped distribution_id=none agent_id=%s",
            agent_id,
        )
        return ParameterDrawResult(distribution_id="none")
    rng = new_agent_init_stream(
        run_config,
        run_id=run_id,
        agent_id=agent_id,
        draw_name=draw_name,
    )
    if distribution.distribution_id == "uniform_drive_delta":
        kind = DriveKind(str(distribution.params["drive_kind"]))
        min_delta = float(distribution.params["min_delta"])
        max_delta = float(distribution.params["max_delta"])
        delta = rng.uniform(min_delta, max_delta)
        _LOG.debug(
            "parameter_draw_complete distribution_id=uniform_drive_delta "
            "agent_id=%s draw_name=%s drive_kind=%s",
            agent_id,
            draw_name,
            kind.value,
        )
        return ParameterDrawResult(
            distribution_id="uniform_drive_delta",
            drive_kind=kind,
            delta=delta,
        )
    raise ValueError(
        f"unhandled distribution_id {distribution.distribution_id!r} "
        "(code=unknown_parameter_distribution_id)"
    )


def apply_drive_delta_to_overrides(
    *,
    base_overrides: tuple[DriveOverrideSpec, ...],
    draw: ParameterDrawResult,
) -> tuple[DriveOverrideSpec, ...]:
    """Apply a uniform drive delta onto sparse overrides (baseline only)."""
    if draw.distribution_id == "none" or draw.drive_kind is None or draw.delta is None:
        return base_overrides
    kind = draw.drive_kind
    delta = draw.delta
    existing = {item.kind: item for item in base_overrides}
    prior = existing.get(kind)
    baseline = 0.5 if prior is None or prior.baseline is None else prior.baseline
    sensitivity = None if prior is None else prior.sensitivity
    new_baseline = min(1.0, max(0.0, baseline + delta))
    existing[kind] = DriveOverrideSpec(
        kind=kind, baseline=new_baseline, sensitivity=sensitivity
    )
    return tuple(existing[k] for k in sorted(existing, key=lambda item: item.value))


def resolve_spawn_location(
    *,
    policy: SpawnLocationPolicy,
    candidate_location_id: EntityId | None,
    provenance_is_demographic: bool,
    rng: random.Random | None = None,
) -> EntityId:
    """Resolve spawn location per locked precedence rules."""
    if type(policy) is not SpawnLocationPolicy:
        raise TypeError("policy must be SpawnLocationPolicy")
    if provenance_is_demographic:
        if candidate_location_id is None:
            raise ValueError(
                "demographic admit requires candidate spawn_location_id "
                "(code=spawn_location_candidate_required)"
            )
        if type(candidate_location_id) is not EntityId:
            raise TypeError("candidate_location_id must be EntityId")
        if policy.policy_id == "defer_to_candidate":
            return candidate_location_id
        allowlist = policy.allowlist_ids()
        if allowlist is None or candidate_location_id.value not in allowlist:
            raise ValueError(
                "candidate spawn location not allowed by policy "
                "(code=spawn_location_not_allowed)"
            )
        return candidate_location_id
    # External entry: resolve solely via policy.
    if policy.policy_id == "defer_to_candidate":
        raise ValueError(
            "external entry forbids defer_to_candidate "
            "(code=spawn_location_policy_required)"
        )
    if policy.policy_id == "fixed":
        return EntityId(str(policy.params["location_id"]))
    if policy.policy_id == "seeded_allowlist":
        if rng is None:
            raise ValueError(
                "seeded_allowlist requires rng "
                "(code=spawn_location_rng_required)"
            )
        ids = policy.params["location_ids"]
        assert isinstance(ids, tuple) and ids
        return EntityId(str(rng.choice(ids)))
    if policy.policy_id == "allowlist":
        raise ValueError(
            "external entry requires fixed or seeded_allowlist "
            "(code=spawn_location_policy_required)"
        )
    raise ValueError(
        f"unhandled spawn_location_policy {policy.policy_id!r} "
        "(code=unknown_spawn_location_policy_id)"
    )


# Re-export helper key set for serialization (exact child keys).
NEW_AGENT_INITIALIZATION_KEYS: Final[frozenset[str]] = _NEW_AGENT_INIT_KEYS
PROVENANCE_POLICY_KEYS: Final[frozenset[str]] = _PROVENANCE_POLICY_KEYS


@dataclass(frozen=True, slots=True)
class InitialConditionsSummary:
    """Exact structured summary recorded on AgentInitializationRecorded."""

    location_id: str
    dependency_status: str
    stage: str
    health: float
    hunger: float
    thirst: float
    fatigue: float
    temperature: float
    carry_capacity: float

    def canonical_payload(self) -> dict[str, object]:
        return {
            "carry_capacity": self.carry_capacity,
            "dependency_status": self.dependency_status,
            "fatigue": self.fatigue,
            "health": self.health,
            "hunger": self.hunger,
            "location_id": self.location_id,
            "stage": self.stage,
            "temperature": self.temperature,
            "thirst": self.thirst,
        }


@dataclass(frozen=True, slots=True)
class PreparedEntrantBody:
    """Shared pre-admit objective body + provenance facts."""

    body: object
    location_id: EntityId
    creation_reason: str
    origin_refs: tuple[OriginRef, ...]
    creation_config_id: str
    initial_conditions: InitialConditionsSummary
    stage: object
    dependency_status: object


def build_entrant_body_from_init(
    *,
    init_spec: NewAgentInitializationSpec,
    body_id: EntityId,
    location_id: EntityId,
    stage: object,
    dependency_status: object,
    creation_reason: str,
    origin_refs: tuple[OriginRef, ...] = (),
    creation_config_id: str,
    origin_body: object | None = None,
) -> PreparedEntrantBody:
    """Build objective entrant body using physical policy + objective inheritance.

    Shared by ``admit_population_entry`` and tick-path demographic admit.
    """
    from world.lifecycle import default_entrant_body
    from world.models import AgentBody, CarryCapacity
    from world.values import (
        Fatigue,
        Health,
        Hunger,
        TemperatureCelsius,
        Thirst,
    )

    if type(init_spec) is not NewAgentInitializationSpec:
        raise TypeError("init_spec must be NewAgentInitializationSpec")
    if creation_reason not in CREATION_REASON_CODES:
        raise ValueError(
            f"unknown creation_reason {creation_reason!r} "
            "(code=unknown_creation_reason_code)"
        )
    _LOG.debug(
        "new_agent_init_stage stage=build_objective_body agent_id=- "
        "reason_code=%s",
        creation_reason,
    )
    if init_spec.physical_condition_policy.policy_id != "default_entrant":
        raise ValueError(
            "unsupported physical_condition_policy "
            f"{init_spec.physical_condition_policy.policy_id!r}"
        )
    body = default_entrant_body(body_id=body_id, location_id=location_id)
    # Objective inheritance: only allowlisted keys from origin body.
    allowed = frozenset(init_spec.objective_inheritance.allowed_keys)
    if allowed:
        if origin_body is None:
            raise ValueError(
                "objective_inheritance requires origin_body "
                "(code=objective_inheritance_origin_required)"
            )
        if type(origin_body) is not AgentBody:
            raise TypeError("origin_body must be AgentBody")
        for key in allowed:
            if key != "carry_capacity":
                raise ValueError(
                    f"objective_inheritance key {key!r} forbidden "
                    "(code=objective_inheritance_key_forbidden)"
                )
        body = AgentBody(
            entity_id=body.entity_id,
            location_id=body.location_id,
            health=body.health,
            hunger=body.hunger,
            thirst=body.thirst,
            fatigue=body.fatigue,
            temperature=body.temperature,
            inventory=body.inventory,
            life_status=body.life_status,
            carry_capacity=CarryCapacity(origin_body.carry_capacity.value),
        )
    assert type(body) is AgentBody
    summary = InitialConditionsSummary(
        location_id=location_id.value,
        dependency_status=str(
            getattr(dependency_status, "value", dependency_status)
        ),
        stage=str(getattr(stage, "value", stage)),
        health=float(body.health.value),
        hunger=float(body.hunger.value),
        thirst=float(body.thirst.value),
        fatigue=float(body.fatigue.value),
        temperature=float(body.temperature.value),
        carry_capacity=float(body.carry_capacity.value),
    )
    # Silence unused imports if values types are only used via body fields.
    _ = (Health, Hunger, Thirst, Fatigue, TemperatureCelsius)
    return PreparedEntrantBody(
        body=body,
        location_id=location_id,
        creation_reason=creation_reason,
        origin_refs=origin_refs,
        creation_config_id=creation_config_id,
        initial_conditions=summary,
        stage=stage,
        dependency_status=dependency_status,
    )


def enforce_spawn_location_for_candidate(
    *,
    init_spec: NewAgentInitializationSpec,
    candidate_location_id: EntityId,
    provenance_is_demographic: bool,
) -> EntityId:
    """Apply spawn-location precedence; fail closed on disallow."""
    return resolve_spawn_location(
        policy=init_spec.spawn_location_policy,
        candidate_location_id=candidate_location_id,
        provenance_is_demographic=provenance_is_demographic,
    )
