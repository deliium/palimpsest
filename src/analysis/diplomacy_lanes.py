"""Six independent inter-society evidence lanes.

Lane rows are person-pair counts. They are not candidate claims, and no lane
produces a bilateral relationship score.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, replace
from typing import Final

from analysis.diplomacy_contract import (
    DIPLOMACY_FORBIDDEN_RESULT_FIELDS,
    DiplomacyAnalysisError,
    InterSocietyLane,
    diplomacy_agent_token,
    require_diplomacy_token,
)
from analysis.objective_metrics import CONFLICT_ACTION_KINDS

__all__ = [
    "InterSocietyRelationRow",
    "relation_rows_from_agent_relationships",
    "relation_rows_from_agreements",
    "relation_rows_from_conflict",
    "relation_rows_from_institutional_interaction",
    "relation_rows_from_narratives",
    "relation_rows_from_trade",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.diplomacy_lanes")


@dataclass(frozen=True, slots=True)
class InterSocietyRelationRow:
    lane: str
    left_token: str
    right_token: str
    tick: int
    event_count: int
    denominator: int
    provenance_ref: str | None = None

    def __post_init__(self) -> None:
        if self.lane not in {member.value for member in InterSocietyLane}:
            raise DiplomacyAnalysisError("diplomacy_invalid_row")
        require_diplomacy_token(self.left_token)
        require_diplomacy_token(self.right_token)
        if self.left_token > self.right_token:
            raise DiplomacyAnalysisError("diplomacy_invalid_row")
        if self.left_token == self.right_token:
            raise DiplomacyAnalysisError("diplomacy_invalid_row")
        for value in (self.tick, self.event_count, self.denominator):
            if type(value) is not int or isinstance(value, bool) or value < 0:
                raise DiplomacyAnalysisError("diplomacy_invalid_row")
        for name in DIPLOMACY_FORBIDDEN_RESULT_FIELDS:
            if hasattr(self, name):
                raise DiplomacyAnalysisError("diplomacy_forbidden_result_field")


def _token(value: object) -> str:
    return diplomacy_agent_token(value)


def _pair(left: object, right: object) -> tuple[str, str]:
    first, second = _token(left), _token(right)
    if first == second:
        raise DiplomacyAnalysisError("diplomacy_invalid_row")
    return (first, second) if first < second else (second, first)


def _tick(value: object) -> int:
    if type(value) is not int or isinstance(value, bool) or value < 0:
        raise DiplomacyAnalysisError("diplomacy_invalid_row")
    return value


def _finalize(
    rows: Iterable[InterSocietyRelationRow],
) -> tuple[InterSocietyRelationRow, ...]:
    merged: dict[tuple[str, str, str, int], InterSocietyRelationRow] = {}
    for row in rows:
        key = (row.lane, row.left_token, row.right_token, row.tick)
        existing = merged.get(key)
        if existing is None:
            merged[key] = row
        else:
            merged[key] = replace(
                existing,
                event_count=existing.event_count + row.event_count,
                denominator=existing.denominator + row.denominator,
            )
    return tuple(
        sorted(
            merged.values(),
            key=lambda row: (row.lane, row.left_token, row.right_token, row.tick),
        )
    )


def relation_rows_from_agent_relationships(
    rows: Sequence[object],
) -> tuple[InterSocietyRelationRow, ...]:
    """Count directed relationship revisions as person-pair evidence."""

    result = []
    for row in rows:
        left = getattr(row, "source_id", None)
        right = getattr(row, "target_id", None)
        if left is None or right is None:
            continue
        left_token, right_token = _pair(left, right)
        result.append(
            InterSocietyRelationRow(
                lane=InterSocietyLane.AGENT_RELATIONSHIPS.value,
                left_token=left_token,
                right_token=right_token,
                tick=_tick(getattr(row, "logical_tick", 0)),
                event_count=1,
                denominator=len(rows),
                provenance_ref=None,
            )
        )
    return _finalize(result)


def relation_rows_from_trade(
    events: Sequence[object], entity_to_agent: Callable[[object], object] | None = None
) -> tuple[InterSocietyRelationRow, ...]:
    """Count completed exchanges only. A one-way transfer is never trade."""

    result = []
    completed = 0
    for event in events:
        details = getattr(event, "details", None)
        if type(details).__name__ != "ExchangeCompleted":
            continue
        actor = getattr(details, "actor_id", None)
        counterparty = getattr(details, "counterparty_id", None)
        if entity_to_agent is not None:
            actor = entity_to_agent(actor)
            counterparty = entity_to_agent(counterparty)
        left_token, right_token = _pair(actor, counterparty)
        completed += 1
        result.append(
            InterSocietyRelationRow(
                lane=InterSocietyLane.TRADE.value,
                left_token=left_token,
                right_token=right_token,
                tick=_tick(getattr(event, "tick", 0)),
                event_count=1,
                denominator=1,
            )
        )
    return _finalize(result)


def relation_rows_from_conflict(
    rows: Sequence[object],
) -> tuple[InterSocietyRelationRow, ...]:
    """Count applied conflict actions as person-pair evidence."""

    result = []
    for row in rows:
        if getattr(row, "action_kind", None) not in CONFLICT_ACTION_KINDS:
            continue
        target = getattr(row, "target_id", None)
        if target is None:
            continue
        left_token, right_token = _pair(row.agent_id, target)
        result.append(
            InterSocietyRelationRow(
                lane=InterSocietyLane.CONFLICT.value,
                left_token=left_token,
                right_token=right_token,
                tick=_tick(getattr(row, "tick", 0)),
                event_count=1,
                denominator=len(rows),
            )
        )
    return _finalize(result)


def relation_rows_from_agreements(
    declarations: Sequence[object],
    commitments: Sequence[object] = (),
) -> tuple[InterSocietyRelationRow, ...]:
    """Count accepted/accepted-commitment evidence without a score."""

    accepted: dict[str, set[str]] = {}
    for row in declarations:
        if getattr(row, "act", None) not in {"accept", "promise"}:
            continue
        owner = getattr(row, "owner_token", None)
        party = getattr(row, "party_token", None)
        if owner is None or party is None:
            continue
        accepted.setdefault(getattr(row, "instrument_id", ""), set()).update(
            {owner, party}
        )
    result = []
    for instrument_id, parties in accepted.items():
        ordered = sorted(parties)
        for index, left in enumerate(ordered):
            for right in ordered[index + 1 :]:
                result.append(
                    InterSocietyRelationRow(
                        lane=InterSocietyLane.AGREEMENTS.value,
                        left_token=left,
                        right_token=right,
                        tick=0,
                        event_count=1,
                        denominator=len(accepted),
                        provenance_ref=instrument_id,
                    )
                )
    for row in commitments:
        owner = getattr(row, "owner_token", None)
        counterparty = getattr(row, "counterparty_token", None)
        if owner is None or counterparty is None:
            continue
        left_token, right_token = sorted((str(owner), str(counterparty)))
        if left_token == right_token:
            continue
        result.append(
            InterSocietyRelationRow(
                lane=InterSocietyLane.AGREEMENTS.value,
                left_token=require_diplomacy_token(left_token),
                right_token=require_diplomacy_token(right_token),
                tick=_tick(getattr(row, "tick", 0)),
                event_count=1,
                denominator=len(commitments),
            )
        )
    return _finalize(result)


def relation_rows_from_narratives(
    rows: Sequence[object],
) -> tuple[InterSocietyRelationRow, ...]:
    """Pair owners that share one narrative variant token."""

    shared: dict[str, set[str]] = {}
    for row in rows:
        owner = getattr(row, "owner_token", None)
        variant = getattr(row, "variant_token", getattr(row, "variant_id", None))
        if owner is None or variant is None:
            continue
        shared.setdefault(str(variant), set()).add(require_diplomacy_token(owner))
    result = []
    for owners in shared.values():
        ordered = sorted(owners)
        for index, left in enumerate(ordered):
            for right in ordered[index + 1 :]:
                result.append(
                    InterSocietyRelationRow(
                        lane=InterSocietyLane.NARRATIVES.value,
                        left_token=left,
                        right_token=right,
                        tick=0,
                        event_count=1,
                        denominator=len(shared),
                    )
                )
    return _finalize(result)


def relation_rows_from_institutional_interaction(
    formal_rule_rows: Sequence[object] = (),
    dispute_rows: Sequence[object] = (),
    evidence_rows: Sequence[object] = (),
    organization_agency_rows: Sequence[object] = (),
) -> tuple[InterSocietyRelationRow, ...]:
    """Pair owners that reference the same institutional anchor."""

    shared: dict[str, set[str]] = {}
    for rows in (
        formal_rule_rows,
        dispute_rows,
        evidence_rows,
        organization_agency_rows,
    ):
        for row in rows:
            owner = getattr(row, "owner_token", None)
            if owner is None:
                continue
            anchors = getattr(row, "anchor_refs", None)
            if anchors is None:
                anchor = getattr(row, "anchor_ref", None)
                anchors = () if anchor is None else (anchor,)
            for anchor in anchors:
                shared.setdefault(str(anchor), set()).add(
                    require_diplomacy_token(owner)
                )
    result = []
    for owners in shared.values():
        ordered = sorted(owners)
        for index, left in enumerate(ordered):
            for right in ordered[index + 1 :]:
                result.append(
                    InterSocietyRelationRow(
                        lane=InterSocietyLane.INSTITUTIONAL_INTERACTION.value,
                        left_token=left,
                        right_token=right,
                        tick=0,
                        event_count=1,
                        denominator=len(shared),
                    )
                )
    return _finalize(result)
