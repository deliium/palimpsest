"""Owner-scoped social convention contracts, evidence, and habit updates."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from agents.cognition.configuration import CognitionSocialConventionMode
from agents.cognition.models import (
    ActionDirection,
    CounterpartBinding,
    OwnerSafeSocialIdentity,
)
from agents.cognition.social_conventions import (
    SOCIAL_CONVENTION_POLICY_VERSION,
    ConventionBelief,
    ConventionConceptualization,
    ConventionContent,
    ConventionEvidenceChannel,
    ConventionEvidenceItem,
    ConventionExplanation,
    ConventionLedger,
    ConventionSituation,
    ConventionStatus,
    ConventionTransmission,
    SocialConventionPolicy,
    apply_convention_update,
    convention_belief_id,
    convention_evidence_id,
    convention_habit_penalties,
    default_social_convention_policy,
    empty_convention_ledger,
    require_owner_social_conventions,
)
from agents.models import AgentId
from simulation.runner_models import SocialConventionMode
from world.identifiers import EntityId, EventId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import (
    CoarseHealth,
    Observation,
    ObservationAudienceRole,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedOccurrence,
    ObservedSelf,
    VisibleBody,
)
from world.values import (
    CarryCapacity,
    DayPhase,
    Fatigue,
    Health,
    Hunger,
    TemperatureCelsius,
    Thirst,
)


def _agent(value: str) -> AgentId:
    return AgentId(value)


def _content(
    *,
    situation: ConventionSituation = ConventionSituation.COLOCATED_MEETING,
    usual_action: str = "wait",
) -> ConventionContent:
    return ConventionContent(situation=situation, usual_action=usual_action)


def _identity() -> OwnerSafeSocialIdentity:
    return OwnerSafeSocialIdentity(
        owner_id=_agent("ada"),
        owner_entity_id=EntityId("body-ada"),
        counterparts=(
            CounterpartBinding(agent_id=_agent("ben"), entity_id=EntityId("body-ben")),
            CounterpartBinding(agent_id=_agent("cy"), entity_id=EntityId("body-cy")),
        ),
    )


def _self() -> ObservedSelf:
    return ObservedSelf(
        entity_id=EntityId("body-ada"),
        location_id=EntityId("clearing"),
        health=Health(100),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )


def _body(entity: str) -> VisibleBody:
    return VisibleBody(
        entity_id=EntityId(entity),
        life_status=LifeStatus.ALIVE,
        coarse_health=CoarseHealth.STABLE,
    )


def _occur(
    kind: str,
    actor: str,
    other: str | None,
    event: str,
    *,
    tick: int,
    success: bool | None = True,
) -> ObservedOccurrence:
    return ObservedOccurrence(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.OCCURRENCE,
            source_tick=tick,
            source_event_id=EventId(event),
        ),
        kind=kind,
        audience_role=ObservationAudienceRole.WITNESS,
        actor_id=EntityId(actor),
        other_entity_id=None if other is None else EntityId(other),
        success=success,
    )


def _observe(
    *occurrences: ObservedOccurrence,
    tick: int,
    day_phase: DayPhase | None = None,
    bodies: tuple[VisibleBody, ...] | None = None,
) -> Observation:
    visible = (_body("body-ben"),) if bodies is None else bodies
    return Observation(
        world_id=WorldId("world-w"),
        observer_id=EntityId("body-ada"),
        revision=WorldRevision(1),
        tick=tick + 1,
        self_body=_self(),
        occurrences=occurrences,
        visible_bodies=visible,
        day_phase=day_phase,
    )


def _belief(
    ledger: ConventionLedger, situation: ConventionSituation, action: str
) -> ConventionBelief:
    matches = [
        item
        for item in ledger.beliefs
        if item.content.situation is situation and item.content.usual_action == action
    ]
    assert len(matches) == 1
    return matches[0]


@dataclass
class _Future:
    future_id: str
    direction: object


def test_policy_locks_constants_and_modes_match() -> None:
    policy = default_social_convention_policy()
    assert (
        policy.version
        == SOCIAL_CONVENTION_POLICY_VERSION
        == "social-conventions.v1"
    )
    assert policy.active_strength == 0.40
    assert policy.retire_strength == 0.20
    assert policy.decay == 0.05
    assert policy.conforming_colocated_meeting == 0.12
    assert policy.conforming_timed_gathering == 0.15
    assert policy.conforming_greeting_exchange == 0.12
    assert policy.conforming_habitual_exchange == 0.15
    assert policy.conforming_collective_action == 0.15
    assert policy.transmission_delta == 0.10
    assert policy.remembered_delta == 0.08
    assert policy.penalty == 0.30
    assert policy.promotion_count == 3
    assert policy.explanation_fade_ticks == 8
    assert policy.utterance_interval == 4
    assert policy.max_beliefs == 8
    assert policy.max_evidence == 32
    assert policy.max_participants == 8
    assert policy.max_variants == 4
    with pytest.raises(ValueError, match="unsupported_policy"):
        SocialConventionPolicy(active_strength=0.5)
    assert [mode.value for mode in CognitionSocialConventionMode] == [
        mode.value for mode in SocialConventionMode
    ]
    assert CognitionSocialConventionMode.DISABLED.value == "disabled"
    assert CognitionSocialConventionMode.DETERMINISTIC.value == "deterministic"


def test_belief_id_is_sha256_of_owner_and_content_key() -> None:
    owner = _agent("ada")
    content = _content()
    belief_id = convention_belief_id(owner, content)
    expected = hashlib.sha256(
        f"{owner.value}|{content.situation.value}|{content.usual_action}"
        f"|-|-|{content.counterpart_class.value}|-".encode()
    ).hexdigest()
    assert belief_id == expected
    assert len(belief_id) == 64


def test_belief_rejects_unknown_enums_and_oversized_participants() -> None:
    owner = _agent("ada")
    content = _content()
    belief_id = convention_belief_id(owner, content)
    with pytest.raises(ValueError, match="unknown_status"):
        ConventionBelief(
            belief_id=belief_id,
            owner_id=owner,
            content=content,
            status="active",  # type: ignore[arg-type]
            strength=0.4,
        )
    participants = tuple(_agent(f"p{index}") for index in range(9))
    with pytest.raises(ValueError, match="cap_exceeded"):
        ConventionBelief(
            belief_id=belief_id,
            owner_id=owner,
            content=content,
            status=ConventionStatus.CANDIDATE,
            strength=0.12,
            participant_ids=participants,
        )


def test_named_custom_requires_communicated_custom_lineage() -> None:
    owner = _agent("ada")
    content = _content(
        situation=ConventionSituation.GREETING_EXCHANGE,
        usual_action="talk",
    )
    belief_id = convention_belief_id(owner, content)
    with pytest.raises(ValueError, match="custom_lineage_required"):
        ConventionBelief(
            belief_id=belief_id,
            owner_id=owner,
            content=content,
            status=ConventionStatus.ACTIVE,
            strength=0.40,
            conceptualization=ConventionConceptualization.NAMED_CUSTOM,
        )
    evidence = ConventionEvidenceItem(
        evidence_id=convention_evidence_id(
            belief_id,
            0,
            ConventionEvidenceChannel.COMMUNICATED,
            "tick-1-0",
        ),
        ordinal=0,
        channel=ConventionEvidenceChannel.COMMUNICATED,
        lineage_ref="tick-1-0",
        tick=1,
        predicate="custom",
    )
    belief = ConventionBelief(
        belief_id=belief_id,
        owner_id=owner,
        content=content,
        status=ConventionStatus.ACTIVE,
        strength=0.40,
        conceptualization=ConventionConceptualization.NAMED_CUSTOM,
        transmission=ConventionTransmission.COMMUNICATED,
        remembered_explanation=ConventionExplanation.SOCIAL_CONTACT,
        evidence=(evidence,),
    )
    assert belief.conceptualization is ConventionConceptualization.NAMED_CUSTOM


def test_disabled_mode_accepts_none_ledger() -> None:
    owner = _agent("ada")
    require_owner_social_conventions(None, owner, field_name="social_conventions")
    ledger = empty_convention_ledger(owner)
    assert isinstance(ledger, ConventionLedger)
    assert ledger.beliefs == ()
    require_owner_social_conventions(
        ledger, owner, field_name="social_conventions"
    )
    with pytest.raises(ValueError, match="owner_id mismatch"):
        require_owner_social_conventions(
            ledger, _agent("ben"), field_name="social_conventions"
        )
    with pytest.raises(TypeError, match="ConventionLedger"):
        require_owner_social_conventions(
            object(), owner, field_name="social_conventions"
        )


def test_runner_v18_wires_deterministic_convention_mode(
    caplog: pytest.LogCaptureFixture,
) -> None:
    import json
    import logging
    from dataclasses import replace

    from agents.cognition.configuration import CognitionSocialConventionMode
    from simulation.runner import _cognition_config_for
    from simulation.runner_models import (
        RUNNER_SCHEMA_VERSION,
        RUNNER_SCHEMA_VERSION_V17,
        RUNNER_SCHEMA_VERSION_V18,
        CognitionTraceDetail,
        CognitionTraceSpec,
        GroupFormationMode,
        MortalityMode,
        SocialConventionMode,
        SocialNormMode,
        V2CapabilityFlags,
    )
    from simulation.runner_serialization import (
        decode_runner_config,
        encode_runner_config,
    )
    from tests.unit.test_runner_serialization import _configured
    from world.environment import example_environmental_dynamics

    assert RUNNER_SCHEMA_VERSION == "runner-config-v4"
    flags = V2CapabilityFlags(multi_hop_testimony_tracking=True)
    assert flags.unimplemented_enabled_names() == ("multi_hop_testimony_tracking",)
    base = _configured(schema_version=RUNNER_SCHEMA_VERSION)
    quiet = json.loads(encode_runner_config(base).decode("utf-8"))
    assert quiet["schema_version"] == "runner-config-v4"
    assert "social_convention_mode" not in quiet["agents"][0]["cognition"]
    agent = base.agents[0]
    early = replace(
        agent,
        cognition=replace(
            agent.cognition,
            social_convention_mode=SocialConventionMode.DETERMINISTIC,
        ),
    )
    with pytest.raises(ValueError, match="social_convention_mode_requires_v18"):
        replace(base, agents=(early,))
    norms_only = replace(
        agent,
        cognition=replace(
            agent.cognition, social_norm_mode=SocialNormMode.DETERMINISTIC
        ),
    )
    norms_config = replace(
        base, agents=(norms_only,), schema_version=RUNNER_SCHEMA_VERSION_V17
    )
    norms_doc = json.loads(encode_runner_config(norms_config).decode("utf-8"))
    assert norms_doc["schema_version"] == "runner-config-v17"
    assert "social_convention_mode" not in norms_doc["agents"][0]["cognition"]
    assert norms_doc["agents"][0]["cognition"]["social_norm_mode"] == "deterministic"
    with pytest.raises(ValueError, match="v18_requires_social_conventions"):
        replace(norms_config, schema_version=RUNNER_SCHEMA_VERSION_V18)
    enabled = replace(base, agents=(early,), schema_version=RUNNER_SCHEMA_VERSION_V18)
    encoded = encode_runner_config(enabled)
    document = json.loads(encoded.decode("utf-8"))
    assert document["schema_version"] == "runner-config-v18"
    assert (
        document["agents"][0]["cognition"]["social_convention_mode"] == "deterministic"
    )
    assert decode_runner_config(encoded) == enabled
    both = replace(
        early,
        cognition=replace(
            early.cognition,
            social_norm_mode=SocialNormMode.DETERMINISTIC,
            group_formation_mode=GroupFormationMode.DETERMINISTIC,
        ),
    )
    traced = replace(
        base,
        agents=(both,),
        schema_version=RUNNER_SCHEMA_VERSION_V18,
        environmental_dynamics=example_environmental_dynamics(),
        capability_flags=V2CapabilityFlags(extended_self_model=True),
        cognition_trace=CognitionTraceSpec(
            enabled=True,
            detail=CognitionTraceDetail.SUMMARY,
        ),
    )
    traced_doc = json.loads(encode_runner_config(traced).decode("utf-8"))
    assert traced_doc["capability_flags"]["extended_self_model"] is True
    assert traced_doc["cognition_trace"]["enabled"] is True
    assert "environmental_dynamics" in traced_doc
    cognition = traced_doc["agents"][0]["cognition"]
    assert cognition["social_norm_mode"] == "deterministic"
    assert cognition["social_convention_mode"] == "deterministic"
    assert cognition["group_formation_mode"] == "deterministic"
    assert decode_runner_config(encode_runner_config(traced)) == traced
    caplog.set_level(logging.DEBUG, logger="simulation.runner")
    built = _cognition_config_for(
        early.cognition,
        mortality_mode=MortalityMode.ENABLED,
        capability_flags=V2CapabilityFlags(),
    )
    assert built.social_convention_mode is CognitionSocialConventionMode.DETERMINISTIC
    assert built.social_convention_policy is not None
    assert built.social_convention_policy.version == "social-conventions.v1"
    assert any(
        "cognition_config_social_convention_mode mode=deterministic "
        "policy_version=social-conventions.v1" in record.getMessage()
        for record in caplog.records
    )


def test_content_rejects_unknown_situation_and_action() -> None:
    with pytest.raises(ValueError, match="unknown_situation"):
        ConventionContent(
            situation="ritual",  # type: ignore[arg-type]
            usual_action="wait",
        )
    with pytest.raises(ValueError, match="unknown_action"):
        ConventionContent(
            situation=ConventionSituation.COLOCATED_MEETING,
            usual_action="ritual",
        )
    with pytest.raises(ValueError, match="unexpected_day_phase"):
        from world.values import DayPhase

        ConventionContent(
            situation=ConventionSituation.COLOCATED_MEETING,
            usual_action="wait",
            day_phase=DayPhase.DAY,
        )
    location = EntityId("clearing")
    content = ConventionContent(
        situation=ConventionSituation.COLOCATED_MEETING,
        usual_action="wait",
        location_id=location,
    )
    assert content.location_id == location


def test_colocated_meeting_promotes_after_strength_threshold() -> None:
    identity = _identity()
    ledger = None
    # 0.12 * 3 = 0.36 < 0.40, so three ticks stay candidate with below_strength.
    for tick in range(3):
        ledger = apply_convention_update(
            _observe(
                _occur("wait", "body-ada", None, f"w-{tick}", tick=tick),
                tick=tick,
            ),
            identity,
            ledger,
        )
    assert ledger is not None
    mid = _belief(ledger, ConventionSituation.COLOCATED_MEETING, "wait")
    assert mid.status is ConventionStatus.CANDIDATE
    assert mid.repetition_count == 3
    assert "below_strength" in ledger.notices
    # Fourth conforming tick reaches active strength.
    ledger = apply_convention_update(
        _observe(
            _occur("wait", "body-ada", None, "w-3", tick=3),
            tick=3,
        ),
        identity,
        ledger,
    )
    belief = _belief(ledger, ConventionSituation.COLOCATED_MEETING, "wait")
    assert belief.status is ConventionStatus.ACTIVE
    assert belief.repetition_count == 4
    assert belief.strength >= 0.40
    one = apply_convention_update(
        _observe(
            _occur("wait", "body-ben", None, "w-solo", tick=10),
            tick=10,
        ),
        identity,
        None,
    )
    candidate = _belief(one, ConventionSituation.COLOCATED_MEETING, "wait")
    assert candidate.status is ConventionStatus.CANDIDATE
    assert candidate.repetition_count == 1
    assert "below_count" in one.notices


def test_three_timed_gatherings_promote() -> None:
    identity = _identity()
    ledger = None
    for tick in range(3):
        ledger = apply_convention_update(
            _observe(
                _occur("wait", "body-ada", None, f"tg-p-{tick}", tick=tick),
                tick=tick,
                day_phase=DayPhase.DAY,
            ),
            identity,
            ledger,
        )
    assert ledger is not None
    belief = _belief(ledger, ConventionSituation.TIMED_GATHERING, "wait")
    assert belief.status is ConventionStatus.ACTIVE
    assert belief.repetition_count == 3
    assert belief.strength >= 0.40


def test_timed_gathering_exclusive_of_colocated() -> None:
    identity = _identity()
    first = apply_convention_update(
        _observe(
            _occur("wait", "body-ada", None, "tg-0", tick=0),
            tick=0,
            day_phase=DayPhase.DAY,
        ),
        identity,
        None,
    )
    belief = _belief(first, ConventionSituation.TIMED_GATHERING, "wait")
    assert belief.content.day_phase is DayPhase.DAY
    assert all(
        item.content.situation is not ConventionSituation.COLOCATED_MEETING
        for item in first.beliefs
    )
    night = apply_convention_update(
        _observe(
            _occur("wait", "body-ada", None, "tg-1", tick=1),
            tick=1,
            day_phase=DayPhase.NIGHT,
        ),
        identity,
        first,
    )
    assert night.beliefs[0].repetition_count == 1
    day_again = apply_convention_update(
        _observe(
            _occur("wait", "body-ada", None, "tg-2", tick=2),
            tick=2,
            day_phase=DayPhase.DAY,
        ),
        identity,
        first,
    )
    assert day_again.beliefs[0].repetition_count == 2


def test_forbidden_inputs_and_memory_reinforce_only() -> None:
    identity = _identity()

    class WorldState:
        pass

    class MetricDocument:
        pass

    with pytest.raises(TypeError, match="forbidden_input"):
        apply_convention_update(WorldState(), identity, None)
    with pytest.raises(TypeError, match="forbidden_input"):
        apply_convention_update(_observe(tick=0), identity, MetricDocument())
    empty = apply_convention_update(
        _observe(tick=0),
        identity,
        None,
        memories=(
            SimpleNamespace(
                memory_id=SimpleNamespace(value="mem-1"),
                concepts=(SimpleNamespace(concept="colocated_meeting"),),
                relations=(),
                forgotten_at_tick=None,
                expires_at_tick=None,
            ),
        ),
    )
    assert empty.beliefs == ()
    seeded = apply_convention_update(
        _observe(
            _occur("wait", "body-ada", None, "seed", tick=0),
            tick=0,
        ),
        identity,
        None,
    )
    before = seeded.beliefs[0].strength
    reinforced = apply_convention_update(
        _observe(tick=1, bodies=(_body("body-ben"),)),
        identity,
        seeded,
        memories=(
            SimpleNamespace(
                memory_id=SimpleNamespace(value="mem-2"),
                concepts=(
                    SimpleNamespace(
                        mention_id=SimpleNamespace(value="c1"),
                        concept="colocated_meeting",
                    ),
                    SimpleNamespace(
                        mention_id=SimpleNamespace(value="c2"),
                        concept="wait",
                    ),
                ),
                relations=(),
                forgotten_at_tick=None,
                expires_at_tick=None,
            ),
        ),
    )
    assert reinforced.beliefs[0].strength == pytest.approx(before + 0.08)
    assert any(
        item.channel is ConventionEvidenceChannel.REMEMBERED
        for item in reinforced.beliefs[0].evidence
    )


def test_explanation_fades_while_habit_persists() -> None:
    identity = _identity()
    ledger = None
    for tick in range(3):
        ledger = apply_convention_update(
            _observe(
                _occur("wait", "body-ada", None, f"fade-{tick}", tick=tick),
                tick=tick,
                day_phase=DayPhase.DAY,
                bodies=(_body("body-ben"), _body("body-cy")),
            ),
            identity,
            ledger,
        )
    assert ledger is not None
    belief = ledger.beliefs[0]
    assert belief.status is ConventionStatus.ACTIVE
    assert belief.remembered_explanation is ConventionExplanation.COORDINATION
    # Conforming evidence continues but only one other present → cue gone.
    for tick in range(3, 12):
        ledger = apply_convention_update(
            _observe(
                _occur("wait", "body-ada", None, f"fade-{tick}", tick=tick),
                tick=tick,
                day_phase=DayPhase.DAY,
                bodies=(_body("body-ben"),),
            ),
            identity,
            ledger,
        )
    faded = ledger.beliefs[0]
    assert faded.remembered_explanation is ConventionExplanation.FORGOTTEN
    assert faded.status is ConventionStatus.ACTIVE
    assert faded.strength >= 0.40


def test_transmission_usually_and_habit_penalties() -> None:
    from world.communications import CommunicationRelation, origin_utterance
    from world.observations import ObservedCommunication

    identity = _identity()
    communication = ObservedCommunication(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.COMMUNICATION,
            source_tick=0,
            source_event_id=EventId("comm-0"),
        ),
        speaker_id=EntityId("body-ben"),
        listener_id=EntityId("body-ada"),
        utterance=origin_utterance(
            text="usually",
            speaker_id=EntityId("body-ben"),
            relations=(
                CommunicationRelation(
                    subject="colocated_meeting",
                    predicate="usually",
                    object="wait",
                ),
            ),
        ),
        action_kind="talk",
    )
    adopted = apply_convention_update(
        Observation(
            world_id=WorldId("world-w"),
            observer_id=EntityId("body-ada"),
            revision=WorldRevision(1),
            tick=1,
            self_body=_self(),
            communications=(communication,),
            visible_bodies=(_body("body-ben"),),
        ),
        identity,
        None,
    )
    belief = _belief(adopted, ConventionSituation.COLOCATED_MEETING, "wait")
    assert belief.transmission is ConventionTransmission.COMMUNICATED
    assert belief.conceptualization is ConventionConceptualization.NAMED_USUAL
    # Promote via more conforming ticks, then check penalties.
    ledger = adopted
    for tick in range(1, 4):
        ledger = apply_convention_update(
            _observe(
                _occur("wait", "body-ada", None, f"tx-{tick}", tick=tick),
                tick=tick,
            ),
            identity,
            ledger,
        )
    active = _belief(ledger, ConventionSituation.COLOCATED_MEETING, "wait")
    assert active.status is ConventionStatus.ACTIVE
    futures = (
        _Future("f-wait", ActionDirection.WAIT),
        _Future("f-eat", ActionDirection.EAT),
    )
    penalties = convention_habit_penalties(
        ledger,
        _observe(tick=5, bodies=(_body("body-ben"),)),
        futures,
        mode=CognitionSocialConventionMode.DETERMINISTIC,
    )
    assert penalties.get("f-eat") == pytest.approx(0.30)
    assert "f-wait" not in penalties
    empty = convention_habit_penalties(
        None,
        _observe(tick=5),
        futures,
        mode=CognitionSocialConventionMode.DISABLED,
    )
    assert empty == {}
    speaker = empty_convention_ledger(_agent("ben"))
    assert adopted is not speaker
    assert all(item.owner_id == _agent("ada") for item in adopted.beliefs)


def test_habitual_exchange_promotes_and_links_competing_variant() -> None:
    identity = _identity()
    ledger = None
    for tick in range(3):
        ledger = apply_convention_update(
            _observe(
                _occur("give", "body-ada", "body-ben", f"g-{tick}", tick=tick),
                tick=tick,
            ),
            identity,
            ledger,
        )
    assert ledger is not None
    habit = _belief(ledger, ConventionSituation.HABITUAL_EXCHANGE, "give")
    assert habit.status is ConventionStatus.ACTIVE
    assert habit.repetition_count == 3
    # Competing variants share situation/location/phase and differ in usual_action.
    wait_ledger = None
    for tick in range(4):
        wait_ledger = apply_convention_update(
            _observe(
                _occur("wait", "body-ada", None, f"cv-w-{tick}", tick=tick),
                tick=tick,
            ),
            identity,
            wait_ledger,
        )
    talk_ledger = wait_ledger
    for tick in range(4, 8):
        talk_ledger = apply_convention_update(
            _observe(
                _occur("talk", "body-ada", "body-ben", f"cv-t-{tick}", tick=tick),
                tick=tick,
            ),
            identity,
            talk_ledger,
        )
    wait_belief = _belief(
        talk_ledger, ConventionSituation.COLOCATED_MEETING, "wait"
    )
    talk_belief = _belief(
        talk_ledger, ConventionSituation.COLOCATED_MEETING, "talk"
    )
    assert talk_belief.belief_id in wait_belief.competing_variant_ids
    assert wait_belief.belief_id in talk_belief.competing_variant_ids


def test_bare_talk_is_not_greeting_exchange() -> None:
    identity = _identity()
    ledger = apply_convention_update(
        _observe(
            _occur("talk", "body-ben", "body-ada", "talk-bare", tick=0),
            tick=0,
        ),
        identity,
        None,
    )
    assert all(
        item.content.situation is not ConventionSituation.GREETING_EXCHANGE
        for item in ledger.beliefs
    )


def test_owners_keep_separate_ledgers_and_no_ritual_fields() -> None:
    ada = _identity()
    ben = OwnerSafeSocialIdentity(
        owner_id=_agent("ben"),
        owner_entity_id=EntityId("body-ben"),
        counterparts=(
            CounterpartBinding(agent_id=_agent("ada"), entity_id=EntityId("body-ada")),
            CounterpartBinding(agent_id=_agent("cy"), entity_id=EntityId("body-cy")),
        ),
    )
    shared = _observe(
        _occur("wait", "body-ada", None, "sep-0", tick=0),
        tick=0,
    )
    ada_ledger = apply_convention_update(shared, ada, None)
    ben_observation = Observation(
        world_id=WorldId("world-w"),
        observer_id=EntityId("body-ben"),
        revision=WorldRevision(1),
        tick=1,
        self_body=ObservedSelf(
            entity_id=EntityId("body-ben"),
            location_id=EntityId("clearing"),
            health=Health(100),
            hunger=Hunger(0),
            thirst=Thirst(0),
            fatigue=Fatigue(0),
            temperature=TemperatureCelsius(36.5),
            inventory=(),
            life_status=LifeStatus.ALIVE,
            carry_capacity=CarryCapacity(10),
        ),
        occurrences=(
            _occur("wait", "body-ada", None, "sep-0", tick=0),
        ),
        visible_bodies=(_body("body-ada"),),
    )
    ben_ledger = apply_convention_update(ben_observation, ben, None)
    assert ada_ledger.owner_id != ben_ledger.owner_id
    assert ada_ledger.beliefs[0].belief_id != ben_ledger.beliefs[0].belief_id
    field_names = set(ConventionBelief.__dataclass_fields__)
    assert field_names.isdisjoint({"ritual", "tradition", "ceremony", "culture"})
    content_names = set(ConventionContent.__dataclass_fields__)
    assert content_names.isdisjoint({"ritual", "tradition", "ceremony", "culture"})
