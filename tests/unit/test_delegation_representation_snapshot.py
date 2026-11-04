"""V4-09 canonical representation snapshot and codec."""

from __future__ import annotations

import json

import pytest

from simulation.delegation_representation_codec import (
    compute_delegation_representation_publication_id,
    decode_delegation_representation_snapshot,
    delegation_representation_snapshot_digest,
    encode_delegation_representation_snapshot,
    finalize_delegation_representation_snapshot,
)
from simulation.delegation_representation_models import (
    DELEGATION_REPRESENTATION_SNAPSHOT_SCHEMA,
    MAX_SNAPSHOT_BYTES,
    MAX_SNAPSHOT_MANDATES,
    DelegationRepresentationArtifactError,
    DelegationRepresentationCandidateRow,
    DelegationRepresentationConflictRow,
    DelegationRepresentationLineageRow,
    DelegationRepresentationMandateRow,
    DelegationRepresentationMetricProvenanceRow,
    DelegationRepresentationPositionRow,
    DelegationRepresentationSnapshot,
    DelegationRepresentationSummaryRow,
    empty_delegation_representation_snapshot,
)

pytestmark = pytest.mark.unit

_OWNER = "a" * 16
_REP = "b" * 16
_PRINCIPAL = "c" * 16
_RUN = "run-representation-snapshot"


def _summary(**overrides: int | str) -> DelegationRepresentationSummaryRow:
    values: dict[str, object] = dict(
        mandate_count=0,
        position_count=0,
        revocation_count=0,
        conflict_count=0,
        candidate_count=0,
        lineage_edge_count=0,
        owner_count=0,
        coverage="complete",
    )
    values.update(overrides)
    return DelegationRepresentationSummaryRow(**values)  # type: ignore[arg-type]


def _mandate(mandate_id: str = "rmd-" + "1" * 16) -> DelegationRepresentationMandateRow:
    return DelegationRepresentationMandateRow(
        mandate_id=mandate_id,
        owner_token=_OWNER,
        principal_kind="agent",
        principal_token=_PRINCIPAL,
        representative_token=_REP,
        scope_kind="speak_for",
        scope_subject_token="border",
        duration_kind="until_revoked",
        start_tick=1,
        end_tick=None,
        provenance="self_declared",
        status="claimed",
        recognition_basis="none",
        support_roots=0,
        opposition_roots=0,
        confidence_band="mid",
        coverage="complete",
    )


def _snapshot(**overrides: object) -> DelegationRepresentationSnapshot:
    values: dict[str, object] = dict(
        run_id=_RUN,
        generated_tick=3,
        created_from="d" * 64,
        summary=_summary(),
    )
    values.update(overrides)
    return DelegationRepresentationSnapshot(**values)  # type: ignore[arg-type]


def test_empty_snapshot_round_trips_and_is_canonical() -> None:
    snapshot = finalize_delegation_representation_snapshot(
        empty_delegation_representation_snapshot(_RUN)
    )
    assert DELEGATION_REPRESENTATION_SNAPSHOT_SCHEMA == (
        "delegation-representation-snapshot-v1"
    )
    payload = encode_delegation_representation_snapshot(snapshot)
    assert type(payload) is bytes
    decoded = decode_delegation_representation_snapshot(payload)
    assert decoded == snapshot
    assert decoded.publication_id.startswith("drep-pub-")


def test_digest_and_publication_id_are_content_addressed() -> None:
    snapshot = finalize_delegation_representation_snapshot(_snapshot())
    assert delegation_representation_snapshot_digest(snapshot) == snapshot.digest
    assert (
        compute_delegation_representation_publication_id(_RUN, snapshot.digest)
        == snapshot.publication_id
    )


def test_rows_round_trip_and_are_sorted() -> None:
    mandate = _mandate()
    position = DelegationRepresentationPositionRow(
        position_id="rmp-" + "1" * 16,
        mandate_id=mandate.mandate_id,
        owner_token=_OWNER,
        actor_token="e" * 16,
        stance="support",
        provenance="communicated",
        tick=2,
        active=True,
    )
    summary = _summary(mandate_count=1, position_count=1, owner_count=1)
    snapshot = finalize_delegation_representation_snapshot(
        _snapshot(mandates=(mandate,), positions=(position,), summary=summary)
    )
    decoded = decode_delegation_representation_snapshot(
        encode_delegation_representation_snapshot(snapshot)
    )
    assert decoded.mandates == (mandate,)
    assert decoded.positions == (position,)


def test_permuted_rows_produce_identical_bytes() -> None:
    first = _mandate("rmd-" + "1" * 16)
    second = _mandate("rmd-" + "2" * 16)
    summary = _summary(mandate_count=2, owner_count=1)
    left = finalize_delegation_representation_snapshot(
        _snapshot(mandates=(first, second), summary=summary)
    )
    right = finalize_delegation_representation_snapshot(
        _snapshot(mandates=(second, first), summary=summary)
    )
    assert encode_delegation_representation_snapshot(left) == (
        encode_delegation_representation_snapshot(right)
    )


def test_raw_agent_id_and_free_text_scope_are_rejected() -> None:
    from dataclasses import replace

    with pytest.raises(DelegationRepresentationArtifactError):
        replace(_mandate(), owner_token="agent-owner")
    with pytest.raises(DelegationRepresentationArtifactError):
        replace(_mandate(), scope_subject_token="Free Text")


def test_candidate_conflict_lineage_and_metric_rows_validate() -> None:
    candidate = DelegationRepresentationCandidateRow(
        candidate_id="rep-" + "1" * 16,
        principal_kind="agent",
        principal_token=_PRINCIPAL,
        scope_kind="speak_for",
        scope_subject_token="border",
        status="claimed",
        representative_tokens=(_REP,),
        lineage_kind="emerged",
        coverage="complete",
    )
    edge = DelegationRepresentationLineageRow(
        edge_id="rep-edge-" + "1" * 16,
        from_candidate_id=candidate.candidate_id,
        to_candidate_id=candidate.candidate_id,
        kind="emerged",
        tick=1,
    )
    mandate = _mandate()
    conflict = DelegationRepresentationConflictRow(
        conflict_id="rmx-" + "1" * 16,
        owner_token=_OWNER,
        mandate_ids=(mandate.mandate_id,),
        kind="revocation_dispute",
        status="unresolved",
        tick=2,
    )
    provenance = DelegationRepresentationMetricProvenanceRow(
        family_id="representation_mandate_structure@1",
        family_version=1,
        document_digest="f" * 64,
    )
    summary = _summary(
        mandate_count=1,
        conflict_count=1,
        candidate_count=1,
        lineage_edge_count=1,
        owner_count=1,
    )
    snapshot = finalize_delegation_representation_snapshot(
        _snapshot(
            mandates=(mandate,),
            candidates=(candidate,),
            lineage=(edge,),
            conflicts=(conflict,),
            metric_provenance=(provenance,),
            summary=summary,
        )
    )
    assert (
        decode_delegation_representation_snapshot(
            encode_delegation_representation_snapshot(snapshot)
        )
        == snapshot
    )


def test_unsupported_schema_extra_keys_and_tamper_are_rejected() -> None:
    snapshot = finalize_delegation_representation_snapshot(_snapshot())
    payload = json.loads(encode_delegation_representation_snapshot(snapshot))
    payload["schema_version"] = "delegation-representation-snapshot-v2"
    with pytest.raises(DelegationRepresentationArtifactError) as excinfo:
        decode_delegation_representation_snapshot(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        )
    assert excinfo.value.code == "delegation_representation_snapshot_unsupported"

    payload = json.loads(encode_delegation_representation_snapshot(snapshot))
    payload["extra"] = 1
    with pytest.raises(DelegationRepresentationArtifactError):
        decode_delegation_representation_snapshot(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        )

    payload = json.loads(encode_delegation_representation_snapshot(snapshot))
    payload["coverage"] = "partial"
    with pytest.raises(DelegationRepresentationArtifactError):
        decode_delegation_representation_snapshot(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        )


def test_caps_are_declared_and_empty_snapshot_is_bounded() -> None:
    assert MAX_SNAPSHOT_MANDATES == 8192
    assert MAX_SNAPSHOT_BYTES == 4 * 1024 * 1024
    snapshot = finalize_delegation_representation_snapshot(
        empty_delegation_representation_snapshot(_RUN)
    )
    assert len(encode_delegation_representation_snapshot(snapshot)) < MAX_SNAPSHOT_BYTES
