"""Owner-scoped reputation contracts."""

from __future__ import annotations

import dataclasses
import logging

import pytest

from agents.cognition.configuration import CognitionReputationMode
from agents.cognition.models import CounterpartBinding, OwnerSafeSocialIdentity
from agents.cognition.reputation import (
    REPUTATION_POLICY_VERSION,
    ReputationChannel,
    ReputationDimension,
    ReputationDimensionState,
    ReputationEvidenceItem,
    ReputationFormationPolicy,
    ReputationLedger,
    ReputationProfile,
    ReputationSourceTrustBand,
    apply_reputation_update,
    default_reputation_policy,
    empty_reputation_ledger,
    neutral_dimension_state,
    reputation_evidence_id,
    reputation_profile_id,
    source_trust_band_for,
)
from agents.models import AgentId
from simulation.runner_models import ReputationMode
from world.identifiers import EntityId, EventId, WorldId, WorldRevision
from world.observations import (
    Observation,
    ObservationAudienceRole,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedOccurrence,
)

_LOGGER = "agents.cognition.reputation"
_BANNED_FIELDS = frozenset(
    {
        "global_score",
        "trustworthy",
        "dangerous",
        "generous",
        "competent",
        "unreliable",
        "rumor",
        "prestige",
    }
)
_TYPES = (
    ReputationDimensionState,
    ReputationEvidenceItem,
    ReputationProfile,
    ReputationLedger,
    ReputationFormationPolicy,
)


def _agent(value: str) -> AgentId:
    return AgentId(value)


def _states() -> dict[str, ReputationDimensionState]:
    neutral = neutral_dimension_state()
    return {
        "reliability": neutral,
        "harm": neutral,
        "generosity": neutral,
        "competence": neutral,
    }


def _profile(
    owner: AgentId,
    target: AgentId,
    evidence: tuple[ReputationEvidenceItem, ...] = (),
    **states: ReputationDimensionState,
) -> ReputationProfile:
    fields = _states()
    fields.update(states)
    return ReputationProfile(
        profile_id=reputation_profile_id(owner, target),
        owner_id=owner,
        target_id=target,
        evidence=evidence,
        reliability=fields["reliability"],
        harm=fields["harm"],
        generosity=fields["generosity"],
        competence=fields["competence"],
    )


def _item(
    owner: AgentId,
    target: AgentId,
    *,
    ordinal: int = 0,
    dimension: ReputationDimension = ReputationDimension.GENEROSITY,
    channel: ReputationChannel = ReputationChannel.DIRECT_OBSERVATION,
    lineage_ref: str = "event-1",
    delta: float = 0.25,
    tick: int = 1,
) -> ReputationEvidenceItem:
    profile_id = reputation_profile_id(owner, target)
    return ReputationEvidenceItem(
        owner_id=owner,
        target_id=target,
        dimension=dimension,
        channel=channel,
        lineage_ref=lineage_ref,
        source_id=owner,
        pre_scale_delta=delta,
        source_trust_band=ReputationSourceTrustBand.UNMEDIATED,
        tick=tick,
        policy_version=REPUTATION_POLICY_VERSION,
        profile_id=profile_id,
        ordinal=ordinal,
    )


def test_modes_match_and_default_off() -> None:
    assert CognitionReputationMode.DISABLED.value == "disabled"
    assert CognitionReputationMode.DETERMINISTIC.value == "deterministic"
    assert ReputationMode.DISABLED.value == CognitionReputationMode.DISABLED.value
    assert (
        ReputationMode.DETERMINISTIC.value
        == CognitionReputationMode.DETERMINISTIC.value
    )
    policy = default_reputation_policy()
    assert policy.version == "reputation-formation.v1"
    assert policy.speech_rate == 0.5
    assert policy.remembered_scale == 0.5
    assert policy.reading_threshold == 0.4
    assert policy.max_profiles == 32
    assert policy.max_evidence == 64


def test_banned_names_are_not_fields() -> None:
    for model in _TYPES:
        names = {item.name for item in dataclasses.fields(model)}
        assert names.isdisjoint(_BANNED_FIELDS)


def test_ledger_construction_logs_owner_policy_and_count(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger=_LOGGER)
    owner = _agent("owner-a")
    target = _agent("target-a")
    ledger = ReputationLedger(owner_id=owner, profiles=(_profile(owner, target),))
    assert ledger.profile_for(target) is not None
    assert ledger.profile_for(_agent("missing")) is None
    matches = [
        record
        for record in caplog.records
        if record.name == _LOGGER and "reputation_ledger_constructed" in record.message
    ]
    assert matches
    message = matches[-1].getMessage()
    assert "owner_id=owner-a" in message
    assert "policy_version=reputation-formation.v1" in message
    assert "profile_count=1" in message
    assert "0.25" not in message


def test_dimension_heads_stay_independent() -> None:
    owner = _agent("owner-a")
    target = _agent("target-a")
    profile = _profile(
        owner,
        target,
        generosity=ReputationDimensionState(
            value=0.8,
            support_mass=0.8,
            contradiction_mass=0.0,
        ),
        harm=ReputationDimensionState(
            value=0.8,
            support_mass=0.8,
            contradiction_mass=0.0,
        ),
    )
    assert profile.dimension_state(ReputationDimension.GENEROSITY).value == 0.8
    assert profile.dimension_state(ReputationDimension.HARM).value == 0.8
    assert profile.dimension_state(ReputationDimension.COMPETENCE).value == 0.0
    evidence = _item(owner, target)
    stored = _profile(owner, target, evidence=(evidence,))
    assert stored.evidence[0].evidence_id == reputation_evidence_id(
        profile_id=stored.profile_id,
        ordinal=0,
        dimension=ReputationDimension.GENEROSITY,
        channel=ReputationChannel.DIRECT_OBSERVATION,
        lineage_ref="event-1",
    )
    assert empty_reputation_ledger(owner).profiles == ()


@pytest.mark.parametrize(
    ("builder", "code"),
    [
        (
            lambda: ReputationDimensionState(
                value=float("nan"),
                support_mass=0.0,
                contradiction_mass=0.0,
            ),
            "not_finite",
        ),
        (
            lambda: ReputationDimensionState(
                value=1.25,
                support_mass=0.0,
                contradiction_mass=0.0,
            ),
            "out_of_range",
        ),
        (
            lambda: ReputationEvidenceItem(
                owner_id=_agent("owner-a"),
                target_id=_agent("target-a"),
                dimension="reliability",  # type: ignore[arg-type]
                channel=ReputationChannel.COMMUNICATION,
                lineage_ref="event-1",
                source_id=_agent("owner-a"),
                pre_scale_delta=0.1,
                source_trust_band=ReputationSourceTrustBand.MID,
                tick=1,
                policy_version=REPUTATION_POLICY_VERSION,
                profile_id=reputation_profile_id(
                    _agent("owner-a"), _agent("target-a")
                ),
                ordinal=0,
            ),
            "unknown_dimension",
        ),
        (
            lambda: _item(_agent("same"), _agent("same")),
            "owner_is_target",
        ),
    ],
)
def test_constructors_reject_invalid_values(
    builder: object,
    code: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.ERROR, logger=_LOGGER)
    with pytest.raises(ValueError, match=code):
        builder()  # type: ignore[operator]
    assert "reputation_validation_failed" in caplog.text
    assert f"reason_code={code}" in caplog.text
    assert "1.25" not in caplog.text


def test_duplicate_targets_owner_mismatch_and_caps() -> None:
    owner = _agent("owner-a")
    other = _agent("owner-b")
    target = _agent("target-a")
    profile = _profile(owner, target)
    with pytest.raises(ValueError, match="duplicate_target"):
        ReputationLedger(owner_id=owner, profiles=(profile, profile))
    with pytest.raises(ValueError, match="owner_mismatch"):
        ReputationLedger(owner_id=other, profiles=(profile,))
    profiles = tuple(
        _profile(owner, _agent(f"target-{index}")) for index in range(33)
    )
    with pytest.raises(ValueError, match="cap_exceeded"):
        ReputationLedger(owner_id=owner, profiles=profiles)
    evidence = tuple(
        _item(
            owner,
            target,
            ordinal=index,
            lineage_ref=f"event-{index}",
        )
        for index in range(65)
    )
    with pytest.raises(ValueError, match="cap_exceeded"):
        _profile(owner, target, evidence=evidence)
    first = _item(owner, target, ordinal=0)
    second = _item(owner, target, ordinal=1)
    with pytest.raises(ValueError, match="duplicate_evidence"):
        _profile(owner, target, evidence=(first, second))
    foreign = _item(other, _agent("target-b"), ordinal=0)
    with pytest.raises(ValueError, match="owner_mismatch"):
        _profile(owner, target, evidence=(foreign,))


def _identity(
    owner: str, owner_entity: str, *bindings: tuple[str, str]
) -> OwnerSafeSocialIdentity:
    ordered = tuple(
        sorted(bindings, key=lambda item: item[1])
    )
    return OwnerSafeSocialIdentity(
        owner_id=_agent(owner),
        owner_entity_id=EntityId(owner_entity),
        counterparts=tuple(
            CounterpartBinding(agent_id=_agent(agent), entity_id=EntityId(entity))
            for agent, entity in ordered
        ),
    )


def _occurrence(
    kind: str,
    *,
    actor: str,
    event: str,
    success: bool | None = True,
    other: str | None = None,
    source_tick: int = 1,
) -> ObservedOccurrence:
    return ObservedOccurrence(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.OCCURRENCE,
            source_tick=source_tick,
            source_event_id=EventId(event),
        ),
        kind=kind,
        audience_role=ObservationAudienceRole.WITNESS,
        actor_id=EntityId(actor),
        other_entity_id=None if other is None else EntityId(other),
        success=success,
    )


def _observation(*occurrences: ObservedOccurrence, tick: int = 2) -> Observation:
    return Observation(
        observer_id=EntityId("body-owner"),
        world_id=WorldId("world-1"),
        revision=WorldRevision(1),
        tick=tick,
        occurrences=occurrences,
    )


def test_direct_observation_moves_named_dimensions_only(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger=_LOGGER)
    owner = _agent("owner-a")
    identity = _identity("owner-a", "body-owner", ("focal", "body-focal"))
    updated = apply_reputation_update(
        owner_id=owner,
        tick=2,
        observation=_observation(
            _occurrence("help", actor="body-focal", event="evt-help")
        ),
        social_identity=identity,
    )
    profile = updated.profile_for(_agent("focal"))
    assert profile is not None
    assert profile.generosity.value == 0.25
    assert profile.reliability.value == 0.1
    assert profile.harm.value == -0.05
    assert profile.competence.value == 0.0
    assert {item.channel.value for item in profile.evidence} == {"direct_observation"}
    assert {item.dimension.value for item in profile.evidence} == {
        "generosity",
        "reliability",
        "harm",
    }
    assert all(
        item.source_trust_band.value == "unmediated" for item in profile.evidence
    )
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "reputation_observation_applied" in messages
    assert "channel=direct_observation" in messages
    assert "dimension=generosity" in messages
    assert "sign=positive" in messages
    assert "sign=negative" in messages
    assert "reputation_head_updated" in messages
    assert "0.25" not in messages
    assert "trustworthy" not in messages


def test_unknown_kind_unresolved_actor_and_repeat_do_not_stack(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger=_LOGGER)
    owner = _agent("owner-a")
    identity = _identity("owner-a", "body-owner", ("focal", "body-focal"))
    once = apply_reputation_update(
        owner_id=owner,
        tick=2,
        observation=_observation(
            _occurrence("help", actor="body-focal", event="evt-help"),
            _occurrence("flee", actor="body-focal", event="evt-flee"),
            _occurrence("help", actor="body-stranger", event="evt-stranger"),
        ),
        social_identity=identity,
    )
    again = apply_reputation_update(
        owner_id=owner,
        tick=2,
        observation=_observation(
            _occurrence("help", actor="body-focal", event="evt-help")
        ),
        social_identity=identity,
        ledger=once,
    )
    profile = again.profile_for(_agent("focal"))
    assert profile is not None
    assert profile.generosity.value == 0.25
    assert len(profile.evidence) == 3
    assert again.profile_for(_agent("body-stranger")) is None
    reasons = [
        record.getMessage()
        for record in caplog.records
        if "reputation_evidence_dropped" in record.getMessage()
    ]
    assert any("reason=ignored_kind" in line for line in reasons)
    assert any("reason=unresolved_entity" in line for line in reasons)


def test_failed_help_is_ignored_and_attack_requires_success() -> None:
    owner = _agent("owner-a")
    identity = _identity("owner-a", "body-owner", ("focal", "body-focal"))
    missed = apply_reputation_update(
        owner_id=owner,
        tick=2,
        observation=_observation(
            _occurrence("help", actor="body-focal", event="evt-miss", success=False)
        ),
        social_identity=identity,
    )
    assert missed.profiles == ()
    struck = apply_reputation_update(
        owner_id=owner,
        tick=2,
        observation=_observation(
            _occurrence("attack", actor="body-focal", event="evt-hit", success=True)
        ),
        social_identity=identity,
    )
    profile = struck.profile_for(_agent("focal"))
    assert profile is not None
    assert profile.harm.value == 0.35
    assert profile.reliability.value == -0.1
    assert profile.generosity.value == -0.15
    assert profile.competence.value == 0.0


def test_observation_cap_keeps_older_evidence() -> None:
    owner = _agent("owner-a")
    bindings = tuple((f"target-{index}", f"body-{index:02d}") for index in range(33))
    identity = _identity("owner-a", "body-owner", *bindings)
    occurrences = tuple(
        _occurrence("give", actor=f"body-{index:02d}", event=f"evt-{index}")
        for index in range(33)
    )
    updated = apply_reputation_update(
        owner_id=owner,
        tick=2,
        observation=_observation(*occurrences),
        social_identity=identity,
    )
    assert len(updated.profiles) == 32
    assert updated.profile_for(_agent("target-0")) is not None
    assert updated.profile_for(_agent("target-32")) is None


def test_world_inputs_are_rejected() -> None:
    from world._state import WorldState
    from world.events import WorldEvent

    owner = _agent("owner-a")
    identity = _identity("owner-a", "body-owner", ("focal", "body-focal"))
    observation = _observation(
        _occurrence("help", actor="body-focal", event="evt-help")
    )
    with pytest.raises(TypeError, match="forbidden_input"):
        apply_reputation_update(
            owner_id=owner,
            tick=2,
            observation=observation,
            social_identity=identity,
            world_state=WorldState,  # type: ignore[arg-type]
        )
    with pytest.raises(TypeError, match="forbidden_input"):
        apply_reputation_update(
            owner_id=owner,
            tick=2,
            observation=WorldEvent,  # type: ignore[arg-type]
            social_identity=identity,
        )


def test_owner_mismatch_on_update_is_an_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.ERROR, logger=_LOGGER)
    with pytest.raises(ValueError, match="owner_mismatch"):
        apply_reputation_update(
            owner_id=_agent("owner-a"),
            tick=2,
            observation=_observation(),
            social_identity=_identity("owner-b", "body-b", ("focal", "body-focal")),
        )
    assert "reason_code=owner_mismatch" in caplog.text


def test_policy_rejects_thresholds_and_trust_band_is_closed() -> None:
    with pytest.raises(ValueError, match="unsupported_policy"):
        ReputationFormationPolicy(speech_rate=0.9)
    assert source_trust_band_for(1.0) is ReputationSourceTrustBand.HIGH
    assert source_trust_band_for(0.5) is ReputationSourceTrustBand.MID
    assert source_trust_band_for(0.2) is ReputationSourceTrustBand.LOW
    assert (
        source_trust_band_for(0.0, unmediated=True)
        is ReputationSourceTrustBand.UNMEDIATED
    )
    with pytest.raises(ValueError, match="not_finite"):
        source_trust_band_for(float("nan"))
