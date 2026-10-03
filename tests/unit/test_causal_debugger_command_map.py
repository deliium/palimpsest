"""Unit tests for closed semantic/detail → command_kind mapping."""

from __future__ import annotations

from simulation.causal_debugger import (
    CommandKindMappingStatus,
    map_event_to_command_kind,
)


def test_agent_attacked_maps_to_attack() -> None:
    mapped = map_event_to_command_kind(
        semantic_type="AGENT_ATTACKED",
        detail_kind="attack",
        detail_type_name="Attacked",
    )
    assert mapped.status is CommandKindMappingStatus.MAPPED
    assert mapped.command_kind == "attack"
    assert mapped.reason_code is None


def test_detail_type_name_attacked_maps_when_semantic_absent() -> None:
    mapped = map_event_to_command_kind(detail_type_name="Attacked")
    assert mapped.status is CommandKindMappingStatus.MAPPED
    assert mapped.command_kind == "attack"


def test_died_is_secondary_attack_mapping() -> None:
    mapped = map_event_to_command_kind(
        semantic_type="AGENT_DIED",
        detail_kind="died",
        detail_type_name="Died",
    )
    assert mapped.status is CommandKindMappingStatus.SECONDARY_ATTACK
    assert mapped.command_kind == "attack"
    assert mapped.reason_code == "secondary_consequence_died"


def test_environmental_weather_not_applicable() -> None:
    mapped = map_event_to_command_kind(semantic_type="WEATHER_CHANGED")
    assert mapped.status is CommandKindMappingStatus.NOT_APPLICABLE
    assert mapped.command_kind is None
    assert mapped.reason_code == "causal_trace_not_applicable"


def test_unknown_semantic_warns_unmapped() -> None:
    mapped = map_event_to_command_kind(semantic_type="AGENT_UNKNOWN_GESTURE")
    assert mapped.status is CommandKindMappingStatus.UNMAPPED
    assert mapped.reason_code == "unmapped_semantic_type"


def test_common_agent_commands_table() -> None:
    cases = (
        ("AGENT_MOVED", "move"),
        ("AGENT_TALKED", "talk"),
        ("AGENT_HELPED", "help"),
        ("AGENT_WAITED", "wait"),
        ("RESOURCE_HARVESTED", "harvest"),
        ("ARTIFACT_CREATED", "inscribe"),
    )
    for semantic, expected in cases:
        mapped = map_event_to_command_kind(semantic_type=semantic)
        assert mapped.command_kind == expected, semantic
        assert mapped.status is CommandKindMappingStatus.MAPPED
