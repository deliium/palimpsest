"""Paired off/on commons-governance report comparison (autonomous lane).

Accepts validated neutral matched reports. Mechanism and autonomous lanes must
not be merged in one call. Complete nulls remain valid; incomplete or mismatched
pairs are excluded with reason codes rather than interpolated.
"""

from __future__ import annotations

import logging
import statistics
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from analysis.commons_governance_metrics import CommonsGovernanceReport
from analysis.numerical import quantize_float
from simulation.commons_governance_evidence import CommonsLaneStatus
from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "COMMONS_GOVERNANCE_COMPARISON_VERSION",
    "CommonsGovernanceArmRecord",
    "CommonsGovernanceComparisonError",
    "CommonsGovernanceComparisonResult",
    "CommonsGovernanceLayoutSummary",
    "CommonsGovernanceMatchIdentity",
    "CommonsGovernanceMetricDelta",
    "CommonsGovernanceSeedBlockSummary",
    "compare_commons_governance_reports",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.commons_governance_comparison"
)

COMMONS_GOVERNANCE_COMPARISON_VERSION: Final[str] = (
    "commons-governance-comparison-v1"
)

_AUTONOMOUS: Final[str] = "autonomous"
_MECHANISM: Final[str] = "mechanism"
_ALLOWED_LANES: Final[frozenset[str]] = frozenset({_AUTONOMOUS, _MECHANISM})
_COMPLETE_STATUSES: Final[frozenset[str]] = frozenset(
    {"complete", "null_complete"}
)
_PAIRABLE_STATUSES: Final[frozenset[str]] = frozenset(
    {"complete", "null_complete", "unavailable"}
)


class CommonsGovernanceComparisonError(ValueError):
    """Stable, payload-free comparison failure code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CommonsGovernanceMatchIdentity:
    """Matched replicate identity excluding tested selector and schema version."""

    layout: str
    numeric_seed: int
    replicate_ordinal: int
    stochastic_identity: str
    declared_horizon: int
    config_fingerprint: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "layout", require_stable_id("layout", self.layout)
        )
        object.__setattr__(
            self,
            "numeric_seed",
            require_exact_nonneg_int("numeric_seed", self.numeric_seed),
        )
        object.__setattr__(
            self,
            "replicate_ordinal",
            require_exact_nonneg_int(
                "replicate_ordinal", self.replicate_ordinal
            ),
        )
        object.__setattr__(
            self,
            "stochastic_identity",
            require_stable_id(
                "stochastic_identity", self.stochastic_identity
            ),
        )
        object.__setattr__(
            self,
            "declared_horizon",
            require_exact_nonneg_int(
                "declared_horizon", self.declared_horizon
            ),
        )
        object.__setattr__(
            self,
            "config_fingerprint",
            require_stable_id(
                "config_fingerprint", self.config_fingerprint
            ),
        )

    @property
    def key(self) -> tuple[object, ...]:
        return (
            self.layout,
            self.numeric_seed,
            self.replicate_ordinal,
            self.stochastic_identity,
            self.declared_horizon,
            self.config_fingerprint,
        )


@dataclass(frozen=True, slots=True)
class CommonsGovernanceArmRecord:
    """One arm contribution for paired comparison."""

    identity: CommonsGovernanceMatchIdentity
    condition_id: str
    role: str
    lane: str
    coverage: str
    report: CommonsGovernanceReport | None = None
    stop_reason: str | None = None

    def __post_init__(self) -> None:
        if type(self.identity) is not CommonsGovernanceMatchIdentity:
            raise TypeError("identity must be CommonsGovernanceMatchIdentity")
        object.__setattr__(
            self,
            "condition_id",
            require_stable_id("condition_id", self.condition_id),
        )
        object.__setattr__(self, "role", require_stable_id("role", self.role))
        if self.role not in {"control", "treatment"}:
            raise CommonsGovernanceComparisonError("arm_role_invalid")
        object.__setattr__(self, "lane", require_stable_id("lane", self.lane))
        if self.lane not in _ALLOWED_LANES:
            raise CommonsGovernanceComparisonError("lane_unknown")
        object.__setattr__(
            self, "coverage", require_stable_id("coverage", self.coverage)
        )
        if self.report is not None and type(self.report) is not CommonsGovernanceReport:
            raise TypeError("report must be CommonsGovernanceReport or None")
        if self.stop_reason is not None:
            object.__setattr__(
                self,
                "stop_reason",
                require_stable_id("stop_reason", self.stop_reason),
            )


@dataclass(frozen=True, slots=True)
class CommonsGovernanceMetricDelta:
    """One treatment-minus-control descriptive delta."""

    stock_id: str
    family: str
    metric: str
    control: float | None
    treatment: float | None
    difference: float | None

    def __post_init__(self) -> None:
        for name in ("stock_id", "family", "metric"):
            object.__setattr__(
                self, name, require_stable_id(name, getattr(self, name))
            )
        for name in ("control", "treatment", "difference"):
            value = getattr(self, name)
            if value is not None and type(value) not in (int, float):
                raise TypeError(f"{name} must be float or None")
            if value is not None:
                object.__setattr__(self, name, float(value))


@dataclass(frozen=True, slots=True)
class CommonsGovernanceSeedBlockSummary:
    """Within-seed average of paired differences; replicas are not blocks."""

    layout: str
    numeric_seed: int
    paired_count: int
    mean_deltas: tuple[CommonsGovernanceMetricDelta, ...]
    membership: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "layout", require_stable_id("layout", self.layout)
        )
        object.__setattr__(
            self,
            "numeric_seed",
            require_exact_nonneg_int("numeric_seed", self.numeric_seed),
        )
        object.__setattr__(
            self,
            "paired_count",
            require_exact_nonneg_int("paired_count", self.paired_count),
        )
        object.__setattr__(self, "mean_deltas", tuple(self.mean_deltas))
        object.__setattr__(self, "membership", tuple(self.membership))


@dataclass(frozen=True, slots=True)
class CommonsGovernanceLayoutSummary:
    """Per-layout descriptive rollup across seed blocks."""

    layout: str
    seed_block_count: int
    paired_slot_count: int
    excluded_count: int
    median_deltas: tuple[CommonsGovernanceMetricDelta, ...]
    range_deltas: tuple[tuple[str, str, float | None, float | None], ...]
    provenance: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "layout", require_stable_id("layout", self.layout)
        )
        for name in ("seed_block_count", "paired_slot_count", "excluded_count"):
            object.__setattr__(
                self,
                name,
                require_exact_nonneg_int(name, getattr(self, name)),
            )
        object.__setattr__(self, "median_deltas", tuple(self.median_deltas))
        object.__setattr__(self, "range_deltas", tuple(self.range_deltas))
        object.__setattr__(self, "provenance", tuple(self.provenance))


@dataclass(frozen=True, slots=True)
class CommonsGovernanceComparisonResult:
    """Detached comparison output; mechanism and autonomous stay separate."""

    schema_version: str
    lane: str
    layout_summaries: tuple[CommonsGovernanceLayoutSummary, ...]
    seed_blocks: tuple[CommonsGovernanceSeedBlockSummary, ...]
    excluded: tuple[tuple[str, str], ...]
    provenance: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.schema_version != COMMONS_GOVERNANCE_COMPARISON_VERSION:
            raise ValueError("commons_governance_comparison_schema_invalid")
        object.__setattr__(self, "lane", require_stable_id("lane", self.lane))
        object.__setattr__(
            self, "layout_summaries", tuple(self.layout_summaries)
        )
        object.__setattr__(self, "seed_blocks", tuple(self.seed_blocks))
        object.__setattr__(self, "excluded", tuple(self.excluded))
        object.__setattr__(self, "provenance", tuple(self.provenance))


def _as_float(value: object) -> float | None:
    if value is None:
        return None
    if type(value) is bool:
        return None
    if type(value) is int:
        return float(value)
    if type(value) is float:
        return value
    return None


def _metric_rows(
    report: CommonsGovernanceReport,
) -> dict[tuple[str, str, str], float | None]:
    rows: dict[tuple[str, str, str], float | None] = {}
    for sustainability in report.sustainability:
        sid = sustainability.stock_id.value
        rows[(sid, "sustainability", "end_stock_tenths")] = _as_float(
            sustainability.end_stock_tenths
        )
        rows[(sid, "sustainability", "withdrawal_tenths_total")] = _as_float(
            sustainability.withdrawal_tenths_total
        )
        rows[(sid, "sustainability", "renewal_over_withdrawal")] = _as_float(
            sustainability.renewal_over_withdrawal
        )
        rows[(sid, "sustainability", "mean_end_stock_over_baseline")] = (
            _as_float(sustainability.mean_end_stock_over_baseline)
        )
    for joint_use in report.joint_use:
        sid = joint_use.stock_id.value
        rows[(sid, "joint_use", "attributed_drunk_count")] = _as_float(
            joint_use.attributed_drunk_count
        )
        rows[(sid, "joint_use", "multi_user_ticks")] = _as_float(
            joint_use.multi_user_ticks
        )
    for cooperation in report.cooperation:
        sid = cooperation.stock_id.value
        rows[(sid, "cooperation", "supported_arrangements")] = _as_float(
            cooperation.supported_arrangements
        )
        rows[(sid, "cooperation", "voluntary_deferrals")] = _as_float(
            cooperation.voluntary_deferrals
        )
        rows[(sid, "cooperation", "criticism_delivered")] = _as_float(
            cooperation.criticism_delivered
        )
        rows[(sid, "cooperation", "access_claims")] = _as_float(
            cooperation.access_claims
        )
    welfare = report.welfare
    rows[("*", "welfare", "terminal_living_founders")] = _as_float(
        welfare.terminal_living_founders
    )
    rows[("*", "welfare", "thirst_mean_tenths")] = _as_float(
        welfare.thirst_mean_tenths
    )
    return rows


def _pair_deltas(
    control: CommonsGovernanceReport,
    treatment: CommonsGovernanceReport,
) -> tuple[CommonsGovernanceMetricDelta, ...]:
    left = _metric_rows(control)
    right = _metric_rows(treatment)
    keys = sorted(set(left) | set(right))
    deltas: list[CommonsGovernanceMetricDelta] = []
    for stock_id, family, metric in keys:
        control_value = left.get((stock_id, family, metric))
        treatment_value = right.get((stock_id, family, metric))
        difference = None
        if control_value is not None and treatment_value is not None:
            difference = quantize_float(treatment_value - control_value)
        deltas.append(
            CommonsGovernanceMetricDelta(
                stock_id=stock_id,
                family=family,
                metric=metric,
                control=control_value,
                treatment=treatment_value,
                difference=difference,
            )
        )
    return tuple(deltas)


def _identity_label(identity: CommonsGovernanceMatchIdentity) -> str:
    return (
        f"{identity.layout}:{identity.numeric_seed}:"
        f"{identity.replicate_ordinal}:{identity.config_fingerprint[:12]}"
    )


def _role_from_condition(condition_id: str) -> str | None:
    if condition_id.endswith("-off"):
        return "control"
    if condition_id.endswith("-on"):
        return "treatment"
    return None


def _average_deltas(
    slots: Sequence[tuple[CommonsGovernanceMetricDelta, ...]],
) -> tuple[CommonsGovernanceMetricDelta, ...]:
    if not slots:
        return ()
    buckets: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    meta: dict[tuple[str, str, str], tuple[float | None, float | None]] = {}
    for deltas in slots:
        for row in deltas:
            key = (row.stock_id, row.family, row.metric)
            meta.setdefault(key, (row.control, row.treatment))
            if row.difference is not None:
                buckets[key].append(row.difference)
    averaged: list[CommonsGovernanceMetricDelta] = []
    for key in sorted(buckets):
        values = buckets[key]
        control, treatment = meta[key]
        mean = quantize_float(statistics.fmean(values)) if values else None
        averaged.append(
            CommonsGovernanceMetricDelta(
                stock_id=key[0],
                family=key[1],
                metric=key[2],
                control=control,
                treatment=treatment,
                difference=mean,
            )
        )
    # Preserve keys that never had a numeric difference.
    for deltas in slots:
        for row in deltas:
            key = (row.stock_id, row.family, row.metric)
            if key in buckets:
                continue
            averaged.append(
                CommonsGovernanceMetricDelta(
                    stock_id=row.stock_id,
                    family=row.family,
                    metric=row.metric,
                    control=row.control,
                    treatment=row.treatment,
                    difference=None,
                )
            )
            buckets[key] = []
    averaged.sort(key=lambda item: (item.stock_id, item.family, item.metric))
    return tuple(averaged)


def _median_and_range(
    blocks: Sequence[CommonsGovernanceSeedBlockSummary],
) -> tuple[
    tuple[CommonsGovernanceMetricDelta, ...],
    tuple[tuple[str, str, float | None, float | None], ...],
]:
    series: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    for block in blocks:
        for row in block.mean_deltas:
            if row.difference is None:
                continue
            series[(row.stock_id, row.family, row.metric)].append(
                row.difference
            )
    medians: list[CommonsGovernanceMetricDelta] = []
    ranges: list[tuple[str, str, float | None, float | None]] = []
    for key in sorted(series):
        values = series[key]
        medians.append(
            CommonsGovernanceMetricDelta(
                stock_id=key[0],
                family=key[1],
                metric=key[2],
                control=None,
                treatment=None,
                difference=quantize_float(statistics.median(values)),
            )
        )
        ranges.append(
            (
                f"{key[0]}|{key[1]}|{key[2]}",
                key[1],
                quantize_float(min(values)),
                quantize_float(max(values)),
            )
        )
    return tuple(medians), tuple(ranges)


def compare_commons_governance_reports(
    arms: Sequence[CommonsGovernanceArmRecord],
) -> CommonsGovernanceComparisonResult:
    """Compare validated matched off/on reports within one capture lane."""

    if isinstance(arms, (str, bytes, Mapping)) or not isinstance(arms, Sequence):
        raise CommonsGovernanceComparisonError("arms_invalid")
    records = tuple(arms)
    if not records:
        raise CommonsGovernanceComparisonError("arms_empty")
    for row in records:
        if type(row) is not CommonsGovernanceArmRecord:
            raise CommonsGovernanceComparisonError("arm_type_invalid")

    lanes = {row.lane for row in records}
    if len(lanes) != 1:
        raise CommonsGovernanceComparisonError("lane_mixed")
    lane = next(iter(lanes))
    if lane == _MECHANISM:
        raise CommonsGovernanceComparisonError("mechanism_lane_not_compared")

    excluded: list[tuple[str, str]] = []
    by_key: dict[tuple[object, ...], dict[str, list[CommonsGovernanceArmRecord]]] = (
        defaultdict(lambda: defaultdict(list))
    )
    for row in records:
        expected_role = _role_from_condition(row.condition_id)
        if expected_role is None:
            excluded.append((_identity_label(row.identity), "condition_unpaired"))
            continue
        if expected_role != row.role:
            raise CommonsGovernanceComparisonError("arm_role_mismatch")
        by_key[row.identity.key][row.role].append(row)

    paired_slots: list[
        tuple[CommonsGovernanceMatchIdentity, tuple[CommonsGovernanceMetricDelta, ...]]
    ] = []
    unavailable_retained = 0
    for key, roles in sorted(by_key.items(), key=lambda item: repr(item[0])):
        control_rows = roles.get("control", [])
        treatment_rows = roles.get("treatment", [])
        label = (
            f"{key[0]}:{key[1]}:{key[2]}"
            if key
            else "unknown"
        )
        if len(control_rows) > 1 or len(treatment_rows) > 1:
            excluded.append((label, "duplicate_arm_identity"))
            continue
        if not control_rows or not treatment_rows:
            excluded.append((label, "missing_arm"))
            continue
        control = control_rows[0]
        treatment = treatment_rows[0]
        if control.identity != treatment.identity:
            excluded.append((label, "identity_mismatch"))
            continue
        if control.identity.layout != treatment.identity.layout:
            raise CommonsGovernanceComparisonError("cross_layout_pair")
        if (
            control.identity.config_fingerprint
            != treatment.identity.config_fingerprint
        ):
            raise CommonsGovernanceComparisonError("selector_fingerprint_mismatch")
        if control.coverage not in _PAIRABLE_STATUSES:
            excluded.append((label, f"control_{control.coverage}"))
            continue
        if treatment.coverage not in _PAIRABLE_STATUSES:
            excluded.append((label, f"treatment_{treatment.coverage}"))
            continue
        if (
            control.coverage == "unavailable"
            or treatment.coverage == "unavailable"
            or control.report is None
            or treatment.report is None
        ):
            unavailable_retained += 1
            excluded.append((label, "unavailable_retained"))
            continue
        if control.coverage not in _COMPLETE_STATUSES:
            excluded.append((label, f"control_{control.coverage}"))
            continue
        if treatment.coverage not in _COMPLETE_STATUSES:
            excluded.append((label, f"treatment_{treatment.coverage}"))
            continue
        # Common complete lanes only; keep complete nulls.
        control_lanes = {
            item.lane: item.status for item in control.report.lanes
        }
        treatment_lanes = {
            item.lane: item.status for item in treatment.report.lanes
        }
        shared = set(control_lanes) & set(treatment_lanes)
        usable = False
        for lane_name in shared:
            left = control_lanes[lane_name]
            right = treatment_lanes[lane_name]
            if (
                left is CommonsLaneStatus.COMPLETE
                and right is CommonsLaneStatus.COMPLETE
            ):
                usable = True
                break
            if (
                left is CommonsLaneStatus.INAPPLICABLE
                and right is CommonsLaneStatus.INAPPLICABLE
            ):
                continue
        if not usable and control.coverage != "null_complete":
            # Still allow complete empty social/objective zeros via null_complete.
            if not (
                control.coverage == "complete"
                and treatment.coverage == "complete"
            ):
                excluded.append((label, "no_common_complete_lane"))
                continue
        deltas = _pair_deltas(control.report, treatment.report)
        paired_slots.append((control.identity, deltas))

    _Slot = tuple[
        CommonsGovernanceMatchIdentity,
        tuple[CommonsGovernanceMetricDelta, ...],
    ]
    blocks_map: dict[tuple[str, int], list[_Slot]] = defaultdict(list)
    for identity, deltas in paired_slots:
        blocks_map[(identity.layout, identity.numeric_seed)].append(
            (identity, deltas)
        )

    seed_blocks: list[CommonsGovernanceSeedBlockSummary] = []
    for (layout, seed), members in sorted(blocks_map.items()):
        averaged = _average_deltas([deltas for _identity, deltas in members])
        seed_blocks.append(
            CommonsGovernanceSeedBlockSummary(
                layout=layout,
                numeric_seed=seed,
                paired_count=len(members),
                mean_deltas=averaged,
                membership=tuple(
                    sorted(_identity_label(identity) for identity, _ in members)
                ),
            )
        )

    layout_summaries: list[CommonsGovernanceLayoutSummary] = []
    for layout in sorted({block.layout for block in seed_blocks}):
        layout_blocks = [block for block in seed_blocks if block.layout == layout]
        medians, ranges = _median_and_range(layout_blocks)
        layout_excluded = sum(
            1 for label, _reason in excluded if label.startswith(f"{layout}:")
        )
        layout_summaries.append(
            CommonsGovernanceLayoutSummary(
                layout=layout,
                seed_block_count=len(layout_blocks),
                paired_slot_count=sum(block.paired_count for block in layout_blocks),
                excluded_count=layout_excluded,
                median_deltas=medians,
                range_deltas=ranges,
                provenance=(
                    COMMONS_GOVERNANCE_COMPARISON_VERSION,
                    "paired_treatment_minus_control",
                    "seed_block_inferential_unit",
                    f"n={len(layout_blocks)}",
                ),
            )
        )

    provenance = (
        COMMONS_GOVERNANCE_COMPARISON_VERSION,
        f"lane={lane}",
        f"paired={len(paired_slots)}",
        f"excluded={len(excluded)}",
        f"unavailable_retained={unavailable_retained}",
        "no_adoption_threshold_gate",
    )
    _LOG.info(
        "commons_governance_compared lane=%s paired=%s excluded=%s",
        lane,
        len(paired_slots),
        len(excluded),
    )
    return CommonsGovernanceComparisonResult(
        schema_version=COMMONS_GOVERNANCE_COMPARISON_VERSION,
        lane=lane,
        layout_summaries=tuple(layout_summaries),
        seed_blocks=tuple(seed_blocks),
        excluded=tuple(excluded),
        provenance=provenance,
    )
