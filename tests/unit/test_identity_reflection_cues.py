"""Dissonant memories are preferred by reflection without a second belief writer."""

from __future__ import annotations

from dataclasses import replace

from agents.cognition.identity import (
    IDENTITY_POLICY_ID,
    IDENTITY_POLICY_VERSION,
    IdentityAspect,
    IdentityPolicy,
    IdentityProvenanceKind,
    IdentityRevisionPoint,
    IdentityRevisionSummary,
    IdentityState,
    aggregate_identity_confidence,
    assemble_identity_belief_view,
    build_identity_claim,
    identity_predicate,
    reflection_cue_memory_ids,
)
from agents.cognition.reflection import (
    ReflectionContext,
    _select_memories,
    default_reflection_policy,
)
from agents.models import AgentId
from memory.beliefs import BeliefActivationState, BeliefValueKind, ClaimValue
from memory.models import (
    BeliefId,
    ConceptMention,
    MemoryId,
    MemoryProvenance,
    MemorySituationContext,
    MemorySourceKind,
    MemoryTrace,
    MentionId,
)
from world.identifiers import WorldRevision

_OWNER = AgentId("agent-1")


def _trace(memory_id: str, tick: int) -> MemoryTrace:
    return MemoryTrace(
        memory_id=MemoryId(memory_id),
        owner_id=_OWNER,
        world_revision=WorldRevision(0),
        concepts=(ConceptMention(mention_id=MentionId("c-1"), concept="trail"),),
        entities=(),
        relations=(),
        context=MemorySituationContext(),
        emotional_salience=0.0,
        confidence=1.0,
        provenance=MemoryProvenance(
            kind=MemorySourceKind.DIRECT_OBSERVATION, source_tick=tick
        ),
        created_tick=tick,
        source_tick=tick,
        last_access_tick=tick,
        access_count=0,
    )


def _view(
    *,
    belief_id: str,
    supporting: tuple[str, ...],
    contradicting: tuple[str, ...],
) -> object:
    claim = build_identity_claim(
        _OWNER,
        identity_predicate(
            IdentityAspect.ABILITY,
            IdentityProvenanceKind.OBSERVED_OUTCOME,
            "search",
        ),
        ClaimValue(kind=BeliefValueKind.BOOL, bool_value=True),
    )
    return assemble_identity_belief_view(
        belief_id=BeliefId(belief_id),
        claim=claim,
        confidence=0.8,
        supporting_memory_ids=tuple(MemoryId(item) for item in supporting),
        contradicting_memory_ids=tuple(MemoryId(item) for item in contradicting),
        activation=BeliefActivationState.ACTIVE,
        revision_points=(
            IdentityRevisionPoint(
                ordinal=0, tick=1, confidence=0.8, contradicted=False
            ),
        ),
        revision_summaries=(
            IdentityRevisionSummary(
                ordinal=0, tick=1, activation=BeliefActivationState.ACTIVE
            ),
        ),
    )


def _state(*views: object) -> IdentityState:
    typed = tuple(views)
    return IdentityState(
        owner_id=_OWNER,
        policy_id=IDENTITY_POLICY_ID,
        policy_version=IDENTITY_POLICY_VERSION,
        views=typed,  # type: ignore[arg-type]
        aggregate_confidence=aggregate_identity_confidence(typed),  # type: ignore[arg-type]
    )


def test_high_contradiction_mass_cues_the_later_memory() -> None:
    identity = _state(
        _view(
            belief_id="belief-ability",
            supporting=(),
            contradicting=("mem-late",),
        )
    )
    assert reflection_cue_memory_ids(identity) == ("mem-late",)
    early = _trace("mem-early", 1)
    late = _trace("mem-late", 9)
    context = ReflectionContext(
        owner_id=_OWNER,
        tick=10,
        policy=default_reflection_policy(),
        memories=(early, late),
        cited_memory_ids=reflection_cue_memory_ids(identity),
    )
    selected = _select_memories(context)
    assert selected[0].memory_id.value == "mem-late"
    assert all(not item.memory_id.value.startswith("identity.") for item in selected)


def test_mass_at_the_floor_is_not_a_cue() -> None:
    identity = _state(
        _view(
            belief_id="belief-ability",
            supporting=("mem-support",),
            contradicting=("mem-late",),
        )
    )
    floor = IdentityPolicy().dissonance_cue_floor
    assert floor == 0.5
    assert reflection_cue_memory_ids(identity) == ()
    uncued = _select_memories(
        ReflectionContext(
            owner_id=_OWNER,
            tick=10,
            policy=default_reflection_policy(),
            memories=(_trace("mem-early", 1), _trace("mem-late", 9)),
        )
    )
    assert uncued[0].memory_id.value == "mem-early"


def test_cited_order_is_stable_when_the_context_is_replaced() -> None:
    identity = _state(
        _view(
            belief_id="belief-ability",
            supporting=(),
            contradicting=("mem-late",),
        )
    )
    base = ReflectionContext(
        owner_id=_OWNER,
        tick=10,
        policy=default_reflection_policy(),
        memories=(_trace("mem-early", 1), _trace("mem-late", 9)),
    )
    cued = replace(base, cited_memory_ids=reflection_cue_memory_ids(identity))
    assert _select_memories(base)[0].memory_id.value == "mem-early"
    assert _select_memories(cued)[0].memory_id.value == "mem-late"
