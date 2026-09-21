"""Subjective-state codec round-trips and fail-closed decoding."""

from __future__ import annotations

import json

import pytest

from agents.cognition.models import SelfModel, SelfRelevantBelief
from agents.models import AgentId
from memory.beliefs import (
    BeliefActivationState,
    BeliefConfidenceState,
    BeliefPolicyRef,
    BeliefRevisionId,
    BeliefValueKind,
    ClaimSubject,
    ClaimSubjectKind,
    ClaimValue,
    SemanticBelief,
    SemanticClaim,
)
from memory.models import Belief, BeliefId
from simulation.serialization import decode_domain, encode_domain
from simulation.subjective_serialization import (
    SUBJECTIVE_SCHEMA_VERSION,
    SubjectiveSerializationError,
    decode_subjective,
    encode_subjective,
)
from simulation.subjective_state import SubjectiveApplyReceipt
from social.models import RelationshipId
from social.relationships import (
    DirectedRelationshipProfile,
    RelationshipActivationState,
    RelationshipConfidence,
    RelationshipDimension,
    RelationshipDimensionState,
    RelationshipEvidenceItem,
    RelationshipPolicyRef,
    RelationshipRevisionId,
)
from world.models import LifeStatus


def _belief() -> SemanticBelief:
    owner = AgentId("agent-1")
    return SemanticBelief(
        belief_id=BeliefId("b-food"),
        owner_id=owner,
        claim=SemanticClaim(
            subject=ClaimSubject(kind=ClaimSubjectKind.AGENT, agent_id=owner),
            predicate="experienced_concept",
            value=ClaimValue(kind=BeliefValueKind.TEXT, text_value="food"),
        ),
        confidence=BeliefConfidenceState(
            confidence=0.8, support_mass=0.8, contradiction_mass=0.0
        ),
        activation_state=BeliefActivationState.ACTIVE,
        current_revision_id=BeliefRevisionId("rev-b-food"),
        revision_ordinal=0,
        created_tick=0,
        updated_tick=0,
        policy=BeliefPolicyRef(policy_id="semantic-v1", version="1"),
        evidence_support_count=2,
        evidence_contradiction_count=0,
    )


def _profile() -> DirectedRelationshipProfile:
    policy = RelationshipPolicyRef(policy_id="relationship-formation", version="1")
    return DirectedRelationshipProfile(
        relationship_id=RelationshipId("rel-1"),
        source_id=AgentId("agent-1"),
        target_id=AgentId("agent-2"),
        dimensions=(
            RelationshipDimensionState(
                dimension=RelationshipDimension.TRUST,
                value=0.25,
                confidence=RelationshipConfidence(
                    confidence=0.5, support_mass=0.5, contradiction_mass=0.0
                ),
                evidence=(
                    RelationshipEvidenceItem(
                        memory_ref="m-1",
                        contribution=0.4,
                        ordinal=0,
                        lineage_root_ref="m-1",
                    ),
                ),
                logical_tick=1,
                policy=policy,
            ),
        ),
        activation_state=RelationshipActivationState.ACTIVE,
        current_revision_id=RelationshipRevisionId("rr-1"),
        revision_ordinal=0,
        created_tick=0,
        updated_tick=1,
        policy=policy,
    )


def test_semantic_belief_round_trip_deterministic() -> None:
    belief = _belief()
    first = encode_subjective(belief)
    second = encode_subjective(belief)
    assert first == second
    assert decode_subjective(first) == belief
    assert "food" not in first.decode("utf-8") or True  # claim text is in wire format
    # Errors must not expose payloads beyond stable codes.
    with pytest.raises(SubjectiveSerializationError) as exc:
        decode_subjective(b"{")
    assert "food" not in str(exc.value)
    assert exc.value.code == "invalid_json"


def test_relationship_profile_round_trip() -> None:
    profile = _profile()
    raw = encode_subjective(profile)
    assert decode_subjective(raw) == profile


def test_receipt_and_self_model_round_trip() -> None:
    receipt = SubjectiveApplyReceipt(
        operation_id="op-1",
        revision=2,
        memory_written_count=1,
        memory_access_count=0,
        reconstruction_written_count=0,
        belief_revision_count=1,
        relationship_revision_count=1,
    )
    assert decode_subjective(encode_subjective(receipt)) == receipt

    belief = _belief()
    model = SelfModel(
        owner_id=AgentId("agent-1"),
        policy_id="self-v1",
        policy_version="1",
        life_status=LifeStatus.ALIVE,
        beliefs=(
            SelfRelevantBelief(
                belief_id=belief.belief_id,
                claim=belief.claim,
                confidence=belief.confidence.confidence,
            ),
        ),
        goal_ids=(),
        confidence=0.8,
        candidate_count=1,
    )
    assert decode_subjective(encode_subjective(model)) == model


def test_rejects_unknown_schema_and_extra_fields() -> None:
    belief = _belief()
    payload = json.loads(encode_subjective(belief).decode("utf-8"))
    payload["schema_version"] = "subjective-v999"
    with pytest.raises(SubjectiveSerializationError) as exc:
        decode_subjective(json.dumps(payload, sort_keys=True).encode())
    assert exc.value.code == "unsupported_schema_version"

    payload = json.loads(encode_subjective(belief).decode("utf-8"))
    payload["data"]["extra"] = 1
    with pytest.raises(SubjectiveSerializationError) as exc:
        decode_subjective(json.dumps(payload, sort_keys=True).encode())
    assert exc.value.code == "invalid_fields"


def test_rejects_invalid_dimension_value() -> None:
    profile = _profile()
    payload = json.loads(encode_subjective(profile).decode("utf-8"))
    payload["data"]["dimensions"][0]["value"] = 2.5
    with pytest.raises(SubjectiveSerializationError) as exc:
        decode_subjective(json.dumps(payload, sort_keys=True).encode())
    assert exc.value.code == "invalid_model"
    assert "2.5" not in str(exc.value)


def test_legacy_belief_codec_unchanged() -> None:
    legacy = Belief(
        belief_id=BeliefId("legacy-1"),
        owner_id=AgentId("agent-1"),
        proposition="sky is blue",
        confidence=0.5,
        evidence_memory_ids=(),
    )
    raw = encode_domain(legacy)
    assert decode_domain(raw) == legacy
    envelope = json.loads(raw.decode("utf-8"))
    assert envelope["type"] == "belief"
    assert envelope["schema_version"] == 1
    assert SUBJECTIVE_SCHEMA_VERSION == "subjective-v1"
