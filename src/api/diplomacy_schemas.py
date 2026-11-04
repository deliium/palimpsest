"""Strict read-only response schemas for diplomacy routes."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

__all__ = [
    "MAX_PAGE_LIMIT",
    "DiplomacyConflictOut",
    "DiplomacyContactOut",
    "DiplomacyDeclarationOut",
    "DiplomacyEnvoyOut",
    "DiplomacyInstrumentDetailOut",
    "DiplomacyInstrumentOut",
    "DiplomacyInstrumentPageOut",
    "DiplomacyLineageOut",
    "DiplomacyLineagePageOut",
    "DiplomacyMisrepresentationOut",
    "DiplomacyNegotiationOut",
    "DiplomacyPartyOut",
    "DiplomacyRelationDetailOut",
    "DiplomacyRelationOut",
    "DiplomacyRelationPageOut",
    "DiplomacySummaryOut",
    "DiplomacyTerminationOut",
]

MAX_PAGE_LIMIT = 500


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DiplomacySummaryOut(_Strict):
    run_id: str
    publication_id: str
    snapshot_digest: str
    relation_count: int
    party_count: int
    contact_count: int
    envoy_count: int
    negotiation_count: int
    instrument_count: int
    declaration_count: int
    misrepresentation_count: int
    termination_count: int
    conflict_count: int
    candidate_count: int
    lineage_edge_count: int
    coverage: str


class DiplomacyRelationOut(_Strict):
    relation_id: str
    owner_token: str
    party_tokens: tuple[str, ...]
    opened_tick: int
    last_tick: int
    provenance: str


class DiplomacyPartyOut(_Strict):
    party_id: str
    owner_token: str
    party_token: str | None = None
    party_kind: str
    resolution: str
    first_seen_tick: int
    provenance: str


class DiplomacyContactOut(_Strict):
    contact_id: str
    relation_id: str
    owner_token: str
    tick: int
    contact_kind: str
    location_anchor: str | None = None
    participant_count: int
    provenance: str


class DiplomacyEnvoyOut(_Strict):
    envoy_id: str
    relation_id: str
    owner_token: str
    party_token: str | None = None
    envoy_token: str
    mandate_token: str | None = None
    status: str
    accredited_tick: int
    end_tick: int | None = None
    provenance: str


class DiplomacyNegotiationOut(_Strict):
    negotiation_id: str
    relation_id: str
    owner_token: str
    subject_token: str | None = None
    status: str
    opened_tick: int
    last_tick: int
    term_kind: str
    provenance: str


class DiplomacyInstrumentOut(_Strict):
    instrument_id: str
    relation_id: str
    owner_token: str
    party_tokens: tuple[str, ...]
    instrument_kind: str
    term_kind: str
    subject_token: str | None = None
    opener_envoy_token: str | None = None
    opened_tick: int
    end_tick: int | None = None
    anchor_refs: tuple[str, ...]
    provenance: str


class DiplomacyDeclarationOut(_Strict):
    declaration_id: str
    instrument_id: str
    owner_token: str
    party_token: str | None = None
    envoy_token: str | None = None
    act: str
    declared_tick: int
    provenance: str


class DiplomacyMisrepresentationOut(_Strict):
    misrepresentation_id: str
    instrument_id: str
    owner_token: str
    kind: str
    observed_tick: int
    envoy_token: str
    party_token: str | None = None
    provenance: str


class DiplomacyTerminationOut(_Strict):
    termination_id: str
    owner_token: str
    target_kind: str
    target_ref: str
    kind: str
    tick: int
    provenance: str


class DiplomacyConflictOut(_Strict):
    conflict_id: str
    relation_id: str
    owner_token: str
    kind: str
    observed_tick: int
    instrument_refs: tuple[str, ...]
    party_tokens: tuple[str, ...]
    provenance: str


class DiplomacyLineageOut(_Strict):
    edge_id: str
    from_candidate_id: str
    to_candidate_id: str
    kind: str
    tick: int


class DiplomacyRelationDetailOut(_Strict):
    relation: DiplomacyRelationOut
    parties: tuple[DiplomacyPartyOut, ...] = ()
    contacts: tuple[DiplomacyContactOut, ...] = ()
    envoys: tuple[DiplomacyEnvoyOut, ...] = ()
    negotiations: tuple[DiplomacyNegotiationOut, ...] = ()
    instruments: tuple[DiplomacyInstrumentOut, ...] = ()
    declarations: tuple[DiplomacyDeclarationOut, ...] = ()
    misrepresentations: tuple[DiplomacyMisrepresentationOut, ...] = ()
    terminations: tuple[DiplomacyTerminationOut, ...] = ()
    truncated: bool = False


class DiplomacyInstrumentDetailOut(_Strict):
    instrument: DiplomacyInstrumentOut
    declarations: tuple[DiplomacyDeclarationOut, ...] = ()
    misrepresentations: tuple[DiplomacyMisrepresentationOut, ...] = ()
    terminations: tuple[DiplomacyTerminationOut, ...] = ()
    truncated: bool = False


class DiplomacyRelationPageOut(_Strict):
    items: tuple[DiplomacyRelationOut, ...]
    next_cursor: str | None = None


class DiplomacyInstrumentPageOut(_Strict):
    items: tuple[DiplomacyInstrumentOut, ...]
    next_cursor: str | None = None


class DiplomacyLineagePageOut(_Strict):
    items: tuple[DiplomacyLineageOut, ...]
    next_cursor: str | None = None
