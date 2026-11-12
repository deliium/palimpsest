"""Detached accounting ledger analysis over committed evidence.

No objective ledger, audit, fraud finding, money, or wealth oracle exists.
Rows are descriptive and researcher-facing only; they never reach cognition,
prompts, memory, world state, observer semantics, or stop selectors.
"""

from __future__ import annotations

import hashlib
import logging
from enum import StrEnum
from typing import Final

__all__ = [
    "ACCOUNTING_ALIGNMENT_PREFIX",
    "ACCOUNTING_CLAIM_PREFIX",
    "ACCOUNTING_COUNTERPARTY_PREFIX",
    "ACCOUNTING_ENTRY_PREFIX",
    "ACCOUNTING_FLOW_PREFIX",
    "ACCOUNTING_LEDGERS_ANALYSIS_POLICY_VERSION",
    "ACCOUNTING_OWNER_PREFIX",
    "ACCOUNTING_PEER_PREFIX",
    "ACCOUNTING_RECORD_PREFIX",
    "AccountingAlignment",
    "AccountingAnalysisError",
    "AccountingAnalysisLayer",
    "AccountingCoverage",
    "AccountingDistributionStatus",
    "AccountingEntryDirection",
    "AccountingEntryKindToken",
    "AccountingRecordAssessmentToken",
    "AccountingRecordIntegrityToken",
    "accounting_alignment_token",
    "accounting_claim_token",
    "accounting_counterparty_token",
    "accounting_entry_row_token",
    "accounting_flow_token",
    "accounting_owner_token",
    "accounting_record_row_token",
    "assert_accounting_layer_separation",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.accounting_ledgers.contract"
)

ACCOUNTING_LEDGERS_ANALYSIS_POLICY_VERSION: Final[str] = "accounting-ledgers.v1"
ACCOUNTING_OWNER_PREFIX: Final[str] = "acco-"
ACCOUNTING_ENTRY_PREFIX: Final[str] = "acce-"
ACCOUNTING_RECORD_PREFIX: Final[str] = "accr-"
ACCOUNTING_CLAIM_PREFIX: Final[str] = "accc-"
ACCOUNTING_FLOW_PREFIX: Final[str] = "accf-"
ACCOUNTING_COUNTERPARTY_PREFIX: Final[str] = "acccp-"
ACCOUNTING_ALIGNMENT_PREFIX: Final[str] = "acca-"
ACCOUNTING_PEER_PREFIX: Final[str] = "accpeer-"
ACCOUNTING_ANALYSIS_HEX_LEN: Final[int] = 16


class AccountingCoverage(StrEnum):
    """Coverage of one bounded evidence or analytical family."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    MISSING = "missing"


class AccountingAnalysisLayer(StrEnum):
    """Strictly separated objective, owner, and analytical layers."""

    OBJECTIVE_RECORD = "objective_record"
    OWNER_CLAIM = "owner_claim"
    ANALYTICAL_ENTRY = "analytical_entry"


class AccountingDistributionStatus(StrEnum):
    """Closed availability of one descriptive distribution."""

    AVAILABLE = "available"
    INSUFFICIENT_SAMPLES = "insufficient_samples"


class AccountingEntryKindToken(StrEnum):
    """Closed detached record-kind token."""

    EXCHANGE = "exchange"
    DEBT = "debt"
    INVENTORY = "inventory"
    ORGANIZATIONAL_RESOURCE = "organizational_resource"
    CONTRIBUTION = "contribution"


class AccountingEntryDirection(StrEnum):
    """Closed detached direction token."""

    INFLOW = "inflow"
    OUTFLOW = "outflow"
    HOLDING = "holding"
    RECEIVABLE = "receivable"
    PAYABLE = "payable"
    CONTRIBUTION = "contribution"


class AccountingRecordAssessmentToken(StrEnum):
    """Closed detached owner-appraisal token."""

    UNASSESSED = "unassessed"
    CONSISTENT = "consistent"
    CONTRADICTED = "contradicted"
    OUTDATED = "outdated"
    SUSPECTED_FRAUDULENT = "suspected_fraudulent"
    DAMAGED = "damaged"


class AccountingRecordIntegrityToken(StrEnum):
    """Closed detached observed-integrity token."""

    INTACT = "intact"
    DAMAGED = "damaged"
    PARTIALLY_LOST = "partially_lost"
    UNKNOWN = "unknown"


class AccountingAlignment(StrEnum):
    """Researcher-only alignment; never reaches cognition."""

    CONSISTENT = "consistent"
    UNRESOLVED = "unresolved"
    INCONSISTENT = "inconsistent"
    NOT_APPLICABLE = "not_applicable"


ACCOUNTING_ANALYSIS_FORBIDDEN_KEYS: Final[frozenset[str]] = frozenset(
    {
        "truth",
        "verified",
        "canonical_ledger",
        "audited",
        "objective_" + "bal" + "ance",
        "book_" + "value",
        "sol" + "vent",
        "sol" + "vency",
        "credit_score",
        "money",
        "currency",
        "price",
        "interest",
        "principal_" + "bal" + "ance",
        "reconciled",
        "fraud",
        "archive",
        "institution",
        "meaning",
        "bal" + "ance",
        "total_" + "value",
        "net_" + "worth",
        "score",
        "ranking",
    }
)

ACCOUNTING_ANALYSIS_NOTICE_CODES: Final[frozenset[str]] = frozenset(
    {
        "accounting_claim_malformed",
        "accounting_evidence_truncated",
        "accounting_record_truncated",
        "accounting_transfer_truncated",
        "accounting_contribution_truncated",
        "accounting_claim_truncated",
        "accounting_entry_truncated",
        "accounting_condition_truncated",
        "accounting_flow_truncated",
        "accounting_counterparty_truncated",
        "accounting_alignment_truncated",
        "accounting_row_out_of_range",
        "accounting_missing_owner_rows",
        "accounting_missing_evidence",
    }
)


class AccountingAnalysisError(ValueError):
    """Fail-closed analysis error; ``args[0]`` is a stable reason code."""

    @property
    def reason_code(self) -> str:
        if not self.args:
            return "accounting_analysis_invalid_row"
        return str(self.args[0])


def _require_material(value: object) -> str:
    if type(value) is not str or not value:
        raise AccountingAnalysisError("accounting_analysis_invalid_row")
    return value


def _require_count(value: object) -> int:
    if isinstance(value, bool) or type(value) is not int or value < 0:
        raise AccountingAnalysisError("accounting_analysis_invalid_window")
    return value


def accounting_token_hash(prefix: str, *parts: str) -> str:
    """Length-prefixed content-addressed token helper."""

    material = "\x1f".join(f"{len(part)}:{part}" for part in parts)
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return f"{prefix}{digest[:ACCOUNTING_ANALYSIS_HEX_LEN]}"


def accounting_record_evidence_token(artifact_id: str) -> str:
    """Mint the ``accrec-`` token used by cognition for one observed artifact."""

    digest = hashlib.sha256(_require_material(artifact_id).encode("utf-8")).hexdigest()
    return f"accrec-{digest[:ACCOUNTING_ANALYSIS_HEX_LEN]}"


def accounting_owner_token(owner_token: str, window_index: int) -> str:
    return accounting_token_hash(
        ACCOUNTING_OWNER_PREFIX,
        _require_material(owner_token),
        str(_require_count(window_index)),
    )


def accounting_entry_row_token(entry_token: str, window_index: int) -> str:
    return accounting_token_hash(
        ACCOUNTING_ENTRY_PREFIX,
        _require_material(entry_token),
        str(_require_count(window_index)),
    )


def accounting_record_row_token(record_token: str, window_index: int) -> str:
    return accounting_token_hash(
        ACCOUNTING_RECORD_PREFIX,
        _require_material(record_token),
        str(_require_count(window_index)),
    )


def accounting_claim_token(*parts: str) -> str:
    if not parts:
        raise AccountingAnalysisError("accounting_analysis_invalid_row")
    return accounting_token_hash(
        ACCOUNTING_CLAIM_PREFIX,
        *(_require_material(part) for part in parts),
    )


def accounting_flow_token(
    entry_kind: str, direction: str, window_index: int
) -> str:
    return accounting_token_hash(
        ACCOUNTING_FLOW_PREFIX,
        _require_material(entry_kind),
        _require_material(direction),
        str(_require_count(window_index)),
    )


def accounting_counterparty_token(counterparty_token: str) -> str:
    return accounting_token_hash(
        ACCOUNTING_COUNTERPARTY_PREFIX,
        _require_material(counterparty_token),
    )


def accounting_alignment_token(entry_token: str, window_index: int) -> str:
    return accounting_token_hash(
        ACCOUNTING_ALIGNMENT_PREFIX,
        _require_material(entry_token),
        str(_require_count(window_index)),
    )


def assert_accounting_layer_separation(*rows: object) -> None:
    """Reject a mixed list of objective, owner, and analytical rows."""

    observed: set[tuple[str, ...]] = set()
    for row in rows:
        layers = getattr(row, "source_layers", None)
        if layers is None:
            raise AccountingAnalysisError("accounting_analysis_layer_leak")
        try:
            normalized = tuple(
                layer.value if hasattr(layer, "value") else str(layer)
                for layer in layers
            )
        except TypeError as error:
            raise AccountingAnalysisError(
                "accounting_analysis_layer_leak"
            ) from error
        observed.add(normalized)
    if len(observed) > 1:
        raise AccountingAnalysisError("accounting_analysis_layer_leak")
