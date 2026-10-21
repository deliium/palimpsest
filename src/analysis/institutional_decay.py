"""Detached institutional-decay evidence, windows, and lifecycle classification.

Rows are owner-scoped and derived from exported decay samples plus optional
objective context after a completed run. This module never feeds live cognition
and never creates an objective institution entity.

The lifecycle thresholds below are descriptive research hypotheses, not world
rules. Missing evidence yields unknown/partial/right-censored availability, not
a fabricated zero or a scripted collapse.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "INSTITUTION_LIFECYCLE_POLICY_VERSION",
    "InstitutionContextEvidenceRow",
    "InstitutionLifecycleResult",
    "InstitutionLifecycleState",
    "InstitutionTemporalRow",
    "InstitutionWindowRow",
    "compute_institutional_decay",
    "institution_decay_rows_from_ledgers",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.institutional_decay")

INSTITUTION_LIFECYCLE_POLICY_VERSION: Final[str] = "institutional-lifecycle.v1"
_WINDOW_TICKS: Final[int] = 4
_STRONG: Final[float] = 0.50
_LOW: Final[float] = 0.10
_RENEWAL: Final[float] = 0.30
_WEAKENING_DELTA: Final[float] = 0.10


class InstitutionDecayAnalysisError(ValueError):
    """Fail-closed analysis error with code-only messages."""


class InstitutionDecayAvailability(StrEnum):
    """Analysis-local mirror of the subjective availability vocabulary."""

    OBSERVED = "observed"
    UNKNOWN = "unknown"
    DISABLED = "disabled"
    PARTIAL = "partial"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True, slots=True)
class InstitutionKnowledgeAssessment:
    transition_id: str
    before_entry_ids: tuple[str, ...]
    retained_entry_ids: tuple[str, ...]


class InstitutionLifecycleState(StrEnum):
    EMERGING = "emerging"
    STABLE = "stable"
    WEAKENING = "weakening"
    COLLAPSED = "collapsed"
    UNKNOWN = "unknown"
    RIGHT_CENSORED = "right_censored"


def _nonneg(field_name: str, value: object) -> int:
    return require_exact_nonneg_int(field_name, value)


def _unit(field_name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InstitutionDecayAnalysisError(f"invalid:{field_name}")
    number = float(value)
    if not 0.0 <= number <= 1.0:
        raise InstitutionDecayAnalysisError(f"invalid:{field_name}")
    return round(number, 6)


def _sequence(field_name: str, value: object) -> tuple[object, ...]:
    if isinstance(value, (str, bytes, set, frozenset)) or not isinstance(
        value, Sequence
    ):
        raise InstitutionDecayAnalysisError(f"invalid:{field_name}")
    return tuple(value)


@dataclass(frozen=True, slots=True)
class InstitutionTemporalRow:
    owner_id: str
    local_pattern_id: str
    observation_tick: int
    source_first_tick: int
    source_last_tick: int
    role_recognition: float
    procedure_recurrence: float
    social_expectation: float
    legitimacy_belief: float
    succession_observed: float
    generational_continuity: float
    recognized: bool
    observed_cohort: tuple[str, ...] = ()
    supporters: tuple[tuple[str, str], ...] = ()
    participant_actions: tuple[tuple[str, str], ...] = ()
    performed_procedure_keys: tuple[str, ...] = ()
    succession_transitions: tuple[str, ...] = ()
    completed_transitions: tuple[str, ...] = ()
    knowledge_assessments: tuple[InstitutionKnowledgeAssessment, ...] = ()
    structural_components: tuple[str, ...] = ()
    context_key: str | None = None
    office_id: str | None = None
    covered: bool = True
    pruned: bool = False
    availability: InstitutionDecayAvailability = InstitutionDecayAvailability.OBSERVED

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "owner_id",
            require_stable_id("owner_id", self.owner_id),
        )
        object.__setattr__(
            self,
            "local_pattern_id",
            require_stable_id("local_pattern_id", self.local_pattern_id),
        )
        for name in ("observation_tick", "source_first_tick", "source_last_tick"):
            object.__setattr__(self, name, _nonneg(name, getattr(self, name)))
        if self.source_last_tick < self.source_first_tick:
            raise InstitutionDecayAnalysisError("invalid:source_interval")
        if self.source_last_tick > self.observation_tick:
            raise InstitutionDecayAnalysisError("invalid:future_source")
        for name in (
            "role_recognition",
            "procedure_recurrence",
            "social_expectation",
            "legitimacy_belief",
            "succession_observed",
            "generational_continuity",
        ):
            object.__setattr__(self, name, _unit(name, getattr(self, name)))
        if type(self.recognized) is not bool:
            raise InstitutionDecayAnalysisError("invalid:recognized")
        cohort = _sequence("observed_cohort", self.observed_cohort)
        checked_cohort: list[str] = []
        for item in cohort:
            if not isinstance(item, str) or not item:
                raise InstitutionDecayAnalysisError("invalid:observed_cohort")
            if item not in checked_cohort:
                checked_cohort.append(item)
        object.__setattr__(
            self,
            "observed_cohort",
            tuple(sorted(checked_cohort)),
        )
        for name in (
            "supporters",
            "participant_actions",
            "performed_procedure_keys",
            "succession_transitions",
            "completed_transitions",
            "knowledge_assessments",
            "structural_components",
        ):
            object.__setattr__(self, name, _sequence(name, getattr(self, name)))
        if type(self.availability) is not InstitutionDecayAvailability:
            raise InstitutionDecayAnalysisError("invalid:availability")


@dataclass(frozen=True, slots=True)
class InstitutionWindowRow:
    owner_id: str
    local_pattern_id: str
    start_tick: int
    end_tick: int
    complete: bool
    covered_updates: int
    cohort: tuple[str, ...]
    support_numerator: int
    participation_numerator: int
    procedure_numerator: int
    succession_eligible: int
    succession_completed: int
    knowledge_before: int
    knowledge_retained: int
    support_ratio: float | None = None
    participation_ratio: float | None = None
    procedure_ratio: float | None = None
    legitimacy_strength: float | None = None
    succession_ratio: float | None = None
    knowledge_ratio: float | None = None
    support_availability: InstitutionDecayAvailability = (
        InstitutionDecayAvailability.UNKNOWN
    )
    participation_availability: InstitutionDecayAvailability = (
        InstitutionDecayAvailability.UNKNOWN
    )
    procedure_availability: InstitutionDecayAvailability = (
        InstitutionDecayAvailability.UNKNOWN
    )
    succession_availability: InstitutionDecayAvailability = (
        InstitutionDecayAvailability.UNKNOWN
    )
    knowledge_availability: InstitutionDecayAvailability = (
        InstitutionDecayAvailability.UNKNOWN
    )
    pruned: bool = False


@dataclass(frozen=True, slots=True)
class InstitutionContextEvidenceRow:
    owner_id: str
    local_pattern_id: str
    kind: str
    start_tick: int
    end_tick: int
    native_ref: str
    observed: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "owner_id",
            require_stable_id("owner_id", self.owner_id),
        )
        object.__setattr__(
            self,
            "local_pattern_id",
            require_stable_id("local_pattern_id", self.local_pattern_id),
        )
        object.__setattr__(self, "kind", require_stable_id("kind", self.kind))
        object.__setattr__(self, "start_tick", _nonneg("start_tick", self.start_tick))
        object.__setattr__(self, "end_tick", _nonneg("end_tick", self.end_tick))
        if self.end_tick < self.start_tick:
            raise InstitutionDecayAnalysisError("invalid:context_interval")
        object.__setattr__(
            self, "native_ref", require_stable_id("native_ref", self.native_ref)
        )


@dataclass(frozen=True, slots=True)
class InstitutionLifecycleResult:
    policy_version: str
    as_of_tick: int
    states: tuple[tuple[tuple[str, str], str], ...]
    windows: tuple[InstitutionWindowRow, ...]
    context: tuple[InstitutionContextEvidenceRow, ...]
    mechanism_tags: tuple[tuple[str, str, str], ...] = ()
    collapsed_intervals: tuple[tuple[str, str, int, int], ...] = ()
    excluded_rows: int = 0
    pruned_rows: int = 0

    @property
    def state_for(self) -> dict[tuple[str, str], str]:
        return dict(self.states)

    def was_collapsed_before(
        self, owner_id: str, local_pattern_id: str, tick: int
    ) -> bool:
        return any(
            owner == owner_id
            and pattern == local_pattern_id
            and end_tick <= tick
            for owner, pattern, _start_tick, end_tick in self.collapsed_intervals
        )


def _row_owner_key(row: InstitutionTemporalRow) -> tuple[str, str, int]:
    return (row.owner_id, row.local_pattern_id, row.observation_tick)


def _validated_rows(
    rows: object, *, as_of_tick: int
) -> tuple[InstitutionTemporalRow, ...]:
    if isinstance(rows, (str, bytes, set, frozenset)) or not isinstance(rows, Sequence):
        raise InstitutionDecayAnalysisError("invalid:rows")
    checked: list[InstitutionTemporalRow] = []
    seen: dict[tuple[str, str, int], InstitutionTemporalRow] = {}
    for item in rows:
        if type(item) is not InstitutionTemporalRow:
            raise InstitutionDecayAnalysisError("invalid:row_type")
        if item.observation_tick > as_of_tick:
            raise InstitutionDecayAnalysisError("future_evidence")
        key = _row_owner_key(item)
        previous = seen.get(key)
        if previous is not None and previous != item:
            raise InstitutionDecayAnalysisError("conflicting_duplicate")
        if previous is None:
            seen[key] = item
            checked.append(item)
    checked.sort(key=_row_owner_key)
    return tuple(checked)


def _window_for(
    rows: Sequence[InstitutionTemporalRow], *, start: int, end: int
) -> InstitutionWindowRow:
    first = rows[0]
    ticks = {row.observation_tick for row in rows}
    complete = (
        ticks == set(range(start, end + 1))
        and len(rows) == _WINDOW_TICKS
        and all(row.covered for row in rows)
        and not any(row.pruned for row in rows)
        and all(
            row.availability is InstitutionDecayAvailability.OBSERVED
            for row in rows
        )
    )
    covered_updates = len(rows)
    cohort_sets = [set(row.observed_cohort) for row in rows]
    cohort = set.intersection(*cohort_sets) if cohort_sets else set()
    supporters: set[str] = set()
    for row in rows:
        for actor, _root in row.supporters:
            if actor in cohort:
                supporters.add(actor)
    participants: set[str] = set()
    seen_actions: set[tuple[str, str]] = set()
    for row in rows:
        for actor, action_key in row.participant_actions:
            pair = (actor, action_key)
            if actor in cohort and pair not in seen_actions:
                seen_actions.add(pair)
                participants.add(actor)
    procedure_updates = sum(1 for row in rows if row.performed_procedure_keys)
    eligible: set[str] = set()
    completed: set[str] = set()
    knowledge_pairs: set[tuple[str, str]] = set()
    before_pairs: set[tuple[str, str]] = set()
    for row in rows:
        eligible.update(row.succession_transitions)
        completed.update(row.completed_transitions)
        for assessment in row.knowledge_assessments:
            for entry in assessment.before_entry_ids:
                before_pairs.add((assessment.transition_id, entry))
            for entry in assessment.retained_entry_ids:
                if entry in set(assessment.before_entry_ids):
                    knowledge_pairs.add((assessment.transition_id, entry))
    support_available = bool(cohort)
    succession_available = bool(eligible)
    knowledge_available = bool(before_pairs)
    return InstitutionWindowRow(
        owner_id=first.owner_id,
        local_pattern_id=first.local_pattern_id,
        start_tick=start,
        end_tick=end,
        complete=complete,
        covered_updates=covered_updates,
        cohort=tuple(sorted(cohort)),
        support_numerator=len(supporters),
        participation_numerator=len(participants),
        procedure_numerator=procedure_updates,
        succession_eligible=len(eligible),
        succession_completed=len(completed),
        knowledge_before=len(before_pairs),
        knowledge_retained=len(knowledge_pairs),
        support_ratio=(len(supporters) / len(cohort) if support_available else None),
        participation_ratio=(
            len(participants) / len(cohort) if support_available else None
        ),
        procedure_ratio=procedure_updates / _WINDOW_TICKS,
        legitimacy_strength=max(row.legitimacy_belief for row in rows),
        succession_ratio=(
            len(completed) / len(eligible) if succession_available else None
        ),
        knowledge_ratio=(
            len(knowledge_pairs) / len(before_pairs) if knowledge_available else None
        ),
        support_availability=(
            InstitutionDecayAvailability.OBSERVED
            if support_available
            else InstitutionDecayAvailability.UNKNOWN
        ),
        participation_availability=(
            InstitutionDecayAvailability.OBSERVED
            if support_available
            else InstitutionDecayAvailability.UNKNOWN
        ),
        procedure_availability=(
            InstitutionDecayAvailability.OBSERVED
            if rows[0].availability is InstitutionDecayAvailability.OBSERVED
            else InstitutionDecayAvailability.PARTIAL
        ),
        succession_availability=(
            InstitutionDecayAvailability.OBSERVED
            if succession_available
            else InstitutionDecayAvailability.NOT_APPLICABLE
        ),
        knowledge_availability=(
            InstitutionDecayAvailability.OBSERVED
            if knowledge_available
            else InstitutionDecayAvailability.NOT_APPLICABLE
        ),
        pruned=any(row.pruned for row in rows),
    )


def _core_ratios(window: InstitutionWindowRow) -> tuple[float | None, ...]:
    return (
        window.support_ratio,
        window.participation_ratio,
        window.procedure_ratio,
    )


def _is_stable_window(window: InstitutionWindowRow) -> bool:
    core = [value for value in _core_ratios(window) if value is not None]
    if len([value for value in core if value >= _STRONG]) < 2:
        return False
    return window.participation_numerator > 0 or window.procedure_numerator >= 2


def _is_low_window(window: InstitutionWindowRow) -> bool:
    core = [value for value in _core_ratios(window) if value is not None]
    if not core or max(core) > _RENEWAL:
        return False
    low = sum(1 for value in core if value <= _LOW)
    practice_low = (
        window.procedure_ratio is not None and window.procedure_ratio <= _LOW
    )
    return low >= 2 and practice_low and window.procedure_numerator == 0


def _classify(windows: Sequence[InstitutionWindowRow]) -> InstitutionLifecycleState:
    complete = [window for window in windows if window.complete]
    if not complete:
        return InstitutionLifecycleState.UNKNOWN
    latest = complete[-1]
    core = [value for value in _core_ratios(latest) if value is not None]
    if not core:
        return InstitutionLifecycleState.UNKNOWN
    prior = complete[-2] if len(complete) >= 2 else None
    earlier = complete[:-2]
    prior_stable_history = any(_is_stable_window(window) for window in earlier)
    if prior is not None and _is_stable_window(prior):
        prior_stable_history = True
    if prior is not None and prior_stable_history and _is_low_window(latest) and (
        _is_low_window(prior)
    ):
        return InstitutionLifecycleState.COLLAPSED
    if prior is not None and prior_stable_history:
        prior_core = [value for value in _core_ratios(prior) if value is not None]
        legitimacy_declined = (
            prior.legitimacy_strength is not None
            and latest.legitimacy_strength is not None
            and prior.legitimacy_strength - latest.legitimacy_strength
            >= _WEAKENING_DELTA
        )
        comparable = [
            (current, previous)
            for current, previous in zip(core, prior_core, strict=False)
            if current is not None and previous is not None
        ]
        if legitimacy_declined or any(
            previous - current >= _WEAKENING_DELTA for current, previous in comparable
        ):
            return InstitutionLifecycleState.WEAKENING
    if _is_stable_window(latest):
        if prior is None or _is_stable_window(prior):
            return InstitutionLifecycleState.STABLE
        return InstitutionLifecycleState.EMERGING
    return InstitutionLifecycleState.EMERGING


def _mechanism_tags(
    owner_id: str,
    pattern_id: str,
    windows: Sequence[InstitutionWindowRow],
    context_rows: Sequence[InstitutionContextEvidenceRow],
) -> tuple[tuple[str, str, str], ...]:
    tags: list[tuple[str, str, str]] = []
    for context in context_rows:
        if context.owner_id != owner_id or context.local_pattern_id != pattern_id:
            continue
        tags.append((pattern_id, context.kind, context.native_ref))
    return tuple(sorted(set(tags)))


def compute_institutional_decay(
    rows: object,
    *,
    as_of_tick: int,
    context_rows: Iterable[InstitutionContextEvidenceRow] = (),
) -> InstitutionLifecycleResult:
    """Classify lifecycle states from raw temporal rows. Pure and detached."""
    if type(as_of_tick) is not int or as_of_tick < 0:
        raise InstitutionDecayAnalysisError("invalid:as_of_tick")
    checked = _validated_rows(rows, as_of_tick=as_of_tick)
    contexts = tuple(context_rows)
    for context in contexts:
        if type(context) is not InstitutionContextEvidenceRow:
            raise InstitutionDecayAnalysisError("invalid:context_row")
        if context.end_tick > as_of_tick:
            raise InstitutionDecayAnalysisError("future_evidence")
    grouped: dict[tuple[str, str], list[InstitutionTemporalRow]] = {}
    for row in checked:
        grouped.setdefault((row.owner_id, row.local_pattern_id), []).append(row)
    states: list[tuple[tuple[str, str], str]] = []
    windows: list[InstitutionWindowRow] = []
    all_tags: list[tuple[str, str, str]] = []
    collapsed: set[tuple[str, str, int, int]] = set()
    for (owner_value, pattern_id), pattern_rows in sorted(grouped.items()):
        pattern_rows.sort(key=lambda item: item.observation_tick)
        pattern_windows: list[InstitutionWindowRow] = []
        start = pattern_rows[0].observation_tick
        while start + _WINDOW_TICKS - 1 <= as_of_tick:
            chunks = [
                row
                for row in pattern_rows
                if start <= row.observation_tick <= start + _WINDOW_TICKS - 1
            ]
            if chunks:
                pattern_windows.append(
                    _window_for(
                        chunks,
                        start=start,
                        end=start + _WINDOW_TICKS - 1,
                    )
                )
            start += _WINDOW_TICKS
        state = _classify(pattern_windows)
        for index in range(2, len(pattern_windows) + 1):
            prefix = pattern_windows[:index]
            if _classify(prefix) is InstitutionLifecycleState.COLLAPSED:
                collapsed.add(
                    (
                        owner_value,
                        pattern_id,
                        prefix[-2].start_tick,
                        prefix[-1].end_tick,
                    )
                )
        states.append(((owner_value, pattern_id), state.value))
        windows.extend(pattern_windows)
        all_tags.extend(
            _mechanism_tags(
                pattern_rows[0].owner_id, pattern_id, pattern_windows, contexts
            )
        )
    _LOG.debug(
        "institutional_decay_analysis rows=%s patterns=%s windows=%s",
        len(checked),
        len(grouped),
        len(windows),
    )
    return InstitutionLifecycleResult(
        policy_version=INSTITUTION_LIFECYCLE_POLICY_VERSION,
        as_of_tick=as_of_tick,
        states=tuple(states),
        windows=tuple(windows),
        context=contexts,
        mechanism_tags=tuple(sorted(set(all_tags))),
        collapsed_intervals=tuple(sorted(collapsed)),
        excluded_rows=0,
        pruned_rows=sum(1 for row in checked if row.pruned),
    )


def institution_decay_rows_from_ledgers(
    ledgers: Sequence[object],
) -> tuple[InstitutionTemporalRow, ...]:
    """Project exported decay ledgers into detached temporal rows."""
    rows: list[InstitutionTemporalRow] = []
    for ledger in ledgers:
        raw_owner = getattr(ledger, "owner_id", None)
        owner_value = getattr(raw_owner, "value", None)
        if not isinstance(owner_value, str) or not owner_value:
            raise InstitutionDecayAnalysisError("invalid:ledger_owner")
        bindings = {
            binding.local_pattern_id: binding
            for binding in getattr(ledger, "bindings", ())
        }
        records = {
            record.local_pattern_id: record for record in getattr(ledger, "records", ())
        }
        for sample in getattr(ledger, "samples", ()):
            binding = bindings.get(getattr(sample, "local_pattern_id", None))
            if binding is None:
                raise InstitutionDecayAnalysisError("invalid:sample_binding")
            record = records.get(binding.local_pattern_id)
            evidence = sample.evidence
            rows.append(
                InstitutionTemporalRow(
                    owner_id=owner_value,
                    local_pattern_id=binding.local_pattern_id,
                    observation_tick=sample.observation_tick,
                    source_first_tick=sample.source_first_tick,
                    source_last_tick=sample.source_last_tick,
                    role_recognition=sample.role_recognition,
                    procedure_recurrence=sample.procedure_recurrence,
                    social_expectation=sample.social_expectation,
                    legitimacy_belief=sample.legitimacy_belief,
                    succession_observed=sample.succession_observed,
                    generational_continuity=sample.generational_continuity,
                    recognized=sample.recognized,
                    observed_cohort=tuple(
                        agent.value for agent in evidence.observed_cohort
                    ),
                    supporters=tuple(
                        (agent.value, root) for agent, root in evidence.supporters
                    ),
                    participant_actions=tuple(
                        (agent.value, key)
                        for agent, key in evidence.participant_actions
                    ),
                    performed_procedure_keys=evidence.performed_procedure_keys,
                    succession_transitions=evidence.succession_transitions,
                    completed_transitions=evidence.completed_transitions,
                    knowledge_assessments=tuple(
                        InstitutionKnowledgeAssessment(
                            transition_id=item.transition_id,
                            before_entry_ids=item.before_entry_ids,
                            retained_entry_ids=item.retained_entry_ids,
                        )
                        for item in evidence.knowledge_assessments
                    ),
                    structural_components=sample.structural_components,
                    context_key=sample.context_key,
                    office_id=sample.office_id,
                    covered=sample.covered,
                    pruned=(
                        record is not None
                        and record.sample_pruned_through_tick is not None
                        and sample.observation_tick <= record.sample_pruned_through_tick
                    ),
                )
            )
    rows.sort(
        key=lambda row: (row.owner_id, row.local_pattern_id, row.observation_tick)
    )
    return tuple(rows)
