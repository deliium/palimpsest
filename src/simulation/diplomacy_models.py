"""Canonical ``diplomacy-snapshot-v1`` records.

Every identity field is a hashed token or an owner-safe anchor; raw agent ids,
free-text subjects, and frame bodies never appear.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, fields
from typing import Any, Final, NoReturn

__all__ = [
    "DIPLOMACY_ARTIFACT_ERROR_CODES",
    "DIPLOMACY_CURSOR_PURPOSES",
    "DIPLOMACY_SNAPSHOT_POLICY",
    "DIPLOMACY_SNAPSHOT_SCHEMA",
    "MAX_DETAIL_ROWS",
    "MAX_SNAPSHOT_BYTES",
    "MAX_SNAPSHOT_CANDIDATES",
    "MAX_SNAPSHOT_CONTACTS",
    "MAX_SNAPSHOT_DECLARATIONS",
    "MAX_SNAPSHOT_ENVOYS",
    "MAX_SNAPSHOT_INSTRUMENTS",
    "MAX_SNAPSHOT_LINEAGE",
    "MAX_SNAPSHOT_NEGOTIATIONS",
    "MAX_SNAPSHOT_PARTIES",
    "MAX_SNAPSHOT_RELATIONS",
    "SUPPORTED_DIPLOMACY_SNAPSHOT_SCHEMAS",
    "DiplomacyArtifactError",
    "DiplomacySnapshot",
    "DiplomacySnapshotConflictRow",
    "DiplomacySnapshotContactRow",
    "DiplomacySnapshotDeclarationRow",
    "DiplomacySnapshotEnvoyRow",
    "DiplomacySnapshotInstrumentRow",
    "DiplomacySnapshotLineageRow",
    "DiplomacySnapshotMetricProvenanceRow",
    "DiplomacySnapshotMisrepresentationRow",
    "DiplomacySnapshotNegotiationRow",
    "DiplomacySnapshotPartyRow",
    "DiplomacySnapshotRelationRow",
    "DiplomacySnapshotSummaryRow",
    "DiplomacySnapshotTerminationRow",
    "empty_diplomacy_snapshot",
]

_LOG: Final[logging.Logger] = logging.getLogger("simulation.diplomacy_models")

DIPLOMACY_SNAPSHOT_SCHEMA: Final[str] = "diplomacy-snapshot-v1"
DIPLOMACY_SNAPSHOT_POLICY: Final[str] = "diplomacy-snapshot-policy.v1"
SUPPORTED_DIPLOMACY_SNAPSHOT_SCHEMAS: Final[tuple[str, ...]] = (
    DIPLOMACY_SNAPSHOT_SCHEMA,
)

MAX_SNAPSHOT_RELATIONS: Final[int] = 4096
MAX_SNAPSHOT_PARTIES: Final[int] = 8192
MAX_SNAPSHOT_CONTACTS: Final[int] = 16384
MAX_SNAPSHOT_ENVOYS: Final[int] = 8192
MAX_SNAPSHOT_NEGOTIATIONS: Final[int] = 8192
MAX_SNAPSHOT_INSTRUMENTS: Final[int] = 16384
MAX_SNAPSHOT_DECLARATIONS: Final[int] = 32768
MAX_SNAPSHOT_LINEAGE: Final[int] = 8192
MAX_SNAPSHOT_CANDIDATES: Final[int] = 2048
MAX_SNAPSHOT_BYTES: Final[int] = 4 * 1024 * 1024
MAX_DETAIL_ROWS: Final[int] = 500

PUBLICATION_ID_PREFIX: Final[str] = "dip-pub-"
DIPLOMACY_CURSOR_PURPOSES: Final[tuple[str, ...]] = (
    "summary",
    "relations",
    "relation",
    "instruments",
    "instrument",
    "lineage",
)
_RELATION_PREFIX: Final[str] = "dpl-"
_PARTY_PREFIX: Final[str] = "dpp-"
_CONTACT_PREFIX: Final[str] = "dpc-"
_ENVOY_PREFIX: Final[str] = "dpe-"
_NEGOTIATION_PREFIX: Final[str] = "dpn-"
_INSTRUMENT_PREFIX: Final[str] = "dpi-"
_DECLARATION_PREFIX: Final[str] = "dpd-"
_MISREPRESENTATION_PREFIX: Final[str] = "dps-"
_TERMINATION_PREFIX: Final[str] = "dpt-"
_CONFLICT_PREFIX: Final[str] = "dpx-"
_CANDIDATE_PREFIX: Final[str] = "dip-"
_EDGE_PREFIX: Final[str] = "dip-edge-"
_HEX16: Final[str] = "0123456789abcdef"
_FORBIDDEN_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "score",
        "relation_score",
        "trust",
        "rank",
        "valence",
        "index",
        "composite",
        "overall_relation",
        "bilateral_score",
        "mean_score",
        "truth",
        "verified",
        "legitimate",
    }
)
DIPLOMACY_ARTIFACT_ERROR_CODES: Final[frozenset[str]] = frozenset(
    {
        "diplomacy_snapshot_invalid",
        "diplomacy_snapshot_schema_unknown",
        "diplomacy_snapshot_digest_mismatch",
        "diplomacy_snapshot_size_limit",
        "diplomacy_snapshot_foreign_reference",
        "diplomacy_snapshot_forbidden_field",
        "diplomacy_snapshot_unsupported",
        "diplomacy_not_found",
        "diplomacy_publication_exists",
        "diplomacy_quota_exceeded",
        "diplomacy_publication_digest_mismatch",
    }
)


class DiplomacyArtifactError(ValueError):
    """Stable-code snapshot violation with no payload detail."""

    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        if code not in DIPLOMACY_ARTIFACT_ERROR_CODES:
            raise ValueError("diplomacy_invalid_error_code")
        self.code = code
        super().__init__(code)


def _fail(code: str) -> NoReturn:
    raise DiplomacyArtifactError(code)


def _reject_forbidden(model: type[Any]) -> None:
    if {field.name for field in fields(model)} & _FORBIDDEN_FIELDS:
        _fail("diplomacy_snapshot_forbidden_field")


def _text(value: object, *, max_len: int = 128) -> str:
    if type(value) is not str or not value or len(value) > max_len:
        _fail("diplomacy_snapshot_invalid")
    return value


def _optional_text(value: object, *, max_len: int = 128) -> str | None:
    if value is None:
        return None
    return _text(value, max_len=max_len)


def _tick(value: object) -> int:
    if type(value) is not int or isinstance(value, bool) or value < 0:
        _fail("diplomacy_snapshot_invalid")
    return value


def _agent_token(value: object) -> str:
    text = _text(value, max_len=16)
    if len(text) != 16 or any(character not in _HEX16 for character in text):
        _fail("diplomacy_snapshot_invalid")
    return text


def _party_or_anchor(value: object) -> str | None:
    if value is None:
        return None
    text = _text(value, max_len=128)
    if len(text) == 16 and all(character in _HEX16 for character in text):
        return text
    if text.startswith("orgc-") or text.startswith("region"):
        return text
    _fail("diplomacy_snapshot_invalid")


def _subject_token(value: object) -> str | None:
    if value is None:
        return None
    text = _text(value, max_len=16)
    if len(text) != 16 or any(character not in _HEX16 for character in text):
        _fail("diplomacy_snapshot_invalid")
    return text


def _record_id(value: object, prefix: str) -> str:
    text = _text(value, max_len=32)
    if not text.startswith(prefix) or len(text) != len(prefix) + 16:
        _fail("diplomacy_snapshot_invalid")
    if any(character not in _HEX16 for character in text[len(prefix) :]):
        _fail("diplomacy_snapshot_invalid")
    return text


def _candidate_id(value: object) -> str:
    text = _text(value, max_len=32)
    if text.startswith(_EDGE_PREFIX) or not text.startswith(_CANDIDATE_PREFIX):
        _fail("diplomacy_snapshot_invalid")
    if len(text) != len(_CANDIDATE_PREFIX) + 16:
        _fail("diplomacy_snapshot_invalid")
    return text


def _token_tuple(value: object, *, max_items: int = 32) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (tuple, list)):
        _fail("diplomacy_snapshot_invalid")
    rows = tuple(value)
    if len(rows) > max_items:
        _fail("diplomacy_snapshot_invalid")
    return tuple(sorted({_party_or_anchor(item) or "" for item in rows}))


def _ordered(value: object) -> tuple[object, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (tuple, list)):
        _fail("diplomacy_snapshot_invalid")
    return tuple(value)


@dataclass(frozen=True, slots=True)
class DiplomacySnapshotSummaryRow:
    relation_count: int = 0
    party_count: int = 0
    contact_count: int = 0
    envoy_count: int = 0
    negotiation_count: int = 0
    instrument_count: int = 0
    declaration_count: int = 0
    misrepresentation_count: int = 0
    termination_count: int = 0
    conflict_count: int = 0
    candidate_count: int = 0
    lineage_edge_count: int = 0
    last_activity_tick: int = 0
    coverage: str = "complete"

    def __post_init__(self) -> None:
        _reject_forbidden(type(self))
        for field in fields(type(self)):
            if field.name == "coverage":
                continue
            _tick(getattr(self, field.name))
        if self.coverage not in {"complete", "partial"}:
            _fail("diplomacy_snapshot_invalid")


@dataclass(frozen=True, slots=True)
class DiplomacySnapshotRelationRow:
    relation_id: str
    owner_token: str
    party_tokens: tuple[str, ...]
    opened_tick: int
    last_tick: int
    provenance: str

    def __post_init__(self) -> None:
        _reject_forbidden(type(self))
        _record_id(self.relation_id, _RELATION_PREFIX)
        _agent_token(self.owner_token)
        tokens = _token_tuple(self.party_tokens)
        if len(tokens) < 2:
            _fail("diplomacy_snapshot_invalid")
        object.__setattr__(self, "party_tokens", tokens)
        _tick(self.opened_tick)
        _tick(self.last_tick)
        _text(self.provenance)


@dataclass(frozen=True, slots=True)
class DiplomacySnapshotPartyRow:
    party_id: str
    owner_token: str
    party_token: str | None
    party_kind: str
    resolution: str
    first_seen_tick: int
    provenance: str

    def __post_init__(self) -> None:
        _reject_forbidden(type(self))
        _record_id(self.party_id, _PARTY_PREFIX)
        _agent_token(self.owner_token)
        _party_or_anchor(self.party_token)
        _text(self.party_kind)
        _text(self.resolution)
        _tick(self.first_seen_tick)
        _text(self.provenance)


@dataclass(frozen=True, slots=True)
class DiplomacySnapshotContactRow:
    contact_id: str
    relation_id: str
    owner_token: str
    tick: int
    contact_kind: str
    location_anchor: str | None
    participant_count: int
    provenance: str

    def __post_init__(self) -> None:
        _reject_forbidden(type(self))
        _record_id(self.contact_id, _CONTACT_PREFIX)
        _record_id(self.relation_id, _RELATION_PREFIX)
        _agent_token(self.owner_token)
        _tick(self.tick)
        _text(self.contact_kind)
        _optional_text(self.location_anchor)
        if self.participant_count < 1:
            _fail("diplomacy_snapshot_invalid")
        _text(self.provenance)


@dataclass(frozen=True, slots=True)
class DiplomacySnapshotEnvoyRow:
    envoy_id: str
    relation_id: str
    owner_token: str
    party_token: str | None
    envoy_token: str
    mandate_token: str | None
    status: str
    accredited_tick: int
    end_tick: int | None
    provenance: str

    def __post_init__(self) -> None:
        _reject_forbidden(type(self))
        _record_id(self.envoy_id, _ENVOY_PREFIX)
        _record_id(self.relation_id, _RELATION_PREFIX)
        _agent_token(self.owner_token)
        _party_or_anchor(self.party_token)
        _agent_token(self.envoy_token)
        _optional_text(self.mandate_token)
        _text(self.status)
        _tick(self.accredited_tick)
        if self.end_tick is not None:
            _tick(self.end_tick)
        _text(self.provenance)


@dataclass(frozen=True, slots=True)
class DiplomacySnapshotNegotiationRow:
    negotiation_id: str
    relation_id: str
    owner_token: str
    subject_token: str | None
    status: str
    opened_tick: int
    last_tick: int
    term_kind: str
    provenance: str

    def __post_init__(self) -> None:
        _reject_forbidden(type(self))
        _record_id(self.negotiation_id, _NEGOTIATION_PREFIX)
        _record_id(self.relation_id, _RELATION_PREFIX)
        _agent_token(self.owner_token)
        _subject_token(self.subject_token)
        _text(self.status)
        _tick(self.opened_tick)
        _tick(self.last_tick)
        _text(self.term_kind)
        _text(self.provenance)


@dataclass(frozen=True, slots=True)
class DiplomacySnapshotInstrumentRow:
    instrument_id: str
    relation_id: str
    owner_token: str
    party_tokens: tuple[str, ...]
    instrument_kind: str
    term_kind: str
    subject_token: str | None
    opener_envoy_token: str | None
    opened_tick: int
    end_tick: int | None
    anchor_refs: tuple[str, ...]
    provenance: str

    def __post_init__(self) -> None:
        _reject_forbidden(type(self))
        _record_id(self.instrument_id, _INSTRUMENT_PREFIX)
        _record_id(self.relation_id, _RELATION_PREFIX)
        _agent_token(self.owner_token)
        tokens = _token_tuple(self.party_tokens)
        if len(tokens) < 2:
            _fail("diplomacy_snapshot_invalid")
        object.__setattr__(self, "party_tokens", tokens)
        _text(self.instrument_kind)
        _text(self.term_kind)
        _subject_token(self.subject_token)
        if self.opener_envoy_token is not None:
            _agent_token(self.opener_envoy_token)
        _tick(self.opened_tick)
        if self.end_tick is not None:
            _tick(self.end_tick)
        if isinstance(self.anchor_refs, (str, bytes)) or not isinstance(
            self.anchor_refs, (tuple, list)
        ):
            _fail("diplomacy_snapshot_invalid")
        object.__setattr__(
            self,
            "anchor_refs",
            tuple(sorted({_text(item) for item in self.anchor_refs})),
        )
        _text(self.provenance)


@dataclass(frozen=True, slots=True)
class DiplomacySnapshotDeclarationRow:
    declaration_id: str
    instrument_id: str
    owner_token: str
    party_token: str | None
    envoy_token: str | None
    act: str
    declared_tick: int
    provenance: str

    def __post_init__(self) -> None:
        _reject_forbidden(type(self))
        _record_id(self.declaration_id, _DECLARATION_PREFIX)
        _record_id(self.instrument_id, _INSTRUMENT_PREFIX)
        _agent_token(self.owner_token)
        _party_or_anchor(self.party_token)
        if self.envoy_token is not None:
            _agent_token(self.envoy_token)
        _text(self.act)
        _tick(self.declared_tick)
        _text(self.provenance)


@dataclass(frozen=True, slots=True)
class DiplomacySnapshotMisrepresentationRow:
    misrepresentation_id: str
    instrument_id: str
    owner_token: str
    kind: str
    observed_tick: int
    envoy_token: str
    party_token: str | None
    provenance: str

    def __post_init__(self) -> None:
        _reject_forbidden(type(self))
        _record_id(self.misrepresentation_id, _MISREPRESENTATION_PREFIX)
        _record_id(self.instrument_id, _INSTRUMENT_PREFIX)
        _agent_token(self.owner_token)
        _text(self.kind)
        _tick(self.observed_tick)
        _agent_token(self.envoy_token)
        _party_or_anchor(self.party_token)
        _text(self.provenance)


@dataclass(frozen=True, slots=True)
class DiplomacySnapshotTerminationRow:
    termination_id: str
    owner_token: str
    target_kind: str
    target_ref: str
    kind: str
    tick: int
    provenance: str

    def __post_init__(self) -> None:
        _reject_forbidden(type(self))
        _record_id(self.termination_id, _TERMINATION_PREFIX)
        _agent_token(self.owner_token)
        _text(self.target_kind)
        _text(self.target_ref)
        _text(self.kind)
        _tick(self.tick)
        _text(self.provenance)


@dataclass(frozen=True, slots=True)
class DiplomacySnapshotConflictRow:
    conflict_id: str
    relation_id: str
    owner_token: str
    kind: str
    observed_tick: int
    instrument_refs: tuple[str, ...]
    party_tokens: tuple[str, ...]
    provenance: str

    def __post_init__(self) -> None:
        _reject_forbidden(type(self))
        _record_id(self.conflict_id, _CONFLICT_PREFIX)
        _record_id(self.relation_id, _RELATION_PREFIX)
        _agent_token(self.owner_token)
        _text(self.kind)
        _tick(self.observed_tick)
        if isinstance(self.instrument_refs, (str, bytes)) or not isinstance(
            self.instrument_refs, (tuple, list)
        ):
            _fail("diplomacy_snapshot_invalid")
        object.__setattr__(
            self,
            "instrument_refs",
            tuple(sorted({_text(item) for item in self.instrument_refs})),
        )
        object.__setattr__(self, "party_tokens", _token_tuple(self.party_tokens))
        _text(self.provenance)


@dataclass(frozen=True, slots=True)
class DiplomacySnapshotLineageRow:
    edge_id: str
    from_candidate_id: str
    to_candidate_id: str
    kind: str
    tick: int

    def __post_init__(self) -> None:
        _reject_forbidden(type(self))
        _text(self.edge_id)
        if not self.edge_id.startswith(_EDGE_PREFIX):
            _fail("diplomacy_snapshot_invalid")
        _candidate_id(self.from_candidate_id)
        _candidate_id(self.to_candidate_id)
        _text(self.kind)
        _tick(self.tick)


@dataclass(frozen=True, slots=True)
class DiplomacySnapshotMetricProvenanceRow:
    family_id: str
    family_version: int
    document_digest: str

    def __post_init__(self) -> None:
        _reject_forbidden(type(self))
        _text(self.family_id)
        _tick(self.family_version)
        if (
            type(self.document_digest) is not str
            or len(self.document_digest) != 64
            or any(character not in _HEX16 for character in self.document_digest)
        ):
            _fail("diplomacy_snapshot_invalid")


@dataclass(frozen=True, slots=True)
class DiplomacySnapshot:
    """One bounded canonical diplomacy snapshot."""

    run_id: str
    created_revision: str
    window_end: int
    publication_id: str = ""
    coverage: str = "complete"
    summary: DiplomacySnapshotSummaryRow = DiplomacySnapshotSummaryRow()
    relations: tuple[DiplomacySnapshotRelationRow, ...] = ()
    parties: tuple[DiplomacySnapshotPartyRow, ...] = ()
    contacts: tuple[DiplomacySnapshotContactRow, ...] = ()
    envoys: tuple[DiplomacySnapshotEnvoyRow, ...] = ()
    negotiations: tuple[DiplomacySnapshotNegotiationRow, ...] = ()
    instruments: tuple[DiplomacySnapshotInstrumentRow, ...] = ()
    declarations: tuple[DiplomacySnapshotDeclarationRow, ...] = ()
    misrepresentations: tuple[DiplomacySnapshotMisrepresentationRow, ...] = ()
    terminations: tuple[DiplomacySnapshotTerminationRow, ...] = ()
    conflicts: tuple[DiplomacySnapshotConflictRow, ...] = ()
    lineage: tuple[DiplomacySnapshotLineageRow, ...] = ()
    metric_provenance: tuple[DiplomacySnapshotMetricProvenanceRow, ...] = ()
    metric_families: tuple[str, ...] = ()
    policy_version: str = DIPLOMACY_SNAPSHOT_POLICY
    schema_version: str = DIPLOMACY_SNAPSHOT_SCHEMA
    digest: str = ""

    def __post_init__(self) -> None:
        _reject_forbidden(type(self))
        if self.schema_version not in SUPPORTED_DIPLOMACY_SNAPSHOT_SCHEMAS:
            _fail("diplomacy_snapshot_schema_unknown")
        if self.policy_version != DIPLOMACY_SNAPSHOT_POLICY:
            _fail("diplomacy_snapshot_invalid")
        _text(self.run_id)
        _text(self.created_revision)
        _tick(self.window_end)
        if self.coverage not in {"complete", "partial"}:
            _fail("diplomacy_snapshot_invalid")
        tables: tuple[tuple[str, type, int, str, str], ...] = (
            (
                "relations",
                DiplomacySnapshotRelationRow,
                MAX_SNAPSHOT_RELATIONS,
                "opened_tick",
                "relation_id",
            ),
            (
                "parties",
                DiplomacySnapshotPartyRow,
                MAX_SNAPSHOT_PARTIES,
                "first_seen_tick",
                "party_id",
            ),
            (
                "contacts",
                DiplomacySnapshotContactRow,
                MAX_SNAPSHOT_CONTACTS,
                "tick",
                "contact_id",
            ),
            (
                "envoys",
                DiplomacySnapshotEnvoyRow,
                MAX_SNAPSHOT_ENVOYS,
                "accredited_tick",
                "envoy_id",
            ),
            (
                "negotiations",
                DiplomacySnapshotNegotiationRow,
                MAX_SNAPSHOT_NEGOTIATIONS,
                "opened_tick",
                "negotiation_id",
            ),
            (
                "instruments",
                DiplomacySnapshotInstrumentRow,
                MAX_SNAPSHOT_INSTRUMENTS,
                "opened_tick",
                "instrument_id",
            ),
            (
                "declarations",
                DiplomacySnapshotDeclarationRow,
                MAX_SNAPSHOT_DECLARATIONS,
                "declared_tick",
                "declaration_id",
            ),
            (
                "misrepresentations",
                DiplomacySnapshotMisrepresentationRow,
                MAX_SNAPSHOT_DECLARATIONS,
                "observed_tick",
                "misrepresentation_id",
            ),
            (
                "terminations",
                DiplomacySnapshotTerminationRow,
                MAX_SNAPSHOT_DECLARATIONS,
                "tick",
                "termination_id",
            ),
            (
                "conflicts",
                DiplomacySnapshotConflictRow,
                MAX_SNAPSHOT_DECLARATIONS,
                "observed_tick",
                "conflict_id",
            ),
            (
                "lineage",
                DiplomacySnapshotLineageRow,
                MAX_SNAPSHOT_LINEAGE,
                "tick",
                "edge_id",
            ),
        )
        resolved: dict[str, tuple[Any, ...]] = {}
        for name, row_type, cap, tick_name, id_name in tables:
            rows = _ordered(getattr(self, name))
            if len(rows) > cap:
                _fail("diplomacy_snapshot_size_limit")
            for row in rows:
                if type(row) is not row_type:
                    _fail("diplomacy_snapshot_invalid")
            keys = [(getattr(row, tick_name), getattr(row, id_name)) for row in rows]
            if keys != sorted(keys):
                _fail("diplomacy_snapshot_invalid")
            ids = [getattr(row, id_name) for row in rows]
            if len(set(ids)) != len(ids):
                _fail("diplomacy_snapshot_invalid")
            object.__setattr__(self, name, rows)
            resolved[name] = rows
        relation_ids = {row.relation_id for row in resolved["relations"]}
        instrument_ids = {row.instrument_id for row in resolved["instruments"]}
        envoy_ids = {row.envoy_id for row in resolved["envoys"]}
        for row in resolved["parties"]:
            if row.party_token is None:
                _fail("diplomacy_snapshot_invalid")
        for row in resolved["relations"]:
            if any(
                token not in {party.party_token for party in resolved["parties"]}
                for token in row.party_tokens
            ):
                _fail("diplomacy_snapshot_foreign_reference")
        for table in ("contacts", "envoys", "negotiations", "instruments"):
            for row in resolved[table]:
                if row.relation_id not in relation_ids:
                    _fail("diplomacy_snapshot_foreign_reference")
        for instrument in resolved["instruments"]:
            relation = next(
                (
                    row
                    for row in resolved["relations"]
                    if row.relation_id == instrument.relation_id
                ),
                None,
            )
            if relation is None or instrument.party_tokens != relation.party_tokens:
                _fail("diplomacy_snapshot_invalid")
        for row in resolved["declarations"]:
            if row.instrument_id not in instrument_ids:
                _fail("diplomacy_snapshot_foreign_reference")
        for row in resolved["misrepresentations"]:
            if row.instrument_id not in instrument_ids:
                _fail("diplomacy_snapshot_foreign_reference")
        for row in resolved["terminations"]:
            if row.target_kind == "instrument" and row.target_ref not in instrument_ids:
                _fail("diplomacy_snapshot_foreign_reference")
            if row.target_kind == "envoy" and row.target_ref not in envoy_ids:
                _fail("diplomacy_snapshot_foreign_reference")
            if row.target_kind == "relation" and row.target_ref not in relation_ids:
                _fail("diplomacy_snapshot_foreign_reference")
        for row in resolved["conflicts"]:
            if row.relation_id not in relation_ids:
                _fail("diplomacy_snapshot_foreign_reference")
            if any(ref not in instrument_ids for ref in row.instrument_refs):
                _fail("diplomacy_snapshot_foreign_reference")
        provenance = _ordered(self.metric_provenance)
        if len(provenance) > MAX_SNAPSHOT_CANDIDATES:
            _fail("diplomacy_snapshot_size_limit")
        for row in provenance:
            if type(row) is not DiplomacySnapshotMetricProvenanceRow:
                _fail("diplomacy_snapshot_invalid")
        object.__setattr__(self, "metric_provenance", provenance)
        if isinstance(self.metric_families, (str, bytes)) or not isinstance(
            self.metric_families, (tuple, list)
        ):
            _fail("diplomacy_snapshot_invalid")
        object.__setattr__(
            self,
            "metric_families",
            tuple(sorted({_text(item, max_len=64) for item in self.metric_families})),
        )
        if self.digest:
            _text(self.digest, max_len=64)
        if self.publication_id and not self.publication_id.startswith(
            PUBLICATION_ID_PREFIX
        ):
            _fail("diplomacy_snapshot_invalid")


def empty_diplomacy_snapshot(
    run_id: object, *, revision: object, window_end: int
) -> DiplomacySnapshot:
    return DiplomacySnapshot(
        run_id=_text(run_id),
        created_revision=_text(revision),
        window_end=_tick(window_end),
    )
