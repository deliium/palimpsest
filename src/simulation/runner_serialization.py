"""Strict canonical JSON codecs and fingerprints for runner configuration.

Codecs are log-free except for one compatibility WARNING when decoding the
legacy ``recording_policy=recorded`` alias. Errors expose only stable ``code``
and ``path`` metadata. Credentials, base URLs, prompts, and full seed-bearing
dumps never appear in exception messages.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Mapping
from typing import Any, Final

from agents.models import AgentId, DriveKind, Goal
from llm.factory import ProviderAdapterKind
from llm.models import StructuredOutputMode
from simulation.models import StochasticIdentity
from simulation.runner_models import (
    COGNITION_POLICY_VERSION,
    MORTALITY_POLICY_VERSION,
    PROVIDER_SETTINGS_VERSION,
    RESULT_SCHEMA_VERSION,
    RESULT_SCHEMA_VERSION_V2,
    RUNNER_SCHEMA_VERSION_V1,
    RUNNER_SCHEMA_VERSION_V2,
    RUNNER_SCHEMA_VERSION_V3,
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V5,
    RUNNER_SCHEMA_VERSION_V6,
    RUNNER_SCHEMA_VERSION_V7,
    RUNNER_SCHEMA_VERSION_V8,
    RUNNER_SCHEMA_VERSION_V9,
    RUNNER_SCHEMA_VERSION_V10,
    RUNNER_SCHEMA_VERSION_V11,
    RUNNER_SCHEMA_VERSION_V12,
    RUNNER_SCHEMA_VERSION_V13,
    RUNNER_SCHEMA_VERSION_V14,
    RUNNER_SCHEMA_VERSION_V15,
    RUNNER_SCHEMA_VERSION_V16,
    RUNNER_SCHEMA_VERSION_V17,
    RUNNER_SCHEMA_VERSION_V18,
    RUNNER_SCHEMA_VERSION_V19,
    RUNNER_SCHEMA_VERSION_V20,
    RUNNER_SCHEMA_VERSION_V21,
    RUNNER_SCHEMA_VERSION_V22,
    RUNNER_SCHEMA_VERSION_V23,
    RUNNER_SCHEMA_VERSION_V24,
    RUNNER_SCHEMA_VERSION_V25,
    RUNNER_SCHEMA_VERSION_V26,
    RUNNER_SCHEMA_VERSION_V27,
    RUNNER_SCHEMA_VERSION_V28,
    RUNNER_SCHEMA_VERSION_V29,
    RUNNER_SCHEMA_VERSION_V30,
    RUNNER_SCHEMA_VERSION_V31,
    RUNNER_SCHEMA_VERSION_V32,
    SUPPORTED_RUNNER_SCHEMA_VERSIONS,
    AgentCognitionSpec,
    AgentRunnerSpec,
    ArtifactInterpretationMode,
    CognitionCounters,
    CognitionFailurePolicy,
    CognitionTraceDetail,
    CognitionTraceSpec,
    CognitiveBudgetLimits,
    CognitiveBudgetMode,
    CommunicationStrategyMode,
    ConsolidationMode,
    CounterfactualMode,
    CulturalFeatureBiasPolicy,
    CulturalFeatureMutationPolicy,
    CulturalFeatureProvenanceSpec,
    CulturalFeatureRecombinationPolicy,
    CulturalFeatureUptakeCompose,
    CulturalNarrativeMode,
    DependencyCareSpec,
    DevelopmentalCognitiveBudgetCoupling,
    DevelopmentalLearningSpec,
    DriveOverrideSpec,
    ExactReproducibilityMode,
    ExperimentAssignmentRef,
    FinalizedTickReceipt,
    GroupFormationMode,
    HistoricalMemoryLayersSpec,
    ImaginationMode,
    KinshipSpec,
    MemoryMode,
    MentorshipBondPolicy,
    MentorshipLineagePolicy,
    MentorshipPartnerBias,
    MentorshipSpec,
    MortalityMode,
    PopulationLifecycleSpec,
    ProductionKnowledgeMode,
    ProspectiveImaginationMode,
    RecordingPolicy,
    ReflectionMode,
    ReputationMode,
    RunnerCheckpointPolicy,
    RunnerConfigDiagnostics,
    RunnerPersistenceSpec,
    RunnerProviderSettings,
    RunnerStopPolicy,
    SemanticNamingMode,
    SimulationRunnerConfig,
    SimulationRunnerResult,
    SimulationRunnerResultDocument,
    SkillLearningMode,
    SocialConventionMode,
    SocialNormMode,
    TeachingInteractionMode,
    TerritorialClaimMode,
    V2CapabilityFlags,
    V3CapabilityFlags,
    WorldScenarioSpec,
    runner_config_diagnostics,
)
from simulation.serialization import (
    DomainSerializationError,
    _decode_agent_body,
    _decode_goal,
    _decode_item,
    _decode_location,
    _decode_physical_rules,
    _decode_resource,
    _decode_weather,
    _encode_agent_body,
    _encode_goal,
    _encode_item,
    _encode_location,
    _encode_physical_rules,
    _encode_resource,
    _encode_weather,
)
from world.environment import (
    EnvironmentalDynamicsSpec,
    HazardKind,
    HazardRule,
    Season,
    SeasonalYield,
    ShortageWindow,
    TemperatureBand,
)
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import physical_rules_fingerprint
from world.values import ResourceKind, WeatherCondition

__all__ = [
    "RunnerSerializationError",
    "build_runner_diagnostics",
    "build_runner_result_document",
    "cognition_fingerprint",
    "decode_finalization_command",
    "decode_runner_config",
    "encode_finalization_command",
    "encode_runner_config",
    "encode_runner_result_document",
    "exact_trajectory_hash",
    "finalization_command_to_mapping",
    "objective_projection_hash",
    "provider_fingerprint",
    "replica_normalized_trajectory_hash",
    "runner_config_fingerprint",
    "runner_result_fingerprint",
    "scenario_fingerprint",
]

_LOG: Final[logging.Logger] = logging.getLogger("simulation.runner_serialization")
_RECORDED_ALIAS_WARNED: bool = False


class RunnerSerializationError(ValueError):
    """Fail-closed runner codec error with stable metadata only."""

    def __init__(self, code: str, path: str) -> None:
        self.code = code
        self.path = path
        super().__init__(f"{code}:{path}")


def _canonical_dumps(value: object) -> bytes:
    text = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return text.encode("utf-8")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RunnerSerializationError("duplicate_key", "$")
        result[key] = value
    return result


def _sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _require_keys(data: Mapping[str, Any], required: set[str], *, path: str) -> None:
    keys = set(data)
    if required - keys:
        raise RunnerSerializationError("missing_field", path)
    if keys - required:
        raise RunnerSerializationError("invalid_fields", path)


def _str_field(data: Mapping[str, Any], key: str, *, path: str) -> str:
    value = data[key]
    if not isinstance(value, str):
        raise RunnerSerializationError("invalid_string", f"{path}.{key}")
    return value


def _bool_field(data: Mapping[str, Any], key: str, *, path: str) -> bool:
    value = data[key]
    if type(value) is not bool:
        raise RunnerSerializationError("invalid_bool", f"{path}.{key}")
    return value


def _nonneg_int_field(data: Mapping[str, Any], key: str, *, path: str) -> int:
    value = data[key]
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RunnerSerializationError("invalid_int", f"{path}.{key}")
    return value


def _required_float(data: Mapping[str, Any], key: str, *, path: str) -> float:
    if key not in data:
        raise RunnerSerializationError("invalid_fields", path)
    value = data[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RunnerSerializationError("invalid_number", f"{path}.{key}")
    number = float(value)
    if number != number or number in {float("inf"), float("-inf")}:
        raise RunnerSerializationError("non_finite_number", f"{path}.{key}")
    return number


def _optional_float(data: Mapping[str, Any], key: str, *, path: str) -> float | None:
    if key not in data or data[key] is None:
        return None
    value = data[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RunnerSerializationError("invalid_number", f"{path}.{key}")
    number = float(value)
    if number != number or number in {float("inf"), float("-inf")}:
        raise RunnerSerializationError("non_finite_number", f"{path}.{key}")
    return number


def _map_domain(exc: DomainSerializationError) -> RunnerSerializationError:
    code = exc.code
    if code == "non_finite_float":
        code = "non_finite_number"
    return RunnerSerializationError(code, exc.path)


def _raise_invalid_object(path: str) -> bool:
    raise RunnerSerializationError("invalid_object", path)


def _encode_drive_override(value: DriveOverrideSpec) -> dict[str, Any]:
    payload: dict[str, Any] = {"kind": value.kind.value}
    if value.baseline is not None:
        payload["baseline"] = value.baseline
    if value.sensitivity is not None:
        payload["sensitivity"] = value.sensitivity
    return payload


def _decode_drive_override(data: dict[str, Any], *, path: str) -> DriveOverrideSpec:
    allowed = {"kind", "baseline", "sensitivity"}
    if set(data) - allowed or "kind" not in data:
        raise RunnerSerializationError("invalid_fields", path)
    try:
        kind = DriveKind(_str_field(data, "kind", path=path))
    except ValueError as exc:
        raise RunnerSerializationError("invalid_enum", f"{path}.kind") from exc
    try:
        return DriveOverrideSpec(
            kind=kind,
            baseline=_optional_float(data, "baseline", path=path),
            sensitivity=_optional_float(data, "sensitivity", path=path),
        )
    except (TypeError, ValueError) as exc:
        raise RunnerSerializationError("invalid_model", path) from exc


_COGNITION_KEYS_V4: Final[set[str]] = {
    "agent_id",
    "memory_mode",
    "imagination_mode",
    "drive_overrides",
    "policy_version",
}
_COGNITION_KEYS_V5: Final[set[str]] = {
    *_COGNITION_KEYS_V4,
    "consolidation_mode",
}
_COGNITION_KEYS_V6: Final[set[str]] = {
    *_COGNITION_KEYS_V5,
    "reflection_mode",
}
_COGNITION_KEYS_V7: Final[set[str]] = {
    *_COGNITION_KEYS_V6,
    "prospective_mode",
}
_COGNITION_KEYS_V8: Final[set[str]] = {
    *_COGNITION_KEYS_V7,
    "counterfactual_mode",
}
_COGNITION_KEYS_V9: Final[set[str]] = {
    *_COGNITION_KEYS_V8,
    "communication_strategy_mode",
}
_COGNITION_KEYS_V10: Final[set[str]] = {
    *_COGNITION_KEYS_V9,
    "reputation_mode",
}
_SKILL_RATE_KEYS: Final[tuple[str, ...]] = (
    "practice_rate",
    "success_rate",
    "failure_rate",
    "instruction_rate",
    "observation_rate",
    "probability_gain",
    "efficiency_gain",
    "belief_practice_rate",
    "belief_success_rate",
    "belief_failure_rate",
    "belief_instruction_rate",
    "belief_observation_rate",
    "belief_prior",
    "belief_action_weight",
)
_COGNITION_KEYS_V11: Final[set[str]] = {
    *_COGNITION_KEYS_V10,
    "skill_learning_mode",
    *_SKILL_RATE_KEYS,
}
_TEACHING_WEIGHT_KEYS: Final[tuple[str, ...]] = (
    "demonstration_rate",
    "practice_together_rate",
    "offer_window",
    "belief_explain_rate",
    "explain_low_below",
    "explain_high_at",
    "teaching_response_weight",
)
_COGNITION_KEYS_V12: Final[set[str]] = {
    *_COGNITION_KEYS_V11,
    "teaching_interaction_mode",
    *_TEACHING_WEIGHT_KEYS,
}
_COGNITION_KEYS_V13: Final[set[str]] = {
    *_COGNITION_KEYS_V12,
    "production_catalog",
    "production_knowledge_mode",
}
_COGNITION_KEYS_V15: Final[set[str]] = {
    *_COGNITION_KEYS_V13,
    "territorial_claim_mode",
}
_COGNITION_KEYS_V16: Final[set[str]] = {
    *_COGNITION_KEYS_V15,
    "group_formation_mode",
}
_COGNITION_KEYS_V17: Final[set[str]] = {
    *_COGNITION_KEYS_V16,
    "social_norm_mode",
}
_COGNITION_KEYS_V18: Final[set[str]] = {
    *_COGNITION_KEYS_V17,
    "social_convention_mode",
}
_COGNITION_KEYS_V19: Final[set[str]] = {
    *_COGNITION_KEYS_V18,
    "artifact_interpretation_mode",
}
_COGNITION_KEYS_V20: Final[set[str]] = {
    *_COGNITION_KEYS_V19,
    "semantic_naming_mode",
}
_COGNITION_KEYS_V21: Final[set[str]] = {
    *_COGNITION_KEYS_V20,
    "cultural_narrative_mode",
}
_BUDGET_LIMIT_KEYS: Final[tuple[str, ...]] = (
    "max_llm_calls_per_tick",
    "max_tokens_per_tick",
    "max_imagination_branches",
    "max_planning_depth",
    "max_recalled_memories",
    "max_tom_targets",
    "reflection_interval_ticks",
    "timeout_seconds",
)
_COGNITION_KEYS_V22: Final[set[str]] = {
    *_COGNITION_KEYS_V21,
    "cognitive_budget_mode",
    *_BUDGET_LIMIT_KEYS,
}
_SKILL_SCHEMA_VERSIONS: Final[frozenset[str]] = frozenset(
    {
        RUNNER_SCHEMA_VERSION_V11,
        RUNNER_SCHEMA_VERSION_V12,
        RUNNER_SCHEMA_VERSION_V13,
        RUNNER_SCHEMA_VERSION_V14,
        RUNNER_SCHEMA_VERSION_V15,
        RUNNER_SCHEMA_VERSION_V16,
        RUNNER_SCHEMA_VERSION_V17,
        RUNNER_SCHEMA_VERSION_V18,
        RUNNER_SCHEMA_VERSION_V19,
        RUNNER_SCHEMA_VERSION_V20,
        RUNNER_SCHEMA_VERSION_V21,
        RUNNER_SCHEMA_VERSION_V22,
        RUNNER_SCHEMA_VERSION_V23,
        RUNNER_SCHEMA_VERSION_V24,
        RUNNER_SCHEMA_VERSION_V25,
        RUNNER_SCHEMA_VERSION_V26,
        RUNNER_SCHEMA_VERSION_V27,
    RUNNER_SCHEMA_VERSION_V28,
    RUNNER_SCHEMA_VERSION_V29,
    RUNNER_SCHEMA_VERSION_V30,
    RUNNER_SCHEMA_VERSION_V31,
    RUNNER_SCHEMA_VERSION_V32,
    }
)
_COGNITION_SCHEMA_CONSOLIDATION: Final[frozenset[str]] = frozenset(
    {
        RUNNER_SCHEMA_VERSION_V5,
        RUNNER_SCHEMA_VERSION_V6,
        RUNNER_SCHEMA_VERSION_V7,
        RUNNER_SCHEMA_VERSION_V8,
        RUNNER_SCHEMA_VERSION_V9,
        RUNNER_SCHEMA_VERSION_V10,
        RUNNER_SCHEMA_VERSION_V11,
        RUNNER_SCHEMA_VERSION_V12,
        RUNNER_SCHEMA_VERSION_V13,
        RUNNER_SCHEMA_VERSION_V14,
        RUNNER_SCHEMA_VERSION_V15,
        RUNNER_SCHEMA_VERSION_V16,
        RUNNER_SCHEMA_VERSION_V17,
        RUNNER_SCHEMA_VERSION_V18,
        RUNNER_SCHEMA_VERSION_V19,
        RUNNER_SCHEMA_VERSION_V20,
        RUNNER_SCHEMA_VERSION_V21,
        RUNNER_SCHEMA_VERSION_V22,
        RUNNER_SCHEMA_VERSION_V23,
        RUNNER_SCHEMA_VERSION_V24,
        RUNNER_SCHEMA_VERSION_V25,
        RUNNER_SCHEMA_VERSION_V26,
        RUNNER_SCHEMA_VERSION_V27,
    RUNNER_SCHEMA_VERSION_V28,
    RUNNER_SCHEMA_VERSION_V29,
    RUNNER_SCHEMA_VERSION_V30,
    RUNNER_SCHEMA_VERSION_V31,
    RUNNER_SCHEMA_VERSION_V32,
    }
)
_COGNITION_SCHEMA_REFLECTION: Final[frozenset[str]] = frozenset(
    {
        RUNNER_SCHEMA_VERSION_V6,
        RUNNER_SCHEMA_VERSION_V7,
        RUNNER_SCHEMA_VERSION_V8,
        RUNNER_SCHEMA_VERSION_V9,
        RUNNER_SCHEMA_VERSION_V10,
        RUNNER_SCHEMA_VERSION_V11,
        RUNNER_SCHEMA_VERSION_V12,
        RUNNER_SCHEMA_VERSION_V13,
        RUNNER_SCHEMA_VERSION_V14,
        RUNNER_SCHEMA_VERSION_V15,
        RUNNER_SCHEMA_VERSION_V16,
        RUNNER_SCHEMA_VERSION_V17,
        RUNNER_SCHEMA_VERSION_V18,
        RUNNER_SCHEMA_VERSION_V19,
        RUNNER_SCHEMA_VERSION_V20,
        RUNNER_SCHEMA_VERSION_V21,
        RUNNER_SCHEMA_VERSION_V22,
        RUNNER_SCHEMA_VERSION_V23,
        RUNNER_SCHEMA_VERSION_V24,
        RUNNER_SCHEMA_VERSION_V25,
        RUNNER_SCHEMA_VERSION_V26,
        RUNNER_SCHEMA_VERSION_V27,
    RUNNER_SCHEMA_VERSION_V28,
    RUNNER_SCHEMA_VERSION_V29,
    RUNNER_SCHEMA_VERSION_V30,
    RUNNER_SCHEMA_VERSION_V31,
    RUNNER_SCHEMA_VERSION_V32,
    }
)
_COGNITION_SCHEMA_PROSPECTIVE: Final[frozenset[str]] = frozenset(
    {
        RUNNER_SCHEMA_VERSION_V7,
        RUNNER_SCHEMA_VERSION_V8,
        RUNNER_SCHEMA_VERSION_V9,
        RUNNER_SCHEMA_VERSION_V10,
        RUNNER_SCHEMA_VERSION_V11,
        RUNNER_SCHEMA_VERSION_V12,
        RUNNER_SCHEMA_VERSION_V13,
        RUNNER_SCHEMA_VERSION_V14,
        RUNNER_SCHEMA_VERSION_V15,
        RUNNER_SCHEMA_VERSION_V16,
        RUNNER_SCHEMA_VERSION_V17,
        RUNNER_SCHEMA_VERSION_V18,
        RUNNER_SCHEMA_VERSION_V19,
        RUNNER_SCHEMA_VERSION_V20,
        RUNNER_SCHEMA_VERSION_V21,
        RUNNER_SCHEMA_VERSION_V22,
        RUNNER_SCHEMA_VERSION_V23,
        RUNNER_SCHEMA_VERSION_V24,
        RUNNER_SCHEMA_VERSION_V25,
        RUNNER_SCHEMA_VERSION_V26,
        RUNNER_SCHEMA_VERSION_V27,
    RUNNER_SCHEMA_VERSION_V28,
    RUNNER_SCHEMA_VERSION_V29,
    RUNNER_SCHEMA_VERSION_V30,
    RUNNER_SCHEMA_VERSION_V31,
    RUNNER_SCHEMA_VERSION_V32,
    }
)
_COGNITION_SCHEMA_COUNTERFACTUAL: Final[frozenset[str]] = frozenset(
    {
        RUNNER_SCHEMA_VERSION_V8,
        RUNNER_SCHEMA_VERSION_V9,
        RUNNER_SCHEMA_VERSION_V10,
        RUNNER_SCHEMA_VERSION_V11,
        RUNNER_SCHEMA_VERSION_V12,
        RUNNER_SCHEMA_VERSION_V13,
        RUNNER_SCHEMA_VERSION_V14,
        RUNNER_SCHEMA_VERSION_V15,
        RUNNER_SCHEMA_VERSION_V16,
        RUNNER_SCHEMA_VERSION_V17,
        RUNNER_SCHEMA_VERSION_V18,
        RUNNER_SCHEMA_VERSION_V19,
        RUNNER_SCHEMA_VERSION_V20,
        RUNNER_SCHEMA_VERSION_V21,
        RUNNER_SCHEMA_VERSION_V22,
        RUNNER_SCHEMA_VERSION_V23,
        RUNNER_SCHEMA_VERSION_V24,
        RUNNER_SCHEMA_VERSION_V25,
        RUNNER_SCHEMA_VERSION_V26,
        RUNNER_SCHEMA_VERSION_V27,
    RUNNER_SCHEMA_VERSION_V28,
    RUNNER_SCHEMA_VERSION_V29,
    RUNNER_SCHEMA_VERSION_V30,
    RUNNER_SCHEMA_VERSION_V31,
    RUNNER_SCHEMA_VERSION_V32,
    }
)
_COGNITION_SCHEMA_STRATEGY: Final[frozenset[str]] = frozenset(
    {
        RUNNER_SCHEMA_VERSION_V9,
        RUNNER_SCHEMA_VERSION_V10,
        RUNNER_SCHEMA_VERSION_V11,
        RUNNER_SCHEMA_VERSION_V12,
        RUNNER_SCHEMA_VERSION_V13,
        RUNNER_SCHEMA_VERSION_V14,
        RUNNER_SCHEMA_VERSION_V15,
        RUNNER_SCHEMA_VERSION_V16,
        RUNNER_SCHEMA_VERSION_V17,
        RUNNER_SCHEMA_VERSION_V18,
        RUNNER_SCHEMA_VERSION_V19,
        RUNNER_SCHEMA_VERSION_V20,
        RUNNER_SCHEMA_VERSION_V21,
        RUNNER_SCHEMA_VERSION_V22,
        RUNNER_SCHEMA_VERSION_V23,
        RUNNER_SCHEMA_VERSION_V24,
        RUNNER_SCHEMA_VERSION_V25,
        RUNNER_SCHEMA_VERSION_V26,
        RUNNER_SCHEMA_VERSION_V27,
    RUNNER_SCHEMA_VERSION_V28,
    RUNNER_SCHEMA_VERSION_V29,
    RUNNER_SCHEMA_VERSION_V30,
    RUNNER_SCHEMA_VERSION_V31,
    RUNNER_SCHEMA_VERSION_V32,
    }
)
_COGNITION_SCHEMA_REPUTATION: Final[frozenset[str]] = frozenset(
    {
        RUNNER_SCHEMA_VERSION_V10,
        RUNNER_SCHEMA_VERSION_V11,
        RUNNER_SCHEMA_VERSION_V12,
        RUNNER_SCHEMA_VERSION_V13,
        RUNNER_SCHEMA_VERSION_V14,
        RUNNER_SCHEMA_VERSION_V15,
        RUNNER_SCHEMA_VERSION_V16,
        RUNNER_SCHEMA_VERSION_V17,
        RUNNER_SCHEMA_VERSION_V18,
        RUNNER_SCHEMA_VERSION_V19,
        RUNNER_SCHEMA_VERSION_V20,
        RUNNER_SCHEMA_VERSION_V21,
        RUNNER_SCHEMA_VERSION_V22,
        RUNNER_SCHEMA_VERSION_V23,
        RUNNER_SCHEMA_VERSION_V24,
        RUNNER_SCHEMA_VERSION_V25,
        RUNNER_SCHEMA_VERSION_V26,
        RUNNER_SCHEMA_VERSION_V27,
    RUNNER_SCHEMA_VERSION_V28,
    RUNNER_SCHEMA_VERSION_V29,
    RUNNER_SCHEMA_VERSION_V30,
    RUNNER_SCHEMA_VERSION_V31,
    RUNNER_SCHEMA_VERSION_V32,
    }
)


def _encode_production_catalog(catalog: object) -> list[dict[str, Any]]:
    from world.production import ProductionCatalog

    if type(catalog) is not ProductionCatalog:
        raise RunnerSerializationError("invalid_model", "production_catalog")
    return [_encode_production_recipe(recipe) for recipe in catalog.recipes]


def _encode_production_recipe(recipe: object) -> dict[str, Any]:
    from world.production import ProductionRecipe

    if type(recipe) is not ProductionRecipe:
        raise RunnerSerializationError("invalid_model", "production_catalog")
    return {
        "action": recipe.action.value,
        "duration_ticks": recipe.duration_ticks,
        "inputs": [_encode_production_input(item) for item in recipe.inputs],
        "output": _encode_production_output(recipe.output),
        "recipe_id": recipe.recipe_id.value,
        "success_probability": recipe.success_probability,
        "tool_role": None if recipe.tool_role is None else recipe.tool_role.value,
    }


def _encode_production_input(item: object) -> dict[str, Any]:
    from world.production import HeldItemKindInput, HeldItemNameInput, ResourceNameInput

    if type(item) is ResourceNameInput:
        return {"kind": "resource_name", "name": item.name}
    if type(item) is HeldItemNameInput:
        return {"kind": "held_name", "name": item.name}
    if type(item) is HeldItemKindInput:
        return {"item_kind": item.item_kind.value, "kind": "held_kind"}
    raise RunnerSerializationError("invalid_model", "production_catalog")


def _encode_production_output(item: object) -> dict[str, Any]:
    from world.production import (
        ItemProduct,
        RepairProduct,
        ShelterProduct,
        StoreProduct,
    )

    if type(item) is ItemProduct:
        return {
            "item_kind": item.item_kind.value,
            "kind": "item",
            "load": item.load.value,
            "name": item.name,
            "tool_role": None if item.tool_role is None else item.tool_role.value,
        }
    if type(item) is ShelterProduct:
        return {
            "initial_integrity": item.initial_integrity,
            "kind": "shelter",
            "structure_kind": item.structure_kind.value,
        }
    if type(item) is RepairProduct:
        return {"integrity_delta": item.integrity_delta, "kind": "repair"}
    if type(item) is StoreProduct:
        return {
            "initial_integrity": item.initial_integrity,
            "initial_stored_quantity": item.initial_stored_quantity,
            "kind": "store",
            "quantity_delta": item.quantity_delta,
        }
    raise RunnerSerializationError("invalid_model", "production_catalog")


def _decode_production_catalog(data: list[object], *, path: str) -> object:
    from world.production import ProductionCatalog, ProductionRecipe

    recipes: list[ProductionRecipe] = []
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise RunnerSerializationError("invalid_object", f"{path}[{index}]")
        recipes.append(_decode_production_recipe(item, path=f"{path}[{index}]"))
    try:
        return ProductionCatalog(tuple(recipes))
    except (TypeError, ValueError) as exc:
        raise RunnerSerializationError("invalid_model", path) from exc


def _decode_production_recipe(data: Mapping[str, Any], *, path: str) -> object:
    from world.identifiers import RecipeId
    from world.production import ProductionAction, ProductionRecipe, ToolRole

    _require_keys(
        data,
        {
            "action",
            "duration_ticks",
            "inputs",
            "output",
            "recipe_id",
            "success_probability",
            "tool_role",
        },
        path=path,
    )
    inputs_raw = data["inputs"]
    output_raw = data["output"]
    if not isinstance(inputs_raw, list) or not inputs_raw:
        raise RunnerSerializationError("invalid_array", f"{path}.inputs")
    if not isinstance(output_raw, dict):
        raise RunnerSerializationError("invalid_object", f"{path}.output")
    tool_role_raw = data["tool_role"]
    tool_role = None
    if tool_role_raw is not None:
        if type(tool_role_raw) is not str:
            raise RunnerSerializationError("invalid_enum", f"{path}.tool_role")
        try:
            tool_role = ToolRole(tool_role_raw)
        except ValueError as exc:
            raise RunnerSerializationError("invalid_enum", f"{path}.tool_role") from exc
    try:
        return ProductionRecipe(
            recipe_id=RecipeId(_str_field(data, "recipe_id", path=path)),
            action=ProductionAction(_str_field(data, "action", path=path)),
            duration_ticks=_nonneg_int_field(data, "duration_ticks", path=path),
            success_probability=_required_float(data, "success_probability", path=path),
            inputs=tuple(
                _decode_production_input(item, path=f"{path}.inputs[{index}]")
                for index, item in enumerate(inputs_raw)
            ),
            output=_decode_production_output(output_raw, path=f"{path}.output"),
            tool_role=tool_role,
        )
    except RunnerSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise RunnerSerializationError("invalid_model", path) from exc


def _decode_production_input(data: object, *, path: str) -> object:
    from world.production import HeldItemKindInput, HeldItemNameInput, ResourceNameInput
    from world.values import ItemKind

    if not isinstance(data, dict):
        raise RunnerSerializationError("invalid_object", path)
    kind = _str_field(data, "kind", path=path)
    if kind == "resource_name":
        _require_keys(data, {"kind", "name"}, path=path)
        return ResourceNameInput(name=_str_field(data, "name", path=path))
    if kind == "held_name":
        _require_keys(data, {"kind", "name"}, path=path)
        return HeldItemNameInput(name=_str_field(data, "name", path=path))
    if kind == "held_kind":
        _require_keys(data, {"item_kind", "kind"}, path=path)
        try:
            return HeldItemKindInput(
                item_kind=ItemKind(_str_field(data, "item_kind", path=path))
            )
        except ValueError as exc:
            raise RunnerSerializationError("invalid_enum", f"{path}.item_kind") from exc
    raise RunnerSerializationError("invalid_enum", f"{path}.kind")


def _decode_production_output(data: Mapping[str, Any], *, path: str) -> object:
    from world.production import (
        ItemProduct,
        RepairProduct,
        ShelterProduct,
        StoreProduct,
        StructureKind,
        ToolRole,
    )
    from world.values import ItemKind, ItemLoad

    kind = _str_field(data, "kind", path=path)
    if kind == "item":
        _require_keys(
            data,
            {"item_kind", "kind", "load", "name", "tool_role"},
            path=path,
        )
        tool_role_raw = data["tool_role"]
        tool_role = None
        if tool_role_raw is not None:
            try:
                tool_role = ToolRole(tool_role_raw)
            except ValueError as exc:
                raise RunnerSerializationError(
                    "invalid_enum", f"{path}.tool_role"
                ) from exc
        try:
            return ItemProduct(
                item_kind=ItemKind(_str_field(data, "item_kind", path=path)),
                name=_str_field(data, "name", path=path),
                load=ItemLoad(_nonneg_int_field(data, "load", path=path)),
                tool_role=tool_role,
            )
        except (TypeError, ValueError) as exc:
            raise RunnerSerializationError("invalid_model", path) from exc
    if kind == "shelter":
        _require_keys(data, {"initial_integrity", "kind", "structure_kind"}, path=path)
        try:
            return ShelterProduct(
                structure_kind=StructureKind(
                    _str_field(data, "structure_kind", path=path)
                ),
                initial_integrity=_required_float(data, "initial_integrity", path=path),
            )
        except (TypeError, ValueError) as exc:
            raise RunnerSerializationError("invalid_model", path) from exc
    if kind == "repair":
        _require_keys(data, {"integrity_delta", "kind"}, path=path)
        try:
            return RepairProduct(
                integrity_delta=_required_float(data, "integrity_delta", path=path)
            )
        except (TypeError, ValueError) as exc:
            raise RunnerSerializationError("invalid_model", path) from exc
    if kind == "store":
        _require_keys(
            data,
            {
                "initial_integrity",
                "initial_stored_quantity",
                "kind",
                "quantity_delta",
            },
            path=path,
        )
        try:
            return StoreProduct(
                quantity_delta=_nonneg_int_field(data, "quantity_delta", path=path),
                initial_integrity=_required_float(data, "initial_integrity", path=path),
                initial_stored_quantity=_nonneg_int_field(
                    data, "initial_stored_quantity", path=path
                ),
            )
        except (TypeError, ValueError) as exc:
            raise RunnerSerializationError("invalid_model", path) from exc
    raise RunnerSerializationError("invalid_enum", f"{path}.kind")


def _encode_cognition(
    value: AgentCognitionSpec, *, schema_version: str
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "agent_id": value.agent_id.value,
        "drive_overrides": [
            _encode_drive_override(item) for item in value.drive_overrides
        ],
        "imagination_mode": value.imagination_mode.value,
        "memory_mode": value.memory_mode.value,
        "policy_version": value.policy_version,
    }
    if schema_version in _COGNITION_SCHEMA_CONSOLIDATION:
        payload["consolidation_mode"] = value.consolidation_mode.value
    if schema_version in _COGNITION_SCHEMA_REFLECTION:
        payload["reflection_mode"] = value.reflection_mode.value
    if schema_version in _COGNITION_SCHEMA_PROSPECTIVE:
        payload["prospective_mode"] = value.prospective_mode.value
    if schema_version in _COGNITION_SCHEMA_COUNTERFACTUAL:
        payload["counterfactual_mode"] = value.counterfactual_mode.value
    if schema_version in _COGNITION_SCHEMA_STRATEGY:
        payload["communication_strategy_mode"] = value.communication_strategy_mode.value
    if schema_version in _COGNITION_SCHEMA_REPUTATION:
        payload["reputation_mode"] = value.reputation_mode.value
    if schema_version in _SKILL_SCHEMA_VERSIONS:
        payload["skill_learning_mode"] = value.skill_learning_mode.value
        for name in _SKILL_RATE_KEYS:
            payload[name] = getattr(value, name)
    if schema_version in {
        RUNNER_SCHEMA_VERSION_V12,
        RUNNER_SCHEMA_VERSION_V13,
        RUNNER_SCHEMA_VERSION_V14,
        RUNNER_SCHEMA_VERSION_V15,
        RUNNER_SCHEMA_VERSION_V16,
        RUNNER_SCHEMA_VERSION_V17,
        RUNNER_SCHEMA_VERSION_V18,
        RUNNER_SCHEMA_VERSION_V19,
        RUNNER_SCHEMA_VERSION_V20,
        RUNNER_SCHEMA_VERSION_V21,
        RUNNER_SCHEMA_VERSION_V22,
        RUNNER_SCHEMA_VERSION_V23,
        RUNNER_SCHEMA_VERSION_V24,
        RUNNER_SCHEMA_VERSION_V25,
        RUNNER_SCHEMA_VERSION_V26,
        RUNNER_SCHEMA_VERSION_V27,
    RUNNER_SCHEMA_VERSION_V28,
    RUNNER_SCHEMA_VERSION_V29,
    RUNNER_SCHEMA_VERSION_V30,
    RUNNER_SCHEMA_VERSION_V31,
    RUNNER_SCHEMA_VERSION_V32,
    }:
        payload["teaching_interaction_mode"] = value.teaching_interaction_mode.value
        for name in _TEACHING_WEIGHT_KEYS:
            payload[name] = getattr(value, name)
    if schema_version in {
        RUNNER_SCHEMA_VERSION_V13,
        RUNNER_SCHEMA_VERSION_V14,
        RUNNER_SCHEMA_VERSION_V15,
        RUNNER_SCHEMA_VERSION_V16,
        RUNNER_SCHEMA_VERSION_V17,
        RUNNER_SCHEMA_VERSION_V18,
        RUNNER_SCHEMA_VERSION_V19,
        RUNNER_SCHEMA_VERSION_V20,
        RUNNER_SCHEMA_VERSION_V21,
        RUNNER_SCHEMA_VERSION_V22,
        RUNNER_SCHEMA_VERSION_V23,
        RUNNER_SCHEMA_VERSION_V24,
        RUNNER_SCHEMA_VERSION_V25,
        RUNNER_SCHEMA_VERSION_V26,
        RUNNER_SCHEMA_VERSION_V27,
    RUNNER_SCHEMA_VERSION_V28,
    RUNNER_SCHEMA_VERSION_V29,
    RUNNER_SCHEMA_VERSION_V30,
    RUNNER_SCHEMA_VERSION_V31,
    RUNNER_SCHEMA_VERSION_V32,
    }:
        payload["production_knowledge_mode"] = value.production_knowledge_mode.value
        payload["production_catalog"] = _encode_production_catalog(
            value.production_catalog
        )
    if schema_version in {
        RUNNER_SCHEMA_VERSION_V15,
        RUNNER_SCHEMA_VERSION_V16,
        RUNNER_SCHEMA_VERSION_V17,
        RUNNER_SCHEMA_VERSION_V18,
        RUNNER_SCHEMA_VERSION_V19,
        RUNNER_SCHEMA_VERSION_V20,
        RUNNER_SCHEMA_VERSION_V21,
        RUNNER_SCHEMA_VERSION_V22,
        RUNNER_SCHEMA_VERSION_V23,
        RUNNER_SCHEMA_VERSION_V24,
        RUNNER_SCHEMA_VERSION_V25,
        RUNNER_SCHEMA_VERSION_V26,
        RUNNER_SCHEMA_VERSION_V27,
    RUNNER_SCHEMA_VERSION_V28,
    RUNNER_SCHEMA_VERSION_V29,
    RUNNER_SCHEMA_VERSION_V30,
    RUNNER_SCHEMA_VERSION_V31,
    RUNNER_SCHEMA_VERSION_V32,
    }:
        payload["territorial_claim_mode"] = value.territorial_claim_mode.value
    if schema_version in {
        RUNNER_SCHEMA_VERSION_V16,
        RUNNER_SCHEMA_VERSION_V17,
        RUNNER_SCHEMA_VERSION_V18,
        RUNNER_SCHEMA_VERSION_V19,
        RUNNER_SCHEMA_VERSION_V20,
        RUNNER_SCHEMA_VERSION_V21,
        RUNNER_SCHEMA_VERSION_V22,
        RUNNER_SCHEMA_VERSION_V23,
        RUNNER_SCHEMA_VERSION_V24,
        RUNNER_SCHEMA_VERSION_V25,
        RUNNER_SCHEMA_VERSION_V26,
        RUNNER_SCHEMA_VERSION_V27,
    RUNNER_SCHEMA_VERSION_V28,
    RUNNER_SCHEMA_VERSION_V29,
    RUNNER_SCHEMA_VERSION_V30,
    RUNNER_SCHEMA_VERSION_V31,
    RUNNER_SCHEMA_VERSION_V32,
    }:
        payload["group_formation_mode"] = value.group_formation_mode.value
    if schema_version in {
        RUNNER_SCHEMA_VERSION_V17,
        RUNNER_SCHEMA_VERSION_V18,
        RUNNER_SCHEMA_VERSION_V19,
        RUNNER_SCHEMA_VERSION_V20,
        RUNNER_SCHEMA_VERSION_V21,
        RUNNER_SCHEMA_VERSION_V22,
        RUNNER_SCHEMA_VERSION_V23,
        RUNNER_SCHEMA_VERSION_V24,
        RUNNER_SCHEMA_VERSION_V25,
        RUNNER_SCHEMA_VERSION_V26,
        RUNNER_SCHEMA_VERSION_V27,
    RUNNER_SCHEMA_VERSION_V28,
    RUNNER_SCHEMA_VERSION_V29,
    RUNNER_SCHEMA_VERSION_V30,
    RUNNER_SCHEMA_VERSION_V31,
    RUNNER_SCHEMA_VERSION_V32,
    }:
        payload["social_norm_mode"] = value.social_norm_mode.value
    if schema_version in {
        RUNNER_SCHEMA_VERSION_V18,
        RUNNER_SCHEMA_VERSION_V19,
        RUNNER_SCHEMA_VERSION_V20,
        RUNNER_SCHEMA_VERSION_V21,
        RUNNER_SCHEMA_VERSION_V22,
        RUNNER_SCHEMA_VERSION_V23,
        RUNNER_SCHEMA_VERSION_V24,
        RUNNER_SCHEMA_VERSION_V25,
        RUNNER_SCHEMA_VERSION_V26,
        RUNNER_SCHEMA_VERSION_V27,
    RUNNER_SCHEMA_VERSION_V28,
    RUNNER_SCHEMA_VERSION_V29,
    RUNNER_SCHEMA_VERSION_V30,
    RUNNER_SCHEMA_VERSION_V31,
    RUNNER_SCHEMA_VERSION_V32,
    }:
        payload["social_convention_mode"] = value.social_convention_mode.value
    if schema_version in {
        RUNNER_SCHEMA_VERSION_V19,
        RUNNER_SCHEMA_VERSION_V20,
        RUNNER_SCHEMA_VERSION_V21,
        RUNNER_SCHEMA_VERSION_V22,
        RUNNER_SCHEMA_VERSION_V23,
        RUNNER_SCHEMA_VERSION_V24,
        RUNNER_SCHEMA_VERSION_V25,
        RUNNER_SCHEMA_VERSION_V26,
        RUNNER_SCHEMA_VERSION_V27,
    RUNNER_SCHEMA_VERSION_V28,
    RUNNER_SCHEMA_VERSION_V29,
    RUNNER_SCHEMA_VERSION_V30,
    RUNNER_SCHEMA_VERSION_V31,
    RUNNER_SCHEMA_VERSION_V32,
    }:
        payload["artifact_interpretation_mode"] = (
            value.artifact_interpretation_mode.value
        )
    if schema_version in {
        RUNNER_SCHEMA_VERSION_V20,
        RUNNER_SCHEMA_VERSION_V21,
        RUNNER_SCHEMA_VERSION_V22,
        RUNNER_SCHEMA_VERSION_V23,
        RUNNER_SCHEMA_VERSION_V24,
        RUNNER_SCHEMA_VERSION_V25,
        RUNNER_SCHEMA_VERSION_V26,
        RUNNER_SCHEMA_VERSION_V27,
    RUNNER_SCHEMA_VERSION_V28,
    RUNNER_SCHEMA_VERSION_V29,
    RUNNER_SCHEMA_VERSION_V30,
    RUNNER_SCHEMA_VERSION_V31,
    RUNNER_SCHEMA_VERSION_V32,
    }:
        payload["semantic_naming_mode"] = value.semantic_naming_mode.value
    if schema_version in {
        RUNNER_SCHEMA_VERSION_V21,
        RUNNER_SCHEMA_VERSION_V22,
        RUNNER_SCHEMA_VERSION_V23,
        RUNNER_SCHEMA_VERSION_V24,
        RUNNER_SCHEMA_VERSION_V25,
        RUNNER_SCHEMA_VERSION_V26,
        RUNNER_SCHEMA_VERSION_V27,
    RUNNER_SCHEMA_VERSION_V28,
    RUNNER_SCHEMA_VERSION_V29,
    RUNNER_SCHEMA_VERSION_V30,
    RUNNER_SCHEMA_VERSION_V31,
    RUNNER_SCHEMA_VERSION_V32,
    }:
        payload["cultural_narrative_mode"] = value.cultural_narrative_mode.value
    if schema_version in {
        RUNNER_SCHEMA_VERSION_V22,
        RUNNER_SCHEMA_VERSION_V23,
        RUNNER_SCHEMA_VERSION_V24,
        RUNNER_SCHEMA_VERSION_V25,
        RUNNER_SCHEMA_VERSION_V26,
        RUNNER_SCHEMA_VERSION_V27,
    RUNNER_SCHEMA_VERSION_V28,
    RUNNER_SCHEMA_VERSION_V29,
    RUNNER_SCHEMA_VERSION_V30,
    RUNNER_SCHEMA_VERSION_V31,
    RUNNER_SCHEMA_VERSION_V32,
    }:
        payload["cognitive_budget_mode"] = value.cognitive_budget_mode.value
        limits = value.cognitive_budget_limits
        if value.cognitive_budget_mode is CognitiveBudgetMode.ENFORCED:
            if limits is None:
                raise RunnerSerializationError(
                    "invalid_model", "$.cognitive_budget_limits"
                )
            payload["max_llm_calls_per_tick"] = limits.max_llm_calls_per_tick
            payload["max_tokens_per_tick"] = limits.max_tokens_per_tick
            payload["max_imagination_branches"] = limits.max_imagination_branches
            payload["max_planning_depth"] = limits.max_planning_depth
            payload["max_recalled_memories"] = limits.max_recalled_memories
            payload["max_tom_targets"] = limits.max_tom_targets
            payload["reflection_interval_ticks"] = limits.reflection_interval_ticks
            payload["timeout_seconds"] = limits.timeout_seconds
        elif schema_version in {
            RUNNER_SCHEMA_VERSION_V23,
            RUNNER_SCHEMA_VERSION_V24,
            RUNNER_SCHEMA_VERSION_V25,
            RUNNER_SCHEMA_VERSION_V26,
            RUNNER_SCHEMA_VERSION_V27,
        RUNNER_SCHEMA_VERSION_V28,
        RUNNER_SCHEMA_VERSION_V29,
        RUNNER_SCHEMA_VERSION_V30,
        RUNNER_SCHEMA_VERSION_V31,
        RUNNER_SCHEMA_VERSION_V32,
        }:
            # Full v22 keyset on v23+; DISABLED budgets encode null limit keys.
            for key in _BUDGET_LIMIT_KEYS:
                payload[key] = None
        else:
            if limits is None:
                raise RunnerSerializationError(
                    "invalid_model", "$.cognitive_budget_limits"
                )
            payload["max_llm_calls_per_tick"] = limits.max_llm_calls_per_tick
            payload["max_tokens_per_tick"] = limits.max_tokens_per_tick
            payload["max_imagination_branches"] = limits.max_imagination_branches
            payload["max_planning_depth"] = limits.max_planning_depth
            payload["max_recalled_memories"] = limits.max_recalled_memories
            payload["max_tom_targets"] = limits.max_tom_targets
            payload["reflection_interval_ticks"] = limits.reflection_interval_ticks
            payload["timeout_seconds"] = limits.timeout_seconds
    return payload


def _decode_cognition(
    data: dict[str, Any], *, path: str, schema_version: str
) -> AgentCognitionSpec:
    if schema_version in {
        RUNNER_SCHEMA_VERSION_V22,
        RUNNER_SCHEMA_VERSION_V23,
        RUNNER_SCHEMA_VERSION_V24,
        RUNNER_SCHEMA_VERSION_V25,
        RUNNER_SCHEMA_VERSION_V26,
        RUNNER_SCHEMA_VERSION_V27,
    RUNNER_SCHEMA_VERSION_V28,
    RUNNER_SCHEMA_VERSION_V29,
    RUNNER_SCHEMA_VERSION_V30,
    RUNNER_SCHEMA_VERSION_V31,
    RUNNER_SCHEMA_VERSION_V32,
    }:
        _require_keys(data, _COGNITION_KEYS_V22, path=path)
    elif schema_version == RUNNER_SCHEMA_VERSION_V21:
        _require_keys(data, _COGNITION_KEYS_V21, path=path)
    elif schema_version == RUNNER_SCHEMA_VERSION_V20:
        _require_keys(data, _COGNITION_KEYS_V20, path=path)
    elif schema_version == RUNNER_SCHEMA_VERSION_V19:
        _require_keys(data, _COGNITION_KEYS_V19, path=path)
    elif schema_version == RUNNER_SCHEMA_VERSION_V18:
        _require_keys(data, _COGNITION_KEYS_V18, path=path)
    elif schema_version == RUNNER_SCHEMA_VERSION_V17:
        _require_keys(data, _COGNITION_KEYS_V17, path=path)
    elif schema_version == RUNNER_SCHEMA_VERSION_V16:
        _require_keys(data, _COGNITION_KEYS_V16, path=path)
    elif schema_version == RUNNER_SCHEMA_VERSION_V15:
        _require_keys(data, _COGNITION_KEYS_V15, path=path)
    elif schema_version in {RUNNER_SCHEMA_VERSION_V13, RUNNER_SCHEMA_VERSION_V14}:
        _require_keys(data, _COGNITION_KEYS_V13, path=path)
    elif schema_version == RUNNER_SCHEMA_VERSION_V12:
        _require_keys(data, _COGNITION_KEYS_V12, path=path)
    elif schema_version == RUNNER_SCHEMA_VERSION_V11:
        _require_keys(data, _COGNITION_KEYS_V11, path=path)
    elif schema_version == RUNNER_SCHEMA_VERSION_V10:
        _require_keys(data, _COGNITION_KEYS_V10, path=path)
    elif schema_version == RUNNER_SCHEMA_VERSION_V9:
        _require_keys(data, _COGNITION_KEYS_V9, path=path)
    elif schema_version == RUNNER_SCHEMA_VERSION_V8:
        _require_keys(data, _COGNITION_KEYS_V8, path=path)
    elif schema_version == RUNNER_SCHEMA_VERSION_V7:
        _require_keys(data, _COGNITION_KEYS_V7, path=path)
    elif schema_version == RUNNER_SCHEMA_VERSION_V6:
        _require_keys(data, _COGNITION_KEYS_V6, path=path)
    elif schema_version == RUNNER_SCHEMA_VERSION_V5:
        _require_keys(data, _COGNITION_KEYS_V5, path=path)
    else:
        _require_keys(data, _COGNITION_KEYS_V4, path=path)
    consolidation_mode = ConsolidationMode.DISABLED
    reflection_mode = ReflectionMode.DISABLED
    prospective_mode = ProspectiveImaginationMode.DISABLED
    counterfactual_mode = CounterfactualMode.DISABLED
    communication_strategy_mode = CommunicationStrategyMode.DISABLED
    reputation_mode = ReputationMode.DISABLED
    skill_learning_mode = SkillLearningMode.DISABLED
    teaching_interaction_mode = TeachingInteractionMode.DISABLED
    territorial_claim_mode = TerritorialClaimMode.DISABLED
    group_formation_mode = GroupFormationMode.DISABLED
    social_norm_mode = SocialNormMode.DISABLED
    social_convention_mode = SocialConventionMode.DISABLED
    artifact_interpretation_mode = ArtifactInterpretationMode.DISABLED
    semantic_naming_mode = SemanticNamingMode.DISABLED
    skill_rates: dict[str, float] = {}
    teaching_weights: dict[str, float | int] = {}
    if schema_version in _COGNITION_SCHEMA_CONSOLIDATION:
        try:
            consolidation_mode = ConsolidationMode(
                _str_field(data, "consolidation_mode", path=path)
            )
        except RunnerSerializationError:
            raise
        except ValueError as exc:
            raise RunnerSerializationError(
                "invalid_enum", f"{path}.consolidation_mode"
            ) from exc
    if schema_version in _COGNITION_SCHEMA_REFLECTION:
        try:
            reflection_mode = ReflectionMode(
                _str_field(data, "reflection_mode", path=path)
            )
        except RunnerSerializationError:
            raise
        except ValueError as exc:
            raise RunnerSerializationError(
                "invalid_enum", f"{path}.reflection_mode"
            ) from exc
    if schema_version in _COGNITION_SCHEMA_PROSPECTIVE:
        try:
            prospective_mode = ProspectiveImaginationMode(
                _str_field(data, "prospective_mode", path=path)
            )
        except RunnerSerializationError:
            raise
        except ValueError as exc:
            raise RunnerSerializationError(
                "invalid_enum", f"{path}.prospective_mode"
            ) from exc
    if schema_version in _COGNITION_SCHEMA_COUNTERFACTUAL:
        try:
            counterfactual_mode = CounterfactualMode(
                _str_field(data, "counterfactual_mode", path=path)
            )
        except RunnerSerializationError:
            raise
        except ValueError as exc:
            raise RunnerSerializationError(
                "invalid_enum", f"{path}.counterfactual_mode"
            ) from exc
    if schema_version in _COGNITION_SCHEMA_STRATEGY:
        try:
            communication_strategy_mode = CommunicationStrategyMode(
                _str_field(data, "communication_strategy_mode", path=path)
            )
        except RunnerSerializationError:
            raise
        except ValueError as exc:
            raise RunnerSerializationError(
                "invalid_enum", f"{path}.communication_strategy_mode"
            ) from exc
    if schema_version in _COGNITION_SCHEMA_REPUTATION:
        try:
            reputation_mode = ReputationMode(
                _str_field(data, "reputation_mode", path=path)
            )
        except RunnerSerializationError:
            raise
        except ValueError as exc:
            raise RunnerSerializationError(
                "invalid_enum", f"{path}.reputation_mode"
            ) from exc
    if schema_version in _SKILL_SCHEMA_VERSIONS:
        try:
            skill_learning_mode = SkillLearningMode(
                _str_field(data, "skill_learning_mode", path=path)
            )
        except RunnerSerializationError:
            raise
        except ValueError as exc:
            raise RunnerSerializationError(
                "invalid_enum", f"{path}.skill_learning_mode"
            ) from exc
        for name in _SKILL_RATE_KEYS:
            skill_rates[name] = _required_float(data, name, path=path)
    production_knowledge_mode = ProductionKnowledgeMode.DISABLED
    production_catalog = None
    if schema_version in {
        RUNNER_SCHEMA_VERSION_V12,
        RUNNER_SCHEMA_VERSION_V13,
        RUNNER_SCHEMA_VERSION_V14,
        RUNNER_SCHEMA_VERSION_V15,
        RUNNER_SCHEMA_VERSION_V16,
        RUNNER_SCHEMA_VERSION_V17,
        RUNNER_SCHEMA_VERSION_V18,
        RUNNER_SCHEMA_VERSION_V19,
        RUNNER_SCHEMA_VERSION_V20,
        RUNNER_SCHEMA_VERSION_V21,
        RUNNER_SCHEMA_VERSION_V22,
        RUNNER_SCHEMA_VERSION_V23,
        RUNNER_SCHEMA_VERSION_V24,
        RUNNER_SCHEMA_VERSION_V25,
        RUNNER_SCHEMA_VERSION_V26,
        RUNNER_SCHEMA_VERSION_V27,
    RUNNER_SCHEMA_VERSION_V28,
    RUNNER_SCHEMA_VERSION_V29,
    RUNNER_SCHEMA_VERSION_V30,
    RUNNER_SCHEMA_VERSION_V31,
    RUNNER_SCHEMA_VERSION_V32,
    }:
        try:
            teaching_interaction_mode = TeachingInteractionMode(
                _str_field(data, "teaching_interaction_mode", path=path)
            )
        except RunnerSerializationError:
            raise
        except ValueError as exc:
            raise RunnerSerializationError(
                "invalid_enum", f"{path}.teaching_interaction_mode"
            ) from exc
        for name in _TEACHING_WEIGHT_KEYS:
            if name == "offer_window":
                teaching_weights[name] = _nonneg_int_field(data, name, path=path)
            else:
                teaching_weights[name] = _required_float(data, name, path=path)
    if schema_version in {
        RUNNER_SCHEMA_VERSION_V13,
        RUNNER_SCHEMA_VERSION_V14,
        RUNNER_SCHEMA_VERSION_V15,
        RUNNER_SCHEMA_VERSION_V16,
        RUNNER_SCHEMA_VERSION_V17,
        RUNNER_SCHEMA_VERSION_V18,
        RUNNER_SCHEMA_VERSION_V19,
        RUNNER_SCHEMA_VERSION_V20,
        RUNNER_SCHEMA_VERSION_V21,
        RUNNER_SCHEMA_VERSION_V22,
        RUNNER_SCHEMA_VERSION_V23,
        RUNNER_SCHEMA_VERSION_V24,
        RUNNER_SCHEMA_VERSION_V25,
        RUNNER_SCHEMA_VERSION_V26,
        RUNNER_SCHEMA_VERSION_V27,
    RUNNER_SCHEMA_VERSION_V28,
    RUNNER_SCHEMA_VERSION_V29,
    RUNNER_SCHEMA_VERSION_V30,
    RUNNER_SCHEMA_VERSION_V31,
    RUNNER_SCHEMA_VERSION_V32,
    }:
        try:
            production_knowledge_mode = ProductionKnowledgeMode(
                _str_field(data, "production_knowledge_mode", path=path)
            )
        except RunnerSerializationError:
            raise
        except ValueError as exc:
            raise RunnerSerializationError(
                "invalid_enum", f"{path}.production_knowledge_mode"
            ) from exc
        catalog_raw = data.get("production_catalog")
        if not isinstance(catalog_raw, list):
            raise RunnerSerializationError(
                "invalid_array", f"{path}.production_catalog"
            )
        production_catalog = _decode_production_catalog(
            catalog_raw, path=f"{path}.production_catalog"
        )
    if schema_version in {
        RUNNER_SCHEMA_VERSION_V15,
        RUNNER_SCHEMA_VERSION_V16,
        RUNNER_SCHEMA_VERSION_V17,
        RUNNER_SCHEMA_VERSION_V18,
        RUNNER_SCHEMA_VERSION_V19,
        RUNNER_SCHEMA_VERSION_V20,
        RUNNER_SCHEMA_VERSION_V21,
        RUNNER_SCHEMA_VERSION_V22,
        RUNNER_SCHEMA_VERSION_V23,
        RUNNER_SCHEMA_VERSION_V24,
        RUNNER_SCHEMA_VERSION_V25,
        RUNNER_SCHEMA_VERSION_V26,
        RUNNER_SCHEMA_VERSION_V27,
    RUNNER_SCHEMA_VERSION_V28,
    RUNNER_SCHEMA_VERSION_V29,
    RUNNER_SCHEMA_VERSION_V30,
    RUNNER_SCHEMA_VERSION_V31,
    RUNNER_SCHEMA_VERSION_V32,
    }:
        try:
            territorial_claim_mode = TerritorialClaimMode(
                _str_field(data, "territorial_claim_mode", path=path)
            )
        except RunnerSerializationError:
            raise
        except ValueError as exc:
            raise RunnerSerializationError(
                "invalid_enum", f"{path}.territorial_claim_mode"
            ) from exc
    if schema_version in {
        RUNNER_SCHEMA_VERSION_V16,
        RUNNER_SCHEMA_VERSION_V17,
        RUNNER_SCHEMA_VERSION_V18,
        RUNNER_SCHEMA_VERSION_V19,
        RUNNER_SCHEMA_VERSION_V20,
        RUNNER_SCHEMA_VERSION_V21,
        RUNNER_SCHEMA_VERSION_V22,
        RUNNER_SCHEMA_VERSION_V23,
        RUNNER_SCHEMA_VERSION_V24,
        RUNNER_SCHEMA_VERSION_V25,
        RUNNER_SCHEMA_VERSION_V26,
        RUNNER_SCHEMA_VERSION_V27,
    RUNNER_SCHEMA_VERSION_V28,
    RUNNER_SCHEMA_VERSION_V29,
    RUNNER_SCHEMA_VERSION_V30,
    RUNNER_SCHEMA_VERSION_V31,
    RUNNER_SCHEMA_VERSION_V32,
    }:
        try:
            group_formation_mode = GroupFormationMode(
                _str_field(data, "group_formation_mode", path=path)
            )
        except RunnerSerializationError:
            raise
        except ValueError as exc:
            raise RunnerSerializationError(
                "invalid_enum", f"{path}.group_formation_mode"
            ) from exc
    if schema_version in {
        RUNNER_SCHEMA_VERSION_V17,
        RUNNER_SCHEMA_VERSION_V18,
        RUNNER_SCHEMA_VERSION_V19,
        RUNNER_SCHEMA_VERSION_V20,
        RUNNER_SCHEMA_VERSION_V21,
        RUNNER_SCHEMA_VERSION_V22,
        RUNNER_SCHEMA_VERSION_V23,
        RUNNER_SCHEMA_VERSION_V24,
        RUNNER_SCHEMA_VERSION_V25,
        RUNNER_SCHEMA_VERSION_V26,
        RUNNER_SCHEMA_VERSION_V27,
    RUNNER_SCHEMA_VERSION_V28,
    RUNNER_SCHEMA_VERSION_V29,
    RUNNER_SCHEMA_VERSION_V30,
    RUNNER_SCHEMA_VERSION_V31,
    RUNNER_SCHEMA_VERSION_V32,
    }:
        try:
            social_norm_mode = SocialNormMode(
                _str_field(data, "social_norm_mode", path=path)
            )
        except RunnerSerializationError:
            raise
        except ValueError as exc:
            raise RunnerSerializationError(
                "invalid_enum", f"{path}.social_norm_mode"
            ) from exc
    if schema_version in {
        RUNNER_SCHEMA_VERSION_V18,
        RUNNER_SCHEMA_VERSION_V19,
        RUNNER_SCHEMA_VERSION_V20,
        RUNNER_SCHEMA_VERSION_V21,
        RUNNER_SCHEMA_VERSION_V22,
        RUNNER_SCHEMA_VERSION_V23,
        RUNNER_SCHEMA_VERSION_V24,
        RUNNER_SCHEMA_VERSION_V25,
        RUNNER_SCHEMA_VERSION_V26,
        RUNNER_SCHEMA_VERSION_V27,
    RUNNER_SCHEMA_VERSION_V28,
    RUNNER_SCHEMA_VERSION_V29,
    RUNNER_SCHEMA_VERSION_V30,
    RUNNER_SCHEMA_VERSION_V31,
    RUNNER_SCHEMA_VERSION_V32,
    }:
        try:
            social_convention_mode = SocialConventionMode(
                _str_field(data, "social_convention_mode", path=path)
            )
        except RunnerSerializationError:
            raise
        except ValueError as exc:
            raise RunnerSerializationError(
                "invalid_enum", f"{path}.social_convention_mode"
            ) from exc
    if schema_version in {
        RUNNER_SCHEMA_VERSION_V19,
        RUNNER_SCHEMA_VERSION_V20,
        RUNNER_SCHEMA_VERSION_V21,
        RUNNER_SCHEMA_VERSION_V22,
        RUNNER_SCHEMA_VERSION_V23,
        RUNNER_SCHEMA_VERSION_V24,
        RUNNER_SCHEMA_VERSION_V25,
        RUNNER_SCHEMA_VERSION_V26,
        RUNNER_SCHEMA_VERSION_V27,
    RUNNER_SCHEMA_VERSION_V28,
    RUNNER_SCHEMA_VERSION_V29,
    RUNNER_SCHEMA_VERSION_V30,
    RUNNER_SCHEMA_VERSION_V31,
    RUNNER_SCHEMA_VERSION_V32,
    }:
        try:
            artifact_interpretation_mode = ArtifactInterpretationMode(
                _str_field(data, "artifact_interpretation_mode", path=path)
            )
        except RunnerSerializationError:
            raise
        except ValueError as exc:
            raise RunnerSerializationError(
                "invalid_enum", f"{path}.artifact_interpretation_mode"
            ) from exc
    cultural_narrative_mode = CulturalNarrativeMode.DISABLED
    if schema_version in {
        RUNNER_SCHEMA_VERSION_V20,
        RUNNER_SCHEMA_VERSION_V21,
        RUNNER_SCHEMA_VERSION_V22,
        RUNNER_SCHEMA_VERSION_V23,
        RUNNER_SCHEMA_VERSION_V24,
        RUNNER_SCHEMA_VERSION_V25,
        RUNNER_SCHEMA_VERSION_V26,
        RUNNER_SCHEMA_VERSION_V27,
    RUNNER_SCHEMA_VERSION_V28,
    RUNNER_SCHEMA_VERSION_V29,
    RUNNER_SCHEMA_VERSION_V30,
    RUNNER_SCHEMA_VERSION_V31,
    RUNNER_SCHEMA_VERSION_V32,
    }:
        try:
            semantic_naming_mode = SemanticNamingMode(
                _str_field(data, "semantic_naming_mode", path=path)
            )
        except RunnerSerializationError:
            raise
        except ValueError as exc:
            raise RunnerSerializationError(
                "invalid_enum", f"{path}.semantic_naming_mode"
            ) from exc
    if schema_version in {
        RUNNER_SCHEMA_VERSION_V21,
        RUNNER_SCHEMA_VERSION_V22,
        RUNNER_SCHEMA_VERSION_V23,
        RUNNER_SCHEMA_VERSION_V24,
        RUNNER_SCHEMA_VERSION_V25,
        RUNNER_SCHEMA_VERSION_V26,
        RUNNER_SCHEMA_VERSION_V27,
    RUNNER_SCHEMA_VERSION_V28,
    RUNNER_SCHEMA_VERSION_V29,
    RUNNER_SCHEMA_VERSION_V30,
    RUNNER_SCHEMA_VERSION_V31,
    RUNNER_SCHEMA_VERSION_V32,
    }:
        try:
            cultural_narrative_mode = CulturalNarrativeMode(
                _str_field(data, "cultural_narrative_mode", path=path)
            )
        except RunnerSerializationError:
            raise
        except ValueError as exc:
            raise RunnerSerializationError(
                "invalid_enum", f"{path}.cultural_narrative_mode"
            ) from exc
    cognitive_budget_mode = CognitiveBudgetMode.DISABLED
    cognitive_budget_limits: CognitiveBudgetLimits | None = None
    if schema_version in {
        RUNNER_SCHEMA_VERSION_V22,
        RUNNER_SCHEMA_VERSION_V23,
        RUNNER_SCHEMA_VERSION_V24,
        RUNNER_SCHEMA_VERSION_V25,
        RUNNER_SCHEMA_VERSION_V26,
        RUNNER_SCHEMA_VERSION_V27,
    RUNNER_SCHEMA_VERSION_V28,
    RUNNER_SCHEMA_VERSION_V29,
    RUNNER_SCHEMA_VERSION_V30,
    RUNNER_SCHEMA_VERSION_V31,
    RUNNER_SCHEMA_VERSION_V32,
    }:
        try:
            cognitive_budget_mode = CognitiveBudgetMode(
                _str_field(data, "cognitive_budget_mode", path=path)
            )
        except RunnerSerializationError:
            raise
        except ValueError as exc:
            raise RunnerSerializationError(
                "invalid_enum", f"{path}.cognitive_budget_mode"
            ) from exc
        if (
            schema_version
            in {
                RUNNER_SCHEMA_VERSION_V23,
                RUNNER_SCHEMA_VERSION_V24,
                RUNNER_SCHEMA_VERSION_V25,
                RUNNER_SCHEMA_VERSION_V26,
                RUNNER_SCHEMA_VERSION_V27,
            RUNNER_SCHEMA_VERSION_V28,
            RUNNER_SCHEMA_VERSION_V29,
            RUNNER_SCHEMA_VERSION_V30,
            RUNNER_SCHEMA_VERSION_V31,
            RUNNER_SCHEMA_VERSION_V32,
            }
            and cognitive_budget_mode is CognitiveBudgetMode.DISABLED
        ):
            for key in _BUDGET_LIMIT_KEYS:
                if data.get(key) is not None:
                    raise RunnerSerializationError(
                        "invalid_model", f"{path}.{key}"
                    )
            cognitive_budget_limits = None
        else:
            try:
                cognitive_budget_limits = CognitiveBudgetLimits(
                    max_llm_calls_per_tick=_nonneg_int_field(
                        data, "max_llm_calls_per_tick", path=path
                    ),
                    max_tokens_per_tick=_nonneg_int_field(
                        data, "max_tokens_per_tick", path=path
                    ),
                    max_imagination_branches=_nonneg_int_field(
                        data, "max_imagination_branches", path=path
                    ),
                    max_planning_depth=_nonneg_int_field(
                        data, "max_planning_depth", path=path
                    ),
                    max_recalled_memories=_nonneg_int_field(
                        data, "max_recalled_memories", path=path
                    ),
                    max_tom_targets=_nonneg_int_field(
                        data, "max_tom_targets", path=path
                    ),
                    reflection_interval_ticks=_nonneg_int_field(
                        data, "reflection_interval_ticks", path=path
                    ),
                    timeout_seconds=_required_float(
                        data, "timeout_seconds", path=path
                    ),
                )
            except RunnerSerializationError:
                raise
            except (TypeError, ValueError) as exc:
                raise RunnerSerializationError(
                    "invalid_model", f"{path}.cognitive_budget_limits"
                ) from exc
    overrides_raw = data["drive_overrides"]
    if not isinstance(overrides_raw, list):
        raise RunnerSerializationError("invalid_array", f"{path}.drive_overrides")
    overrides: list[DriveOverrideSpec] = []
    for index, item in enumerate(overrides_raw):
        if not isinstance(item, dict):
            raise RunnerSerializationError(
                "invalid_object", f"{path}.drive_overrides[{index}]"
            )
        overrides.append(
            _decode_drive_override(item, path=f"{path}.drive_overrides[{index}]")
        )
    try:
        return AgentCognitionSpec(
            agent_id=AgentId(_str_field(data, "agent_id", path=path)),
            memory_mode=MemoryMode(_str_field(data, "memory_mode", path=path)),
            imagination_mode=ImaginationMode(
                _str_field(data, "imagination_mode", path=path)
            ),
            drive_overrides=tuple(overrides),
            policy_version=_str_field(data, "policy_version", path=path),
            consolidation_mode=consolidation_mode,
            reflection_mode=reflection_mode,
            prospective_mode=prospective_mode,
            counterfactual_mode=counterfactual_mode,
            communication_strategy_mode=communication_strategy_mode,
            reputation_mode=reputation_mode,
            skill_learning_mode=skill_learning_mode,
            teaching_interaction_mode=teaching_interaction_mode,
            practice_rate=skill_rates.get("practice_rate", 0.02),
            success_rate=skill_rates.get("success_rate", 0.05),
            failure_rate=skill_rates.get("failure_rate", 0.01),
            instruction_rate=skill_rates.get("instruction_rate", 0.04),
            observation_rate=skill_rates.get("observation_rate", 0.01),
            probability_gain=skill_rates.get("probability_gain", 0.50),
            efficiency_gain=skill_rates.get("efficiency_gain", 0.50),
            belief_practice_rate=skill_rates.get("belief_practice_rate", 0.00),
            belief_success_rate=skill_rates.get("belief_success_rate", 0.10),
            belief_failure_rate=skill_rates.get("belief_failure_rate", 0.00),
            belief_instruction_rate=skill_rates.get("belief_instruction_rate", 0.08),
            belief_observation_rate=skill_rates.get("belief_observation_rate", 0.02),
            belief_prior=skill_rates.get("belief_prior", 1.0),
            belief_action_weight=skill_rates.get("belief_action_weight", 0.25),
            demonstration_rate=float(teaching_weights.get("demonstration_rate", 0.02)),
            practice_together_rate=float(
                teaching_weights.get("practice_together_rate", 0.02)
            ),
            offer_window=int(teaching_weights.get("offer_window", 8)),
            belief_explain_rate=float(
                teaching_weights.get("belief_explain_rate", 0.08)
            ),
            explain_low_below=float(teaching_weights.get("explain_low_below", 0.34)),
            explain_high_at=float(teaching_weights.get("explain_high_at", 0.67)),
            teaching_response_weight=float(
                teaching_weights.get("teaching_response_weight", 0.25)
            ),
            production_knowledge_mode=production_knowledge_mode,
            territorial_claim_mode=territorial_claim_mode,
            group_formation_mode=group_formation_mode,
            social_norm_mode=social_norm_mode,
            social_convention_mode=social_convention_mode,
            artifact_interpretation_mode=artifact_interpretation_mode,
            semantic_naming_mode=semantic_naming_mode,
            cultural_narrative_mode=cultural_narrative_mode,
            cognitive_budget_mode=cognitive_budget_mode,
            cognitive_budget_limits=cognitive_budget_limits,
            **(
                {}
                if production_catalog is None
                else {"production_catalog": production_catalog}
            ),
        )
    except RunnerSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise RunnerSerializationError("invalid_model", path) from exc


def _encode_agent(value: AgentRunnerSpec, *, schema_version: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "agent_id": value.agent_id.value,
        "cognition": _encode_cognition(value.cognition, schema_version=schema_version),
        "entity_id": value.entity_id.value,
    }
    if schema_version in {
        RUNNER_SCHEMA_VERSION_V2,
        RUNNER_SCHEMA_VERSION_V3,
        RUNNER_SCHEMA_VERSION_V4,
        RUNNER_SCHEMA_VERSION_V5,
        RUNNER_SCHEMA_VERSION_V6,
        RUNNER_SCHEMA_VERSION_V7,
        RUNNER_SCHEMA_VERSION_V8,
        RUNNER_SCHEMA_VERSION_V9,
        RUNNER_SCHEMA_VERSION_V10,
        RUNNER_SCHEMA_VERSION_V11,
        RUNNER_SCHEMA_VERSION_V12,
        RUNNER_SCHEMA_VERSION_V13,
        RUNNER_SCHEMA_VERSION_V14,
        RUNNER_SCHEMA_VERSION_V15,
        RUNNER_SCHEMA_VERSION_V16,
        RUNNER_SCHEMA_VERSION_V17,
        RUNNER_SCHEMA_VERSION_V18,
        RUNNER_SCHEMA_VERSION_V19,
        RUNNER_SCHEMA_VERSION_V20,
        RUNNER_SCHEMA_VERSION_V21,
        RUNNER_SCHEMA_VERSION_V22,
        RUNNER_SCHEMA_VERSION_V23,
        RUNNER_SCHEMA_VERSION_V24,
        RUNNER_SCHEMA_VERSION_V25,
        RUNNER_SCHEMA_VERSION_V26,
        RUNNER_SCHEMA_VERSION_V27,
    RUNNER_SCHEMA_VERSION_V28,
    RUNNER_SCHEMA_VERSION_V29,
    RUNNER_SCHEMA_VERSION_V30,
    RUNNER_SCHEMA_VERSION_V31,
    RUNNER_SCHEMA_VERSION_V32,
    }:
        assert value.name is not None
        payload["name"] = value.name
        payload["initial_goals"] = [_encode_goal(goal) for goal in value.initial_goals]
    return payload


def _decode_agent(
    data: dict[str, Any], *, path: str, schema_version: str
) -> AgentRunnerSpec:
    if schema_version == RUNNER_SCHEMA_VERSION_V1:
        _require_keys(data, {"agent_id", "entity_id", "cognition"}, path=path)
        cognition_raw = data["cognition"]
        if not isinstance(cognition_raw, dict):
            raise RunnerSerializationError("invalid_object", f"{path}.cognition")
        try:
            agent_id = AgentId(_str_field(data, "agent_id", path=path))
            # Explicit V1 upgrade: name defaults to agent_id; goals empty.
            return AgentRunnerSpec(
                agent_id=agent_id,
                entity_id=EntityId(_str_field(data, "entity_id", path=path)),
                cognition=_decode_cognition(
                    cognition_raw,
                    path=f"{path}.cognition",
                    schema_version=schema_version,
                ),
                name=agent_id.value,
                initial_goals=(),
            )
        except RunnerSerializationError:
            raise
        except (TypeError, ValueError) as exc:
            raise RunnerSerializationError("invalid_model", path) from exc

    _require_keys(
        data,
        {"agent_id", "entity_id", "cognition", "name", "initial_goals"},
        path=path,
    )
    cognition_raw = data["cognition"]
    if not isinstance(cognition_raw, dict):
        raise RunnerSerializationError("invalid_object", f"{path}.cognition")
    goals_raw = data["initial_goals"]
    if not isinstance(goals_raw, list):
        raise RunnerSerializationError("invalid_array", f"{path}.initial_goals")
    goals: list[Goal] = []
    for index, item in enumerate(goals_raw):
        if not isinstance(item, dict):
            raise RunnerSerializationError(
                "invalid_object", f"{path}.initial_goals[{index}]"
            )
        try:
            goals.append(_decode_goal(item, path=f"{path}.initial_goals[{index}]"))
        except DomainSerializationError as exc:
            raise _map_domain(exc) from exc
    try:
        return AgentRunnerSpec(
            agent_id=AgentId(_str_field(data, "agent_id", path=path)),
            entity_id=EntityId(_str_field(data, "entity_id", path=path)),
            cognition=_decode_cognition(
                cognition_raw,
                path=f"{path}.cognition",
                schema_version=schema_version,
            ),
            name=_str_field(data, "name", path=path),
            initial_goals=tuple(goals),
        )
    except RunnerSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise RunnerSerializationError("invalid_model", path) from exc


def _encode_scenario(value: WorldScenarioSpec) -> dict[str, Any]:
    try:
        return {
            "bodies": [_encode_agent_body(body) for body in value.bodies],
            "items": [_encode_item(item) for item in value.items],
            "locations": [_encode_location(loc) for loc in value.locations],
            "physical_rules": _encode_physical_rules(value.physical_rules),
            "resources": [_encode_resource(item) for item in value.resources],
            "revision": value.revision.value,
            "rules_fingerprint": physical_rules_fingerprint(value.physical_rules),
            "weather": [_encode_weather(item) for item in value.weather],
            "world_id": value.world_id.value,
        }
    except DomainSerializationError as exc:
        raise _map_domain(exc) from exc


def _decode_scenario(data: dict[str, Any], *, path: str) -> WorldScenarioSpec:
    _require_keys(
        data,
        {
            "world_id",
            "revision",
            "physical_rules",
            "rules_fingerprint",
            "locations",
            "bodies",
            "items",
            "resources",
            "weather",
        },
        path=path,
    )
    rules_raw = data["physical_rules"]
    if not isinstance(rules_raw, dict):
        raise RunnerSerializationError("invalid_object", f"{path}.physical_rules")
    try:
        rules = _decode_physical_rules(rules_raw, path=f"{path}.physical_rules")
    except DomainSerializationError as exc:
        raise _map_domain(exc) from exc
    expected = _str_field(data, "rules_fingerprint", path=path)
    if physical_rules_fingerprint(rules) != expected:
        raise RunnerSerializationError("hash_mismatch", f"{path}.rules_fingerprint")

    def _decode_list(key: str, decoder: Any) -> tuple[Any, ...]:
        raw = data[key]
        if not isinstance(raw, list):
            raise RunnerSerializationError("invalid_array", f"{path}.{key}")
        items: list[Any] = []
        for index, item in enumerate(raw):
            if not isinstance(item, dict):
                raise RunnerSerializationError(
                    "invalid_object", f"{path}.{key}[{index}]"
                )
            try:
                items.append(decoder(item, path=f"{path}.{key}[{index}]"))
            except DomainSerializationError as exc:
                raise _map_domain(exc) from exc
        return tuple(items)

    try:
        return WorldScenarioSpec(
            world_id=WorldId(_str_field(data, "world_id", path=path)),
            revision=WorldRevision(_nonneg_int_field(data, "revision", path=path)),
            physical_rules=rules,
            locations=_decode_list("locations", _decode_location),
            bodies=_decode_list("bodies", _decode_agent_body),
            items=_decode_list("items", _decode_item),
            resources=_decode_list("resources", _decode_resource),
            weather=_decode_list("weather", _decode_weather),
        )
    except RunnerSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise RunnerSerializationError("invalid_model", path) from exc


def _require_positive_number_field(
    data: Mapping[str, Any], key: str, *, path: str
) -> float:
    value = data[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RunnerSerializationError("invalid_number", f"{path}.{key}")
    number = float(value)
    if number != number or number in {float("inf"), float("-inf")} or number <= 0.0:
        raise RunnerSerializationError("invalid_number", f"{path}.{key}")
    return number


def _decode_recording_policy(raw: str, *, path: str) -> RecordingPolicy:
    """Decode recording policy; map legacy ``recorded`` → ``replay`` once."""
    global _RECORDED_ALIAS_WARNED
    value = raw
    if value == "recorded":
        if not _RECORDED_ALIAS_WARNED:
            _LOG.warning(
                "recording_policy_decode reason=recording_policy_recorded_alias"
            )
            _RECORDED_ALIAS_WARNED = True
        value = RecordingPolicy.REPLAY.value
    try:
        return RecordingPolicy(value)
    except ValueError as exc:
        raise RunnerSerializationError(
            "invalid_model", f"{path}.recording_policy"
        ) from exc


def _encode_provider(value: RunnerProviderSettings) -> dict[str, Any]:
    return {
        "adapter_kind": value.adapter_kind.value,
        "exact_reproducibility": value.exact_reproducibility.value,
        "max_header_bytes": value.max_header_bytes,
        "max_output_tokens": value.max_output_tokens,
        "max_request_bytes": value.max_request_bytes,
        "max_response_bytes": value.max_response_bytes,
        "model": value.model,
        "per_attempt_timeout_seconds": value.per_attempt_timeout_seconds,
        "provider_seed": value.provider_seed,
        "recording_policy": value.recording_policy.value,
        "retry_count": value.retry_count,
        "send_correlation_header": value.send_correlation_header,
        "settings_version": value.settings_version,
        "stop_sequences": list(value.stop_sequences),
        "structured_output_mode": value.structured_output_mode.value,
        "temperature": value.temperature,
        "top_p": value.top_p,
        "total_deadline_seconds": value.total_deadline_seconds,
    }


def _decode_provider(data: dict[str, Any], *, path: str) -> RunnerProviderSettings:
    required = {
        "adapter_kind",
        "model",
        "structured_output_mode",
        "temperature",
        "top_p",
        "provider_seed",
        "max_output_tokens",
        "stop_sequences",
        "retry_count",
        "per_attempt_timeout_seconds",
        "total_deadline_seconds",
        "max_request_bytes",
        "max_response_bytes",
        "max_header_bytes",
        "send_correlation_header",
        "recording_policy",
        "exact_reproducibility",
        "settings_version",
    }
    _require_keys(data, required, path=path)
    if any(key in data for key in ("api_key", "base_url", "endpoint", "authorization")):
        raise RunnerSerializationError("credentials_forbidden", path)
    stops_raw = data["stop_sequences"]
    if not isinstance(stops_raw, list):
        raise RunnerSerializationError("invalid_array", f"{path}.stop_sequences")
    stops: list[str] = []
    for index, item in enumerate(stops_raw):
        if not isinstance(item, str):
            raise RunnerSerializationError(
                "invalid_string", f"{path}.stop_sequences[{index}]"
            )
        stops.append(item)
    model = data["model"]
    if model is not None and not isinstance(model, str):
        raise RunnerSerializationError("invalid_string", f"{path}.model")
    max_output = data["max_output_tokens"]
    provider_seed = data["provider_seed"]
    try:
        return RunnerProviderSettings(
            adapter_kind=ProviderAdapterKind(
                _str_field(data, "adapter_kind", path=path)
            ),
            model=model,
            structured_output_mode=StructuredOutputMode(
                _str_field(data, "structured_output_mode", path=path)
            ),
            temperature=_optional_float(data, "temperature", path=path),
            top_p=_optional_float(data, "top_p", path=path),
            provider_seed=(
                None
                if provider_seed is None
                else _nonneg_int_field(data, "provider_seed", path=path)
            ),
            max_output_tokens=(
                None
                if max_output is None
                else _nonneg_int_field(data, "max_output_tokens", path=path)
            ),
            stop_sequences=tuple(stops),
            retry_count=_nonneg_int_field(data, "retry_count", path=path),
            per_attempt_timeout_seconds=_require_positive_number_field(
                data, "per_attempt_timeout_seconds", path=path
            ),
            total_deadline_seconds=_optional_float(
                data, "total_deadline_seconds", path=path
            ),
            max_request_bytes=_nonneg_int_field(data, "max_request_bytes", path=path),
            max_response_bytes=_nonneg_int_field(data, "max_response_bytes", path=path),
            max_header_bytes=_nonneg_int_field(data, "max_header_bytes", path=path),
            send_correlation_header=_bool_field(
                data, "send_correlation_header", path=path
            ),
            recording_policy=_decode_recording_policy(
                _str_field(data, "recording_policy", path=path),
                path=path,
            ),
            exact_reproducibility=ExactReproducibilityMode(
                _str_field(data, "exact_reproducibility", path=path)
            ),
            settings_version=_str_field(data, "settings_version", path=path),
        )
    except RunnerSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise RunnerSerializationError("invalid_model", path) from exc


_RUNNER_ROOT_KEYS_LEGACY: Final[set[str]] = {
    "schema_version",
    "derivation_version",
    "seed",
    "stochastic_identity",
    "scenario",
    "agents",
    "stop_policy",
    "mortality_mode",
    "mortality_policy_version",
    "cognition_failure_policy",
    "provider",
    "persistence",
    "experiment",
}
_RUNNER_ROOT_KEYS_V3: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_LEGACY,
    "capability_flags",
}
_RUNNER_ROOT_KEYS_V4: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V3,
    "cognition_trace",
}
_RUNNER_ROOT_KEYS_V14: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V4,
    "environmental_dynamics",
}
_RUNNER_ROOT_KEYS_V23: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V4,
    "v3_capability_flags",
}
_RUNNER_ROOT_KEYS_V23_WITH_DYNAMICS: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V14,
    "v3_capability_flags",
}
_RUNNER_ROOT_KEYS_V24: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V23,
    "population_lifecycle",
}
_RUNNER_ROOT_KEYS_V24_WITH_DYNAMICS: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V23_WITH_DYNAMICS,
    "population_lifecycle",
}
_RUNNER_ROOT_KEYS_V25: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V24,
    "new_agent_initialization",
}
_RUNNER_ROOT_KEYS_V25_WITH_DYNAMICS: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V24_WITH_DYNAMICS,
    "new_agent_initialization",
}
_RUNNER_ROOT_KEYS_V26: Final[set[str]] = set(_RUNNER_ROOT_KEYS_V25)
_RUNNER_ROOT_KEYS_V26_WITH_DYNAMICS: Final[set[str]] = set(
    _RUNNER_ROOT_KEYS_V25_WITH_DYNAMICS
)
_RUNNER_ROOT_KEYS_V27_KINSHIP_ONLY: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V23,
    "kinship",
}
_RUNNER_ROOT_KEYS_V27_KINSHIP_ONLY_WITH_DYNAMICS: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V23_WITH_DYNAMICS,
    "kinship",
}
_RUNNER_ROOT_KEYS_V27_WITH_LIFECYCLE: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V26,
    "kinship",
}
_RUNNER_ROOT_KEYS_V27_WITH_LIFECYCLE_AND_DYNAMICS: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V26_WITH_DYNAMICS,
    "kinship",
}
_RUNNER_ROOT_KEYS_V28_KINSHIP_ONLY: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V27_KINSHIP_ONLY,
}
_RUNNER_ROOT_KEYS_V28_KINSHIP_ONLY_WITH_DYNAMICS: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V27_KINSHIP_ONLY_WITH_DYNAMICS,
}
_RUNNER_ROOT_KEYS_V28_WITH_LIFECYCLE: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V27_WITH_LIFECYCLE,
    "dependency_care",
}
_RUNNER_ROOT_KEYS_V28_WITH_LIFECYCLE_AND_DYNAMICS: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V27_WITH_LIFECYCLE_AND_DYNAMICS,
    "dependency_care",
}
_RUNNER_ROOT_KEYS_V28_WITH_LIFECYCLE_NO_KINSHIP: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V26,
    "dependency_care",
}
_RUNNER_ROOT_KEYS_V28_WITH_LIFECYCLE_NO_KINSHIP_AND_DYNAMICS: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V26_WITH_DYNAMICS,
    "dependency_care",
}
_RUNNER_ROOT_KEYS_V29_WITH_LIFECYCLE: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V28_WITH_LIFECYCLE,
    "developmental_learning",
}
_RUNNER_ROOT_KEYS_V29_WITH_LIFECYCLE_AND_DYNAMICS: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V28_WITH_LIFECYCLE_AND_DYNAMICS,
    "developmental_learning",
}
_RUNNER_ROOT_KEYS_V29_WITH_LIFECYCLE_NO_KINSHIP: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V28_WITH_LIFECYCLE_NO_KINSHIP,
    "developmental_learning",
}
_RUNNER_ROOT_KEYS_V29_WITH_LIFECYCLE_NO_KINSHIP_AND_DYNAMICS: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V28_WITH_LIFECYCLE_NO_KINSHIP_AND_DYNAMICS,
    "developmental_learning",
}
_RUNNER_ROOT_KEYS_V29_NO_DEPENDENCY_CARE: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V27_WITH_LIFECYCLE,
    "developmental_learning",
}
_RUNNER_ROOT_KEYS_V29_NO_DEPENDENCY_CARE_AND_DYNAMICS: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V27_WITH_LIFECYCLE_AND_DYNAMICS,
    "developmental_learning",
}
_RUNNER_ROOT_KEYS_V29_NO_DEPENDENCY_CARE_NO_KINSHIP: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V26,
    "developmental_learning",
}
_RUNNER_ROOT_KEYS_V29_NO_DEPENDENCY_CARE_NO_KINSHIP_AND_DYNAMICS: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V26_WITH_DYNAMICS,
    "developmental_learning",
}
# v30 = v29 accepted roots U mentorship; developmental_learning optional on v30.
_RUNNER_ROOT_KEYS_V30_WITH_LIFECYCLE: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V29_WITH_LIFECYCLE,
    "mentorship",
}
_RUNNER_ROOT_KEYS_V30_WITH_LIFECYCLE_AND_DYNAMICS: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V29_WITH_LIFECYCLE_AND_DYNAMICS,
    "mentorship",
}
_RUNNER_ROOT_KEYS_V30_WITH_LIFECYCLE_NO_KINSHIP: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V29_WITH_LIFECYCLE_NO_KINSHIP,
    "mentorship",
}
_RUNNER_ROOT_KEYS_V30_WITH_LIFECYCLE_NO_KINSHIP_AND_DYNAMICS: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V29_WITH_LIFECYCLE_NO_KINSHIP_AND_DYNAMICS,
    "mentorship",
}
_RUNNER_ROOT_KEYS_V30_NO_DEPENDENCY_CARE: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V29_NO_DEPENDENCY_CARE,
    "mentorship",
}
_RUNNER_ROOT_KEYS_V30_NO_DEPENDENCY_CARE_AND_DYNAMICS: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V29_NO_DEPENDENCY_CARE_AND_DYNAMICS,
    "mentorship",
}
_RUNNER_ROOT_KEYS_V30_NO_DEPENDENCY_CARE_NO_KINSHIP: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V29_NO_DEPENDENCY_CARE_NO_KINSHIP,
    "mentorship",
}
_RUNNER_ROOT_KEYS_V30_NO_DEPENDENCY_CARE_NO_KINSHIP_AND_DYNAMICS: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V29_NO_DEPENDENCY_CARE_NO_KINSHIP_AND_DYNAMICS,
    "mentorship",
}
_RUNNER_ROOT_KEYS_V30_NO_DEV_WITH_LIFECYCLE: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V28_WITH_LIFECYCLE,
    "mentorship",
}
_RUNNER_ROOT_KEYS_V30_NO_DEV_WITH_LIFECYCLE_AND_DYNAMICS: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V28_WITH_LIFECYCLE_AND_DYNAMICS,
    "mentorship",
}
_RUNNER_ROOT_KEYS_V30_NO_DEV_WITH_LIFECYCLE_NO_KINSHIP: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V28_WITH_LIFECYCLE_NO_KINSHIP,
    "mentorship",
}
_RUNNER_ROOT_KEYS_V30_NO_DEV_WITH_LIFECYCLE_NO_KINSHIP_AND_DYNAMICS: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V28_WITH_LIFECYCLE_NO_KINSHIP_AND_DYNAMICS,
    "mentorship",
}
_RUNNER_ROOT_KEYS_V30_NO_DEV_NO_DEPENDENCY_CARE: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V27_WITH_LIFECYCLE,
    "mentorship",
}
_RUNNER_ROOT_KEYS_V30_NO_DEV_NO_DEPENDENCY_CARE_AND_DYNAMICS: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V27_WITH_LIFECYCLE_AND_DYNAMICS,
    "mentorship",
}
_RUNNER_ROOT_KEYS_V30_NO_DEV_NO_DEPENDENCY_CARE_NO_KINSHIP: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V26,
    "mentorship",
}
_RUNNER_ROOT_KEYS_V30_NO_DEV_NO_DEPENDENCY_CARE_NO_KINSHIP_AND_DYNAMICS: Final[
    set[str]
] = {
    *_RUNNER_ROOT_KEYS_V26_WITH_DYNAMICS,
    "mentorship",
}
# v31 = v30 accepted roots U cultural_feature_provenance; mentorship optional on v31.
_RUNNER_ROOT_KEYS_V31_WITH_LIFECYCLE: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V30_WITH_LIFECYCLE,
    "cultural_feature_provenance",
}
_RUNNER_ROOT_KEYS_V31_WITH_LIFECYCLE_AND_DYNAMICS: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V30_WITH_LIFECYCLE_AND_DYNAMICS,
    "cultural_feature_provenance",
}
_RUNNER_ROOT_KEYS_V31_WITH_LIFECYCLE_NO_KINSHIP: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V30_WITH_LIFECYCLE_NO_KINSHIP,
    "cultural_feature_provenance",
}
_RUNNER_ROOT_KEYS_V31_WITH_LIFECYCLE_NO_KINSHIP_AND_DYNAMICS: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V30_WITH_LIFECYCLE_NO_KINSHIP_AND_DYNAMICS,
    "cultural_feature_provenance",
}
_RUNNER_ROOT_KEYS_V31_NO_DEPENDENCY_CARE: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V30_NO_DEPENDENCY_CARE,
    "cultural_feature_provenance",
}
_RUNNER_ROOT_KEYS_V31_NO_DEPENDENCY_CARE_AND_DYNAMICS: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V30_NO_DEPENDENCY_CARE_AND_DYNAMICS,
    "cultural_feature_provenance",
}
_RUNNER_ROOT_KEYS_V31_NO_DEPENDENCY_CARE_NO_KINSHIP: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V30_NO_DEPENDENCY_CARE_NO_KINSHIP,
    "cultural_feature_provenance",
}
_RUNNER_ROOT_KEYS_V31_NO_DEPENDENCY_CARE_NO_KINSHIP_AND_DYNAMICS: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V30_NO_DEPENDENCY_CARE_NO_KINSHIP_AND_DYNAMICS,
    "cultural_feature_provenance",
}
_RUNNER_ROOT_KEYS_V31_NO_DEV_WITH_LIFECYCLE: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V30_NO_DEV_WITH_LIFECYCLE,
    "cultural_feature_provenance",
}
_RUNNER_ROOT_KEYS_V31_NO_DEV_WITH_LIFECYCLE_AND_DYNAMICS: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V30_NO_DEV_WITH_LIFECYCLE_AND_DYNAMICS,
    "cultural_feature_provenance",
}
_RUNNER_ROOT_KEYS_V31_NO_DEV_WITH_LIFECYCLE_NO_KINSHIP: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V30_NO_DEV_WITH_LIFECYCLE_NO_KINSHIP,
    "cultural_feature_provenance",
}
_RUNNER_ROOT_KEYS_V31_NO_DEV_WITH_LIFECYCLE_NO_KINSHIP_AND_DYNAMICS: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V30_NO_DEV_WITH_LIFECYCLE_NO_KINSHIP_AND_DYNAMICS,
    "cultural_feature_provenance",
}
_RUNNER_ROOT_KEYS_V31_NO_DEV_NO_DEPENDENCY_CARE: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V30_NO_DEV_NO_DEPENDENCY_CARE,
    "cultural_feature_provenance",
}
_RUNNER_ROOT_KEYS_V31_NO_DEV_NO_DEPENDENCY_CARE_AND_DYNAMICS: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V30_NO_DEV_NO_DEPENDENCY_CARE_AND_DYNAMICS,
    "cultural_feature_provenance",
}
_RUNNER_ROOT_KEYS_V31_NO_DEV_NO_DEPENDENCY_CARE_NO_KINSHIP: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V30_NO_DEV_NO_DEPENDENCY_CARE_NO_KINSHIP,
    "cultural_feature_provenance",
}
_RUNNER_ROOT_KEYS_V31_NO_DEV_NO_DEPENDENCY_CARE_NO_KINSHIP_AND_DYNAMICS: Final[
    set[str]
] = {
    *_RUNNER_ROOT_KEYS_V30_NO_DEV_NO_DEPENDENCY_CARE_NO_KINSHIP_AND_DYNAMICS,
    "cultural_feature_provenance",
}
# v31 without mentorship = v29 roots U cultural_feature_provenance
_RUNNER_ROOT_KEYS_V31_NO_MENTORSHIP_WITH_LIFECYCLE: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V29_WITH_LIFECYCLE,
    "cultural_feature_provenance",
}
_RUNNER_ROOT_KEYS_V31_NO_MENTORSHIP_WITH_LIFECYCLE_AND_DYNAMICS: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V29_WITH_LIFECYCLE_AND_DYNAMICS,
    "cultural_feature_provenance",
}
_RUNNER_ROOT_KEYS_V31_NO_MENTORSHIP_WITH_LIFECYCLE_NO_KINSHIP: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V29_WITH_LIFECYCLE_NO_KINSHIP,
    "cultural_feature_provenance",
}
_RUNNER_ROOT_KEYS_V31_NO_MENTORSHIP_WITH_LIFECYCLE_NO_KINSHIP_AND_DYNAMICS: Final[
    set[str]
] = {
    *_RUNNER_ROOT_KEYS_V29_WITH_LIFECYCLE_NO_KINSHIP_AND_DYNAMICS,
    "cultural_feature_provenance",
}
_RUNNER_ROOT_KEYS_V31_NO_MENTORSHIP_NO_DEPENDENCY_CARE: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V29_NO_DEPENDENCY_CARE,
    "cultural_feature_provenance",
}
_RUNNER_ROOT_KEYS_V31_NO_MENTORSHIP_NO_DEPENDENCY_CARE_AND_DYNAMICS: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V29_NO_DEPENDENCY_CARE_AND_DYNAMICS,
    "cultural_feature_provenance",
}
_RUNNER_ROOT_KEYS_V31_NO_MENTORSHIP_NO_DEPENDENCY_CARE_NO_KINSHIP: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V29_NO_DEPENDENCY_CARE_NO_KINSHIP,
    "cultural_feature_provenance",
}
_RUNNER_ROOT_KEYS_V31_NO_MENTORSHIP_NO_DEPENDENCY_CARE_NO_KINSHIP_AND_DYNAMICS: Final[
    set[str]
] = {
    *_RUNNER_ROOT_KEYS_V29_NO_DEPENDENCY_CARE_NO_KINSHIP_AND_DYNAMICS,
    "cultural_feature_provenance",
}
_RUNNER_ROOT_KEYS_V31_NO_MENTORSHIP_NO_DEV_WITH_LIFECYCLE: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V28_WITH_LIFECYCLE,
    "cultural_feature_provenance",
}
_RUNNER_ROOT_KEYS_V31_NO_MENTORSHIP_NO_DEV_WITH_LIFECYCLE_AND_DYNAMICS: Final[
    set[str]
] = {
    *_RUNNER_ROOT_KEYS_V28_WITH_LIFECYCLE_AND_DYNAMICS,
    "cultural_feature_provenance",
}
_RUNNER_ROOT_KEYS_V31_NO_MENTORSHIP_NO_DEV_WITH_LIFECYCLE_NO_KINSHIP: Final[
    set[str]
] = {
    *_RUNNER_ROOT_KEYS_V28_WITH_LIFECYCLE_NO_KINSHIP,
    "cultural_feature_provenance",
}
_RUNNER_ROOT_KEYS_V31_NO_MENTORSHIP_NO_DEV_WITH_LIFECYCLE_NO_KINSHIP_AND_DYNAMICS: Final[  # noqa: E501
    set[str]
] = {
    *_RUNNER_ROOT_KEYS_V28_WITH_LIFECYCLE_NO_KINSHIP_AND_DYNAMICS,
    "cultural_feature_provenance",
}
_RUNNER_ROOT_KEYS_V31_NO_MENTORSHIP_NO_DEV_NO_DEPENDENCY_CARE: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V27_WITH_LIFECYCLE,
    "cultural_feature_provenance",
}
_RUNNER_ROOT_KEYS_V31_NO_MENTORSHIP_NO_DEV_NO_DEPENDENCY_CARE_AND_DYNAMICS: Final[
    set[str]
] = {
    *_RUNNER_ROOT_KEYS_V27_WITH_LIFECYCLE_AND_DYNAMICS,
    "cultural_feature_provenance",
}
_RUNNER_ROOT_KEYS_V31_NO_MENTORSHIP_NO_DEV_NO_DEPENDENCY_CARE_NO_KINSHIP: Final[
    set[str]
] = {
    *_RUNNER_ROOT_KEYS_V26,
    "cultural_feature_provenance",
}
_RUNNER_ROOT_KEYS_V31_NO_MENTORSHIP_NO_DEV_NO_DEPENDENCY_CARE_NO_KINSHIP_AND_DYNAMICS: (
    Final[set[str]]
) = {
    *_RUNNER_ROOT_KEYS_V26_WITH_DYNAMICS,
    "cultural_feature_provenance",
}
# Cultural-only (no lifecycle/init) +/- kinship +/- dynamics
_RUNNER_ROOT_KEYS_V31_CULTURAL_ONLY: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V23,
    "cultural_feature_provenance",
}
_RUNNER_ROOT_KEYS_V31_CULTURAL_ONLY_WITH_DYNAMICS: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V23_WITH_DYNAMICS,
    "cultural_feature_provenance",
}
_RUNNER_ROOT_KEYS_V31_CULTURAL_KINSHIP_ONLY: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V27_KINSHIP_ONLY,
    "cultural_feature_provenance",
}
_RUNNER_ROOT_KEYS_V31_CULTURAL_KINSHIP_ONLY_WITH_DYNAMICS: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V27_KINSHIP_ONLY_WITH_DYNAMICS,
    "cultural_feature_provenance",
}
# v32 = v31 accepted roots U historical_memory_layers
_RUNNER_ROOT_KEYS_V32_WITH_LIFECYCLE: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V31_WITH_LIFECYCLE,
    "historical_memory_layers",
}
_RUNNER_ROOT_KEYS_V32_WITH_LIFECYCLE_AND_DYNAMICS: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V31_WITH_LIFECYCLE_AND_DYNAMICS,
    "historical_memory_layers",
}
_RUNNER_ROOT_KEYS_V32_WITH_LIFECYCLE_NO_KINSHIP: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V31_WITH_LIFECYCLE_NO_KINSHIP,
    "historical_memory_layers",
}
_RUNNER_ROOT_KEYS_V32_WITH_LIFECYCLE_NO_KINSHIP_AND_DYNAMICS: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V31_WITH_LIFECYCLE_NO_KINSHIP_AND_DYNAMICS,
    "historical_memory_layers",
}
_RUNNER_ROOT_KEYS_V32_NO_DEPENDENCY_CARE: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V31_NO_DEPENDENCY_CARE,
    "historical_memory_layers",
}
_RUNNER_ROOT_KEYS_V32_NO_DEPENDENCY_CARE_AND_DYNAMICS: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V31_NO_DEPENDENCY_CARE_AND_DYNAMICS,
    "historical_memory_layers",
}
_RUNNER_ROOT_KEYS_V32_NO_DEPENDENCY_CARE_NO_KINSHIP: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V31_NO_DEPENDENCY_CARE_NO_KINSHIP,
    "historical_memory_layers",
}
_RUNNER_ROOT_KEYS_V32_NO_DEPENDENCY_CARE_NO_KINSHIP_AND_DYNAMICS: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V31_NO_DEPENDENCY_CARE_NO_KINSHIP_AND_DYNAMICS,
    "historical_memory_layers",
}
_RUNNER_ROOT_KEYS_V32_NO_DEV_WITH_LIFECYCLE: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V31_NO_DEV_WITH_LIFECYCLE,
    "historical_memory_layers",
}
_RUNNER_ROOT_KEYS_V32_NO_DEV_WITH_LIFECYCLE_AND_DYNAMICS: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V31_NO_DEV_WITH_LIFECYCLE_AND_DYNAMICS,
    "historical_memory_layers",
}
_RUNNER_ROOT_KEYS_V32_NO_DEV_WITH_LIFECYCLE_NO_KINSHIP: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V31_NO_DEV_WITH_LIFECYCLE_NO_KINSHIP,
    "historical_memory_layers",
}
_RUNNER_ROOT_KEYS_V32_NO_DEV_WITH_LIFECYCLE_NO_KINSHIP_AND_DYNAMICS: Final[
    set[str]
] = {
    *_RUNNER_ROOT_KEYS_V31_NO_DEV_WITH_LIFECYCLE_NO_KINSHIP_AND_DYNAMICS,
    "historical_memory_layers",
}
_RUNNER_ROOT_KEYS_V32_NO_DEV_NO_DEPENDENCY_CARE: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V31_NO_DEV_NO_DEPENDENCY_CARE,
    "historical_memory_layers",
}
_RUNNER_ROOT_KEYS_V32_NO_DEV_NO_DEPENDENCY_CARE_AND_DYNAMICS: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V31_NO_DEV_NO_DEPENDENCY_CARE_AND_DYNAMICS,
    "historical_memory_layers",
}
_RUNNER_ROOT_KEYS_V32_NO_DEV_NO_DEPENDENCY_CARE_NO_KINSHIP: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V31_NO_DEV_NO_DEPENDENCY_CARE_NO_KINSHIP,
    "historical_memory_layers",
}
_RUNNER_ROOT_KEYS_V32_NO_DEV_NO_DEPENDENCY_CARE_NO_KINSHIP_AND_DYNAMICS: Final[
    set[str]
] = {
    *_RUNNER_ROOT_KEYS_V31_NO_DEV_NO_DEPENDENCY_CARE_NO_KINSHIP_AND_DYNAMICS,
    "historical_memory_layers",
}
_RUNNER_ROOT_KEYS_V32_NO_MENTORSHIP_WITH_LIFECYCLE: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V31_NO_MENTORSHIP_WITH_LIFECYCLE,
    "historical_memory_layers",
}
_RUNNER_ROOT_KEYS_V32_NO_MENTORSHIP_WITH_LIFECYCLE_AND_DYNAMICS: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V31_NO_MENTORSHIP_WITH_LIFECYCLE_AND_DYNAMICS,
    "historical_memory_layers",
}
_RUNNER_ROOT_KEYS_V32_NO_MENTORSHIP_WITH_LIFECYCLE_NO_KINSHIP: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V31_NO_MENTORSHIP_WITH_LIFECYCLE_NO_KINSHIP,
    "historical_memory_layers",
}
_RUNNER_ROOT_KEYS_V32_NO_MENTORSHIP_WITH_LIFECYCLE_NO_KINSHIP_AND_DYNAMICS: Final[
    set[str]
] = {
    *_RUNNER_ROOT_KEYS_V31_NO_MENTORSHIP_WITH_LIFECYCLE_NO_KINSHIP_AND_DYNAMICS,
    "historical_memory_layers",
}
_RUNNER_ROOT_KEYS_V32_NO_MENTORSHIP_NO_DEPENDENCY_CARE: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V31_NO_MENTORSHIP_NO_DEPENDENCY_CARE,
    "historical_memory_layers",
}
_RUNNER_ROOT_KEYS_V32_NO_MENTORSHIP_NO_DEPENDENCY_CARE_AND_DYNAMICS: Final[
    set[str]
] = {
    *_RUNNER_ROOT_KEYS_V31_NO_MENTORSHIP_NO_DEPENDENCY_CARE_AND_DYNAMICS,
    "historical_memory_layers",
}
_RUNNER_ROOT_KEYS_V32_NO_MENTORSHIP_NO_DEPENDENCY_CARE_NO_KINSHIP: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V31_NO_MENTORSHIP_NO_DEPENDENCY_CARE_NO_KINSHIP,
    "historical_memory_layers",
}
_RUNNER_ROOT_KEYS_V32_NO_MENTORSHIP_NO_DEPENDENCY_CARE_NO_KINSHIP_AND_DYNAMICS: Final[
    set[str]
] = {
    *_RUNNER_ROOT_KEYS_V31_NO_MENTORSHIP_NO_DEPENDENCY_CARE_NO_KINSHIP_AND_DYNAMICS,
    "historical_memory_layers",
}
_RUNNER_ROOT_KEYS_V32_NO_MENTORSHIP_NO_DEV_WITH_LIFECYCLE: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V31_NO_MENTORSHIP_NO_DEV_WITH_LIFECYCLE,
    "historical_memory_layers",
}
_RUNNER_ROOT_KEYS_V32_NO_MENTORSHIP_NO_DEV_WITH_LIFECYCLE_AND_DYNAMICS: Final[
    set[str]
] = {
    *_RUNNER_ROOT_KEYS_V31_NO_MENTORSHIP_NO_DEV_WITH_LIFECYCLE_AND_DYNAMICS,
    "historical_memory_layers",
}
_RUNNER_ROOT_KEYS_V32_NO_MENTORSHIP_NO_DEV_WITH_LIFECYCLE_NO_KINSHIP: Final[
    set[str]
] = {
    *_RUNNER_ROOT_KEYS_V31_NO_MENTORSHIP_NO_DEV_WITH_LIFECYCLE_NO_KINSHIP,
    "historical_memory_layers",
}
_RUNNER_ROOT_KEYS_V32_NO_MENTORSHIP_NO_DEV_WITH_LIFECYCLE_NO_KINSHIP_AND_DYNAMICS: Final[  # noqa: E501
    set[str]
] = {
    *_RUNNER_ROOT_KEYS_V31_NO_MENTORSHIP_NO_DEV_WITH_LIFECYCLE_NO_KINSHIP_AND_DYNAMICS,
    "historical_memory_layers",
}
_RUNNER_ROOT_KEYS_V32_NO_MENTORSHIP_NO_DEV_NO_DEPENDENCY_CARE: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V31_NO_MENTORSHIP_NO_DEV_NO_DEPENDENCY_CARE,
    "historical_memory_layers",
}
_RUNNER_ROOT_KEYS_V32_NO_MENTORSHIP_NO_DEV_NO_DEPENDENCY_CARE_AND_DYNAMICS: Final[
    set[str]
] = {
    *_RUNNER_ROOT_KEYS_V31_NO_MENTORSHIP_NO_DEV_NO_DEPENDENCY_CARE_AND_DYNAMICS,
    "historical_memory_layers",
}
_RUNNER_ROOT_KEYS_V32_NO_MENTORSHIP_NO_DEV_NO_DEPENDENCY_CARE_NO_KINSHIP: Final[
    set[str]
] = {
    *_RUNNER_ROOT_KEYS_V31_NO_MENTORSHIP_NO_DEV_NO_DEPENDENCY_CARE_NO_KINSHIP,
    "historical_memory_layers",
}
_RUNNER_ROOT_KEYS_V32_NO_MENTORSHIP_NO_DEV_NO_DEPENDENCY_CARE_NO_KINSHIP_AND_DYNAMICS: Final[  # noqa: E501
    set[str]
] = {
    *_RUNNER_ROOT_KEYS_V31_NO_MENTORSHIP_NO_DEV_NO_DEPENDENCY_CARE_NO_KINSHIP_AND_DYNAMICS,
    "historical_memory_layers",
}
_RUNNER_ROOT_KEYS_V32_CULTURAL_ONLY: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V31_CULTURAL_ONLY,
    "historical_memory_layers",
}
_RUNNER_ROOT_KEYS_V32_CULTURAL_ONLY_WITH_DYNAMICS: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V31_CULTURAL_ONLY_WITH_DYNAMICS,
    "historical_memory_layers",
}
_RUNNER_ROOT_KEYS_V32_CULTURAL_KINSHIP_ONLY: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V31_CULTURAL_KINSHIP_ONLY,
    "historical_memory_layers",
}
_RUNNER_ROOT_KEYS_V32_CULTURAL_KINSHIP_ONLY_WITH_DYNAMICS: Final[set[str]] = {
    *_RUNNER_ROOT_KEYS_V31_CULTURAL_KINSHIP_ONLY_WITH_DYNAMICS,
    "historical_memory_layers",
}
_HISTORICAL_MEMORY_LAYERS_KEYS: Final[set[str]] = {
    "mode",
    "max_communicative_hops",
    "witness_definition",
    "include_narrative_lineage",
    "include_cultural_features",
    "include_artifact_edges",
    "include_teaching_edges",
    "generation_distance_weight",
    "query_event_selector",
    "transition_tick_resolution",
    "applicability",
}
_HISTORICAL_MEMORY_FORBIDDEN_ALIASES: Final[set[str]] = {
    "inject_into_agents",
    "label_agent_memories",
    "assmann_cognition_mode",
    "auto_layer_beliefs",
    "assmann_label_for_agent",
    "agent_memory_class",
    "self_knowledge_layer",
    "lived_experience_flag",
    "living_memory",
    "communicative_memory",
    "cultural_memory",
    "society_memory_tier",
}
_CULTURAL_FEATURE_PROVENANCE_KEYS: Final[set[str]] = {
    "enabled_feature_kinds",
    "enabled_provenance_channels",
    "mutation_policy",
    "recombination_policy",
    "uptake_compose",
    "bias_policy",
    "cultural_feature_mode",
    "max_beliefs_per_owner",
    "max_evidence_refs",
    "applicability",
}
_CULTURAL_FEATURE_MUTATION_POLICY_KEYS: Final[set[str]] = {
    "allow_mutation",
    "mutation_requires_evidence",
    "max_token_edits",
    "rng_namespace",
}
_CULTURAL_FEATURE_RECOMBINATION_POLICY_KEYS: Final[set[str]] = {
    "allow_recombination",
    "max_parents",
    "min_token_overlap",
}
_CULTURAL_FEATURE_UPTAKE_COMPOSE_KEYS: Final[set[str]] = {
    "naming",
    "narrative",
    "norms",
    "conventions",
    "teaching",
    "artifacts",
    "mentorship",
}
_CULTURAL_FEATURE_BIAS_POLICY_KEYS: Final[set[str]] = {
    "mode",
    "communicate_weight",
    "content_affinity",
}
_MENTORSHIP_KEYS: Final[set[str]] = {
    "enabled_content_kinds",
    "bond_policy",
    "lineage_policy",
    "partner_bias",
    "mentorship_mode",
    "requires_teaching_interaction",
    "max_bonds_per_owner",
    "max_lineage_entries_per_owner",
    "applicability",
}
_MENTORSHIP_BOND_POLICY_KEYS: Final[set[str]] = {
    "form_after_successful_acts",
    "min_trust",
    "reinforce_on_learning_evidence",
    "decay_per_tick",
    "offer_window_extend",
    "symmetric",
}
_MENTORSHIP_LINEAGE_POLICY_KEYS: Final[set[str]] = {
    "max_hop_depth",
    "record_attempts",
    "allow_learner_mutation",
    "mutation_requires_evidence",
    "confidence_inherit_mode",
}
_MENTORSHIP_PARTNER_BIAS_KEYS: Final[set[str]] = {
    "mode",
    "communicate_weight",
    "content_kind_affinity",
}
_DEVELOPMENTAL_LEARNING_KEYS: Final[set[str]] = {
    "enabled_domains",
    "enabled_sources",
    "domain_rates",
    "source_weights",
    "applicability",
    "cognitive_budget_coupling",
    "developmental_learning_mode",
    "learner_species_defaults_id",
    "max_entries_per_domain",
    "divergence_salt_policy",
}
_DEVELOPMENTAL_DOMAIN_RATE_KEYS: Final[set[str]] = {
    "base_rate",
    "stage_compose",
    "min_exposures",
    "confidence_floor",
}
_DEVELOPMENTAL_BUDGET_KEYS: Final[set[str]] = {
    "mode",
    "acquisition_cost_units",
    "degrade_policy",
}
_DEPENDENCY_CARE_KEYS: Final[set[str]] = {
    "enabled_needs",
    "need_policies",
    "care_action_policy",
    "perception_mode",
    "caregiving_cognition_mode",
}
_DEPENDENCY_CARE_NEED_POLICY_KEYS: Final[set[str]] = {
    "self_satisfy",
    "unmet_accrual_per_tick",
    "critical_threshold",
    "critical_consequence",
}
_DEPENDENCY_CARE_ACTION_POLICY_KEYS: Final[set[str]] = {
    "allow_feed",
    "allow_transport",
    "allow_help_safety",
    "allow_teach_learning",
    "require_colocated",
}
_DEPENDENCY_CARE_FORBIDDEN_KEYS: Final[set[str]] = {
    "love",
    "attention",
    "emotion",
    "parenting",
    "attachment",
    "sex",
    "fertility",
    "pregnancy",
    "lactation",
    "nanny",
    "guardian",
    "caregiver",
    "ward",
    "parent_id",
    "assigned_caregiver",
}
_KINSHIP_KEYS: Final[set[str]] = {
    "bootstrap_edges",
    "max_query_depth",
    "max_parents_per_child",
    "perception_mode",
    "admit_link_policy",
}
_KINSHIP_BOOTSTRAP_EDGE_KEYS: Final[set[str]] = {
    "parent_agent_id",
    "child_agent_id",
    "established_tick",
}
_KINSHIP_ADMIT_LINK_KEYS: Final[set[str]] = {
    "allow_parent_links_on_admit",
    "require_living_parent",
}
_KINSHIP_FORBIDDEN_KEYS: Final[set[str]] = {
    "affection",
    "trust",
    "loyalty",
    "obligation",
    "inheritance_rights",
    "group_id",
    "clan",
    "dynasty",
    "spouse",
    "mate",
    "sex",
    "fertility",
    "pregnancy",
}
_POPULATION_LIFECYCLE_KEYS: Final[set[str]] = {
    "lifespan_ticks",
    "stage_thresholds",
    "dependent_until_stage",
    "demographic_policy_id",
    "demographic_policy_params",
    "max_population",
    "natural_death_on_lifespan",
}
_POPULATION_LIFECYCLE_KEYS_V26: Final[set[str]] = {
    *_POPULATION_LIFECYCLE_KEYS,
    "stage_capability_effects",
    "gradual_aging",
    "lifespan_distribution",
}
_GRADUAL_AGING_KEYS: Final[set[str]] = {"intra_stage_interpolation"}
_LIFESPAN_DISTRIBUTION_KEYS: Final[set[str]] = {"distribution_id", "params"}
_STAGE_CAPABILITY_EFFECT_KEYS: Final[set[str]] = {
    "stage_id",
    "physical_capacity_factor",
    "learning_rate_factor",
    "fatigue_accrual_factor",
    "denied_command_kinds",
}
_STAGE_THRESHOLD_KEYS: Final[set[str]] = {
    "stage_id",
    "inclusive_max_age",
}
_CAPABILITY_FLAG_KEYS: Final[set[str]] = {
    "advanced_social_inference",
    "multi_hop_testimony_tracking",
    "predictive_world_model",
    "extended_self_model",
    "short_term_emotional_state",
}
_V3_CAPABILITY_FLAG_KEYS: Final[set[str]] = {
    "generational_population",
    "kinship_inheritance",
    "multi_polity_migration",
    "institutional_economy",
    "cultural_historical_memory",
}
_COGNITION_TRACE_KEYS: Final[set[str]] = {
    "enabled",
    "detail",
    "sample_every_n_ticks",
    "max_bytes_per_invocation",
}


def _encode_capability_flags(flags: V2CapabilityFlags) -> dict[str, Any]:
    return {
        "advanced_social_inference": flags.advanced_social_inference,
        "multi_hop_testimony_tracking": flags.multi_hop_testimony_tracking,
        "predictive_world_model": flags.predictive_world_model,
        "extended_self_model": flags.extended_self_model,
        "short_term_emotional_state": flags.short_term_emotional_state,
    }


def _decode_capability_flags(
    data: Mapping[str, Any], *, path: str
) -> V2CapabilityFlags:
    if not isinstance(data, dict):
        raise RunnerSerializationError("invalid_object", path)
    _require_keys(data, _CAPABILITY_FLAG_KEYS, path=path)
    try:
        return V2CapabilityFlags(
            advanced_social_inference=_bool_field(
                data, "advanced_social_inference", path=path
            ),
            multi_hop_testimony_tracking=_bool_field(
                data, "multi_hop_testimony_tracking", path=path
            ),
            predictive_world_model=_bool_field(
                data, "predictive_world_model", path=path
            ),
            extended_self_model=_bool_field(data, "extended_self_model", path=path),
            short_term_emotional_state=_bool_field(
                data, "short_term_emotional_state", path=path
            ),
        )
    except RunnerSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise RunnerSerializationError("invalid_model", path) from exc


def _encode_v3_capability_flags(flags: V3CapabilityFlags) -> dict[str, Any]:
    return {
        "generational_population": flags.generational_population,
        "kinship_inheritance": flags.kinship_inheritance,
        "multi_polity_migration": flags.multi_polity_migration,
        "institutional_economy": flags.institutional_economy,
        "cultural_historical_memory": flags.cultural_historical_memory,
    }


def _decode_v3_capability_flags(
    data: Mapping[str, Any], *, path: str
) -> V3CapabilityFlags:
    if not isinstance(data, dict):
        raise RunnerSerializationError("invalid_object", path)
    _require_keys(data, _V3_CAPABILITY_FLAG_KEYS, path=path)
    try:
        return V3CapabilityFlags(
            generational_population=_bool_field(
                data, "generational_population", path=path
            ),
            kinship_inheritance=_bool_field(data, "kinship_inheritance", path=path),
            multi_polity_migration=_bool_field(
                data, "multi_polity_migration", path=path
            ),
            institutional_economy=_bool_field(
                data, "institutional_economy", path=path
            ),
            cultural_historical_memory=_bool_field(
                data, "cultural_historical_memory", path=path
            ),
        )
    except RunnerSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise RunnerSerializationError("invalid_model", path) from exc


def _encode_kinship(spec: KinshipSpec) -> dict[str, Any]:
    return spec.canonical_payload()


def _decode_kinship(data: Mapping[str, Any], *, path: str) -> KinshipSpec:
    from agents.models import AgentId
    from simulation.runner_models import (
        KinshipAdmitLinkPolicy,
        KinshipBootstrapEdgeSpec,
    )

    if not isinstance(data, dict):
        raise RunnerSerializationError("invalid_object", path)
    forbidden = set(data) & _KINSHIP_FORBIDDEN_KEYS
    if forbidden:
        raise RunnerSerializationError("unknown_field", path)
    _require_keys(data, _KINSHIP_KEYS, path=path)
    edges_raw = data["bootstrap_edges"]
    if not isinstance(edges_raw, list):
        raise RunnerSerializationError("invalid_array", f"{path}.bootstrap_edges")
    edges: list[KinshipBootstrapEdgeSpec] = []
    for index, item in enumerate(edges_raw):
        item_path = f"{path}.bootstrap_edges[{index}]"
        if not isinstance(item, dict):
            raise RunnerSerializationError("invalid_object", item_path)
        _require_keys(item, _KINSHIP_BOOTSTRAP_EDGE_KEYS, path=item_path)
        try:
            edges.append(
                KinshipBootstrapEdgeSpec(
                    parent_agent_id=AgentId(
                        _str_field(item, "parent_agent_id", path=item_path)
                    ),
                    child_agent_id=AgentId(
                        _str_field(item, "child_agent_id", path=item_path)
                    ),
                    established_tick=_nonneg_int_field(
                        item, "established_tick", path=item_path
                    ),
                )
            )
        except (TypeError, ValueError) as exc:
            raise RunnerSerializationError("invalid_model", item_path) from exc
    policy_raw = data["admit_link_policy"]
    if not isinstance(policy_raw, dict):
        raise RunnerSerializationError("invalid_object", f"{path}.admit_link_policy")
    _require_keys(
        policy_raw, _KINSHIP_ADMIT_LINK_KEYS, path=f"{path}.admit_link_policy"
    )
    try:
        return KinshipSpec(
            bootstrap_edges=tuple(edges),
            max_query_depth=_nonneg_int_field(data, "max_query_depth", path=path),
            max_parents_per_child=_nonneg_int_field(
                data, "max_parents_per_child", path=path
            ),
            perception_mode=_str_field(data, "perception_mode", path=path),
            admit_link_policy=KinshipAdmitLinkPolicy(
                allow_parent_links_on_admit=_bool_field(
                    policy_raw,
                    "allow_parent_links_on_admit",
                    path=f"{path}.admit_link_policy",
                ),
                require_living_parent=_bool_field(
                    policy_raw,
                    "require_living_parent",
                    path=f"{path}.admit_link_policy",
                ),
            ),
        )
    except (TypeError, ValueError) as exc:
        raise RunnerSerializationError("invalid_model", path) from exc


def _encode_dependency_care(spec: DependencyCareSpec) -> dict[str, Any]:
    return spec.canonical_payload()


def _decode_dependency_care(
    data: Mapping[str, Any], *, path: str
) -> DependencyCareSpec:
    from simulation.runner_models import (
        CareActionPolicySpec,
        DependencyCareNeedPolicySpec,
    )

    if not isinstance(data, dict):
        raise RunnerSerializationError("invalid_object", path)
    forbidden = set(data) & _DEPENDENCY_CARE_FORBIDDEN_KEYS
    if forbidden:
        raise RunnerSerializationError("unknown_field", path)
    _require_keys(data, _DEPENDENCY_CARE_KEYS, path=path)
    needs_raw = data["enabled_needs"]
    if not isinstance(needs_raw, list) or not needs_raw:
        raise RunnerSerializationError("invalid_array", f"{path}.enabled_needs")
    enabled_list: list[str] = []
    for index, item in enumerate(needs_raw):
        item_path = f"{path}.enabled_needs[{index}]"
        if type(item) is not str:
            raise RunnerSerializationError("invalid_string", item_path)
        enabled_list.append(item)
    policies_raw = data["need_policies"]
    if not isinstance(policies_raw, dict):
        raise RunnerSerializationError("invalid_object", f"{path}.need_policies")
    policies: dict[str, DependencyCareNeedPolicySpec] = {}
    for need_id, policy_raw in policies_raw.items():
        policy_path = f"{path}.need_policies.{need_id}"
        if type(need_id) is not str:
            raise RunnerSerializationError("invalid_string", policy_path)
        if not isinstance(policy_raw, dict):
            raise RunnerSerializationError("invalid_object", policy_path)
        forbidden_policy = set(policy_raw) & _DEPENDENCY_CARE_FORBIDDEN_KEYS
        if forbidden_policy:
            raise RunnerSerializationError("unknown_field", policy_path)
        _require_keys(policy_raw, _DEPENDENCY_CARE_NEED_POLICY_KEYS, path=policy_path)
        try:
            policies[need_id] = DependencyCareNeedPolicySpec(
                self_satisfy=_bool_field(policy_raw, "self_satisfy", path=policy_path),
                unmet_accrual_per_tick=_required_float(
                    policy_raw, "unmet_accrual_per_tick", path=policy_path
                ),
                critical_threshold=_required_float(
                    policy_raw, "critical_threshold", path=policy_path
                ),
                critical_consequence=_str_field(
                    policy_raw, "critical_consequence", path=policy_path
                ),
            )
        except (TypeError, ValueError) as exc:
            raise RunnerSerializationError("invalid_model", policy_path) from exc
    action_raw = data["care_action_policy"]
    if not isinstance(action_raw, dict):
        raise RunnerSerializationError("invalid_object", f"{path}.care_action_policy")
    _require_keys(
        action_raw,
        _DEPENDENCY_CARE_ACTION_POLICY_KEYS,
        path=f"{path}.care_action_policy",
    )
    try:
        return DependencyCareSpec(
            enabled_needs=tuple(enabled_list),
            need_policies=policies,
            care_action_policy=CareActionPolicySpec(
                allow_feed=_bool_field(
                    action_raw, "allow_feed", path=f"{path}.care_action_policy"
                ),
                allow_transport=_bool_field(
                    action_raw, "allow_transport", path=f"{path}.care_action_policy"
                ),
                allow_help_safety=_bool_field(
                    action_raw, "allow_help_safety", path=f"{path}.care_action_policy"
                ),
                allow_teach_learning=_bool_field(
                    action_raw,
                    "allow_teach_learning",
                    path=f"{path}.care_action_policy",
                ),
                require_colocated=_bool_field(
                    action_raw, "require_colocated", path=f"{path}.care_action_policy"
                ),
            ),
            perception_mode=_str_field(data, "perception_mode", path=path),
            caregiving_cognition_mode=_str_field(
                data, "caregiving_cognition_mode", path=path
            ),
        )
    except (TypeError, ValueError) as exc:
        raise RunnerSerializationError("invalid_model", path) from exc


def _encode_developmental_learning(spec: DevelopmentalLearningSpec) -> dict[str, Any]:
    return spec.canonical_payload()


def _decode_developmental_learning(
    data: Mapping[str, Any], *, path: str
) -> DevelopmentalLearningSpec:
    from agents.cognition.developmental_learning import (
        DevelopmentalDomainRate,
        DevelopmentalStageCompose,
    )

    if not isinstance(data, dict):
        raise RunnerSerializationError("invalid_object", path)
    _require_keys(data, _DEVELOPMENTAL_LEARNING_KEYS, path=path)
    domains_raw = data["enabled_domains"]
    if not isinstance(domains_raw, list) or not domains_raw:
        raise RunnerSerializationError("invalid_array", f"{path}.enabled_domains")
    enabled_domains: list[str] = []
    for index, item in enumerate(domains_raw):
        item_path = f"{path}.enabled_domains[{index}]"
        if type(item) is not str:
            raise RunnerSerializationError("invalid_string", item_path)
        enabled_domains.append(item)
    sources_raw = data["enabled_sources"]
    if not isinstance(sources_raw, list) or not sources_raw:
        raise RunnerSerializationError("invalid_array", f"{path}.enabled_sources")
    enabled_sources: list[str] = []
    for index, item in enumerate(sources_raw):
        item_path = f"{path}.enabled_sources[{index}]"
        if type(item) is not str:
            raise RunnerSerializationError("invalid_string", item_path)
        enabled_sources.append(item)
    rates_raw = data["domain_rates"]
    if not isinstance(rates_raw, dict):
        raise RunnerSerializationError("invalid_object", f"{path}.domain_rates")
    domain_rates: dict[str, DevelopmentalDomainRate] = {}
    for domain_id, rate_raw in rates_raw.items():
        rate_path = f"{path}.domain_rates.{domain_id}"
        if type(domain_id) is not str:
            raise RunnerSerializationError("invalid_string", rate_path)
        if not isinstance(rate_raw, dict):
            raise RunnerSerializationError("invalid_object", rate_path)
        _require_keys(rate_raw, _DEVELOPMENTAL_DOMAIN_RATE_KEYS, path=rate_path)
        try:
            compose = DevelopmentalStageCompose(
                _str_field(rate_raw, "stage_compose", path=rate_path)
            )
            domain_rates[domain_id] = DevelopmentalDomainRate(
                base_rate=_required_float(rate_raw, "base_rate", path=rate_path),
                stage_compose=compose,
                min_exposures=_nonneg_int_field(
                    rate_raw, "min_exposures", path=rate_path
                ),
                confidence_floor=_required_float(
                    rate_raw, "confidence_floor", path=rate_path
                ),
            )
        except (TypeError, ValueError) as exc:
            raise RunnerSerializationError("invalid_model", rate_path) from exc
    weights_raw = data["source_weights"]
    if not isinstance(weights_raw, dict):
        raise RunnerSerializationError("invalid_object", f"{path}.source_weights")
    source_weights: dict[str, float] = {}
    for source_id, _weight in weights_raw.items():
        weight_path = f"{path}.source_weights.{source_id}"
        if type(source_id) is not str:
            raise RunnerSerializationError("invalid_string", weight_path)
        try:
            source_weights[source_id] = _required_float(
                weights_raw, source_id, path=path + ".source_weights"
            )
        except (TypeError, ValueError) as exc:
            raise RunnerSerializationError("invalid_model", weight_path) from exc
    budget_raw = data["cognitive_budget_coupling"]
    if not isinstance(budget_raw, dict):
        raise RunnerSerializationError(
            "invalid_object", f"{path}.cognitive_budget_coupling"
        )
    _require_keys(
        budget_raw, _DEVELOPMENTAL_BUDGET_KEYS, path=f"{path}.cognitive_budget_coupling"
    )
    try:
        return DevelopmentalLearningSpec(
            enabled_domains=tuple(enabled_domains),
            enabled_sources=tuple(enabled_sources),
            domain_rates=domain_rates,
            source_weights=source_weights,
            applicability=_str_field(data, "applicability", path=path),
            cognitive_budget_coupling=DevelopmentalCognitiveBudgetCoupling(
                mode=_str_field(
                    budget_raw, "mode", path=f"{path}.cognitive_budget_coupling"
                ),
                acquisition_cost_units=_nonneg_int_field(
                    budget_raw,
                    "acquisition_cost_units",
                    path=f"{path}.cognitive_budget_coupling",
                ),
                degrade_policy=_str_field(
                    budget_raw,
                    "degrade_policy",
                    path=f"{path}.cognitive_budget_coupling",
                ),
            ),
            developmental_learning_mode=_str_field(
                data, "developmental_learning_mode", path=path
            ),
            learner_species_defaults_id=_str_field(
                data, "learner_species_defaults_id", path=path
            ),
            max_entries_per_domain=_nonneg_int_field(
                data, "max_entries_per_domain", path=path
            ),
            divergence_salt_policy=_str_field(
                data, "divergence_salt_policy", path=path
            ),
        )
    except (TypeError, ValueError) as exc:
        raise RunnerSerializationError("invalid_model", path) from exc


def _encode_mentorship(spec: MentorshipSpec) -> dict[str, Any]:
    return spec.canonical_payload()


def _decode_mentorship(data: Mapping[str, Any], *, path: str) -> MentorshipSpec:
    if not isinstance(data, dict):
        raise RunnerSerializationError("invalid_object", path)
    _require_keys(data, _MENTORSHIP_KEYS, path=path)
    kinds_raw = data["enabled_content_kinds"]
    if not isinstance(kinds_raw, list) or not kinds_raw:
        raise RunnerSerializationError(
            "invalid_array", f"{path}.enabled_content_kinds"
        )
    enabled_kinds: list[str] = []
    for index, item in enumerate(kinds_raw):
        item_path = f"{path}.enabled_content_kinds[{index}]"
        if type(item) is not str:
            raise RunnerSerializationError("invalid_string", item_path)
        enabled_kinds.append(item)
    bond_raw = data["bond_policy"]
    if not isinstance(bond_raw, dict):
        raise RunnerSerializationError("invalid_object", f"{path}.bond_policy")
    _require_keys(bond_raw, _MENTORSHIP_BOND_POLICY_KEYS, path=f"{path}.bond_policy")
    lineage_raw = data["lineage_policy"]
    if not isinstance(lineage_raw, dict):
        raise RunnerSerializationError("invalid_object", f"{path}.lineage_policy")
    _require_keys(
        lineage_raw, _MENTORSHIP_LINEAGE_POLICY_KEYS, path=f"{path}.lineage_policy"
    )
    bias_raw = data["partner_bias"]
    if not isinstance(bias_raw, dict):
        raise RunnerSerializationError("invalid_object", f"{path}.partner_bias")
    _require_keys(bias_raw, _MENTORSHIP_PARTNER_BIAS_KEYS, path=f"{path}.partner_bias")
    try:
        return MentorshipSpec(
            enabled_content_kinds=tuple(enabled_kinds),
            bond_policy=MentorshipBondPolicy(
                form_after_successful_acts=_nonneg_int_field(
                    bond_raw, "form_after_successful_acts", path=f"{path}.bond_policy"
                ),
                min_trust=_required_float(
                    bond_raw, "min_trust", path=f"{path}.bond_policy"
                ),
                reinforce_on_learning_evidence=_bool_field(
                    bond_raw,
                    "reinforce_on_learning_evidence",
                    path=f"{path}.bond_policy",
                ),
                decay_per_tick=_required_float(
                    bond_raw, "decay_per_tick", path=f"{path}.bond_policy"
                ),
                offer_window_extend=_nonneg_int_field(
                    bond_raw, "offer_window_extend", path=f"{path}.bond_policy"
                ),
                symmetric=_bool_field(
                    bond_raw, "symmetric", path=f"{path}.bond_policy"
                ),
            ),
            lineage_policy=MentorshipLineagePolicy(
                max_hop_depth=_nonneg_int_field(
                    lineage_raw, "max_hop_depth", path=f"{path}.lineage_policy"
                ),
                record_attempts=_bool_field(
                    lineage_raw, "record_attempts", path=f"{path}.lineage_policy"
                ),
                allow_learner_mutation=_bool_field(
                    lineage_raw,
                    "allow_learner_mutation",
                    path=f"{path}.lineage_policy",
                ),
                mutation_requires_evidence=_bool_field(
                    lineage_raw,
                    "mutation_requires_evidence",
                    path=f"{path}.lineage_policy",
                ),
                confidence_inherit_mode=_str_field(
                    lineage_raw,
                    "confidence_inherit_mode",
                    path=f"{path}.lineage_policy",
                ),
            ),
            partner_bias=MentorshipPartnerBias(
                mode=_str_field(bias_raw, "mode", path=f"{path}.partner_bias"),
                communicate_weight=_required_float(
                    bias_raw, "communicate_weight", path=f"{path}.partner_bias"
                ),
                content_kind_affinity=_bool_field(
                    bias_raw, "content_kind_affinity", path=f"{path}.partner_bias"
                ),
            ),
            mentorship_mode=_str_field(data, "mentorship_mode", path=path),
            requires_teaching_interaction=_bool_field(
                data, "requires_teaching_interaction", path=path
            ),
            max_bonds_per_owner=_nonneg_int_field(
                data, "max_bonds_per_owner", path=path
            ),
            max_lineage_entries_per_owner=_nonneg_int_field(
                data, "max_lineage_entries_per_owner", path=path
            ),
            applicability=_str_field(data, "applicability", path=path),
        )
    except (TypeError, ValueError) as exc:
        raise RunnerSerializationError("invalid_model", path) from exc


def _encode_cultural_feature_provenance(
    spec: CulturalFeatureProvenanceSpec,
) -> dict[str, Any]:
    return spec.canonical_payload()


def _decode_cultural_feature_provenance(
    data: Mapping[str, Any], *, path: str
) -> CulturalFeatureProvenanceSpec:
    if not isinstance(data, dict):
        raise RunnerSerializationError("invalid_object", path)
    _require_keys(data, _CULTURAL_FEATURE_PROVENANCE_KEYS, path=path)
    kinds_raw = data["enabled_feature_kinds"]
    if not isinstance(kinds_raw, list) or not kinds_raw:
        raise RunnerSerializationError(
            "invalid_array", f"{path}.enabled_feature_kinds"
        )
    enabled_kinds: list[str] = []
    for index, item in enumerate(kinds_raw):
        item_path = f"{path}.enabled_feature_kinds[{index}]"
        if type(item) is not str:
            raise RunnerSerializationError("invalid_string", item_path)
        enabled_kinds.append(item)
    channels_raw = data["enabled_provenance_channels"]
    if not isinstance(channels_raw, list) or not channels_raw:
        raise RunnerSerializationError(
            "invalid_array", f"{path}.enabled_provenance_channels"
        )
    enabled_channels: list[str] = []
    for index, item in enumerate(channels_raw):
        item_path = f"{path}.enabled_provenance_channels[{index}]"
        if type(item) is not str:
            raise RunnerSerializationError("invalid_string", item_path)
        enabled_channels.append(item)
    mutation_raw = data["mutation_policy"]
    if not isinstance(mutation_raw, dict):
        raise RunnerSerializationError("invalid_object", f"{path}.mutation_policy")
    _require_keys(
        mutation_raw,
        _CULTURAL_FEATURE_MUTATION_POLICY_KEYS,
        path=f"{path}.mutation_policy",
    )
    recomb_raw = data["recombination_policy"]
    if not isinstance(recomb_raw, dict):
        raise RunnerSerializationError(
            "invalid_object", f"{path}.recombination_policy"
        )
    _require_keys(
        recomb_raw,
        _CULTURAL_FEATURE_RECOMBINATION_POLICY_KEYS,
        path=f"{path}.recombination_policy",
    )
    compose_raw = data["uptake_compose"]
    if not isinstance(compose_raw, dict):
        raise RunnerSerializationError("invalid_object", f"{path}.uptake_compose")
    _require_keys(
        compose_raw,
        _CULTURAL_FEATURE_UPTAKE_COMPOSE_KEYS,
        path=f"{path}.uptake_compose",
    )
    bias_raw = data["bias_policy"]
    if not isinstance(bias_raw, dict):
        raise RunnerSerializationError("invalid_object", f"{path}.bias_policy")
    _require_keys(
        bias_raw, _CULTURAL_FEATURE_BIAS_POLICY_KEYS, path=f"{path}.bias_policy"
    )
    try:
        return CulturalFeatureProvenanceSpec(
            enabled_feature_kinds=tuple(enabled_kinds),
            enabled_provenance_channels=tuple(enabled_channels),
            mutation_policy=CulturalFeatureMutationPolicy(
                allow_mutation=_bool_field(
                    mutation_raw, "allow_mutation", path=f"{path}.mutation_policy"
                ),
                mutation_requires_evidence=_bool_field(
                    mutation_raw,
                    "mutation_requires_evidence",
                    path=f"{path}.mutation_policy",
                ),
                max_token_edits=_nonneg_int_field(
                    mutation_raw, "max_token_edits", path=f"{path}.mutation_policy"
                ),
                rng_namespace=_str_field(
                    mutation_raw, "rng_namespace", path=f"{path}.mutation_policy"
                ),
            ),
            recombination_policy=CulturalFeatureRecombinationPolicy(
                allow_recombination=_bool_field(
                    recomb_raw,
                    "allow_recombination",
                    path=f"{path}.recombination_policy",
                ),
                max_parents=_nonneg_int_field(
                    recomb_raw, "max_parents", path=f"{path}.recombination_policy"
                ),
                min_token_overlap=_required_float(
                    recomb_raw,
                    "min_token_overlap",
                    path=f"{path}.recombination_policy",
                ),
            ),
            uptake_compose=CulturalFeatureUptakeCompose(
                naming=_bool_field(
                    compose_raw, "naming", path=f"{path}.uptake_compose"
                ),
                narrative=_bool_field(
                    compose_raw, "narrative", path=f"{path}.uptake_compose"
                ),
                norms=_bool_field(
                    compose_raw, "norms", path=f"{path}.uptake_compose"
                ),
                conventions=_bool_field(
                    compose_raw, "conventions", path=f"{path}.uptake_compose"
                ),
                teaching=_bool_field(
                    compose_raw, "teaching", path=f"{path}.uptake_compose"
                ),
                artifacts=_bool_field(
                    compose_raw, "artifacts", path=f"{path}.uptake_compose"
                ),
                mentorship=_bool_field(
                    compose_raw, "mentorship", path=f"{path}.uptake_compose"
                ),
            ),
            bias_policy=CulturalFeatureBiasPolicy(
                mode=_str_field(bias_raw, "mode", path=f"{path}.bias_policy"),
                communicate_weight=_required_float(
                    bias_raw, "communicate_weight", path=f"{path}.bias_policy"
                ),
                content_affinity=_bool_field(
                    bias_raw, "content_affinity", path=f"{path}.bias_policy"
                ),
            ),
            cultural_feature_mode=_str_field(
                data, "cultural_feature_mode", path=path
            ),
            max_beliefs_per_owner=_nonneg_int_field(
                data, "max_beliefs_per_owner", path=path
            ),
            max_evidence_refs=_nonneg_int_field(
                data, "max_evidence_refs", path=path
            ),
            applicability=_str_field(data, "applicability", path=path),
        )
    except (TypeError, ValueError) as exc:
        raise RunnerSerializationError("invalid_model", path) from exc


def _encode_historical_memory_layers(
    spec: HistoricalMemoryLayersSpec,
) -> dict[str, Any]:
    return spec.canonical_payload()


def _decode_historical_memory_layers(
    data: Mapping[str, Any], *, path: str
) -> HistoricalMemoryLayersSpec:
    if not isinstance(data, dict):
        raise RunnerSerializationError("invalid_object", path)
    forbidden = set(data) & _HISTORICAL_MEMORY_FORBIDDEN_ALIASES
    assmann_keys = {key for key in data if key.startswith("assmann_")}
    if forbidden or assmann_keys:
        _LOG.error(
            "historical_memory_forbidden_alias path=%s "
            "reason_code=historical_memory_forbidden_alias",
            path,
        )
        raise RunnerSerializationError("historical_memory_forbidden_alias", path)
    _require_keys(data, _HISTORICAL_MEMORY_LAYERS_KEYS, path=path)
    try:
        return HistoricalMemoryLayersSpec(
            mode=_str_field(data, "mode", path=path),
            max_communicative_hops=_nonneg_int_field(
                data, "max_communicative_hops", path=path
            ),
            witness_definition=_str_field(data, "witness_definition", path=path),
            include_narrative_lineage=_bool_field(
                data, "include_narrative_lineage", path=path
            ),
            include_cultural_features=_bool_field(
                data, "include_cultural_features", path=path
            ),
            include_artifact_edges=_bool_field(
                data, "include_artifact_edges", path=path
            ),
            include_teaching_edges=_bool_field(
                data, "include_teaching_edges", path=path
            ),
            generation_distance_weight=_required_float(
                data, "generation_distance_weight", path=path
            ),
            query_event_selector=_str_field(data, "query_event_selector", path=path),
            transition_tick_resolution=_str_field(
                data, "transition_tick_resolution", path=path
            ),
            applicability=_str_field(data, "applicability", path=path),
        )
    except (TypeError, ValueError) as exc:
        raise RunnerSerializationError("invalid_model", path) from exc


def _encode_population_lifecycle(
    spec: PopulationLifecycleSpec, *, schema_version: str
) -> dict[str, Any]:
    include_developmental = schema_version == RUNNER_SCHEMA_VERSION_V26
    return spec.canonical_payload(include_developmental=include_developmental)


def _decode_gradual_aging(data: Mapping[str, Any], *, path: str) -> object:
    from simulation.runner_models import GradualAgingSpec

    if not isinstance(data, dict):
        raise RunnerSerializationError("invalid_object", path)
    _require_keys(data, _GRADUAL_AGING_KEYS, path=path)
    try:
        return GradualAgingSpec(
            intra_stage_interpolation=_bool_field(
                data, "intra_stage_interpolation", path=path
            )
        )
    except (TypeError, ValueError) as exc:
        raise RunnerSerializationError("invalid_model", path) from exc


def _decode_lifespan_distribution(data: Mapping[str, Any], *, path: str) -> object:
    from simulation.runner_models import LifespanDistributionSpec

    if not isinstance(data, dict):
        raise RunnerSerializationError("invalid_object", path)
    _require_keys(data, _LIFESPAN_DISTRIBUTION_KEYS, path=path)
    params_raw = data["params"]
    if not isinstance(params_raw, dict):
        raise RunnerSerializationError("invalid_object", f"{path}.params")
    try:
        return LifespanDistributionSpec(
            distribution_id=_str_field(data, "distribution_id", path=path),
            params=dict(params_raw),
        )
    except (TypeError, ValueError) as exc:
        raise RunnerSerializationError("invalid_model", path) from exc


def _decode_stage_capability_effects(
    raw: object, *, path: str
) -> tuple[object, ...]:
    from world.lifecycle import LifecycleStageId
    from world.lifecycle_effects import StageCapabilityEffect

    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise RunnerSerializationError("invalid_array", path)
    effects: list[StageCapabilityEffect] = []
    for index, item in enumerate(raw):
        item_path = f"{path}[{index}]"
        if not isinstance(item, dict):
            raise RunnerSerializationError("invalid_object", item_path)
        forbidden = set(item) & {
            "authority",
            "leader",
            "social_rank",
            "respect",
            "role",
            "parent_id",
            "parent_ids",
            "child_id",
            "child_ids",
            "kinship",
            "heavy_labor",
            "long_travel",
            "teach",
            "combat_initiate",
        }
        if forbidden:
            raise RunnerSerializationError("unknown_field", item_path)
        _require_keys(item, _STAGE_CAPABILITY_EFFECT_KEYS, path=item_path)
        kinds_raw = item["denied_command_kinds"]
        if not isinstance(kinds_raw, list):
            raise RunnerSerializationError(
                "invalid_array", f"{item_path}.denied_command_kinds"
            )
        try:
            effects.append(
                StageCapabilityEffect(
                    stage_id=LifecycleStageId(
                        _str_field(item, "stage_id", path=item_path)
                    ),
                    physical_capacity_factor=_required_float(
                        item, "physical_capacity_factor", path=item_path
                    ),
                    learning_rate_factor=_required_float(
                        item, "learning_rate_factor", path=item_path
                    ),
                    fatigue_accrual_factor=_required_float(
                        item, "fatigue_accrual_factor", path=item_path
                    ),
                    denied_command_kinds=tuple(kinds_raw),
                )
            )
        except (TypeError, ValueError) as exc:
            raise RunnerSerializationError("invalid_model", item_path) from exc
    return tuple(effects)


def _decode_population_lifecycle(
    data: Mapping[str, Any], *, path: str, schema_version: str
) -> PopulationLifecycleSpec:
    from simulation.runner_models import (
        GradualAgingSpec,
        LifespanDistributionSpec,
        default_gradual_aging_spec,
        default_lifespan_distribution_spec,
    )
    from world.lifecycle import LifecycleStageId, LifecycleStageThreshold

    if not isinstance(data, dict):
        raise RunnerSerializationError("invalid_object", path)
    if schema_version == RUNNER_SCHEMA_VERSION_V26:
        _require_keys(data, _POPULATION_LIFECYCLE_KEYS_V26, path=path)
    else:
        _require_keys(data, _POPULATION_LIFECYCLE_KEYS, path=path)
    thresholds_raw = data["stage_thresholds"]
    if not isinstance(thresholds_raw, list):
        raise RunnerSerializationError("invalid_array", f"{path}.stage_thresholds")
    thresholds: list[LifecycleStageThreshold] = []
    for index, item in enumerate(thresholds_raw):
        item_path = f"{path}.stage_thresholds[{index}]"
        if not isinstance(item, dict):
            raise RunnerSerializationError("invalid_object", item_path)
        _require_keys(item, _STAGE_THRESHOLD_KEYS, path=item_path)
        try:
            thresholds.append(
                LifecycleStageThreshold(
                    LifecycleStageId(_str_field(item, "stage_id", path=item_path)),
                    _nonneg_int_field(item, "inclusive_max_age", path=item_path),
                )
            )
        except (TypeError, ValueError) as exc:
            raise RunnerSerializationError("invalid_model", item_path) from exc
    params_raw = data["demographic_policy_params"]
    if not isinstance(params_raw, dict):
        raise RunnerSerializationError(
            "invalid_object", f"{path}.demographic_policy_params"
        )
    if schema_version == RUNNER_SCHEMA_VERSION_V26:
        gradual_aging = _decode_gradual_aging(
            data["gradual_aging"], path=f"{path}.gradual_aging"
        )
        lifespan_distribution = _decode_lifespan_distribution(
            data["lifespan_distribution"], path=f"{path}.lifespan_distribution"
        )
        effects = _decode_stage_capability_effects(
            data["stage_capability_effects"],
            path=f"{path}.stage_capability_effects",
        )
        _LOG.debug(
            "population_lifecycle_developmental_decoded effect_count=%s "
            "distribution_id=%s interpolation=%s",
            len(effects),
            getattr(lifespan_distribution, "distribution_id", None),
            getattr(gradual_aging, "intra_stage_interpolation", None),
        )
    else:
        gradual_aging = default_gradual_aging_spec()
        lifespan_distribution = default_lifespan_distribution_spec()
        effects = ()
        _LOG.debug(
            "population_lifecycle_developmental_synthesized schema_version=%s",
            schema_version,
        )
    try:
        assert type(gradual_aging) is GradualAgingSpec
        assert type(lifespan_distribution) is LifespanDistributionSpec
        return PopulationLifecycleSpec(
            lifespan_ticks=_nonneg_int_field(data, "lifespan_ticks", path=path),
            stage_thresholds=tuple(thresholds),
            dependent_until_stage=LifecycleStageId(
                _str_field(data, "dependent_until_stage", path=path)
            ),
            demographic_policy_id=_str_field(
                data, "demographic_policy_id", path=path
            ),
            demographic_policy_params=dict(params_raw),
            max_population=_nonneg_int_field(data, "max_population", path=path),
            natural_death_on_lifespan=_bool_field(
                data, "natural_death_on_lifespan", path=path
            ),
            stage_capability_effects=effects,  # type: ignore[arg-type]
            gradual_aging=gradual_aging,
            lifespan_distribution=lifespan_distribution,
        )
    except RunnerSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise RunnerSerializationError("invalid_model", path) from exc


def _encode_new_agent_initialization(spec: object) -> dict[str, Any]:
    from simulation.new_agent_initialization import NewAgentInitializationSpec

    if type(spec) is not NewAgentInitializationSpec:
        raise TypeError("new_agent_initialization must be NewAgentInitializationSpec")
    return spec.canonical_payload()


def _decode_new_agent_initialization(
    data: Mapping[str, Any], *, path: str
) -> object:
    from simulation.new_agent_initialization import (
        NEW_AGENT_INITIALIZATION_KEYS,
        CreationReasonCode,
        DependencyBindingPolicy,
        InnateDrivePolicy,
        NewAgentInitializationSpec,
        ObjectiveInheritancePolicy,
        ParameterDistributionSpec,
        PhysicalConditionPolicy,
        ProvenancePolicy,
        SpawnLocationPolicy,
    )

    if not isinstance(data, dict):
        raise RunnerSerializationError("invalid_object", path)
    _require_keys(data, set(NEW_AGENT_INITIALIZATION_KEYS), path=path)
    try:
        dist_raw = data["parameter_distributions"]
        if not isinstance(dist_raw, dict):
            raise RunnerSerializationError(
                "invalid_object", f"{path}.parameter_distributions"
            )
        _require_keys(
            dist_raw,
            {"distribution_id", "params"},
            path=f"{path}.parameter_distributions",
        )
        params_raw = dist_raw["params"]
        if not isinstance(params_raw, dict):
            raise RunnerSerializationError(
                "invalid_object", f"{path}.parameter_distributions.params"
            )
        innate_raw = data["innate_drive_policy"]
        if not isinstance(innate_raw, dict):
            raise RunnerSerializationError(
                "invalid_object", f"{path}.innate_drive_policy"
            )
        _require_keys(
            innate_raw, {"policy_id", "params"}, path=f"{path}.innate_drive_policy"
        )
        innate_params = innate_raw["params"]
        if not isinstance(innate_params, dict):
            raise RunnerSerializationError(
                "invalid_object", f"{path}.innate_drive_policy.params"
            )
        physical_raw = data["physical_condition_policy"]
        if not isinstance(physical_raw, dict):
            raise RunnerSerializationError(
                "invalid_object", f"{path}.physical_condition_policy"
            )
        _require_keys(
            physical_raw,
            {"policy_id", "params"},
            path=f"{path}.physical_condition_policy",
        )
        physical_params = physical_raw["params"]
        if not isinstance(physical_params, dict):
            raise RunnerSerializationError(
                "invalid_object", f"{path}.physical_condition_policy.params"
            )
        spawn_raw = data["spawn_location_policy"]
        if not isinstance(spawn_raw, dict):
            raise RunnerSerializationError(
                "invalid_object", f"{path}.spawn_location_policy"
            )
        _require_keys(
            spawn_raw, {"policy_id", "params"}, path=f"{path}.spawn_location_policy"
        )
        spawn_params = spawn_raw["params"]
        if not isinstance(spawn_params, dict):
            raise RunnerSerializationError(
                "invalid_object", f"{path}.spawn_location_policy.params"
            )
        dep_raw = data["dependency_binding"]
        if not isinstance(dep_raw, dict):
            raise RunnerSerializationError(
                "invalid_object", f"{path}.dependency_binding"
            )
        _require_keys(dep_raw, {"policy_id"}, path=f"{path}.dependency_binding")
        inherit_raw = data["objective_inheritance"]
        if not isinstance(inherit_raw, dict):
            raise RunnerSerializationError(
                "invalid_object", f"{path}.objective_inheritance"
            )
        _require_keys(
            inherit_raw, {"allowed_keys"}, path=f"{path}.objective_inheritance"
        )
        allowed_keys_raw = inherit_raw["allowed_keys"]
        if not isinstance(allowed_keys_raw, list):
            raise RunnerSerializationError(
                "invalid_array", f"{path}.objective_inheritance.allowed_keys"
            )
        reason_raw = data["creation_reason_policy"]
        if not isinstance(reason_raw, list):
            raise RunnerSerializationError(
                "invalid_array", f"{path}.creation_reason_policy"
            )
        for reason in reason_raw:
            if type(reason) is not str:
                raise RunnerSerializationError(
                    "invalid_string", f"{path}.creation_reason_policy"
                )
            CreationReasonCode(reason)
        prov_raw = data["provenance_policy"]
        if not isinstance(prov_raw, dict):
            raise RunnerSerializationError(
                "invalid_object", f"{path}.provenance_policy"
            )
        _require_keys(
            prov_raw,
            {"record_origin_refs", "allowed_roles"},
            path=f"{path}.provenance_policy",
        )
        roles_raw = prov_raw["allowed_roles"]
        if not isinstance(roles_raw, list):
            raise RunnerSerializationError(
                "invalid_array", f"{path}.provenance_policy.allowed_roles"
            )
        return NewAgentInitializationSpec(
            species_defaults_id=_str_field(data, "species_defaults_id", path=path),
            parameter_distributions=ParameterDistributionSpec(
                distribution_id=_str_field(
                    dist_raw, "distribution_id", path=f"{path}.parameter_distributions"
                ),
                params=dict(params_raw),
            ),
            innate_drive_policy=InnateDrivePolicy(
                policy_id=_str_field(
                    innate_raw, "policy_id", path=f"{path}.innate_drive_policy"
                ),
                params=dict(innate_params),
            ),
            physical_condition_policy=PhysicalConditionPolicy(
                policy_id=_str_field(
                    physical_raw,
                    "policy_id",
                    path=f"{path}.physical_condition_policy",
                ),
                params=dict(physical_params),
            ),
            spawn_location_policy=SpawnLocationPolicy(
                policy_id=_str_field(
                    spawn_raw, "policy_id", path=f"{path}.spawn_location_policy"
                ),
                params=dict(spawn_params),
            ),
            dependency_binding=DependencyBindingPolicy(
                policy_id=_str_field(
                    dep_raw, "policy_id", path=f"{path}.dependency_binding"
                )
            ),
            objective_inheritance=ObjectiveInheritancePolicy(
                allowed_keys=tuple(str(item) for item in allowed_keys_raw)
            ),
            creation_reason_policy=tuple(str(item) for item in reason_raw),
            provenance_policy=ProvenancePolicy(
                record_origin_refs=_bool_field(
                    prov_raw,
                    "record_origin_refs",
                    path=f"{path}.provenance_policy",
                ),
                allowed_roles=tuple(str(item) for item in roles_raw),
            ),
        )
    except RunnerSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise RunnerSerializationError("invalid_model", path) from exc


def _encode_cognition_trace(spec: CognitionTraceSpec) -> dict[str, Any]:
    return {
        "enabled": spec.enabled,
        "detail": spec.detail.value,
        "sample_every_n_ticks": spec.sample_every_n_ticks,
        "max_bytes_per_invocation": spec.max_bytes_per_invocation,
    }


def _decode_cognition_trace(
    data: Mapping[str, Any], *, path: str
) -> CognitionTraceSpec:
    if not isinstance(data, dict):
        raise RunnerSerializationError("invalid_object", path)
    _require_keys(data, _COGNITION_TRACE_KEYS, path=path)
    detail_raw = _str_field(data, "detail", path=path)
    try:
        detail = CognitionTraceDetail(detail_raw)
    except ValueError as exc:
        raise RunnerSerializationError("invalid_enum", f"{path}.detail") from exc
    sample = data["sample_every_n_ticks"]
    if sample is not None and (
        isinstance(sample, bool) or not isinstance(sample, int) or sample < 1
    ):
        raise RunnerSerializationError("invalid_int", f"{path}.sample_every_n_ticks")
    max_bytes = data["max_bytes_per_invocation"]
    if max_bytes is not None and (
        isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes < 1
    ):
        raise RunnerSerializationError(
            "invalid_int", f"{path}.max_bytes_per_invocation"
        )
    try:
        return CognitionTraceSpec(
            enabled=_bool_field(data, "enabled", path=path),
            detail=detail,
            sample_every_n_ticks=sample,
            max_bytes_per_invocation=max_bytes,
        )
    except RunnerSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise RunnerSerializationError("invalid_model", path) from exc


def _encode_runner_document(config: SimulationRunnerConfig) -> dict[str, Any]:
    document: dict[str, Any] = {
        "agents": [
            _encode_agent(agent, schema_version=config.schema_version)
            for agent in config.agents
        ],
        "cognition_failure_policy": config.cognition_failure_policy.value,
        "derivation_version": config.derivation_version,
        "mortality_mode": config.mortality_mode.value,
        "mortality_policy_version": config.mortality_policy_version,
        "persistence": {
            "checkpoint": {
                "cadence_ticks": config.persistence.checkpoint.cadence_ticks,
                "enabled": config.persistence.checkpoint.enabled,
            },
            "durable": config.persistence.durable,
        },
        "provider": _encode_provider(config.provider),
        "scenario": _encode_scenario(config.scenario),
        "schema_version": config.schema_version,
        "seed": config.seed,
        "stochastic_identity": config.stochastic_identity.value,
        "stop_policy": {
            "allow_cancellation": config.stop_policy.allow_cancellation,
            "allow_injected_stop": config.stop_policy.allow_injected_stop,
            "max_ticks": config.stop_policy.max_ticks,
            "stop_on_all_agents_terminal": (
                config.stop_policy.stop_on_all_agents_terminal
            ),
        },
    }
    if config.schema_version in {
        RUNNER_SCHEMA_VERSION_V3,
        RUNNER_SCHEMA_VERSION_V4,
        RUNNER_SCHEMA_VERSION_V5,
        RUNNER_SCHEMA_VERSION_V6,
        RUNNER_SCHEMA_VERSION_V7,
        RUNNER_SCHEMA_VERSION_V8,
        RUNNER_SCHEMA_VERSION_V9,
        RUNNER_SCHEMA_VERSION_V10,
        RUNNER_SCHEMA_VERSION_V11,
        RUNNER_SCHEMA_VERSION_V12,
        RUNNER_SCHEMA_VERSION_V13,
        RUNNER_SCHEMA_VERSION_V14,
        RUNNER_SCHEMA_VERSION_V15,
        RUNNER_SCHEMA_VERSION_V16,
        RUNNER_SCHEMA_VERSION_V17,
        RUNNER_SCHEMA_VERSION_V18,
        RUNNER_SCHEMA_VERSION_V19,
        RUNNER_SCHEMA_VERSION_V20,
        RUNNER_SCHEMA_VERSION_V21,
        RUNNER_SCHEMA_VERSION_V22,
        RUNNER_SCHEMA_VERSION_V23,
        RUNNER_SCHEMA_VERSION_V24,
        RUNNER_SCHEMA_VERSION_V25,
        RUNNER_SCHEMA_VERSION_V26,
        RUNNER_SCHEMA_VERSION_V27,
        RUNNER_SCHEMA_VERSION_V28,
        RUNNER_SCHEMA_VERSION_V29,
        RUNNER_SCHEMA_VERSION_V30,
        RUNNER_SCHEMA_VERSION_V31,
        RUNNER_SCHEMA_VERSION_V32,
    }:
        document["capability_flags"] = _encode_capability_flags(config.capability_flags)
    if config.schema_version in {
        RUNNER_SCHEMA_VERSION_V4,
        RUNNER_SCHEMA_VERSION_V5,
        RUNNER_SCHEMA_VERSION_V6,
        RUNNER_SCHEMA_VERSION_V7,
        RUNNER_SCHEMA_VERSION_V8,
        RUNNER_SCHEMA_VERSION_V9,
        RUNNER_SCHEMA_VERSION_V10,
        RUNNER_SCHEMA_VERSION_V11,
        RUNNER_SCHEMA_VERSION_V12,
        RUNNER_SCHEMA_VERSION_V13,
        RUNNER_SCHEMA_VERSION_V14,
        RUNNER_SCHEMA_VERSION_V15,
        RUNNER_SCHEMA_VERSION_V16,
        RUNNER_SCHEMA_VERSION_V17,
        RUNNER_SCHEMA_VERSION_V18,
        RUNNER_SCHEMA_VERSION_V19,
        RUNNER_SCHEMA_VERSION_V20,
        RUNNER_SCHEMA_VERSION_V21,
        RUNNER_SCHEMA_VERSION_V22,
        RUNNER_SCHEMA_VERSION_V23,
        RUNNER_SCHEMA_VERSION_V24,
        RUNNER_SCHEMA_VERSION_V25,
        RUNNER_SCHEMA_VERSION_V26,
        RUNNER_SCHEMA_VERSION_V27,
        RUNNER_SCHEMA_VERSION_V28,
        RUNNER_SCHEMA_VERSION_V29,
        RUNNER_SCHEMA_VERSION_V30,
        RUNNER_SCHEMA_VERSION_V31,
        RUNNER_SCHEMA_VERSION_V32,
    }:
        document["cognition_trace"] = _encode_cognition_trace(config.cognition_trace)
    if config.schema_version == RUNNER_SCHEMA_VERSION_V14 or (
        config.schema_version
        in {
            RUNNER_SCHEMA_VERSION_V15,
            RUNNER_SCHEMA_VERSION_V16,
            RUNNER_SCHEMA_VERSION_V17,
            RUNNER_SCHEMA_VERSION_V18,
            RUNNER_SCHEMA_VERSION_V19,
            RUNNER_SCHEMA_VERSION_V20,
            RUNNER_SCHEMA_VERSION_V21,
            RUNNER_SCHEMA_VERSION_V22,
            RUNNER_SCHEMA_VERSION_V23,
            RUNNER_SCHEMA_VERSION_V24,
            RUNNER_SCHEMA_VERSION_V25,
            RUNNER_SCHEMA_VERSION_V26,
            RUNNER_SCHEMA_VERSION_V27,
        RUNNER_SCHEMA_VERSION_V28,
        RUNNER_SCHEMA_VERSION_V29,
        RUNNER_SCHEMA_VERSION_V30,
        RUNNER_SCHEMA_VERSION_V31,
        RUNNER_SCHEMA_VERSION_V32,
        }
        and config.environmental_dynamics is not None
    ):
        dynamics = config.environmental_dynamics
        if type(dynamics) is not EnvironmentalDynamicsSpec:
            raise TypeError(
                "environmental_dynamics must be EnvironmentalDynamicsSpec or None"
            )
        document["environmental_dynamics"] = dynamics.canonical_payload
    if config.schema_version in {
        RUNNER_SCHEMA_VERSION_V23,
        RUNNER_SCHEMA_VERSION_V24,
        RUNNER_SCHEMA_VERSION_V25,
        RUNNER_SCHEMA_VERSION_V26,
        RUNNER_SCHEMA_VERSION_V27,
    RUNNER_SCHEMA_VERSION_V28,
    RUNNER_SCHEMA_VERSION_V29,
    RUNNER_SCHEMA_VERSION_V30,
    RUNNER_SCHEMA_VERSION_V31,
    RUNNER_SCHEMA_VERSION_V32,
    }:
        document["v3_capability_flags"] = _encode_v3_capability_flags(
            config.v3_capability_flags
        )
        _LOG.debug(
            "runner_config_encode_v3_flags schema_version=%s flag_count=%s",
            config.schema_version,
            len(config.v3_capability_flags.enabled_names()),
        )
    if config.schema_version in {
        RUNNER_SCHEMA_VERSION_V24,
        RUNNER_SCHEMA_VERSION_V25,
        RUNNER_SCHEMA_VERSION_V26,
    } or (
        config.schema_version
        in {
            RUNNER_SCHEMA_VERSION_V27,
            RUNNER_SCHEMA_VERSION_V28,
            RUNNER_SCHEMA_VERSION_V29,
            RUNNER_SCHEMA_VERSION_V30,
            RUNNER_SCHEMA_VERSION_V31,
            RUNNER_SCHEMA_VERSION_V32,
        }
        and config.v3_capability_flags.generational_population
    ):
        lifecycle = config.population_lifecycle
        if type(lifecycle) is not PopulationLifecycleSpec:
            raise TypeError(
                "population_lifecycle must be PopulationLifecycleSpec on "
                f"{config.schema_version}"
            )
        document["population_lifecycle"] = _encode_population_lifecycle(
            lifecycle,
            schema_version=(
                config.schema_version
                if config.schema_version
                not in {
                    RUNNER_SCHEMA_VERSION_V27,
                    RUNNER_SCHEMA_VERSION_V28,
                    RUNNER_SCHEMA_VERSION_V29,
                    RUNNER_SCHEMA_VERSION_V30,
                    RUNNER_SCHEMA_VERSION_V31,
                    RUNNER_SCHEMA_VERSION_V32,
                }
                else RUNNER_SCHEMA_VERSION_V26
            ),
        )
        _LOG.info(
            "runner_config_encode_population_lifecycle schema_version=%s "
            "generational_population=%s developmental_extensions=%s",
            config.schema_version,
            config.v3_capability_flags.generational_population,
            lifecycle.has_developmental_extensions(),
        )
        _LOG.debug(
            "runner_config_encode_population_lifecycle policy_id=%s "
            "effect_count=%s",
            lifecycle.demographic_policy_id,
            len(lifecycle.stage_capability_effects),
        )
    if config.schema_version in {
        RUNNER_SCHEMA_VERSION_V25,
        RUNNER_SCHEMA_VERSION_V26,
    } or (
        config.schema_version
        in {
            RUNNER_SCHEMA_VERSION_V27,
            RUNNER_SCHEMA_VERSION_V28,
            RUNNER_SCHEMA_VERSION_V29,
            RUNNER_SCHEMA_VERSION_V30,
            RUNNER_SCHEMA_VERSION_V31,
            RUNNER_SCHEMA_VERSION_V32,
        }
        and config.v3_capability_flags.generational_population
    ):
        init_spec = config.new_agent_initialization
        document["new_agent_initialization"] = _encode_new_agent_initialization(
            init_spec
        )
        _LOG.debug(
            "runner_config_encode_new_agent_initialization schema_version=%s "
            "key_count=%s",
            config.schema_version,
            len(document["new_agent_initialization"]),
        )
    if config.schema_version in {
        RUNNER_SCHEMA_VERSION_V27,
        RUNNER_SCHEMA_VERSION_V28,
        RUNNER_SCHEMA_VERSION_V29,
        RUNNER_SCHEMA_VERSION_V30,
        RUNNER_SCHEMA_VERSION_V31,
        RUNNER_SCHEMA_VERSION_V32,
    }:
        if config.v3_capability_flags.kinship_inheritance:
            if config.kinship is None:
                raise TypeError(
                    "kinship must be KinshipSpec when kinship_inheritance is on"
                )
            document["kinship"] = _encode_kinship(config.kinship)
            _LOG.info(
                "runner_config_encode_kinship schema_version=%s "
                "kinship_inheritance=%s generational_population=%s edge_count=%s "
                "perception_mode=%s",
                config.schema_version,
                config.v3_capability_flags.kinship_inheritance,
                config.v3_capability_flags.generational_population,
                len(config.kinship.bootstrap_edges),
                config.kinship.perception_mode,
            )
        document["v3_capability_flags"] = _encode_v3_capability_flags(
            config.v3_capability_flags
        )
        if config.v3_capability_flags.generational_population:
            lifecycle = config.population_lifecycle
            if type(lifecycle) is not PopulationLifecycleSpec:
                raise TypeError(
                    "population_lifecycle required on v27/v28 with "
                    "generational_population"
                )
            document["population_lifecycle"] = _encode_population_lifecycle(
                lifecycle, schema_version=RUNNER_SCHEMA_VERSION_V26
            )
    if config.schema_version == RUNNER_SCHEMA_VERSION_V28:
        if config.dependency_care is None:
            raise TypeError(
                "dependency_care must be DependencyCareSpec on runner-config-v28"
            )
        document["dependency_care"] = _encode_dependency_care(config.dependency_care)
        _LOG.info(
            "runner_config_encode_dependency_care schema_version=%s "
            "enabled_needs=%s caregiving_cognition_mode=%s perception_mode=%s",
            config.schema_version,
            list(config.dependency_care.enabled_needs),
            config.dependency_care.caregiving_cognition_mode,
            config.dependency_care.perception_mode,
        )
    if config.schema_version == RUNNER_SCHEMA_VERSION_V29:
        if config.developmental_learning is None:
            raise TypeError(
                "developmental_learning must be DevelopmentalLearningSpec on "
                "runner-config-v29"
            )
        document["developmental_learning"] = _encode_developmental_learning(
            config.developmental_learning
        )
        if config.dependency_care is not None:
            document["dependency_care"] = _encode_dependency_care(
                config.dependency_care
            )
            _LOG.info(
                "runner_config_encode_dependency_care schema_version=%s "
                "enabled_needs=%s caregiving_cognition_mode=%s perception_mode=%s",
                config.schema_version,
                list(config.dependency_care.enabled_needs),
                config.dependency_care.caregiving_cognition_mode,
                config.dependency_care.perception_mode,
            )
        _LOG.info(
            "runner_config_encode_developmental_learning schema_version=%s "
            "enabled_domains=%s enabled_sources=%s "
            "developmental_learning_mode=%s applicability=%s "
            "learner_species_defaults_id=%s",
            config.schema_version,
            list(config.developmental_learning.enabled_domains),
            list(config.developmental_learning.enabled_sources),
            config.developmental_learning.developmental_learning_mode,
            config.developmental_learning.applicability,
            config.developmental_learning.learner_species_defaults_id,
        )
    if config.schema_version == RUNNER_SCHEMA_VERSION_V30:
        if config.mentorship is None:
            raise TypeError(
                "mentorship must be MentorshipSpec on runner-config-v30"
            )
        document["mentorship"] = _encode_mentorship(config.mentorship)
        if config.developmental_learning is not None:
            document["developmental_learning"] = _encode_developmental_learning(
                config.developmental_learning
            )
            _LOG.info(
                "runner_config_encode_developmental_learning schema_version=%s "
                "enabled_domains=%s enabled_sources=%s "
                "developmental_learning_mode=%s applicability=%s "
                "learner_species_defaults_id=%s",
                config.schema_version,
                list(config.developmental_learning.enabled_domains),
                list(config.developmental_learning.enabled_sources),
                config.developmental_learning.developmental_learning_mode,
                config.developmental_learning.applicability,
                config.developmental_learning.learner_species_defaults_id,
            )
        if config.dependency_care is not None:
            document["dependency_care"] = _encode_dependency_care(
                config.dependency_care
            )
            _LOG.info(
                "runner_config_encode_dependency_care schema_version=%s "
                "enabled_needs=%s caregiving_cognition_mode=%s perception_mode=%s",
                config.schema_version,
                list(config.dependency_care.enabled_needs),
                config.dependency_care.caregiving_cognition_mode,
                config.dependency_care.perception_mode,
            )
        _LOG.info(
            "runner_config_encode_mentorship schema_version=%s "
            "content_kind_count=%s bond_policy_form_after=%s max_hop_depth=%s "
            "mentorship_mode=%s applicability=%s",
            config.schema_version,
            len(config.mentorship.enabled_content_kinds),
            config.mentorship.bond_policy.form_after_successful_acts,
            config.mentorship.lineage_policy.max_hop_depth,
            config.mentorship.mentorship_mode,
            config.mentorship.applicability,
        )
    if config.schema_version == RUNNER_SCHEMA_VERSION_V31:
        if config.cultural_feature_provenance is None:
            raise TypeError(
                "cultural_feature_provenance must be CulturalFeatureProvenanceSpec "
                "on runner-config-v31"
            )
        document["cultural_feature_provenance"] = _encode_cultural_feature_provenance(
            config.cultural_feature_provenance
        )
        if config.mentorship is not None:
            document["mentorship"] = _encode_mentorship(config.mentorship)
            _LOG.info(
                "runner_config_encode_mentorship schema_version=%s "
                "content_kind_count=%s bond_policy_form_after=%s max_hop_depth=%s "
                "mentorship_mode=%s applicability=%s",
                config.schema_version,
                len(config.mentorship.enabled_content_kinds),
                config.mentorship.bond_policy.form_after_successful_acts,
                config.mentorship.lineage_policy.max_hop_depth,
                config.mentorship.mentorship_mode,
                config.mentorship.applicability,
            )
        if config.developmental_learning is not None:
            document["developmental_learning"] = _encode_developmental_learning(
                config.developmental_learning
            )
            _LOG.info(
                "runner_config_encode_developmental_learning schema_version=%s "
                "enabled_domains=%s enabled_sources=%s "
                "developmental_learning_mode=%s applicability=%s "
                "learner_species_defaults_id=%s",
                config.schema_version,
                list(config.developmental_learning.enabled_domains),
                list(config.developmental_learning.enabled_sources),
                config.developmental_learning.developmental_learning_mode,
                config.developmental_learning.applicability,
                config.developmental_learning.learner_species_defaults_id,
            )
        if config.dependency_care is not None:
            document["dependency_care"] = _encode_dependency_care(
                config.dependency_care
            )
            _LOG.info(
                "runner_config_encode_dependency_care schema_version=%s "
                "enabled_needs=%s caregiving_cognition_mode=%s perception_mode=%s",
                config.schema_version,
                list(config.dependency_care.enabled_needs),
                config.dependency_care.caregiving_cognition_mode,
                config.dependency_care.perception_mode,
            )
        _LOG.info(
            "runner_config_encode_cultural_feature_provenance schema_version=%s "
            "feature_kind_count=%s channel_count=%s mutation_allowed=%s "
            "recombination_allowed=%s applicability=%s",
            config.schema_version,
            len(config.cultural_feature_provenance.enabled_feature_kinds),
            len(config.cultural_feature_provenance.enabled_provenance_channels),
            config.cultural_feature_provenance.mutation_policy.allow_mutation,
            config.cultural_feature_provenance.recombination_policy.allow_recombination,
            config.cultural_feature_provenance.applicability,
        )
    if config.schema_version == RUNNER_SCHEMA_VERSION_V32:
        if config.cultural_feature_provenance is None:
            raise TypeError(
                "cultural_feature_provenance must be CulturalFeatureProvenanceSpec "
                "on runner-config-v32"
            )
        if config.historical_memory_layers is None:
            raise TypeError(
                "historical_memory_layers must be HistoricalMemoryLayersSpec "
                "on runner-config-v32"
            )
        document["cultural_feature_provenance"] = _encode_cultural_feature_provenance(
            config.cultural_feature_provenance
        )
        document["historical_memory_layers"] = _encode_historical_memory_layers(
            config.historical_memory_layers
        )
        if config.mentorship is not None:
            document["mentorship"] = _encode_mentorship(config.mentorship)
            _LOG.info(
                "runner_config_encode_mentorship schema_version=%s "
                "content_kind_count=%s bond_policy_form_after=%s max_hop_depth=%s "
                "mentorship_mode=%s applicability=%s",
                config.schema_version,
                len(config.mentorship.enabled_content_kinds),
                config.mentorship.bond_policy.form_after_successful_acts,
                config.mentorship.lineage_policy.max_hop_depth,
                config.mentorship.mentorship_mode,
                config.mentorship.applicability,
            )
        if config.developmental_learning is not None:
            document["developmental_learning"] = _encode_developmental_learning(
                config.developmental_learning
            )
            _LOG.info(
                "runner_config_encode_developmental_learning schema_version=%s "
                "enabled_domains=%s enabled_sources=%s "
                "developmental_learning_mode=%s applicability=%s "
                "learner_species_defaults_id=%s",
                config.schema_version,
                list(config.developmental_learning.enabled_domains),
                list(config.developmental_learning.enabled_sources),
                config.developmental_learning.developmental_learning_mode,
                config.developmental_learning.applicability,
                config.developmental_learning.learner_species_defaults_id,
            )
        if config.dependency_care is not None:
            document["dependency_care"] = _encode_dependency_care(
                config.dependency_care
            )
            _LOG.info(
                "runner_config_encode_dependency_care schema_version=%s "
                "enabled_needs=%s caregiving_cognition_mode=%s perception_mode=%s",
                config.schema_version,
                list(config.dependency_care.enabled_needs),
                config.dependency_care.caregiving_cognition_mode,
                config.dependency_care.perception_mode,
            )
        _LOG.info(
            "runner_config_encode_cultural_feature_provenance schema_version=%s "
            "feature_kind_count=%s channel_count=%s mutation_allowed=%s "
            "recombination_allowed=%s applicability=%s",
            config.schema_version,
            len(config.cultural_feature_provenance.enabled_feature_kinds),
            len(config.cultural_feature_provenance.enabled_provenance_channels),
            config.cultural_feature_provenance.mutation_policy.allow_mutation,
            config.cultural_feature_provenance.recombination_policy.allow_recombination,
            config.cultural_feature_provenance.applicability,
        )
        _LOG.info(
            "runner_config_encode_historical_memory_layers schema_version=%s "
            "max_communicative_hops=%s witness_definition=%s "
            "query_event_selector=%s transition_tick_resolution=%s "
            "applicability=%s",
            config.schema_version,
            config.historical_memory_layers.max_communicative_hops,
            config.historical_memory_layers.witness_definition,
            config.historical_memory_layers.query_event_selector,
            config.historical_memory_layers.transition_tick_resolution,
            config.historical_memory_layers.applicability,
        )
    if config.experiment is not None:
        document["experiment"] = {
            "condition_id": config.experiment.condition_id,
            "experiment_id": config.experiment.experiment_id,
            "replicate_index": config.experiment.replicate_index,
            "seed_ordinal": config.experiment.seed_ordinal,
        }
    else:
        document["experiment"] = None
    return document


def encode_runner_config(config: SimulationRunnerConfig) -> bytes:
    """Encode a runner config to strict canonical UTF-8 JSON bytes."""
    if type(config) is not SimulationRunnerConfig:
        raise TypeError("encode_runner_config requires SimulationRunnerConfig")
    return _canonical_dumps(_encode_runner_document(config))


def _decode_environmental_dynamics(data: object) -> EnvironmentalDynamicsSpec:
    path = "$.environmental_dynamics"
    if not isinstance(data, dict):
        raise RunnerSerializationError("invalid_object", path)
    _require_keys(
        data,
        {
            "hazard_rules",
            "season_length_ticks",
            "season_offsets",
            "shortage_windows",
            "yields",
        },
        path=path,
    )
    offsets_raw = data["season_offsets"]
    if not isinstance(offsets_raw, dict):
        raise RunnerSerializationError("invalid_object", f"{path}.season_offsets")
    offsets = {
        Season(name): _required_float(offsets_raw, name, path=f"{path}.season_offsets")
        for name in ("spring", "summer", "autumn", "winter")
    }
    yields = tuple(
        SeasonalYield(
            resource_kind=ResourceKind(item["resource_kind"]),
            season=Season(item["season"]),
            multiplier=item["multiplier"],
        )
        for item in _object_list(data["yields"], path=f"{path}.yields")
    )
    windows = tuple(
        ShortageWindow(
            resource_kind=ResourceKind(item["resource_kind"]),
            start_tick=item["start_tick"],
            duration_ticks=item["duration_ticks"],
        )
        for item in _object_list(
            data["shortage_windows"], path=f"{path}.shortage_windows"
        )
    )
    rules = tuple(
        HazardRule(
            kind=HazardKind(item["kind"]),
            season=Season(item["season"]),
            weather=WeatherCondition(item["weather"]),
            band=TemperatureBand(item["band"]),
            duration_ticks=item["duration_ticks"],
            exposure_extra=item["exposure_extra"],
        )
        for item in _object_list(data["hazard_rules"], path=f"{path}.hazard_rules")
    )
    return EnvironmentalDynamicsSpec(
        season_length_ticks=data["season_length_ticks"],
        season_offsets=offsets,
        yields=yields,
        shortage_windows=windows,
        hazard_rules=rules,
    )


def _object_list(value: object, *, path: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise RunnerSerializationError("invalid_array", path)
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise RunnerSerializationError("invalid_object", f"{path}[{index}]")
        rows.append(item)
    return rows


def decode_runner_config(payload: bytes) -> SimulationRunnerConfig:
    """Decode strict canonical runner config bytes."""
    if not isinstance(payload, (bytes, bytearray)):
        raise TypeError("decode_runner_config requires bytes")
    try:
        decoder = json.JSONDecoder(object_pairs_hook=_reject_duplicate_keys)
        data = decoder.decode(bytes(payload).decode("utf-8"))
    except RunnerSerializationError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RunnerSerializationError("invalid_json", "$") from exc
    if not isinstance(data, dict):
        raise RunnerSerializationError("invalid_object", "$")
    schema_version = data.get("schema_version")
    if not isinstance(schema_version, str):
        raise RunnerSerializationError("invalid_string", "$.schema_version")
    if schema_version not in SUPPORTED_RUNNER_SCHEMA_VERSIONS:
        raise RunnerSerializationError("unsupported_version", "$.schema_version")
    if schema_version == RUNNER_SCHEMA_VERSION_V32:
        has_lifecycle = "population_lifecycle" in data
        has_kinship = "kinship" in data
        has_dynamics = "environmental_dynamics" in data
        has_dependency_care = "dependency_care" in data
        has_developmental = "developmental_learning" in data
        has_mentorship = "mentorship" in data
        if has_lifecycle:
            if has_mentorship:
                if has_developmental:
                    if has_dependency_care:
                        if has_kinship:
                            root_keys = (
                                _RUNNER_ROOT_KEYS_V32_WITH_LIFECYCLE_AND_DYNAMICS
                                if has_dynamics
                                else _RUNNER_ROOT_KEYS_V32_WITH_LIFECYCLE
                            )
                        else:
                            root_keys = (
                                _RUNNER_ROOT_KEYS_V32_WITH_LIFECYCLE_NO_KINSHIP_AND_DYNAMICS
                                if has_dynamics
                                else _RUNNER_ROOT_KEYS_V32_WITH_LIFECYCLE_NO_KINSHIP
                            )
                    elif has_kinship:
                        root_keys = (
                            _RUNNER_ROOT_KEYS_V32_NO_DEPENDENCY_CARE_AND_DYNAMICS
                            if has_dynamics
                            else _RUNNER_ROOT_KEYS_V32_NO_DEPENDENCY_CARE
                        )
                    else:
                        root_keys = (
                            _RUNNER_ROOT_KEYS_V32_NO_DEPENDENCY_CARE_NO_KINSHIP_AND_DYNAMICS
                            if has_dynamics
                            else _RUNNER_ROOT_KEYS_V32_NO_DEPENDENCY_CARE_NO_KINSHIP
                        )
                elif has_dependency_care:
                    if has_kinship:
                        root_keys = (
                            _RUNNER_ROOT_KEYS_V32_NO_DEV_WITH_LIFECYCLE_AND_DYNAMICS
                            if has_dynamics
                            else _RUNNER_ROOT_KEYS_V32_NO_DEV_WITH_LIFECYCLE
                        )
                    else:
                        root_keys = (
                            _RUNNER_ROOT_KEYS_V32_NO_DEV_WITH_LIFECYCLE_NO_KINSHIP_AND_DYNAMICS
                            if has_dynamics
                            else _RUNNER_ROOT_KEYS_V32_NO_DEV_WITH_LIFECYCLE_NO_KINSHIP
                        )
                elif has_kinship:
                    root_keys = (
                        _RUNNER_ROOT_KEYS_V32_NO_DEV_NO_DEPENDENCY_CARE_AND_DYNAMICS
                        if has_dynamics
                        else _RUNNER_ROOT_KEYS_V32_NO_DEV_NO_DEPENDENCY_CARE
                    )
                else:
                    root_keys = (
                        _RUNNER_ROOT_KEYS_V32_NO_DEV_NO_DEPENDENCY_CARE_NO_KINSHIP_AND_DYNAMICS
                        if has_dynamics
                        else _RUNNER_ROOT_KEYS_V32_NO_DEV_NO_DEPENDENCY_CARE_NO_KINSHIP
                    )
            elif has_developmental:
                if has_dependency_care:
                    if has_kinship:
                        root_keys = (
                            _RUNNER_ROOT_KEYS_V32_NO_MENTORSHIP_WITH_LIFECYCLE_AND_DYNAMICS
                            if has_dynamics
                            else _RUNNER_ROOT_KEYS_V32_NO_MENTORSHIP_WITH_LIFECYCLE
                        )
                    else:
                        root_keys = (
                            _RUNNER_ROOT_KEYS_V32_NO_MENTORSHIP_WITH_LIFECYCLE_NO_KINSHIP_AND_DYNAMICS
                            if has_dynamics
                            else _RUNNER_ROOT_KEYS_V32_NO_MENTORSHIP_WITH_LIFECYCLE_NO_KINSHIP  # noqa: E501
                        )
                elif has_kinship:
                    root_keys = (
                        _RUNNER_ROOT_KEYS_V32_NO_MENTORSHIP_NO_DEPENDENCY_CARE_AND_DYNAMICS
                        if has_dynamics
                        else _RUNNER_ROOT_KEYS_V32_NO_MENTORSHIP_NO_DEPENDENCY_CARE
                    )
                else:
                    root_keys = (
                        _RUNNER_ROOT_KEYS_V32_NO_MENTORSHIP_NO_DEPENDENCY_CARE_NO_KINSHIP_AND_DYNAMICS
                        if has_dynamics
                        else _RUNNER_ROOT_KEYS_V32_NO_MENTORSHIP_NO_DEPENDENCY_CARE_NO_KINSHIP  # noqa: E501
                    )
            elif has_dependency_care:
                if has_kinship:
                    root_keys = (
                        _RUNNER_ROOT_KEYS_V32_NO_MENTORSHIP_NO_DEV_WITH_LIFECYCLE_AND_DYNAMICS
                        if has_dynamics
                        else _RUNNER_ROOT_KEYS_V32_NO_MENTORSHIP_NO_DEV_WITH_LIFECYCLE
                    )
                else:
                    root_keys = (
                        _RUNNER_ROOT_KEYS_V32_NO_MENTORSHIP_NO_DEV_WITH_LIFECYCLE_NO_KINSHIP_AND_DYNAMICS
                        if has_dynamics
                        else _RUNNER_ROOT_KEYS_V32_NO_MENTORSHIP_NO_DEV_WITH_LIFECYCLE_NO_KINSHIP  # noqa: E501
                    )
            elif has_kinship:
                root_keys = (
                    _RUNNER_ROOT_KEYS_V32_NO_MENTORSHIP_NO_DEV_NO_DEPENDENCY_CARE_AND_DYNAMICS
                    if has_dynamics
                    else _RUNNER_ROOT_KEYS_V32_NO_MENTORSHIP_NO_DEV_NO_DEPENDENCY_CARE
                )
            else:
                root_keys = (
                    _RUNNER_ROOT_KEYS_V32_NO_MENTORSHIP_NO_DEV_NO_DEPENDENCY_CARE_NO_KINSHIP_AND_DYNAMICS
                    if has_dynamics
                    else _RUNNER_ROOT_KEYS_V32_NO_MENTORSHIP_NO_DEV_NO_DEPENDENCY_CARE_NO_KINSHIP  # noqa: E501
                )
        elif has_kinship:
            root_keys = (
                _RUNNER_ROOT_KEYS_V32_CULTURAL_KINSHIP_ONLY_WITH_DYNAMICS
                if has_dynamics
                else _RUNNER_ROOT_KEYS_V32_CULTURAL_KINSHIP_ONLY
            )
        else:
            root_keys = (
                _RUNNER_ROOT_KEYS_V32_CULTURAL_ONLY_WITH_DYNAMICS
                if has_dynamics
                else _RUNNER_ROOT_KEYS_V32_CULTURAL_ONLY
            )
    elif schema_version == RUNNER_SCHEMA_VERSION_V31:
        has_lifecycle = "population_lifecycle" in data
        has_kinship = "kinship" in data
        has_dynamics = "environmental_dynamics" in data
        has_dependency_care = "dependency_care" in data
        has_developmental = "developmental_learning" in data
        has_mentorship = "mentorship" in data
        if has_lifecycle:
            if has_mentorship:
                if has_developmental:
                    if has_dependency_care:
                        if has_kinship:
                            root_keys = (
                                _RUNNER_ROOT_KEYS_V31_WITH_LIFECYCLE_AND_DYNAMICS
                                if has_dynamics
                                else _RUNNER_ROOT_KEYS_V31_WITH_LIFECYCLE
                            )
                        else:
                            root_keys = (
                                _RUNNER_ROOT_KEYS_V31_WITH_LIFECYCLE_NO_KINSHIP_AND_DYNAMICS
                                if has_dynamics
                                else _RUNNER_ROOT_KEYS_V31_WITH_LIFECYCLE_NO_KINSHIP
                            )
                    elif has_kinship:
                        root_keys = (
                            _RUNNER_ROOT_KEYS_V31_NO_DEPENDENCY_CARE_AND_DYNAMICS
                            if has_dynamics
                            else _RUNNER_ROOT_KEYS_V31_NO_DEPENDENCY_CARE
                        )
                    else:
                        root_keys = (
                            _RUNNER_ROOT_KEYS_V31_NO_DEPENDENCY_CARE_NO_KINSHIP_AND_DYNAMICS
                            if has_dynamics
                            else _RUNNER_ROOT_KEYS_V31_NO_DEPENDENCY_CARE_NO_KINSHIP
                        )
                elif has_dependency_care:
                    if has_kinship:
                        root_keys = (
                            _RUNNER_ROOT_KEYS_V31_NO_DEV_WITH_LIFECYCLE_AND_DYNAMICS
                            if has_dynamics
                            else _RUNNER_ROOT_KEYS_V31_NO_DEV_WITH_LIFECYCLE
                        )
                    else:
                        root_keys = (
                            _RUNNER_ROOT_KEYS_V31_NO_DEV_WITH_LIFECYCLE_NO_KINSHIP_AND_DYNAMICS
                            if has_dynamics
                            else _RUNNER_ROOT_KEYS_V31_NO_DEV_WITH_LIFECYCLE_NO_KINSHIP
                        )
                elif has_kinship:
                    root_keys = (
                        _RUNNER_ROOT_KEYS_V31_NO_DEV_NO_DEPENDENCY_CARE_AND_DYNAMICS
                        if has_dynamics
                        else _RUNNER_ROOT_KEYS_V31_NO_DEV_NO_DEPENDENCY_CARE
                    )
                else:
                    root_keys = (
                        _RUNNER_ROOT_KEYS_V31_NO_DEV_NO_DEPENDENCY_CARE_NO_KINSHIP_AND_DYNAMICS
                        if has_dynamics
                        else _RUNNER_ROOT_KEYS_V31_NO_DEV_NO_DEPENDENCY_CARE_NO_KINSHIP
                    )
            elif has_developmental:
                if has_dependency_care:
                    if has_kinship:
                        root_keys = (
                            _RUNNER_ROOT_KEYS_V31_NO_MENTORSHIP_WITH_LIFECYCLE_AND_DYNAMICS
                            if has_dynamics
                            else _RUNNER_ROOT_KEYS_V31_NO_MENTORSHIP_WITH_LIFECYCLE
                        )
                    else:
                        root_keys = (
                            _RUNNER_ROOT_KEYS_V31_NO_MENTORSHIP_WITH_LIFECYCLE_NO_KINSHIP_AND_DYNAMICS
                            if has_dynamics
                            else _RUNNER_ROOT_KEYS_V31_NO_MENTORSHIP_WITH_LIFECYCLE_NO_KINSHIP  # noqa: E501
                        )
                elif has_kinship:
                    root_keys = (
                        _RUNNER_ROOT_KEYS_V31_NO_MENTORSHIP_NO_DEPENDENCY_CARE_AND_DYNAMICS
                        if has_dynamics
                        else _RUNNER_ROOT_KEYS_V31_NO_MENTORSHIP_NO_DEPENDENCY_CARE
                    )
                else:
                    root_keys = (
                        _RUNNER_ROOT_KEYS_V31_NO_MENTORSHIP_NO_DEPENDENCY_CARE_NO_KINSHIP_AND_DYNAMICS
                        if has_dynamics
                        else _RUNNER_ROOT_KEYS_V31_NO_MENTORSHIP_NO_DEPENDENCY_CARE_NO_KINSHIP  # noqa: E501
                    )
            elif has_dependency_care:
                if has_kinship:
                    root_keys = (
                        _RUNNER_ROOT_KEYS_V31_NO_MENTORSHIP_NO_DEV_WITH_LIFECYCLE_AND_DYNAMICS
                        if has_dynamics
                        else _RUNNER_ROOT_KEYS_V31_NO_MENTORSHIP_NO_DEV_WITH_LIFECYCLE
                    )
                else:
                    root_keys = (
                        _RUNNER_ROOT_KEYS_V31_NO_MENTORSHIP_NO_DEV_WITH_LIFECYCLE_NO_KINSHIP_AND_DYNAMICS
                        if has_dynamics
                        else _RUNNER_ROOT_KEYS_V31_NO_MENTORSHIP_NO_DEV_WITH_LIFECYCLE_NO_KINSHIP  # noqa: E501
                    )
            elif has_kinship:
                root_keys = (
                    _RUNNER_ROOT_KEYS_V31_NO_MENTORSHIP_NO_DEV_NO_DEPENDENCY_CARE_AND_DYNAMICS
                    if has_dynamics
                    else _RUNNER_ROOT_KEYS_V31_NO_MENTORSHIP_NO_DEV_NO_DEPENDENCY_CARE
                )
            else:
                root_keys = (
                    _RUNNER_ROOT_KEYS_V31_NO_MENTORSHIP_NO_DEV_NO_DEPENDENCY_CARE_NO_KINSHIP_AND_DYNAMICS
                    if has_dynamics
                    else _RUNNER_ROOT_KEYS_V31_NO_MENTORSHIP_NO_DEV_NO_DEPENDENCY_CARE_NO_KINSHIP  # noqa: E501
                )
        elif has_kinship:
            root_keys = (
                _RUNNER_ROOT_KEYS_V31_CULTURAL_KINSHIP_ONLY_WITH_DYNAMICS
                if has_dynamics
                else _RUNNER_ROOT_KEYS_V31_CULTURAL_KINSHIP_ONLY
            )
        else:
            root_keys = (
                _RUNNER_ROOT_KEYS_V31_CULTURAL_ONLY_WITH_DYNAMICS
                if has_dynamics
                else _RUNNER_ROOT_KEYS_V31_CULTURAL_ONLY
            )
    elif schema_version == RUNNER_SCHEMA_VERSION_V30:
        has_kinship = "kinship" in data
        has_dynamics = "environmental_dynamics" in data
        has_dependency_care = "dependency_care" in data
        has_developmental = "developmental_learning" in data
        if has_developmental:
            if has_dependency_care:
                if has_kinship:
                    root_keys = (
                        _RUNNER_ROOT_KEYS_V30_WITH_LIFECYCLE_AND_DYNAMICS
                        if has_dynamics
                        else _RUNNER_ROOT_KEYS_V30_WITH_LIFECYCLE
                    )
                else:
                    root_keys = (
                        _RUNNER_ROOT_KEYS_V30_WITH_LIFECYCLE_NO_KINSHIP_AND_DYNAMICS
                        if has_dynamics
                        else _RUNNER_ROOT_KEYS_V30_WITH_LIFECYCLE_NO_KINSHIP
                    )
            elif has_kinship:
                root_keys = (
                    _RUNNER_ROOT_KEYS_V30_NO_DEPENDENCY_CARE_AND_DYNAMICS
                    if has_dynamics
                    else _RUNNER_ROOT_KEYS_V30_NO_DEPENDENCY_CARE
                )
            else:
                root_keys = (
                    _RUNNER_ROOT_KEYS_V30_NO_DEPENDENCY_CARE_NO_KINSHIP_AND_DYNAMICS
                    if has_dynamics
                    else _RUNNER_ROOT_KEYS_V30_NO_DEPENDENCY_CARE_NO_KINSHIP
                )
        elif has_dependency_care:
            if has_kinship:
                root_keys = (
                    _RUNNER_ROOT_KEYS_V30_NO_DEV_WITH_LIFECYCLE_AND_DYNAMICS
                    if has_dynamics
                    else _RUNNER_ROOT_KEYS_V30_NO_DEV_WITH_LIFECYCLE
                )
            else:
                root_keys = (
                    _RUNNER_ROOT_KEYS_V30_NO_DEV_WITH_LIFECYCLE_NO_KINSHIP_AND_DYNAMICS
                    if has_dynamics
                    else _RUNNER_ROOT_KEYS_V30_NO_DEV_WITH_LIFECYCLE_NO_KINSHIP
                )
        elif has_kinship:
            root_keys = (
                _RUNNER_ROOT_KEYS_V30_NO_DEV_NO_DEPENDENCY_CARE_AND_DYNAMICS
                if has_dynamics
                else _RUNNER_ROOT_KEYS_V30_NO_DEV_NO_DEPENDENCY_CARE
            )
        else:
            root_keys = (
                _RUNNER_ROOT_KEYS_V30_NO_DEV_NO_DEPENDENCY_CARE_NO_KINSHIP_AND_DYNAMICS
                if has_dynamics
                else _RUNNER_ROOT_KEYS_V30_NO_DEV_NO_DEPENDENCY_CARE_NO_KINSHIP
            )
    elif schema_version == RUNNER_SCHEMA_VERSION_V29:
        has_kinship = "kinship" in data
        has_dynamics = "environmental_dynamics" in data
        has_dependency_care = "dependency_care" in data
        if has_dependency_care:
            if has_kinship:
                root_keys = (
                    _RUNNER_ROOT_KEYS_V29_WITH_LIFECYCLE_AND_DYNAMICS
                    if has_dynamics
                    else _RUNNER_ROOT_KEYS_V29_WITH_LIFECYCLE
                )
            else:
                root_keys = (
                    _RUNNER_ROOT_KEYS_V29_WITH_LIFECYCLE_NO_KINSHIP_AND_DYNAMICS
                    if has_dynamics
                    else _RUNNER_ROOT_KEYS_V29_WITH_LIFECYCLE_NO_KINSHIP
                )
        elif has_kinship:
            root_keys = (
                _RUNNER_ROOT_KEYS_V29_NO_DEPENDENCY_CARE_AND_DYNAMICS
                if has_dynamics
                else _RUNNER_ROOT_KEYS_V29_NO_DEPENDENCY_CARE
            )
        else:
            root_keys = (
                _RUNNER_ROOT_KEYS_V29_NO_DEPENDENCY_CARE_NO_KINSHIP_AND_DYNAMICS
                if has_dynamics
                else _RUNNER_ROOT_KEYS_V29_NO_DEPENDENCY_CARE_NO_KINSHIP
            )
    elif schema_version == RUNNER_SCHEMA_VERSION_V28:
        has_kinship = "kinship" in data
        has_dynamics = "environmental_dynamics" in data
        if has_kinship:
            root_keys = (
                _RUNNER_ROOT_KEYS_V28_WITH_LIFECYCLE_AND_DYNAMICS
                if has_dynamics
                else _RUNNER_ROOT_KEYS_V28_WITH_LIFECYCLE
            )
        else:
            root_keys = (
                _RUNNER_ROOT_KEYS_V28_WITH_LIFECYCLE_NO_KINSHIP_AND_DYNAMICS
                if has_dynamics
                else _RUNNER_ROOT_KEYS_V28_WITH_LIFECYCLE_NO_KINSHIP
            )
    elif schema_version == RUNNER_SCHEMA_VERSION_V27:
        with_lifecycle = "population_lifecycle" in data
        if with_lifecycle:
            root_keys = (
                _RUNNER_ROOT_KEYS_V27_WITH_LIFECYCLE_AND_DYNAMICS
                if "environmental_dynamics" in data
                else _RUNNER_ROOT_KEYS_V27_WITH_LIFECYCLE
            )
        else:
            root_keys = (
                _RUNNER_ROOT_KEYS_V27_KINSHIP_ONLY_WITH_DYNAMICS
                if "environmental_dynamics" in data
                else _RUNNER_ROOT_KEYS_V27_KINSHIP_ONLY
            )
    elif schema_version == RUNNER_SCHEMA_VERSION_V26:
        root_keys = (
            _RUNNER_ROOT_KEYS_V26_WITH_DYNAMICS
            if "environmental_dynamics" in data
            else _RUNNER_ROOT_KEYS_V26
        )
    elif schema_version == RUNNER_SCHEMA_VERSION_V25:
        root_keys = (
            _RUNNER_ROOT_KEYS_V25_WITH_DYNAMICS
            if "environmental_dynamics" in data
            else _RUNNER_ROOT_KEYS_V25
        )
    elif schema_version == RUNNER_SCHEMA_VERSION_V24:
        root_keys = (
            _RUNNER_ROOT_KEYS_V24_WITH_DYNAMICS
            if "environmental_dynamics" in data
            else _RUNNER_ROOT_KEYS_V24
        )
    elif schema_version == RUNNER_SCHEMA_VERSION_V23:
        root_keys = (
            _RUNNER_ROOT_KEYS_V23_WITH_DYNAMICS
            if "environmental_dynamics" in data
            else _RUNNER_ROOT_KEYS_V23
        )
    elif schema_version == RUNNER_SCHEMA_VERSION_V14:
        root_keys = _RUNNER_ROOT_KEYS_V14
    elif schema_version in {
        RUNNER_SCHEMA_VERSION_V15,
        RUNNER_SCHEMA_VERSION_V16,
        RUNNER_SCHEMA_VERSION_V17,
        RUNNER_SCHEMA_VERSION_V18,
        RUNNER_SCHEMA_VERSION_V19,
        RUNNER_SCHEMA_VERSION_V20,
        RUNNER_SCHEMA_VERSION_V21,
        RUNNER_SCHEMA_VERSION_V22,
    }:
        root_keys = (
            _RUNNER_ROOT_KEYS_V14
            if "environmental_dynamics" in data
            else _RUNNER_ROOT_KEYS_V4
        )
    elif schema_version in {
        RUNNER_SCHEMA_VERSION_V4,
        RUNNER_SCHEMA_VERSION_V5,
        RUNNER_SCHEMA_VERSION_V6,
        RUNNER_SCHEMA_VERSION_V7,
        RUNNER_SCHEMA_VERSION_V8,
        RUNNER_SCHEMA_VERSION_V9,
        RUNNER_SCHEMA_VERSION_V10,
        RUNNER_SCHEMA_VERSION_V11,
        RUNNER_SCHEMA_VERSION_V12,
        RUNNER_SCHEMA_VERSION_V13,
        RUNNER_SCHEMA_VERSION_V14,
        RUNNER_SCHEMA_VERSION_V15,
        RUNNER_SCHEMA_VERSION_V16,
        RUNNER_SCHEMA_VERSION_V17,
        RUNNER_SCHEMA_VERSION_V18,
        RUNNER_SCHEMA_VERSION_V19,
        RUNNER_SCHEMA_VERSION_V20,
        RUNNER_SCHEMA_VERSION_V21,
        RUNNER_SCHEMA_VERSION_V22,
    }:
        root_keys = _RUNNER_ROOT_KEYS_V4
    elif schema_version == RUNNER_SCHEMA_VERSION_V3:
        root_keys = _RUNNER_ROOT_KEYS_V3
    else:
        root_keys = _RUNNER_ROOT_KEYS_LEGACY
    _require_keys(data, root_keys, path="$")
    mortality_policy = _str_field(data, "mortality_policy_version", path="$")
    if mortality_policy != MORTALITY_POLICY_VERSION:
        raise RunnerSerializationError(
            "unsupported_version", "$.mortality_policy_version"
        )
    scenario_raw = data["scenario"]
    provider_raw = data["provider"]
    agents_raw = data["agents"]
    stop_raw = data["stop_policy"]
    persistence_raw = data["persistence"]
    if not isinstance(scenario_raw, dict):
        raise RunnerSerializationError("invalid_object", "$.scenario")
    if not isinstance(provider_raw, dict):
        raise RunnerSerializationError("invalid_object", "$.provider")
    if not isinstance(agents_raw, list):
        raise RunnerSerializationError("invalid_array", "$.agents")
    if not isinstance(stop_raw, dict):
        raise RunnerSerializationError("invalid_object", "$.stop_policy")
    if not isinstance(persistence_raw, dict):
        raise RunnerSerializationError("invalid_object", "$.persistence")
    _require_keys(
        stop_raw,
        {
            "max_ticks",
            "stop_on_all_agents_terminal",
            "allow_injected_stop",
            "allow_cancellation",
        },
        path="$.stop_policy",
    )
    _require_keys(persistence_raw, {"durable", "checkpoint"}, path="$.persistence")
    checkpoint_raw = persistence_raw["checkpoint"]
    if not isinstance(checkpoint_raw, dict):
        raise RunnerSerializationError("invalid_object", "$.persistence.checkpoint")
    _require_keys(
        checkpoint_raw, {"enabled", "cadence_ticks"}, path="$.persistence.checkpoint"
    )
    experiment: ExperimentAssignmentRef | None = None
    experiment_raw = data["experiment"]
    if experiment_raw is not None:
        if not isinstance(experiment_raw, dict):
            raise RunnerSerializationError("invalid_object", "$.experiment")
        _require_keys(
            experiment_raw,
            {"experiment_id", "condition_id", "replicate_index", "seed_ordinal"},
            path="$.experiment",
        )
        try:
            experiment = ExperimentAssignmentRef(
                experiment_id=_str_field(
                    experiment_raw, "experiment_id", path="$.experiment"
                ),
                condition_id=_str_field(
                    experiment_raw, "condition_id", path="$.experiment"
                ),
                replicate_index=_nonneg_int_field(
                    experiment_raw, "replicate_index", path="$.experiment"
                ),
                seed_ordinal=_nonneg_int_field(
                    experiment_raw, "seed_ordinal", path="$.experiment"
                ),
            )
        except (TypeError, ValueError) as exc:
            raise RunnerSerializationError("invalid_model", "$.experiment") from exc
    if schema_version in {
        RUNNER_SCHEMA_VERSION_V3,
        RUNNER_SCHEMA_VERSION_V4,
        RUNNER_SCHEMA_VERSION_V5,
        RUNNER_SCHEMA_VERSION_V6,
        RUNNER_SCHEMA_VERSION_V7,
        RUNNER_SCHEMA_VERSION_V8,
        RUNNER_SCHEMA_VERSION_V9,
        RUNNER_SCHEMA_VERSION_V10,
        RUNNER_SCHEMA_VERSION_V11,
        RUNNER_SCHEMA_VERSION_V12,
        RUNNER_SCHEMA_VERSION_V13,
        RUNNER_SCHEMA_VERSION_V14,
        RUNNER_SCHEMA_VERSION_V15,
        RUNNER_SCHEMA_VERSION_V16,
        RUNNER_SCHEMA_VERSION_V17,
        RUNNER_SCHEMA_VERSION_V18,
        RUNNER_SCHEMA_VERSION_V19,
        RUNNER_SCHEMA_VERSION_V20,
        RUNNER_SCHEMA_VERSION_V21,
        RUNNER_SCHEMA_VERSION_V22,
        RUNNER_SCHEMA_VERSION_V23,
        RUNNER_SCHEMA_VERSION_V24,
        RUNNER_SCHEMA_VERSION_V25,
        RUNNER_SCHEMA_VERSION_V26,
        RUNNER_SCHEMA_VERSION_V27,
        RUNNER_SCHEMA_VERSION_V28,
        RUNNER_SCHEMA_VERSION_V29,
        RUNNER_SCHEMA_VERSION_V30,
        RUNNER_SCHEMA_VERSION_V31,
        RUNNER_SCHEMA_VERSION_V32,
    }:
        capability_flags = _decode_capability_flags(
            data["capability_flags"], path="$.capability_flags"
        )
    else:
        # Legacy v1/v2 decode upgrades to default-off flags.
        capability_flags = V2CapabilityFlags()
    if schema_version in {
        RUNNER_SCHEMA_VERSION_V23,
        RUNNER_SCHEMA_VERSION_V24,
        RUNNER_SCHEMA_VERSION_V25,
        RUNNER_SCHEMA_VERSION_V26,
        RUNNER_SCHEMA_VERSION_V27,
        RUNNER_SCHEMA_VERSION_V28,
        RUNNER_SCHEMA_VERSION_V29,
        RUNNER_SCHEMA_VERSION_V30,
        RUNNER_SCHEMA_VERSION_V31,
        RUNNER_SCHEMA_VERSION_V32,
    }:
        v3_capability_flags = _decode_v3_capability_flags(
            data["v3_capability_flags"], path="$.v3_capability_flags"
        )
        _LOG.debug(
            "runner_config_decode_v3_flags schema_version=%s flag_count=%s",
            schema_version,
            len(v3_capability_flags.enabled_names()),
        )
    else:
        # Legacy v1-v22 decode upgrades to default-off V3 flags.
        v3_capability_flags = V3CapabilityFlags()
        _LOG.debug(
            "runner_config_v3_flags_synthesized schema_version=%s",
            schema_version,
        )
    if schema_version == RUNNER_SCHEMA_VERSION_V27 or (
        schema_version
        in {
            RUNNER_SCHEMA_VERSION_V28,
            RUNNER_SCHEMA_VERSION_V29,
            RUNNER_SCHEMA_VERSION_V30,
            RUNNER_SCHEMA_VERSION_V31,
            RUNNER_SCHEMA_VERSION_V32,
        }
        and "kinship" in data
    ):
        kinship = _decode_kinship(data["kinship"], path="$.kinship")
        _LOG.info(
            "runner_config_decode_kinship schema_version=%s edge_count=%s "
            "perception_mode=%s generational_population=%s",
            schema_version,
            len(kinship.bootstrap_edges),
            kinship.perception_mode,
            v3_capability_flags.generational_population,
        )
    else:
        kinship = None
    if schema_version == RUNNER_SCHEMA_VERSION_V28 or (
        schema_version
        in {
            RUNNER_SCHEMA_VERSION_V29,
            RUNNER_SCHEMA_VERSION_V30,
            RUNNER_SCHEMA_VERSION_V31,
            RUNNER_SCHEMA_VERSION_V32,
        }
        and "dependency_care" in data
    ):
        dependency_care = _decode_dependency_care(
            data["dependency_care"], path="$.dependency_care"
        )
        _LOG.info(
            "runner_config_decode_dependency_care schema_version=%s "
            "enabled_needs=%s caregiving_cognition_mode=%s perception_mode=%s",
            schema_version,
            list(dependency_care.enabled_needs),
            dependency_care.caregiving_cognition_mode,
            dependency_care.perception_mode,
        )
    else:
        dependency_care = None
    if schema_version == RUNNER_SCHEMA_VERSION_V29 or (
        schema_version
        in {
            RUNNER_SCHEMA_VERSION_V30,
            RUNNER_SCHEMA_VERSION_V31,
            RUNNER_SCHEMA_VERSION_V32,
        }
        and "developmental_learning" in data
    ):
        developmental_learning = _decode_developmental_learning(
            data["developmental_learning"], path="$.developmental_learning"
        )
        _LOG.info(
            "runner_config_decode_developmental_learning schema_version=%s "
            "enabled_domains=%s enabled_sources=%s "
            "developmental_learning_mode=%s applicability=%s "
            "learner_species_defaults_id=%s",
            schema_version,
            list(developmental_learning.enabled_domains),
            list(developmental_learning.enabled_sources),
            developmental_learning.developmental_learning_mode,
            developmental_learning.applicability,
            developmental_learning.learner_species_defaults_id,
        )
    else:
        developmental_learning = None
    if schema_version == RUNNER_SCHEMA_VERSION_V30:
        mentorship = _decode_mentorship(data["mentorship"], path="$.mentorship")
        _LOG.info(
            "runner_config_decode_mentorship schema_version=%s "
            "content_kind_count=%s bond_policy_form_after=%s max_hop_depth=%s "
            "mentorship_mode=%s applicability=%s",
            schema_version,
            len(mentorship.enabled_content_kinds),
            mentorship.bond_policy.form_after_successful_acts,
            mentorship.lineage_policy.max_hop_depth,
            mentorship.mentorship_mode,
            mentorship.applicability,
        )
    elif (
        schema_version
        in {RUNNER_SCHEMA_VERSION_V31, RUNNER_SCHEMA_VERSION_V32}
        and "mentorship" in data
    ):
        mentorship = _decode_mentorship(data["mentorship"], path="$.mentorship")
        _LOG.info(
            "runner_config_decode_mentorship schema_version=%s "
            "content_kind_count=%s bond_policy_form_after=%s max_hop_depth=%s "
            "mentorship_mode=%s applicability=%s",
            schema_version,
            len(mentorship.enabled_content_kinds),
            mentorship.bond_policy.form_after_successful_acts,
            mentorship.lineage_policy.max_hop_depth,
            mentorship.mentorship_mode,
            mentorship.applicability,
        )
    else:
        mentorship = None
        _LOG.debug(
            "runner_config_decode_mentorship_absent schema_version=%s "
            "mentorship_active=%s",
            schema_version,
            False,
        )
    if schema_version in {RUNNER_SCHEMA_VERSION_V31, RUNNER_SCHEMA_VERSION_V32}:
        cultural_feature_provenance = _decode_cultural_feature_provenance(
            data["cultural_feature_provenance"],
            path="$.cultural_feature_provenance",
        )
        _LOG.info(
            "runner_config_decode_cultural_feature_provenance schema_version=%s "
            "feature_kind_count=%s channel_count=%s mutation_allowed=%s "
            "recombination_allowed=%s applicability=%s",
            schema_version,
            len(cultural_feature_provenance.enabled_feature_kinds),
            len(cultural_feature_provenance.enabled_provenance_channels),
            cultural_feature_provenance.mutation_policy.allow_mutation,
            cultural_feature_provenance.recombination_policy.allow_recombination,
            cultural_feature_provenance.applicability,
        )
    else:
        cultural_feature_provenance = None
        _LOG.debug(
            "runner_config_decode_cultural_feature_provenance_absent "
            "schema_version=%s cultural_feature_active=%s",
            schema_version,
            False,
        )
    if schema_version == RUNNER_SCHEMA_VERSION_V32:
        historical_memory_layers = _decode_historical_memory_layers(
            data["historical_memory_layers"],
            path="$.historical_memory_layers",
        )
        _LOG.debug(
            "runner_config_decode_historical_memory_layers schema_version=%s "
            "historical_memory_layers_present=%s max_communicative_hops=%s "
            "witness_definition=%s",
            schema_version,
            True,
            historical_memory_layers.max_communicative_hops,
            historical_memory_layers.witness_definition,
        )
    else:
        historical_memory_layers = None
        _LOG.debug(
            "runner_config_decode_historical_memory_layers_absent "
            "schema_version=%s historical_memory_layers_present=%s",
            schema_version,
            False,
        )
    if schema_version in {
        RUNNER_SCHEMA_VERSION_V24,
        RUNNER_SCHEMA_VERSION_V25,
        RUNNER_SCHEMA_VERSION_V26,
        RUNNER_SCHEMA_VERSION_V27,
        RUNNER_SCHEMA_VERSION_V28,
        RUNNER_SCHEMA_VERSION_V29,
        RUNNER_SCHEMA_VERSION_V30,
        RUNNER_SCHEMA_VERSION_V31,
        RUNNER_SCHEMA_VERSION_V32,
    } and (
        schema_version
        not in {
            RUNNER_SCHEMA_VERSION_V27,
            RUNNER_SCHEMA_VERSION_V28,
            RUNNER_SCHEMA_VERSION_V29,
            RUNNER_SCHEMA_VERSION_V30,
            RUNNER_SCHEMA_VERSION_V31,
            RUNNER_SCHEMA_VERSION_V32,
        }
        or v3_capability_flags.generational_population
    ):
        population_lifecycle = _decode_population_lifecycle(
            data["population_lifecycle"],
            path="$.population_lifecycle",
            schema_version=(
                schema_version
                if schema_version
                not in {
                    RUNNER_SCHEMA_VERSION_V27,
                    RUNNER_SCHEMA_VERSION_V28,
                    RUNNER_SCHEMA_VERSION_V29,
                    RUNNER_SCHEMA_VERSION_V30,
                    RUNNER_SCHEMA_VERSION_V31,
                    RUNNER_SCHEMA_VERSION_V32,
                }
                else RUNNER_SCHEMA_VERSION_V26
            ),
        )
        _LOG.debug(
            "runner_config_decode_population_lifecycle schema_version=%s "
            "policy_id=%s developmental_extensions=%s",
            schema_version,
            population_lifecycle.demographic_policy_id,
            population_lifecycle.has_developmental_extensions(),
        )
    else:
        population_lifecycle = None
    if schema_version in {
        RUNNER_SCHEMA_VERSION_V25,
        RUNNER_SCHEMA_VERSION_V26,
    } or (
        schema_version
        in {
            RUNNER_SCHEMA_VERSION_V27,
            RUNNER_SCHEMA_VERSION_V28,
            RUNNER_SCHEMA_VERSION_V29,
            RUNNER_SCHEMA_VERSION_V30,
            RUNNER_SCHEMA_VERSION_V31,
            RUNNER_SCHEMA_VERSION_V32,
        }
        and v3_capability_flags.generational_population
    ):
        new_agent_initialization = _decode_new_agent_initialization(
            data["new_agent_initialization"], path="$.new_agent_initialization"
        )
        _LOG.debug(
            "runner_config_decode_new_agent_initialization schema_version=%s "
            "key_count=%s",
            schema_version,
            len(data["new_agent_initialization"]),
        )
    elif schema_version == RUNNER_SCHEMA_VERSION_V24:
        from simulation.new_agent_initialization import (
            default_new_agent_initialization_spec,
        )

        new_agent_initialization = default_new_agent_initialization_spec()
        _LOG.debug(
            "runner_config_new_agent_initialization_synthesized "
            "schema_version=%s",
            schema_version,
        )
    else:
        new_agent_initialization = None
    if schema_version in {
        RUNNER_SCHEMA_VERSION_V4,
        RUNNER_SCHEMA_VERSION_V5,
        RUNNER_SCHEMA_VERSION_V6,
        RUNNER_SCHEMA_VERSION_V7,
        RUNNER_SCHEMA_VERSION_V8,
        RUNNER_SCHEMA_VERSION_V9,
        RUNNER_SCHEMA_VERSION_V10,
        RUNNER_SCHEMA_VERSION_V11,
        RUNNER_SCHEMA_VERSION_V12,
        RUNNER_SCHEMA_VERSION_V13,
        RUNNER_SCHEMA_VERSION_V14,
        RUNNER_SCHEMA_VERSION_V15,
        RUNNER_SCHEMA_VERSION_V16,
        RUNNER_SCHEMA_VERSION_V17,
        RUNNER_SCHEMA_VERSION_V18,
        RUNNER_SCHEMA_VERSION_V19,
        RUNNER_SCHEMA_VERSION_V20,
        RUNNER_SCHEMA_VERSION_V21,
        RUNNER_SCHEMA_VERSION_V22,
        RUNNER_SCHEMA_VERSION_V23,
        RUNNER_SCHEMA_VERSION_V24,
        RUNNER_SCHEMA_VERSION_V25,
        RUNNER_SCHEMA_VERSION_V26,
        RUNNER_SCHEMA_VERSION_V27,
    RUNNER_SCHEMA_VERSION_V28,
    RUNNER_SCHEMA_VERSION_V29,
    RUNNER_SCHEMA_VERSION_V30,
    RUNNER_SCHEMA_VERSION_V31,
    RUNNER_SCHEMA_VERSION_V32,
    }:
        cognition_trace = _decode_cognition_trace(
            data["cognition_trace"], path="$.cognition_trace"
        )
    else:
        # Legacy v1/v2/v3 decode upgrades to disabled tracing.
        cognition_trace = CognitionTraceSpec()
    agents_list: list[AgentRunnerSpec] = []
    for index, item in enumerate(agents_raw):
        if not isinstance(item, dict):
            raise RunnerSerializationError("invalid_object", f"$.agents[{index}]")
        agents_list.append(
            _decode_agent(
                item, path=f"$.agents[{index}]", schema_version=schema_version
            )
        )
    cadence = checkpoint_raw["cadence_ticks"]
    if cadence is not None and (
        isinstance(cadence, bool) or not isinstance(cadence, int) or cadence < 0
    ):
        raise RunnerSerializationError(
            "invalid_int", "$.persistence.checkpoint.cadence_ticks"
        )
    try:
        return SimulationRunnerConfig(
            seed=_nonneg_int_field(data, "seed", path="$"),
            stochastic_identity=StochasticIdentity(
                _str_field(data, "stochastic_identity", path="$")
            ),
            scenario=_decode_scenario(scenario_raw, path="$.scenario"),
            agents=tuple(agents_list),
            stop_policy=RunnerStopPolicy(
                max_ticks=_nonneg_int_field(
                    stop_raw, "max_ticks", path="$.stop_policy"
                ),
                stop_on_all_agents_terminal=_bool_field(
                    stop_raw, "stop_on_all_agents_terminal", path="$.stop_policy"
                ),
                allow_injected_stop=_bool_field(
                    stop_raw, "allow_injected_stop", path="$.stop_policy"
                ),
                allow_cancellation=_bool_field(
                    stop_raw, "allow_cancellation", path="$.stop_policy"
                ),
            ),
            mortality_mode=MortalityMode(_str_field(data, "mortality_mode", path="$")),
            cognition_failure_policy=CognitionFailurePolicy(
                _str_field(data, "cognition_failure_policy", path="$")
            ),
            provider=_decode_provider(provider_raw, path="$.provider"),
            persistence=RunnerPersistenceSpec(
                durable=_bool_field(persistence_raw, "durable", path="$.persistence"),
                checkpoint=RunnerCheckpointPolicy(
                    enabled=_bool_field(
                        checkpoint_raw, "enabled", path="$.persistence.checkpoint"
                    ),
                    cadence_ticks=cadence,
                ),
            ),
            experiment=experiment,
            capability_flags=capability_flags,
            v3_capability_flags=v3_capability_flags,
            cognition_trace=cognition_trace,
            schema_version=_str_field(data, "schema_version", path="$"),
            derivation_version=_str_field(data, "derivation_version", path="$"),
            mortality_policy_version=_str_field(
                data, "mortality_policy_version", path="$"
            ),
            environmental_dynamics=(
                _decode_environmental_dynamics(data["environmental_dynamics"])
                if schema_version == RUNNER_SCHEMA_VERSION_V14
                or (
                    schema_version
                    in {
                        RUNNER_SCHEMA_VERSION_V15,
                        RUNNER_SCHEMA_VERSION_V16,
                        RUNNER_SCHEMA_VERSION_V17,
                        RUNNER_SCHEMA_VERSION_V18,
                        RUNNER_SCHEMA_VERSION_V19,
                        RUNNER_SCHEMA_VERSION_V20,
                        RUNNER_SCHEMA_VERSION_V21,
                        RUNNER_SCHEMA_VERSION_V22,
                        RUNNER_SCHEMA_VERSION_V23,
                        RUNNER_SCHEMA_VERSION_V24,
                        RUNNER_SCHEMA_VERSION_V25,
                        RUNNER_SCHEMA_VERSION_V26,
                        RUNNER_SCHEMA_VERSION_V27,
                    RUNNER_SCHEMA_VERSION_V28,
                    RUNNER_SCHEMA_VERSION_V29,
                    RUNNER_SCHEMA_VERSION_V30,
                    RUNNER_SCHEMA_VERSION_V31,
                    RUNNER_SCHEMA_VERSION_V32,
                    }
                    and "environmental_dynamics" in data
                )
                else None
            ),
            population_lifecycle=population_lifecycle,
            new_agent_initialization=new_agent_initialization,
            kinship=kinship,
            dependency_care=dependency_care,
            developmental_learning=developmental_learning,
            mentorship=mentorship,
            cultural_feature_provenance=cultural_feature_provenance,
            historical_memory_layers=historical_memory_layers,
        )
    except RunnerSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise RunnerSerializationError("invalid_model", "$") from exc


def runner_config_fingerprint(config: SimulationRunnerConfig) -> str:
    return _sha256_hex(encode_runner_config(config))


def scenario_fingerprint(config: SimulationRunnerConfig) -> str:
    document = {
        "derivation_version": config.derivation_version,
        "scenario": _encode_scenario(config.scenario),
        "seed": config.seed,
        "stochastic_identity": config.stochastic_identity.value,
    }
    return _sha256_hex(_canonical_dumps(document))


def cognition_fingerprint(config: SimulationRunnerConfig) -> str:
    document = {
        "agents": [
            {
                "agent_id": agent.agent_id.value,
                "cognition": _encode_cognition(
                    agent.cognition, schema_version=config.schema_version
                ),
            }
            for agent in config.agents
        ],
        "mortality_mode": config.mortality_mode.value,
        "mortality_policy_version": config.mortality_policy_version,
        "policy_version": COGNITION_POLICY_VERSION,
    }
    return _sha256_hex(_canonical_dumps(document))


def provider_fingerprint(config: SimulationRunnerConfig) -> str:
    document = {
        "provider": _encode_provider(config.provider),
        "settings_version": PROVIDER_SETTINGS_VERSION,
    }
    return _sha256_hex(_canonical_dumps(document))


def build_runner_diagnostics(
    config: SimulationRunnerConfig,
) -> RunnerConfigDiagnostics:
    """Convenience wrapper used by contracts logging helpers."""
    return runner_config_diagnostics(
        config,
        config_fingerprint=runner_config_fingerprint(config),
        scenario_fingerprint=scenario_fingerprint(config),
        cognition_fingerprint=cognition_fingerprint(config),
        provider_fingerprint=provider_fingerprint(config),
    )


def encode_runner_result_document(document: object) -> bytes:
    """Encode a result document as strict canonical JSON bytes."""
    if type(document) is not SimulationRunnerResultDocument:
        raise TypeError(
            "encode_runner_result_document requires SimulationRunnerResultDocument"
        )
    payload: dict[str, Any] = {
        "attempt_count": document.attempt_count,
        "cognition_fingerprint": document.cognition_fingerprint,
        "config_fingerprint": document.config_fingerprint,
        "exact_trajectory_hash": document.exact_trajectory_hash,
        "replica_normalized_trajectory_hash": (
            document.replica_normalized_trajectory_hash
        ),
        "run_id": document.run_id,
        "scenario_fingerprint": document.scenario_fingerprint,
        "schema_version": document.schema_version,
        "stop_reason": document.stop_reason,
        "ticks_committed": document.ticks_committed,
    }
    if document.schema_version == RESULT_SCHEMA_VERSION_V2:
        payload["cognition_invocations"] = document.cognition_invocations
        payload["finalized_tick_count"] = document.finalized_tick_count
        payload["goal_transition_count"] = document.goal_transition_count
        payload["imagination_evaluations"] = document.imagination_evaluations
        payload["imagined_future_count"] = document.imagined_future_count
        payload["objective_state_hash"] = document.objective_state_hash
    return _canonical_dumps(payload)


def runner_result_fingerprint(document: object) -> str:
    return _sha256_hex(encode_runner_result_document(document))


def _encode_resolution_evidence(
    evidence: object, *, include_request_id: bool
) -> dict[str, Any]:
    from simulation.runner_models import ActionResolutionEvidence

    if type(evidence) is not ActionResolutionEvidence:
        raise TypeError("evidence must be ActionResolutionEvidence")
    payload: dict[str, Any] = {
        "agent_id": evidence.agent_id.value,
        "base_revision": evidence.base_revision,
        "command_kind": evidence.command_kind,
        "ordinal": evidence.ordinal,
        "reason": evidence.reason.value,
        "resulting_revision": evidence.resulting_revision,
        "status": evidence.status.value,
        "tick": evidence.tick,
    }
    if include_request_id:
        payload["request_id"] = evidence.request_id
    return payload


def _encode_tick_receipt_for_hash(
    receipt: FinalizedTickReceipt, *, include_run_scoped_ids: bool
) -> dict[str, Any]:
    return {
        "base_revision": receipt.base_revision,
        "event_count": receipt.event_count,
        "objective_state_hash": receipt.objective_state_hash,
        "resolutions": [
            _encode_resolution_evidence(item, include_request_id=include_run_scoped_ids)
            for item in receipt.resolutions
        ],
        "resulting_revision": receipt.resulting_revision,
        "resulting_tick": receipt.resulting_tick,
        "tick": receipt.tick,
    }


def exact_trajectory_hash(
    *,
    run_id: str,
    tick_receipts: tuple[FinalizedTickReceipt, ...],
) -> str:
    """Hash trajectory identity including run-scoped identifiers."""
    document = {
        "mode": "exact",
        "run_id": run_id,
        "ticks": [
            _encode_tick_receipt_for_hash(item, include_run_scoped_ids=True)
            for item in tick_receipts
        ],
    }
    return _sha256_hex(_canonical_dumps(document))


def replica_normalized_trajectory_hash(
    *,
    tick_receipts: tuple[FinalizedTickReceipt, ...],
) -> str:
    """Hash trajectory identity with documented run-derived IDs removed.

    Strips ``request_id`` (run-derived) and omits ``run_id``. Tick ordinals,
    agent identities, command kinds, statuses, and revisions remain so distinct
    trajectories cannot collapse.
    """
    document = {
        "mode": "replica",
        "ticks": [
            _encode_tick_receipt_for_hash(item, include_run_scoped_ids=False)
            for item in tick_receipts
        ],
    }
    return _sha256_hex(_canonical_dumps(document))


def objective_projection_hash(projection: object) -> str:
    """Canonical hash of a detached objective projection."""
    from simulation.runner_models import DetachedObjectiveProjection

    if type(projection) is not DetachedObjectiveProjection:
        raise TypeError("projection must be DetachedObjectiveProjection")
    document = {
        "bodies": [
            {
                "entity_id": body.entity_id.value,
                "inventory": [item.value for item in body.inventory],
                "life_status": body.life_status.value,
                "location_id": body.location_id.value,
            }
            for body in projection.bodies
        ],
        "projection_version": projection.projection_version,
        "revision": projection.revision,
        "tick": projection.tick,
    }
    return _sha256_hex(_canonical_dumps(document))


def build_runner_result_document(
    *,
    result: object,
    config: SimulationRunnerConfig,
) -> SimulationRunnerResultDocument:
    """Build a versioned result document from a finalized runner result."""
    if type(result) is not SimulationRunnerResult:
        raise TypeError("result must be SimulationRunnerResult")
    tick_receipts = result.finalized_tick_receipts
    if tick_receipts:
        exact = exact_trajectory_hash(
            run_id=result.run_id.value, tick_receipts=tick_receipts
        )
        replica = replica_normalized_trajectory_hash(tick_receipts=tick_receipts)
    else:
        # Legacy/empty evidence path: preserve run-scoped vs replica distinction.
        exact = _sha256_hex(
            f"exact|{result.run_id.value}|{result.ticks_committed}".encode()
        )
        replica = _sha256_hex(
            (
                f"replica|{config.stochastic_identity.value}|{result.ticks_committed}"
            ).encode()
        )
    counters = result.cognition_counters
    if type(counters) is not CognitionCounters:
        counters = CognitionCounters()
    return SimulationRunnerResultDocument(
        schema_version=RESULT_SCHEMA_VERSION,
        run_id=result.run_id.value,
        stop_reason=result.stop_reason.value,
        ticks_committed=result.ticks_committed,
        config_fingerprint=runner_config_fingerprint(config),
        scenario_fingerprint=scenario_fingerprint(config),
        cognition_fingerprint=cognition_fingerprint(config),
        exact_trajectory_hash=exact,
        replica_normalized_trajectory_hash=replica,
        attempt_count=len(result.attempt_receipts),
        objective_state_hash=result.objective_state_hash,
        cognition_invocations=counters.cognition_invocations,
        imagination_evaluations=counters.imagination_evaluations,
        imagined_future_count=counters.imagined_future_count,
        goal_transition_count=len(result.goal_transition_receipts),
        finalized_tick_count=len(tick_receipts),
    )


def finalization_command_to_mapping(command: object) -> dict[str, Any]:
    """Encode a FinalizationCommand to a JSONB-safe mapping (log-free)."""
    from agents.cognition.models import IntentionCode, InternalAgentState
    from memory.models import Belief
    from simulation.agent_runtime import AgentRuntimeStatus
    from simulation.clock import Tick
    from simulation.lifecycle import ActionSubmission, TickToken
    from simulation.models import RunId
    from simulation.run_control import (
        FINALIZATION_COMMAND_CODEC_VERSION,
        FinalizationCommand,
    )
    from simulation.serialization import encode_domain
    from simulation.subjective_serialization import encode_subjective_mutation_batch

    if type(command) is not FinalizationCommand:
        raise TypeError("finalization_command_to_mapping requires FinalizationCommand")
    if command.codec_version != FINALIZATION_COMMAND_CODEC_VERSION:
        raise RunnerSerializationError("unsupported_codec_version", "$.codec_version")
    state = command.next_internal_state
    if type(state) is not InternalAgentState:
        raise RunnerSerializationError(
            "invalid_internal_state", "$.next_internal_state"
        )
    submission = command.submission
    if type(submission) is not ActionSubmission:
        raise RunnerSerializationError("invalid_submission", "$.submission")
    command_envelope = json.loads(encode_domain(submission.command).decode("utf-8"))
    beliefs = []
    for item in command.legacy_belief_writes:
        if type(item) is not Belief:
            raise RunnerSerializationError("invalid_belief", "$.legacy_belief_writes")
        beliefs.append(json.loads(encode_domain(item).decode("utf-8")))
    payload: dict[str, Any] = {
        "agent_id": command.agent_id.value,
        "codec_version": command.codec_version,
        "delivery_acknowledged": command.delivery_acknowledged,
        "delivery_content_hash": command.delivery_content_hash,
        "delivery_id": command.delivery_id,
        "effective_command_kind": command.effective_command_kind,
        "final_confidence": command.final_confidence,
        "has_futures_boundary": command.has_futures_boundary,
        "integrity_hash": command.integrity_hash,
        "invocation_id": command.invocation_id,
        "legacy_belief_writes": beliefs,
        "next_internal_state": {
            "invocation_count": state.invocation_count,
            "last_command_kind": state.last_command_kind,
            "last_intention": (
                None if state.last_intention is None else state.last_intention.value
            ),
            "owner_id": state.owner_id.value,
        },
        "next_status": command.next_status.value,
        "observation_key": list(command.observation_key),
        "prior_status": command.prior_status.value,
        "run_id": command.run_id.value,
        "subjective_batch": (
            None
            if command.subjective_batch is None
            else encode_subjective_mutation_batch(command.subjective_batch)
        ),
        "submission": {
            "agent_id": submission.agent_id.value,
            "command": command_envelope,
            "token": {
                "tick": submission.token.tick.value,
                "value": submission.token.value,
            },
        },
        "tick": command.tick,
    }
    _ = (AgentRuntimeStatus, IntentionCode, RunId, Tick, TickToken)
    return payload


def encode_finalization_command(command: object) -> bytes:
    """Canonical UTF-8 bytes for a FinalizationCommand."""
    return _canonical_dumps(finalization_command_to_mapping(command))


def decode_finalization_command(payload: object) -> object:
    """Decode mapping or bytes into a FinalizationCommand."""
    from agents.cognition.models import IntentionCode, InternalAgentState
    from agents.models import AgentId
    from memory.models import Belief
    from simulation.agent_runtime import AgentRuntimeStatus
    from simulation.clock import Tick
    from simulation.lifecycle import ActionSubmission, TickToken
    from simulation.models import RunId
    from simulation.run_control import (
        FINALIZATION_COMMAND_CODEC_VERSION,
        FinalizationCommand,
    )
    from simulation.serialization import decode_domain
    from simulation.subjective_serialization import (
        SubjectiveSerializationError,
        decode_subjective_mutation_batch,
    )
    from world.actions import require_agent_command

    if isinstance(payload, (bytes, bytearray)):
        try:
            text = bytes(payload).decode("utf-8")
            data = json.loads(text)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RunnerSerializationError("invalid_json", "$") from exc
    elif isinstance(payload, Mapping):
        data = dict(payload)
    else:
        raise TypeError("decode_finalization_command requires mapping or bytes")
    if not isinstance(data, dict):
        raise RunnerSerializationError("invalid_envelope", "$")
    required = {
        "codec_version",
        "run_id",
        "agent_id",
        "tick",
        "invocation_id",
        "observation_key",
        "prior_status",
        "next_status",
        "effective_command_kind",
        "integrity_hash",
        "next_internal_state",
        "submission",
        "subjective_batch",
        "has_futures_boundary",
        "final_confidence",
        "legacy_belief_writes",
        "delivery_id",
        "delivery_content_hash",
        "delivery_acknowledged",
    }
    if set(data) != required:
        raise RunnerSerializationError("invalid_fields", "$")
    if data["codec_version"] != FINALIZATION_COMMAND_CODEC_VERSION:
        raise RunnerSerializationError("unsupported_codec_version", "$.codec_version")
    state_raw = data["next_internal_state"]
    if not isinstance(state_raw, dict):
        raise RunnerSerializationError("invalid_object", "$.next_internal_state")
    submission_raw = data["submission"]
    if not isinstance(submission_raw, dict):
        raise RunnerSerializationError("invalid_object", "$.submission")
    token_raw = submission_raw.get("token")
    if not isinstance(token_raw, dict):
        raise RunnerSerializationError("invalid_object", "$.submission.token")
    obs_raw = data["observation_key"]
    if not isinstance(obs_raw, list) or len(obs_raw) != 2:
        raise RunnerSerializationError("invalid_observation_key", "$.observation_key")
    beliefs_raw = data["legacy_belief_writes"]
    if not isinstance(beliefs_raw, list):
        raise RunnerSerializationError("invalid_array", "$.legacy_belief_writes")
    try:
        last_intention_raw = state_raw.get("last_intention")
        last_intention = (
            None
            if last_intention_raw is None
            else IntentionCode(str(last_intention_raw))
        )
        command_obj = decode_domain(
            json.dumps(
                submission_raw["command"],
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        )
        beliefs: list[Belief] = []
        for index, item in enumerate(beliefs_raw):
            decoded = decode_domain(
                json.dumps(
                    item,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                ).encode("utf-8")
            )
            if type(decoded) is not Belief:
                raise RunnerSerializationError(
                    "invalid_belief", f"$.legacy_belief_writes[{index}]"
                )
            beliefs.append(decoded)
        batch_raw = data["subjective_batch"]
        batch = (
            None
            if batch_raw is None
            else decode_subjective_mutation_batch(batch_raw, path="$.subjective_batch")
        )
        return FinalizationCommand(
            codec_version=str(data["codec_version"]),
            run_id=RunId(str(data["run_id"])),
            agent_id=AgentId(str(data["agent_id"])),
            tick=int(data["tick"]),
            invocation_id=str(data["invocation_id"]),
            observation_key=(int(obs_raw[0]), int(obs_raw[1])),
            prior_status=AgentRuntimeStatus(str(data["prior_status"])),
            next_status=AgentRuntimeStatus(str(data["next_status"])),
            effective_command_kind=str(data["effective_command_kind"]),
            integrity_hash=str(data["integrity_hash"]),
            next_internal_state=InternalAgentState(
                owner_id=AgentId(str(state_raw["owner_id"])),
                invocation_count=int(state_raw["invocation_count"]),
                last_intention=last_intention,
                last_command_kind=state_raw.get("last_command_kind"),
            ),
            submission=ActionSubmission(
                token=TickToken(
                    value=str(token_raw["value"]),
                    tick=Tick(int(token_raw["tick"])),
                ),
                agent_id=AgentId(str(submission_raw["agent_id"])),
                command=require_agent_command(command_obj),
            ),
            subjective_batch=batch,
            has_futures_boundary=bool(data["has_futures_boundary"]),
            final_confidence=float(data["final_confidence"]),
            legacy_belief_writes=tuple(beliefs),
            delivery_id=data["delivery_id"],
            delivery_content_hash=data["delivery_content_hash"],
            delivery_acknowledged=bool(data["delivery_acknowledged"]),
        )
    except RunnerSerializationError:
        raise
    except SubjectiveSerializationError as exc:
        raise RunnerSerializationError(exc.code, exc.path) from None
    except (TypeError, ValueError, KeyError) as exc:
        raise RunnerSerializationError("invalid_model", "$") from exc
