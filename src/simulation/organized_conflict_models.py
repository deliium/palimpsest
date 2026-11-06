# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,index,call-overload,attr-defined,no-untyped-def,unused-ignore,type-arg,comparison-overlap"
"""Bounded canonical ``organized-conflict-snapshot-v1`` document."""

from __future__ import annotations

import re
from dataclasses import dataclass, fields
from typing import Final

__all__ = [
    "MAX_DETAIL_ROWS",
    "MAX_SNAPSHOT_BYTES",
    "MAX_SNAPSHOT_CANDIDATES",
    "MAX_SNAPSHOT_CONTRADICTIONS",
    "MAX_SNAPSHOT_EPISODES",
    "MAX_SNAPSHOT_INTERPRETATIONS",
    "MAX_SNAPSHOT_LINEAGE",
    "MAX_SNAPSHOT_OUTCOMES",
    "MAX_SNAPSHOT_PARTICIPANTS",
    "MAX_SNAPSHOT_PLANS",
    "ORGANIZED_CONFLICT_SNAPSHOT_POLICY",
    "ORGANIZED_CONFLICT_SNAPSHOT_SCHEMA",
    "OrganizedConflictContradictionRow",
    "OrganizedConflictEpisodeRow",
    "OrganizedConflictInterpretationRow",
    "OrganizedConflictLineageRow",
    "OrganizedConflictMetricProvenanceRow",
    "OrganizedConflictOutcomeRow",
    "OrganizedConflictParticipantRow",
    "OrganizedConflictPlanRow",
    "OrganizedConflictSnapshot",
    "OrganizedConflictSummaryRow",
    "OrganizedConflictTerminationRow",
    "empty_organized_conflict_snapshot",
]

ORGANIZED_CONFLICT_SNAPSHOT_SCHEMA: Final[str] = "organized-conflict-snapshot-v1"
ORGANIZED_CONFLICT_SNAPSHOT_POLICY: Final[str] = "organized-conflict-snapshot.v1"
MAX_SNAPSHOT_EPISODES: Final[int] = 4096
MAX_SNAPSHOT_PARTICIPANTS: Final[int] = 16384
MAX_SNAPSHOT_PLANS: Final[int] = 8192
MAX_SNAPSHOT_INTERPRETATIONS: Final[int] = 16384
MAX_SNAPSHOT_OUTCOMES: Final[int] = 32768
MAX_SNAPSHOT_CONTRADICTIONS: Final[int] = 8192
MAX_SNAPSHOT_LINEAGE: Final[int] = 16384
MAX_SNAPSHOT_CANDIDATES: Final[int] = 2048
MAX_SNAPSHOT_BYTES: Final[int] = 4 * 1024 * 1024
MAX_DETAIL_ROWS: Final[int] = 500

_HEX_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{16}$")
_ID_PREFIXES: Final[tuple[str, ...]] = (
    "oc-",
    "ocp-",
    "oci-",
    "ocx-",
    "occ-",
    "oct-",
    "oc-edge-",
    "oc-pub-",
)
_FORBIDDEN_NAMES: Final[frozenset[str]] = frozenset(
    {
        "war_score",
        "violence_score",
        "escalation_index",
        "legitimacy",
        "winner",
        "loser",
        "truth",
        "verified",
        "enforced",
        "enforcement",
        "composite",
        "overall_conflict",
        "raw_agent_id",
        "target_text",
    }
)


def _token(name: str, value: object) -> str:
    if type(value) is not str or _HEX_RE.match(value) is None:
        raise ValueError(f"{name} must be an opaque 16-hex token")
    return value


def _identifier(name: str, value: object) -> str:
    if type(value) is not str:
        raise ValueError(f"{name} must be an opaque identifier")
    if not any(value.startswith(prefix) for prefix in _ID_PREFIXES):
        if not (value.startswith("org-") or value.startswith("msoc-")):
            raise ValueError(f"{name} must be an opaque identifier")
    return value


def _tokens(name: str, values: object) -> tuple[str, ...]:
    if isinstance(values, (str, bytes, set, frozenset)):
        raise TypeError(f"{name} must be an ordered tuple")
    return tuple(_token(name, item) for item in values)  # type: ignore[arg-type]


def _nonneg(name: str, value: object) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a non-negative int")
    return value


@dataclass(frozen=True, slots=True)
class OrganizedConflictSummaryRow:
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


@dataclass(frozen=True, slots=True)
class OrganizedConflictEpisodeRow:
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
    macro_society_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _identifier("episode_id", self.episode_id)
        if self.classification not in {
            "individual_violence",
            "coordinated_conflict",
            "persistent_inter_group_conflict",
        }:
            raise ValueError("episode classification is not closed")
        _nonneg("start_tick", self.start_tick)
        _nonneg("end_tick", self.end_tick)
        object.__setattr__(
            self,
            "participant_tokens",
            _tokens("participant_tokens", self.participant_tokens),
        )
        object.__setattr__(
            self, "opponent_tokens", _tokens("opponent_tokens", self.opponent_tokens)
        )
        object.__setattr__(self, "org_ids", tuple(self.org_ids))
        object.__setattr__(
            self, "macro_society_ids", tuple(self.macro_society_ids)
        )


@dataclass(frozen=True, slots=True)
class OrganizedConflictParticipantRow:
    episode_id: str
    participant_token: str
    role: str
    tick: int

    def __post_init__(self) -> None:
        _identifier("episode_id", self.episode_id)
        _token("participant_token", self.participant_token)
        _nonneg("tick", self.tick)


@dataclass(frozen=True, slots=True)
class OrganizedConflictPlanRow:
    plan_id: str
    owner_token: str
    operation: str
    target_kind: str
    status: str
    participant_count: int
    tick: int

    def __post_init__(self) -> None:
        _identifier("plan_id", self.plan_id)
        _token("owner_token", self.owner_token)
        _nonneg("participant_count", self.participant_count)
        _nonneg("tick", self.tick)


@dataclass(frozen=True, slots=True)
class OrganizedConflictInterpretationRow:
    interpretation_id: str
    owner_token: str
    episode_id: str
    kind: str
    alignment: str
    tick: int

    def __post_init__(self) -> None:
        _identifier("interpretation_id", self.interpretation_id)
        _token("owner_token", self.owner_token)
        if self.episode_id:
            _identifier("episode_id", self.episode_id)
        _nonneg("tick", self.tick)


@dataclass(frozen=True, slots=True)
class OrganizedConflictOutcomeRow:
    outcome_id: str
    plan_id: str
    kind: str
    target_token: str
    tick: int

    def __post_init__(self) -> None:
        _identifier("outcome_id", self.outcome_id)
        _identifier("plan_id", self.plan_id)
        _token("target_token", self.target_token)
        _nonneg("tick", self.tick)


@dataclass(frozen=True, slots=True)
class OrganizedConflictContradictionRow:
    contradiction_id: str
    kind: str
    member_count: int
    tick: int

    def __post_init__(self) -> None:
        _identifier("contradiction_id", self.contradiction_id)
        _nonneg("member_count", self.member_count)
        _nonneg("tick", self.tick)


@dataclass(frozen=True, slots=True)
class OrganizedConflictTerminationRow:
    termination_id: str
    plan_id: str
    kind: str
    tick: int

    def __post_init__(self) -> None:
        _identifier("termination_id", self.termination_id)
        _identifier("plan_id", self.plan_id)
        _nonneg("tick", self.tick)


@dataclass(frozen=True, slots=True)
class OrganizedConflictLineageRow:
    edge_id: str
    from_id: str
    to_id: str
    kind: str
    tick: int

    def __post_init__(self) -> None:
        _identifier("edge_id", self.edge_id)
        _identifier("from_id", self.from_id)
        _identifier("to_id", self.to_id)
        if self.kind not in {"continued", "transformed", "split", "merge", "ended"}:
            raise ValueError("lineage kind is not closed")
        _nonneg("tick", self.tick)


@dataclass(frozen=True, slots=True)
class OrganizedConflictMetricProvenanceRow:
    family: str
    algorithm_version: str
    policy_version: str


@dataclass(frozen=True, slots=True)
class OrganizedConflictSnapshot:
    schema_version: str
    policy_version: str
    run_id: str
    publication_id: str
    digest: str
    summary: OrganizedConflictSummaryRow
    episodes: tuple[OrganizedConflictEpisodeRow, ...] = ()
    participants: tuple[OrganizedConflictParticipantRow, ...] = ()
    plans: tuple[OrganizedConflictPlanRow, ...] = ()
    interpretations: tuple[OrganizedConflictInterpretationRow, ...] = ()
    outcomes: tuple[OrganizedConflictOutcomeRow, ...] = ()
    contradictions: tuple[OrganizedConflictContradictionRow, ...] = ()
    terminations: tuple[OrganizedConflictTerminationRow, ...] = ()
    lineage: tuple[OrganizedConflictLineageRow, ...] = ()
    metric_provenance: tuple[OrganizedConflictMetricProvenanceRow, ...] = ()
    coverage: str = "not_applicable"
    notices: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field in fields(type(self)):
            if field.name in _FORBIDDEN_NAMES:
                raise ValueError("organized_conflict_snapshot_forbidden_field")
        if self.schema_version != ORGANIZED_CONFLICT_SNAPSHOT_SCHEMA:
            raise ValueError("organized_conflict_snapshot_schema")
        if self.policy_version != ORGANIZED_CONFLICT_SNAPSHOT_POLICY:
            raise ValueError("organized_conflict_snapshot_schema")
        if type(self.run_id) is not str or not self.run_id:
            raise ValueError("organized_conflict_snapshot_run_id")
        _identifier("publication_id", self.publication_id)
        if len(self.digest) != 64 or any(
            char not in "0123456789abcdef" for char in self.digest
        ):
            raise ValueError("organized_conflict_snapshot_digest")
        if type(self.summary) is not OrganizedConflictSummaryRow:
            raise TypeError("summary must be OrganizedConflictSummaryRow")
        caps = (
            ("episodes", self.episodes, MAX_SNAPSHOT_EPISODES, "episode_id"),
            (
                "participants",
                self.participants,
                MAX_SNAPSHOT_PARTICIPANTS,
                "participant_token",
            ),
            ("plans", self.plans, MAX_SNAPSHOT_PLANS, "plan_id"),
            (
                "interpretations",
                self.interpretations,
                MAX_SNAPSHOT_INTERPRETATIONS,
                "interpretation_id",
            ),
            ("outcomes", self.outcomes, MAX_SNAPSHOT_OUTCOMES, "outcome_id"),
            (
                "contradictions",
                self.contradictions,
                MAX_SNAPSHOT_CONTRADICTIONS,
                "contradiction_id",
            ),
            ("lineage", self.lineage, MAX_SNAPSHOT_LINEAGE, "edge_id"),
        )
        for name, rows, cap, key_name in caps:
            if not isinstance(rows, tuple):
                raise TypeError(f"organized_conflict_snapshot_{name}_order")
            if len(rows) > cap:
                raise ValueError(f"organized_conflict_snapshot_cap:{name}")
            if name == "participants":
                keys = [
                    (row.episode_id, row.participant_token) for row in rows
                ]
            else:
                keys = [getattr(row, key_name) for row in rows]
            if keys != sorted(keys):
                raise ValueError(f"organized_conflict_snapshot_{name}_order")
            if len(set(keys)) != len(keys):
                raise ValueError("organized_conflict_snapshot_duplicate_id")
        episode_ids = {row.episode_id for row in self.episodes}
        plan_ids = {row.plan_id for row in self.plans}
        for row in self.participants:
            if row.episode_id not in episode_ids:
                raise ValueError("organized_conflict_snapshot_foreign_reference")
        for row in self.interpretations:
            if row.episode_id and row.episode_id not in episode_ids:
                raise ValueError("organized_conflict_snapshot_foreign_reference")
        for row in (*self.outcomes, *self.terminations):
            if row.plan_id not in plan_ids:
                raise ValueError("organized_conflict_snapshot_foreign_reference")
        ids = episode_ids | plan_ids
        for row in self.lineage:
            if row.from_id not in ids or row.to_id not in ids:
                raise ValueError("organized_conflict_snapshot_foreign_reference")
        notices = tuple(self.notices)
        if any(type(notice) is not str or not notice for notice in notices):
            raise ValueError("organized_conflict_snapshot_notice")
        object.__setattr__(self, "notices", notices)


def empty_organized_conflict_snapshot(
    run_id: str, *, publication_id: str, digest: str
) -> OrganizedConflictSnapshot:
    return OrganizedConflictSnapshot(
        schema_version=ORGANIZED_CONFLICT_SNAPSHOT_SCHEMA,
        policy_version=ORGANIZED_CONFLICT_SNAPSHOT_POLICY,
        run_id=run_id,
        publication_id=publication_id,
        digest=digest,
        summary=OrganizedConflictSummaryRow(),
    )
