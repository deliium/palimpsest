"""V4-08 canonical ``evidence-testimony-snapshot-v1`` round-trip and bounds."""

from __future__ import annotations

import dataclasses
import json

import pytest

from simulation.evidence_testimony_codec import (
    compute_evidence_testimony_publication_id,
    decode_evidence_testimony_snapshot,
    encode_evidence_testimony_snapshot,
    evidence_testimony_snapshot_digest,
    finalize_evidence_testimony_snapshot,
)
from simulation.evidence_testimony_models import (
    EVIDENCE_TESTIMONY_CANDIDATE_ITEMS_MAX,
    EVIDENCE_TESTIMONY_SNAPSHOT_SCHEMA,
    EvidenceCandidateRecord,
    EvidenceItemRecord,
    EvidenceLineageEdgeRecord,
    EvidenceSourceRecord,
    EvidenceTestimonyArtifactError,
    EvidenceTestimonyCounts,
    EvidenceTestimonySnapshot,
    empty_evidence_testimony_snapshot,
)

pytestmark = pytest.mark.unit
OWNER = "0" * 16


def _source(local_id: str = "evs-" + "0" * 16) -> EvidenceSourceRecord:
    return EvidenceSourceRecord(
        owner_token=OWNER,
        local_id=local_id,
        source_kind="artifact",
        reference_kind="artifact",
        provenance="direct_observation",
        confidence_band="mid",
        tick=1,
        subject_token="artifact-1",
        custody_status="complete_belief",
    )


def _candidate() -> EvidenceCandidateRecord:
    return EvidenceCandidateRecord(
        candidate_id="evid-" + "0" * 16,
        subject_token="artifact-1",
        source_kind_family="documentary",
        owner_tokens=(OWNER,),
        item_count=1,
        source_count=1,
        testimony_count=0,
        contradiction_count=0,
        status="isolated",
        coverage="complete",
        first_tick=1,
        last_tick=1,
        creation_digest="a" * 64,
    )


def _item(candidate_id: str) -> EvidenceItemRecord:
    return EvidenceItemRecord(
        owner_token=OWNER,
        local_id="evi-" + "0" * 16,
        candidate_id=candidate_id,
        subject_token="artifact-1",
        interpretation="supports",
        confidence_band="mid",
        status="active",
        tick=1,
        anchor_local_id="evs-" + "0" * 16,
    )


def _snapshot() -> EvidenceTestimonySnapshot:
    candidate = _candidate()
    source = _source()
    return finalize_evidence_testimony_snapshot(
        EvidenceTestimonySnapshot(
            run_id="run-1",
            generated_tick=3,
            candidates=(candidate,),
            sources=(source,),
            items=(_item(candidate.candidate_id),),
            counts=EvidenceTestimonyCounts(
                candidate_count=1, source_count=1, item_count=1
            ),
        )
    )


def test_empty_snapshot_round_trips_byte_identically() -> None:
    snapshot = finalize_evidence_testimony_snapshot(
        empty_evidence_testimony_snapshot("run-empty", generated_tick=0)
    )
    text = encode_evidence_testimony_snapshot(snapshot)
    decoded = decode_evidence_testimony_snapshot(text)
    assert decoded == snapshot
    assert encode_evidence_testimony_snapshot(decoded) == text
    assert decoded.schema_version == EVIDENCE_TESTIMONY_SNAPSHOT_SCHEMA
    assert decoded.publication_id == compute_evidence_testimony_publication_id(decoded)
    assert decoded.snapshot_digest == evidence_testimony_snapshot_digest(decoded)


def test_full_snapshot_round_trips() -> None:
    snapshot = _snapshot()
    decoded = decode_evidence_testimony_snapshot(
        encode_evidence_testimony_snapshot(snapshot)
    )
    assert decoded == snapshot
    assert decoded.counts.source_count == 1
    assert decoded.publication_id.startswith("evid-pub-")


def test_records_carry_no_forbidden_result_field() -> None:
    for model in (
        EvidenceSourceRecord,
        EvidenceCandidateRecord,
        EvidenceItemRecord,
    ):
        names = {field.name for field in dataclasses.fields(model)}
        assert names.isdisjoint(
            {"truth", "verified", "authenticated", "verdict", "guilt"}
        )


def test_duplicate_ids_and_dangling_refs_fail() -> None:
    candidate = _candidate()
    source = _source()
    with pytest.raises(EvidenceTestimonyArtifactError):
        EvidenceTestimonySnapshot(
            run_id="run-1",
            generated_tick=1,
            sources=(source, source),
        )

    with pytest.raises(EvidenceTestimonyArtifactError):
        EvidenceTestimonySnapshot(
            run_id="run-1",
            generated_tick=1,
            candidates=(candidate,),
            items=(_item("evid-" + "9" * 16),),
            sources=(source,),
        )


def test_items_per_candidate_are_bounded() -> None:
    candidate = _candidate()
    items = tuple(
        EvidenceItemRecord(
            owner_token=OWNER,
            local_id=f"evi-{index:016x}",
            candidate_id=candidate.candidate_id,
            subject_token="artifact-1",
            interpretation="supports",
            confidence_band="mid",
            status="active",
            tick=1,
            anchor_local_id="evs-" + "0" * 16,
        )
        for index in range(EVIDENCE_TESTIMONY_CANDIDATE_ITEMS_MAX + 1)
    )
    with pytest.raises(EvidenceTestimonyArtifactError) as error:
        EvidenceTestimonySnapshot(
            run_id="run-1",
            generated_tick=1,
            candidates=(candidate,),
            sources=(_source(),),
            items=items,
        )
    assert error.value.code == "evidence_testimony_size_limit"


def test_cyclic_lineage_fails() -> None:
    a = "evid-" + "a" * 16
    b = "evid-" + "b" * 16
    with pytest.raises(EvidenceTestimonyArtifactError):
        EvidenceTestimonySnapshot(
            run_id="run-1",
            generated_tick=1,
            edges=(
                EvidenceLineageEdgeRecord(
                    edge_id="evid-edge-" + "1" * 16,
                    kind="continued",
                    source_ids=(a,),
                    target_ids=(b,),
                    window_index=0,
                ),
                EvidenceLineageEdgeRecord(
                    edge_id="evid-edge-" + "2" * 16,
                    kind="continued",
                    source_ids=(b,),
                    target_ids=(a,),
                    window_index=1,
                ),
            ),
        )


def test_mutated_payload_fails_closed() -> None:
    text = encode_evidence_testimony_snapshot(_snapshot())
    payload = json.loads(text)
    payload["generated_tick"] = 99
    with pytest.raises(EvidenceTestimonyArtifactError) as error:
        decode_evidence_testimony_snapshot(
            json.dumps(payload, sort_keys=True, separators=(",", ":"))
        )
    assert error.value.code in {
        "evidence_testimony_digest_mismatch",
        "evidence_testimony_invalid_snapshot",
    }

    with pytest.raises(EvidenceTestimonyArtifactError):
        decode_evidence_testimony_snapshot("{not-json")


def test_unknown_schema_and_nan_fail_closed() -> None:
    text = encode_evidence_testimony_snapshot(_snapshot())
    payload = json.loads(text)
    payload["schema_version"] = "evidence-testimony-snapshot-v2"
    with pytest.raises(EvidenceTestimonyArtifactError):
        decode_evidence_testimony_snapshot(
            json.dumps(payload, sort_keys=True, separators=(",", ":"))
        )
    with pytest.raises(EvidenceTestimonyArtifactError):
        decode_evidence_testimony_snapshot(text.replace('"mid"', "NaN", 1))
