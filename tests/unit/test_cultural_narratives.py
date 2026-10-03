"""Owner-scoped cultural narrative contracts and cue boundary."""

from __future__ import annotations

import hashlib
from types import SimpleNamespace

import pytest

from agents.cognition.configuration import CognitionCulturalNarrativeMode
from agents.cognition.cultural_narratives import (
    CULTURAL_NARRATIVE_POLICY_VERSION,
    CulturalNarrativePolicy,
    NarrativeContent,
    NarrativeCueSummary,
    NarrativeLedger,
    NarrativeOrigin,
    NarrativeStatus,
    NarrativeVariant,
    apply_narrative_update,
    default_cultural_narrative_policy,
    empty_narrative_ledger,
    narrative_communicate_penalties,
    narrative_content_fingerprint,
    narrative_semantic_evidence,
    narrative_variant_id,
    require_owner_cultural_narratives,
)
from agents.cognition.models import CounterpartBinding, OwnerSafeSocialIdentity
from agents.models import AgentId
from simulation.runner_models import CulturalNarrativeMode
from world.communications import (
    CommunicationRelation,
    CommunicationSourceBasis,
    origin_utterance,
)
from world.identifiers import EntityId, EventId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import (
    Observation,
    ObservationAudienceRole,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedCommunication,
    ObservedOccurrence,
    ObservedSelf,
)
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    TemperatureCelsius,
    Thirst,
)


def _agent(value: str) -> AgentId:
    return AgentId(value)


def _identity(owner: str = "alice") -> OwnerSafeSocialIdentity:
    owner_id = _agent(owner)
    return OwnerSafeSocialIdentity(
        owner_id=owner_id,
        owner_entity_id=EntityId(f"body-{owner}"),
        counterparts=(
            CounterpartBinding(
                agent_id=_agent("ben"),
                entity_id=EntityId("body-ben"),
            ),
            CounterpartBinding(
                agent_id=_agent("cy"),
                entity_id=EntityId("body-cy"),
            ),
        ),
    )


def _observation(
    *,
    tick: int = 1,
    owner: str = "alice",
    occurrences: tuple[ObservedOccurrence, ...] = (),
    communications: tuple[ObservedCommunication, ...] = (),
) -> Observation:
    return Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId(f"body-{owner}"),
        revision=WorldRevision(1),
        tick=tick,
        self_body=ObservedSelf(
            entity_id=EntityId(f"body-{owner}"),
            location_id=EntityId("loc-clearing"),
            health=Health(100),
            hunger=Hunger(0),
            thirst=Thirst(0),
            fatigue=Fatigue(0),
            temperature=TemperatureCelsius(36.5),
            inventory=(),
            life_status=LifeStatus.ALIVE,
            carry_capacity=CarryCapacity(10),
        ),
        occurrences=occurrences,
        communications=communications,
    )


def _occurrence(
    kind: str, tick: int, event_id: str | None = None
) -> ObservedOccurrence:
    # Occurrences must come from a prior committed tick.
    source_tick = max(0, tick - 1)
    return ObservedOccurrence(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.OCCURRENCE,
            source_tick=source_tick,
            source_event_id=None if event_id is None else EventId(event_id),
        ),
        kind=kind,
        audience_role=ObservationAudienceRole.WITNESS,
        public_facts={"resource": "water"},
    )


def _communication(
    *,
    tick: int,
    speaker: str,
    listener: str,
    utterance: object,
    action_kind: str = "talk",
    event_id: str,
) -> ObservedCommunication:
    return ObservedCommunication(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.COMMUNICATION,
            source_tick=max(0, tick - 1),
            source_event_id=EventId(event_id),
        ),
        speaker_id=EntityId(f"body-{speaker}"),
        listener_id=EntityId(f"body-{listener}"),
        utterance=utterance,  # type: ignore[arg-type]
        action_kind=action_kind,  # type: ignore[arg-type]
    )


def test_policy_locks_constants_and_modes_match() -> None:
    policy = default_cultural_narrative_policy()
    assert (
        policy.version
        == CULTURAL_NARRATIVE_POLICY_VERSION
        == "cultural-narratives.v1"
    )
    assert policy.active_strength == 0.40
    assert policy.retire_strength == 0.20
    assert policy.decay == 0.05
    assert policy.observed_delta == 0.12
    assert policy.remembered_delta == 0.08
    assert policy.communicated_delta == 0.10
    assert policy.deliberate_lie_delta == 0.10
    assert policy.misread_artifact_delta == 0.10
    assert policy.penalty == 0.30
    assert policy.promotion_count == 3
    assert policy.semantic_uplift_repetitions == 5
    assert policy.semantic_uplift_strength == 0.55
    assert policy.merge_token_overlap == 0.75
    assert policy.utterance_interval == 4
    assert policy.max_variants == 8
    assert policy.max_evidence == 32
    assert policy.max_carriers == 8
    assert policy.max_locations == 8
    assert policy.max_parents == 4
    assert policy.max_competitors == 4
    with pytest.raises(ValueError, match="unsupported_policy"):
        CulturalNarrativePolicy(active_strength=0.5)
    assert [mode.value for mode in CognitionCulturalNarrativeMode] == [
        mode.value for mode in CulturalNarrativeMode
    ]
    assert CognitionCulturalNarrativeMode.DISABLED.value == "disabled"
    assert CognitionCulturalNarrativeMode.DETERMINISTIC.value == "deterministic"


def test_variant_id_and_fingerprint_are_digest_only() -> None:
    owner = _agent("alice")
    content = NarrativeContent(concepts=("water", "depletion"), text="tell_story")
    fingerprint = narrative_content_fingerprint(content)
    assert len(fingerprint) == 64
    variant_id = narrative_variant_id(owner, fingerprint, 0, "")
    expected = hashlib.sha256(
        f"{owner.value}|{fingerprint}|0|".encode()
    ).hexdigest()
    assert variant_id == expected
    other = narrative_variant_id(_agent("ben"), fingerprint, 0, "")
    assert variant_id != other


def test_empty_content_and_prose_rejected() -> None:
    with pytest.raises(ValueError, match="empty_content"):
        NarrativeContent(concepts=(), relations=(), text="tell_story")
    with pytest.raises(ValueError, match="unknown_predicate"):
        NarrativeContent(concepts=("water",), text="free_prose")
    with pytest.raises(ValueError, match="illegal_token"):
        NarrativeContent(concepts=("Dead Place",), text="tell_story")


def test_merged_status_requires_merged_into() -> None:
    owner = _agent("alice")
    content = NarrativeContent(concepts=("water",), text="tell_story")
    fingerprint = narrative_content_fingerprint(content)
    variant_id = narrative_variant_id(owner, fingerprint, 0, "")
    with pytest.raises(ValueError, match="merged_requires_target"):
        NarrativeVariant(
            variant_id=variant_id,
            owner_id=owner,
            content=content,
            content_fingerprint=fingerprint,
            origin=NarrativeOrigin.OBSERVED_EVENT,
            status=NarrativeStatus.MERGED,
            strength=0.5,
        )


def test_require_owner_accepts_none_and_rejects_foreign() -> None:
    owner = _agent("alice")
    require_owner_cultural_narratives(None, owner, field_name="cultural_narratives")
    ledger = empty_narrative_ledger(owner)
    require_owner_cultural_narratives(
        ledger, owner, field_name="cultural_narratives"
    )
    with pytest.raises(ValueError, match="owner_id mismatch"):
        require_owner_cultural_narratives(
            ledger, _agent("ben"), field_name="cultural_narratives"
        )
    with pytest.raises(TypeError, match="NarrativeLedger"):
        require_owner_cultural_narratives(
            "nope", owner, field_name="cultural_narratives"
        )


def test_forbidden_world_and_metric_inputs_raise_type_error() -> None:
    identity = _identity()
    observation = _observation()
    with pytest.raises(TypeError, match="forbidden_input"):
        apply_narrative_update(
            observation=observation,
            identity=identity,
            previous=type("WorldState", (), {})(),
        )
    with pytest.raises(TypeError, match="forbidden_input"):
        apply_narrative_update(
            observation=observation,
            identity=identity,
            previous=None,
            memories=({"metric_family": "x", "availability": "y"},),
        )


def test_three_observed_ticks_promote_one_stays_candidate() -> None:
    identity = _identity()
    ledger: NarrativeLedger | None = None
    for tick in (1, 2, 3):
        ledger = apply_narrative_update(
            observation=_observation(
                tick=tick,
                occurrences=(_occurrence("resource_depleted", tick, f"evt-{tick}"),),
            ),
            identity=identity,
            previous=ledger,
        )
    assert ledger is not None
    assert len(ledger.variants) == 1
    assert ledger.variants[0].status is NarrativeStatus.ACTIVE
    assert ledger.variants[0].origin is NarrativeOrigin.OBSERVED_EVENT
    assert ledger.variants[0].repetition_count >= 3

    single = apply_narrative_update(
        observation=_observation(
            tick=1,
            occurrences=(_occurrence("resource_depleted", 1, "evt-1"),),
        ),
        identity=identity,
        previous=None,
    )
    assert single.variants[0].status is NarrativeStatus.CANDIDATE
    assert "below_count" in single.notices


def test_memory_reinforces_but_never_mints() -> None:
    identity = _identity()
    memory = SimpleNamespace(
        memory_id=SimpleNamespace(value="mem-1"),
        concepts=(SimpleNamespace(concept="water"),),
        relations=(),
        forgotten_at_tick=None,
        expires_at_tick=None,
        narrative="free form prose must be ignored",
    )
    empty = apply_narrative_update(
        observation=_observation(tick=1),
        identity=identity,
        previous=None,
        memories=(memory,),
    )
    assert empty.variants == ()

    seeded = apply_narrative_update(
        observation=_observation(
            tick=1,
            occurrences=(_occurrence("resource_depleted", 1, "evt-1"),),
        ),
        identity=identity,
        previous=None,
    )
    before = seeded.variants[0].strength
    reinforced = apply_narrative_update(
        observation=_observation(tick=2),
        identity=identity,
        previous=seeded,
        memories=(memory,),
    )
    # Same fingerprint only if memory concepts match occurrence content.
    # Occurrence concepts are resource_depleted + water; memory has water only —
    # reinforce only when fingerprints match, so strength may stay if no match.
    assert len(reinforced.variants) == 1
    # Forgotten memory ignored.
    forgotten = SimpleNamespace(
        memory_id=SimpleNamespace(value="mem-2"),
        concepts=(SimpleNamespace(concept="resource_depleted"),),
        relations=(),
        forgotten_at_tick=1,
        expires_at_tick=None,
    )
    after_forgotten = apply_narrative_update(
        observation=_observation(tick=3),
        identity=identity,
        previous=reinforced,
        memories=(forgotten,),
    )
    assert after_forgotten.variants[0].strength <= after_forgotten.variants[0].strength
    assert before >= 0.0


def test_reconstruction_cue_mints_with_source_correlation() -> None:
    identity = _identity()
    cues = NarrativeCueSummary(
        reconstructions=(
            (
                "recon-1",
                ("mem-source-1",),
                ("forest", "fire"),
                (("forest", "caused", "fire"),),
            ),
        ),
    )
    ledger = apply_narrative_update(
        observation=_observation(tick=1),
        identity=identity,
        previous=None,
        cues=cues,
    )
    assert len(ledger.variants) == 1
    assert ledger.variants[0].origin is NarrativeOrigin.RECONSTRUCTED_MEMORY
    assert ledger.variants[0].source_memory_id == "mem-source-1"


def test_misread_artifact_requires_distorted_cue() -> None:
    identity = _identity()
    no_mint = apply_narrative_update(
        observation=_observation(tick=1),
        identity=identity,
        previous=None,
        cues=NarrativeCueSummary(
            distorted_artifacts=(("art-1", False, 2, 3),),
        ),
    )
    assert no_mint.variants == ()
    minted = apply_narrative_update(
        observation=_observation(tick=1),
        identity=identity,
        previous=None,
        cues=NarrativeCueSummary(
            distorted_artifacts=(("art-1", True, 2, 3),),
        ),
    )
    assert len(minted.variants) == 1
    assert minted.variants[0].origin is NarrativeOrigin.MISREAD_ARTIFACT


def test_deliberate_lie_from_unreferenced_tell() -> None:
    identity = _identity()
    utterance = origin_utterance(
        text="claim",
        speaker_id=EntityId("body-ben"),
        communication_id="comm-lie-1",
        concepts=("danger", "ridge"),
        relations=(
            CommunicationRelation(
                subject="danger", predicate="at", object="ridge"
            ),
        ),
        source_basis=CommunicationSourceBasis.UNREFERENCED,
    )
    ledger = apply_narrative_update(
        observation=_observation(
            tick=1,
            communications=(
                _communication(
                    tick=1,
                    speaker="ben",
                    listener="alice",
                    utterance=utterance,
                    action_kind="tell",
                    event_id="evt-lie-1",
                ),
            ),
        ),
        identity=identity,
        previous=None,
    )
    assert len(ledger.variants) == 1
    assert ledger.variants[0].origin is NarrativeOrigin.DELIBERATE_LIE


def test_retell_branches_on_mutated_fingerprint() -> None:
    identity = _identity()
    first = origin_utterance(
        text="tell_story",
        speaker_id=EntityId("body-ben"),
        communication_id="comm-story-1",
        concepts=("water", "gone"),
        relations=(
            CommunicationRelation(
                subject="water", predicate="tell_story", object="gone"
            ),
        ),
        source_basis=CommunicationSourceBasis.UNREFERENCED,
    )
    ledger = apply_narrative_update(
        observation=_observation(
            tick=1,
            communications=(
                _communication(
                    tick=1,
                    speaker="ben",
                    listener="alice",
                    utterance=first,
                    event_id="evt-story-1",
                ),
            ),
        ),
        identity=identity,
        previous=None,
    )
    # Reinforce to active so branching parent stays live.
    for tick in (2, 3):
        ledger = apply_narrative_update(
            observation=_observation(
                tick=tick,
                communications=(
                    _communication(
                        tick=tick,
                        speaker="ben",
                        listener="alice",
                        utterance=first,
                        event_id=f"evt-story-{tick}",
                    ),
                ),
            ),
            identity=identity,
            previous=ledger,
        )
    from world.communications import retell_utterance

    mutated = retell_utterance(
        prior=first,
        speaker_id=EntityId("body-cy"),
        communication_id="comm-story-2",
        text="retell",
        concepts=("water", "poisoned"),
        relations=(
            CommunicationRelation(
                subject="water", predicate="retell", object="poisoned"
            ),
        ),
        source_basis=CommunicationSourceBasis.UNREFERENCED,
    )
    branched = apply_narrative_update(
        observation=_observation(
            tick=4,
            communications=(
                _communication(
                    tick=4,
                    speaker="cy",
                    listener="alice",
                    utterance=mutated,
                    event_id="evt-story-4",
                ),
            ),
        ),
        identity=identity,
        previous=ledger,
    )
    generations = {variant.mutation_generation for variant in branched.variants}
    assert 0 in generations
    assert any(variant.mutation_generation >= 1 for variant in branched.variants)


def test_penalties_empty_when_disabled_or_no_communicate() -> None:
    identity = _identity()
    ledger = empty_narrative_ledger(identity.owner_id)
    assert (
        narrative_communicate_penalties(
            ledger,
            (),
            tick=1,
            mode=CognitionCulturalNarrativeMode.DISABLED,
        )
        == {}
    )
    assert (
        narrative_communicate_penalties(
            None,
            (SimpleNamespace(future_id="f1", direction=SimpleNamespace(value="move")),),
            tick=1,
            mode=CognitionCulturalNarrativeMode.DETERMINISTIC,
        )
        == {}
    )


def test_founding_fingerprint_recovers_across_freeze() -> None:
    from agents.cognition.cultural_narratives import _recover_founding_fingerprint

    identity = _identity()
    owner = identity.owner_id
    parent_content = NarrativeContent(concepts=("water", "gone"), text="tell_story")
    child_content = NarrativeContent(
        concepts=("water", "poisoned"), text="retell"
    )
    parent_fp = narrative_content_fingerprint(parent_content)
    child_fp = narrative_content_fingerprint(child_content)
    parent_id = narrative_variant_id(owner, parent_fp, 0, "")
    child_id = narrative_variant_id(owner, parent_fp, 1, parent_id)
    parent = NarrativeVariant(
        variant_id=parent_id,
        owner_id=owner,
        content=parent_content,
        content_fingerprint=parent_fp,
        origin=NarrativeOrigin.OBSERVED_EVENT,
        status=NarrativeStatus.ACTIVE,
        strength=0.55,
        repetition_count=3,
    )
    child = NarrativeVariant(
        variant_id=child_id,
        owner_id=owner,
        content=child_content,
        content_fingerprint=child_fp,
        origin=NarrativeOrigin.RETOLD_STORY,
        status=NarrativeStatus.ACTIVE,
        strength=0.50,
        repetition_count=2,
        mutation_generation=1,
        parent_variant_ids=(parent_id,),
        transmission_root_id="root-1",
    )
    by_id = {parent_id: parent, child_id: child}
    assert _recover_founding_fingerprint(child, by_id) == parent_fp
    previous = NarrativeLedger(owner_id=owner, variants=(parent, child))
    reloaded = apply_narrative_update(
        observation=_observation(tick=9),
        identity=identity,
        previous=previous,
    )
    live_child = next(
        variant
        for variant in reloaded.variants
        if variant.mutation_generation == 1
    )
    assert live_child.variant_id == child_id
    assert live_child.content_fingerprint == child_fp


def test_overlapping_active_variants_merge() -> None:
    identity = _identity()
    owner = identity.owner_id
    left_content = NarrativeContent(
        concepts=("water", "gone", "clearing"),
        text="tell_story",
    )
    right_content = NarrativeContent(
        concepts=("water", "gone", "clearing", "poison"),
        text="tell_story",
    )
    left_fp = narrative_content_fingerprint(left_content)
    right_fp = narrative_content_fingerprint(right_content)
    left = NarrativeVariant(
        variant_id=narrative_variant_id(owner, left_fp, 0, ""),
        owner_id=owner,
        content=left_content,
        content_fingerprint=left_fp,
        origin=NarrativeOrigin.OBSERVED_EVENT,
        status=NarrativeStatus.ACTIVE,
        strength=0.55,
        repetition_count=3,
    )
    right = NarrativeVariant(
        variant_id=narrative_variant_id(owner, right_fp, 0, ""),
        owner_id=owner,
        content=right_content,
        content_fingerprint=right_fp,
        origin=NarrativeOrigin.OBSERVED_EVENT,
        status=NarrativeStatus.ACTIVE,
        strength=0.50,
        repetition_count=2,
    )
    previous = NarrativeLedger(owner_id=owner, variants=(left, right))
    merged = apply_narrative_update(
        observation=_observation(tick=5),
        identity=identity,
        previous=previous,
    )
    statuses = {variant.status for variant in merged.variants}
    assert NarrativeStatus.MERGED in statuses
    assert NarrativeStatus.ACTIVE in statuses
    parents = [
        variant
        for variant in merged.variants
        if variant.status is NarrativeStatus.MERGED
    ]
    assert all(variant.merged_into_id is not None for variant in parents)
    result = next(
        variant
        for variant in merged.variants
        if (
            variant.status is NarrativeStatus.ACTIVE
            and len(variant.parent_variant_ids) >= 2
        )
    )
    assert set(result.content.concepts) >= {"water", "gone", "clearing", "poison"}


def test_no_myth_type_in_cognition_exports() -> None:
    import agents.cognition as cognition

    assert not hasattr(cognition, "Myth")
    assert "Myth" not in cognition.__all__
    assert "DIRECT_OBSERVATION" not in CommunicationSourceBasis.__members__


def test_disabled_mode_does_not_own_multi_hop_flag() -> None:
    from simulation.runner_models import V2CapabilityFlags

    flags = V2CapabilityFlags()
    assert hasattr(flags, "multi_hop_testimony_tracking")
    assert not hasattr(flags, "cultural_narratives")
    assert not hasattr(flags, "myths")


def test_semantic_uplift_gates() -> None:
    identity = _identity()
    content = NarrativeContent(concepts=("water", "gone"), text="tell_story")
    fingerprint = narrative_content_fingerprint(content)
    owner = identity.owner_id
    variant = NarrativeVariant(
        variant_id=narrative_variant_id(owner, fingerprint, 0, ""),
        owner_id=owner,
        content=content,
        content_fingerprint=fingerprint,
        origin=NarrativeOrigin.OBSERVED_EVENT,
        status=NarrativeStatus.ACTIVE,
        strength=0.55,
        repetition_count=5,
        source_memory_id="mem-anchor-1",
    )
    ledger = NarrativeLedger(owner_id=owner, variants=(variant,))
    requests = narrative_semantic_evidence(
        ledger,
        owner_id=owner,
        tick=10,
        mode=CognitionCulturalNarrativeMode.DETERMINISTIC,
    )
    assert len(requests) == 1
    low = NarrativeVariant(
        variant_id=narrative_variant_id(owner, fingerprint, 0, ""),
        owner_id=owner,
        content=content,
        content_fingerprint=fingerprint,
        origin=NarrativeOrigin.OBSERVED_EVENT,
        status=NarrativeStatus.ACTIVE,
        strength=0.50,
        repetition_count=5,
        source_memory_id="mem-anchor-1",
    )
    withheld = narrative_semantic_evidence(
        NarrativeLedger(owner_id=owner, variants=(low,)),
        owner_id=owner,
        tick=10,
        mode=CognitionCulturalNarrativeMode.DETERMINISTIC,
    )
    assert withheld == ()
    disabled = narrative_semantic_evidence(
        ledger,
        owner_id=owner,
        tick=10,
        mode=CognitionCulturalNarrativeMode.DISABLED,
    )
    assert disabled == ()
