# mypy: ignore-errors
"""V4-33 atomic filesystem diffusion store: quota, idempotence, corruption."""

from __future__ import annotations

import dataclasses
import json
import os

import pytest

from persistence.science_diffusion_filesystem import (
    SCIENCE_DIFFUSION_STORE_VERSION,
    FilesystemScienceDiffusionStore,
)
from simulation.science_diffusion_codec import science_diffusion_publication_id
from simulation.science_diffusion_models import ScienceDiffusionPublicationOptions
from tests.unit.test_science_diffusion_snapshot import _snapshot

pytestmark = pytest.mark.unit


def _store(tmp_path, **kwargs):
    return FilesystemScienceDiffusionStore(
        tmp_path,
        options=ScienceDiffusionPublicationOptions(**kwargs),
    )


def _variant(snapshot, tick: int):
    draft = dataclasses.replace(
        snapshot, publication_id="sdf-pending", boundary_tick=tick
    )
    return dataclasses.replace(
        draft, publication_id=science_diffusion_publication_id(draft)
    )


def test_publish_read_and_idempotence(tmp_path) -> None:
    store = _store(tmp_path)
    snapshot = _snapshot()
    receipt = store.publish(snapshot)
    assert receipt.stored is True
    assert store.list_publications(snapshot.run_id) == (snapshot.publication_id,)
    read = store.read(snapshot.run_id)
    assert read == snapshot
    assert store.latest_publication_id(snapshot.run_id) == snapshot.publication_id

    repeat = store.publish(snapshot)
    assert repeat.stored is False
    assert repeat.reason == "published"
    assert store.list_publications(snapshot.run_id) == (snapshot.publication_id,)


def test_quota_does_not_displace_earlier_publication(tmp_path) -> None:
    store = _store(tmp_path, max_publications=1)
    first = _snapshot()
    assert store.publish(first).stored is True
    second = _variant(first, 65)
    rejected = store.publish(second)
    assert rejected.stored is False
    assert rejected.reason == "quota_exceeded"
    assert store.list_publications(first.run_id) == (first.publication_id,)
    assert store.read(first.run_id, first.publication_id) == first


def test_corrupt_index_fails_closed(tmp_path) -> None:
    store = _store(tmp_path)
    snapshot = _snapshot()
    store.publish(snapshot)
    run_dir = tmp_path / snapshot.run_id
    (run_dir / "state.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError):
        store.read(snapshot.run_id)


def test_symlinked_blob_is_rejected(tmp_path) -> None:
    store = _store(tmp_path)
    snapshot = _snapshot()
    store.publish(snapshot)
    run_dir = tmp_path / snapshot.run_id
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    digest = state["publications"][0]["digest"]
    blob = run_dir / "blobs" / f"{digest}.json"
    material = blob.read_bytes()
    outside = tmp_path / "outside.json"
    outside.write_bytes(material)
    blob.unlink()
    os.symlink(outside, blob)
    with pytest.raises(ValueError):
        store.read(snapshot.run_id)


def test_unreferenced_staged_blob_is_invisible(tmp_path) -> None:
    store = _store(tmp_path)
    snapshot = _snapshot()
    store.publish(snapshot)
    run_dir = tmp_path / snapshot.run_id
    orphan = run_dir / "blobs" / "orphan.json"
    orphan.write_bytes(b"{}")
    assert store.read(snapshot.run_id) == snapshot
    assert store.list_publications(snapshot.run_id) == (snapshot.publication_id,)


def test_path_components_and_index_limits_fail_closed(tmp_path) -> None:
    store = _store(tmp_path)
    with pytest.raises(ValueError):
        store.read("../escape")
    with pytest.raises(ValueError):
        store.read("run/with/slash")

    tiny = _store(tmp_path / "tiny", max_index_bytes=64)
    snapshot = _snapshot()
    receipt = tiny.publish(snapshot)
    assert receipt.stored is False
    assert receipt.reason == "quota_exceeded"
    assert tiny.list_publications(snapshot.run_id) == ()


def test_store_version_is_exact(tmp_path) -> None:
    assert SCIENCE_DIFFUSION_STORE_VERSION == "science-diffusion-store-v1"
    store = _store(tmp_path)
    snapshot = _snapshot()
    store.publish(snapshot)
    state = json.loads(
        (tmp_path / snapshot.run_id / "state.json").read_text(encoding="utf-8")
    )
    assert state["version"] == SCIENCE_DIFFUSION_STORE_VERSION
