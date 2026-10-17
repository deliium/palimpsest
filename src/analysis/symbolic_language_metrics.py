"""Detached, metadata-only symbolic-composition analysis.

Rows carry opaque owner ids, composition ids, and surface digests only. No raw
symbol text, message body, prompt, or narrator output enters a document. These
functions import no persistence, runtime, world private modules, or subjective
ledger types.
"""

from __future__ import annotations

import hashlib
import logging
from collections import Counter, defaultdict
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
    "SYMBOLIC_COMPOSITION_METRIC_VERSION",
    "SYMBOLIC_MESSAGE_FLOW_METRIC_VERSION",
    "SYMBOLIC_SOCIAL_DISTRIBUTION_METRIC_VERSION",
    "SymbolicAnalysisInputs",
    "SymbolicCompositionResult",
    "SymbolicCompositionRow",
    "SymbolicInterpretationResultRow",
    "SymbolicInterpretationRow",
    "SymbolicMessageFlowResult",
    "SymbolicMessageRow",
    "SymbolicSocialDistributionResult",
    "compute_symbolic_composition",
    "compute_symbolic_composition_metric",
    "compute_symbolic_message_flow",
    "compute_symbolic_message_flow_metric",
    "compute_symbolic_social_distribution",
    "compute_symbolic_social_distribution_metric",
    "symbolic_surface_digest",
]

SYMBOLIC_COMPOSITION_METRIC_VERSION: Final[str] = "symbolic_composition@1"
SYMBOLIC_SOCIAL_DISTRIBUTION_METRIC_VERSION: Final[str] = (
    "symbolic_social_distribution@1"
)
SYMBOLIC_MESSAGE_FLOW_METRIC_VERSION: Final[str] = "symbolic_message_flow@1"
_KINDS: Final[frozenset[str]] = frozenset({"attributive", "relational"})
_STATUSES: Final[frozenset[str]] = frozenset({"candidate", "active", "retired"})
_OUTCOMES: Final[frozenset[str]] = frozenset(
    {"parsed", "partial", "unresolved", "ignored"}
)
_BANDS: Final[frozenset[str]] = frozenset({"candidate", "low", "mid", "high"})
_CONFIDENCE_BANDS: Final[frozenset[str]] = frozenset({"low", "mid", "high"})
_LOG: Final[logging.Logger] = logging.getLogger("analysis.symbolic_language")


class SymbolicAnalysisError(ValueError):
    def __init__(self, reason_code: str) -> None:
        self.reason_code = require_stable_id("reason_code", reason_code)
        super().__init__(reason_code)


def symbolic_surface_digest(part: str) -> str:
    """Stable cross-owner surface digest of one symbol token."""
    token = require_stable_id("part", part)
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True, slots=True)
class SymbolicCompositionRow:
    owner_id: str
    composition_id: str
    kind: str
    part_digests: tuple[str, str]
    referent_kind: str | None
    status: str
    strength_band: str
    usage_count: int
    tick_range: tuple[int, int]

    def __post_init__(self) -> None:
        for name in ("owner_id", "composition_id"):
            object.__setattr__(self, name, require_stable_id(name, getattr(self, name)))
        if self.kind not in _KINDS:
            raise SymbolicAnalysisError("invalid_kind")
        parts = tuple(self.part_digests)
        if len(parts) != 2 or any(
            not isinstance(item, str) or not item for item in parts
        ):
            raise SymbolicAnalysisError("invalid_part_digests")
        if parts[0] == parts[1]:
            raise SymbolicAnalysisError("self_reference")
        object.__setattr__(self, "part_digests", (parts[0], parts[1]))
        if self.referent_kind is not None:
            object.__setattr__(
                self,
                "referent_kind",
                require_stable_id("referent_kind", self.referent_kind),
            )
        if self.status not in _STATUSES:
            raise SymbolicAnalysisError("invalid_status")
        if self.strength_band not in _BANDS:
            raise SymbolicAnalysisError("invalid_strength_band")
        object.__setattr__(
            self,
            "usage_count",
            require_exact_nonneg_int("usage_count", self.usage_count),
        )
        first, last = self.tick_range
        object.__setattr__(
            self,
            "tick_range",
            (
                require_exact_nonneg_int("first_tick", first),
                require_exact_nonneg_int("last_tick", last),
            ),
        )
        if last < first:
            raise SymbolicAnalysisError("invalid_tick_range")


@dataclass(frozen=True, slots=True)
class SymbolicMessageRow:
    message_id: str
    speaker_id: str
    listener_id: str | None
    tick: int
    kind: str
    part_digests: tuple[str, str]
    parse_outcome: str
    declared_confidence_band: str | None

    def __post_init__(self) -> None:
        for name in ("message_id", "speaker_id"):
            object.__setattr__(self, name, require_stable_id(name, getattr(self, name)))
        if self.listener_id is not None:
            object.__setattr__(
                self,
                "listener_id",
                require_stable_id("listener_id", self.listener_id),
            )
        object.__setattr__(self, "tick", require_exact_nonneg_int("tick", self.tick))
        if self.kind not in _KINDS:
            raise SymbolicAnalysisError("invalid_kind")
        parts = tuple(self.part_digests)
        if len(parts) != 2:
            raise SymbolicAnalysisError("invalid_part_digests")
        object.__setattr__(self, "part_digests", (parts[0], parts[1]))
        if self.parse_outcome not in _OUTCOMES:
            raise SymbolicAnalysisError("invalid_parse_outcome")
        if self.declared_confidence_band is not None:
            if self.declared_confidence_band not in _CONFIDENCE_BANDS:
                raise SymbolicAnalysisError("invalid_confidence_band")


@dataclass(frozen=True, slots=True)
class SymbolicInterpretationRow:
    owner_id: str
    message_id: str
    outcome: str
    composition_id: str
    tick: int

    def __post_init__(self) -> None:
        for name in ("owner_id", "message_id", "composition_id"):
            object.__setattr__(self, name, require_stable_id(name, getattr(self, name)))
        if self.outcome not in _OUTCOMES:
            raise SymbolicAnalysisError("invalid_parse_outcome")
        object.__setattr__(self, "tick", require_exact_nonneg_int("tick", self.tick))


# Alias used by the plan wording.
SymbolicInterpretationResultRow = SymbolicInterpretationRow


@dataclass(frozen=True, slots=True)
class SymbolicAnalysisInputs:
    compositions: Sequence[SymbolicCompositionRow] = ()
    messages: Sequence[SymbolicMessageRow] = ()
    interpretations: Sequence[SymbolicInterpretationRow] = ()
    communities: Sequence[object] = ()
    expected_owner_count: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "compositions", tuple(self.compositions))
        object.__setattr__(self, "messages", tuple(self.messages))
        object.__setattr__(self, "interpretations", tuple(self.interpretations))
        object.__setattr__(self, "communities", tuple(self.communities))
        object.__setattr__(
            self,
            "expected_owner_count",
            require_exact_nonneg_int("expected_owner_count", self.expected_owner_count),
        )


@dataclass(frozen=True, slots=True)
class SymbolicCompositionResult:
    candidate_count: int
    active_count: int
    retired_count: int
    attributive_count: int
    relational_count: int
    usage_count: int
    interpretation_count: int
    unresolved_interpretation_count: int
    distinct_surface_digest_count: int
    strength_band_counts: tuple[tuple[str, int], ...]
    coverage: MetricCoverage


@dataclass(frozen=True, slots=True)
class SymbolicSocialDistributionResult:
    community_count: int
    surface_digest_count: int
    adopted_digest_count: int
    reinforced_digest_count: int
    borrowed_digest_count: int
    singleton_owner_count: int
    unassigned_owner_count: int
    pairwise_divergence: float | None
    availability: MetricAvailability
    coverage: MetricCoverage


@dataclass(frozen=True, slots=True)
class SymbolicMessageFlowResult:
    composed_message_count: int
    attributive_count: int
    relational_count: int
    parsed_count: int
    partial_count: int
    unresolved_count: int
    ignored_count: int
    speaker_listener_pair_count: int
    unresolved_constituent_count: int
    arity_two_count: int
    confidence_band_counts: tuple[tuple[str, int], ...]
    coverage: MetricCoverage


def _coverage(observed: int, expected: int | None) -> MetricCoverage:
    resolved = 0 if expected is None else max(expected, 0)
    ratio = None if resolved <= 0 else quantize_float(min(1.0, observed / resolved))
    return MetricCoverage(observed=observed, expected=resolved, ratio=ratio)


def _communities(communities: Sequence[object]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for community in communities:
        community_id = getattr(community, "community_id", None)
        for person in getattr(community, "person_ids", ()) or ():
            key = getattr(person, "value", None) or str(person)
            mapping[key] = str(community_id)
    return mapping


def _validate_compositions(
    rows: Sequence[SymbolicCompositionRow],
) -> tuple[SymbolicCompositionRow, ...]:
    values = tuple(rows)
    for row in values:
        if type(row) is not SymbolicCompositionRow:
            raise SymbolicAnalysisError("invalid_composition_row")
    return values


def compute_symbolic_composition(
    rows: Sequence[SymbolicCompositionRow],
    interpretations: Sequence[SymbolicInterpretationRow] = (),
    *,
    expected_owner_count: int | None = None,
) -> SymbolicCompositionResult:
    compositions = _validate_compositions(rows)
    interps = tuple(interpretations)
    for row in interps:
        if type(row) is not SymbolicInterpretationRow:
            raise SymbolicAnalysisError("invalid_interpretation_row")
    statuses = Counter(item.status for item in compositions)
    kinds = Counter(item.kind for item in compositions)
    bands = Counter(item.strength_band for item in compositions)
    usage = sum(item.usage_count for item in compositions)
    unresolved = sum(1 for item in interps if item.outcome == "unresolved")
    digests = {digest for item in compositions for digest in item.part_digests}
    owners = {item.owner_id for item in compositions}
    return SymbolicCompositionResult(
        candidate_count=statuses.get("candidate", 0),
        active_count=statuses.get("active", 0),
        retired_count=statuses.get("retired", 0),
        attributive_count=kinds.get("attributive", 0),
        relational_count=kinds.get("relational", 0),
        usage_count=usage,
        interpretation_count=len(interps),
        unresolved_interpretation_count=unresolved,
        distinct_surface_digest_count=len(digests),
        strength_band_counts=tuple(sorted(bands.items())),
        coverage=_coverage(
            len(owners),
            expected_owner_count if expected_owner_count is not None else None,
        ),
    )


def compute_symbolic_social_distribution(
    inputs: SymbolicAnalysisInputs,
) -> SymbolicSocialDistributionResult:
    if type(inputs) is not SymbolicAnalysisInputs:
        raise SymbolicAnalysisError("invalid_inputs")
    owner_community = _communities(inputs.communities)
    if not owner_community:
        return SymbolicSocialDistributionResult(
            community_count=0,
            surface_digest_count=0,
            adopted_digest_count=0,
            reinforced_digest_count=0,
            borrowed_digest_count=0,
            singleton_owner_count=0,
            unassigned_owner_count=0,
            pairwise_divergence=None,
            availability=MetricAvailability.ABSENT,
            coverage=_coverage(0, None),
        )
    by_community: dict[str, set[str]] = defaultdict(set)
    for row in inputs.compositions:
        community = owner_community.get(row.owner_id)
        if community is not None:
            by_community[community].update(row.part_digests)
    communities = sorted(by_community)
    all_digests: set[str] = (
        set().union(*(by_community.values())) if communities else set()
    )
    borrowed: set[str] = set()
    reinforced: set[str] = set()
    for message in inputs.messages:
        if message.listener_id is None:
            continue
        speaker_community = owner_community.get(message.speaker_id)
        listener_community = owner_community.get(message.listener_id)
        if speaker_community is None or listener_community is None:
            continue
        if speaker_community == listener_community:
            reinforced.update(message.part_digests)
        else:
            borrowed.update(message.part_digests)
    divergence: float | None = None
    if len(communities) >= 2:
        shared = 0.0
        pairs = 0
        for index, left in enumerate(communities):
            left_set = by_community[left]
            for right in communities[index + 1 :]:
                right_set = by_community[right]
                union = left_set | right_set
                overlap = 0.0 if not union else len(left_set & right_set) / len(union)
                shared += 1.0 - overlap
                pairs += 1
        divergence = quantize_float(shared / pairs) if pairs else None
    assigned = set(owner_community)
    observed_owners = {row.owner_id for row in inputs.compositions}
    unassigned = len(observed_owners - assigned)
    singleton = sum(
        1 for community, digests in by_community.items() if len(digests) <= 1
    )
    return SymbolicSocialDistributionResult(
        community_count=len(communities),
        surface_digest_count=len(all_digests),
        adopted_digest_count=len(borrowed),
        reinforced_digest_count=len(reinforced),
        borrowed_digest_count=len(borrowed),
        singleton_owner_count=singleton,
        unassigned_owner_count=unassigned,
        pairwise_divergence=divergence,
        availability=(
            MetricAvailability.PRESENT
            if inputs.compositions
            else MetricAvailability.ABSENT
        ),
        coverage=_coverage(len(observed_owners & assigned), len(observed_owners)),
    )


def compute_symbolic_message_flow(
    messages: Sequence[SymbolicMessageRow],
) -> SymbolicMessageFlowResult:
    rows = tuple(messages)
    for row in rows:
        if type(row) is not SymbolicMessageRow:
            raise SymbolicAnalysisError("invalid_message_row")
    kinds = Counter(item.kind for item in rows)
    outcomes = Counter(item.parse_outcome for item in rows)
    bands = Counter(
        item.declared_confidence_band
        for item in rows
        if item.declared_confidence_band is not None
    )
    pairs = {
        (item.speaker_id, item.listener_id)
        for item in rows
        if item.listener_id is not None
    }
    return SymbolicMessageFlowResult(
        composed_message_count=len(rows),
        attributive_count=kinds.get("attributive", 0),
        relational_count=kinds.get("relational", 0),
        parsed_count=outcomes.get("parsed", 0),
        partial_count=outcomes.get("partial", 0),
        unresolved_count=outcomes.get("unresolved", 0),
        ignored_count=outcomes.get("ignored", 0),
        speaker_listener_pair_count=len(pairs),
        unresolved_constituent_count=outcomes.get("partial", 0)
        + outcomes.get("unresolved", 0),
        arity_two_count=sum(1 for item in rows if len(item.part_digests) == 2),
        confidence_band_counts=tuple(sorted(bands.items())),
        coverage=_coverage(len(pairs), None),
    )


def _document(
    *,
    family: MetricFamilyId,
    values: Mapping[str, object],
    availability: MetricAvailability,
    coverage: MetricCoverage,
    run_id: str,
    input_revision: str,
    source_kind: str,
) -> MetricDocument:
    spec = metric_specification(family)
    return MetricDocument(
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        metric_family=spec.family_id.value,
        algorithm_version=spec.algorithm_version,
        library_versions=library_versions(),
        run_id=require_stable_id("run_id", run_id),
        input_revision=require_stable_id("input_revision", input_revision),
        evidence_stages=frozenset(spec.evidence_inputs),
        population=spec.population,
        denominator=spec.denominator,
        coverage=coverage,
        availability=availability,
        values=dict(values),
        provenance=MetricProvenance(
            source_kind=source_kind,
            source_ids=(),
            notes_code="descriptive_symbolic",
        ),
    )


def compute_symbolic_composition_metric(
    result: SymbolicCompositionResult,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    if type(result) is not SymbolicCompositionResult:
        raise SymbolicAnalysisError("invalid_result")
    availability = (
        MetricAvailability.ABSENT
        if result.candidate_count + result.active_count + result.retired_count == 0
        else MetricAvailability.PRESENT
    )
    values: dict[str, object] = {
        "active_count": result.active_count,
        "attributive_count": result.attributive_count,
        "candidate_count": result.candidate_count,
        "distinct_surface_digest_count": result.distinct_surface_digest_count,
        "interpretation_count": result.interpretation_count,
        "relational_count": result.relational_count,
        "retired_count": result.retired_count,
        "unresolved_interpretation_count": result.unresolved_interpretation_count,
        "usage_count": result.usage_count,
        "composition_count": (
            result.candidate_count + result.active_count + result.retired_count
        ),
    }
    for band, count in result.strength_band_counts:
        values[f"strength_band_{band}_count"] = count
    return _document(
        family=MetricFamilyId.SYMBOLIC_COMPOSITION,
        values=values,
        availability=availability,
        coverage=result.coverage,
        run_id=run_id,
        input_revision=input_revision,
        source_kind="symbolic_composition",
    )


def compute_symbolic_social_distribution_metric(
    result: SymbolicSocialDistributionResult,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    if type(result) is not SymbolicSocialDistributionResult:
        raise SymbolicAnalysisError("invalid_result")
    values: dict[str, object] = {
        "adopted_digest_count": result.adopted_digest_count,
        "borrowed_digest_count": result.borrowed_digest_count,
        "community_count": result.community_count,
        "reinforced_digest_count": result.reinforced_digest_count,
        "singleton_owner_count": result.singleton_owner_count,
        "surface_digest_count": result.surface_digest_count,
        "unassigned_owner_count": result.unassigned_owner_count,
    }
    if result.pairwise_divergence is not None:
        values["pairwise_divergence"] = result.pairwise_divergence
    return _document(
        family=MetricFamilyId.SYMBOLIC_SOCIAL_DISTRIBUTION,
        values=values,
        availability=result.availability,
        coverage=result.coverage,
        run_id=run_id,
        input_revision=input_revision,
        source_kind="symbolic_social_distribution",
    )


def compute_symbolic_message_flow_metric(
    result: SymbolicMessageFlowResult,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    if type(result) is not SymbolicMessageFlowResult:
        raise SymbolicAnalysisError("invalid_result")
    availability = (
        MetricAvailability.ABSENT
        if result.composed_message_count == 0
        else MetricAvailability.PRESENT
    )
    values: dict[str, object] = {
        "arity_two_count": result.arity_two_count,
        "attributive_count": result.attributive_count,
        "composed_message_count": result.composed_message_count,
        "ignored_count": result.ignored_count,
        "parsed_count": result.parsed_count,
        "partial_count": result.partial_count,
        "relational_count": result.relational_count,
        "speaker_listener_pair_count": result.speaker_listener_pair_count,
        "unresolved_constituent_count": result.unresolved_constituent_count,
        "unresolved_count": result.unresolved_count,
    }
    for band, count in result.confidence_band_counts:
        values[f"confidence_band_{band}_count"] = count
    return _document(
        family=MetricFamilyId.SYMBOLIC_MESSAGE_FLOW,
        values=values,
        availability=availability,
        coverage=result.coverage,
        run_id=run_id,
        input_revision=input_revision,
        source_kind="symbolic_message_flow",
    )
