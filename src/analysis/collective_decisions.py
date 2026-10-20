"""Detached analysis of owner-scoped collective decisions.

Rows are harvested from exported subjective ledgers after the run. Owner-local
proposal references remain testimony; cross-owner alignment is analytical
inference over topic/action/context evidence, never a canonical electorate.
Nothing here feeds live cognition.
"""

from __future__ import annotations

import hashlib
import logging
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final

from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
)
from analysis.numerical import library_versions, quantize_float, require_finite
from analysis.specifications import MetricFamilyId, metric_specification
from world.identifiers import require_exact_nonneg_int, require_stable_id

_LOG: Final[logging.Logger] = logging.getLogger("analysis.collective_decisions")

_HEX: Final[frozenset[str]] = frozenset("0123456789abcdef")
_DIGEST_LEN: Final[int] = 16
_ALIGNMENT_FLOOR: Final[float] = 0.5


class CollectiveDecisionAnalysisError(ValueError):
    """Fail-closed analysis error; messages are codes only."""


class CollectiveCourseOutcome(StrEnum):
    """Closed analytical course classification for one owner snapshot."""

    CLAIMED = "claimed"
    ADOPTED = "adopted"
    ATTEMPTED = "attempted"
    EFFECTED = "effected"
    WITHDRAWN = "withdrawn"
    ABANDONED = "abandoned"
    EXPIRED = "expired"
    DISPUTED = "disputed"
    UNKNOWN = "unknown"


def _digest16(material: str) -> str:
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:_DIGEST_LEN]


def _require_hex(field_name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in _HEX for char in value)
    ):
        raise CollectiveDecisionAnalysisError(f"invalid_id:{field_name}")
    return value


def _require_tick(field_name: str, value: object) -> int:
    return require_exact_nonneg_int(field_name, value)


@dataclass(frozen=True, slots=True)
class CollectiveProposalRow:
    """One detached owner-local proposal revision row."""

    owner_id: str
    proposal_ref: str
    revision: int
    topic: str
    status: str
    action_token: str
    target_token: str | None
    window_first_tick: int
    window_last_tick: int
    first_tick: int
    last_tick: int
    originator_id: str | None
    evidence_count: int
    pruned_evidence_count: int
    evidence_coverage: str

    def __post_init__(self) -> None:
        require_stable_id("owner_id", self.owner_id)
        _require_hex("proposal_ref", self.proposal_ref)
        _require_tick("revision", self.revision)
        require_stable_id("topic", self.topic)
        require_stable_id("status", self.status)
        require_stable_id("action_token", self.action_token)
        _require_tick("window_first_tick", self.window_first_tick)
        _require_tick("window_last_tick", self.window_last_tick)
        _require_tick("first_tick", self.first_tick)
        _require_tick("last_tick", self.last_tick)
        _require_tick("evidence_count", self.evidence_count)
        _require_tick("pruned_evidence_count", self.pruned_evidence_count)


@dataclass(frozen=True, slots=True)
class CollectivePositionRow:
    """One detached expressed-position row."""

    owner_id: str
    actor_id: str
    proposal_ref: str
    revision: int
    stance: str
    strength: float
    channel: str
    independently_evidenced: bool
    active: bool
    first_tick: int
    last_tick: int

    def __post_init__(self) -> None:
        require_stable_id("owner_id", self.owner_id)
        require_stable_id("actor_id", self.actor_id)
        _require_hex("proposal_ref", self.proposal_ref)
        _require_tick("revision", self.revision)
        require_stable_id("stance", self.stance)
        object.__setattr__(
            self, "strength", quantize_float(require_finite(self.strength))
        )
        require_stable_id("channel", self.channel)
        _require_tick("first_tick", self.first_tick)
        _require_tick("last_tick", self.last_tick)


@dataclass(frozen=True, slots=True)
class CollectiveDelegationRow:
    """One detached one-hop delegation row."""

    owner_id: str
    delegator_id: str
    delegate_id: str
    proposal_ref: str
    revision: int
    strength: float
    active: bool
    first_tick: int
    last_tick: int
    expires_tick: int

    def __post_init__(self) -> None:
        require_stable_id("owner_id", self.owner_id)
        require_stable_id("delegator_id", self.delegator_id)
        require_stable_id("delegate_id", self.delegate_id)
        _require_hex("proposal_ref", self.proposal_ref)
        _require_tick("revision", self.revision)
        object.__setattr__(
            self, "strength", quantize_float(require_finite(self.strength))
        )
        for name in ("first_tick", "last_tick", "expires_tick"):
            _require_tick(name, getattr(self, name))


@dataclass(frozen=True, slots=True)
class CollectiveOutcomeRow:
    """One detached claimed/attempted/effected course row."""

    owner_id: str
    proposal_ref: str
    revision: int
    kind: str
    execution_status: str
    claimed: bool
    actor_id: str | None
    first_tick: int
    last_tick: int

    def __post_init__(self) -> None:
        require_stable_id("owner_id", self.owner_id)
        _require_hex("proposal_ref", self.proposal_ref)
        _require_tick("revision", self.revision)
        require_stable_id("kind", self.kind)
        require_stable_id("execution_status", self.execution_status)
        _require_tick("first_tick", self.first_tick)
        _require_tick("last_tick", self.last_tick)


@dataclass(frozen=True, slots=True)
class CollectiveComplianceRow:
    """One detached descriptive compliance opportunity row."""

    owner_id: str
    actor_id: str
    proposal_ref: str
    revision: int
    status: str
    window_first_tick: int
    window_last_tick: int
    observed_action_token: str | None
    tick: int

    def __post_init__(self) -> None:
        require_stable_id("owner_id", self.owner_id)
        require_stable_id("actor_id", self.actor_id)
        _require_hex("proposal_ref", self.proposal_ref)
        _require_tick("revision", self.revision)
        require_stable_id("status", self.status)
        for name in ("window_first_tick", "window_last_tick", "tick"):
            _require_tick(name, getattr(self, name))


@dataclass(frozen=True, slots=True)
class CollectiveInfluenceRow:
    """One detached local influence-attribution row."""

    owner_id: str
    proposal_ref: str
    revision: int
    source_act: str
    kind: str
    strength: float
    tick: int
    unavailable_reason: str | None

    def __post_init__(self) -> None:
        require_stable_id("owner_id", self.owner_id)
        _require_hex("proposal_ref", self.proposal_ref)
        _require_tick("revision", self.revision)
        require_stable_id("source_act", self.source_act)
        require_stable_id("kind", self.kind)
        object.__setattr__(
            self, "strength", quantize_float(require_finite(self.strength))
        )
        _require_tick("tick", self.tick)


@dataclass(frozen=True, slots=True)
class CollectiveDecisionSnapshot:
    """Detached rows for one owner, with explicit coverage metadata."""

    owner_id: str
    enabled: bool
    coverage: str
    first_observed_tick: int | None
    last_observed_tick: int | None
    observation_count: int
    proposals: tuple[CollectiveProposalRow, ...] = ()
    positions: tuple[CollectivePositionRow, ...] = ()
    delegations: tuple[CollectiveDelegationRow, ...] = ()
    outcomes: tuple[CollectiveOutcomeRow, ...] = ()
    compliance: tuple[CollectiveComplianceRow, ...] = ()
    influence: tuple[CollectiveInfluenceRow, ...] = ()
    pruned_proposal_count: int = 0
    pruned_evidence_count: int = 0
    pruned_position_count: int = 0
    pruned_outcome_count: int = 0

    def __post_init__(self) -> None:
        require_stable_id("owner_id", self.owner_id)
        if self.coverage not in {"complete", "partial"}:
            raise CollectiveDecisionAnalysisError("invalid_coverage")
        if self.first_observed_tick is not None:
            _require_tick("first_observed_tick", self.first_observed_tick)
        if self.last_observed_tick is not None:
            _require_tick("last_observed_tick", self.last_observed_tick)
        _require_tick("observation_count", self.observation_count)
        for name in (
            "pruned_proposal_count",
            "pruned_evidence_count",
            "pruned_position_count",
            "pruned_outcome_count",
        ):
            _require_tick(name, getattr(self, name))

    @property
    def selected_committed_count(self) -> int:
        return sum(1 for item in self.positions if item.active)


def harvest_collective_decision_snapshot(
    ledger: Any,
) -> CollectiveDecisionSnapshot:
    """Convert one exported owner ledger into detached immutable rows."""
    if type(ledger).__name__ != "CollectiveDecisionLedger":
        raise TypeError("ledger must be CollectiveDecisionLedger")
    if not hasattr(ledger, "owner_id") or not hasattr(ledger, "proposals"):
        raise TypeError("ledger must expose owner_id and proposals")
    return CollectiveDecisionSnapshot(
        owner_id=ledger.owner_id.value,
        enabled=ledger.enabled,
        coverage=ledger.coverage,
        first_observed_tick=ledger.first_observed_tick,
        last_observed_tick=ledger.last_observed_tick,
        observation_count=ledger.observation_count,
        proposals=tuple(
            CollectiveProposalRow(
                owner_id=proposal.owner_id.value,
                proposal_ref=proposal.proposal_ref,
                revision=proposal.revision,
                topic=proposal.topic.value,
                status=proposal.status.value,
                action_token=proposal.action_token,
                target_token=proposal.target_token,
                window_first_tick=proposal.window_first_tick,
                window_last_tick=proposal.window_last_tick,
                first_tick=proposal.first_tick,
                last_tick=proposal.last_tick,
                originator_id=(
                    None
                    if proposal.originator_id is None
                    else proposal.originator_id.value
                ),
                evidence_count=len(proposal.evidence),
                pruned_evidence_count=proposal.pruned_evidence_count,
                evidence_coverage=proposal.evidence_coverage,
            )
            for proposal in ledger.proposals
        ),
        positions=tuple(
            CollectivePositionRow(
                owner_id=ledger.owner_id.value,
                actor_id=position.actor_id.value,
                proposal_ref=position.proposal_ref,
                revision=position.revision,
                stance=position.stance.value,
                strength=position.strength,
                channel=position.channel.value,
                independently_evidenced=position.independently_evidenced,
                active=position.active,
                first_tick=position.first_tick,
                last_tick=position.last_tick,
            )
            for position in ledger.positions
        ),
        delegations=tuple(
            CollectiveDelegationRow(
                owner_id=ledger.owner_id.value,
                delegator_id=delegation.delegator_id.value,
                delegate_id=delegation.delegate_id.value,
                proposal_ref=delegation.proposal_ref,
                revision=delegation.revision,
                strength=delegation.strength,
                active=delegation.active,
                first_tick=delegation.first_tick,
                last_tick=delegation.last_tick,
                expires_tick=delegation.expires_tick,
            )
            for delegation in ledger.delegations
        ),
        outcomes=tuple(
            CollectiveOutcomeRow(
                owner_id=ledger.owner_id.value,
                proposal_ref=outcome.proposal_ref,
                revision=outcome.revision,
                kind=outcome.kind.value,
                execution_status=outcome.execution_status.value,
                claimed=outcome.claimed,
                actor_id=(None if outcome.actor_id is None else outcome.actor_id.value),
                first_tick=outcome.first_tick,
                last_tick=outcome.last_tick,
            )
            for outcome in ledger.outcomes
        ),
        compliance=tuple(
            CollectiveComplianceRow(
                owner_id=ledger.owner_id.value,
                actor_id=row.actor_id.value,
                proposal_ref=row.proposal_ref,
                revision=row.revision,
                status=row.status.value,
                window_first_tick=row.window_first_tick,
                window_last_tick=row.window_last_tick,
                observed_action_token=row.observed_action_token,
                tick=row.tick,
            )
            for row in ledger.compliance
        ),
        influence=tuple(
            CollectiveInfluenceRow(
                owner_id=ledger.owner_id.value,
                proposal_ref=row.proposal_ref,
                revision=row.revision,
                source_act=row.source_act.value,
                kind=row.kind.value,
                strength=row.strength,
                tick=row.tick,
                unavailable_reason=row.unavailable_reason,
            )
            for row in ledger.influence
        ),
        pruned_proposal_count=ledger.pruned_proposal_count,
        pruned_evidence_count=ledger.pruned_evidence_count,
        pruned_position_count=ledger.pruned_position_count,
        pruned_outcome_count=ledger.pruned_outcome_count,
    )


def harvest_collective_decision_rows(
    ledgers: Sequence[object],
) -> tuple[CollectiveDecisionSnapshot, ...]:
    """Harvest owner snapshots in supplied registration order."""
    snapshots: list[CollectiveDecisionSnapshot] = []
    seen: set[str] = set()
    for ledger in ledgers:
        snapshot = harvest_collective_decision_snapshot(ledger)
        if snapshot.owner_id in seen:
            raise CollectiveDecisionAnalysisError("duplicate_owner")
        seen.add(snapshot.owner_id)
        snapshots.append(snapshot)
    _LOG.info(
        "collective_decision_rows_harvested owner_count=%s proposal_count=%s "
        "position_count=%s",
        len(snapshots),
        sum(len(item.proposals) for item in snapshots),
        sum(len(item.positions) for item in snapshots),
    )
    return tuple(snapshots)


@dataclass(frozen=True, slots=True)
class AlignedCourse:
    """Analytical alignment of independently owned proposal revisions."""

    alignment_id: str
    owners: tuple[str, ...]
    topic: str
    action_token: str
    confidence: float
    overlap_first_tick: int
    overlap_last_tick: int
    ambiguous: bool

    def __post_init__(self) -> None:
        require_stable_id("alignment_id", self.alignment_id)
        if not self.owners:
            raise CollectiveDecisionAnalysisError("empty_alignment")
        for owner in self.owners:
            require_stable_id("owners", owner)
        require_stable_id("topic", self.topic)
        require_stable_id("action_token", self.action_token)
        object.__setattr__(
            self, "confidence", quantize_float(require_finite(self.confidence))
        )
        _require_tick("overlap_first_tick", self.overlap_first_tick)
        _require_tick("overlap_last_tick", self.overlap_last_tick)


def align_collective_decision_courses(
    snapshots: Sequence[CollectiveDecisionSnapshot],
) -> tuple[tuple[AlignedCourse, ...], int]:
    """Align local roles by topic/action/window evidence, never by id or label.

    Returns aligned courses plus an excluded (ambiguous/unmatched) count.
    """
    buckets: dict[tuple[str, str], list[tuple[str, CollectiveProposalRow]]] = {}
    for snapshot in snapshots:
        for proposal in snapshot.proposals:
            if proposal.status not in {"active", "superseded", "expired", "retired"}:
                continue
            key = (proposal.topic, proposal.action_token)
            buckets.setdefault(key, []).append((snapshot.owner_id, proposal))
    aligned: list[AlignedCourse] = []
    excluded = 0
    for (topic, action), rows in sorted(buckets.items()):
        by_owner: dict[str, list[CollectiveProposalRow]] = {}
        for owner, proposal in rows:
            by_owner.setdefault(owner, []).append(proposal)
        if any(len(items) > 1 for items in by_owner.values()):
            excluded += 1
            continue
        if len(by_owner) < 2:
            continue
        proposals = [items[0] for items in by_owner.values()]
        overlap_first = max(item.window_first_tick for item in proposals)
        overlap_last = min(item.window_last_tick for item in proposals)
        if overlap_last < overlap_first:
            excluded += 1
            continue
        confidence = min(1.0, 0.5 + 0.1 * (len(proposals) - 1))
        if confidence < _ALIGNMENT_FLOOR:
            excluded += 1
            continue
        aligned.append(
            AlignedCourse(
                alignment_id=_digest16(
                    "alignment|"
                    + topic
                    + "|"
                    + action
                    + "|"
                    + "|".join(sorted(by_owner))
                ),
                owners=tuple(sorted(by_owner)),
                topic=topic,
                action_token=action,
                confidence=confidence,
                overlap_first_tick=overlap_first,
                overlap_last_tick=overlap_last,
                ambiguous=False,
            )
        )
    _LOG.debug(
        "collective_decision_alignment aligned=%s excluded=%s", len(aligned), excluded
    )
    return tuple(aligned), excluded


def _coverage(observed: int, expected: int) -> MetricCoverage:
    return MetricCoverage(
        observed=observed,
        expected=expected,
        ratio=(
            None
            if expected == 0
            else quantize_float(require_finite(observed / expected))
        ),
    )


def compute_collective_decision_process(
    snapshots: Sequence[CollectiveDecisionSnapshot],
    *,
    run_id: str,
    input_revision: str,
    tick: int = 0,
) -> MetricDocument:
    """Measure expressed processes; exposure is not influence."""
    run_id = require_stable_id("run_id", run_id)
    input_revision = require_stable_id("input_revision", input_revision)
    tick = require_exact_nonneg_int("tick", tick)
    spec = metric_specification(MetricFamilyId.COLLECTIVE_DECISION_PROCESS)
    enabled = tuple(item for item in snapshots if item.enabled)
    positions = [row for snapshot in enabled for row in snapshot.positions]
    influence = [row for snapshot in enabled for row in snapshot.influence]
    outcomes = [row for snapshot in enabled for row in snapshot.outcomes]
    projects = [row for snapshot in enabled for row in snapshot.proposals]
    partial = any(item.coverage == "partial" for item in enabled)
    availability = (
        MetricAvailability.ABSENT
        if not enabled
        else MetricAvailability.PARTIAL
        if partial
        else MetricAvailability.PRESENT
    )
    values = {
        "proposal_count": len(projects),
        "revision_count": sum(1 for item in projects if item.revision > 0),
        "direct_position_count": sum(
            1 for item in positions if item.channel == "observed"
        ),
        "reported_position_count": sum(
            1 for item in positions if item.channel in {"communicated", "remembered"}
        ),
        "withdrawal_count": sum(1 for item in positions if not item.active),
        "delegation_count": sum(len(item.delegations) for item in enabled),
        "coordination_count": sum(1 for item in outcomes if item.claimed),
        "preference_changed_count": sum(
            1 for item in influence if item.kind == "preference_changed"
        ),
        "final_command_changed_count": sum(
            1 for item in influence if item.kind == "final_command_changed"
        ),
        "executed_influence_count": sum(
            1 for item in influence if item.kind == "executed"
        ),
        "unavailable_attribution_count": sum(
            1 for item in influence if item.kind == "unavailable"
        ),
        "enabled_owner_count": len(enabled),
        "partial_coverage": partial,
        "as_of_tick": tick,
    }
    assert set(values) == set(spec.value_keys)
    return MetricDocument(
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        metric_family=spec.family_id.value,
        algorithm_version=spec.algorithm_version,
        library_versions=library_versions(),
        run_id=run_id,
        input_revision=input_revision,
        evidence_stages=frozenset(spec.evidence_inputs),
        population=spec.population,
        denominator=spec.denominator,
        coverage=_coverage(len(positions), len(positions)),
        availability=availability,
        values=values,
        provenance=MetricProvenance(
            source_kind="collective_decision_process",
            source_ids=(),
            notes_code="ok"
            if availability is not MetricAvailability.ABSENT
            else "empty",
        ),
    )


def compute_collective_decision_outcomes(
    snapshots: Sequence[CollectiveDecisionSnapshot],
    *,
    run_id: str,
    input_revision: str,
    tick: int = 0,
    effects: Sequence[CollectiveEffectRow] = (),
) -> MetricDocument:
    """Measure claimed/attempted/observed courses with explicit coverage."""
    run_id = require_stable_id("run_id", run_id)
    input_revision = require_stable_id("input_revision", input_revision)
    tick = require_exact_nonneg_int("tick", tick)
    spec = metric_specification(MetricFamilyId.COLLECTIVE_DECISION_OUTCOMES)
    enabled = tuple(item for item in snapshots if item.enabled)
    outcomes = [row for snapshot in enabled for row in snapshot.outcomes]
    compliance = [row for snapshot in enabled for row in snapshot.compliance]
    kinds: dict[str, int] = defaultdict(int)
    for outcome_row in outcomes:
        kinds[outcome_row.kind] += 1
    statuses: dict[str, int] = defaultdict(int)
    censored = 0
    for compliance_row in compliance:
        statuses[compliance_row.status] += 1
        window_open = (
            compliance_row.window_last_tick >= (tick if tick else compliance_row.tick)
            and compliance_row.status == "unknown"
        )
        if window_open:
            censored += 1
    effect_matches = match_collective_effects(enabled, effects)
    matched = statuses.get("matched", 0)
    contrary = statuses.get("contrary", 0)
    partial = any(item.coverage == "partial" for item in enabled)
    availability = (
        MetricAvailability.ABSENT
        if not enabled or (not outcomes and not compliance)
        else MetricAvailability.PARTIAL
        if partial
        else MetricAvailability.PRESENT
    )
    values = {
        "claimed_count": kinds.get("claimed", 0),
        "adopted_count": kinds.get("adopted", 0),
        "attempted_count": kinds.get("attempted", 0),
        "effected_count": kinds.get("effected", 0),
        "abandoned_count": kinds.get("abandoned", 0),
        "expired_count": kinds.get("expired", 0),
        "disputed_count": kinds.get("disputed", 0),
        "unknown_outcome_count": kinds.get("unknown", 0),
        "matched_count": matched,
        "contrary_count": contrary,
        "blocked_count": statuses.get("blocked", 0),
        "unknown_count": statuses.get("unknown", 0),
        "censored_count": censored,
        "compliance_denominator": matched + contrary,
        "objective_effect_count": len(effects),
        "objective_matched_count": len(effect_matches),
        "partial_coverage": partial,
        "as_of_tick": tick,
    }
    assert set(values) == set(spec.value_keys)
    return MetricDocument(
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        metric_family=spec.family_id.value,
        algorithm_version=spec.algorithm_version,
        library_versions=library_versions(),
        run_id=run_id,
        input_revision=input_revision,
        evidence_stages=frozenset(spec.evidence_inputs),
        population=spec.population,
        denominator=spec.denominator,
        coverage=_coverage(
            matched + contrary, matched + contrary + statuses.get("unknown", 0)
        ),
        availability=availability,
        values=values,
        provenance=MetricProvenance(
            source_kind="collective_decision_outcomes",
            source_ids=(),
            notes_code="ok"
            if availability is not MetricAvailability.ABSENT
            else "empty",
        ),
    )


def compute_collective_decision_disagreement(
    snapshots: Sequence[CollectiveDecisionSnapshot],
    *,
    run_id: str,
    input_revision: str,
    tick: int = 0,
) -> MetricDocument:
    """Measure disagreement only within sufficiently aligned courses."""
    run_id = require_stable_id("run_id", run_id)
    input_revision = require_stable_id("input_revision", input_revision)
    tick = require_exact_nonneg_int("tick", tick)
    spec = metric_specification(MetricFamilyId.COLLECTIVE_DECISION_DISAGREEMENT)
    enabled = tuple(item for item in snapshots if item.enabled)
    within_owner = 0
    for snapshot in enabled:
        stances: dict[tuple[str, int], set[str]] = defaultdict(set)
        for row in snapshot.positions:
            if not row.active:
                continue
            stances[(row.proposal_ref, row.revision)].add(row.stance)
        within_owner += sum(1 for values in stances.values() if len(values) > 1)
    alignments, excluded = align_collective_decision_courses(enabled)
    cross_owner = 0
    usable = 0
    for alignment in alignments:
        if alignment.ambiguous or alignment.confidence < _ALIGNMENT_FLOOR:
            continue
        usable += 1
        owner_stances: dict[str, set[str]] = defaultdict(set)
        for snapshot in enabled:
            if snapshot.owner_id not in alignment.owners:
                continue
            for proposal in snapshot.proposals:
                if (
                    proposal.topic != alignment.topic
                    or proposal.action_token != alignment.action_token
                ):
                    continue
                for position in snapshot.positions:
                    if (
                        position.proposal_ref == proposal.proposal_ref
                        and position.revision == proposal.revision
                        and position.active
                    ):
                        owner_stances[snapshot.owner_id].add(position.stance)
        ordered = [
            next(iter(values)) for values in owner_stances.values() if len(values) == 1
        ]
        if len(set(ordered)) > 1:
            cross_owner += 1
    partial = any(item.coverage == "partial" for item in enabled)
    availability = (
        MetricAvailability.ABSENT
        if not enabled
        else (MetricAvailability.PARTIAL if partial else MetricAvailability.PRESENT)
    )
    values = {
        "within_owner_contradiction_count": within_owner,
        "cross_owner_disagreement_count": cross_owner,
        "aligned_course_count": usable,
        "excluded_alignment_count": excluded,
        "ambiguous_alignment_count": sum(1 for item in alignments if item.ambiguous),
        "partial_coverage": partial,
        "as_of_tick": tick,
    }
    assert set(values) == set(spec.value_keys)
    return MetricDocument(
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        metric_family=spec.family_id.value,
        algorithm_version=spec.algorithm_version,
        library_versions=library_versions(),
        run_id=run_id,
        input_revision=input_revision,
        evidence_stages=frozenset(spec.evidence_inputs),
        population=spec.population,
        denominator=spec.denominator,
        coverage=_coverage(usable, usable + excluded),
        availability=availability,
        values=values,
        provenance=MetricProvenance(
            source_kind="collective_decision_disagreement",
            source_ids=(),
            notes_code="ok"
            if availability is not MetricAvailability.ABSENT
            else "empty",
        ),
    )


@dataclass(frozen=True, slots=True)
class CollectiveEffectRow:
    """Detached committed-effect fact used only for post-run correspondence."""

    actor_id: str
    kind: str
    tick: int
    target_token: str | None = None

    def __post_init__(self) -> None:
        require_stable_id("actor_id", self.actor_id)
        require_stable_id("kind", self.kind)
        _require_tick("tick", self.tick)
        if self.target_token is not None:
            require_stable_id("target_token", self.target_token)


@dataclass(frozen=True, slots=True)
class CollectiveEffectMatch:
    """One correspondence between a supported course and a committed effect."""

    owner_id: str
    actor_id: str
    proposal_ref: str
    revision: int
    kind: str
    tick: int

    def __post_init__(self) -> None:
        require_stable_id("owner_id", self.owner_id)
        require_stable_id("actor_id", self.actor_id)
        _require_hex("proposal_ref", self.proposal_ref)
        _require_tick("revision", self.revision)
        require_stable_id("kind", self.kind)
        _require_tick("tick", self.tick)


_EFFECT_MATCH_KINDS: Final[dict[str, frozenset[str]]] = {
    "collective_project": frozenset(
        {
            "collective_project_started",
            "collective_project_contributed",
            "startcollectiveproject",
            "contributecollectiveproject",
        }
    ),
    "resource_allocation": frozenset({"gave", "give", "received"}),
    "migration": frozenset({"move", "moved", "journey_started", "journey_ended"}),
    "shared_defense": frozenset({"helped", "help", "defended"}),
    "storage": frozenset({"stored", "deposited", "retrieved", "store"}),
    "norm_enforcement": frozenset({"warned", "admonished", "mediated"}),
}


def match_collective_effects(
    snapshots: Sequence[CollectiveDecisionSnapshot],
    effects: Sequence[CollectiveEffectRow],
) -> tuple[CollectiveEffectMatch, ...]:
    """Join committed effects to supported courses without feeding cognition.

    A match proves an observable effect happened for the actor inside the
    course window. It never proves the actor accepted the proposal, and it never
    creates a legitimate winner.
    """
    matches: list[CollectiveEffectMatch] = []
    seen: set[tuple[str, str, int, str, int]] = set()
    for snapshot in snapshots:
        if not snapshot.enabled:
            continue
        for proposal in snapshot.proposals:
            allowed = _EFFECT_MATCH_KINDS.get(proposal.topic, frozenset())
            if not allowed:
                continue
            actors = {
                position.actor_id
                for position in snapshot.positions
                if position.proposal_ref == proposal.proposal_ref
                and position.revision == proposal.revision
                and position.active
                and position.stance in {"support", "delegate"}
            }
            for effect in effects:
                if effect.actor_id not in actors:
                    continue
                if effect.kind not in allowed:
                    continue
                if not (
                    proposal.window_first_tick
                    <= effect.tick
                    <= proposal.window_last_tick
                ):
                    continue
                key = (
                    snapshot.owner_id,
                    proposal.proposal_ref,
                    proposal.revision,
                    effect.kind,
                    effect.tick,
                )
                if key in seen:
                    continue
                seen.add(key)
                matches.append(
                    CollectiveEffectMatch(
                        owner_id=snapshot.owner_id,
                        actor_id=effect.actor_id,
                        proposal_ref=proposal.proposal_ref,
                        revision=proposal.revision,
                        kind=effect.kind,
                        tick=effect.tick,
                    )
                )
    _LOG.debug(
        "collective_decision_effect_join effects=%s matches=%s",
        len(effects),
        len(matches),
    )
    return tuple(matches)
