# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,index,call-overload,attr-defined,no-untyped-def,unused-ignore,type-arg,comparison-overlap"
"""Strict read-only schemas for organized conflict."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

MAX_PAGE_LIMIT = 500


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class OrganizedConflictSummaryResponse(_Strict):
    run_id: str
    publication_id: str
    digest: str
    episode_count: int = 0
    individual_episode_count: int = 0
    coordinated_episode_count: int = 0
    persistent_inter_group_episode_count: int = 0
    participant_count: int = 0
    plan_count: int = 0
    interpretation_count: int = 0
    outcome_count: int = 0
    contradiction_count: int = 0
    termination_count: int = 0
    sustained_episode_count: int = 0
    coverage: str = "not_applicable"


class OrganizedConflictEpisodeResponse(_Strict):
    episode_id: str
    classification: str
    start_tick: int
    end_tick: int
    participant_tokens: tuple[str, ...] = ()
    opponent_tokens: tuple[str, ...] = ()
    side_count: int = 0
    hostile_event_count: int = 0
    active_window_count: int = 0
    sustained: bool = False
    org_ids: tuple[str, ...] = ()
    msoc_ids: tuple[str, ...] = ()


class OrganizedConflictParticipantResponse(_Strict):
    episode_id: str
    participant_token: str
    role: str
    tick: int


class OrganizedConflictPlanResponse(_Strict):
    plan_id: str
    owner_token: str
    operation: str
    target_kind: str
    status: str
    participant_count: int
    tick: int


class OrganizedConflictInterpretationResponse(_Strict):
    interpretation_id: str
    owner_token: str
    episode_id: str
    kind: str
    alignment: str
    tick: int


class OrganizedConflictLineageResponse(_Strict):
    edge_id: str
    from_id: str
    to_id: str
    kind: str
    tick: int


class OrganizedConflictEpisodePageOut(_Strict):
    items: tuple[OrganizedConflictEpisodeResponse, ...]
    next_cursor: str | None = None
    truncated: bool = False


class OrganizedConflictEpisodeDetailOut(_Strict):
    episode: OrganizedConflictEpisodeResponse
    participants: tuple[OrganizedConflictParticipantResponse, ...]
    lineage: tuple[OrganizedConflictLineageResponse, ...] = ()
    truncated: bool = False


class OrganizedConflictPlanPageOut(_Strict):
    items: tuple[OrganizedConflictPlanResponse, ...]
    next_cursor: str | None = None
    truncated: bool = False


class OrganizedConflictPlanDetailOut(_Strict):
    plan: OrganizedConflictPlanResponse
    outcomes: tuple[dict[str, object], ...] = ()
    terminations: tuple[dict[str, object], ...] = ()
    truncated: bool = False


class OrganizedConflictInterpretationPageOut(_Strict):
    items: tuple[OrganizedConflictInterpretationResponse, ...]
    next_cursor: str | None = None
    truncated: bool = False
