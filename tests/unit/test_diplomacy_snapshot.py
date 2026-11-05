"""V4-10 diplomacy snapshot and codec tests."""

from __future__ import annotations

from dataclasses import replace

import pytest

from simulation.diplomacy_codec import (
    compute_diplomacy_publication_id,
    decode_diplomacy_snapshot,
    diplomacy_snapshot_digest,
    encode_diplomacy_snapshot,
    finalize_diplomacy_snapshot,
)
from simulation.diplomacy_models import (
    DIPLOMACY_SNAPSHOT_SCHEMA,
    MAX_SNAPSHOT_PARTIES,
    DiplomacyArtifactError,
    DiplomacySnapshot,
    DiplomacySnapshotContactRow,
    DiplomacySnapshotDeclarationRow,
    DiplomacySnapshotEnvoyRow,
    DiplomacySnapshotInstrumentRow,
    DiplomacySnapshotPartyRow,
    DiplomacySnapshotRelationRow,
    DiplomacySnapshotTerminationRow,
    empty_diplomacy_snapshot,
)

pytestmark = pytest.mark.unit

OWNER = "0" * 16
OTHER = "1" * 16
RELATION = "dpl-" + "2" * 16
INSTRUMENT = "dpi-" + "3" * 16
PARTY = "dpp-" + "4" * 16
CONTACT = "dpc-" + "5" * 16
ENVOY = "dpe-" + "6" * 16
DECLARATION = "dpd-" + "7" * 16
TERMINATION = "dpt-" + "8" * 16
ORG = "orgc-" + "9" * 16
REGION = "region-1"


def _snapshot() -> DiplomacySnapshot:
    return finalize_diplomacy_snapshot(
        DiplomacySnapshot(
            run_id="run-1",
            created_revision="rev-1",
            window_end=4,
            relations=(
                DiplomacySnapshotRelationRow(
                    relation_id=RELATION,
                    owner_token=OWNER,
                    party_tokens=(OWNER, OTHER),
                    opened_tick=1,
                    last_tick=3,
                    provenance="communicated",
                ),
            ),
            parties=(
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
                    party_id=PARTY,
                    owner_token=OWNER,
                    party_token=OTHER,
                    party_kind="agent",
                    resolution="resolved",
                    first_seen_tick=1,
                    provenance="communicated",
                ),
                DiplomacySnapshotPartyRow(
                    party_id="dpp-" + "a" * 16,
                    owner_token=OWNER,
                    party_token=ORG,
                    party_kind="organization",
                    resolution="unresolved",
                    first_seen_tick=1,
                    provenance="communicated",
                ),
            ),
            contacts=(
                DiplomacySnapshotContactRow(
                    contact_id=CONTACT,
                    relation_id=RELATION,
                    owner_token=OWNER,
                    tick=1,
                    contact_kind="direct_co_presence",
                    location_anchor=REGION,
                    participant_count=2,
                    provenance="witnessed_contact",
                ),
            ),
            envoys=(
                DiplomacySnapshotEnvoyRow(
                    envoy_id=ENVOY,
                    relation_id=RELATION,
                    owner_token=OWNER,
                    party_token=OTHER,
                    envoy_token=OTHER,
                    mandate_token="rmd-" + "b" * 16,
                    status="claimed",
                    accredited_tick=1,
                    end_tick=None,
                    provenance="communicated",
                ),
            ),
            instruments=(
                DiplomacySnapshotInstrumentRow(
                    instrument_id=INSTRUMENT,
                    relation_id=RELATION,
                    owner_token=OWNER,
                    party_tokens=(OWNER, OTHER),
                    instrument_kind="proposal",
                    term_kind="material_exchange",
                    subject_token="c" * 16,
                    opener_envoy_token=None,
                    opened_tick=2,
                    end_tick=None,
                    anchor_refs=(ORG,),
                    provenance="communicated",
                ),
            ),
            declarations=(
                DiplomacySnapshotDeclarationRow(
                    declaration_id=DECLARATION,
                    instrument_id=INSTRUMENT,
                    owner_token=OWNER,
                    party_token=OTHER,
                    envoy_token=None,
                    act="accept",
                    declared_tick=2,
                    provenance="communicated",
                ),
            ),
            terminations=(
                DiplomacySnapshotTerminationRow(
                    termination_id=TERMINATION,
                    owner_token=OWNER,
                    target_kind="instrument",
                    target_ref=INSTRUMENT,
                    kind="superseded",
                    tick=3,
                    provenance="communicated",
                ),
            ),
        )
    )


def test_round_trip_and_digest_are_stable() -> None:
    snapshot = _snapshot()
    payload = encode_diplomacy_snapshot(snapshot)
    decoded = decode_diplomacy_snapshot(payload)
    assert decoded == snapshot
    assert decoded.digest == snapshot.digest
    assert decode_diplomacy_snapshot(encode_diplomacy_snapshot(decoded)) == decoded
    assert diplomacy_snapshot_digest(snapshot) == snapshot.digest


def test_publication_id_is_content_addressed() -> None:
    snapshot = _snapshot()
    assert snapshot.publication_id.startswith("dip-pub-")
    assert snapshot.publication_id == compute_diplomacy_publication_id(
        snapshot.run_id, snapshot.digest
    )
    assert compute_diplomacy_publication_id("run-1", snapshot.digest) != (
        compute_diplomacy_publication_id("run-2", snapshot.digest)
    )


def test_unknown_schema_and_key_are_rejected() -> None:
    with pytest.raises(DiplomacyArtifactError) as excinfo:
        replace(_snapshot(), schema_version="diplomacy-snapshot-v9")
    assert excinfo.value.code == "diplomacy_snapshot_schema_unknown"

    payload = encode_diplomacy_snapshot(_snapshot()).replace(
        b'"window_end"', b'"extra":1,"window_end"'
    )
    with pytest.raises(DiplomacyArtifactError):
        decode_diplomacy_snapshot(payload)


def test_tampered_digest_is_rejected() -> None:
    snapshot = _snapshot()
    payload = encode_diplomacy_snapshot(snapshot).replace(
        snapshot.digest.encode(), b"0" * 64
    )
    with pytest.raises(DiplomacyArtifactError) as excinfo:
        decode_diplomacy_snapshot(payload)
    assert excinfo.value.code == "diplomacy_snapshot_digest_mismatch"


def test_caps_and_foreign_references_fail_closed() -> None:
    snapshot = empty_diplomacy_snapshot("run-1", revision="rev-1", window_end=1)
    too_many = tuple(
        DiplomacySnapshotPartyRow(
            party_id="dpp-" + f"{index:016x}",
            owner_token=OWNER,
            party_token=f"{index:016x}",
            party_kind="agent",
            resolution="resolved",
            first_seen_tick=1,
            provenance="communicated",
        )
        for index in range(MAX_SNAPSHOT_PARTIES + 1)
    )
    with pytest.raises(DiplomacyArtifactError) as excinfo:
        replace(snapshot, parties=too_many)
    assert excinfo.value.code == "diplomacy_snapshot_size_limit"

    relation = _snapshot().relations[0]
    with pytest.raises(DiplomacyArtifactError) as excinfo:
        replace(snapshot, relations=(relation,))
    assert excinfo.value.code == "diplomacy_snapshot_foreign_reference"


def test_raw_agent_ids_and_free_text_are_rejected() -> None:
    snapshot = empty_diplomacy_snapshot("run-1", revision="rev-1", window_end=1)
    with pytest.raises(DiplomacyArtifactError):
        replace(
            snapshot,
            parties=(
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
                    party_id=PARTY,
                    owner_token=OWNER,
                    party_token="agent-b",
                    party_kind="agent",
                    resolution="resolved",
                    first_seen_tick=1,
                    provenance="communicated",
                ),
            ),
        )
    with pytest.raises(DiplomacyArtifactError):
        replace(
            snapshot,
            instruments=(
                DiplomacySnapshotInstrumentRow(
                    instrument_id=INSTRUMENT,
                    relation_id=RELATION,
                    owner_token=OWNER,
                    party_tokens=(OWNER, OTHER),
                    instrument_kind="proposal",
                    term_kind="material_exchange",
                    subject_token="free text",
                    opener_envoy_token=None,
                    opened_tick=1,
                    end_tick=None,
                    anchor_refs=(),
                    provenance="communicated",
                ),
            ),
        )


def test_existing_snapshot_schemas_remain_unchanged() -> None:
    from simulation.delegation_representation_models import (
        DELEGATION_REPRESENTATION_SNAPSHOT_SCHEMA,
    )
    from simulation.dispute_models import DISPUTE_SNAPSHOT_SCHEMA
    from simulation.evidence_testimony_models import EVIDENCE_TESTIMONY_SNAPSHOT_SCHEMA
    from simulation.formal_rule_models import FORMAL_RULE_SNAPSHOT_SCHEMA
    from simulation.organization_models import ORGANIZATION_SNAPSHOT_SCHEMA_VERSION

    assert DIPLOMACY_SNAPSHOT_SCHEMA == "diplomacy-snapshot-v2"
    assert DELEGATION_REPRESENTATION_SNAPSHOT_SCHEMA == (
        "delegation-representation-snapshot-v1"
    )
    assert ORGANIZATION_SNAPSHOT_SCHEMA_VERSION == "organization-snapshot-v3"
    assert FORMAL_RULE_SNAPSHOT_SCHEMA == "formal-rule-snapshot-v1"
    assert DISPUTE_SNAPSHOT_SCHEMA == "dispute-resolution-snapshot-v1"
    assert EVIDENCE_TESTIMONY_SNAPSHOT_SCHEMA == "evidence-testimony-snapshot-v1"


def test_publication_ids_are_not_candidate_ids() -> None:
    from analysis.diplomacy_contract import (
        DiplomacyAnalysisError,
        require_diplomacy_candidate_id,
    )

    with pytest.raises(DiplomacyAnalysisError):
        require_diplomacy_candidate_id("dip-pub-" + "a" * 16)
