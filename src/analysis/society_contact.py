"""Cross-candidate-community contact exposure and closed interaction mix."""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from collections.abc import Sequence
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
    "CONTACT_INTERACTION_KINDS",
    "SOCIETY_CONTACT_METRIC_VERSION",
    "ContactEpisodeRow",
    "ContactInteractionRow",
    "ContactKinshipRow",
    "ContactPairRow",
    "ContactPresenceRow",
    "SocietyContactError",
    "SocietyContactResult",
    "compute_society_contact",
    "compute_society_contact_metric",
]

SOCIETY_CONTACT_METRIC_VERSION: Final[str] = "society_contact@1"
CONTACT_INTERACTION_KINDS: Final[tuple[str, ...]] = (
    "communication",
    "exchange",
    "teaching",
    "cooperation",
    "conflict",
    "kinship",
)
_COLLECTIVE_KINDS: Final[frozenset[str]] = frozenset(
    {"collective_project_contribution", "public_good_maintenance"}
)
_LOG: Final[logging.Logger] = logging.getLogger("analysis.society_contact")


class SocietyContactError(ValueError):
    def __init__(self, reason_code: str) -> None:
        self.reason_code = require_stable_id("reason_code", reason_code)
        super().__init__(reason_code)


def _person(value: object, field_name: str) -> str:
    return require_stable_id(field_name, value)


def _tick(value: object) -> int:
    return require_exact_nonneg_int("tick", value)


@dataclass(frozen=True, slots=True)
class ContactEpisodeRow:
    """One detached neutral contact occurrence."""

    participant_ids: tuple[str, ...]
    present_ids: tuple[str, ...]
    location_id: str
    tick: int

    def __post_init__(self) -> None:
        for name in ("participant_ids", "present_ids"):
            rows = getattr(self, name)
            if (
                isinstance(rows, (str, bytes))
                or not isinstance(rows, Sequence)
                or not rows
            ):
                raise SocietyContactError("invalid_contact_ids")
            values = tuple(_person(item, name) for item in rows)
            if tuple(sorted(values)) != values or len(set(values)) != len(values):
                raise SocietyContactError("unsorted_contact_ids")
            object.__setattr__(self, name, values)
        if set(self.participant_ids) & set(self.present_ids):
            raise SocietyContactError("overlapping_contact_ids")
        object.__setattr__(
            self, "location_id", require_stable_id("location_id", self.location_id)
        )
        object.__setattr__(self, "tick", _tick(self.tick))


@dataclass(frozen=True, slots=True)
class ContactPresenceRow:
    person_id: str
    location_id: str
    tick: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "person_id", require_stable_id("person_id", self.person_id)
        )
        object.__setattr__(
            self, "location_id", require_stable_id("location_id", self.location_id)
        )
        object.__setattr__(self, "tick", _tick(self.tick))


@dataclass(frozen=True, slots=True)
class ContactInteractionRow:
    kind: str
    actor_person_id: str
    counterparty_person_id: str | None
    tick: int
    participant_person_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        kind = require_stable_id("kind", self.kind)
        if kind not in CONTACT_INTERACTION_KINDS + tuple(_COLLECTIVE_KINDS):
            raise SocietyContactError("unknown_interaction_kind")
        object.__setattr__(self, "kind", kind)
        object.__setattr__(
            self,
            "actor_person_id",
            require_stable_id("actor_person_id", self.actor_person_id),
        )
        if self.counterparty_person_id is not None:
            object.__setattr__(
                self,
                "counterparty_person_id",
                require_stable_id(
                    "counterparty_person_id", self.counterparty_person_id
                ),
            )
        object.__setattr__(self, "tick", _tick(self.tick))
        for item in self.participant_person_ids:
            require_stable_id("participant_person_id", item)


@dataclass(frozen=True, slots=True)
class ContactKinshipRow:
    parent_person_id: str
    child_person_id: str
    tick: int

    def __post_init__(self) -> None:
        parent = require_stable_id("parent_person_id", self.parent_person_id)
        child = require_stable_id("child_person_id", self.child_person_id)
        if parent == child:
            raise SocietyContactError("self_kinship_edge")
        object.__setattr__(self, "parent_person_id", parent)
        object.__setattr__(self, "child_person_id", child)
        object.__setattr__(self, "tick", _tick(self.tick))


@dataclass(frozen=True, slots=True)
class ContactPairRow:
    community_a_id: str
    community_b_id: str
    onset_tick: int
    contact_event_count: int
    location_tick_count: int
    cross_community_person_ticks: int
    interaction_counts: tuple[tuple[str, int], ...]
    cross_community_kinship_edge_count: int

    def __post_init__(self) -> None:
        if self.community_a_id >= self.community_b_id:
            raise SocietyContactError("pair_order_invalid")
        for name in (
            "onset_tick",
            "contact_event_count",
            "location_tick_count",
            "cross_community_person_ticks",
            "cross_community_kinship_edge_count",
        ):
            object.__setattr__(self, name, _tick(getattr(self, name)))

    def interaction_count(self, kind: str) -> int:
        return dict(self.interaction_counts).get(kind, 0)


@dataclass(frozen=True, slots=True)
class SocietyContactResult:
    pairs: tuple[ContactPairRow, ...]
    coverage: MetricCoverage
    unassigned_person_count: int = 0
    collective_project_contribution_count: int = 0
    public_good_maintenance_count: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "pairs",
            tuple(
                sorted(
                    self.pairs,
                    key=lambda item: (item.community_a_id, item.community_b_id),
                )
            ),
        )
        if type(self.coverage) is not MetricCoverage:
            raise SocietyContactError("invalid_coverage")


def _pair_key(left: str, right: str) -> tuple[str, str]:
    return (left, right) if left < right else (right, left)


def _community_map(
    communities: Sequence[CandidateCommunityRow],
) -> tuple[dict[str, str], int]:
    owner: dict[str, str] = {}
    for community in communities:
        for person in community.person_ids:
            if person in owner:
                raise SocietyContactError("duplicate_person_across_communities")
            owner[person] = community.community_id
    return owner, 0


def compute_society_contact(
    communities: Sequence[CandidateCommunityRow],
    *,
    episodes: Sequence[ContactEpisodeRow] = (),
    presence: Sequence[ContactPresenceRow] = (),
    interactions: Sequence[ContactInteractionRow] = (),
    kinship: Sequence[ContactKinshipRow] = (),
) -> SocietyContactResult:
    community_rows = tuple(communities)
    if any(type(item) is not CandidateCommunityRow for item in community_rows):
        raise SocietyContactError("invalid_communities")
    owner, _ = _community_map(community_rows)

    location_presence: dict[tuple[int, str], list[str]] = defaultdict(list)
    for presence_row in presence:
        if type(presence_row) is not ContactPresenceRow:
            raise SocietyContactError("invalid_presence_row")
        location_presence[(presence_row.tick, presence_row.location_id)].append(
            presence_row.person_id
        )

    pair_events: Counter[tuple[str, str]] = Counter()
    pair_onset: dict[tuple[str, str], int] = {}
    for episode_row in episodes:
        if type(episode_row) is not ContactEpisodeRow:
            raise SocietyContactError("invalid_episode_row")
        members = tuple(
            sorted(
                {
                    owner[person]
                    for person in (
                        *episode_row.participant_ids,
                        *episode_row.present_ids,
                    )
                    if person in owner
                }
            )
        )
        for left_index, left in enumerate(members):
            for right in members[left_index + 1 :]:
                key = _pair_key(left, right)
                pair_events[key] += 1
                pair_onset[key] = min(
                    pair_onset.get(key, episode_row.tick), episode_row.tick
                )

    location_ticks: Counter[tuple[str, str]] = Counter()
    person_ticks: Counter[tuple[str, str]] = Counter()
    for (tick, _location), persons in location_presence.items():
        by_community: dict[str, set[str]] = defaultdict(set)
        for person in persons:
            community = owner.get(person)
            if community is not None:
                by_community[community].add(person)
        communities_here = sorted(by_community)
        for left_index, left in enumerate(communities_here):
            for right in communities_here[left_index + 1 :]:
                key = _pair_key(left, right)
                location_ticks[key] += 1
                person_ticks[key] += len(by_community[left]) + len(by_community[right])
                pair_onset[key] = min(pair_onset.get(key, tick), tick)

    interaction_counts: Counter[tuple[tuple[str, str], str]] = Counter()
    collective_counts: Counter[str] = Counter()
    for interaction_row in interactions:
        if type(interaction_row) is not ContactInteractionRow:
            raise SocietyContactError("invalid_interaction_row")
        if interaction_row.kind in _COLLECTIVE_KINDS:
            actor_community = owner.get(interaction_row.actor_person_id)
            participant_communities = {
                owner.get(item) for item in interaction_row.participant_person_ids
            }
            if (
                actor_community is not None
                and None not in participant_communities
                and participant_communities - {actor_community}
            ):
                collective_counts[interaction_row.kind] += 1
            continue
        if interaction_row.counterparty_person_id is None:
            continue
        actor_community = owner.get(interaction_row.actor_person_id)
        counterparty_community = owner.get(interaction_row.counterparty_person_id)
        if (
            actor_community is None
            or counterparty_community is None
            or actor_community == counterparty_community
        ):
            continue
        key = _pair_key(actor_community, counterparty_community)
        interaction_counts[(key, interaction_row.kind)] += 1
        pair_onset[key] = min(
            pair_onset.get(key, interaction_row.tick), interaction_row.tick
        )

    kinship_counts: Counter[tuple[str, str]] = Counter()
    for kinship_edge in kinship:
        if type(kinship_edge) is not ContactKinshipRow:
            raise SocietyContactError("invalid_kinship_row")
        parent_community = owner.get(kinship_edge.parent_person_id)
        child_community = owner.get(kinship_edge.child_person_id)
        if (
            parent_community is None
            or child_community is None
            or parent_community == child_community
        ):
            continue
        key = _pair_key(parent_community, child_community)
        kinship_counts[key] += 1
        pair_onset[key] = min(pair_onset.get(key, kinship_edge.tick), kinship_edge.tick)

    keys = sorted(set(pair_onset))
    pairs = tuple(
        ContactPairRow(
            community_a_id=key[0],
            community_b_id=key[1],
            onset_tick=pair_onset[key],
            contact_event_count=pair_events[key],
            location_tick_count=location_ticks[key],
            cross_community_person_ticks=person_ticks[key],
            interaction_counts=tuple(
                (kind, interaction_counts[(key, kind)])
                for kind in CONTACT_INTERACTION_KINDS
                if interaction_counts[(key, kind)]
            ),
            cross_community_kinship_edge_count=kinship_counts[key],
        )
        for key in keys
    )
    assessed = sum(1 for row in presence if row.person_id in owner)
    expected = len(tuple(presence))
    coverage = MetricCoverage(
        observed=assessed,
        expected=expected,
        ratio=(
            quantize_float(require_finite(assessed / expected)) if expected else None
        ),
    )
    unassigned = len({row.person_id for row in presence if row.person_id not in owner})
    result = SocietyContactResult(
        pairs=pairs,
        coverage=coverage,
        unassigned_person_count=unassigned,
        collective_project_contribution_count=collective_counts[
            "collective_project_contribution"
        ],
        public_good_maintenance_count=collective_counts["public_good_maintenance"],
    )
    _LOG.info(
        "society_contact_computed pair_count=%s episode_count=%s preset_people=%s",
        len(pairs),
        len(tuple(episodes)),
        expected,
    )
    return result


def compute_society_contact_metric(
    result: SocietyContactResult,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    if type(result) is not SocietyContactResult:
        raise SocietyContactError("invalid_contact_result")
    spec = metric_specification(MetricFamilyId.SOCIETY_CONTACT)
    totals = {
        kind: sum(pair.interaction_count(kind) for pair in result.pairs)
        for kind in CONTACT_INTERACTION_KINDS
    }
    values: dict[str, object] = {
        "contact_event_count": sum(pair.contact_event_count for pair in result.pairs),
        "contact_pair_count": len(result.pairs),
        "contact_location_tick_count": sum(
            pair.location_tick_count for pair in result.pairs
        ),
        "cross_community_person_ticks": sum(
            pair.cross_community_person_ticks for pair in result.pairs
        ),
        "cross_community_kinship_edge_count": sum(
            pair.cross_community_kinship_edge_count for pair in result.pairs
        ),
        "communication_count": totals["communication"],
        "exchange_count": totals["exchange"],
        "teaching_count": totals["teaching"],
        "cooperation_count": totals["cooperation"],
        "conflict_count": totals["conflict"],
        "collective_project_contribution_count": (
            result.collective_project_contribution_count
        ),
        "public_good_maintenance_count": result.public_good_maintenance_count,
        "unassigned_person_count": result.unassigned_person_count,
    }
    availability = (
        MetricAvailability.ABSENT if not result.pairs else MetricAvailability.PRESENT
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
            source_kind="society_contact",
            source_ids=(),
            notes_code="descriptive_contact_association",
        ),
    )
