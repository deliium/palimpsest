"""Detached multi-generational narrative analysis rows and metrics.

Analysis-only. This module imports no agent cognition, runtime, persistence, or
private world types. Callers supply duck-typed ledgers and objective rows.
Results never re-enter cognition, memory formation, prompts, or admission.
"""

from __future__ import annotations

import logging
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
from analysis.numerical import library_versions, quantize_float
from analysis.specifications import MetricFamilyId, metric_specification
from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "GENERATIONAL_NARRATIVE_ALIGNMENT_WINDOW_TICKS",
    "GenerationalNarrativeInputs",
    "NarrativeGenerationRow",
    "NarrativeHistoryComparisonRow",
    "NarrativeRecordRow",
    "NarrativeSourceLossRow",
    "compute_generational_narrative_continuity",
    "compute_narrative_historical_alignment",
    "compute_narrative_source_loss",
    "generational_narrative_inputs_from_harvest",
    "narrative_generation_rows_from_ledgers",
    "narrative_history_comparison_rows_from_rows",
    "narrative_record_rows_from_ledgers",
    "narrative_source_loss_rows_from_ledgers",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.generational_narratives")
GENERATIONAL_NARRATIVE_ALIGNMENT_WINDOW_TICKS: Final[int] = 2
_ABSENT: Final[str] = MetricAvailability.ABSENT.value
_ALIGNMENT_CLASSES: Final[tuple[str, ...]] = (
    "aligned",
    "partial",
    "divergent",
    "unverifiable",
)
_DAMAGED_INTEGRITY: Final[frozenset[str]] = frozenset(
    {"damaged", "partial", "partially_lost"}
)
_DESTROYED_INTEGRITY: Final[frozenset[str]] = frozenset({"destroyed", "lost"})


def _value(item: object, name: str, default: object = None) -> object:
    if isinstance(item, Mapping):
        return item.get(name, default)
    return getattr(item, name, default)


def _text(item: object, name: str) -> str | None:
    value = _value(item, name)
    return value if isinstance(value, str) and value else None


def _int(item: object, name: str) -> int | None:
    value = _value(item, name)
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _items(item: object, name: str) -> tuple[object, ...]:
    value = _value(item, name, ()) or ()
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        return ()
    return tuple(value)


@dataclass(frozen=True, slots=True)
class NarrativeGenerationRow:
    owner_id: str
    variant_id: str
    root_id: str | None
    source_event_id: str | None
    themes: tuple[str, ...]
    status: str
    origin: str
    first_tick: int | None
    last_tick: int | None
    carrier_agent_ids: tuple[str, ...]
    carrier_generations: tuple[int, ...]
    generation_span: int | None
    witness_count: int
    dead_witness_count: int
    record_count: int
    transition_count: int
    declared_hop_count: int
    source_loss_state: str | None
    record_backed: bool
    location_ids: tuple[str, ...] = ()
    variant_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class NarrativeRecordRow:
    owner_id: str
    variant_id: str
    record_id: str
    role: str
    observed_revision: int
    copy_generation: int | None
    integrity: str | None
    annotation_revisions: int | None
    tick: int
    source_loss_state: str | None


@dataclass(frozen=True, slots=True)
class NarrativeSourceLossRow:
    owner_id: str
    variant_id: str
    subjective_state: str
    subjective_reason: str
    objective_state: str
    dead_witness_share: float
    record_integrity: str
    all_witnesses_dead: bool
    record_backed: bool


@dataclass(frozen=True, slots=True)
class NarrativeHistoryComparisonRow:
    owner_id: str
    variant_id: str
    source_event_id: str | None
    objective_event_kind: str | None
    actor_token: str | None
    target_token: str | None
    location_token: str | None
    objective_tick: int | None
    narrative_tick: int | None
    token_coverage: float
    participant_coverage: float
    location_agreement: bool
    temporal_distance: int | None
    classification: str


@dataclass(frozen=True, slots=True)
class GenerationalNarrativeInputs:
    generation_rows: tuple[NarrativeGenerationRow, ...] = ()
    record_rows: tuple[NarrativeRecordRow, ...] = ()
    source_loss_rows: tuple[NarrativeSourceLossRow, ...] = ()
    comparison_rows: tuple[NarrativeHistoryComparisonRow, ...] = ()
    transition_counts: tuple[tuple[str, int], ...] = ()
    coverage_gaps: tuple[str, ...] = ()


def _generation_values(
    carrier_agent_ids: Sequence[str],
    generation_index_by_agent: Mapping[str, int] | None,
) -> tuple[int, ...]:
    if generation_index_by_agent is None:
        return ()
    values: list[int] = []
    for agent_id in carrier_agent_ids:
        value = generation_index_by_agent.get(agent_id)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            values.append(value)
    return tuple(sorted(dict.fromkeys(values)))


def narrative_generation_rows_from_ledgers(
    ledgers: Sequence[object] | None,
    *,
    generation_index_by_agent: Mapping[str, int] | None = None,
) -> tuple[NarrativeGenerationRow, ...]:
    rows: list[NarrativeGenerationRow] = []
    for ledger in ledgers or ():
        owner_id = _text(ledger, "owner_id")
        if owner_id is None:
            owner_value = _value(ledger, "owner_id")
            owner_id = getattr(owner_value, "value", None)
        if not isinstance(owner_id, str) or not owner_id:
            continue
        for variant in _items(ledger, "variants"):
            variant_id = _text(variant, "variant_id")
            if variant_id is None:
                continue
            carrier_ids = tuple(
                value
                for item in _items(variant, "carrier_agent_ids")
                if isinstance((value := getattr(item, "value", item)), str) and value
            )
            generations = _generation_values(
                carrier_ids, generation_index_by_agent
            )
            span: int | None = None
            if generations:
                span = max(generations) - min(generations)
            witnesses = _items(variant, "source_witnesses")
            first_hand = [
                witness
                for witness in witnesses
                if _text(witness, "kind") == "first_hand"
            ]
            dead = sum(
                1
                for witness in first_hand
                if _int(witness, "death_observed_tick") is not None
            )
            loss = _value(variant, "source_loss")
            source_loss_state = None if loss is None else _text(loss, "state")
            record_backed = (
                bool(_value(loss, "record_backed", False)) if loss else False
            )
            themes = tuple(
                value
                for theme in _items(variant, "themes")
                if isinstance((value := getattr(theme, "value", theme)), str)
                and value
            )
            locations = tuple(
                value for item in _items(variant, "location_ids")
                if isinstance((value := getattr(item, "value", item)), str) and value
            )
            parent_ids = tuple(
                value for item in _items(variant, "parent_variant_ids")
                if isinstance(value, str) and value
            )
            rows.append(
                NarrativeGenerationRow(
                    owner_id=owner_id,
                    variant_id=variant_id,
                    root_id=_text(variant, "transmission_root_id"),
                    source_event_id=_text(variant, "source_event_id"),
                    themes=themes,
                    status=_text(variant, "status") or "unknown",
                    origin=_text(variant, "origin") or "unknown",
                    first_tick=_int(variant, "first_tick"),
                    last_tick=_int(variant, "last_tick"),
                    carrier_agent_ids=carrier_ids,
                    carrier_generations=generations,
                    generation_span=span,
                    witness_count=len(first_hand),
                    dead_witness_count=dead,
                    record_count=len(_items(variant, "record_refs")),
                    transition_count=len(_items(variant, "transitions")),
                    declared_hop_count=_int(variant, "declared_hop_count") or 0,
                    source_loss_state=source_loss_state,
                    record_backed=record_backed,
                    location_ids=locations,
                    variant_ids=(variant_id, *parent_ids),
                )
            )
    _LOG.debug(
        "generational_narrative_generation_rows row_count=%s ledger_count=%s",
        len(rows),
        len(tuple(ledgers or ())),
    )
    return tuple(rows)


def narrative_record_rows_from_ledgers(
    ledgers: Sequence[object] | None,
) -> tuple[NarrativeRecordRow, ...]:
    rows: list[NarrativeRecordRow] = []
    for ledger in ledgers or ():
        owner_value = _value(ledger, "owner_id")
        owner_id = getattr(owner_value, "value", owner_value)
        if not isinstance(owner_id, str) or not owner_id:
            continue
        for variant in _items(ledger, "variants"):
            variant_id = _text(variant, "variant_id")
            if variant_id is None:
                continue
            loss = _value(variant, "source_loss")
            state = None if loss is None else _text(loss, "state")
            for record in _items(variant, "record_refs"):
                record_id = _text(record, "record_id")
                role = _text(record, "role")
                observed_revision = _int(record, "observed_revision")
                tick = _int(record, "tick")
                if (
                    record_id is None
                    or role is None
                    or observed_revision is None
                    or tick is None
                ):
                    continue
                rows.append(
                    NarrativeRecordRow(
                        owner_id=owner_id,
                        variant_id=variant_id,
                        record_id=record_id,
                        role=role,
                        observed_revision=observed_revision,
                        copy_generation=_int(record, "copy_generation"),
                        integrity=_text(record, "integrity"),
                        annotation_revisions=_int(
                            record, "annotation_revisions"
                        ),
                        tick=tick,
                        source_loss_state=state,
                    )
                )
    _LOG.debug("generational_narrative_record_rows row_count=%s", len(rows))
    return tuple(rows)


def _record_integrity(
    records: Sequence[object],
) -> str:
    states: set[str] = set()
    for record in records:
        integrity = _text(record, "integrity")
        role = _text(record, "role")
        if role in {"damaged", "partially_lost"}:
            states.add("damaged")
        if role == "destroyed":
            states.add("destroyed")
        if integrity is not None:
            lowered = integrity.lower()
            if lowered in _DAMAGED_INTEGRITY:
                states.add("damaged")
            elif lowered in _DESTROYED_INTEGRITY:
                states.add("destroyed")
            elif lowered == "intact":
                states.add("intact")
    if "destroyed" in states:
        return "destroyed"
    if "damaged" in states:
        return "damaged"
    if "intact" in states:
        return "intact"
    return "none"


def narrative_source_loss_rows_from_ledgers(
    ledgers: Sequence[object] | None,
) -> tuple[NarrativeSourceLossRow, ...]:
    rows: list[NarrativeSourceLossRow] = []
    for ledger in ledgers or ():
        owner_value = _value(ledger, "owner_id")
        owner_id = getattr(owner_value, "value", owner_value)
        if not isinstance(owner_id, str) or not owner_id:
            continue
        for variant in _items(ledger, "variants"):
            variant_id = _text(variant, "variant_id")
            if variant_id is None:
                continue
            first_hand = [
                witness
                for witness in _items(variant, "source_witnesses")
                if _text(witness, "kind") == "first_hand"
            ]
            known = len(first_hand)
            dead = sum(
                1
                for witness in first_hand
                if _int(witness, "death_observed_tick") is not None
            )
            loss = _value(variant, "source_loss")
            state = "unknown" if loss is None else (_text(loss, "state") or "unknown")
            reason = "unknown" if loss is None else (
                _text(loss, "reason") or "unknown"
            )
            integrity = _record_integrity(_items(variant, "record_refs"))
            all_dead = known > 0 and dead == known
            objective_lost = all_dead and integrity != "intact"
            objective_state = "lost" if objective_lost else (
                "unknown" if known == 0 and integrity == "none" else "intact"
            )
            rows.append(
                NarrativeSourceLossRow(
                    owner_id=owner_id,
                    variant_id=variant_id,
                    subjective_state=state,
                    subjective_reason=reason,
                    objective_state=objective_state,
                    dead_witness_share=(0.0 if known == 0 else dead / known),
                    record_integrity=integrity,
                    all_witnesses_dead=all_dead,
                    record_backed=bool(_value(loss, "record_backed", False))
                    if loss
                    else False,
                )
            )
    _LOG.debug("generational_narrative_source_loss_rows row_count=%s", len(rows))
    return tuple(rows)


def _objective_event_rows(
    objective_events: Sequence[object] | None,
) -> dict[str, Mapping[str, object]]:
    by_event: dict[str, Mapping[str, object]] = {}
    for event in objective_events or ():
        if isinstance(event, Mapping):
            event_id = event.get("event_id")
        else:
            event_id = getattr(event, "event_id", None)
        event_id = getattr(event_id, "value", event_id)
        if isinstance(event_id, str) and event_id:
            if isinstance(event, Mapping):
                by_event[event_id] = event
            else:
                by_event[event_id] = {
                    "event_id": event_id,
                    "kind": getattr(event, "kind", None),
                    "actor_id": getattr(event, "actor_id", None),
                    "target_id": getattr(event, "target_id", None),
                    "location_id": getattr(event, "location_id", None),
                    "tick": getattr(event, "tick", None),
                }
    return by_event


def narrative_history_comparison_rows_from_rows(
    rows: Sequence[NarrativeGenerationRow],
    *,
    objective_events: Sequence[object] | None = None,
) -> tuple[NarrativeHistoryComparisonRow, ...]:
    by_event = _objective_event_rows(objective_events)
    comparisons: list[NarrativeHistoryComparisonRow] = []
    for row in rows:
        objective = (
            None
            if row.source_event_id is None
            else by_event.get(row.source_event_id)
        )
        actor = None if objective is None else objective.get("actor_id")
        target = None if objective is None else objective.get("target_id")
        location = None if objective is None else objective.get("location_id")
        actor = str(getattr(actor, "value", actor)) if actor is not None else None
        target = str(getattr(target, "value", target)) if target is not None else None
        location = (
            str(getattr(location, "value", location))
            if location is not None
            else None
        )
        objective_spec = None if objective is None else objective.get("kind")
        objective_kind = (
            objective_spec if isinstance(objective_spec, str) else None
        )
        objective_tick = (
            None if objective is None else objective.get("tick")
        )
        if isinstance(objective_tick, bool) or not isinstance(objective_tick, int):
            objective_tick = None
        narrative_tick = row.first_tick
        participant_tokens = set(row.carrier_agent_ids)
        objective_participants = {value for value in (actor, target) if value}
        participant_coverage = 0.0
        if objective_participants:
            participant_coverage = len(
                participant_tokens & objective_participants
            ) / len(objective_participants)
        location_agreement = (
            location is not None and location in set(row.location_ids)
        )
        tokens = participant_tokens | set(row.location_ids)
        objective_tokens = objective_participants | (
            {location} if location else set()
        )
        token_coverage = 0.0
        if objective_tokens:
            token_coverage = len(tokens & objective_tokens) / len(objective_tokens)
        temporal_distance = None
        if objective_tick is not None and narrative_tick is not None:
            temporal_distance = abs(objective_tick - narrative_tick)
        if objective is None or row.source_event_id is None:
            classification = "unverifiable"
        elif (
            temporal_distance is not None
            and temporal_distance <= GENERATIONAL_NARRATIVE_ALIGNMENT_WINDOW_TICKS
            and (participant_coverage > 0.0 or location_agreement)
        ):
            classification = "aligned"
        elif (
            temporal_distance is not None
            and temporal_distance <= GENERATIONAL_NARRATIVE_ALIGNMENT_WINDOW_TICKS
            and not objective_tokens
        ):
            classification = "partial"
        else:
            classification = "divergent"
        comparisons.append(
            NarrativeHistoryComparisonRow(
                owner_id=row.owner_id,
                variant_id=row.variant_id,
                source_event_id=row.source_event_id,
                objective_event_kind=objective_kind,
                actor_token=actor,
                target_token=target,
                location_token=location,
                objective_tick=objective_tick,
                narrative_tick=narrative_tick,
                token_coverage=quantize_float(token_coverage),
                participant_coverage=quantize_float(participant_coverage),
                location_agreement=location_agreement,
                temporal_distance=temporal_distance,
                classification=classification,
            )
        )
    _LOG.debug(
        "generational_narrative_comparison_rows row_count=%s", len(comparisons)
    )
    return tuple(comparisons)


def _historical_memory_transition_counts(
    harvest: object,
) -> tuple[tuple[str, int], ...]:
    from analysis.historical_memory import (
        HistoricalMemoryHarvest,
        HistoricalMemoryTransitionCause,
        materialize_historical_memory_from_harvest,
    )

    if type(harvest) is not HistoricalMemoryHarvest:
        return ()
    if harvest.layers_spec is None:
        return ()
    try:
        _, _, transitions, _ = materialize_historical_memory_from_harvest(harvest)
    except Exception:
        _LOG.warning(
            "generational_narrative_harvest_transition_failed reason=%s",
            "materialize_failed",
        )
        return ()
    counts: dict[str, int] = {}
    for transition in transitions:
        if transition.cause is HistoricalMemoryTransitionCause.GENERATION_BOUNDARY:
            counts["generation_boundary"] = counts.get("generation_boundary", 0) + 1
        elif (
            transition.cause
            is HistoricalMemoryTransitionCause.LAST_DIRECT_WITNESS_DIED
        ):
            counts["last_direct_witness_died"] = (
                counts.get("last_direct_witness_died", 0) + 1
            )
    return tuple(sorted(counts.items()))


def generational_narrative_inputs_from_harvest(
    harvest: object,
    *,
    objective_events: Sequence[object] | None = None,
) -> GenerationalNarrativeInputs:
    ledgers = _items(harvest, "cultural_narrative_ledgers")
    if not ledgers:
        ledgers = _items(harvest, "narrative_ledgers")
    generation_map = _value(harvest, "generation_index_by_agent")
    if not isinstance(generation_map, Mapping):
        generation_map = None
    generation_rows = narrative_generation_rows_from_ledgers(
        ledgers, generation_index_by_agent=generation_map
    )
    if objective_events is None:
        objective_events = _items(harvest, "died_events")
    comparison_rows = narrative_history_comparison_rows_from_rows(
        generation_rows, objective_events=objective_events
    )
    gaps: list[str] = []
    if generation_map is None:
        gaps.append("generation_index_map_missing")
    if not objective_events:
        gaps.append("objective_events_missing")
    _LOG.info(
        "generational_narrative_harvest generation_rows=%s record_rows=%s "
        "source_loss_rows=%s comparison_rows=%s coverage_gap_count=%s",
        len(generation_rows),
        len(narrative_record_rows_from_ledgers(ledgers)),
        len(narrative_source_loss_rows_from_ledgers(ledgers)),
        len(comparison_rows),
        len(gaps),
    )
    return GenerationalNarrativeInputs(
        generation_rows=generation_rows,
        record_rows=narrative_record_rows_from_ledgers(ledgers),
        source_loss_rows=narrative_source_loss_rows_from_ledgers(ledgers),
        comparison_rows=comparison_rows,
        transition_counts=_historical_memory_transition_counts(harvest),
        coverage_gaps=tuple(gaps),
    )


def _mean(values: Sequence[float]) -> float | None:
    if not values:
        return None
    return quantize_float(sum(values) / len(values))


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return quantize_float(numerator / denominator)


def _document(
    *,
    family: MetricFamilyId,
    run_id: str,
    input_revision: str,
    availability: MetricAvailability,
    values: Mapping[str, object],
    observed: int = 0,
    expected: int = 0,
    notes_code: str,
) -> MetricDocument:
    spec = metric_specification(family)
    coverage = None
    if availability is MetricAvailability.PRESENT:
        coverage = MetricCoverage(observed=observed, expected=max(expected, observed))
    return MetricDocument(
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        metric_family=spec.family_id.value,
        algorithm_version=spec.algorithm_version,
        library_versions=library_versions(),
        run_id=run_id,
        input_revision=input_revision,
        evidence_stages=frozenset(spec.evidence_inputs),
        population=spec.population,
        denominator=spec.denominator,
        coverage=coverage,
        availability=availability,
        values=dict(values),
        provenance=MetricProvenance(
            source_kind=family.value,
            source_ids=() if availability is MetricAvailability.ABSENT else (run_id,),
            notes_code=notes_code,
        ),
    )


def _active(rows: Sequence[NarrativeGenerationRow]) -> list[NarrativeGenerationRow]:
    return [row for row in rows if row.status == "active"]


def compute_generational_narrative_continuity(
    rows: Sequence[NarrativeGenerationRow] | None,
    *,
    run_id: str,
    input_revision: str,
    tick: int = 0,
    transition_counts: Sequence[tuple[str, int]] = (),
) -> MetricDocument:
    run_id = require_stable_id("run_id", run_id)
    input_revision = require_stable_id("input_revision", input_revision)
    require_exact_nonneg_int("tick", tick)
    active = _active(tuple(rows or ()))
    if not active:
        _LOG.info(
            "generational_narrative_continuity_metric_run run_id=%s "
            "availability=%s",
            run_id,
            _ABSENT,
        )
        return _document(
            family=MetricFamilyId.GENERATIONAL_NARRATIVE_CONTINUITY,
            run_id=run_id,
            input_revision=input_revision,
            availability=MetricAvailability.ABSENT,
            values={},
            notes_code="empty_rows",
        )
    spans = [
        float(row.generation_span)
        for row in active
        if row.generation_span is not None
    ]
    multi_generation = sum(1 for value in spans if value >= 1)
    first_hand = [row for row in active if row.witness_count > 0]
    retold = sum(
        1
        for row in first_hand
        if row.transition_count > 0 and row.declared_hop_count > 0
    )
    all_dead = [
        row
        for row in active
        if row.witness_count > 0
        and row.dead_witness_count == row.witness_count
    ]
    all_dead_survived = sum(1 for row in all_dead if row.carrier_agent_ids)
    record_backed = [row for row in active if row.record_backed]
    theme_counts: dict[str, int] = {}
    for row in active:
        for theme in row.themes:
            theme_counts[theme] = theme_counts.get(theme, 0) + 1
    values: dict[str, object] = {
        "active_lineage_count": len(active),
        "mean_generation_span": _ABSENT if not spans else _mean(spans),
        "max_generation_span": _ABSENT if not spans else max(spans),
        "multi_generation_lineage_rate": (
            _ABSENT if not spans else _rate(multi_generation, len(spans))
        ),
        "first_hand_to_retold_rate": (
            _ABSENT if not first_hand else _rate(retold, len(first_hand))
        ),
        "all_witnesses_dead_survival_rate": (
            _ABSENT
            if not all_dead
            else _rate(all_dead_survived, len(all_dead))
        ),
        "record_backed_survival_rate": (
            _ABSENT
            if not record_backed
            else _rate(
                sum(1 for row in record_backed if row.carrier_agent_ids),
                len(record_backed),
            )
        ),
        "mean_carrier_turnover": _mean(
            [float(len(row.carrier_agent_ids)) for row in active]
        ),
        "mean_provenance_hops": _mean(
            [float(row.declared_hop_count) for row in active]
        ),
        "theme_counts": ";".join(
            f"{name}:{count}" for name, count in sorted(theme_counts.items())
        ),
        "generation_boundary_transition_count": dict(transition_counts).get(
            "generation_boundary", 0
        ),
        "last_direct_witness_death_transition_count": dict(
            transition_counts
        ).get("last_direct_witness_died", 0),
    }
    _LOG.info(
        "generational_narrative_continuity_metric_run run_id=%s "
        "availability=%s active_lineage_count=%s",
        run_id,
        MetricAvailability.PRESENT.value,
        len(active),
    )
    return _document(
        family=MetricFamilyId.GENERATIONAL_NARRATIVE_CONTINUITY,
        run_id=run_id,
        input_revision=input_revision,
        availability=MetricAvailability.PRESENT,
        values=values,
        observed=len(active),
        expected=len(active),
        notes_code="detached_ledgers",
    )


def compute_narrative_source_loss(
    rows: Sequence[NarrativeSourceLossRow] | None,
    *,
    run_id: str,
    input_revision: str,
    tick: int = 0,
) -> MetricDocument:
    run_id = require_stable_id("run_id", run_id)
    input_revision = require_stable_id("input_revision", input_revision)
    require_exact_nonneg_int("tick", tick)
    items = tuple(rows or ())
    if not items:
        return _document(
            family=MetricFamilyId.NARRATIVE_SOURCE_LOSS,
            run_id=run_id,
            input_revision=input_revision,
            availability=MetricAvailability.ABSENT,
            values={},
            notes_code="empty_rows",
        )
    loss_numerator = sum(1 for row in items if row.subjective_state == "lost")
    objective_numerator = sum(1 for row in items if row.objective_state == "lost")
    state_counts: dict[str, int] = {}
    reason_counts: dict[str, int] = {}
    for row in items:
        state_counts[row.subjective_state] = (
            state_counts.get(row.subjective_state, 0) + 1
        )
        reason_counts[row.subjective_reason] = (
            reason_counts.get(row.subjective_reason, 0) + 1
        )
    values: dict[str, object] = {
        "subjective_source_loss_rate": _rate(loss_numerator, len(items)),
        "objective_source_loss_rate": _rate(objective_numerator, len(items)),
        "mean_dead_witness_share": _mean(
            [row.dead_witness_share for row in items]
        ),
        "all_witnesses_dead_count": sum(
            1 for row in items if row.all_witnesses_dead
        ),
        "record_backed_count": sum(1 for row in items if row.record_backed),
        "reason_counts": ";".join(
            f"{name}:{count}" for name, count in sorted(reason_counts.items())
        ),
        "state_counts": ";".join(
            f"{name}:{count}" for name, count in sorted(state_counts.items())
        ),
    }
    _LOG.info(
        "narrative_source_loss_metric_run run_id=%s state_count=%s",
        run_id,
        len(items),
    )
    return _document(
        family=MetricFamilyId.NARRATIVE_SOURCE_LOSS,
        run_id=run_id,
        input_revision=input_revision,
        availability=MetricAvailability.PRESENT,
        values=values,
        observed=len(items),
        expected=len(items),
        notes_code="subjective_vs_objective",
    )


def compute_narrative_historical_alignment(
    rows: Sequence[NarrativeHistoryComparisonRow] | None,
    *,
    run_id: str,
    input_revision: str,
    tick: int = 0,
) -> MetricDocument:
    run_id = require_stable_id("run_id", run_id)
    input_revision = require_stable_id("input_revision", input_revision)
    require_exact_nonneg_int("tick", tick)
    items = tuple(rows or ())
    if not items:
        return _document(
            family=MetricFamilyId.NARRATIVE_HISTORICAL_ALIGNMENT,
            run_id=run_id,
            input_revision=input_revision,
            availability=MetricAvailability.ABSENT,
            values={},
            notes_code="empty_rows",
        )
    verifiable = [row for row in items if row.classification != "unverifiable"]
    counts = {name: 0 for name in _ALIGNMENT_CLASSES}
    for row in items:
        counts[row.classification] = counts.get(row.classification, 0) + 1
    distances = [
        float(row.temporal_distance)
        for row in items
        if row.temporal_distance is not None
    ]
    with_location = [row for row in items if row.location_token is not None]
    source_event_coverage = _rate(
        sum(1 for row in items if row.source_event_id is not None), len(items)
    )
    participant_coverage = _mean([row.participant_coverage for row in items])
    values: dict[str, object] = {
        "source_event_coverage": source_event_coverage,
        "participant_coverage": participant_coverage,
        "location_agreement": (
            _ABSENT
            if not with_location
            else _rate(
                sum(1 for row in with_location if row.location_agreement),
                len(with_location),
            )
        ),
        "mean_temporal_distance": _ABSENT if not distances else _mean(distances),
        "aligned_rate": (
            _ABSENT
            if not verifiable
            else _rate(counts["aligned"], len(verifiable))
        ),
        "partial_rate": (
            _ABSENT
            if not verifiable
            else _rate(counts["partial"], len(verifiable))
        ),
        "divergent_rate": (
            _ABSENT
            if not verifiable
            else _rate(counts["divergent"], len(verifiable))
        ),
        "unverifiable_rate": _rate(counts["unverifiable"], len(items)),
    }
    _LOG.info(
        "narrative_historical_alignment_metric_run run_id=%s claim_count=%s "
        "verifiable_count=%s",
        run_id,
        len(items),
        len(verifiable),
    )
    return _document(
        family=MetricFamilyId.NARRATIVE_HISTORICAL_ALIGNMENT,
        run_id=run_id,
        input_revision=input_revision,
        availability=MetricAvailability.PRESENT,
        values=values,
        observed=len(verifiable),
        expected=len(items),
        notes_code="analysis_only_classification",
    )
