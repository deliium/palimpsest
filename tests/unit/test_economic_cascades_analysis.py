# mypy: ignore-errors
"""Bounded composition of the economic-cascade analysis value."""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

from analysis.economic_cascades_analysis import (
    economic_cascades_analysis_digest,
    empty_economic_cascades_analysis,
    harvest_economic_cascades_analysis,
)
from analysis.economic_cascades_contract import (
    CascadeCoverage,
    CascadeDisruptionKind,
    EconomicCascadesError,
)
from analysis.economic_cascades_policy import policy_with
from analysis.supply_chain_contract import NONE_TOKEN
from analysis.supply_chain_events import (
    SupplyRecipeSpec,
    SupplyStageObservation,
)
from world.effects import ActionCause
from world.events import (
    OccurrenceContext,
    ResourceHarvested,
    ResourceNodeDepleted,
    WorldEvent,
    target_id_for_details,
)
from world.identifiers import (
    EntityId,
    EventId,
    RecipeId,
    RequestId,
    WorldId,
    WorldRevision,
)

pytestmark = pytest.mark.unit

_WORLD = WorldId("world-cascades-analysis")


def _event(
    details,
    *,
    tick: int,
    sequence: int,
    event_id: str,
) -> WorldEvent:
    return WorldEvent(
        event_id=EventId(event_id),
        run_id="run-cascades",
        world_id=_WORLD,
        tick=tick,
        sequence=sequence,
        request_id=RequestId(f"req-{event_id}"),
        resulting_revision=WorldRevision(tick),
        schema_version=27,
        details=details,
        actor_id=EntityId("body-1"),
        target_id=target_id_for_details(details),
        cause=ActionCause(RequestId(f"req-{event_id}"), EntityId("body-1")),
        occurrence=OccurrenceContext(origin_location_id=EntityId("loc-1")),
    )


def _harvest_events(*, tick: int = 0, start: int = 0) -> tuple[WorldEvent, ...]:
    return (
        _event(
            ResourceHarvested(
                RecipeId("harvest_ore"),
                EntityId("res-ore"),
                True,
                2,
                1.0,
                created_item_id=EntityId("item-ore"),
            ),
            tick=tick,
            sequence=start,
            event_id=f"evt-harvest-{tick}",
        ),
        _event(
            ResourceNodeDepleted(EntityId("res-ore"), 0.0),
            tick=tick,
            sequence=start + 1,
            event_id=f"evt-depleted-{tick}",
        ),
    )


def _recipes() -> tuple[SupplyRecipeSpec, ...]:
    return (
        SupplyRecipeSpec(
            recipe_id="harvest_ore",
            action="harvest",
            resource_input_names=("ore",),
            item_input_names=(),
            input_kinds=(),
            output_name="ore",
            output_kind="material",
        ),
        SupplyRecipeSpec(
            recipe_id="smelt_ore",
            action="craft",
            resource_input_names=(),
            item_input_names=("ore",),
            input_kinds=(),
            output_name="metal",
            output_kind="material",
        ),
    )


def _stage(
    window: int = 0, *, completions: int = 1, sequence: int = 0
) -> SupplyStageObservation:
    return SupplyStageObservation(
        tick=window * 32,
        sequence=sequence,
        window_index=window,
        recipe_id="smelt_ore",
        action="craft",
        location_token="loc-1",
        actor_token="body-1",
        item_names=("ore",),
        completed=completions > 0,
        attempt=True,
        started_success=True,
        duration_ticks=2,
        created_item_token=NONE_TOKEN,
        cause="craft",
    )


def test_empty_evidence_is_an_empty_missing_analysis() -> None:
    analysis = harvest_economic_cascades_analysis(events=[], recipe_specs=())
    assert analysis.coverage is CascadeCoverage.MISSING
    assert analysis.disruptions == ()
    assert analysis.chains == ()
    assert analysis.row_count == 0
    assert analysis.coverage_row.coverage is CascadeCoverage.MISSING


def test_one_episode_and_one_linked_chain_are_composed() -> None:
    analysis = harvest_economic_cascades_analysis(
        events=_harvest_events(),
        recipe_specs=_recipes(),
        stages=[_stage(completions=1), _stage(completions=0, sequence=1)],
    )
    assert analysis.disruption_count == 1
    assert analysis.disruptions[0].kind is CascadeDisruptionKind.RESOURCE_LOSS
    assert analysis.stage_count == 1
    assert analysis.dependency_edge_count >= 1
    assert analysis.chain_count == 1
    assert analysis.linked_chain_count == 1
    assert analysis.max_depth == 1
    assert analysis.coverage is CascadeCoverage.COMPLETE
    assert analysis.labor_join_count >= 1


def test_digest_is_stable() -> None:
    analysis = harvest_economic_cascades_analysis(
        events=_harvest_events(),
        recipe_specs=_recipes(),
        stages=[_stage()],
    )
    assert economic_cascades_analysis_digest(analysis) == (
        economic_cascades_analysis_digest(analysis)
    )
    assert economic_cascades_analysis_digest(
        empty_economic_cascades_analysis()
    ) != economic_cascades_analysis_digest(analysis)


def test_digest_matches_across_hash_seeds() -> None:
    script = (
        "from analysis.economic_cascades_analysis import "
        "empty_economic_cascades_analysis, economic_cascades_analysis_digest; "
        "print(economic_cascades_analysis_digest("
        "empty_economic_cascades_analysis()))"
    )
    digests = []
    for seed in ("0", "1"):
        env = dict(os.environ, PYTHONHASHSEED=seed)
        completed = subprocess.run(
            [sys.executable, "-c", script],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
        digests.append(completed.stdout.strip())
    assert digests[0] == digests[1]


def test_window_end_drops_later_events() -> None:
    events = (*_harvest_events(tick=0), *_harvest_events(tick=40, start=2))
    analysis = harvest_economic_cascades_analysis(
        events=events,
        recipe_specs=_recipes(),
        stages=[],
        window_end=10,
    )
    assert analysis.event_count == 2
    assert analysis.disruption_count == 1


def test_partial_coverage_is_reported_by_notice() -> None:
    analysis = harvest_economic_cascades_analysis(
        events=_harvest_events(),
        recipe_specs=_recipes(),
        stages=[],
        policy=policy_with(max_notices=1),
    )
    assert len(analysis.notices) <= 1
    assert analysis.coverage is CascadeCoverage.PARTIAL


def test_invalid_policy_is_rejected() -> None:
    with pytest.raises(EconomicCascadesError):
        harvest_economic_cascades_analysis(
            events=_harvest_events(),
            recipe_specs=_recipes(),
            stages=[],
            policy=object(),  # type: ignore[arg-type]
        )
