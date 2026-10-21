"""Owner-local institutional information contracts.

Information associated with a recognized role or recurring procedure is held by
one owner at a time. There is no institution-owned mind, shared content store, or
globally authoritative record. A role channel keeps a stable local identity while
occupants change; nothing is inherited merely by becoming an occupant.

The module is contract-only. It defines bounded values, deterministic local
identity, owner validation, and deterministic retention. Acquisition and use are
separate owner-scoped steps performed by the caller.
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
from collections.abc import Mapping as _Mapping
from collections.abc import Sequence
from dataclasses import dataclass, replace
from decimal import Decimal
from enum import StrEnum
from typing import Final, cast

from agents.cognition.artifacts import (
    ArtifactInterpretation,
    ArtifactInterpretationLedger,
)
from agents.cognition.institution_concepts import (
    InstitutionConcept,
    InstitutionConceptLedger,
    InstitutionPatternChannel,
)
from agents.cognition.models import OwnerSafeSocialIdentity
from agents.cognition.offices import (
    OfficeConcept,
    OfficeConceptLedger,
    OfficeConceptStatus,
    OfficeOccupantStatus,
)
from agents.models import AgentId
from world.artifacts import RecordIntegrity
from world.communications import DeclaredTransmission
from world.identifiers import (
    EntityId,
    require_bounded_text,
    require_exact_nonneg_int,
)
from world.observations import Observation

__all__ = [
    "INSTITUTIONAL_MEMORY_POLICY_VERSION",
    "InstitutionalBindingKind",
    "InstitutionalChannel",
    "InstitutionalFact",
    "InstitutionalLocalReference",
    "InstitutionalMemoryChannel",
    "InstitutionalMemoryEntry",
    "InstitutionalMemoryLedger",
    "InstitutionalMemoryPolicy",
    "InstitutionalMemorySelection",
    "InstitutionalMemorySelectionKind",
    "InstitutionalMemoryUse",
    "InstitutionalMemoryUseDisposition",
    "InstitutionalOccupantClaim",
    "InstitutionalOccupantStatus",
    "InstitutionalProvenance",
    "InstitutionalReferenceState",
    "append_institutional_memory_channel",
    "append_institutional_memory_entry",
    "append_institutional_memory_use",
    "apply_institutional_memory_update",
    "default_institutional_memory_policy",
    "empty_institutional_memory_ledger",
    "institutional_anchor_token",
    "institutional_channel_id",
    "institutional_entity_token",
    "institutional_entry_id",
    "institutional_kind_token",
    "institutional_role_token",
    "record_institutional_acquisition_receipt",
    "require_owner_institutional_memory",
    "require_owner_institutional_memory_selection",
]

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.institutional_memory")

INSTITUTIONAL_MEMORY_POLICY_VERSION: Final[str] = "institutional-memory.v1"

_QUANTUM: Final[Decimal] = Decimal("0.000001")
_HEX: Final[frozenset[str]] = frozenset("0123456789abcdef")
_DIGEST_LEN: Final[int] = 16
_TOKEN_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-z][a-z0-9_]{0,31}$")

_MAX_CHANNELS: Final[int] = 32
_MAX_ENTRIES: Final[int] = 128
_MAX_USES: Final[int] = 32
_MAX_PROVENANCE: Final[int] = 16
_MAX_RECEIPTS: Final[int] = 256
_MAX_OCCUPANTS: Final[int] = 16
_MAX_FACTS: Final[int] = 3
_MAX_TEXT_LEN: Final[int] = 256

_WIRE_ROOT_LEN: Final[int] = 26
_WIRE_PARENT_LEN: Final[int] = 26
_NONE_PARENT: Final[str] = "p_none"


def _fail(field_name: str, code: str) -> ValueError:
    _LOG.error(
        "institutional_memory_validation_failed field=%s reason_code=%s",
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


def _require_unit(field_name: str, value: object) -> float:
    if isinstance(value, bool) or type(value) not in {int, float}:
        raise _fail(field_name, "invalid_type")
    number = cast("float | int", value)
    if not math.isfinite(number):
        raise _fail(field_name, "nonfinite")
    if number < 0.0 or number > 1.0:
        raise _fail(field_name, "out_of_range")
    return _quantize(float(number))


def _require_hex_id(field_name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in _HEX for char in value)
    ):
        raise _fail(field_name, "invalid_id")
    return value


def _require_digest(field_name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != _DIGEST_LEN
        or any(char not in _HEX for char in value)
    ):
        raise _fail(field_name, "invalid_digest")
    return value


def _require_token(field_name: str, value: object) -> str:
    if not isinstance(value, str) or _TOKEN_PATTERN.fullmatch(value) is None:
        raise _fail(field_name, "illegal_token")
    return value


def _require_text(
    field_name: str, value: object, *, max_length: int = _MAX_TEXT_LEN
) -> str:
    try:
        return require_bounded_text(field_name, value, max_length=max_length)
    except ValueError as error:
        raise _fail(field_name, "invalid_text") from error


def _require_tuple(field_name: str, values: object) -> tuple[object, ...]:
    if isinstance(values, (str, bytes, set, frozenset)) or not isinstance(
        values, Sequence
    ):
        raise _fail(field_name, "invalid_type")
    return tuple(values)


def _require_nonneg_int(field_name: str, value: object) -> int:
    try:
        return require_exact_nonneg_int(field_name, value)
    except ValueError as error:
        raise _fail(field_name, "invalid_type") from error


def _require_bool(field_name: str, value: object) -> bool:
    if type(value) is not bool:
        raise _fail(field_name, "invalid_type")
    return value


def _require_optional_hex_id(field_name: str, value: object) -> str | None:
    if value is None:
        return None
    return _require_hex_id(field_name, value)


def _require_optional_text(field_name: str, value: object) -> str | None:
    if value is None:
        return None
    return _require_text(field_name, value)


def _require_wire_root(field_name: str, value: object) -> str:
    text = _require_optional_text(field_name, value)
    if text is None:
        raise _fail(field_name, "invalid_type")
    if (
        len(text) != _WIRE_ROOT_LEN
        or not text.startswith("r_")
        or any(char not in _HEX for char in text[2:])
    ):
        raise _fail(field_name, "invalid_root")
    return text


def _require_wire_parent(field_name: str, value: object) -> str:
    text = _require_optional_text(field_name, value)
    if text is None:
        raise _fail(field_name, "invalid_type")
    if text == _NONE_PARENT:
        return text
    if (
        len(text) != _WIRE_PARENT_LEN
        or not text.startswith("p_")
        or any(char not in _HEX for char in text[2:])
    ):
        raise _fail(field_name, "invalid_parent")
    return text


def _require_agent(field_name: str, value: object) -> AgentId:
    if type(value) is not AgentId:
        raise _fail(field_name, "invalid_type")
    return value


def _require_optional_agent(field_name: str, value: object) -> AgentId | None:
    if value is None:
        return None
    return _require_agent(field_name, value)


def _require_optional_entity(field_name: str, value: object) -> EntityId | None:
    if value is None:
        return None
    if type(value) is not EntityId:
        raise _fail(field_name, "invalid_type")
    return value


def _require_span(prefix: str, first_tick: object, last_tick: object) -> None:
    first = _require_nonneg_int(f"{prefix}.first_tick", first_tick)
    last = _require_nonneg_int(f"{prefix}.last_tick", last_tick)
    if last < first:
        raise _fail(f"{prefix}.last_tick", "before_first_tick")


class InstitutionalBindingKind(StrEnum):
    """What a channel is locally attached to."""

    ROLE = "role"
    PROCEDURE = "procedure"


class InstitutionalMemoryChannel(StrEnum):
    """Immediate acquisition channel. Never an objective truth label."""

    OBSERVATION = "observation"
    RECORD = "record"
    TRANSMISSION = "transmission"
    TEACHING = "teaching"
    RECALL = "recall"


class InstitutionalOccupantStatus(StrEnum):
    """Attribution status for one claimed role occupant."""

    OBSERVED = "observed"
    CLAIMED = "claimed"
    ENDED = "ended"
    DISPUTED = "disputed"
    UNKNOWN = "unknown"


class InstitutionalReferenceState(StrEnum):
    """Whether a local predecessor reference can be resolved."""

    RETAINED = "retained"
    PRUNED = "pruned"
    UNRESOLVED = "unresolved"


class InstitutionalMemorySelectionKind(StrEnum):
    """Closed selection vocabulary. A selection proposes, never commands."""

    CONSULT = "consult"
    TRANSMIT = "transmit"
    TEACH = "teach"
    RECORD = "record"
    IGNORE = "ignore"


class InstitutionalMemoryUseDisposition(StrEnum):
    """Effective disposition recorded only after loop completion."""

    CONSULTED = "consulted"
    TRANSMISSION_ATTEMPT = "transmission_attempt"
    TEACHING_ATTEMPT = "teaching_attempt"
    RECORDING_ATTEMPT = "recording_attempt"
    IGNORED = "ignored"
    UNIGNORED = "unignored"
    SUPERSEDED = "superseded"


def institutional_channel_id(
    owner_id: AgentId,
    binding_kind: InstitutionalBindingKind,
    inception_reference: str,
) -> str:
    """Stable owner-local channel identity fixed at inception.

    It is never derived from the current occupant, label, evidence revision, or
    a truncated wire reference.
    """
    _require_agent("owner_id", owner_id)
    if type(binding_kind) is not InstitutionalBindingKind:
        raise _fail("binding_kind", "invalid_type")
    inception = _require_hex_id("inception_reference", inception_reference)
    return _sha256_hex(
        f"{owner_id.value}|institutional-channel|{binding_kind.value}|{inception}"
    )


def institutional_entry_id(
    owner_id: AgentId,
    channel_id: str | None,
    ordinal: int,
) -> str:
    """Stable owner-local entry identity independent of public labels."""
    _require_agent("owner_id", owner_id)
    channel_key = (
        "unbound" if channel_id is None else _require_hex_id("channel_id", channel_id)
    )
    sequence = _require_nonneg_int("ordinal", ordinal)
    return _sha256_hex(f"{owner_id.value}|institutional-entry|{channel_key}|{sequence}")


@dataclass(frozen=True, slots=True)
class InstitutionalFact:
    """One bounded claim triple. Claims are not world facts."""

    subject: str
    predicate: str
    object: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "subject", _require_token("fact.subject", self.subject)
        )
        object.__setattr__(
            self, "predicate", _require_token("fact.predicate", self.predicate)
        )
        object.__setattr__(self, "object", _require_token("fact.object", self.object))

    def __repr__(self) -> str:
        return "InstitutionalFact(fields=3)"


@dataclass(frozen=True, slots=True)
class InstitutionalLocalReference:
    """A local predecessor reference with explicit resolution state."""

    entry_id: str
    state: InstitutionalReferenceState = InstitutionalReferenceState.RETAINED

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "entry_id", _require_hex_id("reference.entry_id", self.entry_id)
        )
        if type(self.state) is not InstitutionalReferenceState:
            raise _fail("reference.state", "invalid_type")

    def __repr__(self) -> str:
        return f"InstitutionalLocalReference(state={self.state.value!r})"


@dataclass(frozen=True, slots=True)
class InstitutionalOccupantClaim:
    """One attributed occupant claim; absence is unknown, not vacancy."""

    attributed_actor_id: EntityId | None
    occupant_id: AgentId | None
    status: InstitutionalOccupantStatus
    start_tick: int | None = None
    end_tick: int | None = None
    source_evidence_ref: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "attributed_actor_id",
            _require_optional_entity(
                "claim.attributed_actor_id", self.attributed_actor_id
            ),
        )
        object.__setattr__(
            self,
            "occupant_id",
            _require_optional_agent("claim.occupant_id", self.occupant_id),
        )
        if type(self.status) is not InstitutionalOccupantStatus:
            raise _fail("claim.status", "invalid_type")
        if (
            self.occupant_id is None
            and self.status is not InstitutionalOccupantStatus.UNKNOWN
        ):
            raise _fail("claim.status", "unknown_occupant")
        start = (
            None
            if self.start_tick is None
            else _require_nonneg_int("claim.start_tick", self.start_tick)
        )
        end = (
            None
            if self.end_tick is None
            else _require_nonneg_int("claim.end_tick", self.end_tick)
        )
        if start is not None and end is not None and end < start:
            raise _fail("claim.end_tick", "before_start_tick")
        object.__setattr__(self, "start_tick", start)
        object.__setattr__(self, "end_tick", end)
        object.__setattr__(
            self,
            "source_evidence_ref",
            _require_optional_text(
                "claim.source_evidence_ref", self.source_evidence_ref
            ),
        )

    def __repr__(self) -> str:
        return (
            f"InstitutionalOccupantClaim(status={self.status.value!r}, "
            f"has_occupant={self.occupant_id is not None})"
        )


@dataclass(frozen=True, slots=True)
class InstitutionalChannel:
    """A stable local role or procedure association.

    Role references are the owner's ``OfficeConcept.office_id`` and remain fixed
    across occupant replacement.
    """

    owner_id: AgentId
    channel_id: str
    binding_kind: InstitutionalBindingKind
    inception_reference: str
    current_local_reference: str
    public_function_token: str
    context_digest: str
    first_tick: int
    last_tick: int
    revision_count: int
    occupants: tuple[InstitutionalOccupantClaim, ...] = ()

    def __post_init__(self) -> None:
        _require_agent("channel.owner_id", self.owner_id)
        if type(self.binding_kind) is not InstitutionalBindingKind:
            raise _fail("channel.binding_kind", "invalid_type")
        object.__setattr__(
            self,
            "inception_reference",
            _require_hex_id("channel.inception_reference", self.inception_reference),
        )
        expected_id = institutional_channel_id(
            self.owner_id, self.binding_kind, self.inception_reference
        )
        object.__setattr__(
            self, "channel_id", _require_hex_id("channel.channel_id", self.channel_id)
        )
        if self.channel_id != expected_id:
            raise _fail("channel.channel_id", "id_mismatch")
        if self.binding_kind is InstitutionalBindingKind.ROLE:
            object.__setattr__(
                self,
                "current_local_reference",
                _require_hex_id(
                    "channel.current_local_reference", self.current_local_reference
                ),
            )
        else:
            object.__setattr__(
                self,
                "current_local_reference",
                _require_text(
                    "channel.current_local_reference", self.current_local_reference
                ),
            )
        object.__setattr__(
            self,
            "public_function_token",
            _require_token("channel.public_function_token", self.public_function_token),
        )
        object.__setattr__(
            self,
            "context_digest",
            _require_digest("channel.context_digest", self.context_digest),
        )
        _require_span("channel", self.first_tick, self.last_tick)
        object.__setattr__(
            self,
            "revision_count",
            _require_nonneg_int("channel.revision_count", self.revision_count),
        )
        occupants = _require_tuple("channel.occupants", self.occupants)
        checked: list[InstitutionalOccupantClaim] = []
        for claimant in occupants:
            if type(claimant) is not InstitutionalOccupantClaim:
                raise _fail("channel.occupants", "invalid_type")
            checked.append(claimant)
        if len(checked) > _MAX_OCCUPANTS:
            raise _fail("channel.occupants", "cap_exceeded")
        object.__setattr__(self, "occupants", tuple(checked))
        _LOG.debug(
            "institutional_channel_constructed owner_id=%s binding_kind=%s "
            "occupant_count=%s revision_count=%s",
            self.owner_id.value,
            self.binding_kind.value,
            len(self.occupants),
            self.revision_count,
        )

    def __repr__(self) -> str:
        return (
            f"InstitutionalChannel(binding_kind={self.binding_kind.value!r}, "
            f"occupant_count={len(self.occupants)}, "
            f"revision_count={self.revision_count})"
        )


@dataclass(frozen=True, slots=True)
class InstitutionalProvenance:
    """How one local owner acquired or learned a bounded claim.

    Objective native carrier evidence, public declared lineage, and local
    predecessor references are distinct fields. None means unknown.
    """

    immediate_channel: InstitutionalMemoryChannel
    observed_entity_id: EntityId | None = None
    resolved_source_agent_id: AgentId | None = None
    occurrence_ref: str | None = None
    artifact_id: EntityId | None = None
    artifact_revision: int | None = None
    artifact_parent_id: EntityId | None = None
    artifact_root_id: EntityId | None = None
    declared_frame_root: str | None = None
    declared_frame_parent: str | None = None
    declared_transmission: DeclaredTransmission | None = None
    predecessor: InstitutionalLocalReference | None = None

    def __post_init__(self) -> None:
        if type(self.immediate_channel) is not InstitutionalMemoryChannel:
            raise _fail("provenance.immediate_channel", "invalid_type")
        object.__setattr__(
            self,
            "observed_entity_id",
            _require_optional_entity(
                "provenance.observed_entity_id", self.observed_entity_id
            ),
        )
        object.__setattr__(
            self,
            "resolved_source_agent_id",
            _require_optional_agent(
                "provenance.resolved_source_agent_id",
                self.resolved_source_agent_id,
            ),
        )
        object.__setattr__(
            self,
            "occurrence_ref",
            _require_optional_text("provenance.occurrence_ref", self.occurrence_ref),
        )
        object.__setattr__(
            self,
            "artifact_id",
            _require_optional_entity("provenance.artifact_id", self.artifact_id),
        )
        if self.artifact_revision is None:
            if self.artifact_id is not None:
                raise _fail("provenance.artifact_revision", "missing_revision")
        else:
            object.__setattr__(
                self,
                "artifact_revision",
                _require_nonneg_int(
                    "provenance.artifact_revision", self.artifact_revision
                ),
            )
            if self.artifact_id is None:
                raise _fail("provenance.artifact_revision", "missing_artifact")
        object.__setattr__(
            self,
            "artifact_parent_id",
            _require_optional_entity(
                "provenance.artifact_parent_id", self.artifact_parent_id
            ),
        )
        object.__setattr__(
            self,
            "artifact_root_id",
            _require_optional_entity(
                "provenance.artifact_root_id", self.artifact_root_id
            ),
        )
        root = self.declared_frame_root
        parent = self.declared_frame_parent
        if root is not None:
            root = _require_wire_root("provenance.declared_frame_root", root)
        if parent is not None:
            parent = _require_wire_parent("provenance.declared_frame_parent", parent)
        if parent is not None and root is None:
            raise _fail("provenance.declared_frame_root", "missing_root")
        object.__setattr__(self, "declared_frame_root", root)
        object.__setattr__(self, "declared_frame_parent", parent)
        if (
            self.declared_transmission is not None
            and type(self.declared_transmission) is not DeclaredTransmission
        ):
            raise _fail("provenance.declared_transmission", "invalid_type")
        if (
            self.predecessor is not None
            and type(self.predecessor) is not InstitutionalLocalReference
        ):
            raise _fail("provenance.predecessor", "invalid_type")

    def __repr__(self) -> str:
        return (
            f"InstitutionalProvenance(channel={self.immediate_channel.value!r}, "
            f"has_artifact={self.artifact_id is not None}, "
            f"has_declared_frame={self.declared_frame_root is not None}, "
            f"has_declared_transmission={self.declared_transmission is not None})"
        )


@dataclass(frozen=True, slots=True)
class InstitutionalMemoryEntry:
    """One owner-local, fallible entry. Not a belief or an executable permission."""

    owner_id: AgentId
    entry_id: str
    channel_id: str | None
    ordinal: int
    revision: int
    facts: tuple[InstitutionalFact, ...]
    declared_fact_count: int
    acquisition_tick: int
    confidence: float
    distorted: bool
    partial: bool
    active: bool
    ignored: bool
    provenance: tuple[InstitutionalProvenance, ...]
    superseded_entry: InstitutionalLocalReference | None = None
    binding_kind: InstitutionalBindingKind | None = None
    binding_function_token: str | None = None
    binding_context_digest: str | None = None

    def __post_init__(self) -> None:
        _require_agent("entry.owner_id", self.owner_id)
        object.__setattr__(
            self,
            "channel_id",
            _require_optional_hex_id("entry.channel_id", self.channel_id),
        )
        ordinal = _require_nonneg_int("entry.ordinal", self.ordinal)
        object.__setattr__(
            self, "entry_id", _require_hex_id("entry.entry_id", self.entry_id)
        )
        expected_id = institutional_entry_id(self.owner_id, self.channel_id, ordinal)
        if self.entry_id != expected_id:
            raise _fail("entry.entry_id", "id_mismatch")
        object.__setattr__(
            self, "revision", _require_nonneg_int("entry.revision", self.revision)
        )
        facts = _require_tuple("entry.facts", self.facts)
        checked_facts: list[InstitutionalFact] = []
        for fact in facts:
            if type(fact) is not InstitutionalFact:
                raise _fail("entry.facts", "invalid_type")
            checked_facts.append(fact)
        if not 1 <= len(checked_facts) <= _MAX_FACTS:
            raise _fail("entry.facts", "out_of_range")
        object.__setattr__(self, "facts", tuple(checked_facts))
        declared = _require_nonneg_int(
            "entry.declared_fact_count", self.declared_fact_count
        )
        if not 1 <= declared <= _MAX_FACTS:
            raise _fail("entry.declared_fact_count", "out_of_range")
        if declared < len(checked_facts):
            raise _fail("entry.declared_fact_count", "before_retained_facts")
        object.__setattr__(self, "declared_fact_count", declared)
        object.__setattr__(
            self,
            "acquisition_tick",
            _require_nonneg_int("entry.acquisition_tick", self.acquisition_tick),
        )
        object.__setattr__(
            self, "confidence", _require_unit("entry.confidence", self.confidence)
        )
        for name in ("distorted", "partial", "active", "ignored"):
            object.__setattr__(
                self, name, _require_bool(f"entry.{name}", getattr(self, name))
            )
        provenance = _require_tuple("entry.provenance", self.provenance)
        checked_provenance: list[InstitutionalProvenance] = []
        for item in provenance:
            if type(item) is not InstitutionalProvenance:
                raise _fail("entry.provenance", "invalid_type")
            checked_provenance.append(item)
        if not 1 <= len(checked_provenance) <= _MAX_PROVENANCE:
            raise _fail("entry.provenance", "out_of_range")
        object.__setattr__(self, "provenance", tuple(checked_provenance))
        if (
            self.superseded_entry is not None
            and type(self.superseded_entry) is not InstitutionalLocalReference
        ):
            raise _fail("entry.superseded_entry", "invalid_type")
        if (
            self.superseded_entry is not None
            and self.superseded_entry.entry_id == self.entry_id
        ):
            raise _fail("entry.superseded_entry", "self_reference")
        binding_values = (
            self.binding_kind,
            self.binding_function_token,
            self.binding_context_digest,
        )
        if any(value is None for value in binding_values) and any(
            value is not None for value in binding_values
        ):
            raise _fail("entry.binding_kind", "incomplete_binding")
        if self.binding_kind is not None:
            if type(self.binding_kind) is not InstitutionalBindingKind:
                raise _fail("entry.binding_kind", "invalid_type")
            object.__setattr__(
                self,
                "binding_function_token",
                _require_token(
                    "entry.binding_function_token", self.binding_function_token
                ),
            )
            object.__setattr__(
                self,
                "binding_context_digest",
                _require_digest(
                    "entry.binding_context_digest", self.binding_context_digest
                ),
            )
        _LOG.debug(
            "institutional_entry_constructed owner_id=%s channel_bound=%s "
            "fact_count=%s declared_fact_count=%s provenance_count=%s "
            "active=%s ignored=%s partial=%s",
            self.owner_id.value,
            self.channel_id is not None,
            len(self.facts),
            self.declared_fact_count,
            len(self.provenance),
            self.active,
            self.ignored,
            self.partial,
        )

    @property
    def enabled(self) -> bool:
        return True

    def __repr__(self) -> str:
        return (
            f"InstitutionalMemoryEntry(fact_count={len(self.facts)}, "
            f"declared_fact_count={self.declared_fact_count}, "
            f"provenance_count={len(self.provenance)}, revision={self.revision}, "
            f"active={self.active}, ignored={self.ignored}, "
            f"partial={self.partial}, distorted={self.distorted})"
        )


@dataclass(frozen=True, slots=True)
class InstitutionalMemorySelection:
    """Proposal metadata for at most one institutional decision."""

    owner_id: AgentId
    entry_id: str
    channel_id: str | None
    tick: int
    kind: InstitutionalMemorySelectionKind
    ignored: bool | None = None

    def __post_init__(self) -> None:
        _require_agent("selection.owner_id", self.owner_id)
        object.__setattr__(
            self, "entry_id", _require_hex_id("selection.entry_id", self.entry_id)
        )
        object.__setattr__(
            self,
            "channel_id",
            _require_optional_hex_id("selection.channel_id", self.channel_id),
        )
        object.__setattr__(
            self, "tick", _require_nonneg_int("selection.tick", self.tick)
        )
        if type(self.kind) is not InstitutionalMemorySelectionKind:
            raise _fail("selection.kind", "invalid_type")
        if self.kind is InstitutionalMemorySelectionKind.IGNORE:
            if type(self.ignored) is not bool:
                raise _fail("selection.ignored", "invalid_type")
        elif self.ignored is not None:
            raise _fail("selection.ignored", "unexpected_ignored")
        _LOG.debug(
            "institutional_selection_constructed owner_id=%s kind=%s "
            "ignored=%s channel_bound=%s",
            self.owner_id.value,
            self.kind.value,
            self.ignored,
            self.channel_id is not None,
        )

    def __repr__(self) -> str:
        return (
            f"InstitutionalMemorySelection(kind={self.kind.value!r}, "
            f"ignored={self.ignored}, channel_bound={self.channel_id is not None})"
        )


@dataclass(frozen=True, slots=True)
class InstitutionalMemoryUse:
    """Receipt produced only after the cognition loop completes."""

    owner_id: AgentId
    invocation_id: str
    entry_id: str
    channel_id: str | None
    tick: int
    disposition: InstitutionalMemoryUseDisposition

    def __post_init__(self) -> None:
        _require_agent("use.owner_id", self.owner_id)
        object.__setattr__(
            self,
            "invocation_id",
            _require_text("use.invocation_id", self.invocation_id),
        )
        object.__setattr__(
            self, "entry_id", _require_hex_id("use.entry_id", self.entry_id)
        )
        object.__setattr__(
            self,
            "channel_id",
            _require_optional_hex_id("use.channel_id", self.channel_id),
        )
        object.__setattr__(self, "tick", _require_nonneg_int("use.tick", self.tick))
        if type(self.disposition) is not InstitutionalMemoryUseDisposition:
            raise _fail("use.disposition", "invalid_type")
        _LOG.debug(
            "institutional_use_constructed owner_id=%s disposition=%s channel_bound=%s",
            self.owner_id.value,
            self.disposition.value,
            self.channel_id is not None,
        )

    def __repr__(self) -> str:
        return (
            f"InstitutionalMemoryUse(disposition={self.disposition.value!r}, "
            f"channel_bound={self.channel_id is not None})"
        )


@dataclass(frozen=True, slots=True)
class InstitutionalMemoryPolicy:
    """Locked retention and capacity constants."""

    version: str = INSTITUTIONAL_MEMORY_POLICY_VERSION
    max_channels: int = _MAX_CHANNELS
    max_entries: int = _MAX_ENTRIES
    max_uses: int = _MAX_USES
    max_provenance: int = _MAX_PROVENANCE
    max_receipts: int = _MAX_RECEIPTS
    max_occupants: int = _MAX_OCCUPANTS

    def __post_init__(self) -> None:
        if self.version != INSTITUTIONAL_MEMORY_POLICY_VERSION:
            raise _fail("version", "unsupported_policy")
        for name, expected in (
            ("max_channels", _MAX_CHANNELS),
            ("max_entries", _MAX_ENTRIES),
            ("max_uses", _MAX_USES),
            ("max_provenance", _MAX_PROVENANCE),
            ("max_receipts", _MAX_RECEIPTS),
            ("max_occupants", _MAX_OCCUPANTS),
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or type(value) is not int:
                raise _fail(name, "invalid_type")
            if value != expected:
                raise _fail(name, "unsupported_policy")


@dataclass(frozen=True, slots=True)
class InstitutionalMemoryLedger:
    """Owner-scoped information. ``None`` outside means the mode is disabled.

    An empty typed ledger means the mode is enabled without acquired information.
    """

    owner_id: AgentId
    channels: tuple[InstitutionalChannel, ...] = ()
    entries: tuple[InstitutionalMemoryEntry, ...] = ()
    uses: tuple[InstitutionalMemoryUse, ...] = ()
    acquisition_receipt_keys: tuple[str, ...] = ()
    policy_version: str = INSTITUTIONAL_MEMORY_POLICY_VERSION
    first_observed_tick: int | None = None
    last_observed_tick: int | None = None
    observation_count: int = 0
    pruned_channel_count: int = 0
    pruned_entry_count: int = 0
    pruned_use_count: int = 0
    pruned_provenance_count: int = 0
    pruned_receipt_count: int = 0

    def __post_init__(self) -> None:
        _require_agent("ledger.owner_id", self.owner_id)
        if self.policy_version != INSTITUTIONAL_MEMORY_POLICY_VERSION:
            raise _fail("ledger.policy_version", "unsupported_policy")
        channels = _require_tuple("ledger.channels", self.channels)
        checked_channels: list[InstitutionalChannel] = []
        channel_ids: set[str] = set()
        for channel in channels:
            if type(channel) is not InstitutionalChannel:
                raise _fail("ledger.channels", "invalid_type")
            if channel.owner_id != self.owner_id:
                raise _fail("ledger.channels.owner_id", "owner_mismatch")
            if channel.channel_id in channel_ids:
                raise _fail("ledger.channels", "duplicate_id")
            channel_ids.add(channel.channel_id)
            checked_channels.append(channel)
        if len(checked_channels) > _MAX_CHANNELS:
            raise _fail("ledger.channels", "cap_exceeded")
        object.__setattr__(self, "channels", tuple(checked_channels))

        entries = _require_tuple("ledger.entries", self.entries)
        checked_entries: list[InstitutionalMemoryEntry] = []
        entry_ids: set[str] = set()
        for entry in entries:
            if type(entry) is not InstitutionalMemoryEntry:
                raise _fail("ledger.entries", "invalid_type")
            if entry.owner_id != self.owner_id:
                raise _fail("ledger.entries.owner_id", "owner_mismatch")
            if entry.entry_id in entry_ids:
                raise _fail("ledger.entries", "duplicate_id")
            if entry.channel_id is not None and entry.channel_id not in channel_ids:
                raise _fail("ledger.entries.channel_id", "unknown_channel")
            entry_ids.add(entry.entry_id)
            checked_entries.append(entry)
        if len(checked_entries) > _MAX_ENTRIES:
            raise _fail("ledger.entries", "cap_exceeded")
        for entry in checked_entries:
            _validate_local_references(entry, entry_ids)
        object.__setattr__(self, "entries", tuple(checked_entries))

        uses = _require_tuple("ledger.uses", self.uses)
        checked_uses: list[InstitutionalMemoryUse] = []
        invocation_ids: set[str] = set()
        for use in uses:
            if type(use) is not InstitutionalMemoryUse:
                raise _fail("ledger.uses", "invalid_type")
            if use.owner_id != self.owner_id:
                raise _fail("ledger.uses.owner_id", "owner_mismatch")
            if use.invocation_id in invocation_ids:
                raise _fail("ledger.uses", "duplicate_id")
            invocation_ids.add(use.invocation_id)
            checked_uses.append(use)
        if len(checked_uses) > _MAX_USES:
            raise _fail("ledger.uses", "cap_exceeded")
        object.__setattr__(self, "uses", tuple(checked_uses))

        receipts = _require_tuple(
            "ledger.acquisition_receipt_keys", self.acquisition_receipt_keys
        )
        checked_receipts: list[str] = []
        for receipt in receipts:
            key = _require_text("ledger.acquisition_receipt_keys", receipt)
            if key in checked_receipts:
                raise _fail("ledger.acquisition_receipt_keys", "duplicate_id")
            checked_receipts.append(key)
        if len(checked_receipts) > _MAX_RECEIPTS:
            raise _fail("ledger.acquisition_receipt_keys", "cap_exceeded")
        object.__setattr__(self, "acquisition_receipt_keys", tuple(checked_receipts))

        first = self.first_observed_tick
        last = self.last_observed_tick
        if (first is None) != (last is None):
            raise _fail("ledger.first_observed_tick", "incomplete_window")
        if first is not None:
            first_tick = _require_nonneg_int("ledger.first_observed_tick", first)
            last_tick = _require_nonneg_int("ledger.last_observed_tick", last)
            if last_tick < first_tick:
                raise _fail("ledger.last_observed_tick", "before_first_tick")
        observation_count = _require_nonneg_int(
            "ledger.observation_count", self.observation_count
        )
        if first is None and observation_count:
            raise _fail("ledger.observation_count", "missing_window")
        object.__setattr__(self, "observation_count", observation_count)
        for name in (
            "pruned_channel_count",
            "pruned_entry_count",
            "pruned_use_count",
            "pruned_provenance_count",
            "pruned_receipt_count",
        ):
            object.__setattr__(
                self, name, _require_nonneg_int(f"ledger.{name}", getattr(self, name))
            )
        _LOG.debug(
            "institutional_ledger_constructed owner_id=%s policy_version=%s "
            "channel_count=%s entry_count=%s use_count=%s receipt_count=%s "
            "observation_count=%s coverage=%s",
            self.owner_id.value,
            self.policy_version,
            len(self.channels),
            len(self.entries),
            len(self.uses),
            len(self.acquisition_receipt_keys),
            self.observation_count,
            self.coverage,
        )

    @property
    def enabled(self) -> bool:
        return True

    @property
    def has_content(self) -> bool:
        return bool(self.channels or self.entries or self.uses)

    @property
    def coverage(self) -> str:
        return (
            "partial"
            if any(
                (
                    self.pruned_channel_count,
                    self.pruned_entry_count,
                    self.pruned_use_count,
                    self.pruned_provenance_count,
                    self.pruned_receipt_count,
                )
            )
            else "complete"
        )

    def __repr__(self) -> str:
        return (
            f"InstitutionalMemoryLedger(owner_id={self.owner_id.value!r}, "
            f"channel_count={len(self.channels)}, entry_count={len(self.entries)}, "
            f"use_count={len(self.uses)}, "
            f"receipt_count={len(self.acquisition_receipt_keys)}, "
            f"observation_count={self.observation_count}, "
            f"coverage={self.coverage!r})"
        )


def _validate_local_references(
    entry: InstitutionalMemoryEntry, entry_ids: set[str]
) -> None:
    for provenance in entry.provenance:
        reference = provenance.predecessor
        if (
            reference is None
            or reference.state is not InstitutionalReferenceState.RETAINED
        ):
            continue
        if reference.entry_id not in entry_ids:
            raise _fail("entry.provenance.predecessor", "dangling_reference")
    superseded = entry.superseded_entry
    if (
        superseded is not None
        and superseded.state is InstitutionalReferenceState.RETAINED
        and superseded.entry_id not in entry_ids
    ):
        raise _fail("entry.superseded_entry", "dangling_reference")


def _mark_pruned_entry(
    entry: InstitutionalMemoryEntry, entry_ids: set[str]
) -> tuple[InstitutionalMemoryEntry, int]:
    pruned_count = 0
    provenance: list[InstitutionalProvenance] = []
    for item in entry.provenance:
        reference = item.predecessor
        if (
            reference is not None
            and reference.state is InstitutionalReferenceState.RETAINED
            and reference.entry_id not in entry_ids
        ):
            item = replace(
                item,
                predecessor=InstitutionalLocalReference(
                    entry_id=reference.entry_id,
                    state=InstitutionalReferenceState.PRUNED,
                ),
            )
            pruned_count += 1
        provenance.append(item)
    superseded = entry.superseded_entry
    if (
        superseded is not None
        and superseded.state is InstitutionalReferenceState.RETAINED
        and superseded.entry_id not in entry_ids
    ):
        superseded = InstitutionalLocalReference(
            entry_id=superseded.entry_id,
            state=InstitutionalReferenceState.PRUNED,
        )
        pruned_count += 1
    if not pruned_count:
        return entry, 0
    return (
        replace(entry, provenance=tuple(provenance), superseded_entry=superseded),
        pruned_count,
    )


def _resolve_policy(
    policy: InstitutionalMemoryPolicy | None,
) -> InstitutionalMemoryPolicy:
    if policy is None:
        return default_institutional_memory_policy()
    if type(policy) is not InstitutionalMemoryPolicy:
        raise _fail("policy", "invalid_type")
    return policy


def default_institutional_memory_policy() -> InstitutionalMemoryPolicy:
    """Return the only accepted institutional-memory policy."""
    return InstitutionalMemoryPolicy()


def empty_institutional_memory_ledger(owner_id: AgentId) -> InstitutionalMemoryLedger:
    """Ledger with no acquired information. Disabled mode does not call this."""
    return InstitutionalMemoryLedger(owner_id=owner_id)


def require_owner_institutional_memory(
    ledger: object,
    owner_id: AgentId,
    *,
    field_name: str,
) -> None:
    """Reject a foreign or mistyped institutional-memory ledger."""
    if ledger is None:
        return
    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    if type(ledger) is not InstitutionalMemoryLedger:
        _LOG.warning("institutional_memory_carry_rejected reason=%s", "invalid_type")
        raise TypeError(f"{field_name} must be InstitutionalMemoryLedger")
    if ledger.owner_id != owner_id:
        _LOG.error(
            "institutional_memory_validation_failed field=%s reason_code=%s",
            field_name,
            "owner_mismatch",
        )
        _LOG.warning("institutional_memory_carry_rejected reason=%s", "owner_mismatch")
        raise ValueError(f"{field_name} owner_id mismatch")


def require_owner_institutional_memory_selection(
    selection: object,
    owner_id: AgentId,
    *,
    field_name: str,
) -> None:
    """Reject a foreign or mistyped institutional-memory selection."""
    if selection is None:
        return
    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    if type(selection) is not InstitutionalMemorySelection:
        raise TypeError(f"{field_name} must be InstitutionalMemorySelection")
    if selection.owner_id != owner_id:
        _LOG.error(
            "institutional_memory_validation_failed field=%s reason_code=%s",
            field_name,
            "owner_mismatch",
        )
        raise ValueError(f"{field_name} owner_id mismatch")


def _check_owner(ledger: InstitutionalMemoryLedger, owner_id: AgentId) -> None:
    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    if ledger.owner_id != owner_id:
        raise _fail("owner_id", "owner_mismatch")


def append_institutional_memory_channel(
    ledger: InstitutionalMemoryLedger,
    channel: InstitutionalChannel,
    *,
    policy: InstitutionalMemoryPolicy | None = None,
) -> InstitutionalMemoryLedger:
    """Add one channel, evicting only unreferenced channels under cap pressure."""
    if type(ledger) is not InstitutionalMemoryLedger:
        raise _fail("ledger", "invalid_type")
    if type(channel) is not InstitutionalChannel:
        raise _fail("channel", "invalid_type")
    _check_owner(ledger, channel.owner_id)
    resolved = _resolve_policy(policy)
    if any(item.channel_id == channel.channel_id for item in ledger.channels):
        raise _fail("channel.channel_id", "duplicate_id")
    channels = list(ledger.channels)
    pruned = 0
    if len(channels) >= resolved.max_channels:
        referenced = {
            entry.channel_id for entry in ledger.entries if entry.channel_id is not None
        }
        candidates = [item for item in channels if item.channel_id not in referenced]
        if not candidates:
            _LOG.warning(
                "institutional_memory_prune_blocked owner_id=%s reason=%s",
                ledger.owner_id.value,
                "retained_channel",
            )
            raise _fail("ledger.channels", "cap_exceeded")
        oldest = min(candidates, key=lambda item: (item.first_tick, item.channel_id))
        channels.remove(oldest)
        pruned += 1
    channels.append(channel)
    updated = replace(
        ledger,
        channels=tuple(channels),
        pruned_channel_count=ledger.pruned_channel_count + pruned,
    )
    _LOG.debug(
        "institutional_memory_channel_appended owner_id=%s binding_kind=%s "
        "channel_count=%s pruned=%s",
        ledger.owner_id.value,
        channel.binding_kind.value,
        len(channels),
        pruned,
    )
    return updated


def append_institutional_memory_entry(
    ledger: InstitutionalMemoryLedger,
    entry: InstitutionalMemoryEntry,
    *,
    policy: InstitutionalMemoryPolicy | None = None,
) -> InstitutionalMemoryLedger:
    """Append one entry, deterministically evicting the oldest under cap."""
    if type(ledger) is not InstitutionalMemoryLedger:
        raise _fail("ledger", "invalid_type")
    if type(entry) is not InstitutionalMemoryEntry:
        raise _fail("entry", "invalid_type")
    _check_owner(ledger, entry.owner_id)
    resolved = _resolve_policy(policy)
    if any(item.entry_id == entry.entry_id for item in ledger.entries):
        raise _fail("entry.entry_id", "duplicate_id")
    if entry.channel_id is not None and not any(
        item.channel_id == entry.channel_id for item in ledger.channels
    ):
        raise _fail("entry.channel_id", "unknown_channel")
    entries = list(ledger.entries)
    entries.append(entry)
    pruned_entries = 0
    pruned_provenance = 0
    while len(entries) > resolved.max_entries:
        oldest = min(entries, key=lambda item: (item.acquisition_tick, item.entry_id))
        entries.remove(oldest)
        pruned_entries += 1
        pruned_provenance += len(oldest.provenance)
    remaining_ids = {item.entry_id for item in entries}
    checked: list[InstitutionalMemoryEntry] = []
    for item in entries:
        marked, count = _mark_pruned_entry(item, remaining_ids)
        pruned_provenance += count
        checked.append(marked)
    updated = replace(
        ledger,
        entries=tuple(checked),
        pruned_entry_count=ledger.pruned_entry_count + pruned_entries,
        pruned_provenance_count=ledger.pruned_provenance_count + pruned_provenance,
    )
    if pruned_entries:
        _LOG.warning(
            "institutional_memory_pruned owner_id=%s reason=%s "
            "pruned_entry_count=%s pruned_provenance_count=%s",
            ledger.owner_id.value,
            "entry_cap",
            pruned_entries,
            pruned_provenance,
        )
    _LOG.debug(
        "institutional_memory_entry_appended owner_id=%s channel_bound=%s "
        "entry_count=%s pruned_entries=%s",
        ledger.owner_id.value,
        entry.channel_id is not None,
        len(checked),
        pruned_entries,
    )
    return updated


def append_institutional_memory_use(
    ledger: InstitutionalMemoryLedger,
    use: InstitutionalMemoryUse,
    *,
    policy: InstitutionalMemoryPolicy | None = None,
) -> InstitutionalMemoryLedger:
    """Append one completion receipt, evicting the oldest under cap."""
    if type(ledger) is not InstitutionalMemoryLedger:
        raise _fail("ledger", "invalid_type")
    if type(use) is not InstitutionalMemoryUse:
        raise _fail("use", "invalid_type")
    _check_owner(ledger, use.owner_id)
    resolved = _resolve_policy(policy)
    if any(item.invocation_id == use.invocation_id for item in ledger.uses):
        raise _fail("use.invocation_id", "duplicate_id")
    uses = list(ledger.uses)
    uses.append(use)
    pruned = 0
    while len(uses) > resolved.max_uses:
        oldest = min(uses, key=lambda item: (item.tick, item.invocation_id))
        uses.remove(oldest)
        pruned += 1
    updated = replace(
        ledger,
        uses=tuple(uses),
        pruned_use_count=ledger.pruned_use_count + pruned,
    )
    if pruned:
        _LOG.warning(
            "institutional_memory_pruned owner_id=%s reason=%s pruned_use_count=%s",
            ledger.owner_id.value,
            "use_cap",
            pruned,
        )
    _LOG.debug(
        "institutional_memory_use_appended owner_id=%s disposition=%s use_count=%s",
        ledger.owner_id.value,
        use.disposition.value,
        len(uses),
    )
    return updated


def record_institutional_acquisition_receipt(
    ledger: InstitutionalMemoryLedger,
    receipt_key: str,
    *,
    policy: InstitutionalMemoryPolicy | None = None,
) -> InstitutionalMemoryLedger:
    """Remember one acquisition key, evicting the oldest under cap pressure."""
    if type(ledger) is not InstitutionalMemoryLedger:
        raise _fail("ledger", "invalid_type")
    resolved = _resolve_policy(policy)
    key = _require_text("receipt_key", receipt_key)
    if key in ledger.acquisition_receipt_keys:
        return ledger
    receipts = list(ledger.acquisition_receipt_keys)
    receipts.append(key)
    pruned = 0
    while len(receipts) > resolved.max_receipts:
        receipts.pop(0)
        pruned += 1
    updated = replace(
        ledger,
        acquisition_receipt_keys=tuple(receipts),
        pruned_receipt_count=ledger.pruned_receipt_count + pruned,
    )
    if pruned:
        _LOG.warning(
            "institutional_memory_pruned owner_id=%s reason=%s pruned_receipt_count=%s",
            ledger.owner_id.value,
            "receipt_cap",
            pruned,
        )
    _LOG.debug(
        "institutional_memory_receipt_recorded owner_id=%s receipt_count=%s",
        ledger.owner_id.value,
        len(receipts),
    )
    return updated


# ---------------------------------------------------------------------------
# Owner-local grounding and locally produced information
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _InstitutionalCandidate:
    channel_id: str | None
    fact: InstitutionalFact
    tick: int
    source_ref: str
    confidence: float
    binding_kind: InstitutionalBindingKind | None = None
    binding_function_token: str | None = None
    binding_context_digest: str | None = None


def institutional_entity_token(value: str) -> str:
    """Opaque local token for one observed actor or counterpart."""
    if not isinstance(value, str) or not value:
        raise _fail("entity_token", "invalid_type")
    return "e_" + _sha256_hex(f"entity|{value}")[:24]


def institutional_kind_token(kind: str) -> str:
    """Artifact-safe occurrence token; irreversible normalization."""
    if not isinstance(kind, str) or not kind:
        raise _fail("kind_token", "invalid_type")
    if _TOKEN_PATTERN.fullmatch(kind) is not None:
        return kind
    return "k_" + _sha256_hex(f"kind|{kind}")[:24]


def institutional_role_token(function: str, context_key: str) -> str:
    """Bounded public token for one locally recognized role."""
    if not isinstance(function, str) or not function:
        raise _fail("role.function", "invalid_type")
    context = _require_digest("role.context_key", context_key)
    token = f"{function.split('_')[0]}_{context[:8]}"
    return _require_token("role.token", token)


def institutional_anchor_token(anchor_digest: str) -> str:
    anchor = _require_digest("anchor_digest", anchor_digest)
    return "a_" + anchor


def _office_occupant_status(
    status: OfficeOccupantStatus,
) -> InstitutionalOccupantStatus:
    if (
        status is OfficeOccupantStatus.DISPUTED
        or status is OfficeOccupantStatus.OPPOSED
    ):
        return InstitutionalOccupantStatus.DISPUTED
    if status is OfficeOccupantStatus.CANDIDATE:
        return InstitutionalOccupantStatus.CLAIMED
    return InstitutionalOccupantStatus.CLAIMED


def _require_ledger_owner(value: object, owner_id: AgentId, expected: type) -> None:
    if value is None:
        return
    if type(value) is not expected:
        raise _fail("store", "invalid_type")
    store_owner = getattr(value, "owner_id", None)
    if store_owner is not None and store_owner != owner_id:
        raise _fail("store", "owner_mismatch")


def _role_channel(concept: OfficeConcept) -> InstitutionalChannel:
    function = concept.function.value
    role_token = institutional_role_token(function, concept.context_key)
    occupants: list[InstitutionalOccupantClaim] = []
    for claim in concept.occupants[:_MAX_OCCUPANTS]:
        status = _office_occupant_status(claim.status)
        occupant = claim.occupant_id
        if occupant is None:
            status = InstitutionalOccupantStatus.UNKNOWN
        occupants.append(
            InstitutionalOccupantClaim(
                attributed_actor_id=None,
                occupant_id=occupant,
                status=status,
                start_tick=claim.first_tick,
                end_tick=None,
                source_evidence_ref=(
                    None if not claim.evidence_ids else claim.evidence_ids[0]
                ),
            )
        )
    return InstitutionalChannel(
        owner_id=concept.owner_id,
        channel_id=institutional_channel_id(
            concept.owner_id,
            InstitutionalBindingKind.ROLE,
            concept.office_id,
        ),
        binding_kind=InstitutionalBindingKind.ROLE,
        inception_reference=concept.office_id,
        current_local_reference=concept.office_id,
        public_function_token=role_token,
        context_digest=concept.context_key,
        first_tick=concept.first_tick,
        last_tick=concept.last_tick,
        revision_count=len(concept.revisions),
        occupants=tuple(occupants),
    )


def _procedure_channel(
    concept: InstitutionConcept,
    previous_channels: Sequence[InstitutionalChannel],
) -> InstitutionalChannel | None:
    anchors = tuple(concept.anchor_digests)
    if not anchors:
        return None
    overlapping = tuple(
        channel
        for channel in previous_channels
        if channel.binding_kind is InstitutionalBindingKind.PROCEDURE
        and channel.current_local_reference in anchors
    )
    if len(overlapping) > 1:
        _LOG.debug(
            "institutional_channel_ambiguous reason=%s anchor_count=%s",
            "procedure_overlap",
            len(anchors),
        )
        return None
    if overlapping:
        inception = overlapping[0].inception_reference
    else:
        inception = _sha256_hex(
            f"{concept.owner_id.value}|procedure-inception|" + "|".join(sorted(anchors))
        )
    channel_id = institutional_channel_id(
        concept.owner_id, InstitutionalBindingKind.PROCEDURE, inception
    )
    return InstitutionalChannel(
        owner_id=concept.owner_id,
        channel_id=channel_id,
        binding_kind=InstitutionalBindingKind.PROCEDURE,
        inception_reference=inception,
        current_local_reference=anchors[0],
        public_function_token="procedure",
        context_digest=concept.group_key[:16],
        first_tick=concept.first_tick,
        last_tick=concept.last_tick,
        revision_count=0,
    )


def _office_candidates(
    concept: OfficeConcept,
    channel: InstitutionalChannel,
) -> tuple[list[_InstitutionalCandidate], set[str]]:
    role_token = channel.public_function_token
    evidence_tokens: set[str] = set()
    for item in concept.evidence:
        evidence_tokens.add(item.lineage_ref)
        evidence_tokens.add(item.root_ref)
        if item.actor_id is not None:
            evidence_tokens.add(item.actor_id.value)
    candidates: list[_InstitutionalCandidate] = []
    for duty in concept.duties:
        candidates.append(
            _InstitutionalCandidate(
                channel_id=channel.channel_id,
                fact=InstitutionalFact(role_token, "duty", duty.kind.value),
                tick=duty.last_tick,
                source_ref=duty.duty_id,
                confidence=0.7,
            )
        )
    for claim in concept.occupants:
        if claim.occupant_id is None:
            continue
        candidates.append(
            _InstitutionalCandidate(
                channel_id=channel.channel_id,
                fact=InstitutionalFact(
                    role_token,
                    "occupant_claim",
                    institutional_entity_token(claim.occupant_id.value),
                ),
                tick=claim.last_tick,
                source_ref=claim.claim_id,
                confidence=0.7,
            )
        )
    for succession in concept.succession:
        candidates.append(
            _InstitutionalCandidate(
                channel_id=channel.channel_id,
                fact=InstitutionalFact(
                    role_token, "succession_claim", succession.kind.value
                ),
                tick=succession.tick,
                source_ref=succession.succession_id,
                confidence=0.7,
            )
        )
    return candidates, evidence_tokens


def _procedure_candidates(
    concept: InstitutionConcept, channel: InstitutionalChannel
) -> tuple[list[_InstitutionalCandidate], set[str]]:
    candidates: list[_InstitutionalCandidate] = []
    evidence_tokens: set[str] = set()
    for item in concept.evidence:
        evidence_tokens.add(item.lineage_ref)
        if item.actor_id is not None:
            evidence_tokens.add(item.actor_id.value)
        if item.pattern is not InstitutionPatternChannel.PROCEDURE_RECURRENCE:
            continue
        candidates.append(
            _InstitutionalCandidate(
                channel_id=channel.channel_id,
                fact=InstitutionalFact(
                    "procedure",
                    "observed_pattern",
                    institutional_anchor_token(item.anchor_digest),
                ),
                tick=item.tick,
                source_ref=item.evidence_id,
                confidence=0.7,
            )
        )
    return candidates, evidence_tokens


def _occurrence_candidates(
    observation: Observation,
    channel_evidence: _Mapping[str, set[str]],
) -> list[_InstitutionalCandidate]:
    candidates: list[_InstitutionalCandidate] = []
    for occurrence in observation.occurrences:
        actor = occurrence.actor_id
        target = occurrence.other_entity_id or occurrence.destination_id
        if actor is None or target is None:
            _LOG.debug("institutional_occurrence_skipped reason=%s", "unresolved_actor")
            continue
        event_ref = (
            None
            if occurrence.provenance.source_event_id is None
            else occurrence.provenance.source_event_id.value
        )
        matches = [
            channel_id
            for channel_id, tokens in channel_evidence.items()
            if (event_ref is not None and event_ref in tokens) or actor.value in tokens
        ]
        if not matches:
            _LOG.debug("institutional_occurrence_skipped reason=%s", "unbound")
            continue
        if len(matches) > 1:
            _LOG.debug(
                "institutional_occurrence_skipped reason=%s", "ambiguous_binding"
            )
            continue
        kind = institutional_kind_token(occurrence.kind)
        predicate = kind
        if occurrence.success is not None:
            suffix = "success" if occurrence.success else "failure"
            combined = f"{kind}_{suffix}"
            predicate = (
                combined
                if _TOKEN_PATTERN.fullmatch(combined) is not None
                else "k_" + _sha256_hex(f"result|{kind}|{suffix}")[:24]
            )
        candidates.append(
            _InstitutionalCandidate(
                channel_id=matches[0],
                fact=InstitutionalFact(
                    institutional_entity_token(actor.value),
                    predicate,
                    institutional_entity_token(target.value),
                ),
                tick=occurrence.provenance.source_tick,
                source_ref=event_ref
                or f"occurrence|{occurrence.provenance.source_tick}|{actor.value}",
                confidence=0.7,
            )
        )
    return candidates


def _reconsider_binding(
    entry: InstitutionalMemoryEntry,
    channels: Sequence[InstitutionalChannel],
    existing_ids: set[str],
) -> InstitutionalMemoryEntry:
    if entry.channel_id is not None or entry.binding_kind is None:
        return entry
    matches = tuple(
        channel
        for channel in channels
        if channel.binding_kind is entry.binding_kind
        and channel.public_function_token == entry.binding_function_token
        and channel.context_digest == entry.binding_context_digest
    )
    if len(matches) != 1:
        _LOG.debug(
            "institutional_rebinding_skipped reason=%s",
            "ambiguous_binding" if matches else "unbound",
        )
        return entry
    channel = matches[0]
    new_id = institutional_entry_id(entry.owner_id, channel.channel_id, entry.ordinal)
    if new_id in existing_ids:
        return entry
    return replace(entry, channel_id=channel.channel_id, entry_id=new_id)


def apply_institutional_memory_update(
    *,
    owner_id: AgentId,
    observation: Observation,
    identity: OwnerSafeSocialIdentity,
    previous: InstitutionalMemoryLedger | None = None,
    office_concepts: OfficeConceptLedger | None = None,
    institution_concepts: InstitutionConceptLedger | None = None,
    artifact_interpretations: object | None = None,
    retrieved_memory_context: object | None = None,
    relationships: _Mapping[str, float] | None = None,
    teaching_enabled: bool = False,
    policy: InstitutionalMemoryPolicy | None = None,
) -> InstitutionalMemoryLedger:
    """Apply one tick of owner-local institutional information.

    Only the owner's observation, owner-safe identity, prepared local ledgers,
    and previous institutional ledger are inputs. No sender ledger is read.
    """
    _require_agent("owner_id", owner_id)
    if type(observation) is not Observation:
        raise _fail("observation", "invalid_type")
    if type(identity) is not OwnerSafeSocialIdentity:
        raise _fail("identity", "invalid_type")
    if identity.owner_id != owner_id:
        raise _fail("identity.owner_id", "owner_mismatch")
    if observation.observer_id != identity.owner_entity_id:
        raise _fail("observation.observer_id", "owner_mismatch")
    if previous is not None and type(previous) is not InstitutionalMemoryLedger:
        raise _fail("previous", "invalid_type")
    if type(teaching_enabled) is not bool:
        raise _fail("teaching_enabled", "invalid_type")
    for store, expected in (
        (office_concepts, OfficeConceptLedger),
        (institution_concepts, InstitutionConceptLedger),
    ):
        _require_ledger_owner(store, owner_id, expected)
    if artifact_interpretations is not None:
        _require_ledger_owner(
            artifact_interpretations, owner_id, ArtifactInterpretationLedger
        )
    if retrieved_memory_context is not None:
        context_owner = getattr(retrieved_memory_context, "owner_id", None)
        if context_owner != owner_id:
            raise _fail("retrieved_memory_context", "owner_mismatch")
    if relationships is not None and not isinstance(relationships, _Mapping):
        raise _fail("relationships", "invalid_type")
    resolved = _resolve_policy(policy)
    ledger = previous or empty_institutional_memory_ledger(owner_id)
    if ledger.owner_id != owner_id:
        raise _fail("previous", "owner_mismatch")

    channels: dict[str, InstitutionalChannel] = {
        channel.channel_id: channel for channel in ledger.channels
    }
    channel_evidence: dict[str, set[str]] = {}
    candidates: list[_InstitutionalCandidate] = []

    if office_concepts is not None:
        for concept in office_concepts.concepts:
            if concept.status not in {
                OfficeConceptStatus.RECOGNIZED,
                OfficeConceptStatus.VACANT,
                OfficeConceptStatus.DISPUTED,
            }:
                continue
            role_channel = _role_channel(concept)
            channels[role_channel.channel_id] = role_channel
            produced, evidence = _office_candidates(concept, role_channel)
            channel_evidence[role_channel.channel_id] = evidence
            candidates.extend(produced)

    if institution_concepts is not None:
        previous_channels = tuple(channels.values())
        for institution_concept in institution_concepts.concepts:
            if institution_concept.procedure_recurrence <= 0.0:
                continue
            if not any(
                item.pattern is InstitutionPatternChannel.PROCEDURE_RECURRENCE
                for item in institution_concept.evidence
            ):
                continue
            procedure_channel = _procedure_channel(
                institution_concept, previous_channels
            )
            if procedure_channel is None:
                continue
            channels[procedure_channel.channel_id] = procedure_channel
            produced, evidence = _procedure_candidates(
                institution_concept, procedure_channel
            )
            channel_evidence[procedure_channel.channel_id] = evidence
            candidates.extend(produced)

    candidates.extend(_occurrence_candidates(observation, channel_evidence))
    if not candidates and previous is None:
        _LOG.debug(
            "institutional_memory_update owner_id=%s channel_count=%s "
            "entry_count=%s reason=%s",
            owner_id.value,
            0,
            0,
            "no_content",
        )

    candidates.sort(key=lambda item: (item.tick, item.source_ref, item.fact.subject))
    existing_receipts = set(ledger.acquisition_receipt_keys)
    existing_refs: set[tuple[str | None, str | None]] = {
        (entry.channel_id, provenance.occurrence_ref)
        for entry in ledger.entries
        for provenance in entry.provenance
        if provenance.occurrence_ref is not None
    }
    next_ordinal = (
        0 if not ledger.entries else max(entry.ordinal for entry in ledger.entries) + 1
    )
    new_entries: list[InstitutionalMemoryEntry] = []
    groups: list[list[_InstitutionalCandidate]] = []
    current: list[_InstitutionalCandidate] = []
    for candidate in candidates:
        if current and (
            candidate.channel_id,
            candidate.tick,
            candidate.source_ref,
        ) != (
            current[0].channel_id,
            current[0].tick,
            current[0].source_ref,
        ):
            groups.append(current)
            current = []
        current.append(candidate)
    if current:
        groups.append(current)
    for group in groups:
        for index in range(0, len(group), _MAX_FACTS):
            chunk = group[index : index + _MAX_FACTS]
            first = chunk[0]
            key = f"{first.channel_id or 'unbound'}|{first.tick}|{first.source_ref}"
            if key in existing_receipts:
                continue
            if (first.channel_id, first.source_ref) in existing_refs:
                continue
            entry = InstitutionalMemoryEntry(
                owner_id=owner_id,
                entry_id=institutional_entry_id(
                    owner_id, first.channel_id, next_ordinal
                ),
                channel_id=first.channel_id,
                ordinal=next_ordinal,
                revision=0,
                facts=tuple(item.fact for item in chunk),
                declared_fact_count=len(chunk),
                acquisition_tick=first.tick,
                confidence=first.confidence,
                distorted=False,
                partial=False,
                active=True,
                ignored=False,
                provenance=(
                    InstitutionalProvenance(
                        immediate_channel=InstitutionalMemoryChannel.OBSERVATION,
                        occurrence_ref=first.source_ref,
                    ),
                ),
                binding_kind=first.binding_kind,
                binding_function_token=first.binding_function_token,
                binding_context_digest=first.binding_context_digest,
            )
            next_ordinal += 1
            new_entries.append(entry)
            existing_receipts.add(key)

    channel_list = tuple(sorted(channels.values(), key=lambda item: item.channel_id))
    existing_ids = {entry.entry_id for entry in ledger.entries}
    for entry in new_entries:
        existing_refs.add(
            (
                entry.channel_id,
                None if not entry.provenance else entry.provenance[0].occurrence_ref,
            )
        )
    acquired = _record_acquisitions(
        owner_id=owner_id,
        observation=observation,
        previous=ledger,
        interpretations=(
            artifact_interpretations
            if type(artifact_interpretations) is ArtifactInterpretationLedger
            else None
        ),
        channels=channel_list,
    )
    acquired.extend(
        _speech_acquisitions(
            observation=observation,
            identity=identity,
            channels=channel_list,
            relationships=relationships,
            teaching_enabled=teaching_enabled,
        )
    )
    for item in acquired:
        if item.receipt_key in existing_receipts:
            continue
        if any(
            (item.channel_id, provenance.occurrence_ref) in existing_refs
            for provenance in item.provenance
        ):
            continue
        entry = InstitutionalMemoryEntry(
            owner_id=owner_id,
            entry_id=institutional_entry_id(owner_id, item.channel_id, next_ordinal),
            channel_id=item.channel_id,
            ordinal=next_ordinal,
            revision=0,
            facts=item.facts,
            declared_fact_count=item.declared_fact_count,
            acquisition_tick=item.tick,
            confidence=item.confidence,
            distorted=item.distorted,
            partial=item.partial,
            active=True,
            ignored=False,
            provenance=item.provenance,
            binding_kind=item.binding_kind,
            binding_function_token=item.binding_function_token,
            binding_context_digest=item.binding_context_digest,
        )
        next_ordinal += 1
        new_entries.append(entry)
        existing_receipts.add(item.receipt_key)
        for provenance in item.provenance:
            existing_refs.add((item.channel_id, provenance.occurrence_ref))
    rebound: list[InstitutionalMemoryEntry] = []
    for entry in ledger.entries:
        updated = _reconsider_binding(entry, channel_list, existing_ids)
        if updated is not entry:
            existing_ids.discard(entry.entry_id)
            existing_ids.add(updated.entry_id)
        rebound.append(updated)

    entries = tuple(rebound) + tuple(new_entries)
    while len(entries) > resolved.max_entries:
        oldest = min(entries, key=lambda item: (item.acquisition_tick, item.entry_id))
        entries = tuple(item for item in entries if item is not oldest)
    first_tick = ledger.first_observed_tick
    if first_tick is None:
        first_tick = observation.tick
    updated_ledger = replace(
        ledger,
        channels=channel_list,
        entries=entries,
        acquisition_receipt_keys=tuple(existing_receipts),
        first_observed_tick=first_tick,
        last_observed_tick=observation.tick,
        observation_count=ledger.observation_count + 1,
    )
    _LOG.debug(
        "institutional_memory_update owner_id=%s channel_count=%s entry_count=%s "
        "candidate_count=%s",
        owner_id.value,
        len(channel_list),
        len(entries),
        len(candidates),
    )
    return updated_ledger


@dataclass(frozen=True, slots=True)
class _AcquiredEntry:
    channel_id: str | None
    facts: tuple[InstitutionalFact, ...]
    declared_fact_count: int
    tick: int
    confidence: float
    distorted: bool
    partial: bool
    provenance: tuple[InstitutionalProvenance, ...]
    receipt_key: str
    binding_kind: InstitutionalBindingKind | None = None
    binding_function_token: str | None = None
    binding_context_digest: str | None = None


def _bind_frame(frame: object, channels: Sequence[InstitutionalChannel]) -> str | None:
    from agents.cognition.institutional_memory_frames import (
        InstitutionalMemoryFrame,
    )

    if type(frame) is not InstitutionalMemoryFrame:
        return None
    context_digest = frame.context_digest.removeprefix("c_")
    if frame.binding_kind is InstitutionalBindingKind.ROLE:
        matches = tuple(
            channel
            for channel in channels
            if channel.binding_kind is InstitutionalBindingKind.ROLE
            and channel.public_function_token == frame.function_token
            and channel.context_digest == context_digest
        )
    else:
        matches = tuple(
            channel
            for channel in channels
            if channel.binding_kind is InstitutionalBindingKind.PROCEDURE
            and channel.context_digest == context_digest
        )
    if len(matches) != 1:
        _LOG.debug(
            "institutional_frame_binding reason=%s",
            "ambiguous_binding" if matches else "unbound",
        )
        return None
    return matches[0].channel_id


def _record_acquisitions(
    *,
    owner_id: AgentId,
    observation: Observation,
    previous: InstitutionalMemoryLedger,
    interpretations: ArtifactInterpretationLedger | None,
    channels: Sequence[InstitutionalChannel],
) -> list[_AcquiredEntry]:
    if interpretations is None:
        return []
    from agents.cognition.institutional_memory_frames import (
        decode_institutional_marks,
    )

    by_artifact: dict[str, ArtifactInterpretation] = {
        entry.artifact_id.value: entry for entry in interpretations.interpretations
    }
    acquired: list[_AcquiredEntry] = []
    for artifact in observation.artifacts:
        reading = by_artifact.get(artifact.entity_id.value)
        if reading is None or reading.observed_revision != artifact.content_revision:
            continue
        frame = decode_institutional_marks(reading.reading_marks)
        if frame is None:
            _LOG.debug("institutional_record_skipped reason=%s", "invalid_frame")
            continue
        channel_id = _bind_frame(frame, channels)
        damaged = artifact.integrity in {
            RecordIntegrity.DAMAGED,
            RecordIntegrity.PARTIALLY_LOST,
        }
        confidence = reading.confidence
        if damaged:
            confidence = max(0.0, confidence * 0.5)
        root = artifact.source_artifact_id or artifact.entity_id
        acquired.append(
            _AcquiredEntry(
                channel_id=channel_id,
                facts=frame.facts,
                declared_fact_count=frame.declared_fact_count or len(frame.facts),
                tick=reading.source_tick,
                confidence=confidence,
                distorted=reading.distorted or damaged,
                partial=frame.partial or damaged,
                provenance=(
                    InstitutionalProvenance(
                        immediate_channel=InstitutionalMemoryChannel.RECORD,
                        occurrence_ref=(
                            None
                            if reading.source_event_id is None
                            else reading.source_event_id.value
                        )
                        or f"{artifact.entity_id.value}|{artifact.content_revision}",
                        artifact_id=artifact.entity_id,
                        artifact_revision=artifact.content_revision,
                        artifact_parent_id=artifact.parent_artifact_id,
                        artifact_root_id=root,
                        declared_frame_root=frame.root,
                        declared_frame_parent=frame.parent,
                    ),
                ),
                receipt_key=(
                    f"record|{artifact.entity_id.value}|"
                    f"{artifact.content_revision}|{frame.root}"
                ),
                binding_kind=frame.binding_kind,
                binding_function_token=frame.function_token,
                binding_context_digest=frame.context_digest.removeprefix("c_"),
            )
        )
    return acquired


def _trust_factor(
    relationships: _Mapping[str, float] | None, agent_id: AgentId
) -> float:
    if relationships is None:
        return 0.75
    value = relationships.get(agent_id.value)
    if value is None or isinstance(value, bool) or type(value) not in {int, float}:
        return 0.75
    number = float(value)
    if not math.isfinite(number) or number < 0.0 or number > 1.0:
        return 0.75
    return 0.5 + 0.5 * number


def _speech_acquisitions(
    *,
    observation: Observation,
    identity: OwnerSafeSocialIdentity,
    channels: Sequence[InstitutionalChannel],
    relationships: _Mapping[str, float] | None,
    teaching_enabled: bool,
) -> list[_AcquiredEntry]:
    from agents.cognition.institutional_memory_frames import (
        INSTITUTIONAL_TEACH_PREDICATE,
        InstitutionalMemoryFrame,
        parse_institutional_frame_relation,
    )

    counterpart_by_entity = {
        binding.entity_id.value: binding.agent_id for binding in identity.counterparts
    }
    acquired: list[_AcquiredEntry] = []
    for communication in observation.communications:
        if communication.listener_id != observation.observer_id:
            continue
        speaker = counterpart_by_entity.get(communication.speaker_id.value)
        if speaker is None:
            _LOG.debug("institutional_speech_skipped reason=%s", "unresolved_actor")
            continue
        recognized: list[tuple[int, InstitutionalMemoryFrame, bool]] = []
        for index, relation in enumerate(communication.utterance.content.relations):
            frame = parse_institutional_frame_relation(relation)
            if frame is None:
                continue
            teaching = relation.predicate == INSTITUTIONAL_TEACH_PREDICATE
            if teaching and not teaching_enabled:
                _LOG.debug(
                    "institutional_speech_skipped reason=%s", "teaching_disabled"
                )
                continue
            recognized.append((index, frame, teaching))
        if not recognized:
            continue
        if len(recognized) > 1:
            _LOG.debug("institutional_speech_skipped reason=%s", "ambiguous_binding")
            continue
        index, frame, teaching = recognized[0]
        event_ref = (
            None
            if communication.provenance.source_event_id is None
            else communication.provenance.source_event_id.value
        )
        occurrence_ref = (
            event_ref or communication.utterance.declared.communication_id.value
        )
        factor = _trust_factor(relationships, speaker)
        acquired.append(
            _AcquiredEntry(
                channel_id=_bind_frame(frame, channels),
                facts=frame.facts,
                declared_fact_count=frame.declared_fact_count or len(frame.facts),
                tick=communication.provenance.source_tick,
                confidence=_quantize(0.5 * factor),
                distorted=False,
                partial=frame.partial,
                provenance=(
                    InstitutionalProvenance(
                        immediate_channel=(
                            InstitutionalMemoryChannel.TEACHING
                            if teaching
                            else InstitutionalMemoryChannel.TRANSMISSION
                        ),
                        observed_entity_id=communication.speaker_id,
                        resolved_source_agent_id=speaker,
                        occurrence_ref=occurrence_ref,
                        declared_frame_root=frame.root,
                        declared_frame_parent=frame.parent,
                        declared_transmission=communication.utterance.declared,
                    ),
                ),
                receipt_key=f"speech|{occurrence_ref}|{index}|{frame.root}",
                binding_kind=frame.binding_kind,
                binding_function_token=frame.function_token,
                binding_context_digest=frame.context_digest.removeprefix("c_"),
            )
        )
    return acquired
