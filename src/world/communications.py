"""Closed structured communication payloads and speaker-declared transmission.

World-verified delivery fields (event ID, actor, recipient, tick, delivery
outcome) live on events and observations. Source basis, inherited chain data,
and sender confidence here are speaker-declared testimony only.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final

from world._freeze import require_bounded_text, require_ordered_unique
from world.identifiers import (
    EntityId,
    require_exact_nonneg_int,
    require_stable_id,
)

__all__ = [
    "COMMUNICATION_ELIGIBILITY_POLICY_VERSION",
    "COMMUNICATION_SCHEMA_VERSION",
    "MAX_COMMUNICATION_CONCEPTS",
    "MAX_COMMUNICATION_HOPS",
    "MAX_COMMUNICATION_RELATIONS",
    "MAX_SOURCE_AGENT_CHAIN",
    "CommunicationContent",
    "CommunicationId",
    "CommunicationRelation",
    "CommunicationSourceBasis",
    "DeclaredTransmission",
    "StructuredUtterance",
    "canonical_content_bytes",
    "confidence_band",
    "content_fingerprint",
    "legacy_text_utterance",
    "observation_allows_communication_target",
    "origin_utterance",
    "retell_utterance",
]

COMMUNICATION_SCHEMA_VERSION: Final[str] = "communication.v1"
COMMUNICATION_ELIGIBILITY_POLICY_VERSION: Final[str] = "communication-eligibility.v1"
MAX_COMMUNICATION_CONCEPTS: Final[int] = 32
MAX_COMMUNICATION_RELATIONS: Final[int] = 32
MAX_COMMUNICATION_HOPS: Final[int] = 64
MAX_SOURCE_AGENT_CHAIN: Final[int] = 64
_MAX_CONCEPT_CHARS: Final[int] = 256
_MAX_PREDICATE_CHARS: Final[int] = 128


class CommunicationSourceBasis(StrEnum):
    """Speaker-declared grounding for an utterance (not world-verified)."""

    BELIEF = "belief"
    RECONSTRUCTED_MEMORY = "reconstructed_memory"
    GOAL = "goal"
    RELATIONSHIP = "relationship"
    UNREFERENCED = "unreferenced"


@dataclass(frozen=True, slots=True)
class CommunicationId:
    """Opaque stable identity for one communication utterance."""

    value: str

    def __post_init__(self) -> None:
        require_stable_id("CommunicationId.value", self.value)

    def __repr__(self) -> str:
        return f"CommunicationId(value={self.value!r})"


def confidence_band(value: float) -> str:
    """Map a unit confidence to a coarse band for metadata-only logging/repr."""
    if value < 0.34:
        return "low"
    if value < 0.67:
        return "mid"
    return "high"


def _require_confidence(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name}: not_confidence")
    number = float(value)
    if not math.isfinite(number) or number < 0.0 or number > 1.0:
        raise ValueError(f"{name}: not_confidence")
    return 0.0 if number == 0.0 else number


@dataclass(frozen=True, slots=True)
class CommunicationRelation:
    """Bounded subject-predicate-object atom inside an utterance."""

    subject: str
    predicate: str
    object: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "subject",
            require_bounded_text(
                "CommunicationRelation.subject",
                self.subject,
                max_length=_MAX_CONCEPT_CHARS,
            ),
        )
        object.__setattr__(
            self,
            "predicate",
            require_bounded_text(
                "CommunicationRelation.predicate",
                self.predicate,
                max_length=_MAX_PREDICATE_CHARS,
            ),
        )
        object.__setattr__(
            self,
            "object",
            require_bounded_text(
                "CommunicationRelation.object",
                self.object,
                max_length=_MAX_CONCEPT_CHARS,
            ),
        )

    def __repr__(self) -> str:
        return "CommunicationRelation(fields=3)"


@dataclass(frozen=True, slots=True)
class CommunicationContent:
    """Bounded structured utterance body shared by talk, ask, and tell.

    Distinguishes ordinary conversation, questions, and testimony only through
    accompanying command/event kind — not domain rumor/culture labels.
    """

    text: str
    concepts: Sequence[str] = field(default_factory=tuple)
    relations: Sequence[CommunicationRelation] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "text",
            require_bounded_text("CommunicationContent.text", self.text),
        )
        concepts = require_ordered_unique(
            "CommunicationContent.concepts",
            self.concepts,
            item_type=str,
        )
        if len(concepts) > MAX_COMMUNICATION_CONCEPTS:
            raise ValueError("CommunicationContent.concepts: too_many")
        normalized_concepts: list[str] = []
        for index, concept in enumerate(concepts):
            normalized_concepts.append(
                require_bounded_text(
                    f"CommunicationContent.concepts[{index}]",
                    concept,
                    max_length=_MAX_CONCEPT_CHARS,
                )
            )
        object.__setattr__(self, "concepts", tuple(normalized_concepts))
        if isinstance(self.relations, (set, frozenset)):
            raise TypeError("CommunicationContent.relations: not_ordered")
        if isinstance(self.relations, (str, bytes)) or not isinstance(
            self.relations, Sequence
        ):
            raise TypeError("CommunicationContent.relations: not_ordered")
        relations = tuple(self.relations)
        if len(relations) > MAX_COMMUNICATION_RELATIONS:
            raise ValueError("CommunicationContent.relations: too_many")
        for index, relation in enumerate(relations):
            if type(relation) is not CommunicationRelation:
                raise TypeError(
                    f"CommunicationContent.relations[{index}]: not_relation"
                )
        object.__setattr__(self, "relations", relations)

    def __repr__(self) -> str:
        return (
            f"CommunicationContent(concept_count={len(self.concepts)}, "
            f"relation_count={len(self.relations)})"
        )


def canonical_content_bytes(content: CommunicationContent) -> bytes:
    """Deterministic UTF-8 JSON bytes for content fingerprinting."""
    if type(content) is not CommunicationContent:
        raise TypeError("canonical_content_bytes requires CommunicationContent")
    payload = {
        "concepts": list(content.concepts),
        "relations": [
            {
                "object": relation.object,
                "predicate": relation.predicate,
                "subject": relation.subject,
            }
            for relation in content.relations
        ],
        "text": content.text,
        "version": COMMUNICATION_SCHEMA_VERSION,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def content_fingerprint(content: CommunicationContent) -> str:
    """SHA-256 hex digest of canonical content bytes."""
    return hashlib.sha256(canonical_content_bytes(content)).hexdigest()


@dataclass(frozen=True, slots=True)
class DeclaredTransmission:
    """Speaker-declared transmission lineage (testimony, not world truth)."""

    communication_id: CommunicationId
    immediate_source_id: EntityId
    parent_communication_id: CommunicationId | None
    root_communication_id: CommunicationId
    source_agent_chain: Sequence[EntityId]
    hop_count: int
    sender_confidence: float
    source_basis: CommunicationSourceBasis

    def __post_init__(self) -> None:
        if type(self.communication_id) is not CommunicationId:
            raise TypeError(
                "DeclaredTransmission.communication_id: not_communication_id"
            )
        if type(self.immediate_source_id) is not EntityId:
            raise TypeError("DeclaredTransmission.immediate_source_id: not_entity_id")
        if (
            self.parent_communication_id is not None
            and type(self.parent_communication_id) is not CommunicationId
        ):
            raise TypeError(
                "DeclaredTransmission.parent_communication_id: not_communication_id"
            )
        if type(self.root_communication_id) is not CommunicationId:
            raise TypeError(
                "DeclaredTransmission.root_communication_id: not_communication_id"
            )
        if type(self.source_basis) is not CommunicationSourceBasis:
            raise TypeError("DeclaredTransmission.source_basis: not_source_basis")
        chain = require_ordered_unique(
            "DeclaredTransmission.source_agent_chain",
            self.source_agent_chain,
            item_type=EntityId,
        )
        if not chain:
            raise ValueError("DeclaredTransmission.source_agent_chain: empty")
        if len(chain) > MAX_SOURCE_AGENT_CHAIN:
            raise ValueError("DeclaredTransmission.source_agent_chain: too_many")
        object.__setattr__(self, "source_agent_chain", chain)
        hop = require_exact_nonneg_int("DeclaredTransmission.hop_count", self.hop_count)
        if hop > MAX_COMMUNICATION_HOPS:
            raise ValueError("DeclaredTransmission.hop_count: too_large")
        if hop != len(chain) - 1:
            raise ValueError("DeclaredTransmission.hop_count: chain_mismatch")
        if chain[-1] != self.immediate_source_id:
            raise ValueError("DeclaredTransmission.source_agent_chain: not_immediate")
        if hop == 0 and self.parent_communication_id is not None:
            raise ValueError("DeclaredTransmission.parent_communication_id: unexpected")
        if hop > 0 and self.parent_communication_id is None:
            raise ValueError("DeclaredTransmission.parent_communication_id: missing")
        if (
            self.parent_communication_id is not None
            and self.parent_communication_id == self.communication_id
        ):
            raise ValueError("DeclaredTransmission.parent_communication_id: self_ref")
        if hop == 0 and self.root_communication_id != self.communication_id:
            raise ValueError("DeclaredTransmission.root_communication_id: origin_mismatch")
        if (
            hop > 0
            and self.root_communication_id == self.communication_id
        ):
            raise ValueError("DeclaredTransmission.root_communication_id: not_inherited")
        object.__setattr__(self, "hop_count", hop)
        object.__setattr__(
            self,
            "sender_confidence",
            _require_confidence(
                "DeclaredTransmission.sender_confidence", self.sender_confidence
            ),
        )

    def __repr__(self) -> str:
        parent = (
            None
            if self.parent_communication_id is None
            else self.parent_communication_id.value
        )
        return (
            f"DeclaredTransmission(communication_id={self.communication_id.value!r}, "
            f"immediate_source_id={self.immediate_source_id.value!r}, "
            f"parent_communication_id={parent!r}, "
            f"root_communication_id={self.root_communication_id.value!r}, "
            f"hop_count={self.hop_count}, "
            f"chain_count={len(self.source_agent_chain)}, "
            f"confidence_band={confidence_band(self.sender_confidence)!r}, "
            f"source_basis={self.source_basis.value!r})"
        )


@dataclass(frozen=True, slots=True)
class StructuredUtterance:
    """Closed payload shared by Talk/Ask/Tell commands and Talked/Asked/Told."""

    content: CommunicationContent
    declared: DeclaredTransmission
    content_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.content) is not CommunicationContent:
            raise TypeError("StructuredUtterance.content: not_content")
        if type(self.declared) is not DeclaredTransmission:
            raise TypeError("StructuredUtterance.declared: not_declared")
        digest = content_fingerprint(self.content)
        object.__setattr__(self, "content_fingerprint", digest)

    def __repr__(self) -> str:
        return (
            f"StructuredUtterance(communication_id="
            f"{self.declared.communication_id.value!r}, "
            f"hop_count={self.declared.hop_count}, "
            f"confidence_band="
            f"{confidence_band(self.declared.sender_confidence)!r}, "
            f"source_basis={self.declared.source_basis.value!r}, "
            f"concept_count={len(self.content.concepts)}, "
            f"relation_count={len(self.content.relations)}, "
            f"schema_version={COMMUNICATION_SCHEMA_VERSION!r})"
        )


def origin_utterance(
    *,
    text: str,
    speaker_id: EntityId,
    communication_id: str = "comm-1",
    sender_confidence: float = 1.0,
    source_basis: CommunicationSourceBasis = CommunicationSourceBasis.UNREFERENCED,
    concepts: Sequence[str] = (),
    relations: Sequence[CommunicationRelation] = (),
) -> StructuredUtterance:
    """Build a hop-0 origin utterance for tests and safe planner fallbacks."""
    comm_id = CommunicationId(communication_id)
    return StructuredUtterance(
        content=CommunicationContent(
            text=text,
            concepts=concepts,
            relations=relations,
        ),
        declared=DeclaredTransmission(
            communication_id=comm_id,
            immediate_source_id=speaker_id,
            parent_communication_id=None,
            root_communication_id=comm_id,
            source_agent_chain=(speaker_id,),
            hop_count=0,
            sender_confidence=sender_confidence,
            source_basis=source_basis,
        ),
    )


def retell_utterance(
    *,
    prior: StructuredUtterance,
    speaker_id: EntityId,
    communication_id: str,
    sender_confidence: float | None = None,
    text: str | None = None,
    concepts: Sequence[str] | None = None,
    relations: Sequence[CommunicationRelation] | None = None,
    source_basis: CommunicationSourceBasis = (
        CommunicationSourceBasis.RECONSTRUCTED_MEMORY
    ),
) -> StructuredUtterance:
    """Append the current speaker as a new hop without copying prior identity."""
    if type(prior) is not StructuredUtterance:
        raise TypeError("retell_utterance requires StructuredUtterance")
    if type(speaker_id) is not EntityId:
        raise TypeError("speaker_id must be EntityId")
    if speaker_id in prior.declared.source_agent_chain:
        raise ValueError("retell_utterance: speaker_already_in_chain")
    chain = (*prior.declared.source_agent_chain, speaker_id)
    confidence = (
        prior.declared.sender_confidence
        if sender_confidence is None
        else sender_confidence
    )
    content = CommunicationContent(
        text=prior.content.text if text is None else text,
        concepts=prior.content.concepts if concepts is None else concepts,
        relations=prior.content.relations if relations is None else relations,
    )
    return StructuredUtterance(
        content=content,
        declared=DeclaredTransmission(
            communication_id=CommunicationId(communication_id),
            immediate_source_id=speaker_id,
            parent_communication_id=prior.declared.communication_id,
            root_communication_id=prior.declared.root_communication_id,
            source_agent_chain=chain,
            hop_count=len(chain) - 1,
            sender_confidence=confidence,
            source_basis=source_basis,
        ),
    )


def legacy_text_utterance(
    *,
    text: str,
    speaker_id: EntityId,
    event_id: str,
) -> StructuredUtterance:
    """Map replay-v2/v3/v4 text-only communication into unreferenced structure."""
    stable_event = require_stable_id("legacy_text_utterance.event_id", event_id)
    return origin_utterance(
        text=text,
        speaker_id=speaker_id,
        communication_id=f"legacy-{stable_event}",
        sender_confidence=1.0,
        source_basis=CommunicationSourceBasis.UNREFERENCED,
    )


def observation_allows_communication_target(
    *,
    visibility: float | None,
    visible_body_ids: Sequence[EntityId],
    recipient_id: EntityId,
    visibility_threshold: float,
) -> bool:
    """Agent-facing feasibility mirror of world communication eligibility.

    Uses only observation-derived evidence. Does not import private world rules.
    """
    if type(recipient_id) is not EntityId:
        raise TypeError("recipient_id must be EntityId")
    if visibility is not None:
        if isinstance(visibility, bool) or not isinstance(visibility, (int, float)):
            raise ValueError("visibility: not_finite")
        number = float(visibility)
        if not math.isfinite(number):
            raise ValueError("visibility: not_finite")
        if number < visibility_threshold:
            return False
    return any(body_id == recipient_id for body_id in visible_body_ids)
