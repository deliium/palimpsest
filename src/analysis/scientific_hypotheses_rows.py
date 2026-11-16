"""Frozen token-only facts and rows for scientific-hypothesis analysis.

Facts are the only crossing point from the experiments bridge; they are produced
from owner ledgers and carry tokenized identities only. Rows are produced by the
detached analysis and never carry an objective rule, engine probability, truth
value, or composite scientific score.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from analysis.scientific_hypotheses_contract import (
    NONE_TOKEN,
    SCIENTIFIC_HYPOTHESES_FORBIDDEN_KEYS,
    ScientificHypothesesError,
    ScientificHypothesisAvailability,
    ScientificHypothesisConditionSlot,
    ScientificHypothesisCoverage,
    ScientificHypothesisRevisionReason,
    ScientificHypothesisSourceKind,
    ScientificHypothesisStatus,
)
from world.experimentation import (
    DiscoveryMode,
    ExperimentOperator,
    ExperimentOutcomeClass,
)

__all__ = [
    "HypothesisConditionFact",
    "HypothesisFact",
    "HypothesisRevisionFact",
    "HypothesisTrialFact",
    "ScientificCoverageRow",
    "ScientificHypothesisRow",
    "ScientificObjectiveEvidenceRow",
    "ScientificOutcomeRow",
    "ScientificRevisionRow",
    "ScientificSourceRow",
    "ScientificTrialRow",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.scientific_hypotheses.rows"
)

MAX_CONDITIONS: Final[int] = 8
MAX_REVISIONS: Final[int] = 32
MAX_TRIALS: Final[int] = 64


def _forbid_keys(cls: type[object]) -> None:
    names = set(getattr(cls, "__dataclass_fields__", {}))
    if names & SCIENTIFIC_HYPOTHESES_FORBIDDEN_KEYS:
        raise ScientificHypothesesError("scientific_hypotheses_forbidden_key")


def _count(value: object) -> int:
    if isinstance(value, bool) or type(value) is not int or value < 0:
        raise ScientificHypothesesError("scientific_hypotheses_invalid_hypothesis")
    return value


def _share(value: object) -> int:
    if (
        isinstance(value, bool)
        or type(value) is not int
        or value < 0
        or value > 1_000
    ):
        raise ScientificHypothesesError("scientific_hypotheses_invalid_hypothesis")
    return value


def _flag(value: object) -> bool:
    if type(value) is not bool:
        raise ScientificHypothesesError("scientific_hypotheses_invalid_hypothesis")
    return value


def _token(value: object) -> str:
    if type(value) is not str or not value:
        raise ScientificHypothesesError("scientific_hypotheses_unstable_token")
    if len(value) > 128 or value != value.strip():
        raise ScientificHypothesesError("scientific_hypotheses_unstable_token")
    if any(ord(char) < 32 for char in value):
        raise ScientificHypothesesError("scientific_hypotheses_unstable_token")
    return value


def _enum(value: object, enum_type: type) -> object:
    if type(value) is enum_type:
        return value
    if type(value) is str and value in {
        item.value for item in enum_type
    }:
        return enum_type(value)
    raise ScientificHypothesesError("scientific_hypotheses_invalid_hypothesis")


def _outcome(value: object) -> ExperimentOutcomeClass | str:
    if value == NONE_TOKEN:
        return NONE_TOKEN
    if type(value) is ExperimentOutcomeClass:
        return value
    if type(value) is str and value in {
        item.value for item in ExperimentOutcomeClass
    }:
        return ExperimentOutcomeClass(value)
    raise ScientificHypothesesError("scientific_hypotheses_invalid_hypothesis")


def _condition_pairs(
    value: object,
) -> tuple[tuple[ScientificHypothesisConditionSlot, str], ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ScientificHypothesesError("scientific_hypotheses_invalid_condition")
    rows: list[tuple[ScientificHypothesisConditionSlot, str]] = []
    seen: set[ScientificHypothesisConditionSlot] = set()
    for item in value:
        if isinstance(item, (str, bytes)) or not isinstance(item, Sequence):
            raise ScientificHypothesesError(
                "scientific_hypotheses_invalid_condition"
            )
        if len(item) != 2:
            raise ScientificHypothesesError(
                "scientific_hypotheses_invalid_condition"
            )
        slot = _enum(item[0], ScientificHypothesisConditionSlot)
        token = _token(item[1])
        if slot in seen:
            raise ScientificHypothesesError(
                "scientific_hypotheses_invalid_condition"
            )
        seen.add(slot)
        rows.append((slot, token))
    if len(rows) > MAX_CONDITIONS:
        raise ScientificHypothesesError("scientific_hypotheses_invalid_cap")
    return tuple(rows)


@dataclass(frozen=True, slots=True)
class HypothesisConditionFact:
    """One closed observation slot and its tokenized value."""

    slot: ScientificHypothesisConditionSlot
    value_token: str

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(
            self, "slot", _enum(self.slot, ScientificHypothesisConditionSlot)
        )
        object.__setattr__(self, "value_token", _token(self.value_token))


@dataclass(frozen=True, slots=True)
class HypothesisRevisionFact:
    """One append-only owner revision in the facts layer."""

    revision_index: int
    tick: int
    reason: ScientificHypothesisRevisionReason
    claim_token: str
    predicted_outcome: ExperimentOutcomeClass | str
    condition_pairs: tuple[tuple[ScientificHypothesisConditionSlot, str], ...]
    confidence_milli: int
    evidence_ref: str

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(self, "revision_index", _count(self.revision_index))
        object.__setattr__(self, "tick", _count(self.tick))
        object.__setattr__(
            self,
            "reason",
            _enum(self.reason, ScientificHypothesisRevisionReason),
        )
        object.__setattr__(self, "claim_token", _token(self.claim_token))
        object.__setattr__(self, "predicted_outcome", _outcome(self.predicted_outcome))
        object.__setattr__(
            self, "condition_pairs", _condition_pairs(self.condition_pairs)
        )
        object.__setattr__(
            self, "confidence_milli", _share(self.confidence_milli)
        )
        if self.evidence_ref:
            object.__setattr__(self, "evidence_ref", _token(self.evidence_ref))


@dataclass(frozen=True, slots=True)
class HypothesisTrialFact:
    """One remembered trial outcome and whether it matched the prediction."""

    tick: int
    event_token: str
    outcome_class: ExperimentOutcomeClass
    discovery_mode: DiscoveryMode
    predicted_outcome: ExperimentOutcomeClass | str
    matched: bool

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(self, "tick", _count(self.tick))
        object.__setattr__(self, "event_token", _token(self.event_token))
        object.__setattr__(
            self, "outcome_class", _enum(self.outcome_class, ExperimentOutcomeClass)
        )
        object.__setattr__(
            self, "discovery_mode", _enum(self.discovery_mode, DiscoveryMode)
        )
        object.__setattr__(self, "predicted_outcome", _outcome(self.predicted_outcome))
        object.__setattr__(self, "matched", _flag(self.matched))


@dataclass(frozen=True, slots=True)
class HypothesisFact:
    """One owner-relative testable hypothesis projected into detached facts."""

    owner_token: str
    hypothesis_token: str
    claim_token: str
    causal_hypothesis_token: str
    status: ScientificHypothesisStatus
    predicted_outcome: ExperimentOutcomeClass | str
    confidence_milli: int
    created_tick: int
    active: bool
    source_kind: ScientificHypothesisSourceKind
    source_token: str
    conditions: tuple[HypothesisConditionFact, ...]
    revisions: tuple[HypothesisRevisionFact, ...]
    trials: tuple[HypothesisTrialFact, ...]

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(self, "owner_token", _token(self.owner_token))
        object.__setattr__(self, "hypothesis_token", _token(self.hypothesis_token))
        object.__setattr__(self, "claim_token", _token(self.claim_token))
        object.__setattr__(
            self,
            "causal_hypothesis_token",
            _token(self.causal_hypothesis_token),
        )
        object.__setattr__(
            self, "status", _enum(self.status, ScientificHypothesisStatus)
        )
        object.__setattr__(self, "predicted_outcome", _outcome(self.predicted_outcome))
        object.__setattr__(
            self, "confidence_milli", _share(self.confidence_milli)
        )
        object.__setattr__(self, "created_tick", _count(self.created_tick))
        object.__setattr__(self, "active", _flag(self.active))
        object.__setattr__(
            self, "source_kind", _enum(self.source_kind, ScientificHypothesisSourceKind)
        )
        object.__setattr__(self, "source_token", _token(self.source_token))
        object.__setattr__(self, "conditions", _facts(self.conditions, HypothesisConditionFact, MAX_CONDITIONS))  # noqa: E501
        slots = {condition.slot for condition in self.conditions}
        if len(slots) != len(self.conditions):
            raise ScientificHypothesesError(
                "scientific_hypotheses_invalid_condition"
            )
        object.__setattr__(self, "revisions", _facts(self.revisions, HypothesisRevisionFact, MAX_REVISIONS))  # noqa: E501
        indexes = [revision.revision_index for revision in self.revisions]
        if indexes != sorted(indexes) or len(set(indexes)) != len(indexes):
            raise ScientificHypothesesError(
                "scientific_hypotheses_invalid_revision"
            )
        object.__setattr__(self, "trials", _facts(self.trials, HypothesisTrialFact, MAX_TRIALS))  # noqa: E501


def _facts(value: object, fact_type: type, maximum: int) -> tuple[object, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ScientificHypothesesError("scientific_hypotheses_invalid_hypothesis")
    rows = tuple(value)
    if len(rows) > maximum:
        raise ScientificHypothesesError("scientific_hypotheses_invalid_cap")
    for row in rows:
        if type(row) is not fact_type:
            raise ScientificHypothesesError(
                "scientific_hypotheses_invalid_hypothesis"
            )
    return rows


@dataclass(frozen=True, slots=True)
class ScientificObjectiveEvidenceRow:
    """Committed experiment evidence with safe objective fields only."""

    window_index: int
    window_tick: int
    sequence: int
    event_token: str
    operator: ExperimentOperator
    outcome_class: ExperimentOutcomeClass
    discovery_mode: DiscoveryMode
    coverage: ScientificHypothesisCoverage

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        for name in ("window_index", "window_tick", "sequence"):
            object.__setattr__(self, name, _count(getattr(self, name)))
        object.__setattr__(self, "event_token", _token(self.event_token))
        object.__setattr__(
            self, "operator", _enum(self.operator, ExperimentOperator)
        )
        object.__setattr__(
            self, "outcome_class", _enum(self.outcome_class, ExperimentOutcomeClass)
        )
        object.__setattr__(
            self, "discovery_mode", _enum(self.discovery_mode, DiscoveryMode)
        )
        object.__setattr__(
            self, "coverage", _enum(self.coverage, ScientificHypothesisCoverage)
        )


@dataclass(frozen=True, slots=True)
class ScientificHypothesisRow:
    """One owner hypothesis row; identity tokens are already pseudonymous."""

    window_index: int
    window_tick: int
    owner_token: str
    hypothesis_token: str
    claim_token: str
    causal_hypothesis_token: str
    status: ScientificHypothesisStatus
    predicted_outcome: ExperimentOutcomeClass | str
    confidence_milli: int
    condition_count: int
    condition_pairs: tuple[tuple[ScientificHypothesisConditionSlot, str], ...]
    support_count: int
    contradiction_count: int
    revision_count: int
    source_kind: ScientificHypothesisSourceKind
    active: bool
    created_tick: int
    coverage: ScientificHypothesisCoverage

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        for name in ("window_index", "window_tick"):
            object.__setattr__(self, name, _count(getattr(self, name)))
        object.__setattr__(self, "owner_token", _token(self.owner_token))
        object.__setattr__(self, "hypothesis_token", _token(self.hypothesis_token))
        object.__setattr__(self, "claim_token", _token(self.claim_token))
        object.__setattr__(
            self, "causal_hypothesis_token", _token(self.causal_hypothesis_token)
        )
        object.__setattr__(
            self, "status", _enum(self.status, ScientificHypothesisStatus)
        )
        object.__setattr__(self, "predicted_outcome", _outcome(self.predicted_outcome))
        object.__setattr__(
            self, "confidence_milli", _share(self.confidence_milli)
        )
        pairs = _condition_pairs(self.condition_pairs)
        object.__setattr__(self, "condition_pairs", pairs)
        if _count(self.condition_count) != len(pairs):
            raise ScientificHypothesesError(
                "scientific_hypotheses_invalid_condition"
            )
        for name in ("support_count", "contradiction_count", "revision_count"):
            object.__setattr__(self, name, _count(getattr(self, name)))
        object.__setattr__(
            self, "source_kind", _enum(self.source_kind, ScientificHypothesisSourceKind)
        )
        object.__setattr__(self, "active", _flag(self.active))
        object.__setattr__(self, "created_tick", _count(self.created_tick))
        object.__setattr__(
            self, "coverage", _enum(self.coverage, ScientificHypothesisCoverage)
        )


@dataclass(frozen=True, slots=True)
class ScientificRevisionRow:
    """One append-only revision row in the owner hypothesis layer."""

    window_index: int
    window_tick: int
    hypothesis_token: str
    revision_index: int
    revision_tick: int
    reason: ScientificHypothesisRevisionReason
    claim_token: str
    predicted_outcome: ExperimentOutcomeClass | str
    condition_pairs: tuple[tuple[ScientificHypothesisConditionSlot, str], ...]
    confidence_milli: int
    coverage: ScientificHypothesisCoverage

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        for name in (
            "window_index",
            "window_tick",
            "revision_index",
            "revision_tick",
        ):
            object.__setattr__(self, name, _count(getattr(self, name)))
        object.__setattr__(self, "hypothesis_token", _token(self.hypothesis_token))
        object.__setattr__(
            self,
            "reason",
            _enum(self.reason, ScientificHypothesisRevisionReason),
        )
        object.__setattr__(self, "claim_token", _token(self.claim_token))
        object.__setattr__(self, "predicted_outcome", _outcome(self.predicted_outcome))
        object.__setattr__(
            self, "condition_pairs", _condition_pairs(self.condition_pairs)
        )
        object.__setattr__(
            self, "confidence_milli", _share(self.confidence_milli)
        )
        object.__setattr__(
            self, "coverage", _enum(self.coverage, ScientificHypothesisCoverage)
        )


@dataclass(frozen=True, slots=True)
class ScientificTrialRow:
    """Per-hypothesis trial counts in the analytical summary layer."""

    window_index: int
    window_tick: int
    hypothesis_token: str
    trial_count: int
    matched_count: int
    mismatched_count: int
    inconclusive_count: int
    last_trial_tick: int
    coverage: ScientificHypothesisCoverage
    deliberate_count: int = 0
    accidental_count: int = 0

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        for name in (
            "window_index",
            "window_tick",
            "trial_count",
            "matched_count",
            "mismatched_count",
            "inconclusive_count",
            "last_trial_tick",
            "deliberate_count",
            "accidental_count",
        ):
            object.__setattr__(self, name, _count(getattr(self, name)))
        object.__setattr__(self, "hypothesis_token", _token(self.hypothesis_token))
        if (
            self.matched_count + self.mismatched_count + self.inconclusive_count
            != self.trial_count
        ):
            raise ScientificHypothesesError("scientific_hypotheses_invalid_trial")
        if self.deliberate_count + self.accidental_count > self.trial_count:
            raise ScientificHypothesesError("scientific_hypotheses_invalid_trial")
        object.__setattr__(
            self, "coverage", _enum(self.coverage, ScientificHypothesisCoverage)
        )


@dataclass(frozen=True, slots=True)
class ScientificSourceRow:
    """Hypothesis counts grouped by descriptive source kind."""

    window_index: int
    window_tick: int
    source_kind: ScientificHypothesisSourceKind
    hypothesis_count: int
    adopted_count: int
    coverage: ScientificHypothesisCoverage

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        for name in ("window_index", "window_tick", "hypothesis_count", "adopted_count"):  # noqa: E501
            object.__setattr__(self, name, _count(getattr(self, name)))
        object.__setattr__(
            self, "source_kind", _enum(self.source_kind, ScientificHypothesisSourceKind)
        )
        if self.adopted_count > self.hypothesis_count:
            raise ScientificHypothesesError("scientific_hypotheses_invalid_hypothesis")
        object.__setattr__(
            self, "coverage", _enum(self.coverage, ScientificHypothesisCoverage)
        )


@dataclass(frozen=True, slots=True)
class ScientificOutcomeRow:
    """Prediction-outcome distribution for one closed outcome class."""

    window_index: int
    window_tick: int
    outcome_class: ExperimentOutcomeClass
    trial_count: int
    matched_count: int
    mismatched_count: int
    share_milli: int
    coverage: ScientificHypothesisCoverage
    availability: ScientificHypothesisAvailability

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        for name in (
            "window_index",
            "window_tick",
            "trial_count",
            "matched_count",
            "mismatched_count",
        ):
            object.__setattr__(self, name, _count(getattr(self, name)))
        object.__setattr__(
            self, "outcome_class", _enum(self.outcome_class, ExperimentOutcomeClass)
        )
        if self.matched_count + self.mismatched_count > self.trial_count:
            raise ScientificHypothesesError("scientific_hypotheses_invalid_trial")
        object.__setattr__(self, "share_milli", _share(self.share_milli))
        object.__setattr__(
            self, "coverage", _enum(self.coverage, ScientificHypothesisCoverage)
        )
        object.__setattr__(
            self,
            "availability",
            _enum(self.availability, ScientificHypothesisAvailability),
        )


@dataclass(frozen=True, slots=True)
class ScientificCoverageRow:
    """Bounded window totals and explicit coverage or availability state."""

    window_index: int
    window_tick: int
    window_count: int
    event_count: int
    owner_count: int
    hypothesis_count: int
    condition_count: int
    revision_count: int
    trial_count: int
    truncated: bool
    coverage: ScientificHypothesisCoverage
    availability: ScientificHypothesisAvailability

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        for name in (
            "window_index",
            "window_tick",
            "window_count",
            "event_count",
            "owner_count",
            "hypothesis_count",
            "condition_count",
            "revision_count",
            "trial_count",
        ):
            object.__setattr__(self, name, _count(getattr(self, name)))
        object.__setattr__(self, "truncated", _flag(self.truncated))
        object.__setattr__(
            self, "coverage", _enum(self.coverage, ScientificHypothesisCoverage)
        )
        object.__setattr__(
            self,
            "availability",
            _enum(self.availability, ScientificHypothesisAvailability),
        )
