"""Link dependency-conditioned analytical cascade chains and propagation rows.

A chain is ``linked`` only when an observed disruption reaches an observed
downstream stage shortfall along an emitted dependency edge, within the configured
depth and lag bounds. ``unlinked`` and ``unresolved`` are first-class results. No
row asserts an objective cause, severity, or priority.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from analysis.economic_cascades_contract import (
    NONE_TOKEN,
    CascadeAvailability,
    CascadeChainState,
    CascadeCoverage,
    CascadeDisruptionKind,
    EconomicCascadesError,
    mint_chain_token,
)
from analysis.economic_cascades_detection import CascadeStageShortfall
from analysis.economic_cascades_policy import (
    EconomicCascadesPolicy,
    default_policy,
    window_tick,
)
from analysis.economic_cascades_rows import (
    CascadeChainRow,
    CascadeDependencyEdgeRow,
    CascadeDisruptionRow,
    CascadeEpisodeRow,
    CascadePropagationRow,
)

__all__ = [
    "CascadeChainResult",
    "link_economic_cascade_chains",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.economic_cascades.chains")


@dataclass(frozen=True, slots=True)
class CascadeChainResult:
    """Analytical chains, per-kind propagation rows, and coverage."""

    chains: tuple[CascadeChainRow, ...] = ()
    propagation_rows: tuple[CascadePropagationRow, ...] = ()
    notices: tuple[str, ...] = ()
    coverage: CascadeCoverage = CascadeCoverage.MISSING
    chain_count: int = 0
    linked_count: int = 0
    unlinked_count: int = 0
    unresolved_count: int = 0
    max_depth: int = 0

    def __post_init__(self) -> None:
        for name in ("chains", "propagation_rows", "notices"):
            value = getattr(self, name)
            if isinstance(value, (str, bytes)) or not isinstance(value, tuple):
                raise EconomicCascadesError("economic_cascades_invalid_chain")
        if type(self.coverage) is not CascadeCoverage:
            raise EconomicCascadesError("economic_cascades_invalid_chain")
        for name in (
            "chain_count",
            "linked_count",
            "unlinked_count",
            "unresolved_count",
            "max_depth",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or type(value) is not int or value < 0:
                raise EconomicCascadesError("economic_cascades_invalid_chain")


def _labor_map(
    joins: Sequence[tuple[str, tuple[str, ...]]],
) -> dict[str, tuple[str, ...]]:
    mapping: dict[str, tuple[str, ...]] = {}
    for actor_token, recipe_ids in joins:
        if type(actor_token) is not str or not actor_token:
            raise EconomicCascadesError("economic_cascades_invalid_chain")
        if isinstance(recipe_ids, (str, bytes)) or not isinstance(
            recipe_ids, tuple
        ):
            raise EconomicCascadesError("economic_cascades_invalid_chain")
        mapping[actor_token] = tuple(recipe_ids)
    return mapping


def _subject_map(
    disruptions: Sequence[CascadeDisruptionRow],
    episodes: Sequence[CascadeEpisodeRow],
    labor: dict[str, tuple[str, ...]],
) -> dict[tuple[int, CascadeDisruptionKind], tuple[tuple[str, ...], tuple[str, ...]]]:
    """Map an episode key to (start tokens, evidence tokens)."""

    grouped: dict[
        tuple[int, CascadeDisruptionKind], list[CascadeDisruptionRow]
    ] = {}
    for row in disruptions:
        grouped.setdefault((row.window_index, row.kind), []).append(row)
    result: dict[
        tuple[int, CascadeDisruptionKind], tuple[tuple[str, ...], tuple[str, ...]]
    ] = {}
    for episode in episodes:
        key = (episode.window_index, episode.kind)
        rows = grouped.get(key, [])
        starts: list[str] = []
        evidence: set[str] = set()
        for row in rows:
            evidence.add(row.evidence_event_token)
            if row.kind is CascadeDisruptionKind.POPULATION_LOSS:
                recipes = labor.get(row.subject_token)
                if recipes:
                    starts.extend(f"labor:{recipe_id}" for recipe_id in recipes)
                continue
            starts.append(row.subject_token)
        result[key] = (tuple(sorted(set(starts))), tuple(sorted(evidence)))
    return result


def _stage_index(
    stages: Sequence[CascadeStageShortfall],
) -> dict[str, dict[int, tuple[CascadeStageShortfall, ...]]]:
    index: dict[str, dict[int, list[CascadeStageShortfall]]] = {}
    for item in stages:
        index.setdefault(item.recipe_id, {}).setdefault(
            item.window_index, []
        ).append(item)
    return {
        recipe_id: {
            window: tuple(values)
            for window, values in sorted(by_window.items())
        }
        for recipe_id, by_window in index.items()
    }


def _adjacency(
    edges: Sequence[CascadeDependencyEdgeRow],
) -> dict[str, tuple[CascadeDependencyEdgeRow, ...]]:
    mapping: dict[str, list[CascadeDependencyEdgeRow]] = {}
    for edge in edges:
        mapping.setdefault(edge.upstream_token, []).append(edge)
    return {
        token: tuple(
            sorted(values, key=lambda row: (row.downstream_recipe_id, row.kind.value))
        )
        for token, values in mapping.items()
    }


def link_economic_cascade_chains(
    *,
    episodes: Sequence[CascadeEpisodeRow],
    disruptions: Sequence[CascadeDisruptionRow],
    stages: Sequence[CascadeStageShortfall],
    edges: Sequence[CascadeDependencyEdgeRow],
    labor_joins: Sequence[tuple[str, tuple[str, ...]]] = (),
    policy: EconomicCascadesPolicy | None = None,
) -> CascadeChainResult:
    """Link observed disruptions to downstream shortfalls along emitted edges."""

    active = default_policy() if policy is None else policy
    if type(active) is not EconomicCascadesPolicy:
        raise EconomicCascadesError("economic_cascades_invalid_policy")
    if isinstance(episodes, (str, bytes)) or not isinstance(episodes, Sequence):
        raise EconomicCascadesError("economic_cascades_invalid_chain")
    if isinstance(disruptions, (str, bytes)) or not isinstance(
        disruptions, Sequence
    ):
        raise EconomicCascadesError("economic_cascades_invalid_chain")
    if isinstance(stages, (str, bytes)) or not isinstance(stages, Sequence):
        raise EconomicCascadesError("economic_cascades_invalid_chain")
    if isinstance(edges, (str, bytes)) or not isinstance(edges, Sequence):
        raise EconomicCascadesError("economic_cascades_invalid_chain")
    for episode_item in episodes:
        if type(episode_item) is not CascadeEpisodeRow:
            raise EconomicCascadesError("economic_cascades_invalid_chain")
    for disruption_item in disruptions:
        if type(disruption_item) is not CascadeDisruptionRow:
            raise EconomicCascadesError("economic_cascades_invalid_chain")
    for stage_item in stages:
        if type(stage_item) is not CascadeStageShortfall:
            raise EconomicCascadesError("economic_cascades_invalid_chain")
    for edge_item in edges:
        if type(edge_item) is not CascadeDependencyEdgeRow:
            raise EconomicCascadesError("economic_cascades_invalid_chain")

    notices: set[str] = set()
    labor = _labor_map(labor_joins)
    starts_by_episode = _subject_map(disruptions, episodes, labor)
    stage_index = _stage_index(stages)
    adjacency = _adjacency(edges)
    chains: list[CascadeChainRow] = []
    unresolved_fallbacks: list[tuple[int, CascadeDisruptionKind, str]] = []

    for episode in episodes:
        key = (episode.window_index, episode.kind)
        starts, evidence = starts_by_episode.get(key, ((), ()))
        if episode.kind is CascadeDisruptionKind.POPULATION_LOSS and not starts:
            unresolved_fallbacks.append(
                (episode.window_index, episode.kind, "labor:unresolved")
            )
            notices.add("labor_join_missing")
            continue
        if not starts:
            subject = "resource:unknown"
            grouped = [
                row
                for row in disruptions
                if row.window_index == episode.window_index
                and row.kind is episode.kind
            ]
            if grouped:
                subject = grouped[0].subject_token
            unresolved_fallbacks.append(
                (episode.window_index, episode.kind, subject)
            )
            notices.add("chain_unresolved")
            continue

        for start in starts:
            if start.startswith("labor:"):
                root_recipe = start.split(":", 1)[1]
                chain_upstream = start
            elif start.startswith(("route:", "asset:", "resource:")):
                root_recipe = None
                chain_upstream = start
                if start.startswith("resource:"):
                    notices.add("chain_unresolved")
                    unresolved_fallbacks.append(
                        (episode.window_index, episode.kind, start)
                    )
                    continue
            else:
                root_recipe = start
                chain_upstream = start

            frontier: list[tuple[str, int]] = []
            if root_recipe is not None:
                frontier.append((root_recipe, 1))
            else:
                frontier.append((start, 1))
            visited: set[tuple[str, int]] = set()
            while frontier:
                node, depth = frontier.pop(0)
                if depth > active.max_chain_depth:
                    continue
                if (node, depth) in visited:
                    continue
                visited.add((node, depth))
                for edge in adjacency.get(node, ()):
                    downstream = edge.downstream_recipe_id
                    downstream_windows = stage_index.get(downstream)
                    if downstream_windows is None:
                        chains.append(
                            _chain_row(
                                episode=episode,
                                upstream_token=chain_upstream,
                                downstream_recipe_id=downstream,
                                depth=depth,
                                lag_windows=0,
                                shortfall_share_milli=0,
                                state=CascadeChainState.UNRESOLVED,
                                coverage=CascadeCoverage.PARTIAL,
                                evidence=evidence,
                                policy=active,
                            )
                        )
                        notices.add("chain_unresolved")
                        continue
                    found = False
                    for lag in range(active.max_propagation_lag_windows + 1):
                        window = episode.window_index + lag
                        for shortfall_item in downstream_windows.get(window, ()):
                            found = True
                            state = (
                                CascadeChainState.LINKED
                                if shortfall_item.in_shortfall
                                else CascadeChainState.UNLINKED
                            )
                            chains.append(
                                _chain_row(
                                    episode=episode,
                                    upstream_token=chain_upstream,
                                    downstream_recipe_id=downstream,
                                    depth=depth,
                                    lag_windows=lag,
                                    shortfall_share_milli=(
                                        shortfall_item.shortfall_share_milli
                                    ),
                                    state=state,
                                    coverage=shortfall_item.stage.coverage,
                                    evidence=evidence,
                                    window_index=window,
                                    policy=active,
                                )
                            )
                    if not found:
                        chains.append(
                            _chain_row(
                                episode=episode,
                                upstream_token=chain_upstream,
                                downstream_recipe_id=downstream,
                                depth=depth,
                                lag_windows=0,
                                shortfall_share_milli=0,
                                state=CascadeChainState.UNRESOLVED,
                                coverage=CascadeCoverage.PARTIAL,
                                evidence=evidence,
                                policy=active,
                            )
                        )
                        notices.add("chain_unresolved")
                        continue
                    frontier.append((downstream, depth + 1))

    for window_index, kind, upstream in unresolved_fallbacks:
        chains.append(
            CascadeChainRow(
                chain_token=mint_chain_token(
                    disruption_kind=kind,
                    upstream_token=upstream,
                    downstream_recipe_id=NONE_TOKEN,
                    depth=1,
                    lag_windows=0,
                    window_index=window_index,
                    evidence_tokens=(),
                ),
                window_index=window_index,
                window_tick=window_tick(window_index, active),
                disruption_kind=kind,
                upstream_token=upstream,
                downstream_recipe_id=NONE_TOKEN,
                depth=1,
                lag_windows=0,
                shortfall_share_milli=0,
                state=CascadeChainState.UNRESOLVED,
                coverage=CascadeCoverage.PARTIAL,
                )
        )

    merged: dict[tuple[str, int], CascadeChainRow] = {}
    for row in chains:
        merge_key = (row.chain_token, row.window_index)
        previous = merged.get(merge_key)
        if (
            previous is None
            or row.shortfall_share_milli > previous.shortfall_share_milli
        ):
            merged[merge_key] = row
    ordered = sorted(
        merged.values(),
        key=lambda row: (
            row.window_index,
            row.disruption_kind.value,
            row.depth,
            row.downstream_recipe_id,
            row.chain_token,
        ),
    )
    if len(ordered) > active.max_chains:
        ordered = ordered[: active.max_chains]
        notices.add("chains_truncated")
        _LOG.warning(
            "economic_cascades_chains_truncated retained=%s cap=%s",
            len(ordered),
            active.max_chains,
        )

    propagation = _propagation_rows(ordered, episodes, active)
    if len(propagation) > active.max_propagation_rows:
        propagation = propagation[: active.max_propagation_rows]
        notices.add("propagation_truncated")

    linked_count = sum(
        1 for row in ordered if row.state is CascadeChainState.LINKED
    )
    unlinked_count = sum(
        1 for row in ordered if row.state is CascadeChainState.UNLINKED
    )
    unresolved_count = sum(
        1 for row in ordered if row.state is CascadeChainState.UNRESOLVED
    )
    max_depth = max((row.depth for row in ordered), default=0)

    if not ordered and not episodes:
        coverage = CascadeCoverage.MISSING
    elif notices or any(
        row.coverage is CascadeCoverage.PARTIAL for row in ordered
    ):
        coverage = CascadeCoverage.PARTIAL
    else:
        coverage = CascadeCoverage.COMPLETE

    _LOG.debug(
        "economic_cascades_chain_traversal nodes=%s depth=%s",
        len(ordered),
        max_depth,
    )
    _LOG.info(
        "economic_cascades_chains_complete chains=%s linked=%s",
        len(ordered),
        linked_count,
    )
    if unresolved_count:
        _LOG.warning("economic_cascades_chain_unresolved count=%s", unresolved_count)
    if coverage is CascadeCoverage.PARTIAL:
        _LOG.warning(
            "economic_cascades_partial_coverage notices=%s",
            ",".join(sorted(notices)),
        )
    return CascadeChainResult(
        chains=tuple(ordered),
        propagation_rows=tuple(propagation),
        notices=tuple(sorted(notices)),
        coverage=coverage,
        chain_count=len(ordered),
        linked_count=linked_count,
        unlinked_count=unlinked_count,
        unresolved_count=unresolved_count,
        max_depth=max_depth,
    )


def _chain_row(
    *,
    episode: CascadeEpisodeRow,
    upstream_token: str,
    downstream_recipe_id: str,
    depth: int,
    lag_windows: int,
    shortfall_share_milli: int,
    state: CascadeChainState,
    coverage: CascadeCoverage,
    evidence: tuple[str, ...],
    policy: EconomicCascadesPolicy,
    window_index: int | None = None,
) -> CascadeChainRow:
    window = episode.window_index if window_index is None else window_index
    return CascadeChainRow(
        chain_token=mint_chain_token(
            disruption_kind=episode.kind,
            upstream_token=upstream_token,
            downstream_recipe_id=downstream_recipe_id,
            depth=depth,
            lag_windows=lag_windows,
            window_index=window,
            evidence_tokens=evidence,
        ),
        window_index=window,
        window_tick=window_tick(window, policy),
        disruption_kind=episode.kind,
        upstream_token=upstream_token,
        downstream_recipe_id=downstream_recipe_id,
        depth=depth,
        lag_windows=lag_windows,
        shortfall_share_milli=shortfall_share_milli,
        state=state,
        coverage=coverage,
    )


def _propagation_rows(
    chains: Sequence[CascadeChainRow],
    episodes: Sequence[CascadeEpisodeRow],
    policy: EconomicCascadesPolicy,
) -> list[CascadePropagationRow]:
    grouped: dict[tuple[int, CascadeDisruptionKind], list[CascadeChainRow]] = {}
    for episode in episodes:
        grouped.setdefault((episode.window_index, episode.kind), [])
    for row in chains:
        grouped.setdefault((row.window_index, row.disruption_kind), []).append(row)
    rows: list[CascadePropagationRow] = []
    for (window_index, kind), group in sorted(
        grouped.items(), key=lambda item: (item[0][0], item[0][1].value)
    ):
        chain_count = len(group)
        linked = sum(
            1 for row in group if row.state is CascadeChainState.LINKED
        )
        unlinked = sum(
            1 for row in group if row.state is CascadeChainState.UNLINKED
        )
        unresolved = sum(
            1 for row in group if row.state is CascadeChainState.UNRESOLVED
        )
        total_depth = sum(row.depth for row in group)
        total_lag = sum(row.lag_windows for row in group)
        mean_depth = (
            (1_000 * total_depth + chain_count // 2) // chain_count
            if chain_count
            else 0
        )
        mean_lag = (
            (1_000 * total_lag + chain_count // 2) // chain_count
            if chain_count
            else 0
        )
        if linked >= policy.min_linked_chains:
            availability = CascadeAvailability.AVAILABLE
        elif linked > 0:
            availability = CascadeAvailability.INSUFFICIENT_SAMPLES
        else:
            availability = CascadeAvailability.UNAVAILABLE
        coverage = (
            CascadeCoverage.PARTIAL
            if any(row.coverage is CascadeCoverage.PARTIAL for row in group)
            else CascadeCoverage.COMPLETE
        )
        rows.append(
            CascadePropagationRow(
                window_index=window_index,
                window_tick=window_tick(window_index, policy),
                disruption_kind=kind,
                chain_count=chain_count,
                linked_chain_count=linked,
                unlinked_chain_count=unlinked,
                unresolved_chain_count=unresolved,
                mean_depth_milli=mean_depth,
                mean_lag_milli=mean_lag,
                downstream_stage_count=len(
                    {row.downstream_recipe_id for row in group}
                ),
                coverage=coverage,
                availability=availability,
            )
        )
    return rows
