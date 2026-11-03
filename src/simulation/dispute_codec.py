"""Strict canonical codec for ``dispute-resolution-snapshot-v1``.

Encoding is non-circular: ``snapshot_digest`` is computed over the canonical
payload with the digest member removed, and the publication id is derived from a
normalized payload with both the publication id and digest replaced by
placeholders.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
from dataclasses import replace
from typing import Final, cast

from simulation.dispute_models import (
    DISPUTE_PUBLICATION_ID_PREFIX,
    MAX_DISPUTE_SNAPSHOT_BYTES,
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
)
from simulation.dispute_models import (
    DISPUTE_SNAPSHOT_SCHEMA as _SCHEMA,
)

__all__ = [
    "compute_dispute_publication_id",
    "decode_dispute_snapshot",
    "decode_dispute_value",
    "dispute_snapshot_digest",
    "encode_dispute_snapshot",
    "encode_dispute_value",
    "finalize_dispute_snapshot",
    "validate_dispute_value",
]

_LOG: Final[logging.Logger] = logging.getLogger("simulation.dispute_codec")

_SNAPSHOT_KEYS: Final[frozenset[str]] = frozenset(
    {
        "schema_version",
        "policy_version",
        "run_id",
        "input_revision",
        "generated_tick",
        "publication_id",
        "snapshot_digest",
        "coverage",
        "candidates",
        "cases",
        "claims",
        "testimony",
        "evidence",
        "rule_references",
        "authority_references",
        "mediation_references",
        "resolutions",
        "responses",
        "objective_rows",
        "windows",
        "lineage",
        "counts",
        "provenance_code",
    }
)
_COVERAGE_KEYS: Final[frozenset[str]] = frozenset(
    {"observed", "expected", "ratio", "note"}
)
_CANDIDATE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "candidate_id",
        "kind",
        "subject_token",
        "party_count",
        "owner_count",
        "case_count",
        "claim_count",
        "counterclaim_count",
        "testimony_count",
        "evidence_count",
        "resolution_count",
        "disagreement_count",
        "status",
        "first_tick",
        "last_tick",
        "coverage",
    }
)
_CASE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "case_ref",
        "kind",
        "subject_kind",
        "subject_token",
        "status",
        "party_ids",
        "first_tick",
        "last_tick",
        "coverage",
    }
)
_CLAIM_KEYS: Final[frozenset[str]] = frozenset(
    {
        "claim_id",
        "case_ref",
        "claimant_id",
        "respondent_id",
        "role",
        "claim_kind",
        "polarity",
        "subject_token",
        "counters_claim_ref",
        "evidence_count",
        "first_tick",
        "last_tick",
        "candidate_id",
    }
)
_TESTIMONY_KEYS: Final[frozenset[str]] = frozenset(
    {
        "testimony_id",
        "case_ref",
        "claim_id",
        "speaker_id",
        "channel",
        "root_token",
        "independently_evidenced",
        "tick",
    }
)
_EVIDENCE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "evidence_id",
        "case_ref",
        "claim_id",
        "channel",
        "reference_kind",
        "reference_token",
        "tick",
        "independently_evidenced",
    }
)
_RULE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "rule_reference_id",
        "case_ref",
        "claim_ref",
        "system_token",
        "rule_token",
        "version_number",
        "applicability",
        "interpretation",
        "status",
    }
)
_AUTHORITY_KEYS: Final[frozenset[str]] = frozenset(
    {
        "authority_reference_id",
        "case_ref",
        "authority_kind",
        "reference_token",
        "strength",
        "uncertainty",
        "dissenting",
    }
)
_MEDIATION_KEYS: Final[frozenset[str]] = frozenset(
    {
        "mediation_reference_id",
        "case_ref",
        "mediation_case_token",
        "recommendation_token",
        "response_token",
        "outcome_token",
        "link_status",
    }
)
_RESOLUTION_KEYS: Final[frozenset[str]] = frozenset(
    {
        "resolution_id",
        "resolution_ref",
        "case_ref",
        "proposer_id",
        "source",
        "terms_digest",
        "status",
        "first_tick",
        "last_tick",
        "expires_tick",
        "accepted_party_count",
        "rejected_party_count",
        "candidate_id",
    }
)
_RESPONSE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "response_id",
        "resolution_ref",
        "party_id",
        "kind",
        "tick",
        "terms_digest",
        "active",
    }
)
_OBJECTIVE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "tick",
        "observed_occurrence_count",
        "observed_transfer_count",
        "observed_harm_count",
        "observed_commitment_count",
        "observed_record_count",
        "observed_communication_count",
    }
)
_WINDOW_KEYS: Final[frozenset[str]] = frozenset(
    {"start_tick", "end_tick", "owner_count", "candidate_count", "claim_count"}
)
_EDGE_KEYS: Final[frozenset[str]] = frozenset(
    {"edge_id", "source", "target", "kind", "tick"}
)
_COUNTS_KEYS: Final[frozenset[str]] = frozenset(
    {
        "candidate_count",
        "case_count",
        "claim_count",
        "counterclaim_count",
        "testimony_count",
        "evidence_count",
        "resolution_count",
        "accepted_count",
        "rejected_count",
        "owner_count",
        "response_count",
        "edge_count",
        "rule_reference_count",
        "authority_reference_count",
        "mediation_reference_count",
        "objective_row_count",
        "window_count",
    }
)
_PLACEHOLDER_PUBLICATION_ID: Final[str] = f"{DISPUTE_PUBLICATION_ID_PREFIX}{'0' * 16}"
_PLACEHOLDER_DIGEST: Final[str] = "0" * 64


def _fail(code: str = "dispute_invalid_value") -> None:
    raise DisputeArtifactError(code)


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            _fail()
        result[key] = value
    return result


def _reject_constant(value: str) -> object:
    _ = value
    _fail()
    return None


def validate_dispute_value(value: object) -> object:
    """Require a JSON-safe finite value tree."""
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            _fail()
        return value
    if type(value) is list:
        return [validate_dispute_value(item) for item in value]
    if type(value) is dict:
        checked: dict[str, object] = {}
        for key, item in value.items():
            if type(key) is not str:
                _fail()
            checked[key] = validate_dispute_value(item)
        return checked
    _fail()
    return None


def encode_dispute_value(value: object) -> bytes:
    checked = validate_dispute_value(value)
    return json.dumps(
        checked,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def decode_dispute_value(payload: bytes) -> object:
    if not isinstance(payload, (bytes, bytearray)):
        _fail()
    try:
        text = bytes(payload).decode("utf-8")
    except UnicodeDecodeError:
        _fail()
    try:
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_constant,
        )
    except (json.JSONDecodeError, UnicodeDecodeError):
        _fail()
    return None


def _require_keys(value: object, keys: frozenset[str]) -> dict[str, object]:
    if not isinstance(value, dict):
        _fail()
    mapping = cast(dict[str, object], value)
    if set(mapping) != keys:
        _fail()
    return mapping


def _string(value: object) -> str:
    if not isinstance(value, str) or not value:
        _fail()
    return cast(str, value)


def _plain_string(value: object) -> str:
    if not isinstance(value, str):
        _fail()
    return cast(str, value)


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    return _string(value)


def _int(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        _fail()
    return cast(int, value)


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    return _int(value)


def _float(value: object) -> float:
    if type(value) not in (float, int) or isinstance(value, bool):
        _fail()
    number = float(cast(float, value))
    if not math.isfinite(number):
        _fail()
    return number


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    return _float(value)


def _bool(value: object) -> bool:
    if type(value) is not bool:
        _fail()
    return cast(bool, value)


def _list(value: object) -> list[object]:
    if type(value) is not list:
        _fail()
    return cast(list[object], value)


def _string_list(value: object) -> list[str]:
    return [_string(item) for item in _list(value)]


def _coverage_value(coverage: DisputeCoverage) -> dict[str, object]:
    return {
        "observed": coverage.observed,
        "expected": coverage.expected,
        "ratio": coverage.ratio,
        "note": coverage.note,
    }


def _counts_value(counts: DisputeCounts) -> dict[str, object]:
    return {
        "candidate_count": counts.candidate_count,
        "case_count": counts.case_count,
        "claim_count": counts.claim_count,
        "counterclaim_count": counts.counterclaim_count,
        "testimony_count": counts.testimony_count,
        "evidence_count": counts.evidence_count,
        "resolution_count": counts.resolution_count,
        "accepted_count": counts.accepted_count,
        "rejected_count": counts.rejected_count,
        "owner_count": counts.owner_count,
        "response_count": counts.response_count,
        "edge_count": counts.edge_count,
        "rule_reference_count": counts.rule_reference_count,
        "authority_reference_count": counts.authority_reference_count,
        "mediation_reference_count": counts.mediation_reference_count,
        "objective_row_count": counts.objective_row_count,
        "window_count": counts.window_count,
    }


def _snapshot_to_value(snapshot: DisputeSnapshot) -> dict[str, object]:
    return {
        "schema_version": snapshot.schema_version,
        "policy_version": snapshot.ref.policy_version,
        "run_id": snapshot.ref.run_id,
        "input_revision": snapshot.ref.input_revision,
        "generated_tick": snapshot.ref.generated_tick,
        "publication_id": snapshot.ref.publication_id,
        "snapshot_digest": snapshot.ref.snapshot_digest,
        "coverage": _coverage_value(snapshot.coverage),
        "candidates": [
            {
                "candidate_id": item.candidate_id,
                "kind": item.kind,
                "subject_token": item.subject_token,
                "party_count": item.party_count,
                "owner_count": item.owner_count,
                "case_count": item.case_count,
                "claim_count": item.claim_count,
                "counterclaim_count": item.counterclaim_count,
                "testimony_count": item.testimony_count,
                "evidence_count": item.evidence_count,
                "resolution_count": item.resolution_count,
                "disagreement_count": item.disagreement_count,
                "status": item.status,
                "first_tick": item.first_tick,
                "last_tick": item.last_tick,
                "coverage": _coverage_value(item.coverage),
            }
            for item in snapshot.candidates
        ],
        "cases": [
            {
                "case_ref": item.case_ref,
                "kind": item.kind,
                "subject_kind": item.subject_kind,
                "subject_token": item.subject_token,
                "status": item.status,
                "party_ids": list(item.party_ids),
                "first_tick": item.first_tick,
                "last_tick": item.last_tick,
                "coverage": _coverage_value(item.coverage),
            }
            for item in snapshot.cases
        ],
        "claims": [
            {
                "claim_id": item.claim_id,
                "case_ref": item.case_ref,
                "claimant_id": item.claimant_id,
                "respondent_id": item.respondent_id,
                "role": item.role,
                "claim_kind": item.claim_kind,
                "polarity": item.polarity,
                "subject_token": item.subject_token,
                "counters_claim_ref": item.counters_claim_ref,
                "evidence_count": item.evidence_count,
                "first_tick": item.first_tick,
                "last_tick": item.last_tick,
                "candidate_id": item.candidate_id,
            }
            for item in snapshot.claims
        ],
        "testimony": [
            {
                "testimony_id": item.testimony_id,
                "case_ref": item.case_ref,
                "claim_id": item.claim_id,
                "speaker_id": item.speaker_id,
                "channel": item.channel,
                "root_token": item.root_token,
                "independently_evidenced": item.independently_evidenced,
                "tick": item.tick,
            }
            for item in snapshot.testimony
        ],
        "evidence": [
            {
                "evidence_id": item.evidence_id,
                "case_ref": item.case_ref,
                "claim_id": item.claim_id,
                "channel": item.channel,
                "reference_kind": item.reference_kind,
                "reference_token": item.reference_token,
                "tick": item.tick,
                "independently_evidenced": item.independently_evidenced,
            }
            for item in snapshot.evidence
        ],
        "rule_references": [
            {
                "rule_reference_id": item.rule_reference_id,
                "case_ref": item.case_ref,
                "claim_ref": item.claim_ref,
                "system_token": item.system_token,
                "rule_token": item.rule_token,
                "version_number": item.version_number,
                "applicability": item.applicability,
                "interpretation": item.interpretation,
                "status": item.status,
            }
            for item in snapshot.rule_references
        ],
        "authority_references": [
            {
                "authority_reference_id": item.authority_reference_id,
                "case_ref": item.case_ref,
                "authority_kind": item.authority_kind,
                "reference_token": item.reference_token,
                "strength": item.strength,
                "uncertainty": item.uncertainty,
                "dissenting": item.dissenting,
            }
            for item in snapshot.authority_references
        ],
        "mediation_references": [
            {
                "mediation_reference_id": item.mediation_reference_id,
                "case_ref": item.case_ref,
                "mediation_case_token": item.mediation_case_token,
                "recommendation_token": item.recommendation_token,
                "response_token": item.response_token,
                "outcome_token": item.outcome_token,
                "link_status": item.link_status,
            }
            for item in snapshot.mediation_references
        ],
        "resolutions": [
            {
                "resolution_id": item.resolution_id,
                "resolution_ref": item.resolution_ref,
                "case_ref": item.case_ref,
                "proposer_id": item.proposer_id,
                "source": item.source,
                "terms_digest": item.terms_digest,
                "status": item.status,
                "first_tick": item.first_tick,
                "last_tick": item.last_tick,
                "expires_tick": item.expires_tick,
                "accepted_party_count": item.accepted_party_count,
                "rejected_party_count": item.rejected_party_count,
                "candidate_id": item.candidate_id,
            }
            for item in snapshot.resolutions
        ],
        "responses": [
            {
                "response_id": item.response_id,
                "resolution_ref": item.resolution_ref,
                "party_id": item.party_id,
                "kind": item.kind,
                "tick": item.tick,
                "terms_digest": item.terms_digest,
                "active": item.active,
            }
            for item in snapshot.responses
        ],
        "objective_rows": [
            {
                "tick": item.tick,
                "observed_occurrence_count": item.observed_occurrence_count,
                "observed_transfer_count": item.observed_transfer_count,
                "observed_harm_count": item.observed_harm_count,
                "observed_commitment_count": item.observed_commitment_count,
                "observed_record_count": item.observed_record_count,
                "observed_communication_count": item.observed_communication_count,
            }
            for item in snapshot.objective_rows
        ],
        "windows": [
            {
                "start_tick": item.start_tick,
                "end_tick": item.end_tick,
                "owner_count": item.owner_count,
                "candidate_count": item.candidate_count,
                "claim_count": item.claim_count,
            }
            for item in snapshot.windows
        ],
        "lineage": [
            {
                "edge_id": item.edge_id,
                "source": item.source,
                "target": item.target,
                "kind": item.kind,
                "tick": item.tick,
            }
            for item in snapshot.lineage
        ],
        "counts": _counts_value(snapshot.counts),
        "provenance_code": snapshot.provenance_code,
    }


def encode_dispute_snapshot(snapshot: DisputeSnapshot) -> bytes:
    """Encode one snapshot into canonical bytes with a size bound."""
    if type(snapshot) is not DisputeSnapshot:
        raise TypeError("snapshot must be DisputeSnapshot")
    payload = encode_dispute_value(_snapshot_to_value(snapshot))
    if len(payload) > MAX_DISPUTE_SNAPSHOT_BYTES:
        raise DisputeArtifactError("dispute_size_limit")
    _LOG.info(
        "dispute_snapshot_encoded candidates=%s bytes=%s",
        len(snapshot.candidates),
        len(payload),
    )
    return payload


def _digest_from_value(data: dict[str, object]) -> str:
    body = {key: value for key, value in data.items() if key != "snapshot_digest"}
    return hashlib.sha256(encode_dispute_value(body)).hexdigest()


def dispute_snapshot_digest(payload: bytes) -> str:
    """Return the content digest over canonical bytes excluding the digest."""
    data = _require_keys(decode_dispute_value(payload), _SNAPSHOT_KEYS)
    _string(data["snapshot_digest"])
    return _digest_from_value(data)


def finalize_dispute_snapshot(snapshot: DisputeSnapshot) -> DisputeSnapshot:
    """Return a copy whose ref carries the canonical content digest."""
    if type(snapshot) is not DisputeSnapshot:
        raise TypeError("snapshot must be DisputeSnapshot")
    digest = dispute_snapshot_digest(encode_dispute_snapshot(snapshot))
    return replace(snapshot, ref=replace(snapshot.ref, snapshot_digest=digest))


def compute_dispute_publication_id(snapshot: DisputeSnapshot) -> str:
    """Derive a content-addressed ``disp-pub-`` id, non-circularly."""
    if type(snapshot) is not DisputeSnapshot:
        raise TypeError("snapshot must be DisputeSnapshot")
    normalized = replace(
        snapshot,
        ref=replace(
            snapshot.ref,
            publication_id=_PLACEHOLDER_PUBLICATION_ID,
            snapshot_digest=_PLACEHOLDER_DIGEST,
        ),
    )
    encoded = encode_dispute_snapshot(normalized)
    body = hashlib.sha256(
        snapshot.ref.run_id.encode("utf-8") + b"\x00" + encoded
    ).hexdigest()[:16]
    return f"{DISPUTE_PUBLICATION_ID_PREFIX}{body}"


def _decode_coverage(value: object) -> DisputeCoverage:
    data = _require_keys(value, _COVERAGE_KEYS)
    return DisputeCoverage(
        observed=_int(data["observed"]),
        expected=_int(data["expected"]),
        ratio=_optional_float(data["ratio"]),
        note=_plain_string(data["note"]),
    )


def _decode_counts(value: object) -> DisputeCounts:
    data = _require_keys(value, _COUNTS_KEYS)
    return DisputeCounts(
        candidate_count=_int(data["candidate_count"]),
        case_count=_int(data["case_count"]),
        claim_count=_int(data["claim_count"]),
        counterclaim_count=_int(data["counterclaim_count"]),
        testimony_count=_int(data["testimony_count"]),
        evidence_count=_int(data["evidence_count"]),
        resolution_count=_int(data["resolution_count"]),
        accepted_count=_int(data["accepted_count"]),
        rejected_count=_int(data["rejected_count"]),
        owner_count=_int(data["owner_count"]),
        response_count=_int(data["response_count"]),
        edge_count=_int(data["edge_count"]),
        rule_reference_count=_int(data["rule_reference_count"]),
        authority_reference_count=_int(data["authority_reference_count"]),
        mediation_reference_count=_int(data["mediation_reference_count"]),
        objective_row_count=_int(data["objective_row_count"]),
        window_count=_int(data["window_count"]),
    )


def decode_dispute_snapshot(payload: bytes) -> DisputeSnapshot:
    """Strictly decode one snapshot and verify its digest and byte equality."""
    if not isinstance(payload, (bytes, bytearray)):
        _fail()
    data = _require_keys(decode_dispute_value(payload), _SNAPSHOT_KEYS)
    embedded = _string(data["snapshot_digest"])
    if _digest_from_value(data) != embedded:
        raise DisputeArtifactError("dispute_digest_mismatch")
    snapshot = DisputeSnapshot(
        ref=DisputeSnapshotRef(
            run_id=_string(data["run_id"]),
            input_revision=_string(data["input_revision"]),
            generated_tick=_int(data["generated_tick"]),
            publication_id=_string(data["publication_id"]),
            snapshot_digest=embedded,
            policy_version=_string(data["policy_version"]),
        ),
        coverage=_decode_coverage(data["coverage"]),
        candidates=tuple(
            DisputeCandidateRecord(
                candidate_id=_string(item["candidate_id"]),
                kind=_string(item["kind"]),
                subject_token=_string(item["subject_token"]),
                party_count=_int(item["party_count"]),
                owner_count=_int(item["owner_count"]),
                case_count=_int(item["case_count"]),
                claim_count=_int(item["claim_count"]),
                counterclaim_count=_int(item["counterclaim_count"]),
                testimony_count=_int(item["testimony_count"]),
                evidence_count=_int(item["evidence_count"]),
                resolution_count=_int(item["resolution_count"]),
                disagreement_count=_int(item["disagreement_count"]),
                status=_string(item["status"]),
                first_tick=_int(item["first_tick"]),
                last_tick=_int(item["last_tick"]),
                coverage=_decode_coverage(item["coverage"]),
            )
            for item in (
                _require_keys(raw, _CANDIDATE_KEYS) for raw in _list(data["candidates"])
            )
        ),
        cases=tuple(
            DisputeCaseRecord(
                case_ref=_string(item["case_ref"]),
                kind=_string(item["kind"]),
                subject_kind=_string(item["subject_kind"]),
                subject_token=_string(item["subject_token"]),
                status=_string(item["status"]),
                party_ids=tuple(_string_list(item["party_ids"])),
                first_tick=_int(item["first_tick"]),
                last_tick=_int(item["last_tick"]),
                coverage=_decode_coverage(item["coverage"]),
            )
            for item in (_require_keys(raw, _CASE_KEYS) for raw in _list(data["cases"]))
        ),
        claims=tuple(
            DisputeClaimRecord(
                claim_id=_string(item["claim_id"]),
                case_ref=_string(item["case_ref"]),
                claimant_id=_string(item["claimant_id"]),
                respondent_id=_string(item["respondent_id"]),
                role=_string(item["role"]),
                claim_kind=_string(item["claim_kind"]),
                polarity=_string(item["polarity"]),
                subject_token=_string(item["subject_token"]),
                counters_claim_ref=_optional_string(item["counters_claim_ref"]),
                evidence_count=_int(item["evidence_count"]),
                first_tick=_int(item["first_tick"]),
                last_tick=_int(item["last_tick"]),
                candidate_id=_plain_string(item["candidate_id"]),
            )
            for item in (
                _require_keys(raw, _CLAIM_KEYS) for raw in _list(data["claims"])
            )
        ),
        testimony=tuple(
            DisputeTestimonyRecord(
                testimony_id=_string(item["testimony_id"]),
                case_ref=_string(item["case_ref"]),
                claim_id=_string(item["claim_id"]),
                speaker_id=_string(item["speaker_id"]),
                channel=_string(item["channel"]),
                root_token=_string(item["root_token"]),
                independently_evidenced=_bool(item["independently_evidenced"]),
                tick=_int(item["tick"]),
            )
            for item in (
                _require_keys(raw, _TESTIMONY_KEYS) for raw in _list(data["testimony"])
            )
        ),
        evidence=tuple(
            DisputeEvidenceRecord(
                evidence_id=_string(item["evidence_id"]),
                case_ref=_string(item["case_ref"]),
                claim_id=_string(item["claim_id"]),
                channel=_string(item["channel"]),
                reference_kind=_string(item["reference_kind"]),
                reference_token=_string(item["reference_token"]),
                tick=_int(item["tick"]),
                independently_evidenced=_bool(item["independently_evidenced"]),
            )
            for item in (
                _require_keys(raw, _EVIDENCE_KEYS) for raw in _list(data["evidence"])
            )
        ),
        rule_references=tuple(
            DisputeRuleReferenceRecord(
                rule_reference_id=_string(item["rule_reference_id"]),
                case_ref=_string(item["case_ref"]),
                claim_ref=_string(item["claim_ref"]),
                system_token=_string(item["system_token"]),
                rule_token=_string(item["rule_token"]),
                version_number=_int(item["version_number"]),
                applicability=_string(item["applicability"]),
                interpretation=_string(item["interpretation"]),
                status=_string(item["status"]),
            )
            for item in (
                _require_keys(raw, _RULE_KEYS) for raw in _list(data["rule_references"])
            )
        ),
        authority_references=tuple(
            DisputeAuthorityReferenceRecord(
                authority_reference_id=_string(item["authority_reference_id"]),
                case_ref=_string(item["case_ref"]),
                authority_kind=_string(item["authority_kind"]),
                reference_token=_string(item["reference_token"]),
                strength=_float(item["strength"]),
                uncertainty=_float(item["uncertainty"]),
                dissenting=_bool(item["dissenting"]),
            )
            for item in (
                _require_keys(raw, _AUTHORITY_KEYS)
                for raw in _list(data["authority_references"])
            )
        ),
        mediation_references=tuple(
            DisputeMediationReferenceRecord(
                mediation_reference_id=_string(item["mediation_reference_id"]),
                case_ref=_string(item["case_ref"]),
                mediation_case_token=_string(item["mediation_case_token"]),
                recommendation_token=_optional_string(item["recommendation_token"]),
                response_token=_optional_string(item["response_token"]),
                outcome_token=_optional_string(item["outcome_token"]),
                link_status=_string(item["link_status"]),
            )
            for item in (
                _require_keys(raw, _MEDIATION_KEYS)
                for raw in _list(data["mediation_references"])
            )
        ),
        resolutions=tuple(
            DisputeResolutionRecord(
                resolution_id=_string(item["resolution_id"]),
                resolution_ref=_string(item["resolution_ref"]),
                case_ref=_string(item["case_ref"]),
                proposer_id=_string(item["proposer_id"]),
                source=_string(item["source"]),
                terms_digest=_string(item["terms_digest"]),
                status=_string(item["status"]),
                first_tick=_int(item["first_tick"]),
                last_tick=_int(item["last_tick"]),
                expires_tick=_optional_int(item["expires_tick"]),
                accepted_party_count=_int(item["accepted_party_count"]),
                rejected_party_count=_int(item["rejected_party_count"]),
                candidate_id=_plain_string(item["candidate_id"]),
            )
            for item in (
                _require_keys(raw, _RESOLUTION_KEYS)
                for raw in _list(data["resolutions"])
            )
        ),
        responses=tuple(
            DisputeResolutionResponseRecord(
                response_id=_string(item["response_id"]),
                resolution_ref=_string(item["resolution_ref"]),
                party_id=_string(item["party_id"]),
                kind=_string(item["kind"]),
                tick=_int(item["tick"]),
                terms_digest=_string(item["terms_digest"]),
                active=_bool(item["active"]),
            )
            for item in (
                _require_keys(raw, _RESPONSE_KEYS) for raw in _list(data["responses"])
            )
        ),
        objective_rows=tuple(
            DisputeObjectiveRow(
                tick=_int(item["tick"]),
                observed_occurrence_count=_int(item["observed_occurrence_count"]),
                observed_transfer_count=_int(item["observed_transfer_count"]),
                observed_harm_count=_int(item["observed_harm_count"]),
                observed_commitment_count=_int(item["observed_commitment_count"]),
                observed_record_count=_int(item["observed_record_count"]),
                observed_communication_count=_int(item["observed_communication_count"]),
            )
            for item in (
                _require_keys(raw, _OBJECTIVE_KEYS)
                for raw in _list(data["objective_rows"])
            )
        ),
        windows=tuple(
            DisputeWindowRecord(
                start_tick=_int(item["start_tick"]),
                end_tick=_int(item["end_tick"]),
                owner_count=_int(item["owner_count"]),
                candidate_count=_int(item["candidate_count"]),
                claim_count=_int(item["claim_count"]),
            )
            for item in (
                _require_keys(raw, _WINDOW_KEYS) for raw in _list(data["windows"])
            )
        ),
        lineage=tuple(
            DisputeLineageEdgeRecord(
                edge_id=_string(item["edge_id"]),
                source=_string(item["source"]),
                target=_string(item["target"]),
                kind=_string(item["kind"]),
                tick=_int(item["tick"]),
            )
            for item in (
                _require_keys(raw, _EDGE_KEYS) for raw in _list(data["lineage"])
            )
        ),
        counts=_decode_counts(data["counts"]),
        provenance_code=_string(data["provenance_code"]),
        schema_version=_string(data["schema_version"]),
    )
    if snapshot.schema_version != _SCHEMA:
        _fail()
    if encode_dispute_snapshot(snapshot) != bytes(payload):
        raise DisputeArtifactError("dispute_digest_mismatch")
    return snapshot
