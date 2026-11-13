# mypy: ignore-errors
"""Completed-run economic-inequality bridge tests."""

from __future__ import annotations

from types import SimpleNamespace

from experiments.economic_inequality_completed_run import (
    build_completed_run_economic_inequality_analysis,
    economic_inequality_recipe_mappings,
)
from world.effects import ActionCause
from world.events import (
    ItemCrafted,
    OccurrenceContext,
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
from world.production import example_production_catalog

_WORLD = WorldId("world-economic-inequality-completed")


def _crafted(index: int, owner: str, recipe: str, tick: int) -> WorldEvent:
    details = ItemCrafted(
        recipe_id=RecipeId(recipe),
        created_item_id=EntityId(f"item-{index}"),
        resulting_holder_id=EntityId(owner),
        duration_ticks=1,
    )
    return WorldEvent(
        event_id=EventId(f"evt-{index}"),
        run_id="run-completed",
        world_id=_WORLD,
        tick=tick,
        sequence=index,
        request_id=RequestId(f"req-{index}"),
        resulting_revision=WorldRevision(tick),
        schema_version=6,
        details=details,
        actor_id=EntityId(owner),
        target_id=target_id_for_details(details),
        cause=ActionCause(RequestId(f"req-{index}"), EntityId(owner)),
        occurrence=OccurrenceContext(origin_location_id=EntityId("loc-a")),
    )


def _config(catalog):
    return SimpleNamespace(
        agents=[SimpleNamespace(cognition=SimpleNamespace(production_catalog=catalog))],
    )


def test_recipe_mappings_come_from_the_shared_catalog() -> None:
    output_kinds, structure_kinds = economic_inequality_recipe_mappings(
        _config(example_production_catalog())
    )
    assert output_kinds["craft_tool"] == "tool"
    assert output_kinds["harvest_wood"] == "material"
    assert "build_shelter" in structure_kinds


def test_empty_catalog_yields_no_mapping() -> None:
    from world.production import ProductionCatalog

    output_kinds, structure_kinds = economic_inequality_recipe_mappings(
        _config(ProductionCatalog())
    )
    assert output_kinds == {}
    assert structure_kinds == {}


def test_completed_run_analysis_is_token_only_and_bounded() -> None:
    events = tuple(
        _crafted(index, owner, "craft_tool", index)
        for index, owner in enumerate(("body-1", "body-2", "body-3", "body-4"))
    )
    analysis = build_completed_run_economic_inequality_analysis(
        object(),
        runner_config=_config(example_production_catalog()),
        committed_events=events,
        run_id="run-completed",
        window_end=31,
    )
    assert analysis.owner_count == 4
    assert analysis.dimension_rows
    assert all("body-" not in str(row) for row in analysis.dimension_rows)
    assert all(row.cohort_token.startswith("eic-") for row in analysis.cohort_rows)


def test_macro_society_membership_is_applied_to_recorded_windows() -> None:
    events = tuple(
        _crafted(index, owner, "craft_tool", index)
        for index, owner in enumerate(("body-1", "body-2", "body-3", "body-4"))
    )
    macro = SimpleNamespace(
        records=(
            SimpleNamespace(
                macro_society_id="msoc-0123456789abcdef",
                member_ids=("body-1", "body-2", "body-3", "body-4"),
                window_indexes=(0,),
            ),
        )
    )
    analysis = build_completed_run_economic_inequality_analysis(
        object(),
        runner_config=_config(example_production_catalog()),
        committed_events=events,
        run_id="run-completed",
        macro_society_analysis=macro,
        window_end=31,
    )
    assert len(analysis.society_rows) == 1
    assert analysis.society_rows[0].owner_count == 4
    assert analysis.society_rows[0].society_token.startswith("eis-")


def test_generation_membership_defaults_bootstrap_owners_to_zero() -> None:
    events = tuple(
        _crafted(index, owner, "craft_tool", index)
        for index, owner in enumerate(("body-1", "body-2", "body-3", "body-4"))
    )
    analysis = build_completed_run_economic_inequality_analysis(
        object(),
        runner_config=_config(example_production_catalog()),
        committed_events=events,
        run_id="run-completed",
        window_end=31,
    )
    assert analysis.cohort_rows
    assert {row.generation_index for row in analysis.cohort_rows} == {0}
    assert analysis.cohort_rows[0].cohort_token.startswith("eic-")


def test_invalid_run_id_is_rejected() -> None:
    import pytest

    with pytest.raises(ValueError, match="invalid_input"):
        build_completed_run_economic_inequality_analysis(
            object(),
            runner_config=_config(example_production_catalog()),
            committed_events=(),
            run_id="",
        )
