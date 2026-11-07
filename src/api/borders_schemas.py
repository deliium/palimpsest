"""Strict read-only schemas for border claims."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

MAX_PAGE_LIMIT = 500


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class BordersSummaryOut(_Strict):
    run_id: str
    publication_id: str
    digest: str
    schema_version: str
    candidate_count: int = 0
    claim_count: int = 0
    agreement_count: int = 0
    dispute_count: int = 0
    physical_row_count: int = 0
    pattern_count: int = 0
    coverage: str = "not_applicable"


class BordersClaimOut(_Strict):
    claim_token: str
    owner_token: str
    domain_token: str
    location_tokens: tuple[str, ...] = ()
    boundary_edge_tokens: tuple[tuple[str, str], ...] = ()
    status: str
    strength: float
    anchor_token: str = ""


class BordersAgreementOut(_Strict):
    agreement_token: str
    domain_token: str
    counterparty_token: str
    provision_tokens: tuple[str, ...] = ()
    status: str
    recognition: str
    effective_tick: int | None = None
    expiry_tick: int | None = None


class BordersControlRowOut(_Strict):
    layer: str
    location_token: str | None = None
    window_start: int | None = None
    window_end: int | None = None
    actor_count: int = 0
    action_count: int = 0
    hostile_count: int = 0
    assistance_count: int = 0
    presence_ticks: int = 0
    classification: str | None = None
    pattern_token: str | None = None
    domain_token: str | None = None
    location_tokens: tuple[str, ...] = ()
    pattern: str | None = None
    physical_actions: int = 0
    claim_count: int = 0
    agreement_count: int = 0
    dispute_count: int = 0


class BordersClaimPageOut(_Strict):
    items: tuple[BordersClaimOut, ...] = ()
    next_cursor: str | None = None


class BordersAgreementPageOut(_Strict):
    items: tuple[BordersAgreementOut, ...] = ()
    next_cursor: str | None = None


class BordersControlPageOut(_Strict):
    items: tuple[BordersControlRowOut, ...] = ()
    next_cursor: str | None = None
