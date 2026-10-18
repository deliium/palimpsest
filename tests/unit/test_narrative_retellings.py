"""Declared retelling chains become owner-scoped testimony, never truth."""

from __future__ import annotations

from agents.cognition.cultural_narratives import (
    CULTURAL_NARRATIVE_POLICY_VERSION_V2,
    NarrativeLedger,
    NarrativeTransitionKind,
    NarrativeWitnessKind,
    apply_narrative_update,
    default_generational_narrative_policy,
)
from agents.models import AgentId
from tests.unit.test_cultural_narratives import _communication, _identity, _observation
from world.communications import (
    CommunicationRelation,
    CommunicationSourceBasis,
    origin_utterance,
    retell_utterance,
)
from world.identifiers import EntityId

_OWNER = AgentId("alice")


def _first_utterance():
    return origin_utterance(
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


def test_declared_chain_adds_source_and_reteller_witnesses() -> None:
    first = _first_utterance()
    retold = retell_utterance(
        prior=first,
        speaker_id=EntityId("body-cy"),
        communication_id="comm-story-2",
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
            tick=2,
            communications=(
                _communication(
                    tick=2,
                    speaker="cy",
                    listener="alice",
                    utterance=retold,
                    event_id="evt-retold-2",
                ),
            ),
        ),
        identity=_identity(),
        previous=NarrativeLedger(
            owner_id=_OWNER,
            policy_version=CULTURAL_NARRATIVE_POLICY_VERSION_V2,
        ),
        policy=default_generational_narrative_policy(),
    )
    variant = ledger.variants[0]
    kinds = {
        witness.witness_agent_id.value: witness.kind
        for witness in variant.source_witnesses
    }
    assert kinds == {
        "ben": NarrativeWitnessKind.DECLARED_SOURCE,
        "cy": NarrativeWitnessKind.DECLARED_RETELLER,
    }
    sources = {
        witness.witness_agent_id.value: witness.hop_index
        for witness in variant.source_witnesses
    }
    assert sources == {"ben": 0, "cy": 1}
    assert variant.declared_hop_count == 1
    assert variant.first_hand is False
    assert "alice" in variant.carrier_agent_ids
    assert NarrativeTransitionKind.RETOLD in {
        transition.kind for transition in variant.transitions
    }


def test_unknown_declared_entity_stays_a_reference() -> None:
    first = _first_utterance()
    retold = retell_utterance(
        prior=first,
        speaker_id=EntityId("body-unknown"),
        communication_id="comm-story-3",
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
            tick=2,
            communications=(
                _communication(
                    tick=2,
                    speaker="ben",
                    listener="alice",
                    utterance=retold,
                    event_id="evt-retold-3",
                ),
            ),
        ),
        identity=_identity(),
        previous=NarrativeLedger(
            owner_id=_OWNER,
            policy_version=CULTURAL_NARRATIVE_POLICY_VERSION_V2,
        ),
        policy=default_generational_narrative_policy(),
    )
    variant = ledger.variants[0]
    assert "body-unknown" in variant.declared_source_entity_ids
    assert all(
        witness.witness_agent_id.value != "body-unknown"
        for witness in variant.source_witnesses
    )
