"""Map communicated transmission and testimony factors to/from ORM columns."""

from __future__ import annotations

from typing import Any

from memory.beliefs import AppliedTestimonyFactors, CommunicatedEvidenceDecision
from memory.models import CommunicatedTransmissionMeta, EntityId

__all__ = [
    "applied_factors_from_row",
    "applied_factors_to_columns",
    "transmission_from_row",
    "transmission_to_columns",
]


def transmission_to_columns(
    meta: CommunicatedTransmissionMeta | None,
) -> dict[str, Any]:
    if meta is None:
        return {
            "transmission_communication_id": None,
            "transmission_action_kind": None,
            "transmission_hop_count": None,
            "transmission_sender_confidence": None,
            "transmission_receiver_confidence": None,
            "transmission_content_fingerprint": None,
            "transmission_parent_communication_id": None,
            "transmission_source_agent_chain": None,
            "transmission_root_id": None,
            "transmission_policy_version": None,
        }
    return {
        "transmission_communication_id": meta.communication_id,
        "transmission_action_kind": meta.action_kind,
        "transmission_hop_count": meta.hop_count,
        "transmission_sender_confidence": meta.sender_confidence,
        "transmission_receiver_confidence": meta.receiver_confidence,
        "transmission_content_fingerprint": meta.content_fingerprint,
        "transmission_parent_communication_id": meta.parent_communication_id,
        "transmission_source_agent_chain": [
            item.value for item in meta.source_agent_chain
        ],
        "transmission_root_id": meta.transmission_root_id,
        "transmission_policy_version": meta.policy_version,
    }


def transmission_from_row(row: object) -> CommunicatedTransmissionMeta | None:
    communication_id = getattr(row, "transmission_communication_id", None)
    if communication_id is None:
        return None
    chain_raw = getattr(row, "transmission_source_agent_chain", None) or ()
    return CommunicatedTransmissionMeta(
        communication_id=str(communication_id),
        action_kind=str(row.transmission_action_kind),
        hop_count=int(row.transmission_hop_count),
        sender_confidence=float(row.transmission_sender_confidence),
        receiver_confidence=float(row.transmission_receiver_confidence),
        content_fingerprint=str(row.transmission_content_fingerprint),
        parent_communication_id=(
            None
            if getattr(row, "transmission_parent_communication_id", None) is None
            else str(row.transmission_parent_communication_id)
        ),
        source_agent_chain=tuple(EntityId(str(item)) for item in chain_raw),
        transmission_root_id=str(row.transmission_root_id or ""),
        policy_version=str(row.transmission_policy_version),
    )


def applied_factors_to_columns(
    factors: AppliedTestimonyFactors | None,
) -> dict[str, Any]:
    if factors is None:
        return {
            "testimony_decision": None,
            "testimony_hop_count": None,
            "testimony_trust": None,
            "testimony_trust_confidence": None,
            "testimony_sender_confidence": None,
            "testimony_receiver_confidence": None,
            "testimony_context_relevance": None,
            "testimony_hop_attenuation": None,
            "testimony_base_contribution": None,
            "testimony_adjusted_contribution": None,
            "testimony_confidence_delta": None,
            "testimony_policy_version": None,
        }
    return {
        "testimony_decision": factors.decision.value,
        "testimony_hop_count": factors.hop_count,
        "testimony_trust": factors.trust,
        "testimony_trust_confidence": factors.trust_confidence,
        "testimony_sender_confidence": factors.sender_confidence,
        "testimony_receiver_confidence": factors.receiver_confidence,
        "testimony_context_relevance": factors.context_relevance,
        "testimony_hop_attenuation": factors.hop_attenuation,
        "testimony_base_contribution": factors.base_contribution,
        "testimony_adjusted_contribution": factors.adjusted_contribution,
        "testimony_confidence_delta": factors.confidence_delta,
        "testimony_policy_version": factors.policy_version,
    }


def applied_factors_from_row(row: object) -> AppliedTestimonyFactors | None:
    decision = getattr(row, "testimony_decision", None)
    if decision is None:
        return None
    return AppliedTestimonyFactors(
        decision=CommunicatedEvidenceDecision(str(decision)),
        hop_count=int(row.testimony_hop_count),
        trust=float(row.testimony_trust),
        trust_confidence=float(row.testimony_trust_confidence),
        sender_confidence=float(row.testimony_sender_confidence),
        receiver_confidence=float(row.testimony_receiver_confidence),
        context_relevance=float(row.testimony_context_relevance),
        hop_attenuation=float(row.testimony_hop_attenuation),
        base_contribution=float(row.testimony_base_contribution),
        adjusted_contribution=float(row.testimony_adjusted_contribution),
        confidence_delta=float(row.testimony_confidence_delta),
        policy_version=str(row.testimony_policy_version),
    )
