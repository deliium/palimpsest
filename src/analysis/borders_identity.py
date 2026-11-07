"""Content-addressed border candidates, forward-only lineage, read-only joins."""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Sequence
from typing import Final

from analysis.borders_contract import (
    BORDER_CANDIDATE_PREFIX,
    BORDER_EDGE_PREFIX,
    BorderCandidate,
    BorderClaimRow,
    BorderLineageEdge,
    BorderPatternRow,
)

_LOG: Final[logging.Logger] = logging.getLogger("analysis.borders.identity")


def _short(prefix: str, material: str) -> str:
    return f"{prefix}{hashlib.sha256(material.encode('utf-8')).hexdigest()[:16]}"


def border_candidate_id(location_tokens: Sequence[str]) -> str:
    """Owner-independent content address over sorted location tokens."""
    if isinstance(location_tokens, (str, bytes, set, frozenset)) or not isinstance(
        location_tokens, Sequence
    ):
        raise TypeError("location_tokens must be an ordered sequence")
    tokens = sorted({str(item) for item in location_tokens})
    if not tokens:
        raise ValueError("borders_lineage: empty_location_set")
    return _short(BORDER_CANDIDATE_PREFIX, "|".join(tokens))


def assign_border_identities(
    claims: Sequence[BorderClaimRow], patterns: Sequence[BorderPatternRow]
) -> tuple[BorderCandidate, ...]:
    """One owner-independent candidate per distinct location set."""
    del patterns
    groups: dict[tuple[str, ...], list[BorderClaimRow]] = {}
    for claim in claims:
        groups.setdefault(tuple(sorted(claim.location_tokens)), []).append(claim)
    candidates: list[BorderCandidate] = []
    for locations, group in sorted(groups.items()):
        status = group[0].status
        for claim in group:
            if claim.status == "disputed":
                status = "disputed"
            elif claim.status == "recognized" and status != "disputed":
                status = "recognized"
        edges: set[tuple[str, str]] = set()
        for claim in group:
            edges.update(claim.boundary_edge_tokens)
        first_tick = 0
        last_tick = 0
        candidates.append(
            BorderCandidate(
                candidate_id=border_candidate_id(locations),
                location_tokens=locations,
                boundary_edge_tokens=tuple(sorted(edges)),
                status=status,
                evidence_count=len(group),
                first_tick=first_tick,
                last_tick=last_tick,
            )
        )
    candidates.sort(key=lambda item: item.candidate_id)
    return tuple(candidates)


def derive_border_lineage(
    candidates: Sequence[BorderCandidate],
) -> tuple[BorderLineageEdge, ...]:
    """Forward-only parent/child edges over ordered candidate snapshots."""
    ordered = sorted(candidates, key=lambda item: (item.first_tick, item.candidate_id))
    edges: list[BorderLineageEdge] = []
    if not ordered:
        return ()
    for candidate in ordered:
        parent = f"bord-start-{candidate.candidate_id[len(BORDER_CANDIDATE_PREFIX) :]}"
        edges.append(
            BorderLineageEdge(
                edge_id=_short(
                    BORDER_EDGE_PREFIX, f"{parent}|{candidate.candidate_id}|emerged"
                ),
                parent_token=parent,
                child_token=candidate.candidate_id,
                kind="emerged",
                first_tick=candidate.first_tick,
                last_tick=candidate.first_tick,
            )
        )
    for index in range(len(ordered) - 1):
        left = ordered[index]
        right = ordered[index + 1]
        left_set = set(left.location_tokens)
        right_set = set(right.location_tokens)
        if left_set == right_set:
            kind = "continued"
        elif left_set < right_set:
            kind = "transformed"
        elif left_set > right_set:
            kind = "transformed"
        elif left_set & right_set:
            kind = "transformed"
        else:
            kind = "dissolved"
        edges.append(
            BorderLineageEdge(
                edge_id=_short(
                    BORDER_EDGE_PREFIX,
                    f"{left.candidate_id}|{right.candidate_id}|{kind}",
                ),
                parent_token=left.candidate_id,
                child_token=right.candidate_id,
                kind=kind,
                first_tick=min(left.first_tick, right.first_tick),
                last_tick=max(left.last_tick, right.last_tick),
            )
        )
    # Explicit terminal dissolution for the last candidate.
    last = ordered[-1]
    terminal = f"bord-end-{last.candidate_id[len(BORDER_CANDIDATE_PREFIX) :]}"
    edges.append(
        BorderLineageEdge(
            edge_id=_short(
                BORDER_EDGE_PREFIX, f"{last.candidate_id}|{terminal}|dissolved"
            ),
            parent_token=last.candidate_id,
            child_token=terminal,
            kind="dissolved",
            first_tick=last.last_tick,
            last_tick=last.last_tick,
        )
    )
    edges.sort(key=lambda item: (item.parent_token, item.child_token, item.edge_id))
    _LOG.debug(
        "borders_identity candidates=%s edge_count=%s", len(candidates), len(edges)
    )
    return tuple(edges)


def join_border_identities(
    candidates: Sequence[BorderCandidate],
    org_candidates: Sequence[object] = (),
    macro_candidates: Sequence[object] = (),
) -> tuple[tuple[str, str, str], ...]:
    """Read-only anchor joins. Never mints, renames, splits, or merges ids."""
    joins: list[tuple[str, str, str]] = []
    for candidate in candidates:
        locations = set(candidate.location_tokens)
        for kind, items in (("org", org_candidates), ("msoc", macro_candidates)):
            for item in items:
                references = getattr(item, "border_domain_tokens", None)
                if references is not None and locations & set(references):
                    target = (
                        getattr(item, "organization_id", None)
                        or getattr(item, "society_id", None)
                        or getattr(item, "candidate_id", None)
                    )
                    if type(target) is str and target:
                        joins.append((candidate.candidate_id, kind, target))
    joins.sort()
    return tuple(joins)


def split_merge_lineage(
    parents: Sequence[BorderCandidate], children: Sequence[BorderCandidate]
) -> tuple[BorderLineageEdge, ...]:
    """Explicit split/merge helper used when snapshots are supplied in pairs."""
    edges: list[BorderLineageEdge] = []
    for parent in parents:
        parent_set = set(parent.location_tokens)
        matches = [
            child for child in children if parent_set & set(child.location_tokens)
        ]
        if len(matches) > 1:
            for child in matches:
                edges.append(
                    BorderLineageEdge(
                        edge_id=_short(
                            BORDER_EDGE_PREFIX,
                            f"{parent.candidate_id}|{child.candidate_id}|split",
                        ),
                        parent_token=parent.candidate_id,
                        child_token=child.candidate_id,
                        kind="split",
                        first_tick=child.first_tick,
                        last_tick=child.last_tick,
                    )
                )
    for child in children:
        child_set = set(child.location_tokens)
        matches = [
            parent for parent in parents if child_set & set(parent.location_tokens)
        ]
        if len(matches) > 1:
            for parent in matches:
                edges.append(
                    BorderLineageEdge(
                        edge_id=_short(
                            BORDER_EDGE_PREFIX,
                            f"{parent.candidate_id}|{child.candidate_id}|merge",
                        ),
                        parent_token=parent.candidate_id,
                        child_token=child.candidate_id,
                        kind="merge",
                        first_tick=child.first_tick,
                        last_tick=child.last_tick,
                    )
                )
    edges.sort(key=lambda item: item.edge_id)
    return tuple(edges)


__all__ = [
    "assign_border_identities",
    "border_candidate_id",
    "derive_border_lineage",
    "join_border_identities",
    "split_merge_lineage",
]
