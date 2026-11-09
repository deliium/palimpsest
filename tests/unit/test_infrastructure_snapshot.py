"""infrastructure-networks-snapshot-v1 round-trip, size, duplicate, corrupt."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from analysis.infrastructure_networks_analysis import (
    harvest_infrastructure_networks_analysis,
)
from experiments.infrastructure_completed_run import (
    compose_infrastructure_networks_snapshot,
)
from experiments.infrastructure_publication import (
    publish_infrastructure_networks_snapshot,
)
from persistence.infrastructure_filesystem import (
    create_infrastructure_networks_publisher,
    create_infrastructure_networks_reader,
)
from simulation.infrastructure_codec import (
    decode_infrastructure_networks_snapshot,
    encode_infrastructure_networks_snapshot,
)
from simulation.infrastructure_models import (
    INFRASTRUCTURE_MAX_BYTES,
    INFRASTRUCTURE_NETWORKS_SNAPSHOT_VERSION,
    INFRASTRUCTURE_NETWORKS_STORE_VERSION,
    InfrastructureNetworksArtifactError,
)
from world.identifiers import EntityId
from world.infrastructure import (
    InfrastructureAsset,
    InfrastructureKind,
    InfrastructureStatus,
    InfrastructureTopology,
    mint_infrastructure_id,
)

pytestmark = pytest.mark.unit


def _asset(
    kind: InfrastructureKind,
    *,
    project: str,
    endpoint: str | None = None,
    status: InfrastructureStatus = InfrastructureStatus.OPERATIONAL,
    integrity: float = 1.0,
) -> InfrastructureAsset:
    location_id = EntityId("loc-a")
    endpoint_id = None if endpoint is None else EntityId(endpoint)
    project_id = EntityId(project)
    return InfrastructureAsset(
        asset_id=mint_infrastructure_id(
            kind=kind,
            location_id=location_id,
            endpoint_location_id=endpoint_id,
            created_tick=1,
            project_id=project_id,
        ),
        kind=kind,
        topology=(
            InfrastructureTopology.EDGE
            if endpoint is not None
            else InfrastructureTopology.NODE
        ),
        status=status,
        integrity=integrity,
        location_id=location_id,
        endpoint_location_id=endpoint_id,
        linked_structure_id=EntityId(f"struct-{project}"),
        linked_project_id=project_id,
        created_tick=1,
        last_maintained_tick=1,
    )


def test_schema_and_store_versions() -> None:
    assert INFRASTRUCTURE_NETWORKS_SNAPSHOT_VERSION == (
        "infrastructure-networks-snapshot-v1"
    )
    assert INFRASTRUCTURE_NETWORKS_STORE_VERSION == "infrastructure-networks-store-v1"
    assert INFRASTRUCTURE_MAX_BYTES == 4 * 1024 * 1024


def test_codec_round_trip() -> None:
    analysis = harvest_infrastructure_networks_analysis(
        (
            _asset(InfrastructureKind.BRIDGE, project="b1"),
            _asset(InfrastructureKind.ROAD, project="r1", endpoint="loc-b"),
        ),
        window_tick=10,
    )
    snapshot = compose_infrastructure_networks_snapshot(analysis, run_id="run-infra")
    encoded = encode_infrastructure_networks_snapshot(snapshot)
    decoded = decode_infrastructure_networks_snapshot(encoded)
    assert decoded.digest == snapshot.digest
    assert decoded.publication_id == snapshot.publication_id
    assert decoded.summary.asset_count == 2
    assert decoded.summary.edge_count == 1
    assert b"score" not in encoded


def test_empty_snapshot_finalize() -> None:
    snapshot = compose_infrastructure_networks_snapshot(
        harvest_infrastructure_networks_analysis(()), run_id="run-empty"
    )
    assert snapshot.summary.asset_count == 0
    assert snapshot.publication_id.startswith("infra-pub-")
    assert len(snapshot.digest) == 64


def test_filesystem_publish_duplicate_and_corrupt(tmp_path: Path) -> None:
    analysis = harvest_infrastructure_networks_analysis(
        (_asset(InfrastructureKind.STORAGE, project="s1"),),
        window_tick=5,
    )
    snapshot = compose_infrastructure_networks_snapshot(analysis, run_id="run-store")
    publisher = create_infrastructure_networks_publisher(tmp_path)
    publisher.publish(snapshot)
    publisher.publish(snapshot)

    run_dir = tmp_path / "run-store"
    pub_path = run_dir / f"{snapshot.publication_id}.json"
    pub_path.write_bytes(b'{"different":true}\n')
    with pytest.raises(ValueError, match="infrastructure_networks_publication_exists"):
        publisher.publish(snapshot)

    pub_path.write_bytes(b"{not-json")
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    state["publications"][snapshot.publication_id]["digest"] = snapshot.digest
    (run_dir / "state.json").write_text(
        json.dumps(state, sort_keys=True), encoding="utf-8"
    )
    reader = create_infrastructure_networks_reader(tmp_path)
    with pytest.raises(ValueError, match="infrastructure_networks_store_corrupt"):
        reader.read_snapshot("run-store")


def test_decode_corrupt_payload() -> None:
    with pytest.raises(
        InfrastructureNetworksArtifactError,
        match="infrastructure_networks_store_corrupt",
    ):
        decode_infrastructure_networks_snapshot(b"{not-json")


def test_publication_disabled_receipt() -> None:
    receipt = publish_infrastructure_networks_snapshot(
        object(),
        None,
        run_id="run-disabled",
    )
    assert receipt.status == "disabled"
    assert receipt.reason == "root_unset"
