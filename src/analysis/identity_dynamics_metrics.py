"""Analysis-only identity dynamics from harvested belief heads.

Live cognition never reads this report. Documents store counts and a
quantized divergence, never claim text.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
)
from analysis.numerical import library_versions, quantize_float
from analysis.specifications import MetricFamilyId, metric_specification
from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "IDENTITY_DYNAMICS_METRIC_VERSION",
    "IdentityAuditReport",
    "IdentityDissonanceInput",
    "IdentityHeadInput",
    "IdentityOwnerAudit",
    "build_identity_audit",
    "compute_identity_dynamics",
]

IDENTITY_DYNAMICS_METRIC_VERSION: Final[str] = "identity_dynamics@1"
_LOG: Final[logging.Logger] = logging.getLogger("analysis.identity_dynamics_metrics")
_ASPECTS: Final[tuple[str, ...]] = (
    "ability",
    "weakness",
    "recurring_behavior",
    "inferred_value",
    "social_role",
    "relationship",
    "commitment",
    "perceived_status",
    "reliability",
    "risk_tolerance",
    "competence",
)
_PROVENANCE: Final[frozenset[str]] = frozenset(
    {
        "observed_outcome",
        "own_choice",
        "social_feedback",
        "relationship_evidence",
        "goal_outcome",
    }
)
_BANDS: Final[frozenset[str]] = frozenset({"low", "mid", "high"})
_CONFLICTS: Final[tuple[str, ...]] = (
    "commitment_command",
    "inferred_value_command",
    "risk_above_tolerance",
)
_VALUE_KEYS: Final[tuple[str, ...]] = (
    *(f"aspect_{aspect}" for aspect in _ASPECTS),
    "stability_low",
    "stability_mid",
    "stability_high",
    "dissonance_commitment_command",
    "dissonance_inferred_value_command",
    "dissonance_risk_above_tolerance",
    "owner_divergence",
)


def _reason(field: str, code: str) -> ValueError:
    return ValueError(f"{field}: {code}")


@dataclass(frozen=True, slots=True)
class IdentityHeadInput:
    """One harvested belief head. The predicate is not stored on the audit."""

    owner_id: str
    predicate: str
    bool_value: bool
    stability_band: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "owner_id",
            require_stable_id("IdentityHeadInput.owner_id", self.owner_id),
        )
        if type(self.predicate) is not str or not self.predicate:
            raise TypeError("IdentityHeadInput.predicate: invalid_type")
        if type(self.bool_value) is not bool:
            raise TypeError("IdentityHeadInput.bool_value: invalid_type")
        if self.stability_band not in _BANDS:
            raise _reason("IdentityHeadInput.stability_band", "unknown_band")


@dataclass(frozen=True, slots=True)
class IdentityDissonanceInput:
    """Closed conflict-code count for one owner. No claim text."""

    owner_id: str
    conflict_code: str
    count: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "owner_id",
            require_stable_id("IdentityDissonanceInput.owner_id", self.owner_id),
        )
        if self.conflict_code not in _CONFLICTS:
            raise _reason("IdentityDissonanceInput.conflict_code", "unknown_conflict")
        object.__setattr__(
            self,
            "count",
            require_exact_nonneg_int("IdentityDissonanceInput.count", self.count),
        )


@dataclass(frozen=True, slots=True)
class IdentityOwnerAudit:
    """Counts for one owner. Aspect codes only."""

    owner_id: str
    aspect_counts: tuple[tuple[str, int], ...]
    stability_low: int = 0
    stability_mid: int = 0
    stability_high: int = 0
    dissonance_counts: tuple[tuple[str, int], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "owner_id",
            require_stable_id("IdentityOwnerAudit.owner_id", self.owner_id),
        )
        object.__setattr__(
            self,
            "aspect_counts",
            _count_pairs("aspect_counts", self.aspect_counts, _ASPECTS),
        )
        object.__setattr__(
            self,
            "dissonance_counts",
            _count_pairs("dissonance_counts", self.dissonance_counts, _CONFLICTS),
        )
        for name in ("stability_low", "stability_mid", "stability_high"):
            object.__setattr__(
                self,
                name,
                require_exact_nonneg_int(
                    f"IdentityOwnerAudit.{name}", getattr(self, name)
                ),
            )


@dataclass(frozen=True, slots=True)
class IdentityAuditReport:
    """Run-level identity audit. Empty owners are not a self-model."""

    run_id: str
    owners: tuple[IdentityOwnerAudit, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "run_id", require_stable_id("IdentityAuditReport.run_id", self.run_id)
        )
        if isinstance(self.owners, (set, frozenset, Mapping)):
            raise TypeError("IdentityAuditReport.owners: not_ordered")
        if isinstance(self.owners, (str, bytes)) or not isinstance(
            self.owners, Sequence
        ):
            raise TypeError("IdentityAuditReport.owners: not_ordered")
        owners = tuple(self.owners)
        seen: set[str] = set()
        for owner in owners:
            if type(owner) is not IdentityOwnerAudit:
                raise TypeError("IdentityAuditReport.owners: invalid_type")
            if owner.owner_id in seen:
                raise _reason("IdentityAuditReport.owners", "duplicate_owner")
            seen.add(owner.owner_id)
        object.__setattr__(
            self,
            "owners",
            tuple(sorted(owners, key=lambda item: item.owner_id)),
        )


def build_identity_audit(
    *,
    run_id: str,
    heads: Sequence[IdentityHeadInput],
    dissonance: Sequence[IdentityDissonanceInput] = (),
) -> IdentityAuditReport | None:
    """Map identity-shaped ``BOOL`` ``true`` heads into counts. Others are ignored."""
    if isinstance(heads, (set, frozenset, Mapping)) or not isinstance(heads, Sequence):
        raise TypeError("build_identity_audit.heads: not_ordered")
    if isinstance(dissonance, (set, frozenset, Mapping)) or not isinstance(
        dissonance, Sequence
    ):
        raise TypeError("build_identity_audit.dissonance: not_ordered")
    grouped: dict[str, list[IdentityHeadInput]] = {}
    for head in heads:
        if type(head) is not IdentityHeadInput:
            raise TypeError("build_identity_audit.heads: invalid_type")
        if not head.predicate.startswith("identity.") or head.bool_value is not True:
            continue
        _parse_identity_predicate(head.predicate)
        grouped.setdefault(head.owner_id, []).append(head)
    if not grouped:
        return None
    notices: dict[str, dict[str, int]] = {}
    for item in dissonance:
        if type(item) is not IdentityDissonanceInput:
            raise TypeError("build_identity_audit.dissonance: invalid_type")
        bucket = notices.setdefault(item.owner_id, {})
        bucket[item.conflict_code] = bucket.get(item.conflict_code, 0) + item.count
    owners: list[IdentityOwnerAudit] = []
    for owner_id in sorted(grouped):
        aspects = {aspect: 0 for aspect in _ASPECTS}
        bands = {"low": 0, "mid": 0, "high": 0}
        for head in grouped[owner_id]:
            aspect, _provenance, _token = _parse_identity_predicate(head.predicate)
            aspects[aspect] += 1
            bands[head.stability_band] += 1
        owners.append(
            IdentityOwnerAudit(
                owner_id=owner_id,
                aspect_counts=tuple(aspects.items()),
                stability_low=bands["low"],
                stability_mid=bands["mid"],
                stability_high=bands["high"],
                dissonance_counts=tuple(notices.get(owner_id, {}).items()),
            )
        )
    return IdentityAuditReport(run_id=run_id, owners=tuple(owners))


def compute_identity_dynamics(
    report: IdentityAuditReport | None,
    *,
    input_revision: str,
    run_id: str | None = None,
) -> MetricDocument:
    """Same audit always yields the same document. A missing audit is absent."""
    if report is not None and type(report) is not IdentityAuditReport:
        raise TypeError("compute_identity_dynamics: invalid_report")
    revision = require_stable_id("input_revision", input_revision)
    spec = metric_specification(MetricFamilyId.IDENTITY_DYNAMICS)
    document_run = report.run_id if report is not None else run_id
    if document_run is None:
        raise _reason("compute_identity_dynamics.run_id", "required")
    document_run = require_stable_id("compute_identity_dynamics.run_id", document_run)
    owners = () if report is None else report.owners
    present = bool(owners)
    _LOG.debug(
        "identity_dynamics_mapped schema_version=%s owner_count=%s family=%s",
        METRIC_DOCUMENT_SCHEMA_VERSION,
        len(owners),
        "present" if present else "absent",
    )
    if not present:
        return MetricDocument(
            schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
            metric_family=spec.family_id.value,
            algorithm_version=spec.algorithm_version,
            library_versions=library_versions(),
            run_id=document_run,
            input_revision=revision,
            evidence_stages=frozenset(spec.evidence_inputs),
            population=spec.population,
            denominator=spec.denominator,
            coverage=None,
            availability=MetricAvailability.ABSENT,
            values={},
            provenance=MetricProvenance(
                source_kind="identity_dynamics",
                source_ids=(),
                notes_code="no_identity_heads",
            ),
        )
    totals = {key: 0.0 for key in _VALUE_KEYS}
    for owner in owners:
        for aspect, count in owner.aspect_counts:
            totals[f"aspect_{aspect}"] += count
        totals["stability_low"] += owner.stability_low
        totals["stability_mid"] += owner.stability_mid
        totals["stability_high"] += owner.stability_high
        for code, count in owner.dissonance_counts:
            totals[f"dissonance_{code}"] += count
    totals["owner_divergence"] = _owner_divergence(owners)
    values = {key: quantize_float(totals[key]) for key in _VALUE_KEYS}
    return MetricDocument(
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        metric_family=spec.family_id.value,
        algorithm_version=spec.algorithm_version,
        library_versions=library_versions(),
        run_id=document_run,
        input_revision=revision,
        evidence_stages=frozenset(spec.evidence_inputs),
        population=spec.population,
        denominator=spec.denominator,
        coverage=MetricCoverage(observed=len(owners), expected=len(owners)),
        availability=MetricAvailability.PRESENT,
        values=values,
        provenance=MetricProvenance(
            source_kind="identity_dynamics",
            source_ids=(document_run,),
            notes_code="ok",
        ),
    )


def _parse_identity_predicate(predicate: str) -> tuple[str, str, str]:
    parts = predicate.split(".")
    if len(parts) != 4 or parts[0] != "identity":
        raise _reason("identity_audit.predicate", "unknown_predicate")
    aspect, provenance, token = parts[1], parts[2], parts[3]
    if aspect not in _ASPECTS:
        raise _reason("identity_audit.predicate", "unknown_aspect")
    if provenance not in _PROVENANCE:
        raise _reason("identity_audit.predicate", "unknown_provenance")
    if not token:
        raise _reason("identity_audit.predicate", "unknown_predicate")
    return aspect, provenance, token


def _count_pairs(
    name: str, values: object, closed: Sequence[str]
) -> tuple[tuple[str, int], ...]:
    if isinstance(values, (set, frozenset, Mapping)):
        raise TypeError(f"IdentityOwnerAudit.{name}: not_ordered")
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise TypeError(f"IdentityOwnerAudit.{name}: not_ordered")
    allowed = set(closed)
    seen: set[str] = set()
    copied: list[tuple[str, int]] = []
    for item in values:
        if type(item) is not tuple or len(item) != 2:
            raise TypeError(f"IdentityOwnerAudit.{name}: invalid_type")
        code, count = item
        if type(code) is not str or code not in allowed:
            raise _reason(f"IdentityOwnerAudit.{name}", "unknown_code")
        if code in seen:
            raise _reason(f"IdentityOwnerAudit.{name}", "duplicate")
        seen.add(code)
        copied.append((code, require_exact_nonneg_int(name, count)))
    copied.sort(key=lambda pair: pair[0])
    return tuple(copied)


def _owner_divergence(owners: Sequence[IdentityOwnerAudit]) -> float:
    if len(owners) < 2:
        return 0.0
    vectors = [
        {aspect: count for aspect, count in owner.aspect_counts} for owner in owners
    ]
    distances: list[float] = []
    for left_index, left in enumerate(vectors):
        for right in vectors[left_index + 1 :]:
            diff = 0
            total = 0
            for aspect in _ASPECTS:
                left_count = left.get(aspect, 0)
                right_count = right.get(aspect, 0)
                diff += abs(left_count - right_count)
                total += left_count + right_count
            distances.append(0.0 if total == 0 else diff / total)
    return sum(distances) / len(distances)
