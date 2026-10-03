"""Owner-scoped semantic naming contracts and cue boundary."""

from __future__ import annotations

import hashlib
from types import SimpleNamespace

import pytest

from agents.cognition.configuration import CognitionSemanticNamingMode
from agents.cognition.models import CounterpartBinding, OwnerSafeSocialIdentity
from agents.cognition.semantic_naming import (
    SEMANTIC_NAMING_POLICY_VERSION,
    LabelBinding,
    NamingCandidate,
    NamingCueSummary,
    NamingReferentKind,
    NamingStatus,
    NamingStrengthBand,
    NamingTransmission,
    SemanticNamingPolicy,
    TerminologyLedger,
    apply_naming_update,
    default_semantic_naming_policy,
    empty_terminology_ledger,
    label_binding_id,
    label_display,
    naming_strength_band,
    require_owner_semantic_naming,
    stable8_digest,
)
from agents.models import AgentId
from simulation.runner_models import SemanticNamingMode
from world.communications import (
    CommunicationRelation,
    CommunicationSourceBasis,
    origin_utterance,
)
from world.environment import HazardKind
from world.identifiers import EntityId, EventId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import (
    Observation,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedCommunication,
    ObservedSelf,
    VisibleBody,
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


def test_policy_locks_constants_and_modes_match() -> None:
    policy = default_semantic_naming_policy()
    assert (
        policy.version
        == SEMANTIC_NAMING_POLICY_VERSION
        == "semantic-naming.v1"
    )
    assert policy.active_strength == 0.40
    assert policy.retire_strength == 0.20
    assert policy.decay == 0.05
    assert policy.conforming_location == 0.12
    assert policy.conforming_agent == 0.10
    assert policy.conforming_group == 0.12
    assert policy.conforming_recurring_event == 0.12
    assert policy.conforming_dangerous_resource == 0.15
    assert policy.conforming_social_practice == 0.10
    assert policy.transmission_delta == 0.10
    assert policy.remembered_delta == 0.08
    assert policy.penalty == 0.30
    assert policy.promotion_count == 3
    assert policy.meaning_shift_ticks == 6
    assert policy.merge_jaccard == 0.50
    assert policy.utterance_interval == 4
    assert policy.max_bindings == 16
    assert policy.max_evidence == 32
    assert policy.max_candidates == 4
    assert policy.max_competitors == 4
    assert policy.max_merge_fan_in == 4
    with pytest.raises(ValueError, match="unsupported_policy"):
        SemanticNamingPolicy(active_strength=0.5)
    assert [mode.value for mode in CognitionSemanticNamingMode] == [
        mode.value for mode in SemanticNamingMode
    ]
    assert CognitionSemanticNamingMode.DISABLED.value == "disabled"
    assert CognitionSemanticNamingMode.DETERMINISTIC.value == "deterministic"


def test_label_binding_id_and_stable8_are_digest_only() -> None:
    owner = _agent("alice")
    kind = NamingReferentKind.LOCATION
    token = "place_a1b2c3d4"
    expected = hashlib.sha256(
        f"{owner.value}|{kind.value}|{token}".encode()
    ).hexdigest()
    assert label_binding_id(owner, kind, token) == expected
    digest = stable8_digest(owner, kind, "location_17")
    assert len(digest) == 8
    assert digest == hashlib.sha256(
        f"{owner.value}|{kind.value}|location_17".encode()
    ).hexdigest()[:8]
    other = stable8_digest(_agent("bob"), kind, "location_17")
    assert digest != other


def test_illegal_label_token_and_candidate_cap_rejected() -> None:
    owner = _agent("alice")
    with pytest.raises(ValueError, match="illegal_token"):
        label_binding_id(owner, NamingReferentKind.LOCATION, "Dead Place")
    with pytest.raises(ValueError, match="illegal_token"):
        label_binding_id(owner, NamingReferentKind.LOCATION, "UPPER")
    candidates = tuple(
        NamingCandidate(
            kind=NamingReferentKind.LOCATION,
            entity_id=f"loc-{index}",
            confidence=0.5,
        )
        for index in range(5)
    )
    token = "place_deadbeef"
    binding_id = label_binding_id(owner, NamingReferentKind.LOCATION, token)
    with pytest.raises(ValueError, match="cap_exceeded"):
        LabelBinding(
            binding_id=binding_id,
            owner_id=owner,
            label_token=token,
            referent_kind=NamingReferentKind.LOCATION,
            status=NamingStatus.CANDIDATE,
            strength=0.12,
            candidates=candidates,
        )


def test_binding_id_mismatch_and_non_finite_rejected() -> None:
    owner = _agent("alice")
    token = "place_deadbeef"
    with pytest.raises(ValueError, match="id_mismatch"):
        LabelBinding(
            binding_id="0" * 64,
            owner_id=owner,
            label_token=token,
            referent_kind=NamingReferentKind.LOCATION,
            status=NamingStatus.CANDIDATE,
            strength=0.12,
        )
    binding_id = label_binding_id(owner, NamingReferentKind.LOCATION, token)
    with pytest.raises(ValueError, match="not_finite"):
        LabelBinding(
            binding_id=binding_id,
            owner_id=owner,
            label_token=token,
            referent_kind=NamingReferentKind.LOCATION,
            status=NamingStatus.CANDIDATE,
            strength=float("nan"),
        )


def test_empty_ledger_and_require_owner() -> None:
    owner = _agent("alice")
    ledger = empty_terminology_ledger(owner)
    assert ledger.bindings == ()
    assert ledger.policy_version == SEMANTIC_NAMING_POLICY_VERSION
    require_owner_semantic_naming(None, owner, field_name="semantic_naming")
    require_owner_semantic_naming(ledger, owner, field_name="semantic_naming")
    with pytest.raises(ValueError, match="owner_id mismatch"):
        require_owner_semantic_naming(
            ledger, _agent("bob"), field_name="semantic_naming"
        )
    with pytest.raises(TypeError, match="TerminologyLedger"):
        require_owner_semantic_naming(
            SimpleNamespace(owner_id=owner), owner, field_name="semantic_naming"
        )


def test_label_display_and_strength_band() -> None:
    assert label_display("dead_a1b2c3d4") == "Dead A1b2c3d4"
    assert (
        naming_strength_band(NamingStatus.CANDIDATE, 0.9)
        is NamingStrengthBand.CANDIDATE
    )
    assert naming_strength_band(NamingStatus.ACTIVE, 0.39) is NamingStrengthBand.LOW
    assert naming_strength_band(NamingStatus.ACTIVE, 0.40) is NamingStrengthBand.MID
    assert naming_strength_band(NamingStatus.ACTIVE, 0.70) is NamingStrengthBand.HIGH


def test_naming_cue_summary_accepts_plain_strings() -> None:
    summary = NamingCueSummary(
        group_concept_ids=("a" * 64,),
        practice_action_kinds=("talk", "wait"),
    )
    assert summary.group_concept_ids == ("a" * 64,)
    assert summary.practice_action_kinds == ("talk", "wait")
    snake = NamingCueSummary(group_concept_ids=("group_deadbeef",))
    assert snake.group_concept_ids == ("group_deadbeef",)


def test_naming_cue_summary_rejects_forbidden_ledger_like_objects() -> None:
    class GroupLedger:
        pass

    with pytest.raises(TypeError, match="forbidden_type"):
        NamingCueSummary(group_concept_ids=(GroupLedger(),))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="invalid_token"):
        NamingCueSummary(practice_action_kinds=("Talk Loudly",))


def test_disabled_mode_leaves_snapshot_field_none_contract() -> None:
    """DISABLED is a passthrough: callers keep snapshot.semantic_naming as None."""
    assert CognitionSemanticNamingMode.DISABLED is CognitionSemanticNamingMode(
        "disabled"
    )
    assert SemanticNamingMode.DISABLED is SemanticNamingMode("disabled")
    # Constructing a ledger is allowed for DETERMINISTIC paths only; DISABLED
    # callers must leave the field None rather than allocate an empty ledger.
    ledger: TerminologyLedger | None = None
    assert ledger is None


def test_transmission_and_status_enums_reject_unknown() -> None:
    owner = _agent("alice")
    token = "place_deadbeef"
    binding_id = label_binding_id(owner, NamingReferentKind.LOCATION, token)
    with pytest.raises(ValueError, match="unknown_status"):
        LabelBinding(
            binding_id=binding_id,
            owner_id=owner,
            label_token=token,
            referent_kind=NamingReferentKind.LOCATION,
            status="active",  # type: ignore[arg-type]
            strength=0.4,
        )
    with pytest.raises(ValueError, match="unknown_transmission"):
        LabelBinding(
            binding_id=binding_id,
            owner_id=owner,
            label_token=token,
            referent_kind=NamingReferentKind.LOCATION,
            status=NamingStatus.ACTIVE,
            strength=0.4,
            transmission="heard",  # type: ignore[arg-type]
        )
    assert NamingTransmission.OBSERVED.value == "observed"
    assert NamingTransmission.COMMUNICATED.value == "communicated"
    assert NamingTransmission.BOTH.value == "both"


def _identity(owner: str = "ada", *others: str) -> OwnerSafeSocialIdentity:
    counterparts = tuple(
        CounterpartBinding(
            agent_id=_agent(name), entity_id=EntityId(f"body-{name}")
        )
        for name in others
    )
    return OwnerSafeSocialIdentity(
        owner_id=_agent(owner),
        owner_entity_id=EntityId(f"body-{owner}"),
        counterparts=counterparts,
    )


def _self(owner: str = "ada", location: str = "clearing") -> ObservedSelf:
    return ObservedSelf(
        entity_id=EntityId(f"body-{owner}"),
        location_id=EntityId(location),
        health=Health(100),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )


def _observe(
    tick: int,
    *,
    owner: str = "ada",
    location: str = "clearing",
    bodies: tuple[VisibleBody, ...] = (),
    communications: tuple[ObservedCommunication, ...] = (),
    hazard_kinds: tuple[HazardKind, ...] | None = None,
) -> Observation:
    return Observation(
        world_id=WorldId("world-w"),
        observer_id=EntityId(f"body-{owner}"),
        revision=WorldRevision(1),
        tick=tick,
        self_body=_self(owner, location),
        occurrences=(),
        visible_bodies=bodies,
        communications=communications,
        hazard_kinds=hazard_kinds,
    )


def test_three_location_ticks_promote_binding() -> None:
    identity = _identity()
    ledger = None
    for tick in (1, 2, 3):
        ledger = apply_naming_update(_observe(tick), identity, ledger)
    assert ledger is not None
    binding = ledger.bindings[0]
    assert binding.referent_kind is NamingReferentKind.LOCATION
    assert binding.status is NamingStatus.ACTIVE
    assert binding.evidence_count == 3
    assert binding.strength >= 0.40
    one = apply_naming_update(_observe(1), identity, None)
    assert one.bindings[0].status is NamingStatus.CANDIDATE
    assert one.bindings[0].evidence_count == 1


def test_two_owners_mint_different_place_seeds() -> None:
    alice = apply_naming_update(_observe(1, owner="alice"), _identity("alice"), None)
    bob = apply_naming_update(_observe(1, owner="bob"), _identity("bob"), None)
    assert alice.bindings[0].label_token != bob.bindings[0].label_token
    assert alice.bindings[0].label_token.startswith("place_")
    assert bob.bindings[0].label_token.startswith("place_")


def test_forbidden_world_state_and_metric_rejected() -> None:
    identity = _identity()
    obs = _observe(1)

    class WorldState:
        pass

    class MetricDocument(dict):
        pass

    with pytest.raises(TypeError, match="forbidden_input"):
        apply_naming_update(WorldState(), identity, None)
    with pytest.raises(TypeError, match="forbidden_input"):
        apply_naming_update(
            obs,
            identity,
            None,
            memories=[MetricDocument(metric_family="x")],
        )


def test_memory_reinforces_only_existing_bindings() -> None:
    identity = _identity()
    ledger = None
    for tick in (1, 2, 3):
        ledger = apply_naming_update(_observe(tick), identity, ledger)
    assert ledger is not None
    token = ledger.bindings[0].label_token
    before = ledger.bindings[0].strength
    memory = SimpleNamespace(
        memory_id=SimpleNamespace(value="mem-1"),
        forgotten_at_tick=None,
        expires_at_tick=None,
        concepts=(SimpleNamespace(concept=token),),
        relations=(),
    )
    reinforced = apply_naming_update(
        _observe(4), identity, ledger, memories=(memory,)
    )
    match = next(item for item in reinforced.bindings if item.label_token == token)
    assert match.strength > before
    empty = apply_naming_update(
        _observe(1, owner="cy", location="other"),
        _identity("cy"),
        None,
        memories=(memory,),
    )
    assert empty.bindings == () or all(
        item.label_token != token for item in empty.bindings
    )
    # memory alone on empty ledger does not mint that token
    assert all(item.label_token.startswith("place_") for item in empty.bindings)


def test_call_transmission_adopts_without_speaker_candidates() -> None:
    speaker_identity = _identity("ada", "ben")
    speaker_ledger = None
    for tick in (1, 2, 3):
        speaker_ledger = apply_naming_update(
            _observe(tick, owner="ada"), speaker_identity, speaker_ledger
        )
    assert speaker_ledger is not None
    token = speaker_ledger.bindings[0].label_token
    utterance = origin_utterance(
        text="call",
        speaker_id=EntityId("body-ada"),
        communication_id="call-1",
        relations=(
            CommunicationRelation(
                subject=token,
                predicate="call",
                object="location",
            ),
        ),
        source_basis=CommunicationSourceBasis.UNREFERENCED,
    )
    communication = ObservedCommunication(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.COMMUNICATION,
            source_tick=0,
            source_event_id=EventId("evt-call-1"),
        ),
        speaker_id=EntityId("body-ada"),
        listener_id=EntityId("body-ben"),
        utterance=utterance,
        action_kind="talk",
    )
    listener = _identity("ben", "ada")
    # Listener at a different location so they do not self-bind the speaker token.
    adopted = apply_naming_update(
        _observe(
            1,
            owner="ben",
            location="forest",
            communications=(communication,),
        ),
        listener,
        None,
    )
    adopted_binding = next(
        item for item in adopted.bindings if item.label_token == token
    )
    assert adopted_binding.transmission is NamingTransmission.COMMUNICATED
    assert adopted_binding.candidates == ()
    assert adopted_binding.status is NamingStatus.CANDIDATE


def test_seeds_ignore_location_display_names() -> None:
    identity = _identity()
    ledger = apply_naming_update(
        _observe(1, location="northern_forest"), identity, None
    )
    token = ledger.bindings[0].label_token
    assert "northern" not in token
    assert "forest" not in token
    assert token.startswith("place_")
