"""All-witness-destruction is provenance loss, not falsity or retirement."""

from __future__ import annotations

import pytest

from agents.cognition.cultural_narratives import (
    CULTURAL_NARRATIVE_POLICY_VERSION_V2,
    NarrativeContent,
    NarrativeCueSummary,
    NarrativeLedger,
    NarrativeOrigin,
    NarrativeRecordCue,
    NarrativeSourceLoss,
    NarrativeSourceLossReason,
    NarrativeSourceLossState,
    NarrativeStatus,
    NarrativeTransitionKind,
    NarrativeVariant,
    NarrativeWitness,
    NarrativeWitnessKind,
    apply_narrative_update,
    default_generational_narrative_policy,
    narrative_content_fingerprint,
    narrative_variant_id,
    require_owner_cultural_narratives,
)
from agents.models import AgentId
from tests.unit.test_cultural_narratives import _identity, _observation

_OWNER = AgentId("alice")


def _lost_variant() -> NarrativeVariant:
    content = NarrativeContent(concepts=("water", "gone"), text="tell_story")
    witness = NarrativeWitness(
        witness_agent_id=AgentId("ben"),
        kind=NarrativeWitnessKind.FIRST_HAND,
        hop_index=0,
        first_seen_tick=1,
        last_seen_tick=1,
        death_observed_tick=2,
    )
    return NarrativeVariant(
        variant_id=narrative_variant_id(
            _OWNER, narrative_content_fingerprint(content), 0, ""
        ),
        owner_id=_OWNER,
        content=content,
        content_fingerprint=narrative_content_fingerprint(content),
        origin=NarrativeOrigin.OBSERVED_EVENT,
        status=NarrativeStatus.ACTIVE,
        strength=0.5,
        repetition_count=1,
        first_tick=1,
        last_tick=2,
        source_witnesses=(witness,),
        first_hand=True,
        source_loss=NarrativeSourceLoss(
            state=NarrativeSourceLossState.LOST,
            reason=NarrativeSourceLossReason.ALL_FIRST_HAND_WITNESSES_DEAD,
            tick=2,
            known_witness_count=1,
            dead_witness_count=1,
            record_backed=False,
        ),
    )


def _ledger(variant: NarrativeVariant) -> NarrativeLedger:
    return NarrativeLedger(
        owner_id=_OWNER,
        policy_version=CULTURAL_NARRATIVE_POLICY_VERSION_V2,
        variants=(variant,),
    )


def test_lost_variant_stays_in_ledger_and_is_not_retired() -> None:
    variant = _lost_variant()
    ledger = apply_narrative_update(
        observation=_observation(tick=3),
        identity=_identity(),
        previous=_ledger(variant),
        policy=default_generational_narrative_policy(),
    )
    kept = ledger.variants[0]
    assert kept.variant_id == variant.variant_id
    assert kept.status is NarrativeStatus.ACTIVE
    assert kept.source_loss is not None
    assert kept.source_loss.state is NarrativeSourceLossState.LOST


def test_record_read_reactivates_lost_source() -> None:
    ledger = apply_narrative_update(
        observation=_observation(tick=3),
        identity=_identity(),
        previous=_ledger(_lost_variant()),
        cues=NarrativeCueSummary(
            records=(
                NarrativeRecordCue(
                    record_id="record-1",
                    observed_revision=1,
                    source_tick=2,
                    integrity="intact",
                    concepts=("water", "gone"),
                ),
            )
        ),
        policy=default_generational_narrative_policy(),
    )
    variant = ledger.variants[0]
    assert variant.source_loss is not None
    assert variant.source_loss.state is NarrativeSourceLossState.INTACT
    assert NarrativeTransitionKind.REACTIVATED in {
        transition.kind for transition in variant.transitions
    }


@pytest.mark.parametrize(
    "name",
    ["WorldEvent", "MetricDocument", "HistoricalMemoryHarvest"],
)
def test_ledger_rejects_world_and_analysis_boundaries(name: str) -> None:
    foreign = type(name, (), {})()
    with pytest.raises((TypeError, ValueError)):
        apply_narrative_update(
            observation=_observation(tick=2),
            identity=_identity(),
            previous=foreign,  # type: ignore[arg-type]
            policy=default_generational_narrative_policy(),
        )


def test_require_owner_rejects_foreign_ledger() -> None:
    with pytest.raises(ValueError, match="owner_id mismatch"):
        require_owner_cultural_narratives(
            _ledger(_lost_variant()),
            AgentId("ben"),
            field_name="cultural_narratives",
        )


def test_source_loss_alone_never_changes_status_or_strength_rule() -> None:
    variant = _lost_variant()
    ledger = apply_narrative_update(
        observation=_observation(tick=3),
        identity=_identity(),
        previous=_ledger(variant),
        policy=default_generational_narrative_policy(),
    )
    assert ledger.variants[0].strength == 0.45
    assert ledger.variants[0].status is NarrativeStatus.ACTIVE


def test_lost_variant_can_be_retold_to_a_new_carrier() -> None:
    from tests.unit.test_cultural_narratives import _communication
    from world.communications import (
        CommunicationRelation,
        CommunicationSourceBasis,
        origin_utterance,
        retell_utterance,
    )
    from world.identifiers import EntityId

    first = origin_utterance(
        text="tell_story",
        speaker_id=EntityId("body-ben"),
        communication_id="comm-lost-1",
        concepts=("water", "gone"),
        relations=(
            CommunicationRelation(
                subject="water", predicate="tell_story", object="gone"
            ),
        ),
        source_basis=CommunicationSourceBasis.UNREFERENCED,
    )
    retold = retell_utterance(
        prior=first,
        speaker_id=EntityId("body-cy"),
        communication_id="comm-lost-2",
        text="retell",
        concepts=("water", "gone"),
        relations=(
            CommunicationRelation(
                subject="water", predicate="retell", object="gone"
            ),
        ),
    )
    ledger = apply_narrative_update(
        observation=_observation(
            tick=3,
            communications=(
                _communication(
                    tick=3,
                    speaker="cy",
                    listener="alice",
                    utterance=retold,
                    event_id="evt-lost-retold",
                ),
            ),
        ),
        identity=_identity(),
        previous=_ledger(_lost_variant()),
        policy=default_generational_narrative_policy(),
    )
    retold_variant = ledger.variants[-1]
    assert "alice" in retold_variant.carrier_agent_ids
    assert any(
        transition.kind is NarrativeTransitionKind.RETOLD
        for transition in retold_variant.transitions
    )
