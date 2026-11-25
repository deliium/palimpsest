"""Detached collapse-recovery evidence contracts (analysis-only).

Frozen narrow input models. No experiments or runner orchestration imports.
Capture adapters project receipts into these shapes after ordinary finalization.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from simulation.resilience_evidence import (
    OwnerLaneState,
    ResilienceInfrastructureRow,
    ResilienceOwnerKeys,
)
from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "MAX_COLLAPSE_CUMULATIVE_FRAME_ROWS",
    "MAX_COLLAPSE_CUMULATIVE_RAW_EVENTS",
    "MAX_COLLAPSE_CUMULATIVE_RECEIPTS",
    "MAX_COLLAPSE_FRAME_ROWS",
    "MAX_COLLAPSE_HORIZON",
    "MAX_COLLAPSE_INFRASTRUCTURE_ASSETS",
    "MAX_COLLAPSE_REGIONS",
    "MAX_COLLAPSE_ROSTER",
    "CollapseBatch",
    "CollapseBodyRow",
    "CollapseEvidence",
    "CollapseEvidenceError",
    "CollapseFrame",
    "CollapseReceiptKind",
    "CollapseReceiptRow",
    "CollapseSourceCoverage",
    "OwnerLaneState",
    "ResilienceInfrastructureRow",
    "ResilienceOwnerKeys",
    "count_collapse_frame_rows",
    "validate_collapse_evidence",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.collapse_recovery_evidence")

MAX_COLLAPSE_HORIZON: Final[int] = 512
MAX_COLLAPSE_ROSTER: Final[int] = 128
MAX_COLLAPSE_REGIONS: Final[int] = 64
MAX_COLLAPSE_INFRASTRUCTURE_ASSETS: Final[int] = 512
MAX_COLLAPSE_FRAME_ROWS: Final[int] = 4_096
MAX_COLLAPSE_CUMULATIVE_FRAME_ROWS: Final[int] = 262_144
MAX_COLLAPSE_CUMULATIVE_RAW_EVENTS: Final[int] = 50_000
MAX_COLLAPSE_CUMULATIVE_RECEIPTS: Final[int] = 100_000

_ERROR_CODES: Final[frozenset[str]] = frozenset(
    {
        "collapse_evidence_invalid_integer",
        "collapse_evidence_invalid_token",
        "collapse_evidence_invalid_input",
        "collapse_evidence_roster_overflow",
        "collapse_evidence_region_overflow",
        "collapse_evidence_infra_overflow",
        "collapse_evidence_frame_overflow",
        "collapse_evidence_receipt_overflow",
        "collapse_evidence_clock_mismatch",
        "collapse_evidence_run_mismatch",
        "collapse_evidence_revision_gap",
        "collapse_evidence_duplicate_id",
        "collapse_evidence_order",
    }
)


class CollapseEvidenceError(ValueError):
    """Fail-closed evidence validation error with a stable reason code."""

    @property
    def reason_code(self) -> str:
        if not self.args:
            return "collapse_evidence_invalid_input"
        return str(self.args[0])


class CollapseReceiptKind(StrEnum):
    """Closed receipt kinds retained for measurement and lineage."""

    DEATH = "death"
    JOURNEY_ARRIVAL = "journey_arrival"
    EXCHANGE = "exchange"
    HARVEST = "harvest"
    CRAFT = "craft"
    ATTACK = "attack"
    SPEECH_CONTACT = "speech_contact"
    HELP_CONTACT = "help_contact"
    FEED_CONTACT = "feed_contact"
    EXCHANGE_CONTACT = "exchange_contact"


@dataclass(frozen=True, slots=True)
class CollapseBodyRow:
    """Registered body presence without held-item inventory counts."""

    body_id: str
    agent_id: str
    living: bool
    region_id: str | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "body_id", require_stable_id("body_id", self.body_id))
        object.__setattr__(
            self, "agent_id", require_stable_id("agent_id", self.agent_id)
        )
        if type(self.living) is not bool:
            raise CollapseEvidenceError("collapse_evidence_invalid_input")
        if self.region_id is not None:
            object.__setattr__(
                self, "region_id", require_stable_id("region_id", self.region_id)
            )


@dataclass(frozen=True, slots=True)
class CollapseSourceCoverage:
    """Accepted-spec availability; independent of whether events arrived."""

    regions_migration: bool
    resource_exchange: bool
    production: bool
    infrastructure: OwnerLaneState

    def __post_init__(self) -> None:
        for name in ("regions_migration", "resource_exchange", "production"):
            if type(getattr(self, name)) is not bool:
                raise CollapseEvidenceError("collapse_evidence_invalid_input")
        if type(self.infrastructure) is not OwnerLaneState:
            raise CollapseEvidenceError("collapse_evidence_invalid_input")


@dataclass(frozen=True, slots=True)
class CollapseFrame:
    """One finalized boundary projection for collapse-recovery capture."""

    run_id: str
    config_fingerprint: str
    tick: int
    revision: int
    body_projection_hash: str | None
    history_length: int
    infrastructure_channel: OwnerLaneState
    bodies: tuple[CollapseBodyRow, ...]
    infrastructure: tuple[ResilienceInfrastructureRow, ...]
    owners: tuple[ResilienceOwnerKeys, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", require_stable_id("run_id", self.run_id))
        object.__setattr__(
            self,
            "config_fingerprint",
            require_stable_id("config_fingerprint", self.config_fingerprint),
        )
        object.__setattr__(self, "tick", require_exact_nonneg_int("tick", self.tick))
        object.__setattr__(
            self, "revision", require_exact_nonneg_int("revision", self.revision)
        )
        if self.body_projection_hash is not None:
            object.__setattr__(
                self,
                "body_projection_hash",
                require_stable_id("body_projection_hash", self.body_projection_hash),
            )
        object.__setattr__(
            self,
            "history_length",
            require_exact_nonneg_int("history_length", self.history_length),
        )
        if type(self.infrastructure_channel) is not OwnerLaneState:
            raise CollapseEvidenceError("collapse_evidence_invalid_input")
        if type(self.bodies) is not tuple:
            raise CollapseEvidenceError("collapse_evidence_invalid_input")
        if type(self.infrastructure) is not tuple:
            raise CollapseEvidenceError("collapse_evidence_invalid_input")
        if type(self.owners) is not tuple:
            raise CollapseEvidenceError("collapse_evidence_invalid_input")
        body_ids: set[str] = set()
        for row in self.bodies:
            if type(row) is not CollapseBodyRow:
                raise CollapseEvidenceError("collapse_evidence_invalid_input")
            if row.body_id in body_ids:
                raise CollapseEvidenceError("collapse_evidence_duplicate_id")
            body_ids.add(row.body_id)
        if len(self.bodies) > MAX_COLLAPSE_ROSTER:
            raise CollapseEvidenceError("collapse_evidence_roster_overflow")
        asset_ids: set[str] = set()
        for asset_row in self.infrastructure:
            if type(asset_row) is not ResilienceInfrastructureRow:
                raise CollapseEvidenceError("collapse_evidence_invalid_input")
            if asset_row.asset_id in asset_ids:
                raise CollapseEvidenceError("collapse_evidence_duplicate_id")
            asset_ids.add(asset_row.asset_id)
        if len(self.infrastructure) > MAX_COLLAPSE_INFRASTRUCTURE_ASSETS:
            raise CollapseEvidenceError("collapse_evidence_infra_overflow")
        owner_ids: set[str] = set()
        for owner_row in self.owners:
            if type(owner_row) is not ResilienceOwnerKeys:
                raise CollapseEvidenceError("collapse_evidence_invalid_input")
            if owner_row.agent_id in owner_ids:
                raise CollapseEvidenceError("collapse_evidence_duplicate_id")
            owner_ids.add(owner_row.agent_id)
        total = count_collapse_frame_rows(
            bodies=self.bodies,
            infrastructure=self.infrastructure,
            owners=self.owners,
        )
        if total > MAX_COLLAPSE_FRAME_ROWS:
            raise CollapseEvidenceError("collapse_evidence_frame_overflow")


@dataclass(frozen=True, slots=True)
class CollapseReceiptRow:
    """Normalized committed receipt; parties and sites only, never payloads."""

    event_id: str
    tick: int
    sequence: int
    kind: CollapseReceiptKind
    participant_body_id: str | None
    counterpart_body_id: str | None
    origin_location_id: str | None
    destination_location_id: str | None
    origin_region_id: str | None
    destination_region_id: str | None
    site_location_id: str | None
    site_region_id: str | None
    attribution_gap: bool

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "event_id", require_stable_id("event_id", self.event_id)
        )
        object.__setattr__(self, "tick", require_exact_nonneg_int("tick", self.tick))
        object.__setattr__(
            self, "sequence", require_exact_nonneg_int("sequence", self.sequence)
        )
        if type(self.kind) is not CollapseReceiptKind:
            raise CollapseEvidenceError("collapse_evidence_invalid_input")
        if type(self.attribution_gap) is not bool:
            raise CollapseEvidenceError("collapse_evidence_invalid_input")
        for name in (
            "participant_body_id",
            "counterpart_body_id",
            "origin_location_id",
            "destination_location_id",
            "origin_region_id",
            "destination_region_id",
            "site_location_id",
            "site_region_id",
        ):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, require_stable_id(name, value))


@dataclass(frozen=True, slots=True)
class CollapseBatch:
    """Ordered normalized receipts for one committed tick."""

    tick: int
    resulting_revision: int
    raw_event_count: int
    receipts: tuple[CollapseReceiptRow, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "tick", require_exact_nonneg_int("tick", self.tick))
        object.__setattr__(
            self,
            "resulting_revision",
            require_exact_nonneg_int("resulting_revision", self.resulting_revision),
        )
        object.__setattr__(
            self,
            "raw_event_count",
            require_exact_nonneg_int("raw_event_count", self.raw_event_count),
        )
        if type(self.receipts) is not tuple:
            raise CollapseEvidenceError("collapse_evidence_invalid_input")
        previous: tuple[int, str, str, str] | None = None
        for row in self.receipts:
            if type(row) is not CollapseReceiptRow:
                raise CollapseEvidenceError("collapse_evidence_invalid_input")
            if row.tick != self.tick:
                raise CollapseEvidenceError("collapse_evidence_clock_mismatch")
            key = (
                row.sequence,
                row.event_id,
                row.kind.value,
                "" if row.participant_body_id is None else row.participant_body_id,
            )
            if previous is not None and key < previous:
                raise CollapseEvidenceError("collapse_evidence_order")
            previous = key


@dataclass(frozen=True, slots=True)
class CollapseEvidence:
    """Sealed contiguous finalized prefix ready for detached reducers."""

    run_id: str
    config_fingerprint: str
    captured_through: int
    committed_through: int
    seal_reason: str | None
    region_ids: tuple[str, ...]
    location_regions: Mapping[str, str]
    source_coverage: CollapseSourceCoverage
    frames: tuple[CollapseFrame, ...]
    batches: tuple[CollapseBatch, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", require_stable_id("run_id", self.run_id))
        object.__setattr__(
            self,
            "config_fingerprint",
            require_stable_id("config_fingerprint", self.config_fingerprint),
        )
        object.__setattr__(
            self,
            "captured_through",
            require_exact_nonneg_int("captured_through", self.captured_through),
        )
        object.__setattr__(
            self,
            "committed_through",
            require_exact_nonneg_int("committed_through", self.committed_through),
        )
        if self.seal_reason is not None:
            object.__setattr__(
                self,
                "seal_reason",
                require_stable_id("seal_reason", self.seal_reason),
            )
        if type(self.region_ids) is not tuple:
            raise CollapseEvidenceError("collapse_evidence_invalid_input")
        seen_regions: set[str] = set()
        normalized_regions: list[str] = []
        for region_id in self.region_ids:
            token = require_stable_id("region_id", region_id)
            if token in seen_regions:
                raise CollapseEvidenceError("collapse_evidence_duplicate_id")
            seen_regions.add(token)
            normalized_regions.append(token)
        if len(normalized_regions) > MAX_COLLAPSE_REGIONS:
            raise CollapseEvidenceError("collapse_evidence_region_overflow")
        object.__setattr__(self, "region_ids", tuple(normalized_regions))
        if not isinstance(self.location_regions, Mapping):
            raise CollapseEvidenceError("collapse_evidence_invalid_input")
        object.__setattr__(
            self,
            "location_regions",
            {
                require_stable_id("location_id", key): require_stable_id(
                    "region_id", value
                )
                for key, value in self.location_regions.items()
            },
        )
        if type(self.source_coverage) is not CollapseSourceCoverage:
            raise CollapseEvidenceError("collapse_evidence_invalid_input")
        if type(self.frames) is not tuple or type(self.batches) is not tuple:
            raise CollapseEvidenceError("collapse_evidence_invalid_input")
        validate_collapse_evidence(self)


def count_collapse_frame_rows(
    *,
    bodies: Sequence[CollapseBodyRow],
    infrastructure: Sequence[ResilienceInfrastructureRow],
    owners: Sequence[ResilienceOwnerKeys],
) -> int:
    """Count normalized frame entries including owner key leaves."""

    total = len(bodies) + len(infrastructure) + len(owners)
    for owner in owners:
        total += len(owner.recognized_concept_ids) + len(owner.active_content_keys)
    return total


def validate_collapse_evidence(evidence: CollapseEvidence) -> None:
    """Validate clock continuity, run identity, caps and ordering."""

    if evidence.captured_through > evidence.committed_through:
        raise CollapseEvidenceError("collapse_evidence_clock_mismatch")
    if evidence.captured_through > MAX_COLLAPSE_HORIZON:
        raise CollapseEvidenceError("collapse_evidence_invalid_integer")
    frames = evidence.frames
    batches = evidence.batches
    if not frames:
        if evidence.captured_through != 0:
            raise CollapseEvidenceError("collapse_evidence_clock_mismatch")
        if batches:
            raise CollapseEvidenceError("collapse_evidence_invalid_input")
        return
    expected_ticks = evidence.captured_through + 1
    if len(frames) != expected_ticks:
        raise CollapseEvidenceError("collapse_evidence_clock_mismatch")
    if len(batches) != evidence.captured_through:
        raise CollapseEvidenceError("collapse_evidence_clock_mismatch")
    cumulative_rows = 0
    cumulative_receipts = 0
    cumulative_raw = 0
    previous_revision = -1
    for index, frame in enumerate(frames):
        if type(frame) is not CollapseFrame:
            raise CollapseEvidenceError("collapse_evidence_invalid_input")
        if frame.tick != index:
            raise CollapseEvidenceError("collapse_evidence_clock_mismatch")
        if frame.run_id != evidence.run_id:
            raise CollapseEvidenceError("collapse_evidence_run_mismatch")
        if frame.config_fingerprint != evidence.config_fingerprint:
            raise CollapseEvidenceError("collapse_evidence_run_mismatch")
        if frame.revision < previous_revision:
            raise CollapseEvidenceError("collapse_evidence_revision_gap")
        previous_revision = frame.revision
        cumulative_rows += count_collapse_frame_rows(
            bodies=frame.bodies,
            infrastructure=frame.infrastructure,
            owners=frame.owners,
        )
        if cumulative_rows > MAX_COLLAPSE_CUMULATIVE_FRAME_ROWS:
            raise CollapseEvidenceError("collapse_evidence_frame_overflow")
    for index, batch in enumerate(batches):
        if type(batch) is not CollapseBatch:
            raise CollapseEvidenceError("collapse_evidence_invalid_input")
        if batch.tick != index:
            raise CollapseEvidenceError("collapse_evidence_clock_mismatch")
        frame = frames[index + 1]
        if batch.resulting_revision != frame.revision:
            raise CollapseEvidenceError("collapse_evidence_revision_gap")
        cumulative_raw += batch.raw_event_count
        cumulative_receipts += len(batch.receipts)
        if cumulative_raw > MAX_COLLAPSE_CUMULATIVE_RAW_EVENTS:
            raise CollapseEvidenceError("collapse_evidence_receipt_overflow")
        if cumulative_receipts > MAX_COLLAPSE_CUMULATIVE_RECEIPTS:
            raise CollapseEvidenceError("collapse_evidence_receipt_overflow")
    _LOG.debug(
        "collapse_evidence_validated run_id=%s captured_through=%s frames=%s "
        "batches=%s rows=%s receipts=%s",
        evidence.run_id,
        evidence.captured_through,
        len(frames),
        len(batches),
        cumulative_rows,
        cumulative_receipts,
    )
