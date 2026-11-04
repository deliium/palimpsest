"""Deterministic inter-society relation candidate detection."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from analysis.diplomacy_contract import (
    DiplomacyAnalysisError,
    DiplomaticRelationStatus,
    diplomacy_candidate_key,
)
from analysis.diplomacy_lanes import InterSocietyRelationRow
from analysis.diplomacy_rows import DiplomacyHarvestRows

__all__ = [
    "DiplomaticRelationCandidate",
    "DiplomaticRelationMember",
    "detect_diplomacy_candidates",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.diplomacy_detection")


@dataclass(frozen=True, slots=True)
class DiplomaticRelationMember:
    owner_token: str
    party_token: str
    party_kind: str
    lane_counts: tuple[tuple[str, int], ...] = ()

    def __post_init__(self) -> None:
        if type(self.owner_token) is not str or not self.owner_token:
            raise DiplomacyAnalysisError("diplomacy_invalid_row")
        if type(self.party_token) is not str or not self.party_token:
            raise DiplomacyAnalysisError("diplomacy_invalid_row")


@dataclass(frozen=True, slots=True)
class DiplomaticRelationCandidate:
    candidate_key: str
    owner_token: str
    party_tokens: tuple[str, ...]
    lanes: tuple[str, ...]
    status: str

    def __post_init__(self) -> None:
        if type(self.candidate_key) is not str or not self.candidate_key:
            raise DiplomacyAnalysisError("diplomacy_invalid_row")
        if self.status not in {member.value for member in DiplomaticRelationStatus}:
            raise DiplomacyAnalysisError("diplomacy_invalid_row")
        if len(self.party_tokens) < 2:
            raise DiplomacyAnalysisError("diplomacy_invalid_row")


def detect_diplomacy_candidates(
    diplomacy_rows: DiplomacyHarvestRows,
    lane_rows: Sequence[InterSocietyRelationRow],
    *,
    max_candidates: int = 2048,
) -> tuple[DiplomaticRelationCandidate, ...]:
    """Group retained evidence into unordered owner/party candidates."""

    if type(diplomacy_rows) is not DiplomacyHarvestRows:
        raise TypeError("diplomacy_rows must be DiplomacyHarvestRows")
    if type(max_candidates) is not int or max_candidates <= 0:
        raise DiplomacyAnalysisError("diplomacy_analysis_invalid_input")
    candidates: dict[str, dict[str, object]] = {}
    for relation in diplomacy_rows.relations:
        counterparties = tuple(
            token for token in relation.party_tokens if token != relation.owner_token
        )
        for party in counterparties:
            key = diplomacy_candidate_key(
                relation.owner_token, (relation.owner_token, party)
            )
            entry = candidates.setdefault(
                key,
                {
                    "owner": relation.owner_token,
                    "parties": (relation.owner_token, party),
                    "lanes": set(),
                    "last_tick": relation.last_tick,
                    "contested": False,
                    "contact": 0,
                },
            )
            entry["last_tick"] = max(int(entry["last_tick"]), relation.last_tick)
    for contact in diplomacy_rows.contacts:
        for relation in diplomacy_rows.relations:
            if relation.relation_id != contact.relation_id:
                continue
            for party in relation.party_tokens:
                if party == relation.owner_token:
                    continue
                key = diplomacy_candidate_key(
                    relation.owner_token, (relation.owner_token, party)
                )
                entry = candidates.setdefault(
                    key,
                    {
                        "owner": relation.owner_token,
                        "parties": (relation.owner_token, party),
                        "lanes": set(),
                        "last_tick": contact.tick,
                        "contested": False,
                        "contact": 0,
                    },
                )
                entry["contact"] = int(entry["contact"]) + 1
    for _ in diplomacy_rows.conflicts:
        for entry in candidates.values():
            entry["contested"] = True
    for row in lane_rows:
        for entry in candidates.values():
            parties = set(entry["parties"])  # type: ignore[arg-type]
            if row.left_token in parties and row.right_token in parties:
                entry["lanes"].add(row.lane)  # type: ignore[union-attr]
    results: list[DiplomaticRelationCandidate] = []
    for key, entry in candidates.items():
        parties = tuple(sorted(entry["parties"]))  # type: ignore[arg-type]
        lanes = tuple(sorted(entry["lanes"]))  # type: ignore[arg-type]
        if entry["contested"]:
            status = DiplomaticRelationStatus.CONTESTED
        elif len(lanes) <= 1 and int(entry["contact"]) <= 0:
            status = DiplomaticRelationStatus.FRAGMENTED
        elif int(entry["contact"]) <= 0 and not lanes:
            status = DiplomaticRelationStatus.DORMANT
        else:
            status = DiplomaticRelationStatus.OBSERVED
        results.append(
            DiplomaticRelationCandidate(
                candidate_key=key,
                owner_token=str(entry["owner"]),
                party_tokens=parties,
                lanes=lanes,
                status=status.value,
            )
        )
    results.sort(key=lambda row: row.candidate_key)
    if len(results) > max_candidates:
        _LOG.error("diplomacy_candidate_capacity_reached")
        raise DiplomacyAnalysisError("diplomacy_candidate_capacity_reached")
    _LOG.info("diplomacy_candidates count=%s lineage_edges=%s", len(results), 0)
    return tuple(results)
