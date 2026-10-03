"""Research fork materialization service (durable child runs).

Creates a self-contained child journal by rematerializing a parent objective
prefix under a new ``run_id``. Never rewrites parent history, never calls
``open_durable`` on a temporary parent restore engine, and never bit-copies
parent ``CommitHash`` values (``compute_commit_hash`` includes ``run_id``).

Research interventions mutate child-only runner config / subjective clones.
Named architecture presets expand via ``agents.cognition.architectures`` —
this module must never import ``experiments``.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Final

from agents.cognition.architectures import (
    ArchitectureCompatibilityError,
    ArchitectureModeSnapshot,
    get_architecture,
    validate_architecture_compatibility,
)
from agents.models import AgentId, Goal
from memory.beliefs import (
    BeliefId,
    BeliefValueKind,
    ClaimSubject,
    ClaimSubjectKind,
    ClaimValue,
    SemanticBelief,
    SemanticClaim,
)
from simulation.branching import (
    BeliefPatchPayload,
    BranchCreateRequest,
    BranchCreateResult,
    BranchError,
    BranchLineage,
    CommunicationRemoveTarget,
    ResearchIntervention,
    ResearchInterventionKind,
    SeedStreamPolicy,
    canonical_intervention_document,
    intervention_fingerprint,
    resolve_idempotent_create,
    seed_stream_token_for_intervention,
    validate_branch_create_request,
    validate_research_intervention,
)
from simulation.clock import Tick, require_exact_nonneg_int
from simulation.identifiers import derive_branch_id, derive_branch_run_id
from simulation.journal import (
    compute_commit_hash,
    hash_snapshot,
    hash_tick_events,
    hash_tick_payload,
    verify_commit_chain,
)
from simulation.models import RunId, SimulationRunConfig, StochasticIdentity
from simulation.persistence import (
    CommitHash,
    PayloadHash,
    RunControlRepository,
    RunCreateRequest,
    RunManifest,
    SimulationRunRepository,
    SnapshotId,
    SnapshotRepository,
    SubjectiveClonePort,
    TickAppendRequest,
    TickCommit,
    TickJournalRepository,
    WorldSnapshot,
)
from simulation.run_control import (
    ConfigAvailability,
    RunControlRecord,
    RunLifecycleState,
)
from simulation.runner_models import (
    AgentRunnerSpec,
    CognitiveBudgetMode,
    ImaginationMode,
    MemoryMode,
    MortalityMode,
    ProspectiveImaginationMode,
    ReflectionMode,
    SimulationRunnerConfig,
    V2CapabilityFlags,
)
from simulation.runner_serialization import (
    encode_runner_config,
    runner_config_fingerprint,
)
from simulation.subjective_state import SubjectiveOwnerSnapshot
from world.events import Asked, Talked, Told, WorldEvent
from world.identifiers import EntityId, require_stable_id

__all__ = [
    "BranchService",
    "InMemorySubjectiveClonePort",
    "InterventionApplicationResult",
    "ObjectiveForkMaterialization",
    "SubjectiveCloneResult",
    "apply_belief_patch",
    "apply_research_intervention",
    "derive_fork_snapshot_id",
    "rematerialize_event",
    "rematerialize_snapshot",
    "rematerialize_tick_append",
    "write_child_run_control_record",
]

_COMMUNICATION_PAYLOAD_TYPES: Final[tuple[type, ...]] = (Talked, Asked, Told)

_LOG: Final[logging.Logger] = logging.getLogger("simulation.branching")


@dataclass(frozen=True, slots=True)
class ObjectiveForkMaterialization:
    """Result of rematerializing a parent objective prefix into a child run."""

    parent_run_id: RunId
    child_run_id: RunId
    fork_tick: int
    child_manifest: RunManifest
    child_commits: tuple[TickCommit, ...]
    event_count: int
    bootstrap_snapshot_id: SnapshotId

    def __post_init__(self) -> None:
        if type(self.parent_run_id) is not RunId:
            raise TypeError("parent_run_id must be RunId")
        if type(self.child_run_id) is not RunId:
            raise TypeError("child_run_id must be RunId")
        object.__setattr__(
            self,
            "fork_tick",
            require_exact_nonneg_int("fork_tick", self.fork_tick),
        )
        if type(self.child_manifest) is not RunManifest:
            raise TypeError("child_manifest must be RunManifest")
        if type(self.bootstrap_snapshot_id) is not SnapshotId:
            raise TypeError("bootstrap_snapshot_id must be SnapshotId")
        object.__setattr__(
            self,
            "event_count",
            require_exact_nonneg_int("event_count", self.event_count),
        )


@dataclass(frozen=True, slots=True)
class SubjectiveCloneResult:
    """Counts-only receipt for a subjective clone into a child run."""

    parent_run_id: RunId
    child_run_id: RunId
    fork_tick: int
    owner_count: int
    memory_rows: int
    belief_rows: int
    relationship_rows: int
    goal_rows: int

    def __post_init__(self) -> None:
        if type(self.parent_run_id) is not RunId:
            raise TypeError("parent_run_id must be RunId")
        if type(self.child_run_id) is not RunId:
            raise TypeError("child_run_id must be RunId")
        for name in (
            "fork_tick",
            "owner_count",
            "memory_rows",
            "belief_rows",
            "relationship_rows",
            "goal_rows",
        ):
            object.__setattr__(
                self,
                name,
                require_exact_nonneg_int(name, getattr(self, name)),
            )


class InMemorySubjectiveClonePort:
    """In-memory subjective clone for unit proofs (not durable).

    Explicitly excludes cognition-trace rows, scientific evidence, and
    stream-outbox cursors — those stores are never consulted here.
    """

    def __init__(self) -> None:
        self._parent: dict[tuple[str, str], SubjectiveOwnerSnapshot] = {}
        self._parent_goals: dict[tuple[str, str], tuple[Goal, ...]] = {}
        self._child: dict[tuple[str, str], SubjectiveOwnerSnapshot] = {}
        self._child_goals: dict[tuple[str, str], tuple[Goal, ...]] = {}
        self._force_incomplete: bool = False

    def seed_parent_owner(
        self,
        *,
        run_id: RunId,
        owner_id: AgentId,
        snapshot: SubjectiveOwnerSnapshot,
        goals: tuple[Goal, ...] = (),
    ) -> None:
        key = (run_id.value, owner_id.value)
        self._parent[key] = snapshot
        self._parent_goals[key] = tuple(goals)

    def child_snapshot(
        self, *, run_id: RunId, owner_id: AgentId
    ) -> SubjectiveOwnerSnapshot | None:
        return self._child.get((run_id.value, owner_id.value))

    def child_goals(self, *, run_id: RunId, owner_id: AgentId) -> tuple[Goal, ...]:
        return self._child_goals.get((run_id.value, owner_id.value), ())

    def parent_snapshot(
        self, *, run_id: RunId, owner_id: AgentId
    ) -> SubjectiveOwnerSnapshot | None:
        return self._parent.get((run_id.value, owner_id.value))

    def replace_child_snapshot(
        self,
        *,
        run_id: RunId,
        owner_id: AgentId,
        snapshot: SubjectiveOwnerSnapshot,
    ) -> None:
        """Replace a previously cloned child owner snapshot (belief patches)."""
        if type(run_id) is not RunId or type(owner_id) is not AgentId:
            raise TypeError("replace_child_snapshot requires RunId and AgentId")
        if type(snapshot) is not SubjectiveOwnerSnapshot:
            raise TypeError("snapshot must be SubjectiveOwnerSnapshot")
        key = (run_id.value, owner_id.value)
        if key not in self._child:
            raise BranchError("belief_not_found", "child_owner_missing")
        self._child[key] = snapshot

    async def clone_as_of(
        self,
        *,
        parent_run_id: RunId,
        child_run_id: RunId,
        fork_tick: int,
    ) -> SubjectiveCloneResult:
        if type(parent_run_id) is not RunId or type(child_run_id) is not RunId:
            raise TypeError("clone_as_of requires RunId")
        tick = require_exact_nonneg_int("fork_tick", fork_tick)
        if self._force_incomplete:
            _LOG.error(
                "subjective_clone_incomplete parent_run_id=%s child_run_id=%s",
                parent_run_id.value,
                child_run_id.value,
            )
            raise BranchError("subjective_clone_incomplete")

        owners = sorted(
            {
                owner
                for (run_id, owner) in self._parent
                if run_id == parent_run_id.value
            }
        )
        memory_rows = 0
        belief_rows = 0
        relationship_rows = 0
        goal_rows = 0
        for owner in owners:
            key = (parent_run_id.value, owner)
            parent_snap = self._parent[key]
            memories = tuple(
                trace
                for trace in parent_snap.memories
                if trace.created_tick <= tick and trace.source_tick <= tick
            )
            beliefs = tuple(
                belief
                for belief in parent_snap.semantic_beliefs
                if belief.updated_tick <= tick
            )
            relationships = tuple(parent_snap.relationships)
            goals = tuple(self._parent_goals.get(key, ()))
            child_key = (child_run_id.value, owner)
            self._child[child_key] = SubjectiveOwnerSnapshot(
                memories=memories,
                semantic_beliefs=beliefs,
                relationships=relationships,
                reconstruction_count=sum(
                    1
                    for trace in memories
                    if trace.lineage.reconstruction_id is not None
                ),
            )
            self._child_goals[child_key] = goals
            memory_rows += len(memories)
            belief_rows += len(beliefs)
            relationship_rows += len(relationships)
            goal_rows += len(goals)
            _LOG.debug(
                "subjective_clone_owner parent_run_id=%s child_run_id=%s "
                "owner_id=%s memory_rows=%s belief_rows=%s "
                "relationship_rows=%s goal_rows=%s",
                parent_run_id.value,
                child_run_id.value,
                owner,
                len(memories),
                len(beliefs),
                len(relationships),
                len(goals),
            )

        result = SubjectiveCloneResult(
            parent_run_id=parent_run_id,
            child_run_id=child_run_id,
            fork_tick=tick,
            owner_count=len(owners),
            memory_rows=memory_rows,
            belief_rows=belief_rows,
            relationship_rows=relationship_rows,
            goal_rows=goal_rows,
        )
        _LOG.debug(
            "subjective_clone_complete parent_run_id=%s child_run_id=%s "
            "owner_count=%s memory_rows=%s belief_rows=%s "
            "relationship_rows=%s goal_rows=%s",
            parent_run_id.value,
            child_run_id.value,
            result.owner_count,
            result.memory_rows,
            result.belief_rows,
            result.relationship_rows,
            result.goal_rows,
        )
        return result


def derive_fork_snapshot_id(
    child_run_id: RunId,
    *,
    purpose: str,
    fork_tick: int,
    source_snapshot_id: str,
) -> SnapshotId:
    """Derive a child-scoped snapshot id (no wall clock / Python hash)."""
    if type(child_run_id) is not RunId:
        raise TypeError("derive_fork_snapshot_id requires RunId")
    purpose_token = require_stable_id("purpose", purpose)
    tick = require_exact_nonneg_int("fork_tick", fork_tick)
    source = require_stable_id("source_snapshot_id", source_snapshot_id)
    hasher = hashlib.sha256()
    hasher.update(b"research-fork-snapshot-v1")
    for part in (
        child_run_id.value.encode("utf-8"),
        purpose_token.encode("utf-8"),
        str(tick).encode("utf-8"),
        source.encode("utf-8"),
    ):
        hasher.update(len(part).to_bytes(4, "big") + part)
    return SnapshotId(hasher.hexdigest())


def rematerialize_event(event: WorldEvent, child_run_id: RunId) -> WorldEvent:
    """Rewrite event ``run_id`` for the child journal (payload otherwise intact)."""
    if type(event) is not WorldEvent:
        raise TypeError("rematerialize_event requires WorldEvent")
    if type(child_run_id) is not RunId:
        raise TypeError("rematerialize_event requires RunId")
    return replace(event, run_id=child_run_id.value)


def rematerialize_snapshot(
    snapshot: WorldSnapshot,
    *,
    child_run_id: RunId,
    snapshot_id: SnapshotId,
    config: SimulationRunConfig | None = None,
    predecessor_commit_hash: CommitHash | None = None,
    next_tick: Tick | None = None,
) -> WorldSnapshot:
    """Scope a snapshot to the child and recompute ``integrity_hash``."""
    if type(snapshot) is not WorldSnapshot:
        raise TypeError("rematerialize_snapshot requires WorldSnapshot")
    if type(child_run_id) is not RunId:
        raise TypeError("rematerialize_snapshot requires RunId")
    if type(snapshot_id) is not SnapshotId:
        raise TypeError("rematerialize_snapshot requires SnapshotId")
    resolved_config = snapshot.config if config is None else config
    if type(resolved_config) is not SimulationRunConfig:
        raise TypeError("config must be SimulationRunConfig")
    resolved_next = snapshot.next_tick if next_tick is None else next_tick
    if type(resolved_next) is not Tick:
        raise TypeError("next_tick must be Tick")
    if (
        predecessor_commit_hash is not None
        and type(predecessor_commit_hash) is not CommitHash
    ):
        raise TypeError("predecessor_commit_hash must be CommitHash or None")
    draft = WorldSnapshot(
        snapshot_id=snapshot_id,
        run_id=child_run_id,
        world_id=snapshot.world_id,
        seed=resolved_config.seed,
        config=resolved_config,
        registrations=snapshot.registrations,
        locations=snapshot.locations,
        bodies=snapshot.bodies,
        items=snapshot.items,
        resources=snapshot.resources,
        weather=snapshot.weather,
        next_tick=resolved_next,
        revision=snapshot.revision,
        event_schema_version=snapshot.event_schema_version,
        projector_version=snapshot.projector_version,
        persistence_codec_version=snapshot.persistence_codec_version,
        derivation_version=resolved_config.derivation_version
        if resolved_config.derivation_version is not None
        else snapshot.derivation_version,
        integrity_hash=PayloadHash("a" * 64),
        predecessor_commit_hash=predecessor_commit_hash,
        structures=snapshot.structures,
        production_jobs=snapshot.production_jobs,
        tool_marks=snapshot.tool_marks,
        active_hazards=snapshot.active_hazards,
        artifacts=snapshot.artifacts,
    )
    return WorldSnapshot(
        snapshot_id=draft.snapshot_id,
        run_id=draft.run_id,
        world_id=draft.world_id,
        seed=draft.seed,
        config=draft.config,
        registrations=draft.registrations,
        locations=draft.locations,
        bodies=draft.bodies,
        items=draft.items,
        resources=draft.resources,
        weather=draft.weather,
        next_tick=draft.next_tick,
        revision=draft.revision,
        event_schema_version=draft.event_schema_version,
        projector_version=draft.projector_version,
        persistence_codec_version=draft.persistence_codec_version,
        derivation_version=draft.derivation_version,
        integrity_hash=hash_snapshot(draft),
        predecessor_commit_hash=draft.predecessor_commit_hash,
        structures=draft.structures,
        production_jobs=draft.production_jobs,
        tool_marks=draft.tool_marks,
        active_hazards=draft.active_hazards,
        artifacts=draft.artifacts,
    )


def rematerialize_tick_append(
    *,
    parent_commit: TickCommit,
    parent_events: Sequence[WorldEvent],
    child_run_id: RunId,
    predecessor_commit_hash: CommitHash | None,
    snapshot: WorldSnapshot | None = None,
) -> TickAppendRequest:
    """Build a child tick append with recomputed identity (no parent hashes)."""
    if type(parent_commit) is not TickCommit:
        raise TypeError("parent_commit must be TickCommit")
    if type(child_run_id) is not RunId:
        raise TypeError("child_run_id must be RunId")
    child_events = tuple(
        rematerialize_event(event, child_run_id) for event in parent_events
    )
    idempotency_key = (
        f"research-fork-{child_run_id.value}-tick-{parent_commit.tick.value}"
    )
    return TickAppendRequest(
        run_id=child_run_id,
        tick=parent_commit.tick,
        expected_base_revision=parent_commit.base_revision,
        expected_predecessor_commit_hash=predecessor_commit_hash,
        idempotency_key=idempotency_key,
        events=child_events,
        snapshot=snapshot,
    )


@dataclass(frozen=True, slots=True)
class InterventionApplicationResult:
    """Child-only outcome of applying one closed research intervention."""

    runner_config: SimulationRunnerConfig
    seed_stream_policy: SeedStreamPolicy
    removed_communication: Mapping[str, object] | None = None
    belief_patched: bool = False

    def __post_init__(self) -> None:
        if type(self.runner_config) is not SimulationRunnerConfig:
            raise TypeError("runner_config must be SimulationRunnerConfig")
        if type(self.seed_stream_policy) is not SeedStreamPolicy:
            raise TypeError("seed_stream_policy must be SeedStreamPolicy")
        if type(self.belief_patched) is not bool:
            raise TypeError("belief_patched must be bool")
        if self.removed_communication is not None and not isinstance(
            self.removed_communication, Mapping
        ):
            raise TypeError("removed_communication must be a mapping or None")


def _select_agent_ids(
    config: SimulationRunnerConfig,
    agent_ids: Sequence[str],
) -> frozenset[str]:
    if not agent_ids:
        return frozenset(agent.agent_id.value for agent in config.agents)
    known = {agent.agent_id.value for agent in config.agents}
    missing = [agent_id for agent_id in agent_ids if agent_id not in known]
    if missing:
        _LOG.error(
            "research_intervention_rejected reason_code=%s",
            "invalid_intervention",
        )
        raise BranchError("invalid_intervention", "unknown_agent_id")
    return frozenset(agent_ids)


def _map_agent_cognition(
    config: SimulationRunnerConfig,
    targets: frozenset[str],
    *,
    schema_version: str | None = None,
    **cognition_updates: object,
) -> SimulationRunnerConfig:
    agents: list[AgentRunnerSpec] = []
    for agent in config.agents:
        if agent.agent_id.value not in targets:
            agents.append(agent)
            continue
        cognition = replace(agent.cognition, **cognition_updates)
        agents.append(replace(agent, cognition=cognition))
    if schema_version is None:
        return replace(config, agents=tuple(agents))
    return replace(config, agents=tuple(agents), schema_version=schema_version)


def _flags_for_architecture(required_flags: frozenset[str]) -> V2CapabilityFlags:
    enabled = set(required_flags)
    return V2CapabilityFlags(
        advanced_social_inference="advanced_social_inference" in enabled,
        multi_hop_testimony_tracking=False,
        predictive_world_model="predictive_world_model" in enabled,
        extended_self_model="extended_self_model" in enabled,
        short_term_emotional_state="short_term_emotional_state" in enabled,
    )


def _architecture_mode_snapshot(
    config: SimulationRunnerConfig,
    *,
    agent_id: str,
) -> ArchitectureModeSnapshot:
    agent = next(a for a in config.agents if a.agent_id.value == agent_id)
    cognition = agent.cognition
    flags = {
        "advanced_social_inference": config.capability_flags.advanced_social_inference,
        "multi_hop_testimony_tracking": (
            config.capability_flags.multi_hop_testimony_tracking
        ),
        "predictive_world_model": config.capability_flags.predictive_world_model,
        "extended_self_model": config.capability_flags.extended_self_model,
        "short_term_emotional_state": (
            config.capability_flags.short_term_emotional_state
        ),
    }
    modes = {
        "memory_mode": cognition.memory_mode.value,
        "imagination_mode": cognition.imagination_mode.value,
        "reflection_mode": cognition.reflection_mode.value,
        "prospective_mode": cognition.prospective_mode.value,
        "mortality_appraisal": config.mortality_mode.value,
    }
    return ArchitectureModeSnapshot(flags=flags, modes=modes)


def _expand_agent_architecture(
    config: SimulationRunnerConfig,
    *,
    architecture_id: str,
    agent_ids: Sequence[str],
) -> SimulationRunnerConfig:
    try:
        definition = get_architecture(architecture_id)
    except ArchitectureCompatibilityError as exc:
        _LOG.error(
            "research_intervention_rejected reason_code=%s",
            exc.reason_code,
        )
        raise BranchError(exc.reason_code) from exc
    modes = definition.capabilities.required_modes
    targets = _select_agent_ids(config, agent_ids)
    expanded = _map_agent_cognition(
        config,
        targets,
        memory_mode=MemoryMode(modes["memory_mode"]),
        imagination_mode=ImaginationMode(modes["imagination_mode"]),
        reflection_mode=ReflectionMode(modes["reflection_mode"]),
        prospective_mode=ProspectiveImaginationMode(modes["prospective_mode"]),
    )
    expanded = replace(
        expanded,
        mortality_mode=MortalityMode(modes["mortality_appraisal"]),
        capability_flags=_flags_for_architecture(
            frozenset(definition.capabilities.required_flags)
        ),
        schema_version=definition.schema_version,
    )
    snapshot = _architecture_mode_snapshot(
        expanded, agent_id=next(iter(targets))
    )
    try:
        validate_architecture_compatibility(definition, snapshot)
    except ArchitectureCompatibilityError as exc:
        _LOG.error(
            "research_intervention_rejected reason_code=%s",
            exc.reason_code,
        )
        raise BranchError(exc.reason_code) from exc
    _LOG.debug(
        "research_intervention_architecture_expanded architecture_id=%s "
        "schema_version=%s target_count=%s",
        architecture_id,
        definition.schema_version,
        len(targets),
    )
    return expanded


def _locate_communication_event(
    events: Sequence[WorldEvent],
    target: CommunicationRemoveTarget,
) -> WorldEvent:
    for event in events:
        if target.event_id is not None:
            if event.event_id.value == target.event_id:
                return event
            continue
        if event.tick == target.tick and event.sequence == target.sequence:
            return event
    _LOG.error(
        "research_intervention_rejected reason_code=%s",
        "invalid_intervention",
    )
    raise BranchError("invalid_intervention", "communication_event_missing")


def _validate_communication_remove(
    *,
    fork_tick: int,
    target: CommunicationRemoveTarget,
    parent_events: Sequence[WorldEvent],
) -> dict[str, object]:
    event = _locate_communication_event(parent_events, target)
    if not isinstance(event.details, _COMMUNICATION_PAYLOAD_TYPES):
        _LOG.error(
            "research_intervention_rejected reason_code=%s",
            "invalid_intervention",
        )
        raise BranchError("invalid_intervention", "not_communication_event")
    if event.tick < fork_tick:
        _LOG.error(
            "research_intervention_rejected reason_code=%s",
            "intervention_past_event",
        )
        raise BranchError("intervention_past_event")
    record: dict[str, object] = {
        "event_id": event.event_id.value,
        "tick": event.tick,
        "sequence": event.sequence,
        "kind": type(event.details).__name__,
    }
    _LOG.debug(
        "research_intervention_communication_remove event_id=%s tick=%s "
        "sequence=%s",
        event.event_id.value,
        event.tick,
        event.sequence,
    )
    return record


def _claim_subject_from_patch(patch: BeliefPatchPayload) -> ClaimSubject:
    if patch.subject_kind == "agent":
        return ClaimSubject(
            kind=ClaimSubjectKind.AGENT, agent_id=AgentId(patch.subject_id)
        )
    if patch.subject_kind == "entity":
        return ClaimSubject(
            kind=ClaimSubjectKind.ENTITY, entity_id=EntityId(patch.subject_id)
        )
    # subject_kind == "self" — claim about the belief owner.
    return ClaimSubject(
        kind=ClaimSubjectKind.AGENT, agent_id=AgentId(patch.owner_id)
    )


def _claim_value_from_patch(patch: BeliefPatchPayload) -> ClaimValue:
    kind = BeliefValueKind(patch.value_kind)
    if kind is BeliefValueKind.BOOL:
        assert patch.bool_value is not None
        return ClaimValue(kind=kind, bool_value=patch.bool_value)
    if kind is BeliefValueKind.NUMBER:
        assert patch.number_value is not None
        return ClaimValue(kind=kind, number_value=float(patch.number_value))
    if kind is BeliefValueKind.TEXT:
        assert patch.text_value is not None
        return ClaimValue(kind=kind, text_value=patch.text_value)
    if kind is BeliefValueKind.AGENT:
        assert patch.agent_value is not None
        return ClaimValue(kind=kind, agent_id=AgentId(patch.agent_value))
    assert patch.entity_value is not None
    return ClaimValue(kind=kind, entity_id=EntityId(patch.entity_value))


def apply_belief_patch(
    snapshot: SubjectiveOwnerSnapshot,
    patch: BeliefPatchPayload,
) -> SubjectiveOwnerSnapshot:
    """Replace one owner belief on a child subjective snapshot."""
    if type(snapshot) is not SubjectiveOwnerSnapshot:
        raise TypeError("snapshot must be SubjectiveOwnerSnapshot")
    if type(patch) is not BeliefPatchPayload:
        raise TypeError("patch must be BeliefPatchPayload")
    owner = AgentId(patch.owner_id)
    belief_id = BeliefId(patch.belief_id)
    found: SemanticBelief | None = None
    for belief in snapshot.semantic_beliefs:
        if belief.owner_id == owner and belief.belief_id == belief_id:
            found = belief
            break
    if found is None:
        _LOG.error(
            "research_intervention_rejected reason_code=%s",
            "belief_not_found",
        )
        raise BranchError("belief_not_found")
    claim = SemanticClaim(
        subject=_claim_subject_from_patch(patch),
        predicate=patch.predicate,
        value=_claim_value_from_patch(patch),
    )
    revised = replace(found, claim=claim)
    beliefs = tuple(
        (
            revised
            if belief.belief_id == belief_id and belief.owner_id == owner
            else belief
        )
        for belief in snapshot.semantic_beliefs
    )
    return SubjectiveOwnerSnapshot(
        memories=snapshot.memories,
        semantic_beliefs=beliefs,
        relationships=snapshot.relationships,
        reconstruction_count=snapshot.reconstruction_count,
    )


def apply_research_intervention(
    config: SimulationRunnerConfig,
    intervention: ResearchIntervention,
    *,
    fork_tick: int,
    parent_events: Sequence[WorldEvent] | None = None,
) -> InterventionApplicationResult:
    """Apply one closed research intervention to a child runner config.

    Belief patches are validated here but applied via ``apply_belief_patch``
    against the child subjective clone. ``COMMUNICATION_REMOVE`` validates
    parent events and returns a lineage record without rewriting history.
    """
    if type(config) is not SimulationRunnerConfig:
        raise TypeError("config must be SimulationRunnerConfig")
    validated = validate_research_intervention(intervention)
    tick = require_exact_nonneg_int("fork_tick", fork_tick)
    kind = validated.kind
    removed: Mapping[str, object] | None = None
    child = config
    policy = SeedStreamPolicy.INHERIT

    if kind is ResearchInterventionKind.MEMORY_ARCHITECTURE:
        assert validated.memory_mode is not None
        targets = _select_agent_ids(config, validated.agent_ids)
        child = _map_agent_cognition(
            config, targets, memory_mode=validated.memory_mode
        )
    elif kind is ResearchInterventionKind.BELIEF_PATCH:
        # Config unchanged; subjective patch applied after clone.
        assert validated.belief_patch is not None
        _LOG.debug(
            "research_intervention_belief_patch_pending owner_id=%s belief_id=%s",
            validated.belief_patch.owner_id,
            validated.belief_patch.belief_id,
        )
    elif kind is ResearchInterventionKind.COMMUNICATION_REMOVE:
        assert validated.communication_remove is not None
        if parent_events is None:
            _LOG.error(
                "research_intervention_rejected reason_code=%s",
                "invalid_intervention",
            )
            raise BranchError("invalid_intervention", "parent_events_required")
        removed = _validate_communication_remove(
            fork_tick=tick,
            target=validated.communication_remove,
            parent_events=parent_events,
        )
    elif kind is ResearchInterventionKind.MORTALITY_DISABLED:
        child = replace(config, mortality_mode=MortalityMode.DISABLED)
    elif kind is ResearchInterventionKind.COGNITIVE_BUDGET:
        assert validated.cognitive_budget_mode is not None
        targets = _select_agent_ids(config, validated.agent_ids)
        schema_version = (
            "runner-config-v22"
            if validated.cognitive_budget_mode is CognitiveBudgetMode.ENFORCED
            else None
        )
        child = _map_agent_cognition(
            config,
            targets,
            schema_version=schema_version,
            cognitive_budget_mode=validated.cognitive_budget_mode,
            cognitive_budget_limits=validated.cognitive_budget_limits,
        )
    elif kind is ResearchInterventionKind.AGENT_ARCHITECTURE:
        assert validated.architecture_id is not None
        child = _expand_agent_architecture(
            config,
            architecture_id=validated.architecture_id,
            agent_ids=validated.agent_ids,
        )
    elif kind is ResearchInterventionKind.ALTERNATE_SEED_STREAM:
        assert validated.alternate_stochastic_identity is not None
        child = replace(
            config,
            stochastic_identity=validated.alternate_stochastic_identity,
        )
        policy = SeedStreamPolicy.ALTERNATE
    else:  # pragma: no cover - closed enum
        raise BranchError("invalid_intervention", "unknown_kind")

    # Default inherit: keep parent's stochastic_identity (already on config).
    if policy is SeedStreamPolicy.INHERIT:
        if child.stochastic_identity != config.stochastic_identity:
            child = replace(
                child, stochastic_identity=config.stochastic_identity
            )

    _LOG.debug(
        "research_intervention_applied kind=%s seed_policy=%s",
        kind.value,
        policy.value,
    )
    return InterventionApplicationResult(
        runner_config=child,
        seed_stream_policy=policy,
        removed_communication=removed,
        belief_patched=False,
    )


def write_child_run_control_record(
    *,
    child_run_id: RunId,
    runner_config: SimulationRunnerConfig,
    ticks_committed: int,
) -> RunControlRecord:
    """Build a child ``RunControlRecord`` for resume/rehydrate (no payload logs)."""
    if type(child_run_id) is not RunId:
        raise TypeError("child_run_id must be RunId")
    if type(runner_config) is not SimulationRunnerConfig:
        raise TypeError("runner_config must be SimulationRunnerConfig")
    committed = require_exact_nonneg_int("ticks_committed", ticks_committed)
    payload = encode_runner_config(runner_config)
    fingerprint = runner_config_fingerprint(runner_config)
    record = RunControlRecord(
        run_id=child_run_id,
        lifecycle_state=RunLifecycleState.READY,
        lifecycle_version=0,
        config_availability=ConfigAvailability.AVAILABLE,
        ticks_committed=committed,
        progress_cursor=committed,
        config_schema_version=runner_config.schema_version,
        config_fingerprint=fingerprint,
        config_payload=payload,
        lease=None,
        terminal_reason_code=None,
    )
    _LOG.debug(
        "research_fork_run_control_written child_run_id=%s lifecycle=%s",
        child_run_id.value,
        record.lifecycle_state.value,
    )
    return record


def _child_simulation_run_config(
    parent: SimulationRunConfig,
    *,
    stochastic_identity: StochasticIdentity,
) -> SimulationRunConfig:
    return SimulationRunConfig(
        seed=parent.seed,
        physical_rules=parent.physical_rules,
        derivation_version=parent.derivation_version,
        stochastic_identity=stochastic_identity,
    )


class BranchService:
    """Materialize research forks as distinct durable child runs."""

    __slots__ = (
        "_journal",
        "_lineage",
        "_run_control",
        "_runs",
        "_snapshots",
        "_subjective_clone",
    )

    def __init__(
        self,
        *,
        runs: SimulationRunRepository,
        journal: TickJournalRepository,
        snapshots: SnapshotRepository,
        lineage: object | None = None,
        subjective_clone: SubjectiveClonePort | None = None,
        run_control: RunControlRepository | None = None,
    ) -> None:
        self._runs = runs
        self._journal = journal
        self._snapshots = snapshots
        self._lineage = lineage
        self._subjective_clone = subjective_clone
        self._run_control = run_control

    async def clone_subjective_state(
        self,
        *,
        parent_run_id: RunId,
        child_run_id: RunId,
        fork_tick: int,
    ) -> SubjectiveCloneResult:
        """Clone owner-scoped subjective stores into the child run scope."""
        if self._subjective_clone is None:
            _LOG.error(
                "subjective_clone_incomplete parent_run_id=%s child_run_id=%s",
                parent_run_id.value,
                child_run_id.value,
            )
            raise BranchError("subjective_clone_incomplete")
        result = await self._subjective_clone.clone_as_of(
            parent_run_id=parent_run_id,
            child_run_id=child_run_id,
            fork_tick=fork_tick,
        )
        if type(result) is not SubjectiveCloneResult:
            raise TypeError("SubjectiveClonePort must return SubjectiveCloneResult")
        return result

    async def materialize_objective_fork(
        self,
        *,
        parent_run_id: RunId,
        child_run_id: RunId,
        fork_tick: int,
        child_config: SimulationRunConfig | None = None,
    ) -> ObjectiveForkMaterialization:
        """Rematerialize parent objective prefix ``event.tick < fork_tick``."""
        if type(parent_run_id) is not RunId:
            raise TypeError("parent_run_id must be RunId")
        if type(child_run_id) is not RunId:
            raise TypeError("child_run_id must be RunId")
        tick = require_exact_nonneg_int("fork_tick", fork_tick)

        parent_manifest = await self._runs.get_run(parent_run_id)
        if parent_manifest is None:
            _LOG.error(
                "research_fork_rejected reason_code=%s parent_run_id=%s",
                "unknown_parent",
                parent_run_id.value,
            )
            raise BranchError("unknown_parent")

        head_next = await self._durable_head_next_tick(parent_run_id)
        if tick > head_next.value:
            _LOG.error(
                "research_fork_rejected reason_code=%s parent_run_id=%s "
                "fork_tick=%s head=%s",
                "fork_tick_ahead_of_head",
                parent_run_id.value,
                tick,
                head_next.value,
            )
            raise BranchError("fork_tick_ahead_of_head")

        parent_bootstrap = await self._snapshots.get_latest_at_or_before(
            parent_run_id, Tick(0)
        )
        if parent_bootstrap is None or parent_bootstrap.next_tick != Tick(0):
            _LOG.error(
                "research_fork_rejected reason_code=%s parent_run_id=%s",
                "bootstrap_missing",
                parent_run_id.value,
            )
            raise BranchError("invalid_intervention", "bootstrap_missing")

        resolved_config = (
            parent_manifest.config if child_config is None else child_config
        )
        if type(resolved_config) is not SimulationRunConfig:
            raise TypeError("child_config must be SimulationRunConfig")

        parent_commits = await self._journal.list_tick_commits(
            parent_run_id, from_tick=Tick(0), to_tick=None
        )
        prefix_commits = tuple(
            commit for commit in parent_commits if commit.tick.value < tick
        )
        # Capture parent commit hashes before any child writes for isolation proofs.
        parent_commit_hashes = {
            commit.tick.value: commit.commit_hash.value for commit in parent_commits
        }

        bootstrap_id = derive_fork_snapshot_id(
            child_run_id,
            purpose="bootstrap",
            fork_tick=0,
            source_snapshot_id=parent_bootstrap.snapshot_id.value,
        )
        child_bootstrap = rematerialize_snapshot(
            parent_bootstrap,
            child_run_id=child_run_id,
            snapshot_id=bootstrap_id,
            config=resolved_config,
            predecessor_commit_hash=None,
            next_tick=Tick(0),
        )
        child_manifest = await self._runs.create_run(
            RunCreateRequest(
                run_id=child_run_id,
                world_id=parent_manifest.world_id,
                seed=resolved_config.seed,
                config=resolved_config,
                bootstrap=child_bootstrap,
                derivation_version=(
                    resolved_config.derivation_version
                    if resolved_config.derivation_version is not None
                    else parent_manifest.derivation_version
                ),
                event_schema_version=parent_manifest.event_schema_version,
                projector_version=parent_manifest.projector_version,
                persistence_codec_version=parent_manifest.persistence_codec_version,
            )
        )

        child_commits: list[TickCommit] = []
        predecessor: CommitHash | None = None
        event_count = 0
        for parent_commit in prefix_commits:
            parent_events = await self._journal.list_events(
                parent_run_id,
                from_tick=parent_commit.tick,
                to_tick=parent_commit.tick,
                limit=10_000_000,
                offset=0,
            )
            fork_snapshot: WorldSnapshot | None = None
            if parent_commit.tick.value == tick - 1:
                # Attach fork-point checkpoint when rematerializing the last
                # prefix tick so the child resumes at ``fork_tick``.
                parent_fork_snap = await self._snapshots.get_latest_at_or_before(
                    parent_run_id, Tick(tick)
                )
                if (
                    parent_fork_snap is not None
                    and parent_fork_snap.next_tick.value == tick
                ):
                    # Predecessor is filled after we know the child commit hash.
                    fork_snapshot = rematerialize_snapshot(
                        parent_fork_snap,
                        child_run_id=child_run_id,
                        snapshot_id=derive_fork_snapshot_id(
                            child_run_id,
                            purpose="fork-point",
                            fork_tick=tick,
                            source_snapshot_id=parent_fork_snap.snapshot_id.value,
                        ),
                        config=resolved_config,
                        predecessor_commit_hash=None,
                        next_tick=Tick(tick),
                    )

            # First pass without snapshot when we must bind predecessor hash.
            request = rematerialize_tick_append(
                parent_commit=parent_commit,
                parent_events=parent_events,
                child_run_id=child_run_id,
                predecessor_commit_hash=predecessor,
                snapshot=None,
            )
            # Compute expected child commit hash to bind snapshot predecessor.
            payload = hash_tick_payload(request.events)
            event_hashes = hash_tick_events(request.events)
            expected_commit_hash = compute_commit_hash(
                predecessor_commit_hash=predecessor,
                run_id=child_run_id,
                tick=parent_commit.tick,
                base_revision=parent_commit.base_revision,
                resulting_revision=parent_commit.resulting_revision,
                event_hashes=event_hashes,
                payload_hash=payload,
            )
            if fork_snapshot is not None:
                fork_snapshot = rematerialize_snapshot(
                    fork_snapshot,
                    child_run_id=child_run_id,
                    snapshot_id=fork_snapshot.snapshot_id,
                    config=resolved_config,
                    predecessor_commit_hash=expected_commit_hash,
                    next_tick=Tick(tick),
                )
                request = rematerialize_tick_append(
                    parent_commit=parent_commit,
                    parent_events=parent_events,
                    child_run_id=child_run_id,
                    predecessor_commit_hash=predecessor,
                    snapshot=fork_snapshot,
                )

            child_commit = await self._journal.append_tick(request)
            if child_commit.commit_hash.value == parent_commit.commit_hash.value:
                _LOG.error(
                    "research_fork_rejected reason_code=%s tick=%s",
                    "commit_hash_collision",
                    parent_commit.tick.value,
                )
                raise BranchError("branch_identity_conflict", "commit_hash_collision")
            child_commits.append(child_commit)
            predecessor = child_commit.commit_hash
            event_count += len(request.events)

        verify_commit_chain(tuple(child_commits))

        # Parent hashes must be unchanged after child materialization.
        parent_after = await self._journal.list_tick_commits(
            parent_run_id, from_tick=Tick(0), to_tick=None
        )
        for commit in parent_after:
            expected = parent_commit_hashes.get(commit.tick.value)
            if expected is not None and commit.commit_hash.value != expected:
                _LOG.error(
                    "research_fork_rejected reason_code=%s parent_run_id=%s",
                    "parent_history_mutated",
                    parent_run_id.value,
                )
                raise BranchError("branch_identity_conflict", "parent_history_mutated")

        _LOG.info(
            "research_fork_objective_materialized parent_run_id=%s "
            "child_run_id=%s fork_tick=%s event_count=%s",
            parent_run_id.value,
            child_run_id.value,
            tick,
            event_count,
        )
        _LOG.debug(
            "research_fork_objective_rehash parent_run_id=%s child_run_id=%s "
            "commit_count=%s bootstrap_snapshot_id=%s",
            parent_run_id.value,
            child_run_id.value,
            len(child_commits),
            bootstrap_id.value,
        )
        return ObjectiveForkMaterialization(
            parent_run_id=parent_run_id,
            child_run_id=child_run_id,
            fork_tick=tick,
            child_manifest=child_manifest,
            child_commits=tuple(child_commits),
            event_count=event_count,
            bootstrap_snapshot_id=bootstrap_id,
        )

    async def write_child_run_control(
        self,
        *,
        child_run_id: RunId,
        runner_config: SimulationRunnerConfig,
        ticks_committed: int,
    ) -> RunControlRecord:
        """Persist child run-control so rehydrate/list paths observe the fork."""
        if self._run_control is None:
            _LOG.error(
                "research_fork_rejected reason_code=%s child_run_id=%s",
                "invalid_intervention",
                child_run_id.value,
            )
            raise BranchError("invalid_intervention", "run_control_missing")
        record = write_child_run_control_record(
            child_run_id=child_run_id,
            runner_config=runner_config,
            ticks_committed=ticks_committed,
        )
        stored = await self._run_control.upsert_configured(record)
        return stored

    async def create_research_fork(
        self,
        request: BranchCreateRequest,
        *,
        parent_runner_config: SimulationRunnerConfig,
    ) -> BranchCreateResult:
        """Materialize a child run, apply one intervention, and record lineage."""
        if type(parent_runner_config) is not SimulationRunnerConfig:
            raise TypeError("parent_runner_config must be SimulationRunnerConfig")
        validated = validate_branch_create_request(request)
        fingerprint = intervention_fingerprint(validated.intervention)
        seed_token = seed_stream_token_for_intervention(validated.intervention)
        child_run_id = derive_branch_run_id(
            validated.parent_run_id,
            validated.fork_tick,
            fingerprint,
            seed_token,
        )
        branch_id = derive_branch_id(
            validated.parent_run_id,
            validated.fork_tick,
            fingerprint,
            seed_token,
        )

        existing: BranchLineage | None = None
        if self._lineage is not None:
            existing = await self._lineage.get_lineage(child_run_id=child_run_id)  # type: ignore[union-attr]
            if existing is not None and type(existing) is not BranchLineage:
                raise TypeError("lineage repository must return BranchLineage")
        hit = resolve_idempotent_create(
            child_run_id=child_run_id,
            request=validated,
            existing=existing,
        )
        if hit is not None:
            return hit

        parent_events: tuple[WorldEvent, ...] = ()
        if (
            validated.intervention.kind
            is ResearchInterventionKind.COMMUNICATION_REMOVE
        ):
            parent_events = tuple(
                await self._journal.list_events(
                    validated.parent_run_id,
                    from_tick=Tick(0),
                    to_tick=None,
                    limit=10_000_000,
                    offset=0,
                )
            )

        applied = apply_research_intervention(
            parent_runner_config,
            validated.intervention,
            fork_tick=validated.fork_tick,
            parent_events=parent_events,
        )

        parent_manifest = await self._runs.get_run(validated.parent_run_id)
        if parent_manifest is None:
            raise BranchError("unknown_parent")
        child_run_config = _child_simulation_run_config(
            parent_manifest.config,
            stochastic_identity=applied.runner_config.stochastic_identity,
        )

        materialization = await self.materialize_objective_fork(
            parent_run_id=validated.parent_run_id,
            child_run_id=child_run_id,
            fork_tick=validated.fork_tick,
            child_config=child_run_config,
        )
        await self.clone_subjective_state(
            parent_run_id=validated.parent_run_id,
            child_run_id=child_run_id,
            fork_tick=validated.fork_tick,
        )

        belief_patched = False
        if validated.intervention.kind is ResearchInterventionKind.BELIEF_PATCH:
            patch = validated.intervention.belief_patch
            assert patch is not None
            if not isinstance(self._subjective_clone, InMemorySubjectiveClonePort):
                _LOG.error(
                    "research_intervention_rejected reason_code=%s",
                    "invalid_intervention",
                )
                raise BranchError(
                    "invalid_intervention", "belief_patch_requires_clone_port"
                )
            owner = AgentId(patch.owner_id)
            snap = self._subjective_clone.child_snapshot(
                run_id=child_run_id, owner_id=owner
            )
            if snap is None:
                raise BranchError("belief_not_found", "child_owner_missing")
            patched = apply_belief_patch(snap, patch)
            self._subjective_clone.replace_child_snapshot(
                run_id=child_run_id, owner_id=owner, snapshot=patched
            )
            belief_patched = True

        if self._run_control is not None:
            await self.write_child_run_control(
                child_run_id=child_run_id,
                runner_config=applied.runner_config,
                ticks_committed=validated.fork_tick,
            )

        head_next = await self._durable_head_next_tick(validated.parent_run_id)
        lineage = BranchLineage(
            child_run_id=child_run_id,
            parent_run_id=validated.parent_run_id,
            fork_tick=validated.fork_tick,
            intervention_kind=validated.intervention.kind,
            intervention_fingerprint=fingerprint,
            intervention_canonical=canonical_intervention_document(
                validated.intervention
            ),
            branch_id=branch_id,
            created_as_of_parent_head=head_next.value,
        )
        if self._lineage is not None:
            await self._lineage.put_lineage(lineage)  # type: ignore[union-attr]

        _LOG.info(
            "research_fork_created parent_run_id=%s child_run_id=%s "
            "fork_tick=%s kind=%s fingerprint=%s",
            validated.parent_run_id.value,
            child_run_id.value,
            validated.fork_tick,
            validated.intervention.kind.value,
            fingerprint,
        )
        _LOG.debug(
            "research_fork_created_detail branch_id=%s event_count=%s "
            "belief_patched=%s removed_communication=%s",
            branch_id,
            materialization.event_count,
            belief_patched,
            applied.removed_communication is not None,
        )
        return BranchCreateResult(
            child_run_id=child_run_id,
            branch_id=branch_id,
            lineage=lineage,
            idempotent_hit=False,
        )

    async def _durable_head_next_tick(self, run_id: RunId) -> Tick:
        commits = await self._journal.list_tick_commits(
            run_id, from_tick=Tick(0), to_tick=None
        )
        if not commits:
            return Tick(0)
        return Tick(commits[-1].tick.value + 1)
