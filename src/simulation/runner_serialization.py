"""Strict canonical JSON codecs and fingerprints for runner configuration.

Codecs are log-free. Errors expose only stable ``code`` and ``path`` metadata.
Credentials, base URLs, prompts, and full seed-bearing dumps never appear in
exception messages.
"""

from __future__ import annotations

import hashlib
import json
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
    SUPPORTED_RUNNER_SCHEMA_VERSIONS,
    AgentCognitionSpec,
    AgentRunnerSpec,
    CognitionCounters,
    CognitionFailurePolicy,
    CognitionTraceDetail,
    CognitionTraceSpec,
    CommunicationStrategyMode,
    ConsolidationMode,
    CounterfactualMode,
    DriveOverrideSpec,
    ExactReproducibilityMode,
    ExperimentAssignmentRef,
    FinalizedTickReceipt,
    ImaginationMode,
    MemoryMode,
    MortalityMode,
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
    SimulationRunnerConfig,
    SimulationRunnerResult,
    SimulationRunnerResultDocument,
    SkillLearningMode,
    TeachingInteractionMode,
    V2CapabilityFlags,
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
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import physical_rules_fingerprint

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
_SKILL_SCHEMA_VERSIONS: Final[frozenset[str]] = frozenset(
    {
        RUNNER_SCHEMA_VERSION_V11,
        RUNNER_SCHEMA_VERSION_V12,
        RUNNER_SCHEMA_VERSION_V13,
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
    }
)
_COGNITION_SCHEMA_STRATEGY: Final[frozenset[str]] = frozenset(
    {
        RUNNER_SCHEMA_VERSION_V9,
        RUNNER_SCHEMA_VERSION_V10,
        RUNNER_SCHEMA_VERSION_V11,
        RUNNER_SCHEMA_VERSION_V12,
        RUNNER_SCHEMA_VERSION_V13,
    }
)
_COGNITION_SCHEMA_REPUTATION: Final[frozenset[str]] = frozenset(
    {
        RUNNER_SCHEMA_VERSION_V10,
        RUNNER_SCHEMA_VERSION_V11,
        RUNNER_SCHEMA_VERSION_V12,
        RUNNER_SCHEMA_VERSION_V13,
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
        _require_keys(
            data, {"initial_integrity", "kind", "structure_kind"}, path=path
        )
        try:
            return ShelterProduct(
                structure_kind=StructureKind(
                    _str_field(data, "structure_kind", path=path)
                ),
                initial_integrity=_required_float(
                    data, "initial_integrity", path=path
                ),
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
                initial_integrity=_required_float(
                    data, "initial_integrity", path=path
                ),
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
        payload["communication_strategy_mode"] = (
            value.communication_strategy_mode.value
        )
    if schema_version in _COGNITION_SCHEMA_REPUTATION:
        payload["reputation_mode"] = value.reputation_mode.value
    if schema_version in _SKILL_SCHEMA_VERSIONS:
        payload["skill_learning_mode"] = value.skill_learning_mode.value
        for name in _SKILL_RATE_KEYS:
            payload[name] = getattr(value, name)
    if schema_version in {RUNNER_SCHEMA_VERSION_V12, RUNNER_SCHEMA_VERSION_V13}:
        payload["teaching_interaction_mode"] = value.teaching_interaction_mode.value
        for name in _TEACHING_WEIGHT_KEYS:
            payload[name] = getattr(value, name)
    if schema_version == RUNNER_SCHEMA_VERSION_V13:
        payload["production_knowledge_mode"] = value.production_knowledge_mode.value
        payload["production_catalog"] = _encode_production_catalog(
            value.production_catalog
        )
    return payload


def _decode_cognition(
    data: dict[str, Any], *, path: str, schema_version: str
) -> AgentCognitionSpec:
    if schema_version == RUNNER_SCHEMA_VERSION_V13:
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
    if schema_version in {RUNNER_SCHEMA_VERSION_V12, RUNNER_SCHEMA_VERSION_V13}:
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
    if schema_version == RUNNER_SCHEMA_VERSION_V13:
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
            recording_policy=RecordingPolicy(
                _str_field(data, "recording_policy", path=path)
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
_CAPABILITY_FLAG_KEYS: Final[set[str]] = {
    "advanced_social_inference",
    "multi_hop_testimony_tracking",
    "predictive_world_model",
    "extended_self_model",
    "short_term_emotional_state",
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
    }:
        document["cognition_trace"] = _encode_cognition_trace(config.cognition_trace)
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
    }:
        capability_flags = _decode_capability_flags(
            data["capability_flags"], path="$.capability_flags"
        )
    else:
        # Legacy v1/v2 decode upgrades to default-off flags.
        capability_flags = V2CapabilityFlags()
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
            cognition_trace=cognition_trace,
            schema_version=_str_field(data, "schema_version", path="$"),
            derivation_version=_str_field(data, "derivation_version", path="$"),
            mortality_policy_version=_str_field(
                data, "mortality_policy_version", path="$"
            ),
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
