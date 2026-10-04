"""Metadata-safe subjective ledger projections for Research UI.

Documents never include proposition text, utterances, prompts, or narratives.
Self-model is an emergent projection (identity_cursor + goal refs), not a
checkpoint column or second belief store.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final, Literal

from simulation.run_control import AgentRuntimeCheckpoint
from world.identifiers import require_stable_id

_LOG: Final[logging.Logger] = logging.getLogger("simulation.subjective_projections")

Availability = Literal["available", "unavailable"]

__all__ = [
    "EmotionalStateProjection",
    "EmotionIntensitySummary",
    "GoalsProjection",
    "GoalSummary",
    "GroupFormationProjection",
    "LedgerItemSummary",
    "NarrativeProjection",
    "SelfModelProjection",
    "SocialConventionsProjection",
    "SocialNormsProjection",
    "TheoryOfMindProjection",
    "project_cultural_narratives",
    "project_emotional_state",
    "project_goals",
    "project_group_formation",
    "project_self_model",
    "project_social_conventions",
    "project_social_norms",
    "project_theory_of_mind",
]


@dataclass(frozen=True, slots=True)
class GoalSummary:
    goal_id: str
    status: str
    horizon: str
    priority: float
    confidence: float | None
    created_tick: int
    parent_goal_id: str | None
    dependency_count: int


@dataclass(frozen=True, slots=True)
class GoalsProjection:
    schema_version: Literal["research-goals-v1"]
    owner_id: str
    availability: Availability
    head_count: int
    items: tuple[GoalSummary, ...]


@dataclass(frozen=True, slots=True)
class EmotionIntensitySummary:
    kind: str
    intensity: float


@dataclass(frozen=True, slots=True)
class EmotionalStateProjection:
    schema_version: Literal["research-emotional-state-v1"]
    owner_id: str
    availability: Availability
    tick: int | None
    last_update_tick: int | None
    policy_version: str | None
    head_count: int
    intensities: tuple[EmotionIntensitySummary, ...]


@dataclass(frozen=True, slots=True)
class SelfModelProjection:
    schema_version: Literal["research-self-model-v1"]
    owner_id: str
    availability: Availability
    identity_tick: int | None
    identity_operation_count: int
    goal_count: int
    goal_ids: tuple[str, ...]
    note: str


@dataclass(frozen=True, slots=True)
class LedgerItemSummary:
    item_id: str
    kind_code: str
    status: str | None
    strength: float | None
    target_id: str | None
    evidence_count: int


@dataclass(frozen=True, slots=True)
class TheoryOfMindProjection:
    schema_version: Literal["research-theory-of-mind-v1"]
    owner_id: str
    availability: Availability
    head_count: int
    items: tuple[LedgerItemSummary, ...]


@dataclass(frozen=True, slots=True)
class GroupFormationProjection:
    schema_version: Literal["research-group-formation-v1"]
    owner_id: str
    availability: Availability
    head_count: int
    concept_count: int
    items: tuple[LedgerItemSummary, ...]


@dataclass(frozen=True, slots=True)
class SocialNormsProjection:
    schema_version: Literal["research-social-norms-v1"]
    owner_id: str
    availability: Availability
    head_count: int
    items: tuple[LedgerItemSummary, ...]


@dataclass(frozen=True, slots=True)
class SocialConventionsProjection:
    schema_version: Literal["research-social-conventions-v1"]
    owner_id: str
    availability: Availability
    head_count: int
    items: tuple[LedgerItemSummary, ...]


@dataclass(frozen=True, slots=True)
class NarrativeProjection:
    schema_version: Literal["research-cultural-narratives-v1"]
    owner_id: str
    availability: Availability
    head_count: int
    items: tuple[LedgerItemSummary, ...]


def _owner_ok(owner_id: str, checkpoint: AgentRuntimeCheckpoint | None) -> bool:
    require_stable_id("owner_id", owner_id)
    return checkpoint is not None and checkpoint.agent_id.value == owner_id


def project_goals(
    owner_id: str, checkpoint: AgentRuntimeCheckpoint | None
) -> GoalsProjection:
    if not _owner_ok(owner_id, checkpoint) or checkpoint is None:
        _LOG.debug("subjective_projection kind=goals availability=unavailable")
        return GoalsProjection(
            schema_version="research-goals-v1",
            owner_id=owner_id,
            availability="unavailable",
            head_count=0,
            items=(),
        )
    items: list[GoalSummary] = []
    for goal in checkpoint.goals:
        parent = None if goal.parent_goal_id is None else goal.parent_goal_id.value
        items.append(
            GoalSummary(
                goal_id=goal.goal_id.value,
                status=goal.status.value,
                horizon=goal.horizon.value,
                priority=float(goal.priority),
                confidence=None if goal.confidence is None else float(goal.confidence),
                created_tick=int(goal.created_tick),
                parent_goal_id=parent,
                dependency_count=len(goal.dependency_ids),
            )
        )
    _LOG.debug(
        "subjective_projection kind=goals availability=available head_count=%s",
        len(items),
    )
    return GoalsProjection(
        schema_version="research-goals-v1",
        owner_id=owner_id,
        availability="available",
        head_count=len(items),
        items=tuple(items),
    )


def project_emotional_state(
    owner_id: str, checkpoint: AgentRuntimeCheckpoint | None
) -> EmotionalStateProjection:
    if not _owner_ok(owner_id, checkpoint) or checkpoint is None:
        return EmotionalStateProjection(
            schema_version="research-emotional-state-v1",
            owner_id=owner_id,
            availability="unavailable",
            tick=None,
            last_update_tick=None,
            policy_version=None,
            head_count=0,
            intensities=(),
        )
    state = checkpoint.emotional_state
    if state is None:
        _LOG.debug(
            "subjective_projection kind=emotional_state availability=unavailable"
        )
        return EmotionalStateProjection(
            schema_version="research-emotional-state-v1",
            owner_id=owner_id,
            availability="unavailable",
            tick=None,
            last_update_tick=None,
            policy_version=None,
            head_count=0,
            intensities=(),
        )
    intensities = tuple(
        EmotionIntensitySummary(kind=entry.kind.value, intensity=float(entry.intensity))
        for entry in state.intensities
    )
    _LOG.debug(
        "subjective_projection kind=emotional_state availability=available "
        "head_count=%s",
        len(intensities),
    )
    return EmotionalStateProjection(
        schema_version="research-emotional-state-v1",
        owner_id=owner_id,
        availability="available",
        tick=int(state.tick),
        last_update_tick=int(state.last_update_tick),
        policy_version=str(state.policy_version),
        head_count=len(intensities),
        intensities=intensities,
    )


def project_self_model(
    owner_id: str, checkpoint: AgentRuntimeCheckpoint | None
) -> SelfModelProjection:
    """Project self-model chrome from identity_cursor + goals (not a row)."""
    if not _owner_ok(owner_id, checkpoint) or checkpoint is None:
        return SelfModelProjection(
            schema_version="research-self-model-v1",
            owner_id=owner_id,
            availability="unavailable",
            identity_tick=None,
            identity_operation_count=0,
            goal_count=0,
            goal_ids=(),
            note="checkpoint_missing",
        )
    cursor = checkpoint.identity_cursor
    goal_ids = tuple(goal.goal_id.value for goal in checkpoint.goals)
    if cursor is None and not goal_ids:
        _LOG.debug("subjective_projection kind=self_model availability=unavailable")
        return SelfModelProjection(
            schema_version="research-self-model-v1",
            owner_id=owner_id,
            availability="unavailable",
            identity_tick=None,
            identity_operation_count=0,
            goal_count=0,
            goal_ids=(),
            note="identity_and_goals_absent",
        )
    identity_tick = None if cursor is None else int(cursor.last_applied_tick)
    op_count = 0 if cursor is None else len(cursor.operation_ids)
    _LOG.debug(
        "subjective_projection kind=self_model availability=available "
        "goal_count=%s identity_ops=%s",
        len(goal_ids),
        op_count,
    )
    return SelfModelProjection(
        schema_version="research-self-model-v1",
        owner_id=owner_id,
        availability="available",
        identity_tick=identity_tick,
        identity_operation_count=op_count,
        goal_count=len(goal_ids),
        goal_ids=goal_ids,
        note="projection_from_identity_cursor_and_goals",
    )


def project_theory_of_mind(
    owner_id: str, checkpoint: AgentRuntimeCheckpoint | None
) -> TheoryOfMindProjection:
    if not _owner_ok(owner_id, checkpoint) or checkpoint is None:
        return TheoryOfMindProjection(
            schema_version="research-theory-of-mind-v1",
            owner_id=owner_id,
            availability="unavailable",
            head_count=0,
            items=(),
        )
    model = checkpoint.theory_of_mind
    if model is None:
        return TheoryOfMindProjection(
            schema_version="research-theory-of-mind-v1",
            owner_id=owner_id,
            availability="unavailable",
            head_count=0,
            items=(),
        )
    items: list[LedgerItemSummary] = []
    for hyp in getattr(model, "hypotheses", ()):
        items.append(
            LedgerItemSummary(
                item_id=str(getattr(hyp, "hypothesis_id", "")),
                kind_code=str(getattr(getattr(hyp, "aspect", None), "value", "unknown")),
                status=None,
                strength=float(getattr(hyp, "confidence", 0.0)),
                target_id=str(
                    getattr(getattr(hyp, "subject_id", None), "value", "") or ""
                )
                or None,
                evidence_count=len(getattr(hyp, "evidence_ids", ())),
            )
        )
    _LOG.debug(
        "subjective_projection kind=theory_of_mind availability=available "
        "head_count=%s",
        len(items),
    )
    return TheoryOfMindProjection(
        schema_version="research-theory-of-mind-v1",
        owner_id=owner_id,
        availability="available",
        head_count=len(items),
        items=tuple(items),
    )


def project_group_formation(
    owner_id: str, checkpoint: AgentRuntimeCheckpoint | None
) -> GroupFormationProjection:
    if not _owner_ok(owner_id, checkpoint) or checkpoint is None:
        return GroupFormationProjection(
            schema_version="research-group-formation-v1",
            owner_id=owner_id,
            availability="unavailable",
            head_count=0,
            concept_count=0,
            items=(),
        )
    ledger = checkpoint.group_formation
    if ledger is None:
        return GroupFormationProjection(
            schema_version="research-group-formation-v1",
            owner_id=owner_id,
            availability="unavailable",
            head_count=0,
            concept_count=0,
            items=(),
        )
    items: list[LedgerItemSummary] = []
    for belief in getattr(ledger, "beliefs", ()):
        status = getattr(belief, "status", None)
        members = getattr(belief, "member_ids", ())
        items.append(
            LedgerItemSummary(
                item_id=str(getattr(belief, "belief_id", "")),
                kind_code=str(
                    getattr(getattr(belief, "stance", None), "value", "membership")
                ),
                status=None if status is None else str(getattr(status, "value", status)),
                strength=float(getattr(belief, "support", 0.0)),
                target_id=f"members:{len(members)}" if members else None,
                evidence_count=len(getattr(belief, "evidence", ())),
            )
        )
    concepts = getattr(ledger, "concepts", ())
    _LOG.debug(
        "subjective_projection kind=group_formation availability=available "
        "head_count=%s",
        len(items),
    )
    return GroupFormationProjection(
        schema_version="research-group-formation-v1",
        owner_id=owner_id,
        availability="available",
        head_count=len(items),
        concept_count=len(concepts),
        items=tuple(items),
    )


def project_social_norms(
    owner_id: str, checkpoint: AgentRuntimeCheckpoint | None
) -> SocialNormsProjection:
    if not _owner_ok(owner_id, checkpoint) or checkpoint is None:
        return SocialNormsProjection(
            schema_version="research-social-norms-v1",
            owner_id=owner_id,
            availability="unavailable",
            head_count=0,
            items=(),
        )
    ledger = checkpoint.social_norms
    if ledger is None:
        return SocialNormsProjection(
            schema_version="research-social-norms-v1",
            owner_id=owner_id,
            availability="unavailable",
            head_count=0,
            items=(),
        )
    items: list[LedgerItemSummary] = []
    for belief in getattr(ledger, "beliefs", ()):
        status = getattr(belief, "status", None)
        items.append(
            LedgerItemSummary(
                item_id=str(getattr(belief, "belief_id", "")),
                kind_code=str(
                    getattr(getattr(belief, "pattern", None), "value", "norm")
                ),
                status=None if status is None else str(getattr(status, "value", status)),
                strength=float(getattr(belief, "confidence", 0.0)),
                target_id=None,
                evidence_count=len(getattr(belief, "evidence", ())),
            )
        )
    _LOG.debug(
        "subjective_projection kind=social_norms availability=available head_count=%s",
        len(items),
    )
    return SocialNormsProjection(
        schema_version="research-social-norms-v1",
        owner_id=owner_id,
        availability="available",
        head_count=len(items),
        items=tuple(items),
    )


def project_social_conventions(
    owner_id: str, checkpoint: AgentRuntimeCheckpoint | None
) -> SocialConventionsProjection:
    if not _owner_ok(owner_id, checkpoint) or checkpoint is None:
        return SocialConventionsProjection(
            schema_version="research-social-conventions-v1",
            owner_id=owner_id,
            availability="unavailable",
            head_count=0,
            items=(),
        )
    ledger = checkpoint.social_conventions
    if ledger is None:
        return SocialConventionsProjection(
            schema_version="research-social-conventions-v1",
            owner_id=owner_id,
            availability="unavailable",
            head_count=0,
            items=(),
        )
    items: list[LedgerItemSummary] = []
    beliefs = getattr(ledger, "beliefs", None)
    if beliefs is None:
        beliefs = getattr(ledger, "conventions", ())
    for belief in beliefs:
        status = getattr(belief, "status", None)
        items.append(
            LedgerItemSummary(
                item_id=str(
                    getattr(belief, "belief_id", None)
                    or getattr(belief, "convention_id", "")
                ),
                kind_code=str(
                    getattr(
                        getattr(belief, "pattern", None),
                        "value",
                        getattr(getattr(belief, "kind", None), "value", "convention"),
                    )
                ),
                status=None if status is None else str(getattr(status, "value", status)),
                strength=float(getattr(belief, "confidence", getattr(belief, "strength", 0.0))),
                target_id=None,
                evidence_count=len(getattr(belief, "evidence", ())),
            )
        )
    _LOG.debug(
        "subjective_projection kind=social_conventions availability=available "
        "head_count=%s",
        len(items),
    )
    return SocialConventionsProjection(
        schema_version="research-social-conventions-v1",
        owner_id=owner_id,
        availability="available",
        head_count=len(items),
        items=tuple(items),
    )


def project_cultural_narratives(
    owner_id: str, checkpoint: AgentRuntimeCheckpoint | None
) -> NarrativeProjection:
    if not _owner_ok(owner_id, checkpoint) or checkpoint is None:
        return NarrativeProjection(
            schema_version="research-cultural-narratives-v1",
            owner_id=owner_id,
            availability="unavailable",
            head_count=0,
            items=(),
        )
    ledger = checkpoint.cultural_narratives
    if ledger is None:
        return NarrativeProjection(
            schema_version="research-cultural-narratives-v1",
            owner_id=owner_id,
            availability="unavailable",
            head_count=0,
            items=(),
        )
    items: list[LedgerItemSummary] = []
    for variant in getattr(ledger, "variants", ()):
        status = getattr(variant, "status", None)
        items.append(
            LedgerItemSummary(
                item_id=str(getattr(variant, "variant_id", "")),
                kind_code=str(
                    getattr(getattr(variant, "origin", None), "value", "narrative")
                ),
                status=None if status is None else str(getattr(status, "value", status)),
                strength=float(getattr(variant, "strength", 0.0)),
                target_id=None,
                evidence_count=len(getattr(variant, "evidence", ())),
            )
        )
    _LOG.debug(
        "subjective_projection kind=cultural_narratives availability=available "
        "head_count=%s",
        len(items),
    )
    return NarrativeProjection(
        schema_version="research-cultural-narratives-v1",
        owner_id=owner_id,
        availability="available",
        head_count=len(items),
        items=tuple(items),
    )
