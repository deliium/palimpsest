"""Detached support networks, citation aggregates, and matched performance."""

from __future__ import annotations

import logging
from typing import Final

from analysis.competing_theories_models import (
    MAX_THEORY_WINDOWS,
    CompetingTheoriesAnalysisError,
    CompetingTheoryAnalysis,
    CompetingTheoryFacts,
    TheoryCaseRow,
    TheoryCitationFact,
    TheoryCitationRow,
    TheoryClaimRow,
    TheoryCommunityRow,
    TheoryCoverageRow,
    TheorySupportEdge,
    TheoryTransmissionEdge,
)

__all__ = ["harvest_competing_theories_analysis"]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.competing_theories.analysis")


def _windows(
    facts: CompetingTheoryFacts,
) -> tuple[tuple[int, int], ...]:
    ticks: list[int] = []
    for claim in facts.claims:
        ticks.append(claim.created_tick)
    for stance in facts.stances:
        ticks.append(stance.tick)
    for receipt in facts.receipts:
        ticks.append(receipt.tick)
    for forecast in facts.forecasts:
        ticks.append(forecast.issued_tick)
        ticks.append(forecast.target_tick)
    for _, tick in facts.owner_last_ticks:
        ticks.append(tick)
    if not ticks:
        return ()
    high = max(ticks)
    width = max(1, facts.window_ticks)
    count = high // width + 1
    starts = range(0, count * width, width)
    windows = tuple((start, start + width - 1) for start in starts)
    return windows[-MAX_THEORY_WINDOWS:]


def _claim_context(facts: CompetingTheoryFacts) -> dict[str, str]:
    return {row.claim_token: row.context_token for row in facts.claims}


def _latest_stances(
    facts: CompetingTheoryFacts, *, window_end: int
) -> dict[tuple[str, str], str]:
    latest: dict[tuple[str, str], tuple[int, str, str]] = {}
    for row in facts.stances:
        if row.tick > window_end:
            continue
        key = (row.owner_token, row.context_token)
        current = latest.get(key)
        candidate = (row.tick, row.revision, row.claim_token)
        if current is None or candidate[:2] > current[:2]:
            latest[key] = candidate
    return {key: value[2] for key, value in latest.items()}


def _components(nodes: set[str], edges: set[tuple[str, str]]) -> list[tuple[str, ...]]:
    adjacency: dict[str, set[str]] = {node: set() for node in nodes}
    for left, right in edges:
        if left not in adjacency or right not in adjacency:
            continue
        adjacency[left].add(right)
        adjacency[right].add(left)
    components: list[tuple[str, ...]] = []
    seen: set[str] = set()
    for node in sorted(nodes):
        if node in seen:
            continue
        stack = [node]
        group: list[str] = []
        seen.add(node)
        while stack:
            current = stack.pop()
            group.append(current)
            for neighbour in sorted(adjacency[current]):
                if neighbour not in seen:
                    seen.add(neighbour)
                    stack.append(neighbour)
        components.append(tuple(sorted(group)))
    return components


def harvest_competing_theories_analysis(
    facts: CompetingTheoryFacts,
) -> CompetingTheoryAnalysis:
    if type(facts) is not CompetingTheoryFacts:
        raise CompetingTheoriesAnalysisError("facts_invalid_type")
    windows = _windows(facts)
    if not windows:
        raise CompetingTheoriesAnalysisError("facts_empty")
    claim_context = _claim_context(facts)
    all_windows = len(
        range(0, (max(end for _, end in windows) + 1), facts.window_ticks)
    )
    omitted = max(0, all_windows - len(windows))
    structure: list[tuple[int, int, int, int]] = []
    support: list[TheorySupportEdge] = []
    communities: list[TheoryCommunityRow] = []
    citation_rows: list[tuple[int, int, str, str, int, int, int]] = []
    prediction_rows: list[tuple[int, int, int, int, int, int]] = []
    failure_rows: list[tuple[int, int, int]] = []
    transmission: list[TheoryTransmissionEdge] = []
    coverage: list[TheoryCoverageRow] = []
    seen_support: set[tuple[int, str, str]] = set()
    seen_transmission: set[tuple[int, str, str, str, str]] = set()
    for start, end in windows:
        stances = _latest_stances(facts, window_end=end)
        supporters: dict[str, set[str]] = {}
        for (owner, _context), claim in stances.items():
            if claim not in claim_context:
                continue
            supporters.setdefault(claim, set()).add(owner)
            key = (start, owner, claim)
            if key not in seen_support:
                seen_support.add(key)
                support.append(TheorySupportEdge(start, end, owner, claim))
        contexts: dict[str, set[str]] = {}
        for claim in claim_context:
            contexts.setdefault(claim_context[claim], set()).add(claim)
        rival_pairs = sum(
            len({claim for claim in claims if claim in supporters})
            * (len({claim for claim in claims if claim in supporters}) - 1)
            // 2
            for claims in contexts.values()
        )
        structure.append((start, end, len(supporters), rival_pairs))
        for claim, owners in sorted(supporters.items()):
            edges: set[tuple[str, str]] = set()
            for receipt in facts.receipts:
                if receipt.tick < start or receipt.tick > end:
                    continue
                if receipt.claim_token != claim:
                    continue
                if receipt.act not in {"support", "teach"}:
                    continue
                if receipt.speaker_token in owners and receipt.learner_token in owners:
                    edges.add((receipt.speaker_token, receipt.learner_token))
            for index, component in enumerate(_components(owners, edges)):
                communities.append(
                    TheoryCommunityRow(
                        start,
                        end,
                        claim,
                        f"community:{start}:{claim}:{index}",
                        component,
                    )
                )
        citation_groups: dict[tuple[str, str], list[TheoryCitationFact]] = {}
        for citation in facts.citations:
            if citation.tick < start or citation.tick > end:
                continue
            citation_groups.setdefault((citation.kind, citation.polarity), []).append(
                citation
            )
        for (kind, polarity), rows in sorted(citation_groups.items()):
            roots = {
                row.root_token for row in rows if row.independent and row.root_token
            }
            pointers = sum(1 for row in rows if not row.independent)
            citation_rows.append(
                (start, end, kind, polarity, len(rows), len(roots), pointers)
            )
        issued = [row for row in facts.forecasts if start <= row.issued_tick <= end]
        predictions = sum(len(row.rows) for row in issued)
        scored = 0
        hits = 0
        misses = 0
        unscored = 0
        for row in issued:
            if row.state == "scored":
                hit_map = dict(row.hits)
                for claim_token, _, _, brier in row.rows:
                    scored += 1
                    if hit_map.get(claim_token, brier == 0):
                        hits += 1
                    else:
                        misses += 1
            elif row.state != "pending":
                unscored += 1
        prediction_rows.append((start, end, predictions, scored, hits, len(issued)))
        failure_rows.append((start, end, misses))
        for receipt in facts.receipts:
            if receipt.tick < start or receipt.tick > end:
                continue
            if receipt.act not in {"support", "teach"}:
                continue
            transmission_key = (
                start,
                receipt.speaker_token,
                receipt.learner_token,
                receipt.claim_token,
                receipt.act,
            )
            if transmission_key in seen_transmission:
                continue
            seen_transmission.add(transmission_key)
            transmission.append(
                TheoryTransmissionEdge(
                    start,
                    end,
                    receipt.speaker_token,
                    receipt.learner_token,
                    receipt.claim_token,
                    receipt.act,
                )
            )
        death = dict(facts.death_ticks)
        last = dict(facts.owner_last_ticks)
        observed = 0
        unavailable = 0
        for owner in facts.owner_tokens:
            if owner in death and death[owner] <= end:
                unavailable += 1
                continue
            watermark = last.get(owner)
            if watermark is None or watermark < start:
                unavailable += 1
                continue
            observed += 1
        coverage.append(
            TheoryCoverageRow(
                start,
                end,
                observed,
                len(facts.owner_tokens),
                unavailable,
                omitted,
            )
        )
    paired: list[tuple[str, str, int, int]] = []
    for forecast in facts.forecasts:
        if forecast.state != "scored":
            continue
        paired_rows: list[tuple[str, int]] = sorted(
            (claim, brier) for claim, _, _, brier in forecast.rows
        )
        if len(paired_rows) < 2:
            continue
        paired.append(
            (
                forecast.case_token,
                forecast.owner_token,
                paired_rows[0][1],
                paired_rows[1][1],
            )
        )
    paired_count = sum(1 for row in paired if row[2] is not None)
    paired_difference = (
        sum(row[3] - row[2] for row in paired) if paired_count >= 3 else 0
    )
    width = max(1, facts.window_ticks)

    def _window(tick: int) -> tuple[int, int]:
        start = tick // width * width
        return start, start + width - 1

    claim_rows = tuple(
        TheoryClaimRow(
            claim_token=row.claim_token,
            owner_token=row.owner_token,
            context_token=row.context_token,
            account=row.account,
            category=row.category,
            created_tick=row.created_tick,
            window_start=_window(row.created_tick)[0],
            window_end=_window(row.created_tick)[1],
        )
        for row in sorted(
            facts.claims, key=lambda row: (row.created_tick, row.claim_token)
        )
    )
    citation_edges = tuple(
        TheoryCitationRow(
            claim_token=row.claim_token,
            owner_token=row.owner_token,
            window_start=_window(row.tick)[0],
            window_end=_window(row.tick)[1],
            kind=row.kind,
            polarity=row.polarity,
            root_token=row.root_token,
            independent=row.independent,
            tick=row.tick,
        )
        for row in sorted(
            facts.citations,
            key=lambda row: (row.tick, row.claim_token, row.kind),
        )
    )
    case_rows = tuple(
        TheoryCaseRow(
            case_token=row.case_token,
            owner_token=row.owner_token,
            window_start=_window(row.issued_tick)[0],
            window_end=_window(row.issued_tick)[1],
            state=row.state,
            observed_category=row.observed_category or "",
            issued_tick=row.issued_tick,
            target_tick=row.target_tick,
            rows=tuple(
                sorted(
                    (
                        claim_token,
                        predicted,
                        ",".join(
                            str(value)
                            for value in dict(row.vectors).get(
                                claim_token,
                                (probabilities,),
                            )
                        ),
                        brier,
                    )
                    for claim_token, predicted, probabilities, brier in row.rows
                )
            ),
        )
        for row in sorted(
            facts.forecasts, key=lambda row: (row.issued_tick, row.case_token)
        )
    )
    analysis = CompetingTheoryAnalysis(
        structure_rows=tuple(structure),
        support_edges=tuple(support),
        communities=tuple(communities),
        citation_rows=tuple(citation_rows),
        prediction_rows=tuple(prediction_rows),
        failure_rows=tuple(failure_rows),
        transmission_edges=tuple(transmission),
        coverage=tuple(coverage),
        claim_rows=claim_rows,
        case_rows=case_rows,
        citation_edges=citation_edges,
        claim_count=len(facts.claims),
        rival_pair_count=sum(row[3] for row in structure),
        support_edge_count=len(support),
        community_count=len(communities),
        citation_count=len(facts.citations),
        verified_root_count=len(
            {
                row.root_token
                for row in facts.citations
                if row.independent and row.root_token
            }
        ),
        prediction_count=sum(len(row.rows) for row in facts.forecasts),
        scored_count=sum(
            len(row.rows) for row in facts.forecasts if row.state == "scored"
        ),
        failure_count=sum(row[2] for row in failure_rows),
        unscored_count=sum(
            1 for row in facts.forecasts if row.state not in {"pending", "scored"}
        ),
        delivered_count=sum(
            1
            for row in facts.receipts
            if row.kind == "communicated" and row.act == "support"
        ),
        teaching_count=sum(1 for row in facts.receipts if row.kind == "taught"),
        paired_count=paired_count,
        paired_brier_difference=paired_difference,
    )
    _LOG.debug(
        "competing_theories_analysis claims=%s supports=%s communities=%s",
        analysis.claim_count,
        analysis.support_edge_count,
        analysis.community_count,
    )
    return analysis
