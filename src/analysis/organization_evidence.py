"""Windowed detached organization evidence and objective-anchor rows."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from analysis.organization_contract import (
    MAX_EVIDENCE_WINDOWS,
    OrganizationAnalysisError,
)
from analysis.organizations import OrganizationHarvestRows
from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "ANCHOR_FAMILIES",
    "OrganizationObjectiveAnchorRow",
    "OrganizationWindowEvidence",
    "build_organization_windows",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.organization_evidence")

ANCHOR_FAMILIES: Final[tuple[str, ...]] = (
    "roles",
    "goals",
    "resources",
    "procedures",
    "records",
    "commitments",
    "identities",
)


@dataclass(frozen=True, slots=True)
class OrganizationObjectiveAnchorRow:
    """One objective or owner-local anchor referenced by a subjective claim."""

    anchor_kind: str
    anchor_id: str
    first_tick: int
    last_tick: int
    reference_count: int
    resolved: bool

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "anchor_kind", require_stable_id("anchor_kind", self.anchor_kind)
        )
        object.__setattr__(
            self, "anchor_id", require_stable_id("anchor_id", self.anchor_id)
        )
        first = require_exact_nonneg_int("first_tick", self.first_tick)
        last = require_exact_nonneg_int("last_tick", self.last_tick)
        if last < first:
            raise OrganizationAnalysisError("organization_window_invalid")
        object.__setattr__(
            self,
            "reference_count",
            require_exact_nonneg_int("reference_count", self.reference_count),
        )
        if type(self.resolved) is not bool:
            raise OrganizationAnalysisError("organization_window_invalid")


@dataclass(frozen=True, slots=True)
class OrganizationWindowEvidence:
    """One fixed window of detached owner rows and referenced anchors."""

    window_index: int
    start_tick: int
    end_tick: int
    owner_rows: tuple[OrganizationHarvestRows, ...]
    known_person_ids: tuple[str, ...]
    lane_presence: tuple[tuple[str, bool], ...]
    anchors: tuple[OrganizationObjectiveAnchorRow, ...] = ()

    def __post_init__(self) -> None:
        require_exact_nonneg_int("window_index", self.window_index)
        require_exact_nonneg_int("start_tick", self.start_tick)
        require_exact_nonneg_int("end_tick", self.end_tick)
        if self.end_tick < self.start_tick:
            raise OrganizationAnalysisError("organization_window_invalid")

    @property
    def has_evidence(self) -> bool:
        return bool(self.owner_rows) or bool(self.anchors)

    def lane(self, name: str) -> bool:
        return dict(self.lane_presence).get(name, False)


def _concept_overlaps(row: object, start: int, end: int) -> bool:
    first = getattr(row, "first_tick", 0)
    last = getattr(row, "last_tick", 0)
    return first <= end and last >= start


def _anchors_for(
    harvest: OrganizationHarvestRows, start: int, end: int
) -> list[OrganizationObjectiveAnchorRow]:
    anchors: list[OrganizationObjectiveAnchorRow] = []
    for kind, rows in (
        ("role", harvest.roles),
        ("goal", harvest.goals),
        ("resource", harvest.resources),
        ("procedure", harvest.procedures),
        ("record", harvest.records),
        ("commitment", harvest.commitments),
    ):
        for row in rows:
            first = getattr(row, "first_tick", start)
            last = getattr(row, "last_tick", end)
            if not (first <= end and last >= start):
                continue
            anchor_id = str(
                getattr(row, "anchor_id", None)
                or getattr(row, "office_id", None)
                or getattr(row, "commitment_id", "")
            )
            anchors.append(
                OrganizationObjectiveAnchorRow(
                    anchor_kind=kind,
                    anchor_id=anchor_id,
                    first_tick=first,
                    last_tick=last,
                    reference_count=1,
                    resolved=True,
                )
            )
    merged: dict[tuple[str, str], OrganizationObjectiveAnchorRow] = {}
    for anchor in anchors:
        key = (anchor.anchor_kind, anchor.anchor_id)
        existing = merged.get(key)
        if existing is None:
            merged[key] = anchor
            continue
        merged[key] = OrganizationObjectiveAnchorRow(
            anchor_kind=existing.anchor_kind,
            anchor_id=existing.anchor_id,
            first_tick=min(existing.first_tick, anchor.first_tick),
            last_tick=max(existing.last_tick, anchor.last_tick),
            reference_count=existing.reference_count + anchor.reference_count,
            resolved=True,
        )
    return sorted(merged.values(), key=lambda item: (item.anchor_kind, item.anchor_id))


def build_organization_windows(
    harvest: Sequence[OrganizationHarvestRows],
    window_ticks: int,
) -> tuple[OrganizationWindowEvidence, ...]:
    """Group harvested rows into fixed absolute-tick windows."""

    ticks = require_exact_nonneg_int("window_ticks", window_ticks)
    if ticks <= 0:
        raise OrganizationAnalysisError("organization_window_invalid")
    if not harvest:
        return ()
    max_tick = max(
        (concept.last_tick for owner in harvest for concept in owner.concepts),
        default=0,
    )
    window_count = max_tick // ticks + 1
    if window_count > MAX_EVIDENCE_WINDOWS:
        raise OrganizationAnalysisError("organization_window_invalid")
    windows: list[OrganizationWindowEvidence] = []
    for index in range(window_count):
        start = index * ticks
        end = start + ticks - 1
        owner_rows: list[OrganizationHarvestRows] = []
        known: set[str] = set()
        presence = dict.fromkeys(ANCHOR_FAMILIES, False)
        anchors: list[OrganizationObjectiveAnchorRow] = []
        for owner in harvest:
            active_concepts = [
                concept
                for concept in owner.concepts
                if _concept_overlaps(concept, start, end)
            ]
            if not active_concepts:
                continue
            owner_rows.append(owner)
            known.update(member.member_id for member in owner.members)
            for family in ANCHOR_FAMILIES:
                if getattr(owner, family):
                    presence[family] = True
            anchors.extend(_anchors_for(owner, start, end))
        if not owner_rows:
            continue
        windows.append(
            OrganizationWindowEvidence(
                window_index=index,
                start_tick=start,
                end_tick=end,
                owner_rows=tuple(owner_rows),
                known_person_ids=tuple(sorted(known)),
                lane_presence=tuple(sorted(presence.items())),
                anchors=tuple(anchors),
            )
        )
    _LOG.debug("organization_windows windows=%s window_ticks=%s", len(windows), ticks)
    return tuple(windows)
