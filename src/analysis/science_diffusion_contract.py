"""Closed detached vocabulary for scientific-knowledge diffusion analysis.

The module declares frozen value types only. Objective occurrences, one owner's
subjective evidence, and analytical associations stay separate on purpose:
collapsing them into a single "diffused theory" object would invent a global
scientific registry. Nothing here imports cognition, world authority, API,
persistence, observers, or clients.

Comparable content is represented explicitly. Missing descriptor fields are
``None`` (unknown), never a wildcard: representational equality is not
scientific equivalence, and a fingerprint is a comparison key rather than an
identity.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, NoReturn

from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "DIFFUSION_WINDOW_TICKS",
    "MAX_DIFFUSION_EVENTS",
    "MAX_DIFFUSION_INPUT_ROWS",
    "MAX_DIFFUSION_OWNERS",
    "MAX_DIFFUSION_TICKS",
    "MAX_DIFFUSION_WINDOWS",
    "SCIENCE_DIFFUSION_POLICY_VERSION",
    "SCIENCE_DIFFUSION_TOKEN_HEX_LEN",
    "SCIENCE_DIFFUSION_TOKEN_NAMESPACE",
    "SCIENCE_DIFFUSION_TOKEN_PREFIX",
    "DiffusionAccumulator",
    "DiffusionContextFlag",
    "DiffusionError",
    "DiffusionInputs",
    "DiffusionLane",
    "DiffusionLayer",
    "DiffusionOccurrence",
    "DiffusionReason",
    "DiffusionResolution",
    "DiffusionStage",
    "EvidenceKind",
    "EvidenceRef",
    "HypothesisDescriptor",
    "LaneCoverage",
    "LaneCoverageState",
    "ModelDescriptor",
    "ScienceKind",
    "ScienceVersion",
    "ScienceVersionKey",
    "StagedDiffusionBoundary",
    "canonical_fingerprint",
    "compare_science_versions",
    "derive_diffusion_token",
    "require_capture_plan",
    "require_diffusion_window_index",
    "require_input_row_cap",
    "require_source_prior",
    "restrict_reason",
]

SCIENCE_DIFFUSION_POLICY_VERSION: Final[str] = "science-diffusion.v1"
SCIENCE_DIFFUSION_TOKEN_NAMESPACE: Final[str] = "science-diffusion.v1"
SCIENCE_DIFFUSION_TOKEN_PREFIX: Final[str] = "sdf:"
SCIENCE_DIFFUSION_TOKEN_HEX_LEN: Final[int] = 32

DIFFUSION_WINDOW_TICKS: Final[int] = 32
MAX_DIFFUSION_TICKS: Final[int] = 512
MAX_DIFFUSION_WINDOWS: Final[int] = MAX_DIFFUSION_TICKS // DIFFUSION_WINDOW_TICKS
MAX_DIFFUSION_OWNERS: Final[int] = 128
MAX_DIFFUSION_EVENTS: Final[int] = 32_768
MAX_DIFFUSION_INPUT_ROWS: Final[int] = 16_384

_TOKEN_DOMAINS: Final[frozenset[str]] = frozenset(
    {
        "carrier",
        "entry",
        "evidence",
        "occurrence",
        "owner",
        "receipt",
        "translation",
        "version",
    }
)

_LOG: Final[logging.Logger] = logging.getLogger("analysis.science_diffusion_contract")

_HYPOTHESIS_FIELDS: Final[tuple[str, ...]] = (
    "operator",
    "operand_refs",
    "process",
    "predicted_outcome",
    "conditions",
)
_MODEL_FIELDS: Final[tuple[str, ...]] = (
    "target_kind",
    "target_ref",
    "unit",
    "horizon",
    "variant",
    "conditions",
    "predicted_class",
    "parameter_digest",
)


class DiffusionError(ValueError):
    """Fail-closed analysis error carrying only a stable reason code."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code: str = require_stable_id("reason_code", reason_code)
        super().__init__(reason_code)


def _fail(reason_code: str) -> NoReturn:
    raise DiffusionError(reason_code)


class DiffusionLane(StrEnum):
    """Closed evidence lanes, each with its own denominator."""

    SCIENCE = "science"
    SPEECH = "speech"
    TEACHING = "teaching"
    RECORDS = "records"
    KNOWLEDGE_GENEALOGY = "knowledge_genealogy"
    ORGANIZATIONS = "organizations"
    MIGRATION = "migration"
    SOCIETIES = "societies"
    TRANSLATION = "translation"


class LaneCoverageState(StrEnum):
    """Per-lane availability; absence is never reported as zero."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class DiffusionLayer(StrEnum):
    """The three representations that must never be collapsed."""

    OBJECTIVE_OCCURRENCE = "objective_occurrence"
    OWNER_EVIDENCE = "owner_evidence"
    ANALYTICAL_ASSOCIATION = "analytical_association"


class ScienceKind(StrEnum):
    """Closed scientific version families tracked by diffusion."""

    HYPOTHESIS = "hypothesis"
    MODEL = "model"


class EvidenceKind(StrEnum):
    """Closed evidence reference kinds retained by the neutral sidecar."""

    EVENT = "event"
    OWNER_ROW = "owner_row"
    ARTIFACT = "artifact"
    CARRIER = "carrier"
    KNOWLEDGE_ENTRY = "knowledge_entry"


class DiffusionStage(StrEnum):
    """Closed normalized transmission stages."""

    DELIVERED = "delivered"
    INTERPRETED = "interpreted"
    ADOPTED = "adopted"
    LOCALLY_DERIVED = "locally_derived"
    REPORTED_REFERENCE = "reported_reference"
    CARRIED = "carried"


class DiffusionResolution(StrEnum):
    """Closed per-occurrence resolution, distinct from lane availability."""

    CONFIRMED = "confirmed"
    UNRESOLVED = "unresolved"
    AMBIGUOUS = "ambiguous"
    EXCLUDED = "excluded"


class DiffusionContextFlag(StrEnum):
    """Nonadditive contextual labels attached to one occurrence."""

    ORGANIZATION_MEDIATED = "organization_mediated"
    SHARED_ORG_CONTEXT = "shared_org_context"
    CARRIED_ACROSS_REGION = "carried_across_region"
    CROSS_SOCIETY = "cross_society"
    TRANSLATION_APPLIED = "translation_applied"
    PHYSICAL_CARRIER = "physical_carrier"


class DiffusionReason(StrEnum):
    """Closed reason codes; join flags are not availability states."""

    IDENTITY_CONFLICT = "identity_conflict"
    UNSUPPORTED_SCHEMA = "unsupported_schema"
    COVERAGE_GAP = "coverage_gap"
    LIMIT_REACHED = "limit_reached"
    SOURCE_NOT_PRIOR = "source_not_prior"
    MALFORMED_EVIDENCE = "malformed_evidence"
    UNVERIFIED_REFERENCE = "unverified_reference"
    AMBIGUOUS_SOURCE = "ambiguous_source"
    UNADDRESSED = "unaddressed"
    MARKER_INCOMPLETE = "marker_incomplete"
    RELAY_PARENT_MISSING = "relay_parent_missing"
    RECORD_REVISION_MISSING = "record_revision_missing"
    GENEALOGY_ANCHOR_MISSING = "genealogy_anchor_missing"
    MEMBERSHIP_UNKNOWN = "membership_unknown"
    OVERLAPPING_MEMBERSHIP = "overlapping_membership"
    UNQUALIFIED_ARRIVAL = "unqualified_arrival"
    TRANSLATION_UNBOUND = "translation_unbound"
    PARTIAL_READ = "partial_read"
    DIVERGENT_READ = "divergent_read"


def restrict_reason(value: object) -> DiffusionReason | None:
    """Normalize an optional closed reason code."""

    if value is None:
        return None
    if type(value) is not DiffusionReason:
        _fail(DiffusionReason.UNSUPPORTED_SCHEMA.value)
    return value


def require_diffusion_window_index(value: object) -> int:
    """Validate one absolute 32-tick window index."""

    index = _require_tick("window_index", value)
    if index >= MAX_DIFFUSION_WINDOWS:
        _fail(DiffusionReason.LIMIT_REACHED.value)
    return index


def require_capture_plan(
    *, committed_ticks: object, owner_count: object, cumulative_events: object
) -> tuple[int, int, int]:
    """Preflight a capture plan before any checkpoint export is requested."""

    ticks = _require_tick("committed_ticks", committed_ticks)
    owners = _require_tick("owner_count", owner_count)
    events = _require_tick("cumulative_events", cumulative_events)
    if ticks > MAX_DIFFUSION_TICKS:
        _fail(DiffusionReason.LIMIT_REACHED.value)
    if owners > MAX_DIFFUSION_OWNERS:
        _fail(DiffusionReason.LIMIT_REACHED.value)
    if events > MAX_DIFFUSION_EVENTS:
        _fail(DiffusionReason.LIMIT_REACHED.value)
    return ticks, owners, events


def require_input_row_cap(value: object) -> int:
    """Reject normalized input beyond the cumulative row cap."""

    rows = _require_tick("input_row_count", value)
    if rows > MAX_DIFFUSION_INPUT_ROWS:
        _fail(DiffusionReason.LIMIT_REACHED.value)
    return rows


def derive_diffusion_token(domain: str, *parts: str) -> str:
    """Derive one run-scoped opaque token in an explicit digest domain."""

    if domain not in _TOKEN_DOMAINS:
        _fail(DiffusionReason.MALFORMED_EVIDENCE.value)
    if not parts:
        _fail(DiffusionReason.MALFORMED_EVIDENCE.value)
    material: list[str] = []
    for part in parts:
        if type(part) is not str or not part:
            _fail(DiffusionReason.MALFORMED_EVIDENCE.value)
        material.append(part)
    payload = "\x1f".join((SCIENCE_DIFFUSION_TOKEN_NAMESPACE, domain, *material))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"{SCIENCE_DIFFUSION_TOKEN_PREFIX}{digest[:SCIENCE_DIFFUSION_TOKEN_HEX_LEN]}"


def _canonical_value(value: object) -> object:
    if value is None or type(value) is bool:
        return value
    if type(value) is int:
        return value
    if type(value) is str:
        return value
    if isinstance(value, Mapping):
        out: dict[str, object] = {}
        for key, item in value.items():
            if type(key) is not str or not key:
                _fail(DiffusionReason.MALFORMED_EVIDENCE.value)
            out[key] = _canonical_value(item)
        return out
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    _fail(DiffusionReason.MALFORMED_EVIDENCE.value)


def canonical_fingerprint(domain: str, value: object) -> str:
    """Return a domain-separated SHA-256 over canonical compact JSON."""

    if type(domain) is not str or not domain:
        _fail(DiffusionReason.MALFORMED_EVIDENCE.value)
    normalized = _canonical_value(value)
    payload = json.dumps(
        normalized,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    framed = b"\x1f".join(
        (
            SCIENCE_DIFFUSION_TOKEN_NAMESPACE.encode("utf-8"),
            domain.encode("utf-8"),
            payload,
        )
    )
    return hashlib.sha256(framed).hexdigest()


def require_source_prior(
    *,
    source_tick: object,
    target_tick: object,
    source_sequence: object = None,
    target_sequence: object = None,
    causal_evidence: bool = False,
) -> None:
    """Enforce causal ordering, including the bounded same-tick exception."""

    left = _require_tick("source_tick", source_tick)
    right = _require_tick("target_tick", target_tick)
    if left < right:
        return
    if left > right:
        _fail(DiffusionReason.SOURCE_NOT_PRIOR.value)
    if not causal_evidence:
        _fail(DiffusionReason.SOURCE_NOT_PRIOR.value)
    if source_sequence is None or target_sequence is None:
        _fail(DiffusionReason.SOURCE_NOT_PRIOR.value)
    source_order = _require_tick("source_sequence", source_sequence)
    target_order = _require_tick("target_sequence", target_sequence)
    if source_order >= target_order:
        _fail(DiffusionReason.SOURCE_NOT_PRIOR.value)


def _require_tick(name: str, value: object) -> int:
    try:
        return require_exact_nonneg_int(name, value)
    except (TypeError, ValueError) as exc:
        raise DiffusionError(DiffusionReason.MALFORMED_EVIDENCE.value) from exc


def _require_text(name: str, value: object) -> str:
    try:
        return require_stable_id(name, value)
    except (TypeError, ValueError) as exc:
        raise DiffusionError(DiffusionReason.MALFORMED_EVIDENCE.value) from exc


def _sorted_pairs(
    name: str, values: object
) -> tuple[tuple[str, str], ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        _fail(DiffusionReason.MALFORMED_EVIDENCE.value)
    out: list[tuple[str, str]] = []
    for entry in values:
        if not isinstance(entry, tuple) or len(entry) != 2:
            _fail(DiffusionReason.MALFORMED_EVIDENCE.value)
        key, value = entry
        out.append((_require_text(f"{name}.key", key), _require_text(name, value)))
    if len(set(out)) != len(out):
        _fail(DiffusionReason.IDENTITY_CONFLICT.value)
    if tuple(out) != tuple(sorted(out)):
        _fail(DiffusionReason.MALFORMED_EVIDENCE.value)
    return tuple(out)


def _require_typed_ref(name: str, value: object) -> str:
    ref = _require_text(name, value)
    if ":" not in ref:
        _fail(DiffusionReason.MALFORMED_EVIDENCE.value)
    kind, _, token = ref.partition(":")
    if not kind or not token or kind != kind.lower():
        _fail(DiffusionReason.MALFORMED_EVIDENCE.value)
    return ref


@dataclass(frozen=True, slots=True)
class EvidenceRef:
    """One exact retained evidence reference with its provenance binding."""

    kind: EvidenceKind
    run_id: str
    tick: int
    event_id: str | None = None
    sequence: int | None = None
    owner_id: str | None = None
    local_id: str | None = None
    revision_index: int | None = None
    carrier_id: str | None = None
    content_revision: int | None = None
    entry_id: str | None = None

    def __post_init__(self) -> None:
        if type(self.kind) is not EvidenceKind:
            _fail(DiffusionReason.UNSUPPORTED_SCHEMA.value)
        object.__setattr__(self, "run_id", _require_text("run_id", self.run_id))
        object.__setattr__(self, "tick", _require_tick("tick", self.tick))
        for name in (
            "event_id",
            "owner_id",
            "local_id",
            "carrier_id",
            "entry_id",
        ):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _require_text(name, value))
        for name in ("sequence", "revision_index", "content_revision"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _require_tick(name, value))
        required: dict[EvidenceKind, tuple[str, ...]] = {
            EvidenceKind.EVENT: ("event_id", "sequence"),
            EvidenceKind.OWNER_ROW: ("owner_id", "local_id", "revision_index"),
            EvidenceKind.ARTIFACT: ("carrier_id", "content_revision"),
            EvidenceKind.CARRIER: ("carrier_id",),
            EvidenceKind.KNOWLEDGE_ENTRY: ("owner_id", "entry_id"),
        }
        for name in required[self.kind]:
            if getattr(self, name) is None:
                _fail(DiffusionReason.MALFORMED_EVIDENCE.value)
        forbidden = {
            EvidenceKind.EVENT: ("owner_id", "local_id", "revision_index", "entry_id"),
            EvidenceKind.OWNER_ROW: ("event_id", "sequence", "entry_id"),
            EvidenceKind.ARTIFACT: ("event_id", "sequence", "owner_id", "entry_id"),
            EvidenceKind.CARRIER: (
                "event_id",
                "sequence",
                "owner_id",
                "local_id",
                "revision_index",
                "entry_id",
            ),
            EvidenceKind.KNOWLEDGE_ENTRY: (
                "event_id",
                "sequence",
                "local_id",
                "revision_index",
                "entry_id",
            ),
        }
        for name in forbidden[self.kind]:
            if getattr(self, name) is not None:
                _fail(DiffusionReason.MALFORMED_EVIDENCE.value)

    def qualified_key(self) -> tuple[object, ...]:
        """Return the exact retained reference key used for deduplication."""

        return (
            self.kind.value,
            self.run_id,
            self.tick,
            self.event_id,
            self.sequence,
            self.owner_id,
            self.local_id,
            self.revision_index,
            self.carrier_id,
            self.content_revision,
            self.entry_id,
        )


@dataclass(frozen=True, slots=True)
class ScienceVersionKey:
    """Qualified identity of one immutable owner science version."""

    run_id: str
    owner_id: str
    kind: ScienceKind
    local_id: str
    revision_index: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _require_text("run_id", self.run_id))
        object.__setattr__(self, "owner_id", _require_text("owner_id", self.owner_id))
        if type(self.kind) is not ScienceKind:
            _fail(DiffusionReason.UNSUPPORTED_SCHEMA.value)
        object.__setattr__(self, "local_id", _require_text("local_id", self.local_id))
        object.__setattr__(
            self,
            "revision_index",
            _require_tick("revision_index", self.revision_index),
        )

    def as_tuple(self) -> tuple[str, str, str, str, int]:
        """Return a stable sort/comparison tuple."""

        return (
            self.run_id,
            self.owner_id,
            self.kind.value,
            self.local_id,
            self.revision_index,
        )

    def token(self) -> str:
        """Return an opaque run-qualified token for this version."""

        run_id, owner_id, kind, local_id, revision_index = self.as_tuple()
        return derive_diffusion_token(
            "version", run_id, owner_id, kind, local_id, str(revision_index)
        )


@dataclass(frozen=True, slots=True)
class HypothesisDescriptor:
    """Explicit comparable representation of one hypothesis revision."""

    operator: str
    operand_refs: tuple[str, ...]
    process: str
    predicted_outcome: str | None = None
    conditions: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "operator", _require_text("operator", self.operator))
        object.__setattr__(self, "process", _require_text("process", self.process))
        if (
            isinstance(self.operand_refs, (str, bytes))
            or not isinstance(self.operand_refs, Sequence)
            or not 1 <= len(self.operand_refs) <= 2
        ):
            _fail(DiffusionReason.MALFORMED_EVIDENCE.value)
        operands = tuple(
            _require_typed_ref("operand_ref", item) for item in self.operand_refs
        )
        object.__setattr__(self, "operand_refs", operands)
        if self.predicted_outcome is not None:
            object.__setattr__(
                self,
                "predicted_outcome",
                _require_text("predicted_outcome", self.predicted_outcome),
            )
        object.__setattr__(
            self, "conditions", _sorted_pairs("conditions", self.conditions)
        )

    def comparable_fields(self) -> dict[str, object]:
        return {
            "operator": self.operator,
            "operand_refs": list(self.operand_refs),
            "process": self.process,
            "predicted_outcome": self.predicted_outcome,
            "conditions": [list(item) for item in self.conditions],
        }


@dataclass(frozen=True, slots=True)
class ModelDescriptor:
    """Explicit comparable representation of one predictive-model revision."""

    target_kind: str
    target_ref: str
    unit: str
    horizon: int
    variant: str
    conditions: tuple[tuple[str, str], ...] = ()
    predicted_class: str | None = None
    parameter_digest: str = ""
    parameter_scope: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "target_kind", _require_text("target_kind", self.target_kind)
        )
        object.__setattr__(
            self, "target_ref", _require_typed_ref("target_ref", self.target_ref)
        )
        object.__setattr__(self, "unit", _require_text("unit", self.unit))
        horizon = _require_tick("horizon", self.horizon)
        if horizon < 1:
            _fail(DiffusionReason.MALFORMED_EVIDENCE.value)
        object.__setattr__(self, "horizon", horizon)
        object.__setattr__(self, "variant", _require_text("variant", self.variant))
        object.__setattr__(
            self, "conditions", _sorted_pairs("conditions", self.conditions)
        )
        if self.predicted_class is not None:
            object.__setattr__(
                self,
                "predicted_class",
                _require_text("predicted_class", self.predicted_class),
            )
        if self.parameter_digest:
            object.__setattr__(
                self,
                "parameter_digest",
                _require_text("parameter_digest", self.parameter_digest),
            )
            object.__setattr__(
                self,
                "parameter_scope",
                _require_text("parameter_scope", self.parameter_scope),
            )
        elif self.parameter_scope:
            _fail(DiffusionReason.MALFORMED_EVIDENCE.value)

    def comparable_fields(self) -> dict[str, object]:
        return {
            "target_kind": self.target_kind,
            "target_ref": self.target_ref,
            "unit": self.unit,
            "horizon": self.horizon,
            "variant": self.variant,
            "conditions": [list(item) for item in self.conditions],
            "predicted_class": self.predicted_class,
            "parameter_digest": self.parameter_digest,
        }


@dataclass(frozen=True, slots=True)
class ScienceVersion:
    """One immutable owner science version plus exact retention evidence."""

    key: ScienceVersionKey
    occurrence_tick: int
    first_observed_boundary: int
    wire: tuple[tuple[str, str], ...]
    hypothesis: HypothesisDescriptor | None = None
    model: ModelDescriptor | None = None
    evidence: EvidenceRef | None = None
    root_kind: str = ""
    root_ref: str = ""

    def __post_init__(self) -> None:
        if type(self.key) is not ScienceVersionKey:
            _fail(DiffusionReason.UNSUPPORTED_SCHEMA.value)
        object.__setattr__(
            self,
            "occurrence_tick",
            _require_tick("occurrence_tick", self.occurrence_tick),
        )
        observed = _require_tick(
            "first_observed_boundary", self.first_observed_boundary
        )
        if observed < self.occurrence_tick:
            _fail(DiffusionReason.SOURCE_NOT_PRIOR.value)
        object.__setattr__(self, "first_observed_boundary", observed)
        object.__setattr__(self, "wire", _sorted_pairs("wire", self.wire))
        if (self.hypothesis is None) == (self.model is None):
            _fail(DiffusionReason.MALFORMED_EVIDENCE.value)
        if self.key.kind is ScienceKind.HYPOTHESIS:
            if type(self.hypothesis) is not HypothesisDescriptor:
                _fail(DiffusionReason.MALFORMED_EVIDENCE.value)
        elif type(self.model) is not ModelDescriptor:
            _fail(DiffusionReason.MALFORMED_EVIDENCE.value)
        for name in ("root_kind", "root_ref"):
            value = getattr(self, name)
            if value:
                object.__setattr__(self, name, _require_text(name, value))
        if bool(self.root_kind) != bool(self.root_ref):
            _fail(DiffusionReason.MALFORMED_EVIDENCE.value)
        if self.evidence is not None:
            if type(self.evidence) is not EvidenceRef:
                _fail(DiffusionReason.UNSUPPORTED_SCHEMA.value)
            if self.evidence.run_id != self.key.run_id:
                _fail(DiffusionReason.IDENTITY_CONFLICT.value)
            if self.evidence.tick > self.occurrence_tick:
                _fail(DiffusionReason.SOURCE_NOT_PRIOR.value)

    def descriptor_fields(self) -> dict[str, object]:
        """Return only content-comparable fields, excluding owner and clocks."""

        if self.hypothesis is not None:
            return self.hypothesis.comparable_fields()
        assert self.model is not None
        return self.model.comparable_fields()

    def content_fingerprint(self) -> str:
        """Return a representational comparison key, never an identity."""

        domain = f"science-{self.key.kind.value}-content"
        return canonical_fingerprint(domain, self.descriptor_fields())

    def with_first_observed(self, boundary: int) -> ScienceVersion:
        """Return the same row anchored no later than the first observation."""

        candidate = _require_tick("first_observed_boundary", boundary)
        if candidate >= self.first_observed_boundary:
            return self
        return ScienceVersion(
            key=self.key,
            occurrence_tick=self.occurrence_tick,
            first_observed_boundary=candidate,
            wire=self.wire,
            hypothesis=self.hypothesis,
            model=self.model,
            evidence=self.evidence,
            root_kind=self.root_kind,
            root_ref=self.root_ref,
        )


def compare_science_versions(
    left: ScienceVersion, right: ScienceVersion
) -> tuple[str, ...]:
    """Return changed content-field categories; empty means representational match."""

    if type(left) is not ScienceVersion or type(right) is not ScienceVersion:
        _fail(DiffusionReason.UNSUPPORTED_SCHEMA.value)
    if left.key.kind is not right.key.kind:
        return ("kind",)
    left_fields = left.descriptor_fields()
    right_fields = right.descriptor_fields()
    if left.key.kind is ScienceKind.HYPOTHESIS:
        fields = _HYPOTHESIS_FIELDS
    else:
        fields = _MODEL_FIELDS
        left_model = left.model
        right_model = right.model
        assert left_model is not None and right_model is not None
        if left_model.parameter_scope != right_model.parameter_scope:
            fields = tuple(name for name in _MODEL_FIELDS if name != "parameter_digest")
            scope_changed = [
                name
                for name in fields
                if left_fields.get(name) != right_fields.get(name)
            ]
            return tuple((*scope_changed, "parameter_scope"))
    changed: list[str] = []
    for name in fields:
        if left_fields.get(name) != right_fields.get(name):
            changed.append(name)
    return tuple(changed)


@dataclass(frozen=True, slots=True)
class LaneCoverage:
    """Half-open coverage of one closed lane over absolute ticks."""

    lane: DiffusionLane
    start_tick: int
    end_tick_exclusive: int
    state: LaneCoverageState
    observed: int = 0
    reason: DiffusionReason | None = None

    def __post_init__(self) -> None:
        if type(self.lane) is not DiffusionLane:
            _fail(DiffusionReason.UNSUPPORTED_SCHEMA.value)
        start = _require_tick("start_tick", self.start_tick)
        end = _require_tick("end_tick_exclusive", self.end_tick_exclusive)
        if end <= start:
            _fail(DiffusionReason.MALFORMED_EVIDENCE.value)
        object.__setattr__(self, "start_tick", start)
        object.__setattr__(self, "end_tick_exclusive", end)
        if type(self.state) is not LaneCoverageState:
            _fail(DiffusionReason.UNSUPPORTED_SCHEMA.value)
        object.__setattr__(self, "observed", _require_tick("observed", self.observed))
        reason = restrict_reason(self.reason)
        if self.state is LaneCoverageState.COMPLETE:
            if reason is not None:
                _fail(DiffusionReason.MALFORMED_EVIDENCE.value)
        elif reason is None:
            _fail(DiffusionReason.MALFORMED_EVIDENCE.value)
        object.__setattr__(self, "reason", reason)

    def covers(self, tick: int) -> bool:
        return self.start_tick <= tick < self.end_tick_exclusive


@dataclass(frozen=True, slots=True)
class DiffusionOccurrence:
    """One lane-local occurrence with exact provenance and resolution."""

    run_id: str
    lane: DiffusionLane
    occurrence_kind: str
    tick: int
    first_observed_boundary: int
    evidence: EvidenceRef
    stage: DiffusionStage
    confirmation_boundary: int | None = None
    actor_id: str | None = None
    counterparty_id: str | None = None
    source_version: ScienceVersionKey | None = None
    variant_version: ScienceVersionKey | None = None
    target_version: ScienceVersionKey | None = None
    carrier_kind: str | None = None
    carrier_id: str | None = None
    content_revision: int | None = None
    context_flags: tuple[DiffusionContextFlag, ...] = ()
    detail: tuple[tuple[str, str], ...] = ()
    resolution: DiffusionResolution = DiffusionResolution.CONFIRMED
    reason: DiffusionReason | None = None
    same_tick_causal_ref: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _require_text("run_id", self.run_id))
        if type(self.lane) is not DiffusionLane:
            _fail(DiffusionReason.UNSUPPORTED_SCHEMA.value)
        object.__setattr__(
            self,
            "occurrence_kind",
            _require_text("occurrence_kind", self.occurrence_kind),
        )
        tick = _require_tick("tick", self.tick)
        observed = _require_tick(
            "first_observed_boundary", self.first_observed_boundary
        )
        if observed < tick:
            _fail(DiffusionReason.SOURCE_NOT_PRIOR.value)
        object.__setattr__(self, "tick", tick)
        object.__setattr__(self, "first_observed_boundary", observed)
        if type(self.evidence) is not EvidenceRef:
            _fail(DiffusionReason.UNSUPPORTED_SCHEMA.value)
        if self.evidence.run_id != self.run_id:
            _fail(DiffusionReason.IDENTITY_CONFLICT.value)
        if self.evidence.tick > tick:
            _fail(DiffusionReason.SOURCE_NOT_PRIOR.value)
        if type(self.stage) is not DiffusionStage:
            _fail(DiffusionReason.UNSUPPORTED_SCHEMA.value)
        confirmation = self.confirmation_boundary
        if confirmation is not None:
            confirmation = _require_tick("confirmation_boundary", confirmation)
            if confirmation < observed:
                _fail(DiffusionReason.SOURCE_NOT_PRIOR.value)
        object.__setattr__(self, "confirmation_boundary", confirmation)
        for name in ("actor_id", "counterparty_id", "carrier_kind", "carrier_id"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _require_text(name, value))
        for name in ("content_revision",):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _require_tick(name, value))
        for name in ("source_version", "variant_version", "target_version"):
            value = getattr(self, name)
            if value is not None:
                if type(value) is not ScienceVersionKey:
                    _fail(DiffusionReason.UNSUPPORTED_SCHEMA.value)
                if value.run_id != self.run_id:
                    _fail(DiffusionReason.IDENTITY_CONFLICT.value)
        flags = self.context_flags
        if isinstance(flags, (str, bytes)) or not isinstance(flags, Sequence):
            _fail(DiffusionReason.MALFORMED_EVIDENCE.value)
        seen: set[DiffusionContextFlag] = set()
        for flag in flags:
            if type(flag) is not DiffusionContextFlag:
                _fail(DiffusionReason.UNSUPPORTED_SCHEMA.value)
            if flag in seen:
                _fail(DiffusionReason.IDENTITY_CONFLICT.value)
            seen.add(flag)
        object.__setattr__(self, "context_flags", tuple(sorted(seen)))
        object.__setattr__(self, "detail", _sorted_pairs("detail", self.detail))
        if type(self.resolution) is not DiffusionResolution:
            _fail(DiffusionReason.UNSUPPORTED_SCHEMA.value)
        reason = restrict_reason(self.reason)
        if self.resolution is DiffusionResolution.CONFIRMED:
            if reason is not None:
                _fail(DiffusionReason.MALFORMED_EVIDENCE.value)
        elif reason is None:
            _fail(DiffusionReason.MALFORMED_EVIDENCE.value)
        object.__setattr__(self, "reason", reason)
        if self.same_tick_causal_ref:
            object.__setattr__(
                self,
                "same_tick_causal_ref",
                _require_text("same_tick_causal_ref", self.same_tick_causal_ref),
            )

    def sort_key(self) -> tuple[object, ...]:
        return (
            self.lane.value,
            self.tick,
            self.occurrence_kind,
            self.evidence.kind.value,
            self.evidence.tick,
            -1 if self.evidence.sequence is None else self.evidence.sequence,
            self.actor_id or "",
            self.counterparty_id or "",
            self.stage.value,
        )


def _ordered_unique_versions(
    versions: Iterable[ScienceVersion],
) -> tuple[ScienceVersion, ...]:
    retained: dict[ScienceVersionKey, ScienceVersion] = {}
    for version in versions:
        if type(version) is not ScienceVersion:
            _fail(DiffusionReason.UNSUPPORTED_SCHEMA.value)
        prior = retained.get(version.key)
        if prior is None:
            retained[version.key] = version
            continue
        if prior != version:
            _LOG.warning(
                "science_diffusion_identity_conflict run_id=%s kind=%s revision=%s",
                version.key.run_id,
                version.key.kind.value,
                version.key.revision_index,
            )
            _fail(DiffusionReason.IDENTITY_CONFLICT.value)
    return tuple(sorted(retained.values(), key=lambda item: item.key.as_tuple()))


@dataclass(frozen=True, slots=True)
class StagedDiffusionBoundary:
    """One boundary's normalized additions, staged before state changes."""

    boundary_tick: int
    versions: tuple[ScienceVersion, ...] = ()
    occurrences: tuple[DiffusionOccurrence, ...] = ()
    coverage: tuple[LaneCoverage, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "boundary_tick", _require_tick("boundary_tick", self.boundary_tick)
        )
        object.__setattr__(
            self, "versions", _ordered_unique_versions(self.versions)
        )
        for occurrence in self.occurrences:
            if type(occurrence) is not DiffusionOccurrence:
                _fail(DiffusionReason.UNSUPPORTED_SCHEMA.value)
        object.__setattr__(
            self,
            "occurrences",
            tuple(sorted(self.occurrences, key=lambda item: item.sort_key())),
        )
        for row in self.coverage:
            if type(row) is not LaneCoverage:
                _fail(DiffusionReason.UNSUPPORTED_SCHEMA.value)
        object.__setattr__(
            self,
            "coverage",
            tuple(
                sorted(
                    self.coverage,
                    key=lambda item: (
                        item.lane.value,
                        item.start_tick,
                        item.end_tick_exclusive,
                    ),
                )
            ),
        )

    @property
    def row_count(self) -> int:
        return len(self.versions) + len(self.occurrences) + len(self.coverage)


class DiffusionAccumulator:
    """Bounded, all-or-nothing staging for one capture session.

    A boundary that would overflow the evidence budget is discarded in full and
    the trusted prefix is sealed with one bounded coverage tail per lane. The
    tail reserve lives outside the evidence-row budget, so a biased partial
    batch can never be published as if complete.
    """

    def __init__(
        self, run_id: str, *, max_rows: int = MAX_DIFFUSION_INPUT_ROWS
    ) -> None:
        self._run_id = _require_text("run_id", run_id)
        cap = require_input_row_cap(max_rows)
        self._evidence_cap = cap - len(DiffusionLane)
        self._versions: list[ScienceVersion] = []
        self._occurrences: list[DiffusionOccurrence] = []
        self._coverage: list[LaneCoverage] = []
        self._rows = 0
        self._last_boundary = -1
        self._sealed: DiffusionReason | None = None

    @property
    def row_count(self) -> int:
        return self._rows

    @property
    def sealed(self) -> DiffusionReason | None:
        return self._sealed

    @property
    def last_boundary_tick(self) -> int:
        return self._last_boundary

    def _seal_tail(self, start_tick: int, end_tick: int) -> None:
        if self._sealed is not None:
            return
        start = max(start_tick, 0)
        end = end_tick if end_tick > start else start + 1
        for lane in DiffusionLane:
            self._coverage.append(
                LaneCoverage(
                    lane=lane,
                    start_tick=start,
                    end_tick_exclusive=end,
                    state=LaneCoverageState.PARTIAL,
                    reason=DiffusionReason.LIMIT_REACHED,
                )
            )
        self._sealed = DiffusionReason.LIMIT_REACHED
        _LOG.warning(
            "science_diffusion_capture_sealed run_id=%s start_tick=%s end_tick=%s",
            self._run_id,
            start,
            end,
        )

    def stage(self, boundary: StagedDiffusionBoundary) -> bool:
        """Stage one boundary atomically; return False when it is discarded."""

        if type(boundary) is not StagedDiffusionBoundary:
            _fail(DiffusionReason.UNSUPPORTED_SCHEMA.value)
        if self._sealed is not None:
            return False
        if boundary.boundary_tick <= self._last_boundary:
            _fail(DiffusionReason.SOURCE_NOT_PRIOR.value)
        for occurrence in boundary.occurrences:
            if occurrence.run_id != self._run_id:
                _fail(DiffusionReason.IDENTITY_CONFLICT.value)
        for row in boundary.coverage:
            if row.start_tick < 0:
                _fail(DiffusionReason.MALFORMED_EVIDENCE.value)
        if self._rows + boundary.row_count > self._evidence_cap:
            self._seal_tail(
                self._last_boundary if self._last_boundary >= 0 else 0,
                boundary.boundary_tick,
            )
            return False
        self._versions.extend(boundary.versions)
        self._occurrences.extend(boundary.occurrences)
        self._coverage.extend(boundary.coverage)
        self._rows += boundary.row_count
        self._last_boundary = boundary.boundary_tick
        return True

    def results(self) -> tuple[
        tuple[ScienceVersion, ...],
        tuple[DiffusionOccurrence, ...],
        tuple[LaneCoverage, ...],
    ]:
        return (
            _ordered_unique_versions(self._versions),
            tuple(sorted(self._occurrences, key=lambda item: item.sort_key())),
            tuple(
                sorted(
                    self._coverage,
                    key=lambda item: (
                        item.lane.value,
                        item.start_tick,
                        item.end_tick_exclusive,
                    ),
                )
            ),
        )

    def add_coverage(self, rows: Iterable[LaneCoverage]) -> None:
        """Attach final cumulative lane coverage without consuming evidence rows."""

        if self._sealed is not None:
            return
        for row in rows:
            if type(row) is not LaneCoverage:
                _fail(DiffusionReason.UNSUPPORTED_SCHEMA.value)
            self._coverage.append(row)

    def inputs(self) -> DiffusionInputs:
        versions, occurrences, coverage = self.results()
        return DiffusionInputs(
            run_id=self._run_id,
            versions=versions,
            occurrences=occurrences,
            coverage=coverage,
        )


@dataclass(frozen=True, slots=True)
class DiffusionInputs:
    """Complete neutral input for one detached diffusion assessment."""

    run_id: str
    versions: tuple[ScienceVersion, ...]
    occurrences: tuple[DiffusionOccurrence, ...]
    coverage: tuple[LaneCoverage, ...]
    policy_version: str = SCIENCE_DIFFUSION_POLICY_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _require_text("run_id", self.run_id))
        if self.policy_version != SCIENCE_DIFFUSION_POLICY_VERSION:
            _fail(DiffusionReason.UNSUPPORTED_SCHEMA.value)
        versions = _ordered_unique_versions(self.versions)
        object.__setattr__(self, "versions", versions)
        for occurrence in self.occurrences:
            if type(occurrence) is not DiffusionOccurrence:
                _fail(DiffusionReason.UNSUPPORTED_SCHEMA.value)
            if occurrence.run_id != self.run_id:
                _fail(DiffusionReason.IDENTITY_CONFLICT.value)
        object.__setattr__(
            self,
            "occurrences",
            tuple(sorted(self.occurrences, key=lambda item: item.sort_key())),
        )
        for row in self.coverage:
            if type(row) is not LaneCoverage:
                _fail(DiffusionReason.UNSUPPORTED_SCHEMA.value)
        coverage = tuple(
            sorted(
                self.coverage,
                key=lambda item: (
                    item.lane.value,
                    item.start_tick,
                    item.end_tick_exclusive,
                ),
            )
        )
        last_end: dict[DiffusionLane, int] = {}
        for row in coverage:
            if row.start_tick < last_end.get(row.lane, 0):
                _fail(DiffusionReason.COVERAGE_GAP.value)
            last_end[row.lane] = row.end_tick_exclusive
        object.__setattr__(self, "coverage", coverage)
        self._validate_references()

    def _validate_references(self) -> None:
        known = {version.key for version in self.versions}
        for occurrence in self.occurrences:
            for key in (
                occurrence.source_version,
                occurrence.variant_version,
                occurrence.target_version,
            ):
                if key is not None and key not in known:
                    _LOG.warning(
                        "science_diffusion_foreign_reference run_id=%s lane=%s",
                        self.run_id,
                        occurrence.lane.value,
                    )
                    _fail(DiffusionReason.IDENTITY_CONFLICT.value)
        for occurrence in self.occurrences:
            source = occurrence.source_version
            if source is None:
                continue
            version = next(item for item in self.versions if item.key == source)
            require_source_prior(
                source_tick=version.occurrence_tick,
                target_tick=occurrence.tick,
                source_sequence=(
                    version.evidence.sequence if version.evidence is not None else None
                ),
                target_sequence=occurrence.evidence.sequence,
                causal_evidence=bool(occurrence.same_tick_causal_ref),
            )

    @property
    def row_count(self) -> int:
        return len(self.versions) + len(self.occurrences) + len(self.coverage)

    def version(self, key: ScienceVersionKey) -> ScienceVersion | None:
        for item in self.versions:
            if item.key == key:
                return item
        return None

    def lane_state(self, lane: DiffusionLane) -> LaneCoverageState:
        """Return the coarsest availability of one lane over the input."""

        rows = [item for item in self.coverage if item.lane is lane]
        if not rows:
            return LaneCoverageState.UNAVAILABLE
        if any(item.state is LaneCoverageState.UNAVAILABLE for item in rows):
            return LaneCoverageState.UNAVAILABLE
        if any(item.state is LaneCoverageState.PARTIAL for item in rows):
            return LaneCoverageState.PARTIAL
        return LaneCoverageState.COMPLETE

    def coverage_at(self, lane: DiffusionLane, tick: int) -> LaneCoverage | None:
        for row in self.coverage:
            if row.lane is lane and row.covers(tick):
                return row
        return None
