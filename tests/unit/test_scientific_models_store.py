# mypy: ignore-errors

"""Immutable filesystem publication: atomicity, quotas, digests, isolation."""

from __future__ import annotations

import dataclasses
import os
from pathlib import Path

import pytest

from persistence.scientific_models_filesystem import (
    FilesystemScientificModelsStore,
    ScientificModelsStoreError,
    ScientificModelsStoreOptions,
    scientific_models_store_publisher,
    scientific_models_store_reader,
)
from simulation.scientific_models_codec import scientific_models_snapshot_digest
from tests.unit.test_scientific_models_snapshot import _snapshot

pytestmark = pytest.mark.unit

_RUN = "3" * 32


def _store(
    root: Path, *, enabled: bool = True, publications: int = 16
) -> FilesystemScientificModelsStore:
    return FilesystemScientificModelsStore(
        root,
        options=ScientificModelsStoreOptions(
            enabled=enabled, max_publications=publications
        ),
    )


def _publication(publication_id: str):
    return dataclasses.replace(_snapshot(), publication_id=publication_id)


def test_round_trip_and_idempotent_publication(tmp_path: Path) -> None:
    store = _store(tmp_path)
    snapshot = _snapshot()
    first = store.publish(snapshot)
    second = store.publish(snapshot)
    assert first.stored is True and second.stored is True
    assert store.list_publications(_RUN) == (snapshot.publication_id,)
    loaded = store.read_snapshot(_RUN, snapshot.publication_id)
    assert scientific_models_snapshot_digest(loaded) == (
        scientific_models_snapshot_digest(snapshot)
    )


def test_older_publications_remain_readable(tmp_path: Path) -> None:
    store = _store(tmp_path)
    first = _publication("a" * 32)
    second = _publication("b" * 32)
    assert store.publish(first).stored is True
    assert store.publish(second).stored is True
    assert store.list_publications(_RUN) == (
        first.publication_id,
        second.publication_id,
    )
    assert store.read_snapshot(_RUN, first.publication_id) == store.read_snapshot(
        _RUN, first.publication_id
    )


def test_cumulative_quota_refuses_without_dropping_history(tmp_path: Path) -> None:
    store = _store(tmp_path, publications=1)
    assert store.publish(_publication("a" * 32)).stored is True
    receipt = store.publish(_publication("b" * 32))
    assert receipt.stored is False
    assert receipt.reason == "quota_exceeded"
    assert store.list_publications(_RUN) == ("a" * 32,)


def test_corrupt_child_and_manifest_are_detected(tmp_path: Path) -> None:
    store = _store(tmp_path)
    snapshot = _snapshot()
    store.publish(snapshot)
    child = tmp_path / _RUN / f"{snapshot.publication_id}.json"
    child.write_bytes(child.read_bytes() + b" ")
    with pytest.raises(ScientificModelsStoreError) as exc:
        store.read_snapshot(_RUN, snapshot.publication_id)
    assert exc.value.code == "scientific_models_store_corrupt"
    manifest = tmp_path / _RUN / "state.json"
    manifest.write_text("{}", encoding="utf-8")
    with pytest.raises(ScientificModelsStoreError):
        store.list_publications(_RUN)


def test_run_and_publication_missing_are_distinct(tmp_path: Path) -> None:
    reader = scientific_models_store_reader(
        tmp_path, options=ScientificModelsStoreOptions(enabled=False)
    )
    with pytest.raises(ScientificModelsStoreError) as exc:
        reader.list_publications(_RUN)
    assert exc.value.code == "scientific_models_store_run_missing"
    store = _store(tmp_path)
    store.publish(_snapshot())
    with pytest.raises(ScientificModelsStoreError) as exc:
        store.read_snapshot(_RUN, "f" * 32)
    assert exc.value.code == "scientific_models_store_publication_missing"


def test_disabled_publisher_and_unsafe_components(tmp_path: Path) -> None:
    disabled = scientific_models_store_publisher(
        tmp_path, options=ScientificModelsStoreOptions(enabled=False)
    )
    receipt = disabled.publish(_snapshot())
    assert receipt.stored is False
    assert receipt.reason == "disabled"
    assert not (tmp_path / _RUN).exists()
    reader = _store(tmp_path)
    with pytest.raises(ScientificModelsStoreError) as exc:
        reader.read_snapshot("../escape", "a" * 32)
    assert exc.value.code == "scientific_models_store_invalid_run"
    with pytest.raises(ValueError, match="invalid_positive_int"):
        ScientificModelsStoreOptions(max_publications=True)


def test_symlinked_child_is_corrupt(tmp_path: Path) -> None:
    store = _store(tmp_path)
    snapshot = _snapshot()
    store.publish(snapshot)
    child = tmp_path / _RUN / f"{snapshot.publication_id}.json"
    other = tmp_path / "other.json"
    other.write_bytes(child.read_bytes())
    child.unlink()
    os.symlink(other, child)
    with pytest.raises(ScientificModelsStoreError) as exc:
        store.read_snapshot(_RUN, snapshot.publication_id)
    assert exc.value.code == "scientific_models_store_corrupt"
