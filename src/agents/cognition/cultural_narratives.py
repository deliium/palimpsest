"""Owner-scoped cultural narrative lineages (narrative ledger).

A ledger tracks private recurring story variants — not a Myth type, not a world
rule, and not an automatic society-wide influence. Updates read one owner's
Observation, previous NarrativeLedger, OwnerSafeSocialIdentity, already-loaded
memories (reinforce-only), and an optional caller-built NarrativeCueSummary.
They never read WorldState, WorldEvent, PhysicalRules, another owner's ledger,
sibling artifact/naming/convention/norm/group ledger objects, or analysis
documents.
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Final, TypeGuard

from agents.cognition.models import OwnerSafeSocialIdentity
from agents.models import AgentId
from world.communications import (
    CommunicationContent,
    CommunicationRelation,
    CommunicationSourceBasis,
)
from world.communications import (
    content_fingerprint as world_content_fingerprint,
)
from world.identifiers import EntityId, require_exact_nonneg_int
from world.observations import Observation, ObservedCommunication, ObservedOccurrence

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.cultural_narratives")

CULTURAL_NARRATIVE_POLICY_VERSION: Final[str] = "cultural-narratives.v1"
CULTURAL_NARRATIVE_POLICY_VERSION_V2: Final[str] = "cultural-narratives.v2"
_QUANTUM: Final[Decimal] = Decimal("0.000001")
_ACTIVE_STRENGTH: Final[float] = 0.40
_RETIRE_STRENGTH: Final[float] = 0.20
_DECAY: Final[float] = 0.05
_OBSERVED_DELTA: Final[float] = 0.12
_REMEMBERED_DELTA: Final[float] = 0.08
_COMMUNICATED_DELTA: Final[float] = 0.10
_DELIBERATE_LIE_DELTA: Final[float] = 0.10
_MISREAD_ARTIFACT_DELTA: Final[float] = 0.10
_PENALTY: Final[float] = 0.30
_PROMOTION_COUNT: Final[int] = 3
_SEMANTIC_UPLIFT_REPETITIONS: Final[int] = 5
_SEMANTIC_UPLIFT_STRENGTH: Final[float] = 0.55
_MERGE_TOKEN_OVERLAP: Final[float] = 0.75
_UTTERANCE_INTERVAL: Final[int] = 4
_MAX_VARIANTS: Final[int] = 8
_MAX_EVIDENCE: Final[int] = 32
_MAX_CARRIERS: Final[int] = 8
_MAX_LOCATIONS: Final[int] = 8
_MAX_PARENTS: Final[int] = 4
_MAX_COMPETITORS: Final[int] = 4
_MAX_WITNESSES: Final[int] = 8
_MAX_RECORDS: Final[int] = 8
_MAX_TRANSITIONS: Final[int] = 16
_MAX_DECLARED_CHAIN: Final[int] = 8
_MAX_THEMES: Final[int] = 3
_RECORD_READ_DELTA: Final[float] = 0.10
_HEX: Final[frozenset[str]] = frozenset("0123456789abcdef")
_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_NARRATIVE_PREDICATES: Final[frozenset[str]] = frozenset(
    {"tell_story", "retell", "merge_story"}
)
_FORBIDDEN_PROSE_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "sentence",
        "utterance_text",
        "translation",
        "natural_language",
        "narrative",
        "myth",
        "legend",
        "story_text",
    }
)
_NOTICE_REASONS: Final[frozenset[str]] = frozenset(
    {
        "cap_exceeded",
        "ignored_kind",
        "unresolved_entity",
        "empty_content",
        "no_candidate",
        "candidate_only",
        "utterance_interval",
        "below_count",
        "below_strength",
        "below_overlap",
        "below_repetition",
        "inactive_status",
        "disabled",
        "no_memory_anchor",
        "forbidden_type",
        "invalid_token",
    }
)
_FORBIDDEN_TYPES: Final[frozenset[str]] = frozenset(
    {
        "WorldState",
        "WorldEvent",
        "PhysicalRules",
        "AgentBody",
        "MetricDocument",
        "GroupLedger",
        "NormLedger",
        "ConventionLedger",
        "ArtifactInterpretationLedger",
        "TerminologyLedger",
        "LabelBinding",
        "HistoricalMemoryHarvest",
        "NarrativeGenerationRow",
        "NarrativeRecordRow",
        "NarrativeSourceLossRow",
        "NarrativeHistoryComparisonRow",
        "GenerationalNarrativeInputs",
    }
)
type _ReconstructionCueRow = tuple[
    str,
    tuple[str, ...],
    tuple[str, ...],
    tuple[tuple[str, str, str], ...],
]
_FORBIDDEN_CUE_TYPE_NAMES: Final[frozenset[str]] = frozenset(
    {
        "GroupLedger",
        "NormLedger",
        "ConventionLedger",
        "ArtifactInterpretationLedger",
        "TerminologyLedger",
        "LabelBinding",
        "GroupConcept",
        "NormBelief",
        "ConventionBelief",
    }
)

__all__ = [
    "CULTURAL_NARRATIVE_POLICY_VERSION",
    "CULTURAL_NARRATIVE_POLICY_VERSION_V2",
    "CulturalNarrativePolicy",
    "GenerationalNarrativePolicy",
    "NarrativeContent",
    "NarrativeCueSummary",
    "NarrativeEvidenceChannel",
    "NarrativeEvidenceItem",
    "NarrativeLedger",
    "NarrativeOrigin",
    "NarrativeRecordCue",
    "NarrativeRecordRef",
    "NarrativeRecordRole",
    "NarrativeSourceLoss",
    "NarrativeSourceLossReason",
    "NarrativeSourceLossState",
    "NarrativeStatus",
    "NarrativeTheme",
    "NarrativeThemeBasis",
    "NarrativeTransition",
    "NarrativeTransitionKind",
    "NarrativeUtterancePlan",
    "NarrativeVariant",
    "NarrativeWitness",
    "NarrativeWitnessKind",
    "apply_narrative_update",
    "default_cultural_narrative_policy",
    "default_generational_narrative_policy",
    "empty_narrative_ledger",
    "narrative_communicate_penalties",
    "narrative_communicate_utterance",
    "narrative_content_fingerprint",
    "narrative_evidence_id",
    "narrative_record_ref_id",
    "narrative_semantic_evidence",
    "narrative_transition_id",
    "narrative_variant_id",
    "narrative_witness_id",
    "require_owner_cultural_narratives",
]


class NarrativeOrigin(StrEnum):
    """Closed founding origin class for one narrative variant."""

    OBSERVED_EVENT = "observed_event"
    RECONSTRUCTED_MEMORY = "reconstructed_memory"
    DELIBERATE_LIE = "deliberate_lie"
    MISREAD_ARTIFACT = "misread_artifact"
    RETOLD_STORY = "retold_story"
    DURABLE_RECORD = "durable_record"


class NarrativeStatus(StrEnum):
    """Closed lifecycle for one owner's narrative variant."""

    CANDIDATE = "candidate"
    ACTIVE = "active"
    RETIRED = "retired"
    MERGED = "merged"


class NarrativeEvidenceChannel(StrEnum):
    """Closed evidence channel for one ledger item."""

    OBSERVED = "observed"
    REMEMBERED = "remembered"
    RECONSTRUCTED = "reconstructed"
    COMMUNICATED = "communicated"
    ARTIFACT = "artifact"
    RECORD = "record"


class NarrativeWitnessKind(StrEnum):
    """Closed provenance role for one known witness of a variant."""

    FIRST_HAND = "first_hand"
    DECLARED_SOURCE = "declared_source"
    DECLARED_RETELLER = "declared_reteller"
    RECORD_MEDIATED = "record_mediated"


class NarrativeRecordRole(StrEnum):
    """Closed observed role for a durable record reference."""

    AUTHORED = "authored"
    READ = "read"
    COPIED = "copied"
    AMENDED = "amended"
    ANNOTATED = "annotated"
    DAMAGED = "damaged"
    PARTIALLY_LOST = "partially_lost"
    DESTROYED = "destroyed"


class NarrativeTransitionKind(StrEnum):
    """Closed provenance transition for one narrative variant."""

    MINTED = "minted"
    RETOLD = "retold"
    RECORD_READ = "record_read"
    RECORD_COPIED = "record_copied"
    RECORD_AMENDED = "record_amended"
    RECORD_ANNOTATED = "record_annotated"
    RECORD_DAMAGED = "record_damaged"
    MERGED = "merged"
    EDITED = "edited"
    FIRST_HAND_WITNESS_DIED = "first_hand_witness_died"
    ALL_WITNESSES_DEAD = "all_witnesses_dead"
    SOURCE_LOST = "source_lost"
    RETIRED = "retired"
    REACTIVATED = "reactivated"


class NarrativeSourceLossState(StrEnum):
    """Owner-observed source preservation state. Never a truth value."""

    INTACT = "intact"
    PARTIAL = "partial"
    LOST = "lost"
    UNKNOWN = "unknown"


class NarrativeSourceLossReason(StrEnum):
    """Closed reason for the owner's subjective source-loss state."""

    NONE = "none"
    SOME_WITNESSES_DEAD = "some_witnesses_dead"
    ALL_FIRST_HAND_WITNESSES_DEAD = "all_first_hand_witnesses_dead"
    RECORD_DAMAGED = "record_damaged"
    RECORD_DESTROYED = "record_destroyed"
    WITNESS_AND_RECORD_LOSS = "witness_and_record_loss"
    UNKNOWN = "unknown"


class NarrativeTheme(StrEnum):
    """Closed descriptive theme grouping. Not importance and not truth."""

    FOUNDERS = "founders"
    DISASTERS = "disasters"
    DISCOVERIES = "discoveries"
    CONFLICTS = "conflicts"
    MIGRATIONS = "migrations"
    INNOVATIONS = "innovations"
    UNCLASSIFIED = "unclassified"


class NarrativeThemeBasis(StrEnum):
    """Closed basis for how a variant acquired its theme set."""

    OBSERVED_OCCURRENCE_KIND = "observed_occurrence_kind"
    INHERITED_LINEAGE = "inherited_lineage"
    UNCLASSIFIED = "unclassified"


_THEME_ORDER: Final[tuple[NarrativeTheme, ...]] = (
    NarrativeTheme.FOUNDERS,
    NarrativeTheme.DISASTERS,
    NarrativeTheme.DISCOVERIES,
    NarrativeTheme.CONFLICTS,
    NarrativeTheme.MIGRATIONS,
    NarrativeTheme.INNOVATIONS,
    NarrativeTheme.UNCLASSIFIED,
)
_THEME_RANK: Final[dict[NarrativeTheme, int]] = {
    theme: rank for rank, theme in enumerate(_THEME_ORDER)
}


def _require_nonneg_int(field_name: str, value: object) -> int:
    if isinstance(value, bool) or type(value) is not int:
        raise _fail(field_name, "invalid_type")
    if value < 0:
        raise _fail(field_name, "out_of_range")
    return value


def _require_optional_nonneg_int(field_name: str, value: object) -> int | None:
    if value is None:
        return None
    return _require_nonneg_int(field_name, value)


def _require_optional_text(field_name: str, value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise _fail(field_name, "invalid_type")
    return value


def _require_text(field_name: str, value: object) -> str:
    if not isinstance(value, str) or not value:
        raise _fail(field_name, "invalid_type")
    return value


@dataclass(frozen=True, slots=True)
class NarrativeWitness:
    """One agent the owner can bind as a witness for a narrative variant."""

    witness_agent_id: AgentId
    kind: NarrativeWitnessKind
    hop_index: int
    first_seen_tick: int
    last_seen_tick: int
    death_observed_tick: int | None = None

    def __post_init__(self) -> None:
        if type(self.witness_agent_id) is not AgentId:
            raise _fail("witness_agent_id", "invalid_type")
        if type(self.kind) is not NarrativeWitnessKind:
            raise _fail("witness.kind", "unknown_witness_kind")
        object.__setattr__(
            self, "hop_index", _require_nonneg_int("witness.hop_index", self.hop_index)
        )
        object.__setattr__(
            self,
            "first_seen_tick",
            _require_nonneg_int("witness.first_seen_tick", self.first_seen_tick),
        )
        last_seen = _require_nonneg_int(
            "witness.last_seen_tick", self.last_seen_tick
        )
        if last_seen < self.first_seen_tick:
            raise _fail("witness.last_seen_tick", "before_first_seen_tick")
        object.__setattr__(self, "last_seen_tick", last_seen)
        death = _require_optional_nonneg_int(
            "witness.death_observed_tick", self.death_observed_tick
        )
        if death is not None and death < self.first_seen_tick:
            raise _fail("witness.death_observed_tick", "before_first_seen_tick")
        object.__setattr__(self, "death_observed_tick", death)


@dataclass(frozen=True, slots=True)
class NarrativeRecordRef:
    """Opaque durable-record reference. Never carries record text or marks."""

    record_id: str
    role: NarrativeRecordRole
    observed_revision: int
    tick: int
    copy_generation: int | None = None
    integrity: str | None = None
    annotation_revisions: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "record_id",
            _require_text("record_ref.record_id", self.record_id),
        )
        if type(self.role) is not NarrativeRecordRole:
            raise _fail("record_ref.role", "unknown_record_role")
        object.__setattr__(
            self,
            "observed_revision",
            _require_nonneg_int(
                "record_ref.observed_revision", self.observed_revision
            ),
        )
        object.__setattr__(
            self, "tick", _require_nonneg_int("record_ref.tick", self.tick)
        )
        copy_generation = _require_optional_nonneg_int(
            "record_ref.copy_generation", self.copy_generation
        )
        object.__setattr__(self, "copy_generation", copy_generation)
        annotation_revisions = _require_optional_nonneg_int(
            "record_ref.annotation_revisions", self.annotation_revisions
        )
        object.__setattr__(self, "annotation_revisions", annotation_revisions)
        object.__setattr__(
            self,
            "integrity",
            _require_optional_text("record_ref.integrity", self.integrity),
        )


@dataclass(frozen=True, slots=True)
class NarrativeTransition:
    """One provenance transition in a variant's owner-scoped history."""

    transition_id: str
    kind: NarrativeTransitionKind
    tick: int
    parent_variant_ids: tuple[str, ...] = ()
    carrier_agent_id: AgentId | None = None
    record_id: str | None = None
    hop_index: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "transition_id",
            _require_hex_id("transition_id", self.transition_id),
        )
        if type(self.kind) is not NarrativeTransitionKind:
            raise _fail("transition.kind", "unknown_transition_kind")
        object.__setattr__(
            self, "tick", _require_nonneg_int("transition.tick", self.tick)
        )
        parents = _require_tuple(
            "transition.parent_variant_ids", self.parent_variant_ids
        )
        checked: list[str] = []
        for item in parents:
            checked.append(_require_hex_id("transition.parent_variant_ids", item))
        if len(checked) != len(set(checked)):
            raise _fail("transition.parent_variant_ids", "duplicate_parent")
        if len(checked) > _MAX_PARENTS:
            raise _fail("transition.parent_variant_ids", "cap_exceeded")
        object.__setattr__(self, "parent_variant_ids", tuple(checked))
        if (
            self.carrier_agent_id is not None
            and type(self.carrier_agent_id) is not AgentId
        ):
            raise _fail("transition.carrier_agent_id", "invalid_type")
        object.__setattr__(
            self,
            "record_id",
            _require_optional_text("transition.record_id", self.record_id),
        )
        hop_index = _require_optional_nonneg_int(
            "transition.hop_index", self.hop_index
        )
        object.__setattr__(self, "hop_index", hop_index)


@dataclass(frozen=True, slots=True)
class NarrativeSourceLoss:
    """Owner-observed preservation state. Missing evidence is not loss."""

    state: NarrativeSourceLossState
    reason: NarrativeSourceLossReason
    tick: int | None
    known_witness_count: int
    dead_witness_count: int
    record_backed: bool

    def __post_init__(self) -> None:
        if type(self.state) is not NarrativeSourceLossState:
            raise _fail("source_loss.state", "unknown_source_loss_state")
        if type(self.reason) is not NarrativeSourceLossReason:
            raise _fail("source_loss.reason", "unknown_source_loss_reason")
        object.__setattr__(
            self, "tick", _require_optional_nonneg_int("source_loss.tick", self.tick)
        )
        known = _require_nonneg_int(
            "source_loss.known_witness_count", self.known_witness_count
        )
        dead = _require_nonneg_int(
            "source_loss.dead_witness_count", self.dead_witness_count
        )
        if dead > known:
            raise _fail("source_loss.dead_witness_count", "exceeds_known")
        if type(self.record_backed) is not bool:
            raise _fail("source_loss.record_backed", "invalid_type")
        if self.state is NarrativeSourceLossState.UNKNOWN and dead != 0:
            raise _fail("source_loss.state", "unknown_with_dead_witnesses")
        if (
            self.state is NarrativeSourceLossState.PARTIAL
            and not (0 < dead < known)
            and self.reason
            is not NarrativeSourceLossReason.RECORD_DAMAGED
        ):
            raise _fail("source_loss.state", "partial_without_partial_death")
        if self.state is NarrativeSourceLossState.LOST:
            all_dead = known > 0 and dead == known
            record_lost = self.reason in {
                NarrativeSourceLossReason.RECORD_DESTROYED,
                NarrativeSourceLossReason.WITNESS_AND_RECORD_LOSS,
            }
            if not all_dead and not record_lost:
                raise _fail("source_loss.state", "lost_without_loss_evidence")
        if (
            self.state is NarrativeSourceLossState.INTACT
            and known > 0
            and dead == known
            and not self.record_backed
            and self.reason
            not in {
                NarrativeSourceLossReason.RECORD_DAMAGED,
                NarrativeSourceLossReason.RECORD_DESTROYED,
            }
        ):
            raise _fail("source_loss.state", "intact_without_source")


def narrative_witness_id(
    owner_id: AgentId,
    variant_id: str,
    witness_agent_id: AgentId,
    kind: NarrativeWitnessKind,
    hop_index: int,
) -> str:
    """Stable sha256 id for one witness row (owner/variant/witness/kind/hop)."""
    if type(owner_id) is not AgentId or type(witness_agent_id) is not AgentId:
        raise _fail("witness_id", "invalid_type")
    head = _require_hex_id("variant_id", variant_id)
    if type(kind) is not NarrativeWitnessKind:
        raise _fail("witness_id", "unknown_witness_kind")
    hop = _require_nonneg_int("hop_index", hop_index)
    return _sha256_hex(
        f"{owner_id.value}|{head}|{witness_agent_id.value}|{kind.value}|{hop}"
    )


def narrative_record_ref_id(
    variant_id: str,
    record_id: str,
    observed_revision: int,
    role: NarrativeRecordRole,
) -> str:
    """Stable sha256 id for one opaque record reference row."""
    head = _require_hex_id("variant_id", variant_id)
    record = _require_text("record_id", record_id)
    revision = _require_nonneg_int("observed_revision", observed_revision)
    if type(role) is not NarrativeRecordRole:
        raise _fail("record_ref_id", "unknown_record_role")
    return _sha256_hex(f"{head}|{record}|{revision}|{role.value}")


def narrative_transition_id(
    owner_id: AgentId,
    variant_id: str,
    kind: NarrativeTransitionKind,
    tick: int,
    reference: str,
) -> str:
    """Stable sha256 id for one transition (owner/variant/kind/tick/ref)."""
    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    head = _require_hex_id("variant_id", variant_id)
    if type(kind) is not NarrativeTransitionKind:
        raise _fail("transition_id", "unknown_transition_kind")
    tick_value = _require_nonneg_int("tick", tick)
    if not isinstance(reference, str):
        raise _fail("transition_id", "invalid_type")
    return _sha256_hex(
        f"{owner_id.value}|{head}|{kind.value}|{tick_value}|{reference}"
    )


def _fail(field_name: str, code: str) -> ValueError:
    _LOG.error(
        "narrative_validation_failed field=%s reason_code=%s",
        field_name,
        code,
    )
    return ValueError(f"{field_name}: {code}")


def _sha256_hex(material: str) -> str:
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _quantize(value: float) -> float:
    steps = round(value / 1e-6)
    quantized = float(Decimal(steps) * _QUANTUM)
    return 0.0 if quantized == 0.0 else quantized


def _apply_delta(current: float, delta: float) -> float:
    total = (Decimal(str(current)) + Decimal(str(delta))).quantize(
        _QUANTUM, rounding=ROUND_HALF_UP
    )
    number = float(total)
    if number < 0.0:
        return 0.0
    if number > 1.0:
        return 1.0
    return 0.0 if number == 0.0 else number


def _finite(field_name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _fail(field_name, "not_finite")
    number = float(value)
    if not math.isfinite(number):
        raise _fail(field_name, "not_finite")
    return number


def _locked_float(field_name: str, value: object, expected: float) -> float:
    number = _finite(field_name, value)
    if _quantize(number) != _quantize(expected):
        raise _fail(field_name, "unsupported_policy")
    return _quantize(expected)


def _locked_int(field_name: str, value: object, expected: int) -> int:
    if isinstance(value, bool) or type(value) is not int:
        raise _fail(field_name, "invalid_type")
    if value != expected:
        raise _fail(field_name, "unsupported_policy")
    return value


def _require_hex_id(field_name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in _HEX for char in value)
    ):
        raise _fail(field_name, "invalid_id")
    return value


def _require_tuple(field_name: str, values: object) -> tuple[object, ...]:
    if isinstance(values, (str, bytes, set, frozenset)) or not isinstance(
        values, Sequence
    ):
        raise _fail(field_name, "invalid_type")
    return tuple(values)


def _require_token(field_name: str, value: object) -> str:
    if not isinstance(value, str) or not _TOKEN_RE.fullmatch(value):
        raise _fail(field_name, "illegal_token")
    if value in _FORBIDDEN_PROSE_FIELDS:
        raise _fail(field_name, "forbidden_prose")
    return value


def _reject_forbidden(value: object) -> None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return
    name = type(value).__name__
    module = type(value).__module__
    if (
        name in _FORBIDDEN_TYPES
        or module.startswith("analysis")
        or module.startswith("analysis.")
    ):
        raise TypeError(f"{name}: forbidden_input")
    if isinstance(value, Mapping):
        keys = {str(key) for key in value}
        if "metric_family" in keys or "availability" in keys:
            raise TypeError(f"{name}: forbidden_input")


def narrative_variant_id(
    owner_id: AgentId,
    founding_fingerprint: str,
    mutation_generation: int,
    parent_salt: str,
) -> str:
    """sha256 hex of owner|founding_fingerprint|generation|parent_salt."""
    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    fingerprint = _require_hex_id("founding_fingerprint", founding_fingerprint)
    if isinstance(mutation_generation, bool) or type(mutation_generation) is not int:
        raise _fail("mutation_generation", "invalid_type")
    if mutation_generation < 0:
        raise _fail("mutation_generation", "out_of_range")
    if not isinstance(parent_salt, str):
        raise _fail("parent_salt", "invalid_type")
    return _sha256_hex(
        f"{owner_id.value}|{fingerprint}|{mutation_generation}|{parent_salt}"
    )


def narrative_evidence_id(
    variant_id: str,
    ordinal: int,
    channel: NarrativeEvidenceChannel,
    lineage_ref: str,
) -> str:
    """sha256 of variant id, ordinal, channel, and lineage ref."""
    head = _require_hex_id("variant_id", variant_id)
    if isinstance(ordinal, bool) or type(ordinal) is not int or ordinal < 0:
        raise _fail("ordinal", "invalid_type")
    if type(channel) is not NarrativeEvidenceChannel:
        raise _fail("channel", "unknown_channel")
    if not isinstance(lineage_ref, str) or not lineage_ref:
        raise _fail("lineage_ref", "invalid_type")
    return _sha256_hex(f"{head}|{ordinal}|{channel.value}|{lineage_ref}")


@dataclass(frozen=True, slots=True)
class NarrativeContent:
    """Closed structured story tokens. Free-form prose is forbidden."""

    concepts: tuple[str, ...] = ()
    relations: tuple[tuple[str, str, str], ...] = ()
    text: str = "tell_story"

    def __post_init__(self) -> None:
        if self.text not in _NARRATIVE_PREDICATES:
            raise _fail("content.text", "unknown_predicate")
        concepts = _require_tuple("concepts", self.concepts)
        checked_concepts: list[str] = []
        for item in concepts:
            checked_concepts.append(_require_token("concepts", item))
        if len(checked_concepts) != len(set(checked_concepts)):
            raise _fail("concepts", "duplicate_token")
        relations = _require_tuple("relations", self.relations)
        checked_relations: list[tuple[str, str, str]] = []
        for item in relations:
            if (
                not isinstance(item, tuple)
                or len(item) != 3
                or any(not isinstance(part, str) for part in item)
            ):
                raise _fail("relations", "invalid_type")
            subject = _require_token("relations.subject", item[0])
            predicate = _require_token("relations.predicate", item[1])
            obj = _require_token("relations.object", item[2])
            checked_relations.append((subject, predicate, obj))
        object.__setattr__(self, "concepts", tuple(sorted(checked_concepts)))
        object.__setattr__(
            self,
            "relations",
            tuple(sorted(checked_relations, key=lambda row: (row[0], row[1], row[2]))),
        )
        if not self.concepts and not self.relations:
            raise _fail("content", "empty_content")


def narrative_content_fingerprint(content: NarrativeContent) -> str:
    """Project NarrativeContent onto CommunicationContent and fingerprint it."""
    if type(content) is not NarrativeContent:
        raise TypeError("narrative_content_fingerprint requires NarrativeContent")
    projected = CommunicationContent(
        text=content.text,
        concepts=content.concepts,
        relations=tuple(
            CommunicationRelation(subject=s, predicate=p, object=o)
            for s, p, o in content.relations
        ),
    )
    return world_content_fingerprint(projected)


def _content_tokens(content: NarrativeContent) -> frozenset[str]:
    tokens = set(content.concepts)
    for subject, predicate, obj in content.relations:
        tokens.add(subject)
        tokens.add(predicate)
        tokens.add(obj)
    return frozenset(tokens)


def _token_overlap(left: NarrativeContent, right: NarrativeContent) -> float:
    left_tokens = _content_tokens(left)
    right_tokens = _content_tokens(right)
    if not left_tokens and not right_tokens:
        return 0.0
    union = left_tokens | right_tokens
    if not union:
        return 0.0
    return _quantize(len(left_tokens & right_tokens) / len(union))


@dataclass(frozen=True, slots=True)
class NarrativeEvidenceItem:
    """One observed, remembered, reconstructed, communicated, or artifact item."""

    evidence_id: str
    ordinal: int
    channel: NarrativeEvidenceChannel
    lineage_ref: str
    tick: int
    actor_id: AgentId | None = None
    predicate: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "evidence_id", _require_hex_id("evidence_id", self.evidence_id)
        )
        if isinstance(self.ordinal, bool) or type(self.ordinal) is not int:
            raise _fail("evidence.ordinal", "invalid_type")
        if self.ordinal < 0:
            raise _fail("evidence.ordinal", "out_of_range")
        if type(self.channel) is not NarrativeEvidenceChannel:
            raise _fail("evidence.channel", "unknown_channel")
        if not isinstance(self.lineage_ref, str) or not self.lineage_ref:
            raise _fail("evidence.lineage_ref", "invalid_type")
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("NarrativeEvidenceItem.tick", self.tick),
        )
        if self.actor_id is not None and type(self.actor_id) is not AgentId:
            raise _fail("evidence.actor_id", "invalid_type")
        if self.predicate is not None:
            if (
                not isinstance(self.predicate, str)
                or self.predicate not in _NARRATIVE_PREDICATES
            ):
                raise _fail("evidence.predicate", "unknown_predicate")


@dataclass(frozen=True, slots=True)
class NarrativeUtterancePlan:
    """Relation recipe the planner may place on an existing talk future."""

    subject: str
    object: str
    predicate: str
    source_basis: CommunicationSourceBasis
    content_fingerprint: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "subject",
            _require_token("utterance.subject", self.subject),
        )
        object.__setattr__(
            self,
            "object",
            _require_token("utterance.object", self.object),
        )
        if self.predicate not in _NARRATIVE_PREDICATES:
            raise _fail("utterance.predicate", "unknown_predicate")
        if type(self.source_basis) is not CommunicationSourceBasis:
            raise _fail("utterance.source_basis", "unsupported_basis")
        if self.source_basis is CommunicationSourceBasis.BELIEF:
            raise _fail("utterance.source_basis", "unsupported_basis")
        # DIRECT_OBSERVATION does not exist; reject any unknown string path.
        object.__setattr__(
            self,
            "content_fingerprint",
            _require_hex_id("utterance.content_fingerprint", self.content_fingerprint),
        )


@dataclass(frozen=True, slots=True)
class NarrativeVariant:
    """One owner's private recurring story claim with lineage."""

    variant_id: str
    owner_id: AgentId
    content: NarrativeContent
    content_fingerprint: str
    origin: NarrativeOrigin
    status: NarrativeStatus
    strength: float
    repetition_count: int = 0
    first_tick: int | None = None
    last_tick: int | None = None
    last_utterance_tick: int | None = None
    mutation_generation: int = 0
    parent_variant_ids: tuple[str, ...] = ()
    merged_into_id: str | None = None
    competing_variant_ids: tuple[str, ...] = ()
    evidence: tuple[NarrativeEvidenceItem, ...] = ()
    source_event_id: str | None = None
    source_memory_id: str | None = None
    reconstruction_id: str | None = None
    transmission_root_id: str | None = None
    last_communication_id: str | None = None
    location_ids: tuple[str, ...] = ()
    carrier_agent_ids: tuple[str, ...] = ()
    notices: tuple[str, ...] = ()
    declared_source_basis: CommunicationSourceBasis | None = None
    source_witnesses: tuple[NarrativeWitness, ...] = ()
    declared_source_entity_ids: tuple[str, ...] = ()
    declared_hop_count: int = 0
    first_hand: bool = False
    record_refs: tuple[NarrativeRecordRef, ...] = ()
    transitions: tuple[NarrativeTransition, ...] = ()
    source_loss: NarrativeSourceLoss | None = None
    themes: tuple[NarrativeTheme, ...] = ()
    theme_basis: NarrativeThemeBasis = NarrativeThemeBasis.UNCLASSIFIED

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "variant_id", _require_hex_id("variant_id", self.variant_id)
        )
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        if type(self.content) is not NarrativeContent:
            raise _fail("content", "invalid_type")
        object.__setattr__(
            self,
            "content_fingerprint",
            _require_hex_id("content_fingerprint", self.content_fingerprint),
        )
        expected_fp = narrative_content_fingerprint(self.content)
        if self.content_fingerprint != expected_fp:
            raise _fail("content_fingerprint", "id_mismatch")
        if type(self.origin) is not NarrativeOrigin:
            raise _fail("origin", "unknown_origin")
        if type(self.status) is not NarrativeStatus:
            raise _fail("status", "unknown_status")
        strength = _finite("strength", self.strength)
        quantized = _quantize(strength)
        if quantized < 0.0 or quantized > 1.0:
            raise _fail("strength", "out_of_range")
        object.__setattr__(self, "strength", quantized)
        if (
            isinstance(self.repetition_count, bool)
            or type(self.repetition_count) is not int
        ):
            raise _fail("repetition_count", "invalid_type")
        if self.repetition_count < 0:
            raise _fail("repetition_count", "out_of_range")
        if (
            isinstance(self.mutation_generation, bool)
            or type(self.mutation_generation) is not int
        ):
            raise _fail("mutation_generation", "invalid_type")
        if self.mutation_generation < 0:
            raise _fail("mutation_generation", "out_of_range")
        parents = _require_tuple("parent_variant_ids", self.parent_variant_ids)
        checked_parents: list[str] = []
        seen_parents: set[str] = set()
        for item in parents:
            head = _require_hex_id("parent_variant_ids", item)
            if head == self.variant_id:
                raise _fail("parent_variant_ids", "self_parent")
            if head in seen_parents:
                raise _fail("parent_variant_ids", "duplicate_parent")
            seen_parents.add(head)
            checked_parents.append(head)
        if len(checked_parents) > _MAX_PARENTS:
            raise _fail("parent_variant_ids", "cap_exceeded")
        if self.status is NarrativeStatus.MERGED and self.merged_into_id is None:
            raise _fail("merged_into_id", "merged_requires_target")
        if self.merged_into_id is not None:
            object.__setattr__(
                self,
                "merged_into_id",
                _require_hex_id("merged_into_id", self.merged_into_id),
            )
            if self.merged_into_id == self.variant_id:
                raise _fail("merged_into_id", "self_merge")
            if self.status is not NarrativeStatus.MERGED:
                raise _fail("status", "merged_into_requires_merged")
        competitors = _require_tuple(
            "competing_variant_ids", self.competing_variant_ids
        )
        checked_competitors: list[str] = []
        seen_competitors: set[str] = set()
        for item in competitors:
            head = _require_hex_id("competing_variant_ids", item)
            if head == self.variant_id:
                raise _fail("competing_variant_ids", "self_competitor")
            if head in seen_competitors:
                raise _fail("competing_variant_ids", "duplicate_competitor")
            seen_competitors.add(head)
            checked_competitors.append(head)
        if len(checked_competitors) > _MAX_COMPETITORS:
            raise _fail("competing_variant_ids", "cap_exceeded")
        evidence = _require_tuple("evidence", self.evidence)
        checked_evidence: list[NarrativeEvidenceItem] = []
        seen_ids: set[str] = set()
        for item in evidence:
            if type(item) is not NarrativeEvidenceItem:
                raise _fail("evidence", "invalid_type")
            if item.evidence_id in seen_ids:
                raise _fail("evidence", "duplicate_evidence")
            seen_ids.add(item.evidence_id)
            checked_evidence.append(item)
        if len(checked_evidence) > _MAX_EVIDENCE:
            raise _fail("evidence", "cap_exceeded")
        for field_name in (
            "source_event_id",
            "source_memory_id",
            "reconstruction_id",
            "transmission_root_id",
            "last_communication_id",
        ):
            value = getattr(self, field_name)
            if value is not None and (not isinstance(value, str) or not value):
                raise _fail(field_name, "invalid_type")
        locations = _require_tuple("location_ids", self.location_ids)
        checked_locations: list[str] = []
        for item in locations:
            if not isinstance(item, str) or not item:
                raise _fail("location_ids", "invalid_type")
            if item not in checked_locations:
                checked_locations.append(item)
        if len(checked_locations) > _MAX_LOCATIONS:
            raise _fail("location_ids", "cap_exceeded")
        carriers = _require_tuple("carrier_agent_ids", self.carrier_agent_ids)
        checked_carriers: list[str] = []
        for item in carriers:
            if not isinstance(item, str) or not item:
                raise _fail("carrier_agent_ids", "invalid_type")
            if item not in checked_carriers:
                checked_carriers.append(item)
        if len(checked_carriers) > _MAX_CARRIERS:
            raise _fail("carrier_agent_ids", "cap_exceeded")
        if self.first_tick is not None:
            object.__setattr__(
                self,
                "first_tick",
                require_exact_nonneg_int(
                    "NarrativeVariant.first_tick", self.first_tick
                ),
            )
        if self.last_tick is not None:
            object.__setattr__(
                self,
                "last_tick",
                require_exact_nonneg_int("NarrativeVariant.last_tick", self.last_tick),
            )
        if (
            self.first_tick is not None
            and self.last_tick is not None
            and self.last_tick < self.first_tick
        ):
            raise _fail("last_tick", "before_first_tick")
        if self.last_utterance_tick is not None:
            object.__setattr__(
                self,
                "last_utterance_tick",
                require_exact_nonneg_int(
                    "NarrativeVariant.last_utterance_tick", self.last_utterance_tick
                ),
            )
        if (
            self.declared_source_basis is not None
            and type(self.declared_source_basis) is not CommunicationSourceBasis
        ):
            raise _fail("declared_source_basis", "unsupported_basis")
        notices = _require_tuple("notices", self.notices)
        checked_notices: list[str] = []
        for item in notices:
            if not isinstance(item, str) or item not in _NOTICE_REASONS:
                raise _fail("notices", "invalid_notice")
            if item not in checked_notices:
                checked_notices.append(item)
        witnesses = _require_tuple("source_witnesses", self.source_witnesses)
        checked_witnesses: list[NarrativeWitness] = []
        seen_witness_agents: set[str] = set()
        for item in witnesses:
            if type(item) is not NarrativeWitness:
                raise _fail("source_witnesses", "invalid_type")
            agent_value = item.witness_agent_id.value
            if agent_value in seen_witness_agents:
                raise _fail("source_witnesses", "duplicate_witness")
            seen_witness_agents.add(agent_value)
            checked_witnesses.append(item)
        if len(checked_witnesses) > _MAX_WITNESSES:
            raise _fail("source_witnesses", "cap_exceeded")
        if self.first_hand:
            if not any(
                item.kind is NarrativeWitnessKind.FIRST_HAND
                for item in checked_witnesses
            ):
                raise _fail("first_hand", "requires_first_hand_witness")
        elif any(
            item.kind is NarrativeWitnessKind.FIRST_HAND
            for item in checked_witnesses
        ):
            raise _fail("first_hand", "first_hand_witness_without_flag")
        declared_ids = _require_tuple(
            "declared_source_entity_ids", self.declared_source_entity_ids
        )
        checked_declared: list[str] = []
        for item in declared_ids:
            value = _require_text("declared_source_entity_ids", item)
            if value not in checked_declared:
                checked_declared.append(value)
        if len(checked_declared) > _MAX_DECLARED_CHAIN:
            raise _fail("declared_source_entity_ids", "cap_exceeded")
        hop_count = _require_nonneg_int(
            "declared_hop_count", self.declared_hop_count
        )
        if hop_count > _MAX_DECLARED_CHAIN:
            raise _fail("declared_hop_count", "cap_exceeded")
        if type(self.first_hand) is not bool:
            raise _fail("first_hand", "invalid_type")
        records = _require_tuple("record_refs", self.record_refs)
        checked_records: list[NarrativeRecordRef] = []
        seen_records: set[tuple[str, int, str]] = set()
        for item in records:
            if type(item) is not NarrativeRecordRef:
                raise _fail("record_refs", "invalid_type")
            dedup = (item.record_id, item.observed_revision, item.role.value)
            if dedup in seen_records:
                raise _fail("record_refs", "duplicate_record")
            seen_records.add(dedup)
            checked_records.append(item)
        if len(checked_records) > _MAX_RECORDS:
            raise _fail("record_refs", "cap_exceeded")
        transitions = _require_tuple("transitions", self.transitions)
        checked_transitions: list[NarrativeTransition] = []
        seen_transition_ids: set[str] = set()
        for item in transitions:
            if type(item) is not NarrativeTransition:
                raise _fail("transitions", "invalid_type")
            if item.transition_id in seen_transition_ids:
                raise _fail("transitions", "duplicate_transition")
            seen_transition_ids.add(item.transition_id)
            if self.variant_id in item.parent_variant_ids:
                raise _fail("transitions", "self_parent")
            checked_transitions.append(item)
        if len(checked_transitions) > _MAX_TRANSITIONS:
            raise _fail("transitions", "cap_exceeded")
        source_loss = self.source_loss
        if source_loss is not None:
            if type(source_loss) is not NarrativeSourceLoss:
                raise _fail("source_loss", "invalid_type")
            if (
                source_loss.tick is not None
                and self.first_tick is not None
                and source_loss.tick < self.first_tick
            ):
                raise _fail("source_loss.tick", "before_first_tick")
            first_hand_witnesses = [
                item
                for item in checked_witnesses
                if item.kind is NarrativeWitnessKind.FIRST_HAND
            ]
            dead_count = sum(
                1
                for item in first_hand_witnesses
                if item.death_observed_tick is not None
            )
            if source_loss.known_witness_count != len(first_hand_witnesses):
                raise _fail(
                    "source_loss.known_witness_count", "count_mismatch"
                )
            if source_loss.dead_witness_count != dead_count:
                raise _fail(
                    "source_loss.dead_witness_count", "count_mismatch"
                )
        themes = _require_tuple("themes", self.themes)
        checked_themes: list[NarrativeTheme] = []
        for item in themes:
            if type(item) is not NarrativeTheme:
                raise _fail("themes", "unknown_theme")
            if item in checked_themes:
                raise _fail("themes", "duplicate_theme")
            checked_themes.append(item)
        if len(checked_themes) > _MAX_THEMES:
            raise _fail("themes", "cap_exceeded")
        if (
            NarrativeTheme.UNCLASSIFIED in checked_themes
            and len(checked_themes) > 1
        ):
            raise _fail("themes", "unclassified_mixed")
        if checked_themes != sorted(checked_themes, key=_THEME_RANK.__getitem__):
            raise _fail("themes", "unordered")
        if type(self.theme_basis) is not NarrativeThemeBasis:
            raise _fail("theme_basis", "unknown_theme_basis")
        theme_tuple = tuple(checked_themes)
        if self.theme_basis is NarrativeThemeBasis.UNCLASSIFIED:
            if theme_tuple not in {(), (NarrativeTheme.UNCLASSIFIED,)}:
                raise _fail("theme_basis", "unclassified_with_themes")
        elif theme_tuple == (NarrativeTheme.UNCLASSIFIED,):
            raise _fail("theme_basis", "classified_basis_with_unclassified")
        object.__setattr__(self, "source_witnesses", tuple(checked_witnesses))
        object.__setattr__(
            self, "declared_source_entity_ids", tuple(checked_declared)
        )
        object.__setattr__(self, "declared_hop_count", hop_count)
        object.__setattr__(self, "record_refs", tuple(checked_records))
        object.__setattr__(self, "transitions", tuple(checked_transitions))
        object.__setattr__(self, "themes", tuple(checked_themes))
        object.__setattr__(self, "parent_variant_ids", tuple(checked_parents))
        object.__setattr__(self, "competing_variant_ids", tuple(checked_competitors))
        object.__setattr__(self, "evidence", tuple(checked_evidence))
        object.__setattr__(self, "location_ids", tuple(checked_locations))
        object.__setattr__(self, "carrier_agent_ids", tuple(checked_carriers))
        object.__setattr__(self, "notices", tuple(checked_notices))


@dataclass(frozen=True, slots=True)
class NarrativeLedger:
    """Private narrative variants for one owner. ``None`` means the mode is off."""

    owner_id: AgentId
    variants: tuple[NarrativeVariant, ...] = ()
    notices: tuple[str, ...] = ()
    utterance_plans: tuple[NarrativeUtterancePlan, ...] = ()
    policy_version: str = CULTURAL_NARRATIVE_POLICY_VERSION

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        if self.policy_version not in {
            CULTURAL_NARRATIVE_POLICY_VERSION,
            CULTURAL_NARRATIVE_POLICY_VERSION_V2,
        }:
            raise _fail("policy_version", "unsupported_policy")
        variants = _require_tuple("variants", self.variants)
        checked: list[NarrativeVariant] = []
        seen: set[str] = set()
        for item in variants:
            if type(item) is not NarrativeVariant:
                raise _fail("variants", "invalid_type")
            if item.owner_id != self.owner_id:
                raise _fail("variants.owner_id", "owner_mismatch")
            if item.variant_id in seen:
                raise _fail("variants", "duplicate_variant")
            if self.policy_version == CULTURAL_NARRATIVE_POLICY_VERSION:
                if (
                    item.source_witnesses
                    or item.declared_source_entity_ids
                    or item.declared_hop_count
                    or item.first_hand
                    or item.record_refs
                    or item.transitions
                    or item.source_loss is not None
                    or item.themes
                    or item.theme_basis is not NarrativeThemeBasis.UNCLASSIFIED
                ):
                    raise _fail("policy_version", "v1_with_v2_fields")
            seen.add(item.variant_id)
            checked.append(item)
        if len(checked) > _MAX_VARIANTS:
            raise _fail("variants", "cap_exceeded")
        notices = _require_tuple("notices", self.notices)
        checked_notices: list[str] = []
        for item in notices:
            if not isinstance(item, str) or item not in _NOTICE_REASONS:
                raise _fail("notices", "invalid_notice")
            if item not in checked_notices:
                checked_notices.append(item)
        plans = _require_tuple("utterance_plans", self.utterance_plans)
        for item in plans:
            if type(item) is not NarrativeUtterancePlan:
                raise _fail("utterance_plans", "invalid_type")
        object.__setattr__(self, "variants", tuple(checked))
        object.__setattr__(self, "notices", tuple(checked_notices))
        object.__setattr__(self, "utterance_plans", tuple(plans))
        _LOG.debug(
            "narrative_ledger_constructed owner_id=%s policy_version=%s "
            "variant_count=%s",
            self.owner_id.value,
            self.policy_version,
            len(self.variants),
        )
        if self.policy_version == CULTURAL_NARRATIVE_POLICY_VERSION_V2:
            _LOG.info(
                "narrative_ledger_v2_constructed owner_id=%s variant_count=%s "
                "witness_count=%s record_count=%s transition_count=%s",
                self.owner_id.value,
                len(self.variants),
                sum(len(item.source_witnesses) for item in self.variants),
                sum(len(item.record_refs) for item in self.variants),
                sum(len(item.transitions) for item in self.variants),
            )


@dataclass(frozen=True, slots=True)
class NarrativeRecordCue:
    """Duck-typed owner-observed record cue built only by CognitiveLoop."""

    record_id: str
    observed_revision: int
    source_tick: int
    distorted: bool = False
    copy_generation: int | None = None
    integrity: str | None = None
    annotation_revisions: int | None = None
    lost_mark_count: int = 0
    concepts: tuple[str, ...] = ()
    relations: tuple[tuple[str, str, str], ...] = ()
    authored: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "record_id",
            _require_text("record_cue.record_id", self.record_id),
        )
        object.__setattr__(
            self,
            "observed_revision",
            _require_nonneg_int(
                "record_cue.observed_revision", self.observed_revision
            ),
        )
        object.__setattr__(
            self,
            "source_tick",
            _require_nonneg_int("record_cue.source_tick", self.source_tick),
        )
        if type(self.distorted) is not bool:
            raise _fail("record_cue.distorted", "invalid_type")
        object.__setattr__(
            self,
            "copy_generation",
            _require_optional_nonneg_int(
                "record_cue.copy_generation", self.copy_generation
            ),
        )
        object.__setattr__(
            self,
            "integrity",
            _require_optional_text("record_cue.integrity", self.integrity),
        )
        object.__setattr__(
            self,
            "annotation_revisions",
            _require_optional_nonneg_int(
                "record_cue.annotation_revisions", self.annotation_revisions
            ),
        )
        object.__setattr__(
            self,
            "lost_mark_count",
            _require_nonneg_int(
                "record_cue.lost_mark_count", self.lost_mark_count
            ),
        )
        concepts = _require_tuple("record_cue.concepts", self.concepts)
        checked_concepts = tuple(
            _require_token("record_cue.concepts", item) for item in concepts
        )
        relations = _require_tuple("record_cue.relations", self.relations)
        checked_relations: list[tuple[str, str, str]] = []
        for item in relations:
            if (
                not isinstance(item, tuple)
                or len(item) != 3
                or any(not isinstance(part, str) for part in item)
            ):
                raise _fail("record_cue.relations", "invalid_type")
            checked_relations.append(
                (
                    _require_token("record_cue.relations", item[0]),
                    _require_token("record_cue.relations", item[1]),
                    _require_token("record_cue.relations", item[2]),
                )
            )
        object.__setattr__(self, "concepts", checked_concepts)
        object.__setattr__(self, "relations", tuple(checked_relations))
        if type(self.authored) is not bool:
            raise _fail("record_cue.authored", "invalid_type")


@dataclass(frozen=True, slots=True)
class NarrativeCueSummary:
    """Duck-typed closed cue bag built only by CognitiveLoop.

    Holds distorted artifact cue rows and optional reconstruction cue rows
    already known from prepared snapshot / retrieve-context fields. Must not
    carry ledger objects, analysis rows, or free-form prose.
    """

    distorted_artifacts: tuple[tuple[str, bool, int, int], ...] = ()
    reconstructions: tuple[_ReconstructionCueRow, ...] = ()
    records: tuple[NarrativeRecordCue, ...] = ()

    def __post_init__(self) -> None:
        artifacts = _require_tuple("distorted_artifacts", self.distorted_artifacts)
        checked_artifacts: list[tuple[str, bool, int, int]] = []
        for item in artifacts:
            if type(item).__name__ in _FORBIDDEN_CUE_TYPE_NAMES:
                _LOG.warning("narrative_cues_dropped reason=%s", "forbidden_type")
                raise TypeError("NarrativeCueSummary: forbidden_type")
            if (
                not isinstance(item, tuple)
                or len(item) != 4
                or not isinstance(item[0], str)
                or not item[0]
                or type(item[1]) is not bool
                or isinstance(item[2], bool)
                or type(item[2]) is not int
                or isinstance(item[3], bool)
                or type(item[3]) is not int
            ):
                _LOG.warning("narrative_cues_dropped reason=%s", "invalid_token")
                raise _fail("distorted_artifacts", "invalid_token")
            checked_artifacts.append((item[0], item[1], item[2], item[3]))
        reconstructions = _require_tuple("reconstructions", self.reconstructions)
        checked_reconstructions: list[_ReconstructionCueRow] = []
        for item in reconstructions:
            if type(item).__name__ in _FORBIDDEN_CUE_TYPE_NAMES:
                _LOG.warning("narrative_cues_dropped reason=%s", "forbidden_type")
                raise TypeError("NarrativeCueSummary: forbidden_type")
            if not isinstance(item, tuple) or len(item) != 4:
                _LOG.warning("narrative_cues_dropped reason=%s", "invalid_token")
                raise _fail("reconstructions", "invalid_token")
            reconstruction_id, source_memory_ids, concepts, relations = item
            if not isinstance(reconstruction_id, str) or not reconstruction_id:
                raise _fail("reconstructions", "invalid_token")
            if isinstance(source_memory_ids, (str, bytes)) or not isinstance(
                source_memory_ids, Sequence
            ):
                raise _fail("reconstructions", "invalid_token")
            mem_ids = tuple(
                mid for mid in source_memory_ids if isinstance(mid, str) and mid
            )
            if isinstance(concepts, (str, bytes)) or not isinstance(concepts, Sequence):
                raise _fail("reconstructions", "invalid_token")
            concept_tokens = tuple(
                _require_token("reconstructions.concepts", c) for c in concepts
            )
            if isinstance(relations, (str, bytes)) or not isinstance(
                relations, Sequence
            ):
                raise _fail("reconstructions", "invalid_token")
            rel_tokens: list[tuple[str, str, str]] = []
            for rel in relations:
                if (
                    not isinstance(rel, tuple)
                    or len(rel) != 3
                    or any(not isinstance(part, str) for part in rel)
                ):
                    raise _fail("reconstructions", "invalid_token")
                rel_tokens.append(
                    (
                        _require_token("reconstructions.relations", rel[0]),
                        _require_token("reconstructions.relations", rel[1]),
                        _require_token("reconstructions.relations", rel[2]),
                    )
                )
            checked_reconstructions.append(
                (
                    reconstruction_id,
                    mem_ids,
                    concept_tokens,
                    tuple(rel_tokens),
                )
            )
        records = _require_tuple("records", self.records)
        checked_records: list[NarrativeRecordCue] = []
        for item in records:
            if type(item) is not NarrativeRecordCue:
                raise _fail("records", "invalid_type")
            checked_records.append(item)
        object.__setattr__(self, "distorted_artifacts", tuple(checked_artifacts))
        object.__setattr__(self, "reconstructions", tuple(checked_reconstructions))
        object.__setattr__(self, "records", tuple(checked_records))
        _LOG.debug(
            "narrative_cues_accepted artifact_count=%s reconstruction_count=%s "
            "record_count=%s",
            len(self.distorted_artifacts),
            len(self.reconstructions),
            len(self.records),
        )


@dataclass(frozen=True, slots=True)
class CulturalNarrativePolicy:
    """Locked narrative constants. Runner JSON does not carry these weights."""

    version: str = CULTURAL_NARRATIVE_POLICY_VERSION
    active_strength: float = _ACTIVE_STRENGTH
    retire_strength: float = _RETIRE_STRENGTH
    decay: float = _DECAY
    observed_delta: float = _OBSERVED_DELTA
    remembered_delta: float = _REMEMBERED_DELTA
    communicated_delta: float = _COMMUNICATED_DELTA
    deliberate_lie_delta: float = _DELIBERATE_LIE_DELTA
    misread_artifact_delta: float = _MISREAD_ARTIFACT_DELTA
    penalty: float = _PENALTY
    promotion_count: int = _PROMOTION_COUNT
    semantic_uplift_repetitions: int = _SEMANTIC_UPLIFT_REPETITIONS
    semantic_uplift_strength: float = _SEMANTIC_UPLIFT_STRENGTH
    merge_token_overlap: float = _MERGE_TOKEN_OVERLAP
    utterance_interval: int = _UTTERANCE_INTERVAL
    max_variants: int = _MAX_VARIANTS
    max_evidence: int = _MAX_EVIDENCE
    max_carriers: int = _MAX_CARRIERS
    max_locations: int = _MAX_LOCATIONS
    max_parents: int = _MAX_PARENTS
    max_competitors: int = _MAX_COMPETITORS

    def __post_init__(self) -> None:
        if self.version != CULTURAL_NARRATIVE_POLICY_VERSION:
            raise _fail("version", "unsupported_policy")
        floats = (
            ("active_strength", _ACTIVE_STRENGTH),
            ("retire_strength", _RETIRE_STRENGTH),
            ("decay", _DECAY),
            ("observed_delta", _OBSERVED_DELTA),
            ("remembered_delta", _REMEMBERED_DELTA),
            ("communicated_delta", _COMMUNICATED_DELTA),
            ("deliberate_lie_delta", _DELIBERATE_LIE_DELTA),
            ("misread_artifact_delta", _MISREAD_ARTIFACT_DELTA),
            ("penalty", _PENALTY),
            ("semantic_uplift_strength", _SEMANTIC_UPLIFT_STRENGTH),
            ("merge_token_overlap", _MERGE_TOKEN_OVERLAP),
        )
        for name, expected in floats:
            object.__setattr__(
                self, name, _locked_float(name, getattr(self, name), expected)
            )
        counts = (
            ("promotion_count", _PROMOTION_COUNT),
            ("semantic_uplift_repetitions", _SEMANTIC_UPLIFT_REPETITIONS),
            ("utterance_interval", _UTTERANCE_INTERVAL),
            ("max_variants", _MAX_VARIANTS),
            ("max_evidence", _MAX_EVIDENCE),
            ("max_carriers", _MAX_CARRIERS),
            ("max_locations", _MAX_LOCATIONS),
            ("max_parents", _MAX_PARENTS),
            ("max_competitors", _MAX_COMPETITORS),
        )
        for name, expected in counts:
            object.__setattr__(
                self, name, _locked_int(name, getattr(self, name), expected)
            )
        _LOG.debug(
            "narrative_policy_constructed policy_version=%s variant_count=%s",
            self.version,
            0,
        )


def default_cultural_narrative_policy() -> CulturalNarrativePolicy:
    """Return the only accepted cultural-narrative policy."""
    return CulturalNarrativePolicy()


@dataclass(frozen=True, slots=True)
class GenerationalNarrativePolicy(CulturalNarrativePolicy):
    """V2 policy: v1 constants plus witness/record/theme provenance caps."""

    version: str = CULTURAL_NARRATIVE_POLICY_VERSION_V2
    record_read_delta: float = _RECORD_READ_DELTA
    max_witnesses: int = _MAX_WITNESSES
    max_records: int = _MAX_RECORDS
    max_transitions: int = _MAX_TRANSITIONS
    max_declared_chain: int = _MAX_DECLARED_CHAIN

    def __post_init__(self) -> None:
        if self.version != CULTURAL_NARRATIVE_POLICY_VERSION_V2:
            raise _fail("version", "unsupported_policy")
        floats = (
            ("active_strength", _ACTIVE_STRENGTH),
            ("retire_strength", _RETIRE_STRENGTH),
            ("decay", _DECAY),
            ("observed_delta", _OBSERVED_DELTA),
            ("remembered_delta", _REMEMBERED_DELTA),
            ("communicated_delta", _COMMUNICATED_DELTA),
            ("deliberate_lie_delta", _DELIBERATE_LIE_DELTA),
            ("misread_artifact_delta", _MISREAD_ARTIFACT_DELTA),
            ("penalty", _PENALTY),
            ("semantic_uplift_strength", _SEMANTIC_UPLIFT_STRENGTH),
            ("merge_token_overlap", _MERGE_TOKEN_OVERLAP),
            ("record_read_delta", _RECORD_READ_DELTA),
        )
        for name, expected in floats:
            object.__setattr__(
                self, name, _locked_float(name, getattr(self, name), expected)
            )
        counts = (
            ("promotion_count", _PROMOTION_COUNT),
            ("semantic_uplift_repetitions", _SEMANTIC_UPLIFT_REPETITIONS),
            ("utterance_interval", _UTTERANCE_INTERVAL),
            ("max_variants", _MAX_VARIANTS),
            ("max_evidence", _MAX_EVIDENCE),
            ("max_carriers", _MAX_CARRIERS),
            ("max_locations", _MAX_LOCATIONS),
            ("max_parents", _MAX_PARENTS),
            ("max_competitors", _MAX_COMPETITORS),
            ("max_witnesses", _MAX_WITNESSES),
            ("max_records", _MAX_RECORDS),
            ("max_transitions", _MAX_TRANSITIONS),
            ("max_declared_chain", _MAX_DECLARED_CHAIN),
        )
        for name, expected in counts:
            object.__setattr__(
                self, name, _locked_int(name, getattr(self, name), expected)
            )
        _LOG.debug(
            "generational_narrative_policy_constructed policy_version=%s "
            "max_witnesses=%s max_records=%s max_transitions=%s",
            self.version,
            self.max_witnesses,
            self.max_records,
            self.max_transitions,
        )


def default_generational_narrative_policy(
    *,
    max_witnesses: int = _MAX_WITNESSES,
    max_records: int = _MAX_RECORDS,
    max_transitions: int = _MAX_TRANSITIONS,
    max_declared_chain: int = _MAX_DECLARED_CHAIN,
) -> GenerationalNarrativePolicy:
    """Return the only accepted V2 generational-narrative policy."""
    return GenerationalNarrativePolicy(
        max_witnesses=max_witnesses,
        max_records=max_records,
        max_transitions=max_transitions,
        max_declared_chain=max_declared_chain,
    )


def empty_narrative_ledger(
    owner_id: AgentId, *, policy_version: str = CULTURAL_NARRATIVE_POLICY_VERSION
) -> NarrativeLedger:
    """Ledger with no variants. Disabled mode does not call this."""
    return NarrativeLedger(owner_id=owner_id, policy_version=policy_version)


def require_owner_cultural_narratives(
    ledger: object,
    owner_id: AgentId,
    *,
    field_name: str,
) -> None:
    """Reject a foreign or mistyped ledger. ``None`` is passthrough."""
    if ledger is None:
        return
    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    if type(ledger) is not NarrativeLedger:
        _LOG.warning("narrative_carry_rejected reason=%s", "invalid_type")
        raise TypeError(f"{field_name} must be NarrativeLedger")
    if ledger.owner_id != owner_id:
        _LOG.error(
            "narrative_validation_failed field=%s reason_code=%s",
            field_name,
            "owner_mismatch",
        )
        _LOG.warning("narrative_carry_rejected reason=%s", "owner_mismatch")
        raise ValueError(f"{field_name} owner_id mismatch")


def _sign(before: float, after: float) -> str:
    if after > before:
        return "positive"
    if after < before:
        return "negative"
    return "zero"


def _notice(notices: list[str], reason: str) -> None:
    if reason not in notices:
        notices.append(reason)


def _log_drop(reason: str) -> None:
    _LOG.warning("narrative_evidence_dropped reason=%s", reason)


def _resolve_agent(
    identity: OwnerSafeSocialIdentity, entity_id: EntityId | None
) -> AgentId | None:
    if type(entity_id) is not EntityId:
        return None
    if entity_id == identity.owner_entity_id:
        return identity.owner_id
    for binding in identity.counterparts:
        if binding.entity_id == entity_id:
            return binding.agent_id
    return None


def _endpoint_token(endpoint: object) -> str | None:
    if isinstance(endpoint, str) and _TOKEN_RE.fullmatch(endpoint):
        return endpoint
    concept = getattr(endpoint, "concept", None)
    if isinstance(concept, str) and _TOKEN_RE.fullmatch(concept):
        return concept
    label = getattr(endpoint, "label", None)
    if isinstance(label, str) and _TOKEN_RE.fullmatch(label):
        return label
    value = getattr(endpoint, "value", None)
    if isinstance(value, str) and _TOKEN_RE.fullmatch(value):
        return value
    return None


@dataclass
class _VariantDraft:
    content: NarrativeContent
    content_fingerprint: str
    origin: NarrativeOrigin
    status: NarrativeStatus
    strength: float
    repetition_count: int
    first_tick: int | None
    last_tick: int | None
    last_utterance_tick: int | None
    mutation_generation: int
    parent_variant_ids: list[str]
    merged_into_id: str | None
    competing_variant_ids: list[str]
    evidence: list[NarrativeEvidenceItem]
    source_event_id: str | None
    source_memory_id: str | None
    reconstruction_id: str | None
    transmission_root_id: str | None
    last_communication_id: str | None
    location_ids: list[str]
    carrier_agent_ids: list[str]
    notices: list[str] = field(default_factory=list)
    declared_source_basis: CommunicationSourceBasis | None = None
    source_witnesses: list[NarrativeWitness] = field(default_factory=list)
    declared_source_entity_ids: list[str] = field(default_factory=list)
    declared_hop_count: int = 0
    first_hand: bool = False
    record_refs: list[NarrativeRecordRef] = field(default_factory=list)
    transitions: list[NarrativeTransition] = field(default_factory=list)
    source_loss: NarrativeSourceLoss | None = None
    themes: list[NarrativeTheme] = field(default_factory=list)
    theme_basis: NarrativeThemeBasis = NarrativeThemeBasis.UNCLASSIFIED
    founding_fingerprint: str = ""
    parent_salt: str = ""
    touched: bool = False
    variant_id_override: str | None = None


def _recover_founding_fingerprint(
    variant: NarrativeVariant,
    by_id: Mapping[str, NarrativeVariant],
    *,
    _seen: frozenset[str] | None = None,
) -> str:
    """Recover founding content fingerprint via parent walk after freeze."""
    seen = frozenset() if _seen is None else _seen
    if variant.mutation_generation == 0 or not variant.parent_variant_ids:
        return variant.content_fingerprint
    roots: list[str] = []
    for parent_id in variant.parent_variant_ids:
        if parent_id in seen:
            continue
        parent = by_id.get(parent_id)
        if parent is None:
            continue
        roots.append(
            _recover_founding_fingerprint(
                parent, by_id, _seen=seen | {variant.variant_id, parent_id}
            )
        )
    if roots:
        return sorted(roots)[0]
    return variant.content_fingerprint


def _drafts_from(
    previous: NarrativeLedger | None, owner_id: AgentId
) -> list[_VariantDraft]:
    drafts: list[_VariantDraft] = []
    if previous is None:
        return drafts
    if previous.owner_id != owner_id:
        _LOG.error(
            "narrative_validation_failed field=%s reason_code=%s",
            "owner_id",
            "owner_mismatch",
        )
        raise ValueError("owner_id: owner_mismatch")
    by_id = {variant.variant_id: variant for variant in previous.variants}
    for variant in previous.variants:
        drafts.append(
            _VariantDraft(
                content=variant.content,
                content_fingerprint=variant.content_fingerprint,
                origin=variant.origin,
                status=variant.status,
                strength=variant.strength,
                repetition_count=variant.repetition_count,
                first_tick=variant.first_tick,
                last_tick=variant.last_tick,
                last_utterance_tick=variant.last_utterance_tick,
                mutation_generation=variant.mutation_generation,
                parent_variant_ids=list(variant.parent_variant_ids),
                merged_into_id=variant.merged_into_id,
                competing_variant_ids=list(variant.competing_variant_ids),
                evidence=list(variant.evidence),
                source_event_id=variant.source_event_id,
                source_memory_id=variant.source_memory_id,
                reconstruction_id=variant.reconstruction_id,
                transmission_root_id=variant.transmission_root_id,
                last_communication_id=variant.last_communication_id,
                location_ids=list(variant.location_ids),
                carrier_agent_ids=list(variant.carrier_agent_ids),
                notices=list(variant.notices),
                declared_source_basis=variant.declared_source_basis,
                source_witnesses=list(variant.source_witnesses),
                declared_source_entity_ids=list(
                    variant.declared_source_entity_ids
                ),
                declared_hop_count=variant.declared_hop_count,
                first_hand=variant.first_hand,
                record_refs=list(variant.record_refs),
                transitions=list(variant.transitions),
                source_loss=variant.source_loss,
                themes=list(variant.themes),
                theme_basis=variant.theme_basis,
                founding_fingerprint=_recover_founding_fingerprint(variant, by_id),
                parent_salt="|".join(variant.parent_variant_ids),
                variant_id_override=variant.variant_id,
            )
        )
    return drafts


def _find_by_fingerprint(
    drafts: list[_VariantDraft], fingerprint: str
) -> _VariantDraft | None:
    for draft in drafts:
        if (
            draft.content_fingerprint == fingerprint
            and draft.merged_into_id is None
            and draft.status is not NarrativeStatus.RETIRED
            and draft.status is not NarrativeStatus.MERGED
        ):
            return draft
    return None


def _draft_variant_id(owner_id: AgentId, draft: _VariantDraft) -> str:
    if draft.variant_id_override is not None:
        return draft.variant_id_override
    founding = draft.founding_fingerprint or draft.content_fingerprint
    return narrative_variant_id(
        owner_id,
        founding,
        draft.mutation_generation,
        draft.parent_salt,
    )


def _append_location(
    draft: _VariantDraft, location_id: str | None, notices: list[str]
) -> None:
    if location_id is None:
        return
    if location_id in draft.location_ids:
        return
    if len(draft.location_ids) >= _MAX_LOCATIONS:
        _notice(notices, "cap_exceeded")
        _log_drop("cap_exceeded")
        return
    draft.location_ids.append(location_id)


def _append_carrier(
    draft: _VariantDraft, agent_id: AgentId | None, notices: list[str]
) -> None:
    if agent_id is None:
        return
    value = agent_id.value
    if value in draft.carrier_agent_ids:
        return
    if len(draft.carrier_agent_ids) >= _MAX_CARRIERS:
        _notice(notices, "cap_exceeded")
        _log_drop("cap_exceeded")
        return
    draft.carrier_agent_ids.append(value)


_THEME_BY_OCCURRENCE_KIND: Final[dict[str, tuple[NarrativeTheme, ...]]] = {
    "agent_entered_world": (NarrativeTheme.FOUNDERS,),
    "agent_created": (NarrativeTheme.FOUNDERS,),
    "agent_initialization_recorded": (NarrativeTheme.FOUNDERS,),
    "died": (NarrativeTheme.DISASTERS,),
    "exposure_applied": (NarrativeTheme.DISASTERS,),
    "environmental_hazard_started": (NarrativeTheme.DISASTERS,),
    "resource_node_depleted": (NarrativeTheme.DISASTERS,),
    "artifact_destroyed": (NarrativeTheme.DISASTERS,),
    "artifact_damaged": (NarrativeTheme.DISASTERS,),
    "artifact_partially_lost": (NarrativeTheme.DISASTERS,),
    "attack": (NarrativeTheme.CONFLICTS,),
    "flee": (NarrativeTheme.CONFLICTS,),
    "move": (NarrativeTheme.MIGRATIONS,),
    "transport": (NarrativeTheme.MIGRATIONS,),
    "journey_started": (NarrativeTheme.MIGRATIONS,),
    "journey_arrived": (NarrativeTheme.MIGRATIONS,),
    "journey_ended": (NarrativeTheme.MIGRATIONS,),
    "experiment_resolved": (
        NarrativeTheme.DISCOVERIES,
        NarrativeTheme.INNOVATIONS,
    ),
    "craft_started": (NarrativeTheme.INNOVATIONS,),
    "item_crafted": (NarrativeTheme.INNOVATIONS,),
    "structure_built": (NarrativeTheme.INNOVATIONS,),
    "structure_repaired": (NarrativeTheme.INNOVATIONS,),
    "resource_harvested": (NarrativeTheme.DISCOVERIES,),
    "repository_established": (NarrativeTheme.DISCOVERIES,),
}
_DEATH_OCCURRENCE_KINDS: Final[frozenset[str]] = frozenset({"died"})
_DAMAGED_RECORD_ROLES: Final[frozenset[NarrativeRecordRole]] = frozenset(
    {
        NarrativeRecordRole.DAMAGED,
        NarrativeRecordRole.PARTIALLY_LOST,
    }
)
_DESTROYED_RECORD_ROLES: Final[frozenset[NarrativeRecordRole]] = frozenset(
    {NarrativeRecordRole.DESTROYED}
)


def _is_v2_policy(
    policy: object,
) -> TypeGuard[GenerationalNarrativePolicy]:
    return type(policy) is GenerationalNarrativePolicy


def _theme_set(
    themes: list[NarrativeTheme],
    additions: tuple[NarrativeTheme, ...],
    *,
    cap: int = _MAX_THEMES,
) -> None:
    if not additions:
        return
    if NarrativeTheme.UNCLASSIFIED in themes:
        themes.clear()
    for theme in additions:
        if theme is NarrativeTheme.UNCLASSIFIED:
            continue
        if theme not in themes:
            themes.append(theme)
    themes.sort(key=_THEME_RANK.__getitem__)
    del themes[cap:]


def _append_transition(
    *,
    draft: _VariantDraft,
    owner_id: AgentId,
    kind: NarrativeTransitionKind,
    tick: int,
    reference: str,
    policy: GenerationalNarrativePolicy,
    carrier_agent_id: AgentId | None = None,
    record_id: str | None = None,
    hop_index: int | None = None,
    parent_variant_ids: tuple[str, ...] = (),
) -> None:
    variant_id = _draft_variant_id(owner_id, draft)
    transition_id = narrative_transition_id(
        owner_id, variant_id, kind, tick, reference
    )
    if any(item.transition_id == transition_id for item in draft.transitions):
        return
    if len(draft.transitions) >= policy.max_transitions:
        return
    draft.transitions.append(
        NarrativeTransition(
            transition_id=transition_id,
            kind=kind,
            tick=tick,
            parent_variant_ids=parent_variant_ids,
            carrier_agent_id=carrier_agent_id,
            record_id=record_id,
            hop_index=hop_index,
        )
    )


def _add_witness(
    *,
    draft: _VariantDraft,
    owner_id: AgentId,
    witness_agent_id: AgentId,
    kind: NarrativeWitnessKind,
    hop_index: int,
    tick: int,
    policy: GenerationalNarrativePolicy,
) -> bool:
    for index, existing in enumerate(draft.source_witnesses):
        if existing.witness_agent_id != witness_agent_id:
            continue
        if (
            existing.kind is kind
            and existing.hop_index == hop_index
            and existing.last_seen_tick >= tick
        ):
            return False
        if (
            existing.kind is NarrativeWitnessKind.FIRST_HAND
            and kind is not NarrativeWitnessKind.FIRST_HAND
        ):
            return False
        draft.source_witnesses[index] = NarrativeWitness(
            witness_agent_id=witness_agent_id,
            kind=kind,
            hop_index=hop_index,
            first_seen_tick=existing.first_seen_tick,
            last_seen_tick=max(existing.last_seen_tick, tick),
            death_observed_tick=existing.death_observed_tick,
        )
        return True
    if len(draft.source_witnesses) >= policy.max_witnesses:
        return False
    draft.source_witnesses.append(
        NarrativeWitness(
            witness_agent_id=witness_agent_id,
            kind=kind,
            hop_index=hop_index,
            first_seen_tick=tick,
            last_seen_tick=tick,
        )
    )
    return True


def _record_is_intact(record: NarrativeRecordRef) -> bool:
    if record.role in _DAMAGED_RECORD_ROLES | _DESTROYED_RECORD_ROLES:
        return False
    integrity = None if record.integrity is None else record.integrity.lower()
    return integrity not in {
        "damaged",
        "partial",
        "partially_lost",
        "destroyed",
        "lost",
    }


def _record_is_damaged(record: NarrativeRecordRef) -> bool:
    if record.role in _DAMAGED_RECORD_ROLES:
        return True
    integrity = None if record.integrity is None else record.integrity.lower()
    return integrity in {"damaged", "partial", "partially_lost"}


def _record_is_destroyed(record: NarrativeRecordRef) -> bool:
    if record.role in _DESTROYED_RECORD_ROLES:
        return True
    integrity = None if record.integrity is None else record.integrity.lower()
    return integrity in {"destroyed", "lost"}


def _record_on_draft(
    *,
    draft: _VariantDraft,
    owner_id: AgentId,
    delta: float,
    channel: NarrativeEvidenceChannel,
    lineage_ref: str,
    tick: int,
    policy: CulturalNarrativePolicy,
    notices: list[str],
    seen: set[tuple[str, str, str]],
    actor_id: AgentId | None = None,
    predicate: str | None = None,
    origin: NarrativeOrigin | None = None,
) -> None:
    dedup = (draft.content_fingerprint, channel.value, lineage_ref)
    if dedup in seen:
        return
    seen.add(dedup)
    if any(item.lineage_ref == lineage_ref for item in draft.evidence):
        return
    if len(draft.evidence) >= policy.max_evidence:
        _notice(notices, "cap_exceeded")
        _log_drop("cap_exceeded")
        return
    before = draft.strength
    if before == 0.0 and channel is NarrativeEvidenceChannel.OBSERVED:
        draft.strength = _apply_delta(0.0, max(delta, policy.active_strength))
    else:
        draft.strength = _apply_delta(before, delta)
    draft.repetition_count += 1
    if draft.first_tick is None:
        draft.first_tick = tick
    draft.last_tick = tick
    draft.touched = True
    if origin is not None and draft.repetition_count == 1:
        draft.origin = origin
    variant_id = _draft_variant_id(owner_id, draft)
    ordinal = len(draft.evidence)
    draft.evidence.append(
        NarrativeEvidenceItem(
            evidence_id=narrative_evidence_id(
                variant_id, ordinal, channel, lineage_ref
            ),
            ordinal=ordinal,
            channel=channel,
            lineage_ref=lineage_ref,
            tick=tick,
            actor_id=actor_id,
            predicate=predicate,
        )
    )
    _LOG.debug(
        "narrative_variant_applied owner_id=%s tick=%s origin=%s sign=%s",
        owner_id.value,
        tick,
        draft.origin.value,
        _sign(before, draft.strength),
    )


def _mint_variant(
    *,
    drafts: list[_VariantDraft],
    notices: list[str],
    owner_id: AgentId,
    content: NarrativeContent,
    origin: NarrativeOrigin,
    delta: float,
    channel: NarrativeEvidenceChannel,
    lineage_ref: str,
    tick: int,
    policy: CulturalNarrativePolicy,
    seen: set[tuple[str, str, str]],
    source_event_id: str | None = None,
    source_memory_id: str | None = None,
    reconstruction_id: str | None = None,
    transmission_root_id: str | None = None,
    last_communication_id: str | None = None,
    location_id: str | None = None,
    carrier: AgentId | None = None,
    actor_id: AgentId | None = None,
    predicate: str | None = None,
    parent_variant_ids: tuple[str, ...] = (),
    mutation_generation: int = 0,
    founding_fingerprint: str | None = None,
    declared_source_basis: CommunicationSourceBasis | None = None,
) -> _VariantDraft | None:
    fingerprint = narrative_content_fingerprint(content)
    existing = _find_by_fingerprint(drafts, fingerprint)
    if existing is not None:
        _record_on_draft(
            draft=existing,
            owner_id=owner_id,
            delta=delta,
            channel=channel,
            lineage_ref=lineage_ref,
            tick=tick,
            policy=policy,
            notices=notices,
            seen=seen,
            actor_id=actor_id,
            predicate=predicate,
        )
        _append_location(existing, location_id, notices)
        _append_carrier(existing, carrier, notices)
        if source_event_id and existing.source_event_id is None:
            existing.source_event_id = source_event_id
        if source_memory_id and existing.source_memory_id is None:
            existing.source_memory_id = source_memory_id
        if last_communication_id:
            existing.last_communication_id = last_communication_id
        if transmission_root_id and existing.transmission_root_id is None:
            existing.transmission_root_id = transmission_root_id
        return existing
    if len(drafts) >= policy.max_variants:
        _notice(notices, "cap_exceeded")
        _log_drop("cap_exceeded")
        return None
    parent_salt = "|".join(parent_variant_ids)
    founding = founding_fingerprint or fingerprint
    draft = _VariantDraft(
        content=content,
        content_fingerprint=fingerprint,
        origin=origin,
        status=NarrativeStatus.CANDIDATE,
        strength=0.0,
        repetition_count=0,
        first_tick=tick,
        last_tick=tick,
        last_utterance_tick=None,
        mutation_generation=mutation_generation,
        parent_variant_ids=list(parent_variant_ids),
        merged_into_id=None,
        competing_variant_ids=[],
        evidence=[],
        source_event_id=source_event_id,
        source_memory_id=source_memory_id,
        reconstruction_id=reconstruction_id,
        transmission_root_id=transmission_root_id,
        last_communication_id=last_communication_id,
        location_ids=[],
        carrier_agent_ids=[],
        founding_fingerprint=founding,
        parent_salt=parent_salt,
        declared_source_basis=declared_source_basis,
    )
    drafts.append(draft)
    _record_on_draft(
        draft=draft,
        owner_id=owner_id,
        delta=delta,
        channel=channel,
        lineage_ref=lineage_ref,
        tick=tick,
        policy=policy,
        notices=notices,
        seen=seen,
        actor_id=actor_id,
        predicate=predicate,
        origin=origin,
    )
    _append_location(draft, location_id, notices)
    _append_carrier(draft, carrier, notices)
    return draft


def _content_from_occurrence(occurrence: ObservedOccurrence) -> NarrativeContent | None:
    concepts: list[str] = []
    kind = occurrence.kind
    if isinstance(kind, str) and _TOKEN_RE.fullmatch(kind):
        concepts.append(kind)
    for key, value in (occurrence.public_facts or {}).items():
        if isinstance(key, str) and _TOKEN_RE.fullmatch(key):
            concepts.append(key)
        if isinstance(value, str) and _TOKEN_RE.fullmatch(value):
            concepts.append(value)
    concepts = list(dict.fromkeys(concepts))
    if not concepts:
        return None
    try:
        return NarrativeContent(concepts=tuple(concepts), text="tell_story")
    except ValueError:
        return None


def _content_from_utterance(
    communication: ObservedCommunication, *, text: str
) -> NarrativeContent | None:
    content = communication.utterance.content
    concepts = tuple(
        c for c in content.concepts if isinstance(c, str) and _TOKEN_RE.fullmatch(c)
    )
    relations: list[tuple[str, str, str]] = []
    for relation in content.relations:
        subject = getattr(relation, "subject", None)
        predicate = getattr(relation, "predicate", None)
        obj = getattr(relation, "object", None)
        if (
            isinstance(subject, str)
            and isinstance(predicate, str)
            and isinstance(obj, str)
            and _TOKEN_RE.fullmatch(subject)
            and _TOKEN_RE.fullmatch(predicate)
            and _TOKEN_RE.fullmatch(obj)
        ):
            relations.append((subject, predicate, obj))
    if not concepts and not relations:
        return None
    try:
        return NarrativeContent(
            concepts=concepts, relations=tuple(relations), text=text
        )
    except ValueError:
        return None


def _apply_observed_events(
    *,
    observation: Observation,
    identity: OwnerSafeSocialIdentity,
    drafts: list[_VariantDraft],
    notices: list[str],
    policy: CulturalNarrativePolicy,
    seen: set[tuple[str, str, str]],
) -> None:
    owner_id = identity.owner_id
    tick = observation.tick
    location = (
        None if observation.self_body is None else observation.self_body.location_id
    )
    location_value = None if location is None else location.value
    for index, occurrence in enumerate(observation.occurrences):
        if type(occurrence) is not ObservedOccurrence:
            continue
        content = _content_from_occurrence(occurrence)
        if content is None:
            _notice(notices, "empty_content")
            _log_drop("empty_content")
            continue
        event_id = occurrence.provenance.source_event_id
        lineage = f"tick-{tick}-{index}" if event_id is None else event_id.value
        draft = _mint_variant(
            drafts=drafts,
            notices=notices,
            owner_id=owner_id,
            content=content,
            origin=NarrativeOrigin.OBSERVED_EVENT,
            delta=policy.observed_delta,
            channel=NarrativeEvidenceChannel.OBSERVED,
            lineage_ref=lineage,
            tick=tick,
            policy=policy,
            seen=seen,
            source_event_id=None if event_id is None else event_id.value,
            location_id=location_value,
            carrier=owner_id,
        )
        if draft is None or not _is_v2_policy(policy):
            continue
        draft.first_hand = True
        _add_witness(
            draft=draft,
            owner_id=owner_id,
            witness_agent_id=owner_id,
            kind=NarrativeWitnessKind.FIRST_HAND,
            hop_index=0,
            tick=tick,
            policy=policy,
        )
        _theme_set(
            draft.themes,
            _THEME_BY_OCCURRENCE_KIND.get(occurrence.kind, ()),
        )
        if draft.themes:
            draft.theme_basis = NarrativeThemeBasis.OBSERVED_OCCURRENCE_KIND
        _append_transition(
            draft=draft,
            owner_id=owner_id,
            kind=NarrativeTransitionKind.MINTED,
            tick=tick,
            reference=lineage,
            policy=policy,
            carrier_agent_id=owner_id,
        )


def _apply_deliberate_lies(
    *,
    observation: Observation,
    identity: OwnerSafeSocialIdentity,
    drafts: list[_VariantDraft],
    notices: list[str],
    policy: CulturalNarrativePolicy,
    seen: set[tuple[str, str, str]],
) -> None:
    owner_id = identity.owner_id
    tick = observation.tick
    for index, communication in enumerate(observation.communications):
        if type(communication) is not ObservedCommunication:
            continue
        if communication.listener_id != identity.owner_entity_id:
            continue
        if communication.action_kind not in {"tell", "talk"}:
            continue
        basis = communication.utterance.declared.source_basis
        if basis is not CommunicationSourceBasis.UNREFERENCED:
            continue
        # Story predicates are handled by retell path; UNREFERENCED non-story
        # content still founds a deliberate_lie.
        predicates = {
            getattr(rel, "predicate", None)
            for rel in communication.utterance.content.relations
        }
        if predicates & _NARRATIVE_PREDICATES:
            continue
        content = _content_from_utterance(communication, text="tell_story")
        if content is None:
            _notice(notices, "empty_content")
            _log_drop("empty_content")
            continue
        speaker = _resolve_agent(identity, communication.speaker_id)
        if speaker is None:
            _notice(notices, "unresolved_entity")
            _log_drop("unresolved_entity")
            continue
        event_id = communication.provenance.source_event_id
        lineage = f"tick-{tick}-lie-{index}" if event_id is None else event_id.value
        comm_id = communication.utterance.declared.communication_id.value
        root_id = communication.utterance.declared.root_communication_id.value
        _mint_variant(
            drafts=drafts,
            notices=notices,
            owner_id=owner_id,
            content=content,
            origin=NarrativeOrigin.DELIBERATE_LIE,
            delta=policy.deliberate_lie_delta,
            channel=NarrativeEvidenceChannel.COMMUNICATED,
            lineage_ref=lineage,
            tick=tick,
            policy=policy,
            seen=seen,
            transmission_root_id=root_id,
            last_communication_id=comm_id,
            carrier=speaker,
            actor_id=speaker,
            declared_source_basis=CommunicationSourceBasis.UNREFERENCED,
        )


def _apply_cues(
    *,
    cues: NarrativeCueSummary | None,
    drafts: list[_VariantDraft],
    notices: list[str],
    owner_id: AgentId,
    tick: int,
    policy: CulturalNarrativePolicy,
    seen: set[tuple[str, str, str]],
    location_id: str | None,
) -> None:
    if cues is None:
        return
    for artifact_id, distorted, reading_count, mark_count in cues.distorted_artifacts:
        if not distorted:
            continue
        concepts: tuple[str, ...] = (
            "artifact",
            f"mark_{min(mark_count, 99)}",
            f"reading_{min(reading_count, 99)}",
        )
        try:
            content = NarrativeContent(concepts=concepts, text="tell_story")
        except ValueError:
            _notice(notices, "empty_content")
            _log_drop("empty_content")
            continue
        _mint_variant(
            drafts=drafts,
            notices=notices,
            owner_id=owner_id,
            content=content,
            origin=NarrativeOrigin.MISREAD_ARTIFACT,
            delta=policy.misread_artifact_delta,
            channel=NarrativeEvidenceChannel.ARTIFACT,
            lineage_ref=f"artifact-{artifact_id}",
            tick=tick,
            policy=policy,
            seen=seen,
            location_id=location_id,
            carrier=owner_id,
            declared_source_basis=CommunicationSourceBasis.UNREFERENCED,
        )
    for (
        reconstruction_id,
        source_memory_ids,
        concepts,
        relations,
    ) in cues.reconstructions:
        if not concepts and not relations:
            _notice(notices, "empty_content")
            _log_drop("empty_content")
            continue
        source_memory_id = source_memory_ids[0] if source_memory_ids else None
        if source_memory_id is None:
            _notice(notices, "no_memory_anchor")
            _log_drop("empty_content")
            continue
        try:
            content = NarrativeContent(
                concepts=concepts, relations=relations, text="tell_story"
            )
        except ValueError:
            _notice(notices, "empty_content")
            _log_drop("empty_content")
            continue
        fingerprint = narrative_content_fingerprint(content)
        parent = None
        for draft in drafts:
            if (
                draft.transmission_root_id is not None
                and draft.content_fingerprint != fingerprint
                and draft.status in {NarrativeStatus.ACTIVE, NarrativeStatus.CANDIDATE}
                and draft.merged_into_id is None
            ):
                # Branch only when an explicit parent link exists via shared root.
                parent = draft
                break
        if parent is not None and parent.content_fingerprint != fingerprint:
            parent_id = _draft_variant_id(owner_id, parent)
            reconstructed = _mint_variant(
                drafts=drafts,
                notices=notices,
                owner_id=owner_id,
                content=content,
                origin=NarrativeOrigin.RECONSTRUCTED_MEMORY,
                delta=policy.remembered_delta,
                channel=NarrativeEvidenceChannel.RECONSTRUCTED,
                lineage_ref=f"recon-{reconstruction_id}",
                tick=tick,
                policy=policy,
                seen=seen,
                source_memory_id=source_memory_id,
                reconstruction_id=reconstruction_id,
                transmission_root_id=parent.transmission_root_id,
                location_id=location_id,
                carrier=owner_id,
                parent_variant_ids=(parent_id,),
                mutation_generation=parent.mutation_generation + 1,
                founding_fingerprint=parent.founding_fingerprint
                or parent.content_fingerprint,
                declared_source_basis=CommunicationSourceBasis.RECONSTRUCTED_MEMORY,
            )
            if (
                reconstructed is not None
                and _is_v2_policy(policy)
                and parent.themes
            ):
                _theme_set(reconstructed.themes, tuple(parent.themes))
                if reconstructed.themes:
                    reconstructed.theme_basis = (
                        NarrativeThemeBasis.INHERITED_LINEAGE
                    )
            _LOG.debug(
                "narrative_variant_branched owner_id=%s tick=%s "
                "status=%s generation=%s",
                owner_id.value,
                tick,
                NarrativeStatus.CANDIDATE.value,
                parent.mutation_generation + 1,
            )
        else:
            reconstructed = _mint_variant(
                drafts=drafts,
                notices=notices,
                owner_id=owner_id,
                content=content,
                origin=NarrativeOrigin.RECONSTRUCTED_MEMORY,
                delta=policy.remembered_delta,
                channel=NarrativeEvidenceChannel.RECONSTRUCTED,
                lineage_ref=f"recon-{reconstruction_id}",
                tick=tick,
                policy=policy,
                seen=seen,
                source_memory_id=source_memory_id,
                reconstruction_id=reconstruction_id,
                location_id=location_id,
                carrier=owner_id,
                declared_source_basis=CommunicationSourceBasis.RECONSTRUCTED_MEMORY,
            )


def _apply_record_cues(
    *,
    cues: NarrativeCueSummary | None,
    drafts: list[_VariantDraft],
    notices: list[str],
    owner_id: AgentId,
    tick: int,
    policy: CulturalNarrativePolicy,
    seen: set[tuple[str, str, str]],
    location_id: str | None,
) -> None:
    if cues is None or not _is_v2_policy(policy) or not cues.records:
        return
    for cue in cues.records:
        concepts = cue.concepts or (
            "record",
            f"revision_{min(cue.observed_revision, 99)}",
        )
        try:
            content = NarrativeContent(
                concepts=concepts,
                relations=cue.relations,
                text="tell_story",
            )
        except ValueError:
            _notice(notices, "empty_content")
            _log_drop("empty_content")
            continue
        draft = _mint_variant(
            drafts=drafts,
            notices=notices,
            owner_id=owner_id,
            content=content,
            origin=NarrativeOrigin.DURABLE_RECORD,
            delta=policy.record_read_delta,
            channel=NarrativeEvidenceChannel.RECORD,
            lineage_ref=f"record-{cue.record_id}-{cue.observed_revision}",
            tick=tick,
            policy=policy,
            seen=seen,
            location_id=location_id,
            carrier=owner_id,
            declared_source_basis=CommunicationSourceBasis.UNREFERENCED,
        )
        if draft is None:
            continue
        previous_revision = max(
            (
                ref.observed_revision
                for ref in draft.record_refs
                if ref.record_id == cue.record_id
            ),
            default=-1,
        )
        previous_annotations = max(
            (
                ref.annotation_revisions or 0
                for ref in draft.record_refs
                if ref.record_id == cue.record_id
            ),
            default=-1,
        )
        previous_copy_generation = max(
            (
                ref.copy_generation or 0
                for ref in draft.record_refs
                if ref.record_id == cue.record_id
            ),
            default=-1,
        )
        integrity = cue.integrity
        integrity_value = None if integrity is None else integrity.lower()
        damaged = integrity_value in {
            "damaged",
            "partial",
            "partially_lost",
        }
        destroyed = integrity_value in {"destroyed", "lost"}
        if destroyed:
            role = NarrativeRecordRole.DESTROYED
        elif damaged:
            role = NarrativeRecordRole.DAMAGED
        elif cue.authored:
            role = NarrativeRecordRole.AUTHORED
        elif (
            cue.copy_generation is not None
            and previous_copy_generation >= 0
            and cue.copy_generation > previous_copy_generation
        ):
            role = NarrativeRecordRole.COPIED
        elif (
            cue.annotation_revisions is not None
            and previous_annotations >= 0
            and cue.annotation_revisions > previous_annotations
        ):
            role = NarrativeRecordRole.ANNOTATED
        elif previous_revision >= 0 and cue.observed_revision > previous_revision:
            role = NarrativeRecordRole.AMENDED
        else:
            role = NarrativeRecordRole.READ
        if len(draft.record_refs) >= policy.max_records and not any(
            ref.record_id == cue.record_id
            and ref.observed_revision == cue.observed_revision
            and ref.role is role
            for ref in draft.record_refs
        ):
            continue
        draft.record_refs.append(
            NarrativeRecordRef(
                record_id=cue.record_id,
                role=role,
                observed_revision=cue.observed_revision,
                tick=tick,
                copy_generation=cue.copy_generation,
                integrity=integrity,
                annotation_revisions=cue.annotation_revisions,
            )
        )
        kind = {
            NarrativeRecordRole.AUTHORED: NarrativeTransitionKind.RECORD_READ,
            NarrativeRecordRole.READ: NarrativeTransitionKind.RECORD_READ,
            NarrativeRecordRole.COPIED: NarrativeTransitionKind.RECORD_COPIED,
            NarrativeRecordRole.AMENDED: NarrativeTransitionKind.RECORD_AMENDED,
            NarrativeRecordRole.ANNOTATED: NarrativeTransitionKind.RECORD_ANNOTATED,
            NarrativeRecordRole.DAMAGED: NarrativeTransitionKind.RECORD_DAMAGED,
            NarrativeRecordRole.PARTIALLY_LOST: (
                NarrativeTransitionKind.RECORD_DAMAGED
            ),
            NarrativeRecordRole.DESTROYED: NarrativeTransitionKind.RECORD_DAMAGED,
        }[role]
        _append_transition(
            draft=draft,
            owner_id=owner_id,
            kind=kind,
            tick=tick,
            reference=f"{cue.record_id}:{cue.observed_revision}",
            policy=policy,
            carrier_agent_id=owner_id,
            record_id=cue.record_id,
        )
        if role is NarrativeRecordRole.AMENDED:
            _append_transition(
                draft=draft,
                owner_id=owner_id,
                kind=NarrativeTransitionKind.EDITED,
                tick=tick,
                reference=f"record-edit-{cue.record_id}:{cue.observed_revision}",
                policy=policy,
                carrier_agent_id=owner_id,
                record_id=cue.record_id,
            )
        _LOG.debug(
            "narrative_record_cue owner_id=%s variant_id=%s role=%s "
            "revision=%s transition=%s theme_count=%s",
            owner_id.value,
            _draft_variant_id(owner_id, draft),
            role.value,
            cue.observed_revision,
            kind.value,
            len(draft.themes),
        )


def _apply_memory_reinforcement(
    *,
    memories: Sequence[object] | None,
    drafts: list[_VariantDraft],
    notices: list[str],
    owner_id: AgentId,
    tick: int,
    policy: CulturalNarrativePolicy,
    seen: set[tuple[str, str, str]],
) -> None:
    if not memories or not drafts:
        return
    by_fp = {
        draft.content_fingerprint: draft
        for draft in drafts
        if draft.merged_into_id is None
        and draft.status not in {NarrativeStatus.RETIRED, NarrativeStatus.MERGED}
    }
    for trace in memories:
        if getattr(trace, "forgotten_at_tick", None) is not None:
            continue
        expires = getattr(trace, "expires_at_tick", None)
        if expires is not None and isinstance(expires, int) and expires <= tick:
            continue
        memory_id = getattr(getattr(trace, "memory_id", None), "value", None)
        if not isinstance(memory_id, str) or not memory_id:
            continue
        concepts: list[str] = []
        for item in getattr(trace, "concepts", ()) or ():
            token = _endpoint_token(item) or (item if isinstance(item, str) else None)
            if isinstance(token, str) and _TOKEN_RE.fullmatch(token):
                concepts.append(token)
            concept = getattr(item, "concept", None)
            if isinstance(concept, str) and _TOKEN_RE.fullmatch(concept):
                concepts.append(concept)
        relations: list[tuple[str, str, str]] = []
        for item in getattr(trace, "relations", ()) or ():
            subject = _endpoint_token(getattr(item, "subject", None))
            predicate = getattr(item, "predicate", None)
            obj = _endpoint_token(getattr(item, "object", None))
            if (
                isinstance(subject, str)
                and isinstance(predicate, str)
                and isinstance(obj, str)
                and _TOKEN_RE.fullmatch(predicate)
            ):
                relations.append((subject, predicate, obj))
        # Never use free-form narrative prose.
        if hasattr(trace, "narrative") and getattr(trace, "narrative", None):
            pass
        if not concepts and not relations:
            continue
        try:
            content = NarrativeContent(
                concepts=tuple(dict.fromkeys(concepts)),
                relations=tuple(relations),
                text="tell_story",
            )
        except ValueError:
            continue
        fingerprint = narrative_content_fingerprint(content)
        draft = by_fp.get(fingerprint)
        if draft is None:
            # Memory never mints.
            continue
        _record_on_draft(
            draft=draft,
            owner_id=owner_id,
            delta=policy.remembered_delta,
            channel=NarrativeEvidenceChannel.REMEMBERED,
            lineage_ref=memory_id,
            tick=tick,
            policy=policy,
            notices=notices,
            seen=seen,
        )


def _apply_retells(
    *,
    observation: Observation,
    identity: OwnerSafeSocialIdentity,
    drafts: list[_VariantDraft],
    notices: list[str],
    policy: CulturalNarrativePolicy,
    seen: set[tuple[str, str, str]],
) -> None:
    owner_id = identity.owner_id
    tick = observation.tick
    location = (
        None if observation.self_body is None else observation.self_body.location_id
    )
    location_value = None if location is None else location.value
    for index, communication in enumerate(observation.communications):
        if type(communication) is not ObservedCommunication:
            continue
        if communication.listener_id != identity.owner_entity_id:
            continue
        speaker = _resolve_agent(identity, communication.speaker_id)
        if speaker is None:
            _notice(notices, "unresolved_entity")
            _log_drop("unresolved_entity")
            continue
        for relation in communication.utterance.content.relations:
            predicate = getattr(relation, "predicate", None)
            if predicate not in _NARRATIVE_PREDICATES:
                continue
            content = _content_from_utterance(communication, text=str(predicate))
            if content is None:
                _notice(notices, "empty_content")
                _log_drop("empty_content")
                continue
            fingerprint = narrative_content_fingerprint(content)
            root_id = communication.utterance.declared.root_communication_id.value
            comm_id = communication.utterance.declared.communication_id.value
            basis = communication.utterance.declared.source_basis
            event_id = communication.provenance.source_event_id
            lineage = (
                f"tick-{tick}-retell-{index}" if event_id is None else event_id.value
            )
            parent = None
            for draft in drafts:
                if (
                    draft.transmission_root_id == root_id
                    and draft.content_fingerprint != fingerprint
                    and draft.merged_into_id is None
                    and draft.status
                    in {NarrativeStatus.ACTIVE, NarrativeStatus.CANDIDATE}
                ):
                    parent = draft
                    break
            if parent is not None:
                parent_id = _draft_variant_id(owner_id, parent)
                retold_draft = _mint_variant(
                    drafts=drafts,
                    notices=notices,
                    owner_id=owner_id,
                    content=content,
                    origin=NarrativeOrigin.RETOLD_STORY,
                    delta=policy.communicated_delta,
                    channel=NarrativeEvidenceChannel.COMMUNICATED,
                    lineage_ref=lineage,
                    tick=tick,
                    policy=policy,
                    seen=seen,
                    transmission_root_id=root_id,
                    last_communication_id=comm_id,
                    location_id=location_value,
                    carrier=speaker,
                    actor_id=speaker,
                    predicate=str(predicate),
                    parent_variant_ids=(parent_id,),
                    mutation_generation=parent.mutation_generation + 1,
                    founding_fingerprint=parent.founding_fingerprint
                    or parent.content_fingerprint,
                    declared_source_basis=basis,
                )
                _LOG.debug(
                    "narrative_variant_branched owner_id=%s tick=%s status=%s "
                    "generation=%s",
                    owner_id.value,
                    tick,
                    NarrativeStatus.CANDIDATE.value,
                    parent.mutation_generation + 1,
                )
            else:
                parent = None
                retold_draft = _mint_variant(
                    drafts=drafts,
                    notices=notices,
                    owner_id=owner_id,
                    content=content,
                    origin=NarrativeOrigin.RETOLD_STORY,
                    delta=policy.communicated_delta,
                    channel=NarrativeEvidenceChannel.COMMUNICATED,
                    lineage_ref=lineage,
                    tick=tick,
                    policy=policy,
                    seen=seen,
                    transmission_root_id=root_id,
                    last_communication_id=comm_id,
                    location_id=location_value,
                    carrier=speaker,
                    actor_id=speaker,
                    predicate=str(predicate),
                    declared_source_basis=basis,
                )
            if retold_draft is not None and _is_v2_policy(policy):
                declared = communication.utterance.declared
                chain = tuple(declared.source_agent_chain)
                for hop_index, entity_id in enumerate(chain):
                    agent_id = _resolve_agent(identity, entity_id)
                    if agent_id is None:
                        entity_value = getattr(entity_id, "value", None)
                        if (
                            isinstance(entity_value, str)
                            and entity_value
                            and entity_value
                            not in retold_draft.declared_source_entity_ids
                            and len(retold_draft.declared_source_entity_ids)
                            < policy.max_declared_chain
                        ):
                            retold_draft.declared_source_entity_ids.append(entity_value)
                        continue
                    kind = (
                        NarrativeWitnessKind.DECLARED_SOURCE
                        if hop_index == 0
                        else NarrativeWitnessKind.DECLARED_RETELLER
                    )
                    _add_witness(
                        draft=retold_draft,
                        owner_id=owner_id,
                        witness_agent_id=agent_id,
                        kind=kind,
                        hop_index=min(hop_index, policy.max_declared_chain),
                        tick=tick,
                        policy=policy,
                    )
                retold_draft.declared_source_entity_ids[:] = (
                    retold_draft.declared_source_entity_ids[: policy.max_declared_chain]
                )
                retold_draft.declared_hop_count = max(
                    retold_draft.declared_hop_count,
                    min(declared.hop_count, policy.max_declared_chain),
                )
                _append_carrier(retold_draft, owner_id, notices)
                if parent is not None and parent.themes:
                    _theme_set(retold_draft.themes, tuple(parent.themes))
                    if retold_draft.themes:
                        retold_draft.theme_basis = parent.theme_basis
                if parent is not None and parent.content_fingerprint != fingerprint:
                    _append_transition(
                        draft=retold_draft,
                        owner_id=owner_id,
                        kind=NarrativeTransitionKind.EDITED,
                        tick=tick,
                        reference=f"edit-{declared.communication_id.value}",
                        policy=policy,
                        carrier_agent_id=owner_id,
                    )
                _append_transition(
                    draft=retold_draft,
                    owner_id=owner_id,
                    kind=NarrativeTransitionKind.RETOLD,
                    tick=tick,
                    reference=declared.communication_id.value,
                    policy=policy,
                    carrier_agent_id=owner_id,
                    hop_index=min(declared.hop_count, policy.max_declared_chain),
                )
            _LOG.debug(
                "narrative_transmission_applied owner_id=%s tick=%s channel=%s",
                owner_id.value,
                tick,
                "communicated",
            )


def _apply_witness_deaths(
    *,
    observation: Observation,
    identity: OwnerSafeSocialIdentity,
    drafts: list[_VariantDraft],
    policy: CulturalNarrativePolicy,
    tick: int,
) -> None:
    if not _is_v2_policy(policy):
        return
    dead_agents: set[AgentId] = set()
    for occurrence in observation.occurrences:
        if type(occurrence) is not ObservedOccurrence:
            continue
        if occurrence.kind not in _DEATH_OCCURRENCE_KINDS:
            continue
        for attribute in ("actor_id", "target_id", "other_entity_id"):
            agent_id = _resolve_agent(
                identity, getattr(occurrence, attribute, None)
            )
            if agent_id is not None:
                dead_agents.add(agent_id)
    if not dead_agents:
        return
    for draft in drafts:
        for index, witness in enumerate(draft.source_witnesses):
            if witness.witness_agent_id not in dead_agents:
                continue
            if witness.death_observed_tick is not None:
                continue
            draft.source_witnesses[index] = NarrativeWitness(
                witness_agent_id=witness.witness_agent_id,
                kind=witness.kind,
                hop_index=witness.hop_index,
                first_seen_tick=witness.first_seen_tick,
                last_seen_tick=max(witness.last_seen_tick, tick),
                death_observed_tick=tick,
            )
            if witness.kind is NarrativeWitnessKind.FIRST_HAND:
                _append_transition(
                    draft=draft,
                    owner_id=identity.owner_id,
                    kind=NarrativeTransitionKind.FIRST_HAND_WITNESS_DIED,
                    tick=tick,
                    reference=witness.witness_agent_id.value,
                    policy=policy,
                    carrier_agent_id=identity.owner_id,
                )
                _LOG.debug(
                    "narrative_witness_died owner_id=%s variant_id=%s "
                    "witness_id=%s hop_index=%s",
                    identity.owner_id.value,
                    _draft_variant_id(identity.owner_id, draft),
                    witness.witness_agent_id.value,
                    witness.hop_index,
                )


def _update_source_loss(
    *,
    drafts: list[_VariantDraft],
    owner_id: AgentId,
    policy: CulturalNarrativePolicy,
    tick: int,
) -> None:
    if not _is_v2_policy(policy):
        return
    for draft in drafts:
        first_hand = [
            witness
            for witness in draft.source_witnesses
            if witness.kind is NarrativeWitnessKind.FIRST_HAND
        ]
        known = len(first_hand)
        dead = sum(
            1
            for witness in first_hand
            if witness.death_observed_tick is not None
        )
        intact_record = any(
            _record_is_intact(record) for record in draft.record_refs
        )
        damaged_record = any(
            _record_is_damaged(record) for record in draft.record_refs
        )
        destroyed_record = any(
            _record_is_destroyed(record) for record in draft.record_refs
        )
        has_record = bool(draft.record_refs)
        if intact_record:
            state = NarrativeSourceLossState.INTACT
            reason = NarrativeSourceLossReason.NONE
        elif known == 0 and not has_record:
            state = NarrativeSourceLossState.UNKNOWN
            reason = NarrativeSourceLossReason.UNKNOWN
        elif known > 0 and dead == 0:
            state = NarrativeSourceLossState.INTACT
            reason = NarrativeSourceLossReason.NONE
        elif known > 0 and dead < known:
            state = NarrativeSourceLossState.PARTIAL
            reason = (
                NarrativeSourceLossReason.RECORD_DAMAGED
                if damaged_record
                else NarrativeSourceLossReason.SOME_WITNESSES_DEAD
            )
        elif destroyed_record:
            state = NarrativeSourceLossState.LOST
            reason = (
                NarrativeSourceLossReason.WITNESS_AND_RECORD_LOSS
                if known > 0
                else NarrativeSourceLossReason.RECORD_DESTROYED
            )
        elif damaged_record:
            state = NarrativeSourceLossState.PARTIAL
            reason = NarrativeSourceLossReason.RECORD_DAMAGED
        elif known > 0:
            state = NarrativeSourceLossState.LOST
            reason = NarrativeSourceLossReason.ALL_FIRST_HAND_WITNESSES_DEAD
        else:
            state = NarrativeSourceLossState.UNKNOWN
            reason = NarrativeSourceLossReason.UNKNOWN
        previous = draft.source_loss
        unchanged = (
            previous is not None
            and previous.state is state
            and previous.reason is reason
            and previous.known_witness_count == known
            and previous.dead_witness_count == dead
            and previous.record_backed == intact_record
        )
        if unchanged:
            continue
        draft.source_loss = NarrativeSourceLoss(
            state=state,
            reason=reason,
            tick=tick,
            known_witness_count=known,
            dead_witness_count=dead,
            record_backed=intact_record,
        )
        if previous is not None and previous.state is not state:
            if state is NarrativeSourceLossState.LOST:
                if known > 0 and dead == known:
                    _append_transition(
                        draft=draft,
                        owner_id=owner_id,
                        kind=NarrativeTransitionKind.ALL_WITNESSES_DEAD,
                        tick=tick,
                        reference=reason.value,
                        policy=policy,
                        carrier_agent_id=owner_id,
                    )
                _append_transition(
                    draft=draft,
                    owner_id=owner_id,
                    kind=NarrativeTransitionKind.SOURCE_LOST,
                    tick=tick,
                    reference=reason.value,
                    policy=policy,
                    carrier_agent_id=owner_id,
                )
            elif previous.state is NarrativeSourceLossState.LOST:
                _append_transition(
                    draft=draft,
                    owner_id=owner_id,
                    kind=NarrativeTransitionKind.REACTIVATED,
                    tick=tick,
                    reference=state.value,
                    policy=policy,
                    carrier_agent_id=owner_id,
                )
        _LOG.info(
            "narrative_source_loss_changed owner_id=%s variant_id=%s "
            "state=%s reason=%s known_witness_count=%s "
            "dead_witness_count=%s",
            owner_id.value,
            _draft_variant_id(owner_id, draft),
            state.value,
            reason.value,
            known,
            dead,
        )
        _LOG.debug(
            "narrative_source_loss owner_id=%s variant_id=%s state=%s "
            "reason=%s known_witness_count=%s dead_witness_count=%s "
            "record_backed=%s",
            owner_id.value,
            _draft_variant_id(owner_id, draft),
            state.value,
            reason.value,
            known,
            dead,
            intact_record,
        )


def _promote(
    drafts: list[_VariantDraft],
    owner_id: AgentId,
    tick: int,
    policy: CulturalNarrativePolicy,
    notices: list[str],
) -> None:
    for draft in drafts:
        if draft.status is not NarrativeStatus.CANDIDATE:
            continue
        if draft.merged_into_id is not None:
            continue
        if draft.repetition_count < policy.promotion_count:
            _notice(notices, "below_count")
            continue
        if draft.strength < policy.active_strength:
            _notice(notices, "below_strength")
            continue
        draft.status = NarrativeStatus.ACTIVE
        _LOG.debug(
            "narrative_variant_promoted owner_id=%s tick=%s status=%s generation=%s",
            owner_id.value,
            tick,
            draft.status.value,
            draft.mutation_generation,
        )


def _link_competitors(
    drafts: list[_VariantDraft],
    owner_id: AgentId,
    policy: CulturalNarrativePolicy,
) -> None:
    active = [
        draft
        for draft in drafts
        if draft.status is NarrativeStatus.ACTIVE and draft.merged_into_id is None
    ]
    for draft in active:
        if draft.transmission_root_id is None:
            draft.competing_variant_ids = []
            continue
        competitors: list[str] = []
        for other in active:
            if other is draft:
                continue
            if other.transmission_root_id != draft.transmission_root_id:
                continue
            if other.content_fingerprint == draft.content_fingerprint:
                continue
            competitors.append(_draft_variant_id(owner_id, other))
        draft.competing_variant_ids = competitors[: policy.max_competitors]


def _merge(
    drafts: list[_VariantDraft],
    owner_id: AgentId,
    tick: int,
    policy: CulturalNarrativePolicy,
    notices: list[str],
) -> None:
    active = [
        draft
        for draft in drafts
        if draft.status is NarrativeStatus.ACTIVE
        and draft.merged_into_id is None
        and draft.repetition_count >= 2
    ]
    active.sort(key=lambda item: (-item.repetition_count, item.content_fingerprint))
    merged_pairs: set[tuple[str, str]] = set()
    for index, left in enumerate(active):
        for right in active[index + 1 :]:
            if right.merged_into_id is not None or left.merged_into_id is not None:
                continue
            overlap = _token_overlap(left.content, right.content)
            if overlap < policy.merge_token_overlap:
                _LOG.warning("narrative_merge_withheld reason=%s", "below_overlap")
                _notice(notices, "below_overlap")
                continue
            if right.repetition_count < 2 or left.repetition_count < 2:
                _LOG.warning("narrative_merge_withheld reason=%s", "below_count")
                _notice(notices, "below_count")
                continue
            left_id = _draft_variant_id(owner_id, left)
            right_id = _draft_variant_id(owner_id, right)
            pair = (min(left_id, right_id), max(left_id, right_id))
            if pair in merged_pairs:
                continue
            if len(drafts) >= policy.max_variants:
                _LOG.warning("narrative_merge_withheld reason=%s", "cap_exceeded")
                _notice(notices, "cap_exceeded")
                return
            dominant, other = (
                (left, right)
                if (
                    left.repetition_count > right.repetition_count
                    or (
                        left.repetition_count == right.repetition_count
                        and left.content_fingerprint < right.content_fingerprint
                    )
                )
                else (right, left)
            )
            concept_union = tuple(
                sorted(set(left.content.concepts) | set(right.content.concepts))
            )
            relation_union = tuple(
                sorted(
                    set(left.content.relations) | set(right.content.relations),
                    key=lambda row: (row[0], row[1], row[2]),
                )
            )
            try:
                merged_content = NarrativeContent(
                    concepts=concept_union,
                    relations=relation_union,
                    text="merge_story",
                )
            except ValueError:
                continue
            parent_ids = tuple(
                sorted(
                    (
                        _draft_variant_id(owner_id, left),
                        _draft_variant_id(owner_id, right),
                    )
                )
            )
            merged = _mint_variant(
                drafts=drafts,
                notices=notices,
                owner_id=owner_id,
                content=merged_content,
                origin=dominant.origin,
                delta=max(left.strength, right.strength),
                channel=NarrativeEvidenceChannel.COMMUNICATED,
                lineage_ref=f"merge-{parent_ids[0][:8]}-{parent_ids[1][:8]}-{tick}",
                tick=tick,
                policy=policy,
                seen=set(),
                transmission_root_id=dominant.transmission_root_id
                or other.transmission_root_id,
                location_id=None,
                carrier=owner_id,
                parent_variant_ids=parent_ids,
                mutation_generation=max(
                    left.mutation_generation, right.mutation_generation
                )
                + 1,
                founding_fingerprint=dominant.founding_fingerprint
                or dominant.content_fingerprint,
                declared_source_basis=dominant.declared_source_basis,
            )
            if merged is None:
                continue
            merged.status = NarrativeStatus.ACTIVE
            if _is_v2_policy(policy):
                _theme_set(
                    merged.themes,
                    tuple(left.themes) + tuple(right.themes),
                )
                if merged.themes:
                    merged.theme_basis = (
                        NarrativeThemeBasis.INHERITED_LINEAGE
                    )
                _append_transition(
                    draft=merged,
                    owner_id=owner_id,
                    kind=NarrativeTransitionKind.MERGED,
                    tick=tick,
                    reference="-".join(parent_ids),
                    policy=policy,
                    carrier_agent_id=owner_id,
                    parent_variant_ids=parent_ids,
                )
            for loc in dict.fromkeys(left.location_ids + right.location_ids):
                _append_location(merged, loc, notices)
            for carrier in dict.fromkeys(
                left.carrier_agent_ids + right.carrier_agent_ids
            ):
                if carrier not in merged.carrier_agent_ids:
                    if len(merged.carrier_agent_ids) < policy.max_carriers:
                        merged.carrier_agent_ids.append(carrier)
            merged_id = _draft_variant_id(owner_id, merged)
            left.status = NarrativeStatus.MERGED
            left.merged_into_id = merged_id
            right.status = NarrativeStatus.MERGED
            right.merged_into_id = merged_id
            merged_pairs.add(pair)
            _LOG.debug(
                "narrative_variant_merged owner_id=%s tick=%s status=%s generation=%s",
                owner_id.value,
                tick,
                NarrativeStatus.MERGED.value,
                merged.mutation_generation,
            )


def _decay(
    drafts: list[_VariantDraft],
    owner_id: AgentId,
    tick: int,
    policy: CulturalNarrativePolicy,
) -> None:
    for draft in drafts:
        if draft.status in {NarrativeStatus.RETIRED, NarrativeStatus.MERGED}:
            continue
        if draft.touched:
            continue
        before = draft.strength
        draft.strength = _apply_delta(before, -policy.decay)
        if draft.strength < policy.retire_strength:
            draft.status = NarrativeStatus.RETIRED
            if _is_v2_policy(policy):
                _append_transition(
                    draft=draft,
                    owner_id=owner_id,
                    kind=NarrativeTransitionKind.RETIRED,
                    tick=tick,
                    reference="strength",
                    policy=policy,
                    carrier_agent_id=owner_id,
                )
            _LOG.debug(
                "narrative_variant_retired owner_id=%s tick=%s status=%s generation=%s",
                owner_id.value,
                tick,
                draft.status.value,
                draft.mutation_generation,
            )


def _freeze(
    owner_id: AgentId,
    drafts: list[_VariantDraft],
    notices: list[str],
    *,
    policy_version: str = CULTURAL_NARRATIVE_POLICY_VERSION,
) -> NarrativeLedger:
    variants: list[NarrativeVariant] = []
    for draft in drafts:
        variant_id = _draft_variant_id(owner_id, draft)
        variants.append(
            NarrativeVariant(
                variant_id=variant_id,
                owner_id=owner_id,
                content=draft.content,
                content_fingerprint=draft.content_fingerprint,
                origin=draft.origin,
                status=draft.status,
                strength=draft.strength,
                repetition_count=draft.repetition_count,
                first_tick=draft.first_tick,
                last_tick=draft.last_tick,
                last_utterance_tick=draft.last_utterance_tick,
                mutation_generation=draft.mutation_generation,
                parent_variant_ids=tuple(draft.parent_variant_ids[:_MAX_PARENTS]),
                merged_into_id=draft.merged_into_id,
                competing_variant_ids=tuple(
                    draft.competing_variant_ids[:_MAX_COMPETITORS]
                ),
                evidence=tuple(draft.evidence[:_MAX_EVIDENCE]),
                source_event_id=draft.source_event_id,
                source_memory_id=draft.source_memory_id,
                reconstruction_id=draft.reconstruction_id,
                transmission_root_id=draft.transmission_root_id,
                last_communication_id=draft.last_communication_id,
                location_ids=tuple(draft.location_ids[:_MAX_LOCATIONS]),
                carrier_agent_ids=tuple(draft.carrier_agent_ids[:_MAX_CARRIERS]),
                notices=tuple(draft.notices),
                declared_source_basis=draft.declared_source_basis,
                source_witnesses=tuple(draft.source_witnesses[:_MAX_WITNESSES]),
                declared_source_entity_ids=tuple(
                    draft.declared_source_entity_ids[:_MAX_DECLARED_CHAIN]
                ),
                declared_hop_count=draft.declared_hop_count,
                first_hand=draft.first_hand,
                record_refs=tuple(draft.record_refs[:_MAX_RECORDS]),
                transitions=tuple(draft.transitions[:_MAX_TRANSITIONS]),
                source_loss=draft.source_loss,
                themes=tuple(
                    sorted(draft.themes, key=_THEME_RANK.__getitem__)[:_MAX_THEMES]
                ),
                theme_basis=draft.theme_basis,
            )
        )
    return NarrativeLedger(
        owner_id=owner_id,
        variants=tuple(variants),
        notices=tuple(notices),
        policy_version=policy_version,
    )


def apply_narrative_update(
    *,
    observation: Observation,
    identity: OwnerSafeSocialIdentity,
    previous: NarrativeLedger | None,
    memories: Sequence[object] | None = None,
    cues: NarrativeCueSummary | None = None,
    policy: CulturalNarrativePolicy | GenerationalNarrativePolicy | None = None,
) -> NarrativeLedger:
    """Apply one tick of narrative evidence for a single owner.

    Disabled callers do not call this function. Passing world authority or a
    metric document raises ``TypeError``. Memory reinforces existing variants
    only and never mints a new variant.
    """
    _LOG.debug(
        "apply_narrative_update owner_id=%s tick=%s",
        getattr(getattr(identity, "owner_id", None), "value", None),
        getattr(observation, "tick", None),
    )
    for value in (observation, identity, previous, policy, memories, cues):
        _reject_forbidden(value)
    if memories is not None:
        for item in memories:
            _reject_forbidden(item)
    if type(observation) is not Observation:
        raise TypeError("observation must be Observation")
    if type(identity) is not OwnerSafeSocialIdentity:
        raise TypeError("identity must be OwnerSafeSocialIdentity")
    if previous is not None and type(previous) is not NarrativeLedger:
        raise TypeError("previous must be NarrativeLedger or None")
    if cues is not None and type(cues) is not NarrativeCueSummary:
        raise TypeError("cues must be NarrativeCueSummary or None")
    active_policy = default_cultural_narrative_policy() if policy is None else policy
    if type(active_policy) not in {
        CulturalNarrativePolicy,
        GenerationalNarrativePolicy,
    }:
        raise TypeError(
            "policy must be CulturalNarrativePolicy or "
            "GenerationalNarrativePolicy"
        )
    policy_version = (
        CULTURAL_NARRATIVE_POLICY_VERSION_V2
        if type(active_policy) is GenerationalNarrativePolicy
        else CULTURAL_NARRATIVE_POLICY_VERSION
    )
    owner_id = identity.owner_id
    tick = observation.tick
    drafts = _drafts_from(previous, owner_id)
    notices: list[str] = []
    seen: set[tuple[str, str, str]] = set()
    location = (
        None if observation.self_body is None else observation.self_body.location_id
    )
    location_value = None if location is None else location.value
    _apply_observed_events(
        observation=observation,
        identity=identity,
        drafts=drafts,
        notices=notices,
        policy=active_policy,
        seen=seen,
    )
    _apply_deliberate_lies(
        observation=observation,
        identity=identity,
        drafts=drafts,
        notices=notices,
        policy=active_policy,
        seen=seen,
    )
    _apply_cues(
        cues=cues,
        drafts=drafts,
        notices=notices,
        owner_id=owner_id,
        tick=tick,
        policy=active_policy,
        seen=seen,
        location_id=location_value,
    )
    _apply_record_cues(
        cues=cues,
        drafts=drafts,
        notices=notices,
        owner_id=owner_id,
        tick=tick,
        policy=active_policy,
        seen=seen,
        location_id=location_value,
    )
    _apply_memory_reinforcement(
        memories=memories,
        drafts=drafts,
        notices=notices,
        owner_id=owner_id,
        tick=tick,
        policy=active_policy,
        seen=seen,
    )
    _apply_retells(
        observation=observation,
        identity=identity,
        drafts=drafts,
        notices=notices,
        policy=active_policy,
        seen=seen,
    )
    _apply_witness_deaths(
        observation=observation,
        identity=identity,
        drafts=drafts,
        policy=active_policy,
        tick=tick,
    )
    _update_source_loss(
        drafts=drafts,
        owner_id=owner_id,
        policy=active_policy,
        tick=tick,
    )
    _promote(drafts, owner_id, tick, active_policy, notices)
    _link_competitors(drafts, owner_id, active_policy)
    _merge(drafts, owner_id, tick, active_policy, notices)
    _decay(drafts, owner_id, tick, active_policy)
    ledger = _freeze(owner_id, drafts, notices, policy_version=policy_version)
    _LOG.info(
        "narrative_ledger_updated owner_id=%s variant_count=%s",
        owner_id.value,
        len(ledger.variants),
    )
    return ledger


def _source_basis_for(variant: NarrativeVariant) -> CommunicationSourceBasis:
    if variant.declared_source_basis is not None:
        return variant.declared_source_basis
    if variant.origin is NarrativeOrigin.RECONSTRUCTED_MEMORY:
        return CommunicationSourceBasis.RECONSTRUCTED_MEMORY
    return CommunicationSourceBasis.UNREFERENCED


def _predicate_for(variant: NarrativeVariant) -> str:
    if variant.status is NarrativeStatus.MERGED or len(variant.parent_variant_ids) >= 2:
        return "merge_story"
    if (
        variant.mutation_generation >= 1
        or variant.origin is NarrativeOrigin.RETOLD_STORY
    ):
        return "retell"
    return "tell_story"


def _direction_value(future: object) -> str | None:
    from agents.cognition.models import ActionDirection

    direction = getattr(future, "direction", None)
    if type(direction) is ActionDirection:
        return direction.value
    value = getattr(direction, "value", None)
    return value if isinstance(value, str) else None


def _future_id(future: object) -> str | None:
    value = getattr(future, "future_id", None)
    return value if isinstance(value, str) and value else None


def narrative_communicate_penalties(
    ledger: object,
    futures: Sequence[object],
    *,
    tick: int,
    mode: object | None = None,
    policy: CulturalNarrativePolicy | None = None,
) -> Mapping[str, float]:
    """Prefer an existing COMMUNICATE future for a speakable narrative."""
    _reject_forbidden(ledger)
    if mode is not None:
        from agents.cognition.configuration import CognitionCulturalNarrativeMode

        if mode is not CognitionCulturalNarrativeMode.DETERMINISTIC:
            return {}
    if ledger is None or type(ledger) is not NarrativeLedger:
        return {}
    active_policy = default_cultural_narrative_policy() if policy is None else policy
    if type(active_policy) not in {
        CulturalNarrativePolicy,
        GenerationalNarrativePolicy,
    }:
        raise TypeError(
            "policy must be CulturalNarrativePolicy or "
            "GenerationalNarrativePolicy"
        )
    communicate_ids = [
        future_id
        for future in futures
        if (future_id := _future_id(future)) is not None
        and _direction_value(future) == "communicate"
    ]
    if not communicate_ids:
        _LOG.warning("narrative_response_withheld reason=%s", "no_candidate")
        return {}
    speakable = False
    for variant in ledger.variants:
        if variant.status is NarrativeStatus.CANDIDATE:
            _LOG.warning("narrative_response_withheld reason=%s", "candidate_only")
            continue
        if variant.status is not NarrativeStatus.ACTIVE:
            continue
        if variant.strength < active_policy.active_strength:
            continue
        if (
            variant.last_utterance_tick is not None
            and tick - variant.last_utterance_tick < active_policy.utterance_interval
        ):
            _LOG.warning("narrative_response_withheld reason=%s", "utterance_interval")
            continue
        speakable = True
        break
    if not speakable:
        return {}
    penalties: dict[str, float] = {}
    for future in futures:
        future_id = _future_id(future)
        if future_id is None or future_id in communicate_ids:
            continue
        total = _apply_delta(penalties.get(future_id, 0.0), active_policy.penalty)
        if total < 0.0:
            raise _fail("penalty", "negative_penalty")
        penalties[future_id] = total
    _LOG.debug("narrative_penalty_applied future_count=%s", len(penalties))
    _LOG.debug(
        "narrative_response_selected owner_id=%s tick=%s response=%s",
        ledger.owner_id.value,
        tick,
        "communicate",
    )
    return penalties


def narrative_communicate_utterance(
    command: object,
    *,
    owner_id: AgentId,
    tick: int,
    observation: Observation,
    identity: OwnerSafeSocialIdentity | None,
    ledger: object | None,
    mode: object | None,
) -> object:
    """Stamp an existing Talk command with one narrative relation recipe."""
    from agents.cognition.configuration import CognitionCulturalNarrativeMode
    from world.actions import Talk
    from world.communications import origin_utterance

    if mode is not CognitionCulturalNarrativeMode.DETERMINISTIC:
        return command
    if type(observation) is not Observation:
        return command
    if type(command) is not Talk:
        return command
    if type(ledger) is not NarrativeLedger or not ledger.variants:
        return command
    if identity is None:
        return command
    if observation.tick != tick:
        return command
    policy = default_cultural_narrative_policy()
    chosen: NarrativeVariant | None = None
    for variant in ledger.variants:
        if variant.status is not NarrativeStatus.ACTIVE:
            continue
        if variant.strength < policy.active_strength:
            continue
        if (
            variant.last_utterance_tick is not None
            and tick - variant.last_utterance_tick < policy.utterance_interval
        ):
            continue
        if chosen is None or variant.strength > chosen.strength:
            chosen = variant
    if chosen is None:
        _LOG.warning("narrative_response_withheld reason=%s", "no_candidate")
        return command
    predicate = _predicate_for(chosen)
    subject = chosen.content.concepts[0] if chosen.content.concepts else "story"
    obj = (
        chosen.content.concepts[1]
        if len(chosen.content.concepts) > 1
        else chosen.origin.value
    )
    utterance = origin_utterance(
        text=predicate,
        speaker_id=identity.owner_entity_id,
        communication_id=(
            f"cultural-narrative-{owner_id.value}-{tick}-{chosen.variant_id[:12]}"
        ),
        concepts=chosen.content.concepts,
        relations=(
            CommunicationRelation(
                subject=subject,
                predicate=predicate,
                object=obj,
            ),
        ),
        source_basis=_source_basis_for(chosen),
    )
    _LOG.debug(
        "narrative_response_selected owner_id=%s tick=%s response=%s",
        owner_id.value,
        tick,
        predicate,
    )
    return Talk(
        recipient_id=command.recipient_id,
        utterance=utterance,
    )


def narrative_semantic_evidence(
    ledger: object,
    *,
    owner_id: AgentId,
    tick: int,
    mode: object | None = None,
    policy: CulturalNarrativePolicy | None = None,
) -> tuple[object, ...]:
    """Return BeliefRevisionRequest values for gated active narratives.

    Does not call MemoryService writers and does not emit MemoryUpdateIntent.
    """
    from memory.belief_formation import (
        DEFAULT_BELIEF_FORMATION_POLICY,
        belief_id_for_claim,
    )
    from memory.beliefs import (
        BeliefEvidenceBundle,
        BeliefEvidenceContribution,
        BeliefRevisionRequest,
        BeliefValueKind,
        ClaimSubject,
        ClaimSubjectKind,
        ClaimValue,
        EvidenceStance,
        SemanticClaim,
    )
    from memory.models import MemoryId

    if mode is not None:
        from agents.cognition.configuration import CognitionCulturalNarrativeMode

        if mode is not CognitionCulturalNarrativeMode.DETERMINISTIC:
            _LOG.warning("narrative_uplift_withheld reason=%s", "disabled")
            _LOG.debug(
                "narrative_semantic_uplift owner_id=%s tick=%s variant_count=%s "
                "uplift=%s",
                owner_id.value,
                tick,
                0,
                False,
            )
            return ()
    if ledger is None or type(ledger) is not NarrativeLedger:
        return ()
    if ledger.owner_id != owner_id:
        raise ValueError("owner_id: owner_mismatch")
    active_policy = default_cultural_narrative_policy() if policy is None else policy
    if type(active_policy) not in {
        CulturalNarrativePolicy,
        GenerationalNarrativePolicy,
    }:
        raise TypeError(
            "policy must be CulturalNarrativePolicy or "
            "GenerationalNarrativePolicy"
        )
    requests: list[BeliefRevisionRequest] = []
    for variant in ledger.variants:
        if variant.status is not NarrativeStatus.ACTIVE:
            _LOG.warning("narrative_uplift_withheld reason=%s", "inactive_status")
            continue
        if variant.repetition_count < active_policy.semantic_uplift_repetitions:
            _LOG.warning("narrative_uplift_withheld reason=%s", "below_repetition")
            continue
        if variant.strength < active_policy.semantic_uplift_strength:
            _LOG.warning("narrative_uplift_withheld reason=%s", "below_strength")
            continue
        if variant.source_memory_id is not None:
            memory_id = MemoryId(variant.source_memory_id)
        else:
            synthetic = f"narrative-lineage-{variant.variant_id}"
            memory_id = MemoryId(synthetic)
            _LOG.warning("narrative_uplift_withheld reason=%s", "no_memory_anchor")
            # Plan allows synthetic lineage memory id derived from variant_id
            # when an existing owner memory id is unavailable.
        concept = (
            variant.content.concepts[0]
            if variant.content.concepts
            else "narrative_claim"
        )
        claim = SemanticClaim(
            subject=ClaimSubject(
                kind=ClaimSubjectKind.CONCEPT,
                concept=concept,
            ),
            predicate="cultural_narrative",
            value=ClaimValue(
                kind=BeliefValueKind.TEXT,
                text_value=variant.content_fingerprint[:24],
            ),
        )
        evidence = BeliefEvidenceBundle(
            supporting=(
                BeliefEvidenceContribution(
                    memory_id=memory_id,
                    stance=EvidenceStance.SUPPORTING,
                    contribution=0.5,
                    ordinal=0,
                    lineage_root_id=memory_id,
                ),
            ),
            contradicting=(),
        )
        belief_id = belief_id_for_claim(owner_id=owner_id, claim=claim)
        digest = hashlib.sha256(
            f"{owner_id.value}|{variant.variant_id}".encode()
        ).hexdigest()[:24]
        requests.append(
            BeliefRevisionRequest(
                owner_id=owner_id,
                operation_id=f"narrative-belief-{digest}",
                logical_tick=tick,
                claim=claim,
                evidence=evidence,
                policy=DEFAULT_BELIEF_FORMATION_POLICY.as_ref(),
                belief_id=belief_id,
            )
        )
    uplift = bool(requests)
    _LOG.debug(
        "narrative_semantic_uplift owner_id=%s tick=%s variant_count=%s uplift=%s",
        owner_id.value,
        tick,
        len(ledger.variants),
        uplift,
    )
    return tuple(requests)
