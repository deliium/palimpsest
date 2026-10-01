"""Season successors learned from the current observation only."""

from __future__ import annotations

import ast
import inspect
import logging
from pathlib import Path

import pytest

from agents.cognition.models import ActionDirection
from agents.cognition.world_model import (
    CausalOutcome,
    CausalSlot,
    CausalWorldModel,
    SeasonSuccessorTable,
    apply_recorded_season_successor,
    contemplated_situation_atoms,
    default_world_model_policy,
    empty_world_model,
    episodes_from_observation,
    match_hypothesis,
    update_world_model,
)
from agents.models import AgentId
from world.environment import HazardKind, Season, TemperatureBand
from world.identifiers import EntityId, EventId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import (
    Observation,
    ObservationAudienceRole,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedOccurrence,
    ObservedSelf,
)
from world.values import (
    CarryCapacity,
    DayPhase,
    Fatigue,
    Health,
    Hunger,
    TemperatureCelsius,
    Thirst,
    WeatherCondition,
)


def test_new_slots_follow_concept() -> None:
    slots = list(CausalSlot)
    assert slots[slots.index(CausalSlot.CONCEPT) + 1 :] == [
        CausalSlot.SEASON,
        CausalSlot.TEMPERATURE_BAND,
        CausalSlot.HAZARD,
    ]


def test_updater_rejects_world_authority_types() -> None:
    class EnvironmentalDynamicsSpec:
        pass

    class WorldState:
        pass

    with pytest.raises(TypeError):
        episodes_from_observation(
            EnvironmentalDynamicsSpec(),  # type: ignore[arg-type]
            AgentId("agent-1"),
            None,
        )
    with pytest.raises(TypeError):
        episodes_from_observation(
            WorldState(),  # type: ignore[arg-type]
            AgentId("agent-1"),
            None,
        )
    for function in (update_world_model, episodes_from_observation):
        names = set(inspect.signature(function).parameters)
        assert "environmental_dynamics" not in names
        assert "world_state" not in names


def test_missing_season_adds_no_environment_atoms() -> None:
    episodes = episodes_from_observation(_observation(tick=1), AgentId("agent-1"))
    assert all(
        atom.slot
        not in {CausalSlot.SEASON, CausalSlot.TEMPERATURE_BAND, CausalSlot.HAZARD}
        for episode in episodes
        for atom in episode.atoms
    )


def test_learned_winter_search_is_more_costly_than_naive_autumn(
    caplog: pytest.LogCaptureFixture,
) -> None:
    owner = AgentId("agent-1")
    policy = default_world_model_policy()
    winter = _observation(
        tick=1,
        season=Season.WINTER,
        search_failed=True,
    )
    autumn = _observation(tick=2, season=Season.AUTUMN)
    with caplog.at_level(logging.DEBUG, logger="agents.cognition.world_model"):
        learned = empty_world_model(owner)
        learned = update_world_model(
            learned,
            episodes_from_observation(winter, owner, learned),
            policy,
            tick=1,
            observed_health=100.0,
        )
        learned = update_world_model(
            learned,
            episodes_from_observation(autumn, owner, learned),
            policy,
            tick=2,
            observed_health=100.0,
        )
    assert learned.season_successors.previous_season == "autumn"
    assert ("winter", "autumn", 1) in learned.season_successors.transitions
    assert any(
        record.message
        == "season_successor_updated owner_id=agent-1 season=autumn successor_count=1"
        for record in caplog.records
    )

    atoms = contemplated_situation_atoms(
        autumn, direction=ActionDirection.SEARCH, target_entity_id=None
    )
    biased = apply_recorded_season_successor(
        atoms,
        learned.season_successors,
        owner_id=owner,
    )
    season_values = [
        atom.value for atom in biased if atom.slot is CausalSlot.SEASON
    ]
    assert season_values == ["autumn"]
    learned_score = _search_failure_score(learned, biased)
    naive_score = _search_failure_score(empty_world_model(owner), atoms)
    assert learned_score < naive_score


def test_ambiguous_successor_keeps_the_current_season(
    caplog: pytest.LogCaptureFixture,
) -> None:
    table = SeasonSuccessorTable(
        previous_season="autumn",
        transitions=(("autumn", "winter", 1), ("autumn", "spring", 1)),
    )
    atoms = contemplated_situation_atoms(
        _observation(tick=3, season=Season.AUTUMN),
        direction=ActionDirection.SEARCH,
        target_entity_id=None,
    )
    with caplog.at_level(logging.INFO, logger="agents.cognition.world_model"):
        resolved = apply_recorded_season_successor(
            atoms,
            table,
            owner_id=AgentId("agent-1"),
        )
    assert tuple(atom.value for atom in resolved if atom.slot is CausalSlot.SEASON) == (
        "autumn",
    )
    assert any(
        record.message == "season_successor_unused reason_code=successor_ambiguous"
        for record in caplog.records
    )


def test_cognition_modules_do_not_import_the_spec() -> None:
    roots = (
        "src/agents/cognition/world_model.py",
        "src/agents/cognition/prospective.py",
        "src/agents/cognition/deliberation.py",
    )
    for path in roots:
        source = Path(path).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = [
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
        ]
        rendered = "\n".join(
            ast.get_source_segment(source, node) or "" for node in imports
        )
        assert "world.environment" not in rendered
        assert "llm.models" not in rendered


def _search_failure_score(
    model: CausalWorldModel,
    atoms: tuple,
) -> float:
    match = match_hypothesis(
        model, outcome=CausalOutcome.SEARCH_FAILURE, atoms=atoms
    )
    if match is None:
        return 0.0
    return -match.confidence


def _observation(
    *,
    tick: int,
    season: Season | None = None,
    search_failed: bool = False,
) -> Observation:
    occurrences: tuple[ObservedOccurrence, ...] = ()
    if search_failed:
        occurrences = (
            ObservedOccurrence(
                provenance=ObservationProvenance(
                    source_kind=ObservationSourceKind.OCCURRENCE,
                    source_tick=0,
                    source_event_id=EventId("event-search-1"),
                ),
                kind="search",
                audience_role=ObservationAudienceRole.ACTOR,
                actor_id=EntityId("body-1"),
                success=False,
            ),
            )
    return Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("body-1"),
        revision=WorldRevision(tick),
        tick=tick,
        self_body=ObservedSelf(
            entity_id=EntityId("body-1"),
            location_id=EntityId("loc-1"),
            health=Health(100.0),
            hunger=Hunger(0.0),
            thirst=Thirst(0.0),
            fatigue=Fatigue(0.0),
            temperature=TemperatureCelsius(36.5),
            inventory=(),
            life_status=LifeStatus.ALIVE,
            carry_capacity=CarryCapacity(10),
        ),
        day_phase=DayPhase.NIGHT,
        weather_condition=WeatherCondition.STORM,
        season=season,
        temperature_band=None if season is None else TemperatureBand.COLD,
        hazard_kinds=None if season is None else (HazardKind.COLD_SNAP,),
        occurrences=occurrences,
    )
