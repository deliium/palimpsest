"""Strict versioned domain serialization boundary.

Codecs emit no logs. Errors expose only stable ``code`` and ``path`` metadata.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from typing import Any, Final

from agents.models import Agent, AgentId, Goal, GoalId, GoalStatus
from memory.models import Belief, BeliefId, MemoryId, MemoryTrace
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
from world.events import (
    EVENT_SCHEMA_AUDIT_V1,
    EVENT_SCHEMA_REPLAY_V1,
    Asked,
    Attacked,
    Dropped,
    Drunk,
    Eaten,
    Fled,
    Given,
    Helped,
    Moved,
    Searched,
    Slept,
    Taken,
    Talked,
    Told,
    Waited,
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
from world.models import AgentBody, Item, LifeStatus, Location, Resource, Weather
from world.observations import Observation
from world.values import Fatigue, Health, Hunger, TemperatureCelsius, Thirst

SCHEMA_VERSION: Final[int] = 1
_INT64_MIN = -(2**63)
_INT64_MAX = 2**63 - 1

SerializableDomainValue = (
    Location
    | Item
    | Resource
    | Weather
    | AgentBody
    | Agent
    | Goal
    | MemoryTrace
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
    if type(value) is Agent:
        return "agent", _encode_agent(value)
    if type(value) is Goal:
        return "goal", _encode_goal(value)
    if type(value) is MemoryTrace:
        return "memory_trace", _encode_memory_trace(value)
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
    if tag == "agent":
        return _decode_agent(data, path=path)
    if tag == "goal":
        return _decode_goal(data, path=path)
    if tag == "memory_trace":
        return _decode_memory_trace(data, path=path)
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


def _require_keys(data: Mapping[str, Any], keys: set[str], *, path: str) -> None:
    if set(data) != keys:
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
    return {"entity_id": value.entity_id.value, "name": value.name}


def _decode_location(data: dict[str, Any], *, path: str) -> Location:
    _require_keys(data, {"entity_id", "name"}, path=path)
    try:
        return Location(
            entity_id=EntityId(_str_field(data, "entity_id", path=path)),
            name=_str_field(data, "name", path=path),
        )
    except DomainSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise DomainSerializationError("invalid_model", path) from exc


def _encode_item(value: Item) -> dict[str, Any]:
    return {
        "entity_id": value.entity_id.value,
        "holder_id": None if value.holder_id is None else value.holder_id.value,
        "location_id": None if value.location_id is None else value.location_id.value,
        "name": value.name,
    }


def _decode_item(data: dict[str, Any], *, path: str) -> Item:
    _require_keys(data, {"entity_id", "name", "location_id", "holder_id"}, path=path)
    location = _optional_str(data, "location_id", path=path)
    holder = _optional_str(data, "holder_id", path=path)
    try:
        return Item(
            entity_id=EntityId(_str_field(data, "entity_id", path=path)),
            name=_str_field(data, "name", path=path),
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
        "location_id": value.location_id.value,
        "name": value.name,
        "quantity": value.quantity,
        "unit": value.unit,
    }


def _decode_resource(data: dict[str, Any], *, path: str) -> Resource:
    _require_keys(
        data, {"entity_id", "name", "location_id", "quantity", "unit"}, path=path
    )
    try:
        return Resource(
            entity_id=EntityId(_str_field(data, "entity_id", path=path)),
            name=_str_field(data, "name", path=path),
            location_id=EntityId(_str_field(data, "location_id", path=path)),
            quantity=_float_field(data, "quantity", path=path),
            unit=_str_field(data, "unit", path=path),
        )
    except DomainSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise DomainSerializationError("invalid_model", path) from exc


def _encode_weather(value: Weather) -> dict[str, Any]:
    return {
        "condition": value.condition,
        "location_id": value.location_id.value,
        "temperature": value.temperature.value,
    }


def _decode_weather(data: dict[str, Any], *, path: str) -> Weather:
    _require_keys(data, {"location_id", "condition", "temperature"}, path=path)
    try:
        return Weather(
            location_id=EntityId(_str_field(data, "location_id", path=path)),
            condition=_str_field(data, "condition", path=path),
            temperature=TemperatureCelsius(
                _float_field(data, "temperature", path=path)
            ),
        )
    except DomainSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise DomainSerializationError("invalid_model", path) from exc


def _encode_agent_body(value: AgentBody) -> dict[str, Any]:
    return {
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
        )
    except DomainSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise DomainSerializationError("invalid_model", path) from exc


def _require_list_str(value: object, *, path: str) -> str:
    if not isinstance(value, str):
        raise DomainSerializationError("invalid_string", path)
    return value


def _encode_goal(value: Goal) -> dict[str, Any]:
    return {
        "description": value.description,
        "goal_id": value.goal_id.value,
        "owner_id": value.owner_id.value,
        "priority": value.priority,
        "status": value.status.value,
    }


def _decode_goal(data: dict[str, Any], *, path: str) -> Goal:
    _require_keys(
        data, {"goal_id", "owner_id", "description", "priority", "status"}, path=path
    )
    try:
        return Goal(
            goal_id=GoalId(_str_field(data, "goal_id", path=path)),
            owner_id=AgentId(_str_field(data, "owner_id", path=path)),
            description=_str_field(data, "description", path=path),
            priority=_float_field(data, "priority", path=path),
            status=GoalStatus(_str_field(data, "status", path=path)),
        )
    except DomainSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise DomainSerializationError("invalid_model", path) from exc


def _encode_agent(value: Agent) -> dict[str, Any]:
    return {
        "agent_id": value.agent_id.value,
        "goals": [_encode_goal(goal) for goal in value.goals],
        "name": value.name,
    }


def _decode_agent(data: dict[str, Any], *, path: str) -> Agent:
    _require_keys(data, {"agent_id", "name", "goals"}, path=path)
    goals_raw = data["goals"]
    if not isinstance(goals_raw, list):
        raise DomainSerializationError("invalid_array", f"{path}.goals")
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
        "content": _encode_content(dict(value.content), path="$.content"),
        "memory_id": value.memory_id.value,
        "owner_id": value.owner_id.value,
        "world_revision": value.world_revision.value,
    }


def _decode_memory_trace(data: dict[str, Any], *, path: str) -> MemoryTrace:
    _require_keys(
        data, {"memory_id", "owner_id", "world_revision", "content"}, path=path
    )
    content = data["content"]
    if not isinstance(content, dict):
        raise DomainSerializationError("invalid_object", f"{path}.content")
    try:
        return MemoryTrace(
            memory_id=MemoryId(_str_field(data, "memory_id", path=path)),
            owner_id=AgentId(_str_field(data, "owner_id", path=path)),
            world_revision=WorldRevision(_int_field(data, "world_revision", path=path)),
            content=_decode_content(content, path=f"{path}.content"),  # type: ignore[arg-type]
        )
    except DomainSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise DomainSerializationError("invalid_model", path) from exc


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
        case Talk(recipient_id=recipient_id, text=text) | Ask(
            recipient_id=recipient_id, text=text
        ) | Tell(recipient_id=recipient_id, text=text):
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
        "items": [_encode_item(item) for item in value.items],
        "locations": [_encode_location(item) for item in value.locations],
        "observer_id": value.observer_id.value,
        "resources": [_encode_resource(item) for item in value.resources],
        "revision": value.revision.value,
        "self_body": None
        if value.self_body is None
        else _encode_agent_body(value.self_body),
        "weather": [_encode_weather(item) for item in value.weather],
        "world_id": value.world_id.value,
    }


def _decode_observation(data: dict[str, Any], *, path: str) -> Observation:
    _require_keys(
        data,
        {
            "world_id",
            "observer_id",
            "revision",
            "self_body",
            "locations",
            "items",
            "resources",
            "weather",
        },
        path=path,
    )
    self_body_raw = data["self_body"]
    try:
        self_body = None
        if self_body_raw is not None:
            if not isinstance(self_body_raw, dict):
                raise DomainSerializationError("invalid_object", f"{path}.self_body")
            self_body = _decode_agent_body(self_body_raw, path=f"{path}.self_body")
        return Observation(
            world_id=WorldId(_str_field(data, "world_id", path=path)),
            observer_id=EntityId(_str_field(data, "observer_id", path=path)),
            revision=WorldRevision(_int_field(data, "revision", path=path)),
            self_body=self_body,
            locations=_decode_object_list(
                data["locations"], _decode_location, path=f"{path}.locations"
            ),
            items=_decode_object_list(
                data["items"], _decode_item, path=f"{path}.items"
            ),
            resources=_decode_object_list(
                data["resources"], _decode_resource, path=f"{path}.resources"
            ),
            weather=_decode_object_list(
                data["weather"], _decode_weather, path=f"{path}.weather"
            ),
        )
    except DomainSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise DomainSerializationError("invalid_model", path) from exc


def _decode_object_list(
    raw: object, decoder: Any, *, path: str
) -> tuple[Any, ...]:
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
        case Moved(destination_id=destination_id):
            return {"destination_id": destination_id.value, "kind": "move"}
        case Searched(target_id=target_id):
            return {
                "kind": "search",
                "target_id": None if target_id is None else target_id.value,
            }
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
        case Eaten(item_id=item_id):
            return {"item_id": item_id.value, "kind": "eat"}
        case Drunk(source_id=source_id):
            return {"kind": "drink", "source_id": source_id.value}
        case Slept():
            return {"kind": "sleep"}
        case Talked(recipient_id=recipient_id, text=text):
            return {"kind": "talk", "recipient_id": recipient_id.value, "text": text}
        case Asked(recipient_id=recipient_id, text=text):
            return {"kind": "ask", "recipient_id": recipient_id.value, "text": text}
        case Told(recipient_id=recipient_id, text=text):
            return {"kind": "tell", "recipient_id": recipient_id.value, "text": text}
        case Helped(target_id=target_id):
            return {"kind": "help", "target_id": target_id.value}
        case Attacked(target_id=target_id):
            return {"kind": "attack", "target_id": target_id.value}
        case Fled(threat_id=threat_id):
            return {
                "kind": "flee",
                "threat_id": None if threat_id is None else threat_id.value,
            }
        case Waited():
            return {"kind": "wait"}
        case _:
            raise DomainSerializationError("unsupported_type", "$")


def _decode_event_details(data: dict[str, Any], *, path: str) -> object:
    if "kind" not in data or not isinstance(data["kind"], str):
        raise DomainSerializationError("invalid_fields", path)
    kind = data["kind"]
    fields = {key: value for key, value in data.items() if key != "kind"}
    try:
        if kind == "move":
            _require_keys(fields, {"destination_id"}, path=path)
            return Moved(EntityId(_str_field(fields, "destination_id", path=path)))
        if kind == "search":
            _require_keys(fields, {"target_id"}, path=path)
            target = _optional_str(fields, "target_id", path=path)
            return Searched(None if target is None else EntityId(target))
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
            _require_keys(fields, {"item_id"}, path=path)
            return Eaten(EntityId(_str_field(fields, "item_id", path=path)))
        if kind == "drink":
            _require_keys(fields, {"source_id"}, path=path)
            return Drunk(EntityId(_str_field(fields, "source_id", path=path)))
        if kind == "sleep":
            _require_keys(fields, set(), path=path)
            return Slept()
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
            _require_keys(fields, {"target_id"}, path=path)
            return Helped(EntityId(_str_field(fields, "target_id", path=path)))
        if kind == "attack":
            _require_keys(fields, {"target_id"}, path=path)
            return Attacked(EntityId(_str_field(fields, "target_id", path=path)))
        if kind == "flee":
            _require_keys(fields, {"threat_id"}, path=path)
            threat = _optional_str(fields, "threat_id", path=path)
            return Fled(None if threat is None else EntityId(threat))
        if kind == "wait":
            _require_keys(fields, set(), path=path)
            return Waited()
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
    return payload


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
        required = replay_keys - {"event_type"}
        expected = required | ({"event_type"} if "event_type" in data else set())
        _require_keys(data, expected, path=path)
        if keys - replay_keys:
            raise DomainSerializationError("invalid_fields", path)
        schema_version = _int_field(data, "schema_version", path=path)
        if schema_version not in {EVENT_SCHEMA_AUDIT_V1, EVENT_SCHEMA_REPLAY_V1}:
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
