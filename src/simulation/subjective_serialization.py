"""Canonical codecs for subjective agent state (beliefs, relationships, self).

Separate from authoritative world journals/checkpoints. Legacy schema-v1
``belief`` / ``relationship`` codecs in ``simulation.serialization`` remain
unchanged. These codecs never log and never put claim/value/dimension text into
exception messages.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from typing import Any, Final

from agents.cognition.models import SelfModel, SelfRelevantBelief
from agents.models import AgentId, GoalId
from memory.beliefs import (
    AppliedTestimonyFactors,
    BeliefActivationState,
    BeliefConfidenceState,
    BeliefPolicyRef,
    BeliefRevisionId,
    BeliefValueKind,
    ClaimSubject,
    ClaimSubjectKind,
    ClaimValue,
    CommunicatedEvidenceDecision,
    SemanticBelief,
    SemanticClaim,
)
from memory.models import BeliefId, CommunicatedTransmissionMeta, EntityId
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

__all__ = [
    "SUBJECTIVE_SCHEMA_VERSION",
    "SubjectiveSerializationError",
    "decode_subjective",
    "encode_subjective",
]

SUBJECTIVE_SCHEMA_VERSION: Final[str] = "subjective-v1"
_INT64_MIN: Final[int] = -(2**63)
_INT64_MAX: Final[int] = 2**63 - 1


class SubjectiveSerializationError(ValueError):
    """Fail-closed codec error with stable metadata only (no payloads)."""

    def __init__(self, code: str, path: str) -> None:
        self.code = code
        self.path = path
        super().__init__(f"{code} at {path}")


def encode_subjective(value: object) -> bytes:
    """Encode a supported subjective value to canonical UTF-8 bytes."""
    tag, data = _encode_top(value, path="$")
    envelope = {
        "data": data,
        "schema_version": SUBJECTIVE_SCHEMA_VERSION,
        "type": tag,
    }
    text = json.dumps(
        envelope,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return text.encode("utf-8")


def decode_subjective(data: bytes) -> object:
    """Decode canonical subjective bytes into an exact typed value."""
    if not isinstance(data, (bytes, bytearray)):
        raise SubjectiveSerializationError("invalid_bytes", "$")
    if isinstance(data, bytearray):
        data = bytes(data)
    if data.startswith(b"\xef\xbb\xbf"):
        raise SubjectiveSerializationError("bom_forbidden", "$")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SubjectiveSerializationError("invalid_utf8", "$") from exc
    decoder = json.JSONDecoder(object_pairs_hook=_reject_duplicate_keys)
    try:
        payload, end = decoder.raw_decode(text)
    except json.JSONDecodeError as exc:
        raise SubjectiveSerializationError("invalid_json", "$") from exc
    if end != len(text):
        raise SubjectiveSerializationError("trailing_data", "$")
    if not isinstance(payload, dict):
        raise SubjectiveSerializationError("invalid_envelope", "$")
    if set(payload) != {"schema_version", "type", "data"}:
        raise SubjectiveSerializationError("invalid_envelope", "$")
    if payload["schema_version"] != SUBJECTIVE_SCHEMA_VERSION:
        raise SubjectiveSerializationError(
            "unsupported_schema_version", "$.schema_version"
        )
    type_tag = payload["type"]
    if not isinstance(type_tag, str):
        raise SubjectiveSerializationError("invalid_type", "$.type")
    data_obj = payload["data"]
    if not isinstance(data_obj, dict):
        raise SubjectiveSerializationError("invalid_data", "$.data")
    return _decode_top(type_tag, data_obj, path="$.data")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SubjectiveSerializationError("duplicate_key", "$")
        result[key] = value
    return result


def _require_keys(
    data: Mapping[str, Any],
    keys: set[str],
    *,
    path: str,
    optional: set[str] | None = None,
) -> None:
    allowed = keys if optional is None else keys | optional
    present = set(data)
    if not keys.issubset(present) or not present.issubset(allowed):
        raise SubjectiveSerializationError("invalid_fields", path)


def _str_field(data: Mapping[str, Any], key: str, *, path: str) -> str:
    value = data[key]
    if not isinstance(value, str):
        raise SubjectiveSerializationError("invalid_string", f"{path}.{key}")
    return value


def _int_field(data: Mapping[str, Any], key: str, *, path: str) -> int:
    value = data[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise SubjectiveSerializationError("invalid_int", f"{path}.{key}")
    if value < _INT64_MIN or value > _INT64_MAX:
        raise SubjectiveSerializationError("int_out_of_range", f"{path}.{key}")
    return value


def _float_field(data: Mapping[str, Any], key: str, *, path: str) -> float:
    value = data[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SubjectiveSerializationError("invalid_float", f"{path}.{key}")
    number = float(value)
    if not math.isfinite(number):
        raise SubjectiveSerializationError("non_finite_float", f"{path}.{key}")
    return 0.0 if number == 0.0 else number


def _bool_field(data: Mapping[str, Any], key: str, *, path: str) -> bool:
    value = data[key]
    if type(value) is not bool:
        raise SubjectiveSerializationError("invalid_bool", f"{path}.{key}")
    return value


def _encode_top(value: object, *, path: str) -> tuple[str, dict[str, Any]]:
    if type(value) is SemanticBelief:
        return "semantic_belief", _encode_semantic_belief(value)
    if type(value) is DirectedRelationshipProfile:
        return "directed_relationship_profile", _encode_relationship_profile(value)
    if type(value) is SubjectiveApplyReceipt:
        return "subjective_apply_receipt", _encode_receipt(value)
    if type(value) is SelfModel:
        return "self_model", _encode_self_model(value)
    if type(value) is AppliedTestimonyFactors:
        return "applied_testimony_factors", _encode_applied_factors(value)
    if type(value) is CommunicatedTransmissionMeta:
        return "communicated_transmission_meta", _encode_transmission_meta(value)
    raise SubjectiveSerializationError("unsupported_type", path)


def _decode_top(tag: str, data: dict[str, Any], *, path: str) -> object:
    if tag == "semantic_belief":
        return _decode_semantic_belief(data, path=path)
    if tag == "directed_relationship_profile":
        return _decode_relationship_profile(data, path=path)
    if tag == "subjective_apply_receipt":
        return _decode_receipt(data, path=path)
    if tag == "self_model":
        return _decode_self_model(data, path=path)
    if tag == "applied_testimony_factors":
        return _decode_applied_factors(data, path=path)
    if tag == "communicated_transmission_meta":
        return _decode_transmission_meta(data, path=path)
    raise SubjectiveSerializationError("unsupported_type", path)


def _encode_applied_factors(value: AppliedTestimonyFactors) -> dict[str, Any]:
    return {
        "adjusted_contribution": value.adjusted_contribution,
        "base_contribution": value.base_contribution,
        "confidence_delta": value.confidence_delta,
        "context_relevance": value.context_relevance,
        "decision": value.decision.value,
        "hop_attenuation": value.hop_attenuation,
        "hop_count": value.hop_count,
        "policy_version": value.policy_version,
        "receiver_confidence": value.receiver_confidence,
        "sender_confidence": value.sender_confidence,
        "trust": value.trust,
        "trust_confidence": value.trust_confidence,
    }


def _decode_applied_factors(
    data: dict[str, Any], *, path: str
) -> AppliedTestimonyFactors:
    _require_keys(
        data,
        {
            "adjusted_contribution",
            "base_contribution",
            "confidence_delta",
            "context_relevance",
            "decision",
            "hop_attenuation",
            "hop_count",
            "policy_version",
            "receiver_confidence",
            "sender_confidence",
            "trust",
            "trust_confidence",
        },
        path=path,
    )
    try:
        decision = CommunicatedEvidenceDecision(_str_field(data, "decision", path=path))
        return AppliedTestimonyFactors(
            decision=decision,
            hop_count=_int_field(data, "hop_count", path=path),
            trust=_float_field(data, "trust", path=path),
            trust_confidence=_float_field(data, "trust_confidence", path=path),
            sender_confidence=_float_field(data, "sender_confidence", path=path),
            receiver_confidence=_float_field(data, "receiver_confidence", path=path),
            context_relevance=_float_field(data, "context_relevance", path=path),
            hop_attenuation=_float_field(data, "hop_attenuation", path=path),
            base_contribution=_float_field(data, "base_contribution", path=path),
            adjusted_contribution=_float_field(
                data, "adjusted_contribution", path=path
            ),
            confidence_delta=_float_field(data, "confidence_delta", path=path),
            policy_version=_str_field(data, "policy_version", path=path),
        )
    except SubjectiveSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise SubjectiveSerializationError("invalid_model", path) from exc


def _encode_transmission_meta(value: CommunicatedTransmissionMeta) -> dict[str, Any]:
    return {
        "action_kind": value.action_kind,
        "communication_id": value.communication_id,
        "content_fingerprint": value.content_fingerprint,
        "hop_count": value.hop_count,
        "parent_communication_id": value.parent_communication_id,
        "policy_version": value.policy_version,
        "receiver_confidence": value.receiver_confidence,
        "sender_confidence": value.sender_confidence,
        "source_agent_chain": [item.value for item in value.source_agent_chain],
        "transmission_root_id": value.transmission_root_id,
    }


def _decode_transmission_meta(
    data: dict[str, Any], *, path: str
) -> CommunicatedTransmissionMeta:
    _require_keys(
        data,
        {
            "action_kind",
            "communication_id",
            "content_fingerprint",
            "hop_count",
            "policy_version",
            "receiver_confidence",
            "sender_confidence",
            "source_agent_chain",
            "transmission_root_id",
        },
        path=path,
        optional={"parent_communication_id"},
    )
    chain_raw = data["source_agent_chain"]
    if not isinstance(chain_raw, list):
        raise SubjectiveSerializationError(
            "invalid_array", f"{path}.source_agent_chain"
        )
    parent = data.get("parent_communication_id")
    if parent is not None and not isinstance(parent, str):
        raise SubjectiveSerializationError(
            "invalid_string", f"{path}.parent_communication_id"
        )
    try:
        return CommunicatedTransmissionMeta(
            communication_id=_str_field(data, "communication_id", path=path),
            action_kind=_str_field(data, "action_kind", path=path),
            hop_count=_int_field(data, "hop_count", path=path),
            sender_confidence=_float_field(data, "sender_confidence", path=path),
            receiver_confidence=_float_field(data, "receiver_confidence", path=path),
            content_fingerprint=_str_field(data, "content_fingerprint", path=path),
            parent_communication_id=parent,
            source_agent_chain=tuple(EntityId(str(item)) for item in chain_raw),
            transmission_root_id=_str_field(data, "transmission_root_id", path=path),
            policy_version=_str_field(data, "policy_version", path=path),
        )
    except SubjectiveSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise SubjectiveSerializationError("invalid_model", path) from exc


def _encode_claim_subject(subject: ClaimSubject) -> dict[str, Any]:
    payload: dict[str, Any] = {"kind": subject.kind.value}
    if subject.kind is ClaimSubjectKind.AGENT:
        assert subject.agent_id is not None
        payload["agent_id"] = subject.agent_id.value
    elif subject.kind is ClaimSubjectKind.ENTITY:
        assert subject.entity_id is not None
        payload["entity_id"] = subject.entity_id.value
    else:
        assert subject.concept is not None
        payload["concept"] = subject.concept
    return payload


def _decode_claim_subject(raw: object, *, path: str) -> ClaimSubject:
    if not isinstance(raw, dict):
        raise SubjectiveSerializationError("invalid_object", path)
    kind_raw = raw.get("kind")
    if not isinstance(kind_raw, str):
        raise SubjectiveSerializationError("invalid_string", f"{path}.kind")
    try:
        kind = ClaimSubjectKind(kind_raw)
    except ValueError as exc:
        raise SubjectiveSerializationError("invalid_enum", f"{path}.kind") from exc
    if kind is ClaimSubjectKind.AGENT:
        _require_keys(raw, {"kind", "agent_id"}, path=path)
        return ClaimSubject(
            kind=kind, agent_id=AgentId(_str_field(raw, "agent_id", path=path))
        )
    if kind is ClaimSubjectKind.ENTITY:
        _require_keys(raw, {"kind", "entity_id"}, path=path)
        return ClaimSubject(
            kind=kind, entity_id=EntityId(_str_field(raw, "entity_id", path=path))
        )
    _require_keys(raw, {"kind", "concept"}, path=path)
    return ClaimSubject(kind=kind, concept=_str_field(raw, "concept", path=path))


def _encode_claim_value(value: ClaimValue) -> dict[str, Any]:
    payload: dict[str, Any] = {"kind": value.kind.value}
    if value.kind is BeliefValueKind.BOOL:
        payload["bool_value"] = value.bool_value
    elif value.kind is BeliefValueKind.NUMBER:
        payload["number_value"] = value.number_value
    elif value.kind is BeliefValueKind.TEXT:
        payload["text_value"] = value.text_value
    elif value.kind is BeliefValueKind.AGENT:
        assert value.agent_id is not None
        payload["agent_id"] = value.agent_id.value
    else:
        assert value.entity_id is not None
        payload["entity_id"] = value.entity_id.value
    return payload


def _decode_claim_value(raw: object, *, path: str) -> ClaimValue:
    if not isinstance(raw, dict):
        raise SubjectiveSerializationError("invalid_object", path)
    kind_raw = raw.get("kind")
    if not isinstance(kind_raw, str):
        raise SubjectiveSerializationError("invalid_string", f"{path}.kind")
    try:
        kind = BeliefValueKind(kind_raw)
    except ValueError as exc:
        raise SubjectiveSerializationError("invalid_enum", f"{path}.kind") from exc
    if kind is BeliefValueKind.BOOL:
        _require_keys(raw, {"kind", "bool_value"}, path=path)
        return ClaimValue(
            kind=kind,
            bool_value=_bool_field(raw, "bool_value", path=path),
        )
    if kind is BeliefValueKind.NUMBER:
        _require_keys(raw, {"kind", "number_value"}, path=path)
        return ClaimValue(
            kind=kind, number_value=_float_field(raw, "number_value", path=path)
        )
    if kind is BeliefValueKind.TEXT:
        _require_keys(raw, {"kind", "text_value"}, path=path)
        return ClaimValue(
            kind=kind,
            text_value=_str_field(raw, "text_value", path=path),
        )
    if kind is BeliefValueKind.AGENT:
        _require_keys(raw, {"kind", "agent_id"}, path=path)
        return ClaimValue(
            kind=kind, agent_id=AgentId(_str_field(raw, "agent_id", path=path))
        )
    _require_keys(raw, {"kind", "entity_id"}, path=path)
    return ClaimValue(
        kind=kind, entity_id=EntityId(_str_field(raw, "entity_id", path=path))
    )


def _encode_claim(claim: SemanticClaim) -> dict[str, Any]:
    return {
        "predicate": claim.predicate,
        "subject": _encode_claim_subject(claim.subject),
        "value": _encode_claim_value(claim.value),
    }


def _decode_claim(raw: object, *, path: str) -> SemanticClaim:
    if not isinstance(raw, dict):
        raise SubjectiveSerializationError("invalid_object", path)
    _require_keys(raw, {"subject", "predicate", "value"}, path=path)
    try:
        return SemanticClaim(
            subject=_decode_claim_subject(raw["subject"], path=f"{path}.subject"),
            predicate=_str_field(raw, "predicate", path=path),
            value=_decode_claim_value(raw["value"], path=f"{path}.value"),
        )
    except SubjectiveSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise SubjectiveSerializationError("invalid_model", path) from exc


def _encode_confidence(state: BeliefConfidenceState) -> dict[str, Any]:
    return {
        "confidence": state.confidence,
        "contradiction_mass": state.contradiction_mass,
        "support_mass": state.support_mass,
    }


def _decode_confidence(raw: object, *, path: str) -> BeliefConfidenceState:
    if not isinstance(raw, dict):
        raise SubjectiveSerializationError("invalid_object", path)
    _require_keys(raw, {"confidence", "support_mass", "contradiction_mass"}, path=path)
    try:
        return BeliefConfidenceState(
            confidence=_float_field(raw, "confidence", path=path),
            support_mass=_float_field(raw, "support_mass", path=path),
            contradiction_mass=_float_field(raw, "contradiction_mass", path=path),
        )
    except (TypeError, ValueError) as exc:
        raise SubjectiveSerializationError("invalid_model", path) from exc


def _encode_policy(policy: BeliefPolicyRef) -> dict[str, Any]:
    return {"policy_id": policy.policy_id, "version": policy.version}


def _decode_belief_policy(raw: object, *, path: str) -> BeliefPolicyRef:
    if not isinstance(raw, dict):
        raise SubjectiveSerializationError("invalid_object", path)
    _require_keys(raw, {"policy_id", "version"}, path=path)
    try:
        return BeliefPolicyRef(
            policy_id=_str_field(raw, "policy_id", path=path),
            version=_str_field(raw, "version", path=path),
        )
    except (TypeError, ValueError) as exc:
        raise SubjectiveSerializationError("invalid_model", path) from exc


def _encode_semantic_belief(value: SemanticBelief) -> dict[str, Any]:
    return {
        "activation_state": value.activation_state.value,
        "belief_id": value.belief_id.value,
        "claim": _encode_claim(value.claim),
        "confidence": _encode_confidence(value.confidence),
        "created_tick": value.created_tick,
        "current_revision_id": value.current_revision_id.value,
        "evidence_contradiction_count": value.evidence_contradiction_count,
        "evidence_support_count": value.evidence_support_count,
        "owner_id": value.owner_id.value,
        "policy": _encode_policy(value.policy),
        "revision_ordinal": value.revision_ordinal,
        "updated_tick": value.updated_tick,
    }


def _decode_semantic_belief(data: dict[str, Any], *, path: str) -> SemanticBelief:
    _require_keys(
        data,
        {
            "activation_state",
            "belief_id",
            "claim",
            "confidence",
            "created_tick",
            "current_revision_id",
            "evidence_contradiction_count",
            "evidence_support_count",
            "owner_id",
            "policy",
            "revision_ordinal",
            "updated_tick",
        },
        path=path,
    )
    try:
        activation = BeliefActivationState(
            _str_field(data, "activation_state", path=path)
        )
        return SemanticBelief(
            belief_id=BeliefId(_str_field(data, "belief_id", path=path)),
            owner_id=AgentId(_str_field(data, "owner_id", path=path)),
            claim=_decode_claim(data["claim"], path=f"{path}.claim"),
            confidence=_decode_confidence(
                data["confidence"], path=f"{path}.confidence"
            ),
            activation_state=activation,
            current_revision_id=BeliefRevisionId(
                _str_field(data, "current_revision_id", path=path)
            ),
            revision_ordinal=_int_field(data, "revision_ordinal", path=path),
            created_tick=_int_field(data, "created_tick", path=path),
            updated_tick=_int_field(data, "updated_tick", path=path),
            policy=_decode_belief_policy(data["policy"], path=f"{path}.policy"),
            evidence_support_count=_int_field(
                data, "evidence_support_count", path=path
            ),
            evidence_contradiction_count=_int_field(
                data, "evidence_contradiction_count", path=path
            ),
        )
    except SubjectiveSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise SubjectiveSerializationError("invalid_model", path) from exc


def _encode_rel_policy(policy: RelationshipPolicyRef) -> dict[str, Any]:
    return {"policy_id": policy.policy_id, "version": policy.version}


def _decode_rel_policy(raw: object, *, path: str) -> RelationshipPolicyRef:
    if not isinstance(raw, dict):
        raise SubjectiveSerializationError("invalid_object", path)
    _require_keys(raw, {"policy_id", "version"}, path=path)
    try:
        return RelationshipPolicyRef(
            policy_id=_str_field(raw, "policy_id", path=path),
            version=_str_field(raw, "version", path=path),
        )
    except (TypeError, ValueError) as exc:
        raise SubjectiveSerializationError("invalid_model", path) from exc


def _encode_rel_confidence(state: RelationshipConfidence) -> dict[str, Any]:
    return {
        "confidence": state.confidence,
        "contradiction_mass": state.contradiction_mass,
        "support_mass": state.support_mass,
    }


def _decode_rel_confidence(raw: object, *, path: str) -> RelationshipConfidence:
    if not isinstance(raw, dict):
        raise SubjectiveSerializationError("invalid_object", path)
    _require_keys(raw, {"confidence", "support_mass", "contradiction_mass"}, path=path)
    try:
        return RelationshipConfidence(
            confidence=_float_field(raw, "confidence", path=path),
            support_mass=_float_field(raw, "support_mass", path=path),
            contradiction_mass=_float_field(raw, "contradiction_mass", path=path),
        )
    except (TypeError, ValueError) as exc:
        raise SubjectiveSerializationError("invalid_model", path) from exc


def _encode_rel_evidence(item: RelationshipEvidenceItem) -> dict[str, Any]:
    return {
        "contribution": item.contribution,
        "lineage_root_ref": item.lineage_root_ref,
        "memory_ref": item.memory_ref,
        "ordinal": item.ordinal,
    }


def _decode_rel_evidence(raw: object, *, path: str) -> RelationshipEvidenceItem:
    if not isinstance(raw, dict):
        raise SubjectiveSerializationError("invalid_object", path)
    _require_keys(
        raw,
        {"memory_ref", "contribution", "ordinal", "lineage_root_ref"},
        path=path,
    )
    try:
        return RelationshipEvidenceItem(
            memory_ref=_str_field(raw, "memory_ref", path=path),
            contribution=_float_field(raw, "contribution", path=path),
            ordinal=_int_field(raw, "ordinal", path=path),
            lineage_root_ref=_str_field(raw, "lineage_root_ref", path=path),
        )
    except (TypeError, ValueError) as exc:
        raise SubjectiveSerializationError("invalid_model", path) from exc


def _encode_dimension(state: RelationshipDimensionState) -> dict[str, Any]:
    return {
        "confidence": _encode_rel_confidence(state.confidence),
        "dimension": state.dimension.value,
        "evidence": [_encode_rel_evidence(item) for item in state.evidence],
        "logical_tick": state.logical_tick,
        "policy": _encode_rel_policy(state.policy),
        "value": state.value,
    }


def _decode_dimension(raw: object, *, path: str) -> RelationshipDimensionState:
    if not isinstance(raw, dict):
        raise SubjectiveSerializationError("invalid_object", path)
    _require_keys(
        raw,
        {
            "dimension",
            "value",
            "confidence",
            "evidence",
            "logical_tick",
            "policy",
        },
        path=path,
    )
    evidence_raw = raw["evidence"]
    if not isinstance(evidence_raw, list):
        raise SubjectiveSerializationError("invalid_array", f"{path}.evidence")
    try:
        dimension = RelationshipDimension(_str_field(raw, "dimension", path=path))
        evidence = tuple(
            _decode_rel_evidence(item, path=f"{path}.evidence[{index}]")
            for index, item in enumerate(evidence_raw)
        )
        return RelationshipDimensionState(
            dimension=dimension,
            value=_float_field(raw, "value", path=path),
            confidence=_decode_rel_confidence(
                raw["confidence"], path=f"{path}.confidence"
            ),
            evidence=evidence,
            logical_tick=_int_field(raw, "logical_tick", path=path),
            policy=_decode_rel_policy(raw["policy"], path=f"{path}.policy"),
        )
    except SubjectiveSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise SubjectiveSerializationError("invalid_model", path) from exc


def _encode_relationship_profile(
    value: DirectedRelationshipProfile,
) -> dict[str, Any]:
    return {
        "activation_state": value.activation_state.value,
        "created_tick": value.created_tick,
        "current_revision_id": value.current_revision_id.value,
        "dimensions": [_encode_dimension(item) for item in value.dimensions],
        "policy": _encode_rel_policy(value.policy),
        "relationship_id": value.relationship_id.value,
        "revision_ordinal": value.revision_ordinal,
        "source_id": value.source_id.value,
        "target_id": value.target_id.value,
        "updated_tick": value.updated_tick,
    }


def _decode_relationship_profile(
    data: dict[str, Any], *, path: str
) -> DirectedRelationshipProfile:
    _require_keys(
        data,
        {
            "activation_state",
            "created_tick",
            "current_revision_id",
            "dimensions",
            "policy",
            "relationship_id",
            "revision_ordinal",
            "source_id",
            "target_id",
            "updated_tick",
        },
        path=path,
    )
    dims_raw = data["dimensions"]
    if not isinstance(dims_raw, list):
        raise SubjectiveSerializationError("invalid_array", f"{path}.dimensions")
    try:
        dimensions = tuple(
            _decode_dimension(item, path=f"{path}.dimensions[{index}]")
            for index, item in enumerate(dims_raw)
        )
        return DirectedRelationshipProfile(
            relationship_id=RelationshipId(
                _str_field(data, "relationship_id", path=path)
            ),
            source_id=AgentId(_str_field(data, "source_id", path=path)),
            target_id=AgentId(_str_field(data, "target_id", path=path)),
            dimensions=dimensions,
            activation_state=RelationshipActivationState(
                _str_field(data, "activation_state", path=path)
            ),
            current_revision_id=RelationshipRevisionId(
                _str_field(data, "current_revision_id", path=path)
            ),
            revision_ordinal=_int_field(data, "revision_ordinal", path=path),
            created_tick=_int_field(data, "created_tick", path=path),
            updated_tick=_int_field(data, "updated_tick", path=path),
            policy=_decode_rel_policy(data["policy"], path=f"{path}.policy"),
        )
    except SubjectiveSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise SubjectiveSerializationError("invalid_model", path) from exc


def _encode_receipt(value: SubjectiveApplyReceipt) -> dict[str, Any]:
    return {
        "belief_activated_count": value.belief_activated_count,
        "belief_retired_count": value.belief_retired_count,
        "belief_revision_count": value.belief_revision_count,
        "idempotent": value.idempotent,
        "memory_access_count": value.memory_access_count,
        "memory_written_count": value.memory_written_count,
        "operation_id": value.operation_id,
        "reconstruction_written_count": value.reconstruction_written_count,
        "relationship_revision_count": value.relationship_revision_count,
        "revision": value.revision,
    }


def _decode_receipt(data: dict[str, Any], *, path: str) -> SubjectiveApplyReceipt:
    _require_keys(
        data,
        {
            "belief_activated_count",
            "belief_retired_count",
            "belief_revision_count",
            "idempotent",
            "memory_access_count",
            "memory_written_count",
            "operation_id",
            "reconstruction_written_count",
            "relationship_revision_count",
            "revision",
        },
        path=path,
    )
    try:
        return SubjectiveApplyReceipt(
            operation_id=_str_field(data, "operation_id", path=path),
            revision=_int_field(data, "revision", path=path),
            memory_written_count=_int_field(data, "memory_written_count", path=path),
            memory_access_count=_int_field(data, "memory_access_count", path=path),
            reconstruction_written_count=_int_field(
                data, "reconstruction_written_count", path=path
            ),
            belief_revision_count=_int_field(data, "belief_revision_count", path=path),
            relationship_revision_count=_int_field(
                data, "relationship_revision_count", path=path
            ),
            belief_activated_count=_int_field(
                data, "belief_activated_count", path=path
            ),
            belief_retired_count=_int_field(data, "belief_retired_count", path=path),
            idempotent=_bool_field(data, "idempotent", path=path),
        )
    except SubjectiveSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise SubjectiveSerializationError("invalid_model", path) from exc


def _encode_self_relevant(item: SelfRelevantBelief) -> dict[str, Any]:
    return {
        "belief_id": item.belief_id.value,
        "claim": _encode_claim(item.claim),
        "confidence": item.confidence,
    }


def _decode_self_relevant(raw: object, *, path: str) -> SelfRelevantBelief:
    if not isinstance(raw, dict):
        raise SubjectiveSerializationError("invalid_object", path)
    _require_keys(raw, {"belief_id", "claim", "confidence"}, path=path)
    try:
        return SelfRelevantBelief(
            belief_id=BeliefId(_str_field(raw, "belief_id", path=path)),
            claim=_decode_claim(raw["claim"], path=f"{path}.claim"),
            confidence=_float_field(raw, "confidence", path=path),
        )
    except SubjectiveSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise SubjectiveSerializationError("invalid_model", path) from exc


def _encode_self_model(value: SelfModel) -> dict[str, Any]:
    return {
        "beliefs": [_encode_self_relevant(item) for item in value.beliefs],
        "candidate_count": value.candidate_count,
        "confidence": value.confidence,
        "goal_ids": [item.value for item in value.goal_ids],
        "life_status": None if value.life_status is None else value.life_status.value,
        "owner_id": value.owner_id.value,
        "policy_id": value.policy_id,
        "policy_version": value.policy_version,
    }


def _decode_self_model(data: dict[str, Any], *, path: str) -> SelfModel:
    _require_keys(
        data,
        {
            "beliefs",
            "candidate_count",
            "confidence",
            "goal_ids",
            "life_status",
            "owner_id",
            "policy_id",
            "policy_version",
        },
        path=path,
    )
    beliefs_raw = data["beliefs"]
    goals_raw = data["goal_ids"]
    if not isinstance(beliefs_raw, list):
        raise SubjectiveSerializationError("invalid_array", f"{path}.beliefs")
    if not isinstance(goals_raw, list):
        raise SubjectiveSerializationError("invalid_array", f"{path}.goal_ids")
    life_raw = data["life_status"]
    try:
        life_status = None if life_raw is None else LifeStatus(str(life_raw))
        beliefs = tuple(
            _decode_self_relevant(item, path=f"{path}.beliefs[{index}]")
            for index, item in enumerate(beliefs_raw)
        )
        goals = tuple(
            GoalId(_require_list_str(item, path=f"{path}.goal_ids[{index}]"))
            for index, item in enumerate(goals_raw)
        )
        return SelfModel(
            owner_id=AgentId(_str_field(data, "owner_id", path=path)),
            policy_id=_str_field(data, "policy_id", path=path),
            policy_version=_str_field(data, "policy_version", path=path),
            life_status=life_status,
            beliefs=beliefs,
            goal_ids=goals,
            confidence=_float_field(data, "confidence", path=path),
            candidate_count=_int_field(data, "candidate_count", path=path),
        )
    except SubjectiveSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise SubjectiveSerializationError("invalid_model", path) from exc


def _require_list_str(value: object, *, path: str) -> str:
    if not isinstance(value, str):
        raise SubjectiveSerializationError("invalid_string", path)
    return value
