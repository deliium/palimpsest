"""Live disaster candidate application for one open tick.

Engine-owned helpers; publish only through the ordinary tick commit.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

from simulation.disasters_randomness import (
    fictional_surge_opportunity_draw,
)
from simulation.models import SimulationRunConfig
from world._disasters import (
    DisasterState,
    DisasterStockPulse,
    apply_stock_disaster,
    mark_disaster_rule_applied,
)
from world._state import WorldState, rebuild_world_state
from world.disasters import (
    DisasterCandidate,
    DisasterInfrastructureTarget,
    DisasterKind,
    DisasterLocationTarget,
    DisasterOrigin,
    DisasterResourceTarget,
    DisasterSkipReason,
    DisasterSurgeEffect,
)
from world.events import (
    DisasterInfrastructureEffectRecord,
    DisasterInfrastructureTargetView,
    DisasterLocationTargetView,
    DisasterOutcome,
    DisasterResolved,
    DisasterResourceTargetView,
    DisasterStockEffectRecord,
    DisasterSurgeEffectRecord,
    disaster_outcome_from_skip,
)
from world.identifiers import EntityId

__all__ = [
    "DisasterTickApplication",
    "apply_disaster_candidates",
    "build_surge_opportunity",
    "target_entity_id",
]

_LOG: Final[logging.Logger] = logging.getLogger("simulation.disasters_resolve")


@dataclass(frozen=True, slots=True)
class DisasterTickApplication:
    """Detached outcome of one disaster tranche within a tick."""

    working_state: WorldState
    disaster_state: DisasterState
    stock_infra_details: tuple[object, ...]
    surge_details: tuple[DisasterResolved, ...]
    semantic_mutation: bool
    surge_by_location: Mapping[EntityId, DisasterCandidate]


def target_entity_id(candidate: DisasterCandidate) -> EntityId:
    target = candidate.rule.target
    if type(target) is DisasterResourceTarget:
        return target.resource_id
    if type(target) is DisasterInfrastructureTarget:
        return target.location_id
    if type(target) is DisasterLocationTarget:
        return target.location_id
    raise TypeError("unsupported disaster target")


def _target_view(candidate: DisasterCandidate) -> object:
    target = candidate.rule.target
    if type(target) is DisasterResourceTarget:
        return DisasterResourceTargetView(resource_id=target.resource_id)
    if type(target) is DisasterInfrastructureTarget:
        return DisasterInfrastructureTargetView(
            location_id=target.location_id,
            endpoint_location_id=target.endpoint_location_id,
            infrastructure_kind=target.infrastructure_kind,
        )
    if type(target) is DisasterLocationTarget:
        return DisasterLocationTargetView(location_id=target.location_id)
    raise TypeError("unsupported disaster target")


def build_surge_opportunity(
    *,
    run_config: SimulationRunConfig,
    tick: int,
    surge_by_location: Mapping[EntityId, DisasterCandidate],
) -> Callable[[EntityId, EntityId], bool]:
    """Pure extra-opportunity callback keyed by location then entity."""

    def extra_opportunity(location_id: EntityId, entity_id: EntityId) -> bool:
        candidate = surge_by_location.get(location_id)
        if candidate is None:
            return False
        effect = candidate.rule.effect
        if type(effect) is not DisasterSurgeEffect:
            return False
        return fictional_surge_opportunity_draw(
            run_config,
            tick=tick,
            rule_id=candidate.rule.rule_id,
            entity_id=entity_id,
            extra_opportunity_milli=effect.extra_opportunity_milli,
        )

    return extra_opportunity


def apply_disaster_candidates(
    *,
    working_state: WorldState,
    disaster_state: DisasterState,
    candidates: Sequence[DisasterCandidate],
    tick: int,
) -> DisasterTickApplication:
    """Apply stock and infrastructure candidates; defer surge receipts."""
    from world._infrastructure import destroy_infrastructure_for_disaster

    next_state = working_state
    next_ledger = disaster_state
    stock_infra: list[object] = []
    surge_map: dict[EntityId, DisasterCandidate] = {}
    mutation = False

    for candidate in candidates:
        rule = candidate.rule
        if rule.kind is DisasterKind.EPIDEMIC_SURGE:
            if type(rule.target) is not DisasterLocationTarget:
                raise TypeError("surge target must be DisasterLocationTarget")
            location_id = rule.target.location_id
            if location_id in surge_map:
                raise ValueError("disaster_surge_duplicate_location")
            surge_map[location_id] = candidate
            continue

        if rule.kind is DisasterKind.INFRASTRUCTURE_DESTRUCTION:
            if type(rule.target) is not DisasterInfrastructureTarget:
                raise TypeError("infrastructure target mismatch")
            next_state, asset_or_skip, detail = destroy_infrastructure_for_disaster(
                next_state,
                location_id=rule.target.location_id,
                endpoint_location_id=rule.target.endpoint_location_id,
                infrastructure_kind=rule.target.infrastructure_kind,
                tick=tick,
            )
            if type(asset_or_skip) is DisasterSkipReason:
                if candidate.origin is DisasterOrigin.SCHEDULED:
                    stock_infra.append(
                        DisasterResolved(
                            rule_id=rule.rule_id,
                            disaster_kind=rule.kind,
                            origin=candidate.origin,
                            target=_target_view(candidate),  # type: ignore[arg-type]
                            outcome=disaster_outcome_from_skip(asset_or_skip),
                            effect=None,
                        )
                    )
                continue
            assert detail is not None
            from world.infrastructure import InfrastructureAsset

            if type(asset_or_skip) is not InfrastructureAsset:
                raise TypeError(
                    "infrastructure disaster asset must be InfrastructureAsset"
                )
            mutation = True
            next_ledger = mark_disaster_rule_applied(next_ledger, rule.rule_id)
            stock_infra.append(detail)
            stock_infra.append(
                DisasterResolved(
                    rule_id=rule.rule_id,
                    disaster_kind=rule.kind,
                    origin=candidate.origin,
                    target=_target_view(candidate),  # type: ignore[arg-type]
                    outcome=DisasterOutcome.APPLIED,
                    effect=DisasterInfrastructureEffectRecord(
                        asset_id=asset_or_skip.asset_id
                    ),
                )
            )
            continue

        # Stock kinds
        next_state, pulse_or_skip, witness = apply_stock_disaster(next_state, candidate)
        if type(pulse_or_skip) is DisasterSkipReason:
            if candidate.origin is DisasterOrigin.SCHEDULED:
                stock_infra.append(
                    DisasterResolved(
                        rule_id=rule.rule_id,
                        disaster_kind=rule.kind,
                        origin=candidate.origin,
                        target=_target_view(candidate),  # type: ignore[arg-type]
                        outcome=disaster_outcome_from_skip(pulse_or_skip),
                        effect=None,
                    )
                )
            continue
        pulse = pulse_or_skip
        assert type(pulse) is DisasterStockPulse
        mutation = True
        next_ledger = mark_disaster_rule_applied(next_ledger, rule.rule_id)
        stock_infra.append(
            DisasterResolved(
                rule_id=rule.rule_id,
                disaster_kind=rule.kind,
                origin=candidate.origin,
                target=_target_view(candidate),  # type: ignore[arg-type]
                outcome=DisasterOutcome.APPLIED,
                effect=DisasterStockEffectRecord(
                    quantity_before_tenths=pulse.quantity_before_tenths,
                    quantity_after_tenths=pulse.quantity_after_tenths,
                    damage_before_tenths=pulse.damage_before_tenths,
                    damage_after_tenths=pulse.damage_after_tenths,
                ),
            )
        )
        # Positive-to-zero crossing: witness immediately follows the receipt.
        if witness is not None:
            stock_infra.append(witness)

    next_state = rebuild_world_state(
        next_state,
        disaster_state=next_ledger,
        replace_disaster_state=True,
    )
    _LOG.debug(
        "disaster_candidates_applied stock_infra=%s surge=%s mutation=%s",
        len(stock_infra),
        len(surge_map),
        mutation,
    )
    return DisasterTickApplication(
        working_state=next_state,
        disaster_state=next_ledger,
        stock_infra_details=tuple(stock_infra),
        surge_details=(),
        semantic_mutation=mutation,
        surge_by_location=surge_map,
    )


def finalize_surge_receipts(
    *,
    working_state: WorldState,
    disaster_state: DisasterState,
    surge_by_location: Mapping[EntityId, DisasterCandidate],
    extra_latent_recipients: Sequence[EntityId],
    start_disease: Mapping[EntityId, Any] | None,
    end_disease: Mapping[EntityId, Any] | None,
) -> tuple[WorldState, DisasterState, tuple[DisasterResolved, ...], bool]:
    """Emit surge receipts after private disease nets are known."""
    from world._disease import DiseasePhase

    # Count finalized absent→latent transitions among extra recipients.
    start_rows = start_disease or {}
    end_rows = end_disease or {}
    location_counts: dict[EntityId, int] = {key: 0 for key in surge_by_location}
    for entity_id in extra_latent_recipients:
        body = working_state.bodies.get(entity_id)
        if body is None:
            continue
        location_id = body.location_id
        if location_id not in location_counts:
            continue
        before = start_rows.get(entity_id)
        after = end_rows.get(entity_id)
        if before is not None:
            continue
        if after is None or after.phase is not DiseasePhase.LATENT:
            continue
        location_counts[location_id] += 1

    receipts: list[DisasterResolved] = []
    next_ledger = disaster_state
    mutation = False
    for location_id in sorted(surge_by_location, key=lambda item: item.value):
        candidate = surge_by_location[location_id]
        count = location_counts.get(location_id, 0)
        if count <= 0:
            if candidate.origin is DisasterOrigin.SCHEDULED:
                receipts.append(
                    DisasterResolved(
                        rule_id=candidate.rule.rule_id,
                        disaster_kind=candidate.rule.kind,
                        origin=candidate.origin,
                        target=_target_view(candidate),  # type: ignore[arg-type]
                        outcome=DisasterOutcome.NO_EFFECT,
                        effect=None,
                    )
                )
            continue
        mutation = True
        next_ledger = mark_disaster_rule_applied(next_ledger, candidate.rule.rule_id)
        receipts.append(
            DisasterResolved(
                rule_id=candidate.rule.rule_id,
                disaster_kind=candidate.rule.kind,
                origin=candidate.origin,
                target=_target_view(candidate),  # type: ignore[arg-type]
                outcome=DisasterOutcome.APPLIED,
                effect=DisasterSurgeEffectRecord(additional_latent_count=count),
            )
        )

    next_state = rebuild_world_state(
        working_state,
        disaster_state=next_ledger,
        replace_disaster_state=True,
    )
    return next_state, next_ledger, tuple(receipts), mutation
