"""Read-only regional population census and residence-candidate folds."""

from __future__ import annotations

import logging
import time
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
)
from analysis.numerical import library_versions
from analysis.specifications import MetricFamilyId, metric_specification
from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "REGIONAL_POPULATION_METRIC_VERSION",
    "QualifiedMigrationRow",
    "RegionalEventRow",
    "RegionalHistory",
    "RegionalInitialPlacementRow",
    "RegionalLocationRow",
    "RegionalPopulationError",
    "RegionalPopulationInput",
    "compute_regional_population",
    "fold_regional_history",
]

REGIONAL_POPULATION_METRIC_VERSION: Final[str] = "regional_population@1"
_EVENT_KINDS: Final[frozenset[str]] = frozenset(
    {"relocation", "entry", "death", "stage"}
)
_LOG: Final[logging.Logger] = logging.getLogger("analysis.regional_population")


class RegionalPopulationError(ValueError):
    """Malformed or inconsistent detached regional evidence."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = require_stable_id("reason_code", reason_code)
        _LOG.error("regional_population_invalid reason_code=%s", reason_code)
        super().__init__(reason_code)


@dataclass(frozen=True, slots=True)
class RegionalLocationRow:
    location_id: str
    region_id: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "location_id", require_stable_id("location_id", self.location_id)
        )
        object.__setattr__(
            self, "region_id", require_stable_id("region_id", self.region_id)
        )


@dataclass(frozen=True, slots=True)
class RegionalInitialPlacementRow:
    body_id: str
    location_id: str
    alive: bool = True
    stage_id: str | None = None
    cohort_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "body_id", require_stable_id("body_id", self.body_id))
        object.__setattr__(
            self, "location_id", require_stable_id("location_id", self.location_id)
        )
        if type(self.alive) is not bool:
            raise TypeError("alive must be bool")
        for name in ("stage_id", "cohort_id"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, require_stable_id(name, value))


@dataclass(frozen=True, slots=True)
class RegionalEventRow:
    """One participant-level committed placement, entry, death, or stage fact."""

    tick: int
    sequence: int
    kind: str
    body_id: str
    origin_location_id: str | None = None
    destination_location_id: str | None = None
    stage_id: str | None = None
    relocation_kind: str = "move"

    def __post_init__(self) -> None:
        object.__setattr__(self, "tick", require_exact_nonneg_int("tick", self.tick))
        object.__setattr__(
            self, "sequence", require_exact_nonneg_int("sequence", self.sequence)
        )
        object.__setattr__(self, "kind", require_stable_id("kind", self.kind))
        if self.kind not in _EVENT_KINDS:
            raise ValueError("unknown_regional_event_kind")
        object.__setattr__(self, "body_id", require_stable_id("body_id", self.body_id))
        for name in ("origin_location_id", "destination_location_id", "stage_id"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, require_stable_id(name, value))
        if self.kind == "relocation" and self.destination_location_id is None:
            raise ValueError("relocation_requires_destination")
        object.__setattr__(
            self,
            "relocation_kind",
            require_stable_id("relocation_kind", self.relocation_kind),
        )
        if self.relocation_kind not in {"move", "transport", "flee", "journey"}:
            raise ValueError("invalid_relocation_kind")
        if self.kind == "entry" and self.destination_location_id is None:
            raise ValueError("entry_requires_location")
        if self.kind == "stage" and self.stage_id is None:
            raise ValueError("stage_event_requires_stage")


@dataclass(frozen=True, slots=True)
class RegionalPopulationInput:
    run_id: str
    input_revision: str
    region_ids: tuple[str, ...]
    known_location_ids: tuple[str, ...]
    location_rows: tuple[RegionalLocationRow, ...]
    initial_placements: tuple[RegionalInitialPlacementRow, ...]
    events: tuple[RegionalEventRow, ...]
    residence_min_ticks: int
    window_end: int
    complete_through_boundary: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", require_stable_id("run_id", self.run_id))
        object.__setattr__(
            self,
            "input_revision",
            require_stable_id("input_revision", self.input_revision),
        )
        for field_name, value in (
            ("region_ids", self.region_ids),
            ("known_location_ids", self.known_location_ids),
            ("location_rows", self.location_rows),
            ("initial_placements", self.initial_placements),
            ("events", self.events),
        ):
            if isinstance(value, (str, bytes, Mapping)) or not isinstance(
                value, Sequence
            ):
                raise TypeError(f"{field_name} must be an ordered sequence")
            object.__setattr__(self, field_name, tuple(value))
        region_ids = tuple(
            sorted(require_stable_id("region_id", item) for item in self.region_ids)
        )
        if not region_ids or len(region_ids) != len(set(region_ids)):
            raise ValueError("invalid_region_ids")
        object.__setattr__(self, "region_ids", region_ids)
        known_locations = tuple(
            sorted(
                require_stable_id("location_id", item)
                for item in self.known_location_ids
            )
        )
        if not known_locations or len(known_locations) != len(set(known_locations)):
            raise ValueError("invalid_known_location_ids")
        object.__setattr__(self, "known_location_ids", known_locations)
        known_location_set = set(known_locations)
        if any(type(row) is not RegionalLocationRow for row in self.location_rows):
            raise TypeError("location_rows entries must be RegionalLocationRow")
        if any(
            type(row) is not RegionalInitialPlacementRow
            for row in self.initial_placements
        ):
            raise TypeError(
                "initial_placements entries must be RegionalInitialPlacementRow"
            )
        if any(type(row) is not RegionalEventRow for row in self.events):
            raise TypeError("events entries must be RegionalEventRow")
        if len({row.location_id for row in self.location_rows}) != len(
            self.location_rows
        ):
            raise ValueError("duplicate_location_region")
        if any(row.location_id not in known_location_set for row in self.location_rows):
            raise ValueError("regional_mapping_location_unknown")
        if any(row.region_id not in region_ids for row in self.location_rows):
            raise ValueError("unknown_location_region")
        if len({row.body_id for row in self.initial_placements}) != len(
            self.initial_placements
        ):
            raise ValueError("duplicate_initial_body")
        if any(
            row.location_id not in known_location_set for row in self.initial_placements
        ):
            raise ValueError("initial_placement_location_unknown")
        residence_min = require_exact_nonneg_int(
            "residence_min_ticks", self.residence_min_ticks
        )
        if residence_min < 1:
            raise ValueError("residence_min_ticks_must_be_positive")
        object.__setattr__(self, "residence_min_ticks", residence_min)
        object.__setattr__(
            self, "window_end", require_exact_nonneg_int("window_end", self.window_end)
        )
        complete = (
            self.window_end
            if self.complete_through_boundary is None
            else require_exact_nonneg_int(
                "complete_through_boundary", self.complete_through_boundary
            )
        )
        if complete > self.window_end:
            raise ValueError("coverage_boundary_exceeds_window")
        object.__setattr__(self, "complete_through_boundary", complete)
        ordered = tuple(
            sorted(self.events, key=lambda row: (row.tick, row.sequence, row.body_id))
        )
        if ordered != self.events:
            raise ValueError("events_must_be_ordered")
        for event in self.events:
            if (
                event.origin_location_id is not None
                and event.origin_location_id not in known_location_set
            ):
                raise ValueError("event_origin_location_unknown")
            if (
                event.destination_location_id is not None
                and event.destination_location_id not in known_location_set
            ):
                raise ValueError("event_destination_location_unknown")
        if any(row.tick >= complete for row in self.events):
            raise ValueError("event_exceeds_complete_boundary")
        event_keys = tuple((row.tick, row.sequence, row.body_id) for row in self.events)
        if len(event_keys) != len(set(event_keys)):
            raise ValueError("duplicate_regional_event_participant")


@dataclass(frozen=True, slots=True)
class QualifiedMigrationRow:
    body_id: str
    origin_region_id: str
    destination_region_id: str
    candidate_arrival_boundary: int
    qualified_boundary: int


@dataclass(frozen=True, slots=True)
class RegionalHistory:
    final_population: Mapping[str, int]
    person_ticks: Mapping[str, int]
    entries: Mapping[str, int]
    deaths: Mapping[str, int]
    arrivals: Mapping[str, int]
    departures: Mapping[str, int]
    assigned_unassigned_in: int
    assigned_unassigned_out: int
    raw_interregional_flows: Mapping[tuple[str, str], int]
    relocation_kind_counts: Mapping[str, int]
    qualified_migrations: tuple[QualifiedMigrationRow, ...]
    final_unassigned_population: int
    unassigned_person_ticks: int
    unassigned_entries: int
    unassigned_deaths: int
    observed_boundaries: int
    conservation_check_count: int
    lifecycle_available: bool
    final_stage_population: Mapping[tuple[str, str], int]
    stage_person_ticks: Mapping[tuple[str, str], int]
    final_cohort_population: Mapping[tuple[str, str], int]
    cohort_person_ticks: Mapping[tuple[str, str], int]


@dataclass(slots=True)
class _PersonState:
    location_id: str
    alive: bool
    stage_id: str | None
    cohort_id: str | None
    established_residence: str | None
    candidate_region: str | None = None
    candidate_arrival_boundary: int | None = None
    consecutive_boundary_count: int = 0


def fold_regional_history(inputs: RegionalPopulationInput) -> RegionalHistory:
    """Apply ordered relocations, entries, deaths, then each completed boundary."""
    if type(inputs) is not RegionalPopulationInput:
        raise TypeError("inputs must be RegionalPopulationInput")
    region_by_location = {
        row.location_id: row.region_id for row in inputs.location_rows
    }
    regions = set(inputs.region_ids)
    people: dict[str, _PersonState] = {}
    for row in inputs.initial_placements:
        if (
            row.location_id in region_by_location
            and region_by_location[row.location_id] not in regions
        ):
            raise RegionalPopulationError("initial_location_region_invalid")
        region = region_by_location.get(row.location_id)
        people[row.body_id] = _PersonState(
            location_id=row.location_id,
            alive=row.alive,
            stage_id=row.stage_id,
            cohort_id=row.cohort_id,
            established_residence=region if row.alive else None,
        )

    events_by_tick: dict[int, list[RegionalEventRow]] = defaultdict(list)
    for event in inputs.events:
        events_by_tick[event.tick].append(event)
    person_ticks: Counter[str] = Counter()
    stage_person_ticks: Counter[tuple[str, str]] = Counter()
    cohort_person_ticks: Counter[tuple[str, str]] = Counter()
    unassigned_person_ticks = 0
    entries: Counter[str] = Counter()
    deaths: Counter[str] = Counter()
    arrivals: Counter[str] = Counter()
    departures: Counter[str] = Counter()
    flows: Counter[tuple[str, str]] = Counter()
    relocation_kind_counts: Counter[str] = Counter()
    assigned_unassigned_in = 0
    assigned_unassigned_out = 0
    unassigned_entries = 0
    unassigned_deaths = 0
    qualified: list[QualifiedMigrationRow] = []
    conservation_checks = 0
    lifecycle_available = any(
        person.stage_id is not None or person.cohort_id is not None
        for person in people.values()
    ) or any(event.kind == "stage" for event in inputs.events)

    def census(boundary: int) -> Counter[str | None]:
        current: Counter[str | None] = Counter()
        for body_id in sorted(people):
            person = people[body_id]
            if not person.alive:
                person.candidate_region = None
                person.candidate_arrival_boundary = None
                person.consecutive_boundary_count = 0
                continue
            region = region_by_location.get(person.location_id)
            if region is None:
                person.candidate_region = None
                person.candidate_arrival_boundary = None
                person.consecutive_boundary_count = 0
            elif region == person.established_residence:
                person.candidate_region = None
                person.candidate_arrival_boundary = None
                person.consecutive_boundary_count = 0
            elif region != person.candidate_region:
                person.candidate_region = region
                person.candidate_arrival_boundary = boundary
                person.consecutive_boundary_count = 1
            else:
                person.consecutive_boundary_count += 1
            if (
                person.alive
                and person.candidate_region is not None
                and person.consecutive_boundary_count >= inputs.residence_min_ticks
            ):
                assert person.candidate_arrival_boundary is not None
                if person.established_residence is not None:
                    qualified.append(
                        QualifiedMigrationRow(
                            body_id=body_id,
                            origin_region_id=person.established_residence,
                            destination_region_id=person.candidate_region,
                            candidate_arrival_boundary=person.candidate_arrival_boundary,
                            qualified_boundary=boundary,
                        )
                    )
                _LOG.debug(
                    "regional_residence_qualified boundary=%s first_residence=%s",
                    boundary,
                    person.established_residence is None,
                )
                person.established_residence = person.candidate_region
                person.candidate_region = None
                person.candidate_arrival_boundary = None
                person.consecutive_boundary_count = 0
            region = region_by_location.get(person.location_id)
            if region is None:
                current[None] += 1
                continue
            current[region] += 1
            if person.stage_id is not None:
                stage_person_ticks[(region, person.stage_id)] += 1
            if person.cohort_id is not None:
                cohort_person_ticks[(region, person.cohort_id)] += 1
        return current

    previous = census(0)
    for region, count in previous.items():
        if region is None:
            unassigned_person_ticks += count
        else:
            person_ticks[region] += count

    complete_boundary = inputs.complete_through_boundary or 0
    for boundary in range(1, complete_boundary + 1):
        previous = Counter(
            region_by_location.get(person.location_id)
            for person in people.values()
            if person.alive
        )
        boundary_arrivals: Counter[str] = Counter()
        boundary_departures: Counter[str] = Counter()
        boundary_entries: Counter[str] = Counter()
        boundary_deaths: Counter[str] = Counter()
        boundary_unassigned_in = 0
        boundary_unassigned_out = 0
        boundary_unassigned_entries = 0
        boundary_unassigned_deaths = 0
        for event in events_by_tick.get(boundary - 1, ()):
            person = people.get(event.body_id)
            if event.kind == "entry":
                if person is not None:
                    raise RegionalPopulationError("duplicate_population_entry")
                assert event.destination_location_id is not None
                region = region_by_location.get(event.destination_location_id)
                people[event.body_id] = _PersonState(
                    location_id=event.destination_location_id,
                    alive=True,
                    stage_id=event.stage_id,
                    cohort_id=None,
                    established_residence=region,
                )
                if region is not None:
                    entries[region] += 1
                    boundary_entries[region] += 1
                else:
                    unassigned_entries += 1
                    boundary_unassigned_entries += 1
                continue
            if person is None:
                raise RegionalPopulationError("event_body_missing")
            if event.kind == "relocation":
                if not person.alive:
                    raise RegionalPopulationError("dead_body_relocated")
                assert event.origin_location_id is not None
                assert event.destination_location_id is not None
                if (
                    event.origin_location_id is not None
                    and person.location_id != event.origin_location_id
                ):
                    raise RegionalPopulationError("relocation_origin_mismatch")
                origin_region = region_by_location.get(person.location_id)
                destination_region = region_by_location.get(
                    event.destination_location_id
                )
                if person.location_id != event.destination_location_id:
                    relocation_kind_counts[event.relocation_kind] += 1
                if origin_region != destination_region:
                    if origin_region is not None:
                        departures[origin_region] += 1
                        boundary_departures[origin_region] += 1
                    if destination_region is not None:
                        arrivals[destination_region] += 1
                        boundary_arrivals[destination_region] += 1
                    if origin_region is None and destination_region is not None:
                        assigned_unassigned_in += 1
                        boundary_unassigned_in += 1
                    elif origin_region is not None and destination_region is None:
                        assigned_unassigned_out += 1
                        boundary_unassigned_out += 1
                    if origin_region is not None and destination_region is not None:
                        flows[(origin_region, destination_region)] += 1
                person.location_id = event.destination_location_id
                continue
            if event.kind == "death":
                if not person.alive:
                    raise RegionalPopulationError("duplicate_body_death")
                region = region_by_location.get(person.location_id)
                if region is not None:
                    deaths[region] += 1
                    boundary_deaths[region] += 1
                else:
                    unassigned_deaths += 1
                    boundary_unassigned_deaths += 1
                person.alive = False
                person.candidate_region = None
                person.candidate_arrival_boundary = None
                person.consecutive_boundary_count = 0
                continue
            if event.kind == "stage":
                if not person.alive:
                    raise RegionalPopulationError("dead_body_stage_change")
                person.stage_id = event.stage_id

        current = census(boundary)
        for region in inputs.region_ids:
            expected_delta = (
                boundary_arrivals[region]
                - boundary_departures[region]
                + boundary_entries[region]
                - boundary_deaths[region]
            )
            actual_delta = current[region] - previous[region]
            if actual_delta != expected_delta:
                raise RegionalPopulationError("population_conservation_failed")
            conservation_checks += 1
        expected_unassigned_delta = (
            boundary_unassigned_out
            - boundary_unassigned_in
            + boundary_unassigned_entries
            - boundary_unassigned_deaths
        )
        if current[None] - previous[None] != expected_unassigned_delta:
            raise RegionalPopulationError("unassigned_population_conservation_failed")
        conservation_checks += 1
        for region, count in current.items():
            if region is None:
                unassigned_person_ticks += count
            else:
                person_ticks[region] += count

    final_population = Counter(
        region_by_location.get(person.location_id)
        for person in people.values()
        if person.alive
    )
    stage_population: Counter[tuple[str, str]] = Counter()
    cohort_population: Counter[tuple[str, str]] = Counter()
    for person in people.values():
        if not person.alive:
            continue
        region = region_by_location.get(person.location_id)
        if region is not None:
            if person.stage_id is not None:
                stage_population[(region, person.stage_id)] += 1
            if person.cohort_id is not None:
                cohort_population[(region, person.cohort_id)] += 1
    return RegionalHistory(
        final_population={
            region: final_population[region] for region in inputs.region_ids
        },
        person_ticks={region: person_ticks[region] for region in inputs.region_ids},
        entries={region: entries[region] for region in inputs.region_ids},
        deaths={region: deaths[region] for region in inputs.region_ids},
        arrivals={region: arrivals[region] for region in inputs.region_ids},
        departures={region: departures[region] for region in inputs.region_ids},
        assigned_unassigned_in=assigned_unassigned_in,
        assigned_unassigned_out=assigned_unassigned_out,
        raw_interregional_flows=dict(sorted(flows.items())),
        relocation_kind_counts=dict(sorted(relocation_kind_counts.items())),
        qualified_migrations=tuple(qualified),
        final_unassigned_population=final_population[None],
        unassigned_person_ticks=unassigned_person_ticks,
        unassigned_entries=unassigned_entries,
        unassigned_deaths=unassigned_deaths,
        observed_boundaries=self_complete_boundary_count(inputs),
        conservation_check_count=conservation_checks,
        lifecycle_available=lifecycle_available,
        final_stage_population=dict(stage_population),
        stage_person_ticks=dict(stage_person_ticks),
        final_cohort_population=dict(cohort_population),
        cohort_person_ticks=dict(cohort_person_ticks),
    )


def self_complete_boundary_count(inputs: RegionalPopulationInput) -> int:
    return (inputs.complete_through_boundary or 0) + 1


def compute_regional_population(inputs: RegionalPopulationInput) -> MetricDocument:
    if type(inputs) is not RegionalPopulationInput:
        raise TypeError("inputs must be RegionalPopulationInput")
    started = time.perf_counter()
    history = fold_regional_history(inputs)
    spec = metric_specification(MetricFamilyId.REGIONAL_POPULATION)
    if spec.version_identifier != REGIONAL_POPULATION_METRIC_VERSION:
        raise RegionalPopulationError("unsupported_metric_version")
    expected_boundaries = inputs.window_end + 1
    observed = history.observed_boundaries
    complete = observed == expected_boundaries
    values: dict[str, object] = {
        "assigned_living_population": sum(history.final_population.values()),
        "assigned_person_ticks": sum(history.person_ticks.values()),
        "assigned_unassigned_in": history.assigned_unassigned_in,
        "assigned_unassigned_out": history.assigned_unassigned_out,
        "conservation_check_count": history.conservation_check_count,
        "conservation_violations": 0,
        "entry_count": sum(history.entries.values()),
        "death_count": sum(history.deaths.values()),
        "final_unassigned_population": history.final_unassigned_population,
        "unassigned_person_ticks": history.unassigned_person_ticks,
        "unassigned_entry_count": history.unassigned_entries,
        "unassigned_death_count": history.unassigned_deaths,
        "region_arrivals": sum(history.arrivals.values()),
        "region_departures": sum(history.departures.values()),
        "region_deaths": sum(history.deaths.values()),
        "region_entries": sum(history.entries.values()),
        "region_living_population": sum(history.final_population.values()),
        "region_person_ticks": sum(history.person_ticks.values()),
        "region_count": len(inputs.region_ids),
        "relocation_kind_counts": sum(history.relocation_kind_counts.values()),
        "unassigned_coverage": (
            "present"
            if len(inputs.known_location_ids) > len(inputs.location_rows)
            else "none"
        ),
        "unassigned_location_count": len(inputs.known_location_ids)
        - len(inputs.location_rows),
    }
    if history.lifecycle_available:
        values["lifecycle_evidence_available"] = True
    else:
        values["lifecycle_evidence_available"] = False
    values["region_stage_living_population"] = sum(
        history.final_stage_population.values()
    )
    values["region_stage_person_ticks"] = sum(history.stage_person_ticks.values())
    values["region_stage_group_count"] = len(history.final_stage_population)
    values["region_cohort_living_population"] = sum(
        history.final_cohort_population.values()
    )
    values["region_cohort_person_ticks"] = sum(history.cohort_person_ticks.values())
    values["region_cohort_group_count"] = len(history.final_cohort_population)
    for region in inputs.region_ids:
        values[f"region:{region}:arrivals"] = history.arrivals[region]
        values[f"region:{region}:departures"] = history.departures[region]
        values[f"region:{region}:deaths"] = history.deaths[region]
        values[f"region:{region}:entries"] = history.entries[region]
        values[f"region:{region}:living_population"] = history.final_population[region]
        values[f"region:{region}:person_ticks"] = history.person_ticks[region]
    if history.lifecycle_available:
        for (region, stage), count in history.final_stage_population.items():
            values[f"region:{region}:stage:{stage}:living_population"] = count
        for (region, stage), count in history.stage_person_ticks.items():
            values[f"region:{region}:stage:{stage}:person_ticks"] = count
        for (region, cohort), count in history.final_cohort_population.items():
            values[f"region:{region}:cohort:{cohort}:living_population"] = count
        for (region, cohort), count in history.cohort_person_ticks.items():
            values[f"region:{region}:cohort:{cohort}:person_ticks"] = count
    availability = (
        MetricAvailability.PRESENT if complete else MetricAvailability.PARTIAL
    )
    _LOG.info(
        "regional_population_complete run_id=%s region_count=%s boundary_count=%s "
        "availability=%s",
        inputs.run_id,
        len(inputs.region_ids),
        observed,
        availability.value,
    )
    _LOG.debug(
        "regional_population_coverage run_id=%s entry_count=%s death_count=%s "
        "qualified_count=%s conservation_checks=%s duration_ms=%s",
        inputs.run_id,
        sum(history.entries.values()),
        sum(history.deaths.values()),
        len(history.qualified_migrations),
        history.conservation_check_count,
        int((time.perf_counter() - started) * 1000),
    )
    return MetricDocument(
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        metric_family=spec.family_id.value,
        algorithm_version=spec.algorithm_version,
        library_versions=library_versions(),
        run_id=inputs.run_id,
        input_revision=inputs.input_revision,
        evidence_stages=frozenset(spec.evidence_inputs),
        population=spec.population,
        denominator=spec.denominator,
        coverage=MetricCoverage(observed=observed, expected=expected_boundaries),
        availability=availability,
        values=values,
        provenance=MetricProvenance(
            source_kind="regional_population",
            source_ids=(inputs.run_id,),
            notes_code="ok" if complete else "incomplete_prefix",
        ),
    )
