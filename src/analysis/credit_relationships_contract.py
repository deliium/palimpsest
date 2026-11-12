"""Detached credit relationship analysis over committed speech and transfer evidence.

No canonical debt, credit score, bank, money, or enforcement. Analysis rows are
descriptive and researcher-facing only; they never reach cognition, prompts,
memory, world state, observer semantics, or stop selectors.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Mapping
from enum import StrEnum
from typing import Final

__all__ = [
    "CREDIT_ALIGNMENT",
    "CREDIT_ALIGNMENT_PREFIX",
    "CREDIT_ANALYSIS_ERROR_CODES",
    "CREDIT_ANALYSIS_FORBIDDEN_KEYS",
    "CREDIT_ANALYSIS_HEX_LEN",
    "CREDIT_ANALYSIS_NOTICE_CODES",
    "CREDIT_CLAIM_ACTS",
    "CREDIT_CLAIM_CONDITIONS",
    "CREDIT_CLAIM_PREFIX",
    "CREDIT_COLLATERAL_KINDS",
    "CREDIT_COUNTERPARTY_PREFIX",
    "CREDIT_DISTRIBUTION_PREFIX",
    "CREDIT_LAYER_FORBIDDEN_PREFIXES",
    "CREDIT_OWNER_PREFIX",
    "CREDIT_PEER_PREFIX",
    "CREDIT_PERFORMANCE_PREFIX",
    "CREDIT_RELATIONSHIPS_ANALYSIS_POLICY_VERSION",
    "CreditAlignment",
    "CreditAnalysisLayer",
    "CreditClaimAct",
    "CreditClaimDirection",
    "CreditCoverage",
    "CreditDistributionStatus",
    "CreditOwnerLevel",
    "CreditOwnerStatus",
    "CreditPerformanceOutcome",
    "CreditRelationshipAnalysisError",
    "CreditSampleSource",
    "credit_alignment_token",
    "credit_claim_token",
    "credit_counterparty_token",
    "credit_distribution_token",
    "credit_owner_token",
    "credit_peer_token",
    "credit_performance_token",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.credit_relationships.contract"
)

CREDIT_RELATIONSHIPS_ANALYSIS_POLICY_VERSION: Final[str] = "credit-relationships.v1"
CREDIT_OWNER_PREFIX: Final[str] = "credo-"
CREDIT_PERFORMANCE_PREFIX: Final[str] = "credp-"
CREDIT_DISTRIBUTION_PREFIX: Final[str] = "credd-"
CREDIT_COUNTERPARTY_PREFIX: Final[str] = "credcp-"
CREDIT_PEER_PREFIX: Final[str] = "credpeer-"
CREDIT_CLAIM_PREFIX: Final[str] = "credcl-"
CREDIT_ALIGNMENT_PREFIX: Final[str] = "creda-"
CREDIT_ANALYSIS_HEX_LEN: Final[int] = 16

CREDIT_CLAIM_ACTS: Final[frozenset[str]] = frozenset(
    {
        "propose",
        "accept",
        "decline",
        "repay",
        "default",
        "renegotiate",
        "forgive",
        "dispute",
        "withdraw",
    }
)
CREDIT_CLAIM_CONDITIONS: Final[frozenset[str]] = frozenset(
    {"on_receipt", "by_deadline", "after_return", "shared_witness", "unspecified"}
)
CREDIT_COLLATERAL_KINDS: Final[frozenset[str]] = frozenset(
    {
        "none",
        "item_pledge",
        "service_pledge",
        "custody_pledge",
        "reputation_pledge",
        "unspecified",
    }
)


class CreditCoverage(StrEnum):
    """Coverage of one bounded evidence or analytical family."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    MISSING = "missing"


class CreditAnalysisLayer(StrEnum):
    """Strictly separated objective, owner, analytical, and comparison layers."""

    OBJECTIVE_CLAIM = "objective_claim"
    OWNER_CREDIT = "owner_credit"
    ANALYTICAL_PERFORMANCE = "analytical_performance"
    COMPARISON_VIEW = "comparison_view"


class CreditSampleSource(StrEnum):
    """Closed source of distribution samples; never pooled together."""

    PROPOSED = "proposed"
    AGREED = "agreed"


class CreditDistributionStatus(StrEnum):
    """Closed availability of one analytical distribution."""

    AVAILABLE = "available"
    INSUFFICIENT_SAMPLES = "insufficient_samples"


class CreditPerformanceOutcome(StrEnum):
    """Closed descriptive outcome label; never a probability or score."""

    ACTIVE = "active"
    PARTIALLY_REPAID = "partially_repaid"
    REPAID = "repaid"
    DEFAULTED = "defaulted"
    FORGIVEN = "forgiven"
    DISPUTED = "disputed"
    EXPIRED = "expired"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class CreditAlignment(StrEnum):
    """Researcher-only alignment; never reaches cognition."""

    CONSISTENT = "consistent"
    UNRESOLVED = "unresolved"
    INCONSISTENT = "inconsistent"
    NOT_APPLICABLE = "not_applicable"


class CreditClaimAct(StrEnum):
    """Closed credit claim act token for detached evidence rows."""

    PROPOSE = "propose"
    ACCEPT = "accept"
    DECLINE = "decline"
    REPAY = "repay"
    DEFAULT = "default"
    RENEGOTIATE = "renegotiate"
    FORGIVE = "forgive"
    DISPUTE = "dispute"
    WITHDRAW = "withdraw"


class CreditClaimDirection(StrEnum):
    """Closed owner-relative direction token for detached evidence rows."""

    OWNER_DEBTOR = "owner_debtor"
    OWNER_CREDITOR = "owner_creditor"


class CreditOwnerStatus(StrEnum):
    """Closed owner credit status token for detached export rows."""

    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    OPEN = "open"
    PARTIALLY_REPAID = "partially_repaid"
    REPAID = "repaid"
    DEFAULTED = "defaulted"
    FORGIVEN = "forgiven"
    DISPUTED = "disputed"
    WITHDRAWN = "withdrawn"
    DECLINED = "declined"
    EXPIRED = "expired"


class CreditOwnerLevel(StrEnum):
    """Closed owner expectation level token."""

    NONE = "none"
    WEAK = "weak"
    EXPECTED = "expected"
    STRONG = "strong"


CREDIT_ALIGNMENT: Final[frozenset[CreditAlignment]] = frozenset(CreditAlignment)

CREDIT_ANALYSIS_FORBIDDEN_KEYS: Final[frozenset[str]] = frozenset(
    {
        "bank",
        "banker",
        "loan",
        "interest",
        "interest_rate",
        "apr",
        "credit_score",
        "credit_limit",
        "default_probability",
        "money",
        "currency",
        "legal_tender",
        "deposit",
        "reserve",
        "enforceable_debt",
        "enforcement",
        "collection",
        "allocation",
        "quota",
        "canonical_credit",
        "ranking",
        "recommendation",
    }
)

CREDIT_LAYER_FORBIDDEN_PREFIXES: Final[Mapping[CreditAnalysisLayer, frozenset[str]]] = {
    CreditAnalysisLayer.OBJECTIVE_CLAIM: frozenset(
        {
            CREDIT_OWNER_PREFIX,
            CREDIT_PERFORMANCE_PREFIX,
            CREDIT_DISTRIBUTION_PREFIX,
            CREDIT_COUNTERPARTY_PREFIX,
            CREDIT_ALIGNMENT_PREFIX,
        }
    ),
    CreditAnalysisLayer.OWNER_CREDIT: frozenset(
        {
            CREDIT_PERFORMANCE_PREFIX,
            CREDIT_DISTRIBUTION_PREFIX,
            CREDIT_COUNTERPARTY_PREFIX,
            CREDIT_ALIGNMENT_PREFIX,
        }
    ),
    CreditAnalysisLayer.ANALYTICAL_PERFORMANCE: frozenset(
        {"event_token", "raw_event_token"}
    ),
    CreditAnalysisLayer.COMPARISON_VIEW: frozenset(
        {"event_token", "raw_event_token"}
    ),
}

CREDIT_ANALYSIS_NOTICE_CODES: Final[frozenset[str]] = frozenset(
    {
        "credit_claim_malformed",
        "credit_evidence_truncated",
        "credit_ratio_out_of_range",
        "credit_direction_conflict",
        "credit_performance_truncated",
        "credit_distribution_truncated",
        "credit_counterparty_truncated",
        "credit_owner_truncated",
        "credit_alignment_truncated",
        "credit_terms_mismatch",
        "credit_missing_owner_rows",
        "credit_missing_evidence",
    }
)

CREDIT_ANALYSIS_ERROR_CODES: Final[frozenset[str]] = frozenset(
    {
        "credit_analysis_invalid_policy",
        "credit_analysis_invalid_row",
        "credit_analysis_invalid_window",
        "credit_analysis_cap_exceeded",
        "credit_analysis_forbidden_key",
        "credit_analysis_layer_leak",
        "credit_analysis_missing_input",
    }
)


class CreditRelationshipAnalysisError(ValueError):
    """Fail-closed analysis error; ``args[0]`` is a stable reason code."""

    @property
    def reason_code(self) -> str:
        if not self.args:
            return "credit_analysis_invalid_row"
        return str(self.args[0])


def _require_material(value: object) -> str:
    if type(value) is not str or not value:
        _LOG.error(
            "credit_relationships_analysis_invalid "
            "code=credit_analysis_invalid_row"
        )
        raise CreditRelationshipAnalysisError("credit_analysis_invalid_row")
    return value


def _require_window(value: object) -> int:
    if isinstance(value, bool) or type(value) is not int or value < 0:
        raise CreditRelationshipAnalysisError("credit_analysis_invalid_window")
    return value


def _token_hash(prefix: str, *parts: str) -> str:
    material = "\x1f".join(f"{len(part)}:{part}" for part in parts)
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return f"{prefix}{digest[:CREDIT_ANALYSIS_HEX_LEN]}"


def credit_owner_token(
    owner_token: str, anchor_token: str, window_index: int
) -> str:
    """Content-addressed ``credo-`` token for one owner credit row."""

    return _token_hash(
        CREDIT_OWNER_PREFIX,
        _require_material(owner_token),
        _require_material(anchor_token),
        str(_require_window(window_index)),
    )


def credit_performance_token(anchor_token: str, window_index: int) -> str:
    """Content-addressed ``credp-`` token for one performance row."""

    return _token_hash(
        CREDIT_PERFORMANCE_PREFIX,
        _require_material(anchor_token),
        str(_require_window(window_index)),
    )


def credit_distribution_token(
    principal_kind: str,
    repayment_kind: str,
    sample_source: str,
    window_index: int,
) -> str:
    """Content-addressed ``credd-`` token for one distribution group."""

    return _token_hash(
        CREDIT_DISTRIBUTION_PREFIX,
        _require_material(principal_kind),
        _require_material(repayment_kind),
        _require_material(sample_source),
        str(_require_window(window_index)),
    )


def credit_counterparty_token(
    left_token: str, right_token: str, window_index: int
) -> str:
    """Content-addressed symmetric ``credcp-`` token for one party pair."""

    left, right = sorted(
        (_require_material(left_token), _require_material(right_token))
    )
    return _token_hash(
        CREDIT_COUNTERPARTY_PREFIX,
        left,
        right,
        str(_require_window(window_index)),
    )


def credit_peer_token(party_token: str) -> str:
    """Content-addressed ``credpeer-`` token for one detached owner export."""

    return _token_hash(CREDIT_PEER_PREFIX, _require_material(party_token))


def credit_claim_token(event_token: str, act: str, direction: str) -> str:
    """Content-addressed ``credcl-`` token for one claim relation."""

    return _token_hash(
        CREDIT_CLAIM_PREFIX,
        _require_material(event_token),
        _require_material(act),
        _require_material(direction),
    )


def credit_alignment_token(
    owner_token: str, anchor_token: str, window_index: int
) -> str:
    """Content-addressed ``creda-`` token for one researcher alignment row."""

    return _token_hash(
        CREDIT_ALIGNMENT_PREFIX,
        _require_material(owner_token),
        _require_material(anchor_token),
        str(_require_window(window_index)),
    )
