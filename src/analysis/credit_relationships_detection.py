"""Descriptive credit performance, distribution, and counterparty analytics."""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Final

from analysis.credit_relationships_contract import (
    CREDIT_LAYER_FORBIDDEN_PREFIXES,
    CreditClaimAct,
    CreditClaimDirection,
    CreditCoverage,
    CreditDistributionStatus,
    CreditPerformanceOutcome,
    CreditRelationshipAnalysisError,
    CreditSampleSource,
    credit_counterparty_token,
    credit_distribution_token,
    credit_performance_token,
)
from analysis.credit_relationships_policy import (
    CreditRelationshipsAnalysisPolicy,
    default_credit_relationships_analysis_policy,
)
from analysis.credit_relationships_rows import (
    CreditClaimEvidenceRow,
    CreditCounterpartyRow,
    CreditDistributionRow,
    CreditEvidenceHarvest,
    CreditPerformanceRow,
    infer_credit_layer,
)

__all__ = [
    "CreditDistributionSummary",
    "assert_credit_layer_separation",
    "credit_distribution_summary",
    "detect_credit_counterparties",
    "detect_credit_distributions",
    "detect_credit_performances",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.credit_relationships.detection"
)

_TERMS_ACTS: Final[frozenset[CreditClaimAct]] = frozenset(
    {CreditClaimAct.PROPOSE, CreditClaimAct.ACCEPT, CreditClaimAct.RENEGOTIATE}
)


def _policy(
    policy: CreditRelationshipsAnalysisPolicy | None,
) -> CreditRelationshipsAnalysisPolicy:
    active = (
        default_credit_relationships_analysis_policy()
        if policy is None
        else policy
    )
    if type(active) is not CreditRelationshipsAnalysisPolicy:
        raise CreditRelationshipAnalysisError("credit_analysis_invalid_policy")
    return active


@dataclass(frozen=True, slots=True)
class CreditDistributionSummary:
    """Nearest-rank quantiles and five bin shares for repayment ratios."""

    status: CreditDistributionStatus
    sample_count: int
    minimum: int
    p25: int
    median: int
    p75: int
    maximum: int
    iqr: int
    dispersion: int
    bins: tuple[int, int, int, int, int]


def credit_distribution_summary(
    ratios: Sequence[int],
    *,
    policy: CreditRelationshipsAnalysisPolicy | None = None,
) -> CreditDistributionSummary:
    """Return nearest-rank quantiles and five bin shares for raw ratios."""

    active = _policy(policy)
    values = sorted(ratios)
    count = len(values)
    if count < active.min_distribution_samples:
        return CreditDistributionSummary(
            status=CreditDistributionStatus.INSUFFICIENT_SAMPLES,
            sample_count=count,
            minimum=0,
            p25=0,
            median=0,
            p75=0,
            maximum=0,
            iqr=0,
            dispersion=0,
            bins=(0, 0, 0, 0, 0),
        )
    minimum = values[0]
    maximum = values[-1]
    p25 = values[(count - 1) // 4]
    median = values[(count - 1) // 2]
    p75 = values[(3 * (count - 1)) // 4]
    iqr = p75 - p25
    dispersion = iqr * 1_000 // max(1, median)
    q20 = values[(count - 1) // 5]
    q40 = values[(2 * (count - 1)) // 5]
    q60 = values[(3 * (count - 1)) // 5]
    q80 = values[(4 * (count - 1)) // 5]
    counts = [0, 0, 0, 0, 0]
    for value in values:
        if value < q20:
            counts[0] += 1
        elif value < q40:
            counts[1] += 1
        elif value < q60:
            counts[2] += 1
        elif value < q80:
            counts[3] += 1
        else:
            counts[4] += 1
    shares = [bucket * 1_000 // count for bucket in counts]
    shares[4] = 1_000 - sum(shares[:4])
    return CreditDistributionSummary(
        status=CreditDistributionStatus.AVAILABLE,
        sample_count=count,
        minimum=minimum,
        p25=p25,
        median=median,
        p75=p75,
        maximum=maximum,
        iqr=iqr,
        dispersion=dispersion,
        bins=(shares[0], shares[1], shares[2], shares[3], shares[4]),
    )


def _grouped_claims(
    evidence: CreditEvidenceHarvest,
) -> dict[tuple[str, int], list[CreditClaimEvidenceRow]]:
    grouped: dict[tuple[str, int], list[CreditClaimEvidenceRow]] = defaultdict(list)
    for row in evidence.claims:
        grouped[(row.anchor_token, row.window_index)].append(row)
    for rows in grouped.values():
        rows.sort(key=lambda row: (row.tick, row.claim_id))
    return grouped


def _outcome(
    *,
    paid: int,
    repayment_quantity: int,
    counts: Mapping[CreditClaimAct, int],
    due_tick: int | None,
    window_end: int,
) -> CreditPerformanceOutcome:
    if paid >= repayment_quantity:
        return CreditPerformanceOutcome.REPAID
    if counts[CreditClaimAct.DEFAULT]:
        return CreditPerformanceOutcome.DEFAULTED
    if counts[CreditClaimAct.FORGIVE]:
        return CreditPerformanceOutcome.FORGIVEN
    if counts[CreditClaimAct.DISPUTE]:
        return CreditPerformanceOutcome.DISPUTED
    if counts[CreditClaimAct.REPAY]:
        return CreditPerformanceOutcome.PARTIALLY_REPAID
    if (
        due_tick is not None
        and window_end > due_tick + 8
        and not any(
            counts[act]
            for act in (
                CreditClaimAct.REPAY,
                CreditClaimAct.DEFAULT,
                CreditClaimAct.FORGIVE,
                CreditClaimAct.DISPUTE,
            )
        )
    ):
        return CreditPerformanceOutcome.EXPIRED
    return CreditPerformanceOutcome.ACTIVE


def detect_credit_performances(
    evidence: CreditEvidenceHarvest,
    *,
    window_end: int | None = None,
    policy: CreditRelationshipsAnalysisPolicy | None = None,
) -> tuple[CreditPerformanceRow, ...]:
    """Classify descriptive performance outcomes from claim and transfer evidence."""

    active = _policy(policy)
    if type(evidence) is not CreditEvidenceHarvest:
        raise CreditRelationshipAnalysisError("credit_analysis_invalid_row")
    if window_end is None:
        ticks = [row.tick for row in evidence.claims]
        ticks.extend(row.tick for row in evidence.transfers)
        window_end = max(ticks) if ticks else 0
    if isinstance(window_end, bool) or type(window_end) is not int or window_end < 0:
        raise CreditRelationshipAnalysisError("credit_analysis_invalid_row")

    grouped = _grouped_claims(evidence)
    rows: list[CreditPerformanceRow] = []
    for (anchor, window_index), claims in grouped.items():
        earliest = claims[0]
        terms = next(
            (row for row in claims if row.act in _TERMS_ACTS),
            earliest,
        )
        direction_conflict = any(
            row.direction is not earliest.direction
            or row.principal_kind != terms.principal_kind
            or row.repayment_kind != terms.repayment_kind
            for row in claims
        )
        counts = {act: 0 for act in CreditClaimAct}
        for row in claims:
            counts[row.act] += 1
        paid = min(
            terms.repayment_quantity,
            max((row.paid_quantity for row in claims), default=0),
        )
        if earliest.direction is CreditClaimDirection.OWNER_DEBTOR:
            debtor_token = earliest.actor_token
            creditor_token = earliest.counterparty_token
        else:
            debtor_token = earliest.counterparty_token
            creditor_token = earliest.actor_token
        observed_transfer_count = sum(
            1
            for transfer in evidence.transfers
            if transfer.window_index == window_index
            and transfer.actor_token == debtor_token
            and transfer.recipient_token == creditor_token
        )
        outcome = _outcome(
            paid=paid,
            repayment_quantity=terms.repayment_quantity,
            counts=counts,
            due_tick=terms.due_tick,
            window_end=window_end,
        )
        coverage = evidence.coverage
        if (
            direction_conflict
            or coverage is CreditCoverage.PARTIAL
            or any(
                row.confidence_milli == 0 or row.act is CreditClaimAct.DECLINE
                for row in claims
                if row.coverage is CreditCoverage.PARTIAL
            )
        ):
            coverage = CreditCoverage.PARTIAL
        if direction_conflict:
            _LOG.warning("credit_direction_conflict count=1")
        rows.append(
            CreditPerformanceRow(
                performance_id=credit_performance_token(anchor, window_index),
                window_index=window_index,
                anchor_token=anchor,
                debtor_token=debtor_token,
                creditor_token=creditor_token,
                direction=earliest.direction,
                principal_kind=terms.principal_kind,
                repayment_kind=terms.repayment_kind,
                principal_quantity=terms.principal_quantity,
                repayment_quantity=terms.repayment_quantity,
                paid_quantity=paid,
                claim_count=len(claims),
                propose_count=counts[CreditClaimAct.PROPOSE],
                accept_count=counts[CreditClaimAct.ACCEPT],
                decline_count=counts[CreditClaimAct.DECLINE],
                withdraw_count=counts[CreditClaimAct.WITHDRAW],
                repay_count=counts[CreditClaimAct.REPAY],
                default_count=counts[CreditClaimAct.DEFAULT],
                renegotiate_count=counts[CreditClaimAct.RENEGOTIATE],
                forgive_count=counts[CreditClaimAct.FORGIVE],
                dispute_count=counts[CreditClaimAct.DISPUTE],
                observed_transfer_count=observed_transfer_count,
                outcome=outcome,
                first_tick=claims[0].tick,
                last_tick=claims[-1].tick,
                due_tick=terms.due_tick,
                direction_conflict=direction_conflict,
                coverage=coverage,
            )
        )
    rows.sort(key=lambda row: (row.window_index, row.performance_id))
    if len(rows) > active.max_performance_rows:
        rows = rows[: active.max_performance_rows]
        rows = [replace(row, coverage=CreditCoverage.PARTIAL) for row in rows]
        _LOG.warning(
            "credit_performance_truncated count=%s",
            active.max_performance_rows,
        )
    _LOG.debug("credit_detection_completed performances=%s", len(rows))
    return tuple(rows)


def detect_credit_distributions(
    evidence: CreditEvidenceHarvest,
    *,
    policy: CreditRelationshipsAnalysisPolicy | None = None,
) -> tuple[CreditDistributionRow, ...]:
    """Emit separate proposed and agreed repayment-ratio distributions."""

    active = _policy(policy)
    if type(evidence) is not CreditEvidenceHarvest:
        raise CreditRelationshipAnalysisError("credit_analysis_invalid_row")
    grouped: dict[tuple[int, str, str, CreditSampleSource], list[int]] = defaultdict(
        list
    )
    skipped = 0
    for row in evidence.claims:
        if row.act is CreditClaimAct.PROPOSE:
            source = CreditSampleSource.PROPOSED
        elif row.act in {CreditClaimAct.ACCEPT, CreditClaimAct.RENEGOTIATE}:
            source = CreditSampleSource.AGREED
        else:
            continue
        ratio = row.repayment_quantity * 1_000 // row.principal_quantity
        if ratio <= 0 or ratio > active.max_ratio_milli:
            skipped += 1
            continue
        grouped[
            (row.window_index, row.principal_kind, row.repayment_kind, source)
        ].append(ratio)
    if skipped:
        _LOG.warning("credit_ratio_out_of_range count=%s", skipped)
    rows: list[CreditDistributionRow] = []
    for key in sorted(
        grouped,
        key=lambda item: (item[0], item[1], item[2], item[3].value),
    ):
        window_index, principal_kind, repayment_kind, source = key
        summary = credit_distribution_summary(grouped[key], policy=active)
        rows.append(
            CreditDistributionRow(
                distribution_id=credit_distribution_token(
                    principal_kind,
                    repayment_kind,
                    source.value,
                    window_index,
                ),
                window_index=window_index,
                principal_kind=principal_kind,
                repayment_kind=repayment_kind,
                sample_source=source,
                sample_count=summary.sample_count,
                min_ratio_milli=summary.minimum,
                p25_ratio_milli=summary.p25,
                median_ratio_milli=summary.median,
                p75_ratio_milli=summary.p75,
                max_ratio_milli=summary.maximum,
                iqr_milli=summary.iqr,
                dispersion_milli=summary.dispersion,
                bin_shares_milli=summary.bins,
                status=summary.status,
                coverage=(
                    CreditCoverage.PARTIAL
                    if evidence.coverage is CreditCoverage.PARTIAL
                    else CreditCoverage.COMPLETE
                ),
            )
        )
    rows.sort(
        key=lambda row: (
            row.window_index,
            row.sample_source.value,
            row.distribution_id,
        )
    )
    if len(rows) > active.max_distribution_rows:
        rows = rows[: active.max_distribution_rows]
        rows = [replace(row, coverage=CreditCoverage.PARTIAL) for row in rows]
        _LOG.warning(
            "credit_distribution_truncated count=%s",
            active.max_distribution_rows,
        )
    _LOG.debug("credit_detection_completed distributions=%s", len(rows))
    return tuple(rows)


def _pair(left: str, right: str) -> tuple[str, str]:
    return (left, right) if left <= right else (right, left)


def detect_credit_counterparties(
    evidence: CreditEvidenceHarvest,
    *,
    policy: CreditRelationshipsAnalysisPolicy | None = None,
) -> tuple[CreditCounterpartyRow, ...]:
    """Aggregate claim and transfer counts over unordered party pairs."""

    active = _policy(policy)
    if type(evidence) is not CreditEvidenceHarvest:
        raise CreditRelationshipAnalysisError("credit_analysis_invalid_row")
    grouped: dict[tuple[int, str, str], list[CreditClaimEvidenceRow]] = defaultdict(
        list
    )
    for row in evidence.claims:
        left, right = _pair(row.actor_token, row.counterparty_token)
        grouped[(row.window_index, left, right)].append(row)
    rows: list[CreditCounterpartyRow] = []
    for key in sorted(grouped):
        window_index, left, right = key
        members = grouped[key]
        counts = {act: 0 for act in CreditClaimAct}
        for member in members:
            counts[member.act] += 1
        observed_transfer_count = sum(
            1
            for transfer in evidence.transfers
            if transfer.window_index == window_index
            and _pair(transfer.actor_token, transfer.recipient_token)
            == (left, right)
        )
        rows.append(
            CreditCounterpartyRow(
                counterparty_id=credit_counterparty_token(
                    left, right, window_index
                ),
                window_index=window_index,
                left_token=left,
                right_token=right,
                relationship_count=len({member.anchor_token for member in members}),
                owner_count=len({member.actor_token for member in members}),
                claim_count=len(members),
                repay_claim_count=counts[CreditClaimAct.REPAY],
                default_claim_count=counts[CreditClaimAct.DEFAULT],
                forgive_claim_count=counts[CreditClaimAct.FORGIVE],
                dispute_claim_count=counts[CreditClaimAct.DISPUTE],
                renegotiate_claim_count=counts[CreditClaimAct.RENEGOTIATE],
                observed_transfer_count=observed_transfer_count,
                coverage=(
                    CreditCoverage.PARTIAL
                    if evidence.coverage is CreditCoverage.PARTIAL
                    else CreditCoverage.COMPLETE
                ),
            )
        )
    rows.sort(key=lambda row: (row.window_index, row.counterparty_id))
    if len(rows) > active.max_counterparty_rows:
        rows = rows[: active.max_counterparty_rows]
        rows = [replace(row, coverage=CreditCoverage.PARTIAL) for row in rows]
        _LOG.warning(
            "credit_counterparty_truncated count=%s",
            active.max_counterparty_rows,
        )
    _LOG.debug("credit_detection_completed counterparties=%s", len(rows))
    return tuple(rows)


def assert_credit_layer_separation(
    layers: Mapping[object, Sequence[object]] | Sequence[object],
) -> None:
    """Raise on a forbidden field or a cross-layer identity/value leak."""

    entries: list[tuple[object, object]] = []
    if isinstance(layers, Mapping):
        for layer, rows in layers.items():
            if isinstance(rows, (str, bytes)) or not isinstance(rows, Sequence):
                raise CreditRelationshipAnalysisError("credit_analysis_invalid_row")
            entries.extend((layer, row) for row in rows)
    elif isinstance(layers, (str, bytes)) or not isinstance(layers, Sequence):
        raise CreditRelationshipAnalysisError("credit_analysis_missing_input")
    else:
        for row in layers:
            entries.append((infer_credit_layer(row), row))

    from analysis.credit_relationships_contract import (
        CREDIT_ANALYSIS_FORBIDDEN_KEYS,
    )

    for layer, row in entries:
        fields = getattr(type(row), "__dataclass_fields__", {})
        if set(fields) & CREDIT_ANALYSIS_FORBIDDEN_KEYS:
            raise CreditRelationshipAnalysisError("credit_analysis_forbidden_key")
        forbidden = CREDIT_LAYER_FORBIDDEN_PREFIXES[layer]  # type: ignore[index]
        for name in fields:
            if name in forbidden or any(name.startswith(pre) for pre in forbidden):
                raise CreditRelationshipAnalysisError("credit_analysis_layer_leak")
            value = getattr(row, name)
            values = value if isinstance(value, (tuple, list)) else (value,)
            for item in values:
                if type(item) is not str:
                    continue
                for prefix in forbidden:
                    if prefix.endswith("-") and item.startswith(prefix):
                        raise CreditRelationshipAnalysisError(
                            "credit_analysis_layer_leak"
                        )
