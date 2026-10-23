"""Validated analysis-side cultural evolution evidence.

The module owns conservative, detached contracts for post-run measurement. It
never imports live world state, cognition loops, or the simulation runner.
Values are immutable; ``repr`` exposes only safe identities, counts, and status.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Final

from analysis.models import MetricAvailability
from simulation.cultural_evidence import (
    CULTURAL_EVIDENCE_CHANNEL_CULTURAL_FEATURES,
    CULTURAL_EVIDENCE_CHANNEL_NARRATIVES,
    CULTURAL_EVIDENCE_CHANNEL_PRACTICAL_KNOWLEDGE,
    CULTURAL_EVIDENCE_CHANNEL_TERMINOLOGY,
    CULTURAL_EVIDENCE_COVERAGE_DISABLED,
    CULTURAL_EVIDENCE_COVERAGE_MISSING,
    CulturalBoundaryExport,
    CulturalChannelExport,
    CulturalOwnerExport,
)
from world.identifiers import require_exact_nonneg_int, require_stable_id

_LOG: Final[logging.Logger] = logging.getLogger("analysis.cultural_evolution_evidence")

CULTURAL_EVOLUTION_POLICY_VERSION: Final[str] = "cultural-evolution.v1"
CULTURAL_EVOLUTION_BOUNDARY_INTERVAL: Final[int] = 1

CULTURAL_MEASUREMENT_ROW_DOMAIN: Final[str] = "cultural-measurement-row-v1"
CULTURAL_EVIDENCE_POINTER_DOMAIN: Final[str] = "cultural-evidence-pointer-v1"

CULTURAL_FEATURE_DIMENSIONS: Final[tuple[str, ...]] = (
    "feature:practice",
    "feature:narrative_element",
    "feature:term",
    "feature:production_technique",
    "feature:social_expectation",
    "feature:symbolic_association",
)

CULTURAL_DIMENSIONS: Final[tuple[str, ...]] = (
    *CULTURAL_FEATURE_DIMENSIONS,
    "vocabulary",
    "narrative",
    "technology",
)

CULTURAL_DIMENSION_SET: Final[frozenset[str]] = frozenset(CULTURAL_DIMENSIONS)

CULTURAL_REPRESENTATIONS: Final[frozenset[str]] = frozenset(
    {
        "ledger_carriage",
        "label_inventory",
        "narrative_lineage",
        "practical_content_key",
        "practical_variant",
        "transmission_edge",
    }
)

CULTURAL_SCOPES: Final[frozenset[str]] = frozenset(
    {"global", "group", "group_pair", "owner", "edge"}
)

CULTURAL_COVERAGE_CODES: Final[frozenset[str]] = frozenset(
    {"complete", "missing", "disabled"}
)

CULTURAL_POPULATION_BASES: Final[frozenset[str]] = frozenset(
    {
        "eligible_living_owners",
        "carrier_incidences",
        "fixed_baseline_traits",
        "fixed_eligible_pairs",
        "attributable_acquisitions",
        "comparable_single_source_edges",
        "living_holders",
        "archive_records",
        "eligible_owners",
        "eligible_pairs",
    }
)

CULTURAL_DENOMINATOR_CODES: Final[frozenset[str]] = frozenset(
    {
        "eligible_living_owners",
        "carrier_incidences",
        "fixed_baseline_traits",
        "fixed_eligible_pairs",
        "attributable_acquisitions",
        "comparable_single_source_edges",
        "living_holders",
        "archive_records",
        "eligible_owners",
        "eligible_pairs",
    }
)

CULTURAL_UNITS: Final[frozenset[str]] = frozenset(
    {
        "count",
        "proportion",
        "nats",
        "effective_traits",
        "jaccard_distance",
        "ticks",
        "generations",
    }
)

CULTURAL_TRANSMISSION_MODALITIES: Final[frozenset[str]] = frozenset(
    {
        "observation",
        "teaching",
        "communication",
        "artifact",
        "imitation",
        "independent_rediscovery",
    }
)

CULTURAL_ATTRIBUTION_STATUSES: Final[frozenset[str]] = frozenset(
    {
        "resolved",
        "ambiguous_source",
        "unknown_source",
        "independent_rediscovery",
    }
)

CULTURAL_GENERATION_CLASSES: Final[frozenset[str]] = frozenset(
    {
        "horizontal",
        "intergenerational",
        "reverse_intergenerational",
        "unknown",
    }
)

_DIGEST_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")
_CONFLICT_MESSAGE: Final[str] = "cultural_evidence_conflict"


def _fail(field_name: str, code: str) -> ValueError:
    _LOG.error(
        "cultural_evolution_evidence_validation_failed field=%s reason_code=%s",
        field_name,
        code,
    )
    return ValueError(f"{field_name}: {code}")


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _domain_digest(domain: str, payload: object) -> str:
    encoded = _canonical_json(payload).encode("utf-8")
    return hashlib.sha256(domain.encode("utf-8") + b"\x00" + encoded).hexdigest()


def _require_digest(field_name: str, value: object) -> str:
    if not isinstance(value, str) or _DIGEST_PATTERN.fullmatch(value) is None:
        raise _fail(field_name, "invalid_digest")
    return value


def _require_optional_id(field_name: str, value: object) -> str | None:
    if value is None:
        return None
    return require_stable_id(field_name, value)


def _require_finite_optional(field_name: str, value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _fail(field_name, "not_finite")
    number = float(value)
    if not math.isfinite(number):
        raise _fail(field_name, "not_finite")
    return number


def _require_sequence(field_name: str, value: object) -> tuple[object, ...]:
    if isinstance(value, (str, bytes, bytearray, set, frozenset, Mapping)):
        raise _fail(field_name, "invalid_type")
    if not isinstance(value, Sequence):
        raise _fail(field_name, "invalid_type")
    return tuple(value)


def _require_sorted_unique_ids(field_name: str, value: object) -> tuple[str, ...]:
    raw = _require_sequence(field_name, value)
    checked: list[str] = []
    seen: set[str] = set()
    for item in raw:
        token = require_stable_id(field_name, item)
        if token in seen:
            raise _fail(field_name, "duplicate_id")
        seen.add(token)
        checked.append(token)
    checked.sort()
    return tuple(checked)


def _require_closed(field_name: str, value: object, allowed: frozenset[str]) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise _fail(field_name, "unknown_value")
    return value


def _deduplicate[RowT](
    field_name: str,
    rows: Sequence[RowT],
    identity: Callable[[RowT], object],
) -> tuple[RowT, ...]:
    if not callable(identity):
        raise _fail(field_name, "invalid_identity")
    kept: dict[object, RowT] = {}
    for row in rows:
        key = identity(row)
        existing = kept.get(key)
        if existing is None:
            kept[key] = row
            continue
        if existing != row:
            raise ValueError(_CONFLICT_MESSAGE)
    return tuple(kept[key] for key in sorted(kept, key=str))


@dataclass(frozen=True, slots=True)
class CulturalAnalysisWindow:
    """Exact requested boundary window; never rebased onto observed frames."""

    baseline_boundary: int = 0
    end_boundary: int | None = None

    def __post_init__(self) -> None:
        baseline = require_exact_nonneg_int(
            "window.baseline_boundary", self.baseline_boundary
        )
        object.__setattr__(self, "baseline_boundary", baseline)
        if self.end_boundary is not None:
            endpoint = require_exact_nonneg_int(
                "window.end_boundary", self.end_boundary
            )
            if endpoint <= baseline:
                raise _fail("window.end_boundary", "must_exceed_baseline")
            object.__setattr__(self, "end_boundary", endpoint)

    def resolve(self, last_finalized_boundary: int) -> tuple[int, int]:
        """Resolve the endpoint to the run's actual last finalized boundary."""
        last = require_exact_nonneg_int(
            "last_finalized_boundary", last_finalized_boundary
        )
        if last < self.baseline_boundary:
            raise _fail("window.baseline_boundary", "after_last_finalized")
        end = last if self.end_boundary is None else self.end_boundary
        return (self.baseline_boundary, end)

    def endpoint_reached(self, last_finalized_boundary: int) -> bool:
        last = require_exact_nonneg_int(
            "last_finalized_boundary", last_finalized_boundary
        )
        if self.end_boundary is None:
            return last >= self.baseline_boundary
        return last >= self.end_boundary

    def __repr__(self) -> str:
        return (
            f"CulturalAnalysisWindow(baseline_boundary={self.baseline_boundary}, "
            f"end_boundary={self.end_boundary})"
        )


@dataclass(frozen=True, slots=True)
class EvidencePointer:
    """Opaque, resolvable pointer to one owner-local or roster witness."""

    run_id: str
    owner_id: str | None
    boundary_tick: int
    source_kind: str
    local_id: str | None
    source_revision_digest: str | None
    original_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", require_stable_id("run_id", self.run_id))
        object.__setattr__(
            self, "owner_id", _require_optional_id("owner_id", self.owner_id)
        )
        object.__setattr__(
            self,
            "boundary_tick",
            require_exact_nonneg_int("boundary_tick", self.boundary_tick),
        )
        object.__setattr__(
            self,
            "source_kind",
            require_stable_id("source_kind", self.source_kind),
        )
        object.__setattr__(
            self, "local_id", _require_optional_id("local_id", self.local_id)
        )
        if self.source_revision_digest is not None:
            object.__setattr__(
                self,
                "source_revision_digest",
                _require_digest("source_revision_digest", self.source_revision_digest),
            )
        object.__setattr__(
            self,
            "original_refs",
            _require_sorted_unique_ids("original_refs", self.original_refs),
        )

    @property
    def pointer_id(self) -> str:
        return _domain_digest(
            CULTURAL_EVIDENCE_POINTER_DOMAIN,
            (
                self.run_id,
                self.owner_id,
                self.boundary_tick,
                self.source_kind,
                self.local_id,
                self.source_revision_digest,
            ),
        )

    def __repr__(self) -> str:
        return (
            f"EvidencePointer(run_id={self.run_id!r}, owner_id={self.owner_id!r}, "
            f"boundary_tick={self.boundary_tick}, "
            f"source_kind={self.source_kind!r}, "
            f"has_local_id={self.local_id is not None}, "
            f"has_revision_digest={self.source_revision_digest is not None}, "
            f"ref_count={len(self.original_refs)})"
        )


def build_evidence_registry(
    pointers: Sequence[EvidencePointer],
) -> Mapping[str, EvidencePointer]:
    """Return a stable pointer registry; conflicting duplicates fail."""
    raw = _require_sequence("evidence_pointers", pointers)
    registry: dict[str, EvidencePointer] = {}
    for item in raw:
        if type(item) is not EvidencePointer:
            raise _fail("evidence_pointers", "invalid_item")
        existing = registry.get(item.pointer_id)
        if existing is None:
            registry[item.pointer_id] = item
        elif existing != item:
            raise ValueError(_CONFLICT_MESSAGE)
    return MappingProxyType(dict(sorted(registry.items())))


@dataclass(frozen=True, slots=True)
class TraitPresence:
    """One owner-local inventory entry observed at one boundary."""

    owner_id: str
    local_entry_id: str
    dimension: str
    content_digest: str
    lineage_key: str | None = None
    acquisition_tick: int | None = None
    parent_refs: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()
    status: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "owner_id", require_stable_id("owner_id", self.owner_id)
        )
        object.__setattr__(
            self,
            "local_entry_id",
            require_stable_id("local_entry_id", self.local_entry_id),
        )
        object.__setattr__(
            self,
            "dimension",
            _require_closed("dimension", self.dimension, CULTURAL_DIMENSION_SET),
        )
        object.__setattr__(
            self,
            "content_digest",
            _require_digest("content_digest", self.content_digest),
        )
        object.__setattr__(
            self, "lineage_key", _require_optional_id("lineage_key", self.lineage_key)
        )
        if self.acquisition_tick is not None:
            object.__setattr__(
                self,
                "acquisition_tick",
                require_exact_nonneg_int("acquisition_tick", self.acquisition_tick),
            )
        object.__setattr__(
            self,
            "parent_refs",
            _require_sorted_unique_ids("parent_refs", self.parent_refs),
        )
        object.__setattr__(
            self,
            "source_refs",
            _require_sorted_unique_ids("source_refs", self.source_refs),
        )
        object.__setattr__(self, "status", _require_optional_id("status", self.status))

    def __repr__(self) -> str:
        return (
            f"TraitPresence(owner_id={self.owner_id!r}, "
            f"local_entry_id={self.local_entry_id!r}, "
            f"dimension={self.dimension!r}, "
            f"has_lineage={self.lineage_key is not None}, "
            f"acquisition_tick={self.acquisition_tick}, "
            f"parent_count={len(self.parent_refs)}, "
            f"source_count={len(self.source_refs)}, status={self.status!r})"
        )


@dataclass(frozen=True, slots=True)
class InventoryBoundary:
    """Complete or explicitly incomplete inventory at one finalized boundary."""

    boundary_tick: int
    living_owner_ids: tuple[str, ...]
    generation_by_owner: Mapping[str, int]
    owner_dimension_coverage: tuple[tuple[str, str, str], ...]
    entries: tuple[TraitPresence, ...]

    def __post_init__(self) -> None:
        boundary = require_exact_nonneg_int("boundary_tick", self.boundary_tick)
        object.__setattr__(self, "boundary_tick", boundary)

        living = _require_sorted_unique_ids("living_owner_ids", self.living_owner_ids)
        if not living:
            object.__setattr__(self, "living_owner_ids", living)
        else:
            object.__setattr__(self, "living_owner_ids", living)
        living_set = set(living)

        if not isinstance(self.generation_by_owner, Mapping):
            raise _fail("generation_by_owner", "invalid_type")
        generations: dict[str, int] = {}
        for key in sorted(self.generation_by_owner):
            owner = require_stable_id("generation_by_owner", key)
            value = require_exact_nonneg_int(
                "generation_by_owner", self.generation_by_owner[key]
            )
            generations[owner] = value
        if set(generations) != living_set:
            raise _fail("generation_by_owner", "roster_mismatch")
        object.__setattr__(self, "generation_by_owner", MappingProxyType(generations))

        raw_coverage = _require_sequence(
            "owner_dimension_coverage", self.owner_dimension_coverage
        )
        coverage: dict[tuple[str, str], str] = {}
        for item in raw_coverage:
            if not isinstance(item, (tuple, list)) or len(item) != 3:
                raise _fail("owner_dimension_coverage", "invalid_item")
            owner = require_stable_id("owner_dimension_coverage", item[0])
            dimension = _require_closed(
                "owner_dimension_coverage.dimension",
                item[1],
                CULTURAL_DIMENSION_SET,
            )
            code = _require_closed(
                "owner_dimension_coverage.coverage",
                item[2],
                CULTURAL_COVERAGE_CODES,
            )
            coverage_key = (owner, dimension)
            if coverage_key in coverage:
                raise _fail("owner_dimension_coverage", "duplicate_entry")
            coverage[coverage_key] = code
        expected = {
            (owner, dimension) for owner in living for dimension in CULTURAL_DIMENSIONS
        }
        if set(coverage) != expected:
            raise _fail("owner_dimension_coverage", "incomplete_matrix")
        normalized_coverage = tuple(
            (owner, dimension, coverage[(owner, dimension)])
            for owner in living
            for dimension in CULTURAL_DIMENSIONS
        )
        object.__setattr__(self, "owner_dimension_coverage", normalized_coverage)

        raw_entries = _require_sequence("entries", self.entries)
        entries: list[TraitPresence] = []
        seen_entries: set[tuple[str, str, str]] = set()
        for item in raw_entries:
            if type(item) is not TraitPresence:
                raise _fail("entries", "invalid_item")
            if item.owner_id not in living_set:
                raise _fail("entries", "owner_not_living")
            if item.acquisition_tick is not None and item.acquisition_tick > boundary:
                raise _fail("entries", "future_evidence")
            entry_key = (item.owner_id, item.dimension, item.local_entry_id)
            if entry_key in seen_entries:
                raise _fail("entries", "duplicate_entry")
            seen_entries.add(entry_key)
            entries.append(item)
        entries.sort(key=lambda row: (row.owner_id, row.dimension, row.local_entry_id))
        object.__setattr__(self, "entries", tuple(entries))

    def __repr__(self) -> str:
        return (
            f"InventoryBoundary(boundary_tick={self.boundary_tick}, "
            f"living_owner_count={len(self.living_owner_ids)}, "
            f"entry_count={len(self.entries)}, "
            f"coverage_row_count={len(self.owner_dimension_coverage)})"
        )


@dataclass(frozen=True, slots=True)
class TransmissionEdge:
    """One attributable acquisition edge with explicit uncertainty."""

    edge_id: str
    source_owner_id: str | None
    receiver_owner_id: str
    source_local_id: str | None
    receiver_local_id: str
    acquisition_boundary: int
    modality: str
    attribution_status: str
    generation_class: str
    kin_vertical: bool
    source_digest: str | None = None
    target_digest: str | None = None
    mutated: bool = False
    recombined: bool = False
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "edge_id", require_stable_id("edge_id", self.edge_id))
        object.__setattr__(
            self,
            "source_owner_id",
            _require_optional_id("source_owner_id", self.source_owner_id),
        )
        object.__setattr__(
            self,
            "receiver_owner_id",
            require_stable_id("receiver_owner_id", self.receiver_owner_id),
        )
        object.__setattr__(
            self,
            "source_local_id",
            _require_optional_id("source_local_id", self.source_local_id),
        )
        object.__setattr__(
            self,
            "receiver_local_id",
            require_stable_id("receiver_local_id", self.receiver_local_id),
        )
        object.__setattr__(
            self,
            "acquisition_boundary",
            require_exact_nonneg_int("acquisition_boundary", self.acquisition_boundary),
        )
        object.__setattr__(
            self,
            "modality",
            _require_closed(
                "modality", self.modality, CULTURAL_TRANSMISSION_MODALITIES
            ),
        )
        status = _require_closed(
            "attribution_status",
            self.attribution_status,
            CULTURAL_ATTRIBUTION_STATUSES,
        )
        object.__setattr__(self, "attribution_status", status)
        generation = _require_closed(
            "generation_class",
            self.generation_class,
            CULTURAL_GENERATION_CLASSES,
        )
        object.__setattr__(self, "generation_class", generation)
        if type(self.kin_vertical) is not bool:
            raise _fail("kin_vertical", "invalid_type")
        if type(self.mutated) is not bool:
            raise _fail("mutated", "invalid_type")
        if type(self.recombined) is not bool:
            raise _fail("recombined", "invalid_type")
        if self.source_digest is not None:
            object.__setattr__(
                self,
                "source_digest",
                _require_digest("source_digest", self.source_digest),
            )
        if self.target_digest is not None:
            object.__setattr__(
                self,
                "target_digest",
                _require_digest("target_digest", self.target_digest),
            )
        if (self.source_digest is None) != (self.target_digest is None):
            raise _fail("source_digest", "digest_pair_required")
        if status == "resolved":
            if self.source_owner_id is None or self.source_local_id is None:
                raise _fail("source_owner_id", "resolved_requires_source")
        elif self.source_owner_id is not None or self.source_local_id is not None:
            raise _fail("source_owner_id", "unresolved_must_not_name_source")
        if status == "independent_rediscovery" and self.modality != (
            "independent_rediscovery"
        ):
            raise _fail("modality", "rediscovery_modality_mismatch")
        if self.kin_vertical and generation != "intergenerational":
            raise _fail("kin_vertical", "requires_intergenerational")
        object.__setattr__(
            self,
            "evidence_ids",
            _require_sorted_unique_ids("evidence_ids", self.evidence_ids),
        )

    def __repr__(self) -> str:
        return (
            f"TransmissionEdge(edge_id={self.edge_id!r}, "
            f"source_owner_id={self.source_owner_id!r}, "
            f"receiver_owner_id={self.receiver_owner_id!r}, "
            f"acquisition_boundary={self.acquisition_boundary}, "
            f"modality={self.modality!r}, "
            f"attribution_status={self.attribution_status!r}, "
            f"generation_class={self.generation_class!r}, "
            f"kin_vertical={self.kin_vertical}, "
            f"has_comparable_digests={self.source_digest is not None})"
        )


@dataclass(frozen=True, slots=True)
class GroupMembership:
    """One detached owner-to-group assignment with an explicit basis."""

    boundary_tick: int
    owner_id: str
    group_id: str
    basis_id: str
    basis_version: str
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "boundary_tick",
            require_exact_nonneg_int("boundary_tick", self.boundary_tick),
        )
        object.__setattr__(
            self, "owner_id", require_stable_id("owner_id", self.owner_id)
        )
        object.__setattr__(
            self, "group_id", require_stable_id("group_id", self.group_id)
        )
        object.__setattr__(
            self, "basis_id", require_stable_id("basis_id", self.basis_id)
        )
        object.__setattr__(
            self,
            "basis_version",
            require_stable_id("basis_version", self.basis_version),
        )
        object.__setattr__(
            self,
            "evidence_ids",
            _require_sorted_unique_ids("evidence_ids", self.evidence_ids),
        )

    def __repr__(self) -> str:
        return (
            f"GroupMembership(boundary_tick={self.boundary_tick}, "
            f"owner_id={self.owner_id!r}, group_id={self.group_id!r}, "
            f"basis_id={self.basis_id!r}, "
            f"evidence_count={len(self.evidence_ids)})"
        )


@dataclass(frozen=True, slots=True)
class ArchiveKnowledgeState:
    """Record/holder evidence for technology retention and loss."""

    boundary_tick: int
    subject_id: str
    content_digest: str
    record_present: bool
    holder_owner_ids: tuple[str, ...] = ()
    provenance_source_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "boundary_tick",
            require_exact_nonneg_int("boundary_tick", self.boundary_tick),
        )
        object.__setattr__(
            self, "subject_id", require_stable_id("subject_id", self.subject_id)
        )
        object.__setattr__(
            self,
            "content_digest",
            _require_digest("content_digest", self.content_digest),
        )
        if type(self.record_present) is not bool:
            raise _fail("record_present", "invalid_type")
        object.__setattr__(
            self,
            "holder_owner_ids",
            _require_sorted_unique_ids("holder_owner_ids", self.holder_owner_ids),
        )
        object.__setattr__(
            self,
            "provenance_source_ids",
            _require_sorted_unique_ids(
                "provenance_source_ids", self.provenance_source_ids
            ),
        )
        object.__setattr__(
            self,
            "evidence_ids",
            _require_sorted_unique_ids("evidence_ids", self.evidence_ids),
        )

    def __repr__(self) -> str:
        return (
            f"ArchiveKnowledgeState(boundary_tick={self.boundary_tick}, "
            f"subject_id={self.subject_id!r}, record_present={self.record_present}, "
            f"holder_count={len(self.holder_owner_ids)}, "
            f"provenance_count={len(self.provenance_source_ids)})"
        )


@dataclass(frozen=True, slots=True)
class CulturalMeasurement:
    """One scalar cultural measurement with full scientific selectors.

    ``row_id`` is derived from the selector tuple; it is never a cross-run
    comparison key. Use the scientific selectors for comparison.
    """

    family: str
    algorithm_version: str
    policy_version: str
    measurement_id: str
    dimension: str
    representation: str
    scope: str
    partition_id: str | None
    group_ids: tuple[str, ...]
    population_basis: str
    denominator_code: str
    baseline_tick: int
    end_tick: int
    trait_id: str | None
    lineage_id: str | None
    subject_id: str | None
    units: str
    value: float | None
    numerator: float | None
    denominator: float | None
    availability: MetricAvailability
    reason_code: str | None
    coverage_observed: int
    coverage_expected: int | None
    left_censored: bool
    right_censored: bool
    evidence_ids: tuple[str, ...]
    row_id: str = field(init=False)

    def __post_init__(self) -> None:
        for name in ("family", "algorithm_version", "policy_version"):
            object.__setattr__(self, name, require_stable_id(name, getattr(self, name)))
        object.__setattr__(
            self,
            "measurement_id",
            require_stable_id("measurement_id", self.measurement_id),
        )
        object.__setattr__(
            self,
            "dimension",
            _require_closed("dimension", self.dimension, CULTURAL_DIMENSION_SET),
        )
        object.__setattr__(
            self,
            "representation",
            _require_closed(
                "representation", self.representation, CULTURAL_REPRESENTATIONS
            ),
        )
        scope = _require_closed("scope", self.scope, CULTURAL_SCOPES)
        object.__setattr__(self, "scope", scope)
        object.__setattr__(
            self,
            "partition_id",
            _require_optional_id("partition_id", self.partition_id),
        )
        group_ids = _require_sorted_unique_ids("group_ids", self.group_ids)
        if len(group_ids) > 2:
            raise _fail("group_ids", "too_many_groups")
        expected_groups = {
            "global": 0,
            "owner": 0,
            "edge": 0,
            "group": 1,
            "group_pair": 2,
        }[scope]
        if len(group_ids) != expected_groups:
            raise _fail("group_ids", "scope_mismatch")
        object.__setattr__(self, "group_ids", group_ids)
        object.__setattr__(
            self,
            "population_basis",
            _require_closed(
                "population_basis", self.population_basis, CULTURAL_POPULATION_BASES
            ),
        )
        object.__setattr__(
            self,
            "denominator_code",
            _require_closed(
                "denominator_code",
                self.denominator_code,
                CULTURAL_DENOMINATOR_CODES,
            ),
        )
        baseline = require_exact_nonneg_int("baseline_tick", self.baseline_tick)
        end = require_exact_nonneg_int("end_tick", self.end_tick)
        if end < baseline:
            raise _fail("end_tick", "before_baseline")
        object.__setattr__(self, "baseline_tick", baseline)
        object.__setattr__(self, "end_tick", end)
        object.__setattr__(
            self, "trait_id", _require_optional_id("trait_id", self.trait_id)
        )
        object.__setattr__(
            self, "lineage_id", _require_optional_id("lineage_id", self.lineage_id)
        )
        object.__setattr__(
            self, "subject_id", _require_optional_id("subject_id", self.subject_id)
        )
        object.__setattr__(
            self,
            "units",
            _require_closed("units", self.units, CULTURAL_UNITS),
        )
        object.__setattr__(self, "value", _require_finite_optional("value", self.value))
        object.__setattr__(
            self,
            "numerator",
            _require_finite_optional("numerator", self.numerator),
        )
        object.__setattr__(
            self,
            "denominator",
            _require_finite_optional("denominator", self.denominator),
        )
        if type(self.availability) is not MetricAvailability:
            raise _fail("availability", "invalid_type")
        object.__setattr__(
            self,
            "reason_code",
            _require_optional_id("reason_code", self.reason_code),
        )
        observed = require_exact_nonneg_int("coverage_observed", self.coverage_observed)
        object.__setattr__(self, "coverage_observed", observed)
        if self.coverage_expected is not None:
            expected = require_exact_nonneg_int(
                "coverage_expected", self.coverage_expected
            )
            if observed > expected:
                raise _fail("coverage_observed", "exceeds_expected")
            object.__setattr__(self, "coverage_expected", expected)
        if type(self.left_censored) is not bool:
            raise _fail("left_censored", "invalid_type")
        if type(self.right_censored) is not bool:
            raise _fail("right_censored", "invalid_type")
        object.__setattr__(
            self,
            "evidence_ids",
            _require_sorted_unique_ids("evidence_ids", self.evidence_ids),
        )
        object.__setattr__(self, "row_id", self._compute_row_id())

    def _selector_tuple(self) -> tuple[object, ...]:
        return (
            self.family,
            self.algorithm_version,
            self.policy_version,
            self.measurement_id,
            self.dimension,
            self.representation,
            self.scope,
            self.partition_id,
            list(self.group_ids),
            self.population_basis,
            self.denominator_code,
            self.baseline_tick,
            self.end_tick,
            self.trait_id,
            self.lineage_id,
            self.subject_id,
            self.units,
        )

    def _compute_row_id(self) -> str:
        return _domain_digest(CULTURAL_MEASUREMENT_ROW_DOMAIN, self._selector_tuple())

    def to_payload(self) -> dict[str, object]:
        """Serialize exactly the frozen measurement schema keys."""
        return {
            "row_id": self.row_id,
            "measurement_id": self.measurement_id,
            "dimension": self.dimension,
            "representation": self.representation,
            "scope": self.scope,
            "partition_id": self.partition_id,
            "group_ids": list(self.group_ids),
            "population_basis": self.population_basis,
            "denominator_code": self.denominator_code,
            "baseline_tick": self.baseline_tick,
            "end_tick": self.end_tick,
            "trait_id": self.trait_id,
            "lineage_id": self.lineage_id,
            "subject_id": self.subject_id,
            "units": self.units,
            "value": self.value,
            "numerator": self.numerator,
            "denominator": self.denominator,
            "availability": self.availability.value,
            "reason_code": self.reason_code,
            "coverage_observed": self.coverage_observed,
            "coverage_expected": self.coverage_expected,
            "left_censored": self.left_censored,
            "right_censored": self.right_censored,
            "evidence_ids": list(self.evidence_ids),
        }

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, object],
        *,
        family: str,
        algorithm_version: str,
        policy_version: str,
    ) -> CulturalMeasurement:
        """Rebuild a measurement and verify its stable selector identity."""
        if not isinstance(payload, Mapping):
            raise _fail("measurement", "invalid_type")
        expected_keys = {
            "row_id",
            "measurement_id",
            "dimension",
            "representation",
            "scope",
            "partition_id",
            "group_ids",
            "population_basis",
            "denominator_code",
            "baseline_tick",
            "end_tick",
            "trait_id",
            "lineage_id",
            "subject_id",
            "units",
            "value",
            "numerator",
            "denominator",
            "availability",
            "reason_code",
            "coverage_observed",
            "coverage_expected",
            "left_censored",
            "right_censored",
            "evidence_ids",
        }
        if set(payload) != expected_keys:
            raise _fail("measurement", "key_set_mismatch")
        group_ids = _require_sequence("group_ids", payload["group_ids"])
        availability = payload["availability"]
        if not isinstance(availability, str):
            raise _fail("availability", "invalid_type")
        try:
            parsed_availability = MetricAvailability(availability)
        except ValueError as exc:
            raise _fail("availability", "unknown_value") from exc
        measurement = cls(
            family=family,
            algorithm_version=algorithm_version,
            policy_version=policy_version,
            measurement_id=payload["measurement_id"],  # type: ignore[arg-type]
            dimension=payload["dimension"],  # type: ignore[arg-type]
            representation=payload["representation"],  # type: ignore[arg-type]
            scope=payload["scope"],  # type: ignore[arg-type]
            partition_id=payload["partition_id"],  # type: ignore[arg-type]
            group_ids=group_ids,  # type: ignore[arg-type]
            population_basis=payload["population_basis"],  # type: ignore[arg-type]
            denominator_code=payload["denominator_code"],  # type: ignore[arg-type]
            baseline_tick=payload["baseline_tick"],  # type: ignore[arg-type]
            end_tick=payload["end_tick"],  # type: ignore[arg-type]
            trait_id=payload["trait_id"],  # type: ignore[arg-type]
            lineage_id=payload["lineage_id"],  # type: ignore[arg-type]
            subject_id=payload["subject_id"],  # type: ignore[arg-type]
            units=payload["units"],  # type: ignore[arg-type]
            value=payload["value"],  # type: ignore[arg-type]
            numerator=payload["numerator"],  # type: ignore[arg-type]
            denominator=payload["denominator"],  # type: ignore[arg-type]
            availability=parsed_availability,
            reason_code=payload["reason_code"],  # type: ignore[arg-type]
            coverage_observed=payload["coverage_observed"],  # type: ignore[arg-type]
            coverage_expected=payload["coverage_expected"],  # type: ignore[arg-type]
            left_censored=payload["left_censored"],  # type: ignore[arg-type]
            right_censored=payload["right_censored"],  # type: ignore[arg-type]
            evidence_ids=_require_sequence("evidence_ids", payload["evidence_ids"]),  # type: ignore[arg-type]
        )
        if payload.get("row_id") != measurement.row_id:
            raise ValueError(_CONFLICT_MESSAGE)
        return measurement

    def __repr__(self) -> str:
        return (
            f"CulturalMeasurement(family={self.family!r}, "
            f"measurement_id={self.measurement_id!r}, "
            f"dimension={self.dimension!r}, scope={self.scope!r}, "
            f"units={self.units!r}, availability={self.availability.value!r}, "
            f"baseline_tick={self.baseline_tick}, end_tick={self.end_tick}, "
            f"has_value={self.value is not None}, "
            f"evidence_count={len(self.evidence_ids)})"
        )


@dataclass(frozen=True, slots=True)
class CulturalEvolutionInputs:
    """Fully validated analysis inputs for one run and exact window."""

    run_id: str
    source_revision: str
    window: CulturalAnalysisWindow
    boundaries: tuple[InventoryBoundary, ...] = ()
    transmission_edges: tuple[TransmissionEdge, ...] = ()
    group_memberships: tuple[GroupMembership, ...] = ()
    archive_states: tuple[ArchiveKnowledgeState, ...] = ()
    evidence_pointers: tuple[EvidencePointer, ...] = ()
    gaps: tuple[str, ...] = ()
    policy_version: str = CULTURAL_EVOLUTION_POLICY_VERSION
    expected_boundary_interval: int = CULTURAL_EVOLUTION_BOUNDARY_INTERVAL

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", require_stable_id("run_id", self.run_id))
        object.__setattr__(
            self,
            "source_revision",
            require_stable_id("source_revision", self.source_revision),
        )
        if type(self.window) is not CulturalAnalysisWindow:
            raise _fail("window", "invalid_type")
        if self.policy_version != CULTURAL_EVOLUTION_POLICY_VERSION:
            raise _fail("policy_version", "unsupported_policy")
        interval = require_exact_nonneg_int(
            "expected_boundary_interval", self.expected_boundary_interval
        )
        if interval != CULTURAL_EVOLUTION_BOUNDARY_INTERVAL:
            raise _fail("expected_boundary_interval", "unsupported_interval")
        object.__setattr__(self, "expected_boundary_interval", interval)

        raw_boundaries = _require_sequence("boundaries", self.boundaries)
        boundaries: list[InventoryBoundary] = []
        for item in raw_boundaries:
            if type(item) is not InventoryBoundary:
                raise _fail("boundaries", "invalid_item")
            boundaries.append(item)
        boundaries.sort(key=lambda row: row.boundary_tick)
        seen_ticks: set[int] = set()
        for item in boundaries:
            if item.boundary_tick in seen_ticks:
                raise ValueError(_CONFLICT_MESSAGE)
            seen_ticks.add(item.boundary_tick)
        if self.window.end_boundary is not None:
            for item in boundaries:
                if item.boundary_tick > self.window.end_boundary:
                    raise _fail("boundaries", "future_evidence")
        object.__setattr__(self, "boundaries", tuple(boundaries))

        raw_edges = _require_sequence("transmission_edges", self.transmission_edges)
        edges: list[TransmissionEdge] = []
        for item in raw_edges:
            if type(item) is not TransmissionEdge:
                raise _fail("transmission_edges", "invalid_item")
            if (
                self.window.end_boundary is not None
                and item.acquisition_boundary > self.window.end_boundary
            ):
                raise _fail("transmission_edges", "future_evidence")
            edges.append(item)
        object.__setattr__(
            self,
            "transmission_edges",
            _deduplicate("transmission_edges", edges, lambda row: row.edge_id),
        )

        raw_groups = _require_sequence("group_memberships", self.group_memberships)
        groups: list[GroupMembership] = []
        for item in raw_groups:
            if type(item) is not GroupMembership:
                raise _fail("group_memberships", "invalid_item")
            if (
                self.window.end_boundary is not None
                and item.boundary_tick > self.window.end_boundary
            ):
                raise _fail("group_memberships", "future_evidence")
            groups.append(item)
        object.__setattr__(
            self,
            "group_memberships",
            _deduplicate(
                "group_memberships",
                groups,
                lambda row: (
                    row.boundary_tick,
                    row.owner_id,
                    row.group_id,
                    row.basis_id,
                    row.basis_version,
                ),
            ),
        )

        raw_archives = _require_sequence("archive_states", self.archive_states)
        archives: list[ArchiveKnowledgeState] = []
        for item in raw_archives:
            if type(item) is not ArchiveKnowledgeState:
                raise _fail("archive_states", "invalid_item")
            if (
                self.window.end_boundary is not None
                and item.boundary_tick > self.window.end_boundary
            ):
                raise _fail("archive_states", "future_evidence")
            archives.append(item)
        object.__setattr__(
            self,
            "archive_states",
            _deduplicate(
                "archive_states",
                archives,
                lambda row: (
                    row.boundary_tick,
                    row.subject_id,
                    row.content_digest,
                ),
            ),
        )

        raw_pointers = _require_sequence("evidence_pointers", self.evidence_pointers)
        pointers: list[EvidencePointer] = []
        for item in raw_pointers:
            if type(item) is not EvidencePointer:
                raise _fail("evidence_pointers", "invalid_item")
            if item.run_id != self.run_id:
                raise _fail("evidence_pointers", "run_mismatch")
            pointers.append(item)
        registry = build_evidence_registry(pointers)
        max_boundary = max(seen_ticks) if seen_ticks else None
        max_boundary = (
            self.window.end_boundary
            if self.window.end_boundary is not None
            else max_boundary
        )
        if max_boundary is not None:
            for pointer in registry.values():
                if pointer.boundary_tick > max_boundary:
                    raise _fail("evidence_pointers", "future_evidence")
        object.__setattr__(
            self,
            "evidence_pointers",
            tuple(registry[key] for key in registry),
        )

        raw_gaps = _require_sorted_unique_ids("gaps", self.gaps)
        object.__setattr__(self, "gaps", raw_gaps)

    def resolve_window(self, last_finalized_boundary: int) -> tuple[int, int]:
        """Resolve the window without rebasing onto observed frames."""
        return self.window.resolve(last_finalized_boundary)

    def __repr__(self) -> str:
        return (
            f"CulturalEvolutionInputs(run_id={self.run_id!r}, "
            f"source_revision={self.source_revision!r}, "
            f"window={self.window!r}, boundary_count={len(self.boundaries)}, "
            f"edge_count={len(self.transmission_edges)}, "
            f"group_count={len(self.group_memberships)}, "
            f"archive_count={len(self.archive_states)}, "
            f"pointer_count={len(self.evidence_pointers)}, "
            f"gap_count={len(self.gaps)})"
        )


CULTURAL_FEATURE_DIMENSION_BY_KIND: Final[dict[str, str]] = {
    "practice": "feature:practice",
    "narrative_element": "feature:narrative_element",
    "term": "feature:term",
    "production_technique": "feature:production_technique",
    "social_expectation": "feature:social_expectation",
    "symbolic_association": "feature:symbolic_association",
}

_CHANNEL_DIMENSIONS: Final[dict[str, tuple[str, ...]]] = {
    CULTURAL_EVIDENCE_CHANNEL_CULTURAL_FEATURES: CULTURAL_FEATURE_DIMENSIONS,
    CULTURAL_EVIDENCE_CHANNEL_TERMINOLOGY: ("vocabulary",),
    CULTURAL_EVIDENCE_CHANNEL_NARRATIVES: ("narrative",),
    CULTURAL_EVIDENCE_CHANNEL_PRACTICAL_KNOWLEDGE: ("technology",),
}

_ORIGIN_MODALITY: Final[dict[str, str]] = {
    "independent_discovery": "independent_rediscovery",
    "teaching": "teaching",
    "imitation": "imitation",
    "written_record": "artifact",
    "reconstruction": "observation",
    "combination": "communication",
}


def canonical_source_digest(domain: str, payload: object) -> str:
    """Domain-separated full SHA-256 of exact canonical source content."""
    return _domain_digest(domain, payload)


def _owner_coverage(owner: CulturalOwnerExport) -> tuple[tuple[str, str, str], ...]:
    rows: list[tuple[str, str, str]] = []
    for channel in owner.channels:
        dimensions = _CHANNEL_DIMENSIONS[channel.channel]
        for dimension in dimensions:
            rows.append((owner.owner_id.value, dimension, channel.coverage))
    return tuple(rows)


def _coverage_is_observed(channel: CulturalChannelExport) -> bool:
    return channel.coverage not in {
        CULTURAL_EVIDENCE_COVERAGE_DISABLED,
        CULTURAL_EVIDENCE_COVERAGE_MISSING,
    }


def _boundary_pointers(
    frame: CulturalBoundaryExport, entries: tuple[TraitPresence, ...]
) -> tuple[EvidencePointer, ...]:
    pointers: list[EvidencePointer] = []
    for owner in frame.owners:
        pointers.append(
            EvidencePointer(
                run_id=frame.run_id,
                owner_id=owner.owner_id.value,
                boundary_tick=frame.boundary_tick,
                source_kind="roster",
                local_id=f"roster:{frame.boundary_tick}",
                source_revision_digest=None,
                original_refs=(),
            )
        )
    for entry in entries:
        pointers.append(
            EvidencePointer(
                run_id=frame.run_id,
                owner_id=entry.owner_id,
                boundary_tick=frame.boundary_tick,
                source_kind=f"trait:{entry.dimension}",
                local_id=entry.local_entry_id,
                source_revision_digest=entry.content_digest,
                original_refs=(
                    entry.source_refs if entry.source_refs else entry.parent_refs
                ),
            )
        )
    return tuple(pointers)


def _cultural_feature_presences(
    owner: CulturalOwnerExport, channel: CulturalChannelExport
) -> list[TraitPresence]:
    if channel.ledger is None or not _coverage_is_observed(channel):
        return []
    ledger = channel.ledger
    rows: list[TraitPresence] = []
    for belief in getattr(ledger, "beliefs", ()):
        kind = getattr(belief.feature_kind, "value", None)
        dimension = CULTURAL_FEATURE_DIMENSION_BY_KIND.get(str(kind))
        if dimension is None:
            continue
        digest = canonical_source_digest(
            "cultural-feature-content-v1",
            {
                "kind": str(kind),
                "fingerprint": belief.content_fingerprint,
            },
        )
        rows.append(
            TraitPresence(
                owner_id=owner.owner_id.value,
                local_entry_id=belief.belief_id,
                dimension=dimension,
                content_digest=digest,
                lineage_key=belief.content_key,
                acquisition_tick=belief.acquired_tick,
                parent_refs=belief.parent_belief_ids,
                source_refs=belief.evidence_refs,
                status=getattr(belief.channel, "value", None),
            )
        )
    return rows


def _terminology_presences(
    owner: CulturalOwnerExport, channel: CulturalChannelExport
) -> list[TraitPresence]:
    if channel.ledger is None or not _coverage_is_observed(channel):
        return []
    ledger = channel.ledger
    rows: list[TraitPresence] = []
    for binding in getattr(ledger, "bindings", ()):
        if getattr(getattr(binding, "status", None), "value", None) != "active":
            continue
        if getattr(binding, "merged_into", None) is not None:
            continue
        digest = canonical_source_digest(
            "cultural-vocabulary-label-v1",
            {"label_token": binding.label_token},
        )
        rows.append(
            TraitPresence(
                owner_id=owner.owner_id.value,
                local_entry_id=binding.binding_id,
                dimension="vocabulary",
                content_digest=digest,
                acquisition_tick=getattr(binding, "first_tick", None),
                status="active",
            )
        )
    return rows


def _narrative_presences(
    owner: CulturalOwnerExport, channel: CulturalChannelExport
) -> list[TraitPresence]:
    if channel.ledger is None or not _coverage_is_observed(channel):
        return []
    ledger = channel.ledger
    rows: list[TraitPresence] = []
    for variant in getattr(ledger, "variants", ()):
        if getattr(getattr(variant, "status", None), "value", None) != "active":
            continue
        if getattr(variant, "merged_into_id", None) is not None:
            continue
        digest = canonical_source_digest(
            "cultural-narrative-content-v1",
            {"fingerprint": variant.content_fingerprint},
        )
        rows.append(
            TraitPresence(
                owner_id=owner.owner_id.value,
                local_entry_id=variant.variant_id,
                dimension="narrative",
                content_digest=digest,
                lineage_key=getattr(variant, "transmission_root_id", None),
                acquisition_tick=getattr(variant, "first_tick", None),
                parent_refs=variant.parent_variant_ids,
                status="active",
            )
        )
    return rows


def _technology_digest(entry: Any) -> str:
    return canonical_source_digest(
        "cultural-practical-content-v1",
        {
            "content_key": entry.content_key,
            "fingerprint": list(entry.content_fingerprint),
        },
    )


def _technology_presences(
    owner: CulturalOwnerExport, channel: CulturalChannelExport
) -> list[TraitPresence]:
    if channel.ledger is None or not _coverage_is_observed(channel):
        return []
    ledger = channel.ledger
    rows: list[TraitPresence] = []
    for entry in getattr(ledger, "entries", ()):
        if not bool(getattr(entry, "active", False)):
            continue
        rows.append(
            TraitPresence(
                owner_id=owner.owner_id.value,
                local_entry_id=entry.entry_id,
                dimension="technology",
                content_digest=_technology_digest(entry),
                lineage_key=entry.lineage_root_id,
                acquisition_tick=entry.acquired_tick,
                parent_refs=entry.parent_entry_ids,
                source_refs=entry.evidence_refs,
                status="active",
            )
        )
    return rows


def _presences_for_channel(
    owner: CulturalOwnerExport, channel: CulturalChannelExport
) -> list[TraitPresence]:
    if channel.channel == CULTURAL_EVIDENCE_CHANNEL_CULTURAL_FEATURES:
        return _cultural_feature_presences(owner, channel)
    if channel.channel == CULTURAL_EVIDENCE_CHANNEL_TERMINOLOGY:
        return _terminology_presences(owner, channel)
    if channel.channel == CULTURAL_EVIDENCE_CHANNEL_NARRATIVES:
        return _narrative_presences(owner, channel)
    if channel.channel == CULTURAL_EVIDENCE_CHANNEL_PRACTICAL_KNOWLEDGE:
        return _technology_presences(owner, channel)
    return []


def _normalize_boundaries(
    frames: Sequence[CulturalBoundaryExport],
) -> tuple[tuple[InventoryBoundary, ...], tuple[EvidencePointer, ...]]:
    boundaries: list[InventoryBoundary] = []
    pointers: list[EvidencePointer] = []
    for frame in frames:
        living = tuple(owner.owner_id.value for owner in frame.owners if owner.living)
        generations = {
            owner.owner_id.value: owner.generation_index
            for owner in frame.owners
            if owner.living
        }
        coverage: list[tuple[str, str, str]] = []
        entries: list[TraitPresence] = []
        for owner in frame.owners:
            if not owner.living:
                continue
            coverage.extend(_owner_coverage(owner))
            for channel in owner.channels:
                entries.extend(_presences_for_channel(owner, channel))
        boundary = InventoryBoundary(
            boundary_tick=frame.boundary_tick,
            living_owner_ids=living,
            generation_by_owner=generations,
            owner_dimension_coverage=tuple(coverage),
            entries=tuple(entries),
        )
        boundaries.append(boundary)
        pointers.extend(_boundary_pointers(frame, tuple(boundary.entries)))
    return tuple(boundaries), tuple(pointers)


def _practical_source_rows(
    boundaries: Sequence[InventoryBoundary],
    frames: Sequence[CulturalBoundaryExport],
) -> dict[tuple[str, str], list[tuple[int, str, str]]]:
    rows: dict[tuple[str, str], list[tuple[int, str, str]]] = {}
    for frame in frames:
        for owner in frame.owners:
            for channel in owner.channels:
                if channel.channel != CULTURAL_EVIDENCE_CHANNEL_PRACTICAL_KNOWLEDGE:
                    continue
                if channel.ledger is None or not _coverage_is_observed(channel):
                    continue
                for entry in getattr(channel.ledger, "entries", ()):
                    if not bool(getattr(entry, "active", False)):
                        continue
                    digest = _technology_digest(entry)
                    rows.setdefault((owner.owner_id.value, digest), []).append(
                        (frame.boundary_tick, entry.entry_id, entry.acquired_tick)
                    )
    return rows


def _normalize_transmission_edges(
    boundaries: Sequence[InventoryBoundary],
    frames: Sequence[CulturalBoundaryExport],
    *,
    parent_child_edges: frozenset[tuple[str, str]],
) -> tuple[TransmissionEdge, ...]:
    source_rows = _practical_source_rows(boundaries, frames)
    generations: dict[str, int] = {}
    for boundary in boundaries:
        for owner_token, generation in boundary.generation_by_owner.items():
            generations.setdefault(owner_token, generation)
    edges: list[TransmissionEdge] = []
    for frame in frames:
        for owner in frame.owners:
            for channel in owner.channels:
                if channel.channel != CULTURAL_EVIDENCE_CHANNEL_PRACTICAL_KNOWLEDGE:
                    continue
                if channel.ledger is None or not _coverage_is_observed(channel):
                    continue
                for entry in getattr(channel.ledger, "entries", ()):
                    if not bool(getattr(entry, "active", False)):
                        continue
                    source_owner = getattr(entry, "teacher_agent_id", None)
                    if source_owner is None:
                        source_owner = getattr(entry, "source_agent_id", None)
                    if source_owner is None:
                        continue
                    source_token = getattr(source_owner, "value", None)
                    if not isinstance(source_token, str):
                        continue
                    target_digest = _technology_digest(entry)
                    candidates = [
                        row
                        for row in source_rows.get((source_token, target_digest), ())
                        if row[0] <= entry.acquired_tick
                    ]
                    candidate_ids = sorted({row[1] for row in candidates})
                    if len(candidate_ids) == 1:
                        status = "resolved"
                        source_local_id: str | None = candidate_ids[0]
                    elif len(candidate_ids) > 1:
                        status = "ambiguous_source"
                        source_local_id = None
                    else:
                        status = "unknown_source"
                        source_local_id = None
                    if status == "resolved":
                        source_generation = generations.get(source_token)
                        receiver_generation = generations.get(owner.owner_id.value)
                        if source_generation is None or receiver_generation is None:
                            generation_class = "unknown"
                        elif source_generation < receiver_generation:
                            generation_class = "intergenerational"
                        elif source_generation > receiver_generation:
                            generation_class = "reverse_intergenerational"
                        else:
                            generation_class = "horizontal"
                    else:
                        generation_class = "unknown"
                    edge_id = _domain_digest(
                        "cultural-transmission-edge-v1",
                        (
                            owner.owner_id.value,
                            entry.entry_id,
                            source_token,
                            entry.acquired_tick,
                        ),
                    )
                    edges.append(
                        TransmissionEdge(
                            edge_id=edge_id,
                            source_owner_id=(
                                source_token if status == "resolved" else None
                            ),
                            receiver_owner_id=owner.owner_id.value,
                            source_local_id=source_local_id,
                            receiver_local_id=entry.entry_id,
                            acquisition_boundary=entry.acquired_tick + 1,
                            modality=_ORIGIN_MODALITY.get(
                                getattr(getattr(entry, "origin", None), "value", ""),
                                "teaching",
                            ),
                            attribution_status=status,
                            generation_class=generation_class,
                            kin_vertical=(
                                (source_token, owner.owner_id.value)
                                in parent_child_edges
                                and generation_class == "intergenerational"
                            ),
                            source_digest=(
                                target_digest if status == "resolved" else None
                            ),
                            target_digest=(
                                target_digest if status == "resolved" else None
                            ),
                            mutated=bool(getattr(entry, "mutated", False)),
                            recombined=(
                                getattr(getattr(entry, "origin", None), "value", "")
                                == "combination"
                            ),
                            evidence_ids=(),
                        )
                    )
    return tuple(edges)


def normalize_cultural_frames(
    frames: Sequence[CulturalBoundaryExport],
    *,
    run_id: str,
    source_revision: str,
    window: CulturalAnalysisWindow,
    parent_child_edges: Sequence[tuple[str, str]] = (),
    group_memberships: Sequence[GroupMembership] = (),
    archive_states: Sequence[ArchiveKnowledgeState] = (),
    gaps: Sequence[str] = (),
) -> CulturalEvolutionInputs:
    """Conservatively normalize detached frames into analysis inputs."""
    raw = tuple(frames)
    for frame in raw:
        if type(frame) is not CulturalBoundaryExport:
            raise _fail("frames", "invalid_item")
        if frame.run_id != run_id:
            raise _fail("frames", "run_mismatch")
    boundaries, pointers = _normalize_boundaries(raw)
    edges = _normalize_transmission_edges(
        boundaries,
        raw,
        parent_child_edges=frozenset(parent_child_edges),
    )
    return CulturalEvolutionInputs(
        run_id=run_id,
        source_revision=source_revision,
        window=window,
        boundaries=boundaries,
        transmission_edges=edges,
        group_memberships=tuple(group_memberships),
        archive_states=tuple(archive_states),
        evidence_pointers=pointers,
        gaps=tuple(gaps),
    )


_LOG.debug(
    "cultural_evolution_evidence_contracts_loaded policy=%s dimension_count=%s",
    CULTURAL_EVOLUTION_POLICY_VERSION,
    len(CULTURAL_DIMENSIONS),
)
