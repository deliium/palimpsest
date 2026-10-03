"""Frozen phenomenon-indicator contracts (analysis-only).

Forbidden field names: emerged, culture_emerged, norm_emerged, society_formed,
detected. Report measurable indicators and support bands only.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from analysis.models import MetricAvailability
from world.identifiers import require_stable_id

__all__ = [
    "PHENOMENON_INDICATORS_SCHEMA_VERSION",
    "PhenomenonId",
    "PhenomenonIndicatorPanel",
    "PhenomenonIndicatorReading",
    "PhenomenonIndicatorRef",
    "SupportBand",
    "SupportDirection",
]

PHENOMENON_INDICATORS_SCHEMA_VERSION: Final[str] = "phenomenon-indicators-v1"

_FORBIDDEN_FIELD_NAMES: Final[frozenset[str]] = frozenset(
    {
        "emerged",
        "culture_emerged",
        "norm_emerged",
        "society_formed",
        "detected",
    }
)


class PhenomenonId(StrEnum):
    """Closed set of researcher-facing social/cultural/cognitive phenomena."""

    COMMUNITY_STRUCTURE = "community_structure"
    GROUP_PERSISTENCE = "group_persistence"
    NETWORK_CENTRALITY = "network_centrality"
    RECIPROCITY = "reciprocity"
    COOPERATION = "cooperation"
    RESOURCE_INEQUALITY = "resource_inequality"
    SPECIALIZATION = "specialization"
    TERRITORIAL_CONCENTRATION = "territorial_concentration"
    REPUTATION_DIVERGENCE = "reputation_divergence"
    BELIEF_CONVERGENCE = "belief_convergence"
    NORM_ADOPTION = "norm_adoption"
    CONVENTION_PERSISTENCE = "convention_persistence"
    CULTURAL_SIMILARITY = "cultural_similarity"
    RUMOR_NARRATIVE_MUTATION = "rumor_narrative_mutation"
    VOCABULARY_CONVERGENCE = "vocabulary_convergence"
    SURVIVAL_DIFFERENCES = "survival_differences"
    GOAL_SUCCESS = "goal_success"
    PREDICTION_CALIBRATION = "prediction_calibration"


class SupportBand(StrEnum):
    """Multi-indicator support codes — never a single-threshold emergence flag."""

    ABSENT = "absent"
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"


class SupportDirection(StrEnum):
    """Whether higher or lower scalar values indicate stronger support."""

    HIGHER_IS_STRONGER = "higher_is_stronger"
    LOWER_IS_STRONGER = "lower_is_stronger"


@dataclass(frozen=True, slots=True)
class PhenomenonIndicatorRef:
    """One mapped metric scalar contributing to a phenomenon reading."""

    metric_family: str
    value_key: str
    direction: SupportDirection
    weak_floor: float
    moderate_floor: float
    strong_floor: float

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "metric_family",
            require_stable_id("PhenomenonIndicatorRef.metric_family", self.metric_family),
        )
        object.__setattr__(
            self,
            "value_key",
            require_stable_id("PhenomenonIndicatorRef.value_key", self.value_key),
        )
        if type(self.direction) is not SupportDirection:
            raise TypeError("PhenomenonIndicatorRef.direction: invalid_type")
        for label, value in (
            ("weak_floor", self.weak_floor),
            ("moderate_floor", self.moderate_floor),
            ("strong_floor", self.strong_floor),
        ):
            if type(value) is not float or value != value:
                raise ValueError(f"PhenomenonIndicatorRef.{label}: non_finite")


@dataclass(frozen=True, slots=True)
class PhenomenonIndicatorReading:
    """One phenomenon's indicator tallies and locked support band."""

    phenomenon_id: PhenomenonId
    support_band: SupportBand
    present_indicator_count: int
    indicator_values: tuple[tuple[str, str, object, MetricAvailability], ...]

    def __post_init__(self) -> None:
        if type(self.phenomenon_id) is not PhenomenonId:
            raise TypeError("PhenomenonIndicatorReading.phenomenon_id: invalid_type")
        if type(self.support_band) is not SupportBand:
            raise TypeError("PhenomenonIndicatorReading.support_band: invalid_type")
        if type(self.present_indicator_count) is not int or self.present_indicator_count < 0:
            raise ValueError("PhenomenonIndicatorReading.present_indicator_count: invalid")
        for name in _FORBIDDEN_FIELD_NAMES:
            if hasattr(self, name):
                raise ValueError(f"PhenomenonIndicatorReading: forbidden_field:{name}")


@dataclass(frozen=True, slots=True)
class PhenomenonIndicatorPanel:
    """Canonical multi-phenomenon panel over already-built MetricDocuments."""

    schema_version: str
    run_id: str
    input_revision: str
    readings: tuple[PhenomenonIndicatorReading, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "schema_version",
            require_stable_id(
                "PhenomenonIndicatorPanel.schema_version", self.schema_version
            ),
        )
        object.__setattr__(
            self,
            "run_id",
            require_stable_id("PhenomenonIndicatorPanel.run_id", self.run_id),
        )
        object.__setattr__(
            self,
            "input_revision",
            require_stable_id(
                "PhenomenonIndicatorPanel.input_revision", self.input_revision
            ),
        )
        if not isinstance(self.readings, tuple):
            raise TypeError("PhenomenonIndicatorPanel.readings: not_tuple")
        for name in _FORBIDDEN_FIELD_NAMES:
            if name in type(self).__annotations__ or hasattr(self, name):
                raise ValueError(f"PhenomenonIndicatorPanel: forbidden_field:{name}")
