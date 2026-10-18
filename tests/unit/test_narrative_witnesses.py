"""Witness death tracking and the owner-observed source-loss state."""

from __future__ import annotations

from agents.cognition.cultural_narratives import (
    CULTURAL_NARRATIVE_POLICY_VERSION_V2,
    NarrativeContent,
    NarrativeLedger,
    NarrativeOrigin,
    NarrativeRecordRef,
    NarrativeRecordRole,
    NarrativeSourceLossReason,
    NarrativeSourceLossState,
    NarrativeStatus,
    NarrativeVariant,
    NarrativeWitness,
    NarrativeWitnessKind,
    apply_narrative_update,
    default_generational_narrative_policy,
    narrative_content_fingerprint,
    narrative_variant_id,
)
from agents.models import AgentId
from tests.unit.test_cultural_narratives import _identity, _observation
from world.identifiers import EntityId, EventId
from world.observations import (
    ObservationAudienceRole,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedOccurrence,
)

_OWNER = AgentId("alice")


def _variant(**overrides: object) -> NarrativeVariant:
    content = NarrativeContent(concepts=("founding",), text="tell_story")
    values: dict[str, object] = {
        "variant_id": narrative_variant_id(
            _OWNER, narrative_content_fingerprint(content), 0, ""
        ),
        "owner_id": _OWNER,
        "content": content,
        "content_fingerprint": narrative_content_fingerprint(content),
        "origin": NarrativeOrigin.OBSERVED_EVENT,
        "status": NarrativeStatus.ACTIVE,
        "strength": 0.5,
        "first_tick": 1,
        "last_tick": 1,
    }
    values.update(overrides)
    return NarrativeVariant(**values)  # type: ignore[arg-type]


def _death_occurrence(*, tick: int, agent: str) -> ObservedOccurrence:
    return ObservedOccurrence(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.OCCURRENCE,
            source_tick=max(0, tick - 1),
            source_event_id=EventId(f"event-death-{agent}-{tick}"),
        ),
        kind="died",
        audience_role=ObservationAudienceRole.WITNESS,
        public_facts={},
        actor_id=EntityId(f"body-{agent}"),
    )


def _first_hand(agent: str, *, death: int | None = None) -> NarrativeWitness:
    return NarrativeWitness(
        witness_agent_id=AgentId(agent),
        kind=NarrativeWitnessKind.FIRST_HAND,
        hop_index=0,
        first_seen_tick=1,
        last_seen_tick=1,
        death_observed_tick=death,
    )


def _update(previous: NarrativeLedger, observation):
    return apply_narrative_update(
        observation=observation,
        identity=_identity(),
        previous=previous,
        policy=default_generational_narrative_policy(),
    )


def test_direct_observation_mints_first_hand_witness_and_theme() -> None:
    observation = _observation(tick=2, occurrences=(
        ObservedOccurrence(
            provenance=ObservationProvenance(
                source_kind=ObservationSourceKind.OCCURRENCE,
                source_tick=1,
                source_event_id=EventId("event-founding"),
            ),
            kind="agent_entered_world",
            audience_role=ObservationAudienceRole.WITNESS,
            public_facts={"founder": "alice"},
        ),
    ))
    ledger = _update(NarrativeLedger(
        owner_id=_OWNER, policy_version=CULTURAL_NARRATIVE_POLICY_VERSION_V2
    ), observation)
    variant = ledger.variants[0]
    assert variant.first_hand is True
    assert variant.source_witnesses[0].kind is NarrativeWitnessKind.FIRST_HAND
    assert variant.source_loss is not None
    assert variant.source_loss.state is NarrativeSourceLossState.INTACT
    assert variant.themes[0].value == "founders"
    assert variant.transitions[0].kind.value == "minted"


def test_partial_death_and_no_source_loss_side_effects() -> None:
    previous = NarrativeLedger(
        owner_id=_OWNER,
        policy_version=CULTURAL_NARRATIVE_POLICY_VERSION_V2,
        variants=(
            _variant(
                source_witnesses=(_first_hand("ben"), _first_hand("cy")),
                first_hand=True,
            ),
        ),
    )
    ledger = _update(
        previous,
        _observation(tick=2, occurrences=(_death_occurrence(tick=2, agent="ben"),)),
    )
    variant = ledger.variants[0]
    assert variant.source_loss is not None
    assert variant.source_loss.state is NarrativeSourceLossState.PARTIAL
    assert variant.source_loss.reason is (
        NarrativeSourceLossReason.SOME_WITNESSES_DEAD
    )
    assert variant.strength == 0.45
    assert variant.status is NarrativeStatus.ACTIVE


def test_all_first_hand_witnesses_dead_becomes_lost_not_retired() -> None:
    previous = NarrativeLedger(
        owner_id=_OWNER,
        policy_version=CULTURAL_NARRATIVE_POLICY_VERSION_V2,
        variants=(
            _variant(
                source_witnesses=(_first_hand("ben"),),
                first_hand=True,
            ),
        ),
    )
    ledger = _update(
        previous,
        _observation(tick=2, occurrences=(_death_occurrence(tick=2, agent="ben"),)),
    )
    variant = ledger.variants[0]
    assert variant.source_loss is not None
    assert variant.source_loss.state is NarrativeSourceLossState.LOST
    assert variant.source_loss.reason is (
        NarrativeSourceLossReason.ALL_FIRST_HAND_WITNESSES_DEAD
    )
    assert variant.status is NarrativeStatus.ACTIVE
    assert variant.strength == 0.45


def test_intact_record_keeps_lost_sources_intact() -> None:
    previous = NarrativeLedger(
        owner_id=_OWNER,
        policy_version=CULTURAL_NARRATIVE_POLICY_VERSION_V2,
        variants=(
            _variant(
                source_witnesses=(_first_hand("ben", death=1),),
                first_hand=True,
                record_refs=(
                    NarrativeRecordRef(
                        record_id="record-1",
                        role=NarrativeRecordRole.READ,
                        observed_revision=1,
                        tick=1,
                        integrity="intact",
                    ),
                ),
            ),
        ),
    )
    ledger = _update(previous, _observation(tick=2))
    variant = ledger.variants[0]
    assert variant.source_loss is not None
    assert variant.source_loss.state is NarrativeSourceLossState.INTACT
    assert variant.source_loss.record_backed is True


def test_no_evidence_leaves_unknown() -> None:
    previous = NarrativeLedger(
        owner_id=_OWNER,
        policy_version=CULTURAL_NARRATIVE_POLICY_VERSION_V2,
        variants=(_variant(),),
    )
    ledger = _update(previous, _observation(tick=2))
    variant = ledger.variants[0]
    assert variant.source_loss is not None
    assert variant.source_loss.state is NarrativeSourceLossState.UNKNOWN
    assert variant.source_loss.reason is NarrativeSourceLossReason.UNKNOWN


def test_missing_death_evidence_is_never_loss() -> None:
    previous = NarrativeLedger(
        owner_id=_OWNER,
        policy_version=CULTURAL_NARRATIVE_POLICY_VERSION_V2,
        variants=(
            _variant(
                source_witnesses=(_first_hand("ben"),),
                first_hand=True,
            ),
        ),
    )
    ledger = _update(previous, _observation(tick=2))
    variant = ledger.variants[0]
    assert variant.source_loss is not None
    assert variant.source_loss.state is NarrativeSourceLossState.INTACT
    assert variant.source_witnesses[0].death_observed_tick is None
