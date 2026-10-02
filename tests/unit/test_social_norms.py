"""Owner-scoped social norm contracts, evidence, and private responses."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pytest

from agents.cognition.configuration import CognitionSocialNormMode
from agents.cognition.models import (
    ActionDirection,
    CounterpartBinding,
    OwnerSafeSocialIdentity,
)
from agents.cognition.social_norms import (
    SOCIAL_NORM_POLICY_VERSION,
    NormBelief,
    NormConsequence,
    NormConsequenceChannel,
    NormContext,
    NormEvidenceChannel,
    NormExpectation,
    NormLedger,
    NormPattern,
    NormResponse,
    NormSanction,
    NormStatus,
    NormUtterancePlan,
    SocialNormPolicy,
    apply_norm_update,
    default_social_norm_policy,
    norm_belief_id,
    norm_communicate_utterance,
    norm_response_penalties,
)
from agents.models import AgentId
from simulation.runner_models import SocialNormMode
from world.identifiers import EntityId, EventId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import (
    Observation,
    ObservationAudienceRole,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedOccurrence,
    ObservedResource,
    ObservedSelf,
)
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    ResourceKind,
    TemperatureCelsius,
    Thirst,
)


def _agent(value: str) -> AgentId:
    return AgentId(value)


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
    resources: tuple[ObservedResource, ...] = (),
) -> Observation:
    observation_tick = tick + 1
    return Observation(
        world_id=WorldId("world-w"),
        observer_id=EntityId("body-ada"),
        revision=WorldRevision(1),
        tick=observation_tick,
        self_body=_self(),
        occurrences=occurrences,
        resources=resources,
    )


def _food(quantity: float) -> ObservedResource:
    return ObservedResource(
        entity_id=EntityId("food-stock"),
        name="berries",
        kind=ResourceKind.FOOD,
        quantity=quantity,
        unit="portion",
    )


def _return_pair(tick: int) -> Observation:
    return _observe(
        _occur("give", "body-ada", "body-ben", f"g-{tick}-a", tick=tick),
        _occur("give", "body-ben", "body-ada", f"g-{tick}-b", tick=tick),
        tick=tick,
    )


@dataclass
class _Future:
    future_id: str
    direction: object
    target_agent_id: AgentId | None = None
    target_entity_id: str | None = None


class _GiveDirection:
    value = "give"


def _belief(ledger: object, pattern: NormPattern) -> NormBelief:
    assert ledger is not None
    matches = [item for item in ledger.beliefs if item.pattern is pattern]  # type: ignore[attr-defined]
    assert len(matches) == 1
    return matches[0]


def test_policy_locks_constants_and_modes_match() -> None:
    policy = default_social_norm_policy()
    assert policy.version == SOCIAL_NORM_POLICY_VERSION == "social-norms.v1"
    assert policy.active_confidence == 0.40
    assert policy.enforce_confidence == 0.50
    assert policy.retire_confidence == 0.20
    assert policy.decay == 0.05
    assert policy.conforming_delta == 0.15
    assert policy.violation_delta == -0.20
    assert policy.penalty == 0.35
    assert policy.conforming_count == 3
    assert policy.return_window_ticks == 8
    assert policy.spare_window_ticks == 1
    assert policy.utterance_interval == 4
    assert policy.exclusion_window_ticks == 8
    assert policy.scarcity_quantity == 1.0
    assert policy.critical_need_ratio == 0.75
    assert policy.trust_delta == -0.25
    assert policy.max_beliefs == 8
    assert policy.max_evidence == 32
    assert policy.max_supporters == 8
    with pytest.raises(ValueError, match="unsupported_policy"):
        SocialNormPolicy(active_confidence=0.5)
    assert [mode.value for mode in CognitionSocialNormMode] == [
        mode.value for mode in SocialNormMode
    ]
    assert CognitionSocialNormMode.DISABLED.value == "disabled"


def test_belief_rejects_mismatched_expectation_and_witnessed_own_sanctions() -> None:
    owner = _agent("ada")
    belief_id = norm_belief_id(owner, NormPattern.RETURN_TRANSFER, ())
    with pytest.raises(ValueError, match="pattern_mismatch"):
        NormBelief(
            belief_id=belief_id,
            owner_id=owner,
            pattern=NormPattern.RETURN_TRANSFER,
            expectation=NormExpectation.GIVE,
            context=NormContext(pattern=NormPattern.RETURN_TRANSFER),
            status=NormStatus.CANDIDATE,
            confidence=0.15,
        )
    with pytest.raises(ValueError, match="witnessed_forbidden"):
        NormConsequence(
            sanction=NormSanction.REFUSAL,
            channel=NormConsequenceChannel.WITNESSED,
            tick=1,
        )
    supporters = tuple(_agent(f"agent-{index}") for index in range(9))
    with pytest.raises(ValueError, match="cap_exceeded"):
        NormBelief(
            belief_id=norm_belief_id(owner, NormPattern.SHARE_UNDER_SCARCITY, ()),
            owner_id=owner,
            pattern=NormPattern.SHARE_UNDER_SCARCITY,
            expectation=NormExpectation.GIVE,
            context=NormContext(pattern=NormPattern.SHARE_UNDER_SCARCITY),
            status=NormStatus.CANDIDATE,
            confidence=0.15,
            supporters=supporters,
        )


def test_three_return_pairs_promote_and_one_stays_candidate(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger="agents.cognition.social_norms")
    identity = _identity()
    ledger = None
    for tick in range(3):
        ledger = apply_norm_update(_return_pair(tick), identity, ledger)
    belief = _belief(ledger, NormPattern.RETURN_TRANSFER)
    assert belief.status is NormStatus.ACTIVE
    assert belief.conforming_count == 3
    assert belief.confidence == pytest.approx(0.45)
    alone = apply_norm_update(_return_pair(0), identity, None)
    candidate = _belief(alone, NormPattern.RETURN_TRANSFER)
    assert candidate.status is NormStatus.CANDIDATE
    assert candidate.response_reason == "below_count"
    assert any(
        record.getMessage() == "norm_belief_withheld reason=below_count"
        for record in caplog.records
    )


def test_scarcity_give_conforms_and_a_missing_give_does_not_violate() -> None:
    identity = _identity()
    scarce = apply_norm_update(
        _observe(
            _occur("give", "body-ada", "body-ben", "share-1", tick=1),
            tick=1,
            resources=(_food(1.0),),
        ),
        identity,
        None,
    )
    shared = _belief(scarce, NormPattern.SHARE_UNDER_SCARCITY)
    assert shared.conforming_count == 1
    assert shared.evidence[0].channel is NormEvidenceChannel.CONFORMING
    plentiful = apply_norm_update(
        _observe(
            _occur("give", "body-ada", "body-ben", "share-2", tick=1),
            tick=1,
            resources=(_food(2.0),),
        ),
        identity,
        None,
    )
    assert plentiful.beliefs == ()
    quiet = apply_norm_update(
        _observe(tick=2, resources=(_food(1.0),)),
        identity,
        None,
    )
    assert quiet.beliefs == ()


def test_sleep_conforms_and_later_attack_violates() -> None:
    identity = _identity()
    slept = apply_norm_update(
        _observe(_occur("sleep", "body-ben", None, "sleep-1", tick=1), tick=1),
        identity,
        None,
    )
    spare = _belief(slept, NormPattern.SPARE_AFTER_SLEEP)
    assert spare.conforming_count == 1
    assert spare.status is NormStatus.CANDIDATE
    attacked = apply_norm_update(
        _observe(_occur("attack", "body-cy", "body-ben", "atk-1", tick=2), tick=2),
        identity,
        slept,
    )
    updated = _belief(attacked, NormPattern.SPARE_AFTER_SLEEP)
    assert any(
        item.channel is NormEvidenceChannel.VIOLATION for item in updated.evidence
    )


def test_reciprocal_openers_stay_candidate_until_a_later_give() -> None:
    identity = _identity()
    opened = apply_norm_update(_return_pair(1), identity, None)
    exchange = _belief(opened, NormPattern.RECIPROCAL_EXCHANGE)
    assert exchange.status is NormStatus.CANDIDATE
    assert exchange.confidence == 0.0
    assert exchange.conforming_count == 0
    again = apply_norm_update(
        _observe(_occur("give", "body-ada", "body-ben", "g-2", tick=2), tick=2),
        identity,
        opened,
    )
    later = _belief(again, NormPattern.RECIPROCAL_EXCHANGE)
    assert later.conforming_count == 1
    assert later.confidence == pytest.approx(0.15)


def test_forbidden_inputs_raise_and_owners_stay_separate() -> None:
    class WorldState:
        pass

    class MetricDocument:
        pass

    with pytest.raises(TypeError, match="forbidden_input"):
        apply_norm_update(WorldState(), _identity(), None)
    with pytest.raises(TypeError, match="forbidden_input"):
        apply_norm_update(_observe(tick=1), _identity(), MetricDocument())
    identity = _identity()
    other = OwnerSafeSocialIdentity(
        owner_id=_agent("ben"),
        owner_entity_id=EntityId("body-ben"),
        counterparts=(
            CounterpartBinding(agent_id=_agent("ada"), entity_id=EntityId("body-ada")),
            CounterpartBinding(agent_id=_agent("cy"), entity_id=EntityId("body-cy")),
        ),
    )
    observation = _return_pair(1)
    left = apply_norm_update(observation, identity, None)
    right = apply_norm_update(observation, other, None)
    assert left.owner_id != right.owner_id
    assert left.beliefs[0].belief_id != right.beliefs[0].belief_id


def test_enforce_without_futures_records_unavailable(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger="agents.cognition.social_norms")
    identity = _identity()
    ledger = None
    for tick in range(5):
        ledger = apply_norm_update(
            _observe(
                _occur("sleep", "body-ben", None, f"sleep-{tick}", tick=tick),
                tick=tick,
            ),
            identity,
            ledger,
        )
    attack = _observe(
        _occur("attack", "body-cy", "body-ben", "atk-late", tick=5),
        tick=5,
    )
    violated = apply_norm_update(attack, identity, ledger)
    result = norm_response_penalties(
        violated,
        attack,
        (_Future("wait-1", ActionDirection.WAIT),),
        0.0,
        0.0,
        identity=identity,
        relationships=(),
        mode=CognitionSocialNormMode.DETERMINISTIC,
    )
    assert result.ledger is not None
    spare = _belief(result.ledger, NormPattern.SPARE_AFTER_SLEEP)
    assert spare.response is NormResponse.ENFORCE
    assert spare.response_reason in {"sanction_latent", "sanction_unavailable"}
    assert result.as_dict() == {}
    assert result.ledger.trust_requests == ()
    assert any(
        "trust_revision_skipped reason=no_profile" in record.getMessage()
        for record in caplog.records
    )


def test_communicate_stamps_existing_talk() -> None:
    from world.actions import Talk
    from world.communications import CommunicationSourceBasis, origin_utterance

    identity = _identity()
    owner = identity.owner_id
    placeholder = Talk(
        recipient_id=EntityId("body-ben"),
        utterance=origin_utterance(
            text="placeholder",
            speaker_id=identity.owner_entity_id,
        ),
    )
    ledger = NormLedger(
        owner_id=owner,
        utterance_plans=(
            NormUtterancePlan(
                pattern=NormPattern.RETURN_TRANSFER,
                predicate="expect",
                subject="return_transfer",
                object="ben",
            ),
        ),
    )
    stamped = norm_communicate_utterance(
        placeholder,
        owner_id=owner,
        tick=4,
        observation=_observe(tick=3),
        identity=identity,
        ledger=ledger,
        mode=CognitionSocialNormMode.DETERMINISTIC,
    )
    assert type(stamped) is Talk
    assert stamped.recipient_id == placeholder.recipient_id
    relation = stamped.utterance.content.relations[0]
    assert relation.predicate == "expect"
    assert relation.subject == "return_transfer"
    assert relation.object == "ben"
    assert (
        stamped.utterance.declared.source_basis
        is CommunicationSourceBasis.UNREFERENCED
    )


def test_disabled_mode_returns_an_empty_penalty_map() -> None:
    identity = _identity()
    ledger = None
    for tick in range(3):
        ledger = apply_norm_update(_return_pair(tick), identity, ledger)
    empty = norm_response_penalties(
        ledger,
        _return_pair(4),
        (),
        0.0,
        0.0,
        mode=CognitionSocialNormMode.DISABLED,
    )
    assert empty.as_dict() == {}
    assert empty.ledger is None
    missing = norm_response_penalties(None, _observe(tick=1), (), 0.0, 0.0)
    assert missing.as_dict() == {}


def test_follow_penalizes_existing_eat_and_does_not_add_give() -> None:
    identity = _identity()
    ledger = apply_norm_update(
        _observe(
            _occur("give", "body-ada", "body-ben", "food-1", tick=1),
            tick=1,
            resources=(_food(1.0),),
        ),
        identity,
        None,
    )
    for tick, event in ((2, "food-2"), (3, "food-3")):
        ledger = apply_norm_update(
            _observe(
                _occur("give", "body-ben", "body-ada", event, tick=tick),
                tick=tick,
                resources=(_food(1.0),),
            ),
            identity,
            ledger,
        )
    shared = _belief(ledger, NormPattern.SHARE_UNDER_SCARCITY)
    assert shared.status is NormStatus.ACTIVE
    eat = _Future("eat-1", ActionDirection.EAT)
    wait = _Future("wait-1", ActionDirection.WAIT)
    give = _Future("give-1", _GiveDirection())
    result = norm_response_penalties(
        ledger,
        _observe(tick=4, resources=(_food(1.0),)),
        (eat, wait, give),
        hunger=10.0,
        thirst=0.0,
        identity=identity,
        mode=CognitionSocialNormMode.DETERMINISTIC,
    )
    assert result.ledger is not None
    chosen = _belief(result.ledger, NormPattern.SHARE_UNDER_SCARCITY)
    assert chosen.response is NormResponse.FOLLOW
    penalties = result.as_dict()
    assert penalties.get("eat-1") == pytest.approx(0.35)
    assert "give-1" not in penalties


def test_runner_v17_round_trips_social_norms(caplog: pytest.LogCaptureFixture) -> None:
    import json
    from dataclasses import replace

    from simulation.runner import _cognition_config_for
    from simulation.runner_models import (
        RUNNER_SCHEMA_VERSION,
        RUNNER_SCHEMA_VERSION_V16,
        RUNNER_SCHEMA_VERSION_V17,
        CognitionTraceDetail,
        CognitionTraceSpec,
        GroupFormationMode,
        MortalityMode,
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
    assert "social_norm_mode" not in quiet["agents"][0]["cognition"]
    agent = base.agents[0]
    early = replace(
        agent,
        cognition=replace(
            agent.cognition, social_norm_mode=SocialNormMode.DETERMINISTIC
        ),
    )
    with pytest.raises(ValueError, match="social_norm_mode_requires_v17"):
        replace(base, agents=(early,))
    grouped = replace(
        agent,
        cognition=replace(
            agent.cognition, group_formation_mode=GroupFormationMode.DETERMINISTIC
        ),
    )
    group_only = replace(
        base, agents=(grouped,), schema_version=RUNNER_SCHEMA_VERSION_V16
    )
    group_doc = json.loads(encode_runner_config(group_only).decode("utf-8"))
    assert group_doc["schema_version"] == "runner-config-v16"
    assert "social_norm_mode" not in group_doc["agents"][0]["cognition"]
    with pytest.raises(ValueError, match="v17_requires_social_norms"):
        replace(group_only, schema_version=RUNNER_SCHEMA_VERSION_V17)
    enabled = replace(base, agents=(early,), schema_version=RUNNER_SCHEMA_VERSION_V17)
    encoded = encode_runner_config(enabled)
    document = json.loads(encoded.decode("utf-8"))
    assert document["schema_version"] == "runner-config-v17"
    assert document["agents"][0]["cognition"]["social_norm_mode"] == "deterministic"
    assert decode_runner_config(encoded) == enabled
    both = replace(
        early,
        cognition=replace(
            early.cognition,
            group_formation_mode=GroupFormationMode.DETERMINISTIC,
        ),
    )
    traced = replace(
        base,
        agents=(both,),
        schema_version=RUNNER_SCHEMA_VERSION_V17,
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
    assert cognition["group_formation_mode"] == "deterministic"
    assert decode_runner_config(encode_runner_config(traced)) == traced
    caplog.set_level(logging.DEBUG, logger="simulation.runner")
    built = _cognition_config_for(
        early.cognition,
        mortality_mode=MortalityMode.ENABLED,
        capability_flags=V2CapabilityFlags(),
    )
    assert built.social_norm_mode is CognitionSocialNormMode.DETERMINISTIC
    assert built.social_norm_policy is not None
    assert built.social_norm_policy.version == "social-norms.v1"
    assert any(
        "cognition_config_social_norm_mode mode=deterministic "
        "policy_version=social-norms.v1" in record.getMessage()
        for record in caplog.records
    )
