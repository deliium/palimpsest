"""Strict versioned domain serialization boundary.

Codecs emit no logs. Errors expose only stable ``code`` and ``path`` metadata.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from typing import Any, Final

from agents.models import (
    AGENT_MODEL_VERSION,
    GOAL_MODEL_VERSION,
    Agent,
    AgentId,
    DriveActivation,
    DriveDisposition,
    DriveKind,
    DriveProfile,
    DriveState,
    Goal,
    GoalId,
    GoalOutcome,
    GoalOutcomeKind,
    GoalProgress,
    GoalStatus,
    default_drive_profile,
    default_goal_outcome,
    default_goal_progress,
)
from memory.codec import (
    RECONSTRUCTED_MEMORY_TYPE,
    RECONSTRUCTION_RECORD_TYPE,
    encode_reconstructed_memory,
    encode_reconstruction_record,
)
from memory.models import (
    Belief,
    BeliefId,
    ConceptMention,
    EntityMention,
    MemoryEmbedding,
    MemoryId,
    MemoryLineage,
    MemoryProvenance,
    MemoryRelation,
    MemoryRunId,
    MemorySituationContext,
    MemorySourceKind,
    MemoryTrace,
    MentionId,
    ReconstructedMemory,
    ReconstructionId,
    ReconstructionRecord,
    RelationEndpoint,
    RelationEndpointKind,
)
from simulation.models import (
    LLM_REPLAY_REQUIREMENT,
    ExportMetadata,
    RunId,
    SimulationExport,
)
from social.models import (
    CommunicationEnvelope,
    EnvelopeId,
    Relationship,
    RelationshipId,
)
from world.actions import (
    ActionProposal,
    ActionRequest,
    Ask,
    Attack,
    Drink,
    Drop,
    Eat,
    Flee,
    Give,
    Help,
    Move,
    Search,
    Sleep,
    Take,
    Talk,
    Tell,
    Wait,
    require_agent_command,
)
from world.effects import (
    ActionCause,
    DeathCause,
    SystemCause,
    SystemEffectFamily,
)
from world.events import (
    EVENT_SCHEMA_AUDIT_V1,
    EVENT_SCHEMA_REPLAY_V2,
    EVENT_SCHEMA_REPLAY_V3,
    EVENT_SCHEMA_REPLAY_V4,
    Asked,
    Attacked,
    Died,
    Dropped,
    Drunk,
    Eaten,
    ExposureApplied,
    Fled,
    Given,
    Helped,
    Moved,
    NeedsApplied,
    OccurrenceContext,
    ResourceRegenerated,
    Searched,
    Slept,
    Taken,
    Talked,
    Told,
    Waited,
    WeatherChanged,
    WorldEvent,
    require_event_details,
    target_id_for_details,
)
from world.identifiers import (
    EntityId,
    EventId,
    ProposalId,
    RequestId,
    WorldId,
    WorldRevision,
)
from world.models import (
    AgentBody,
    Item,
    LifeStatus,
    Location,
    PhysicalRules,
    Resource,
    Weather,
    canonical_physical_rules_bytes,
)
from world.observations import (
    CoarseHealth,
    Observation,
    ObservationAudienceRole,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedCommunication,
    ObservedItem,
    ObservedItemPlacement,
    ObservedLocation,
    ObservedOccurrence,
    ObservedResource,
    ObservedSelf,
    VisibleBody,
    VisibleExit,
)
from world.values import (
    BodyCapacity,
    CarryCapacity,
    DayPhase,
    Fatigue,
    Health,
    Hunger,
    ItemCapacity,
    ItemKind,
    ItemLoad,
    ResourceKind,
    TemperatureCelsius,
    Thirst,
    UnitInterval,
    WeatherCondition,
)

SCHEMA_VERSION: Final[int] = 1
EPISODIC_MEMORY_TRACE_VERSION: Final[int] = 1
EPISODIC_MEMORY_TRACE_TYPE: Final[str] = "episodic_memory_trace"
_INT64_MIN = -(2**63)
_INT64_MAX = 2**63 - 1

SerializableDomainValue = (
    Location
    | Item
    | Resource
    | Weather
    | AgentBody
    | PhysicalRules
    | Agent
    | Goal
    | MemoryTrace
    | ReconstructedMemory
    | ReconstructionRecord
    | Belief
    | Relationship
    | CommunicationEnvelope
    | Move
    | Search
    | Take
    | Drop
    | Give
    | Eat
    | Drink
    | Sleep
    | Talk
    | Ask
    | Tell
    | Help
    | Attack
    | Flee
    | Wait
    | ActionProposal
    | Observation
    | WorldEvent
    | SimulationExport
)


class DomainSerializationError(ValueError):
    """Fail-closed codec error with stable metadata only."""

    def __init__(self, code: str, path: str) -> None:
        self.code = code
        self.path = path
        super().__init__(f"{code} at {path}")


def encode_domain(value: object) -> bytes:
    """Encode a supported immutable domain value to canonical UTF-8 bytes."""
    tag, data = _encode_top(value, path="$")
    envelope = {
        "data": data,
        "schema_version": SCHEMA_VERSION,
        "type": tag,
    }
    text = json.dumps(
        envelope,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return text.encode("utf-8")


def decode_domain(data: bytes) -> SerializableDomainValue:
    """Decode canonical domain bytes into an exact typed value."""
    if not isinstance(data, (bytes, bytearray)):
        raise DomainSerializationError("invalid_bytes", "$")
    if isinstance(data, bytearray):
        data = bytes(data)
    if data.startswith(b"\xef\xbb\xbf"):
        raise DomainSerializationError("bom_forbidden", "$")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DomainSerializationError("invalid_utf8", "$") from exc
    decoder = json.JSONDecoder(object_pairs_hook=_reject_duplicate_keys)
    try:
        payload, end = decoder.raw_decode(text)
    except json.JSONDecodeError as exc:
        raise DomainSerializationError("invalid_json", "$") from exc
    if end != len(text):
        raise DomainSerializationError("trailing_data", "$")
    if not isinstance(payload, dict):
        raise DomainSerializationError("invalid_envelope", "$")
    if set(payload) != {"schema_version", "type", "data"}:
        raise DomainSerializationError("invalid_envelope", "$")
    if payload["schema_version"] != SCHEMA_VERSION:
        raise DomainSerializationError("unsupported_schema_version", "$.schema_version")
    type_tag = payload["type"]
    if not isinstance(type_tag, str):
        raise DomainSerializationError("invalid_type", "$.type")
    data_obj = payload["data"]
    if not isinstance(data_obj, dict):
        raise DomainSerializationError("invalid_data", "$.data")
    return _decode_top(type_tag, data_obj, path="$.data")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DomainSerializationError("duplicate_key", "$")
        result[key] = value
    return result


def _encode_top(value: object, *, path: str) -> tuple[str, dict[str, Any]]:
    if type(value) is ActionRequest:
        raise DomainSerializationError("unsupported_type", path)
    # Lifecycle/runtime authority values are intentionally wire-ineligible.
    value_module = getattr(type(value), "__module__", "")
    value_name = type(value).__name__
    if value_module.startswith("simulation.lifecycle") or value_name in {
        "WorldBootstrap",
        "WorldEngine",
        "TickToken",
        "ActionSubmission",
        "ActionResolution",
        "TickResult",
        "ObservationBatch",
    }:
        raise DomainSerializationError("unsupported_type", path)
    # Persistence DTOs use simulation.journal codecs, not schema-v1 export.
    if value_module == "simulation.persistence" or value_name in {
        "WorldSnapshot",
        "RunManifest",
        "TickCommit",
        "TickAppendRequest",
        "RunCreateRequest",
        "CommitHash",
        "PayloadHash",
        "SnapshotId",
        "ExperimentId",
        "ExperimentMetadata",
        "ExperimentRunAssignment",
        "ReplayRequest",
        "ReplayResult",
    }:
        raise DomainSerializationError("unsupported_type", path)
    if type(value) is Location:
        return "location", _encode_location(value)
    if type(value) is Item:
        return "item", _encode_item(value)
    if type(value) is Resource:
        return "resource", _encode_resource(value)
    if type(value) is Weather:
        return "weather", _encode_weather(value)
    if type(value) is AgentBody:
        return "agent_body", _encode_agent_body(value)
    if type(value) is PhysicalRules:
        return "physical_rules", _encode_physical_rules(value)
    if type(value) is Agent:
        return "agent", _encode_agent(value)
    if type(value) is Goal:
        return "goal", _encode_goal(value)
    if type(value) is MemoryTrace:
        return EPISODIC_MEMORY_TRACE_TYPE, _encode_memory_trace(value)
    if type(value) is ReconstructedMemory:
        return RECONSTRUCTED_MEMORY_TYPE, encode_reconstructed_memory(value)
    if type(value) is ReconstructionRecord:
        return RECONSTRUCTION_RECORD_TYPE, encode_reconstruction_record(value)
    if type(value) is Belief:
        return "belief", _encode_belief(value)
    if type(value) is Relationship:
        return "relationship", _encode_relationship(value)
    if type(value) is CommunicationEnvelope:
        return "communication_envelope", _encode_envelope(value)
    if type(value) is ActionProposal:
        return "action_proposal", _encode_proposal(value)
    if type(value) is Observation:
        return "observation", _encode_observation(value)
    if type(value) is WorldEvent:
        return "world_event", _encode_world_event(value)
    if type(value) is SimulationExport:
        return "simulation_export", _encode_export(value)
    try:
        command = require_agent_command(value)
    except TypeError as exc:
        raise DomainSerializationError("unsupported_type", path) from exc
    return command.kind, _encode_command(command)


def _decode_top(
    tag: str, data: dict[str, Any], *, path: str
) -> SerializableDomainValue:
    if tag == "location":
        return _decode_location(data, path=path)
    if tag == "item":
        return _decode_item(data, path=path)
    if tag == "resource":
        return _decode_resource(data, path=path)
    if tag == "weather":
        return _decode_weather(data, path=path)
    if tag == "agent_body":
        return _decode_agent_body(data, path=path)
    if tag == "physical_rules":
        return _decode_physical_rules(data, path=path)
    if tag == "agent":
        return _decode_agent(data, path=path)
    if tag == "goal":
        return _decode_goal(data, path=path)
    if tag == "memory_trace":
        raise DomainSerializationError("unsupported_legacy_memory_trace", path)
    if tag == EPISODIC_MEMORY_TRACE_TYPE:
        return _decode_memory_trace(data, path=path)
    if tag == RECONSTRUCTED_MEMORY_TYPE:
        return _decode_reconstructed_memory(data, path=path)
    if tag == RECONSTRUCTION_RECORD_TYPE:
        return _decode_reconstruction_record(data, path=path)
    if tag == "belief":
        return _decode_belief(data, path=path)
    if tag == "relationship":
        return _decode_relationship(data, path=path)
    if tag == "communication_envelope":
        return _decode_envelope(data, path=path)
    if tag == "action_proposal":
        return _decode_proposal(data, path=path)
    if tag == "observation":
        return _decode_observation(data, path=path)
    if tag == "world_event":
        return _decode_world_event(data, path=path)
    if tag == "simulation_export":
        return _decode_export(data, path=path)
    if tag in _COMMAND_TAGS:
        return require_agent_command(_decode_command(tag, data, path=path))
    raise DomainSerializationError("unknown_type", "$.type")


_COMMAND_TAGS: Final[frozenset[str]] = frozenset(
    {
        "move",
        "search",
        "take",
        "drop",
        "give",
        "eat",
        "drink",
        "sleep",
        "talk",
        "ask",
        "tell",
        "help",
        "attack",
        "flee",
        "wait",
    }
)


def _require_keys(
    data: Mapping[str, Any],
    keys: set[str],
    *,
    path: str,
    optional: set[str] | None = None,
) -> None:
    allowed = keys if optional is None else keys | optional
    present = set(data)
    if not keys.issubset(present) or not present.issubset(allowed):
        raise DomainSerializationError("invalid_fields", path)


def _str_field(data: Mapping[str, Any], key: str, *, path: str) -> str:
    value = data[key]
    if not isinstance(value, str):
        raise DomainSerializationError("invalid_string", f"{path}.{key}")
    return value


def _int_field(data: Mapping[str, Any], key: str, *, path: str) -> int:
    value = data[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise DomainSerializationError("invalid_int", f"{path}.{key}")
    if value < _INT64_MIN or value > _INT64_MAX:
        raise DomainSerializationError("int_out_of_range", f"{path}.{key}")
    return value


def _float_field(data: Mapping[str, Any], key: str, *, path: str) -> float:
    value = data[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DomainSerializationError("invalid_float", f"{path}.{key}")
    number = float(value)
    if not math.isfinite(number):
        raise DomainSerializationError("non_finite_float", f"{path}.{key}")
    return 0.0 if number == 0.0 else number


def _optional_str(data: Mapping[str, Any], key: str, *, path: str) -> str | None:
    value = data[key]
    if value is None:
        return None
    if not isinstance(value, str):
        raise DomainSerializationError("invalid_string", f"{path}.{key}")
    return value


def _encode_content(value: object, *, path: str) -> object:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        if value < _INT64_MIN or value > _INT64_MAX:
            raise DomainSerializationError("int_out_of_range", path)
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise DomainSerializationError("non_finite_float", path)
        return 0.0 if value == 0.0 else value
    if isinstance(value, str):
        return value
    if isinstance(value, (bytes, bytearray, memoryview)):
        raise DomainSerializationError("bytes_forbidden", path)
    if isinstance(value, Mapping):
        encoded: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise DomainSerializationError("non_string_key", path)
            encoded[key] = _encode_content(item, path=f"{path}.{key}")
        return encoded
    if isinstance(value, Sequence):
        return [
            _encode_content(item, path=f"{path}[{index}]")
            for index, item in enumerate(value)
        ]
    raise DomainSerializationError("unsupported_content", path)


def _decode_content(value: object, *, path: str) -> object:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        if value < _INT64_MIN or value > _INT64_MAX:
            raise DomainSerializationError("int_out_of_range", path)
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise DomainSerializationError("non_finite_float", path)
        return 0.0 if value == 0.0 else value
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return tuple(
            _decode_content(item, path=f"{path}[{index}]")
            for index, item in enumerate(value)
        )
    if isinstance(value, dict):
        return {
            key: _decode_content(item, path=f"{path}.{key}")
            for key, item in value.items()
            if _ensure_str_key(key, path=path) or True
        }
    raise DomainSerializationError("unsupported_content", path)


def _ensure_str_key(key: object, *, path: str) -> bool:
    if not isinstance(key, str):
        raise DomainSerializationError("non_string_key", path)
    return True


def _encode_location(value: Location) -> dict[str, Any]:
    return {
        "adjacent": [item.value for item in value.adjacent],
        "base_temperature": value.base_temperature.value,
        "body_capacity": value.body_capacity.value,
        "entity_id": value.entity_id.value,
        "item_capacity": value.item_capacity.value,
        "name": value.name,
        "shelter_factor": value.shelter_factor.value,
        "visibility_factor": value.visibility_factor.value,
    }


def _decode_location(data: dict[str, Any], *, path: str) -> Location:
    _require_keys(
        data,
        {
            "adjacent",
            "base_temperature",
            "body_capacity",
            "entity_id",
            "item_capacity",
            "name",
            "shelter_factor",
            "visibility_factor",
        },
        path=path,
    )
    adjacent_raw = data["adjacent"]
    if not isinstance(adjacent_raw, list):
        raise DomainSerializationError("invalid_array", f"{path}.adjacent")
    try:
        adjacent = tuple(
            EntityId(_require_list_str(item, path=f"{path}.adjacent[{index}]"))
            for index, item in enumerate(adjacent_raw)
        )
        return Location(
            entity_id=EntityId(_str_field(data, "entity_id", path=path)),
            name=_str_field(data, "name", path=path),
            adjacent=adjacent,
            body_capacity=BodyCapacity(_int_field(data, "body_capacity", path=path)),
            item_capacity=ItemCapacity(_int_field(data, "item_capacity", path=path)),
            base_temperature=TemperatureCelsius(
                _float_field(data, "base_temperature", path=path)
            ),
            shelter_factor=UnitInterval(
                _float_field(data, "shelter_factor", path=path)
            ),
            visibility_factor=UnitInterval(
                _float_field(data, "visibility_factor", path=path)
            ),
        )
    except DomainSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise DomainSerializationError("invalid_model", path) from exc


def _encode_item(value: Item) -> dict[str, Any]:
    return {
        "entity_id": value.entity_id.value,
        "holder_id": None if value.holder_id is None else value.holder_id.value,
        "kind": value.kind.value,
        "load": value.load.value,
        "location_id": None if value.location_id is None else value.location_id.value,
        "name": value.name,
    }


def _decode_item(data: dict[str, Any], *, path: str) -> Item:
    _require_keys(
        data,
        {"entity_id", "name", "kind", "load", "location_id", "holder_id"},
        path=path,
    )
    location = _optional_str(data, "location_id", path=path)
    holder = _optional_str(data, "holder_id", path=path)
    try:
        return Item(
            entity_id=EntityId(_str_field(data, "entity_id", path=path)),
            name=_str_field(data, "name", path=path),
            kind=ItemKind(_str_field(data, "kind", path=path)),
            load=ItemLoad(_int_field(data, "load", path=path)),
            location_id=None if location is None else EntityId(location),
            holder_id=None if holder is None else EntityId(holder),
        )
    except DomainSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise DomainSerializationError("invalid_model", path) from exc


def _encode_resource(value: Resource) -> dict[str, Any]:
    return {
        "entity_id": value.entity_id.value,
        "kind": value.kind.value,
        "location_id": value.location_id.value,
        "maximum_quantity": value.maximum_quantity,
        "name": value.name,
        "quantity": value.quantity,
        "regeneration_per_tick": value.regeneration_per_tick,
        "unit": value.unit,
    }


def _decode_resource(data: dict[str, Any], *, path: str) -> Resource:
    _require_keys(
        data,
        {
            "entity_id",
            "name",
            "kind",
            "location_id",
            "quantity",
            "maximum_quantity",
            "regeneration_per_tick",
            "unit",
        },
        path=path,
    )
    try:
        return Resource(
            entity_id=EntityId(_str_field(data, "entity_id", path=path)),
            name=_str_field(data, "name", path=path),
            kind=ResourceKind(_str_field(data, "kind", path=path)),
            location_id=EntityId(_str_field(data, "location_id", path=path)),
            quantity=_float_field(data, "quantity", path=path),
            maximum_quantity=_float_field(data, "maximum_quantity", path=path),
            regeneration_per_tick=_float_field(
                data, "regeneration_per_tick", path=path
            ),
            unit=_str_field(data, "unit", path=path),
        )
    except DomainSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise DomainSerializationError("invalid_model", path) from exc


def _encode_weather(value: Weather) -> dict[str, Any]:
    return {
        "condition": value.condition.value,
        "location_id": value.location_id.value,
    }


def _decode_weather(data: dict[str, Any], *, path: str) -> Weather:
    _require_keys(data, {"location_id", "condition"}, path=path)
    try:
        return Weather(
            location_id=EntityId(_str_field(data, "location_id", path=path)),
            condition=WeatherCondition(_str_field(data, "condition", path=path)),
        )
    except DomainSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise DomainSerializationError("invalid_model", path) from exc


def _encode_physical_rules(value: PhysicalRules) -> dict[str, Any]:
    try:
        payload = json.loads(canonical_physical_rules_bytes(value).decode("utf-8"))
    except (TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DomainSerializationError("invalid_model", "$") from exc
    if not isinstance(payload, dict):
        raise DomainSerializationError("invalid_model", "$")
    return payload


def _decode_physical_rules(data: dict[str, Any], *, path: str) -> PhysicalRules:
    required = {
        "attack_damage_max_exclusive",
        "attack_damage_min",
        "attack_hit_probability",
        "day_end_hour",
        "day_start_hour",
        "day_visibility_factor",
        "drink_thirst_relief",
        "eat_hunger_relief",
        "exposure_damage",
        "exposure_high_celsius",
        "exposure_low_celsius",
        "fatigue_damage",
        "flee_fatigue",
        "flee_success_probability",
        "help_fatigue",
        "help_health_gain",
        "hours_per_day",
        "hunger_damage",
        "metabolism_fatigue",
        "metabolism_hunger",
        "metabolism_thirst",
        "move_fatigue",
        "night_visibility_factor",
        "phase_temperature_offset",
        "resource_extraction_amount",
        "search_base_probability",
        "search_visibility_weight",
        "sleep_fatigue_recovery",
        "temperature_lerp_factor",
        "thirst_damage",
        "version",
        "weather_period_ticks",
        "weather_temperature_offset",
        "weather_transitions",
        "weather_visibility",
    }
    _require_keys(data, required, path=path)
    try:
        phase_raw = data["phase_temperature_offset"]
        weather_vis_raw = data["weather_visibility"]
        weather_temp_raw = data["weather_temperature_offset"]
        transitions_raw = data["weather_transitions"]
        if not isinstance(phase_raw, dict):
            raise DomainSerializationError(
                "invalid_object", f"{path}.phase_temperature_offset"
            )
        if not isinstance(weather_vis_raw, dict):
            raise DomainSerializationError(
                "invalid_object", f"{path}.weather_visibility"
            )
        if not isinstance(weather_temp_raw, dict):
            raise DomainSerializationError(
                "invalid_object", f"{path}.weather_temperature_offset"
            )
        if not isinstance(transitions_raw, dict):
            raise DomainSerializationError(
                "invalid_object", f"{path}.weather_transitions"
            )
        phase_offset = {
            DayPhase(key): _float_field(
                phase_raw, key, path=f"{path}.phase_temperature_offset"
            )
            for key in phase_raw
        }
        weather_visibility = {
            WeatherCondition(key): _float_field(
                weather_vis_raw, key, path=f"{path}.weather_visibility"
            )
            for key in weather_vis_raw
        }
        weather_temperature_offset = {
            WeatherCondition(key): _float_field(
                weather_temp_raw, key, path=f"{path}.weather_temperature_offset"
            )
            for key in weather_temp_raw
        }
        weather_transitions: dict[WeatherCondition, dict[WeatherCondition, float]] = {}
        for source_key, row_raw in transitions_raw.items():
            if not isinstance(row_raw, dict):
                raise DomainSerializationError(
                    "invalid_object",
                    f"{path}.weather_transitions.{source_key}",
                )
            weather_transitions[WeatherCondition(str(source_key))] = {
                WeatherCondition(str(target_key)): _float_field(
                    row_raw,
                    str(target_key),
                    path=f"{path}.weather_transitions.{source_key}",
                )
                for target_key in row_raw
            }
        return PhysicalRules(
            version=_str_field(data, "version", path=path),
            hours_per_day=_int_field(data, "hours_per_day", path=path),
            day_start_hour=_int_field(data, "day_start_hour", path=path),
            day_end_hour=_int_field(data, "day_end_hour", path=path),
            metabolism_hunger=_float_field(data, "metabolism_hunger", path=path),
            metabolism_thirst=_float_field(data, "metabolism_thirst", path=path),
            metabolism_fatigue=_float_field(data, "metabolism_fatigue", path=path),
            hunger_damage=_float_field(data, "hunger_damage", path=path),
            thirst_damage=_float_field(data, "thirst_damage", path=path),
            fatigue_damage=_float_field(data, "fatigue_damage", path=path),
            exposure_damage=_float_field(data, "exposure_damage", path=path),
            exposure_low_celsius=_float_field(data, "exposure_low_celsius", path=path),
            exposure_high_celsius=_float_field(
                data, "exposure_high_celsius", path=path
            ),
            temperature_lerp_factor=_float_field(
                data, "temperature_lerp_factor", path=path
            ),
            move_fatigue=_float_field(data, "move_fatigue", path=path),
            flee_fatigue=_float_field(data, "flee_fatigue", path=path),
            help_fatigue=_float_field(data, "help_fatigue", path=path),
            sleep_fatigue_recovery=_float_field(
                data, "sleep_fatigue_recovery", path=path
            ),
            eat_hunger_relief=_float_field(data, "eat_hunger_relief", path=path),
            drink_thirst_relief=_float_field(data, "drink_thirst_relief", path=path),
            help_health_gain=_float_field(data, "help_health_gain", path=path),
            attack_hit_probability=_float_field(
                data, "attack_hit_probability", path=path
            ),
            attack_damage_min=_int_field(data, "attack_damage_min", path=path),
            attack_damage_max_exclusive=_int_field(
                data, "attack_damage_max_exclusive", path=path
            ),
            flee_success_probability=_float_field(
                data, "flee_success_probability", path=path
            ),
            search_base_probability=_float_field(
                data, "search_base_probability", path=path
            ),
            search_visibility_weight=_float_field(
                data, "search_visibility_weight", path=path
            ),
            resource_extraction_amount=_float_field(
                data, "resource_extraction_amount", path=path
            ),
            weather_period_ticks=_int_field(data, "weather_period_ticks", path=path),
            day_visibility_factor=_float_field(
                data, "day_visibility_factor", path=path
            ),
            night_visibility_factor=_float_field(
                data, "night_visibility_factor", path=path
            ),
            weather_visibility=weather_visibility,
            weather_temperature_offset=weather_temperature_offset,
            phase_temperature_offset=phase_offset,
            weather_transitions=weather_transitions,
        )
    except DomainSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise DomainSerializationError("invalid_model", path) from exc


def _encode_agent_body(value: AgentBody) -> dict[str, Any]:
    return {
        "carry_capacity": value.carry_capacity.value,
        "entity_id": value.entity_id.value,
        "fatigue": value.fatigue.value,
        "health": value.health.value,
        "hunger": value.hunger.value,
        "inventory": [item.value for item in value.inventory],
        "life_status": value.life_status.value,
        "location_id": value.location_id.value,
        "temperature": value.temperature.value,
        "thirst": value.thirst.value,
    }


def _decode_agent_body(data: dict[str, Any], *, path: str) -> AgentBody:
    _require_keys(
        data,
        {
            "entity_id",
            "location_id",
            "health",
            "hunger",
            "thirst",
            "fatigue",
            "temperature",
            "inventory",
            "life_status",
            "carry_capacity",
        },
        path=path,
    )
    inventory_raw = data["inventory"]
    if not isinstance(inventory_raw, list):
        raise DomainSerializationError("invalid_array", f"{path}.inventory")
    try:
        inventory = tuple(
            EntityId(_require_list_str(item, path=f"{path}.inventory[{index}]"))
            for index, item in enumerate(inventory_raw)
        )
        return AgentBody(
            entity_id=EntityId(_str_field(data, "entity_id", path=path)),
            location_id=EntityId(_str_field(data, "location_id", path=path)),
            health=Health(_float_field(data, "health", path=path)),
            hunger=Hunger(_float_field(data, "hunger", path=path)),
            thirst=Thirst(_float_field(data, "thirst", path=path)),
            fatigue=Fatigue(_float_field(data, "fatigue", path=path)),
            temperature=TemperatureCelsius(
                _float_field(data, "temperature", path=path)
            ),
            inventory=inventory,
            life_status=LifeStatus(_str_field(data, "life_status", path=path)),
            carry_capacity=CarryCapacity(_int_field(data, "carry_capacity", path=path)),
        )
    except DomainSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise DomainSerializationError("invalid_model", path) from exc


def _require_list_str(value: object, *, path: str) -> str:
    if not isinstance(value, str):
        raise DomainSerializationError("invalid_string", path)
    return value


_LEGACY_GOAL_KEYS: Final[set[str]] = {
    "goal_id",
    "owner_id",
    "description",
    "priority",
    "status",
}
_GOAL_V2_KEYS: Final[set[str]] = _LEGACY_GOAL_KEYS | {
    "model_version",
    "outcome",
    "progress",
}
_LEGACY_AGENT_KEYS: Final[set[str]] = {"agent_id", "name", "goals"}
_AGENT_V2_KEYS: Final[set[str]] = _LEGACY_AGENT_KEYS | {"model_version", "drives"}


def _encode_goal_outcome(value: GoalOutcome) -> dict[str, Any]:
    payload: dict[str, Any] = {"kind": value.kind.value}
    if value.drive_kind is not None:
        payload["drive_kind"] = value.drive_kind.value
    if value.place_id is not None:
        payload["place_id"] = value.place_id
    if value.entity_id is not None:
        payload["entity_id"] = value.entity_id
    if value.counterpart_id is not None:
        payload["counterpart_id"] = value.counterpart_id.value
    if value.outcome_code is not None:
        payload["outcome_code"] = value.outcome_code
    return payload


def _decode_goal_outcome(data: dict[str, Any], *, path: str) -> GoalOutcome:
    if "kind" not in data:
        raise DomainSerializationError("invalid_fields", path)
    kind_raw = data["kind"]
    if not isinstance(kind_raw, str):
        raise DomainSerializationError("invalid_string", f"{path}.kind")
    try:
        kind = GoalOutcomeKind(kind_raw)
    except ValueError as exc:
        raise DomainSerializationError("invalid_enum", f"{path}.kind") from exc
    allowed = {"kind"}
    drive_kind: DriveKind | None = None
    place_id: str | None = None
    entity_id: str | None = None
    counterpart_id: AgentId | None = None
    outcome_code: str | None = None
    if "drive_kind" in data:
        allowed.add("drive_kind")
        drive_raw = data["drive_kind"]
        if not isinstance(drive_raw, str):
            raise DomainSerializationError("invalid_string", f"{path}.drive_kind")
        try:
            drive_kind = DriveKind(drive_raw)
        except ValueError as exc:
            raise DomainSerializationError(
                "invalid_enum", f"{path}.drive_kind"
            ) from exc
    if "place_id" in data:
        allowed.add("place_id")
        place_id = _str_field(data, "place_id", path=path)
    if "entity_id" in data:
        allowed.add("entity_id")
        entity_id = _str_field(data, "entity_id", path=path)
    if "counterpart_id" in data:
        allowed.add("counterpart_id")
        counterpart_id = AgentId(_str_field(data, "counterpart_id", path=path))
    if "outcome_code" in data:
        allowed.add("outcome_code")
        outcome_code = _str_field(data, "outcome_code", path=path)
    if set(data) != allowed:
        raise DomainSerializationError("invalid_fields", path)
    try:
        return GoalOutcome(
            kind=kind,
            drive_kind=drive_kind,
            place_id=place_id,
            entity_id=entity_id,
            counterpart_id=counterpart_id,
            outcome_code=outcome_code,
        )
    except (TypeError, ValueError) as exc:
        raise DomainSerializationError("invalid_model", path) from exc


def _encode_goal_progress(value: GoalProgress) -> dict[str, Any]:
    return {
        "confidence": value.confidence,
        "estimate": value.estimate,
        "horizon_ticks": value.horizon_ticks,
        "stall_count": value.stall_count,
    }


def _decode_goal_progress(data: dict[str, Any], *, path: str) -> GoalProgress:
    _require_keys(
        data, {"estimate", "confidence", "stall_count", "horizon_ticks"}, path=path
    )
    try:
        return GoalProgress(
            estimate=_float_field(data, "estimate", path=path),
            confidence=_float_field(data, "confidence", path=path),
            stall_count=_int_field(data, "stall_count", path=path),
            horizon_ticks=_int_field(data, "horizon_ticks", path=path),
        )
    except DomainSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise DomainSerializationError("invalid_model", path) from exc


def _encode_drive_disposition(value: DriveDisposition) -> dict[str, Any]:
    return {
        "baseline": value.baseline,
        "kind": value.kind.value,
        "sensitivity": value.sensitivity,
    }


def _decode_drive_disposition(data: dict[str, Any], *, path: str) -> DriveDisposition:
    _require_keys(data, {"kind", "baseline", "sensitivity"}, path=path)
    try:
        return DriveDisposition(
            kind=DriveKind(_str_field(data, "kind", path=path)),
            baseline=_float_field(data, "baseline", path=path),
            sensitivity=_float_field(data, "sensitivity", path=path),
        )
    except DomainSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise DomainSerializationError("invalid_model", path) from exc


def _encode_drive_profile(value: DriveProfile) -> dict[str, Any]:
    return {
        "dispositions": [
            _encode_drive_disposition(item) for item in value.dispositions
        ],
        "owner_id": value.owner_id.value,
    }


def _decode_drive_profile(data: dict[str, Any], *, path: str) -> DriveProfile:
    _require_keys(data, {"owner_id", "dispositions"}, path=path)
    dispositions_raw = data["dispositions"]
    if not isinstance(dispositions_raw, list):
        raise DomainSerializationError("invalid_array", f"{path}.dispositions")
    try:
        dispositions = tuple(
            _decode_drive_disposition(item, path=f"{path}.dispositions[{index}]")
            for index, item in enumerate(dispositions_raw)
            if _ensure_dict(item, path=f"{path}.dispositions[{index}]") or True
        )
        return DriveProfile(
            owner_id=AgentId(_str_field(data, "owner_id", path=path)),
            dispositions=dispositions,
        )
    except DomainSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise DomainSerializationError("invalid_model", path) from exc


def _encode_drive_activation(value: DriveActivation) -> dict[str, Any]:
    return {
        "activation": value.activation,
        "confidence": value.confidence,
        "kind": value.kind.value,
        "urgency": value.urgency,
    }


def _decode_drive_activation(data: dict[str, Any], *, path: str) -> DriveActivation:
    _require_keys(data, {"kind", "activation", "urgency", "confidence"}, path=path)
    try:
        return DriveActivation(
            kind=DriveKind(_str_field(data, "kind", path=path)),
            activation=_float_field(data, "activation", path=path),
            urgency=_float_field(data, "urgency", path=path),
            confidence=_float_field(data, "confidence", path=path),
        )
    except DomainSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise DomainSerializationError("invalid_model", path) from exc


def _encode_drive_state(value: DriveState) -> dict[str, Any]:
    return {
        "activations": [_encode_drive_activation(item) for item in value.activations],
        "owner_id": value.owner_id.value,
    }


def _decode_drive_state(data: dict[str, Any], *, path: str) -> DriveState:
    _require_keys(data, {"owner_id", "activations"}, path=path)
    activations_raw = data["activations"]
    if not isinstance(activations_raw, list):
        raise DomainSerializationError("invalid_array", f"{path}.activations")
    try:
        activations = tuple(
            _decode_drive_activation(item, path=f"{path}.activations[{index}]")
            for index, item in enumerate(activations_raw)
            if _ensure_dict(item, path=f"{path}.activations[{index}]") or True
        )
        return DriveState(
            owner_id=AgentId(_str_field(data, "owner_id", path=path)),
            activations=activations,
        )
    except DomainSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise DomainSerializationError("invalid_model", path) from exc


def _encode_goal(value: Goal) -> dict[str, Any]:
    if value.outcome is None or value.progress is None:
        raise DomainSerializationError("invalid_model", "$")
    return {
        "description": value.description,
        "goal_id": value.goal_id.value,
        "model_version": GOAL_MODEL_VERSION,
        "outcome": _encode_goal_outcome(value.outcome),
        "owner_id": value.owner_id.value,
        "priority": value.priority,
        "progress": _encode_goal_progress(value.progress),
        "status": value.status.value,
    }


def _decode_goal(data: dict[str, Any], *, path: str) -> Goal:
    present = set(data)
    if present == _LEGACY_GOAL_KEYS:
        # Intentional v1→v2 upgrade: default structured outcome/progress.
        try:
            return Goal(
                goal_id=GoalId(_str_field(data, "goal_id", path=path)),
                owner_id=AgentId(_str_field(data, "owner_id", path=path)),
                description=_str_field(data, "description", path=path),
                priority=_float_field(data, "priority", path=path),
                status=GoalStatus(_str_field(data, "status", path=path)),
                outcome=default_goal_outcome(),
                progress=default_goal_progress(),
            )
        except DomainSerializationError:
            raise
        except (TypeError, ValueError) as exc:
            raise DomainSerializationError("invalid_model", path) from exc
    if "model_version" not in data:
        raise DomainSerializationError(
            "unsupported_schema_version", f"{path}.model_version"
        )
    model_version = _int_field(data, "model_version", path=path)
    if model_version != GOAL_MODEL_VERSION:
        raise DomainSerializationError(
            "unsupported_schema_version", f"{path}.model_version"
        )
    _require_keys(data, _GOAL_V2_KEYS, path=path)
    outcome_raw = data["outcome"]
    progress_raw = data["progress"]
    if not isinstance(outcome_raw, dict):
        raise DomainSerializationError("invalid_object", f"{path}.outcome")
    if not isinstance(progress_raw, dict):
        raise DomainSerializationError("invalid_object", f"{path}.progress")
    try:
        return Goal(
            goal_id=GoalId(_str_field(data, "goal_id", path=path)),
            owner_id=AgentId(_str_field(data, "owner_id", path=path)),
            description=_str_field(data, "description", path=path),
            priority=_float_field(data, "priority", path=path),
            status=GoalStatus(_str_field(data, "status", path=path)),
            outcome=_decode_goal_outcome(outcome_raw, path=f"{path}.outcome"),
            progress=_decode_goal_progress(progress_raw, path=f"{path}.progress"),
        )
    except DomainSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise DomainSerializationError("invalid_model", path) from exc


def _encode_agent(value: Agent) -> dict[str, Any]:
    if value.drives is None:
        raise DomainSerializationError("invalid_model", "$")
    return {
        "agent_id": value.agent_id.value,
        "drives": _encode_drive_profile(value.drives),
        "goals": [_encode_goal(goal) for goal in value.goals],
        "model_version": AGENT_MODEL_VERSION,
        "name": value.name,
    }


def _decode_agent(data: dict[str, Any], *, path: str) -> Agent:
    present = set(data)
    if present == _LEGACY_AGENT_KEYS:
        goals_raw = data["goals"]
        if not isinstance(goals_raw, list):
            raise DomainSerializationError("invalid_array", f"{path}.goals")
        try:
            agent_id = AgentId(_str_field(data, "agent_id", path=path))
            goals = tuple(
                _decode_goal(item, path=f"{path}.goals[{index}]")
                for index, item in enumerate(goals_raw)
                if _ensure_dict(item, path=f"{path}.goals[{index}]") or True
            )
            return Agent(
                agent_id=agent_id,
                name=_str_field(data, "name", path=path),
                goals=goals,
                drives=default_drive_profile(agent_id),
            )
        except DomainSerializationError:
            raise
        except (TypeError, ValueError) as exc:
            raise DomainSerializationError("invalid_model", path) from exc
    if "model_version" not in data:
        raise DomainSerializationError(
            "unsupported_schema_version", f"{path}.model_version"
        )
    model_version = _int_field(data, "model_version", path=path)
    if model_version != AGENT_MODEL_VERSION:
        raise DomainSerializationError(
            "unsupported_schema_version", f"{path}.model_version"
        )
    _require_keys(data, _AGENT_V2_KEYS, path=path)
    goals_raw = data["goals"]
    drives_raw = data["drives"]
    if not isinstance(goals_raw, list):
        raise DomainSerializationError("invalid_array", f"{path}.goals")
    if not isinstance(drives_raw, dict):
        raise DomainSerializationError("invalid_object", f"{path}.drives")
    try:
        goals = tuple(
            _decode_goal(item, path=f"{path}.goals[{index}]")
            for index, item in enumerate(goals_raw)
            if _ensure_dict(item, path=f"{path}.goals[{index}]") or True
        )
        return Agent(
            agent_id=AgentId(_str_field(data, "agent_id", path=path)),
            name=_str_field(data, "name", path=path),
            goals=goals,
            drives=_decode_drive_profile(drives_raw, path=f"{path}.drives"),
        )
    except DomainSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise DomainSerializationError("invalid_model", path) from exc


def _ensure_dict(value: object, *, path: str) -> bool:
    if not isinstance(value, dict):
        raise DomainSerializationError("invalid_object", path)
    return True


def _encode_memory_trace(value: MemoryTrace) -> dict[str, Any]:
    return {
        "access_count": value.access_count,
        "concepts": [
            {"concept": item.concept, "mention_id": item.mention_id.value}
            for item in value.concepts
        ],
        "confidence": value.confidence,
        "context": {
            "location_id": (
                None
                if value.context.location_id is None
                else value.context.location_id.value
            ),
            "tags": list(value.context.tags),
        },
        "created_tick": value.created_tick,
        "emotional_salience": value.emotional_salience,
        "entities": [
            {
                "entity_id": (None if item.entity_id is None else item.entity_id.value),
                "label": item.label,
                "mention_id": item.mention_id.value,
            }
            for item in value.entities
        ],
        "embedding": (
            None
            if value.embedding is None
            else {
                "model": value.embedding.model,
                "vector": list(value.embedding.vector),
                "version": value.embedding.version,
            }
        ),
        "expires_at_tick": value.expires_at_tick,
        "forgotten_at_tick": value.forgotten_at_tick,
        "last_access_tick": value.last_access_tick,
        "lineage": {
            "generation": value.lineage.generation,
            "reconstruction_id": (
                None
                if value.lineage.reconstruction_id is None
                else value.lineage.reconstruction_id.value
            ),
            "source_memory_ids": [
                item.value for item in value.lineage.source_memory_ids
            ],
            "supersedes_memory_id": (
                None
                if value.lineage.supersedes_memory_id is None
                else value.lineage.supersedes_memory_id.value
            ),
        },
        "memory_id": value.memory_id.value,
        "owner_id": value.owner_id.value,
        "provenance": {
            "kind": value.provenance.kind.value,
            "observed_source_id": (
                None
                if value.provenance.observed_source_id is None
                else value.provenance.observed_source_id.value
            ),
            "source_tick": value.provenance.source_tick,
            "speaker_id": (
                None
                if value.provenance.speaker_id is None
                else value.provenance.speaker_id.value
            ),
        },
        "relations": [
            {
                "object": {
                    "kind": item.object.kind.value,
                    "mention_id": item.object.mention_id.value,
                },
                "predicate": item.predicate,
                "relation_id": item.relation_id.value,
                "subject": {
                    "kind": item.subject.kind.value,
                    "mention_id": item.subject.mention_id.value,
                },
            }
            for item in value.relations
        ],
        "source_tick": value.source_tick,
        "trace_version": EPISODIC_MEMORY_TRACE_VERSION,
        "world_revision": value.world_revision.value,
    }


def _decode_memory_trace(data: dict[str, Any], *, path: str) -> MemoryTrace:
    if "content" in data:
        raise DomainSerializationError("unsupported_legacy_memory_payload", path)
    _require_keys(
        data,
        {
            "access_count",
            "concepts",
            "confidence",
            "context",
            "created_tick",
            "emotional_salience",
            "entities",
            "embedding",
            "expires_at_tick",
            "forgotten_at_tick",
            "last_access_tick",
            "lineage",
            "memory_id",
            "owner_id",
            "provenance",
            "relations",
            "source_tick",
            "trace_version",
            "world_revision",
        },
        path=path,
    )
    trace_version = _int_field(data, "trace_version", path=path)
    if trace_version != EPISODIC_MEMORY_TRACE_VERSION:
        raise DomainSerializationError(
            "unsupported_trace_version", f"{path}.trace_version"
        )
    concepts_raw = data["concepts"]
    entities_raw = data["entities"]
    relations_raw = data["relations"]
    context_raw = data["context"]
    provenance_raw = data["provenance"]
    lineage_raw = data["lineage"]
    if not isinstance(concepts_raw, list):
        raise DomainSerializationError("invalid_array", f"{path}.concepts")
    if not isinstance(entities_raw, list):
        raise DomainSerializationError("invalid_array", f"{path}.entities")
    if not isinstance(relations_raw, list):
        raise DomainSerializationError("invalid_array", f"{path}.relations")
    if not isinstance(context_raw, dict):
        raise DomainSerializationError("invalid_object", f"{path}.context")
    if not isinstance(provenance_raw, dict):
        raise DomainSerializationError("invalid_object", f"{path}.provenance")
    if not isinstance(lineage_raw, dict):
        raise DomainSerializationError("invalid_object", f"{path}.lineage")
    try:
        concepts = tuple(
            _decode_concept_mention(item, path=f"{path}.concepts[{index}]")
            for index, item in enumerate(concepts_raw)
        )
        entities = tuple(
            _decode_entity_mention(item, path=f"{path}.entities[{index}]")
            for index, item in enumerate(entities_raw)
        )
        relations = tuple(
            _decode_memory_relation(item, path=f"{path}.relations[{index}]")
            for index, item in enumerate(relations_raw)
        )
        _require_keys(context_raw, {"location_id", "tags"}, path=f"{path}.context")
        tags_raw = context_raw["tags"]
        if not isinstance(tags_raw, list):
            raise DomainSerializationError("invalid_array", f"{path}.context.tags")
        decoded_tags: list[str] = []
        for index, tag in enumerate(tags_raw):
            tag_path = f"{path}.context.tags." + str(index)
            decoded_tags.append(_str_field({"tag": tag}, "tag", path=tag_path))
        tags = tuple(decoded_tags)
        _require_keys(
            provenance_raw,
            {"kind", "observed_source_id", "source_tick", "speaker_id"},
            path=f"{path}.provenance",
        )
        kind_raw = _str_field(provenance_raw, "kind", path=f"{path}.provenance")
        try:
            kind = MemorySourceKind(kind_raw)
        except ValueError as exc:
            raise DomainSerializationError(
                "invalid_enum", f"{path}.provenance.kind"
            ) from exc
        observed_raw = provenance_raw["observed_source_id"]
        observed_source_id = None
        if observed_raw is not None:
            if not isinstance(observed_raw, str):
                raise DomainSerializationError(
                    "invalid_string", f"{path}.provenance.observed_source_id"
                )
            observed_source_id = EventId(observed_raw)
        _require_keys(
            lineage_raw,
            {"generation", "supersedes_memory_id"},
            path=f"{path}.lineage",
            optional={"source_memory_ids", "reconstruction_id"},
        )
        supersedes_raw = lineage_raw["supersedes_memory_id"]
        supersedes = None
        if supersedes_raw is not None:
            if not isinstance(supersedes_raw, str):
                raise DomainSerializationError(
                    "invalid_string", f"{path}.lineage.supersedes_memory_id"
                )
            supersedes = MemoryId(supersedes_raw)
        source_memory_ids: tuple[MemoryId, ...] = ()
        if "source_memory_ids" in lineage_raw:
            sources_raw = lineage_raw["source_memory_ids"]
            if not isinstance(sources_raw, list):
                raise DomainSerializationError(
                    "invalid_array", f"{path}.lineage.source_memory_ids"
                )
            decoded_sources: list[MemoryId] = []
            for index, item in enumerate(sources_raw):
                if not isinstance(item, str):
                    raise DomainSerializationError(
                        "invalid_string",
                        f"{path}.lineage.source_memory_ids." + str(index),
                    )
                decoded_sources.append(MemoryId(item))
            source_memory_ids = tuple(decoded_sources)
        reconstruction_id = None
        if "reconstruction_id" in lineage_raw:
            reconstruction_raw = lineage_raw["reconstruction_id"]
            if reconstruction_raw is not None:
                if not isinstance(reconstruction_raw, str):
                    raise DomainSerializationError(
                        "invalid_string", f"{path}.lineage.reconstruction_id"
                    )
                reconstruction_id = ReconstructionId(reconstruction_raw)
        expires_raw = data["expires_at_tick"]
        forgotten_raw = data["forgotten_at_tick"]
        expires_at_tick = (
            None
            if expires_raw is None
            else _int_field(data, "expires_at_tick", path=path)
        )
        forgotten_at_tick = (
            None
            if forgotten_raw is None
            else _int_field(data, "forgotten_at_tick", path=path)
        )
        embedding = _decode_memory_embedding(
            data["embedding"], path=f"{path}.embedding"
        )
        return MemoryTrace(
            memory_id=MemoryId(_str_field(data, "memory_id", path=path)),
            owner_id=AgentId(_str_field(data, "owner_id", path=path)),
            world_revision=WorldRevision(_int_field(data, "world_revision", path=path)),
            concepts=concepts,
            entities=entities,
            relations=relations,
            context=MemorySituationContext(
                location_id=_optional_entity_id(
                    context_raw["location_id"], path=f"{path}.context.location_id"
                ),
                tags=tags,
            ),
            emotional_salience=_float_field(data, "emotional_salience", path=path),
            confidence=_float_field(data, "confidence", path=path),
            provenance=MemoryProvenance(
                kind=kind,
                source_tick=_int_field(
                    provenance_raw, "source_tick", path=f"{path}.provenance"
                ),
                observed_source_id=observed_source_id,
                speaker_id=_optional_entity_id(
                    provenance_raw["speaker_id"],
                    path=f"{path}.provenance.speaker_id",
                ),
            ),
            created_tick=_int_field(data, "created_tick", path=path),
            source_tick=_int_field(data, "source_tick", path=path),
            last_access_tick=_int_field(data, "last_access_tick", path=path),
            access_count=_int_field(data, "access_count", path=path),
            expires_at_tick=expires_at_tick,
            forgotten_at_tick=forgotten_at_tick,
            lineage=MemoryLineage(
                supersedes_memory_id=supersedes,
                generation=_int_field(
                    lineage_raw, "generation", path=f"{path}.lineage"
                ),
                source_memory_ids=source_memory_ids,
                reconstruction_id=reconstruction_id,
            ),
            embedding=embedding,
        )
    except DomainSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise DomainSerializationError("invalid_model", path) from exc


def _decode_memory_embedding(raw: object, *, path: str) -> MemoryEmbedding | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise DomainSerializationError("invalid_object", path)
    _require_keys(raw, {"model", "vector", "version"}, path=path)
    vector_raw = raw["vector"]
    if not isinstance(vector_raw, list):
        raise DomainSerializationError("invalid_array", f"{path}.vector")
    vector: list[float] = []
    for index, item in enumerate(vector_raw):
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise DomainSerializationError(
                "invalid_float", f"{path}.vector." + str(index)
            )
        number = float(item)
        if not math.isfinite(number):
            raise DomainSerializationError(
                "non_finite_float", f"{path}.vector." + str(index)
            )
        vector.append(0.0 if number == 0.0 else number)
    return MemoryEmbedding(
        vector=tuple(vector),
        model=_str_field(raw, "model", path=path),
        version=_str_field(raw, "version", path=path),
    )


def _decode_reconstructed_memory(
    data: dict[str, Any], *, path: str
) -> ReconstructedMemory:
    _require_keys(
        data,
        {
            "concepts",
            "confidence",
            "context",
            "emotional_salience",
            "entities",
            "fallback_used",
            "generation",
            "narrative",
            "owner_id",
            "policy_id",
            "policy_version",
            "prompt_version",
            "reconstructed_at_tick",
            "reconstruction_id",
            "relations",
            "schema_version",
            "source_memory_ids",
            "used_provider",
        },
        path=path,
    )
    concepts_raw = data["concepts"]
    entities_raw = data["entities"]
    relations_raw = data["relations"]
    context_raw = data["context"]
    sources_raw = data["source_memory_ids"]
    if not isinstance(concepts_raw, list):
        raise DomainSerializationError("invalid_array", f"{path}.concepts")
    if not isinstance(entities_raw, list):
        raise DomainSerializationError("invalid_array", f"{path}.entities")
    if not isinstance(relations_raw, list):
        raise DomainSerializationError("invalid_array", f"{path}.relations")
    if not isinstance(context_raw, dict):
        raise DomainSerializationError("invalid_object", f"{path}.context")
    if not isinstance(sources_raw, list):
        raise DomainSerializationError("invalid_array", f"{path}.source_memory_ids")
    try:
        _require_keys(context_raw, {"location_id", "tags"}, path=f"{path}.context")
        tags_raw = context_raw["tags"]
        if not isinstance(tags_raw, list):
            raise DomainSerializationError("invalid_array", f"{path}.context.tags")
        tags = tuple(
            _str_field({"tag": tag}, "tag", path=f"{path}.context.tags." + str(index))
            for index, tag in enumerate(tags_raw)
        )
        decoded_sources: list[MemoryId] = []
        for index, item in enumerate(sources_raw):
            if not isinstance(item, str):
                raise DomainSerializationError(
                    "invalid_string", f"{path}.source_memory_ids." + str(index)
                )
            decoded_sources.append(MemoryId(item))
        return ReconstructedMemory(
            reconstruction_id=ReconstructionId(
                _str_field(data, "reconstruction_id", path=path)
            ),
            owner_id=AgentId(_str_field(data, "owner_id", path=path)),
            narrative=_str_field(data, "narrative", path=path),
            concepts=tuple(
                _decode_concept_mention(item, path=f"{path}.concepts[{index}]")
                for index, item in enumerate(concepts_raw)
            ),
            entities=tuple(
                _decode_entity_mention(item, path=f"{path}.entities[{index}]")
                for index, item in enumerate(entities_raw)
            ),
            relations=tuple(
                _decode_memory_relation(item, path=f"{path}.relations[{index}]")
                for index, item in enumerate(relations_raw)
            ),
            context=MemorySituationContext(
                location_id=_optional_entity_id(
                    context_raw["location_id"], path=f"{path}.context.location_id"
                ),
                tags=tags,
            ),
            confidence=_float_field(data, "confidence", path=path),
            emotional_salience=_float_field(data, "emotional_salience", path=path),
            source_memory_ids=tuple(decoded_sources),
            generation=_int_field(data, "generation", path=path),
            reconstructed_at_tick=_int_field(data, "reconstructed_at_tick", path=path),
            policy_id=_str_field(data, "policy_id", path=path),
            policy_version=_str_field(data, "policy_version", path=path),
            used_provider=_bool_field(data, "used_provider", path=path),
            fallback_used=_bool_field(data, "fallback_used", path=path),
            prompt_version=_optional_str(data, "prompt_version", path=path),
            schema_version=_optional_str(data, "schema_version", path=path),
        )
    except DomainSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise DomainSerializationError("invalid_model", path) from exc


def _decode_reconstruction_record(
    data: dict[str, Any], *, path: str
) -> ReconstructionRecord:
    _require_keys(
        data,
        {
            "created_tick",
            "fallback_used",
            "owner_id",
            "policy_id",
            "policy_version",
            "prompt_version",
            "reconstructed",
            "reconstruction_id",
            "run_id",
            "schema_version",
            "source_memory_ids",
            "used_provider",
        },
        path=path,
    )
    reconstructed_raw = data["reconstructed"]
    sources_raw = data["source_memory_ids"]
    if not isinstance(reconstructed_raw, dict):
        raise DomainSerializationError("invalid_object", f"{path}.reconstructed")
    if not isinstance(sources_raw, list):
        raise DomainSerializationError("invalid_array", f"{path}.source_memory_ids")
    try:
        decoded_sources: list[MemoryId] = []
        for index, item in enumerate(sources_raw):
            if not isinstance(item, str):
                raise DomainSerializationError(
                    "invalid_string", f"{path}.source_memory_ids." + str(index)
                )
            decoded_sources.append(MemoryId(item))
        return ReconstructionRecord(
            reconstruction_id=ReconstructionId(
                _str_field(data, "reconstruction_id", path=path)
            ),
            run_id=MemoryRunId(_str_field(data, "run_id", path=path)),
            owner_id=AgentId(_str_field(data, "owner_id", path=path)),
            source_memory_ids=tuple(decoded_sources),
            reconstructed=_decode_reconstructed_memory(
                reconstructed_raw, path=f"{path}.reconstructed"
            ),
            created_tick=_int_field(data, "created_tick", path=path),
            policy_id=_str_field(data, "policy_id", path=path),
            policy_version=_str_field(data, "policy_version", path=path),
            used_provider=_bool_field(data, "used_provider", path=path),
            fallback_used=_bool_field(data, "fallback_used", path=path),
            prompt_version=_optional_str(data, "prompt_version", path=path),
            schema_version=_optional_str(data, "schema_version", path=path),
        )
    except DomainSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise DomainSerializationError("invalid_model", path) from exc


def _bool_field(data: Mapping[str, Any], key: str, *, path: str) -> bool:
    value = data[key]
    if type(value) is not bool:
        raise DomainSerializationError("invalid_bool", f"{path}.{key}")
    return value


def _decode_concept_mention(raw: object, *, path: str) -> ConceptMention:
    if not isinstance(raw, dict):
        raise DomainSerializationError("invalid_object", path)
    _require_keys(raw, {"concept", "mention_id"}, path=path)
    return ConceptMention(
        mention_id=MentionId(_str_field(raw, "mention_id", path=path)),
        concept=_str_field(raw, "concept", path=path),
    )


def _decode_entity_mention(raw: object, *, path: str) -> EntityMention:
    if not isinstance(raw, dict):
        raise DomainSerializationError("invalid_object", path)
    _require_keys(raw, {"entity_id", "label", "mention_id"}, path=path)
    return EntityMention(
        mention_id=MentionId(_str_field(raw, "mention_id", path=path)),
        label=_str_field(raw, "label", path=path),
        entity_id=_optional_entity_id(raw["entity_id"], path=f"{path}.entity_id"),
    )


def _decode_relation_endpoint(raw: object, *, path: str) -> RelationEndpoint:
    if not isinstance(raw, dict):
        raise DomainSerializationError("invalid_object", path)
    _require_keys(raw, {"kind", "mention_id"}, path=path)
    kind_raw = _str_field(raw, "kind", path=path)
    try:
        kind = RelationEndpointKind(kind_raw)
    except ValueError as exc:
        raise DomainSerializationError("invalid_enum", f"{path}.kind") from exc
    return RelationEndpoint(
        kind=kind,
        mention_id=MentionId(_str_field(raw, "mention_id", path=path)),
    )


def _decode_memory_relation(raw: object, *, path: str) -> MemoryRelation:
    if not isinstance(raw, dict):
        raise DomainSerializationError("invalid_object", path)
    _require_keys(raw, {"object", "predicate", "relation_id", "subject"}, path=path)
    return MemoryRelation(
        relation_id=MentionId(_str_field(raw, "relation_id", path=path)),
        predicate=_str_field(raw, "predicate", path=path),
        subject=_decode_relation_endpoint(raw["subject"], path=f"{path}.subject"),
        object=_decode_relation_endpoint(raw["object"], path=f"{path}.object"),
    )


def _encode_belief(value: Belief) -> dict[str, Any]:
    return {
        "belief_id": value.belief_id.value,
        "confidence": value.confidence,
        "evidence_memory_ids": [item.value for item in value.evidence_memory_ids],
        "owner_id": value.owner_id.value,
        "proposition": value.proposition,
    }


def _decode_belief(data: dict[str, Any], *, path: str) -> Belief:
    _require_keys(
        data,
        {
            "belief_id",
            "owner_id",
            "proposition",
            "confidence",
            "evidence_memory_ids",
        },
        path=path,
    )
    evidence_raw = data["evidence_memory_ids"]
    if not isinstance(evidence_raw, list):
        raise DomainSerializationError("invalid_array", f"{path}.evidence_memory_ids")
    try:
        evidence = tuple(
            MemoryId(_require_list_str(item, path=f"{path}.evidence_memory_ids[{i}]"))
            for i, item in enumerate(evidence_raw)
        )
        return Belief(
            belief_id=BeliefId(_str_field(data, "belief_id", path=path)),
            owner_id=AgentId(_str_field(data, "owner_id", path=path)),
            proposition=_str_field(data, "proposition", path=path),
            confidence=_float_field(data, "confidence", path=path),
            evidence_memory_ids=evidence,
        )
    except DomainSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise DomainSerializationError("invalid_model", path) from exc


def _encode_relationship(value: Relationship) -> dict[str, Any]:
    return {
        "affinity": value.affinity,
        "kind": value.kind,
        "relationship_id": value.relationship_id.value,
        "source_id": value.source_id.value,
        "target_id": value.target_id.value,
    }


def _decode_relationship(data: dict[str, Any], *, path: str) -> Relationship:
    _require_keys(
        data,
        {"relationship_id", "source_id", "target_id", "kind", "affinity"},
        path=path,
    )
    try:
        return Relationship(
            relationship_id=RelationshipId(
                _str_field(data, "relationship_id", path=path)
            ),
            source_id=AgentId(_str_field(data, "source_id", path=path)),
            target_id=AgentId(_str_field(data, "target_id", path=path)),
            kind=_str_field(data, "kind", path=path),
            affinity=_float_field(data, "affinity", path=path),
        )
    except DomainSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise DomainSerializationError("invalid_model", path) from exc


def _encode_envelope(value: CommunicationEnvelope) -> dict[str, Any]:
    return {
        "envelope_id": value.envelope_id.value,
        "payload": _encode_content(dict(value.payload), path="$.payload"),
        "recipient_id": value.recipient_id.value,
        "sender_id": value.sender_id.value,
    }


def _decode_envelope(data: dict[str, Any], *, path: str) -> CommunicationEnvelope:
    _require_keys(
        data, {"envelope_id", "sender_id", "recipient_id", "payload"}, path=path
    )
    payload = data["payload"]
    if not isinstance(payload, dict):
        raise DomainSerializationError("invalid_object", f"{path}.payload")
    try:
        return CommunicationEnvelope(
            envelope_id=EnvelopeId(_str_field(data, "envelope_id", path=path)),
            sender_id=AgentId(_str_field(data, "sender_id", path=path)),
            recipient_id=AgentId(_str_field(data, "recipient_id", path=path)),
            payload=_decode_content(payload, path=f"{path}.payload"),  # type: ignore[arg-type]
        )
    except DomainSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise DomainSerializationError("invalid_model", path) from exc


def _encode_command(value: object) -> dict[str, Any]:
    match value:
        case Move(destination_id=destination_id):
            return {"destination_id": destination_id.value}
        case Search(target_id=target_id):
            return {
                "target_id": None if target_id is None else target_id.value,
            }
        case Take(item_id=item_id) | Drop(item_id=item_id) | Eat(item_id=item_id):
            return {"item_id": item_id.value}
        case Give(recipient_id=recipient_id, item_id=item_id):
            return {
                "item_id": item_id.value,
                "recipient_id": recipient_id.value,
            }
        case Drink(source_id=source_id):
            return {"source_id": source_id.value}
        case Sleep() | Wait():
            return {}
        case (
            Talk(recipient_id=recipient_id, text=text)
            | Ask(recipient_id=recipient_id, text=text)
            | Tell(recipient_id=recipient_id, text=text)
        ):
            return {"recipient_id": recipient_id.value, "text": text}
        case Help(target_id=target_id) | Attack(target_id=target_id):
            return {"target_id": target_id.value}
        case Flee(threat_id=threat_id):
            return {"threat_id": None if threat_id is None else threat_id.value}
        case _:
            raise DomainSerializationError("unsupported_type", "$")


def _decode_command(tag: str, data: dict[str, Any], *, path: str) -> object:
    try:
        if tag == "move":
            _require_keys(data, {"destination_id"}, path=path)
            return Move(EntityId(_str_field(data, "destination_id", path=path)))
        if tag == "search":
            _require_keys(data, {"target_id"}, path=path)
            target = _optional_str(data, "target_id", path=path)
            return Search(None if target is None else EntityId(target))
        if tag == "take":
            _require_keys(data, {"item_id"}, path=path)
            return Take(EntityId(_str_field(data, "item_id", path=path)))
        if tag == "drop":
            _require_keys(data, {"item_id"}, path=path)
            return Drop(EntityId(_str_field(data, "item_id", path=path)))
        if tag == "give":
            _require_keys(data, {"recipient_id", "item_id"}, path=path)
            return Give(
                EntityId(_str_field(data, "recipient_id", path=path)),
                EntityId(_str_field(data, "item_id", path=path)),
            )
        if tag == "eat":
            _require_keys(data, {"item_id"}, path=path)
            return Eat(EntityId(_str_field(data, "item_id", path=path)))
        if tag == "drink":
            _require_keys(data, {"source_id"}, path=path)
            return Drink(EntityId(_str_field(data, "source_id", path=path)))
        if tag == "sleep":
            _require_keys(data, set(), path=path)
            return Sleep()
        if tag == "talk":
            _require_keys(data, {"recipient_id", "text"}, path=path)
            return Talk(
                EntityId(_str_field(data, "recipient_id", path=path)),
                _str_field(data, "text", path=path),
            )
        if tag == "ask":
            _require_keys(data, {"recipient_id", "text"}, path=path)
            return Ask(
                EntityId(_str_field(data, "recipient_id", path=path)),
                _str_field(data, "text", path=path),
            )
        if tag == "tell":
            _require_keys(data, {"recipient_id", "text"}, path=path)
            return Tell(
                EntityId(_str_field(data, "recipient_id", path=path)),
                _str_field(data, "text", path=path),
            )
        if tag == "help":
            _require_keys(data, {"target_id"}, path=path)
            return Help(EntityId(_str_field(data, "target_id", path=path)))
        if tag == "attack":
            _require_keys(data, {"target_id"}, path=path)
            return Attack(EntityId(_str_field(data, "target_id", path=path)))
        if tag == "flee":
            _require_keys(data, {"threat_id"}, path=path)
            threat = _optional_str(data, "threat_id", path=path)
            return Flee(None if threat is None else EntityId(threat))
        if tag == "wait":
            _require_keys(data, set(), path=path)
            return Wait()
    except DomainSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise DomainSerializationError("invalid_model", path) from exc
    raise DomainSerializationError("unknown_type", "$.type")


def _encode_proposal(value: ActionProposal) -> dict[str, Any]:
    command_tag, command_data = value.command.kind, _encode_command(value.command)
    return {
        "command": {"data": command_data, "type": command_tag},
        "proposal_id": value.proposal_id.value,
    }


def _decode_proposal(data: dict[str, Any], *, path: str) -> ActionProposal:
    _require_keys(data, {"proposal_id", "command"}, path=path)
    command_obj = data["command"]
    if not isinstance(command_obj, dict) or set(command_obj) != {"type", "data"}:
        raise DomainSerializationError("invalid_object", f"{path}.command")
    tag = command_obj["type"]
    command_data = command_obj["data"]
    if not isinstance(tag, str) or not isinstance(command_data, dict):
        raise DomainSerializationError("invalid_object", f"{path}.command")
    try:
        command = _decode_command(tag, command_data, path=f"{path}.command.data")
        return ActionProposal(
            proposal_id=ProposalId(_str_field(data, "proposal_id", path=path)),
            command=require_agent_command(command),
        )
    except DomainSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise DomainSerializationError("invalid_model", path) from exc


def _encode_observation(value: Observation) -> dict[str, Any]:
    return {
        "communications": [
            _encode_observed_communication(item) for item in value.communications
        ],
        "day_phase": None if value.day_phase is None else value.day_phase.value,
        "exits": [_encode_visible_exit(item) for item in value.exits],
        "hour": value.hour,
        "items": [_encode_observed_item(item) for item in value.items],
        "locations": [_encode_observed_location(item) for item in value.locations],
        "observer_id": value.observer_id.value,
        "occurrences": [
            _encode_observed_occurrence(item) for item in value.occurrences
        ],
        "resources": [_encode_observed_resource(item) for item in value.resources],
        "revision": value.revision.value,
        "self_body": None
        if value.self_body is None
        else _encode_observed_self(value.self_body),
        "tick": value.tick,
        "visibility": value.visibility,
        "visible_bodies": [_encode_visible_body(item) for item in value.visible_bodies],
        "weather_condition": (
            None if value.weather_condition is None else value.weather_condition.value
        ),
        "world_id": value.world_id.value,
    }


def _decode_observation(data: dict[str, Any], *, path: str) -> Observation:
    _require_keys(
        data,
        {
            "world_id",
            "observer_id",
            "revision",
            "tick",
            "self_body",
            "locations",
            "items",
            "resources",
            "exits",
            "visible_bodies",
            "occurrences",
            "communications",
            "hour",
            "day_phase",
            "visibility",
            "weather_condition",
        },
        path=path,
    )
    self_body_raw = data["self_body"]
    try:
        self_body = None
        if self_body_raw is not None:
            if not isinstance(self_body_raw, dict):
                raise DomainSerializationError("invalid_object", f"{path}.self_body")
            self_body = _decode_observed_self(self_body_raw, path=f"{path}.self_body")
        day_phase_raw = data["day_phase"]
        day_phase = None
        if day_phase_raw is not None:
            if not isinstance(day_phase_raw, str):
                raise DomainSerializationError("invalid_enum", f"{path}.day_phase")
            day_phase = DayPhase(day_phase_raw)
        weather_raw = data["weather_condition"]
        weather_condition = None
        if weather_raw is not None:
            if not isinstance(weather_raw, str):
                raise DomainSerializationError(
                    "invalid_enum", f"{path}.weather_condition"
                )
            weather_condition = WeatherCondition(weather_raw)
        return Observation(
            world_id=WorldId(_str_field(data, "world_id", path=path)),
            observer_id=EntityId(_str_field(data, "observer_id", path=path)),
            revision=WorldRevision(_int_field(data, "revision", path=path)),
            tick=_int_field(data, "tick", path=path),
            self_body=self_body,
            locations=_decode_object_list(
                data["locations"],
                _decode_observed_location,
                path=f"{path}.locations",
            ),
            items=_decode_object_list(
                data["items"], _decode_observed_item, path=f"{path}.items"
            ),
            resources=_decode_object_list(
                data["resources"],
                _decode_observed_resource,
                path=f"{path}.resources",
            ),
            exits=_decode_object_list(
                data["exits"], _decode_visible_exit, path=f"{path}.exits"
            ),
            visible_bodies=_decode_object_list(
                data["visible_bodies"],
                _decode_visible_body,
                path=f"{path}.visible_bodies",
            ),
            occurrences=_decode_object_list(
                data["occurrences"],
                _decode_observed_occurrence,
                path=f"{path}.occurrences",
            ),
            communications=_decode_object_list(
                data["communications"],
                _decode_observed_communication,
                path=f"{path}.communications",
            ),
            hour=None if data["hour"] is None else _int_field(data, "hour", path=path),
            day_phase=day_phase,
            visibility=(
                None
                if data["visibility"] is None
                else _float_field(data, "visibility", path=path)
            ),
            weather_condition=weather_condition,
        )
    except DomainSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise DomainSerializationError("invalid_model", path) from exc


def _encode_observed_location(value: ObservedLocation) -> dict[str, Any]:
    return {"entity_id": value.entity_id.value, "name": value.name}


def _decode_observed_location(data: dict[str, Any], *, path: str) -> ObservedLocation:
    _require_keys(data, {"entity_id", "name"}, path=path)
    try:
        return ObservedLocation(
            entity_id=EntityId(_str_field(data, "entity_id", path=path)),
            name=_str_field(data, "name", path=path),
        )
    except (TypeError, ValueError) as exc:
        raise DomainSerializationError("invalid_model", path) from exc


def _encode_observed_item(value: ObservedItem) -> dict[str, Any]:
    return {
        "entity_id": value.entity_id.value,
        "kind": value.kind.value,
        "load": value.load.value,
        "name": value.name,
        "placement": value.placement.value,
    }


def _decode_observed_item(data: dict[str, Any], *, path: str) -> ObservedItem:
    _require_keys(data, {"entity_id", "name", "kind", "load", "placement"}, path=path)
    try:
        return ObservedItem(
            entity_id=EntityId(_str_field(data, "entity_id", path=path)),
            name=_str_field(data, "name", path=path),
            kind=ItemKind(_str_field(data, "kind", path=path)),
            load=ItemLoad(_int_field(data, "load", path=path)),
            placement=ObservedItemPlacement(_str_field(data, "placement", path=path)),
        )
    except (TypeError, ValueError) as exc:
        raise DomainSerializationError("invalid_model", path) from exc


def _encode_observed_resource(value: ObservedResource) -> dict[str, Any]:
    return {
        "entity_id": value.entity_id.value,
        "kind": value.kind.value,
        "name": value.name,
        "quantity": value.quantity,
        "unit": value.unit,
    }


def _decode_observed_resource(data: dict[str, Any], *, path: str) -> ObservedResource:
    _require_keys(data, {"entity_id", "name", "kind", "quantity", "unit"}, path=path)
    try:
        return ObservedResource(
            entity_id=EntityId(_str_field(data, "entity_id", path=path)),
            name=_str_field(data, "name", path=path),
            kind=ResourceKind(_str_field(data, "kind", path=path)),
            quantity=_float_field(data, "quantity", path=path),
            unit=_str_field(data, "unit", path=path),
        )
    except (TypeError, ValueError) as exc:
        raise DomainSerializationError("invalid_model", path) from exc


def _encode_observed_self(value: ObservedSelf) -> dict[str, Any]:
    return {
        "carry_capacity": value.carry_capacity.value,
        "entity_id": value.entity_id.value,
        "fatigue": value.fatigue.value,
        "health": value.health.value,
        "hunger": value.hunger.value,
        "inventory": [item.value for item in value.inventory],
        "life_status": value.life_status.value,
        "location_id": value.location_id.value,
        "temperature": value.temperature.value,
        "thirst": value.thirst.value,
    }


def _decode_observed_self(data: dict[str, Any], *, path: str) -> ObservedSelf:
    _require_keys(
        data,
        {
            "entity_id",
            "location_id",
            "health",
            "hunger",
            "thirst",
            "fatigue",
            "temperature",
            "inventory",
            "life_status",
            "carry_capacity",
        },
        path=path,
    )
    inventory_raw = data["inventory"]
    if not isinstance(inventory_raw, list):
        raise DomainSerializationError("invalid_array", f"{path}.inventory")
    try:
        inventory_items: list[EntityId] = []
        for index, item in enumerate(inventory_raw):
            if not isinstance(item, str):
                raise DomainSerializationError(
                    "invalid_string", f"{path}.inventory[{index}]"
                )
            inventory_items.append(EntityId(item))
        inventory = tuple(inventory_items)
        return ObservedSelf(
            entity_id=EntityId(_str_field(data, "entity_id", path=path)),
            location_id=EntityId(_str_field(data, "location_id", path=path)),
            health=Health(_float_field(data, "health", path=path)),
            hunger=Hunger(_float_field(data, "hunger", path=path)),
            thirst=Thirst(_float_field(data, "thirst", path=path)),
            fatigue=Fatigue(_float_field(data, "fatigue", path=path)),
            temperature=TemperatureCelsius(
                _float_field(data, "temperature", path=path)
            ),
            inventory=inventory,
            life_status=LifeStatus(_str_field(data, "life_status", path=path)),
            carry_capacity=CarryCapacity(_int_field(data, "carry_capacity", path=path)),
        )
    except DomainSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise DomainSerializationError("invalid_model", path) from exc


def _encode_visible_exit(value: VisibleExit) -> dict[str, Any]:
    return {"destination_id": value.destination_id.value, "name": value.name}


def _decode_visible_exit(data: dict[str, Any], *, path: str) -> VisibleExit:
    _require_keys(data, {"destination_id", "name"}, path=path)
    try:
        return VisibleExit(
            destination_id=EntityId(_str_field(data, "destination_id", path=path)),
            name=_str_field(data, "name", path=path),
        )
    except (TypeError, ValueError) as exc:
        raise DomainSerializationError("invalid_model", path) from exc


def _encode_visible_body(value: VisibleBody) -> dict[str, Any]:
    return {
        "coarse_health": value.coarse_health.value,
        "entity_id": value.entity_id.value,
        "life_status": value.life_status.value,
    }


def _decode_visible_body(data: dict[str, Any], *, path: str) -> VisibleBody:
    _require_keys(data, {"entity_id", "life_status", "coarse_health"}, path=path)
    try:
        return VisibleBody(
            entity_id=EntityId(_str_field(data, "entity_id", path=path)),
            life_status=LifeStatus(_str_field(data, "life_status", path=path)),
            coarse_health=CoarseHealth(_str_field(data, "coarse_health", path=path)),
        )
    except (TypeError, ValueError) as exc:
        raise DomainSerializationError("invalid_model", path) from exc


def _encode_provenance(value: ObservationProvenance) -> dict[str, Any]:
    return {
        "source_event_id": (
            None if value.source_event_id is None else value.source_event_id.value
        ),
        "source_kind": value.source_kind.value,
        "source_tick": value.source_tick,
    }


def _decode_provenance(data: dict[str, Any], *, path: str) -> ObservationProvenance:
    _require_keys(data, {"source_kind", "source_tick", "source_event_id"}, path=path)
    event_raw = data["source_event_id"]
    try:
        source_event_id = None
        if event_raw is not None:
            if not isinstance(event_raw, str):
                raise DomainSerializationError(
                    "invalid_string", f"{path}.source_event_id"
                )
            source_event_id = EventId(event_raw)
        return ObservationProvenance(
            source_kind=ObservationSourceKind(
                _str_field(data, "source_kind", path=path)
            ),
            source_tick=_int_field(data, "source_tick", path=path),
            source_event_id=source_event_id,
        )
    except (TypeError, ValueError) as exc:
        raise DomainSerializationError("invalid_model", path) from exc


def _encode_observed_occurrence(value: ObservedOccurrence) -> dict[str, Any]:
    return {
        "actor_id": None if value.actor_id is None else value.actor_id.value,
        "audience_role": value.audience_role.value,
        "destination_id": (
            None if value.destination_id is None else value.destination_id.value
        ),
        "kind": value.kind,
        "other_entity_id": (
            None if value.other_entity_id is None else value.other_entity_id.value
        ),
        "provenance": _encode_provenance(value.provenance),
        "public_facts": dict(value.public_facts),
        "success": value.success,
    }


def _decode_observed_occurrence(
    data: dict[str, Any], *, path: str
) -> ObservedOccurrence:
    _require_keys(
        data,
        {
            "provenance",
            "kind",
            "audience_role",
            "actor_id",
            "other_entity_id",
            "destination_id",
            "success",
            "public_facts",
        },
        path=path,
    )
    provenance_raw = data["provenance"]
    if not isinstance(provenance_raw, dict):
        raise DomainSerializationError("invalid_object", f"{path}.provenance")
    facts_raw = data["public_facts"]
    if not isinstance(facts_raw, dict):
        raise DomainSerializationError("invalid_object", f"{path}.public_facts")
    try:
        actor_raw = data["actor_id"]
        other_raw = data["other_entity_id"]
        destination_raw = data["destination_id"]
        success_raw = data["success"]
        if success_raw is not None and type(success_raw) is not bool:
            raise DomainSerializationError("invalid_bool", f"{path}.success")
        return ObservedOccurrence(
            provenance=_decode_provenance(provenance_raw, path=f"{path}.provenance"),
            kind=_str_field(data, "kind", path=path),
            audience_role=ObservationAudienceRole(
                _str_field(data, "audience_role", path=path)
            ),
            actor_id=_optional_entity_id(actor_raw, path=f"{path}.actor_id"),
            other_entity_id=_optional_entity_id(
                other_raw, path=f"{path}.other_entity_id"
            ),
            destination_id=_optional_entity_id(
                destination_raw, path=f"{path}.destination_id"
            ),
            success=success_raw,
            public_facts=facts_raw,
        )
    except DomainSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise DomainSerializationError("invalid_model", path) from exc


def _encode_observed_communication(value: ObservedCommunication) -> dict[str, Any]:
    return {
        "listener_id": value.listener_id.value,
        "provenance": _encode_provenance(value.provenance),
        "speaker_id": value.speaker_id.value,
        "text": value.text,
    }


def _decode_observed_communication(
    data: dict[str, Any], *, path: str
) -> ObservedCommunication:
    _require_keys(data, {"provenance", "speaker_id", "listener_id", "text"}, path=path)
    provenance_raw = data["provenance"]
    if not isinstance(provenance_raw, dict):
        raise DomainSerializationError("invalid_object", f"{path}.provenance")
    try:
        return ObservedCommunication(
            provenance=_decode_provenance(provenance_raw, path=f"{path}.provenance"),
            speaker_id=EntityId(_str_field(data, "speaker_id", path=path)),
            listener_id=EntityId(_str_field(data, "listener_id", path=path)),
            text=_str_field(data, "text", path=path),
        )
    except DomainSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise DomainSerializationError("invalid_model", path) from exc


def _optional_entity_id(value: object, *, path: str) -> EntityId | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise DomainSerializationError("invalid_string", path)
    return EntityId(value)


def _decode_occurrence_context(data: dict[str, Any], *, path: str) -> OccurrenceContext:
    _require_keys(
        data,
        {
            "origin_location_id",
            "destination_location_id",
            "affected_entity_ids",
            "private_recipient_ids",
        },
        path=path,
    )
    affected_raw = data["affected_entity_ids"]
    private_raw = data["private_recipient_ids"]
    if not isinstance(affected_raw, list) or not isinstance(private_raw, list):
        raise DomainSerializationError("invalid_array", path)
    try:
        return OccurrenceContext(
            origin_location_id=_optional_entity_id(
                data["origin_location_id"], path=f"{path}.origin_location_id"
            ),
            destination_location_id=_optional_entity_id(
                data["destination_location_id"],
                path=f"{path}.destination_location_id",
            ),
            affected_entity_ids=tuple(
                EntityId(
                    _require_str_item(item, path=f"{path}.affected_entity_ids[{index}]")
                )
                for index, item in enumerate(affected_raw)
            ),
            private_recipient_ids=tuple(
                EntityId(
                    _require_str_item(
                        item, path=f"{path}.private_recipient_ids[{index}]"
                    )
                )
                for index, item in enumerate(private_raw)
            ),
        )
    except DomainSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise DomainSerializationError("invalid_model", path) from exc


def _require_str_item(value: object, *, path: str) -> str:
    if not isinstance(value, str):
        raise DomainSerializationError("invalid_string", path)
    return value


def _decode_object_list(raw: object, decoder: Any, *, path: str) -> tuple[Any, ...]:
    if not isinstance(raw, list):
        raise DomainSerializationError("invalid_array", path)
    items = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise DomainSerializationError("invalid_object", f"{path}[{index}]")
        items.append(decoder(item, path=f"{path}[{index}]"))
    return tuple(items)


def _encode_event_details(value: object) -> dict[str, Any]:
    details = require_event_details(value)
    match details:
        case Moved(
            destination_id=destination_id,
            resulting_location_id=resulting_location_id,
            fatigue_delta=fatigue_delta,
            resulting_fatigue=resulting_fatigue,
        ):
            payload: dict[str, Any] = {
                "destination_id": destination_id.value,
                "kind": "move",
            }
            if resulting_location_id is not None:
                payload["resulting_location_id"] = resulting_location_id.value
            if fatigue_delta is not None:
                payload["fatigue_delta"] = fatigue_delta
            if resulting_fatigue is not None:
                payload["resulting_fatigue"] = resulting_fatigue
            return payload
        case Searched(
            target_id=target_id,
            success=success,
            created_item_id=created_item_id,
            extracted_quantity=extracted_quantity,
            resulting_resource_quantity=resulting_resource_quantity,
        ):
            payload = {
                "kind": "search",
                "target_id": None if target_id is None else target_id.value,
            }
            if success is not None:
                payload["success"] = success
            if created_item_id is not None:
                payload["created_item_id"] = created_item_id.value
            if extracted_quantity is not None:
                payload["extracted_quantity"] = extracted_quantity
            if resulting_resource_quantity is not None:
                payload["resulting_resource_quantity"] = resulting_resource_quantity
            return payload
        case Taken(item_id=item_id, resulting_holder_id=resulting_holder_id):
            payload = {"item_id": item_id.value, "kind": "take"}
            if resulting_holder_id is not None:
                payload["resulting_holder_id"] = resulting_holder_id.value
            return payload
        case Dropped(item_id=item_id, resulting_location_id=resulting_location_id):
            payload = {"item_id": item_id.value, "kind": "drop"}
            if resulting_location_id is not None:
                payload["resulting_location_id"] = resulting_location_id.value
            return payload
        case Given(
            recipient_id=recipient_id,
            item_id=item_id,
            resulting_holder_id=resulting_holder_id,
        ):
            payload = {
                "item_id": item_id.value,
                "kind": "give",
                "recipient_id": recipient_id.value,
            }
            if resulting_holder_id is not None:
                payload["resulting_holder_id"] = resulting_holder_id.value
            return payload
        case Eaten(
            item_id=item_id,
            hunger_delta=hunger_delta,
            resulting_hunger=resulting_hunger,
        ):
            payload = {"item_id": item_id.value, "kind": "eat"}
            if hunger_delta is not None:
                payload["hunger_delta"] = hunger_delta
            if resulting_hunger is not None:
                payload["resulting_hunger"] = resulting_hunger
            return payload
        case Drunk(
            source_id=source_id,
            consumed_item=consumed_item,
            quantity_delta=quantity_delta,
            resulting_resource_quantity=resulting_resource_quantity,
            thirst_delta=thirst_delta,
            resulting_thirst=resulting_thirst,
        ):
            payload = {"kind": "drink", "source_id": source_id.value}
            if consumed_item is not None:
                payload["consumed_item"] = consumed_item
            if quantity_delta is not None:
                payload["quantity_delta"] = quantity_delta
            if resulting_resource_quantity is not None:
                payload["resulting_resource_quantity"] = resulting_resource_quantity
            if thirst_delta is not None:
                payload["thirst_delta"] = thirst_delta
            if resulting_thirst is not None:
                payload["resulting_thirst"] = resulting_thirst
            return payload
        case Slept(fatigue_delta=fatigue_delta, resulting_fatigue=resulting_fatigue):
            payload = {"kind": "sleep"}
            if fatigue_delta is not None:
                payload["fatigue_delta"] = fatigue_delta
            if resulting_fatigue is not None:
                payload["resulting_fatigue"] = resulting_fatigue
            return payload
        case Talked(recipient_id=recipient_id, text=text):
            return {"kind": "talk", "recipient_id": recipient_id.value, "text": text}
        case Asked(recipient_id=recipient_id, text=text):
            return {"kind": "ask", "recipient_id": recipient_id.value, "text": text}
        case Told(recipient_id=recipient_id, text=text):
            return {"kind": "tell", "recipient_id": recipient_id.value, "text": text}
        case Helped(
            target_id=target_id,
            health_delta=health_delta,
            resulting_target_health=resulting_target_health,
            helper_fatigue_delta=helper_fatigue_delta,
            resulting_helper_fatigue=resulting_helper_fatigue,
        ):
            payload = {"kind": "help", "target_id": target_id.value}
            if health_delta is not None:
                payload["health_delta"] = health_delta
            if resulting_target_health is not None:
                payload["resulting_target_health"] = resulting_target_health
            if helper_fatigue_delta is not None:
                payload["helper_fatigue_delta"] = helper_fatigue_delta
            if resulting_helper_fatigue is not None:
                payload["resulting_helper_fatigue"] = resulting_helper_fatigue
            return payload
        case Attacked(
            target_id=target_id,
            hit=hit,
            damage=damage,
            resulting_target_health=resulting_target_health,
        ):
            payload = {"kind": "attack", "target_id": target_id.value}
            if hit is not None:
                payload["hit"] = hit
            if damage is not None:
                payload["damage"] = damage
            if resulting_target_health is not None:
                payload["resulting_target_health"] = resulting_target_health
            return payload
        case Fled(
            threat_id=threat_id,
            success=success,
            destination_id=destination_id,
            fatigue_delta=fatigue_delta,
            resulting_fatigue=resulting_fatigue,
        ):
            payload = {
                "kind": "flee",
                "threat_id": None if threat_id is None else threat_id.value,
            }
            if success is not None:
                payload["success"] = success
            if destination_id is not None:
                payload["destination_id"] = destination_id.value
            if fatigue_delta is not None:
                payload["fatigue_delta"] = fatigue_delta
            if resulting_fatigue is not None:
                payload["resulting_fatigue"] = resulting_fatigue
            return payload
        case Waited():
            return {"kind": "wait"}
        case WeatherChanged(location_id=location_id, condition=condition):
            return {
                "condition": condition.value,
                "kind": "weather_changed",
                "location_id": location_id.value,
            }
        case ResourceRegenerated(
            resource_id=resource_id,
            quantity_delta=quantity_delta,
            resulting_quantity=resulting_quantity,
        ):
            return {
                "kind": "resource_regenerated",
                "quantity_delta": quantity_delta,
                "resource_id": resource_id.value,
                "resulting_quantity": resulting_quantity,
            }
        case NeedsApplied(
            body_id=body_id,
            resulting_hunger=resulting_hunger,
            resulting_thirst=resulting_thirst,
            resulting_fatigue=resulting_fatigue,
            health_delta=health_delta,
            resulting_health=resulting_health,
        ):
            return {
                "body_id": body_id.value,
                "health_delta": health_delta,
                "kind": "needs_applied",
                "resulting_fatigue": resulting_fatigue,
                "resulting_health": resulting_health,
                "resulting_hunger": resulting_hunger,
                "resulting_thirst": resulting_thirst,
            }
        case ExposureApplied(
            body_id=body_id,
            ambient_celsius=ambient_celsius,
            resulting_temperature=resulting_temperature,
            health_delta=health_delta,
            resulting_health=resulting_health,
        ):
            return {
                "ambient_celsius": ambient_celsius,
                "body_id": body_id.value,
                "health_delta": health_delta,
                "kind": "exposure_applied",
                "resulting_health": resulting_health,
                "resulting_temperature": resulting_temperature,
            }
        case Died(
            body_id=body_id,
            death_cause=death_cause,
            resulting_life_status=resulting_life_status,
        ):
            return {
                "body_id": body_id.value,
                "death_cause": death_cause.value,
                "kind": "died",
                "resulting_life_status": resulting_life_status.value,
            }
        case _:
            raise DomainSerializationError("unsupported_type", "$")


def _decode_event_details(data: dict[str, Any], *, path: str) -> object:
    if "kind" not in data or not isinstance(data["kind"], str):
        raise DomainSerializationError("invalid_fields", path)
    kind = data["kind"]
    fields = {key: value for key, value in data.items() if key != "kind"}
    try:
        if kind == "move":
            allowed = {
                "destination_id",
                "resulting_location_id",
                "fatigue_delta",
                "resulting_fatigue",
            }
            if set(fields) - allowed or "destination_id" not in fields:
                raise DomainSerializationError("invalid_fields", path)
            resulting = (
                EntityId(_str_field(fields, "resulting_location_id", path=path))
                if "resulting_location_id" in fields
                else None
            )
            return Moved(
                EntityId(_str_field(fields, "destination_id", path=path)),
                resulting_location_id=resulting,
                fatigue_delta=(
                    _float_field(fields, "fatigue_delta", path=path)
                    if "fatigue_delta" in fields
                    else None
                ),
                resulting_fatigue=(
                    _float_field(fields, "resulting_fatigue", path=path)
                    if "resulting_fatigue" in fields
                    else None
                ),
            )
        if kind == "search":
            allowed = {
                "target_id",
                "success",
                "created_item_id",
                "extracted_quantity",
                "resulting_resource_quantity",
            }
            if set(fields) - allowed or "target_id" not in fields:
                raise DomainSerializationError("invalid_fields", path)
            target = _optional_str(fields, "target_id", path=path)
            created = (
                EntityId(_str_field(fields, "created_item_id", path=path))
                if "created_item_id" in fields
                else None
            )
            success = fields.get("success")
            if success is not None and type(success) is not bool:
                raise DomainSerializationError("invalid_bool", f"{path}.success")
            return Searched(
                None if target is None else EntityId(target),
                success=success,
                created_item_id=created,
                extracted_quantity=(
                    _float_field(fields, "extracted_quantity", path=path)
                    if "extracted_quantity" in fields
                    else None
                ),
                resulting_resource_quantity=(
                    _float_field(fields, "resulting_resource_quantity", path=path)
                    if "resulting_resource_quantity" in fields
                    else None
                ),
            )
        if kind == "take":
            allowed = {"item_id", "resulting_holder_id"}
            if set(fields) - allowed or "item_id" not in fields:
                raise DomainSerializationError("invalid_fields", path)
            holder = (
                EntityId(_str_field(fields, "resulting_holder_id", path=path))
                if "resulting_holder_id" in fields
                else None
            )
            return Taken(
                EntityId(_str_field(fields, "item_id", path=path)),
                resulting_holder_id=holder,
            )
        if kind == "drop":
            allowed = {"item_id", "resulting_location_id"}
            if set(fields) - allowed or "item_id" not in fields:
                raise DomainSerializationError("invalid_fields", path)
            location = (
                EntityId(_str_field(fields, "resulting_location_id", path=path))
                if "resulting_location_id" in fields
                else None
            )
            return Dropped(
                EntityId(_str_field(fields, "item_id", path=path)),
                resulting_location_id=location,
            )
        if kind == "give":
            allowed = {"recipient_id", "item_id", "resulting_holder_id"}
            missing = "recipient_id" not in fields or "item_id" not in fields
            if set(fields) - allowed or missing:
                raise DomainSerializationError("invalid_fields", path)
            holder = (
                EntityId(_str_field(fields, "resulting_holder_id", path=path))
                if "resulting_holder_id" in fields
                else None
            )
            return Given(
                EntityId(_str_field(fields, "recipient_id", path=path)),
                EntityId(_str_field(fields, "item_id", path=path)),
                resulting_holder_id=holder,
            )
        if kind == "eat":
            allowed = {"item_id", "hunger_delta", "resulting_hunger"}
            if set(fields) - allowed or "item_id" not in fields:
                raise DomainSerializationError("invalid_fields", path)
            return Eaten(
                EntityId(_str_field(fields, "item_id", path=path)),
                hunger_delta=(
                    _float_field(fields, "hunger_delta", path=path)
                    if "hunger_delta" in fields
                    else None
                ),
                resulting_hunger=(
                    _float_field(fields, "resulting_hunger", path=path)
                    if "resulting_hunger" in fields
                    else None
                ),
            )
        if kind == "drink":
            allowed = {
                "source_id",
                "consumed_item",
                "quantity_delta",
                "resulting_resource_quantity",
                "thirst_delta",
                "resulting_thirst",
            }
            if set(fields) - allowed or "source_id" not in fields:
                raise DomainSerializationError("invalid_fields", path)
            consumed = fields.get("consumed_item")
            if consumed is not None and type(consumed) is not bool:
                raise DomainSerializationError("invalid_bool", f"{path}.consumed_item")
            return Drunk(
                EntityId(_str_field(fields, "source_id", path=path)),
                consumed_item=consumed,
                quantity_delta=(
                    _float_field(fields, "quantity_delta", path=path)
                    if "quantity_delta" in fields
                    else None
                ),
                resulting_resource_quantity=(
                    _float_field(fields, "resulting_resource_quantity", path=path)
                    if "resulting_resource_quantity" in fields
                    else None
                ),
                thirst_delta=(
                    _float_field(fields, "thirst_delta", path=path)
                    if "thirst_delta" in fields
                    else None
                ),
                resulting_thirst=(
                    _float_field(fields, "resulting_thirst", path=path)
                    if "resulting_thirst" in fields
                    else None
                ),
            )
        if kind == "sleep":
            allowed = {"fatigue_delta", "resulting_fatigue"}
            if set(fields) - allowed:
                raise DomainSerializationError("invalid_fields", path)
            return Slept(
                fatigue_delta=(
                    _float_field(fields, "fatigue_delta", path=path)
                    if "fatigue_delta" in fields
                    else None
                ),
                resulting_fatigue=(
                    _float_field(fields, "resulting_fatigue", path=path)
                    if "resulting_fatigue" in fields
                    else None
                ),
            )
        if kind == "talk":
            _require_keys(fields, {"recipient_id", "text"}, path=path)
            return Talked(
                EntityId(_str_field(fields, "recipient_id", path=path)),
                _str_field(fields, "text", path=path),
            )
        if kind == "ask":
            _require_keys(fields, {"recipient_id", "text"}, path=path)
            return Asked(
                EntityId(_str_field(fields, "recipient_id", path=path)),
                _str_field(fields, "text", path=path),
            )
        if kind == "tell":
            _require_keys(fields, {"recipient_id", "text"}, path=path)
            return Told(
                EntityId(_str_field(fields, "recipient_id", path=path)),
                _str_field(fields, "text", path=path),
            )
        if kind == "help":
            allowed = {
                "target_id",
                "health_delta",
                "resulting_target_health",
                "helper_fatigue_delta",
                "resulting_helper_fatigue",
            }
            if set(fields) - allowed or "target_id" not in fields:
                raise DomainSerializationError("invalid_fields", path)
            return Helped(
                EntityId(_str_field(fields, "target_id", path=path)),
                health_delta=(
                    _float_field(fields, "health_delta", path=path)
                    if "health_delta" in fields
                    else None
                ),
                resulting_target_health=(
                    _float_field(fields, "resulting_target_health", path=path)
                    if "resulting_target_health" in fields
                    else None
                ),
                helper_fatigue_delta=(
                    _float_field(fields, "helper_fatigue_delta", path=path)
                    if "helper_fatigue_delta" in fields
                    else None
                ),
                resulting_helper_fatigue=(
                    _float_field(fields, "resulting_helper_fatigue", path=path)
                    if "resulting_helper_fatigue" in fields
                    else None
                ),
            )
        if kind == "attack":
            allowed = {"target_id", "hit", "damage", "resulting_target_health"}
            if set(fields) - allowed or "target_id" not in fields:
                raise DomainSerializationError("invalid_fields", path)
            hit = fields.get("hit")
            if hit is not None and type(hit) is not bool:
                raise DomainSerializationError("invalid_bool", f"{path}.hit")
            damage = (
                _int_field(fields, "damage", path=path) if "damage" in fields else None
            )
            return Attacked(
                EntityId(_str_field(fields, "target_id", path=path)),
                hit=hit,
                damage=damage,
                resulting_target_health=(
                    _float_field(fields, "resulting_target_health", path=path)
                    if "resulting_target_health" in fields
                    else None
                ),
            )
        if kind == "flee":
            allowed = {
                "threat_id",
                "success",
                "destination_id",
                "fatigue_delta",
                "resulting_fatigue",
            }
            if set(fields) - allowed or "threat_id" not in fields:
                raise DomainSerializationError("invalid_fields", path)
            threat = _optional_str(fields, "threat_id", path=path)
            success = fields.get("success")
            if success is not None and type(success) is not bool:
                raise DomainSerializationError("invalid_bool", f"{path}.success")
            destination = (
                EntityId(_str_field(fields, "destination_id", path=path))
                if "destination_id" in fields
                else None
            )
            return Fled(
                None if threat is None else EntityId(threat),
                success=success,
                destination_id=destination,
                fatigue_delta=(
                    _float_field(fields, "fatigue_delta", path=path)
                    if "fatigue_delta" in fields
                    else None
                ),
                resulting_fatigue=(
                    _float_field(fields, "resulting_fatigue", path=path)
                    if "resulting_fatigue" in fields
                    else None
                ),
            )
        if kind == "wait":
            _require_keys(fields, set(), path=path)
            return Waited()
        if kind == "weather_changed":
            _require_keys(fields, {"location_id", "condition"}, path=path)
            return WeatherChanged(
                EntityId(_str_field(fields, "location_id", path=path)),
                WeatherCondition(_str_field(fields, "condition", path=path)),
            )
        if kind == "resource_regenerated":
            _require_keys(
                fields,
                {"resource_id", "quantity_delta", "resulting_quantity"},
                path=path,
            )
            return ResourceRegenerated(
                EntityId(_str_field(fields, "resource_id", path=path)),
                _float_field(fields, "quantity_delta", path=path),
                _float_field(fields, "resulting_quantity", path=path),
            )
        if kind == "needs_applied":
            _require_keys(
                fields,
                {
                    "body_id",
                    "resulting_hunger",
                    "resulting_thirst",
                    "resulting_fatigue",
                    "health_delta",
                    "resulting_health",
                },
                path=path,
            )
            return NeedsApplied(
                EntityId(_str_field(fields, "body_id", path=path)),
                _float_field(fields, "resulting_hunger", path=path),
                _float_field(fields, "resulting_thirst", path=path),
                _float_field(fields, "resulting_fatigue", path=path),
                _float_field(fields, "health_delta", path=path),
                _float_field(fields, "resulting_health", path=path),
            )
        if kind == "exposure_applied":
            _require_keys(
                fields,
                {
                    "body_id",
                    "ambient_celsius",
                    "resulting_temperature",
                    "health_delta",
                    "resulting_health",
                },
                path=path,
            )
            return ExposureApplied(
                EntityId(_str_field(fields, "body_id", path=path)),
                _float_field(fields, "ambient_celsius", path=path),
                _float_field(fields, "resulting_temperature", path=path),
                _float_field(fields, "health_delta", path=path),
                _float_field(fields, "resulting_health", path=path),
            )
        if kind == "died":
            _require_keys(
                fields,
                {"body_id", "death_cause", "resulting_life_status"},
                path=path,
            )
            return Died(
                EntityId(_str_field(fields, "body_id", path=path)),
                DeathCause(_str_field(fields, "death_cause", path=path)),
                LifeStatus(_str_field(fields, "resulting_life_status", path=path)),
            )
    except DomainSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise DomainSerializationError("invalid_model", path) from exc
    raise DomainSerializationError("unknown_type", f"{path}.kind")


def _encode_world_event(value: WorldEvent) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "actor_id": None if value.actor_id is None else value.actor_id.value,
        "details": _encode_event_details(value.details),
        "event_id": value.event_id.value,
        "event_type": value.event_type,
        "request_id": value.request_id.value,
        "resulting_revision": value.resulting_revision.value,
        "run_id": value.run_id,
        "schema_version": value.schema_version,
        "sequence": value.sequence,
        "target_id": None if value.target_id is None else value.target_id.value,
        "tick": value.tick,
        "world_id": value.world_id.value,
    }
    if value.cause is not None:
        payload["cause"] = _encode_event_cause(value.cause)
    if value.occurrence is not None:
        payload["occurrence"] = {
            "affected_entity_ids": [
                item.value for item in value.occurrence.affected_entity_ids
            ],
            "destination_location_id": (
                None
                if value.occurrence.destination_location_id is None
                else value.occurrence.destination_location_id.value
            ),
            "origin_location_id": (
                None
                if value.occurrence.origin_location_id is None
                else value.occurrence.origin_location_id.value
            ),
            "private_recipient_ids": [
                item.value for item in value.occurrence.private_recipient_ids
            ],
        }
    return payload


def _encode_event_cause(cause: object) -> dict[str, Any]:
    match cause:
        case ActionCause(request_id=request_id, actor_id=actor_id):
            return {
                "actor_id": actor_id.value,
                "kind": "action",
                "request_id": request_id.value,
            }
        case SystemCause(
            cause_id=cause_id,
            effect_family=effect_family,
            entity_id=entity_id,
            family_ordinal=family_ordinal,
        ):
            return {
                "cause_id": cause_id.value,
                "effect_family": effect_family.value,
                "entity_id": entity_id.value,
                "family_ordinal": family_ordinal,
                "kind": "system",
            }
        case _:
            raise DomainSerializationError("unsupported_type", "$.cause")


def _decode_event_cause(data: dict[str, Any], *, path: str) -> object:
    if "kind" not in data or not isinstance(data["kind"], str):
        raise DomainSerializationError("invalid_fields", path)
    kind = data["kind"]
    fields = {key: value for key, value in data.items() if key != "kind"}
    if kind == "action":
        _require_keys(fields, {"request_id", "actor_id"}, path=path)
        return ActionCause(
            RequestId(_str_field(fields, "request_id", path=path)),
            EntityId(_str_field(fields, "actor_id", path=path)),
        )
    if kind == "system":
        _require_keys(
            fields,
            {"cause_id", "effect_family", "entity_id", "family_ordinal"},
            path=path,
        )
        return SystemCause(
            RequestId(_str_field(fields, "cause_id", path=path)),
            SystemEffectFamily(_str_field(fields, "effect_family", path=path)),
            EntityId(_str_field(fields, "entity_id", path=path)),
            _int_field(fields, "family_ordinal", path=path),
        )
    raise DomainSerializationError("unknown_type", f"{path}.kind")


def _decode_world_event(data: dict[str, Any], *, path: str) -> WorldEvent:
    # Legacy schema-v1 audit shape: identity + details only.
    legacy_keys = {"event_id", "request_id", "world_id", "revision", "details"}
    replay_keys = {
        "event_id",
        "run_id",
        "world_id",
        "tick",
        "sequence",
        "request_id",
        "resulting_revision",
        "schema_version",
        "details",
        "actor_id",
        "target_id",
        "event_type",
        "cause",
        "occurrence",
    }
    keys = set(data)
    details_raw = data.get("details")
    if not isinstance(details_raw, dict):
        raise DomainSerializationError("invalid_object", f"{path}.details")
    details = require_event_details(
        _decode_event_details(details_raw, path=f"{path}.details")
    )
    try:
        if keys == legacy_keys or (
            keys == legacy_keys | {"event_type"} and "schema_version" not in data
        ):
            _require_keys(data, legacy_keys, path=path)
            # Legacy under-specified events remain immutable audit records.
            return WorldEvent(
                event_id=EventId(_str_field(data, "event_id", path=path)),
                run_id="legacy-audit",
                world_id=WorldId(_str_field(data, "world_id", path=path)),
                tick=0,
                sequence=0,
                request_id=RequestId(_str_field(data, "request_id", path=path)),
                resulting_revision=WorldRevision(
                    _int_field(data, "revision", path=path)
                ),
                schema_version=EVENT_SCHEMA_AUDIT_V1,
                details=details,
                actor_id=None,
                target_id=target_id_for_details(details),
            )
        required = replay_keys - {"event_type", "cause", "occurrence"}
        expected = required | ({"event_type"} if "event_type" in data else set())
        expected = expected | ({"cause"} if "cause" in data else set())
        expected = expected | ({"occurrence"} if "occurrence" in data else set())
        _require_keys(data, expected, path=path)
        if keys - replay_keys:
            raise DomainSerializationError("invalid_fields", path)
        schema_version = _int_field(data, "schema_version", path=path)
        if schema_version not in {
            EVENT_SCHEMA_AUDIT_V1,
            EVENT_SCHEMA_REPLAY_V2,
            EVENT_SCHEMA_REPLAY_V3,
            EVENT_SCHEMA_REPLAY_V4,
        }:
            raise DomainSerializationError("unsupported_schema_version", path)
        actor_raw = data["actor_id"]
        target_raw = data["target_id"]
        if actor_raw is None:
            actor_id = None
        else:
            actor_id = EntityId(_optional_actor(actor_raw, path))
        if target_raw is None:
            target_id = None
        else:
            target_id = EntityId(_optional_actor(target_raw, path))
        cause = None
        if "cause" in data:
            cause_raw = data["cause"]
            if not isinstance(cause_raw, dict):
                raise DomainSerializationError("invalid_object", f"{path}.cause")
            cause = _decode_event_cause(cause_raw, path=f"{path}.cause")
        occurrence = None
        if "occurrence" in data:
            occurrence_raw = data["occurrence"]
            if not isinstance(occurrence_raw, dict):
                raise DomainSerializationError("invalid_object", f"{path}.occurrence")
            occurrence = _decode_occurrence_context(
                occurrence_raw, path=f"{path}.occurrence"
            )
        event = WorldEvent(
            event_id=EventId(_str_field(data, "event_id", path=path)),
            run_id=_str_field(data, "run_id", path=path),
            world_id=WorldId(_str_field(data, "world_id", path=path)),
            tick=_int_field(data, "tick", path=path),
            sequence=_int_field(data, "sequence", path=path),
            request_id=RequestId(_str_field(data, "request_id", path=path)),
            resulting_revision=WorldRevision(
                _int_field(data, "resulting_revision", path=path)
            ),
            schema_version=schema_version,
            details=details,
            actor_id=actor_id,
            target_id=target_id,
            cause=cause,  # type: ignore[arg-type]
            occurrence=occurrence,
        )
        if "event_type" in data and data["event_type"] != event.event_type:
            raise DomainSerializationError("invalid_fields", f"{path}.event_type")
        return event
    except (TypeError, ValueError) as exc:
        if isinstance(exc, DomainSerializationError):
            raise
        raise DomainSerializationError("invalid_model", path) from exc


def _optional_actor(raw: object, path: str) -> str:
    if not isinstance(raw, str):
        raise DomainSerializationError("invalid_string", path)
    return raw


def _encode_export(value: SimulationExport) -> dict[str, Any]:
    return {
        "events": [_encode_world_event(event) for event in value.events],
        "metadata": {
            "derivation_version": value.metadata.derivation_version,
            "llm_replay": value.metadata.llm_replay,
            "run_id": value.metadata.run_id.value,
            "seed": value.metadata.seed,
        },
    }


def _decode_export(data: dict[str, Any], *, path: str) -> SimulationExport:
    _require_keys(data, {"metadata", "events"}, path=path)
    metadata = data["metadata"]
    events_raw = data["events"]
    if not isinstance(metadata, dict):
        raise DomainSerializationError("invalid_object", f"{path}.metadata")
    if not isinstance(events_raw, list):
        raise DomainSerializationError("invalid_array", f"{path}.events")
    _require_keys(
        metadata,
        {"run_id", "seed", "derivation_version", "llm_replay"},
        path=f"{path}.metadata",
    )
    llm_replay = metadata["llm_replay"]
    if llm_replay != LLM_REPLAY_REQUIREMENT:
        raise DomainSerializationError("invalid_model", f"{path}.metadata.llm_replay")
    try:
        events = tuple(
            _decode_world_event(item, path=f"{path}.events[{index}]")
            for index, item in enumerate(events_raw)
            if _ensure_dict(item, path=f"{path}.events[{index}]") or True
        )
        return SimulationExport(
            metadata=ExportMetadata(
                run_id=RunId(_str_field(metadata, "run_id", path=f"{path}.metadata")),
                seed=_int_field(metadata, "seed", path=f"{path}.metadata"),
                derivation_version=_str_field(
                    metadata, "derivation_version", path=f"{path}.metadata"
                ),
                llm_replay=LLM_REPLAY_REQUIREMENT,
            ),
            events=events,
        )
    except DomainSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise DomainSerializationError("invalid_model", path) from exc
