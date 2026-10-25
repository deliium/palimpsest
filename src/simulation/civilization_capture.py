"""Whitelisted civilization event evidence; never retain objective event bodies.

The event lane is independent of sampled owner/physical boundary inventories.
An examined irrelevant event counts towards source coverage, not towards trade,
migration or cultural transmission. Source uncertainty is never known-empty.
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Literal

from simulation.civilization_models import (
    CivilizationCoverage,
    CivilizationCoverageState,
    CivilizationError,
    _count,
    _id,
)
from simulation.lifecycle import TickResult
from world.events import (
    ArtifactCreated,
    ArtifactModified,
    ExchangeCompleted,
    Given,
    JourneyArrived,
    JourneyEnded,
    JourneyStarted,
    ProjectAbandoned,
    ProjectCompleted,
    ProjectContributed,
    ProjectCreated,
    ProjectShortage,
    PublicGoodBenefit,
    PublicGoodMaintained,
    PublicGoodOpposed,
    RepositoryMemberDeposited,
    RepositoryMemberRetrieved,
    WorldEvent,
)
from world.values import ItemKind

__all__ = [
    "CivilizationCaptureOptions",
    "CivilizationError",
    "CivilizationEventBatch",
    "CivilizationEventKind",
    "CivilizationEventReceipt",
    "CivilizationGroundingObservation",
    "CivilizationGroundingProject",
    "CivilizationGroundingRepository",
    "CivilizationInventoryChannel",
    "CivilizationInventoryCoverage",
    "CivilizationOwnerConcept",
    "CivilizationOwnerConceptEvidence",
    "CivilizationOwnerDecaySample",
    "CivilizationOwnerGroup",
    "CivilizationOwnerInventory",
    "CivilizationOwnerKnowledge",
    "CivilizationOwnerOffice",
    "CivilizationOwnerTrait",
    "CivilizationReceiptItem",
    "InstitutionGroundingWitness",
    "civilization_event_bytes",
    "civilization_event_receipt",
    "civilization_events_from_result",
    "institution_grounding_witnesses",
    "project_civilization_events",
    "project_grounding_observation",
    "recover_civilization_events",
    "unavailable_civilization_events",
]

_LOG = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CivilizationCaptureOptions:
    """Composition-only; never a runner JSON field or a capability flag."""

    enabled: bool = False
    cadence: int = 1
    max_boundaries: int = 10_000
    max_rows: int = 1_000_000
    max_bytes: int = 268_435_456

    def __post_init__(self) -> None:
        if type(self.enabled) is not bool:
            raise CivilizationError()
        if _count(self.cadence) < 1:
            raise CivilizationError()
        for name, maximum in (
            ("max_boundaries", 10_000),
            ("max_rows", 1_000_000),
            ("max_bytes", 268_435_456),
        ):
            value = _count(getattr(self, name))
            if not 1 <= value <= maximum:
                raise CivilizationError()


class CivilizationEventKind(StrEnum):
    EXCHANGE_COMPLETED = "exchange_completed"
    GIVE = "give"
    JOURNEY_STARTED = "journey_started"
    JOURNEY_ARRIVED = "journey_arrived"
    JOURNEY_ENDED = "journey_ended"
    PROJECT_CREATED = "project_created"
    PROJECT_CONTRIBUTED = "project_contributed"
    PROJECT_SHORTAGE = "project_shortage"
    PROJECT_COMPLETED = "project_completed"
    PROJECT_ABANDONED = "project_abandoned"
    PUBLIC_GOOD_BENEFIT = "public_good_benefit"
    PUBLIC_GOOD_MAINTAINED = "public_good_maintained"
    PUBLIC_GOOD_OPPOSED = "public_good_opposed"
    REPOSITORY_MEMBER_DEPOSITED = "repository_member_deposited"
    REPOSITORY_MEMBER_RETRIEVED = "repository_member_retrieved"
    ARTIFACT_CREATED = "artifact_created"
    ARTIFACT_MODIFIED = "artifact_modified"


@dataclass(frozen=True, slots=True)
class CivilizationReceiptItem:
    item_id: str
    kind: ItemKind | None
    direction: Literal["give", "take", "transfer"]

    def __post_init__(self) -> None:
        _id(self.item_id)
        if self.kind is not None and type(self.kind) is not ItemKind:
            raise CivilizationError()
        if self.direction not in {"give", "take", "transfer"}:
            raise CivilizationError()


@dataclass(frozen=True, slots=True)
class CivilizationEventReceipt:
    run_id: str
    event_id: str
    tick: int
    sequence: int
    kind: CivilizationEventKind
    participant_ids: tuple[str, ...] = ()
    origin_location_id: str | None = None
    destination_location_id: str | None = None
    origin_region_id: str | None = None
    destination_region_id: str | None = None
    journey_id: str | None = None
    project_id: str | None = None
    repository_id: str | None = None
    record_id: str | None = None
    structure_id: str | None = None
    items: tuple[CivilizationReceiptItem, ...] = ()
    outcome: (
        Literal[
            "completed",
            "arrived",
            "participant_dead",
            "arrival_timeout",
            "accepted",
            "rejected",
        ]
        | None
    ) = None

    def __post_init__(self) -> None:
        for value in (self.run_id, self.event_id):
            _id(value)
        _count(self.tick)
        _count(self.sequence)
        if type(self.kind) is not CivilizationEventKind:
            raise CivilizationError()
        for name in (
            "origin_location_id",
            "destination_location_id",
            "origin_region_id",
            "destination_region_id",
            "journey_id",
            "project_id",
            "repository_id",
            "record_id",
            "structure_id",
        ):
            value = getattr(self, name)
            if value is not None:
                _id(value)
        participants = tuple(self.participant_ids)
        items = tuple(self.items)
        if len(participants) > 64 or len(set(participants)) != len(participants):
            raise CivilizationError()
        for value in participants:
            _id(value)
        if len(items) > 64 or any(
            type(item) is not CivilizationReceiptItem for item in items
        ):
            raise CivilizationError()
        if len({item.item_id for item in items}) != len(items):
            raise CivilizationError()
        allowed = {
            None,
            "completed",
            "arrived",
            "participant_dead",
            "arrival_timeout",
            "accepted",
            "rejected",
        }
        if self.outcome not in allowed:
            raise CivilizationError()
        outcomes: dict[CivilizationEventKind, set[str | None]] = {
            CivilizationEventKind.EXCHANGE_COMPLETED: {"completed"},
            CivilizationEventKind.JOURNEY_ARRIVED: {"arrived"},
            CivilizationEventKind.JOURNEY_ENDED: {
                "participant_dead",
                "arrival_timeout",
            },
            CivilizationEventKind.PROJECT_CONTRIBUTED: {"accepted", "rejected"},
            CivilizationEventKind.PUBLIC_GOOD_MAINTAINED: {"accepted", "rejected"},
            CivilizationEventKind.PROJECT_COMPLETED: {"completed"},
        }
        if self.outcome not in outcomes.get(self.kind, {None}):
            raise CivilizationError()
        if self.kind is CivilizationEventKind.EXCHANGE_COMPLETED:
            if (
                self.outcome != "completed"
                or len(participants) != 2
                or {item.direction for item in items} != {"give", "take"}
                or any(item.kind is None for item in items)
            ):
                raise CivilizationError()
        if self.kind in {
            CivilizationEventKind.JOURNEY_STARTED,
            CivilizationEventKind.JOURNEY_ARRIVED,
            CivilizationEventKind.JOURNEY_ENDED,
        }:
            if (
                self.journey_id is None
                or not participants
                or self.origin_location_id is None
                or self.destination_location_id is None
            ):
                raise CivilizationError()
        object.__setattr__(self, "participant_ids", participants)
        object.__setattr__(self, "items", items)


@dataclass(frozen=True, slots=True)
class CivilizationEventBatch:
    """Coverage for one finalized tick, independent of inventory cadence.

    No hashes of discarded private payloads are retained. The source high water
    is described by the tick and expected count, not by an empty TickResult.
    """

    run_id: str
    tick: int
    source: Literal["committed_result", "journal", "unavailable"]
    expected_count: int | None
    examined_count: int
    receipts: tuple[CivilizationEventReceipt, ...]
    coverage: CivilizationCoverage

    def __post_init__(self) -> None:
        _id(self.run_id)
        _count(self.tick)
        _count(self.examined_count)
        if self.expected_count is not None:
            _count(self.expected_count)
        if self.source not in {"committed_result", "journal", "unavailable"}:
            raise CivilizationError()
        if type(self.coverage) is not CivilizationCoverage:
            raise CivilizationError()
        values = tuple(self.receipts)
        if len(values) > self.examined_count:
            raise CivilizationError()
        for receipt in values:
            if (
                type(receipt) is not CivilizationEventReceipt
                or receipt.run_id != self.run_id
                or receipt.tick != self.tick
                or receipt.sequence >= self.examined_count
            ):
                raise CivilizationError()
        if len({r.event_id for r in values}) != len(values) or [
            r.sequence for r in values
        ] != sorted({r.sequence for r in values}):
            raise CivilizationError()
        if self.coverage.state is CivilizationCoverageState.COMPLETE:
            if (
                self.source == "unavailable"
                or self.expected_count != self.examined_count
            ):
                raise CivilizationError()
        if self.source == "unavailable" and values:
            raise CivilizationError()
        if (
            self.coverage.observed_count is not None
            and self.coverage.observed_count != self.examined_count
        ):
            raise CivilizationError()
        if self.coverage.expected_count != self.expected_count:
            raise CivilizationError()
        object.__setattr__(self, "receipts", values)


class CivilizationInventoryChannel(StrEnum):
    """Closed owner-evidence lanes captured at a finalized boundary."""

    CULTURAL_FEATURES = "cultural_features"
    TERMINOLOGY = "terminology"
    NARRATIVES = "narratives"
    PRACTICAL_KNOWLEDGE = "practical_knowledge"
    GROUPS = "groups"
    INSTITUTION_CONCEPTS = "institution_concepts"
    OFFICES = "offices"
    INSTITUTIONAL_DECAY = "institutional_decay"


_INVENTORY_CHANNELS: frozenset[str] = frozenset(
    channel.value for channel in CivilizationInventoryChannel
)


def _unit(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CivilizationError()
    number = float(value)
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        raise CivilizationError()
    return number


@dataclass(frozen=True, slots=True)
class CivilizationOwnerTrait:
    """Identity only; never a private label token or narrative content."""

    trait_id: str
    representation_id: str
    acquired_tick: int
    updated_tick: int

    def __post_init__(self) -> None:
        _id(self.trait_id)
        _id(self.representation_id)
        _count(self.acquired_tick)
        _count(self.updated_tick)
        if self.updated_tick < self.acquired_tick:
            raise CivilizationError()


@dataclass(frozen=True, slots=True)
class CivilizationOwnerKnowledge:
    """Selected metadata from one owner's practical-knowledge ledger."""

    entry_id: str
    kind: str
    content_key: str
    origin: str
    parent_entry_ids: tuple[str, ...]
    lineage_root_id: str
    hop_index: int
    mutated: bool
    evidence_refs: tuple[str, ...]
    acquired_tick: int
    active: bool
    capability_anchor: str | None
    source_agent_id: str | None
    teacher_agent_id: str | None

    def __post_init__(self) -> None:
        for value in (
            self.entry_id,
            self.kind,
            self.content_key,
            self.origin,
            self.lineage_root_id,
        ):
            _id(value)
        _count(self.hop_index)
        _count(self.acquired_tick)
        if type(self.mutated) is not bool or type(self.active) is not bool:
            raise CivilizationError()
        for name in ("parent_entry_ids", "evidence_refs"):
            values = tuple(getattr(self, name))
            if len(values) > 64 or len(set(values)) != len(values):
                raise CivilizationError()
            for value in values:
                _id(value)
            object.__setattr__(self, name, values)
        for optional_value in (
            self.capability_anchor,
            self.source_agent_id,
            self.teacher_agent_id,
        ):
            if optional_value is not None:
                _id(optional_value)


@dataclass(frozen=True, slots=True)
class CivilizationOwnerGroup:
    """One owner-qualified native membership belief or concept."""

    belief_id: str
    stance: str
    member_ids: tuple[str, ...]
    support: float
    social_evidence: bool
    status: str
    concept_id: str | None

    def __post_init__(self) -> None:
        _id(self.belief_id)
        _id(self.stance)
        _id(self.status)
        members = tuple(self.member_ids)
        if len(members) > 64 or len(set(members)) != len(members):
            raise CivilizationError()
        for value in members:
            _id(value)
        object.__setattr__(self, "member_ids", members)
        object.__setattr__(self, "support", _unit(self.support))
        if type(self.social_evidence) is not bool:
            raise CivilizationError()
        if self.concept_id is not None:
            _id(self.concept_id)


@dataclass(frozen=True, slots=True)
class CivilizationOwnerConceptEvidence:
    """Native evidence identity needed to resolve an exact physical witness."""

    evidence_id: str
    tick: int
    channel: str
    pattern: str
    lineage_ref: str
    actor_id: str | None

    def __post_init__(self) -> None:
        _id(self.evidence_id)
        _count(self.tick)
        _id(self.channel)
        _id(self.pattern)
        _id(self.lineage_ref)
        if self.actor_id is not None:
            _id(self.actor_id)


@dataclass(frozen=True, slots=True)
class CivilizationOwnerConcept:
    concept_id: str
    status: str
    conceptualization: str
    evidence_count: int
    first_tick: int
    last_tick: int
    evidence: tuple[CivilizationOwnerConceptEvidence, ...]

    def __post_init__(self) -> None:
        _id(self.concept_id)
        _id(self.status)
        _id(self.conceptualization)
        _count(self.evidence_count)
        _count(self.first_tick)
        _count(self.last_tick)
        if self.last_tick < self.first_tick:
            raise CivilizationError()
        values = tuple(self.evidence)
        if len(values) > 64:
            raise CivilizationError()
        for value in values:
            if type(value) is not CivilizationOwnerConceptEvidence:
                raise CivilizationError()
        if len({value.evidence_id for value in values}) != len(values):
            raise CivilizationError()
        object.__setattr__(self, "evidence", values)


@dataclass(frozen=True, slots=True)
class CivilizationOwnerOffice:
    office_id: str
    status: str
    function: str
    first_tick: int
    last_tick: int
    recognized: bool
    coverage: str

    def __post_init__(self) -> None:
        for value in (self.office_id, self.status, self.function, self.coverage):
            _id(value)
        _count(self.first_tick)
        _count(self.last_tick)
        if self.last_tick < self.first_tick or type(self.recognized) is not bool:
            raise CivilizationError()


@dataclass(frozen=True, slots=True)
class CivilizationOwnerDecaySample:
    """One bounded raw decay sample, independent of later native eviction."""

    local_pattern_id: str
    group_key: str
    concept_id: str
    inception_tick: int
    observation_tick: int
    source_first_tick: int
    source_last_tick: int
    role_recognition: float
    procedure_recurrence: float
    social_expectation: float
    legitimacy_belief: float
    succession_observed: float
    generational_continuity: float
    recognized: bool
    covered: bool
    pruned: bool
    anchor_digests: tuple[str, ...]
    structural_components: tuple[str, ...]
    context_key: str | None
    office_id: str | None
    observed_cohort: tuple[str, ...] = ()
    supporters: tuple[tuple[str, str], ...] = ()
    participant_actions: tuple[tuple[str, str], ...] = ()
    performed_procedure_keys: tuple[str, ...] = ()
    succession_transitions: tuple[str, ...] = ()
    completed_transitions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for value in (
            self.local_pattern_id,
            self.group_key,
            self.concept_id,
        ):
            _id(value)
        _count(self.inception_tick)
        _count(self.observation_tick)
        _count(self.source_first_tick)
        _count(self.source_last_tick)
        if (
            self.source_first_tick > self.source_last_tick
            or self.source_last_tick > self.observation_tick
            or self.inception_tick > self.observation_tick
        ):
            raise CivilizationError()
        for name in (
            "role_recognition",
            "procedure_recurrence",
            "social_expectation",
            "legitimacy_belief",
            "succession_observed",
            "generational_continuity",
        ):
            object.__setattr__(self, name, _unit(getattr(self, name)))
        if any(
            type(value) is not bool
            for value in (self.recognized, self.covered, self.pruned)
        ):
            raise CivilizationError()
        for name in ("anchor_digests", "structural_components"):
            values = tuple(getattr(self, name))
            if len(values) > 64 or len(set(values)) != len(values):
                raise CivilizationError()
            for value in values:
                _id(value)
            object.__setattr__(self, name, values)
        for optional_value in (self.context_key, self.office_id):
            if optional_value is not None:
                _id(optional_value)
        cohort = tuple(self.observed_cohort)
        if len(cohort) > 64 or len(set(cohort)) != len(cohort):
            raise CivilizationError()
        for value in cohort:
            _id(value)
        object.__setattr__(self, "observed_cohort", cohort)
        for name in ("supporters", "participant_actions"):
            values = tuple(getattr(self, name))
            if len(values) > 64:
                raise CivilizationError()
            for pair in values:
                if type(pair) is not tuple or len(pair) != 2:
                    raise CivilizationError()
                _id(pair[0])
                _id(pair[1])
            object.__setattr__(self, name, values)
        for name in (
            "performed_procedure_keys",
            "succession_transitions",
            "completed_transitions",
        ):
            values = tuple(getattr(self, name))
            if len(values) > 64 or len(set(values)) != len(values):
                raise CivilizationError()
            for value in values:
                _id(value)
            object.__setattr__(self, name, values)


@dataclass(frozen=True, slots=True)
class CivilizationInventoryCoverage:
    channel: CivilizationInventoryChannel
    coverage: CivilizationCoverage

    def __post_init__(self) -> None:
        if (
            type(self.channel) is not CivilizationInventoryChannel
            or type(self.coverage) is not CivilizationCoverage
        ):
            raise CivilizationError()


@dataclass(frozen=True, slots=True)
class CivilizationOwnerInventory:
    """Detached metadata-only inventory for one owner at one boundary."""

    owner_id: str
    generation_index: int
    living: bool
    channels: tuple[CivilizationInventoryCoverage, ...]
    cultural_traits: tuple[CivilizationOwnerTrait, ...] = ()
    terminology: tuple[CivilizationOwnerTrait, ...] = ()
    narratives: tuple[CivilizationOwnerTrait, ...] = ()
    knowledge: tuple[CivilizationOwnerKnowledge, ...] = ()
    groups: tuple[CivilizationOwnerGroup, ...] = ()
    concepts: tuple[CivilizationOwnerConcept, ...] = ()
    offices: tuple[CivilizationOwnerOffice, ...] = ()
    decay_samples: tuple[CivilizationOwnerDecaySample, ...] = ()

    def __post_init__(self) -> None:
        _id(self.owner_id)
        _count(self.generation_index)
        if type(self.living) is not bool:
            raise CivilizationError()
        channels = tuple(self.channels)
        if (
            len(channels) != len(CivilizationInventoryChannel)
            or len({row.channel for row in channels}) != len(channels)
            or {row.channel for row in channels} != set(CivilizationInventoryChannel)
        ):
            raise CivilizationError()
        for row in channels:
            if type(row) is not CivilizationInventoryCoverage:
                raise CivilizationError()
        by_channel = {row.channel: row.coverage for row in channels}
        for name, expected in (
            ("cultural_traits", CivilizationOwnerTrait),
            ("terminology", CivilizationOwnerTrait),
            ("narratives", CivilizationOwnerTrait),
            ("knowledge", CivilizationOwnerKnowledge),
            ("groups", CivilizationOwnerGroup),
            ("concepts", CivilizationOwnerConcept),
            ("offices", CivilizationOwnerOffice),
            ("decay_samples", CivilizationOwnerDecaySample),
        ):
            values = tuple(getattr(self, name))
            if any(type(value) is not expected for value in values):
                raise CivilizationError()
            object.__setattr__(self, name, values)
        for channel, name in (
            (CivilizationInventoryChannel.CULTURAL_FEATURES, "cultural_traits"),
            (CivilizationInventoryChannel.TERMINOLOGY, "terminology"),
            (CivilizationInventoryChannel.NARRATIVES, "narratives"),
            (CivilizationInventoryChannel.PRACTICAL_KNOWLEDGE, "knowledge"),
            (CivilizationInventoryChannel.GROUPS, "groups"),
            (CivilizationInventoryChannel.INSTITUTION_CONCEPTS, "concepts"),
            (CivilizationInventoryChannel.OFFICES, "offices"),
            (CivilizationInventoryChannel.INSTITUTIONAL_DECAY, "decay_samples"),
        ):
            coverage = by_channel[channel]
            if coverage.state is not CivilizationCoverageState.COMPLETE and getattr(
                self, name
            ):
                raise CivilizationError()
        object.__setattr__(self, "channels", channels)
        if len({concept.concept_id for concept in self.concepts}) != len(self.concepts):
            raise CivilizationError()
        if len({office.office_id for office in self.offices}) != len(self.offices):
            raise CivilizationError()
        seen_samples: dict[tuple[str, int], CivilizationOwnerDecaySample] = {}
        for sample in self.decay_samples:
            key = (sample.local_pattern_id, sample.observation_tick)
            if key in seen_samples and seen_samples[key] != sample:
                raise CivilizationError()
            seen_samples[key] = sample


@dataclass(frozen=True, slots=True)
class CivilizationGroundingProject:
    project_id: str
    location_id: str
    accepted_contributions: tuple[tuple[int, int], ...]

    def __post_init__(self) -> None:
        _id(self.project_id)
        _id(self.location_id)
        rows = tuple(self.accepted_contributions)
        if len(rows) > 64:
            raise CivilizationError()
        for ordinal, tick in rows:
            _count(ordinal)
            _count(tick)
        object.__setattr__(self, "accepted_contributions", rows)


@dataclass(frozen=True, slots=True)
class CivilizationGroundingRepository:
    repository_id: str
    location_id: str
    founder_count: int

    def __post_init__(self) -> None:
        _id(self.repository_id)
        _id(self.location_id)
        _count(self.founder_count)


@dataclass(frozen=True, slots=True)
class CivilizationGroundingObservation:
    """Tick-local observable ordinals; released before the next boundary."""

    owner_id: str
    tick: int
    projects: tuple[CivilizationGroundingProject, ...]
    repositories: tuple[CivilizationGroundingRepository, ...]

    def __post_init__(self) -> None:
        _id(self.owner_id)
        _count(self.tick)
        projects = tuple(self.projects)
        repositories = tuple(self.repositories)
        if any(
            type(row) is not CivilizationGroundingProject for row in projects
        ) or any(
            type(row) is not CivilizationGroundingRepository for row in repositories
        ):
            raise CivilizationError()
        object.__setattr__(self, "projects", projects)
        object.__setattr__(self, "repositories", repositories)


@dataclass(frozen=True, slots=True)
class InstitutionGroundingWitness:
    """Exact observed physical evidence for one owner concept; never a guess."""

    owner_id: str
    concept_id: str
    evidence_id: str
    evidence_tick: int
    source_kind: Literal["project", "repository"]
    source_id: str
    location_id: str

    def __post_init__(self) -> None:
        for value in (
            self.owner_id,
            self.concept_id,
            self.evidence_id,
            self.source_id,
            self.location_id,
        ):
            _id(value)
        _count(self.evidence_tick)
        if self.source_kind not in {"project", "repository"}:
            raise CivilizationError()


def project_grounding_observation(
    owner_id: str, observation: object
) -> CivilizationGroundingObservation:
    """Copy only IDs/ordinals needed to resolve native observed evidence."""
    _id(owner_id)
    tick = getattr(observation, "tick", None)
    if type(tick) is not int:
        raise CivilizationError()
    _count(tick)
    projects: list[CivilizationGroundingProject] = []
    for project in getattr(observation, "collective_projects", ()) or ():
        accepted: list[tuple[int, int]] = []
        for ordinal, contribution in enumerate(
            getattr(project, "contributions", ()) or ()
        ):
            if not getattr(contribution, "accepted", False):
                continue
            contribution_tick = getattr(contribution, "tick", None)
            if type(contribution_tick) is not int:
                raise CivilizationError()
            accepted.append((ordinal, contribution_tick))
        projects.append(
            CivilizationGroundingProject(
                _raw_id(getattr(project, "project_id", None)),
                _raw_id(getattr(project, "location_id", None)),
                tuple(accepted),
            )
        )
    repositories: list[CivilizationGroundingRepository] = []
    for repository in getattr(observation, "repositories", ()) or ():
        founders = getattr(repository, "founder_ids", None) or ()
        repositories.append(
            CivilizationGroundingRepository(
                _raw_id(getattr(repository, "repository_id", None)),
                _raw_id(getattr(repository, "location_id", None)),
                len(founders),
            )
        )
    return CivilizationGroundingObservation(
        owner_id, tick, tuple(projects), tuple(repositories)
    )


def _raw_id(value: object) -> str:
    raw = getattr(value, "value", value)
    return _id(raw)


def institution_grounding_witnesses(
    inventories: tuple[CivilizationOwnerInventory, ...],
    observations: tuple[CivilizationGroundingObservation, ...],
    *,
    complete: bool,
) -> tuple[tuple[InstitutionGroundingWitness, ...], CivilizationCoverage]:
    """Resolve only exact OBSERVED project/repository ordinals from the same tick.

    Missing observations mean an absent witness, never inferred placement.
    """
    if any(
        type(value) is not CivilizationOwnerInventory for value in inventories
    ) or any(
        type(value) is not CivilizationGroundingObservation for value in observations
    ):
        raise CivilizationError()
    if not inventories:
        return (
            (),
            CivilizationCoverage(
                CivilizationCoverageState.UNAVAILABLE, "grounding_unavailable"
            ),
        )
    by_owner = {row.owner_id: row for row in observations}
    witnesses: list[InstitutionGroundingWitness] = []
    unresolved = False
    needs_grounding = any(
        evidence.channel == "observed" and evidence.pattern == "role_recognition"
        for inventory in inventories
        for concept in inventory.concepts
        for evidence in concept.evidence
    )
    if not needs_grounding:
        return (), CivilizationCoverage(CivilizationCoverageState.COMPLETE)
    for inventory in inventories:
        observation = by_owner.get(inventory.owner_id)
        for concept in inventory.concepts:
            for evidence in concept.evidence:
                if (
                    evidence.channel != "observed"
                    or evidence.pattern != "role_recognition"
                ):
                    continue
                if evidence.actor_id is None:
                    unresolved = True
                    continue
                if observation is None or evidence.tick != observation.tick:
                    unresolved = True
                    continue
                resolved = _resolve_grounding(
                    inventory.owner_id, concept.concept_id, evidence, observation
                )
                if resolved is None:
                    unresolved = True
                    continue
                witnesses.append(resolved)
    unique = tuple(
        {
            (
                row.owner_id,
                row.concept_id,
                row.evidence_id,
                row.source_kind,
                row.source_id,
            ): row
            for row in witnesses
        }.values()
    )
    unique = tuple(
        sorted(
            unique,
            key=lambda row: (row.owner_id, row.concept_id, row.evidence_id),
        )
    )
    if not observations:
        return (
            unique,
            CivilizationCoverage(
                CivilizationCoverageState.UNAVAILABLE, "grounding_unavailable"
            ),
        )
    if not complete or unresolved:
        return (
            unique,
            CivilizationCoverage(
                CivilizationCoverageState.PARTIAL, "grounding_unavailable"
            ),
        )
    return unique, CivilizationCoverage(CivilizationCoverageState.COMPLETE)


def _resolve_grounding(
    owner_id: str,
    concept_id: str,
    evidence: CivilizationOwnerConceptEvidence,
    observation: CivilizationGroundingObservation,
) -> InstitutionGroundingWitness | None:
    parts = evidence.lineage_ref.split("-")
    if len(parts) == 4 and parts[0] == "project":
        try:
            project_ordinal, contribution_ordinal, contribution_tick = (
                int(parts[1]),
                int(parts[2]),
                int(parts[3]),
            )
        except ValueError:
            return None
        if project_ordinal >= len(observation.projects):
            return None
        project = observation.projects[project_ordinal]
        if (contribution_ordinal, contribution_tick) not in (
            project.accepted_contributions
        ):
            return None
        return InstitutionGroundingWitness(
            owner_id,
            concept_id,
            evidence.evidence_id,
            evidence.tick,
            "project",
            project.project_id,
            project.location_id,
        )
    if len(parts) == 3 and parts[0] == "repository":
        try:
            repository_ordinal, founder_ordinal = int(parts[1]), int(parts[2])
        except ValueError:
            return None
        if repository_ordinal >= len(observation.repositories):
            return None
        repository = observation.repositories[repository_ordinal]
        if founder_ordinal >= repository.founder_count:
            return None
        return InstitutionGroundingWitness(
            owner_id,
            concept_id,
            evidence.evidence_id,
            evidence.tick,
            "repository",
            repository.repository_id,
            repository.location_id,
        )
    return None


def civilization_event_receipt(event: WorldEvent) -> CivilizationEventReceipt | None:
    """Copy explicit fields from closed native detail types only.

    Never use a later scene to fill missing occurrence endpoints or item kinds.
    An unrelated source event contributes only to its batch's examined count.
    """
    if type(event) is not WorldEvent:
        raise CivilizationError()
    detail = event.details
    kind: CivilizationEventKind
    participants = tuple(
        sorted(
            {
                value.value
                for value in (event.actor_id, event.target_id)
                if value is not None
            }
        )
    )
    occurrence = event.occurrence
    origin = (
        None
        if occurrence is None or occurrence.origin_location_id is None
        else occurrence.origin_location_id.value
    )
    destination = (
        None
        if occurrence is None or occurrence.destination_location_id is None
        else occurrence.destination_location_id.value
    )
    origin_region = destination_region = journey_id = project_id = None
    repository_id = record_id = structure_id = None
    items: tuple[CivilizationReceiptItem, ...] = ()
    outcome: (
        Literal[
            "completed",
            "arrived",
            "participant_dead",
            "arrival_timeout",
            "accepted",
            "rejected",
        ]
        | None
    ) = None
    if type(detail) is ExchangeCompleted:
        kind = CivilizationEventKind.EXCHANGE_COMPLETED
        participants = (detail.actor_id.value, detail.counterparty_id.value)
        items = tuple(
            CivilizationReceiptItem(item.value, ItemKind(item_kind), "give")
            for item, item_kind in zip(
                detail.give_item_ids, detail.give_item_kinds, strict=True
            )
        )
        items += tuple(
            CivilizationReceiptItem(item.value, ItemKind(item_kind), "take")
            for item, item_kind in zip(
                detail.take_item_ids, detail.take_item_kinds, strict=True
            )
        )
        outcome = "completed"
    elif type(detail) is Given:
        kind = CivilizationEventKind.GIVE
        participants = tuple(sorted(set(participants) | {detail.recipient_id.value}))
        items = (CivilizationReceiptItem(detail.item_id.value, None, "transfer"),)
    elif type(detail) is JourneyStarted:
        kind = CivilizationEventKind.JOURNEY_STARTED
        journey = detail.journey
        participants = tuple(item.value for item in journey.participant_body_ids)
        origin, destination = (
            journey.origin_location_id.value,
            journey.destination_location_id.value,
        )
        origin_region, destination_region = (
            journey.origin_region_id,
            journey.destination_region_id,
        )
        journey_id = journey.journey_id
    elif isinstance(detail, JourneyArrived | JourneyEnded):
        kind = (
            CivilizationEventKind.JOURNEY_ARRIVED
            if type(detail) is JourneyArrived
            else CivilizationEventKind.JOURNEY_ENDED
        )
        participants = tuple(item.value for item in detail.participant_body_ids)
        origin, destination = (
            detail.origin_location_id.value,
            detail.destination_location_id.value,
        )
        journey_id = detail.journey_id
        outcome = "arrived" if isinstance(detail, JourneyArrived) else detail.reason
    elif isinstance(
        detail,
        ProjectCreated
        | ProjectContributed
        | ProjectShortage
        | ProjectCompleted
        | ProjectAbandoned
        | PublicGoodBenefit
        | PublicGoodMaintained
        | PublicGoodOpposed,
    ):
        kind = CivilizationEventKind(detail.kind)
        project_id = detail.project_id.value
        if isinstance(detail, ProjectCreated):
            origin = detail.location_id.value
        if isinstance(detail, ProjectContributed | PublicGoodMaintained):
            outcome = "accepted" if detail.accepted else "rejected"
        if isinstance(detail, ProjectContributed) and detail.item_id is not None:
            items = (CivilizationReceiptItem(detail.item_id.value, None, "transfer"),)
        if isinstance(detail, ProjectCompleted):
            structure_id = (
                None if detail.structure_id is None else detail.structure_id.value
            )
            outcome = "completed"
    elif isinstance(detail, RepositoryMemberDeposited | RepositoryMemberRetrieved):
        kind = CivilizationEventKind(detail.kind)
        repository_id, record_id = detail.repository_id.value, detail.artifact_id.value
    elif isinstance(detail, ArtifactCreated | ArtifactModified):
        kind = CivilizationEventKind(detail.kind)
        record_id = detail.artifact_id.value
    else:
        return None
    return CivilizationEventReceipt(
        event.run_id,
        event.event_id.value,
        event.tick,
        event.sequence,
        kind,
        participants,
        origin,
        destination,
        origin_region,
        destination_region,
        journey_id,
        project_id,
        repository_id,
        record_id,
        structure_id,
        items,
        outcome,
    )


def unavailable_civilization_events(
    run_id: str,
    tick: int,
    *,
    expected_count: int | None = None,
    examined_count: int = 0,
) -> CivilizationEventBatch:
    """Recovery without proof is unavailable, never complete with zero receipts."""
    return CivilizationEventBatch(
        run_id,
        tick,
        "unavailable",
        expected_count,
        examined_count,
        (),
        CivilizationCoverage(
            CivilizationCoverageState.UNAVAILABLE,
            "event_gap",
            capture_start=tick,
            capture_end=tick + 1,
            observed_count=examined_count
            if expected_count is None or examined_count <= expected_count
            else None,
            expected_count=expected_count,
        ),
    )


def project_civilization_events(
    run_id: str,
    tick: int,
    events: tuple[WorldEvent, ...],
    *,
    expected_count: int,
    source: Literal["committed_result", "journal"],
) -> CivilizationEventBatch:
    """Require an exact contiguous source before declaring a covered tick."""
    _count(expected_count)
    _count(tick)
    _id(run_id)
    if (
        len(events) != expected_count
        or any(
            type(event) is not WorldEvent
            or event.run_id != run_id
            or event.tick != tick
            or event.sequence != index
            for index, event in enumerate(events)
        )
        or len({event.event_id for event in events}) != len(events)
    ):
        _LOG.warning("civilization_event_gap tick=%s reason_code=event_gap", tick)
        return unavailable_civilization_events(
            run_id, tick, expected_count=expected_count, examined_count=len(events)
        )
    receipts = tuple(
        receipt
        for event in events
        if (receipt := civilization_event_receipt(event)) is not None
    )
    return CivilizationEventBatch(
        run_id,
        tick,
        source,
        expected_count,
        len(events),
        receipts,
        CivilizationCoverage(
            CivilizationCoverageState.COMPLETE,
            capture_start=tick,
            capture_end=tick + 1,
            observed_count=len(events),
            expected_count=expected_count,
        ),
    )


def civilization_events_from_result(
    run_id: str, result: TickResult
) -> CivilizationEventBatch:
    """Live committed results only; never use an empty recovery placeholder."""
    if type(result) is not TickResult:
        raise CivilizationError()
    return project_civilization_events(
        run_id,
        result.tick.value,
        tuple(row.event for row in result.events),
        expected_count=len(result.events),
        source="committed_result",
    )


async def recover_civilization_events(
    journal: object,
    run_id: str,
    tick: int,
    *,
    page_limit: int = 200,
    max_events: int = 2_000,
    max_bytes: int = 4 * 1024 * 1024,
) -> CivilizationEventBatch:
    """Prove one recovered tick from the immutable journal, bounded and exact.

    A missing commit, page, count or ordering is an explicit gap. It is never a
    known-empty tick, and it never repairs missing private owner inventories.
    """
    _id(run_id)
    _count(tick)
    for value, maximum in (
        (page_limit, 200),
        (max_events, 2_000),
    ):
        if not 1 <= _count(value) <= maximum:
            raise CivilizationError()
    if not 1 <= _count(max_bytes) <= 4 * 1024 * 1024:
        raise CivilizationError()
    try:
        from simulation.clock import Tick
        from simulation.models import RunId

        get_commit = getattr(journal, "get_tick_commit", None)
        list_events = getattr(journal, "list_events", None)
        if not callable(get_commit) or not callable(list_events):
            return unavailable_civilization_events(run_id, tick)
        commit = await get_commit(RunId(run_id), Tick(tick))
        if commit is None:
            return unavailable_civilization_events(run_id, tick)
        expected = getattr(commit, "event_count", None)
        commit_tick = getattr(getattr(commit, "tick", None), "value", None)
        commit_run = getattr(getattr(commit, "run_id", None), "value", None)
        if (
            type(expected) is not int
            or expected < 0
            or commit_tick != tick
            or commit_run != run_id
        ):
            raise CivilizationError()
        if expected > max_events:
            return unavailable_civilization_events(
                run_id, tick, expected_count=expected
            )
        events: list[WorldEvent] = []
        offset = 0
        while len(events) < expected:
            page = await list_events(
                RunId(run_id),
                from_tick=Tick(tick),
                to_tick=Tick(tick),
                limit=min(page_limit, expected - len(events)),
                offset=offset,
            )
            page = tuple(page)
            if not page:
                break
            events.extend(page)
            offset += len(page)
        batch = project_civilization_events(
            run_id,
            tick,
            tuple(events),
            expected_count=expected,
            source="journal",
        )
        if batch.coverage.state is not CivilizationCoverageState.COMPLETE:
            return batch
        if len(civilization_event_bytes(batch)) > max_bytes:
            return unavailable_civilization_events(
                run_id, tick, expected_count=expected, examined_count=len(events)
            )
        return batch
    except Exception:
        _LOG.warning("civilization_recovery_gap tick=%s reason_code=event_gap", tick)
        return unavailable_civilization_events(run_id, tick)


def civilization_event_bytes(batch: CivilizationEventBatch) -> bytes:
    """Canonical metadata bytes for capture accounting, never a native event codec."""
    if type(batch) is not CivilizationEventBatch:
        raise CivilizationError()
    try:
        return (
            json.dumps(
                asdict(batch),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise CivilizationError() from None
