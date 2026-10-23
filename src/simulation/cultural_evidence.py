"""Neutral, detached cultural evidence exports for post-run analysis.

These values are historical inspection evidence only. They never grant
cognition access to world state, another owner's ledger, or analysis results.
The sink protocol is observational: implementations may store frames but must
not influence commands, admission, stopping, or memory.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Final, Protocol, runtime_checkable

from agents.cognition.cultural_features import CulturalFeatureLedger
from agents.cognition.cultural_narratives import NarrativeLedger
from agents.cognition.practical_knowledge import PracticalKnowledgeLedger
from agents.cognition.semantic_naming import TerminologyLedger
from agents.models import AgentId
from world.identifiers import require_exact_nonneg_int, require_stable_id

_LOG: Final[logging.Logger] = logging.getLogger("simulation.cultural_evidence")

CULTURAL_EVIDENCE_CHANNEL_CULTURAL_FEATURES: Final[str] = "cultural_features"
CULTURAL_EVIDENCE_CHANNEL_TERMINOLOGY: Final[str] = "terminology"
CULTURAL_EVIDENCE_CHANNEL_NARRATIVES: Final[str] = "narratives"
CULTURAL_EVIDENCE_CHANNEL_PRACTICAL_KNOWLEDGE: Final[str] = "practical_knowledge"

CULTURAL_EVIDENCE_CHANNELS: Final[tuple[str, ...]] = (
    CULTURAL_EVIDENCE_CHANNEL_CULTURAL_FEATURES,
    CULTURAL_EVIDENCE_CHANNEL_TERMINOLOGY,
    CULTURAL_EVIDENCE_CHANNEL_NARRATIVES,
    CULTURAL_EVIDENCE_CHANNEL_PRACTICAL_KNOWLEDGE,
)

CULTURAL_EVIDENCE_COVERAGE_COMPLETE: Final[str] = "complete"
CULTURAL_EVIDENCE_COVERAGE_MISSING: Final[str] = "missing"
CULTURAL_EVIDENCE_COVERAGE_DISABLED: Final[str] = "disabled"

CULTURAL_EVIDENCE_COVERAGES: Final[frozenset[str]] = frozenset(
    {
        CULTURAL_EVIDENCE_COVERAGE_COMPLETE,
        CULTURAL_EVIDENCE_COVERAGE_MISSING,
        CULTURAL_EVIDENCE_COVERAGE_DISABLED,
    }
)

CULTURAL_EVIDENCE_BASIS_CARRIED_LEDGER: Final[str] = "carried_ledger"
CULTURAL_EVIDENCE_BASIS_FRESH_EMPTY: Final[str] = "fresh_empty"
CULTURAL_EVIDENCE_BASIS_RESTORED_LEDGER: Final[str] = "restored_ledger"
CULTURAL_EVIDENCE_BASIS_UNAVAILABLE: Final[str] = "unavailable"
CULTURAL_EVIDENCE_BASIS_CHANNEL_OFF: Final[str] = "channel_off"

CULTURAL_EVIDENCE_BASES: Final[frozenset[str]] = frozenset(
    {
        CULTURAL_EVIDENCE_BASIS_CARRIED_LEDGER,
        CULTURAL_EVIDENCE_BASIS_FRESH_EMPTY,
        CULTURAL_EVIDENCE_BASIS_RESTORED_LEDGER,
        CULTURAL_EVIDENCE_BASIS_UNAVAILABLE,
        CULTURAL_EVIDENCE_BASIS_CHANNEL_OFF,
    }
)

_LEDGER_TYPE_BY_CHANNEL: Final[dict[str, type[object]]] = {
    CULTURAL_EVIDENCE_CHANNEL_CULTURAL_FEATURES: CulturalFeatureLedger,
    CULTURAL_EVIDENCE_CHANNEL_TERMINOLOGY: TerminologyLedger,
    CULTURAL_EVIDENCE_CHANNEL_NARRATIVES: NarrativeLedger,
    CULTURAL_EVIDENCE_CHANNEL_PRACTICAL_KNOWLEDGE: PracticalKnowledgeLedger,
}

_LEDGER_BEARING_BASES: Final[frozenset[str]] = frozenset(
    {
        CULTURAL_EVIDENCE_BASIS_CARRIED_LEDGER,
        CULTURAL_EVIDENCE_BASIS_RESTORED_LEDGER,
    }
)

__all__ = [
    "CULTURAL_EVIDENCE_BASES",
    "CULTURAL_EVIDENCE_BASIS_CARRIED_LEDGER",
    "CULTURAL_EVIDENCE_BASIS_CHANNEL_OFF",
    "CULTURAL_EVIDENCE_BASIS_FRESH_EMPTY",
    "CULTURAL_EVIDENCE_BASIS_RESTORED_LEDGER",
    "CULTURAL_EVIDENCE_BASIS_UNAVAILABLE",
    "CULTURAL_EVIDENCE_CHANNELS",
    "CULTURAL_EVIDENCE_CHANNEL_CULTURAL_FEATURES",
    "CULTURAL_EVIDENCE_CHANNEL_NARRATIVES",
    "CULTURAL_EVIDENCE_CHANNEL_PRACTICAL_KNOWLEDGE",
    "CULTURAL_EVIDENCE_CHANNEL_TERMINOLOGY",
    "CULTURAL_EVIDENCE_COVERAGES",
    "CULTURAL_EVIDENCE_COVERAGE_COMPLETE",
    "CULTURAL_EVIDENCE_COVERAGE_DISABLED",
    "CULTURAL_EVIDENCE_COVERAGE_MISSING",
    "CulturalBoundaryExport",
    "CulturalBoundarySink",
    "CulturalCaptureStatus",
    "CulturalChannelExport",
    "CulturalOwnerExport",
]


def _fail(field_name: str, code: str) -> ValueError:
    _LOG.error(
        "cultural_evidence_validation_failed field=%s reason_code=%s",
        field_name,
        code,
    )
    return ValueError(f"{field_name}: {code}")


def _require_channel(channel: object) -> str:
    if not isinstance(channel, str) or channel not in CULTURAL_EVIDENCE_CHANNELS:
        raise _fail("channel", "unknown_channel")
    return channel


def _require_coverage(coverage: object) -> str:
    if not isinstance(coverage, str) or coverage not in CULTURAL_EVIDENCE_COVERAGES:
        raise _fail("coverage", "unknown_coverage")
    return coverage


def _require_basis(basis: object) -> str:
    if not isinstance(basis, str) or basis not in CULTURAL_EVIDENCE_BASES:
        raise _fail("basis", "unknown_basis")
    return basis


@dataclass(frozen=True, slots=True)
class CulturalChannelExport:
    """One owner channel's inventory state at a finalized boundary.

    ``enabled`` comes from the actually bound channel configuration, never from
    ledger presence. A disabled channel carries no ledger; an enabled channel
    with a validated ledger is complete even when that ledger is empty.
    """

    channel: str
    enabled: bool
    coverage: str
    basis: str
    ledger: object | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        channel = _require_channel(self.channel)
        object.__setattr__(self, "channel", channel)
        if type(self.enabled) is not bool:
            raise _fail("enabled", "invalid_type")
        coverage = _require_coverage(self.coverage)
        basis = _require_basis(self.basis)
        object.__setattr__(self, "coverage", coverage)
        object.__setattr__(self, "basis", basis)

        ledger = self.ledger
        ledger_type = _LEDGER_TYPE_BY_CHANNEL[channel]
        if not self.enabled:
            if coverage != CULTURAL_EVIDENCE_COVERAGE_DISABLED:
                raise _fail("coverage", "disabled_channel_requires_disabled")
            if basis != CULTURAL_EVIDENCE_BASIS_CHANNEL_OFF:
                raise _fail("basis", "disabled_channel_requires_channel_off")
            if ledger is not None:
                raise _fail("ledger", "disabled_channel_requires_no_ledger")
            return

        if coverage == CULTURAL_EVIDENCE_COVERAGE_DISABLED:
            raise _fail("coverage", "enabled_channel_cannot_be_disabled")
        if basis == CULTURAL_EVIDENCE_BASIS_CHANNEL_OFF:
            raise _fail("basis", "enabled_channel_cannot_be_channel_off")

        if ledger is not None:
            if type(ledger) is not ledger_type:
                raise _fail("ledger", "ledger_type_mismatch")
            if coverage != CULTURAL_EVIDENCE_COVERAGE_COMPLETE:
                raise _fail("coverage", "ledger_requires_complete")
            if basis not in _LEDGER_BEARING_BASES:
                raise _fail("basis", "ledger_requires_carried_or_restored")
            return

        if coverage == CULTURAL_EVIDENCE_COVERAGE_COMPLETE:
            if basis != CULTURAL_EVIDENCE_BASIS_FRESH_EMPTY:
                raise _fail("basis", "complete_without_ledger_requires_fresh_empty")
            return

        if coverage != CULTURAL_EVIDENCE_COVERAGE_MISSING:
            raise _fail("coverage", "missing_channel_requires_missing")
        if basis != CULTURAL_EVIDENCE_BASIS_UNAVAILABLE:
            raise _fail("basis", "missing_channel_requires_unavailable")

    def __repr__(self) -> str:
        return (
            f"CulturalChannelExport(channel={self.channel!r}, "
            f"enabled={self.enabled}, coverage={self.coverage!r}, "
            f"basis={self.basis!r}, has_ledger={self.ledger is not None})"
        )


@dataclass(frozen=True, slots=True)
class CulturalOwnerExport:
    """All four channel inventories for one owner at one boundary."""

    owner_id: AgentId
    generation_index: int
    living: bool
    channels: tuple[CulturalChannelExport, ...]

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        object.__setattr__(
            self,
            "generation_index",
            require_exact_nonneg_int("generation_index", self.generation_index),
        )
        if type(self.living) is not bool:
            raise _fail("living", "invalid_type")
        if not isinstance(self.channels, tuple):
            raise _fail("channels", "invalid_type")
        if len(self.channels) != len(CULTURAL_EVIDENCE_CHANNELS):
            raise _fail("channels", "channel_count")
        seen: set[str] = set()
        by_channel: dict[str, CulturalChannelExport] = {}
        for item in self.channels:
            if type(item) is not CulturalChannelExport:
                raise _fail("channels", "invalid_item")
            if item.channel in seen:
                raise _fail("channels", "duplicate_channel")
            seen.add(item.channel)
            by_channel[item.channel] = item
        if seen != set(CULTURAL_EVIDENCE_CHANNELS):
            raise _fail("channels", "unknown_channel")
        for channel in CULTURAL_EVIDENCE_CHANNELS:
            ledger = by_channel[channel].ledger
            if ledger is None:
                continue
            ledger_owner = getattr(ledger, "owner_id", None)
            if ledger_owner != self.owner_id:
                raise _fail("channels", "owner_mismatch")
        object.__setattr__(
            self,
            "channels",
            tuple(by_channel[channel] for channel in CULTURAL_EVIDENCE_CHANNELS),
        )

    def __repr__(self) -> str:
        return (
            f"CulturalOwnerExport(owner_id={self.owner_id.value!r}, "
            f"generation_index={self.generation_index}, living={self.living}, "
            f"channel_count={len(self.channels)})"
        )


@dataclass(frozen=True, slots=True)
class CulturalBoundaryExport:
    """State-after-finalization cultural inventories for one boundary.

    Boundary ``b`` follows ticks ``< b``; boundary 0 is the state before the
    first tick.
    """

    run_id: str
    boundary_tick: int
    owners: tuple[CulturalOwnerExport, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", require_stable_id("run_id", self.run_id))
        object.__setattr__(
            self,
            "boundary_tick",
            require_exact_nonneg_int("boundary_tick", self.boundary_tick),
        )
        if not isinstance(self.owners, tuple):
            raise _fail("owners", "invalid_type")
        seen: set[str] = set()
        checked: list[CulturalOwnerExport] = []
        for item in self.owners:
            if type(item) is not CulturalOwnerExport:
                raise _fail("owners", "invalid_item")
            token = item.owner_id.value
            if token in seen:
                raise _fail("owners", "duplicate_owner")
            seen.add(token)
            checked.append(item)
        checked.sort(key=lambda owner: owner.owner_id.value)
        object.__setattr__(self, "owners", tuple(checked))

    def __repr__(self) -> str:
        return (
            f"CulturalBoundaryExport(run_id={self.run_id!r}, "
            f"boundary_tick={self.boundary_tick}, owner_count={len(self.owners)})"
        )


@dataclass(frozen=True, slots=True)
class CulturalCaptureStatus:
    """Runner-owned capture health, queryable even after exporter failure."""

    active: bool
    failed: bool
    failure_boundary: int | None = None
    failure_code: str | None = None
    missing_prefix_through: int | None = None

    def __post_init__(self) -> None:
        if type(self.active) is not bool:
            raise _fail("active", "invalid_type")
        if type(self.failed) is not bool:
            raise _fail("failed", "invalid_type")
        for name in (
            "failure_boundary",
            "failure_code",
            "missing_prefix_through",
        ):
            value = getattr(self, name)
            if value is None:
                continue
            if name == "failure_code":
                object.__setattr__(
                    self, name, require_stable_id(f"capture.{name}", value)
                )
            else:
                object.__setattr__(
                    self,
                    name,
                    require_exact_nonneg_int(f"capture.{name}", value),
                )
        if self.failed and (self.failure_boundary is None or self.failure_code is None):
            raise _fail("failure_code", "failed_requires_boundary_and_code")

    def __repr__(self) -> str:
        return (
            f"CulturalCaptureStatus(active={self.active}, "
            f"failed={self.failed}, "
            f"failure_boundary={self.failure_boundary}, "
            f"failure_code={self.failure_code!r}, "
            f"missing_prefix_through={self.missing_prefix_through})"
        )


@runtime_checkable
class CulturalBoundarySink(Protocol):
    """Synchronous observational sink for complete finalized boundaries."""

    def capture(self, frame: CulturalBoundaryExport) -> None: ...


_LOG.debug(
    "cultural_evidence_contracts_loaded policy=%s channel_count=%s",
    "cultural-evolution.v1",
    len(CULTURAL_EVIDENCE_CHANNELS),
)
