"""Private objective disease rows. Engine/bootstrap only.

Agents never import this module. Absence of a living-body row means susceptible
when the channel is on; the channel itself is ``None`` while disabled.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from world.identifiers import EntityId
from world.models import AgentBody, LifeStatus, copy_body
from world.values import Health

if TYPE_CHECKING:
    from world._state import WorldState
    from world.events import DiseaseStateChanged

__all__ = [
    "DiseaseConditionRow",
    "DiseaseInvariantError",
    "DiseasePassResult",
    "DiseasePhase",
    "advance_disease_pass",
    "bootstrap_disease_rows",
    "disease_net_transitions",
    "disease_row_from_view",
    "disease_row_view",
    "index_disease_state",
    "project_disease_state_changed",
    "reconcile_disease_rows_for_dead_bodies",
    "validate_disease_boundary",
]

_LOG: Final[logging.Logger] = logging.getLogger("world.disease")


class DiseaseInvariantError(ValueError):
    """Malformed private disease state with a stable safe code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class DiseasePhase(StrEnum):
    LATENT = "latent"
    ACTIVE = "active"
    IMMUNE = "immune"


@dataclass(frozen=True, slots=True)
class DiseaseConditionRow:
    """One entity's private condition row for the enabled disease channel."""

    phase: DiseasePhase
    due_tick: int | None = None
    symptomatic: bool | None = None

    def __post_init__(self) -> None:
        if type(self.phase) is not DiseasePhase:
            raise TypeError("DiseaseConditionRow.phase must be DiseasePhase")
        if self.phase is DiseasePhase.IMMUNE:
            if self.due_tick is not None or self.symptomatic is not None:
                _LOG.error(
                    "disease_row_invalid reason_code=disease_immune_shape"
                )
                raise DiseaseInvariantError("disease_immune_shape")
            return
        if type(self.due_tick) is not int or isinstance(self.due_tick, bool):
            _LOG.error("disease_row_invalid reason_code=disease_due_tick_invalid")
            raise DiseaseInvariantError("disease_due_tick_invalid")
        if self.due_tick < 0:
            _LOG.error("disease_row_invalid reason_code=disease_due_tick_invalid")
            raise DiseaseInvariantError("disease_due_tick_invalid")
        if self.phase is DiseasePhase.LATENT:
            if self.symptomatic is not None:
                _LOG.error(
                    "disease_row_invalid reason_code=disease_latent_symptom"
                )
                raise DiseaseInvariantError("disease_latent_symptom")
            return
        if type(self.symptomatic) is not bool:
            _LOG.error(
                "disease_row_invalid reason_code=disease_active_symptom_invalid"
            )
            raise DiseaseInvariantError("disease_active_symptom_invalid")


def index_disease_state(
    value: Mapping[EntityId, DiseaseConditionRow]
    | Sequence[tuple[EntityId, DiseaseConditionRow]]
    | None,
    *,
    body_index: Mapping[EntityId, AgentBody],
    require_living: bool,
) -> MappingProxyType[EntityId, DiseaseConditionRow] | None:
    """Index disease rows. ``None`` keeps the channel off."""
    if value is None:
        _LOG.debug("disease_channel_off")
        return None
    if isinstance(value, Mapping):
        items = tuple(value.items())
    elif isinstance(value, (tuple, list)):
        items = tuple(value)
    else:
        _LOG.error("disease_state_invalid reason_code=disease_state_type")
        raise DiseaseInvariantError("disease_state_type")
    indexed: dict[EntityId, DiseaseConditionRow] = {}
    for entry in items:
        if not isinstance(entry, tuple) or len(entry) != 2:
            _LOG.error("disease_state_invalid reason_code=disease_row_pair")
            raise DiseaseInvariantError("disease_row_pair")
        entity_id, row = entry
        if type(entity_id) is not EntityId:
            _LOG.error("disease_state_invalid reason_code=disease_entity_type")
            raise DiseaseInvariantError("disease_entity_type")
        if type(row) is not DiseaseConditionRow:
            _LOG.error("disease_state_invalid reason_code=disease_row_type")
            raise DiseaseInvariantError("disease_row_type")
        if entity_id in indexed:
            _LOG.error("disease_state_invalid reason_code=disease_duplicate_entity")
            raise DiseaseInvariantError("disease_duplicate_entity")
        body = body_index.get(entity_id)
        if body is None:
            _LOG.error("disease_state_invalid reason_code=disease_unknown_entity")
            raise DiseaseInvariantError("disease_unknown_entity")
        if require_living and body.life_status is not LifeStatus.ALIVE:
            _LOG.error("disease_state_invalid reason_code=disease_dead_entity")
            raise DiseaseInvariantError("disease_dead_entity")
        indexed[entity_id] = row
    ordered = MappingProxyType(
        {
            entity_id: indexed[entity_id]
            for entity_id in sorted(indexed, key=lambda item: item.value)
        }
    )
    _LOG.info(
        "disease_channel_on row_count=%s require_living=%s",
        len(ordered),
        require_living,
    )
    return ordered


def bootstrap_disease_rows(
    *,
    founder_ids: Sequence[EntityId],
    latent_ticks: int,
    tick0: int,
    body_index: Mapping[EntityId, AgentBody],
) -> MappingProxyType[EntityId, DiseaseConditionRow]:
    """Create founder latent rows for an enabled channel (empty founders OK)."""
    if type(tick0) is not int or isinstance(tick0, bool) or tick0 < 0:
        raise DiseaseInvariantError("disease_tick0_invalid")
    if type(latent_ticks) is not int or isinstance(latent_ticks, bool):
        raise DiseaseInvariantError("disease_latent_ticks_invalid")
    if latent_ticks < 1:
        raise DiseaseInvariantError("disease_latent_ticks_invalid")
    due_tick = tick0 + latent_ticks
    rows: list[tuple[EntityId, DiseaseConditionRow]] = []
    for entity_id in founder_ids:
        if type(entity_id) is not EntityId:
            raise DiseaseInvariantError("disease_entity_type")
        rows.append(
            (
                entity_id,
                DiseaseConditionRow(
                    phase=DiseasePhase.LATENT,
                    due_tick=due_tick,
                    symptomatic=None,
                ),
            )
        )
    indexed = index_disease_state(
        rows, body_index=body_index, require_living=True
    )
    assert indexed is not None
    _LOG.info(
        "disease_bootstrap_ready founder_count=%s due_tick=%s",
        len(indexed),
        due_tick,
    )
    return indexed


def validate_disease_boundary(
    disease_state: Mapping[EntityId, DiseaseConditionRow] | None,
    *,
    body_index: Mapping[EntityId, AgentBody],
    next_tick: int,
) -> None:
    """Boundary check: living keys and no overdue latent/active deadlines."""
    if disease_state is None:
        return
    if type(next_tick) is not int or isinstance(next_tick, bool) or next_tick < 0:
        raise DiseaseInvariantError("disease_next_tick_invalid")
    for entity_id, row in disease_state.items():
        body = body_index.get(entity_id)
        if body is None or body.life_status is not LifeStatus.ALIVE:
            _LOG.error(
                "disease_boundary_invalid reason_code=disease_dead_entity"
            )
            raise DiseaseInvariantError("disease_dead_entity")
        if row.phase is DiseasePhase.IMMUNE:
            continue
        assert row.due_tick is not None
        if row.due_tick < next_tick:
            _LOG.error(
                "disease_boundary_invalid reason_code=disease_due_overdue"
            )
            raise DiseaseInvariantError("disease_due_overdue")
    _LOG.debug(
        "disease_boundary_ok next_tick=%s row_count=%s",
        next_tick,
        len(disease_state),
    )


@dataclass(frozen=True, slots=True)
class DiseasePassResult:
    """Detached outcome of one disease candidate pass."""

    disease_state: MappingProxyType[EntityId, DiseaseConditionRow] | None
    bodies: MappingProxyType[EntityId, AgentBody]
    mortality_body_ids: tuple[EntityId, ...]
    start_rows: MappingProxyType[EntityId, DiseaseConditionRow] | None
    extra_latent_recipients: tuple[EntityId, ...] = ()


def _journey_participants(state: object) -> frozenset[EntityId]:
    journeys = getattr(state, "journeys", None)
    if journeys is None:
        return frozenset()
    occupied: set[EntityId] = set()
    for journey in journeys.values():
        occupied.update(journey.participant_body_ids)
    return frozenset(occupied)


def _eligible_settled_ids(
    *,
    start_state: object,
    working_state: object,
) -> tuple[EntityId, ...]:
    start_bodies: Mapping[EntityId, AgentBody] = start_state.bodies  # type: ignore[attr-defined]
    working_bodies: Mapping[EntityId, AgentBody] = working_state.bodies  # type: ignore[attr-defined]
    blocked = _journey_participants(start_state) | _journey_participants(working_state)
    eligible: list[EntityId] = []
    for entity_id in sorted(start_bodies, key=lambda item: item.value):
        start_body = start_bodies[entity_id]
        if start_body.life_status is not LifeStatus.ALIVE:
            continue
        if entity_id in blocked:
            continue
        working_body = working_bodies.get(entity_id)
        if working_body is None or working_body.life_status is not LifeStatus.ALIVE:
            continue
        if working_body.location_id != start_body.location_id:
            continue
        eligible.append(entity_id)
    return tuple(eligible)


def advance_disease_pass(
    *,
    tick: int,
    start_state: object,
    working_state: object,
    latent_ticks: int,
    active_ticks: int,
    immunity_after_recovery: bool,
    draw: Callable[[EntityId, str], bool],
    extra_opportunity: Callable[[EntityId, EntityId], bool] | None = None,
) -> DiseasePassResult:
    """Advance private disease rows for one tick from a frozen start view.

    Does not import simulation. ``draw(entity_id, kind)`` must already encode
    ``randrange(1000) < threshold`` for kind in exposure|transmission|symptom|
    terminal. Optional ``extra_opportunity(location_id, entity_id)`` may supply a
    second exposure chance only after ordinary exposure fails; transmission and
    all other gates remain unchanged.
    """
    start_disease = getattr(start_state, "disease_state", None)
    working_bodies: Mapping[EntityId, AgentBody] = working_state.bodies  # type: ignore[attr-defined]
    bodies = dict(working_bodies)
    if start_disease is None:
        if extra_opportunity is not None:
            raise DiseaseInvariantError("disease_extra_without_channel")
        _LOG.debug("disease_pass_skipped channel=off tick=%s", tick)
        return DiseasePassResult(
            disease_state=None,
            bodies=MappingProxyType(bodies),
            mortality_body_ids=(),
            start_rows=None,
            extra_latent_recipients=(),
        )
    if type(tick) is not int or isinstance(tick, bool) or tick < 0:
        raise DiseaseInvariantError("disease_tick_invalid")
    if (
        type(latent_ticks) is not int
        or isinstance(latent_ticks, bool)
        or latent_ticks < 1
    ):
        raise DiseaseInvariantError("disease_latent_ticks_invalid")
    if (
        type(active_ticks) is not int
        or isinstance(active_ticks, bool)
        or active_ticks < 1
    ):
        raise DiseaseInvariantError("disease_active_ticks_invalid")
    if type(immunity_after_recovery) is not bool:
        raise DiseaseInvariantError("disease_immunity_flag_invalid")
    if extra_opportunity is not None and not callable(extra_opportunity):
        raise TypeError("extra_opportunity must be callable or None")
    start_rows = MappingProxyType(dict(start_disease))
    evolving: dict[EntityId, DiseaseConditionRow] = dict(start_rows)
    eligible = _eligible_settled_ids(
        start_state=start_state, working_state=working_state
    )
    eligible_set = frozenset(eligible)
    start_bodies: Mapping[EntityId, AgentBody] = start_state.bodies  # type: ignore[attr-defined]

    by_location: dict[EntityId, list[EntityId]] = {}
    for entity_id in eligible:
        location_id = start_bodies[entity_id].location_id
        by_location.setdefault(location_id, []).append(entity_id)

    start_active_sources = {
        entity_id
        for entity_id, row in start_rows.items()
        if row.phase is DiseasePhase.ACTIVE and entity_id in eligible_set
    }

    # 1) Due latent → active (cannot transfer until the next pass).
    for entity_id in sorted(start_rows, key=lambda item: item.value):
        row = start_rows[entity_id]
        if row.phase is not DiseasePhase.LATENT:
            continue
        if row.due_tick != tick:
            continue
        if entity_id not in eligible_set:
            continue
        symptomatic = draw(entity_id, "symptom")
        evolving[entity_id] = DiseaseConditionRow(
            phase=DiseasePhase.ACTIVE,
            due_tick=tick + active_ticks,
            symptomatic=symptomatic,
        )

    # 2) Exposure / transmission for susceptibles (start-row absence only).
    extra_latent: list[EntityId] = []
    for location_id, members in sorted(
        by_location.items(), key=lambda item: item[0].value
    ):
        if not any(entity_id in start_active_sources for entity_id in members):
            continue
        for entity_id in members:
            if entity_id in start_rows:
                continue
            used_extra = False
            if not draw(entity_id, "exposure"):
                if extra_opportunity is None or not extra_opportunity(
                    location_id, entity_id
                ):
                    continue
                used_extra = True
            if not draw(entity_id, "transmission"):
                continue
            evolving[entity_id] = DiseaseConditionRow(
                phase=DiseasePhase.LATENT,
                due_tick=tick + latent_ticks,
                symptomatic=None,
            )
            if used_extra:
                extra_latent.append(entity_id)

    # 3) Terminal resolution for start-active rows due this tick.
    mortality: list[EntityId] = []
    for entity_id in sorted(start_active_sources, key=lambda item: item.value):
        row = start_rows[entity_id]
        assert row.due_tick is not None
        if row.due_tick != tick:
            continue
        body = bodies.get(entity_id)
        if body is None or body.life_status is not LifeStatus.ALIVE:
            continue
        if draw(entity_id, "terminal"):
            bodies[entity_id] = copy_body(
                body,
                health=Health(0.0),
                life_status=LifeStatus.DEAD,
            )
            mortality.append(entity_id)
            evolving.pop(entity_id, None)
            continue
        if immunity_after_recovery:
            evolving[entity_id] = DiseaseConditionRow(phase=DiseasePhase.IMMUNE)
        else:
            evolving.pop(entity_id, None)

    indexed = index_disease_state(
        evolving, body_index=bodies, require_living=False
    )
    assert indexed is not None
    mortality_ids = tuple(sorted(mortality, key=lambda item: item.value))
    extra_recipients = tuple(sorted(extra_latent, key=lambda item: item.value))
    _LOG.debug(
        "disease_pass_complete tick=%s row_count=%s mortality_count=%s "
        "eligible_count=%s extra_latent_count=%s",
        tick,
        len(indexed),
        len(mortality_ids),
        len(eligible),
        len(extra_recipients),
    )
    return DiseasePassResult(
        disease_state=indexed,
        bodies=MappingProxyType(bodies),
        mortality_body_ids=mortality_ids,
        start_rows=start_rows,
        extra_latent_recipients=extra_recipients,
    )


def reconcile_disease_rows_for_dead_bodies(
    disease_state: Mapping[EntityId, DiseaseConditionRow] | None,
    *,
    body_index: Mapping[EntityId, AgentBody],
) -> MappingProxyType[EntityId, DiseaseConditionRow] | None:
    """Drop private rows whose body is missing or not living."""
    if disease_state is None:
        return None
    kept = {
        entity_id: row
        for entity_id, row in disease_state.items()
        if (body := body_index.get(entity_id)) is not None
        and body.life_status is LifeStatus.ALIVE
    }
    return index_disease_state(kept, body_index=body_index, require_living=True)


def disease_net_transitions(
    start_rows: Mapping[EntityId, DiseaseConditionRow] | None,
    final_rows: Mapping[EntityId, DiseaseConditionRow] | None,
) -> tuple[
    tuple[EntityId, DiseaseConditionRow | None, DiseaseConditionRow | None], ...
]:
    """Sorted net before/after pairs where the private row changed."""
    if start_rows is None and final_rows is None:
        return ()
    start = {} if start_rows is None else dict(start_rows)
    final = {} if final_rows is None else dict(final_rows)
    keys = sorted(set(start) | set(final), key=lambda item: item.value)
    changes: list[
        tuple[EntityId, DiseaseConditionRow | None, DiseaseConditionRow | None]
    ] = []
    for entity_id in keys:
        before = start.get(entity_id)
        after = final.get(entity_id)
        if before == after:
            continue
        changes.append((entity_id, before, after))
    return tuple(changes)


def disease_row_view(row: DiseaseConditionRow | None) -> object | None:
    """Convert a private row to the detached ``DiseaseRowView`` transport shape."""
    if row is None:
        return None
    from world.events import DiseaseRowView

    return DiseaseRowView(
        phase=row.phase.value,
        due_tick=row.due_tick,
        symptomatic=row.symptomatic,
    )


def disease_row_from_view(view: object | None) -> DiseaseConditionRow | None:
    """Convert a detached ``DiseaseRowView`` into a private row."""
    if view is None:
        return None
    from world.events import DiseaseRowView

    if type(view) is not DiseaseRowView:
        raise TypeError("view must be DiseaseRowView or None")
    return DiseaseConditionRow(
        phase=DiseasePhase(view.phase),
        due_tick=view.due_tick,
        symptomatic=view.symptomatic,
    )


def project_disease_state_changed(
    state: WorldState,
    *,
    details: DiseaseStateChanged,
) -> WorldState:
    """Fold one recorded ``DiseaseStateChanged`` net effect without policy draws."""
    from world._state import WorldState, rebuild_world_state
    from world.events import DiseaseStateChanged

    if type(state) is not WorldState:
        raise TypeError("project_disease_state_changed requires WorldState")
    if type(details) is not DiseaseStateChanged:
        raise TypeError("details must be DiseaseStateChanged")
    if state.disease_state is None:
        raise DiseaseInvariantError("disease_channel_off")
    current = dict(state.disease_state)
    before = disease_row_from_view(details.before)
    after = disease_row_from_view(details.after)
    existing = current.get(details.body_id)
    if existing != before:
        raise DiseaseInvariantError("disease_before_mismatch")
    body = state.bodies.get(details.body_id)
    if body is None:
        raise DiseaseInvariantError("disease_unknown_entity")
    if body.life_status is LifeStatus.ALIVE:
        legal = (
            (
                before is None
                and after is not None
                and after.phase is DiseasePhase.LATENT
            )
            or (
                before is not None
                and before.phase is DiseasePhase.LATENT
                and after is not None
                and after.phase is DiseasePhase.ACTIVE
            )
            or (
                before is not None
                and before.phase is DiseasePhase.ACTIVE
                and (
                    after is None
                    or after.phase is DiseasePhase.IMMUNE
                )
            )
        )
        if not legal:
            raise DiseaseInvariantError("disease_transition_invalid")
    else:
        if before is None or after is not None:
            raise DiseaseInvariantError("disease_dead_transition_invalid")
    if after is None:
        current.pop(details.body_id, None)
    else:
        current[details.body_id] = after
    return rebuild_world_state(
        state,
        disease_state=current,
        replace_disease_state=True,
    )
