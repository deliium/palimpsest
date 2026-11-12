"""Canonical sibling document for completed-run accounting ledgers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from world.identifiers import require_stable_id

__all__ = [
    "ACCOUNTING_LEDGERS_ARTIFACT_MAX_BYTES",
    "ACCOUNTING_LEDGERS_MAX_ALIGNMENTS",
    "ACCOUNTING_LEDGERS_MAX_CONDITIONS",
    "ACCOUNTING_LEDGERS_MAX_COUNTERPARTIES",
    "ACCOUNTING_LEDGERS_MAX_ENTRIES",
    "ACCOUNTING_LEDGERS_MAX_FLOWS",
    "ACCOUNTING_LEDGERS_MAX_RECORDS",
    "ACCOUNTING_LEDGERS_MAX_WINDOWS",
    "ACCOUNTING_LEDGERS_POLICY_VERSION",
    "ACCOUNTING_LEDGERS_PUBLICATION_PREFIX",
    "ACCOUNTING_LEDGERS_SNAPSHOT_VERSION",
    "AccountingLedgersSnapshot",
    "AccountingLedgersSummary",
    "AccountingSnapshotAlignment",
    "AccountingSnapshotCondition",
    "AccountingSnapshotCounterparty",
    "AccountingSnapshotEntry",
    "AccountingSnapshotFlow",
    "AccountingSnapshotRecord",
    "empty_accounting_ledgers_snapshot",
]

ACCOUNTING_LEDGERS_SNAPSHOT_VERSION: Final[str] = "accounting-ledgers-snapshot-v1"
ACCOUNTING_LEDGERS_POLICY_VERSION: Final[str] = "accounting-ledgers.v1"
ACCOUNTING_LEDGERS_PUBLICATION_PREFIX: Final[str] = "acct-pub-"
ACCOUNTING_LEDGERS_MAX_ENTRIES: Final[int] = 4_096
ACCOUNTING_LEDGERS_MAX_RECORDS: Final[int] = 2_048
ACCOUNTING_LEDGERS_MAX_CONDITIONS: Final[int] = 1_024
ACCOUNTING_LEDGERS_MAX_FLOWS: Final[int] = 4_096
ACCOUNTING_LEDGERS_MAX_COUNTERPARTIES: Final[int] = 1_024
ACCOUNTING_LEDGERS_MAX_ALIGNMENTS: Final[int] = 4_096
ACCOUNTING_LEDGERS_MAX_WINDOWS: Final[int] = 512
ACCOUNTING_LEDGERS_ARTIFACT_MAX_BYTES: Final[int] = 8_388_608

_COVERAGE = frozenset({"complete", "partial", "missing"})
_ASSESSMENTS = frozenset(
    {
        "unassessed",
        "consistent",
        "contradicted",
        "outdated",
        "suspected_fraudulent",
        "damaged",
    }
)
_INTEGRITY = frozenset({"intact", "damaged", "partially_lost", "unknown"})
_KINDS = frozenset(
    {
        "exchange",
        "debt",
        "inventory",
        "organizational_resource",
        "contribution",
    }
)
_DIRECTIONS = frozenset(
    {
        "inflow",
        "outflow",
        "holding",
        "receivable",
        "payable",
        "contribution",
    }
)
_ALIGNMENTS = frozenset(
    {"consistent", "unresolved", "inconsistent", "not_applicable"}
)


def _count(value: object) -> int:
    if isinstance(value, bool) or type(value) is not int or value < 0:
        raise ValueError("accounting_ledgers_snapshot_invalid")
    return value


def _token(value: object) -> str:
    if type(value) is not str or not value:
        raise ValueError("accounting_ledgers_snapshot_invalid")
    return require_stable_id("token", value)


def _window(value: object) -> int:
    number = _count(value)
    if number >= ACCOUNTING_LEDGERS_MAX_WINDOWS:
        raise ValueError("accounting_ledgers_snapshot_invalid")
    return number


def _enum(value: object, allowed: frozenset[str]) -> str:
    if type(value) is not str or value not in allowed:
        raise ValueError("accounting_ledgers_snapshot_invalid")
    return value


@dataclass(frozen=True, slots=True)
class AccountingSnapshotEntry:
    entry_token: str
    record_token: str
    entry_kind: str
    direction: str
    item_kind: str
    quantity: int
    assessment: str
    confidence_milli: int
    first_tick: int
    last_tick: int
    window_index: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "entry_token", _token(self.entry_token))
        object.__setattr__(self, "record_token", _token(self.record_token))
        object.__setattr__(self, "entry_kind", _enum(self.entry_kind, _KINDS))
        object.__setattr__(self, "direction", _enum(self.direction, _DIRECTIONS))
        object.__setattr__(self, "item_kind", _token(self.item_kind))
        object.__setattr__(self, "quantity", _count(self.quantity))
        if not 1 <= self.quantity <= 64:
            raise ValueError("accounting_ledgers_snapshot_invalid")
        object.__setattr__(
            self, "assessment", _enum(self.assessment, _ASSESSMENTS)
        )
        object.__setattr__(self, "confidence_milli", _count(self.confidence_milli))
        if self.confidence_milli > 1_000:
            raise ValueError("accounting_ledgers_snapshot_invalid")
        object.__setattr__(self, "first_tick", _count(self.first_tick))
        object.__setattr__(self, "last_tick", _count(self.last_tick))
        object.__setattr__(self, "window_index", _window(self.window_index))


@dataclass(frozen=True, slots=True)
class AccountingSnapshotRecord:
    record_token: str
    record_genre: str
    observed_integrity: str
    content_revision: int
    author_token: str
    tick: int
    event_ordinal: int
    copy_generation: int
    tombstoned: bool
    window_index: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "record_token", _token(self.record_token))
        object.__setattr__(self, "record_genre", _token(self.record_genre))
        object.__setattr__(
            self, "observed_integrity", _enum(self.observed_integrity, _INTEGRITY)
        )
        for name in (
            "content_revision",
            "tick",
            "event_ordinal",
            "copy_generation",
        ):
            object.__setattr__(self, name, _count(getattr(self, name)))
        object.__setattr__(self, "author_token", _token(self.author_token))
        if type(self.tombstoned) is not bool:
            raise ValueError("accounting_ledgers_snapshot_invalid")
        object.__setattr__(self, "window_index", _window(self.window_index))


@dataclass(frozen=True, slots=True)
class AccountingSnapshotCondition:
    condition: str
    record_count: int
    share_milli: int
    window_index: int
    availability: str = "available"

    def __post_init__(self) -> None:
        object.__setattr__(self, "condition", _enum(self.condition, _ASSESSMENTS))
        object.__setattr__(self, "record_count", _count(self.record_count))
        object.__setattr__(self, "share_milli", _count(self.share_milli))
        if self.share_milli > 1_000:
            raise ValueError("accounting_ledgers_snapshot_invalid")
        object.__setattr__(self, "window_index", _window(self.window_index))
        object.__setattr__(
            self,
            "availability",
            _enum(
                self.availability, frozenset({"available", "insufficient_samples"})
            ),
        )


@dataclass(frozen=True, slots=True)
class AccountingSnapshotFlow:
    flow_token: str
    entry_kind: str
    direction: str
    event_count: int
    quantity_sum: int
    owner_count: int
    counterparty_count: int
    window_index: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "flow_token", _token(self.flow_token))
        object.__setattr__(self, "entry_kind", _enum(self.entry_kind, _KINDS))
        object.__setattr__(self, "direction", _enum(self.direction, _DIRECTIONS))
        for name in (
            "event_count",
            "quantity_sum",
            "owner_count",
            "counterparty_count",
        ):
            object.__setattr__(self, name, _count(getattr(self, name)))
        object.__setattr__(self, "window_index", _window(self.window_index))


@dataclass(frozen=True, slots=True)
class AccountingSnapshotCounterparty:
    counterparty_token: str
    entry_count: int
    kinds: tuple[str, ...]
    first_tick: int
    last_tick: int
    window_index: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "counterparty_token", _token(self.counterparty_token))
        object.__setattr__(self, "entry_count", _count(self.entry_count))
        if type(self.kinds) is not tuple:
            raise ValueError("accounting_ledgers_snapshot_invalid")
        object.__setattr__(
            self, "kinds", tuple(_enum(kind, _KINDS) for kind in self.kinds)
        )
        object.__setattr__(self, "first_tick", _count(self.first_tick))
        object.__setattr__(self, "last_tick", _count(self.last_tick))
        object.__setattr__(self, "window_index", _window(self.window_index))


@dataclass(frozen=True, slots=True)
class AccountingSnapshotAlignment:
    alignment_token: str
    entry_token: str
    alignment: str
    gap_milli: int
    record_token: str
    window_index: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "alignment_token", _token(self.alignment_token))
        object.__setattr__(self, "entry_token", _token(self.entry_token))
        object.__setattr__(self, "alignment", _enum(self.alignment, _ALIGNMENTS))
        object.__setattr__(self, "gap_milli", _count(self.gap_milli))
        if self.gap_milli > 1_000:
            raise ValueError("accounting_ledgers_snapshot_invalid")
        object.__setattr__(self, "record_token", _token(self.record_token))
        object.__setattr__(self, "window_index", _window(self.window_index))


@dataclass(frozen=True, slots=True)
class AccountingLedgersSummary:
    entry_count: int
    record_count: int
    condition_count: int
    flow_count: int
    counterparty_count: int
    alignment_count: int
    window_count: int
    entry_coverage: str
    record_coverage: str
    alignment_coverage: str
    condition_coverage: str = "missing"
    flow_coverage: str = "missing"
    counterparty_coverage: str = "missing"
    truncated: bool = False

    def __post_init__(self) -> None:
        for name in (
            "entry_count",
            "record_count",
            "condition_count",
            "flow_count",
            "counterparty_count",
            "alignment_count",
            "window_count",
        ):
            object.__setattr__(self, name, _count(getattr(self, name)))
        for name in (
            "entry_coverage",
            "record_coverage",
            "alignment_coverage",
            "condition_coverage",
            "flow_coverage",
            "counterparty_coverage",
        ):
            object.__setattr__(self, name, _enum(getattr(self, name), _COVERAGE))
        if type(self.truncated) is not bool:
            raise ValueError("accounting_ledgers_snapshot_invalid")


@dataclass(frozen=True, slots=True)
class AccountingLedgersSnapshot:
    run_id: str
    schema_version: str
    policy_version: str
    summary: AccountingLedgersSummary
    entries: tuple[AccountingSnapshotEntry, ...] = ()
    records: tuple[AccountingSnapshotRecord, ...] = ()
    conditions: tuple[AccountingSnapshotCondition, ...] = ()
    flows: tuple[AccountingSnapshotFlow, ...] = ()
    counterparties: tuple[AccountingSnapshotCounterparty, ...] = ()
    alignments: tuple[AccountingSnapshotAlignment, ...] = ()
    digest: str = ""
    publication_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", require_stable_id("run_id", self.run_id))
        if self.schema_version != ACCOUNTING_LEDGERS_SNAPSHOT_VERSION:
            raise ValueError("accounting_ledgers_snapshot_version")
        if self.policy_version != ACCOUNTING_LEDGERS_POLICY_VERSION:
            raise ValueError("accounting_ledgers_snapshot_version")
        if type(self.summary) is not AccountingLedgersSummary:
            raise ValueError("accounting_ledgers_snapshot_invalid")
        for name, row_type, cap, id_field in (
            (
                "entries",
                AccountingSnapshotEntry,
                ACCOUNTING_LEDGERS_MAX_ENTRIES,
                "entry_token",
            ),
            (
                "records",
                AccountingSnapshotRecord,
                ACCOUNTING_LEDGERS_MAX_RECORDS,
                "record_token",
            ),
            (
                "conditions",
                AccountingSnapshotCondition,
                ACCOUNTING_LEDGERS_MAX_CONDITIONS,
                "condition",
            ),
            (
                "flows",
                AccountingSnapshotFlow,
                ACCOUNTING_LEDGERS_MAX_FLOWS,
                "flow_token",
            ),
            (
                "counterparties",
                AccountingSnapshotCounterparty,
                ACCOUNTING_LEDGERS_MAX_COUNTERPARTIES,
                "counterparty_token",
            ),
            (
                "alignments",
                AccountingSnapshotAlignment,
                ACCOUNTING_LEDGERS_MAX_ALIGNMENTS,
                "alignment_token",
            ),
        ):
            values = getattr(self, name)
            if type(values) is not tuple or len(values) > cap:
                raise ValueError("accounting_ledgers_snapshot_invalid")
            seen: set[str] = set()
            for row in values:
                if type(row) is not row_type:
                    raise ValueError("accounting_ledgers_snapshot_invalid")
                identity = (
                    f"{row.condition}:{row.window_index}"
                    if type(row) is AccountingSnapshotCondition
                    else getattr(row, id_field)
                )
                if identity in seen:
                    raise ValueError("accounting_ledgers_snapshot_invalid")
                seen.add(identity)
        if type(self.digest) is not str or type(self.publication_id) is not str:
            raise ValueError("accounting_ledgers_snapshot_invalid")


def empty_accounting_ledgers_snapshot(run_id: str) -> AccountingLedgersSnapshot:
    """Return one empty missing-coverage snapshot."""

    return AccountingLedgersSnapshot(
        run_id=run_id,
        schema_version=ACCOUNTING_LEDGERS_SNAPSHOT_VERSION,
        policy_version=ACCOUNTING_LEDGERS_POLICY_VERSION,
        summary=AccountingLedgersSummary(
            entry_count=0,
            record_count=0,
            condition_count=0,
            flow_count=0,
            counterparty_count=0,
            alignment_count=0,
            window_count=0,
            entry_coverage="missing",
            record_coverage="missing",
            alignment_coverage="missing",
            truncated=False,
        ),
    )
