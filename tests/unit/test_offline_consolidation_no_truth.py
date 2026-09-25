"""Consolidation cannot correct a false memory from world state."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from agents.cognition.configuration import CognitionConsolidationMode
from agents.cognition.consolidation import orchestrate_offline_consolidation
from agents.cognition.emotion import PassthroughEmotionalStateAppraiser
from agents.cognition.goal_manager import PassthroughGoalManager
from agents.cognition.loop import CognitiveLoop
from agents.cognition.models import (
    CognitiveLoopInput,
    InternalAgentState,
    SubjectiveSnapshot,
    project_self_model,
)
from agents.models import AgentId
from memory.consolidation import plan_offline_consolidation
from memory.models import (
    ConceptMention,
    MemoryId,
    MemoryProvenance,
    MemorySituationContext,
    MemorySourceKind,
    MemoryTrace,
    MentionId,
    default_offline_consolidation_policy,
)
from tests.simulation_helpers import make_location, make_weather
from tests.typecheck.cognitive_loop import (
    ScriptedFutureImagination,
    ScriptedIntentionSelector,
    ScriptedMemoryRetriever,
    ScriptedMemoryUpdateHook,
    ScriptedMotivationEvaluator,
    ScriptedPerceptionInterpreter,
    ScriptedPlanner,
    ScriptedSelfStateProjector,
    ScriptedSituationModeler,
)
from world._state import WorldState
from world.actions import Sleep
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import Observation

_WORLD_FACT = "spring-sealed"
_FALSE_CLAIM = "gate-is-open"


def _trace(memory_id: str, concepts: tuple[str, ...]) -> MemoryTrace:
    return MemoryTrace(
        memory_id=MemoryId(memory_id),
        owner_id=AgentId("agent-1"),
        world_revision=WorldRevision(0),
        concepts=tuple(
            ConceptMention(
                mention_id=MentionId(f"{memory_id}-c{index}"), concept=concept
            )
            for index, concept in enumerate(concepts)
        ),
        entities=(),
        relations=(),
        context=MemorySituationContext(),
        emotional_salience=0.6,
        confidence=0.9,
        provenance=MemoryProvenance(
            kind=MemorySourceKind.COMMUNICATED,
            source_tick=0,
            speaker_id=EntityId("speaker-1"),
        ),
        created_tick=0,
        source_tick=0,
        last_access_tick=0,
        access_count=1,
    )


def _disagreeing_world() -> WorldState:
    return WorldState(
        WorldRevision(0),
        locations=(make_location(name=_WORLD_FACT),),
        weather=(make_weather(),),
    )


def _concepts(traces: tuple[MemoryTrace, ...]) -> set[str]:
    return {
        mention.concept for trace in traces for mention in trace.concepts
    }


def test_false_communicated_trace_survives_against_world_fact() -> None:
    world = _disagreeing_world()
    world_names = {location.name for location in world.locations.values()}
    assert world_names == {_WORLD_FACT}
    false = _trace("m-false", ("path", "water", "night", _FALSE_CLAIM))
    other = _trace("m-other", ("path", "water", "night", "camp-quiet"))
    assert _WORLD_FACT not in _concepts((false, other))
    _candidate, selection = plan_offline_consolidation(
        owner_id=AgentId("agent-1"),
        tick=3,
        traces=(false, other),
        policy=default_offline_consolidation_policy(),
    )
    assert false.concepts[-1].concept == _FALSE_CLAIM
    assert false.provenance.kind is MemorySourceKind.COMMUNICATED
    assert false.provenance.speaker_id == EntityId("speaker-1")
    gist_concepts = _concepts(selection.derived_traces)
    assert gist_concepts.isdisjoint(world_names)
    assert _FALSE_CLAIM not in gist_concepts
    assert "camp-quiet" not in gist_concepts
    assert "path" in gist_concepts
    assert selection.derived_traces
    gist = selection.derived_traces[0]
    assert gist.provenance.kind is MemorySourceKind.COMMUNICATED
    assert gist.provenance.speaker_id == EntityId("speaker-1")
    parameters = inspect.signature(plan_offline_consolidation).parameters
    assert "world" not in parameters
    assert "state" not in parameters


@pytest.mark.asyncio
async def test_deterministic_sleep_does_not_import_the_world_fact() -> None:
    world = _disagreeing_world()
    world_names = {location.name for location in world.locations.values()}
    owner = AgentId("agent-1")
    traces = (
        _trace("m-false", ("path", "water", "night", _FALSE_CLAIM)),
        _trace("m-other", ("path", "water", "night", "camp-quiet")),
    )
    snapshot = SubjectiveSnapshot(
        owner_id=owner,
        revision=0,
        memories=traces,
        legacy_beliefs=(),
        semantic_beliefs=(),
        relationships=(),
        goals=(),
    )
    plan = orchestrate_offline_consolidation(
        snapshot=snapshot,
        self_model=project_self_model(
            owner_id=owner, life_status=LifeStatus.ALIVE, beliefs=()
        ),
        write_intents=(),
        tick=3,
        mode="deterministic",
    )
    loop = CognitiveLoop(
        perception=ScriptedPerceptionInterpreter(),
        memory=ScriptedMemoryRetriever(),
        situation=ScriptedSituationModeler(),
        self_state=ScriptedSelfStateProjector(),
        goal_manager=PassthroughGoalManager(),
        emotional_state=PassthroughEmotionalStateAppraiser(),
        futures=ScriptedFutureImagination(),
        motivation=ScriptedMotivationEvaluator(),
        intention=ScriptedIntentionSelector(),
        planner=ScriptedPlanner(),
        memory_updates=ScriptedMemoryUpdateHook(),
        consolidation_mode=CognitionConsolidationMode.DETERMINISTIC,
    )
    proposal = await loop.prepare(
        CognitiveLoopInput(
            agent_id=owner,
            observation=Observation(
                world_id=WorldId("world-1"),
                observer_id=EntityId("body-1"),
                revision=WorldRevision(0),
                tick=3,
            ),
            internal_state=InternalAgentState(owner_id=owner),
            snapshot=snapshot,
        ),
        invocation_id="inv-false",
    )
    result = await loop.complete(proposal, effective_command=Sleep())
    assert result.offline_consolidation is not None
    stored = _concepts(result.offline_consolidation.selection.derived_traces)
    stored.update(_concepts(plan.selection.derived_traces))
    stored.update(_concepts(traces))
    assert stored.isdisjoint(world_names)
    assert traces[0].concepts[-1].concept == _FALSE_CLAIM
    assert traces[0].provenance.kind is MemorySourceKind.COMMUNICATED


def test_world_package_does_not_import_memory_or_cognition() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "world"
    forbidden = {"memory", "agents", "agents.cognition", "simulation"}
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = {alias.name.split(".", 1)[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                names = {node.module.split(".", 1)[0]}
            else:
                continue
            assert names.isdisjoint(forbidden)


def test_consolidation_modules_do_not_name_world_state() -> None:
    root = Path(__file__).resolve().parents[2] / "src"
    paths = (
        root / "memory" / "consolidation.py",
        root / "agents" / "cognition" / "consolidation.py",
    )
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module is not None:
                imported.add(node.module)
            elif isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
        assert "world._state" not in imported
        assert "world.events" not in imported
