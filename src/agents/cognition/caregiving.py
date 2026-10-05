"""Deterministic caregiving candidate bias (no parent hardcode).

When ``dependency_care.caregiving_cognition_mode=deterministic``, boost
care-shaped futures using only owner-scoped subjective inputs:
relationships, goals/drives, norms/conventions (when supplied), subjective
kinship-shaped relationship dimensions / testimony tags, and optional
perceived dependency needs. Never imports ``world.kinship`` or assigns
caregivers. Zero care bias (neglect) is a legal outcome.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Mapping, Sequence
from typing import Final

from agents.cognition.models import ActionDirection, ImaginedFuture
from agents.models import AgentId, DriveKind
from social.relationships import (
    DirectedRelationshipProfile,
    RelationshipDimension,
)
from world.observations import Observation

__all__ = [
    "CAREGIVING_BIAS_POLICY_VERSION",
    "caregiving_future_biases",
    "caregiving_mode_active",
    "score_components_hash",
]

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.caregiving")

CAREGIVING_BIAS_POLICY_VERSION: Final[str] = "caregiving-bias.v1"

_MAX_BIAS: Final[float] = 0.40
_AFFECTION_WEIGHT: Final[float] = 0.35
_TRUST_WEIGHT: Final[float] = 0.20
_FAMILIARITY_WEIGHT: Final[float] = 0.10
_DEPENDENCY_WEIGHT: Final[float] = 0.25
_NEED_CRITICAL_BONUS: Final[float] = 0.20
_NEED_PRESENT_BONUS: Final[float] = 0.10
_DRIVE_SAFETY_BONUS: Final[float] = 0.08
_DRIVE_BELONGING_BONUS: Final[float] = 0.08
_FEAR_PENALTY: Final[float] = 0.25
_RESENTMENT_PENALTY: Final[float] = 0.20

_CARE_DIRECTIONS: Final[frozenset[ActionDirection]] = frozenset(
    {
        ActionDirection.HELP,
        ActionDirection.FEED,
        ActionDirection.TRANSPORT,
        ActionDirection.COMMUNICATE,
    }
)

_ASSIST_FOR_DIRECTION: Final[Mapping[ActionDirection, str]] = {
    ActionDirection.HELP: "help_safety",
    ActionDirection.FEED: "feed",
    ActionDirection.TRANSPORT: "transport",
    ActionDirection.COMMUNICATE: "teach_learning",
}

_KINSHIP_TESTIMONY_TAGS: Final[frozenset[str]] = frozenset(
    {
        "kinship",
        "kin",
        "parent",
        "child",
        "family",
        "related",
    }
)


def caregiving_mode_active(mode: str | None) -> bool:
    """Return whether deterministic caregiving bias should apply."""
    return mode == "deterministic"


def score_components_hash(
    *,
    affection: float,
    trust: float,
    familiarity: float,
    dependency: float,
    need_bonus: float,
    drive_bonus: float,
    fear: float,
    resentment: float,
) -> str:
    """Stable short digest of score components (no payload dumps)."""
    payload = (
        f"a={affection:.4f}|t={trust:.4f}|f={familiarity:.4f}|d={dependency:.4f}|"
        f"n={need_bonus:.4f}|drv={drive_bonus:.4f}|fear={fear:.4f}|res={resentment:.4f}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def caregiving_future_biases(
    *,
    owner_id: AgentId,
    mode: str | None,
    futures: Sequence[ImaginedFuture],
    relationships: Sequence[object],
    observation: Observation,
    active_drive_kinds: (
        Sequence[DriveKind] | frozenset[DriveKind] | set[DriveKind]
    ) = (),
    allow_feed: bool = True,
    allow_transport: bool = True,
    allow_help_safety: bool = True,
    allow_teach_learning: bool = True,
) -> dict[str, float]:
    """Return future_id → bias delta. Empty when mode is disabled."""
    if not caregiving_mode_active(mode):
        return {}
    if type(owner_id) is not AgentId:
        raise TypeError("owner_id must be AgentId")
    if type(observation) is not Observation:
        raise TypeError("observation must be Observation")

    profiles = _index_profiles(relationships)
    active = frozenset(active_drive_kinds)
    biases: dict[str, float] = {}

    for future in futures:
        if type(future) is not ImaginedFuture:
            raise TypeError("futures entries must be ImaginedFuture")
        direction = future.direction
        if direction not in _CARE_DIRECTIONS:
            continue
        if direction is ActionDirection.HELP and not allow_help_safety:
            continue
        if direction is ActionDirection.FEED and not allow_feed:
            continue
        if direction is ActionDirection.TRANSPORT and not allow_transport:
            continue
        if direction is ActionDirection.COMMUNICATE and not allow_teach_learning:
            continue

        target_entity = future.target_entity_id
        if target_entity is None:
            continue
        target_agent = future.target_agent_id
        profile = None
        if target_agent is not None:
            profile = profiles.get(target_agent.value)
        if profile is None:
            # Resolve via social bindings later; entity-only targets may still
            # receive need-based bias without a relationship profile.
            profile = _profile_for_entity(profiles, observation, target_entity)

        affection, trust, familiarity, dependency, fear, resentment = (
            _dimension_values(profile)
        )
        # Subjective kinship-shaped signal: positive DEPENDENCY + testimony tags.
        kinship_belief = _subjective_kinship_hint(
            profile=profile,
            dependency=dependency,
            observation=observation,
            target_entity=target_entity,
        )
        need_bonus = _need_bonus(observation, target_entity, direction)
        drive_bonus = 0.0
        if DriveKind.SAFETY in active:
            drive_bonus += _DRIVE_SAFETY_BONUS
        if DriveKind.BELONGING in active:
            drive_bonus += _DRIVE_BELONGING_BONUS

        raw = (
            _AFFECTION_WEIGHT * max(0.0, affection)
            + _TRUST_WEIGHT * max(0.0, trust)
            + _FAMILIARITY_WEIGHT * max(0.0, familiarity)
            + _DEPENDENCY_WEIGHT * max(0.0, dependency)
            + (0.05 if kinship_belief else 0.0)
            + need_bonus
            + drive_bonus
            - _FEAR_PENALTY * max(0.0, fear)
            - _RESENTMENT_PENALTY * max(0.0, resentment)
        )
        score = _clamp_bias(raw)
        if score <= 0.0:
            continue
        biases[future.future_id] = score
        components = score_components_hash(
            affection=affection,
            trust=trust,
            familiarity=familiarity,
            dependency=dependency,
            need_bonus=need_bonus,
            drive_bonus=drive_bonus,
            fear=fear,
            resentment=resentment,
        )
        _LOG.debug(
            "caregiving_candidate_score owner_id=%s target_id=%s assist_kind=%s "
            "score_components_hash=%s",
            owner_id.value,
            target_entity,
            _ASSIST_FOR_DIRECTION.get(direction, direction.value),
            components,
        )
    return biases


def _clamp_bias(value: float) -> float:
    if value <= 0.0:
        return 0.0
    if value > _MAX_BIAS:
        return _MAX_BIAS
    return value


def _index_profiles(
    relationships: Sequence[object],
) -> dict[str, DirectedRelationshipProfile]:
    indexed: dict[str, DirectedRelationshipProfile] = {}
    for item in relationships:
        if type(item) is not DirectedRelationshipProfile:
            continue
        indexed[item.target_id.value] = item
    return indexed


def _profile_for_entity(
    profiles: Mapping[str, DirectedRelationshipProfile],
    observation: Observation,
    target_entity: str,
) -> DirectedRelationshipProfile | None:
    snapshot_identity = None
    # Observation does not carry social identity; leave unbound.
    _ = observation
    _ = snapshot_identity
    _ = target_entity
    return None


def _dimension_values(
    profile: DirectedRelationshipProfile | None,
) -> tuple[float, float, float, float, float, float]:
    if profile is None:
        return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
    dims = profile.dimension_map()

    def _val(kind: RelationshipDimension) -> float:
        state = dims.get(kind)
        if state is None:
            return 0.0
        return float(state.value)

    return (
        _val(RelationshipDimension.AFFECTION),
        _val(RelationshipDimension.TRUST),
        _val(RelationshipDimension.FAMILIARITY),
        _val(RelationshipDimension.DEPENDENCY),
        _val(RelationshipDimension.FEAR),
        _val(RelationshipDimension.RESENTMENT),
    )


def _subjective_kinship_hint(
    *,
    profile: DirectedRelationshipProfile | None,
    dependency: float,
    observation: Observation,
    target_entity: str,
) -> bool:
    """True only from subjective cues — never objective kinship edges."""
    if dependency > 0.0:
        return True
    _ = profile
    for message in observation.communications:
        tags = getattr(message, "tags", ()) or ()
        content = getattr(message, "content", None)
        text = "" if content is None else str(getattr(content, "text", content))
        haystack = " ".join(str(tag) for tag in tags) + " " + text.lower()
        if any(token in haystack for token in _KINSHIP_TESTIMONY_TAGS):
            speaker = message.speaker_id.value
            if speaker == target_entity or target_entity in haystack:
                return True
    return False


def _need_bonus(
    observation: Observation, target_entity: str, direction: ActionDirection
) -> float:
    body = None
    if (
        observation.self_body is not None
        and observation.self_body.entity_id.value == target_entity
    ):
        body = observation.self_body
    else:
        for visible in observation.visible_bodies:
            if visible.entity_id.value == target_entity:
                body = visible
                break
    if body is None:
        return 0.0
    needs = getattr(body, "dependency_needs", None)
    if needs is None:
        return 0.0
    rows = getattr(needs, "needs", ()) or ()
    if not rows:
        return 0.0
    relevant: set[str]
    if direction is ActionDirection.FEED:
        relevant = {"food", "water"}
    elif direction is ActionDirection.TRANSPORT:
        relevant = {"movement", "shelter"}
    elif direction is ActionDirection.HELP:
        relevant = {"safety", "food", "water"}
    elif direction is ActionDirection.COMMUNICATE:
        relevant = {"learning"}
    else:
        relevant = set()
    bonus = 0.0
    for row in rows:
        need_id = getattr(row, "need_id", None)
        if need_id not in relevant:
            continue
        if bool(getattr(row, "critical", False)):
            bonus = max(bonus, _NEED_CRITICAL_BONUS)
        else:
            bonus = max(bonus, _NEED_PRESENT_BONUS)
    return bonus
