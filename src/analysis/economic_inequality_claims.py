"""Detached credit and organizational-control claims for inequality.

Claims are testimony, never objective possession. Credit rows come from
committed ``crd_v1`` relations; organizational rows come from detached
organization-operation harvests. Counterparty and item ids never enter the
snapshot-facing row; only the owner token, counts, and quantities do.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from analysis.credit_relationships_contract import CreditClaimAct
from analysis.credit_relationships_events import credit_evidence_rows_from_events
from analysis.credit_relationships_rows import CreditClaimEvidenceRow
from analysis.economic_inequality_contract import (
    EconomicInequalityCoverage,
    EconomicInequalityError,
    economic_inequality_owner_token,
)
from analysis.economic_inequality_policy import (
    EconomicInequalityAnalysisPolicy,
    default_economic_inequality_analysis_policy,
    window_index_for_tick,
)
from analysis.economic_inequality_rows import (
    EconomicControlClaimRow,
    EconomicCreditClaimRow,
)
from analysis.organization_operations import OrganizationOperationHarvestRows

__all__ = [
    "EconomicClaimHarvest",
    "control_claim_rows_from_operations",
    "credit_claim_rows_from_events",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.economic_inequality.claims"
)

_CONTROL_DOMAINS: Final[frozenset[str]] = frozenset({"resource_control", "storage"})
_CONTESTED_STANCES: Final[frozenset[str]] = frozenset({"disputed", "contested"})


@dataclass(frozen=True, slots=True)
class EconomicClaimHarvest:
    """Bounded claim evidence plus explicit coverage and notices."""

    credit_rows: tuple[EconomicCreditClaimRow, ...] = ()
    control_rows: tuple[EconomicControlClaimRow, ...] = ()
    notices: tuple[str, ...] = ()
    coverage: EconomicInequalityCoverage = EconomicInequalityCoverage.MISSING
    credit_claim_count: int = 0
    control_claim_count: int = 0
    owner_count: int = 0

    def __post_init__(self) -> None:
        for name in ("credit_rows", "control_rows", "notices"):
            value = getattr(self, name)
            if isinstance(value, (str, bytes)) or not isinstance(value, tuple):
                raise EconomicInequalityError("economic_inequality_invalid_row")
        if type(self.coverage) is not EconomicInequalityCoverage:
            raise EconomicInequalityError("economic_inequality_invalid_row")
        for name in ("credit_claim_count", "control_claim_count", "owner_count"):
            value = getattr(self, name)
            if isinstance(value, bool) or type(value) is not int or value < 0:
                raise EconomicInequalityError("economic_inequality_invalid_row")


def _policy(
    policy: EconomicInequalityAnalysisPolicy | None,
) -> EconomicInequalityAnalysisPolicy:
    active = (
        default_economic_inequality_analysis_policy()
        if policy is None
        else policy
    )
    if type(active) is not EconomicInequalityAnalysisPolicy:
        raise EconomicInequalityError("economic_inequality_invalid_policy")
    return active


def credit_claim_rows_from_events(
    events: Sequence[object],
    *,
    policy: EconomicInequalityAnalysisPolicy | None = None,
) -> tuple[EconomicCreditClaimRow, ...]:
    """Aggregate committed credit claims per owner and window."""

    _policy(policy)
    harvest = credit_evidence_rows_from_events(events)
    claims = harvest.claims
    by_claim: dict[str, list[CreditClaimEvidenceRow]] = {}
    by_owner_window: dict[tuple[str, int], list[CreditClaimEvidenceRow]] = {}
    for claim in claims:
        by_claim.setdefault(claim.anchor_token, []).append(claim)
        key = (claim.actor_token, claim.window_index)
        by_owner_window.setdefault(key, []).append(claim)

    rows: list[EconomicCreditClaimRow] = []
    for (owner, window_index), owner_claims in by_owner_window.items():
        claim_ids = {claim.anchor_token for claim in owner_claims}
        principal = 0
        repaid = 0
        contested = 0
        for claim_id in claim_ids:
            family = by_claim[claim_id]
            principal += max(item.principal_quantity for item in family)
            repaid += max(item.paid_quantity for item in family)
            if any(
                item.act in {CreditClaimAct.DISPUTE} for item in family
            ):
                contested += 1
        tick = max(item.tick for item in owner_claims)
        rows.append(
            EconomicCreditClaimRow(
                owner_token=economic_inequality_owner_token(owner),
                tick=tick,
                window_index=window_index,
                claimed_principal_quantity=principal,
                observed_repayment_quantity=repaid,
                claimed_relationship_count=len(claim_ids),
                contested_count=contested,
            )
        )
    rows.sort(key=lambda row: (row.tick, row.owner_token, row.window_index))
    _LOG.debug(
        "economic_inequality_credit_claims claims=%d rows=%d",
        len(claims),
        len(rows),
    )
    if harvest.coverage.value == "partial":
        _LOG.warning("economic_inequality_credit_claims_partial")
    return tuple(rows)


def control_claim_rows_from_operations(
    operations: Sequence[OrganizationOperationHarvestRows],
    *,
    policy: EconomicInequalityAnalysisPolicy | None = None,
) -> tuple[EconomicControlClaimRow, ...]:
    """Aggregate detached organization-control claims per owner and window."""

    active = _policy(policy)
    if isinstance(operations, (str, bytes)) or not isinstance(
        operations, Sequence
    ):
        raise EconomicInequalityError("economic_inequality_invalid_input")
    rows: list[EconomicControlClaimRow] = []
    for harvest in operations:
        if type(harvest) is not OrganizationOperationHarvestRows:
            raise EconomicInequalityError("economic_inequality_invalid_input")
        controls = tuple(
            row for row in harvest.controls if row.domain in _CONTROL_DOMAINS
        )
        if not controls:
            continue
        ticks = [
            row.last_tick
            for row in controls
            if row.last_tick is not None
        ]
        tick = max(ticks) if ticks else 0
        window_index = window_index_for_tick(tick, active)
        resource_ids = {
            row.organization_id
            for row in controls
            if row.domain == "resource_control"
        }
        storage_ids = {
            row.organization_id
            for row in controls
            if row.domain == "storage"
        }
        contested = sum(
            1
            for row in controls
            if (row.contest_count or 0) > 0
            or (row.stance or "") in _CONTESTED_STANCES
        )
        rows.append(
            EconomicControlClaimRow(
                owner_token=economic_inequality_owner_token(
                    harvest.owner.owner_id
                ),
                tick=tick,
                window_index=window_index,
                claimed_resource_control_count=len(resource_ids),
                claimed_storage_control_count=len(storage_ids),
                contested_count=contested,
            )
        )
    rows.sort(key=lambda row: (row.tick, row.owner_token, row.window_index))
    _LOG.debug(
        "economic_inequality_control_claims owners=%d rows=%d",
        len(operations),
        len(rows),
    )
    return tuple(rows)
