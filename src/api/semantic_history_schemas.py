"""Strict response schemas for retained owner semantic history."""

from __future__ import annotations

from pydantic import Field

from api.schemas import StrictModel


class SemanticHistoryTermOut(StrictModel):
    term_source: str
    term_digest: str
    first_ordinal: int = Field(ge=0)
    current_sense_revision: int = Field(ge=0)


class SemanticHistoryRowOut(StrictModel):
    ordinal: int = Field(ge=0)
    tick: int = Field(ge=0)
    trigger: str
    term_source: str
    term_digest: str
    local_id: str
    referent_kind: str | None = None
    referent_digest: str | None = None
    associated_digests: tuple[str, ...] = ()
    confidence: float | None = None


class SemanticHistoryOut(StrictModel):
    schema_version: str = "observer-semantic-history-v1"
    run_id: str
    agent_id: str
    source: str
    requested_tick: int | None = None
    checkpoint_tick: int | None = None
    history_first_tick: int | None = None
    history_last_tick: int | None = None
    retained_only: bool = True
    prefix_complete: bool = False
    availability: str
    reason: str | None = None
    terms: tuple[SemanticHistoryTermOut, ...] = ()
    rows: tuple[SemanticHistoryRowOut, ...] = ()
    next_cursor: str | None = None
    count: int = Field(ge=0)
