"""Canonical codecs for reconstruction payloads (log-free).

Used for audit ``payload_sha256`` digests and domain serialization. Never logs
or returns narrative/content in errors.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Final

from memory.models import (
    ReconstructedMemory,
    ReconstructionRecord,
)

__all__ = [
    "RECONSTRUCTED_MEMORY_TYPE",
    "RECONSTRUCTION_RECORD_TYPE",
    "encode_reconstructed_memory",
    "encode_reconstruction_record",
    "reconstructed_memory_payload_sha256",
]

RECONSTRUCTED_MEMORY_TYPE: Final[str] = "reconstructed_memory"
RECONSTRUCTION_RECORD_TYPE: Final[str] = "reconstruction_record"


def encode_reconstructed_memory(value: ReconstructedMemory) -> dict[str, Any]:
    """Return the canonical JSON-object form of a reconstructed episode."""
    if type(value) is not ReconstructedMemory:
        raise TypeError("encode_reconstructed_memory: invalid_type")
    return {
        "concepts": [
            {"concept": item.concept, "mention_id": item.mention_id.value}
            for item in value.concepts
        ],
        "confidence": value.confidence,
        "context": {
            "location_id": (
                None
                if value.context.location_id is None
                else value.context.location_id.value
            ),
            "tags": list(value.context.tags),
        },
        "emotional_salience": value.emotional_salience,
        "entities": [
            {
                "entity_id": (None if item.entity_id is None else item.entity_id.value),
                "label": item.label,
                "mention_id": item.mention_id.value,
            }
            for item in value.entities
        ],
        "fallback_used": value.fallback_used,
        "generation": value.generation,
        "narrative": value.narrative,
        "owner_id": value.owner_id.value,
        "policy_id": value.policy_id,
        "policy_version": value.policy_version,
        "prompt_version": value.prompt_version,
        "reconstructed_at_tick": value.reconstructed_at_tick,
        "reconstruction_id": value.reconstruction_id.value,
        "relations": [
            {
                "object": {
                    "kind": item.object.kind.value,
                    "mention_id": item.object.mention_id.value,
                },
                "predicate": item.predicate,
                "relation_id": item.relation_id.value,
                "subject": {
                    "kind": item.subject.kind.value,
                    "mention_id": item.subject.mention_id.value,
                },
            }
            for item in value.relations
        ],
        "schema_version": value.schema_version,
        "source_memory_ids": [item.value for item in value.source_memory_ids],
        "used_provider": value.used_provider,
    }


def encode_reconstruction_record(value: ReconstructionRecord) -> dict[str, Any]:
    """Return the canonical JSON-object form of a reconstruction record."""
    if type(value) is not ReconstructionRecord:
        raise TypeError("encode_reconstruction_record: invalid_type")
    return {
        "created_tick": value.created_tick,
        "fallback_used": value.fallback_used,
        "owner_id": value.owner_id.value,
        "policy_id": value.policy_id,
        "policy_version": value.policy_version,
        "prompt_version": value.prompt_version,
        "reconstructed": encode_reconstructed_memory(value.reconstructed),
        "reconstruction_id": value.reconstruction_id.value,
        "run_id": value.run_id.value,
        "schema_version": value.schema_version,
        "source_memory_ids": [item.value for item in value.source_memory_ids],
        "used_provider": value.used_provider,
    }


def reconstructed_memory_payload_sha256(value: ReconstructedMemory) -> str:
    """SHA-256 hex digest of canonical reconstructed-memory JSON bytes."""
    payload = encode_reconstructed_memory(value)
    text = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
