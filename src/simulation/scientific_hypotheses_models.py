"""Canonical sibling document for completed-run scientific hypotheses."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

from world.identifiers import require_stable_id

__all__ = [
    "MAX_SCIENTIFIC_HYPOTHESES_SNAPSHOT_BYTES",
    "MAX_SCIENTIFIC_HYPOTHESES_WINDOW_INDEX",
    "MAX_SCIENTIFIC_HYPOTHESIS_EVIDENCE_ROWS",
    "MAX_SCIENTIFIC_HYPOTHESIS_REVISION_ROWS",
    "MAX_SCIENTIFIC_HYPOTHESIS_ROWS",
    "MAX_SCIENTIFIC_HYPOTHESIS_TRIAL_ROWS",
    "SCIENTIFIC_HYPOTHESES_POLICY_VERSION",
    "SCIENTIFIC_HYPOTHESES_PUBLICATION_PREFIX",
    "SCIENTIFIC_HYPOTHESES_SNAPSHOT_VERSION",
    "ScientificHypothesesSnapshot",
    "ScientificHypothesisCoverageRecord",
    "ScientificHypothesisEvidenceRecord",
    "ScientificHypothesisRecord",
    "ScientificHypothesisRevisionRecord",
    "ScientificHypothesisSourceRecord",
    "ScientificHypothesisSummaryRecord",
    "ScientificHypothesisTestRecord",
    "empty_scientific_hypotheses_snapshot",
]

SCIENTIFIC_HYPOTHESES_SNAPSHOT_VERSION: Final[str] = "scientific-hypotheses-snapshot-v1"
SCIENTIFIC_HYPOTHESES_POLICY_VERSION: Final[str] = "scientific-hypotheses.v1"
SCIENTIFIC_HYPOTHESES_PUBLICATION_PREFIX: Final[str] = "schyp-"
MAX_SCIENTIFIC_HYPOTHESIS_ROWS: Final[int] = 4_096
MAX_SCIENTIFIC_HYPOTHESIS_EVIDENCE_ROWS: Final[int] = 4_096
MAX_SCIENTIFIC_HYPOTHESIS_REVISION_ROWS: Final[int] = 8_192
MAX_SCIENTIFIC_HYPOTHESIS_TRIAL_ROWS: Final[int] = 4_096
MAX_SCIENTIFIC_HYPOTHESES_SNAPSHOT_BYTES: Final[int] = 8_388_608
MAX_SCIENTIFIC_HYPOTHESES_WINDOW_INDEX: Final[int] = 511

_STATUSES = frozenset(
    {"provisional", "supported", "contradicted", "inconclusive", "superseded", "retired"}  # noqa: E501
)
_SOURCES = frozenset(
    {
        "self_formulated",
        "observed",
        "remembered",
        "communicated",
        "recorded",
        "unknown",
    }
)
_REASONS = frozenset(
    {
        "formulated",
        "prediction_revised",
        "condition_revised",
        "support_added",
        "contradiction_added",
        "confidence_revised",
        "source_adopted",
        "test_formulated",
        "superseded",
        "retired",
    }
)
_SLOTS = frozenset(
    {
        "location",
        "day_phase",
        "weather",
        "held_item_kind",
        "counterpart",
        "season",
        "temperature_band",
        "hazard",
        "action",
        "concept",
    }
)
_OUTCOMES = frozenset(
    {"success", "partial_success", "failure", "harm", "unexpected", "none"}
)
_COVERAGE = frozenset({"complete", "partial", "missing"})
_AVAILABILITY = frozenset({"available", "insufficient_samples", "unavailable"})


def _fail() -> ValueError:
    return ValueError("scientific_hypotheses_snapshot_invalid")


def _count(value: object) -> int:
    if isinstance(value, bool) or type(value) is not int or value < 0:
        raise _fail()
    return value


def _share(value: object) -> int:
    number = _count(value)
    if number > 1_000:
        raise _fail()
    return number


def _flag(value: object) -> bool:
    if type(value) is not bool:
        raise _fail()
    return value


def _token(value: object) -> str:
    if type(value) is not str or not value:
        raise _fail()
    return require_stable_id("token", value)


def _window(value: object) -> int:
    number = _count(value)
    if number > MAX_SCIENTIFIC_HYPOTHESES_WINDOW_INDEX:
        raise _fail()
    return number


def _enum(value: object, allowed: frozenset[str]) -> str:
    if type(value) is not str or value not in allowed:
        raise _fail()
    return value


def _conditions(
    value: object,
) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, tuple) or len(value) > 8:
        raise _fail()
    seen: set[str] = set()
    rows: list[tuple[str, str]] = []
    for item in value:
        if not isinstance(item, tuple) or len(item) != 2:
            raise _fail()
        slot = _enum(item[0], _SLOTS)
        token = _token(item[1])
        if slot in seen:
            raise _fail()
        seen.add(slot)
        rows.append((slot, token))
    return tuple(rows)


@dataclass(frozen=True, slots=True)
class ScientificHypothesisSummaryRecord:
    window_tick: int
    window_count: int
    coverage: str
    availability: str
    owner_count: int
    hypothesis_count: int
    active_count: int
    supported_count: int
    contradicted_count: int
    inconclusive_count: int
    revision_count: int
    trial_count: int
    matched_count: int
    mismatched_count: int

    def __post_init__(self) -> None:
        for name in (
            "window_tick",
            "window_count",
            "owner_count",
            "hypothesis_count",
            "active_count",
            "supported_count",
            "contradicted_count",
            "inconclusive_count",
            "revision_count",
            "trial_count",
            "matched_count",
            "mismatched_count",
        ):
            object.__setattr__(self, name, _count(getattr(self, name)))
        object.__setattr__(self, "coverage", _enum(self.coverage, _COVERAGE))
        object.__setattr__(
            self, "availability", _enum(self.availability, _AVAILABILITY)
        )


@dataclass(frozen=True, slots=True)
class ScientificHypothesisRecord:
    window_index: int
    window_tick: int
    hypothesis_token: str
    claim_token: str
    causal_hypothesis_token: str
    status: str
    predicted_outcome: str
    confidence_milli: int
    condition_count: int
    condition_pairs: tuple[tuple[str, str], ...]
    support_count: int
    contradiction_count: int
    revision_count: int
    source_kind: str
    active: bool
    created_tick: int
    coverage: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "window_index", _window(self.window_index))
        object.__setattr__(self, "window_tick", _count(self.window_tick))
        object.__setattr__(
            self, "hypothesis_token", _token(self.hypothesis_token)
        )
        object.__setattr__(self, "claim_token", _token(self.claim_token))
        object.__setattr__(
            self,
            "causal_hypothesis_token",
            _token(self.causal_hypothesis_token),
        )
        object.__setattr__(self, "status", _enum(self.status, _STATUSES))
        object.__setattr__(
            self, "predicted_outcome", _enum(self.predicted_outcome, _OUTCOMES)
        )
        object.__setattr__(
            self, "confidence_milli", _share(self.confidence_milli)
        )
        pairs = _conditions(self.condition_pairs)
        if _count(self.condition_count) != len(pairs):
            raise _fail()
        object.__setattr__(self, "condition_pairs", pairs)
        for name in ("support_count", "contradiction_count", "revision_count"):
            object.__setattr__(self, name, _count(getattr(self, name)))
        object.__setattr__(self, "source_kind", _enum(self.source_kind, _SOURCES))
        object.__setattr__(self, "active", _flag(self.active))
        object.__setattr__(self, "created_tick", _count(self.created_tick))
        object.__setattr__(self, "coverage", _enum(self.coverage, _COVERAGE))


@dataclass(frozen=True, slots=True)
class ScientificHypothesisEvidenceRecord:
    window_index: int
    window_tick: int
    hypothesis_token: str
    support_observation_count: int
    contradiction_count: int
    evidence_event_count: int
    unlinked_event_count: int
    coverage: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "window_index", _window(self.window_index))
        object.__setattr__(self, "window_tick", _count(self.window_tick))
        object.__setattr__(
            self, "hypothesis_token", _token(self.hypothesis_token)
        )
        for name in (
            "support_observation_count",
            "contradiction_count",
            "evidence_event_count",
            "unlinked_event_count",
        ):
            object.__setattr__(self, name, _count(getattr(self, name)))
        object.__setattr__(self, "coverage", _enum(self.coverage, _COVERAGE))


@dataclass(frozen=True, slots=True)
class ScientificHypothesisTestRecord:
    window_index: int
    window_tick: int
    hypothesis_token: str
    trial_count: int
    matched_count: int
    mismatched_count: int
    inconclusive_count: int
    last_trial_tick: int
    coverage: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "window_index", _window(self.window_index))
        object.__setattr__(self, "window_tick", _count(self.window_tick))
        object.__setattr__(
            self, "hypothesis_token", _token(self.hypothesis_token)
        )
        for name in (
            "trial_count",
            "matched_count",
            "mismatched_count",
            "inconclusive_count",
            "last_trial_tick",
        ):
            object.__setattr__(self, name, _count(getattr(self, name)))
        if (
            self.matched_count + self.mismatched_count + self.inconclusive_count
            != self.trial_count
        ):
            raise _fail()
        object.__setattr__(self, "coverage", _enum(self.coverage, _COVERAGE))


@dataclass(frozen=True, slots=True)
class ScientificHypothesisRevisionRecord:
    window_index: int
    window_tick: int
    hypothesis_token: str
    revision_index: int
    revision_tick: int
    reason: str
    claim_token: str
    predicted_outcome: str
    condition_pairs: tuple[tuple[str, str], ...]
    confidence_milli: int
    coverage: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "window_index", _window(self.window_index))
        for name in (
            "window_tick",
            "revision_index",
            "revision_tick",
        ):
            object.__setattr__(self, name, _count(getattr(self, name)))
        object.__setattr__(
            self, "hypothesis_token", _token(self.hypothesis_token)
        )
        object.__setattr__(self, "reason", _enum(self.reason, _REASONS))
        object.__setattr__(self, "claim_token", _token(self.claim_token))
        object.__setattr__(
            self, "predicted_outcome", _enum(self.predicted_outcome, _OUTCOMES)
        )
        object.__setattr__(
            self, "condition_pairs", _conditions(self.condition_pairs)
        )
        object.__setattr__(
            self, "confidence_milli", _share(self.confidence_milli)
        )
        object.__setattr__(self, "coverage", _enum(self.coverage, _COVERAGE))


@dataclass(frozen=True, slots=True)
class ScientificHypothesisSourceRecord:
    window_index: int
    window_tick: int
    source_kind: str
    hypothesis_count: int
    adopted_count: int
    coverage: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "window_index", _window(self.window_index))
        object.__setattr__(self, "window_tick", _count(self.window_tick))
        object.__setattr__(self, "source_kind", _enum(self.source_kind, _SOURCES))
        for name in ("hypothesis_count", "adopted_count"):
            object.__setattr__(self, name, _count(getattr(self, name)))
        if self.adopted_count > self.hypothesis_count:
            raise _fail()
        object.__setattr__(self, "coverage", _enum(self.coverage, _COVERAGE))


@dataclass(frozen=True, slots=True)
class ScientificHypothesisCoverageRecord:
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
    coverage: str
    availability: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "window_index", _window(self.window_index))
        for name in (
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
        object.__setattr__(self, "coverage", _enum(self.coverage, _COVERAGE))
        object.__setattr__(
            self, "availability", _enum(self.availability, _AVAILABILITY)
        )


@dataclass(frozen=True, slots=True)
class ScientificHypothesesSnapshot:
    snapshot_version: str
    policy_version: str
    run_id: str
    generated_from_tick: int
    summary: ScientificHypothesisSummaryRecord
    hypotheses: tuple[ScientificHypothesisRecord, ...] = ()
    evidence: tuple[ScientificHypothesisEvidenceRecord, ...] = ()
    tests: tuple[ScientificHypothesisTestRecord, ...] = ()
    revisions: tuple[ScientificHypothesisRevisionRecord, ...] = ()
    sources: tuple[ScientificHypothesisSourceRecord, ...] = ()
    coverage: tuple[ScientificHypothesisCoverageRecord, ...] = ()
    internal_digest: str = ""
    publication_id: str = field(default="")

    def __post_init__(self) -> None:
        if self.snapshot_version != SCIENTIFIC_HYPOTHESES_SNAPSHOT_VERSION:
            raise _fail()
        if self.policy_version != SCIENTIFIC_HYPOTHESES_POLICY_VERSION:
            raise _fail()
        object.__setattr__(
            self, "run_id", require_stable_id("run_id", self.run_id)
        )
        object.__setattr__(
            self, "generated_from_tick", _count(self.generated_from_tick)
        )
        if type(self.summary) is not ScientificHypothesisSummaryRecord:
            raise _fail()
        for _name, rows, cap, row_type in (
            ("hypotheses", self.hypotheses, MAX_SCIENTIFIC_HYPOTHESIS_ROWS, ScientificHypothesisRecord),  # noqa: E501
            ("evidence", self.evidence, MAX_SCIENTIFIC_HYPOTHESIS_EVIDENCE_ROWS, ScientificHypothesisEvidenceRecord),  # noqa: E501
            ("tests", self.tests, MAX_SCIENTIFIC_HYPOTHESIS_TRIAL_ROWS, ScientificHypothesisTestRecord),  # noqa: E501
            ("revisions", self.revisions, MAX_SCIENTIFIC_HYPOTHESIS_REVISION_ROWS, ScientificHypothesisRevisionRecord),  # noqa: E501
            ("sources", self.sources, MAX_SCIENTIFIC_HYPOTHESIS_ROWS, ScientificHypothesisSourceRecord),  # noqa: E501
            ("coverage", self.coverage, MAX_SCIENTIFIC_HYPOTHESIS_ROWS, ScientificHypothesisCoverageRecord),  # noqa: E501
        ):
            if not isinstance(rows, tuple) or len(rows) > cap:
                raise _fail()
            for row in rows:
                if type(row) is not row_type:
                    raise _fail()
        if self.internal_digest and not self.internal_digest.startswith("sha256:"):
            raise _fail()
        if self.publication_id and not self.publication_id.startswith(
            SCIENTIFIC_HYPOTHESES_PUBLICATION_PREFIX
        ):
            raise _fail()


def empty_scientific_hypotheses_snapshot(
    *, run_id: str
) -> ScientificHypothesesSnapshot:
    """Return the explicit empty snapshot; no fabricated rows."""

    summary = ScientificHypothesisSummaryRecord(
        window_tick=0,
        window_count=0,
        coverage="missing",
        availability="unavailable",
        owner_count=0,
        hypothesis_count=0,
        active_count=0,
        supported_count=0,
        contradicted_count=0,
        inconclusive_count=0,
        revision_count=0,
        trial_count=0,
        matched_count=0,
        mismatched_count=0,
    )
    return ScientificHypothesesSnapshot(
        snapshot_version=SCIENTIFIC_HYPOTHESES_SNAPSHOT_VERSION,
        policy_version=SCIENTIFIC_HYPOTHESES_POLICY_VERSION,
        run_id=run_id,
        generated_from_tick=0,
        summary=summary,
    )
