"""V4-07 canonical ``dispute-resolution-snapshot-v1`` models and codec."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

import simulation.dispute_codec as dispute_codec
import simulation.dispute_models as dispute_models
from simulation import (
    DISPUTE_FORBIDDEN_FIELD_NAMES,
    DISPUTE_SNAPSHOT_SCHEMA,
    SUPPORTED_DISPUTE_SNAPSHOT_SCHEMAS,
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
    compute_dispute_publication_id,
    decode_dispute_snapshot,
    decode_dispute_value,
    decode_formal_rule_snapshot,
    decode_organization_snapshot,
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
    dispute_snapshot_digest,
    empty_dispute_snapshot,
    encode_dispute_snapshot,
    encode_dispute_value,
    encode_formal_rule_snapshot,
    encode_organization_snapshot,
    finalize_dispute_snapshot,
)

pytestmark = pytest.mark.unit

CANDIDATE = "disp-0123456789abcdef"
OTHER_CANDIDATE = "disp-fedcba9876543210"
PUBLICATION = "disp-pub-0123456789abcdef"
SUBJECT = "commitment-1"
PARTIES = ("agent-1", "agent-2")
CASE_REF = derive_dispute_case_ref(SUBJECT, PARTIES)
CLAIM = derive_dispute_claim_id(CASE_REF, "agent-1", "claim", "debt_owed", SUBJECT)
COUNTERCLAIM = derive_dispute_claim_id(
    CASE_REF, "agent-2", "counterclaim", "debt_owed", SUBJECT, CLAIM
)
EVIDENCE_REFERENCE = "b" * 64
TERMS = "d" * 64
RESOLUTION_REF = "e" * 64
EVIDENCE = derive_dispute_evidence_id(
    CASE_REF, CLAIM, "observed", "observed_occurrence", EVIDENCE_REFERENCE, 3
)
TESTIMONY = derive_dispute_testimony_id(
    CASE_REF, CLAIM, "agent-1", "direct", "root-1", 3
)
RULE_REFERENCE = derive_dispute_rule_reference_id(
    CASE_REF, CLAIM, "custom", "payment-rule", 1
)
AUTHORITY_REFERENCE = derive_dispute_authority_reference_id(
    CASE_REF, "office", "office-token-1"
)
MEDIATION_REFERENCE = derive_dispute_mediation_reference_id(
    CASE_REF, "mediation-case-1"
)
RESOLUTION = derive_dispute_resolution_id(CASE_REF, "agent-1", TERMS)
RESPONSE = derive_dispute_response_id(RESOLUTION_REF, "agent-2", "accept", 6, TERMS)
EDGE = derive_dispute_edge_id(CANDIDATE, OTHER_CANDIDATE, "emerged", 5)


def _coverage(observed: int = 1, expected: int = 1, note: str = "") -> DisputeCoverage:
    ratio = None if expected == 0 else observed / expected
    return DisputeCoverage(observed=observed, expected=expected, ratio=ratio, note=note)


def _candidate(
    candidate_id: str, *, status: str, first: int, last: int
) -> DisputeCandidateRecord:
    return DisputeCandidateRecord(
        candidate_id=candidate_id,
        kind="contested_debt",
        subject_token=SUBJECT,
        party_count=2,
        owner_count=2,
        case_count=1,
        claim_count=2,
        counterclaim_count=1,
        testimony_count=1,
        evidence_count=1,
        resolution_count=1,
        disagreement_count=1,
        status=status,
        first_tick=first,
        last_tick=last,
        coverage=_coverage(),
    )


def _snapshot() -> DisputeSnapshot:
    snapshot = DisputeSnapshot(
        ref=DisputeSnapshotRef(
            run_id="run-1",
            input_revision="revision-1",
            generated_tick=10,
            publication_id=PUBLICATION,
            snapshot_digest="0" * 64,
        ),
        coverage=_coverage(),
        candidates=(
            _candidate(CANDIDATE, status="active", first=2, last=6),
            _candidate(OTHER_CANDIDATE, status="emerging", first=5, last=5),
        ),
        cases=(
            DisputeCaseRecord(
                case_ref=CASE_REF,
                kind="contested_debt",
                subject_kind="commitment",
                subject_token=SUBJECT,
                status="contested",
                party_ids=PARTIES,
                first_tick=2,
                last_tick=6,
                coverage=_coverage(),
            ),
        ),
        claims=(
            DisputeClaimRecord(
                claim_id=CLAIM,
                case_ref=CASE_REF,
                claimant_id="agent-1",
                respondent_id="agent-2",
                role="claim",
                claim_kind="debt_owed",
                polarity="affirm",
                subject_token=SUBJECT,
                counters_claim_ref=None,
                evidence_count=1,
                first_tick=2,
                last_tick=3,
                candidate_id=CANDIDATE,
            ),
            DisputeClaimRecord(
                claim_id=COUNTERCLAIM,
                case_ref=CASE_REF,
                claimant_id="agent-2",
                respondent_id="agent-1",
                role="counterclaim",
                claim_kind="debt_owed",
                polarity="deny",
                subject_token=SUBJECT,
                counters_claim_ref=CLAIM,
                evidence_count=0,
                first_tick=4,
                last_tick=4,
                candidate_id=CANDIDATE,
            ),
        ),
        testimony=(
            DisputeTestimonyRecord(
                testimony_id=TESTIMONY,
                case_ref=CASE_REF,
                claim_id=CLAIM,
                speaker_id="agent-1",
                channel="direct",
                root_token="root-1",
                independently_evidenced=True,
                tick=3,
            ),
        ),
        evidence=(
            DisputeEvidenceRecord(
                evidence_id=EVIDENCE,
                case_ref=CASE_REF,
                claim_id=CLAIM,
                channel="observed",
                reference_kind="observed_occurrence",
                reference_token=EVIDENCE_REFERENCE,
                tick=3,
                independently_evidenced=True,
            ),
        ),
        rule_references=(
            DisputeRuleReferenceRecord(
                rule_reference_id=RULE_REFERENCE,
                case_ref=CASE_REF,
                claim_ref=CLAIM,
                system_token="custom",
                rule_token="payment-rule",
                version_number=1,
                applicability="applies",
                interpretation="literal",
                status="resolved",
            ),
        ),
        authority_references=(
            DisputeAuthorityReferenceRecord(
                authority_reference_id=AUTHORITY_REFERENCE,
                case_ref=CASE_REF,
                authority_kind="office",
                reference_token="office-token-1",
                strength=0.6,
                uncertainty=0.4,
                dissenting=False,
            ),
        ),
        mediation_references=(
            DisputeMediationReferenceRecord(
                mediation_reference_id=MEDIATION_REFERENCE,
                case_ref=CASE_REF,
                mediation_case_token="mediation-case-1",
                recommendation_token="recommendation-1",
                response_token="response-1",
                outcome_token=None,
                link_status="linked",
            ),
        ),
        resolutions=(
            DisputeResolutionRecord(
                resolution_id=RESOLUTION,
                resolution_ref=RESOLUTION_REF,
                case_ref=CASE_REF,
                proposer_id="agent-1",
                source="mediator",
                terms_digest=TERMS,
                status="partially_accepted",
                first_tick=5,
                last_tick=6,
                expires_tick=None,
                accepted_party_count=1,
                rejected_party_count=0,
                candidate_id=CANDIDATE,
            ),
        ),
        responses=(
            DisputeResolutionResponseRecord(
                response_id=RESPONSE,
                resolution_ref=RESOLUTION_REF,
                party_id="agent-2",
                kind="accept",
                tick=6,
                terms_digest=TERMS,
                active=True,
            ),
        ),
        objective_rows=(DisputeObjectiveRow(3, 1, 1, 0, 1, 0, 0),),
        windows=(DisputeWindowRecord(0, 9, 2, 2, 2),),
        lineage=(
            DisputeLineageEdgeRecord(
                edge_id=EDGE,
                source=CANDIDATE,
                target=OTHER_CANDIDATE,
                kind="emerged",
                tick=5,
            ),
        ),
        counts=DisputeCounts(
            candidate_count=2,
            case_count=1,
            claim_count=2,
            counterclaim_count=1,
            testimony_count=1,
            evidence_count=1,
            resolution_count=1,
            accepted_count=1,
            rejected_count=0,
            owner_count=2,
            response_count=1,
            edge_count=1,
            rule_reference_count=1,
            authority_reference_count=1,
            mediation_reference_count=1,
            objective_row_count=1,
            window_count=1,
        ),
        provenance_code="ok",
    )
    return finalize_dispute_snapshot(snapshot)


def test_snapshot_round_trip_is_byte_stable() -> None:
    snapshot = _snapshot()
    payload = encode_dispute_snapshot(snapshot)
    decoded = decode_dispute_snapshot(payload)
    assert decoded == snapshot
    assert encode_dispute_snapshot(decoded) == payload
    reordered = replace(
        snapshot,
        candidates=tuple(reversed(snapshot.candidates)),
        claims=tuple(reversed(snapshot.claims)),
        lineage=tuple(reversed(snapshot.lineage)),
    )
    assert encode_dispute_snapshot(reordered) == payload


def test_snapshot_rejects_owner_local_ids() -> None:
    snapshot = _snapshot()
    with pytest.raises(DisputeArtifactError) as excinfo:
        replace(snapshot.claims[0], claimant_id="dcl-0123456789abcdef")
    assert excinfo.value.code == "dispute_owner_local_id"


def test_snapshot_rejects_verdict_and_binding_fields() -> None:
    names = {field.name for field in DisputeSnapshot.__dataclass_fields__.values()}
    assert names.isdisjoint(DISPUTE_FORBIDDEN_FIELD_NAMES)
    payload = json.loads(encode_dispute_snapshot(_snapshot()))
    payload["verdict"] = "guilty"
    with pytest.raises(DisputeArtifactError) as excinfo:
        decode_dispute_snapshot(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        )
    assert excinfo.value.code == "dispute_invalid_value"


def test_limits_are_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dispute_codec, "MAX_DISPUTE_SNAPSHOT_BYTES", 100)
    with pytest.raises(DisputeArtifactError) as excinfo:
        encode_dispute_snapshot(_snapshot())
    assert excinfo.value.code == "dispute_size_limit"

    with pytest.raises(DisputeArtifactError) as candidate_error:
        replace(_candidate(CANDIDATE, status="active", first=2, last=6), claim_count=65)
    assert candidate_error.value.code == "dispute_size_limit"


@pytest.mark.parametrize(
    "constant",
    [
        "MAX_DISPUTE_CANDIDATES",
        "MAX_DISPUTE_CASES",
        "MAX_DISPUTE_CLAIMS",
        "MAX_DISPUTE_TESTIMONY",
        "MAX_DISPUTE_EVIDENCE",
        "MAX_DISPUTE_RESOLUTIONS",
        "MAX_DISPUTE_RESPONSES",
        "MAX_DISPUTE_WINDOWS",
        "MAX_DISPUTE_OBJECTIVE_ROWS",
    ],
)
def test_each_record_family_bound_is_enforced(
    monkeypatch: pytest.MonkeyPatch, constant: str
) -> None:
    monkeypatch.setattr(dispute_models, constant, 0)
    with pytest.raises(DisputeArtifactError) as excinfo:
        DisputeSnapshot(
            ref=_snapshot().ref,
            coverage=_coverage(),
            candidates=(_candidate(CANDIDATE, status="active", first=2, last=6),),
            counts=DisputeCounts(1, 0, 0, 0, 0, 0, 0, 0, 0, 2),
            provenance_code="ok",
        )
    assert excinfo.value.code == "dispute_size_limit"


def test_counts_must_match_record_families() -> None:
    snapshot = _snapshot()
    with pytest.raises(DisputeArtifactError) as excinfo:
        replace(
            snapshot,
            counts=replace(
                snapshot.counts, claim_count=snapshot.counts.claim_count + 1
            ),
        )
    assert excinfo.value.code == "dispute_invalid_value"


def test_duplicate_json_keys_and_nonfinite_values_fail() -> None:
    with pytest.raises(DisputeArtifactError):
        decode_dispute_value(b'{"a":1,"a":2}')
    with pytest.raises(DisputeArtifactError):
        decode_dispute_value(b'{"a":NaN}')
    with pytest.raises(DisputeArtifactError):
        encode_dispute_value({"a": float("inf")})


def test_digest_and_publication_id_are_content_addressed() -> None:
    snapshot = _snapshot()
    payload = encode_dispute_snapshot(snapshot)
    assert dispute_snapshot_digest(payload) == snapshot.ref.snapshot_digest
    publication_id = compute_dispute_publication_id(snapshot)
    assert publication_id.startswith("disp-pub-")
    assert publication_id == compute_dispute_publication_id(_snapshot())
    changed = finalize_dispute_snapshot(
        replace(snapshot, ref=replace(snapshot.ref, generated_tick=11))
    )
    assert compute_dispute_publication_id(changed) != publication_id
    empty = empty_dispute_snapshot(
        DisputeSnapshotRef(
            run_id="run-empty",
            input_revision="revision-1",
            generated_tick=0,
            publication_id=PUBLICATION,
            snapshot_digest="0" * 64,
        ),
        coverage=DisputeCoverage(0, 0),
    )
    assert decode_dispute_snapshot(encode_dispute_snapshot(empty)) == empty


def test_organization_and_formal_rule_snapshots_remain_decodable() -> None:
    from tests.unit.organization_artifact_helpers import example_snapshot
    from tests.unit.test_formal_rule_snapshot import _snapshot as formal_snapshot

    organization_payload = encode_organization_snapshot(example_snapshot())
    assert decode_organization_snapshot(organization_payload) == example_snapshot()
    formal_payload = encode_formal_rule_snapshot(formal_snapshot())
    assert decode_formal_rule_snapshot(formal_payload) == formal_snapshot()
    assert DISPUTE_SNAPSHOT_SCHEMA not in SUPPORTED_DISPUTE_SNAPSHOT_SCHEMAS[1:]
    assert SUPPORTED_DISPUTE_SNAPSHOT_SCHEMAS == (DISPUTE_SNAPSHOT_SCHEMA,)
