"""Detached dispute rows harvested from exported owner ledgers.

Rows are owner-valued and read-only. Harvesting never mutates a ledger, never
mints an analytical identity, and never reads cognition, world state, events, or
commands. Claim text, evidence payloads, rule bodies, and mediation
recommendations are never copied.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Final, cast

from analysis.dispute_contract import (
    DISPUTE_COVERAGE_TOKENS,
    DISPUTE_DEFAULT_WINDOW_TICKS,
    DisputeAnalysisError,
)
from analysis.numerical import quantize_float

__all__ = [
    "DisputeAuthorityReferenceRow",
    "DisputeCaseRow",
    "DisputeClaimRow",
    "DisputeEvidenceRow",
    "DisputeHarvestRows",
    "DisputeMediationReferenceRow",
    "DisputeOwnerRow",
    "DisputeResolutionResponseRow",
    "DisputeResolutionRow",
    "DisputeRuleReferenceRow",
    "DisputeTestimonyRow",
    "harvest_dispute_rows",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.disputes")


def _fail(code: str = "dispute_invalid_row") -> None:
    raise DisputeAnalysisError(code)


def _text(value: object, code: str = "dispute_invalid_row") -> str:
    if not isinstance(value, str) or not value:
        _fail(code)
    return cast(str, value)


def _opt_text(value: object) -> str | None:
    if value is None:
        return None
    if type(value) is not str or not value:
        _fail()
    return cast(str, value)


def _enum_value(value: object) -> str:
    if isinstance(value, str) and value:
        return value
    token = getattr(value, "value", None)
    if not isinstance(token, str) or not token:
        _fail()
    return cast(str, token)


def _count(value: object) -> int:
    if isinstance(value, bool) or type(value) is not int or value < 0:
        _fail()
    return cast(int, value)


def _tick(value: object) -> int:
    if isinstance(value, bool) or type(value) is not int or value < 0:
        _fail()
    return cast(int, value)


def _unit(value: object) -> float:
    if type(value) is not float:
        _fail()
    number = cast(float, value)
    if not 0.0 <= number <= 1.0:
        _fail()
    return quantize_float(number)


def _flag(value: object) -> bool:
    if type(value) is not bool:
        _fail()
    return cast(bool, value)


def _coverage_token(value: object) -> str:
    token = _text(value)
    if token not in DISPUTE_COVERAGE_TOKENS:
        _fail()
    return token


def _tokens(value: object) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (tuple, list)):
        _fail()
    return tuple(sorted({_text(item) for item in cast("Sequence[object]", value)}))


def _optional_tokens(value: object) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (tuple, list)):
        _fail()
    items: list[str] = []
    for item in cast("Sequence[object]", value):
        items.append(_text(item))
    return tuple(sorted(set(items)))


@dataclass(frozen=True, slots=True)
class DisputeOwnerRow:
    owner_id: str
    case_count: int
    claim_count: int
    testimony_count: int
    evidence_count: int
    resolution_count: int
    pruned_count: int
    coverage: str
    first_tick: int
    last_tick: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "owner_id", _text(self.owner_id))
        object.__setattr__(self, "case_count", _count(self.case_count))
        object.__setattr__(self, "claim_count", _count(self.claim_count))
        object.__setattr__(self, "testimony_count", _count(self.testimony_count))
        object.__setattr__(self, "evidence_count", _count(self.evidence_count))
        object.__setattr__(self, "resolution_count", _count(self.resolution_count))
        object.__setattr__(self, "pruned_count", _count(self.pruned_count))
        object.__setattr__(self, "coverage", _coverage_token(self.coverage))
        first, last = _tick(self.first_tick), _tick(self.last_tick)
        if last < first:
            _fail()
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)


@dataclass(frozen=True, slots=True)
class DisputeCaseRow:
    owner_id: str
    case_ref: str
    kind: str
    subject_kind: str
    subject_token: str
    status: str
    party_ids: tuple[str, ...]
    first_tick: int
    last_tick: int
    coverage: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "owner_id", _text(self.owner_id))
        object.__setattr__(self, "case_ref", _text(self.case_ref))
        object.__setattr__(self, "kind", _text(self.kind))
        object.__setattr__(self, "subject_kind", _text(self.subject_kind))
        object.__setattr__(self, "subject_token", _text(self.subject_token))
        object.__setattr__(self, "status", _text(self.status))
        object.__setattr__(self, "party_ids", _tokens(self.party_ids))
        first, last = _tick(self.first_tick), _tick(self.last_tick)
        if last < first:
            _fail()
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)
        object.__setattr__(self, "coverage", _coverage_token(self.coverage))


@dataclass(frozen=True, slots=True)
class DisputeClaimRow:
    owner_id: str
    case_ref: str
    claim_ref: str
    claimant_id: str
    respondent_id: str
    role: str
    claim_kind: str
    polarity: str
    subject_token: str
    counters_claim_ref: str | None
    evidence_count: int
    first_tick: int
    last_tick: int

    def __post_init__(self) -> None:
        for name in (
            "owner_id",
            "case_ref",
            "claim_ref",
            "claimant_id",
            "respondent_id",
            "role",
            "claim_kind",
            "polarity",
            "subject_token",
        ):
            object.__setattr__(self, name, _text(getattr(self, name)))
        object.__setattr__(
            self, "counters_claim_ref", _opt_text(self.counters_claim_ref)
        )
        object.__setattr__(self, "evidence_count", _count(self.evidence_count))
        first, last = _tick(self.first_tick), _tick(self.last_tick)
        if last < first:
            _fail()
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)


@dataclass(frozen=True, slots=True)
class DisputeTestimonyRow:
    owner_id: str
    case_ref: str
    claim_ref: str
    testimony_ref: str
    speaker_id: str
    channel: str
    root_ref: str
    independently_evidenced: bool
    tick: int

    def __post_init__(self) -> None:
        for name in (
            "owner_id",
            "case_ref",
            "claim_ref",
            "testimony_ref",
            "speaker_id",
            "channel",
            "root_ref",
        ):
            object.__setattr__(self, name, _text(getattr(self, name)))
        object.__setattr__(
            self,
            "independently_evidenced",
            _flag(self.independently_evidenced),
        )
        object.__setattr__(self, "tick", _tick(self.tick))


@dataclass(frozen=True, slots=True)
class DisputeEvidenceRow:
    owner_id: str
    case_ref: str
    claim_ref: str
    evidence_ref: str
    channel: str
    reference_kind: str
    reference_id: str
    tick: int
    independently_evidenced: bool

    def __post_init__(self) -> None:
        for name in (
            "owner_id",
            "case_ref",
            "claim_ref",
            "evidence_ref",
            "channel",
            "reference_kind",
            "reference_id",
        ):
            object.__setattr__(self, name, _text(getattr(self, name)))
        object.__setattr__(self, "tick", _tick(self.tick))
        object.__setattr__(
            self,
            "independently_evidenced",
            _flag(self.independently_evidenced),
        )


@dataclass(frozen=True, slots=True)
class DisputeRuleReferenceRow:
    owner_id: str
    case_ref: str
    claim_ref: str
    rule_reference_ref: str
    system_ref: str
    rule_ref: str
    version_number: int
    applicability: str
    interpretation: str
    status: str

    def __post_init__(self) -> None:
        for name in (
            "owner_id",
            "case_ref",
            "claim_ref",
            "rule_reference_ref",
            "system_ref",
            "rule_ref",
            "applicability",
            "interpretation",
            "status",
        ):
            object.__setattr__(self, name, _text(getattr(self, name)))
        number = _count(self.version_number)
        if number < 1:
            _fail()
        object.__setattr__(self, "version_number", number)


@dataclass(frozen=True, slots=True)
class DisputeAuthorityReferenceRow:
    owner_id: str
    case_ref: str
    authority_ref: str
    authority_kind: str
    reference_id: str
    strength: float
    uncertainty: float
    dissenting: bool

    def __post_init__(self) -> None:
        for name in (
            "owner_id",
            "case_ref",
            "authority_ref",
            "authority_kind",
            "reference_id",
        ):
            object.__setattr__(self, name, _text(getattr(self, name)))
        object.__setattr__(self, "strength", _unit(self.strength))
        object.__setattr__(self, "uncertainty", _unit(self.uncertainty))
        object.__setattr__(self, "dissenting", _flag(self.dissenting))


@dataclass(frozen=True, slots=True)
class DisputeMediationReferenceRow:
    owner_id: str
    case_ref: str
    mediation_ref: str
    mediation_case_ref: str
    recommendation_ref: str | None
    response_ref: str | None
    outcome_ref: str | None
    link_status: str

    def __post_init__(self) -> None:
        for name in (
            "owner_id",
            "case_ref",
            "mediation_ref",
            "mediation_case_ref",
            "link_status",
        ):
            object.__setattr__(self, name, _text(getattr(self, name)))
        object.__setattr__(
            self, "recommendation_ref", _opt_text(self.recommendation_ref)
        )
        object.__setattr__(self, "response_ref", _opt_text(self.response_ref))
        object.__setattr__(self, "outcome_ref", _opt_text(self.outcome_ref))


@dataclass(frozen=True, slots=True)
class DisputeResolutionRow:
    owner_id: str
    case_ref: str
    resolution_ref: str
    proposer_id: str
    source: str
    terms_digest: str
    status: str
    first_tick: int
    last_tick: int
    expires_tick: int | None

    def __post_init__(self) -> None:
        for name in (
            "owner_id",
            "case_ref",
            "resolution_ref",
            "proposer_id",
            "source",
            "terms_digest",
            "status",
        ):
            object.__setattr__(self, name, _text(getattr(self, name)))
        first, last = _tick(self.first_tick), _tick(self.last_tick)
        if last < first:
            _fail()
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)
        if self.expires_tick is not None:
            object.__setattr__(self, "expires_tick", _tick(self.expires_tick))


@dataclass(frozen=True, slots=True)
class DisputeResolutionResponseRow:
    owner_id: str
    case_ref: str
    resolution_ref: str
    response_ref: str
    party_id: str
    kind: str
    tick: int
    terms_digest: str
    active: bool

    def __post_init__(self) -> None:
        for name in (
            "owner_id",
            "case_ref",
            "resolution_ref",
            "response_ref",
            "party_id",
            "kind",
            "terms_digest",
        ):
            object.__setattr__(self, name, _text(getattr(self, name)))
        object.__setattr__(self, "tick", _tick(self.tick))
        object.__setattr__(self, "active", _flag(self.active))


@dataclass(frozen=True, slots=True)
class DisputeHarvestRows:
    owners: tuple[DisputeOwnerRow, ...] = ()
    cases: tuple[DisputeCaseRow, ...] = ()
    claims: tuple[DisputeClaimRow, ...] = ()
    testimony: tuple[DisputeTestimonyRow, ...] = ()
    evidence: tuple[DisputeEvidenceRow, ...] = ()
    rule_references: tuple[DisputeRuleReferenceRow, ...] = ()
    authority_references: tuple[DisputeAuthorityReferenceRow, ...] = ()
    mediation_references: tuple[DisputeMediationReferenceRow, ...] = ()
    resolutions: tuple[DisputeResolutionRow, ...] = ()
    responses: tuple[DisputeResolutionResponseRow, ...] = ()
    window_ticks: int = DISPUTE_DEFAULT_WINDOW_TICKS

    def __post_init__(self) -> None:
        if isinstance(self.window_ticks, bool) or type(self.window_ticks) is not int:
            _fail()
        if self.window_ticks < 1:
            _fail()
        for name in (
            "owners",
            "cases",
            "claims",
            "testimony",
            "evidence",
            "rule_references",
            "authority_references",
            "mediation_references",
            "resolutions",
            "responses",
        ):
            values = tuple(getattr(self, name))
            if len(set(map(id, values))) != len(values):
                _fail()
            object.__setattr__(self, name, values)


def _owner_value(value: object) -> str:
    if isinstance(value, str) and value:
        return value
    token = getattr(value, "value", None)
    if not isinstance(token, str) or not token:
        _fail()
    return cast(str, token)


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    return _tick(value)


def _ordered[RowT](
    rows: Sequence[RowT],
    key: Callable[[RowT], tuple[str, ...]],
) -> tuple[RowT, ...]:
    deduped: dict[tuple[str, ...], RowT] = {}
    for row in rows:
        deduped.setdefault(key(row), row)
    return tuple(deduped[identity] for identity in sorted(deduped))


def _owner_span(ledger: object) -> tuple[int, int]:
    first = getattr(ledger, "first_observed_tick", None)
    last = getattr(ledger, "last_observed_tick", None)
    if first is None or last is None:
        return 0, 0
    return _tick(first), _tick(last)


def harvest_dispute_rows(
    ledgers: Sequence[object],
    *,
    window_ticks: int = DISPUTE_DEFAULT_WINDOW_TICKS,
) -> DisputeHarvestRows:
    """Normalize exported ledgers into sorted, duplicate-free detached rows."""

    if isinstance(window_ticks, bool) or type(window_ticks) is not int:
        _fail()
    if window_ticks < 1:
        _fail()
    if isinstance(ledgers, (str, bytes)) or not isinstance(ledgers, Sequence):
        _fail()
    owners: list[DisputeOwnerRow] = []
    cases: list[DisputeCaseRow] = []
    claims: list[DisputeClaimRow] = []
    testimony: list[DisputeTestimonyRow] = []
    evidence: list[DisputeEvidenceRow] = []
    rule_references: list[DisputeRuleReferenceRow] = []
    authority_references: list[DisputeAuthorityReferenceRow] = []
    mediation_references: list[DisputeMediationReferenceRow] = []
    resolutions: list[DisputeResolutionRow] = []
    responses: list[DisputeResolutionResponseRow] = []
    seen_owners: set[str] = set()
    for ledger in ledgers:
        owner_id = _owner_value(getattr(ledger, "owner_id", None))
        if owner_id in seen_owners:
            raise DisputeAnalysisError("dispute_duplicate_owner")
        seen_owners.add(owner_id)
        pruned_count = sum(
            _count(getattr(ledger, name, 0))
            for name in (
                "pruned_case_count",
                "pruned_claim_count",
                "pruned_testimony_count",
                "pruned_evidence_count",
                "pruned_resolution_count",
                "pruned_reference_count",
            )
        )
        coverage = "partial" if pruned_count else "complete"
        first_tick, last_tick = _owner_span(ledger)
        ledger_cases = tuple(getattr(ledger, "cases", ()) or ())
        ledger_claims = tuple(getattr(ledger, "claims", ()) or ())
        ledger_testimony = tuple(getattr(ledger, "testimony", ()) or ())
        ledger_evidence = tuple(getattr(ledger, "evidence", ()) or ())
        ledger_resolutions = tuple(getattr(ledger, "resolutions", ()) or ())
        owners.append(
            DisputeOwnerRow(
                owner_id=owner_id,
                case_count=len(ledger_cases),
                claim_count=len(ledger_claims),
                testimony_count=len(ledger_testimony),
                evidence_count=len(ledger_evidence),
                resolution_count=len(ledger_resolutions),
                pruned_count=pruned_count,
                coverage=coverage,
                first_tick=first_tick,
                last_tick=last_tick,
            )
        )
        for case in ledger_cases:
            cases.append(
                DisputeCaseRow(
                    owner_id=owner_id,
                    case_ref=_text(getattr(case, "case_ref", None)),
                    kind=_enum_value(getattr(case, "kind", None)),
                    subject_kind=_enum_value(getattr(case, "subject_kind", None)),
                    subject_token=_text(getattr(case, "subject_token", None)),
                    status=_enum_value(getattr(case, "status", None)),
                    party_ids=_optional_tokens(getattr(case, "party_ids", ()) or ()),
                    first_tick=_tick(getattr(case, "first_tick", None)),
                    last_tick=_tick(getattr(case, "last_tick", None)),
                    coverage=coverage,
                )
            )
        for claim in ledger_claims:
            claim_evidence = tuple(getattr(claim, "evidence_ids", ()) or ())
            claims.append(
                DisputeClaimRow(
                    owner_id=owner_id,
                    case_ref=_text(getattr(claim, "case_ref", None)),
                    claim_ref=_text(getattr(claim, "claim_ref", None)),
                    claimant_id=_text(getattr(claim, "claimant_id", None)),
                    respondent_id=_text(getattr(claim, "respondent_id", None)),
                    role=_enum_value(getattr(claim, "role", None)),
                    claim_kind=_enum_value(getattr(claim, "claim_kind", None)),
                    polarity=_enum_value(getattr(claim, "polarity", None)),
                    subject_token=_text(getattr(claim, "subject_token", None)),
                    counters_claim_ref=_opt_text(
                        getattr(claim, "counters_claim_ref", None)
                    ),
                    evidence_count=len(claim_evidence),
                    first_tick=_tick(getattr(claim, "first_tick", None)),
                    last_tick=_tick(getattr(claim, "last_tick", None)),
                )
            )
        for item in ledger_testimony:
            testimony.append(
                DisputeTestimonyRow(
                    owner_id=owner_id,
                    case_ref=_text(getattr(item, "case_ref", None)),
                    claim_ref=_text(getattr(item, "claim_ref", None)),
                    testimony_ref=_text(getattr(item, "testimony_id", None)),
                    speaker_id=_text(getattr(item, "speaker_id", None)),
                    channel=_enum_value(getattr(item, "channel", None)),
                    root_ref=_text(getattr(item, "root_ref", None)),
                    independently_evidenced=_flag(
                        getattr(item, "independently_evidenced", None)
                    ),
                    tick=_tick(getattr(item, "tick", None)),
                )
            )
        for item in ledger_evidence:
            evidence.append(
                DisputeEvidenceRow(
                    owner_id=owner_id,
                    case_ref=_text(getattr(item, "case_ref", None)),
                    claim_ref=_text(getattr(item, "claim_ref", None)),
                    evidence_ref=_text(getattr(item, "evidence_id", None)),
                    channel=_enum_value(getattr(item, "channel", None)),
                    reference_kind=_enum_value(getattr(item, "reference_kind", None)),
                    reference_id=_text(getattr(item, "reference_id", None)),
                    tick=_tick(getattr(item, "tick", None)),
                    independently_evidenced=_flag(
                        getattr(item, "independently_evidenced", None)
                    ),
                )
            )
        for item in getattr(ledger, "rule_references", ()) or ():
            rule_references.append(
                DisputeRuleReferenceRow(
                    owner_id=owner_id,
                    case_ref=_text(getattr(item, "case_ref", None)),
                    claim_ref=_text(getattr(item, "claim_ref", None)),
                    rule_reference_ref=_text(getattr(item, "rule_reference_id", None)),
                    system_ref=_text(getattr(item, "system_ref", None)),
                    rule_ref=_text(getattr(item, "rule_id", None)),
                    version_number=_tick(getattr(item, "version_number", None)),
                    applicability=_enum_value(getattr(item, "applicability", None)),
                    interpretation=_enum_value(getattr(item, "interpretation", None)),
                    status=_enum_value(getattr(item, "status", None)),
                )
            )
        for item in getattr(ledger, "authority_references", ()) or ():
            authority_references.append(
                DisputeAuthorityReferenceRow(
                    owner_id=owner_id,
                    case_ref=_text(getattr(item, "case_ref", None)),
                    authority_ref=_text(getattr(item, "authority_reference_id", None)),
                    authority_kind=_enum_value(getattr(item, "authority_kind", None)),
                    reference_id=_text(getattr(item, "reference_id", None)),
                    strength=float(getattr(item, "strength", 0.0)),
                    uncertainty=float(getattr(item, "uncertainty", 0.0)),
                    dissenting=_flag(getattr(item, "dissenting", None)),
                )
            )
        for item in getattr(ledger, "mediation_references", ()) or ():
            mediation_references.append(
                DisputeMediationReferenceRow(
                    owner_id=owner_id,
                    case_ref=_text(getattr(item, "case_ref", None)),
                    mediation_ref=_text(getattr(item, "mediation_reference_id", None)),
                    mediation_case_ref=_text(getattr(item, "mediation_case_ref", None)),
                    recommendation_ref=_opt_text(
                        getattr(item, "recommendation_ref", None)
                    ),
                    response_ref=_opt_text(getattr(item, "response_ref", None)),
                    outcome_ref=_opt_text(getattr(item, "outcome_ref", None)),
                    link_status=_enum_value(getattr(item, "link_status", None)),
                )
            )
        for item in ledger_resolutions:
            resolutions.append(
                DisputeResolutionRow(
                    owner_id=owner_id,
                    case_ref=_text(getattr(item, "case_ref", None)),
                    resolution_ref=_text(getattr(item, "resolution_ref", None)),
                    proposer_id=_text(getattr(item, "proposer_id", None)),
                    source=_enum_value(getattr(item, "source", None)),
                    terms_digest=_text(getattr(item, "terms_digest", None)),
                    status=_enum_value(getattr(item, "status", None)),
                    first_tick=_tick(getattr(item, "first_tick", None)),
                    last_tick=_tick(getattr(item, "last_tick", None)),
                    expires_tick=_optional_int(getattr(item, "expires_tick", None)),
                )
            )
        for item in getattr(ledger, "resolution_responses", ()) or ():
            responses.append(
                DisputeResolutionResponseRow(
                    owner_id=owner_id,
                    case_ref=_text(getattr(item, "case_ref", None)),
                    resolution_ref=_text(getattr(item, "resolution_ref", None)),
                    response_ref=_text(getattr(item, "response_id", None)),
                    party_id=_text(getattr(item, "party_id", None)),
                    kind=_enum_value(getattr(item, "kind", None)),
                    tick=_tick(getattr(item, "tick", None)),
                    terms_digest=_text(getattr(item, "terms_digest", None)),
                    active=_flag(getattr(item, "active", None)),
                )
            )
    rows = DisputeHarvestRows(
        owners=_ordered(owners, lambda row: (row.owner_id,)),
        cases=_ordered(cases, lambda row: (row.owner_id, row.case_ref)),
        claims=_ordered(claims, lambda row: (row.owner_id, row.claim_ref)),
        testimony=_ordered(testimony, lambda row: (row.owner_id, row.testimony_ref)),
        evidence=_ordered(evidence, lambda row: (row.owner_id, row.evidence_ref)),
        rule_references=_ordered(
            rule_references,
            lambda row: (row.owner_id, row.rule_reference_ref),
        ),
        authority_references=_ordered(
            authority_references,
            lambda row: (row.owner_id, row.authority_ref),
        ),
        mediation_references=_ordered(
            mediation_references,
            lambda row: (row.owner_id, row.mediation_ref),
        ),
        resolutions=_ordered(
            resolutions, lambda row: (row.owner_id, row.resolution_ref)
        ),
        responses=_ordered(responses, lambda row: (row.owner_id, row.response_ref)),
        window_ticks=window_ticks,
    )
    _LOG.debug(
        "dispute_harvest owners=%s cases=%s claims=%s testimony=%s",
        len(rows.owners),
        len(rows.cases),
        len(rows.claims),
        len(rows.testimony),
    )
    return rows
