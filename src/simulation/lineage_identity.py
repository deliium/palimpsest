"""Qualified historical-lineage identity.

Lineage identity never relies on a bare local ID. Every reference carries its
run, family, evidence class, native kind, native ID and (when applicable) the
owner that namespaced the source entry. Objective facts, owner-scoped claims and
detached analytical inference therefore cannot collide or silently merge.

Framework-free: no persistence, API, analysis, experiments or ORM imports.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from simulation.models import RunId
from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "LINEAGE_NODE_KEY_HEX_LENGTH",
    "LineageEvidenceClass",
    "LineageEvidenceRef",
    "LineageFamily",
    "LineageNativeKind",
    "LineageNodeRef",
    "lineage_edge_key",
    "lineage_node_key",
    "require_lineage_key",
    "require_lineage_owner_for_kind",
    "require_supported_scope_owner",
    "require_unique_node_refs",
    "scope_family_classes",
]

LINEAGE_NODE_KEY_HEX_LENGTH: Final[int] = 64


class LineageFamily(StrEnum):
    """Closed historical-lineage families."""

    GENEALOGY = "genealogy"
    MENTORSHIP = "mentorship"
    TECHNOLOGY = "technology"
    KNOWLEDGE = "knowledge"
    RECORD = "record"
    NARRATIVE = "narrative"
    INSTITUTION = "institution"
    OFFICE_SUCCESSION = "office_succession"


class LineageEvidenceClass(StrEnum):
    """Authority class of the evidence behind a node or edge."""

    OBJECTIVE = "objective"
    SUBJECTIVE = "subjective"
    ANALYTICAL = "analytical"


class LineageNativeKind(StrEnum):
    """Closed native source kinds used for qualified lookup and identity."""

    AGENT = "agent"
    ARTIFACT = "artifact"
    RECORD_REVISION = "record_revision"
    MENTORSHIP_ENTRY = "mentorship_entry"
    KNOWLEDGE_ENTRY = "knowledge_entry"
    TECHNIQUE = "technique"
    NARRATIVE_VARIANT = "narrative_variant"
    EVENT = "event"
    INSTITUTION_EPISODE = "institution_episode"
    OFFICE = "office"
    OFFICE_CLAIM = "office_claim"
    OFFICE_TRANSITION = "office_transition"


_OBJECTIVE_FAMILIES: Final[frozenset[LineageFamily]] = frozenset(
    {LineageFamily.GENEALOGY, LineageFamily.RECORD}
)
_SUBJECTIVE_FAMILIES: Final[frozenset[LineageFamily]] = frozenset(
    {
        LineageFamily.MENTORSHIP,
        LineageFamily.TECHNOLOGY,
        LineageFamily.KNOWLEDGE,
        LineageFamily.NARRATIVE,
        LineageFamily.OFFICE_SUCCESSION,
    }
)
_ANALYTICAL_FAMILIES: Final[frozenset[LineageFamily]] = frozenset(
    {
        LineageFamily.MENTORSHIP,
        LineageFamily.TECHNOLOGY,
        LineageFamily.KNOWLEDGE,
        LineageFamily.NARRATIVE,
        LineageFamily.INSTITUTION,
    }
)
_ANALYTICAL_SHARED_KINDS: Final[frozenset[LineageNativeKind]] = frozenset(
    {LineageNativeKind.AGENT, LineageNativeKind.EVENT}
)


def _require_family(value: object) -> LineageFamily:
    if type(value) is not LineageFamily:
        raise ValueError("lineage family must be a LineageFamily")
    return value


def _require_evidence_class(value: object) -> LineageEvidenceClass:
    if type(value) is not LineageEvidenceClass:
        raise ValueError("lineage evidence class must be a LineageEvidenceClass")
    return value


def _require_native_kind(value: object) -> LineageNativeKind:
    if type(value) is not LineageNativeKind:
        raise ValueError("lineage native kind must be a LineageNativeKind")
    return value


def require_lineage_owner_for_kind(
    evidence_class: LineageEvidenceClass, native_kind: LineageNativeKind
) -> bool:
    """Return whether an owner is required for this evidence class and kind."""
    evidence = _require_evidence_class(evidence_class)
    kind = _require_native_kind(native_kind)
    if evidence is LineageEvidenceClass.OBJECTIVE:
        return False
    if evidence is LineageEvidenceClass.SUBJECTIVE:
        return True
    return kind not in _ANALYTICAL_SHARED_KINDS


def require_supported_scope_owner(
    family: LineageFamily, evidence_class: LineageEvidenceClass, owner_id: str | None
) -> None:
    """Validate the closed family/class/owner matrix before any source read."""
    lineage_family = _require_family(family)
    evidence = _require_evidence_class(evidence_class)
    if evidence is LineageEvidenceClass.OBJECTIVE:
        if lineage_family not in _OBJECTIVE_FAMILIES:
            raise ValueError("invalid_lineage_scope")
        if owner_id is not None:
            raise ValueError("invalid_lineage_scope")
        return
    if evidence is LineageEvidenceClass.SUBJECTIVE:
        if lineage_family not in _SUBJECTIVE_FAMILIES:
            raise ValueError("invalid_lineage_scope")
        if owner_id is None:
            raise ValueError("invalid_lineage_scope")
        return
    if lineage_family not in _ANALYTICAL_FAMILIES:
        raise ValueError("invalid_lineage_scope")
    if owner_id is not None:
        raise ValueError("invalid_lineage_scope")


def _canonical_hex(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_owned_reference(
    *,
    evidence_class: LineageEvidenceClass,
    native_kind: LineageNativeKind,
    identity_owner: str | None,
) -> str | None:
    owner_required = require_lineage_owner_for_kind(evidence_class, native_kind)
    if owner_required:
        if identity_owner is None:
            raise ValueError("lineage identity owner is required")
        return require_stable_id("identity_owner", identity_owner)
    if identity_owner is not None:
        raise ValueError("lineage identity owner is forbidden")
    return None


@dataclass(frozen=True, slots=True)
class LineageNodeRef:
    """Structured, qualified node reference with a deterministic identity key."""

    run_id: RunId
    family: LineageFamily
    evidence_class: LineageEvidenceClass
    native_kind: LineageNativeKind
    native_id: str
    identity_owner: str | None = None

    def __post_init__(self) -> None:
        if type(self.run_id) is not RunId:
            raise ValueError("LineageNodeRef.run_id must be RunId")
        object.__setattr__(self, "family", _require_family(self.family))
        object.__setattr__(
            self, "evidence_class", _require_evidence_class(self.evidence_class)
        )
        object.__setattr__(self, "native_kind", _require_native_kind(self.native_kind))
        object.__setattr__(
            self,
            "native_id",
            require_stable_id("LineageNodeRef.native_id", self.native_id),
        )
        object.__setattr__(
            self,
            "identity_owner",
            _validate_owned_reference(
                evidence_class=self.evidence_class,
                native_kind=self.native_kind,
                identity_owner=self.identity_owner,
            ),
        )

    def canonical_payload(self) -> dict[str, object]:
        return {
            "evidence_class": self.evidence_class.value,
            "family": self.family.value,
            "identity_owner": self.identity_owner,
            "native_id": self.native_id,
            "native_kind": self.native_kind.value,
            "run_id": self.run_id.value,
        }

    @property
    def key(self) -> str:
        return _canonical_hex(self.canonical_payload())


def lineage_node_key(ref: LineageNodeRef) -> str:
    """Return the deterministic SHA-256 identity key for a node reference."""
    if type(ref) is not LineageNodeRef:
        raise TypeError("ref must be LineageNodeRef")
    return ref.key


@dataclass(frozen=True, slots=True)
class LineageEvidenceRef:
    """Qualified reference to one underlying native evidence row."""

    evidence_class: LineageEvidenceClass
    native_kind: LineageNativeKind
    native_id: str
    owner_id: str | None = None
    observed_tick: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "evidence_class", _require_evidence_class(self.evidence_class)
        )
        object.__setattr__(self, "native_kind", _require_native_kind(self.native_kind))
        object.__setattr__(
            self,
            "native_id",
            require_stable_id("LineageEvidenceRef.native_id", self.native_id),
        )
        object.__setattr__(
            self,
            "owner_id",
            _validate_owned_reference(
                evidence_class=self.evidence_class,
                native_kind=self.native_kind,
                identity_owner=self.owner_id,
            ),
        )
        if self.observed_tick is not None:
            object.__setattr__(
                self,
                "observed_tick",
                require_exact_nonneg_int(
                    "LineageEvidenceRef.observed_tick", self.observed_tick
                ),
            )

    def canonical_payload(self) -> dict[str, object]:
        return {
            "evidence_class": self.evidence_class.value,
            "native_id": self.native_id,
            "native_kind": self.native_kind.value,
            "observed_tick": self.observed_tick,
            "owner_id": self.owner_id,
        }

    @property
    def key(self) -> str:
        return _canonical_hex(self.canonical_payload())


def require_lineage_key(name: str, value: object) -> str:
    """Validate a lowercase SHA-256 identity key."""
    text = require_stable_id(name, value)
    if len(text) != LINEAGE_NODE_KEY_HEX_LENGTH:
        raise ValueError(f"{name} must be a SHA-256 hex key")
    if any(char not in "0123456789abcdef" for char in text):
        raise ValueError(f"{name} must be a lowercase SHA-256 hex key")
    return text


def _require_hex_key(name: str, value: object) -> str:
    return require_lineage_key(name, value)


def lineage_edge_key(
    *,
    relation: str,
    source_key: str,
    target_key: str,
    native_kind: LineageNativeKind,
    native_id: str,
    claim_owner_id: str | None = None,
    evidence_keys: tuple[str, ...] = (),
) -> str:
    """Deterministic edge identity preserving parallel evidence."""
    payload = {
        "claim_owner_id": claim_owner_id,
        "evidence_keys": sorted(
            _require_hex_key("LineageEvidenceRef.key", item) for item in evidence_keys
        ),
        "native_id": require_stable_id("lineage_edge_key.native_id", native_id),
        "native_kind": _require_native_kind(native_kind).value,
        "relation": require_stable_id("lineage_edge_key.relation", relation),
        "source_key": _require_hex_key("lineage_edge_key.source_key", source_key),
        "target_key": _require_hex_key("lineage_edge_key.target_key", target_key),
    }
    if claim_owner_id is not None:
        payload["claim_owner_id"] = require_stable_id(
            "lineage_edge_key.claim_owner_id", claim_owner_id
        )
    return _canonical_hex(payload)


def require_unique_node_refs(refs: tuple[LineageNodeRef, ...]) -> None:
    """Reject conflicting duplicate qualified identities in one source revision."""
    seen: set[str] = set()
    for ref in refs:
        if type(ref) is not LineageNodeRef:
            raise TypeError("refs must contain LineageNodeRef values")
        key = ref.key
        if key in seen:
            raise ValueError("duplicate_lineage_identity")
        seen.add(key)


def scope_family_classes() -> dict[LineageFamily, tuple[LineageEvidenceClass, ...]]:
    """Return the closed supported family/class matrix for validation and tests."""
    result: dict[LineageFamily, tuple[LineageEvidenceClass, ...]] = {}
    for family in LineageFamily:
        classes: list[LineageEvidenceClass] = []
        for evidence in LineageEvidenceClass:
            try:
                require_supported_scope_owner(
                    family,
                    evidence,
                    "owner-1" if evidence is LineageEvidenceClass.SUBJECTIVE else None,
                )
            except ValueError:
                continue
            classes.append(evidence)
        result[family] = tuple(classes)
    return result
