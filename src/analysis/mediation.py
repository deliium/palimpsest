"""Detached analysis of owner-scoped voluntary conflict mediation.

Rows are harvested from exported subjective ledgers after the run. Owner-local
case references remain testimony; cross-owner alignment is analytical inference
over context/party/function evidence. Nothing here feeds live cognition.
"""

from __future__ import annotations

import hashlib
import logging
from collections import defaultdict
from collections.abc import Mapping, Sequence
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

_LOG: Final[logging.Logger] = logging.getLogger("analysis.mediation")

_HEX: Final[frozenset[str]] = frozenset("0123456789abcdef")
_DIGEST_LEN: Final[int] = 16
_STABLE_RECOGNITION_CASES: Final[int] = 3
_STABLE_RECOGNITION_SUPPORTERS: Final[int] = 2
_STABLE_RECOGNITION_SPAN: Final[int] = 2


class MediationAnalysisError(ValueError):
    """Fail-closed analysis error; messages are codes only."""


class MediationRoleClass(StrEnum):
    """Analytical role classification; never a world or cognition status."""

    TRANSIENT = "transient_assistance"
    REPEATED = "repeated_mediator_activity"
    CANDIDATE = "candidate_recognized_role"
    STABLE = "stable_recognized_role"
    NONE = "no_role_evidence"


def _digest16(material: str) -> str:
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:_DIGEST_LEN]


def _require_hex(field_name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in _HEX for char in value)
    ):
        raise MediationAnalysisError(f"invalid_id:{field_name}")
    return value


def _require_digest(field_name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != _DIGEST_LEN
        or any(char not in _HEX for char in value)
    ):
        raise MediationAnalysisError(f"invalid_digest:{field_name}")
    return value


def _require_tick(field_name: str, value: object) -> int:
    return require_exact_nonneg_int(field_name, value)


@dataclass(frozen=True, slots=True)
class MediationCaseRow:
    owner_id: str
    case_ref: str
    subject_token: str
    context_key: str
    status: str
    origin_id: str | None
    party_ids: tuple[str, ...]
    evidence_count: int
    pruned_evidence_count: int
    first_tick: int
    last_tick: int
    window_first_tick: int
    window_last_tick: int
    evidence_coverage: str
    root_ref: str = ""

    def __post_init__(self) -> None:
        require_stable_id("owner_id", self.owner_id)
        _require_hex("case_ref", self.case_ref)
        require_stable_id("subject_token", self.subject_token)
        _require_digest("context_key", self.context_key)
        require_stable_id("status", self.status)
        for name in (
            "first_tick",
            "last_tick",
            "window_first_tick",
            "window_last_tick",
            "evidence_count",
            "pruned_evidence_count",
        ):
            _require_tick(name, getattr(self, name))


@dataclass(frozen=True, slots=True)
class MediationRecommendationRow:
    owner_id: str
    case_ref: str
    revision: int
    proposed_actor_id: str
    action_token: str
    item_token: str | None
    project_token: str | None
    target_ids: tuple[str, ...]
    terms: tuple[str, ...]
    quantity: int
    status: str
    window_first_tick: int
    window_last_tick: int

    def __post_init__(self) -> None:
        require_stable_id("owner_id", self.owner_id)
        _require_hex("case_ref", self.case_ref)
        _require_tick("revision", self.revision)
        require_stable_id("proposed_actor_id", self.proposed_actor_id)
        require_stable_id("action_token", self.action_token)
        require_stable_id("status", self.status)
        for name in ("window_first_tick", "window_last_tick"):
            _require_tick(name, getattr(self, name))


@dataclass(frozen=True, slots=True)
class MediationResponseRow:
    owner_id: str
    actor_id: str
    case_ref: str
    kind: str
    recommendation_ref: str | None
    recommendation_revision: int | None
    direct: bool
    active: bool
    tick: int

    def __post_init__(self) -> None:
        require_stable_id("owner_id", self.owner_id)
        require_stable_id("actor_id", self.actor_id)
        _require_hex("case_ref", self.case_ref)
        require_stable_id("kind", self.kind)
        _require_tick("tick", self.tick)


@dataclass(frozen=True, slots=True)
class MediationRoleExpressionRow:
    owner_id: str
    actor_id: str
    kind: str
    context_key: str
    active: bool
    first_tick: int
    last_tick: int

    def __post_init__(self) -> None:
        require_stable_id("owner_id", self.owner_id)
        require_stable_id("actor_id", self.actor_id)
        require_stable_id("kind", self.kind)
        _require_digest("context_key", self.context_key)
        _require_tick("first_tick", self.first_tick)
        _require_tick("last_tick", self.last_tick)


@dataclass(frozen=True, slots=True)
class MediationAttemptRow:
    owner_id: str
    actor_id: str
    case_ref: str
    recommendation_ref: str | None
    recommendation_revision: int | None
    status: str
    action_token: str | None
    item_token: str | None
    target_ids: tuple[str, ...]
    resulting_command_token: str | None
    tick: int
    window_first_tick: int | None = None
    window_last_tick: int | None = None

    def __post_init__(self) -> None:
        require_stable_id("owner_id", self.owner_id)
        require_stable_id("actor_id", self.actor_id)
        _require_hex("case_ref", self.case_ref)
        require_stable_id("status", self.status)
        _require_tick("tick", self.tick)


@dataclass(frozen=True, slots=True)
class MediationOutcomeRow:
    owner_id: str
    case_ref: str
    kind: str
    claimed: bool
    actor_id: str | None
    first_tick: int
    last_tick: int

    def __post_init__(self) -> None:
        require_stable_id("owner_id", self.owner_id)
        _require_hex("case_ref", self.case_ref)
        require_stable_id("kind", self.kind)
        _require_tick("first_tick", self.first_tick)
        _require_tick("last_tick", self.last_tick)


@dataclass(frozen=True, slots=True)
class MediationSnapshot:
    """Detached rows for one owner with explicit coverage metadata."""

    owner_id: str
    enabled: bool
    coverage: str
    first_observed_tick: int | None
    last_observed_tick: int | None
    observation_count: int
    cases: tuple[MediationCaseRow, ...] = ()
    recommendations: tuple[MediationRecommendationRow, ...] = ()
    responses: tuple[MediationResponseRow, ...] = ()
    role_expressions: tuple[MediationRoleExpressionRow, ...] = ()
    attempts: tuple[MediationAttemptRow, ...] = ()
    outcomes: tuple[MediationOutcomeRow, ...] = ()
    pruned_case_count: int = 0
    pruned_evidence_count: int = 0
    pruned_recommendation_count: int = 0
    pruned_response_count: int = 0

    def __post_init__(self) -> None:
        require_stable_id("owner_id", self.owner_id)
        if self.coverage not in {"complete", "partial"}:
            raise MediationAnalysisError("invalid_coverage")
        for name in (
            "observation_count",
            "pruned_case_count",
            "pruned_evidence_count",
            "pruned_recommendation_count",
            "pruned_response_count",
        ):
            _require_tick(name, getattr(self, name))


def _case_root_ref(case: Any) -> str:
    roots = sorted(
        {
            str(item.root_ref)
            for item in getattr(case, "evidence", ())
            if getattr(item, "root_ref", "")
        }
    )
    return roots[0] if roots else ""


def harvest_mediation_snapshot(ledger: Any) -> MediationSnapshot:
    """Convert one exported owner ledger into detached immutable rows."""
    if type(ledger).__name__ != "MediationLedger":
        raise TypeError("ledger must be MediationLedger")
    if not hasattr(ledger, "owner_id") or not hasattr(ledger, "cases"):
        raise TypeError("ledger must expose owner_id and cases")
    owner = ledger.owner_id.value
    recommendation_windows = {
        item.recommendation_id: (
            item.revision,
            item.window_first_tick,
            item.window_last_tick,
        )
        for item in ledger.recommendations
    }
    return MediationSnapshot(
        owner_id=owner,
        enabled=ledger.enabled,
        coverage=ledger.coverage,
        first_observed_tick=ledger.first_observed_tick,
        last_observed_tick=ledger.last_observed_tick,
        observation_count=ledger.observation_count,
        cases=tuple(
            MediationCaseRow(
                owner_id=owner,
                case_ref=case.case_ref,
                subject_token=case.subject_token,
                context_key=case.context_key,
                status=case.status.value,
                origin_id=(None if case.origin_id is None else case.origin_id.value),
                party_ids=tuple(item.value for item in case.party_ids),
                evidence_count=len(case.evidence),
                pruned_evidence_count=case.pruned_evidence_count,
                first_tick=case.first_tick,
                last_tick=case.last_tick,
                window_first_tick=case.window_first_tick,
                window_last_tick=case.window_last_tick,
                evidence_coverage=case.evidence_coverage,
                root_ref=_case_root_ref(case),
            )
            for case in ledger.cases
        ),
        recommendations=tuple(
            MediationRecommendationRow(
                owner_id=owner,
                case_ref=item.case_ref,
                revision=item.revision,
                proposed_actor_id=item.proposed_actor_id.value,
                action_token=item.action_token,
                item_token=item.item_token,
                project_token=item.project_token,
                target_ids=tuple(agent.value for agent in item.target_ids),
                terms=item.terms,
                quantity=item.quantity,
                status=item.status.value,
                window_first_tick=item.window_first_tick,
                window_last_tick=item.window_last_tick,
            )
            for item in ledger.recommendations
        ),
        responses=tuple(
            MediationResponseRow(
                owner_id=owner,
                actor_id=item.actor_id.value,
                case_ref=item.case_ref,
                kind=item.kind.value,
                recommendation_ref=item.recommendation_ref,
                recommendation_revision=item.recommendation_revision,
                direct=item.direct,
                active=item.active,
                tick=item.tick,
            )
            for item in ledger.responses
        ),
        role_expressions=tuple(
            MediationRoleExpressionRow(
                owner_id=owner,
                actor_id=item.actor_id.value,
                kind=item.kind.value,
                context_key=item.context_key,
                active=item.active,
                first_tick=item.first_tick,
                last_tick=item.last_tick,
            )
            for item in ledger.role_expressions
        ),
        attempts=tuple(
            MediationAttemptRow(
                owner_id=owner,
                actor_id=item.actor_id.value,
                case_ref=item.case_ref,
                recommendation_ref=item.recommendation_ref,
                recommendation_revision=item.recommendation_revision,
                status=item.status.value,
                action_token=item.action_token,
                item_token=item.item_token,
                target_ids=tuple(agent.value for agent in item.target_ids),
                resulting_command_token=item.resulting_command_token,
                tick=item.tick,
                window_first_tick=(
                    None
                    if item.recommendation_ref is None
                    else recommendation_windows.get(
                        item.recommendation_ref, (None, None, None)
                    )[1]
                ),
                window_last_tick=(
                    None
                    if item.recommendation_ref is None
                    else recommendation_windows.get(
                        item.recommendation_ref, (None, None, None)
                    )[2]
                ),
            )
            for item in ledger.attempts
        ),
        outcomes=tuple(
            MediationOutcomeRow(
                owner_id=owner,
                case_ref=item.case_ref,
                kind=item.kind.value,
                claimed=item.claimed,
                actor_id=(None if item.actor_id is None else item.actor_id.value),
                first_tick=item.first_tick,
                last_tick=item.last_tick,
            )
            for item in ledger.outcomes
        ),
        pruned_case_count=ledger.pruned_case_count,
        pruned_evidence_count=ledger.pruned_evidence_count,
        pruned_recommendation_count=ledger.pruned_recommendation_count,
        pruned_response_count=ledger.pruned_response_count,
    )


def harvest_mediation_rows(ledgers: Sequence[object]) -> tuple[MediationSnapshot, ...]:
    """Harvest completed-result exports into a stable owner-ordered tuple."""
    snapshots: list[MediationSnapshot] = []
    seen: set[str] = set()
    for ledger in ledgers:
        snapshot = harvest_mediation_snapshot(ledger)
        if snapshot.owner_id in seen:
            raise MediationAnalysisError("duplicate_owner")
        seen.add(snapshot.owner_id)
        snapshots.append(snapshot)
    return tuple(sorted(snapshots, key=lambda item: item.owner_id))


@dataclass(frozen=True, slots=True)
class MediationEffectRow:
    """Detached objective effect used only for post-hoc correspondence.

    ``case_ref`` is normally unknown to the objective world and stays ``None``
    for harvested events; matching then uses actor/recipient/item/window scope.
    """

    actor_id: str
    recipient_id: str
    item_token: str | None
    tick: int
    case_ref: str | None = None
    recommendation_ref: str | None = None
    recommendation_revision: int | None = None
    window_first_tick: int | None = None
    window_last_tick: int | None = None

    def __post_init__(self) -> None:
        require_stable_id("actor_id", self.actor_id)
        require_stable_id("recipient_id", self.recipient_id)
        _require_tick("tick", self.tick)
        if self.case_ref is not None:
            _require_hex("case_ref", self.case_ref)
        if self.recommendation_ref is not None:
            _require_hex("recommendation_ref", self.recommendation_ref)
        if (self.recommendation_ref is None) != (
            self.recommendation_revision is None
        ):
            raise MediationAnalysisError("incomplete_recommendation_reference")
        if self.recommendation_revision is not None:
            _require_tick("recommendation_revision", self.recommendation_revision)
        for name in ("window_first_tick", "window_last_tick"):
            value = getattr(self, name)
            if value is not None:
                _require_tick(name, value)
        if (
            self.window_first_tick is not None
            and self.window_last_tick is not None
            and self.window_last_tick < self.window_first_tick
        ):
            raise MediationAnalysisError("invalid_window")


def mediation_effect_rows_from_events(
    events: Sequence[object],
    *,
    entity_to_agent: Mapping[str, str],
) -> tuple[MediationEffectRow, ...]:
    """Project committed Give outcomes into detached effect rows."""
    rows: list[MediationEffectRow] = []
    for event in events:
        details = getattr(event, "details", event)
        if getattr(details, "kind", None) != "give":
            continue
        actor_entity = getattr(event, "actor_id", None)
        recipient_entity = getattr(details, "recipient_id", None)
        item_entity = getattr(details, "item_id", None)
        if actor_entity is None or recipient_entity is None or item_entity is None:
            continue
        actor = entity_to_agent.get(str(getattr(actor_entity, "value", actor_entity)))
        recipient = entity_to_agent.get(
            str(getattr(recipient_entity, "value", recipient_entity))
        )
        tick = getattr(event, "tick", None)
        if actor is None or recipient is None or type(tick) is not int:
            continue
        rows.append(
            MediationEffectRow(
                actor_id=actor,
                recipient_id=recipient,
                item_token=str(getattr(item_entity, "value", item_entity)).lower(),
                tick=tick,
            )
        )
    return tuple(
        sorted(
            rows,
            key=lambda item: (
                item.tick,
                item.actor_id,
                item.recipient_id,
                item.item_token or "",
            ),
        )
    )


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


def _availability(
    enabled: Sequence[MediationSnapshot], *, empty: bool
) -> MetricAvailability:
    if not enabled or empty:
        return MetricAvailability.ABSENT
    if any(item.coverage == "partial" for item in enabled):
        return MetricAvailability.PARTIAL
    return MetricAvailability.PRESENT


def match_mediation_effects(
    snapshots: Sequence[MediationSnapshot],
    effects: Sequence[MediationEffectRow],
) -> tuple[int, int]:
    """Return (matched, ambiguous) using exact revision/recipient/item scope.

    One objective effect never fulfills multiple recommendations.
    """
    attempted = [
        row
        for snapshot in snapshots
        for row in snapshot.attempts
        if row.status == "attempted"
    ]
    used: set[int] = set()
    matched = 0
    ambiguous = 0
    for effect in effects:
        candidates = [
            index
            for index, row in enumerate(attempted)
            if index not in used
            and (effect.case_ref is None or row.case_ref == effect.case_ref)
            and row.actor_id == effect.actor_id
            and effect.recipient_id in row.target_ids
            and (effect.item_token is None or row.item_token == effect.item_token)
            and (
                effect.recommendation_ref is None
                or row.recommendation_ref == effect.recommendation_ref
            )
            and (
                effect.recommendation_revision is None
                or row.recommendation_revision == effect.recommendation_revision
            )
            and effect.tick >= row.tick
            and (row.window_first_tick is None or effect.tick >= row.window_first_tick)
            and (row.window_last_tick is None or effect.tick <= row.window_last_tick)
        ]
        if len(candidates) == 1:
            used.add(candidates[0])
            matched += 1
        elif len(candidates) > 1:
            ambiguous += 1
    return matched, ambiguous


def compute_conflict_mediation(
    snapshots: Sequence[MediationSnapshot],
    *,
    run_id: str,
    input_revision: str,
    tick: int = 0,
    effects: Sequence[MediationEffectRow] = (),
) -> MetricDocument:
    """Measure mediation activity and uptake, never effectiveness."""
    run_id = require_stable_id("run_id", run_id)
    input_revision = require_stable_id("input_revision", input_revision)
    tick = require_exact_nonneg_int("tick", tick)
    spec = metric_specification(MetricFamilyId.CONFLICT_MEDIATION)
    enabled = tuple(item for item in snapshots if item.enabled)
    cases = [row for snapshot in enabled for row in snapshot.cases]
    recommendations = [row for snapshot in enabled for row in snapshot.recommendations]
    responses = [row for snapshot in enabled for row in snapshot.responses]
    attempts = [row for snapshot in enabled for row in snapshot.attempts]
    matched, ambiguous = match_mediation_effects(enabled, effects)
    kinds: defaultdict[str, int] = defaultdict(int)
    for response_row in responses:
        if response_row.active:
            kinds[response_row.kind] += 1
    statuses: defaultdict[str, int] = defaultdict(int)
    for case_row in cases:
        statuses[case_row.status] += 1
    distinct_cases = {
        (case_row.root_ref or case_row.case_ref)
        for snapshot in enabled
        for case_row in snapshot.cases
    }
    availability = _availability(
        enabled, empty=not cases and not recommendations and not responses
    )
    values = {
        "distinct_case_count": len(distinct_cases),
        "recommendation_count": len(recommendations),
        "compromise_count": sum(1 for row in recommendations if not row.terms),
        "restitution_recommendation_count": sum(
            1 for row in recommendations if row.terms
        ),
        "account_count": kinds.get("account", 0),
        "accept_count": kinds.get("accept", 0),
        "refuse_count": kinds.get("refuse", 0),
        "defer_count": kinds.get("defer", 0),
        "counterproposal_count": kinds.get("counterpropose", 0),
        "withdraw_count": kinds.get("withdraw", 0),
        "settlement_claim_count": kinds.get("claim_settlement", 0),
        "attempted_follow_through_count": sum(
            1 for row in attempts if row.status == "attempted"
        ),
        "effected_follow_through_count": matched,
        "ambiguous_effect_count": ambiguous,
        "unresolved_case_count": statuses.get("unresolved", 0),
        "partial_case_count": statuses.get("partially_addressed", 0),
        "disputed_case_count": statuses.get("disputed", 0),
        "apparently_settled_case_count": statuses.get("apparently_settled", 0),
        "ignored_or_unknown_count": sum(
            1
            for snapshot in enabled
            for case_row in snapshot.cases
            if not any(
                row.case_ref == case_row.case_ref and row.active
                for row in responses
            )
        ),
        "enabled_owner_count": len(enabled),
        "partial_coverage": any(item.coverage == "partial" for item in enabled),
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
        coverage=_coverage(len(enabled), len(snapshots)),
        availability=availability,
        values=values,
        provenance=MetricProvenance(
            source_kind="conflict_mediation",
            source_ids=(),
            notes_code=(
                "ok" if availability is not MetricAvailability.ABSENT else "empty"
            ),
        ),
    )


@dataclass(frozen=True, slots=True)
class MediationRoleAssessment:
    actor_id: str
    role_class: MediationRoleClass
    distinct_case_count: int
    independent_supporter_count: int
    span_ticks: int
    contested: bool


def classify_mediation_roles(
    snapshots: Sequence[MediationSnapshot],
) -> tuple[MediationRoleAssessment, ...]:
    """Classify recurrence/recognition per owner without a global role.

    Repeated activity alone cannot reach a stable-role class.
    """
    assessments: list[MediationRoleAssessment] = []
    for snapshot in snapshots:
        if not snapshot.enabled:
            continue
        acting_cases: dict[str, set[str]] = defaultdict(set)
        supporters: dict[str, set[str]] = defaultdict(set)
        span_first: dict[str, int] = {}
        span_last: dict[str, int] = {}
        contested = False
        for expression in snapshot.role_expressions:
            if not expression.active:
                continue
            if expression.kind in {"invite_mediator", "endorse_role"}:
                supporters[snapshot.owner_id].add(
                    f"{expression.actor_id}|{expression.context_key}"
                )
            span_first[snapshot.owner_id] = min(
                span_first.get(snapshot.owner_id, expression.first_tick),
                expression.first_tick,
            )
            span_last[snapshot.owner_id] = max(
                span_last.get(snapshot.owner_id, expression.last_tick),
                expression.last_tick,
            )
        for case in snapshot.cases:
            acting_cases[snapshot.owner_id].add(case.case_ref)
            if case.status == "disputed":
                contested = True
        for actor in sorted(set(acting_cases) | set(supporters)):
            case_count = len(acting_cases.get(actor, ()))
            supporter_count = len(supporters.get(actor, ()))
            span = span_last.get(actor, 0) - span_first.get(actor, 0)
            if case_count >= _STABLE_RECOGNITION_CASES and (
                supporter_count >= _STABLE_RECOGNITION_SUPPORTERS
                and span >= _STABLE_RECOGNITION_SPAN
            ):
                role_class = MediationRoleClass.STABLE
            elif case_count >= 1 and supporter_count >= 1:
                role_class = MediationRoleClass.CANDIDATE
            elif case_count >= 2:
                role_class = MediationRoleClass.REPEATED
            elif case_count == 1:
                role_class = MediationRoleClass.TRANSIENT
            else:
                role_class = MediationRoleClass.NONE
            assessments.append(
                MediationRoleAssessment(
                    actor_id=actor,
                    role_class=role_class,
                    distinct_case_count=case_count,
                    independent_supporter_count=supporter_count,
                    span_ticks=max(0, span),
                    contested=contested,
                )
            )
    return tuple(sorted(assessments, key=lambda item: item.actor_id))


def compute_mediation_role_emergence(
    snapshots: Sequence[MediationSnapshot],
    *,
    run_id: str,
    input_revision: str,
    tick: int = 0,
) -> MetricDocument:
    """Report recurrence/recognition classes with explicit temporal coverage."""
    run_id = require_stable_id("run_id", run_id)
    input_revision = require_stable_id("input_revision", input_revision)
    tick = require_exact_nonneg_int("tick", tick)
    spec = metric_specification(MetricFamilyId.MEDIATION_ROLE_EMERGENCE)
    enabled = tuple(item for item in snapshots if item.enabled)
    assessments = classify_mediation_roles(enabled)
    counts: defaultdict[str, int] = defaultdict(int)
    for item in assessments:
        counts[item.role_class.value] += 1
    invitations = sum(
        1
        for snapshot in enabled
        for row in snapshot.role_expressions
        if row.kind == "invite_mediator" and row.active
    )
    endorsements = sum(
        1
        for snapshot in enabled
        for row in snapshot.role_expressions
        if row.kind == "endorse_role" and row.active
    )
    withdrawn = sum(
        1
        for snapshot in enabled
        for row in snapshot.role_expressions
        if row.kind == "withdraw_role_endorsement" and row.active
    )
    availability = _availability(
        enabled, empty=not assessments and not invitations and not endorsements
    )
    values = {
        "recurring_mediator_count": counts.get("repeated_mediator_activity", 0),
        "transient_assistance_count": counts.get("transient_assistance", 0),
        "candidate_role_count": counts.get("candidate_recognized_role", 0),
        "stable_role_count": counts.get("stable_recognized_role", 0),
        "independent_invitation_count": invitations,
        "independent_endorsement_count": endorsements,
        "contested_recognition_count": sum(1 for item in assessments if item.contested),
        "lost_support_count": withdrawn,
        "enabled_owner_count": len(enabled),
        "partial_coverage": any(item.coverage == "partial" for item in enabled),
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
        coverage=_coverage(len(enabled), len(snapshots)),
        availability=availability,
        values=values,
        provenance=MetricProvenance(
            source_kind="mediation_role_emergence",
            source_ids=(),
            notes_code=(
                "ok" if availability is not MetricAvailability.ABSENT else "empty"
            ),
        ),
    )
