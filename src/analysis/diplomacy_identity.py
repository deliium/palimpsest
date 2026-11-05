"""Stable ``dip-`` identities, read-only joins, and forward-only lineage."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from analysis.diplomacy_contract import (
    DIPLOMACY_IDENTITY_VERSION,
    DiplomacyLineageKind,
    derive_diplomacy_candidate_id,
    diplomacy_edge_id,
    require_diplomacy_candidate_id,
    require_diplomacy_token,
)
from analysis.diplomacy_detection import DiplomaticRelationCandidate
from analysis.diplomacy_rows import (
    DiplomacyTreatyDeclarationRow,
    DiplomacyTreatyRow,
    DiplomacyTreatyVersionRow,
    treaty_version_accepted,
)

__all__ = [
    "DIPLOMACY_ANALYSIS_VERSION",
    "DiplomacyAnalysis",
    "DiplomacyLineageEdge",
    "DiplomaticPartyJoinRow",
    "TreatyVersionLineageEdge",
    "assign_diplomacy_identities",
    "derive_diplomacy_lineage",
    "derive_treaty_version_lineage",
    "join_diplomacy_parties",
    "party_member_tokens",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.diplomacy_identity")
DIPLOMACY_ANALYSIS_VERSION: Final[str] = DIPLOMACY_IDENTITY_VERSION


@dataclass(frozen=True, slots=True)
class DiplomacyAnalysis:
    candidate_id: str
    candidate_key: str
    owner_token: str
    party_tokens: tuple[str, ...]
    status: str
    lanes: tuple[str, ...]
    creation_tick: int
    organization_candidate_ids: tuple[str, ...] = ()
    macro_society_candidate_ids: tuple[str, ...] = ()
    treaty_count: int = 0
    version_count: int = 0
    accepted_version_count: int = 0
    lineage_edge_count: int = 0

    def __post_init__(self) -> None:
        require_diplomacy_candidate_id(self.candidate_id)
        require_diplomacy_token(self.owner_token)


@dataclass(frozen=True, slots=True)
class DiplomacyLineageEdge:
    edge_id: str
    from_candidate_id: str
    to_candidate_id: str
    kind: str
    tick: int


@dataclass(frozen=True, slots=True)
class DiplomaticPartyJoinRow:
    owner_token: str
    party_token: str
    organization_candidate_ids: tuple[str, ...] = ()
    macro_society_candidate_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TreatyVersionLineageEdge:
    edge_id: str
    treaty_id: str
    from_version_id: str
    to_version_id: str
    change_kind: str
    tick: int


def derive_treaty_version_lineage(
    rows: Sequence[object],
) -> tuple[TreatyVersionLineageEdge, ...]:
    """Derive forward-only analytical treaty-version lineage edges."""

    import hashlib

    edges: list[TreatyVersionLineageEdge] = []
    for row in rows:
        treaty_id = getattr(row, "treaty_id", None)
        version_id = getattr(row, "version_id", None)
        change_kind = getattr(row, "change_kind", None)
        tick = getattr(row, "effective_tick", None)
        parents = getattr(row, "parent_version_ids", ())
        if (
            type(treaty_id) is not str
            or type(version_id) is not str
            or type(change_kind) is not str
            or type(tick) is not int
        ):
            continue
        for parent_id in parents:
            if type(parent_id) is not str:
                continue
            body = hashlib.sha256(
                "|".join(
                    (
                        "palimpsest.diplomacy.treaty-edge.v1",
                        treaty_id,
                        parent_id,
                        version_id,
                        change_kind,
                        str(tick),
                    )
                ).encode("utf-8")
            ).hexdigest()[:16]
            edges.append(
                TreatyVersionLineageEdge(
                    edge_id=f"dip-edge-{body}",
                    treaty_id=treaty_id,
                    from_version_id=parent_id,
                    to_version_id=version_id,
                    change_kind=change_kind,
                    tick=tick,
                )
            )
    return tuple(
        sorted(edges, key=lambda edge: (edge.tick, edge.treaty_id, edge.edge_id))
    )


def assign_diplomacy_identities(
    candidates: Sequence[DiplomaticRelationCandidate],
    *,
    creation_ticks: dict[str, int] | None = None,
    treaty_rows: Sequence[DiplomacyTreatyRow] = (),
    treaty_versions: Sequence[DiplomacyTreatyVersionRow] = (),
    treaty_declarations: Sequence[DiplomacyTreatyDeclarationRow] = (),
    treaty_lineage: Sequence[TreatyVersionLineageEdge] = (),
) -> tuple[DiplomacyAnalysis, ...]:
    """Mint content-addressed ``dip-`` ids from creation evidence only."""

    ticks = creation_ticks or {}
    rows = []
    seen: set[str] = set()
    for candidate in sorted(candidates, key=lambda row: row.candidate_key):
        tick = ticks.get(candidate.candidate_key, 0)
        candidate_id = derive_diplomacy_candidate_id(
            candidate.owner_token, candidate.party_tokens, tick
        )
        if candidate_id in seen:
            continue
        seen.add(candidate_id)
        candidate_parties = set(candidate.party_tokens)
        matched_treaties = tuple(
            treaty
            for treaty in treaty_rows
            if treaty.owner_token == candidate.owner_token
            and candidate_parties.issubset(set(treaty.party_tokens))
        )
        treaty_ids = {treaty.treaty_id for treaty in matched_treaties}
        matched_versions = tuple(
            version
            for version in treaty_versions
            if version.treaty_id in treaty_ids
        )
        rows.append(
            DiplomacyAnalysis(
                candidate_id=candidate_id,
                candidate_key=candidate.candidate_key,
                owner_token=candidate.owner_token,
                party_tokens=tuple(sorted(candidate.party_tokens)),
                status=candidate.status,
                lanes=tuple(sorted(candidate.lanes)),
                creation_tick=tick,
                treaty_count=len(matched_treaties),
                version_count=len(matched_versions),
                accepted_version_count=sum(
                    1
                    for version in matched_versions
                    if treaty_version_accepted(version, treaty_declarations)
                ),
                lineage_edge_count=sum(
                    1
                    for edge in treaty_lineage
                    if edge.treaty_id in treaty_ids
                ),
            )
        )
    return tuple(rows)


def derive_diplomacy_lineage(
    previous: Sequence[DiplomacyAnalysis],
    current: Sequence[DiplomacyAnalysis],
    *,
    tick: int,
) -> tuple[DiplomacyLineageEdge, ...]:
    """Emit forward-only lineage edges without renaming existing candidates."""

    edges: list[DiplomacyLineageEdge] = []
    current_by_key = {row.candidate_key: row for row in current}
    previous_by_key = {row.candidate_key: row for row in previous}
    for key, row in sorted(current_by_key.items()):
        if key in previous_by_key:
            edges.append(
                DiplomacyLineageEdge(
                    edge_id=diplomacy_edge_id(
                        previous_by_key[key].candidate_id,
                        row.candidate_id,
                        DiplomacyLineageKind.CONTINUED.value,
                        tick,
                    ),
                    from_candidate_id=previous_by_key[key].candidate_id,
                    to_candidate_id=row.candidate_id,
                    kind=DiplomacyLineageKind.CONTINUED.value,
                    tick=tick,
                )
            )
        else:
            edges.append(
                DiplomacyLineageEdge(
                    edge_id=diplomacy_edge_id(
                        row.candidate_id,
                        row.candidate_id,
                        DiplomacyLineageKind.EMERGED.value
                        if hasattr(DiplomacyLineageKind, "EMERGED")
                        else DiplomacyLineageKind.TRANSFORMED.value,
                        tick,
                    ),
                    from_candidate_id=row.candidate_id,
                    to_candidate_id=row.candidate_id,
                    kind=DiplomacyLineageKind.TRANSFORMED.value,
                    tick=tick,
                )
            )
    for key, row in sorted(previous_by_key.items()):
        if key not in current_by_key:
            edges.append(
                DiplomacyLineageEdge(
                    edge_id=diplomacy_edge_id(
                        row.candidate_id,
                        row.candidate_id,
                        DiplomacyLineageKind.ENDED.value,
                        tick,
                    ),
                    from_candidate_id=row.candidate_id,
                    to_candidate_id=row.candidate_id,
                    kind=DiplomacyLineageKind.ENDED.value,
                    tick=tick,
                )
            )
    return tuple(sorted(edges, key=lambda edge: (edge.tick, edge.edge_id)))


def _organization_members(row: object) -> tuple[str, ...]:
    members = getattr(row, "member_tokens", None)
    if members is None:
        members = getattr(row, "members", ())
    return tuple(str(getattr(item, "token", item)) for item in (members or ()))


def _organization_id(row: object) -> str | None:
    return getattr(row, "candidate_id", getattr(row, "organization_id", None))


def _macro_id(row: object) -> str | None:
    return getattr(row, "candidate_id", getattr(row, "macro_society_id", None))


def _macro_members(row: object) -> tuple[str, ...]:
    members = getattr(row, "member_tokens", None)
    if members is None:
        members = getattr(row, "members", ())
    return tuple(str(getattr(item, "token", item)) for item in (members or ()))


def join_diplomacy_parties(
    candidates: Sequence[DiplomacyAnalysis],
    *,
    organization_rows: Sequence[object] = (),
    macro_society_analysis: object | None = None,
) -> tuple[DiplomaticPartyJoinRow, ...]:
    """Join party tokens to existing ``org-``/``msoc-`` ids read-only."""

    macro_rows = getattr(macro_society_analysis, "candidates", ())
    rows = []
    for candidate in candidates:
        for token in candidate.party_tokens:
            org_ids = tuple(
                sorted(
                    str(_organization_id(row))
                    for row in organization_rows
                    if token in _organization_members(row)
                    or token == getattr(row, "anchor_ref", None)
                )
            )
            msoc_ids = tuple(
                sorted(
                    str(_macro_id(row))
                    for row in macro_rows
                    if token in _macro_members(row)
                    or token == getattr(row, "region_token", None)
                )
            )
            rows.append(
                DiplomaticPartyJoinRow(
                    owner_token=candidate.owner_token,
                    party_token=token,
                    organization_candidate_ids=org_ids,
                    macro_society_candidate_ids=msoc_ids,
                )
            )
    _LOG.debug("diplomacy_join matched=%s unmatched=%s", len(rows), 0)
    return tuple(sorted(rows, key=lambda row: (row.owner_token, row.party_token)))


def party_member_tokens(
    party_token: str,
    *,
    organization_rows: Sequence[object] = (),
    macro_society_analysis: object | None = None,
) -> tuple[str, ...]:
    """Resolve a party token to the person tokens it contains."""

    require_diplomacy_token(party_token)
    tokens: set[str] = {party_token}
    for row in organization_rows:
        if party_token in _organization_members(row) or party_token == getattr(
            row, "anchor_ref", None
        ):
            tokens.update(_organization_members(row))
    for row in getattr(macro_society_analysis, "candidates", ()):
        if party_token in _macro_members(row) or party_token == getattr(
            row, "region_token", None
        ):
            tokens.update(_macro_members(row))
    tokens.discard(party_token)
    return tuple(sorted(tokens))
