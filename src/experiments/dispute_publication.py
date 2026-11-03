"""The only bridge from detached dispute analysis to the published artifact."""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any, Final, cast

from experiments.dispute_harvest import DisputeHarvest
from simulation.dispute_codec import (
    compute_dispute_publication_id,
    decode_dispute_snapshot,
    dispute_snapshot_digest,
    encode_dispute_snapshot,
    finalize_dispute_snapshot,
)
from simulation.dispute_models import (
    DISPUTE_PUBLICATION_ID_PREFIX,
    MAX_DISPUTE_CANDIDATES,
    MAX_DISPUTE_CASES,
    MAX_DISPUTE_CLAIMS,
    MAX_DISPUTE_CLAIMS_PER_CANDIDATE,
    MAX_DISPUTE_OBJECTIVE_ROWS,
    MAX_DISPUTE_RESOLUTIONS,
    MAX_DISPUTE_RESOLUTIONS_PER_CANDIDATE,
    MAX_DISPUTE_WINDOWS,
    DisputeArtifactError,
    DisputeAuthorityReferenceRecord,
    DisputeCandidateRecord,
    DisputeCaseRecord,
    DisputeClaimRecord,
    DisputeCounts,
    DisputeCoverage,
    DisputeEvidenceRecord,
    DisputeLineageEdgeRecord,
    DisputeMediationReferenceRecord,
    DisputeObjectiveRow,
    DisputeResolutionRecord,
    DisputeResolutionResponseRecord,
    DisputeRuleReferenceRecord,
    DisputeSnapshot,
    DisputeSnapshotRef,
    DisputeTestimonyRecord,
    DisputeWindowRecord,
    derive_dispute_authority_reference_id,
    derive_dispute_case_ref,
    derive_dispute_claim_id,
    derive_dispute_edge_id,
    derive_dispute_evidence_id,
    derive_dispute_mediation_reference_id,
    derive_dispute_resolution_id,
    derive_dispute_response_id,
    derive_dispute_rule_reference_id,
    derive_dispute_testimony_id,
)
from simulation.dispute_ports import (
    DisputePublication,
    DisputePublicationPort,
)

_LOG: Final[logging.Logger] = logging.getLogger("experiments.dispute_publication")

_PLACEHOLDER_PUBLICATION_ID: Final[str] = f"{DISPUTE_PUBLICATION_ID_PREFIX}{'0' * 16}"
_PLACEHOLDER_DIGEST: Final[str] = "0" * 64

_DISPUTE_KINDS: Final[frozenset[str]] = frozenset(
    {
        "contested_debt",
        "ownership_claim",
        "contract_interpretation",
        "injury",
        "broken_promise",
        "resource_appropriation",
        "other",
    }
)
_SUBJECT_KINDS: Final[frozenset[str]] = frozenset(
    {
        "commitment",
        "item",
        "resource",
        "action",
        "record",
        "relationship",
        "unspecified",
    }
)
_CASE_STATUSES: Final[frozenset[str]] = frozenset(
    {
        "open",
        "evidence_gathering",
        "rule_cited",
        "mediation_referenced",
        "resolution_proposed",
        "contested",
        "apparently_resolved",
        "withdrawn",
        "abandoned",
        "reopened",
        "expired",
    }
)
_CASE_STATUS_RANK: Final[dict[str, int]] = {
    "contested": 0,
    "resolution_proposed": 1,
    "mediation_referenced": 2,
    "rule_cited": 3,
    "evidence_gathering": 4,
    "reopened": 5,
    "open": 6,
    "apparently_resolved": 7,
    "withdrawn": 8,
    "abandoned": 9,
    "expired": 10,
}
_CLAIM_ROLES: Final[frozenset[str]] = frozenset(
    {"claim", "counterclaim", "supplementary"}
)
_CLAIM_KINDS: Final[frozenset[str]] = frozenset(
    {
        "debt_owed",
        "item_owned",
        "term_meaning",
        "harm_caused",
        "promise_broken",
        "resource_taken",
        "other",
    }
)
_POLARITIES: Final[frozenset[str]] = frozenset({"affirm", "deny", "uncertain"})
_TESTIMONY_CHANNELS: Final[frozenset[str]] = frozenset({"direct", "communicated"})
_EVIDENCE_CHANNELS: Final[frozenset[str]] = frozenset(
    {"observed", "communicated", "remembered", "recorded", "derived", "unknown"}
)
_EVIDENCE_REFERENCE_KINDS: Final[frozenset[str]] = frozenset(
    {
        "observed_occurrence",
        "observed_communication",
        "memory_trace",
        "reconstructed_memory",
        "artifact",
        "durable_record",
        "repository_entry",
        "commitment",
        "valuation",
        "mediation_record",
        "rule_record",
        "office_record",
        "institution_record",
        "organization_record",
        "unknown",
    }
)
_RULE_APPLICABILITIES: Final[frozenset[str]] = frozenset(
    {"applies", "does_not_apply", "uncertain"}
)
_RULE_INTERPRETATIONS: Final[frozenset[str]] = frozenset(
    {"literal", "narrow", "broad", "custom", "unknown"}
)
_RULE_STATUSES: Final[frozenset[str]] = frozenset(
    {"resolved", "orphaned", "version_mismatch", "contested", "retired"}
)
_AUTHORITY_KINDS: Final[frozenset[str]] = frozenset(
    {
        "self",
        "office",
        "institution",
        "organization",
        "collective_decision",
        "procedure",
        "written_record",
        "custom",
        "unknown",
    }
)
_MEDIATION_LINK_STATUSES: Final[frozenset[str]] = frozenset(
    {"linked", "stale", "orphaned", "disputed"}
)
_RESOLUTION_SOURCES: Final[frozenset[str]] = frozenset(
    {"negotiated", "mediator", "unilateral", "custom", "unknown"}
)
_RESOLUTION_STATUSES: Final[frozenset[str]] = frozenset(
    {
        "proposed",
        "partially_accepted",
        "apparently_accepted",
        "contested",
        "withdrawn",
        "expired",
        "superseded",
    }
)
_RESPONSE_KINDS: Final[frozenset[str]] = frozenset(
    {"accept", "reject", "counterpropose", "defer", "withdraw"}
)
_CANDIDATE_STATUSES: Final[frozenset[str]] = frozenset(
    {
        "emerging",
        "active",
        "contested",
        "fragmented",
        "apparently_resolved",
        "dissolved",
        "unknown",
    }
)

# Only opaque, non-owner-local, non-foreign-context tokens are published.
_FORBIDDEN_TOKEN_PREFIXES: Final[tuple[str, ...]] = (
    "dsc-",
    "dcl-",
    "dts-",
    "dev-",
    "drf-",
    "dmr-",
    "dar-",
    "drs-",
    "drp-",
    "frule-",
    "frul-",
    "fruv-",
    "frl-",
    "frs-",
    "frv-",
    "org-",
    "orgop-",
    "orgc-",
    "msoc-",
    "off-",
    "inst-",
    "med-",
    "evt-",
    "mem-",
    "art-",
    "rec-",
    "repo-",
    "cmt-",
    "val-",
)


def _fail(code: str = "dispute_invalid_value") -> None:
    raise DisputeArtifactError(code)


def _digest(namespace: str, *parts: str) -> str:
    return hashlib.sha256("\x1f".join((namespace, *parts)).encode("utf-8")).hexdigest()


def _public_token(namespace: str, value: str) -> str:
    if not value:
        _fail()
    if value.startswith(_FORBIDDEN_TOKEN_PREFIXES):
        return _digest(namespace, value)
    return value


def _public_subject(value: str) -> str:
    return _public_token("dispute-published-subject", value)


def _public_party(value: str) -> str:
    return _public_token("dispute-published-party", value)


def _enum(value: object, allowed: frozenset[str], default: str) -> str:
    token = getattr(value, "value", value)
    if isinstance(token, str) and token in allowed:
        return token
    return default


def _int(value: object, default: int = 0) -> int:
    if type(value) is int and not isinstance(value, bool) and value >= 0:
        return value
    return default


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    return _int(value)


def _unit(value: object) -> float:
    if type(value) is int and not isinstance(value, bool):
        number = float(value)
    elif type(value) is float:
        number = value
    else:
        return 0.0
    if number != number or number in (float("inf"), float("-inf")):
        return 0.0
    if number < 0.0:
        return 0.0
    if number > 1.0:
        return 1.0
    return number


def _coverage(value: object, *, note: str = "") -> DisputeCoverage:
    item = cast(Any, value)
    return DisputeCoverage(
        observed=_int(getattr(item, "observed", 0)),
        expected=_int(getattr(item, "expected", 0)),
        ratio=None,
        note=note,
    )


@dataclass(slots=True)
class _CaseDraft:
    case_ref: str
    subject_token: str
    party_ids: tuple[str, ...]
    kinds: list[str]
    subject_kinds: list[str]
    statuses: list[str]
    first_tick: int
    last_tick: int
    complete: bool = True


@dataclass(slots=True)
class _ClaimDraft:
    owner_id: str
    owner_claim_ref: str
    case_ref: str
    claim_id: str
    claimant_id: str
    respondent_id: str
    role: str
    claim_kind: str
    polarity: str
    subject_token: str
    counters_claim_ref: str | None
    first_tick: int
    last_tick: int
    candidate_id: str = ""


@dataclass(slots=True)
class _ResolutionDraft:
    owner_id: str
    owner_resolution_ref: str
    resolution_ref: str
    resolution_id: str
    case_ref: str
    proposer_id: str
    source: str
    terms_digest: str
    status: str
    first_tick: int
    last_tick: int
    expires_tick: int | None
    candidate_id: str = ""


@dataclass(frozen=True, slots=True)
class DisputeHarvestResult:
    harvest: DisputeHarvest
    snapshot: DisputeSnapshot
    receipt: dict[str, object]
    published: bool


def _case_drafts(
    harvest: DisputeHarvest,
) -> tuple[dict[str, _CaseDraft], dict[tuple[str, str], str], dict[str, str]]:
    cases: dict[str, _CaseDraft] = {}
    by_owner_ref: dict[tuple[str, str], str] = {}
    by_ref: dict[str, str] = {}
    for row in harvest.rows.cases:
        owner = row.owner_id
        subject = _public_subject(row.subject_token)
        parties = tuple(sorted({_public_party(party) for party in row.party_ids}))
        if not parties:
            continue
        case_ref = derive_dispute_case_ref(subject, parties)
        draft = cases.get(case_ref)
        if draft is None:
            draft = _CaseDraft(
                case_ref=case_ref,
                subject_token=subject,
                party_ids=parties,
                kinds=[],
                subject_kinds=[],
                statuses=[],
                first_tick=row.first_tick,
                last_tick=row.last_tick,
            )
            cases[case_ref] = draft
        draft.first_tick = min(draft.first_tick, row.first_tick)
        draft.last_tick = max(draft.last_tick, row.last_tick)
        draft.kinds.append(row.kind)
        draft.subject_kinds.append(row.subject_kind)
        draft.statuses.append(row.status)
        draft.complete = draft.complete and row.coverage == "complete"
        by_owner_ref[(owner, row.case_ref)] = case_ref
        by_ref.setdefault(row.case_ref, case_ref)
    return cases, by_owner_ref, by_ref


def _kind_token(value: object) -> str:
    token = getattr(value, "value", value)
    return token if isinstance(token, str) else "other"


def _case_kind(kinds: Sequence[str]) -> str:
    for kind in sorted({_kind_token(item) for item in kinds}):
        if kind != "other" and kind in _DISPUTE_KINDS:
            return kind
    return "other"


def _case_subject_kind(kinds: Sequence[str]) -> str:
    for kind in sorted({_kind_token(item) for item in kinds}):
        if kind in _SUBJECT_KINDS:
            return kind
    return "unspecified"


def _case_status(statuses: Sequence[str]) -> str:
    valid = [
        token
        for token in (_kind_token(item) for item in statuses)
        if token in _CASE_STATUSES
    ]
    if not valid:
        return "open"
    return min(valid, key=lambda status: _CASE_STATUS_RANK.get(status, 99))


def _claim_drafts(
    harvest: DisputeHarvest,
    cases: dict[str, _CaseDraft],
    case_by_owner_ref: dict[tuple[str, str], str],
    case_by_ref: dict[str, str],
) -> tuple[dict[str, _ClaimDraft], dict[tuple[str, str], str], dict[str, str]]:
    drafts: dict[str, _ClaimDraft] = {}
    by_owner_ref: dict[tuple[str, str], str] = {}
    by_ref: dict[str, str] = {}
    pending: list[tuple[_ClaimDraft, str]] = []
    for row in harvest.rows.claims:
        owner = row.owner_id
        case_ref = case_by_owner_ref.get((owner, row.case_ref)) or case_by_ref.get(
            row.case_ref
        )
        if case_ref is None:
            continue
        case = cases[case_ref]
        subject = _public_subject(row.subject_token) or case.subject_token
        claimant = _public_party(row.claimant_id)
        respondent = _public_party(row.respondent_id)
        role = _enum(row.role, _CLAIM_ROLES, "claim")
        claim_kind = _enum(row.claim_kind, _CLAIM_KINDS, "other")
        polarity = _enum(row.polarity, _POLARITIES, "uncertain")
        claim_id = derive_dispute_claim_id(
            case_ref, claimant, role, claim_kind, subject, None
        )
        existing = drafts.get(claim_id)
        if existing is None:
            draft = _ClaimDraft(
                owner_id=owner,
                owner_claim_ref=row.claim_ref,
                case_ref=case_ref,
                claim_id=claim_id,
                claimant_id=claimant,
                respondent_id=respondent,
                role=role,
                claim_kind=claim_kind,
                polarity=polarity,
                subject_token=subject,
                counters_claim_ref=None,
                first_tick=row.first_tick,
                last_tick=row.last_tick,
            )
            drafts[claim_id] = draft
            existing = draft
            if row.counters_claim_ref:
                pending.append((draft, row.counters_claim_ref))
        by_owner_ref[(owner, row.claim_ref)] = existing.claim_id
        by_ref.setdefault(row.claim_ref, existing.claim_id)
    for draft, countered_ref in sorted(
        pending, key=lambda item: (item[0].case_ref, item[1])
    ):
        target = by_owner_ref.get((draft.owner_id, countered_ref)) or by_ref.get(
            countered_ref
        )
        if target is None or target == draft.claim_id:
            continue
        counter_id = derive_dispute_claim_id(
            draft.case_ref,
            draft.claimant_id,
            draft.role,
            draft.claim_kind,
            draft.subject_token,
            target,
        )
        if counter_id == draft.claim_id or counter_id in drafts:
            continue
        del drafts[draft.claim_id]
        draft.claim_id = counter_id
        draft.counters_claim_ref = target
        drafts[counter_id] = draft
        by_owner_ref[(draft.owner_id, draft.owner_claim_ref)] = counter_id
        by_ref[draft.owner_claim_ref] = counter_id
    return drafts, by_owner_ref, by_ref


def _candidate_claim_map(
    harvest: DisputeHarvest,
    drafts: dict[str, _ClaimDraft],
    case_by_owner_ref: dict[tuple[str, str], str],
    case_by_ref: dict[str, str],
) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for candidate in sorted(
        harvest.analysis.candidates, key=lambda item: item.candidate_key
    ):
        owners = set(candidate.owner_ids)
        refs = set(candidate.claim_refs)
        case_refs = {
            case_ref
            for (owner, owner_ref), case_ref in case_by_owner_ref.items()
            if owner in owners and owner_ref in refs
        }
        case_refs.update(
            case_by_ref[ref] for ref in candidate.case_refs if ref in case_by_ref
        )
        for claim_id, draft in drafts.items():
            if draft.owner_id in owners and draft.owner_claim_ref in refs:
                mapping.setdefault(claim_id, candidate.candidate_key)
            elif draft.case_ref in case_refs:
                mapping.setdefault(claim_id, candidate.candidate_key)
    return mapping


def _select_claims(
    harvest: DisputeHarvest,
    drafts: dict[str, _ClaimDraft],
    candidate_map: dict[str, str],
    kept_candidates: set[str],
    *,
    max_claims: int,
) -> tuple[list[_ClaimDraft], bool]:
    if len(drafts) > MAX_DISPUTE_CLAIMS:
        _fail("dispute_size_limit")
    truncated = False
    ordered = sorted(drafts.values(), key=lambda item: item.claim_id)
    for draft in ordered:
        desired = draft.candidate_id or candidate_map.get(draft.claim_id, "")
        draft.candidate_id = desired if desired in kept_candidates else ""
    if len(ordered) > max_claims:
        ordered = ordered[:max_claims]
        truncated = True
    grouped: dict[str, list[_ClaimDraft]] = {}
    ungrouped: list[_ClaimDraft] = []
    for draft in ordered:
        if draft.candidate_id:
            grouped.setdefault(draft.candidate_id, []).append(draft)
        else:
            ungrouped.append(draft)
    selected: list[_ClaimDraft] = []
    for candidate_id in sorted(grouped):
        items = sorted(grouped[candidate_id], key=lambda item: item.claim_id)
        if len(items) > MAX_DISPUTE_CLAIMS_PER_CANDIDATE:
            items = items[:MAX_DISPUTE_CLAIMS_PER_CANDIDATE]
            truncated = True
        selected.extend(items)
    selected.extend(ungrouped)
    selected.sort(key=lambda item: item.claim_id)
    return selected, truncated


def _claim_records(
    harvest: DisputeHarvest,
    claims: Sequence[_ClaimDraft],
    claim_by_owner_ref: dict[tuple[str, str], str],
    claim_by_ref: dict[str, str],
) -> tuple[
    list[DisputeTestimonyRecord],
    list[DisputeEvidenceRecord],
    list[DisputeRuleReferenceRecord],
    dict[str, int],
]:
    claim_by_id = {claim.claim_id: claim for claim in claims}
    testimony: dict[str, DisputeTestimonyRecord] = {}
    evidence: dict[str, DisputeEvidenceRecord] = {}
    rules: dict[str, DisputeRuleReferenceRecord] = {}
    evidence_per_claim: dict[str, int] = {}
    for testimony_row in harvest.rows.testimony:
        claim_id = claim_by_owner_ref.get(
            (testimony_row.owner_id, testimony_row.claim_ref)
        ) or claim_by_ref.get(testimony_row.claim_ref)
        claim = claim_by_id.get(claim_id) if claim_id is not None else None
        if claim is None:
            continue
        channel = _enum(testimony_row.channel, _TESTIMONY_CHANNELS, "communicated")
        root_token = _digest("dispute-published-testimony-root", testimony_row.root_ref)
        testimony_id = derive_dispute_testimony_id(
            claim.case_ref,
            claim.claim_id,
            _public_party(testimony_row.speaker_id),
            channel,
            root_token,
            testimony_row.tick,
        )
        testimony.setdefault(
            testimony_id,
            DisputeTestimonyRecord(
                testimony_id=testimony_id,
                case_ref=claim.case_ref,
                claim_id=claim.claim_id,
                speaker_id=_public_party(testimony_row.speaker_id),
                channel=channel,
                root_token=root_token,
                independently_evidenced=bool(testimony_row.independently_evidenced),
                tick=testimony_row.tick,
            ),
        )
    for evidence_row in harvest.rows.evidence:
        claim_id = claim_by_owner_ref.get(
            (evidence_row.owner_id, evidence_row.claim_ref)
        ) or claim_by_ref.get(evidence_row.claim_ref)
        claim = claim_by_id.get(claim_id) if claim_id is not None else None
        if claim is None:
            continue
        channel = _enum(evidence_row.channel, _EVIDENCE_CHANNELS, "unknown")
        reference_kind = _enum(
            evidence_row.reference_kind, _EVIDENCE_REFERENCE_KINDS, "unknown"
        )
        reference_token = _digest(
            "dispute-published-evidence-reference",
            reference_kind,
            evidence_row.reference_id,
        )
        evidence_id = derive_dispute_evidence_id(
            claim.case_ref,
            claim.claim_id,
            channel,
            reference_kind,
            reference_token,
            evidence_row.tick,
        )
        evidence.setdefault(
            evidence_id,
            DisputeEvidenceRecord(
                evidence_id=evidence_id,
                case_ref=claim.case_ref,
                claim_id=claim.claim_id,
                channel=channel,
                reference_kind=reference_kind,
                reference_token=reference_token,
                tick=evidence_row.tick,
                independently_evidenced=bool(evidence_row.independently_evidenced),
            ),
        )
        evidence_per_claim[claim.claim_id] = (
            evidence_per_claim.get(claim.claim_id, 0) + 1
        )
    for rule_row in harvest.rows.rule_references:
        claim_id = claim_by_owner_ref.get(
            (rule_row.owner_id, rule_row.claim_ref)
        ) or claim_by_ref.get(rule_row.claim_ref)
        claim = claim_by_id.get(claim_id) if claim_id is not None else None
        if claim is None:
            continue
        system_token = _digest("dispute-published-rule-system", rule_row.system_ref)
        rule_token = _digest("dispute-published-rule", rule_row.rule_ref)
        rule_reference_id = derive_dispute_rule_reference_id(
            claim.case_ref,
            claim.claim_id,
            system_token,
            rule_token,
            rule_row.version_number,
        )
        rules.setdefault(
            rule_reference_id,
            DisputeRuleReferenceRecord(
                rule_reference_id=rule_reference_id,
                case_ref=claim.case_ref,
                claim_ref=claim.claim_id,
                system_token=system_token,
                rule_token=rule_token,
                version_number=max(1, _int(rule_row.version_number, 1)),
                applicability=_enum(
                    rule_row.applicability,
                    _RULE_APPLICABILITIES,
                    "uncertain",
                ),
                interpretation=_enum(
                    rule_row.interpretation,
                    _RULE_INTERPRETATIONS,
                    "unknown",
                ),
                status=_enum(rule_row.status, _RULE_STATUSES, "orphaned"),
            ),
        )
    return (
        [testimony[key] for key in sorted(testimony)],
        [evidence[key] for key in sorted(evidence)],
        [rules[key] for key in sorted(rules)],
        evidence_per_claim,
    )


def _resolution_drafts(
    harvest: DisputeHarvest,
    cases: dict[str, _CaseDraft],
    case_by_owner_ref: dict[tuple[str, str], str],
    case_by_ref: dict[str, str],
) -> tuple[
    dict[str, _ResolutionDraft],
    dict[tuple[str, str], _ResolutionDraft],
    dict[str, _ResolutionDraft],
]:
    drafts: dict[str, _ResolutionDraft] = {}
    by_owner_ref: dict[tuple[str, str], _ResolutionDraft] = {}
    by_ref: dict[str, _ResolutionDraft] = {}
    for row in harvest.rows.resolutions:
        owner = row.owner_id
        case_ref = case_by_owner_ref.get((owner, row.case_ref)) or case_by_ref.get(
            row.case_ref
        )
        if case_ref is None or case_ref not in cases:
            continue
        proposer = _public_party(row.proposer_id)
        terms_digest = _digest("dispute-published-resolution-terms", row.terms_digest)
        resolution_ref = _digest(
            "dispute-published-resolution-ref",
            case_ref,
            proposer,
            terms_digest,
        )
        resolution_id = derive_dispute_resolution_id(case_ref, proposer, terms_digest)
        draft = drafts.get(resolution_ref)
        if draft is None:
            draft = _ResolutionDraft(
                owner_id=owner,
                owner_resolution_ref=row.resolution_ref,
                resolution_ref=resolution_ref,
                resolution_id=resolution_id,
                case_ref=case_ref,
                proposer_id=proposer,
                source=_enum(row.source, _RESOLUTION_SOURCES, "unknown"),
                terms_digest=terms_digest,
                status=_enum(row.status, _RESOLUTION_STATUSES, "proposed"),
                first_tick=row.first_tick,
                last_tick=row.last_tick,
                expires_tick=_optional_int(row.expires_tick),
            )
            drafts[resolution_ref] = draft
        else:
            draft.first_tick = min(draft.first_tick, row.first_tick)
            draft.last_tick = max(draft.last_tick, row.last_tick)
            if draft.expires_tick is None:
                draft.expires_tick = _optional_int(row.expires_tick)
        by_owner_ref[(owner, row.resolution_ref)] = draft
        by_ref.setdefault(row.resolution_ref, draft)
    return drafts, by_owner_ref, by_ref


def _select_resolutions(
    harvest: DisputeHarvest,
    drafts: dict[str, _ResolutionDraft],
    candidate_case: dict[str, str],
    kept_candidates: set[str],
) -> tuple[list[_ResolutionDraft], bool]:
    if len(drafts) > MAX_DISPUTE_RESOLUTIONS:
        _fail("dispute_size_limit")
    truncated = False
    for draft in drafts.values():
        candidate_id = candidate_case.get(draft.case_ref, "")
        draft.candidate_id = candidate_id if candidate_id in kept_candidates else ""
    grouped: dict[str, list[_ResolutionDraft]] = {}
    ungrouped: list[_ResolutionDraft] = []
    for draft in sorted(drafts.values(), key=lambda item: item.resolution_id):
        if draft.candidate_id:
            grouped.setdefault(draft.candidate_id, []).append(draft)
        else:
            ungrouped.append(draft)
    selected: list[_ResolutionDraft] = []
    for candidate_id in sorted(grouped):
        items = sorted(grouped[candidate_id], key=lambda item: item.resolution_id)
        if len(items) > MAX_DISPUTE_RESOLUTIONS_PER_CANDIDATE:
            items = items[:MAX_DISPUTE_RESOLUTIONS_PER_CANDIDATE]
            truncated = True
        selected.extend(items)
    selected.extend(ungrouped)
    selected.sort(key=lambda item: item.resolution_id)
    return selected, truncated


def _resolution_records(
    harvest: DisputeHarvest,
    resolutions: Sequence[_ResolutionDraft],
    resolution_by_owner_ref: dict[tuple[str, str], _ResolutionDraft],
    resolution_by_ref: dict[str, _ResolutionDraft],
) -> tuple[
    list[DisputeResolutionRecord],
    list[DisputeResolutionResponseRecord],
]:
    resolution_by_id = {
        resolution.resolution_ref: resolution for resolution in resolutions
    }
    responses: dict[str, DisputeResolutionResponseRecord] = {}
    accepted: dict[str, int] = {}
    rejected: dict[str, int] = {}
    for row in harvest.rows.responses:
        resolution = resolution_by_owner_ref.get(
            (row.owner_id, row.resolution_ref)
        ) or resolution_by_ref.get(row.resolution_ref)
        if resolution is None:
            continue
        if resolution.resolution_ref not in resolution_by_id:
            continue
        party = _public_party(row.party_id)
        kind = _enum(row.kind, _RESPONSE_KINDS, "defer")
        active = bool(row.active)
        response_id = derive_dispute_response_id(
            resolution.resolution_ref,
            party,
            kind,
            row.tick,
            resolution.terms_digest,
        )
        responses.setdefault(
            response_id,
            DisputeResolutionResponseRecord(
                response_id=response_id,
                resolution_ref=resolution.resolution_ref,
                party_id=party,
                kind=kind,
                tick=row.tick,
                terms_digest=resolution.terms_digest,
                active=active,
            ),
        )
        if active and kind == "accept":
            accepted[resolution.resolution_ref] = (
                accepted.get(resolution.resolution_ref, 0) + 1
            )
        elif active and kind == "reject":
            rejected[resolution.resolution_ref] = (
                rejected.get(resolution.resolution_ref, 0) + 1
            )
    records = [
        DisputeResolutionRecord(
            resolution_id=resolution.resolution_id,
            resolution_ref=resolution.resolution_ref,
            case_ref=resolution.case_ref,
            proposer_id=resolution.proposer_id,
            source=resolution.source,
            terms_digest=resolution.terms_digest,
            status=resolution.status,
            first_tick=resolution.first_tick,
            last_tick=resolution.last_tick,
            expires_tick=resolution.expires_tick,
            accepted_party_count=accepted.get(resolution.resolution_ref, 0),
            rejected_party_count=rejected.get(resolution.resolution_ref, 0),
            candidate_id=resolution.candidate_id,
        )
        for resolution in resolutions
    ]
    return records, [responses[key] for key in sorted(responses)]


def _authority_records(
    harvest: DisputeHarvest,
    cases: dict[str, _CaseDraft],
    case_by_owner_ref: dict[tuple[str, str], str],
    case_by_ref: dict[str, str],
) -> list[DisputeAuthorityReferenceRecord]:
    records: dict[str, DisputeAuthorityReferenceRecord] = {}
    for row in harvest.rows.authority_references:
        case_ref = case_by_owner_ref.get(
            (row.owner_id, row.case_ref)
        ) or case_by_ref.get(row.case_ref)
        if case_ref is None or case_ref not in cases:
            continue
        authority_kind = _enum(row.authority_kind, _AUTHORITY_KINDS, "unknown")
        reference_token = _digest(
            "dispute-published-authority-reference", row.reference_id
        )
        authority_reference_id = derive_dispute_authority_reference_id(
            case_ref, authority_kind, reference_token
        )
        records.setdefault(
            authority_reference_id,
            DisputeAuthorityReferenceRecord(
                authority_reference_id=authority_reference_id,
                case_ref=case_ref,
                authority_kind=authority_kind,
                reference_token=reference_token,
                strength=_unit(row.strength),
                uncertainty=_unit(row.uncertainty),
                dissenting=bool(row.dissenting),
            ),
        )
    return [records[key] for key in sorted(records)]


def _mediation_records(
    harvest: DisputeHarvest,
    cases: dict[str, _CaseDraft],
    case_by_owner_ref: dict[tuple[str, str], str],
    case_by_ref: dict[str, str],
) -> list[DisputeMediationReferenceRecord]:
    records: dict[str, DisputeMediationReferenceRecord] = {}
    for row in harvest.rows.mediation_references:
        case_ref = case_by_owner_ref.get(
            (row.owner_id, row.case_ref)
        ) or case_by_ref.get(row.case_ref)
        if case_ref is None or case_ref not in cases:
            continue
        case_token = _digest("dispute-published-mediation-case", row.mediation_case_ref)
        recommendation = (
            None
            if row.recommendation_ref is None
            else _digest(
                "dispute-published-mediation-recommendation",
                row.recommendation_ref,
            )
        )
        response = (
            None
            if row.response_ref is None
            else _digest("dispute-published-mediation-response", row.response_ref)
        )
        outcome = (
            None
            if row.outcome_ref is None
            else _digest("dispute-published-mediation-outcome", row.outcome_ref)
        )
        mediation_reference_id = derive_dispute_mediation_reference_id(
            case_ref, case_token
        )
        records.setdefault(
            mediation_reference_id,
            DisputeMediationReferenceRecord(
                mediation_reference_id=mediation_reference_id,
                case_ref=case_ref,
                mediation_case_token=case_token,
                recommendation_token=recommendation,
                response_token=response,
                outcome_token=outcome,
                link_status=_enum(
                    row.link_status, _MEDIATION_LINK_STATUSES, "orphaned"
                ),
            ),
        )
    return [records[key] for key in sorted(records)]


def _candidate_case_refs(
    candidate: object,
    case_by_owner_ref: dict[tuple[str, str], str],
    case_by_ref: dict[str, str],
) -> set[str]:
    item = cast(Any, candidate)
    owners = set(getattr(item, "owner_ids", ()))
    refs = set(getattr(item, "case_refs", ()))
    found = {
        case_ref
        for (owner, owner_ref), case_ref in case_by_owner_ref.items()
        if owner in owners and owner_ref in refs
    }
    found.update(case_by_ref[ref] for ref in refs if ref in case_by_ref)
    return found


def _candidate_records(
    harvest: DisputeHarvest,
    kept_candidates: Sequence[object],
    claims: Sequence[_ClaimDraft],
    resolutions: Sequence[_ResolutionDraft],
    testimony: Sequence[DisputeTestimonyRecord],
    evidence: Sequence[DisputeEvidenceRecord],
    case_by_owner_ref: dict[tuple[str, str], str],
    case_by_ref: dict[str, str],
) -> list[DisputeCandidateRecord]:
    records: list[DisputeCandidateRecord] = []
    for candidate in kept_candidates:
        item = cast(Any, candidate)
        candidate_id = item.candidate_key
        candidate_claims = [
            claim for claim in claims if claim.candidate_id == candidate_id
        ]
        candidate_resolutions = [
            resolution
            for resolution in resolutions
            if resolution.candidate_id == candidate_id
        ]
        claim_ids = {claim.claim_id for claim in candidate_claims}
        case_refs = _candidate_case_refs(candidate, case_by_owner_ref, case_by_ref)
        records.append(
            DisputeCandidateRecord(
                candidate_id=candidate_id,
                kind=_case_kind([item.kind]),
                subject_token=_public_subject(item.subject_token),
                party_count=len(item.party_ids),
                owner_count=len(item.owner_ids),
                case_count=len(case_refs),
                claim_count=len(candidate_claims),
                counterclaim_count=sum(
                    1 for claim in candidate_claims if claim.role == "counterclaim"
                ),
                testimony_count=sum(
                    1 for row in testimony if row.claim_id in claim_ids
                ),
                evidence_count=sum(1 for row in evidence if row.claim_id in claim_ids),
                resolution_count=len(candidate_resolutions),
                disagreement_count=_int(item.disagreement_count),
                status=_enum(item.status, _CANDIDATE_STATUSES, "unknown"),
                first_tick=item.first_tick,
                last_tick=item.last_tick,
                coverage=_coverage(item.coverage),
            )
        )
    return records


def _window_records(harvest: DisputeHarvest) -> tuple[list[DisputeWindowRecord], bool]:
    candidate_counts = {
        (window.start_tick, window.end_tick): len(window.candidates)
        for window in harvest.analysis.windows
    }
    ordered = sorted(
        harvest.windows, key=lambda window: (window.start_tick, window.end_tick)
    )
    truncated = len(ordered) > MAX_DISPUTE_WINDOWS
    records = [
        DisputeWindowRecord(
            start_tick=window.start_tick,
            end_tick=window.end_tick,
            owner_count=window.owner_count,
            candidate_count=candidate_counts.get(
                (window.start_tick, window.end_tick), 0
            ),
            claim_count=window.claim_count,
        )
        for window in ordered[:MAX_DISPUTE_WINDOWS]
    ]
    return records, truncated


def _objective_records(
    harvest: DisputeHarvest,
) -> tuple[list[DisputeObjectiveRow], bool]:
    ordered = sorted(harvest.layers.objective, key=lambda row: row.tick)
    truncated = len(ordered) > MAX_DISPUTE_OBJECTIVE_ROWS
    return (
        [
            DisputeObjectiveRow(
                tick=row.tick,
                observed_occurrence_count=row.observed_occurrence_count,
                observed_transfer_count=row.observed_transfer_count,
                observed_harm_count=row.observed_harm_count,
                observed_commitment_count=row.observed_commitment_count,
                observed_record_count=row.observed_record_count,
                observed_communication_count=row.observed_communication_count,
            )
            for row in ordered[:MAX_DISPUTE_OBJECTIVE_ROWS]
        ],
        truncated,
    )


def _lineage_records(
    harvest: DisputeHarvest,
    candidate_ids: set[str],
) -> tuple[list[DisputeLineageEdgeRecord], bool]:
    records: list[DisputeLineageEdgeRecord] = []
    dropped = False
    for edge in sorted(harvest.analysis.edges, key=lambda item: item.edge_id):
        if edge.source not in candidate_ids or edge.target not in candidate_ids:
            dropped = True
            continue
        records.append(
            DisputeLineageEdgeRecord(
                edge_id=derive_dispute_edge_id(
                    edge.source, edge.target, edge.kind.value, edge.tick
                ),
                source=edge.source,
                target=edge.target,
                kind=edge.kind.value,
                tick=edge.tick,
            )
        )
    return records, dropped


def build_dispute_harvest_result(
    harvest: DisputeHarvest,
    *,
    max_candidates: int = MAX_DISPUTE_CANDIDATES,
    max_claims: int = MAX_DISPUTE_CLAIMS,
) -> DisputeHarvestResult:
    """Map detached dispute analysis into one canonical immutable snapshot."""
    if type(harvest) is not DisputeHarvest:
        raise TypeError("harvest must be DisputeHarvest")
    if type(max_candidates) is not int or max_candidates < 0:
        raise ValueError("max_candidates must be a non-negative integer")
    if type(max_claims) is not int or max_claims < 0:
        raise ValueError("max_claims must be a non-negative integer")

    cases, case_by_owner_ref, case_by_ref = _case_drafts(harvest)
    if len(cases) > MAX_DISPUTE_CASES:
        _fail("dispute_size_limit")
    claim_drafts, claim_by_owner_ref, claim_by_ref = _claim_drafts(
        harvest, cases, case_by_owner_ref, case_by_ref
    )
    candidate_map = _candidate_claim_map(
        harvest, claim_drafts, case_by_owner_ref, case_by_ref
    )
    analysis_candidates = sorted(
        harvest.analysis.candidates, key=lambda item: item.candidate_key
    )
    candidate_limit = min(max_candidates, MAX_DISPUTE_CANDIDATES)
    kept_candidates = analysis_candidates[:candidate_limit]
    kept_candidate_ids = {
        cast(Any, candidate).candidate_key for candidate in kept_candidates
    }
    truncated = len(analysis_candidates) > len(kept_candidates)

    claims, claim_cut = _select_claims(
        harvest,
        claim_drafts,
        candidate_map,
        kept_candidate_ids,
        max_claims=max_claims,
    )
    truncated = truncated or claim_cut
    claims = sorted(claims, key=lambda item: item.claim_id)
    final_claim_ids = {claim.claim_id for claim in claims}
    for claim in claims:
        if (
            claim.counters_claim_ref is not None
            and claim.counters_claim_ref not in final_claim_ids
        ):
            claim.counters_claim_ref = None

    testimony, evidence, rule_references, evidence_per_claim = _claim_records(
        harvest, claims, claim_by_owner_ref, claim_by_ref
    )

    resolution_drafts, resolution_by_owner_ref, resolution_by_ref = _resolution_drafts(
        harvest, cases, case_by_owner_ref, case_by_ref
    )
    case_candidate: dict[str, str] = {}
    for candidate in kept_candidates:
        candidate_id = cast(Any, candidate).candidate_key
        for case_ref in _candidate_case_refs(candidate, case_by_owner_ref, case_by_ref):
            case_candidate.setdefault(case_ref, candidate_id)
    resolutions, resolution_cut = _select_resolutions(
        harvest, resolution_drafts, case_candidate, kept_candidate_ids
    )
    truncated = truncated or resolution_cut
    resolution_records, responses = _resolution_records(
        harvest, resolutions, resolution_by_owner_ref, resolution_by_ref
    )

    authority_references = _authority_records(
        harvest, cases, case_by_owner_ref, case_by_ref
    )
    mediation_references = _mediation_records(
        harvest, cases, case_by_owner_ref, case_by_ref
    )
    candidate_records = _candidate_records(
        harvest,
        kept_candidates,
        claims,
        resolutions,
        testimony,
        evidence,
        case_by_owner_ref,
        case_by_ref,
    )
    window_records, window_cut = _window_records(harvest)
    objective_rows, objective_cut = _objective_records(harvest)
    lineage, lineage_cut = _lineage_records(harvest, kept_candidate_ids)
    truncated = truncated or window_cut or objective_cut or lineage_cut
    if harvest.truncation is not None:
        truncated = True

    case_records = [
        DisputeCaseRecord(
            case_ref=case.case_ref,
            kind=_case_kind(case.kinds),
            subject_kind=_case_subject_kind(case.subject_kinds),
            subject_token=case.subject_token,
            status=_case_status(case.statuses),
            party_ids=case.party_ids,
            first_tick=case.first_tick,
            last_tick=case.last_tick,
            coverage=DisputeCoverage(
                observed=1 if case.complete else 0,
                expected=1,
                ratio=None,
                note="" if case.complete else "partial",
            ),
        )
        for case in sorted(cases.values(), key=lambda item: item.case_ref)
    ]
    claim_records = [
        DisputeClaimRecord(
            claim_id=claim.claim_id,
            case_ref=claim.case_ref,
            claimant_id=claim.claimant_id,
            respondent_id=claim.respondent_id,
            role=claim.role,
            claim_kind=claim.claim_kind,
            polarity=claim.polarity,
            subject_token=claim.subject_token,
            counters_claim_ref=claim.counters_claim_ref,
            evidence_count=evidence_per_claim.get(claim.claim_id, 0),
            first_tick=claim.first_tick,
            last_tick=claim.last_tick,
            candidate_id=claim.candidate_id,
        )
        for claim in claims
    ]
    accepted_count = sum(
        1 for response in responses if response.active and response.kind == "accept"
    )
    rejected_count = sum(
        1 for response in responses if response.active and response.kind == "reject"
    )
    coverage_note = (
        "dispute_truncated"
        if truncated
        else "partial"
        if harvest.coverage.partial
        else ""
    )
    snapshot_coverage = DisputeCoverage(
        observed=harvest.coverage.observed,
        expected=harvest.coverage.expected,
        ratio=None,
        note=coverage_note,
    )
    if not candidate_records and not case_records and not claim_records:
        provenance = "truncated" if truncated else "empty"
    elif truncated:
        provenance = "truncated"
    elif harvest.coverage.partial:
        provenance = "partial"
    else:
        provenance = "ok"
    counts = DisputeCounts(
        candidate_count=len(candidate_records),
        case_count=len(case_records),
        claim_count=len(claim_records),
        counterclaim_count=sum(
            1 for claim in claim_records if claim.role == "counterclaim"
        ),
        testimony_count=len(testimony),
        evidence_count=len(evidence),
        resolution_count=len(resolution_records),
        accepted_count=accepted_count,
        rejected_count=rejected_count,
        owner_count=len(harvest.rows.owners),
        response_count=len(responses),
        edge_count=len(lineage),
        rule_reference_count=len(rule_references),
        authority_reference_count=len(authority_references),
        mediation_reference_count=len(mediation_references),
        objective_row_count=len(objective_rows),
        window_count=len(window_records),
    )
    snapshot = DisputeSnapshot(
        ref=DisputeSnapshotRef(
            run_id=harvest.run_id,
            input_revision=harvest.input_revision,
            generated_tick=harvest.generated_tick,
            publication_id=_PLACEHOLDER_PUBLICATION_ID,
            snapshot_digest=_PLACEHOLDER_DIGEST,
        ),
        coverage=snapshot_coverage,
        candidates=tuple(candidate_records),
        cases=tuple(case_records),
        claims=tuple(claim_records),
        testimony=tuple(testimony),
        evidence=tuple(evidence),
        rule_references=tuple(rule_references),
        authority_references=tuple(authority_references),
        mediation_references=tuple(mediation_references),
        resolutions=tuple(resolution_records),
        responses=tuple(responses),
        objective_rows=tuple(objective_rows),
        windows=tuple(window_records),
        lineage=tuple(lineage),
        counts=counts,
        provenance_code=provenance,
    )
    return _finalize(
        snapshot,
        harvest,
        truncated=truncated,
        empty=not case_records and not claim_records,
    )


def _finalize(
    snapshot: DisputeSnapshot,
    harvest: DisputeHarvest,
    *,
    truncated: bool,
    empty: bool,
) -> DisputeHarvestResult:
    publication_id = compute_dispute_publication_id(snapshot)
    published = replace(
        snapshot, ref=replace(snapshot.ref, publication_id=publication_id)
    )
    finalized = finalize_dispute_snapshot(published)
    payload = encode_dispute_snapshot(finalized)
    decoded = decode_dispute_snapshot(payload)
    if encode_dispute_snapshot(decoded) != payload:
        _fail("dispute_digest_mismatch")
    if dispute_snapshot_digest(payload) != finalized.ref.snapshot_digest:
        _fail("dispute_digest_mismatch")
    if empty:
        status = "empty"
        reason_code: str | None = None
    elif truncated:
        status = "published"
        reason_code = "dispute_truncated"
    else:
        status = "published"
        reason_code = "dispute_published"
    coverage = finalized.coverage
    receipt: dict[str, object] = {
        "run_id": finalized.ref.run_id,
        "publication_id": publication_id,
        "snapshot_digest": finalized.ref.snapshot_digest,
        "generated_tick": finalized.ref.generated_tick,
        "candidate_count": len(finalized.candidates),
        "case_count": len(finalized.cases),
        "claim_count": len(finalized.claims),
        "resolution_count": len(finalized.resolutions),
        "coverage": {
            "observed": coverage.observed,
            "expected": coverage.expected,
            "ratio": coverage.ratio,
            "note": coverage.note,
        },
        "status": status,
        "reason_code": reason_code,
    }
    _LOG.info(
        "dispute_publication status=%s candidates=%s bytes=%s",
        status,
        len(finalized.candidates),
        len(payload),
    )
    return DisputeHarvestResult(
        harvest=harvest,
        snapshot=finalized,
        receipt=receipt,
        published=True,
    )


def publish_dispute_snapshot(
    result: DisputeHarvestResult,
    port: DisputePublicationPort,
) -> bool:
    """Publish one finalized snapshot through the injected port exactly once."""
    if type(result) is not DisputeHarvestResult:
        raise TypeError("result must be DisputeHarvestResult")
    payload = encode_dispute_snapshot(result.snapshot)
    returned = port.publish(
        DisputePublication(
            run_id=result.snapshot.ref.run_id,
            publication_id=result.snapshot.ref.publication_id,
            snapshot_digest=result.snapshot.ref.snapshot_digest,
            payload=payload,
            generated_tick=result.snapshot.ref.generated_tick,
        )
    )
    if isinstance(returned, str) and returned:
        result.receipt["publication_id"] = returned
    return True


def dispute_publication_document(
    result: DisputeHarvestResult,
) -> dict[str, object]:
    """Return a metadata-only publication receipt."""
    if type(result) is not DisputeHarvestResult:
        raise TypeError("result must be DisputeHarvestResult")
    return dict(result.receipt)


__all__ = [
    "DisputeHarvestResult",
    "build_dispute_harvest_result",
    "dispute_publication_document",
    "publish_dispute_snapshot",
]
