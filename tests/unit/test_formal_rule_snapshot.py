"""V4-06 canonical formal-rule snapshot models and codec."""

from __future__ import annotations

import json

import pytest

from simulation import (
    FORMAL_RULE_SNAPSHOT_SCHEMA,
    FormalRuleArtifactError,
    FormalRuleCandidateRecord,
    FormalRuleCounts,
    FormalRuleCoverage,
    FormalRuleLineageEdgeRecord,
    FormalRuleRecord,
    FormalRuleSnapshot,
    FormalRuleSnapshotRef,
    FormalRuleVersionRecord,
    FormalRuleWindowRecord,
    FormalRuleWrittenRepresentationRecord,
    compute_formal_rule_publication_id,
    decode_formal_rule_snapshot,
    derive_formal_rule_rule_id,
    derive_formal_rule_version_id,
    empty_formal_rule_snapshot,
    encode_formal_rule_snapshot,
    formal_rule_digest,
    require_formal_rule_candidate_id,
)

pytestmark = pytest.mark.unit

PUB_PLACEHOLDER = "frule-pub-" + "0" * 16
SCOPE = "a" * 64
CANDIDATE = "frule-0123456789abcdef"
OTHER_CANDIDATE = "frule-fedcba9876543210"
RULE = derive_formal_rule_rule_id(
    CANDIDATE, "norm", "obligation", "maintain", "custom"
)
OTHER_RULE = derive_formal_rule_rule_id(
    OTHER_CANDIDATE, "norm", "prohibition", "maintain", "custom"
)
VERSION = derive_formal_rule_version_id(RULE, 1, "b" * 64)


def _ref() -> FormalRuleSnapshotRef:
    return FormalRuleSnapshotRef(
        run_id="run-1",
        input_revision="revision-1",
        generated_tick=10,
        publication_id=PUB_PLACEHOLDER,
    )


def _written() -> FormalRuleWrittenRepresentationRecord:
    return FormalRuleWrittenRepresentationRecord()


def _candidate(
    candidate_id: str,
    *,
    constraint: str,
    competing: tuple[str, ...] = (),
) -> FormalRuleCandidateRecord:
    return FormalRuleCandidateRecord(
        candidate_id=candidate_id,
        status="contested" if competing else "recognized",
        scope_kind="action",
        scope_digest=SCOPE,
        action_token="maintain",
        constraint_kinds=(constraint,),
        stage="norm",
        authority_kinds=("custom",),
        system_count=1,
        rule_count=1,
        version_count=1,
        competing_candidate_ids=competing,
        first_tick=0,
        last_tick=0,
        coverage=FormalRuleCoverage(1, 1),
    )


def _snapshot() -> FormalRuleSnapshot:
    return FormalRuleSnapshot(
        ref=_ref(),
        candidates=(
            _candidate(
                CANDIDATE,
                constraint="obligation",
                competing=(OTHER_CANDIDATE,),
            ),
            _candidate(
                OTHER_CANDIDATE,
                constraint="prohibition",
                competing=(CANDIDATE,),
            ),
        ),
        rules=(
            FormalRuleRecord(
                rule_id=RULE,
                candidate_id=CANDIDATE,
                stage="norm",
                constraint_kind="obligation",
                scope_kind="action",
                action_token="maintain",
                authority_kind="custom",
                recognition="claimed",
                written_representation=_written(),
                sanction_kinds=("criticism",),
                exception_count=0,
                version_count=1,
                latest_version=1,
                proponent_count=1,
                response_counts=(("follow", 1),),
            ),
            FormalRuleRecord(
                rule_id=OTHER_RULE,
                candidate_id=OTHER_CANDIDATE,
                stage="norm",
                constraint_kind="prohibition",
                scope_kind="action",
                action_token="maintain",
                authority_kind="custom",
                recognition="contested",
                written_representation=_written(),
                sanction_kinds=(),
                exception_count=0,
                version_count=1,
                latest_version=1,
                proponent_count=0,
                response_counts=(),
            ),
        ),
        versions=(
            FormalRuleVersionRecord(
                version_id=VERSION,
                rule_id=RULE,
                version_number=1,
                stage="norm",
                constraint_kind="obligation",
                scope_kind="action",
                scope_digest=SCOPE,
                action_token="maintain",
                authority_kind="custom",
                recognition="claimed",
                written_representation=_written(),
                sanction_kinds=("criticism",),
                exception_count=0,
                tick=0,
                revision_kind="initial",
            ),
        ),
        lineage=(
            FormalRuleLineageEdgeRecord(
                edge_id="frule-edge-0123456789abcdef",
                source_candidate_id=CANDIDATE,
                target_candidate_id=OTHER_CANDIDATE,
                kind="split",
                tick=0,
                jaccard=0.0,
                containment=0.5,
            ),
        ),
        windows=(FormalRuleWindowRecord(0, 99, 1, 2),),
        coverage=FormalRuleCoverage(1, 1),
        counts=FormalRuleCounts(
            candidates=2, rules=2, versions=1, objective_rows=0, windows=1
        ),
        provenance_code="ok",
    )


def test_empty_snapshot_is_canonical_and_round_trips() -> None:
    snapshot = empty_formal_rule_snapshot(
        _ref(), coverage=FormalRuleCoverage(0, 0)
    )
    payload = encode_formal_rule_snapshot(snapshot)
    decoded = decode_formal_rule_snapshot(payload)
    assert encode_formal_rule_snapshot(decoded) == payload
    assert decoded.counts == FormalRuleCounts()
    assert json.loads(payload)["schema_version"] == FORMAL_RULE_SNAPSHOT_SCHEMA


def test_exact_top_level_keys_reject_missing_and_extra() -> None:
    payload = json.loads(encode_formal_rule_snapshot(_snapshot()))
    missing = dict(payload)
    missing.pop("counts")
    with pytest.raises(FormalRuleArtifactError) as excinfo:
        decode_formal_rule_snapshot(json.dumps(missing).encode())
    assert excinfo.value.code == "formal_rule_invalid_value"

    extra = dict(payload)
    extra["extra"] = True
    with pytest.raises(FormalRuleArtifactError):
        decode_formal_rule_snapshot(json.dumps(extra).encode())


def test_candidate_rule_version_window_edge_and_coverage_keys_are_exact() -> None:
    payload = json.loads(encode_formal_rule_snapshot(_snapshot()))
    for section, key in (
        ("candidates", "candidate_id"),
        ("rules", "rule_id"),
        ("versions", "version_id"),
        ("lineage", "edge_id"),
        ("windows", "start_tick"),
        ("coverage", "observed"),
    ):
        value = payload[section]
        if isinstance(value, list):
            value[0].pop(key)
        else:
            value.pop(key)
    with pytest.raises(FormalRuleArtifactError):
        decode_formal_rule_snapshot(json.dumps(payload).encode())


def test_duplicate_json_keys_are_rejected() -> None:
    payload = encode_formal_rule_snapshot(_snapshot()).decode()
    duplicate = payload.replace(
        '"run_id":"run-1"', '"run_id":"run-1","run_id":"run-2"', 1
    )
    with pytest.raises(FormalRuleArtifactError):
        decode_formal_rule_snapshot(duplicate.encode())


def test_owner_local_and_cross_context_ids_are_rejected() -> None:
    with pytest.raises(FormalRuleArtifactError):
        require_formal_rule_candidate_id("frl-0123456789abcdef")
    with pytest.raises(FormalRuleArtifactError):
        _candidate("org-0123456789abcdef", constraint="obligation")


def test_candidate_and_rule_caps_are_enforced() -> None:
    candidates = tuple(
        _candidate(f"frule-{index:016x}", constraint="obligation")
        for index in range(2049)
    )
    with pytest.raises(FormalRuleArtifactError) as excinfo:
        FormalRuleSnapshot(
            ref=_ref(),
            candidates=candidates,
            coverage=FormalRuleCoverage(1, 1),
            counts=FormalRuleCounts(candidates=2049, rules=0, versions=0),
            provenance_code="ok",
        )
    assert excinfo.value.code == "formal_rule_size_limit"


def test_competing_candidate_links_are_symmetric() -> None:
    snapshot = _snapshot()
    assert snapshot.candidates[0].competing_candidate_ids == (OTHER_CANDIDATE,)
    with pytest.raises(FormalRuleArtifactError):
        FormalRuleSnapshot(
            ref=_ref(),
            candidates=(
                _candidate(
                    CANDIDATE,
                    constraint="obligation",
                    competing=(OTHER_CANDIDATE,),
                ),
                _candidate(OTHER_CANDIDATE, constraint="prohibition"),
            ),
            rules=_snapshot().rules,
            versions=_snapshot().versions,
            coverage=FormalRuleCoverage(1, 1),
            counts=FormalRuleCounts(candidates=2, rules=2, versions=1),
            provenance_code="ok",
        )


def test_digest_and_publication_id_are_content_addressed() -> None:
    first = _snapshot()
    second = _snapshot()
    payload = encode_formal_rule_snapshot(first)
    assert formal_rule_digest(payload) == formal_rule_digest(
        encode_formal_rule_snapshot(second)
    )
    assert compute_formal_rule_publication_id(first) == (
        compute_formal_rule_publication_id(second)
    )
    assert compute_formal_rule_publication_id(first).startswith("frule-pub-")


def test_organization_snapshot_v1_v2_v3_remain_byte_verifiable() -> None:
    from simulation import (
        ORGANIZATION_SNAPSHOT_SCHEMA_VERSION,
        ORGANIZATION_SNAPSHOT_SCHEMA_VERSION_V1,
        ORGANIZATION_SNAPSHOT_SCHEMA_VERSION_V2,
        SUPPORTED_ORGANIZATION_SNAPSHOT_SCHEMAS,
    )

    assert ORGANIZATION_SNAPSHOT_SCHEMA_VERSION_V1 == "organization-snapshot-v1"
    assert ORGANIZATION_SNAPSHOT_SCHEMA_VERSION_V2 == "organization-snapshot-v2"
    assert ORGANIZATION_SNAPSHOT_SCHEMA_VERSION == "organization-snapshot-v3"
    assert SUPPORTED_ORGANIZATION_SNAPSHOT_SCHEMAS == (
        "organization-snapshot-v1",
        "organization-snapshot-v2",
        "organization-snapshot-v3",
    )
