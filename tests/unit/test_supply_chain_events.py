# mypy: ignore-errors

"""Supply-chain evidence extraction from committed events only."""

from __future__ import annotations

import dataclasses

import pytest

from analysis.supply_chain_contract import NONE_TOKEN, SupplyCoverage
from analysis.supply_chain_events import (
    SupplyInfrastructureFact,
    SupplyOrganizationClaim,
    SupplyRecipeSpec,
    SupplySkillLevel,
    SupplyStageObservation,
    supply_evidence_from_events,
)
from analysis.supply_chain_policy import (
    SupplyChainAnalysisPolicy,
    default_supply_chain_analysis_policy,
)
from world.effects import ActionCause
from world.events import (
    CraftStarted,
    EventDetails,
    Given,
    ItemCrafted,
    ItemStored,
    OccurrenceContext,
    ResourceHarvested,
    StructureBuilt,
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

_WORLD = WorldId("world-supply-events")
_HARVEST = SupplyRecipeSpec(
    recipe_id="harvest_grain",
    action="harvest",
    resource_input_names=("grain",),
    item_input_names=(),
    input_kinds=(),
    output_name="grain",
    output_kind="food",
)
_MILL = SupplyRecipeSpec(
    recipe_id="mill_grain",
    action="craft",
    resource_input_names=(),
    item_input_names=("grain",),
    input_kinds=(),
    output_name="flour",
    output_kind="material",
    skill_domain="crafting",
)
_BREAD = SupplyRecipeSpec(
    recipe_id="bake_bread",
    action="craft",
    resource_input_names=(),
    item_input_names=("flour",),
    input_kinds=(),
    output_name="bread",
    output_kind="food",
    skill_domain="crafting",
)
_BUILD = SupplyRecipeSpec(
    recipe_id="build_shelter",
    action="build",
    resource_input_names=(),
    item_input_names=(),
    input_kinds=("material",),
    output_name="shelter",
    output_kind="structure",
)
_STORE = SupplyRecipeSpec(
    recipe_id="store_food",
    action="store",
    resource_input_names=(),
    item_input_names=(),
    input_kinds=("food",),
    output_name="store",
    output_kind="storage",
)
_RECIPES = (_HARVEST, _MILL, _BREAD, _BUILD, _STORE)


def _event(
    details: EventDetails,
    *,
    tick: int = 0,
    sequence: int = 0,
    event_id: str = "evt-1",
    actor: str | None = "body-1",
    occurrence: OccurrenceContext | None = None,
) -> WorldEvent:
    return WorldEvent(
        event_id=EventId(event_id),
        run_id="run-supply",
        world_id=_WORLD,
        tick=tick,
        sequence=sequence,
        request_id=RequestId(f"req-{event_id}"),
        resulting_revision=WorldRevision(tick),
        schema_version=6,
        details=details,
        actor_id=None if actor is None else EntityId(actor),
        target_id=target_id_for_details(details),
        cause=ActionCause(RequestId(f"req-{event_id}"), EntityId(actor or "body-1")),
        occurrence=occurrence,
    )


def _location(location: str = "loc-1") -> OccurrenceContext:
    return OccurrenceContext(origin_location_id=EntityId(location))


def _harvest(
    *,
    success: bool,
    created: str | None = "item-grain",
    tick: int = 0,
    sequence: int = 0,
    event_id: str = "evt-harvest",
) -> WorldEvent:
    return _event(
        ResourceHarvested(
            RecipeId("harvest_grain"),
            EntityId("res-grain"),
            success,
            2,
            2.0,
            created_item_id=None if created is None else EntityId(created),
        ),
        tick=tick,
        sequence=sequence,
        event_id=event_id,
        occurrence=_location(),
    )


def _craft_start(
    *,
    consumed: tuple[str, ...],
    success: bool = True,
    tick: int = 0,
    sequence: int = 0,
    event_id: str = "evt-start",
    actor: str = "body-1",
) -> WorldEvent:
    return _event(
        CraftStarted(
            RecipeId("mill_grain"),
            success,
            2,
            consumed_item_ids=tuple(EntityId(value) for value in consumed),
        ),
        tick=tick,
        sequence=sequence,
        event_id=event_id,
        actor=actor,
        occurrence=_location(),
    )


def _craft_done(
    *,
    created: str = "item-flour",
    tick: int = 1,
    sequence: int = 0,
    event_id: str = "evt-done",
    holder: str = "body-1",
    actor: str = "body-1",
) -> WorldEvent:
    return _event(
        ItemCrafted(RecipeId("mill_grain"), EntityId(created), EntityId(holder), 2),
        tick=tick,
        sequence=sequence,
        event_id=event_id,
        actor=actor,
        occurrence=_location(),
    )


def test_requires_sequence() -> None:
    from analysis.supply_chain_contract import SupplyChainError

    with pytest.raises(SupplyChainError):
        supply_evidence_from_events(
            "not-events",  # type: ignore[arg-type]
            policy=default_supply_chain_analysis_policy(),
            recipes=_RECIPES,
        )
    with pytest.raises(SupplyChainError):
        supply_evidence_from_events(
            {"not": "sequence"},  # type: ignore[arg-type]
            policy=default_supply_chain_analysis_policy(),
            recipes=_RECIPES,
        )


def test_sorts_by_tick_and_sequence() -> None:
    late = _harvest(success=True, tick=2, sequence=1, event_id="evt-late")
    early = _harvest(
        success=False, created=None, tick=0, sequence=1, event_id="evt-early"
    )
    evidence = supply_evidence_from_events(
        (late, early),
        policy=default_supply_chain_analysis_policy(),
        recipes=_RECIPES,
    )
    assert [row.tick for row in evidence.rows] == [0, 2]


def test_rejects_duplicate_event_id() -> None:
    from analysis.supply_chain_contract import SupplyChainError

    event = _harvest(success=False, created=None, event_id="evt-dup")
    with pytest.raises(SupplyChainError) as excinfo:
        supply_evidence_from_events(
            (event, event),
            policy=default_supply_chain_analysis_policy(),
            recipes=_RECIPES,
        )
    assert excinfo.value.reason_code == "supply_chain_duplicate_event"


def test_harvest_failure_is_attempt_only() -> None:
    evidence = supply_evidence_from_events(
        (_harvest(success=False, created=None),),
        policy=default_supply_chain_analysis_policy(),
        recipes=_RECIPES,
    )
    row = evidence.rows[0]
    assert row.completed is False
    assert row.attempt is True
    assert row.cause == "harvest"


def test_harvest_success_is_completed() -> None:
    evidence = supply_evidence_from_events(
        (_harvest(success=True),),
        policy=default_supply_chain_analysis_policy(),
        recipes=_RECIPES,
    )
    row = evidence.rows[0]
    assert row.completed is True
    assert row.created_item_token == "item-grain"
    assert row.duration_ticks == 2


def test_craft_start_completion_pairing() -> None:
    evidence = supply_evidence_from_events(
        (
            _harvest(success=True, tick=0, event_id="evt-harvest"),
            _craft_start(consumed=("item-grain",), tick=0),
            _craft_done(tick=1),
        ),
        policy=default_supply_chain_analysis_policy(),
        recipes=_RECIPES,
    )
    completed = [
        row for row in evidence.rows if row.recipe_id == "mill_grain" and row.completed
    ]
    assert len(completed) == 1
    assert completed[0].item_names == ("grain",)
    attempts = [
        row for row in evidence.rows if row.recipe_id == "mill_grain" and row.attempt
    ]
    assert len(attempts) == 1
    assert attempts[0].completed is False


def test_one_tick_craft_sets_unresolved_inputs() -> None:
    evidence = supply_evidence_from_events(
        (_craft_done(tick=0),),
        policy=default_supply_chain_analysis_policy(),
        recipes=_RECIPES,
    )
    row = evidence.rows[0]
    assert row.completed is True
    assert row.item_names == ()
    assert "unresolved_craft_inputs" in evidence.notices


def test_failed_start_has_no_completion() -> None:
    evidence = supply_evidence_from_events(
        (_craft_start(consumed=(), success=False),),
        policy=default_supply_chain_analysis_policy(),
        recipes=_RECIPES,
    )
    assert len(evidence.rows) == 1
    assert evidence.rows[0].completed is False
    assert evidence.rows[0].started_success is False


def test_completion_actor_uses_resulting_holder() -> None:
    evidence = supply_evidence_from_events(
        (_craft_done(tick=0, holder="body-2", actor="body-1"),),
        policy=default_supply_chain_analysis_policy(),
        recipes=_RECIPES,
    )
    assert evidence.rows[0].actor_token == "body-2"


def test_missing_occurrence_sets_notice() -> None:
    event = WorldEvent(
        event_id=EventId("evt-no-location"),
        run_id="run-supply",
        world_id=_WORLD,
        tick=0,
        sequence=0,
        request_id=RequestId("req-no-location"),
        resulting_revision=WorldRevision(0),
        schema_version=6,
        details=ResourceHarvested(
            RecipeId("harvest_grain"),
            EntityId("res-grain"),
            False,
            2,
            2.0,
        ),
        actor_id=EntityId("body-1"),
        target_id=target_id_for_details(
            ResourceHarvested(
                RecipeId("harvest_grain"),
                EntityId("res-grain"),
                False,
                2,
                2.0,
            )
        ),
        cause=ActionCause(RequestId("req-no-location"), EntityId("body-1")),
        occurrence=OccurrenceContext(destination_location_id=EntityId("loc-2")),
    )
    evidence = supply_evidence_from_events(
        (event,),
        policy=default_supply_chain_analysis_policy(),
        recipes=_RECIPES,
    )
    assert evidence.rows[0].location_token == NONE_TOKEN
    assert "unresolved_location" in evidence.notices


def test_consumed_ids_resolve_to_input_names() -> None:
    evidence = supply_evidence_from_events(
        (
            _harvest(success=True, tick=0, event_id="evt-harvest"),
            _craft_start(consumed=("item-grain",), tick=0),
            _craft_done(tick=1),
        ),
        policy=default_supply_chain_analysis_policy(),
        recipes=_RECIPES,
    )
    completed = next(
        row for row in evidence.rows if row.completed and row.cause == "craft"
    )
    assert completed.item_names == ("grain",)


def test_structure_and_storage_rows() -> None:
    built = _event(
        StructureBuilt(
            RecipeId("build_shelter"),
            EntityId("structure-1"),
            EntityId("loc-1"),
            0.75,
            1,
            EntityId("item-wood"),
        ),
        tick=0,
        event_id="evt-build",
        occurrence=_location(),
    )
    stored = _event(
        ItemStored(
            RecipeId("store_food"),
            EntityId("structure-2"),
            1,
            1,
            EntityId("item-food"),
        ),
        tick=1,
        event_id="evt-store",
        occurrence=_location(),
    )
    evidence = supply_evidence_from_events(
        (built, stored),
        policy=default_supply_chain_analysis_policy(),
        recipes=_RECIPES,
    )
    assert {row.cause for row in evidence.rows} == {"structure", "storage"}
    assert all(row.completed for row in evidence.rows)


def test_missing_optional_inputs_set_missing_coverage() -> None:
    evidence = supply_evidence_from_events(
        (_harvest(success=True),),
        policy=default_supply_chain_analysis_policy(),
        recipes=_RECIPES,
    )
    assert evidence.skill_coverage is SupplyCoverage.MISSING
    assert evidence.infrastructure_coverage is SupplyCoverage.MISSING
    assert evidence.organization_coverage is SupplyCoverage.MISSING
    assert evidence.coverage is SupplyCoverage.PARTIAL


def test_operational_infrastructure_only() -> None:
    class Fact:
        def __init__(self, status: str) -> None:
            self.location_token = "loc-1"
            self.kinds = ("well",)
            self.status = status

    evidence = supply_evidence_from_events(
        (_harvest(success=True),),
        policy=default_supply_chain_analysis_policy(),
        recipes=_RECIPES,
        infrastructure=(Fact("retired"), Fact("operational")),
    )
    assert evidence.infrastructure == (SupplyInfrastructureFact("loc-1", ("well",)),)


def test_organization_claim_shape_has_no_recipe_or_location() -> None:
    claim = SupplyOrganizationClaim(
        organization_token="org-1",
        command_kinds=("craft",),
        actor_tokens=("body-1",),
        first_tick=0,
        last_tick=1,
        claim_count=2,
    )
    fields = {field.name for field in dataclasses.fields(claim)}
    assert "recipe_id" not in fields
    assert "location_token" not in fields


def test_truncation_sets_partial() -> None:
    events = tuple(
        _harvest(
            success=False,
            created=None,
            event_id=f"evt-{index}",
            tick=index,
            sequence=0,
        )
        for index in range(3)
    )
    evidence = supply_evidence_from_events(
        events,
        policy=SupplyChainAnalysisPolicy(max_evidence_rows=1),
        recipes=_RECIPES,
    )
    assert len(evidence.rows) == 1
    assert "evidence_truncated" in evidence.notices
    assert evidence.coverage is SupplyCoverage.PARTIAL


def test_no_rows_is_missing() -> None:
    evidence = supply_evidence_from_events(
        (
            _event(
                Given(
                    EntityId("body-2"),
                    EntityId("item-grain"),
                    resulting_holder_id=EntityId("body-2"),
                ),
                occurrence=_location(),
            ),
        ),
        policy=default_supply_chain_analysis_policy(),
        recipes=_RECIPES,
    )
    assert evidence.coverage is SupplyCoverage.MISSING
    assert evidence.rows == ()


def test_rows_are_frozen() -> None:
    evidence = supply_evidence_from_events(
        (_harvest(success=True),),
        policy=default_supply_chain_analysis_policy(),
        recipes=_RECIPES,
    )
    row = evidence.rows[0]
    assert isinstance(row, SupplyStageObservation)
    with pytest.raises(dataclasses.FrozenInstanceError):
        row.completed = False  # type: ignore[misc]


def test_objective_skill_rows_are_accepted() -> None:
    class Side:
        value = "objective"

    class Skill:
        side = Side()
        agent_id = EntityId("body-1")
        domain = "crafting"
        level = 0.5

    evidence = supply_evidence_from_events(
        (_harvest(success=True),),
        policy=default_supply_chain_analysis_policy(),
        recipes=_RECIPES,
        skill_levels=(Skill(),),
    )
    assert evidence.skill_levels == (SupplySkillLevel("body-1", "crafting", 0.5),)
    assert evidence.skill_coverage is SupplyCoverage.COMPLETE
