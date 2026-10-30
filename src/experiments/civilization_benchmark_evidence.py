"""Detached boundary evidence for the V3 civilization benchmark.

Every measured store is read from retained owner evidence after full
finalization. The probe never feeds cognition, world state or a stop selector,
and a missing measurement is reported as unavailable rather than as zero.
"""

from __future__ import annotations

import dataclasses
import logging
from collections.abc import Mapping, Sized
from dataclasses import dataclass
from typing import Final

from experiments.civilization_benchmark_models import (
    V3BenchmarkCheck,
    V3BenchmarkCheckStatus,
    V3BenchmarkCoverage,
    V3BenchmarkError,
    V3BenchmarkEvidenceAvailability,
    V3BenchmarkInterventionReceipt,
    V3BenchmarkSourceKind,
    V3BenchmarkSourceReference,
)
from simulation.fork_checkpoint import (
    FinalizedResearchBoundary,
    FinalizedResearchOwnerSnapshot,
)
from simulation.new_agent_initialization import BLANK_SLATE_SUBJECTIVE_STORES
from simulation.runner import SimulationRunner
from simulation.runner_models import RunnerAttemptReceipt

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.civilization_benchmark_evidence"
)

# Stores that are not persisted owner state at a finalized boundary. Deriving
# them would require cognition internals, so they are declared out of coverage
# instead of being reported as measured zeros.
NOT_PERSISTED_STORES: Final[frozenset[str]] = frozenset(
    {
        "self_model",
        "cognition_trace",
        "skill_ledger",
        "taught_content_lineage",
        "experiment_ledger",
    }
)

# store -> (source, attribute) where source is "snapshot" or "runtime".
STORE_PROBE_PATHS: Final[Mapping[str, tuple[str, str]]] = {
    "episodic_memory": ("snapshot", "memories"),
    "semantic_beliefs": ("snapshot", "beliefs"),
    "relationships": ("snapshot", "relationship_profiles"),
    "goals": ("runtime", "goals"),
    "theory_of_mind": ("runtime", "theory_of_mind"),
    "cultural_narratives": ("runtime", "cultural_narratives"),
    "semantic_naming": ("runtime", "semantic_naming"),
    "symbolic_language": ("runtime", "symbolic_language"),
    "translation": ("runtime", "translation"),
    "institution_concepts": ("runtime", "institution_concepts"),
    "institutional_decay": ("runtime", "institutional_decay"),
    "office_concepts": ("runtime", "office_concepts"),
    "mediation": ("runtime", "mediation"),
    "social_norms": ("runtime", "social_norms"),
    "social_conventions": ("runtime", "social_conventions"),
    "developmental_knowledge": ("runtime", "developmental_knowledge"),
    "mentorship_bonds": ("runtime", "mentorship"),
    "cultural_features": ("runtime", "cultural_features"),
    "practical_knowledge": ("runtime", "practical_knowledge"),
    "possession_legitimacy": ("runtime", "possession_legitimacy"),
    "structured_commitments": ("runtime", "structured_commitments"),
    "subjective_valuations": ("runtime", "subjective_valuations"),
    "scarcity_beliefs": ("runtime", "scarcity_beliefs"),
    "acceptance_memories": ("runtime", "acceptance_memories"),
}

_MEASURABLE_STORES: Final[tuple[str, ...]] = tuple(
    store for store in BLANK_SLATE_SUBJECTIVE_STORES if store in STORE_PROBE_PATHS
)

# Closed generational invariant identifiers. Each one is exercised by a
# behavioral test with qualified receipts; a missing source stays unexecuted.
GENERATIONAL_INVARIANT_IDS: Final[tuple[str, ...]] = (
    "blank_slate",
    "valid_historical_channels",
    "dead_stop_acting",
    "physical_record_persistence",
    "false_records_legal",
    "technology_loss_possible",
    "auditable_knowledge_lineage",
    "subjective_roles",
    "possession_not_legitimacy",
    "isolated_knowledge",
    "engine_migration",
    "coordinates_nonsemantic",
    "observer_read_only",
)


def content_count(value: object) -> int:
    """Count retained rows in an opaque owner ledger without reading payloads."""
    if value is None:
        return 0
    if isinstance(value, Mapping):
        return len(value)
    if isinstance(value, (tuple, list, set, frozenset)):
        return len(value)
    if isinstance(value, Sized):
        try:
            return len(value)
        except TypeError:
            pass
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        total = 0
        for field in dataclasses.fields(value):
            item = getattr(value, field.name)
            if isinstance(item, (tuple, list, set, frozenset, Mapping)):
                total += len(item)
        return total
    # An opaque populated object is still content.
    return 1


@dataclass(frozen=True, slots=True)
class OwnerStoreSnapshot:
    """Measured content of one owner at one finalized boundary."""

    owner_id: str
    entity_id: str
    generation_index: int
    living: bool
    invocation_count: int
    counts: tuple[tuple[str, int | None], ...]
    measured_stores: tuple[str, ...]
    unmeasured_stores: tuple[str, ...]
    teaching_audits: int = 0
    developmental_acquisitions: int = 0
    mentorship_audits: int = 0
    cultural_audits: int = 0
    artifact_interpretations: int = 0
    institutional_memory_entries: int = 0

    def count(self, store: str) -> int | None:
        for name, value in self.counts:
            if name == store:
                return value
        raise KeyError(store)

    def is_blank(self) -> bool:
        zero_content = all(value == 0 for _, value in self.counts if value is not None)
        return zero_content and self.invocation_count == 0


@dataclass(frozen=True, slots=True)
class BoundaryObservation:
    """One finalized boundary with newly observed owners highlighted."""

    boundary_tick: int
    owners: tuple[OwnerStoreSnapshot, ...]
    new_owners: tuple[OwnerStoreSnapshot, ...]
    event_count: int = 0
    event_kind_counts: tuple[tuple[str, int], ...] = ()
    needs_applied_body_ids: tuple[str, ...] = ()
    # Cumulative metadata-only counts over every event below this boundary.
    event_kind_totals: tuple[tuple[str, int], ...] = ()
    death_ticks_by_body: tuple[tuple[str, int], ...] = ()
    commitment_promises: tuple[tuple[str, str, int | None], ...] = ()
    given_transfers: tuple[tuple[int, str, str], ...] = ()


def _measure_owner(snapshot: FinalizedResearchOwnerSnapshot) -> OwnerStoreSnapshot:
    runtime = getattr(snapshot, "runtime_checkpoint", None)
    if runtime is None:
        raise V3BenchmarkError(
            "probe_unavailable", "owner runtime checkpoint is missing"
        )
    counts: list[tuple[str, int | None]] = []
    measured: list[str] = []
    unmeasured: list[str] = []
    for store in BLANK_SLATE_SUBJECTIVE_STORES:
        if store in NOT_PERSISTED_STORES or store not in STORE_PROBE_PATHS:
            counts.append((store, None))
            unmeasured.append(store)
            continue
        source, attribute = STORE_PROBE_PATHS[store]
        holder = snapshot if source == "snapshot" else runtime
        counts.append((store, content_count(getattr(holder, attribute, None))))
        measured.append(store)
    return OwnerStoreSnapshot(
        owner_id=snapshot.owner_id.value,
        entity_id=snapshot.entity_id.value,
        generation_index=snapshot.generation_index,
        living=snapshot.living,
        invocation_count=runtime.processed_invocation_count,
        counts=tuple(counts),
        measured_stores=tuple(measured),
        unmeasured_stores=tuple(unmeasured),
        teaching_audits=content_count(getattr(runtime, "teaching_audits", ())),
        developmental_acquisitions=content_count(
            getattr(runtime, "developmental_acquisition_audits", ())
        ),
        mentorship_audits=content_count(getattr(runtime, "mentorship_audits", ())),
        cultural_audits=content_count(getattr(runtime, "cultural_feature_audits", ())),
        artifact_interpretations=content_count(
            getattr(runtime, "artifact_interpretations", ())
        ),
        institutional_memory_entries=content_count(
            getattr(runtime, "institutional_memory", None)
        ),
    )


class BenchmarkBoundaryProbe:
    """Read-only boundary observer collecting first-sight owner measurements."""

    def __init__(self) -> None:
        self._seen: set[str] = set()
        self._observations: list[BoundaryObservation] = []
        self._failures: list[str] = []
        self._scanned_events = 0
        self._event_kind_totals: dict[str, int] = {}
        self._death_ticks_by_body: dict[str, int] = {}
        self._commitment_promises: list[tuple[str, str, int | None]] = []
        self._given_transfers: list[tuple[int, str, str]] = []

    @property
    def observations(self) -> tuple[BoundaryObservation, ...]:
        return tuple(self._observations)

    @property
    def failures(self) -> tuple[str, ...]:
        return tuple(self._failures)

    @property
    def event_kind_totals(self) -> tuple[tuple[str, int], ...]:
        """Cumulative metadata-only event counts for the observed window."""
        return tuple(sorted(self._event_kind_totals.items()))

    @property
    def death_ticks_by_body(self) -> tuple[tuple[str, int], ...]:
        """First observed death tick per body, in stable order."""
        return tuple(sorted(self._death_ticks_by_body.items()))

    @property
    def commitment_promises(self) -> tuple[tuple[str, str, int | None], ...]:
        """Public propose declarations: (actor, counterparty, due tick)."""
        return tuple(self._commitment_promises)

    @property
    def given_transfers(self) -> tuple[tuple[int, str, str], ...]:
        """Committed give outcomes: (tick, actor, recipient)."""
        return tuple(self._given_transfers)

    def event_total(self, kind: str) -> int:
        """Return the cumulative count for one committed event kind."""
        return self._event_kind_totals.get(kind, 0)

    def owner_death_ticks(self) -> dict[str, int]:
        """Map measured owner ids to death ticks through their own bodies."""
        entity_to_owner: dict[str, str] = {}
        for observation in self._observations:
            for owner in observation.owners:
                entity_to_owner[owner.entity_id] = owner.owner_id
        deaths: dict[str, int] = {}
        for body_id, tick in self._death_ticks_by_body.items():
            owner_id = entity_to_owner.get(body_id)
            if owner_id is not None:
                deaths[owner_id] = tick
        return deaths

    def living_owner_ids(self) -> frozenset[str]:
        """Owner ids measured as living at the latest boundary."""
        if not self._observations:
            return frozenset()
        return frozenset(
            owner.owner_id for owner in self._observations[-1].owners if owner.living
        )

    def _scan_new_events(self, events: tuple[object, ...]) -> None:
        """Accumulate only newly visible events; boundaries are prefix-stable."""
        if len(events) < self._scanned_events:
            # Defensive: a non-prefix export would double count. Re-scan from 0.
            self._scanned_events = 0
            self._event_kind_totals.clear()
            self._death_ticks_by_body.clear()
            self._commitment_promises.clear()
            self._given_transfers.clear()
        for event in events[self._scanned_events :]:
            details = getattr(event, "details", None)
            kind = type(details).__name__
            self._event_kind_totals[kind] = self._event_kind_totals.get(kind, 0) + 1
            tick = getattr(event, "tick", None)
            if (
                kind == "CommitmentDeclared"
                and getattr(details, "act", None) == "propose"
            ):
                actor = getattr(getattr(details, "actor_id", None), "value", None)
                other = getattr(
                    getattr(details, "counterparty_id", None), "value", None
                )
                due = getattr(details, "due_tick", None)
                if isinstance(actor, str) and isinstance(other, str):
                    self._commitment_promises.append(
                        (actor, other, due if type(due) is int else None)
                    )
            elif kind == "Given":
                actor = getattr(getattr(event, "actor_id", None), "value", None)
                recipient = getattr(
                    getattr(details, "recipient_id", None), "value", None
                )
                if (
                    isinstance(actor, str)
                    and isinstance(recipient, str)
                    and type(tick) is int
                ):
                    self._given_transfers.append((tick, actor, recipient))
            if kind != "Died":
                continue
            body = getattr(details, "body_id", None)
            body_id = getattr(body, "value", None)
            if not isinstance(body_id, str) or type(tick) is not int:
                continue
            prior = self._death_ticks_by_body.get(body_id)
            if prior is None or tick < prior:
                self._death_ticks_by_body[body_id] = tick
        self._scanned_events = len(events)

    def new_owners(self) -> tuple[OwnerStoreSnapshot, ...]:
        owners: list[OwnerStoreSnapshot] = []
        for observation in self._observations:
            owners.extend(observation.new_owners)
        return tuple(owners)

    async def __call__(
        self,
        runner: SimulationRunner,
        receipt: RunnerAttemptReceipt | None,
    ) -> None:
        boundary = await runner.export_finalized_research_boundary()
        if type(boundary) is not FinalizedResearchBoundary:
            raise V3BenchmarkError(
                "probe_unavailable", "research boundary projection is unsupported"
            )
        owners = tuple(_measure_owner(owner) for owner in boundary.owners)
        new = tuple(owner for owner in owners if owner.owner_id not in self._seen)
        for owner in new:
            self._seen.add(owner.owner_id)
        kind_counts: dict[str, int] = {}
        needs_bodies: list[str] = []
        for event in boundary.events:
            details = getattr(event, "details", None)
            kind = type(details).__name__
            kind_counts[kind] = kind_counts.get(kind, 0) + 1
            if kind == "NeedsApplied":
                body = getattr(details, "body_id", None)
                if body is not None:
                    needs_bodies.append(body.value)
        self._scan_new_events(boundary.events)
        observation = BoundaryObservation(
            boundary_tick=boundary.boundary_tick.value,
            owners=owners,
            new_owners=new,
            event_count=len(boundary.events),
            event_kind_counts=tuple(sorted(kind_counts.items())),
            needs_applied_body_ids=tuple(needs_bodies),
            event_kind_totals=self.event_kind_totals,
            death_ticks_by_body=self.death_ticks_by_body,
            commitment_promises=self.commitment_promises,
            given_transfers=self.given_transfers,
        )
        self._observations.append(observation)
        _LOG.debug(
            "benchmark_boundary_observed owner_count=%s new_owner_count=%s "
            "boundary_tick=%s",
            len(owners),
            len(new),
            observation.boundary_tick,
        )


def blank_slate_check(
    probe: BenchmarkBoundaryProbe,
    *,
    boundary_end_tick: int,
) -> V3BenchmarkCheck:
    """Evaluate measured newborn content against the blank-slate contract."""
    return evaluate_blank_slate(probe.new_owners(), boundary_end_tick=boundary_end_tick)


def evaluate_blank_slate(
    owners: tuple[OwnerStoreSnapshot, ...],
    *,
    boundary_end_tick: int,
) -> V3BenchmarkCheck:
    """Pure blank-slate evaluation over already measured owner rows."""
    if not owners:
        return V3BenchmarkCheck(
            selector_id="new_agent_initialization_evidence",
            selector_version=1,
            status=V3BenchmarkCheckStatus.UNEXECUTED,
            reason_code="no_admitted_owner_observed",
            evidence=V3BenchmarkEvidenceAvailability.UNAVAILABLE,
            coverage=V3BenchmarkCoverage.NOT_EXERCISED,
            source_references=(),
        )
    sources = tuple(
        V3BenchmarkSourceReference(
            source_kind=V3BenchmarkSourceKind.SUBJECTIVE_DEBUG,
            reference_id=owner.owner_id,
            owner_id=owner.owner_id,
        )
        for owner in owners
    )
    measured_complete = all(
        not owner.unmeasured_stores
        or set(owner.unmeasured_stores).issubset(NOT_PERSISTED_STORES)
        for owner in owners
    )
    blank = [owner for owner in owners if owner.is_blank()]
    copied = [owner for owner in owners if not owner.is_blank()]
    if copied:
        return V3BenchmarkCheck(
            selector_id="new_agent_initialization_evidence",
            selector_version=1,
            status=V3BenchmarkCheckStatus.FAIL,
            reason_code="subjective_copy_forbidden",
            evidence=V3BenchmarkEvidenceAvailability.COMPLETE,
            coverage=V3BenchmarkCoverage.EXERCISED,
            source_references=sources,
            boundary_start_tick=0,
            boundary_end_tick=boundary_end_tick,
            numerator=len(blank),
            denominator=len(owners),
        )
    if not measured_complete:
        return V3BenchmarkCheck(
            selector_id="new_agent_initialization_evidence",
            selector_version=1,
            status=V3BenchmarkCheckStatus.UNEXECUTED,
            reason_code="probe_unavailable",
            evidence=V3BenchmarkEvidenceAvailability.PARTIAL,
            coverage=V3BenchmarkCoverage.EXERCISED,
            source_references=sources,
            boundary_start_tick=0,
            boundary_end_tick=boundary_end_tick,
            numerator=len(blank),
            denominator=len(owners),
        )
    return V3BenchmarkCheck(
        selector_id="new_agent_initialization_evidence",
        selector_version=1,
        status=V3BenchmarkCheckStatus.PASS,
        reason_code="blank_slate_measured",
        evidence=V3BenchmarkEvidenceAvailability.COMPLETE,
        coverage=V3BenchmarkCoverage.EXERCISED,
        source_references=sources,
        boundary_start_tick=0,
        boundary_end_tick=boundary_end_tick,
        numerator=len(blank),
        denominator=len(owners),
    )


def evaluate_event_journal(probe: BenchmarkBoundaryProbe) -> V3BenchmarkCheck:
    """Check that committed objective events were retained for this run."""
    observations = probe.observations
    if not observations:
        return V3BenchmarkCheck(
            selector_id="objective_event_journal",
            selector_version=1,
            status=V3BenchmarkCheckStatus.UNEXECUTED,
            reason_code="probe_unavailable",
            evidence=V3BenchmarkEvidenceAvailability.UNAVAILABLE,
            coverage=V3BenchmarkCoverage.NOT_EXERCISED,
            source_references=(),
        )
    last = observations[-1]
    total = sum(item.event_count for item in observations)
    sources = tuple(
        V3BenchmarkSourceReference(
            source_kind=V3BenchmarkSourceKind.OBJECTIVE_INSPECTION,
            reference_id=f"boundary-tick-{item.boundary_tick}",
            tick=item.boundary_tick,
        )
        for item in observations[-1:]
    )
    return V3BenchmarkCheck(
        selector_id="objective_event_journal",
        selector_version=1,
        status=(
            V3BenchmarkCheckStatus.PASS
            if total > 0
            else V3BenchmarkCheckStatus.UNEXECUTED
        ),
        reason_code=("events_retained" if total > 0 else "no_events_observed"),
        evidence=(
            V3BenchmarkEvidenceAvailability.COMPLETE
            if total > 0
            else V3BenchmarkEvidenceAvailability.UNAVAILABLE
        ),
        coverage=V3BenchmarkCoverage.EXERCISED,
        source_references=sources,
        boundary_start_tick=0,
        boundary_end_tick=last.boundary_tick,
        numerator=total,
        denominator=total,
    )


def _entrants(probe: BenchmarkBoundaryProbe) -> tuple[OwnerStoreSnapshot, ...]:
    observations = probe.observations
    if not observations:
        return ()
    founders = {owner.owner_id for owner in observations[0].owners}
    return tuple(
        owner
        for observation in observations[1:]
        for owner in observation.new_owners
        if owner.owner_id not in founders
    )


def _window_complete(probe: BenchmarkBoundaryProbe, boundary_end_tick: int) -> bool:
    observations = probe.observations
    return (
        bool(observations)
        and observations[-1].boundary_tick == boundary_end_tick
        and not probe.failures
    )


def _entrant_sources(
    entrants: tuple[OwnerStoreSnapshot, ...],
) -> tuple[V3BenchmarkSourceReference, ...]:
    return tuple(
        V3BenchmarkSourceReference(
            source_kind=V3BenchmarkSourceKind.SUBJECTIVE_DEBUG,
            reference_id=owner.owner_id,
            owner_id=owner.owner_id,
        )
        for owner in entrants
    )


def _event_total(probe: BenchmarkBoundaryProbe, kind: str) -> int:
    return sum(
        dict(observation.event_kind_counts).get(kind, 0)
        for observation in probe.observations
    )


def evaluate_historical_memory(
    probe: BenchmarkBoundaryProbe, *, boundary_end_tick: int
) -> V3BenchmarkCheck:
    """Measure retained owner memory over a complete observed window."""
    observations = probe.observations
    owners = observations[-1].owners if observations else ()
    with_memory = [owner for owner in owners if owner.count("episodic_memory")]
    complete = _window_complete(probe, boundary_end_tick)
    return V3BenchmarkCheck(
        selector_id="historical_memory_evidence",
        selector_version=1,
        status=(
            V3BenchmarkCheckStatus.PASS
            if complete
            else V3BenchmarkCheckStatus.UNEXECUTED
        ),
        reason_code=("memory_window_complete" if complete else "probe_unavailable"),
        evidence=(
            V3BenchmarkEvidenceAvailability.COMPLETE
            if complete
            else V3BenchmarkEvidenceAvailability.PARTIAL
        ),
        coverage=V3BenchmarkCoverage.EXERCISED,
        source_references=tuple(
            V3BenchmarkSourceReference(
                source_kind=V3BenchmarkSourceKind.SUBJECTIVE_DEBUG,
                reference_id=owner.owner_id,
                owner_id=owner.owner_id,
            )
            for owner in with_memory
        ),
        boundary_start_tick=0,
        boundary_end_tick=boundary_end_tick,
        numerator=len(with_memory),
        denominator=len(owners),
    )


def evaluate_durable_records(
    probe: BenchmarkBoundaryProbe,
    *,
    boundary_end_tick: int,
    mechanism_available: bool,
) -> V3BenchmarkCheck:
    """A record must physically exist; interpretation is measured separately."""
    if not mechanism_available:
        return V3BenchmarkCheck(
            selector_id="durable_record_evidence",
            selector_version=1,
            status=V3BenchmarkCheckStatus.UNEXECUTED,
            reason_code="durable_records_disabled",
            evidence=V3BenchmarkEvidenceAvailability.UNAVAILABLE,
            coverage=V3BenchmarkCoverage.NOT_EXERCISED,
            source_references=(),
        )
    created = _event_total(probe, "ArtifactCreated")
    destroyed = _event_total(probe, "ArtifactDestroyed")
    complete = _window_complete(probe, boundary_end_tick)
    if not complete:
        return V3BenchmarkCheck(
            selector_id="durable_record_evidence",
            selector_version=1,
            status=V3BenchmarkCheckStatus.UNEXECUTED,
            reason_code="probe_unavailable",
            evidence=V3BenchmarkEvidenceAvailability.PARTIAL,
            coverage=V3BenchmarkCoverage.EXERCISED,
            source_references=(),
        )
    if created < 1:
        return V3BenchmarkCheck(
            selector_id="durable_record_evidence",
            selector_version=1,
            status=V3BenchmarkCheckStatus.UNEXECUTED,
            reason_code="no_record_observed",
            evidence=V3BenchmarkEvidenceAvailability.PARTIAL,
            coverage=V3BenchmarkCoverage.NOT_EXERCISED,
            source_references=(),
        )
    observations = probe.observations
    sources = tuple(
        V3BenchmarkSourceReference(
            source_kind=V3BenchmarkSourceKind.OBJECTIVE_INSPECTION,
            reference_id=f"artifact-events-t{observation.boundary_tick}",
            tick=observation.boundary_tick,
        )
        for observation in observations[-1:]
    )
    return V3BenchmarkCheck(
        selector_id="durable_record_evidence",
        selector_version=1,
        status=V3BenchmarkCheckStatus.PASS,
        reason_code=(
            "record_persisted" if destroyed == 0 else "record_physically_removed"
        ),
        evidence=V3BenchmarkEvidenceAvailability.COMPLETE,
        coverage=V3BenchmarkCoverage.EXERCISED,
        source_references=sources,
        boundary_start_tick=0,
        boundary_end_tick=boundary_end_tick,
        numerator=created,
        denominator=created,
    )


def evaluate_population_lifecycle(
    probe: BenchmarkBoundaryProbe, *, boundary_end_tick: int
) -> V3BenchmarkCheck:
    """Confirm population change across a complete observed window."""
    entrants = _entrants(probe)
    complete = _window_complete(probe, boundary_end_tick)
    if complete and not entrants:
        return V3BenchmarkCheck(
            selector_id="population_lifecycle_evidence",
            selector_version=1,
            status=V3BenchmarkCheckStatus.UNEXECUTED,
            reason_code="no_entrant_observed",
            evidence=V3BenchmarkEvidenceAvailability.COMPLETE,
            coverage=V3BenchmarkCoverage.NOT_EXERCISED,
            source_references=(),
            boundary_start_tick=0,
            boundary_end_tick=boundary_end_tick,
            numerator=0,
            denominator=0,
        )
    return V3BenchmarkCheck(
        selector_id="population_lifecycle_evidence",
        selector_version=1,
        status=(
            V3BenchmarkCheckStatus.PASS
            if complete
            else V3BenchmarkCheckStatus.UNEXECUTED
        ),
        reason_code=("population_window_complete" if complete else "probe_unavailable"),
        evidence=(
            V3BenchmarkEvidenceAvailability.COMPLETE
            if complete
            else V3BenchmarkEvidenceAvailability.PARTIAL
        ),
        coverage=V3BenchmarkCoverage.EXERCISED,
        source_references=_entrant_sources(entrants),
        boundary_start_tick=0,
        boundary_end_tick=boundary_end_tick,
        numerator=len(entrants),
        denominator=len(entrants),
    )


def evaluate_dependency_care(
    probe: BenchmarkBoundaryProbe, *, boundary_end_tick: int
) -> V3BenchmarkCheck:
    """Measure applied care for actually admitted dependents."""
    entrants = _entrants(probe)
    if not entrants:
        return V3BenchmarkCheck(
            selector_id="dependency_care_evidence",
            selector_version=1,
            status=V3BenchmarkCheckStatus.UNEXECUTED,
            reason_code="no_dependent_entrant_observed",
            evidence=V3BenchmarkEvidenceAvailability.UNAVAILABLE,
            coverage=V3BenchmarkCoverage.NOT_EXERCISED,
            source_references=(),
        )
    cared_bodies: set[str] = set()
    for observation in probe.observations:
        cared_bodies.update(observation.needs_applied_body_ids)
    cared = [owner for owner in entrants if owner.entity_id in cared_bodies]
    complete = _window_complete(probe, boundary_end_tick)
    return V3BenchmarkCheck(
        selector_id="dependency_care_evidence",
        selector_version=1,
        status=(
            V3BenchmarkCheckStatus.PASS
            if complete
            else V3BenchmarkCheckStatus.UNEXECUTED
        ),
        reason_code=("care_window_complete" if complete else "probe_unavailable"),
        evidence=(
            V3BenchmarkEvidenceAvailability.COMPLETE
            if complete
            else V3BenchmarkEvidenceAvailability.PARTIAL
        ),
        coverage=V3BenchmarkCoverage.EXERCISED,
        source_references=_entrant_sources(entrants),
        boundary_start_tick=0,
        boundary_end_tick=boundary_end_tick,
        numerator=len(cared),
        denominator=len(entrants),
    )


def evaluate_developmental_teaching(
    probe: BenchmarkBoundaryProbe,
    *,
    boundary_end_tick: int,
    selector_id: str,
    mechanism_available: bool,
) -> V3BenchmarkCheck:
    """Measure recipient acquisition; zero acquisition is a valid null."""
    if not mechanism_available:
        return V3BenchmarkCheck(
            selector_id=selector_id,
            selector_version=1,
            status=V3BenchmarkCheckStatus.UNEXECUTED,
            reason_code="recipient_mode_disabled",
            evidence=V3BenchmarkEvidenceAvailability.UNAVAILABLE,
            coverage=V3BenchmarkCoverage.NOT_EXERCISED,
            source_references=(),
        )
    entrants = _entrants(probe)
    if not entrants:
        return V3BenchmarkCheck(
            selector_id=selector_id,
            selector_version=1,
            status=V3BenchmarkCheckStatus.UNEXECUTED,
            reason_code="no_entrant_observed",
            evidence=V3BenchmarkEvidenceAvailability.COMPLETE,
            coverage=V3BenchmarkCoverage.NOT_EXERCISED,
            source_references=(),
            boundary_start_tick=0,
            boundary_end_tick=boundary_end_tick,
            numerator=0,
            denominator=0,
        )
    acquired = [
        owner
        for owner in entrants
        if owner.teaching_audits > 0 or owner.developmental_acquisitions > 0
    ]
    complete = _window_complete(probe, boundary_end_tick)
    return V3BenchmarkCheck(
        selector_id=selector_id,
        selector_version=1,
        status=(
            V3BenchmarkCheckStatus.PASS
            if complete
            else V3BenchmarkCheckStatus.UNEXECUTED
        ),
        reason_code=("teaching_window_complete" if complete else "probe_unavailable"),
        evidence=(
            V3BenchmarkEvidenceAvailability.COMPLETE
            if complete
            else V3BenchmarkEvidenceAvailability.PARTIAL
        ),
        coverage=V3BenchmarkCoverage.EXERCISED,
        source_references=_entrant_sources(entrants),
        boundary_start_tick=0,
        boundary_end_tick=boundary_end_tick,
        numerator=len(acquired),
        denominator=len(entrants),
    )


def evaluate_cultural_mutation(
    probe: BenchmarkBoundaryProbe,
    *,
    boundary_end_tick: int,
    mechanism_available: bool,
) -> V3BenchmarkCheck:
    """Measure cultural acquisition; mutation itself is never required."""
    if not mechanism_available:
        return V3BenchmarkCheck(
            selector_id="cultural_feature_evidence",
            selector_version=1,
            status=V3BenchmarkCheckStatus.UNEXECUTED,
            reason_code="cultural_provenance_disabled",
            evidence=V3BenchmarkEvidenceAvailability.UNAVAILABLE,
            coverage=V3BenchmarkCoverage.NOT_EXERCISED,
            source_references=(),
        )
    entrants = _entrants(probe)
    if not entrants:
        return V3BenchmarkCheck(
            selector_id="cultural_feature_evidence",
            selector_version=1,
            status=V3BenchmarkCheckStatus.UNEXECUTED,
            reason_code="no_entrant_observed",
            evidence=V3BenchmarkEvidenceAvailability.COMPLETE,
            coverage=V3BenchmarkCoverage.NOT_EXERCISED,
            source_references=(),
            boundary_start_tick=0,
            boundary_end_tick=boundary_end_tick,
            numerator=0,
            denominator=0,
        )
    acquired = [
        owner
        for owner in entrants
        if (owner.count("cultural_features") or 0) > 0 or owner.cultural_audits > 0
    ]
    complete = _window_complete(probe, boundary_end_tick)
    return V3BenchmarkCheck(
        selector_id="cultural_feature_evidence",
        selector_version=1,
        status=(
            V3BenchmarkCheckStatus.PASS
            if complete
            else V3BenchmarkCheckStatus.UNEXECUTED
        ),
        reason_code=("cultural_window_complete" if complete else "probe_unavailable"),
        evidence=(
            V3BenchmarkEvidenceAvailability.COMPLETE
            if complete
            else V3BenchmarkEvidenceAvailability.PARTIAL
        ),
        coverage=V3BenchmarkCoverage.EXERCISED,
        source_references=_entrant_sources(entrants),
        boundary_start_tick=0,
        boundary_end_tick=boundary_end_tick,
        numerator=len(acquired),
        denominator=len(entrants),
    )


def evaluate_required_actions(
    receipts: tuple[V3BenchmarkInterventionReceipt, ...],
    required_milestone_ids: tuple[str, ...],
) -> V3BenchmarkCheck:
    """Require APPLIED acknowledgements for every declared mechanism action."""
    by_id = {receipt.milestone_id: receipt for receipt in receipts}
    sources = tuple(
        V3BenchmarkSourceReference(
            source_kind=V3BenchmarkSourceKind.OBJECTIVE_INSPECTION,
            reference_id=milestone_id,
        )
        for milestone_id in required_milestone_ids
        if milestone_id in by_id
    )
    applied = 0
    for milestone_id in required_milestone_ids:
        receipt = by_id.get(milestone_id)
        if receipt is not None and receipt.status == "applied":
            applied += 1
    missing = [item for item in required_milestone_ids if item not in by_id]
    denominator = len(required_milestone_ids)
    if missing:
        return V3BenchmarkCheck(
            selector_id="mechanism_intervention_evidence",
            selector_version=1,
            status=V3BenchmarkCheckStatus.UNEXECUTED,
            reason_code="required_action_not_applied",
            evidence=V3BenchmarkEvidenceAvailability.PARTIAL,
            coverage=V3BenchmarkCoverage.EXERCISED,
            source_references=sources,
            numerator=applied,
            denominator=denominator,
        )
    if applied != denominator:
        return V3BenchmarkCheck(
            selector_id="mechanism_intervention_evidence",
            selector_version=1,
            status=V3BenchmarkCheckStatus.FAIL,
            reason_code="required_action_not_applied",
            evidence=V3BenchmarkEvidenceAvailability.COMPLETE,
            coverage=V3BenchmarkCoverage.EXERCISED,
            source_references=sources,
            numerator=applied,
            denominator=denominator,
        )
    return V3BenchmarkCheck(
        selector_id="mechanism_intervention_evidence",
        selector_version=1,
        status=V3BenchmarkCheckStatus.PASS,
        reason_code="required_actions_applied",
        evidence=V3BenchmarkEvidenceAvailability.COMPLETE,
        coverage=V3BenchmarkCoverage.EXERCISED,
        source_references=sources,
        numerator=applied,
        denominator=denominator,
    )


@dataclass(frozen=True, slots=True)
class ObservedOwnerStore:
    """One owner's measured non-empty store content at a finalized boundary."""

    boundary_tick: int
    owner_id: str
    count: int


def observed_store_counts(
    probe: object, store: str
) -> tuple[ObservedOwnerStore, ...]:
    """Return measured non-empty owner counts for one store over the window.

    This complements final-boundary exports: a transmission, hypothesis, claim
    or memory entry that occurred while its owner was alive remains measured
    evidence even if that owner died before the run finished.
    """
    observations = getattr(probe, "observations", ())
    rows: list[ObservedOwnerStore] = []
    for observation in observations:
        for owner in getattr(observation, "owners", ()):
            counter = getattr(owner, "count", None)
            if not callable(counter):
                continue
            try:
                value = counter(store)
            except (KeyError, TypeError):
                continue
            if value:
                rows.append(
                    ObservedOwnerStore(
                        boundary_tick=observation.boundary_tick,
                        owner_id=owner.owner_id,
                        count=value,
                    )
                )
    return tuple(rows)


def observed_institutional_memory(
    probe: object,
) -> tuple[ObservedOwnerStore, ...]:
    """Return non-empty institutional-memory entries measured at boundaries."""
    observations = getattr(probe, "observations", ())
    rows: list[ObservedOwnerStore] = []
    for observation in observations:
        for owner in getattr(observation, "owners", ()):
            value = getattr(owner, "institutional_memory_entries", 0)
            if value:
                rows.append(
                    ObservedOwnerStore(
                        boundary_tick=observation.boundary_tick,
                        owner_id=owner.owner_id,
                        count=int(value),
                    )
                )
    return tuple(rows)


__all__ = [
    "GENERATIONAL_INVARIANT_IDS",
    "NOT_PERSISTED_STORES",
    "STORE_PROBE_PATHS",
    "BenchmarkBoundaryProbe",
    "BoundaryObservation",
    "ObservedOwnerStore",
    "OwnerStoreSnapshot",
    "blank_slate_check",
    "content_count",
    "evaluate_blank_slate",
    "evaluate_cultural_mutation",
    "evaluate_dependency_care",
    "evaluate_developmental_teaching",
    "evaluate_durable_records",
    "evaluate_event_journal",
    "evaluate_historical_memory",
    "evaluate_population_lifecycle",
    "evaluate_required_actions",
    "observed_institutional_memory",
    "observed_store_counts",
]
