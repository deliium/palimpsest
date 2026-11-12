"""Frozen detached rows for accounting evidence and analytics."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final

from analysis.accounting_ledgers_contract import (
    ACCOUNTING_ANALYSIS_FORBIDDEN_KEYS,
    AccountingAlignment,
    AccountingAnalysisError,
    AccountingAnalysisLayer,
    AccountingCoverage,
    AccountingDistributionStatus,
    AccountingEntryDirection,
    AccountingEntryKindToken,
    AccountingRecordAssessmentToken,
    AccountingRecordIntegrityToken,
)
from world.identifiers import require_stable_id

__all__ = [
    "AccountingAlignmentRow",
    "AccountingClaimEvidenceRow",
    "AccountingContributionEvidenceRow",
    "AccountingCounterpartyRow",
    "AccountingDistributionSummary",
    "AccountingEvidenceHarvest",
    "AccountingFlowRow",
    "AccountingRecordConditionRow",
    "AccountingRecordEvidenceRow",
    "AccountingTransferEvidenceRow",
    "AnalyticalAccountingEntryRow",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.accounting_ledgers.rows")


def _forbid_keys(cls: type[object]) -> None:
    names = set(getattr(cls, "__dataclass_fields__", {}))
    if names & ACCOUNTING_ANALYSIS_FORBIDDEN_KEYS:
        raise AccountingAnalysisError("accounting_analysis_forbidden_key")


def _count(value: object) -> int:
    if isinstance(value, bool) or type(value) is not int or value < 0:
        raise AccountingAnalysisError("accounting_analysis_invalid_row")
    return value


def _token(value: object) -> str:
    if type(value) is not str or not value:
        raise AccountingAnalysisError("accounting_analysis_invalid_row")
    try:
        return require_stable_id("token", value)
    except (TypeError, ValueError) as error:
        raise AccountingAnalysisError("accounting_analysis_invalid_row") from error


def _enum(value: object, enum_type: type) -> object:
    if type(value) is not enum_type:
        raise AccountingAnalysisError("accounting_analysis_invalid_row")
    return value


@dataclass(frozen=True, slots=True)
class AccountingRecordEvidenceRow:
    """One committed record-lifecycle observation, token-only."""

    record_token: str
    record_genre: str
    observed_integrity: AccountingRecordIntegrityToken
    content_revision: int
    author_token: str
    tick: int
    event_ordinal: int
    copy_generation: int
    tombstoned: bool

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(self, "record_token", _token(self.record_token))
        if type(self.record_genre) is not str or not self.record_genre:
            raise AccountingAnalysisError("accounting_analysis_invalid_row")
        object.__setattr__(
            self,
            "observed_integrity",
            _enum(self.observed_integrity, AccountingRecordIntegrityToken),
        )
        for name in ("content_revision", "tick", "event_ordinal", "copy_generation"):
            object.__setattr__(self, name, _count(getattr(self, name)))
        object.__setattr__(self, "author_token", _token(self.author_token))
        if type(self.tombstoned) is not bool:
            raise AccountingAnalysisError("accounting_analysis_invalid_row")

    @property
    def source_layers(self) -> tuple[AccountingAnalysisLayer, ...]:
        return (AccountingAnalysisLayer.OBJECTIVE_RECORD,)


@dataclass(frozen=True, slots=True)
class AccountingTransferEvidenceRow:
    """One committed item transfer, token-only."""

    transfer_token: str
    giver_token: str
    receiver_token: str
    item_kind: str
    quantity: int
    tick: int
    event_ordinal: int

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        for name in ("transfer_token", "giver_token", "receiver_token", "item_kind"):
            object.__setattr__(self, name, _token(getattr(self, name)))
        object.__setattr__(self, "quantity", _count(self.quantity))
        if self.quantity < 1:
            raise AccountingAnalysisError("accounting_analysis_invalid_row")
        object.__setattr__(self, "tick", _count(self.tick))
        object.__setattr__(self, "event_ordinal", _count(self.event_ordinal))

    @property
    def source_layers(self) -> tuple[AccountingAnalysisLayer, ...]:
        return (AccountingAnalysisLayer.OBJECTIVE_RECORD,)


@dataclass(frozen=True, slots=True)
class AccountingContributionEvidenceRow:
    """One committed collective contribution, token-only."""

    project_token: str
    actor_token: str
    accepted: bool
    labor_delta: int
    tick: int
    event_ordinal: int

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(self, "project_token", _token(self.project_token))
        object.__setattr__(self, "actor_token", _token(self.actor_token))
        if type(self.accepted) is not bool:
            raise AccountingAnalysisError("accounting_analysis_invalid_row")
        object.__setattr__(self, "labor_delta", _count(self.labor_delta))
        object.__setattr__(self, "tick", _count(self.tick))
        object.__setattr__(self, "event_ordinal", _count(self.event_ordinal))

    @property
    def source_layers(self) -> tuple[AccountingAnalysisLayer, ...]:
        return (AccountingAnalysisLayer.OBJECTIVE_RECORD,)


@dataclass(frozen=True, slots=True)
class AccountingClaimEvidenceRow:
    """One committed ``acc_v1`` claim relation, token-only testimony."""

    claim_token: str
    record_token: str
    entry_kind: AccountingEntryKindToken
    direction: AccountingEntryDirection
    item_kind: str
    quantity: int
    assessment: AccountingRecordAssessmentToken
    confidence_milli: int
    speaker_token: str
    tick: int
    event_ordinal: int

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        for name in ("claim_token", "record_token", "item_kind", "speaker_token"):
            object.__setattr__(self, name, _token(getattr(self, name)))
        object.__setattr__(
            self, "entry_kind", _enum(self.entry_kind, AccountingEntryKindToken)
        )
        object.__setattr__(
            self, "direction", _enum(self.direction, AccountingEntryDirection)
        )
        object.__setattr__(self, "quantity", _count(self.quantity))
        if not 1 <= self.quantity <= 64:
            raise AccountingAnalysisError("accounting_analysis_invalid_row")
        object.__setattr__(
            self,
            "assessment",
            _enum(self.assessment, AccountingRecordAssessmentToken),
        )
        object.__setattr__(self, "confidence_milli", _count(self.confidence_milli))
        if self.confidence_milli > 1_000:
            raise AccountingAnalysisError("accounting_analysis_invalid_row")
        object.__setattr__(self, "tick", _count(self.tick))
        object.__setattr__(self, "event_ordinal", _count(self.event_ordinal))

    @property
    def source_layers(self) -> tuple[AccountingAnalysisLayer, ...]:
        return (AccountingAnalysisLayer.OWNER_CLAIM,)


@dataclass(frozen=True, slots=True)
class AnalyticalAccountingEntryRow:
    """One analytical accounting entry; never an objective total."""

    entry_token: str
    record_token: str
    entry_kind: AccountingEntryKindToken
    direction: AccountingEntryDirection
    item_kind: str
    quantity: int
    assessment: AccountingRecordAssessmentToken
    confidence_milli: int
    first_tick: int
    last_tick: int
    window_index: int
    source_layers: tuple[AccountingAnalysisLayer, ...] = (
        AccountingAnalysisLayer.ANALYTICAL_ENTRY,
    )

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(self, "entry_token", _token(self.entry_token))
        object.__setattr__(self, "record_token", _token(self.record_token))
        object.__setattr__(
            self, "entry_kind", _enum(self.entry_kind, AccountingEntryKindToken)
        )
        object.__setattr__(
            self, "direction", _enum(self.direction, AccountingEntryDirection)
        )
        object.__setattr__(self, "item_kind", _token(self.item_kind))
        object.__setattr__(self, "quantity", _count(self.quantity))
        object.__setattr__(
            self,
            "assessment",
            _enum(self.assessment, AccountingRecordAssessmentToken),
        )
        object.__setattr__(self, "confidence_milli", _count(self.confidence_milli))
        if self.confidence_milli > 1_000:
            raise AccountingAnalysisError("accounting_analysis_invalid_row")
        object.__setattr__(self, "first_tick", _count(self.first_tick))
        object.__setattr__(self, "last_tick", _count(self.last_tick))
        object.__setattr__(self, "window_index", _count(self.window_index))
        if self.last_tick < self.first_tick:
            raise AccountingAnalysisError("accounting_analysis_invalid_row")


@dataclass(frozen=True, slots=True)
class AccountingRecordConditionRow:
    """One descriptive record-condition count and share."""

    condition: str
    record_count: int
    quantity_histogram: tuple[tuple[int, int], ...]
    share_milli: int
    window_index: int
    availability: str = "available"

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(self, "condition", _token(self.condition))
        object.__setattr__(self, "record_count", _count(self.record_count))
        if self.availability not in {"available", "insufficient_samples"}:
            raise AccountingAnalysisError("accounting_analysis_invalid_row")
        if (
            isinstance(self.quantity_histogram, (str, bytes))
            or not isinstance(self.quantity_histogram, tuple)
        ):
            raise AccountingAnalysisError("accounting_analysis_invalid_row")
        for item in self.quantity_histogram:
            if type(item) is not tuple or len(item) != 2:
                raise AccountingAnalysisError("accounting_analysis_invalid_row")
            _count(item[0])
            _count(item[1])
        object.__setattr__(self, "share_milli", _count(self.share_milli))
        if self.share_milli > 1_000:
            raise AccountingAnalysisError("accounting_analysis_invalid_row")
        object.__setattr__(self, "window_index", _count(self.window_index))

    @property
    def source_layers(self) -> tuple[AccountingAnalysisLayer, ...]:
        return (AccountingAnalysisLayer.ANALYTICAL_ENTRY,)


@dataclass(frozen=True, slots=True)
class AccountingFlowRow:
    """One descriptive per-window claim sum; never a wealth claim."""

    entry_kind: AccountingEntryKindToken
    direction: AccountingEntryDirection
    event_count: int
    quantity_sum: int
    owner_count: int
    counterparty_count: int
    window_index: int

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(
            self, "entry_kind", _enum(self.entry_kind, AccountingEntryKindToken)
        )
        object.__setattr__(
            self, "direction", _enum(self.direction, AccountingEntryDirection)
        )
        for name in (
            "event_count",
            "quantity_sum",
            "owner_count",
            "counterparty_count",
            "window_index",
        ):
            object.__setattr__(self, name, _count(getattr(self, name)))

    @property
    def source_layers(self) -> tuple[AccountingAnalysisLayer, ...]:
        return (AccountingAnalysisLayer.ANALYTICAL_ENTRY,)


@dataclass(frozen=True, slots=True)
class AccountingCounterpartyRow:
    """One descriptive counterparty aggregate, token-only."""

    counterparty_token: str
    entry_count: int
    kinds: tuple[str, ...]
    first_tick: int
    last_tick: int

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(self, "counterparty_token", _token(self.counterparty_token))
        object.__setattr__(self, "entry_count", _count(self.entry_count))
        if (
            isinstance(self.kinds, (str, bytes))
            or not isinstance(self.kinds, tuple)
        ):
            raise AccountingAnalysisError("accounting_analysis_invalid_row")
        object.__setattr__(self, "kinds", tuple(_token(kind) for kind in self.kinds))
        object.__setattr__(self, "first_tick", _count(self.first_tick))
        object.__setattr__(self, "last_tick", _count(self.last_tick))

    @property
    def source_layers(self) -> tuple[AccountingAnalysisLayer, ...]:
        return (AccountingAnalysisLayer.ANALYTICAL_ENTRY,)


@dataclass(frozen=True, slots=True)
class AccountingAlignmentRow:
    """Researcher-only alignment; never reaches cognition."""

    entry_token: str
    alignment: AccountingAlignment
    gap_milli: int
    record_token: str

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(self, "entry_token", _token(self.entry_token))
        object.__setattr__(
            self, "alignment", _enum(self.alignment, AccountingAlignment)
        )
        object.__setattr__(self, "gap_milli", _count(self.gap_milli))
        if self.gap_milli > 1_000:
            raise AccountingAnalysisError("accounting_analysis_invalid_row")
        object.__setattr__(self, "record_token", _token(self.record_token))

    @property
    def source_layers(self) -> tuple[AccountingAnalysisLayer, ...]:
        return (AccountingAnalysisLayer.ANALYTICAL_ENTRY,)


@dataclass(frozen=True, slots=True)
class AccountingDistributionSummary:
    """Descriptive distribution only; never a wealth claim or rank."""

    status: AccountingDistributionStatus
    sample_count: int
    minimum: int | None
    p25: int | None
    median: int | None
    p75: int | None
    maximum: int | None
    iqr: int | None
    dispersion: int | None
    bin_shares_milli: tuple[int, ...]

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(
            self, "status", _enum(self.status, AccountingDistributionStatus)
        )
        object.__setattr__(self, "sample_count", _count(self.sample_count))
        for name in ("minimum", "p25", "median", "p75", "maximum", "iqr", "dispersion"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _count(value))
        if (
            isinstance(self.bin_shares_milli, (str, bytes))
            or not isinstance(self.bin_shares_milli, tuple)
        ):
            raise AccountingAnalysisError("accounting_analysis_invalid_row")
        for share in self.bin_shares_milli:
            _count(share)
            if share > 1_000:
                raise AccountingAnalysisError("accounting_analysis_invalid_row")

    @property
    def source_layers(self) -> tuple[AccountingAnalysisLayer, ...]:
        return (AccountingAnalysisLayer.ANALYTICAL_ENTRY,)


@dataclass(frozen=True, slots=True)
class AccountingEvidenceHarvest:
    """Bounded detached evidence families plus explicit coverage."""

    records: tuple[AccountingRecordEvidenceRow, ...] = ()
    transfers: tuple[AccountingTransferEvidenceRow, ...] = ()
    contributions: tuple[AccountingContributionEvidenceRow, ...] = ()
    claims: tuple[AccountingClaimEvidenceRow, ...] = ()
    notices: tuple[str, ...] = ()
    coverage: AccountingCoverage = AccountingCoverage.MISSING
    malformed_claims: int = 0

    def __post_init__(self) -> None:
        for name in ("records", "transfers", "contributions", "claims", "notices"):
            value = getattr(self, name)
            if isinstance(value, (str, bytes)) or not isinstance(value, tuple):
                raise AccountingAnalysisError("accounting_analysis_invalid_row")
        object.__setattr__(self, "coverage", _enum(self.coverage, AccountingCoverage))
        object.__setattr__(self, "malformed_claims", _count(self.malformed_claims))
