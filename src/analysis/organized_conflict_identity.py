# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,index,call-overload,attr-defined,no-untyped-def,unused-ignore,type-arg,comparison-overlap"
"""Stable analytical identities, forward-only lineage, and read-only joins."""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Sequence
from dataclasses import dataclass, replace
from itertools import pairwise
from typing import Final

from analysis.organized_conflict_detection import ConflictEpisodeCandidate

__all__ = [
    "ConflictLineageEdge",
    "assign_organized_conflict_identities",
    "derive_organized_conflict_lineage",
    "join_organized_conflict_identities",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.organized_conflict.identity")


@dataclass(frozen=True, slots=True)
class ConflictLineageEdge:
    edge_id: str
    from_id: str
    to_id: str
    kind: str
    tick: int

    def __post_init__(self) -> None:
        if not self.edge_id.startswith("oc-edge-"):
            raise ValueError("ConflictLineageEdge.edge_id is invalid")
        if self.kind not in {"continued", "transformed", "split", "merge", "ended"}:
            raise ValueError("ConflictLineageEdge.kind is not closed")
        if self.tick < 0:
            raise ValueError("conflict_backward_lineage")


def assign_organized_conflict_identities(
    candidates: Sequence[ConflictEpisodeCandidate],
) -> tuple[ConflictEpisodeCandidate, ...]:
    """Assign stable ``oc-`` ids from creation evidence only."""

    assigned: list[ConflictEpisodeCandidate] = []
    seen: set[str] = set()
    for candidate in sorted(
        candidates, key=lambda row: (row.start_tick, row.candidate_key)
    ):
        candidate_id = (
            "oc-"
            + hashlib.sha256(
                (
                    "palimpsest.organized_conflict.identity.v1|"
                    f"{candidate.candidate_key}|{candidate.start_tick}"
                ).encode()
            ).hexdigest()[:16]
        )
        if candidate_id in seen:
            raise ValueError("conflict_duplicate_candidate")
        seen.add(candidate_id)
        assigned.append(replace(candidate, candidate_id=candidate_id))
    _LOG.debug(
        "organized_conflict_identity candidates=%s edges=%s joins=%s",
        len(assigned),
        0,
        0,
    )
    return tuple(assigned)


def _edge(previous, current, kind: str) -> ConflictLineageEdge | None:
    previous_id = previous.candidate_id or previous.candidate_key
    current_id = current.candidate_id or current.candidate_key
    if not previous_id.startswith("oc-") or not current_id.startswith("oc-"):
        return None
    edge_id = (
        "oc-edge-"
        + hashlib.sha256(
            (
                "palimpsest.organized_conflict.edge.v1|"
                f"{previous_id}|{current_id}|{kind}|{current.start_tick}"
            ).encode()
        ).hexdigest()[:16]
    )
    return ConflictLineageEdge(
        edge_id=edge_id,
        from_id=previous_id,
        to_id=current_id,
        kind=kind,
        tick=current.start_tick,
    )


def derive_organized_conflict_lineage(
    candidates: Sequence[ConflictEpisodeCandidate],
) -> tuple[ConflictLineageEdge, ...]:
    """Derive forward-only continuation, transformation, split, and merge edges."""

    identified = [
        candidate
        for candidate in sorted(
            candidates,
            key=lambda row: (row.start_tick, row.candidate_id or row.candidate_key),
        )
        if candidate.candidate_id.startswith("oc-")
    ]
    edges: dict[str, ConflictLineageEdge] = {}

    def add(edge: ConflictLineageEdge | None) -> None:
        if edge is not None:
            edges.setdefault(edge.edge_id, edge)

    for previous, current in pairwise(identified):
        if previous.classification == current.classification:
            kind = "continued"
        elif set(previous.participant_tokens) & set(current.participant_tokens):
            kind = "transformed"
        else:
            kind = "ended"
        add(_edge(previous, current, kind))

    for current in identified:
        predecessors = [
            previous
            for previous in identified
            if previous.end_tick < current.start_tick
            and set(previous.participant_tokens) & set(current.participant_tokens)
        ]
        if len(predecessors) >= 2:
            for previous in predecessors:
                add(_edge(previous, current, "merge"))

    for previous in identified:
        successors = [
            current
            for current in identified
            if previous.end_tick < current.start_tick
            and set(previous.participant_tokens) & set(current.participant_tokens)
        ]
        if len(successors) >= 2:
            for current in successors:
                add(_edge(previous, current, "split"))

    return tuple(sorted(edges.values(), key=lambda row: row.edge_id))


def _identity_tokens(
    candidates: Sequence[object],
) -> tuple[dict[str, str], dict[str, str]]:
    organizations: dict[str, str] = {}
    societies: dict[str, str] = {}
    for candidate in candidates:
        identifier = str(
            getattr(candidate, "candidate_id", None)
            or getattr(candidate, "organization_id", None)
            or getattr(candidate, "society_id", None)
            or ""
        )
        if identifier.startswith("org-"):
            for token in getattr(candidate, "member_tokens", ()) or getattr(
                candidate, "participant_tokens", ()
            ):
                organizations[token] = identifier
        elif identifier.startswith("msoc-"):
            for token in getattr(candidate, "member_tokens", ()) or getattr(
                candidate, "participant_tokens", ()
            ):
                societies[token] = identifier
    return organizations, societies


def join_organized_conflict_identities(
    candidates: Sequence[ConflictEpisodeCandidate],
    organization_candidates: Sequence[object] = (),
    macro_society_candidates: Sequence[object] = (),
) -> tuple[ConflictEpisodeCandidate, ...]:
    """Attach existing ``org-``/``msoc-`` ids read-only; never mint or mutate."""

    organizations, societies = _identity_tokens(organization_candidates)
    organizations.update(_identity_tokens(macro_society_candidates)[0])
    societies.update(_identity_tokens(macro_society_candidates)[1])
    joined: list[ConflictEpisodeCandidate] = []
    for candidate in candidates:
        org_ids = tuple(
            sorted(
                {
                    organizations[token]
                    for token in candidate.participant_tokens
                    if token in organizations
                }
            )
        )
        society_ids = tuple(
            sorted(
                {
                    societies[token]
                    for token in candidate.participant_tokens
                    if token in societies
                }
            )
        )
        joined.append(
            replace(
                candidate,
                org_ids=org_ids,
                macro_society_ids=society_ids,
            )
        )
    return tuple(joined)
