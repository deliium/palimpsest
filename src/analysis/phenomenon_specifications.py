"""Published phenomenon → indicator mapping and support_band rules.

Log-free data. Validation errors expose stable reason codes only.
"""

from __future__ import annotations

from typing import Final

from analysis.phenomenon_models import (
    PhenomenonId,
    PhenomenonIndicatorRef,
    SupportBand,
    SupportDirection,
)

__all__ = [
    "SUPPORT_BAND_RULES",
    "indicator_meets_floor",
    "phenomenon_indicator_refs",
    "resolve_support_band",
    "validate_phenomenon_mappings",
]


class PhenomenonSpecificationError(ValueError):
    """Fail-closed specification error; message is a reason code."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)


SUPPORT_BAND_RULES: Final[dict[str, str]] = {
    SupportBand.ABSENT.value: "fewer than 1 present indicator for the phenomenon",
    SupportBand.WEAK.value: (
        "exactly 1 present indicator (unary mappings) "
        "or >=2 present but all below their weak floor"
    ),
    SupportBand.MODERATE.value: (
        ">=2 present indicators and at least half meet their moderate floor"
    ),
    SupportBand.STRONG.value: (
        ">=2 present indicators and all meet their strong floor"
    ),
}


def _ref(
    family: str,
    key: str,
    *,
    direction: SupportDirection = SupportDirection.HIGHER_IS_STRONGER,
    weak: float,
    moderate: float,
    strong: float,
) -> PhenomenonIndicatorRef:
    return PhenomenonIndicatorRef(
        metric_family=family,
        value_key=key,
        direction=direction,
        weak_floor=weak,
        moderate_floor=moderate,
        strong_floor=strong,
    )


_MAPPINGS: Final[dict[PhenomenonId, tuple[PhenomenonIndicatorRef, ...]]] = {
    PhenomenonId.COMMUNITY_STRUCTURE: (
        _ref("group_community_structure", "modularity", weak=0.05, moderate=0.2, strong=0.4),
        _ref(
            "group_community_structure",
            "community_count",
            weak=2.0,
            moderate=3.0,
            strong=4.0,
        ),
    ),
    PhenomenonId.GROUP_PERSISTENCE: (
        _ref(
            "emergent_group_formation",
            "cluster_count",
            weak=1.0,
            moderate=2.0,
            strong=3.0,
        ),
        _ref(
            "emergent_group_formation",
            "agent_count",
            weak=2.0,
            moderate=4.0,
            strong=6.0,
        ),
    ),
    PhenomenonId.NETWORK_CENTRALITY: (
        _ref(
            "trust_network_structure",
            "centralization_out",
            weak=0.1,
            moderate=0.3,
            strong=0.5,
        ),
        _ref(
            "trust_network_structure",
            "mean_betweenness_centrality",
            weak=0.05,
            moderate=0.15,
            strong=0.3,
        ),
    ),
    PhenomenonId.RECIPROCITY: (
        _ref(
            "trust_network_structure",
            "reciprocity",
            weak=0.2,
            moderate=0.5,
            strong=0.8,
        ),
    ),
    PhenomenonId.COOPERATION: (
        _ref(
            "cooperation",
            "coop_occurrence_rate",
            weak=0.1,
            moderate=0.3,
            strong=0.6,
        ),
        _ref(
            "cooperation",
            "coop_event_count",
            weak=1.0,
            moderate=5.0,
            strong=20.0,
        ),
    ),
    PhenomenonId.RESOURCE_INEQUALITY: (
        _ref(
            "resource_inequality",
            "gini",
            weak=0.1,
            moderate=0.3,
            strong=0.5,
        ),
        _ref(
            "resource_inequality",
            "share_top_1",
            weak=0.3,
            moderate=0.5,
            strong=0.7,
        ),
    ),
    PhenomenonId.SPECIALIZATION: (
        _ref(
            "behavioral_specialization",
            "mean_herfindahl",
            weak=0.2,
            moderate=0.4,
            strong=0.7,
        ),
        _ref(
            "behavioral_specialization",
            "agents_scored",
            weak=2.0,
            moderate=4.0,
            strong=6.0,
        ),
    ),
    PhenomenonId.TERRITORIAL_CONCENTRATION: (
        _ref(
            "territorial_concentration",
            "presence_hhi",
            weak=0.2,
            moderate=0.4,
            strong=0.7,
        ),
        _ref(
            "territorial_concentration",
            "presence_top1_share",
            weak=0.3,
            moderate=0.5,
            strong=0.8,
        ),
    ),
    PhenomenonId.REPUTATION_DIVERGENCE: (
        _ref(
            "distributed_reputation",
            "reliability_gap",
            weak=0.1,
            moderate=0.3,
            strong=0.6,
        ),
        _ref(
            "distributed_reputation",
            "mean_pairwise_gap",
            weak=0.1,
            moderate=0.3,
            strong=0.6,
        ),
    ),
    PhenomenonId.BELIEF_CONVERGENCE: (
        _ref(
            "belief_convergence",
            "mean_pairwise_jaccard_final",
            weak=0.2,
            moderate=0.5,
            strong=0.8,
        ),
        _ref(
            "belief_convergence",
            "mean_pairwise_jaccard_delta",
            weak=0.05,
            moderate=0.2,
            strong=0.4,
        ),
    ),
    PhenomenonId.NORM_ADOPTION: (
        _ref(
            "emergent_social_norms",
            "active_belief_count",
            weak=1.0,
            moderate=2.0,
            strong=4.0,
        ),
        _ref(
            "emergent_social_norms",
            "belief_persistence",
            weak=0.2,
            moderate=0.5,
            strong=0.8,
        ),
    ),
    PhenomenonId.CONVENTION_PERSISTENCE: (
        _ref(
            "persistent_social_conventions",
            "active_habit_count",
            weak=1.0,
            moderate=2.0,
            strong=4.0,
        ),
        _ref(
            "persistent_social_conventions",
            "habit_persistence",
            weak=0.2,
            moderate=0.5,
            strong=0.8,
        ),
    ),
    PhenomenonId.CULTURAL_SIMILARITY: (
        _ref(
            "cultural_similarity",
            "naming_mean_pairwise_similarity",
            weak=0.2,
            moderate=0.5,
            strong=0.8,
        ),
        _ref(
            "cultural_similarity",
            "channels_present",
            weak=1.0,
            moderate=2.0,
            strong=3.0,
        ),
    ),
    PhenomenonId.RUMOR_NARRATIVE_MUTATION: (
        _ref(
            "rumor_distortion",
            "mean_concepts_added",
            weak=0.1,
            moderate=0.3,
            strong=0.6,
        ),
        _ref(
            "cultural_narrative_lineage",
            "active_variant_count",
            weak=2.0,
            moderate=4.0,
            strong=8.0,
        ),
    ),
    PhenomenonId.VOCABULARY_CONVERGENCE: (
        _ref(
            "emergent_semantic_naming",
            "label_persistence",
            weak=0.2,
            moderate=0.5,
            strong=0.8,
        ),
        _ref(
            "emergent_semantic_naming",
            "mean_owners_per_label",
            weak=1.0,
            moderate=2.0,
            strong=3.0,
        ),
    ),
    PhenomenonId.SURVIVAL_DIFFERENCES: (
        _ref("survival", "survival_rate_at_T", weak=0.2, moderate=0.5, strong=0.8),
        _ref(
            "survival_cohort_contrast",
            "max_cohort_gap",
            weak=0.1,
            moderate=0.3,
            strong=0.6,
        ),
    ),
    PhenomenonId.GOAL_SUCCESS: (
        _ref(
            "goal_completion",
            "completion_rate",
            weak=0.1,
            moderate=0.3,
            strong=0.6,
        ),
        _ref(
            "goal_completion",
            "goals_total",
            weak=1.0,
            moderate=3.0,
            strong=8.0,
        ),
    ),
    PhenomenonId.PREDICTION_CALIBRATION: (
        _ref(
            "prediction_calibration",
            "brier_score",
            direction=SupportDirection.LOWER_IS_STRONGER,
            weak=0.25,
            moderate=0.15,
            strong=0.05,
        ),
        _ref(
            "prediction_calibration",
            "mean_absolute_calibration_error",
            direction=SupportDirection.LOWER_IS_STRONGER,
            weak=0.25,
            moderate=0.15,
            strong=0.05,
        ),
    ),
}


def phenomenon_indicator_refs(
    phenomenon_id: PhenomenonId,
) -> tuple[PhenomenonIndicatorRef, ...]:
    """Return locked indicator refs for one phenomenon."""
    if type(phenomenon_id) is not PhenomenonId:
        raise PhenomenonSpecificationError("invalid_phenomenon_id")
    refs = _MAPPINGS.get(phenomenon_id)
    if refs is None:
        raise PhenomenonSpecificationError("missing_mapping")
    return refs


def indicator_meets_floor(
    value: float,
    floor: float,
    direction: SupportDirection,
) -> bool:
    """Direction-aware floor check."""
    if direction is SupportDirection.HIGHER_IS_STRONGER:
        return value >= floor
    return value <= floor


def resolve_support_band(
    *,
    present_count: int,
    meets_weak: int,
    meets_moderate: int,
    meets_strong: int,
    unary_allowed: bool,
) -> SupportBand:
    """Apply the locked multi-indicator support_band rule table."""
    if present_count < 1:
        return SupportBand.ABSENT
    if present_count == 1:
        if unary_allowed:
            return SupportBand.WEAK
        return SupportBand.ABSENT
    if meets_strong == present_count:
        return SupportBand.STRONG
    if meets_moderate * 2 >= present_count:
        return SupportBand.MODERATE
    if meets_weak == 0:
        return SupportBand.WEAK
    return SupportBand.WEAK


def validate_phenomenon_mappings() -> None:
    """Fail closed if any phenomenon is missing or unary without unary allowance."""
    expected = frozenset(PhenomenonId)
    seen = frozenset(_MAPPINGS)
    if seen != expected:
        raise PhenomenonSpecificationError("phenomenon_mapping_incomplete")
    for phenomenon_id, refs in _MAPPINGS.items():
        if not refs:
            raise PhenomenonSpecificationError("empty_indicator_refs")
        if len(refs) == 1 and phenomenon_id is not PhenomenonId.RECIPROCITY:
            raise PhenomenonSpecificationError("unexpected_unary_mapping")
