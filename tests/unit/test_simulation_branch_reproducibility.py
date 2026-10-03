"""Hard reproducibility proofs for research forks (not smoke-only)."""

from __future__ import annotations

import ast
import logging
from pathlib import Path

import pytest

from agents.cognition.counterfactual import CounterfactualScenario
from agents.cognition.models import ImaginedFuture
from agents.models import AgentId
from memory.beliefs import (
    BeliefActivationState,
    BeliefConfidenceState,
    BeliefId,
    BeliefPolicyRef,
    BeliefRevisionId,
    BeliefValueKind,
    ClaimSubject,
    ClaimSubjectKind,
    ClaimValue,
    SemanticBelief,
    SemanticClaim,
)
from simulation.bootstrap import AgentRegistration
from simulation.branch_service import BranchService, InMemorySubjectiveClonePort
from simulation.branching import (
    BranchCreateRequest,
    BranchLineage,
    InMemoryBranchLineageRepository,
    ResearchIntervention,
    ResearchInterventionKind,
    canonical_intervention_document,
    intervention_fingerprint,
    resolve_idempotent_create,
    seed_stream_token_for_intervention,
)
from simulation.clock import Tick
from simulation.identifiers import derive_branch_id, derive_branch_run_id, derive_run_id
from simulation.journal import (
    compute_commit_hash,
    hash_snapshot,
    hash_tick_events,
    hash_tick_payload,
)
from simulation.memory_run_control import InMemoryRunControlRepository
from simulation.models import (
    DERIVATION_VERSION,
    DERIVATION_VERSION_V3,
    RunId,
    SimulationRunConfig,
    StochasticIdentity,
)
from simulation.persistence import (
    EVENT_SCHEMA_VERSION,
    PERSISTENCE_CODEC_VERSION,
    PROJECTOR_VERSION,
    PayloadHash,
    RunCreateRequest,
    RunManifest,
    SnapshotId,
    TickAppendRequest,
    TickCommit,
    WorldSnapshot,
)
from simulation.runner_models import FinalizedTickReceipt, MemoryMode
from simulation.runner_serialization import exact_trajectory_hash
from tests.simulation_helpers import make_location, make_weather
from tests.unit.test_runner_serialization import _config
from world.events import Waited, WorldEvent, make_replayable_event
from world.identifiers import (
    EntityId,
    EventId,
    RequestId,
    WorldId,
    WorldRevision,
)
from world.models import AgentBody, LifeStatus, default_physical_rules
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    TemperatureCelsius,
    Thirst,
)

pytestmark = pytest.mark.unit

_SRC = Path(__file__).resolve().parents[2] / "src"


def _memory_intervention() -> ResearchIntervention:
    return ResearchIntervention(
        kind=ResearchInterventionKind.MEMORY_ARCHITECTURE,
        agent_ids=("agent-1",),
        memory_mode=MemoryMode.REFERENCE,
    )


def _alive() -> AgentBody:
    return AgentBody(
        entity_id=EntityId("body-1"),
        location_id=EntityId("loc-1"),
        health=Health(100),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )


def _run_config(*, derivation_v3: bool = False) -> SimulationRunConfig:
    if not derivation_v3:
        return SimulationRunConfig(seed=7)
    return SimulationRunConfig(
        seed=7,
        physical_rules=default_physical_rules(),
        derivation_version=DERIVATION_VERSION_V3,
        stochastic_identity=StochasticIdentity("cmp-codec"),
    )


def _snapshot(
    *,
    run_id: str = "parent-run",
    snapshot_id: str = "snap-0",
    next_tick: int = 0,
    revision: int = 0,
    predecessor: object | None = None,
    derivation_v3: bool = False,
) -> WorldSnapshot:
    draft = WorldSnapshot(
        snapshot_id=SnapshotId(snapshot_id),
        run_id=RunId(run_id),
        world_id=WorldId("world-1"),
        seed=7,
        config=_run_config(derivation_v3=derivation_v3),
        registrations=(AgentRegistration(AgentId("agent-1"), EntityId("body-1")),),
        locations=(make_location("loc-1", name="Camp"),),
        bodies=(_alive(),),
        items=(),
        resources=(),
        weather=(make_weather(),),
        next_tick=Tick(next_tick),
        revision=WorldRevision(revision),
        event_schema_version=EVENT_SCHEMA_VERSION,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version=PERSISTENCE_CODEC_VERSION,
        derivation_version=(
            DERIVATION_VERSION_V3 if derivation_v3 else DERIVATION_VERSION
        ),
        integrity_hash=PayloadHash("a" * 64),
        predecessor_commit_hash=predecessor,  # type: ignore[arg-type]
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
    )


def _manifest(
    run_id: str = "parent-run", *, derivation_v3: bool = False
) -> RunManifest:
    return RunManifest(
        run_id=RunId(run_id),
        world_id=WorldId("world-1"),
        seed=7,
        config=_run_config(derivation_v3=derivation_v3),
        derivation_version=(
            DERIVATION_VERSION_V3 if derivation_v3 else DERIVATION_VERSION
        ),
        event_schema_version=EVENT_SCHEMA_VERSION,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version=PERSISTENCE_CODEC_VERSION,
    )


def _commit_for(
    request: TickAppendRequest, *, resulting_revision: WorldRevision
) -> TickCommit:
    payload = hash_tick_payload(request.events)
    event_hashes = hash_tick_events(request.events)
    commit_hash = compute_commit_hash(
        predecessor_commit_hash=request.expected_predecessor_commit_hash,
        run_id=request.run_id,
        tick=request.tick,
        base_revision=request.expected_base_revision,
        resulting_revision=resulting_revision,
        event_hashes=event_hashes,
        payload_hash=payload,
    )
    return TickCommit(
        run_id=request.run_id,
        tick=request.tick,
        resulting_tick=Tick(request.tick.value + 1),
        base_revision=request.expected_base_revision,
        resulting_revision=resulting_revision,
        predecessor_commit_hash=request.expected_predecessor_commit_hash,
        commit_hash=commit_hash,
        idempotency_key=request.idempotency_key,
        event_count=len(request.events),
        payload_hash=payload,
        snapshot_id=None if request.snapshot is None else request.snapshot.snapshot_id,
    )


class _FakeRuns:
    def __init__(self, manifests: dict[str, RunManifest] | None = None) -> None:
        self.manifests = manifests or {}

    async def get_run(self, run_id: RunId) -> RunManifest | None:
        return self.manifests.get(run_id.value)

    async def create_run(self, request: RunCreateRequest) -> RunManifest:
        if request.run_id.value in self.manifests:
            raise RuntimeError("run_exists")
        manifest = RunManifest(
            run_id=request.run_id,
            world_id=request.world_id,
            seed=request.seed,
            config=request.config,
            derivation_version=request.derivation_version,
            event_schema_version=request.event_schema_version,
            projector_version=request.projector_version,
            persistence_codec_version=request.persistence_codec_version,
        )
        self.manifests[request.run_id.value] = manifest
        return manifest


class _FakeSnapshots:
    def __init__(self, snapshots: list[WorldSnapshot]) -> None:
        self.snapshots = list(snapshots)

    async def get_latest_at_or_before(
        self, run_id: RunId, tick: Tick
    ) -> WorldSnapshot | None:
        candidates = [
            item
            for item in self.snapshots
            if item.run_id == run_id and item.next_tick.value <= tick.value
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda item: item.next_tick.value)

    async def get_snapshot(self, snapshot_id: SnapshotId) -> WorldSnapshot | None:
        for item in self.snapshots:
            if item.snapshot_id == snapshot_id:
                return item
        return None


class _FakeJournal:
    def __init__(
        self,
        commits: list[TickCommit] | None = None,
        events: list[WorldEvent] | None = None,
    ) -> None:
        self.commits = list(commits or [])
        self.events = list(events or [])

    async def append_tick(self, request: TickAppendRequest) -> TickCommit:
        commit = _commit_for(
            request, resulting_revision=WorldRevision(request.tick.value)
        )
        self.commits.append(commit)
        self.events.extend(request.events)
        return commit

    async def get_tick_commit(self, run_id: RunId, tick: Tick) -> TickCommit | None:
        for item in self.commits:
            if item.run_id == run_id and item.tick == tick:
                return item
        return None

    async def list_events(
        self,
        run_id: RunId,
        *,
        from_tick: Tick,
        to_tick: Tick | None,
        limit: int,
        offset: int,
    ) -> tuple[WorldEvent, ...]:
        selected = [
            event
            for event in self.events
            if event.run_id == run_id.value
            and event.tick >= from_tick.value
            and (to_tick is None or event.tick <= to_tick.value)
        ]
        return tuple(selected[offset : offset + limit])

    async def list_tick_commits(
        self,
        run_id: RunId,
        *,
        from_tick: Tick,
        to_tick: Tick | None,
    ) -> tuple[TickCommit, ...]:
        selected = [
            item
            for item in self.commits
            if item.run_id == run_id
            and item.tick.value >= from_tick.value
            and (to_tick is None or item.tick.value <= to_tick.value)
        ]
        return tuple(sorted(selected, key=lambda item: item.tick.value))


def _receipts_from_commits(
    commits: tuple[TickCommit, ...],
) -> tuple[FinalizedTickReceipt, ...]:
    return tuple(
        FinalizedTickReceipt(
            tick=commit.tick.value,
            resulting_tick=commit.resulting_tick.value,
            base_revision=commit.base_revision.value,
            resulting_revision=commit.resulting_revision.value,
            resolutions=(),
            objective_state_hash=commit.commit_hash.value,
            event_count=commit.event_count,
        )
        for commit in commits
    )


def _parent_event() -> WorldEvent:
    return make_replayable_event(
        event_id=EventId("evt-1"),
        run_id="parent-run",
        world_id=WorldId("world-1"),
        tick=0,
        sequence=0,
        request_id=RequestId("req-1"),
        resulting_revision=WorldRevision(0),
        details=Waited(),
        actor_id=EntityId("body-1"),
    )


def _parent_stack(
    *, derivation_v3: bool = False
) -> tuple[_FakeRuns, _FakeJournal, _FakeSnapshots, TickCommit]:
    bootstrap = _snapshot(derivation_v3=derivation_v3)
    event = _parent_event()
    parent_request = TickAppendRequest(
        run_id=RunId("parent-run"),
        tick=Tick(0),
        expected_base_revision=WorldRevision(0),
        expected_predecessor_commit_hash=None,
        idempotency_key="parent-idem-0",
        events=(event,),
    )
    parent_commit = _commit_for(parent_request, resulting_revision=WorldRevision(0))
    fork_point = _snapshot(
        snapshot_id="snap-fork",
        next_tick=1,
        revision=0,
        predecessor=parent_commit.commit_hash,
        derivation_v3=derivation_v3,
    )
    runs = _FakeRuns({"parent-run": _manifest(derivation_v3=derivation_v3)})
    journal = _FakeJournal(commits=[parent_commit], events=[event])
    snapshots = _FakeSnapshots([bootstrap, fork_point])
    return runs, journal, snapshots, parent_commit


def test_identical_fork_config_mints_stable_child_and_branch_ids() -> None:
    intervention = _memory_intervention()
    fingerprint = intervention_fingerprint(intervention)
    token = seed_stream_token_for_intervention(intervention)
    parent = RunId("parent-run")
    first = derive_branch_run_id(parent, 5, fingerprint, token)
    second = derive_branch_run_id(parent, 5, fingerprint, token)
    assert first == second
    assert derive_branch_id(parent, 5, fingerprint, token) == derive_branch_id(
        parent, 5, fingerprint, token
    )
    ordinary = derive_run_id(SimulationRunConfig(seed=99))
    assert first != ordinary


def test_research_fork_excludes_agent_counterfactual_and_belief_types() -> None:
    intervention = _memory_intervention()
    assert type(intervention) is ResearchIntervention
    assert CounterfactualScenario is not ResearchIntervention
    assert ImaginedFuture is not ResearchIntervention
    belief = SemanticBelief(
        belief_id=BeliefId("belief-1"),
        owner_id=AgentId("agent-1"),
        claim=SemanticClaim(
            subject=ClaimSubject(
                kind=ClaimSubjectKind.ENTITY, entity_id=EntityId("place-1")
            ),
            predicate="at_location",
            value=ClaimValue(kind=BeliefValueKind.BOOL, bool_value=True),
        ),
        confidence=BeliefConfidenceState(
            confidence=0.9, support_mass=0.9, contradiction_mass=0.0
        ),
        activation_state=BeliefActivationState.ACTIVE,
        current_revision_id=BeliefRevisionId("rev-1"),
        revision_ordinal=1,
        created_tick=1,
        updated_tick=2,
        policy=BeliefPolicyRef(policy_id="semantic-v1", version="1"),
        evidence_support_count=1,
        evidence_contradiction_count=0,
    )
    assert belief.claim.predicate != "research_fork"
    assert type(belief) is not ResearchIntervention
    assert not issubclass(ResearchIntervention, CounterfactualScenario)
    assert not issubclass(ResearchIntervention, ImaginedFuture)


def test_fingerprint_stable_across_calls() -> None:
    intervention = _memory_intervention()
    assert intervention_fingerprint(intervention) == intervention_fingerprint(
        intervention
    )


def test_simulation_branch_modules_do_not_import_experiments() -> None:
    forbidden = {"experiments"}
    modules = (
        _SRC / "simulation" / "branching.py",
        _SRC / "simulation" / "branch_service.py",
        _SRC / "simulation" / "branch_compare.py",
    )
    for path in modules:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".", 1)[0]
                    assert root not in forbidden, f"{path.name} imports {alias.name}"
            elif isinstance(node, ast.ImportFrom) and node.module:
                root = node.module.split(".", 1)[0]
                assert root not in forbidden, f"{path.name} imports {node.module}"


@pytest.mark.asyncio
async def test_identical_independent_forks_share_exact_trajectory_hash() -> None:
    """Same parent + fork_tick + child id ⇒ equal rematerialized exact hashes."""
    intervention = _memory_intervention()
    fingerprint = intervention_fingerprint(intervention)
    token = seed_stream_token_for_intervention(intervention)
    child_run_id = derive_branch_run_id(RunId("parent-run"), 1, fingerprint, token)

    hashes: list[str] = []
    for _ in range(2):
        runs, journal, snapshots, _parent_commit = _parent_stack()
        service = BranchService(runs=runs, journal=journal, snapshots=snapshots)
        result = await service.materialize_objective_fork(
            parent_run_id=RunId("parent-run"),
            child_run_id=child_run_id,
            fork_tick=1,
        )
        child_commits = await journal.list_tick_commits(
            child_run_id, from_tick=Tick(0), to_tick=None
        )
        assert child_commits == result.child_commits
        hashes.append(
            exact_trajectory_hash(
                run_id=child_run_id.value,
                tick_receipts=_receipts_from_commits(child_commits),
            )
        )
    assert hashes[0] == hashes[1]
    assert len(hashes[0]) == 64


@pytest.mark.asyncio
async def test_parent_exact_trajectory_hash_unchanged_after_fork() -> None:
    runs, journal, snapshots, _parent_commit = _parent_stack()
    parent_before = await journal.list_tick_commits(
        RunId("parent-run"), from_tick=Tick(0), to_tick=None
    )
    parent_hash_before = exact_trajectory_hash(
        run_id="parent-run",
        tick_receipts=_receipts_from_commits(parent_before),
    )
    service = BranchService(runs=runs, journal=journal, snapshots=snapshots)
    await service.materialize_objective_fork(
        parent_run_id=RunId("parent-run"),
        child_run_id=RunId("child-run"),
        fork_tick=1,
    )
    parent_after = await journal.list_tick_commits(
        RunId("parent-run"), from_tick=Tick(0), to_tick=None
    )
    parent_hash_after = exact_trajectory_hash(
        run_id="parent-run",
        tick_receipts=_receipts_from_commits(parent_after),
    )
    assert parent_hash_before == parent_hash_after
    assert parent_before[0].commit_hash == parent_after[0].commit_hash


@pytest.mark.asyncio
async def test_research_fork_created_log_token(
    caplog: pytest.LogCaptureFixture,
) -> None:
    runs, journal, snapshots, _parent_commit = _parent_stack(derivation_v3=True)
    lineage_repo = InMemoryBranchLineageRepository()
    service = BranchService(
        runs=runs,
        journal=journal,
        snapshots=snapshots,
        lineage=lineage_repo,
        subjective_clone=InMemorySubjectiveClonePort(),
        run_control=InMemoryRunControlRepository(),
    )
    request = BranchCreateRequest(
        parent_run_id=RunId("parent-run"),
        fork_tick=1,
        intervention=_memory_intervention(),
    )
    with caplog.at_level(logging.INFO, logger="simulation.branching"):
        result = await service.create_research_fork(
            request, parent_runner_config=_config()
        )
    assert result.idempotent_hit is False
    joined = "\n".join(record.getMessage() for record in caplog.records)
    assert "research_fork_created" in joined
    assert result.lineage.intervention_fingerprint in joined
    assert "hello" not in joined


def test_research_fork_idempotent_hit_log_token(
    caplog: pytest.LogCaptureFixture,
) -> None:
    request = BranchCreateRequest(
        parent_run_id=RunId("parent-run"),
        fork_tick=5,
        intervention=_memory_intervention(),
    )
    fingerprint = intervention_fingerprint(request.intervention)
    token = seed_stream_token_for_intervention(request.intervention)
    child = derive_branch_run_id(
        request.parent_run_id, request.fork_tick, fingerprint, token
    )
    lineage = BranchLineage(
        child_run_id=child,
        parent_run_id=request.parent_run_id,
        fork_tick=request.fork_tick,
        intervention_kind=request.intervention.kind,
        intervention_fingerprint=fingerprint,
        intervention_canonical=canonical_intervention_document(request.intervention),
        branch_id=derive_branch_id(
            request.parent_run_id, request.fork_tick, fingerprint, token
        ),
        created_as_of_parent_head=12,
    )
    with caplog.at_level(logging.INFO, logger="simulation.branching"):
        hit = resolve_idempotent_create(
            child_run_id=child,
            request=request,
            existing=lineage,
        )
    assert hit is not None
    assert hit.idempotent_hit is True
    joined = "\n".join(record.getMessage() for record in caplog.records)
    assert "research_fork_idempotent_hit" in joined
    assert fingerprint in joined
