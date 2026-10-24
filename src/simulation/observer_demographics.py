"""Pure cursor-scoped demographic projections for the read-only observer.

Input is a detached ``ObjectiveScene``; this module never touches a live engine,
analysis metrics, or private world authority.
"""

from __future__ import annotations

import base64
import binascii
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, NoReturn

from simulation.generational_progress import build_population_progress
from simulation.observer_facts import ObjectiveScene
from world.lifecycle import AgentLifecycleRecord, chronological_age
from world.models import AgentBody, LifeStatus

_LOGGER: Final[logging.Logger] = logging.getLogger("simulation.observer_demographics")

__all__ = [
    "SECTIONS",
    "STAGE_ROW_LIMIT",
    "DemographicAgentRow",
    "DemographicCohortRow",
    "DemographicGenerationRow",
    "DemographicPopulationTotals",
    "DemographicProjection",
    "DemographicsError",
    "GenerationMarkerProjection",
    "GenerationMarkerRow",
    "decode_group_cursor",
    "encode_group_cursor",
    "project_demographics",
    "project_generation_markers",
]

SECTIONS: Final[tuple[str, ...]] = ("agents", "cohorts", "generations")
STAGE_ROW_LIMIT: Final[int] = 200
AGENT_ROW_LIMIT: Final[int] = 200
DEFAULT_ROW_LIMIT: Final[int] = 100
MAX_MARKER_LIMIT: Final[int] = 200


class DemographicsError(ValueError):
    """Closed validation failure while projecting demographic rows."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)


def _reject(reason_code: str) -> NoReturn:
    _LOGGER.warning("demographics_rejected reason_code=%s", reason_code)
    raise DemographicsError(reason_code)


def _require_nonneg(name: str, value: object) -> int:
    if isinstance(value, bool) or type(value) is not int or value < 0:
        _reject(f"invalid_{name}")
    return value


@dataclass(frozen=True, slots=True)
class DemographicPopulationTotals:
    living: int
    admitted: int
    dead: int
    max_generation_index: int


@dataclass(frozen=True, slots=True)
class DemographicStageRow:
    stage: str
    life_status: str
    count: int


@dataclass(frozen=True, slots=True)
class DemographicAgentRow:
    agent_id: str
    entity_id: str
    entry_tick: int
    generation_index: int
    cohort_id: str
    stage: str
    dependency_status: str
    life_status: str
    age_ticks: int | None
    age_reason_code: str | None


@dataclass(frozen=True, slots=True)
class DemographicCohortRow:
    generation_index: int
    entry_tick: int
    cohort_id: str
    admitted: int
    living: int
    dead: int


@dataclass(frozen=True, slots=True)
class DemographicGenerationRow:
    generation_index: int
    admitted: int
    living: int
    dead: int


@dataclass(frozen=True, slots=True)
class DemographicProjection:
    availability: str
    reason_code: str | None
    section: str
    selection_state: str
    population: DemographicPopulationTotals | None
    stage_rows: tuple[DemographicStageRow, ...]
    stage_counts_truncated: bool
    agents: tuple[DemographicAgentRow, ...]
    cohorts: tuple[DemographicCohortRow, ...]
    generations: tuple[DemographicGenerationRow, ...]
    next_after_agent_id: str | None
    next_after_group_key: str | None
    limit: int


@dataclass(frozen=True, slots=True)
class GenerationMarkerRow:
    generation_index: int
    first_entry_tick: int
    seek_tick: int
    admitted_count: int
    label_code: str


@dataclass(frozen=True, slots=True)
class GenerationMarkerProjection:
    availability: str
    reason_code: str | None
    markers: tuple[GenerationMarkerRow, ...]
    next_after_generation_index: int | None
    limit: int


def _validate_selector(
    *,
    section: str,
    agent_id: str | None,
    after_agent_id: str | None,
    after_group_key: str | None,
    limit: int,
) -> None:
    if section not in SECTIONS:
        _reject("demographics_unknown_section")
    if isinstance(limit, bool) or type(limit) is not int or not 1 <= limit <= 200:
        _reject("invalid_demographics_limit")
    if agent_id is not None:
        if section != "agents":
            _reject("demographics_agent_filter_section_mismatch")
        if after_agent_id is not None or after_group_key is not None:
            _reject("demographics_selection_cursor_conflict")
    if after_agent_id is not None and section != "agents":
        _reject("demographics_agent_cursor_section_mismatch")
    if after_group_key is not None and section == "agents":
        _reject("demographics_group_cursor_section_mismatch")
    if after_agent_id is not None and after_group_key is not None:
        _reject("demographics_cursor_conflict")


def _bodies_by_id(scene: ObjectiveScene) -> dict[str, AgentBody]:
    return {body.entity_id.value: body for body in scene.bodies}


def _records(scene: ObjectiveScene) -> tuple[AgentLifecycleRecord, ...]:
    return scene.lifecycle_records or ()


def project_demographics(
    scene: ObjectiveScene,
    *,
    requested_tick: int,
    through_sequence: int | None,
    section: str = "agents",
    agent_id: str | None = None,
    after_agent_id: str | None = None,
    after_group_key: str | None = None,
    limit: int = DEFAULT_ROW_LIMIT,
) -> DemographicProjection:
    """Project one bounded row section plus exact full-population totals."""
    if type(scene) is not ObjectiveScene:
        raise TypeError("scene must be ObjectiveScene")
    _require_nonneg("requested_tick", requested_tick)
    if through_sequence is not None:
        _require_nonneg("through_sequence", through_sequence)
    _validate_selector(
        section=section,
        agent_id=agent_id,
        after_agent_id=after_agent_id,
        after_group_key=after_group_key,
        limit=limit,
    )
    if scene.lifecycle_records is None:
        _LOGGER.debug(
            "demographics_unavailable run_id=%s tick=%s reason_code=%s",
            scene.run_id,
            scene.tick,
            "lifecycle_disabled",
        )
        return DemographicProjection(
            availability="unavailable",
            reason_code="lifecycle_disabled",
            section=section,
            selection_state="unavailable",
            population=None,
            stage_rows=(),
            stage_counts_truncated=False,
            agents=(),
            cohorts=(),
            generations=(),
            next_after_agent_id=None,
            next_after_group_key=None,
            limit=limit,
        )

    records = _records(scene)
    bodies = _bodies_by_id(scene)
    progress = build_population_progress(
        lifecycle_records=records,
        detached_bodies=scene.bodies,
        boundary_tick=scene.tick,
    )
    population = DemographicPopulationTotals(
        living=progress.living_population,
        admitted=progress.total_admitted,
        dead=progress.total_deaths,
        max_generation_index=progress.max_generation_index_seen,
    )

    stage_counts: dict[tuple[str, str], int] = {}
    for record in records:
        body = bodies.get(record.body_id.value)
        if body is None:
            _reject("demographics_missing_body")
        key = (record.stage.value, body.life_status.value)
        stage_counts[key] = stage_counts.get(key, 0) + 1
    ordered_stages = sorted(stage_counts.items())
    stage_rows = tuple(
        DemographicStageRow(stage=stage, life_status=status, count=count)
        for (stage, status), count in ordered_stages[:STAGE_ROW_LIMIT]
    )
    stage_counts_truncated = len(ordered_stages) > STAGE_ROW_LIMIT

    agents: tuple[DemographicAgentRow, ...] = ()
    cohorts: tuple[DemographicCohortRow, ...] = ()
    generations: tuple[DemographicGenerationRow, ...] = ()
    next_after_agent_id: str | None = None
    next_after_group_key: str | None = None
    selection_state = "all"

    if section == "agents":
        rows = _agent_rows(
            scene,
            records=records,
            bodies=bodies,
            agent_id=agent_id,
        )
        if agent_id is not None:
            selection_state = "selected" if rows else "not_present_at_cursor"
        if after_agent_id is not None:
            rows = tuple(row for row in rows if row.agent_id > after_agent_id)
        agent_page = rows[: limit + 1]
        if len(agent_page) > limit:
            next_after_agent_id = agent_page[limit - 1].agent_id
        agents = agent_page[:limit]
    elif section == "cohorts":
        cohort_rows = tuple(
            DemographicCohortRow(
                generation_index=row.generation_index,
                entry_tick=row.entry_tick,
                cohort_id=row.cohort_id,
                admitted=row.admitted,
                living=row.living,
                dead=row.dead,
            )
            for row in progress.cohorts
        )
        if after_group_key is not None:
            cohort_rows = tuple(
                row for row in cohort_rows if _cohort_key(row) > after_group_key
            )
        cohort_page = cohort_rows[: limit + 1]
        if len(cohort_page) > limit:
            next_after_group_key = _cohort_key(cohort_page[limit - 1])
        cohorts = cohort_page[:limit]
    else:
        generation_rows = tuple(
            DemographicGenerationRow(
                generation_index=row.generation_index,
                admitted=row.admitted,
                living=row.living,
                dead=row.dead,
            )
            for row in progress.generations
        )
        if after_group_key is not None:
            generation_rows = tuple(
                row for row in generation_rows if _generation_key(row) > after_group_key
            )
        generation_page = generation_rows[: limit + 1]
        if len(generation_page) > limit:
            next_after_group_key = _generation_key(generation_page[limit - 1])
        generations = generation_page[:limit]

    _LOGGER.debug(
        "demographics_projected run_id=%s tick=%s section=%s selection=%s "
        "living=%s admitted=%s dead=%s agents=%s cohorts=%s generations=%s "
        "stage_rows=%s stage_truncated=%s",
        scene.run_id,
        scene.tick,
        section,
        selection_state,
        population.living,
        population.admitted,
        population.dead,
        len(agents),
        len(cohorts),
        len(generations),
        len(stage_rows),
        stage_counts_truncated,
    )
    return DemographicProjection(
        availability="available",
        reason_code=None,
        section=section,
        selection_state=selection_state,
        population=population,
        stage_rows=stage_rows,
        stage_counts_truncated=stage_counts_truncated,
        agents=agents,
        cohorts=cohorts,
        generations=generations,
        next_after_agent_id=next_after_agent_id,
        next_after_group_key=next_after_group_key,
        limit=limit,
    )


def _agent_rows(
    scene: ObjectiveScene,
    *,
    records: Sequence[AgentLifecycleRecord],
    bodies: dict[str, AgentBody],
    agent_id: str | None,
) -> tuple[DemographicAgentRow, ...]:
    rows: list[DemographicAgentRow] = []
    for record in records:
        body = bodies.get(record.body_id.value)
        if body is None:
            _reject("demographics_missing_body")
        if agent_id is not None and record.agent_id != agent_id:
            continue
        living = body.life_status is LifeStatus.ALIVE
        if living:
            age_ticks: int | None = chronological_age(
                entry_tick=record.entry_tick, current_tick=scene.tick
            )
            age_reason: str | None = None
        else:
            age_ticks = None
            age_reason = "dead_age_not_projected"
        rows.append(
            DemographicAgentRow(
                agent_id=record.agent_id,
                entity_id=record.body_id.value,
                entry_tick=record.entry_tick,
                generation_index=record.generation_index,
                cohort_id=record.cohort_id,
                stage=record.stage.value,
                dependency_status=record.dependency_status.value,
                life_status=body.life_status.value,
                age_ticks=age_ticks,
                age_reason_code=age_reason,
            )
        )
    rows.sort(key=lambda row: row.agent_id)
    return tuple(rows)


def _cohort_key(row: DemographicCohortRow) -> str:
    return f"cohort|{row.generation_index:012d}|{row.entry_tick:012d}|{row.cohort_id}"


def _generation_key(row: DemographicGenerationRow) -> str:
    return f"generation|{row.generation_index:012d}"


def encode_group_cursor(
    *, section: str, tick: int, sequence: int | None, key: str
) -> str:
    """Encode an opaque bounded objective keyset position."""
    if section not in {"cohorts", "generations"}:
        raise ValueError("group cursor requires cohorts or generations")
    sequence_value = "-" if sequence is None else str(sequence)
    raw = f"{section}|{tick}|{sequence_value}|{key}".encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def decode_group_cursor(
    value: str,
    *,
    section: str,
    tick: int,
    sequence: int | None,
) -> str:
    """Strictly decode a group continuation and verify its pinned selectors."""
    if type(value) is not str or not value or len(value) > 512:
        _reject("demographics_invalid_group_cursor")
    padding = "=" * (-len(value) % 4)
    try:
        raw = base64.urlsafe_b64decode((value + padding).encode())
        text = raw.decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError) as exc:
        raise DemographicsError("demographics_invalid_group_cursor") from exc
    parts = text.split("|", 3)
    if len(parts) != 4:
        _reject("demographics_invalid_group_cursor")
    cursor_section, cursor_tick, cursor_sequence, key = parts
    expected_sequence = "-" if sequence is None else str(sequence)
    if (
        cursor_section != section
        or cursor_tick != str(tick)
        or cursor_sequence != expected_sequence
        or not key
    ):
        _reject("demographics_group_cursor_mismatch")
    if section == "cohorts" and not key.startswith("cohort|"):
        _reject("demographics_group_cursor_mismatch")
    if section == "generations" and not key.startswith("generation|"):
        _reject("demographics_group_cursor_mismatch")
    return key


def project_generation_markers(
    scene: ObjectiveScene,
    *,
    requested_tick: int,
    from_tick: int | None = None,
    to_tick: int | None = None,
    after_generation_index: int | None = None,
    limit: int = DEFAULT_ROW_LIMIT,
) -> GenerationMarkerProjection:
    """Project admitted-generation markers from stored lifecycle records."""
    if type(scene) is not ObjectiveScene:
        raise TypeError("scene must be ObjectiveScene")
    _require_nonneg("requested_tick", requested_tick)
    if isinstance(limit, bool) or type(limit) is not int or not 1 <= limit <= 200:
        _reject("invalid_marker_limit")
    if after_generation_index is not None:
        _require_nonneg("after_generation_index", after_generation_index)
    if from_tick is not None:
        _require_nonneg("from_tick", from_tick)
    if to_tick is not None:
        _require_nonneg("to_tick", to_tick)
    if from_tick is not None and from_tick > requested_tick:
        _reject("invalid_marker_window")
    if from_tick is not None and to_tick is not None and from_tick > to_tick:
        _reject("invalid_marker_window")
    if to_tick is not None and to_tick > requested_tick:
        _reject("invalid_marker_window")
    if scene.lifecycle_records is None:
        return GenerationMarkerProjection(
            availability="unavailable",
            reason_code="lifecycle_disabled",
            markers=(),
            next_after_generation_index=None,
            limit=limit,
        )

    grouped: dict[int, list[AgentLifecycleRecord]] = {}
    for record in scene.lifecycle_records:
        grouped.setdefault(record.generation_index, []).append(record)
    markers: list[GenerationMarkerRow] = []
    for generation_index in sorted(grouped):
        records = grouped[generation_index]
        first_entry = min(record.entry_tick for record in records)
        seek_tick = 0 if generation_index == 0 else first_entry + 1
        if seek_tick > scene.tick:
            continue
        if from_tick is not None and seek_tick < from_tick:
            continue
        if to_tick is not None and seek_tick > to_tick:
            continue
        if (
            after_generation_index is not None
            and generation_index <= after_generation_index
        ):
            continue
        markers.append(
            GenerationMarkerRow(
                generation_index=generation_index,
                first_entry_tick=first_entry,
                seek_tick=seek_tick,
                admitted_count=len(records),
                label_code=(
                    "founders"
                    if generation_index == 0
                    else "generation_first_admission"
                ),
            )
        )
    page = markers[: limit + 1]
    next_index = page[limit - 1].generation_index if len(page) > limit else None
    _LOGGER.debug(
        "generation_markers_projected run_id=%s tick=%s marker_count=%s next_after=%s",
        scene.run_id,
        scene.tick,
        min(len(page), limit),
        "-" if next_index is None else next_index,
    )
    return GenerationMarkerProjection(
        availability="available",
        reason_code=None,
        markers=tuple(page[:limit]),
        next_after_generation_index=next_index,
        limit=limit,
    )
