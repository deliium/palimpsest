# mypy: ignore-errors
"""V4-11 diplomacy-snapshot-v2 treaty rows and v1 compatibility."""

from __future__ import annotations

from dataclasses import replace

import pytest

from simulation.diplomacy_codec import (
    decode_diplomacy_snapshot,
    diplomacy_snapshot_digest,
    encode_diplomacy_snapshot,
    finalize_diplomacy_snapshot,
)
from simulation.diplomacy_models import (
    DIPLOMACY_SNAPSHOT_POLICY_V1,
    DIPLOMACY_SNAPSHOT_SCHEMA_VERSION_V1,
    DIPLOMACY_SNAPSHOT_SCHEMA_VERSION_V2,
    DiplomacyArtifactError,
    DiplomacySnapshot,
    DiplomacySnapshotPartyRow,
    DiplomacySnapshotRelationRow,
    DiplomacySnapshotTreatyDeclarationRow,
    DiplomacySnapshotTreatyLineageRow,
    DiplomacySnapshotTreatyMisrepresentationRow,
    DiplomacySnapshotTreatyRecollectionRow,
    DiplomacySnapshotTreatyRow,
    DiplomacySnapshotTreatyVersionRow,
    empty_diplomacy_snapshot,
)

pytestmark = pytest.mark.unit

OWNER = "a" * 16
PEER = "b" * 16
TREATY = "dpg-" + "0" * 16
VERSION = "dpv-" + "0" * 16
VERSION2 = "dpv-" + "1" * 16
RELATION = "dpl-" + "0" * 16


def _base() -> DiplomacySnapshot:
    return empty_diplomacy_snapshot("run-1", revision="rev-1", window_end=4)


def _v2() -> DiplomacySnapshot:
    snapshot = _base()
    return DiplomacySnapshot(
        **{
            **{
                field: getattr(snapshot, field)
                for field in (
                    "run_id",
                    "created_revision",
                    "window_end",
                    "coverage",
                    "summary",
                    "metric_families",
                )
            },
            "policy_version": snapshot.policy_version,
            "schema_version": DIPLOMACY_SNAPSHOT_SCHEMA_VERSION_V2,
            "relations": (
                DiplomacySnapshotRelationRow(
                    relation_id=RELATION,
                    owner_token=OWNER,
                    party_tokens=(OWNER, PEER),
                    opened_tick=1,
                    last_tick=4,
                    provenance="communicated",
                ),
            ),
            "parties": (
                DiplomacySnapshotPartyRow(
                    party_id="dpp-" + "0" * 16,
                    owner_token=OWNER,
                    party_token=OWNER,
                    party_kind="agent",
                    resolution="resolved",
                    first_seen_tick=1,
                    provenance="self_declared",
                ),
                DiplomacySnapshotPartyRow(
                    party_id="dpp-" + "1" * 16,
                    owner_token=OWNER,
                    party_token=PEER,
                    party_kind="agent",
                    resolution="resolved",
                    first_seen_tick=1,
                    provenance="communicated",
                ),
            ),
            "treaties": (
                DiplomacySnapshotTreatyRow(
                    treaty_id=TREATY,
                    relation_id=RELATION,
                    owner_token=OWNER,
                    party_tokens=(OWNER, PEER),
                    subject_kind="ceasefire",
                    current_version_id=VERSION2,
                    status="apparently_accepted",
                    opened_tick=1,
                    last_tick=4,
                    provenance="communicated",
                ),
            ),
            "treaty_versions": (
                DiplomacySnapshotTreatyVersionRow(
                    version_id=VERSION,
                    treaty_id=TREATY,
                    owner_token=OWNER,
                    version_index=1,
                    parent_version_ids=(),
                    change_kind="original",
                    status="superseded",
                    acceptance_basis="superseded",
                    party_tokens=(OWNER, PEER),
                    provision_kinds=("non_hostility",),
                    terms_digest="a" * 64,
                    record_refs=("record-1",),
                    institutional_memory_refs=(),
                    effective_tick=1,
                    end_tick=None,
                    proposer_party_token=OWNER,
                    proposer_envoy_token=None,
                    provenance="communicated",
                ),
                DiplomacySnapshotTreatyVersionRow(
                    version_id=VERSION2,
                    treaty_id=TREATY,
                    owner_token=OWNER,
                    version_index=2,
                    parent_version_ids=(VERSION,),
                    change_kind="renewal",
                    status="apparently_accepted",
                    acceptance_basis="all_participants_declared",
                    party_tokens=(OWNER, PEER),
                    provision_kinds=("non_hostility",),
                    terms_digest="b" * 64,
                    record_refs=(),
                    institutional_memory_refs=("c" * 64,),
                    effective_tick=2,
                    end_tick=4,
                    proposer_party_token=OWNER,
                    proposer_envoy_token=None,
                    provenance="communicated",
                ),
            ),
            "treaty_declarations": (
                DiplomacySnapshotTreatyDeclarationRow(
                    declaration_id="dpq-" + "0" * 16,
                    treaty_id=TREATY,
                    version_id=VERSION,
                    owner_token=OWNER,
                    party_token=PEER,
                    envoy_token=None,
                    act="accept",
                    declared_tick=2,
                    provenance="communicated",
                ),
            ),
            "treaty_recollections": (
                DiplomacySnapshotTreatyRecollectionRow(
                    recollection_id="dpz-" + "0" * 16,
                    owner_token=OWNER,
                    treaty_ref=TREATY,
                    version_ref=VERSION,
                    subject_kind="ceasefire",
                    basis="durable_record",
                    stance="remember",
                    claimed_terms_digest="a" * 64,
                    confidence=0.5,
                    first_tick=3,
                    last_tick=3,
                    provenance="communicated",
                ),
            ),
            "treaty_misrepresentations": (
                DiplomacySnapshotTreatyMisrepresentationRow(
                    misrepresentation_id="dpj-" + "0" * 16,
                    version_id=VERSION,
                    owner_token=OWNER,
                    kind="scope_exceeded",
                    observed_tick=3,
                    envoy_token=PEER,
                    party_token=OWNER,
                    provenance="representation_belief",
                ),
            ),
            "treaty_lineage": (
                DiplomacySnapshotTreatyLineageRow(
                    edge_id="dip-edge-" + "0" * 16,
                    treaty_id=TREATY,
                    from_version_id=VERSION,
                    to_version_id=VERSION2,
                    change_kind="renewal",
                    tick=2,
                ),
            ),
        }
    )


def test_v2_round_trips_and_digest_is_stable() -> None:
    snapshot = finalize_diplomacy_snapshot(_v2())
    encoded = encode_diplomacy_snapshot(snapshot)
    decoded = decode_diplomacy_snapshot(encoded)
    assert decoded == snapshot
    assert decoded.schema_version == DIPLOMACY_SNAPSHOT_SCHEMA_VERSION_V2
    assert decoded.treaties[0].status == "apparently_accepted"
    assert decoded.treaty_versions[1].parent_version_ids == (VERSION,)
    assert diplomacy_snapshot_digest(decoded) == snapshot.digest


def test_v1_still_decodes_and_has_no_treaty_rows() -> None:
    v1 = DiplomacySnapshot(
        run_id="run-1",
        created_revision="rev-1",
        window_end=4,
        schema_version=DIPLOMACY_SNAPSHOT_SCHEMA_VERSION_V1,
        policy_version=DIPLOMACY_SNAPSHOT_POLICY_V1,
    )
    finalized = finalize_diplomacy_snapshot(v1)
    decoded = decode_diplomacy_snapshot(encode_diplomacy_snapshot(finalized))
    assert decoded.schema_version == DIPLOMACY_SNAPSHOT_SCHEMA_VERSION_V1
    assert decoded.treaties == ()
    assert decoded.treaty_versions == ()


def test_v2_rejects_foreign_participants_owner_and_closed_labels() -> None:
    snapshot = _v2()
    bad_party = replace(
        snapshot.treaties[0],
        party_tokens=(snapshot.treaties[0].party_tokens[0], "deadbeefdeadbeef"),
    )
    with pytest.raises(DiplomacyArtifactError):
        replace(snapshot, treaties=(bad_party,))
    bad_owner = replace(snapshot.treaty_versions[0], owner_token="c" * 16)
    with pytest.raises(DiplomacyArtifactError):
        replace(
            snapshot,
            treaty_versions=(bad_owner, *snapshot.treaty_versions[1:]),
        )
    with pytest.raises(DiplomacyArtifactError):
        replace(
            snapshot,
            treaties=(
                replace(snapshot.treaties[0], status="invented_status"),
            ),
        )


def test_treaty_snapshot_caps_and_duplicate_ids_fail_closed(monkeypatch) -> None:
    import simulation.diplomacy_models as models

    monkeypatch.setattr(models, "MAX_SNAPSHOT_TREATY_VERSIONS", 0)
    with pytest.raises(DiplomacyArtifactError):
        _v2()
    monkeypatch.undo()
    snapshot = _v2()
    with pytest.raises(DiplomacyArtifactError):
        replace(snapshot, treaties=(snapshot.treaties[0], snapshot.treaties[0]))


def test_raw_agent_id_is_rejected() -> None:
    snapshot = _v2()
    with pytest.raises(DiplomacyArtifactError):
        replace(
            snapshot.treaties[0],
            party_tokens=(snapshot.treaties[0].party_tokens[0], "alice"),
        )


def test_v1_with_treaty_rows_fails() -> None:
    with pytest.raises(DiplomacyArtifactError):
        DiplomacySnapshot(
            run_id="run-1",
            created_revision="rev-1",
            window_end=4,
            schema_version=DIPLOMACY_SNAPSHOT_SCHEMA_VERSION_V1,
            policy_version=DIPLOMACY_SNAPSHOT_POLICY_V1,
            treaties=_v2().treaties,
        )


def test_recollection_with_absent_refs_round_trips() -> None:
    snapshot = _v2()
    recollection = DiplomacySnapshotTreatyRecollectionRow(
        recollection_id="dpz-" + "9" * 16,
        owner_token=OWNER,
        treaty_ref="dpg-" + "9" * 16,
        version_ref="dpv-" + "9" * 16,
        subject_kind="trade",
        basis="narrative",
        stance="ignore",
        claimed_terms_digest=None,
        confidence=0.0,
        first_tick=3,
        last_tick=3,
        provenance="communicated",
    )
    updated = DiplomacySnapshot(
        **{
            **{
                field: getattr(snapshot, field)
                for field in snapshot.__dataclass_fields__
                if field not in {"treaty_recollections", "digest", "publication_id"}
            },
            "treaty_recollections": (
                *snapshot.treaty_recollections,
                recollection,
            ),
        }
    )
    finalized = finalize_diplomacy_snapshot(updated)
    assert decode_diplomacy_snapshot(encode_diplomacy_snapshot(finalized))


def test_forbidden_field_and_bad_digest_fail() -> None:
    with pytest.raises(DiplomacyArtifactError):
        DiplomacySnapshotTreatyVersionRow(
            version_id=VERSION,
            treaty_id=TREATY,
            owner_token=OWNER,
            version_index=1,
            parent_version_ids=(),
            change_kind="original",
            status="proposed",
            acceptance_basis="none",
            party_tokens=(OWNER, PEER),
            provision_kinds=("non_hostility",),
            terms_digest="A" * 64,
            record_refs=(),
            institutional_memory_refs=(),
            effective_tick=1,
            end_tick=None,
            proposer_party_token=OWNER,
            proposer_envoy_token=None,
            provenance="communicated",
        )
