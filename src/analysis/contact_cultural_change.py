"""Pre/post-contact cultural divergence windows per candidate-community pair."""

from __future__ import annotations

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
from analysis.numerical import (
    jensen_shannon_divergence,
    library_versions,
    quantize_float,
    require_finite,
)
from analysis.society_contact import ContactPairRow
from analysis.society_divergence import SOCIETY_DIMENSIONS
from analysis.society_emergence import CandidateCommunityRow
from analysis.specifications import MetricFamilyId, metric_specification
from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "CONTACT_CULTURAL_CHANGE_METRIC_VERSION",
    "ContactCulturalChangeResult",
    "ContactCulturalChangeRow",
    "ContactDigestRow",
    "compute_contact_cultural_change",
    "compute_contact_cultural_change_metric",
]

CONTACT_CULTURAL_CHANGE_METRIC_VERSION: Final[str] = "contact_cultural_change@1"
_LOG: Final[logging.Logger] = logging.getLogger("analysis.contact_cultural_change")


class ContactCulturalChangeError(ValueError):
    def __init__(self, reason_code: str) -> None:
        self.reason_code = require_stable_id("reason_code", reason_code)
        super().__init__(reason_code)


@dataclass(frozen=True, slots=True)
class ContactDigestRow:
    """One ticked society digest token row."""

    dimension: str
    person_id: str
    token: str
    tick: int

    def __post_init__(self) -> None:
        dimension = require_stable_id("dimension", self.dimension)
        if dimension not in SOCIETY_DIMENSIONS:
            raise ContactCulturalChangeError("unknown_dimension")
        object.__setattr__(self, "dimension", dimension)
        object.__setattr__(
            self, "person_id", require_stable_id("person_id", self.person_id)
        )
        object.__setattr__(self, "token", require_stable_id("token", self.token))
        object.__setattr__(self, "tick", require_exact_nonneg_int("tick", self.tick))


@dataclass(frozen=True, slots=True)
class ContactCulturalChangeRow:
    community_a_id: str
    community_b_id: str
    dimension: str
    pre_divergence: float | None
    post_divergence: float | None
    convergence_delta: float | None
    pre_observed: int
    post_observed: int
    reason_code: str


@dataclass(frozen=True, slots=True)
class ContactCulturalChangeResult:
    rows: tuple[ContactCulturalChangeRow, ...]
    coverage: MetricCoverage
    membership_stability: float | None
    coverage_pair_count: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "rows",
            tuple(
                sorted(
                    self.rows,
                    key=lambda row: (
                        row.community_a_id,
                        row.community_b_id,
                        row.dimension,
                    ),
                )
            ),
        )
        if type(self.coverage) is not MetricCoverage:
            raise ContactCulturalChangeError("invalid_coverage")


def _distribution(
    counts: Mapping[str, int], universe: Sequence[str]
) -> tuple[float, ...]:
    return tuple(float(counts.get(token, 0)) for token in universe)


def compute_contact_cultural_change(
    communities: Sequence[CandidateCommunityRow],
    pairs: Sequence[ContactPairRow],
    digest_rows: Sequence[ContactDigestRow],
    *,
    final_tick: int,
    pre_community_by_person: Mapping[str, str] | None = None,
) -> ContactCulturalChangeResult:
    community_rows = tuple(communities)
    if any(type(item) is not CandidateCommunityRow for item in community_rows):
        raise ContactCulturalChangeError("invalid_communities")
    final_tick = require_exact_nonneg_int("final_tick", final_tick)
    owner: dict[str, str] = {}
    for community in community_rows:
        for person in community.person_ids:
            owner[person] = community.community_id

    digest: list[tuple[str, str, int, str]] = []
    for row in digest_rows:
        if type(row) is not ContactDigestRow:
            raise ContactCulturalChangeError("invalid_digest_row")
        community_id = owner.get(row.person_id)
        if community_id is None or row.tick > final_tick:
            continue
        digest.append((community_id, row.dimension, row.tick, row.token))

    result_rows: list[ContactCulturalChangeRow] = []
    evaluable = 0
    expected = 0
    for pair in pairs:
        pair_onset = pair.onset_tick
        for dimension in SOCIETY_DIMENSIONS:
            expected += 1
            rows_by_key: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
            observed: Counter[tuple[str, str]] = Counter()
            for community_id, row_dimension, tick, token in digest:
                if row_dimension != dimension:
                    continue
                if community_id not in (pair.community_a_id, pair.community_b_id):
                    continue
                window = "pre" if tick < pair_onset else "post"
                rows_by_key[(community_id, window)][token] += 1
                observed[(community_id, window)] += 1
            universe = sorted(
                {token for counts in rows_by_key.values() for token in counts}
            )
            a_pre = rows_by_key.get((pair.community_a_id, "pre"), Counter())
            b_pre = rows_by_key.get((pair.community_b_id, "pre"), Counter())
            a_post = rows_by_key.get((pair.community_a_id, "post"), Counter())
            b_post = rows_by_key.get((pair.community_b_id, "post"), Counter())
            pre_observed = observed.get((pair.community_a_id, "pre"), 0) + observed.get(
                (pair.community_b_id, "pre"), 0
            )
            post_observed = observed.get(
                (pair.community_a_id, "post"), 0
            ) + observed.get((pair.community_b_id, "post"), 0)
            if not universe:
                result_rows.append(
                    ContactCulturalChangeRow(
                        pair.community_a_id,
                        pair.community_b_id,
                        dimension,
                        None,
                        None,
                        None,
                        pre_observed,
                        post_observed,
                        "absent_channel",
                    )
                )
                continue
            pre = jensen_shannon_divergence(
                _distribution(a_pre, universe), _distribution(b_pre, universe)
            )
            post = jensen_shannon_divergence(
                _distribution(a_post, universe), _distribution(b_post, universe)
            )
            if pre is None or post is None:
                result_rows.append(
                    ContactCulturalChangeRow(
                        pair.community_a_id,
                        pair.community_b_id,
                        dimension,
                        pre,
                        post,
                        None,
                        pre_observed,
                        post_observed,
                        "missing_window",
                    )
                )
                continue
            evaluable += 1
            result_rows.append(
                ContactCulturalChangeRow(
                    pair.community_a_id,
                    pair.community_b_id,
                    dimension,
                    pre,
                    post,
                    quantize_float(require_finite(pre - post)),
                    pre_observed,
                    post_observed,
                    "ok",
                )
            )

    stability = None
    if pre_community_by_person is not None and owner:
        same = sum(
            1
            for person, community_id in owner.items()
            if pre_community_by_person.get(person) == community_id
        )
        stability = quantize_float(require_finite(same / len(owner)))
    coverage = MetricCoverage(
        observed=evaluable,
        expected=expected,
        ratio=(
            quantize_float(require_finite(evaluable / expected)) if expected else None
        ),
    )
    _LOG.info(
        "contact_cultural_change_computed pair_count=%s evaluable=%s expected=%s",
        len(tuple(pairs)),
        evaluable,
        expected,
    )
    return ContactCulturalChangeResult(
        rows=tuple(result_rows),
        coverage=coverage,
        membership_stability=stability,
        coverage_pair_count=len(tuple(pairs)),
    )


def compute_contact_cultural_change_metric(
    result: ContactCulturalChangeResult,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    spec = metric_specification(MetricFamilyId.CONTACT_CULTURAL_CHANGE)
    values: dict[str, object] = {
        "contact_pair_count": result.coverage_pair_count,
        "coverage_pair_count": result.coverage_pair_count,
    }
    if result.membership_stability is not None:
        values["membership_stability"] = result.membership_stability
    for dimension in SOCIETY_DIMENSIONS:
        rows = [row for row in result.rows if row.dimension == dimension]
        usable = [
            row
            for row in rows
            if row.pre_divergence is not None and row.post_divergence is not None
        ]
        values[f"{dimension}_converging_pair_count"] = sum(
            1 for row in usable if (row.convergence_delta or 0.0) > 0.0
        )
        values[f"{dimension}_continued_divergence_pair_count"] = sum(
            1 for row in usable if (row.convergence_delta or 0.0) <= 0.0
        )
        if usable:
            values[f"{dimension}_pre_contact_divergence"] = quantize_float(
                require_finite(
                    sum(row.pre_divergence or 0.0 for row in usable) / len(usable)
                )
            )
            values[f"{dimension}_post_contact_divergence"] = quantize_float(
                require_finite(
                    sum(row.post_divergence or 0.0 for row in usable) / len(usable)
                )
            )
            values[f"{dimension}_convergence_delta"] = quantize_float(
                require_finite(
                    sum(row.convergence_delta or 0.0 for row in usable) / len(usable)
                )
            )
    if not any(
        row.pre_divergence is not None and row.post_divergence is not None
        for row in result.rows
    ):
        availability = MetricAvailability.ABSENT
    elif result.coverage.observed < result.coverage.expected:
        availability = MetricAvailability.PARTIAL
    else:
        availability = MetricAvailability.PRESENT
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
        coverage=result.coverage,
        availability=availability,
        values=values,
        provenance=MetricProvenance(
            source_kind="contact_cultural_change",
            source_ids=(),
            notes_code="descriptive_contact_association",
        ),
    )
