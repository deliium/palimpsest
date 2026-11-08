# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,index,call-overload,attr-defined,no-untyped-def,unused-ignore,type-arg,comparison-overlap,redundant-cast,operator,misc,return-value,valid-type,override"
"""Content-addressed ``mig-`` candidates, forward-only lineage, read-only joins.

Candidate tokens are content addresses over canonical, ordered material. Lineage
is forward-only: a previous candidate is never rewritten. Existing organization
and macro-society identities are only read; nothing here mints, renames,
splits, merges, or dissolves them. This module imports no cognition, runtime,
experiments, API, persistence, or observer module.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Final

from analysis.migration_displacement_contract import (
    MIGRATION_CANDIDATE_PREFIX,
    analysis_migration_candidate_id,
)
from analysis.migration_displacement_policy import MigrationDisplacementAnalysisPolicy
from analysis.migration_displacement_rows import (
    NONE_TOKEN,
    MigrationCandidateRow,
    MigrationClusterRow,
    MigrationLineageRow,
    MigrationOutcomeRow,
    MigrationWaveRow,
)

__all__ = [
    "MIGRATION_CANDIDATE_PREFIX",
    "MigrationCandidateRow",
    "join_read_only_identities",
    "link_migration_lineage",
    "migration_candidate_row",
    "migration_candidate_token",
    "migration_candidates_from_rows",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.migration_displacement.identity"
)

_OVERLAP_THRESHOLD: Final[float] = 0.5
_READ_ONLY_ERROR: Final[str] = "migration_identity: read_only_identity"


def migration_candidate_token(kind: str, material: str) -> str:
    """Content-addressed candidate token over canonical material."""
    return analysis_migration_candidate_id(kind, material)


def migration_candidate_row(
    kind: str,
    candidate_token: str,
    *,
    status: str = "observed",
    first_tick: int = 0,
    last_tick: int = 0,
    member_count: int = 0,
    origin_token: str = NONE_TOKEN,
    destination_token: str = NONE_TOKEN,
    classification: str = "unknown",
    coverage: str = "complete",
    member_tokens: Sequence[str] = (),
) -> MigrationCandidateRow:
    """Build one candidate summary row; the token must be a ``mig-`` address."""
    return MigrationCandidateRow(
        candidate_token=candidate_token,
        kind=kind,
        status=status,
        first_tick=first_tick,
        last_tick=last_tick,
        member_count=member_count,
        origin_token=origin_token,
        destination_token=destination_token,
        classification=classification,
        coverage=coverage,
        member_tokens=tuple(sorted(set(member_tokens))),
    )


def _status(coverage: str) -> str:
    return "observed" if coverage == "complete" else "partial"


def migration_candidates_from_rows(
    waves: Sequence[MigrationWaveRow],
    clusters: Sequence[MigrationClusterRow],
    outcomes: Sequence[MigrationOutcomeRow],
) -> tuple[MigrationCandidateRow, ...]:
    """One candidate summary per wave, cluster, and outcome row."""
    rows: list[MigrationCandidateRow] = []
    for wave in waves:
        rows.append(
            migration_candidate_row(
                "wave",
                wave.wave_token,
                status=_status(wave.coverage),
                first_tick=wave.start_tick,
                last_tick=wave.end_tick,
                member_count=len(wave.participant_tokens),
                origin_token=wave.origin_token,
                destination_token=wave.destination_token,
                classification=wave.displacement_classification,
                coverage=wave.coverage,
                member_tokens=wave.participant_tokens,
            )
        )
    for cluster in clusters:
        rows.append(
            migration_candidate_row(
                "cluster",
                cluster.cluster_token,
                status=_status(cluster.coverage),
                first_tick=cluster.first_tick,
                last_tick=cluster.last_tick,
                member_count=len(cluster.member_tokens),
                classification="unknown",
                coverage=cluster.coverage,
                member_tokens=cluster.member_tokens,
            )
        )
    for outcome in outcomes:
        rows.append(
            migration_candidate_row(
                "outcome",
                outcome.outcome_token,
                status=_status(outcome.coverage),
                member_count=1,
                destination_token=outcome.destination_token,
                classification=outcome.classification,
                coverage=outcome.coverage,
                member_tokens=(outcome.participant_token,),
            )
        )
    rows.sort(key=lambda item: item.candidate_token)
    return tuple(rows)


def _overlap(left: MigrationCandidateRow, right: MigrationCandidateRow) -> float:
    a, b = set(left.member_tokens), set(right.member_tokens)
    if not a or not b:
        return 1.0 if left.candidate_token == right.candidate_token else 0.0
    return len(a & b) / min(len(a), len(b))


def _require_candidates(name: str, rows: object) -> tuple[MigrationCandidateRow, ...]:
    if isinstance(rows, (str, bytes, Mapping)) or not isinstance(rows, Sequence):
        raise TypeError(f"{name} must be a sequence")
    for item in rows:
        if type(item) is not MigrationCandidateRow:
            raise ValueError("migration_identity: candidate_token")
    return tuple(rows)


def link_migration_lineage(
    previous: Sequence[MigrationCandidateRow],
    current: Sequence[MigrationCandidateRow],
    policy: MigrationDisplacementAnalysisPolicy,
) -> tuple[MigrationLineageRow, ...]:
    """Forward-only lineage between previous and current candidates.

    ``continued`` and ``transformed`` need member overlap of at least one half;
    ``split``, ``merge``, ``dissolved``, and ``emerged`` follow from the links.
    A previous candidate is never rewritten.
    """
    if type(policy) is not MigrationDisplacementAnalysisPolicy:
        raise ValueError("migration_detection: invalid_policy")
    before = _require_candidates("previous", previous)
    after = _require_candidates("current", current)
    links: list[tuple[MigrationCandidateRow, MigrationCandidateRow]] = []
    for old in before:
        for new in after:
            if old.kind != new.kind:
                continue
            linked = old.candidate_token == new.candidate_token or (
                _overlap(old, new) >= _OVERLAP_THRESHOLD
            )
            if not linked:
                continue
            if old.first_tick > new.first_tick:
                raise ValueError("migration_identity: lineage_not_forward")
            links.append((old, new))
    successors: dict[str, int] = {}
    predecessors: dict[str, int] = {}
    for old, new in links:
        successors[old.candidate_token] = successors.get(old.candidate_token, 0) + 1
        predecessors[new.candidate_token] = predecessors.get(new.candidate_token, 0) + 1
    rows: list[MigrationLineageRow] = []
    for old, new in links:
        if successors[old.candidate_token] >= 2:
            relation = "split"
        elif predecessors[new.candidate_token] >= 2:
            relation = "merge"
        elif old.destination_token == new.destination_token:
            relation = "continued"
        else:
            relation = "transformed"
        rows.append(
            MigrationLineageRow(
                candidate_token=new.candidate_token,
                previous_token=old.candidate_token,
                relation=relation,
                first_tick=min(old.first_tick, new.first_tick),
                last_tick=max(old.last_tick, new.last_tick),
            )
        )
    for old in before:
        if old.candidate_token not in successors:
            rows.append(
                MigrationLineageRow(
                    candidate_token=NONE_TOKEN,
                    previous_token=old.candidate_token,
                    relation="dissolved",
                    first_tick=old.last_tick,
                    last_tick=old.last_tick,
                )
            )
    for new in after:
        if new.candidate_token not in predecessors:
            rows.append(
                MigrationLineageRow(
                    candidate_token=new.candidate_token,
                    previous_token=NONE_TOKEN,
                    relation="emerged",
                    first_tick=new.first_tick,
                    last_tick=new.first_tick,
                )
            )
    rows.sort(
        key=lambda item: (item.first_tick, item.candidate_token, item.previous_token)
    )
    _LOG.debug(
        "migration_lineage previous=%s current=%s edges=%s",
        len(before),
        len(after),
        len(rows),
    )
    return tuple(rows)


def _read_only_items(
    identities: object, prefix: str
) -> tuple[tuple[str, frozenset[str]], ...]:
    if identities is None:
        return ()
    if isinstance(identities, Mapping):
        items = list(identities.items())
    elif isinstance(identities, Sequence) and not isinstance(identities, (str, bytes)):
        items = list(identities)
    else:
        raise ValueError(_READ_ONLY_ERROR)
    out: list[tuple[str, frozenset[str]]] = []
    for item in items:
        if type(item) is not tuple or len(item) != 2:
            raise ValueError(_READ_ONLY_ERROR)
        token, members = item
        if (
            type(token) is not str
            or not token.startswith(prefix)
            or isinstance(members, (str, bytes))
            or not isinstance(members, Sequence | set | frozenset)
        ):
            raise ValueError(_READ_ONLY_ERROR)
        out.append((token, frozenset(str(member) for member in members)))
    return tuple(sorted(out, key=lambda pair: pair[0]))


def join_read_only_identities(
    candidates: Sequence[MigrationCandidateRow],
    org_tokens: object,
    msoc_tokens: object,
) -> tuple[tuple[str, str], ...]:
    """Attach existing ``org-``/``msoc-`` tokens by member-token overlap.

    Returns sorted ``(candidate_token, identity_token)`` pairs. Inputs are only
    read: no identity is minted, renamed, split, merged, or dissolved, and any
    token outside the two read-only prefixes is rejected.
    """
    rows = _require_candidates("candidates", candidates)
    joins: set[tuple[str, str]] = set()
    for prefix, source in (("org-", org_tokens), ("msoc-", msoc_tokens)):
        for identity, members in _read_only_items(source, prefix):
            for row in rows:
                if members & set(row.member_tokens):
                    joins.add((row.candidate_token, identity))
    return tuple(sorted(joins))
