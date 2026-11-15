"""Bounded committed-event genealogy and generation harvest for mobility.

Only committed ``WorldEvent`` details are read. No ``WorldState``,
``KinshipGraph``, runtime, store, or API object is consulted.
"""

from __future__ import annotations

import logging
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from analysis.social_mobility_contract import (
    SocialMobilityCoverage,
    SocialMobilityError,
    SocialMobilityIdentityMap,
    social_mobility_lineage_token,
    social_mobility_owner_token,
)
from analysis.social_mobility_policy import (
    SocialMobilityAnalysisPolicy,
    default_social_mobility_analysis_policy,
)
from analysis.social_mobility_rows import (
    SocialMobilityGenealogyRow,
    SocialMobilityLineageEntry,
)
from world.events import AgentCreated, KinshipEdgeRecorded, WorldEvent

__all__ = [
    "SocialMobilityGenealogyHarvest",
    "harvest_social_mobility_genealogy",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.social_mobility.genealogy")


@dataclass(frozen=True, slots=True)
class SocialMobilityGenealogyHarvest:
    """Bounded objective genealogy evidence with explicit coverage."""

    edges: tuple[SocialMobilityGenealogyRow, ...] = ()
    generations: tuple[tuple[str, int], ...] = ()
    lineages: tuple[SocialMobilityLineageEntry, ...] = ()
    notices: tuple[str, ...] = ()
    coverage: SocialMobilityCoverage = SocialMobilityCoverage.MISSING
    event_count: int = 0
    owner_count: int = 0
    max_generation_index: int = 0

    def __post_init__(self) -> None:
        for name in ("edges", "generations", "lineages", "notices"):
            value = getattr(self, name)
            if isinstance(value, (str, bytes)) or not isinstance(value, tuple):
                raise SocialMobilityError("social_mobility_genealogy_invalid")
        if type(self.coverage) is not SocialMobilityCoverage:
            raise SocialMobilityError("social_mobility_genealogy_invalid")
        for name in ("event_count", "owner_count", "max_generation_index"):
            value = getattr(self, name)
            if isinstance(value, bool) or type(value) is not int or value < 0:
                raise SocialMobilityError("social_mobility_genealogy_invalid")

    def generation_for(self, owner_token: str) -> int | None:
        for token, generation in self.generations:
            if token == owner_token:
                return generation
        return None


def _ordered_events(events: Sequence[WorldEvent]) -> tuple[WorldEvent, ...]:
    if isinstance(events, (str, bytes)) or not isinstance(events, Sequence):
        raise SocialMobilityError("social_mobility_invalid_input")
    for event in events:
        if type(event) is not WorldEvent:
            raise SocialMobilityError("social_mobility_invalid_input")
    return tuple(sorted(events, key=lambda event: (event.tick, event.sequence)))


def _notice(notices: list[str], code: str) -> None:
    if code not in notices:
        notices.append(code)


def harvest_social_mobility_genealogy(
    events: Sequence[WorldEvent],
    *,
    identity_map: SocialMobilityIdentityMap,
    policy: SocialMobilityAnalysisPolicy | None = None,
) -> SocialMobilityGenealogyHarvest:
    """Fold committed identity and kinship events into bounded token rows."""

    active = default_social_mobility_analysis_policy() if policy is None else policy
    ordered = _ordered_events(events)
    if not ordered:
        _LOG.debug("social_mobility_genealogy_empty")
        return SocialMobilityGenealogyHarvest(coverage=SocialMobilityCoverage.MISSING)

    notices: list[str] = []
    truncated = False
    event_count = len(ordered)
    if event_count > active.max_event_rows:
        ordered = ordered[: active.max_event_rows]
        event_count = len(ordered)
        _notice(notices, "social_mobility_events_truncated")
        truncated = True

    agent_tokens = frozenset(identity_map.forward.values())
    generations: dict[str, int] = {token: 0 for token in sorted(agent_tokens)}
    excluded: set[str] = set()
    for event in ordered:
        if type(event.details) is not AgentCreated:
            continue
        details = event.details
        try:
            token = identity_map.require_token(details.agent_id)
        except SocialMobilityError:
            _notice(notices, "social_mobility_unmapped_owner")
            truncated = True
            continue
        generation = details.generation_index
        if generation < 0 or generation > active.max_generation_index:
            excluded.add(token)
            generations.pop(token, None)
            _notice(notices, "social_mobility_generation_out_of_range")
            continue
        if token not in excluded:
            generations[token] = generation

    for event in ordered:
        for entity in (event.actor_id, event.target_id):
            raw = getattr(entity, "value", None)
            if isinstance(raw, str) and raw:
                token = social_mobility_owner_token(raw)
                if token in agent_tokens and token not in excluded:
                    generations.setdefault(token, 0)

    owners = sorted(generations)
    if len(owners) > active.max_owners:
        owners = owners[: active.max_owners]
        _notice(notices, "social_mobility_owners_truncated")
        truncated = True
    allowed = set(owners)
    generations = {token: generations[token] for token in owners}

    edge_by_pair: dict[tuple[str, str], SocialMobilityGenealogyRow] = {}
    for event in ordered:
        if type(event.details) is not KinshipEdgeRecorded:
            continue
        edge_details = event.details
        try:
            parent_token = identity_map.require_token(edge_details.parent_agent_id)
            child_token = identity_map.require_token(edge_details.child_agent_id)
        except SocialMobilityError:
            _notice(notices, "social_mobility_unmapped_owner")
            truncated = True
            continue
        if parent_token == child_token:
            _notice(notices, "social_mobility_edge_invalid")
            truncated = True
            continue
        if parent_token not in allowed or child_token not in allowed:
            continue
        parent_generation = generations.get(parent_token)
        child_generation = generations.get(child_token)
        if parent_generation is None or child_generation is None:
            _notice(notices, "social_mobility_missing_generation")
            truncated = True
            continue
        window_index = event.tick // active.window_ticks
        if window_index >= active.max_windows:
            window_index = active.max_windows - 1
        pair = (parent_token, child_token)
        edge_candidate = SocialMobilityGenealogyRow(
            parent_token=parent_token,
            child_token=child_token,
            parent_generation=parent_generation,
            child_generation=child_generation,
            established_tick=event.tick,
            window_index=window_index,
        )
        previous_edge = edge_by_pair.get(pair)
        if previous_edge is None or (
            edge_candidate.established_tick,
            edge_candidate.window_index,
        ) < (
            previous_edge.established_tick,
            previous_edge.window_index,
        ):
            edge_by_pair[pair] = edge_candidate

    edges = tuple(
        sorted(
            edge_by_pair.values(),
            key=lambda row: (
                row.established_tick,
                row.parent_token,
                row.child_token,
            ),
        )
    )

    parents_of: dict[str, list[str]] = {}
    for edge in edges:
        parents_of.setdefault(edge.child_token, []).append(edge.parent_token)
    for children in parents_of.values():
        children.sort()

    lineage_by_pair: dict[tuple[str, str], SocialMobilityLineageEntry] = {}
    for child_token in sorted(parents_of):
        child_generation = generations[child_token]
        queue: deque[tuple[str, int]] = deque(
            (parent, 1) for parent in parents_of[child_token]
        )
        seen: set[str] = set()
        while queue:
            ancestor_token, depth = queue.popleft()
            if ancestor_token in seen or depth > active.max_lineage_depth:
                continue
            seen.add(ancestor_token)
            lag = child_generation - generations[ancestor_token]
            if 1 <= lag <= active.max_generation_lag:
                key = (ancestor_token, child_token)
                lineage_candidate = SocialMobilityLineageEntry(
                    lineage_token=social_mobility_lineage_token(
                        ancestor_token, child_token
                    ),
                    ancestor_token=ancestor_token,
                    descendant_token=child_token,
                    generation_lag=lag,
                    ancestor_generation=generations[ancestor_token],
                    descendant_generation=child_generation,
                )
                previous_lineage = lineage_by_pair.get(key)
                if previous_lineage is None or lineage_candidate.generation_lag < (
                    previous_lineage.generation_lag
                ):
                    lineage_by_pair[key] = lineage_candidate
            for parent in parents_of.get(ancestor_token, ()):
                queue.append((parent, depth + 1))

    lineages = tuple(
        sorted(
            lineage_by_pair.values(),
            key=lambda entry: (
                entry.generation_lag,
                entry.ancestor_token,
                entry.descendant_token,
            ),
        )
    )

    if not edges and not lineages:
        _notice(notices, "social_mobility_missing_generation")
        truncated = True
    coverage = (
        SocialMobilityCoverage.PARTIAL
        if truncated or notices
        else SocialMobilityCoverage.COMPLETE
    )

    max_generation = max(generations.values(), default=0)
    _LOG.debug(
        "social_mobility_genealogy_harvested events=%d edges=%d owners=%d "
        "lineages=%d max_generation=%d",
        event_count,
        len(edges),
        len(generations),
        len(lineages),
        max_generation,
    )
    if coverage is SocialMobilityCoverage.PARTIAL:
        _LOG.warning("social_mobility_genealogy_partial")

    return SocialMobilityGenealogyHarvest(
        edges=edges,
        generations=tuple(sorted(generations.items())),
        lineages=lineages,
        notices=tuple(notices[: active.max_notices]),
        coverage=coverage,
        event_count=event_count,
        owner_count=len(generations),
        max_generation_index=max_generation,
    )
