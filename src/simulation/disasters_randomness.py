"""Deterministic disaster candidate selection; no policy mutation or world writes."""

from __future__ import annotations

import logging
from collections.abc import Collection, Mapping
from typing import Final

from simulation.disasters_config import DisastersSpec
from simulation.models import SimulationRunConfig
from simulation.randomness import StreamScope, create_named_stream
from world.disasters import (
    DISASTERS_POLICY_ID,
    MAX_SURGE_OPPORTUNITY_MILLI,
    MIN_SURGE_OPPORTUNITY_MILLI,
    DisasterCandidate,
    DisasterOrigin,
    DisasterRule,
)
from world.identifiers import EntityId

__all__ = [
    "DISASTERS_STREAM_NAMESPACE",
    "fictional_surge_opportunity_draw",
    "select_disaster_candidates",
    "spontaneous_occurrence_draw",
]

_LOGGER: Final[logging.Logger] = logging.getLogger("simulation.disasters_randomness")

DISASTERS_STREAM_NAMESPACE: Final[str] = DISASTERS_POLICY_ID


def spontaneous_occurrence_draw(
    run_config: SimulationRunConfig,
    *,
    tick: int,
    rule_id: str,
    chance_ppm: int,
) -> bool:
    """Return whether a spontaneous rule fires on ``tick``.

    Uses ``randrange(1_000_000) < chance_ppm``. Callers must omit this draw for
    zero-probability, scheduled, or already-applied rules.
    """
    if type(run_config) is not SimulationRunConfig:
        raise TypeError("run_config must be SimulationRunConfig")
    if type(tick) is not int or isinstance(tick, bool) or tick < 0:
        raise ValueError("tick must be a nonnegative int")
    if type(rule_id) is not str or rule_id == "":
        raise ValueError("rule_id must be a non-empty string")
    if type(chance_ppm) is not int or isinstance(chance_ppm, bool):
        raise TypeError("chance_ppm must be int")
    if chance_ppm <= 0:
        raise ValueError("chance_ppm must be positive for spontaneous draws")
    stream = create_named_stream(
        run_config,
        StreamScope(
            DISASTERS_STREAM_NAMESPACE,
            (str(tick), rule_id, "occurrence"),
        ),
    )
    roll = stream.randrange(1_000_000)
    hit = roll < chance_ppm
    _LOGGER.debug(
        "disaster_spontaneous_draw tick=%s hit=%s",
        tick,
        hit,
    )
    return hit


def fictional_surge_opportunity_draw(
    run_config: SimulationRunConfig,
    *,
    tick: int,
    rule_id: str,
    entity_id: EntityId,
    extra_opportunity_milli: int,
) -> bool:
    """Return whether a fictional surge grants one extra exposure opportunity.

    Uses ``randrange(1000) < extra_opportunity_milli`` on an isolated named stream.
    Does not touch the ordinary disease RNG stream.
    """
    if type(run_config) is not SimulationRunConfig:
        raise TypeError("run_config must be SimulationRunConfig")
    if type(tick) is not int or isinstance(tick, bool) or tick < 0:
        raise ValueError("tick must be a nonnegative int")
    if type(rule_id) is not str or rule_id == "":
        raise ValueError("rule_id must be a non-empty string")
    if type(entity_id) is not EntityId:
        raise TypeError("entity_id must be EntityId")
    if type(extra_opportunity_milli) is not int or isinstance(
        extra_opportunity_milli, bool
    ):
        raise TypeError("extra_opportunity_milli must be int")
    if (
        extra_opportunity_milli < MIN_SURGE_OPPORTUNITY_MILLI
        or extra_opportunity_milli > MAX_SURGE_OPPORTUNITY_MILLI
    ):
        raise ValueError("extra_opportunity_milli out of range")
    stream = create_named_stream(
        run_config,
        StreamScope(
            DISASTERS_STREAM_NAMESPACE,
            (str(tick), rule_id, entity_id.value, "fictional-opportunity"),
        ),
    )
    roll = stream.randrange(1000)
    hit = roll < extra_opportunity_milli
    _LOGGER.debug(
        "disaster_surge_opportunity_draw tick=%s hit=%s",
        tick,
        hit,
    )
    return hit


def select_disaster_candidates(
    spec: DisastersSpec,
    *,
    run_config: SimulationRunConfig,
    tick: int,
    applied_rule_ids: Collection[str] | Mapping[str, object],
) -> tuple[DisasterCandidate, ...]:
    """Select due scheduled then spontaneous candidates for one absolute tick.

    Ordering: all scheduled candidates first (ASCII ``rule_id``), then spontaneous
    hits (ASCII ``rule_id``). Already-applied rules are suppressed. Zero-chance
    and scheduled rules never draw.
    """
    if type(spec) is not DisastersSpec:
        raise TypeError("spec must be DisastersSpec")
    if type(run_config) is not SimulationRunConfig:
        raise TypeError("run_config must be SimulationRunConfig")
    if type(tick) is not int or isinstance(tick, bool) or tick < 0:
        raise ValueError("tick must be a nonnegative int")
    if isinstance(applied_rule_ids, Mapping):
        applied = {str(key) for key in applied_rule_ids}
    else:
        applied = {str(rule_id) for rule_id in applied_rule_ids}

    rules_by_id: dict[str, DisasterRule] = {
        rule.rule_id: rule for rule in spec.rules
    }
    scheduled: list[DisasterCandidate] = []
    for entry in spec.schedule:
        if entry.tick != tick:
            continue
        if entry.rule_id in applied:
            continue
        rule = rules_by_id[entry.rule_id]
        scheduled.append(
            DisasterCandidate(rule=rule, origin=DisasterOrigin.SCHEDULED)
        )
    scheduled.sort(key=lambda candidate: candidate.rule.rule_id)

    spontaneous: list[DisasterCandidate] = []
    for rule in spec.rules:
        if rule.rule_id in applied:
            continue
        if rule.chance_ppm <= 0:
            continue
        # Scheduled rules always have chance_ppm == 0; double-check independence.
        if any(entry.rule_id == rule.rule_id for entry in spec.schedule):
            continue
        if spontaneous_occurrence_draw(
            run_config,
            tick=tick,
            rule_id=rule.rule_id,
            chance_ppm=rule.chance_ppm,
        ):
            spontaneous.append(
                DisasterCandidate(rule=rule, origin=DisasterOrigin.SPONTANEOUS)
            )
    spontaneous.sort(key=lambda candidate: candidate.rule.rule_id)

    selected = tuple(scheduled + spontaneous)
    _LOGGER.debug(
        "disaster_candidates_selected tick=%s scheduled_count=%s "
        "spontaneous_count=%s total=%s",
        tick,
        len(scheduled),
        len(spontaneous),
        len(selected),
    )
    return selected
