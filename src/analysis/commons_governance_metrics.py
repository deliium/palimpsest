"""Pure sustainability and cooperation summaries for commons governance.

Detached from experiments and concrete runner services. Callers supply trusted
overexploitation history rows and finalized-boundary deltas only.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from analysis.overexploitation_history import (
    HistoryCoverage,
    HistoryStopCode,
    OverexploitationHistory,
    OverexploitationHistoryRow,
)
from simulation.commons_governance_evidence import (
    CommonsGovernanceBoundaryExport,
    CommonsGovernanceConsiderationDelta,
    CommonsGovernanceOwnerDelta,
    CommonsGovernanceProposalHead,
    CommonsGovernanceResolutionDelta,
    CommonsGovernanceTransitionDelta,
    CommonsLaneStatus,
)
from simulation.models import RunId
from world.events import Drunk, WorldEvent
from world.identifiers import (
    EntityId,
    WorldId,
    require_exact_nonneg_int,
    require_stable_id,
)
from world.values import round_physical

__all__ = [
    "COMMONS_GOVERNANCE_REPORT_VERSION",
    "CommonsCooperationSummary",
    "CommonsGovernanceReport",
    "CommonsJointUseSummary",
    "CommonsLaneCoverage",
    "CommonsSustainabilitySummary",
    "CommonsWelfareSummary",
    "build_commons_governance_report",
    "summarize_cooperation",
    "summarize_joint_use",
    "summarize_sustainability",
    "summarize_welfare",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.commons_governance_metrics")

COMMONS_GOVERNANCE_REPORT_VERSION: Final[str] = "commons-governance-report-v1"

_UNDEFINED: Final[float | None] = None


@dataclass(frozen=True, slots=True)
class CommonsLaneCoverage:
    """One ledger lane with status, denominators, and reason codes."""

    lane: str
    status: CommonsLaneStatus
    expected: int
    usable: int
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "lane", require_stable_id("lane", self.lane))
        if type(self.status) is not CommonsLaneStatus:
            raise TypeError("status must be CommonsLaneStatus")
        object.__setattr__(
            self, "expected", require_exact_nonneg_int("expected", self.expected)
        )
        object.__setattr__(
            self, "usable", require_exact_nonneg_int("usable", self.usable)
        )
        if self.usable > self.expected:
            raise ValueError("usable must be <= expected")
        codes = tuple(self.reason_codes)
        for code in codes:
            require_stable_id("reason_code", code)
        object.__setattr__(self, "reason_codes", codes)


@dataclass(frozen=True, slots=True)
class CommonsSustainabilitySummary:
    """Objective stock condition from contiguous overexploitation history."""

    stock_id: EntityId
    covered_stock_ticks: int
    initial_stock_tenths: int | None
    end_stock_tenths: int | None
    minimum_stock_tenths: int | None
    mean_end_stock_over_baseline: float | None
    withdrawal_tenths_total: int
    renewal_tenths_total: int
    renewal_over_withdrawal: float | None
    ticks_withdrawal_above_threshold: int
    ticks_at_damage_cap: int
    ticks_damage_increasing: int
    ticks_literal_zero_end_stock: int
    mean_damage_over_baseline: float | None
    terminal_damage_over_baseline: float | None
    resource_depleted_nonzero_denials: int
    literal_zero_denials: int
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.stock_id) is not EntityId:
            raise TypeError("stock_id must be EntityId")
        object.__setattr__(
            self,
            "covered_stock_ticks",
            require_exact_nonneg_int(
                "covered_stock_ticks", self.covered_stock_ticks
            ),
        )


@dataclass(frozen=True, slots=True)
class CommonsJointUseSummary:
    """Objective shared-use counts; never interpreted as cooperation."""

    stock_id: EntityId
    distinct_founders: int
    attributed_drunk_count: int
    multi_user_ticks: int
    managed_draw_attempts: int
    attributed_debit_tenths: int
    receipt_withdrawal_tenths: int
    unattributed_residual_tenths: int
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.stock_id) is not EntityId:
            raise TypeError("stock_id must be EntityId")


@dataclass(frozen=True, slots=True)
class CommonsCooperationSummary:
    """Subjective owner-claim series; no composite cooperation score."""

    stock_id: EntityId
    supported_arrangements: int
    opposition_heads: int
    contested_heads: int
    monitor_checks: int
    access_claims: int
    criticism_delivered: int
    wait_expected_considerations: int
    voluntary_deferrals: int
    proceeded_under_wait_expected: int
    turn_opportunities: int
    turn_matching_receipts: int
    complementary_alternating_acts: int
    support_over_eligible_opportunities: float | None
    eligible_proposal_recipient_opportunities: int
    distinct_support_deliveries: int
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.stock_id) is not EntityId:
            raise TypeError("stock_id must be EntityId")


@dataclass(frozen=True, slots=True)
class CommonsWelfareSummary:
    """Terminal living-founder thirst coverage; not inferred from extraction."""

    terminal_living_founders: int
    thirst_observation_coverage: int
    thirst_sum_tenths: int | None
    thirst_mean_tenths: float | None
    reason_codes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CommonsGovernanceReport:
    """Frozen ``commons-governance-report-v1`` sealed after one capture."""

    schema_version: str
    run_id: str
    stock_ids: tuple[EntityId, ...]
    lanes: tuple[CommonsLaneCoverage, ...]
    sustainability: tuple[CommonsSustainabilitySummary, ...]
    joint_use: tuple[CommonsJointUseSummary, ...]
    cooperation: tuple[CommonsCooperationSummary, ...]
    welfare: CommonsWelfareSummary
    social_applicable: bool
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.schema_version != COMMONS_GOVERNANCE_REPORT_VERSION:
            raise ValueError("commons_governance_report_schema_invalid")
        object.__setattr__(self, "run_id", require_stable_id("run_id", self.run_id))
        stocks = tuple(self.stock_ids)
        for stock in stocks:
            if type(stock) is not EntityId:
                raise TypeError("stock_ids entries must be EntityId")
        object.__setattr__(self, "stock_ids", stocks)
        if type(self.social_applicable) is not bool:
            raise TypeError("social_applicable must be bool")


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return _UNDEFINED
    return numerator / denominator


def _mean(values: Sequence[int]) -> float | None:
    if not values:
        return _UNDEFINED
    return sum(values) / len(values)


def summarize_sustainability(
    history: OverexploitationHistory,
    *,
    baseline_tenths: int | None = None,
    denial_events: Sequence[tuple[EntityId, int, str, int]] = (),
) -> CommonsSustainabilitySummary:
    """Project one stock window into integer-tenths sustainability counts.

    ``denial_events`` entries are ``(stock_id, tick, reason, stock_tenths)``.
    """
    if type(history) is not OverexploitationHistory:
        raise TypeError("history must be OverexploitationHistory")
    rows = history.rows
    reasons: list[str] = []
    if history.coverage is HistoryCoverage.UNAVAILABLE:
        reasons.append(history.stop_code.value)
        return CommonsSustainabilitySummary(
            stock_id=history.resource_id,
            covered_stock_ticks=0,
            initial_stock_tenths=None,
            end_stock_tenths=None,
            minimum_stock_tenths=None,
            mean_end_stock_over_baseline=None,
            withdrawal_tenths_total=0,
            renewal_tenths_total=0,
            renewal_over_withdrawal=None,
            ticks_withdrawal_above_threshold=0,
            ticks_at_damage_cap=0,
            ticks_damage_increasing=0,
            ticks_literal_zero_end_stock=0,
            mean_damage_over_baseline=None,
            terminal_damage_over_baseline=None,
            resource_depleted_nonzero_denials=0,
            literal_zero_denials=0,
            reason_codes=tuple(sorted(set(reasons))),
        )
    if history.coverage is HistoryCoverage.PARTIAL:
        reasons.append(history.stop_code.value)
    if not rows:
        reasons.append("empty_window")
        return CommonsSustainabilitySummary(
            stock_id=history.resource_id,
            covered_stock_ticks=0,
            initial_stock_tenths=None,
            end_stock_tenths=None,
            minimum_stock_tenths=None,
            mean_end_stock_over_baseline=None,
            withdrawal_tenths_total=0,
            renewal_tenths_total=0,
            renewal_over_withdrawal=None,
            ticks_withdrawal_above_threshold=0,
            ticks_at_damage_cap=0,
            ticks_damage_increasing=0,
            ticks_literal_zero_end_stock=0,
            mean_damage_over_baseline=None,
            terminal_damage_over_baseline=None,
            resource_depleted_nonzero_denials=0,
            literal_zero_denials=0,
            reason_codes=tuple(sorted(set(reasons))),
        )

    baseline = (
        baseline_tenths
        if baseline_tenths is not None
        else rows[0].healthy_potential_tenths
    )
    if baseline <= 0:
        reasons.append("baseline_undefined")
        baseline_for_ratio = 0
    else:
        baseline_for_ratio = baseline

    withdrawal_total = sum(row.withdrawal_tenths for row in rows)
    renewal_total = sum(row.replacement_tenths for row in rows)
    above = sum(
        1
        for row in rows
        if row.withdrawal_tenths > row.damage_threshold_tenths
    )
    # Damage cap / floor: damage has consumed all headroom above threshold.
    at_cap = sum(
        1
        for row in rows
        if row.healthy_potential_tenths > row.damage_threshold_tenths
        and row.after_damage_tenths
        >= (row.healthy_potential_tenths - row.damage_threshold_tenths)
    )
    increasing = 0
    prior: OverexploitationHistoryRow | None = None
    for row in rows:
        if prior is not None and row.after_damage_tenths > prior.after_damage_tenths:
            increasing += 1
        prior = row
    zero_end = sum(1 for row in rows if row.end_stock_tenths == 0)
    end_ratios = [row.end_stock_tenths for row in rows]
    damage_ratios = [row.after_damage_tenths for row in rows]
    mean_end = _mean(end_ratios)
    mean_damage = _mean(damage_ratios)
    mean_end_over = (
        None
        if mean_end is None or baseline_for_ratio == 0
        else mean_end / baseline_for_ratio
    )
    mean_damage_over = (
        None
        if mean_damage is None or baseline_for_ratio == 0
        else mean_damage / baseline_for_ratio
    )
    terminal_damage_over = (
        None
        if baseline_for_ratio == 0
        else rows[-1].after_damage_tenths / baseline_for_ratio
    )

    nonzero_denials = 0
    zero_denials = 0
    for stock_id, _tick, reason, stock_tenths in denial_events:
        if stock_id != history.resource_id:
            continue
        if reason != "resource_depleted":
            continue
        if stock_tenths > 0:
            nonzero_denials += 1
        else:
            zero_denials += 1

    return CommonsSustainabilitySummary(
        stock_id=history.resource_id,
        covered_stock_ticks=len(rows),
        initial_stock_tenths=rows[0].start_stock_tenths,
        end_stock_tenths=rows[-1].end_stock_tenths,
        minimum_stock_tenths=min(row.end_stock_tenths for row in rows),
        mean_end_stock_over_baseline=mean_end_over,
        withdrawal_tenths_total=withdrawal_total,
        renewal_tenths_total=renewal_total,
        renewal_over_withdrawal=_ratio(renewal_total, withdrawal_total),
        ticks_withdrawal_above_threshold=above,
        ticks_at_damage_cap=at_cap,
        ticks_damage_increasing=increasing,
        ticks_literal_zero_end_stock=zero_end,
        mean_damage_over_baseline=mean_damage_over,
        terminal_damage_over_baseline=terminal_damage_over,
        resource_depleted_nonzero_denials=nonzero_denials,
        literal_zero_denials=zero_denials,
        reason_codes=tuple(sorted(set(reasons))),
    )


def summarize_joint_use(
    *,
    stock_id: EntityId,
    founder_ids: Sequence[str],
    events: Sequence[WorldEvent],
    resolutions: Sequence[CommonsGovernanceResolutionDelta],
    receipt_withdrawal_tenths: int,
) -> CommonsJointUseSummary:
    """Count attributed joint use without treating shared use as cooperation."""
    if type(stock_id) is not EntityId:
        raise TypeError("stock_id must be EntityId")
    founders = {require_stable_id("founder_id", item) for item in founder_ids}
    reasons: list[str] = []
    users_by_tick: dict[int, set[str]] = defaultdict(set)
    attributed = 0
    debit_tenths = 0
    for event in events:
        details = event.details
        if type(details) is not Drunk:
            continue
        if details.consumed_item is True:
            continue
        if details.source_id != stock_id:
            continue
        actor = event.actor_id
        if actor is None:
            reasons.append("drunk_unattributed_actor")
            continue
        actor_token = actor.value
        attributed += 1
        users_by_tick[event.tick].add(actor_token)
        if details.quantity_delta is not None:
            tenths = round(round_physical(abs(details.quantity_delta)) * 10.0)
            if tenths >= 0:
                debit_tenths += tenths
            else:
                reasons.append("drunk_quantity_invalid")
        else:
            reasons.append("drunk_quantity_missing")

    multi = sum(1 for users in users_by_tick.values() if len(users) >= 2)
    attempts = 0
    for row in resolutions:
        if row.command_kind != "drink":
            continue
        if row.source_id != stock_id:
            continue
        attempts += 1

    residual = receipt_withdrawal_tenths - debit_tenths
    if residual < 0:
        reasons.append("debit_exceeds_receipt")
        residual_abs = abs(residual)
    else:
        residual_abs = residual
    if residual_abs > 0:
        reasons.append("unattributed_residual")

    return CommonsJointUseSummary(
        stock_id=stock_id,
        distinct_founders=len(founders),
        attributed_drunk_count=attributed,
        multi_user_ticks=multi,
        managed_draw_attempts=attempts,
        attributed_debit_tenths=debit_tenths,
        receipt_withdrawal_tenths=receipt_withdrawal_tenths,
        unattributed_residual_tenths=residual_abs,
        reason_codes=tuple(sorted(set(reasons))),
    )


def _proposal_key(head: CommonsGovernanceProposalHead) -> tuple[str, str]:
    return (head.stock_id.value, head.proposal_id)


def summarize_cooperation(
    *,
    stock_id: EntityId,
    transitions: Sequence[CommonsGovernanceTransitionDelta],
    considerations: Sequence[CommonsGovernanceConsiderationDelta],
    proposals: Sequence[CommonsGovernanceProposalHead],
    turn_receipts: Sequence[tuple[str, int, str]] = (),
) -> CommonsCooperationSummary:
    """Count subjective cooperation series without composite scores.

    ``turn_receipts`` entries are ``(owner_id, tick, report_code)`` for
    owner-matching turn reports.
    """
    if type(stock_id) is not EntityId:
        raise TypeError("stock_id must be EntityId")
    reasons: list[str] = []
    stock_transitions = [row for row in transitions if row.stock_id == stock_id]
    stock_considerations = [
        row for row in considerations if row.target_id == stock_id
    ]
    stock_proposals = [row for row in proposals if row.stock_id == stock_id]

    supported = {
        _proposal_key(row)
        for row in stock_proposals
        if row.supported and not row.contested
    }
    opposition = sum(1 for row in stock_proposals if row.opposed)
    contested = sum(1 for row in stock_proposals if row.contested)
    monitor = sum(
        1 for row in stock_transitions if row.code == "stock_checked"
    )
    claims = sum(1 for row in stock_transitions if row.code == "access_claim")
    criticism = sum(1 for row in stock_transitions if row.code == "criticize")

    wait_expected = [
        row
        for row in stock_considerations
        if row.opportunity == "wait_expected"
    ]
    deferrals: set[tuple[str, int, str]] = set()
    proceeded = 0
    for row in wait_expected:
        if row.choice == "deferred_draw":
            deferrals.add((row.owner_id.value, row.tick, row.target_id.value))
        elif row.choice == "proceeded":
            proceeded += 1

    turn_ops = [
        row
        for row in stock_considerations
        if row.opportunity == "turn_expected"
    ]
    matching = 0
    receipt_keys = {(owner, tick) for owner, tick, _code in turn_receipts}
    for row in turn_ops:
        if (row.owner_id.value, row.tick) in receipt_keys:
            matching += 1

    # Complementary alternating acts: matching nonconflicting report_use /
    # report_rest self-reports on the same proposal across distinct owners.
    report_pairs: dict[str, set[str]] = defaultdict(set)
    for transition in stock_transitions:
        if transition.code not in {"report_use", "report_rest"}:
            continue
        if transition.proposal_id is None or transition.actor_id is None:
            continue
        report_pairs[transition.proposal_id].add(transition.actor_id.value)
    complementary = sum(1 for actors in report_pairs.values() if len(actors) >= 2)

    delivery_keys: set[tuple[str, str]] = set()
    eligible_ops = 0
    for head in stock_proposals:
        recipients = head.eligible_recipient_ids
        if not recipients:
            continue
        for recipient in recipients:
            key = (head.proposal_id, recipient.value)
            if key in delivery_keys:
                continue
            delivery_keys.add(key)
            eligible_ops += 1
    # Deduplicate support deliveries once per (proposal, addressed receiver).
    support_keys: set[tuple[str, str]] = set()
    for transition in stock_transitions:
        if transition.code != "stance" or transition.stance != "support":
            continue
        if transition.proposal_id is None or transition.actor_id is None:
            continue
        key = (transition.proposal_id, transition.actor_id.value)
        if key in delivery_keys:
            support_keys.add(key)
    support_deliveries = len(support_keys)

    return CommonsCooperationSummary(
        stock_id=stock_id,
        supported_arrangements=len(supported),
        opposition_heads=opposition,
        contested_heads=contested,
        monitor_checks=monitor,
        access_claims=claims,
        criticism_delivered=criticism,
        wait_expected_considerations=len(wait_expected),
        voluntary_deferrals=len(deferrals),
        proceeded_under_wait_expected=proceeded,
        turn_opportunities=len(turn_ops),
        turn_matching_receipts=matching,
        complementary_alternating_acts=complementary,
        support_over_eligible_opportunities=_ratio(
            support_deliveries, eligible_ops
        ),
        eligible_proposal_recipient_opportunities=eligible_ops,
        distinct_support_deliveries=support_deliveries,
        reason_codes=tuple(sorted(set(reasons))),
    )


def summarize_welfare(
    owners: Sequence[CommonsGovernanceOwnerDelta],
) -> CommonsWelfareSummary:
    """Terminal living founders and thirst coverage from owner deltas."""
    living = [row for row in owners if row.living]
    observed = [row for row in living if row.thirst_tenths is not None]
    reasons: list[str] = []
    if living and len(observed) < len(living):
        reasons.append("thirst_coverage_partial")
    thirst_values = [
        row.thirst_tenths for row in observed if row.thirst_tenths is not None
    ]
    total = sum(thirst_values) if thirst_values else None
    mean = _mean(thirst_values) if thirst_values else None
    return CommonsWelfareSummary(
        terminal_living_founders=len(living),
        thirst_observation_coverage=len(observed),
        thirst_sum_tenths=total,
        thirst_mean_tenths=mean,
        reason_codes=tuple(sorted(set(reasons))),
    )


def build_commons_governance_report(
    *,
    run_id: str,
    stock_ids: Sequence[EntityId],
    histories: Mapping[EntityId, OverexploitationHistory],
    boundaries: Sequence[CommonsGovernanceBoundaryExport],
    founder_ids: Sequence[str],
    social_applicable: bool,
    lane_statuses: Mapping[str, CommonsLaneCoverage] | None = None,
    baseline_tenths_by_stock: Mapping[EntityId, int] | None = None,
    expected_ticks: int | None = None,
    reason_codes: Sequence[str] = (),
) -> CommonsGovernanceReport:
    """Seal one ``commons-governance-report-v1`` from detached evidence."""
    stocks = tuple(sorted(stock_ids, key=lambda item: item.value))
    if len(stocks) != len({item.value for item in stocks}):
        raise ValueError("duplicate_stock_id")
    for stock in stocks:
        if type(stock) is not EntityId:
            raise TypeError("stock_ids entries must be EntityId")
    if type(social_applicable) is not bool:
        raise TypeError("social_applicable must be bool")

    ordered = sorted(boundaries, key=lambda item: item.boundary_tick)
    events: list[WorldEvent] = []
    resolutions: list[CommonsGovernanceResolutionDelta] = []
    transitions: list[CommonsGovernanceTransitionDelta] = []
    considerations: list[CommonsGovernanceConsiderationDelta] = []
    proposals: list[CommonsGovernanceProposalHead] = []
    terminal_owners: dict[str, CommonsGovernanceOwnerDelta] = {}
    for frame in ordered:
        events.extend(frame.events)
        resolutions.extend(frame.resolutions)
        for owner in frame.owners:
            transitions.extend(owner.transitions)
            considerations.extend(owner.considerations)
            proposals.extend(owner.proposals)
            terminal_owners[owner.owner_id.value] = owner

    denial_events: list[tuple[EntityId, int, str, int]] = []
    for row in resolutions:
        if row.command_kind != "drink" or row.source_id is None:
            continue
        if row.status == "applied":
            continue
        if row.reason not in {"structural_rejection", "occurrence"}:
            continue
        # Explicit resource_depleted is encoded as structural_rejection; callers
        # that know the stock tenths at denial attach them via history end stock.
        stock_tenths = 0
        history = histories.get(row.source_id)
        if history is not None:
            for hist_row in history.rows:
                if hist_row.tick == row.tick:
                    stock_tenths = hist_row.post_stock_tenths
                    break
        if row.reason == "structural_rejection":
            denial_events.append(
                (row.source_id, row.tick, "resource_depleted", stock_tenths)
            )

    sustainability: list[CommonsSustainabilitySummary] = []
    joint_use: list[CommonsJointUseSummary] = []
    cooperation: list[CommonsCooperationSummary] = []
    for stock in stocks:
        history = histories.get(stock)
        if history is None:
            history = OverexploitationHistory(
                run_id=RunId(run_id),
                world_id=WorldId("world-scope-unverified"),
                resource_id=stock,
                start_tick=0,
                end_tick=max(0, expected_ticks or 0),
                coverage=HistoryCoverage.UNAVAILABLE,
                covered_through_tick=None,
                stop_code=HistoryStopCode.SCOPE_UNVERIFIED,
                rows=(),
            )
        baseline = None
        if baseline_tenths_by_stock is not None:
            baseline = baseline_tenths_by_stock.get(stock)
        sustainability.append(
            summarize_sustainability(
                history,
                baseline_tenths=baseline,
                denial_events=denial_events,
            )
        )
        receipt_total = sum(row.withdrawal_tenths for row in history.rows)
        joint_use.append(
            summarize_joint_use(
                stock_id=stock,
                founder_ids=founder_ids,
                events=events,
                resolutions=resolutions,
                receipt_withdrawal_tenths=receipt_total,
            )
        )
        if social_applicable:
            cooperation.append(
                summarize_cooperation(
                    stock_id=stock,
                    transitions=transitions,
                    considerations=considerations,
                    proposals=proposals,
                )
            )
        else:
            cooperation.append(
                CommonsCooperationSummary(
                    stock_id=stock,
                    supported_arrangements=0,
                    opposition_heads=0,
                    contested_heads=0,
                    monitor_checks=0,
                    access_claims=0,
                    criticism_delivered=0,
                    wait_expected_considerations=0,
                    voluntary_deferrals=0,
                    proceeded_under_wait_expected=0,
                    turn_opportunities=0,
                    turn_matching_receipts=0,
                    complementary_alternating_acts=0,
                    support_over_eligible_opportunities=None,
                    eligible_proposal_recipient_opportunities=0,
                    distinct_support_deliveries=0,
                    reason_codes=("social_inapplicable",),
                )
            )

    welfare = summarize_welfare(tuple(terminal_owners.values()))
    usable_ticks = len(
        {
            frame.boundary_tick
            for frame in ordered
            if frame.boundary_tick > 0
        }
    )
    expected = (
        expected_ticks
        if expected_ticks is not None
        else usable_ticks
    )
    if lane_statuses is not None:
        lanes = tuple(
            lane_statuses[key]
            for key in sorted(lane_statuses)
        )
    else:
        objective_status = CommonsLaneStatus.COMPLETE
        if usable_ticks == 0 and expected > 0:
            objective_status = CommonsLaneStatus.UNAVAILABLE
        elif usable_ticks < expected:
            objective_status = CommonsLaneStatus.PARTIAL
        social_status = (
            CommonsLaneStatus.INAPPLICABLE
            if not social_applicable
            else objective_status
        )
        lanes = (
            CommonsLaneCoverage(
                lane="objective_sustainability",
                status=objective_status,
                expected=expected,
                usable=usable_ticks,
            ),
            CommonsLaneCoverage(
                lane="objective_joint_use",
                status=objective_status,
                expected=expected,
                usable=usable_ticks,
            ),
            CommonsLaneCoverage(
                lane="subjective_cooperation",
                status=social_status,
                expected=0 if not social_applicable else expected,
                usable=0 if not social_applicable else usable_ticks,
                reason_codes=(
                    ("social_inapplicable",)
                    if not social_applicable
                    else ()
                ),
            ),
            CommonsLaneCoverage(
                lane="welfare_thirst",
                status=objective_status,
                expected=len(founder_ids),
                usable=welfare.thirst_observation_coverage,
                reason_codes=welfare.reason_codes,
            ),
        )

    report = CommonsGovernanceReport(
        schema_version=COMMONS_GOVERNANCE_REPORT_VERSION,
        run_id=run_id,
        stock_ids=stocks,
        lanes=lanes,
        sustainability=tuple(sustainability),
        joint_use=tuple(joint_use),
        cooperation=tuple(cooperation),
        welfare=welfare,
        social_applicable=social_applicable,
        reason_codes=tuple(sorted(set(reason_codes))),
    )
    _LOG.debug(
        "commons_governance_report_built run_id=%s stocks=%s boundaries=%s",
        run_id,
        len(stocks),
        len(ordered),
    )
    return report
