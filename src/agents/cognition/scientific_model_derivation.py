"""Owner-safe derivation of scientific-model hypotheses from observations.

Every adapter reads only detached owner-visible facts. No adapter receives the
environmental dynamics spec, a production catalog, world state, event
repositories, or objective law rows.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import replace
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Final

from agents.cognition.experimentation import (
    ExperimentHypothesis,
    ExperimentLedger,
    HypothesisStatus,
    derive_hypothesis_status,
)
from agents.cognition.scientific_models import (
    MAX_DERIVATION_SAMPLES,
    MAX_HYPOTHESIS_REVISIONS,
    SEASON_CLASSES,
    DerivationSample,
    ModelCondition,
    ModelHypothesis,
    ModelHypothesisRevision,
    ModelLifecycle,
    ModelRevisionReason,
    ModelSourceClaim,
    ModelSourceKind,
    ModelTargetKind,
    ScientificModelLedger,
    bump_notice,
    scientific_hypothesis_id,
)
from world.experimentation import ExperimentOutcomeClass, ExperimentProcessToken
from world.identifiers import AgentId, require_stable_id

__all__ = [
    "ELIGIBLE_PRODUCTION_PROCESSES",
    "derive_model_hypotheses",
    "quantity_milli",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "agents.cognition.scientific_model_derivation"
)

ELIGIBLE_PRODUCTION_PROCESSES: Final[frozenset[ExperimentProcessToken]] = frozenset(
    {
        ExperimentProcessToken.HARVEST,
        ExperimentProcessToken.CRAFT,
        ExperimentProcessToken.BUILD,
        ExperimentProcessToken.REPAIR,
        ExperimentProcessToken.STORE,
    }
)

_RESOURCE_CLASSES: Final[tuple[str, ...]] = ("decrease", "unchanged", "increase")


def _digest(*parts: str) -> str:
    material = "|".join(parts)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]


def _fail(field_name: str, reason: str) -> ValueError:
    return ValueError(f"{field_name}: {reason}")


def quantity_milli(quantity: float) -> int:
    """Convert one observed quantity to milli-units with half-even rounding."""

    if isinstance(quantity, bool) or not isinstance(quantity, (int, float)):
        raise _fail("quantity", "invalid_type")
    number = float(quantity)
    if number != number or number in (float("inf"), float("-inf")) or number < 0:
        raise _fail("quantity", "invalid_range")
    return int(
        (Decimal(str(quantity)) * 1000).to_integral_value(rounding=ROUND_HALF_EVEN)
    )


def _conditions_from_observation(observation: object) -> tuple[ModelCondition, ...]:
    rows: list[ModelCondition] = []
    season = getattr(observation, "season", None)
    if season is not None:
        rows.append(ModelCondition("season", str(getattr(season, "value", season))))
    self_body = getattr(observation, "self_body", None)
    location_id = getattr(self_body, "location_id", None)
    if location_id is not None:
        rows.append(
            ModelCondition(
                "location", str(getattr(location_id, "value", location_id))
            )
        )
    return tuple(sorted(rows, key=lambda row: row.slot))


def _production_conditions(
    observation: object,
) -> tuple[ModelCondition, ...]:
    rows = list(_conditions_from_observation(observation))
    weather = getattr(observation, "weather_condition", None)
    if weather is not None:
        rows.append(ModelCondition("weather", str(getattr(weather, "value", weather))))
    day_phase = getattr(observation, "day_phase", None)
    if day_phase is not None:
        rows.append(
            ModelCondition("day_phase", str(getattr(day_phase, "value", day_phase)))
        )
    return tuple(sorted(rows, key=lambda row: row.slot))


def _append_hypothesis_revision(
    hypothesis: ModelHypothesis,
    *,
    tick: int,
    reason: ModelRevisionReason,
    predicted_class: str,
    conditions: tuple[ModelCondition, ...],
    source_revision_ref: str,
    support_refs: tuple[str, ...] = (),
    contradiction_refs: tuple[str, ...] = (),
) -> ModelHypothesis:
    if len(hypothesis.revisions) >= MAX_HYPOTHESIS_REVISIONS:
        return hypothesis
    revision = ModelHypothesisRevision(
        revision_index=len(hypothesis.revisions),
        tick=tick,
        reason=reason,
        conditions=conditions,
        predicted_class=predicted_class,
        source_revision_ref=source_revision_ref,
        support_refs=support_refs[:64],
        contradiction_refs=contradiction_refs[:64],
    )
    return replace(hypothesis, revisions=(*hypothesis.revisions, revision))


def _upsert_hypothesis(
    ledger: ScientificModelLedger,
    *,
    hypothesis_id: str,
    target_kind: ModelTargetKind,
    target_ref: str,
    unit_token: str,
    horizon_ticks: int,
    source_kind: ModelSourceKind,
    source_refs: tuple[str, ...],
    predicted_class: str,
    source_claim: ModelSourceClaim | None = None,
    conditions: tuple[ModelCondition, ...],
    source_revision_ref: str,
    support_refs: tuple[str, ...],
    tick: int,
    causal_link_ref: str = "",
) -> ScientificModelLedger:
    existing = next(
        (row for row in ledger.hypotheses if row.hypothesis_id == hypothesis_id),
        None,
    )
    if existing is not None and existing.lifecycle is ModelLifecycle.RETIRED:
        return ledger
    if existing is None:
        if len(ledger.hypotheses) >= 32:
            return replace(
                ledger,
                notices=bump_notice(
                    ledger.notices,
                    reason_code="hypothesis_cap",
                    target_kind=target_kind,
                    tick=tick,
                ),
            )
        hypothesis = ModelHypothesis(
            owner_id=ledger.owner_id,
            hypothesis_id=hypothesis_id,
            target_kind=target_kind,
            target_ref=target_ref,
            unit_token=unit_token,
            horizon_ticks=horizon_ticks,
            source_kind=source_kind,
            source_refs=source_refs[:8],
            source_claim=source_claim,
            revisions=(
                ModelHypothesisRevision(
                    revision_index=0,
                    tick=tick,
                    reason=ModelRevisionReason.FORMULATED,
                    conditions=conditions,
                    predicted_class=predicted_class,
                    source_revision_ref=source_revision_ref,
                    support_refs=support_refs[:64],
                ),
            ),
            lifecycle=ModelLifecycle.ACTIVE,
            created_tick=tick,
            sequence=ledger.hypothesis_sequence,
            causal_link_ref=causal_link_ref,
        )
        return replace(
            ledger,
            hypotheses=(*ledger.hypotheses, hypothesis),
            sequence=ledger.sequence + 1,
            hypothesis_sequence=ledger.hypothesis_sequence + 1,
        )
    current = existing.current_revision
    unchanged = (
        current.predicted_class == predicted_class
        and current.conditions == conditions
        and current.source_revision_ref == source_revision_ref
    )
    if unchanged and existing.lifecycle is ModelLifecycle.ACTIVE:
        return ledger
    reason = (
        ModelRevisionReason.SOURCE_CHANGED
        if current.source_revision_ref != source_revision_ref
        else ModelRevisionReason.PARAMETER_UPDATED
    )
    updated = _append_hypothesis_revision(
        existing,
        tick=tick,
        reason=reason,
        predicted_class=predicted_class,
        conditions=conditions,
        source_revision_ref=source_revision_ref,
        support_refs=support_refs,
    )
    if updated.lifecycle is ModelLifecycle.SUSPENDED:
        updated = _set_lifecycle(
            updated,
            tick=tick,
            lifecycle=ModelLifecycle.ACTIVE,
            reason=ModelRevisionReason.RESUMED,
            predicted_class=predicted_class,
            conditions=conditions,
            source_revision_ref=source_revision_ref,
        )
    rows = tuple(
        updated if row.hypothesis_id == hypothesis_id else row
        for row in ledger.hypotheses
    )
    return replace(ledger, hypotheses=rows)


def _set_lifecycle(
    hypothesis: ModelHypothesis,
    *,
    tick: int,
    lifecycle: ModelLifecycle,
    reason: ModelRevisionReason,
    predicted_class: str | None = None,
    conditions: tuple[ModelCondition, ...] | None = None,
    source_revision_ref: str | None = None,
) -> ModelHypothesis:
    if hypothesis.lifecycle is lifecycle:
        return hypothesis
    current = hypothesis.current_revision
    assert current.predicted_class is not None
    updated = _append_hypothesis_revision(
        replace(hypothesis, lifecycle=lifecycle),
        tick=tick,
        reason=reason,
        predicted_class=(
            current.predicted_class if predicted_class is None else predicted_class
        ),
        conditions=current.conditions if conditions is None else conditions,
        source_revision_ref=(
            current.source_revision_ref
            if source_revision_ref is None
            else source_revision_ref
        ),
    )
    return replace(updated, lifecycle=lifecycle)


def _sample_id(
    owner_id: AgentId,
    target_kind: ModelTargetKind,
    target_ref: str,
    tick: int,
) -> str:
    return "smd:" + _digest(owner_id.value, target_kind.value, target_ref, str(tick))


def _retain_samples(
    ledger: ScientificModelLedger,
    additions: list[DerivationSample],
) -> ScientificModelLedger:
    if not additions:
        return ledger
    existing_ids = {row.sample_id for row in ledger.samples}
    rows = list(ledger.samples)
    notice = ledger.notices
    for sample in additions:
        if sample.sample_id in existing_ids:
            continue
        rows.append(sample)
        existing_ids.add(sample.sample_id)
    if len(rows) > MAX_DERIVATION_SAMPLES:
        rows.sort(key=lambda row: (row.observed_tick, row.sample_id))
        rows = rows[-MAX_DERIVATION_SAMPLES:]
        notice = bump_notice(
            notice,
            reason_code="sample_cap",
            target_kind=ModelTargetKind.SEASON,
            tick=rows[-1].observed_tick if rows else 0,
        )
    return replace(ledger, samples=tuple(rows), notices=notice)


def _season_samples(ledger: ScientificModelLedger) -> list[DerivationSample]:
    return sorted(
        (row for row in ledger.samples if row.target_kind is ModelTargetKind.SEASON),
        key=lambda row: (row.observed_tick, row.sample_id),
    )


def _derive_season(
    ledger: ScientificModelLedger, *, tick: int
) -> ScientificModelLedger:
    samples = _season_samples(ledger)
    by_key = {(row.observed_tick, row.location_ref): row for row in samples}
    pairs: dict[str, list[tuple[DerivationSample, DerivationSample]]] = {}
    for start in samples:
        middle = by_key.get((start.observed_tick + 1, start.location_ref))
        end = by_key.get((start.observed_tick + 2, start.location_ref))
        if middle is None or end is None:
            continue
        if start.observed_class is None or end.observed_class is None:
            continue
        pairs.setdefault(start.observed_class, []).append((start, end))
    order = {name: index for index, name in enumerate(SEASON_CLASSES)}
    for start_class, rows in sorted(pairs.items()):
        if len(rows) < 2:
            continue
        counts: dict[str, int] = {}
        for _, end in rows:
            assert end.observed_class is not None
            counts[end.observed_class] = counts.get(end.observed_class, 0) + 1
        modal = min(
            counts,
            key=lambda name: (-counts[name], order.get(name, len(order))),
        )
        start = rows[0][0]
        hypothesis_id = scientific_hypothesis_id(
            ledger.owner_id,
            ModelTargetKind.SEASON,
            f"season:{start_class}",
            "season",
            2,
            ModelSourceKind.OBSERVED_REGULARITY,
        )
        ledger = _upsert_hypothesis(
            ledger,
            hypothesis_id=hypothesis_id,
            target_kind=ModelTargetKind.SEASON,
            target_ref=f"season:{start_class}",
            unit_token="season",
            horizon_ticks=2,
            source_kind=ModelSourceKind.OBSERVED_REGULARITY,
            source_refs=tuple(sample.sample_id for pair in rows[:4] for sample in pair),
            predicted_class=modal,
            conditions=start.conditions,
            source_revision_ref="pairs:"
            + _digest(*sorted(sample.sample_id for pair in rows for sample in pair)),
            support_refs=tuple(sample.sample_id for pair in rows for sample in pair),
            tick=tick,
        )
    return ledger


def _resource_identity(sample: DerivationSample) -> tuple[str, str, str]:
    return sample.target_ref, sample.unit_token, sample.location_ref


def _resource_change(start: int, end: int) -> str:
    if end < start:
        return _RESOURCE_CLASSES[0]
    if end > start:
        return _RESOURCE_CLASSES[2]
    return _RESOURCE_CLASSES[1]


def _derive_resource(
    ledger: ScientificModelLedger, *, tick: int
) -> ScientificModelLedger:
    samples = sorted(
        (
            row
            for row in ledger.samples
            if row.target_kind is ModelTargetKind.RESOURCE_REGENERATION
            and row.quantity_milli is not None
        ),
        key=lambda row: (row.observed_tick, row.sample_id),
    )
    by_key = {(row.observed_tick, *_resource_identity(row)): row for row in samples}
    pairs: dict[
        tuple[str, str, str], list[tuple[DerivationSample, DerivationSample]]
    ] = {}
    for start in samples:
        identity = _resource_identity(start)
        middle = by_key.get((start.observed_tick + 1, *identity))
        end = by_key.get((start.observed_tick + 2, *identity))
        if middle is None or end is None:
            continue
        pairs.setdefault(identity, []).append((start, end))
    for identity, rows in sorted(pairs.items()):
        if len(rows) < 2:
            continue
        counts: dict[str, int] = {}
        for start, end in rows:
            assert start.quantity_milli is not None
            assert end.quantity_milli is not None
            change = _resource_change(start.quantity_milli, end.quantity_milli)
            counts[change] = counts.get(change, 0) + 1
        modal = min(
            counts,
            key=lambda name: (-counts[name], _RESOURCE_CLASSES.index(name)),
        )
        target_ref, unit_token, location_ref = identity
        start = rows[0][0]
        hypothesis_id = scientific_hypothesis_id(
            ledger.owner_id,
            ModelTargetKind.RESOURCE_REGENERATION,
            f"{target_ref}:{location_ref}",
            unit_token,
            2,
            ModelSourceKind.OBSERVED_REGULARITY,
        )
        ledger = _upsert_hypothesis(
            ledger,
            hypothesis_id=hypothesis_id,
            target_kind=ModelTargetKind.RESOURCE_REGENERATION,
            target_ref=f"{target_ref}:{location_ref}",
            unit_token=unit_token,
            horizon_ticks=2,
            source_kind=ModelSourceKind.OBSERVED_REGULARITY,
            source_refs=tuple(sample.sample_id for pair in rows[:4] for sample in pair),
            predicted_class=modal,
            conditions=start.conditions,
            source_revision_ref="pairs:"
            + _digest(*sorted(sample.sample_id for pair in rows for sample in pair)),
            support_refs=tuple(sample.sample_id for pair in rows for sample in pair),
            tick=tick,
        )
    return ledger


def _production_source_ref(hypothesis: ExperimentHypothesis) -> str:
    return "exp:" + _digest(
        hypothesis.hypothesis_id,
        hypothesis.operator.value,
        hypothesis.operand_a_id,
        hypothesis.operand_b_id or "",
        hypothesis.process_token.value,
        hypothesis.predicted_outcome or "",
        *sorted(f"{row.slot.value}={row.value_token}" for row in hypothesis.conditions),
    )


def _eligible_production_sources(
    owner_id: AgentId, experiment_ledger: ExperimentLedger
) -> dict[str, ExperimentHypothesis]:
    sources: dict[str, ExperimentHypothesis] = {}
    for hypothesis in experiment_ledger.hypotheses:
        if type(hypothesis) is not ExperimentHypothesis:
            continue
        if hypothesis.owner_id != owner_id:
            continue
        if not hypothesis.active:
            continue
        status = hypothesis.status or derive_hypothesis_status(
            hypothesis.support, hypothesis.counter
        )
        if status in {HypothesisStatus.RETIRED, HypothesisStatus.SUPERSEDED}:
            continue
        if hypothesis.predicted_outcome is None:
            continue
        if hypothesis.process_token not in ELIGIBLE_PRODUCTION_PROCESSES:
            continue
        if hypothesis.predicted_outcome not in {
            item.value for item in ExperimentOutcomeClass
        }:
            continue
        sources[hypothesis.hypothesis_id] = hypothesis
    return sources


def _retired_source_ids(
    owner_id: AgentId, experiment_ledger: ExperimentLedger
) -> frozenset[str]:
    retired: set[str] = set()
    for hypothesis in experiment_ledger.hypotheses:
        if hypothesis.owner_id != owner_id:
            continue
        status = hypothesis.status or derive_hypothesis_status(
            hypothesis.support, hypothesis.counter
        )
        if status in {HypothesisStatus.RETIRED, HypothesisStatus.SUPERSEDED}:
            retired.add(hypothesis.hypothesis_id)
    return frozenset(retired)


def _successor_link(
    ledger: ScientificModelLedger, predicted_class: str
) -> str:
    candidates = [
        row
        for row in ledger.hypotheses
        if row.lifecycle is ModelLifecycle.RETIRED
        and row.target_kind is ModelTargetKind.PRODUCTION_OUTCOME
        and row.predicted_class == predicted_class
    ]
    if not candidates:
        return ""
    return max(candidates, key=lambda row: row.created_tick).hypothesis_id


def _derive_production(
    ledger: ScientificModelLedger,
    *,
    tick: int,
    conditions: tuple[ModelCondition, ...],
    experiment_ledger: ExperimentLedger,
) -> ScientificModelLedger:
    sources = _eligible_production_sources(ledger.owner_id, experiment_ledger)
    for source_id, source in sorted(sources.items()):
        assert source.predicted_outcome is not None
        ledger = _upsert_hypothesis(
            ledger,
            hypothesis_id=scientific_hypothesis_id(
                ledger.owner_id,
                ModelTargetKind.PRODUCTION_OUTCOME,
                source_id,
                "outcome_class",
                2,
                ModelSourceKind.EXPERIMENT_HYPOTHESIS,
            ),
            target_kind=ModelTargetKind.PRODUCTION_OUTCOME,
            target_ref=source_id,
            unit_token="outcome_class",
            horizon_ticks=2,
            source_kind=ModelSourceKind.EXPERIMENT_HYPOTHESIS,
            source_refs=(source_id,),
            predicted_class=source.predicted_outcome,
            source_claim=ModelSourceClaim(
                operator=source.operator,
                operand_a_id=source.operand_a_id,
                operand_b_id=source.operand_b_id,
                process_token=source.process_token,
            ),
            conditions=conditions,
            source_revision_ref=_production_source_ref(source),
            support_refs=source.evidence_event_ids[:8],
            tick=tick,
            causal_link_ref=_successor_link(ledger, source.predicted_outcome),
        )
    return ledger


def _reconcile(
    ledger: ScientificModelLedger,
    *,
    tick: int,
    observation: object,
    experiment_ledger: ExperimentLedger,
) -> ScientificModelLedger:
    current_season = getattr(observation, "season", None)
    location_ref = self_location(observation)
    resource_targets = {
        f"{resource.entity_id}:{location_ref}"
        for resource in getattr(observation, "resources", ())
    }
    sources = _eligible_production_sources(ledger.owner_id, experiment_ledger)
    retired_sources = _retired_source_ids(ledger.owner_id, experiment_ledger)
    rows: list[ModelHypothesis] = []
    notices = ledger.notices
    for hypothesis in ledger.hypotheses:
        lifecycle = hypothesis.lifecycle
        reason_code: str | None = None
        if hypothesis.target_kind is ModelTargetKind.PRODUCTION_OUTCOME:
            if hypothesis.target_ref in retired_sources:
                if lifecycle is not ModelLifecycle.RETIRED:
                    hypothesis = _set_lifecycle(
                        hypothesis,
                        tick=tick,
                        lifecycle=ModelLifecycle.RETIRED,
                        reason=ModelRevisionReason.RETIRED,
                    )
            elif hypothesis.target_ref in sources:
                if lifecycle is ModelLifecycle.SUSPENDED:
                    hypothesis = _set_lifecycle(
                        hypothesis,
                        tick=tick,
                        lifecycle=ModelLifecycle.ACTIVE,
                        reason=ModelRevisionReason.RESUMED,
                    )
            elif lifecycle is not ModelLifecycle.RETIRED:
                hypothesis = _set_lifecycle(
                    hypothesis,
                    tick=tick,
                    lifecycle=ModelLifecycle.SUSPENDED,
                    reason=ModelRevisionReason.SUSPENDED,
                )
                reason_code = "source_missing"
        elif hypothesis.target_kind is ModelTargetKind.SEASON:
            if current_season is None:
                if lifecycle is not ModelLifecycle.RETIRED:
                    hypothesis = _set_lifecycle(
                        hypothesis,
                        tick=tick,
                        lifecycle=ModelLifecycle.SUSPENDED,
                        reason=ModelRevisionReason.SUSPENDED,
                    )
                reason_code = "observation_source_missing"
            elif lifecycle is ModelLifecycle.SUSPENDED:
                hypothesis = _set_lifecycle(
                    hypothesis,
                    tick=tick,
                    lifecycle=ModelLifecycle.ACTIVE,
                    reason=ModelRevisionReason.RESUMED,
                )
        elif hypothesis.target_kind is ModelTargetKind.RESOURCE_REGENERATION:
            if hypothesis.target_ref not in resource_targets:
                if lifecycle is not ModelLifecycle.RETIRED:
                    hypothesis = _set_lifecycle(
                        hypothesis,
                        tick=tick,
                        lifecycle=ModelLifecycle.SUSPENDED,
                        reason=ModelRevisionReason.SUSPENDED,
                    )
                reason_code = "observation_source_missing"
            elif lifecycle is ModelLifecycle.SUSPENDED:
                hypothesis = _set_lifecycle(
                    hypothesis,
                    tick=tick,
                    lifecycle=ModelLifecycle.ACTIVE,
                    reason=ModelRevisionReason.RESUMED,
                )
        rows.append(hypothesis)
        if reason_code is not None:
            notices = bump_notice(
                notices,
                reason_code=reason_code,
                target_kind=hypothesis.target_kind,
                tick=tick,
            )
    return replace(ledger, hypotheses=tuple(rows), notices=notices)


def self_location(observation: object) -> str:
    self_body = getattr(observation, "self_body", None)
    location_id = getattr(self_body, "location_id", None)
    if location_id is None:
        return "unknown"
    return str(getattr(location_id, "value", location_id))


def derive_model_hypotheses(
    ledger: ScientificModelLedger,
    observation: object,
    *,
    experiment_ledger: ExperimentLedger,
    causal_world_model: object | None = None,
) -> ScientificModelLedger:
    """Retain owner-visible samples and reconcile predictive hypotheses.

    Repeated observation keys are an exact no-op; a strictly older key fails
    closed. The causal world model is accepted as optional provenance only and
    its internal state is never read as a predictive target.
    """

    if type(ledger) is not ScientificModelLedger:
        raise _fail("ledger", "invalid_type")
    if type(experiment_ledger) is not ExperimentLedger:
        raise _fail("experiment_ledger", "invalid_type")
    if experiment_ledger.owner_id != ledger.owner_id:
        raise _fail("experiment_ledger", "owner_mismatch")
    # The trusted loop supplies only this owner's detached observation.
    tick = getattr(observation, "tick", None)
    if isinstance(tick, bool) or type(tick) is not int or tick < 0:
        raise _fail("observation", "invalid_tick")
    observation_key = require_stable_id("observation_key", f"tick:{tick}")
    if ledger.last_observation_key == observation_key:
        return ledger
    if ledger.last_observation_key and tick <= ledger.last_observation_tick:
        raise _fail("observation_key", "out_of_order")

    conditions = _conditions_from_observation(observation)
    location_ref = self_location(observation)
    additions: list[DerivationSample] = []
    season = getattr(observation, "season", None)
    if season is not None:
        additions.append(
            DerivationSample(
                sample_id=_sample_id(
                    ledger.owner_id, ModelTargetKind.SEASON, "season", tick
                ),
                target_kind=ModelTargetKind.SEASON,
                target_ref="season",
                unit_token="season",
                observed_tick=tick,
                observation_key=observation_key,
                location_ref=location_ref,
                observed_class=str(getattr(season, "value", season)),
                conditions=conditions,
            )
        )
    for resource in getattr(observation, "resources", ()):
        entity_id = getattr(resource, "entity_id", None)
        unit = getattr(resource, "unit", None)
        quantity = getattr(resource, "quantity", None)
        if entity_id is None or not isinstance(unit, str) or quantity is None:
            continue
        target_ref = str(entity_id)
        additions.append(
            DerivationSample(
                sample_id=_sample_id(
                    ledger.owner_id,
                    ModelTargetKind.RESOURCE_REGENERATION,
                    target_ref,
                    tick,
                ),
                target_kind=ModelTargetKind.RESOURCE_REGENERATION,
                target_ref=target_ref,
                unit_token=unit,
                observed_tick=tick,
                observation_key=observation_key,
                location_ref=location_ref,
                quantity_milli=quantity_milli(quantity),
                kind_token=str(getattr(resource.kind, "value", "")),
                conditions=conditions,
            )
        )

    updated = replace(
        ledger,
        last_observation_key=observation_key,
        last_observation_tick=tick,
    )
    updated = _retain_samples(updated, additions)
    updated = _derive_season(updated, tick=tick)
    updated = _derive_resource(updated, tick=tick)
    updated = _derive_production(
        updated,
        tick=tick,
        conditions=_production_conditions(observation),
        experiment_ledger=experiment_ledger,
    )
    updated = _reconcile(
        updated,
        tick=tick,
        observation=observation,
        experiment_ledger=experiment_ledger,
    )
    updated = replace(
        updated,
        notices=bump_notice(
            updated.notices,
            reason_code="disease_unavailable_no_observable",
            target_kind=ModelTargetKind.DISEASE_RISK,
            tick=tick,
        ),
    )
    _LOG.debug(
        "scientific_model_derivation tick=%s hypothesis_count=%s sample_count=%s "
        "causal_link_present=%s",
        tick,
        len(updated.hypotheses),
        len(updated.samples),
        causal_world_model is not None,
    )
    return updated
