"""Hybrid-practice detection from existing owner-local lineage evidence."""

from __future__ import annotations

import logging
from collections import defaultdict
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
from analysis.numerical import library_versions, quantize_float, require_finite
from analysis.society_emergence import CandidateCommunityRow
from analysis.specifications import MetricFamilyId, metric_specification
from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "CONTACT_HYBRID_PRACTICE_METRIC_VERSION",
    "ContactCulturalLineageRow",
    "ContactHybridPracticeResult",
    "ContactMergeRow",
    "ContactNarrativeRootRow",
    "ContactPracticalLineageRow",
    "compute_contact_hybrid_practice",
    "compute_contact_hybrid_practice_metric",
]

CONTACT_HYBRID_PRACTICE_METRIC_VERSION: Final[str] = "contact_hybrid_practice@1"
_LOG: Final[logging.Logger] = logging.getLogger("analysis.contact_hybrid_practice")


class ContactHybridPracticeError(ValueError):
    def __init__(self, reason_code: str) -> None:
        self.reason_code = require_stable_id("reason_code", reason_code)
        super().__init__(reason_code)


def _ids(values: object, field_name: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise ContactHybridPracticeError("invalid_lineage_ids")
    return tuple(require_stable_id(field_name, item) for item in values)


@dataclass(frozen=True, slots=True)
class ContactPracticalLineageRow:
    owner_id: str
    parent_person_ids: tuple[str, ...]
    origin: str
    tick: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "owner_id", require_stable_id("owner_id", self.owner_id)
        )
        object.__setattr__(
            self,
            "parent_person_ids",
            _ids(self.parent_person_ids, "parent_person_id"),
        )
        object.__setattr__(self, "origin", require_stable_id("origin", self.origin))
        object.__setattr__(self, "tick", require_exact_nonneg_int("tick", self.tick))


@dataclass(frozen=True, slots=True)
class ContactCulturalLineageRow:
    owner_id: str
    parent_person_ids: tuple[str, ...]
    recombined: bool
    tick: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "owner_id", require_stable_id("owner_id", self.owner_id)
        )
        object.__setattr__(
            self,
            "parent_person_ids",
            _ids(self.parent_person_ids, "parent_person_id"),
        )
        if type(self.recombined) is not bool:
            raise ContactHybridPracticeError("invalid_recombined")
        object.__setattr__(self, "tick", require_exact_nonneg_int("tick", self.tick))


@dataclass(frozen=True, slots=True)
class ContactNarrativeRootRow:
    person_id: str
    transmission_root_id: str
    tick: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "person_id", require_stable_id("person_id", self.person_id)
        )
        object.__setattr__(
            self,
            "transmission_root_id",
            require_stable_id("transmission_root_id", self.transmission_root_id),
        )
        object.__setattr__(self, "tick", require_exact_nonneg_int("tick", self.tick))


@dataclass(frozen=True, slots=True)
class ContactMergeRow:
    owner_id: str
    donor_person_ids: tuple[str, ...]
    kind: str
    tick: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "owner_id", require_stable_id("owner_id", self.owner_id)
        )
        object.__setattr__(
            self,
            "donor_person_ids",
            _ids(self.donor_person_ids, "donor_person_id"),
        )
        kind = require_stable_id("kind", self.kind)
        if kind not in {"naming", "convention"}:
            raise ContactHybridPracticeError("unknown_merge_kind")
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "tick", require_exact_nonneg_int("tick", self.tick))


@dataclass(frozen=True, slots=True)
class ContactHybridPracticeResult:
    hybrid_practical_knowledge_count: int
    intercommunity_combination_count: int
    hybrid_cultural_belief_count: int
    narrative_shared_root_pair_count: int
    narrative_merge_count: int
    resolvable_lineage_entry_count: int
    unresolved_lineage_count: int
    coverage: MetricCoverage

    def __post_init__(self) -> None:
        if type(self.coverage) is not MetricCoverage:
            raise ContactHybridPracticeError("invalid_coverage")


def _communities(
    communities: Sequence[CandidateCommunityRow],
) -> dict[str, str]:
    owner: dict[str, str] = {}
    for community in communities:
        for person in community.person_ids:
            if person in owner:
                raise ContactHybridPracticeError("duplicate_person_across_communities")
            owner[person] = community.community_id
    return owner


def compute_contact_hybrid_practice(
    communities: Sequence[CandidateCommunityRow],
    *,
    practical: Sequence[ContactPracticalLineageRow] = (),
    cultural: Sequence[ContactCulturalLineageRow] = (),
    narratives: Sequence[ContactNarrativeRootRow] = (),
    merges: Sequence[ContactMergeRow] = (),
    onset_tick_by_person: Mapping[str, int] | None = None,
) -> ContactHybridPracticeResult:
    community_rows = tuple(communities)
    if any(type(item) is not CandidateCommunityRow for item in community_rows):
        raise ContactHybridPracticeError("invalid_communities")
    owner = _communities(community_rows)

    hybrid_practical = 0
    intercommunity_combination = 0
    resolvable = 0
    unresolved = 0

    def _post_contact(person_id: str, tick: int) -> bool:
        if onset_tick_by_person is None:
            return True
        onset = onset_tick_by_person.get(person_id)
        return onset is not None and tick >= onset

    for practical_row in practical:
        if type(practical_row) is not ContactPracticalLineageRow:
            raise ContactHybridPracticeError("invalid_practical_row")
        if not _post_contact(practical_row.owner_id, practical_row.tick):
            continue
        if owner.get(practical_row.owner_id) is None:
            continue
        parent_communities = {
            owner.get(item) for item in practical_row.parent_person_ids
        }
        if None in parent_communities:
            unresolved += 1
            continue
        resolvable += 1
        if practical_row.origin == "combination" and len(parent_communities) > 1:
            hybrid_practical += 1
            intercommunity_combination += 1

    hybrid_cultural = 0
    for cultural_row in cultural:
        if type(cultural_row) is not ContactCulturalLineageRow:
            raise ContactHybridPracticeError("invalid_cultural_row")
        if not _post_contact(cultural_row.owner_id, cultural_row.tick):
            continue
        if owner.get(cultural_row.owner_id) is None:
            continue
        parent_communities = {
            owner.get(item) for item in cultural_row.parent_person_ids
        }
        if None in parent_communities:
            unresolved += 1
            continue
        resolvable += 1
        if cultural_row.recombined and len(parent_communities) > 1:
            hybrid_cultural += 1

    roots_by_community: dict[str, set[str]] = defaultdict(set)
    for narrative_row in narratives:
        if type(narrative_row) is not ContactNarrativeRootRow:
            raise ContactHybridPracticeError("invalid_narrative_row")
        community = owner.get(narrative_row.person_id)
        if community is not None:
            roots_by_community[narrative_row.transmission_root_id].add(community)
    shared_root_pairs = sum(
        1
        for communities_for_root in roots_by_community.values()
        if len(communities_for_root) > 1
    )

    narrative_merge = 0
    for merge_row in merges:
        if type(merge_row) is not ContactMergeRow:
            raise ContactHybridPracticeError("invalid_merge_row")
        owner_community = owner.get(merge_row.owner_id)
        donor_communities = {owner.get(item) for item in merge_row.donor_person_ids}
        if owner_community is None or None in donor_communities:
            unresolved += 1
            continue
        resolvable += 1
        if donor_communities - {owner_community}:
            narrative_merge += 1

    expected = resolvable + unresolved
    coverage = MetricCoverage(
        observed=resolvable,
        expected=expected,
        ratio=(
            quantize_float(require_finite(resolvable / expected)) if expected else None
        ),
    )
    _LOG.info(
        "contact_hybrid_practice_computed hybrid_practical=%s hybrid_cultural=%s "
        "shared_roots=%s unresolved=%s",
        hybrid_practical,
        hybrid_cultural,
        shared_root_pairs,
        unresolved,
    )
    return ContactHybridPracticeResult(
        hybrid_practical_knowledge_count=hybrid_practical,
        intercommunity_combination_count=intercommunity_combination,
        hybrid_cultural_belief_count=hybrid_cultural,
        narrative_shared_root_pair_count=shared_root_pairs,
        narrative_merge_count=narrative_merge,
        resolvable_lineage_entry_count=resolvable,
        unresolved_lineage_count=unresolved,
        coverage=coverage,
    )


def compute_contact_hybrid_practice_metric(
    result: ContactHybridPracticeResult,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    spec = metric_specification(MetricFamilyId.CONTACT_HYBRID_PRACTICE)
    denominator = result.resolvable_lineage_entry_count
    values: dict[str, object] = {
        "hybrid_practical_knowledge_count": result.hybrid_practical_knowledge_count,
        "intercommunity_combination_count": result.intercommunity_combination_count,
        "hybrid_cultural_belief_count": result.hybrid_cultural_belief_count,
        "narrative_shared_root_pair_count": result.narrative_shared_root_pair_count,
        "narrative_merge_count": result.narrative_merge_count,
        "resolvable_lineage_entry_count": denominator,
        "unresolved_lineage_count": result.unresolved_lineage_count,
    }
    if denominator:
        values["hybridization_rate"] = quantize_float(
            require_finite(
                (
                    result.hybrid_practical_knowledge_count
                    + result.hybrid_cultural_belief_count
                )
                / denominator
            )
        )
    availability = (
        MetricAvailability.ABSENT if not denominator else MetricAvailability.PRESENT
    )
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
            source_kind="contact_hybrid_practice",
            source_ids=(),
            notes_code="descriptive_contact_association",
        ),
    )
