"""Stable identifier contracts and deterministic factories."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from agents.models import AgentId, GoalId
from memory.models import BeliefId, MemoryId
from simulation.identifiers import (
    derive_belief_id,
    derive_entity_id,
    derive_envelope_id,
    derive_event_id,
    derive_goal_id,
    derive_memory_id,
    derive_proposal_id,
    derive_relationship_id,
    derive_request_id,
    derive_run_id,
    derive_scoped_id,
    derive_world_id,
)
from simulation.models import SimulationRunConfig
from simulation.randomness import StreamScope
from social.models import EnvelopeId, RelationshipId
from world.identifiers import (
    EntityId,
    EventId,
    ProposalId,
    RequestId,
    WorldId,
    WorldRevision,
)

_VALID_IDS = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N"),
        whitelist_characters="-_",
    ),
    min_size=1,
    max_size=64,
)
_SEEDS = st.integers(min_value=0, max_value=2**31 - 1)
_KEYS = st.lists(_VALID_IDS, min_size=1, max_size=4)


@pytest.mark.parametrize(
    ("wrapper",),
    [
        (EntityId,),
        (WorldId,),
        (ProposalId,),
        (RequestId,),
        (EventId,),
        (AgentId,),
        (GoalId,),
        (MemoryId,),
        (BeliefId,),
        (EnvelopeId,),
        (RelationshipId,),
    ],
)
def test_equal_raw_strings_remain_nominally_distinct(wrapper: type) -> None:
    raw = "shared-id"
    left = wrapper(raw)
    right = EntityId(raw) if wrapper is not EntityId else AgentId(raw)
    assert left.value == right.value
    assert type(left) is not type(right)
    assert left != right


@pytest.mark.parametrize(
    ("wrapper", "invalid"),
    [
        (EntityId, ""),
        (WorldId, " leading"),
        (ProposalId, "trailing "),
        (RequestId, "has\x00null"),
        (EventId, "a" * 129),
        (AgentId, 123),
        (GoalId, None),
        (MemoryId, "\tindent"),
        (BeliefId, "line\nbreak"),
        (EnvelopeId, " "),
        (RelationshipId, "\x7f"),
    ],
)
def test_invalid_stable_ids_are_rejected(wrapper: type, invalid: object) -> None:
    with pytest.raises((ValueError, TypeError)):
        wrapper(invalid)


def test_accepted_ids_are_preserved_verbatim() -> None:
    raw = "Exact-Value_42"
    assert EntityId(raw).value == raw
    assert AgentId(raw).value is raw


def test_world_revision_rejects_non_integers_and_booleans() -> None:
    with pytest.raises(ValueError, match="non-negative integer"):
        WorldRevision(True)
    with pytest.raises(ValueError, match="non-negative integer"):
        WorldRevision(-1)
    with pytest.raises(ValueError, match="non-negative integer"):
        WorldRevision(1.5)  # type: ignore[arg-type]
    assert WorldRevision(0).value == 0


@given(seed=_SEEDS, keys=_KEYS)
@settings(max_examples=40, deadline=None)
def test_property_purpose_factories_are_stable(seed: int, keys: list[str]) -> None:
    config = SimulationRunConfig(seed=seed)
    key_tuple = tuple(keys)
    assert derive_world_id(config, *key_tuple) == derive_world_id(config, *key_tuple)
    assert derive_entity_id(config, *key_tuple) == derive_entity_id(config, *key_tuple)
    assert derive_proposal_id(config, *key_tuple) == derive_proposal_id(
        config, *key_tuple
    )
    assert derive_request_id(config, *key_tuple) == derive_request_id(
        config, *key_tuple
    )
    assert derive_event_id(config, *key_tuple) == derive_event_id(config, *key_tuple)
    assert derive_goal_id(config, *key_tuple) == derive_goal_id(config, *key_tuple)
    assert derive_relationship_id(config, *key_tuple) == derive_relationship_id(
        config, *key_tuple
    )
    assert derive_memory_id(config, *key_tuple) == derive_memory_id(config, *key_tuple)
    assert derive_belief_id(config, *key_tuple) == derive_belief_id(config, *key_tuple)
    assert derive_envelope_id(config, *key_tuple) == derive_envelope_id(
        config, *key_tuple
    )


def test_purpose_namespaces_do_not_alias() -> None:
    config = SimulationRunConfig(seed=42)
    keys = ("alpha", "beta")
    derived = {
        derive_world_id(config, *keys).value,
        derive_entity_id(config, *keys).value,
        derive_proposal_id(config, *keys).value,
        derive_request_id(config, *keys).value,
        derive_event_id(config, *keys).value,
        derive_goal_id(config, *keys).value,
        derive_relationship_id(config, *keys).value,
        derive_memory_id(config, *keys).value,
        derive_belief_id(config, *keys).value,
        derive_envelope_id(config, *keys).value,
        derive_run_id(config).value,
        derive_scoped_id(config, StreamScope(namespace="agent", names=keys)),
    }
    assert len(derived) == 12


def test_ambiguous_key_boundaries_do_not_alias() -> None:
    config = SimulationRunConfig(seed=7)
    left = derive_entity_id(config, "ab", "c")
    right = derive_entity_id(config, "a", "bc")
    assert left != right


def test_existing_run_id_golden_vector_is_unchanged() -> None:
    config = SimulationRunConfig(seed=42)
    assert derive_run_id(config).value == (
        "a2c0644c8d97e30daaa54ef76b5c9f1719ed8ef173255a976e61d5bf19af5ff6"
    )


def test_derivation_v2_aliases_on_rules_fingerprint() -> None:
    from world.models import PhysicalRules, default_physical_rules

    left = SimulationRunConfig(seed=42, physical_rules=default_physical_rules())
    right = SimulationRunConfig(seed=42, physical_rules=PhysicalRules(move_fatigue=6.0))
    assert left.derivation_version == "v2"
    assert derive_run_id(left) != derive_run_id(right)
    assert derive_entity_id(left, "camp") != derive_entity_id(right, "camp")
    with pytest.raises(ValueError, match="derivation-v2 requires physical_rules"):
        SimulationRunConfig(seed=1, derivation_version="v2")
    with pytest.raises(ValueError, match="derivation-v1 forbids physical_rules"):
        SimulationRunConfig(
            seed=1,
            physical_rules=default_physical_rules(),
            derivation_version="v1",
        )


def test_factories_reject_empty_key_sets() -> None:
    config = SimulationRunConfig(seed=1)
    with pytest.raises(ValueError, match="at least one key"):
        derive_entity_id(config)


def test_system_cause_ids_are_purpose_separated() -> None:
    from simulation.identifiers import derive_system_cause_id
    from simulation.models import RunId
    from world.models import default_physical_rules

    config = SimulationRunConfig(seed=9, physical_rules=default_physical_rules())
    run_id = RunId("run-abc")
    world_id = WorldId("world-1")
    entity = EntityId("loc-1")
    weather = derive_system_cause_id(
        config,
        run_id=run_id,
        world_id=world_id,
        tick=5,
        effect_family="weather",
        entity_id=entity,
        family_ordinal=0,
    )
    regen = derive_system_cause_id(
        config,
        run_id=run_id,
        world_id=world_id,
        tick=5,
        effect_family="regeneration",
        entity_id=entity,
        family_ordinal=0,
    )
    assert weather != regen
    assert derive_system_cause_id(
        config,
        run_id=run_id,
        world_id=world_id,
        tick=5,
        effect_family="weather",
        entity_id=entity,
        family_ordinal=0,
    ) == weather


def test_physical_sampling_algorithms_are_deterministic() -> None:
    import random

    from simulation.randomness import (
        sample_attack_damage,
        sample_bernoulli,
        sample_destination_index,
        sample_weather_condition,
    )
    from world.values import WeatherCondition

    left = random.Random(123)
    right = random.Random(123)
    assert sample_bernoulli(left, 0.75) == sample_bernoulli(right, 0.75)
    assert sample_attack_damage(left, minimum=10, maximum_exclusive=21) == (
        sample_attack_damage(right, minimum=10, maximum_exclusive=21)
    )
    assert sample_destination_index(left, 3) == sample_destination_index(right, 3)
    transitions = {
        WeatherCondition.CLEAR: 0.6,
        WeatherCondition.CLOUDY: 0.3,
        WeatherCondition.RAIN: 0.1,
        WeatherCondition.STORM: 0.0,
    }
    assert sample_weather_condition(left, transitions) == sample_weather_condition(
        right, transitions
    )
