"""Contracts and deterministic updates for the causal world model."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from agents.cognition.models import _EFFECT_QUANTUM
from agents.cognition.world_model import (
    WORLD_MODEL_POLICY_VERSION,
    CausalAtom,
    CausalEpisode,
    CausalEpisodeRole,
    CausalHypothesis,
    CausalOutcome,
    CausalProvenanceKind,
    CausalSlot,
    CausalUpdateReason,
    CausalWorldModel,
    WorldModelPolicy,
    confidence_from_masses,
    default_world_model_policy,
    empty_world_model,
    episodes_from_observation,
    hypothesis_id_for,
    update_world_model,
)
from agents.models import AgentId
from world._state import WorldState
from world.identifiers import EntityId, EventId, WorldId, WorldRevision
from world.models import LifeStatus, PhysicalRules
from world.observations import (
    Observation,
    ObservationAudienceRole,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedItem,
    ObservedItemPlacement,
    ObservedOccurrence,
    ObservedSelf,
)
from world.values import (
    CarryCapacity,
    DayPhase,
    Fatigue,
    Health,
    Hunger,
    ItemKind,
    ItemLoad,
    TemperatureCelsius,
    Thirst,
    WeatherCondition,
)

_OWNER = AgentId("agent-1")
_OTHER = AgentId("agent-2")
_LOGGER = "agents.cognition.world_model"


def _atom(slot: CausalSlot, value: str) -> CausalAtom:
    return CausalAtom(slot=slot, value=value)


def _hypothesis(
    *,
    support: float = 4.0,
    counter: float = 0.0,
    owner: AgentId = _OWNER,
    atoms: tuple[CausalAtom, ...] | None = None,
    outcome: CausalOutcome = CausalOutcome.DANGER,
) -> CausalHypothesis:
    resolved = atoms or (
        _atom(CausalSlot.LOCATION, "loc-forest"),
        _atom(CausalSlot.DAY_PHASE, "night"),
    )
    return CausalHypothesis(
        owner_id=owner,
        atoms=resolved,
        outcome=outcome,
        support=support,
        counter=counter,
        evidence_ids=("evidence-1",),
        counter_evidence_ids=tuple(f"counter-{index}" for index in range(int(counter))),
        provenance_kind=CausalProvenanceKind.OBSERVATION,
    )


def _self(
    *,
    health: float = 100.0,
    location: str = "loc-forest",
    inventory: tuple[EntityId, ...] = (),
) -> ObservedSelf:
    return ObservedSelf(
        entity_id=EntityId("body-1"),
        location_id=EntityId(location),
        health=Health(health),
        hunger=Hunger(0.0),
        thirst=Thirst(0.0),
        fatigue=Fatigue(0.0),
        temperature=TemperatureCelsius(36.5),
        inventory=inventory,
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )


def _occurrence(
    kind: str,
    *,
    tick: int,
    success: bool | None = None,
    actor: str = "body-1",
    other: str | None = None,
    event: str | None = None,
) -> ObservedOccurrence:
    return ObservedOccurrence(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.OCCURRENCE,
            source_tick=max(tick - 1, 0),
            source_event_id=EventId(event or f"event-{kind}-{tick}"),
        ),
        kind=kind,
        audience_role=ObservationAudienceRole.ACTOR,
        actor_id=EntityId(actor),
        other_entity_id=None if other is None else EntityId(other),
        success=success,
    )


def _observation(
    *,
    tick: int,
    health: float = 100.0,
    phase: DayPhase | None = DayPhase.NIGHT,
    weather: WeatherCondition | None = None,
    occurrences: tuple[ObservedOccurrence, ...] = (),
    items: tuple[ObservedItem, ...] = (),
    communications: tuple[object, ...] = (),
) -> Observation:
    inventory = tuple(
        item.entity_id
        for item in items
        if item.placement is ObservedItemPlacement.HELD_BY_SELF
    )
    return Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("body-1"),
        revision=WorldRevision(tick),
        tick=tick,
        self_body=_self(health=health, inventory=inventory),
        day_phase=phase,
        weather_condition=weather,
        occurrences=occurrences,
        items=items,
        communications=communications,  # type: ignore[arg-type]
    )


def test_policy_defaults_keep_provider_off() -> None:
    policy = default_world_model_policy()
    assert policy.version == WORLD_MODEL_POLICY_VERSION
    assert policy.prior == 1.0
    assert policy.salience_harm == 4.0
    assert policy.emotion_multiplier == 2.0
    assert policy.generalize_rate == 0.5
    assert policy.action_threshold == 0.55
    assert policy.max_hypotheses == 64
    assert policy.max_history == 32
    assert policy.allow_provider is False


def test_hypothesis_id_is_stable_sha256_of_owner_atoms_and_outcome() -> None:
    night = (
        _atom(CausalSlot.DAY_PHASE, "night"),
        _atom(CausalSlot.LOCATION, "loc-forest"),
    )
    ordered = (
        _atom(CausalSlot.LOCATION, "loc-forest"),
        _atom(CausalSlot.DAY_PHASE, "night"),
    )
    first = hypothesis_id_for(
        owner_id=_OWNER, atoms=night, outcome=CausalOutcome.DANGER
    )
    second = hypothesis_id_for(
        owner_id=_OWNER, atoms=ordered, outcome=CausalOutcome.DANGER
    )
    other_outcome = hypothesis_id_for(
        owner_id=_OWNER, atoms=ordered, outcome=CausalOutcome.HELP
    )
    assert first == second
    assert first.startswith("ch-")
    assert len(first) == 3 + 48
    assert first != other_outcome
    source = (
        Path(__file__).resolve().parents[2] / "src/agents/cognition/world_model.py"
    )
    assert "hash(" not in source.read_text(encoding="utf-8")


def test_confidence_persistence_fixture_stays_above_threshold() -> None:
    one_harm = confidence_from_masses(4.0, 0.0, prior=1.0)
    two_counters = confidence_from_masses(4.0, 2.0, prior=1.0)
    three_counters = confidence_from_masses(4.0, 3.0, prior=1.0)
    policy = WorldModelPolicy()
    assert one_harm == 0.8
    assert abs(two_counters - (4.0 / 7.0)) <= _EFFECT_QUANTUM
    assert two_counters > policy.action_threshold
    assert three_counters == 0.5
    assert three_counters < policy.action_threshold
    stored = _hypothesis(counter=2.0)
    assert stored.confidence == two_counters


def test_constructors_reject_invalid_masses_atoms_and_owners() -> None:
    with pytest.raises(ValueError, match="empty_atoms"):
        CausalHypothesis(
            owner_id=_OWNER,
            atoms=(),
            outcome=CausalOutcome.DANGER,
            support=1.0,
            counter=0.0,
            evidence_ids=(),
            counter_evidence_ids=(),
            provenance_kind=CausalProvenanceKind.OBSERVATION,
        )
    with pytest.raises(ValueError, match="duplicate_slot"):
        _hypothesis(
            atoms=(
                _atom(CausalSlot.LOCATION, "loc-a"),
                _atom(CausalSlot.LOCATION, "loc-b"),
            )
        )
    with pytest.raises(ValueError, match="not_finite"):
        _hypothesis(support=float("nan"))
    with pytest.raises(ValueError, match="unknown_slot"):
        CausalAtom(slot="location", value="loc-forest")  # type: ignore[arg-type]
    foreign = _hypothesis(owner=_OTHER)
    with pytest.raises(ValueError, match="owner_mismatch"):
        CausalWorldModel(owner_id=_OWNER, hypotheses=(foreign,))


def test_construction_logs_metadata_without_atom_values(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger=_LOGGER)
    model = CausalWorldModel(
        owner_id=_OWNER,
        hypotheses=(_hypothesis(atoms=(_atom(CausalSlot.LOCATION, "loc-secret"),)),),
    )
    debug = [
        record.getMessage()
        for record in caplog.records
        if record.levelno == logging.DEBUG
    ]
    assert any(
        _OWNER.value in message
        and "policy_version=world-model-v1" in message
        and "hypothesis_count=1" in message
        for message in debug
    )
    info = [
        record.getMessage()
        for record in caplog.records
        if record.levelno == logging.INFO
    ]
    assert all("loc-secret" not in message for message in info)
    assert model.hypotheses[0].atoms[0].value == "loc-secret"
    caplog.clear()
    with pytest.raises(ValueError, match="empty_atoms"):
        CausalHypothesis(
            owner_id=_OWNER,
            atoms=(),
            outcome=CausalOutcome.DANGER,
            support=1.0,
            counter=0.0,
            evidence_ids=(),
            counter_evidence_ids=(),
            provenance_kind=CausalProvenanceKind.OBSERVATION,
        )
    errors = [
        record.getMessage()
        for record in caplog.records
        if record.levelno == logging.ERROR
    ]
    assert any(
        "field=atoms" in message and "reason_code=empty_atoms" in message
        for message in errors
    )
    assert all("loc-secret" not in message for message in errors)


def test_salient_harm_persists_after_two_mild_counters() -> None:
    policy = WorldModelPolicy()
    model = empty_world_model(_OWNER)
    harmed = _observation(tick=1, health=80.0)
    cursor = CausalWorldModel(
        owner_id=_OWNER,
        last_observed_health=100.0,
        last_tick=0,
    )
    episodes = episodes_from_observation(harmed, _OWNER, cursor)
    model = update_world_model(
        model,
        episodes,
        policy,
        tick=1,
        observed_health=80.0,
    )
    danger = _matching(model, CausalOutcome.DANGER, ("location", "day_phase"))
    assert danger is not None
    assert danger.confidence == 0.8
    parent = _matching(model, CausalOutcome.DANGER, ("location",))
    assert parent is not None
    assert len(parent.atoms) == 1
    for tick in (2, 3):
        quiet = _observation(tick=tick, health=80.0)
        episodes = episodes_from_observation(quiet, _OWNER, model)
        model = update_world_model(
            model,
            episodes,
            policy,
            tick=tick,
            observed_health=80.0,
        )
    persisted = _matching(model, CausalOutcome.DANGER, ("location", "day_phase"))
    assert persisted is not None
    assert persisted.confidence == confidence_from_masses(4.0, 2.0)
    assert persisted.confidence > policy.action_threshold
    reasons = tuple(item.reason for item in persisted.update_history)
    assert reasons[0] is CausalUpdateReason.SUPPORT
    assert reasons[1:] == (CausalUpdateReason.COUNTER, CausalUpdateReason.COUNTER)
    quiet = _observation(tick=4, health=80.0)
    episodes = episodes_from_observation(quiet, _OWNER, model)
    model = update_world_model(
        model, episodes, policy, tick=4, observed_health=80.0
    )
    faded = _matching(model, CausalOutcome.DANGER, ("location", "day_phase"))
    assert faded is not None
    assert faded.confidence == 0.5
    assert faded.confidence < policy.action_threshold


def test_missing_weather_does_not_invent_a_weather_atom() -> None:
    observation = _observation(tick=1, weather=None, health=80.0)
    cursor = CausalWorldModel(
        owner_id=_OWNER, last_observed_health=100.0, last_tick=0
    )
    episodes = episodes_from_observation(observation, _OWNER, cursor)
    assert episodes
    assert all(
        atom.slot is not CausalSlot.WEATHER
        for episode in episodes
        for atom in episode.atoms
    )


def test_observation_builder_rejects_engine_types() -> None:
    with pytest.raises(TypeError, match="invalid_observation"):
        episodes_from_observation(PhysicalRules(), _OWNER, None)
    with pytest.raises(TypeError, match="invalid_observation"):
        episodes_from_observation(WorldState(WorldRevision(0)), _OWNER, None)


def test_opposite_search_counters_and_silence_does_not(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger=_LOGGER)
    policy = WorldModelPolicy()
    failure = _support_episode(CausalOutcome.SEARCH_FAILURE, tick=1)
    model = update_world_model(
        empty_world_model(_OWNER),
        (failure,),
        policy,
        tick=1,
    )
    existing = model.hypotheses[0]
    quiet = CausalEpisode(
        owner_id=_OWNER,
        tick=2,
        outcome=CausalOutcome.DANGER,
        atoms=(_atom(CausalSlot.LOCATION, "loc-forest"),),
        evidence_id="ambient-2",
        provenance_kind=CausalProvenanceKind.OBSERVATION,
        role=CausalEpisodeRole.COUNTER,
    )
    held = update_world_model(model, (quiet,), policy, tick=2)
    assert held.hypotheses[0].counter == existing.counter
    success = _support_episode(CausalOutcome.SEARCH_SUCCESS, tick=3)
    countered = update_world_model(held, (success,), policy, tick=3)
    failure_after = next(
        item
        for item in countered.hypotheses
        if item.outcome is CausalOutcome.SEARCH_FAILURE
        and len(item.atoms) == len(failure.atoms)
    )
    assert failure_after.counter == 1.0
    info = [
        record.getMessage()
        for record in caplog.records
        if record.levelno == logging.INFO
        and "world_model_updated" in record.getMessage()
    ]
    assert info
    assert "created_count=" in info[-1]
    assert "search_base_probability" not in " ".join(
        record.getMessage() for record in caplog.records
    )


def test_search_failure_with_rain_and_one_held_item_generalizes() -> None:
    item = ObservedItem(
        entity_id=EntityId("item-1"),
        name="stick",
        kind=ItemKind.MATERIAL,
        load=ItemLoad(1),
        placement=ObservedItemPlacement.HELD_BY_SELF,
    )
    observation = _observation(
        tick=2,
        phase=None,
        weather=WeatherCondition.RAIN,
        occurrences=(
            _occurrence("search", tick=2, success=False, event="event-search-1"),
        ),
        items=(item,),
    )
    episodes = episodes_from_observation(observation, _OWNER, empty_world_model(_OWNER))
    support = next(item for item in episodes if item.role is CausalEpisodeRole.SUPPORT)
    slots = {atom.slot for atom in support.atoms}
    assert CausalSlot.WEATHER in slots
    assert CausalSlot.ACTION in slots
    assert CausalSlot.HELD_ITEM_KIND in slots
    assert CausalSlot.LOCATION in slots
    model = update_world_model(
        empty_world_model(_OWNER),
        episodes,
        WorldModelPolicy(),
        tick=2,
        observed_health=100.0,
    )
    conjunction = next(
        item
        for item in model.hypotheses
        if item.outcome is CausalOutcome.SEARCH_FAILURE
        and len(item.atoms) == len(support.atoms)
    )
    assert conjunction.support == 1.0
    parents = [
        item
        for item in model.hypotheses
        if item.outcome is CausalOutcome.SEARCH_FAILURE
        and len(item.atoms) == len(support.atoms) - 1
    ]
    assert parents
    assert all(item.support == 0.5 for item in parents)
    assert not any(
        len(item.atoms) == 1 and item.outcome is CausalOutcome.SEARCH_FAILURE
        for item in model.hypotheses
    )


def test_first_tick_skips_health_delta_and_emotion_scales_support() -> None:
    from agents.cognition.models import (
        AgentEmotionalState,
        EmotionIntensity,
        EmotionKind,
    )

    first = _observation(tick=1, health=40.0)
    episodes = episodes_from_observation(first, _OWNER, empty_world_model(_OWNER))
    assert all(episode.role is not CausalEpisodeRole.SUPPORT for episode in episodes)
    support = _support_episode(CausalOutcome.SEARCH_FAILURE, tick=2)
    emotion = AgentEmotionalState(
        owner_id=_OWNER,
        tick=2,
        intensities=(EmotionIntensity(kind=EmotionKind.FEAR, intensity=0.5),),
        last_update_tick=2,
        policy_version="emotion.v1",
    )
    model = update_world_model(
        empty_world_model(_OWNER),
        (support,),
        WorldModelPolicy(),
        tick=2,
        emotional_state=emotion,
    )
    full = next(item for item in model.hypotheses if len(item.atoms) == 2)
    assert full.support == 2.0
    assert full.confidence == confidence_from_masses(2.0, 0.0)


def test_hypothesis_cap_drops_lowest_confidence_then_oldest() -> None:
    policy = WorldModelPolicy(max_hypotheses=1)
    first = _support_episode(CausalOutcome.SEARCH_FAILURE, tick=1)
    second = CausalEpisode(
        owner_id=_OWNER,
        tick=2,
        outcome=CausalOutcome.DANGER,
        atoms=(_atom(CausalSlot.LOCATION, "loc-forest"),),
        evidence_id="harm-2",
        provenance_kind=CausalProvenanceKind.OBSERVATION,
    )
    model = update_world_model(empty_world_model(_OWNER), (first,), policy, tick=1)
    model = update_world_model(model, (second,), policy, tick=2)
    assert len(model.hypotheses) == 1
    assert model.hypotheses[0].outcome is CausalOutcome.DANGER


def test_source_does_not_name_engine_probabilities() -> None:
    text = (
        Path(__file__).resolve().parents[2] / "src/agents/cognition/world_model.py"
    ).read_text(encoding="utf-8")
    assert "search_base_probability" not in text
    assert "PhysicalRules" not in text
    assert "WorldState" not in text


def _matching(
    model: CausalWorldModel,
    outcome: CausalOutcome,
    slots: tuple[str, ...],
) -> CausalHypothesis | None:
    wanted = tuple(sorted(slots))
    for item in model.hypotheses:
        found = tuple(sorted(atom.slot.value for atom in item.atoms))
        if item.outcome is outcome and found == wanted:
            return item
    return None


def _support_episode(outcome: CausalOutcome, *, tick: int) -> CausalEpisode:
    return CausalEpisode(
        owner_id=_OWNER,
        tick=tick,
        outcome=outcome,
        atoms=(
            _atom(CausalSlot.WEATHER, "rain"),
            _atom(CausalSlot.ACTION, "search"),
        ),
        evidence_id=f"search-{tick}",
        provenance_kind=CausalProvenanceKind.OBSERVATION,
    )
