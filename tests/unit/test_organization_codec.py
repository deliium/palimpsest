"""Canonical organization snapshot codec: exactness, caps, and identity."""

from __future__ import annotations

import json

import pytest

from simulation.organization_codec import (
    compute_organization_publication_id,
    decode_organization_snapshot,
    encode_organization_snapshot,
    organization_digest,
)
from simulation.organization_models import (
    MAX_SNAPSHOT_BYTES,
    OrganizationArtifactError,
)
from tests.unit.organization_artifact_helpers import example_snapshot

pytestmark = pytest.mark.unit


def test_round_trip_is_byte_identical() -> None:
    snapshot = example_snapshot()
    payload = encode_organization_snapshot(snapshot)
    decoded = decode_organization_snapshot(payload)
    assert decoded == snapshot
    assert encode_organization_snapshot(decoded) == payload
    assert len(organization_digest(payload)) == 64


def test_extra_and_missing_keys_fail_closed() -> None:
    payload = encode_organization_snapshot(example_snapshot())
    data = json.loads(payload)
    data["extra"] = True
    with pytest.raises(OrganizationArtifactError):
        decode_organization_snapshot(json.dumps(data).encode() + b"\n")

    data = json.loads(payload)
    data.pop("windows")
    with pytest.raises(OrganizationArtifactError):
        decode_organization_snapshot(json.dumps(data).encode() + b"\n")


def test_duplicate_keys_and_non_finite_floats_are_rejected() -> None:
    with pytest.raises(OrganizationArtifactError):
        decode_organization_snapshot(b'{"a":1,"a":2}\n')
    with pytest.raises(OrganizationArtifactError):
        decode_organization_snapshot(b'{"a":NaN}\n')


def test_oversize_payload_is_rejected() -> None:
    with pytest.raises(OrganizationArtifactError) as excinfo:
        decode_organization_snapshot(b" " * (MAX_SNAPSHOT_BYTES + 1))
    assert excinfo.value.code == "organization_size_limit"


def test_publication_id_is_stable_and_run_bound() -> None:
    snapshot = example_snapshot()
    first = compute_organization_publication_id(snapshot)
    second = compute_organization_publication_id(snapshot)
    assert first == second
    assert first.startswith("org-edge-")
    assert len(first) == len("org-edge-") + 16

    from dataclasses import replace

    other_run = replace(snapshot, run_id="run-organization-2")
    assert compute_organization_publication_id(other_run) != first

    published = replace(snapshot, publication_id=first)
    assert compute_organization_publication_id(published) == first


def test_member_change_changes_digest_and_publication_id() -> None:
    from dataclasses import replace

    snapshot = example_snapshot()
    candidate = snapshot.candidates[0]
    changed_member = replace(candidate.members[1], status="former")
    changed_candidate = replace(
        candidate, members=(candidate.members[0], changed_member)
    )
    changed = replace(
        snapshot,
        candidates=(changed_candidate, snapshot.candidates[1]),
    )
    assert organization_digest(encode_organization_snapshot(changed)) != (
        organization_digest(encode_organization_snapshot(snapshot))
    )
    assert compute_organization_publication_id(changed) != (
        compute_organization_publication_id(snapshot)
    )


def test_snapshot_contains_no_owner_or_owner_local_ids() -> None:
    payload = encode_organization_snapshot(example_snapshot()).decode()
    assert "orgc-" not in payload
    assert "owner_id" not in payload
    assert "ade" not in payload.replace("body-ada", "")
