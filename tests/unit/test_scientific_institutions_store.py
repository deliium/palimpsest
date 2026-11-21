# mypy: ignore-errors
"""V4-32 atomic bounded scientific-institution snapshot store."""

from __future__ import annotations

import json

import pytest

from experiments.scientific_institutions_publication import (
    compose_scientific_institutions_snapshot,
)
from persistence.scientific_institutions_filesystem import (
    FilesystemScientificInstitutionsStore,
)
from simulation.scientific_institutions_models import (
    ScientificInstitutionsPublicationOptions,
)
from tests.unit.scientific_institutions_publication_helpers import (
    RUN,
    metric_inputs,
)

pytestmark = pytest.mark.unit


def _snapshot(publication_id: str = "pub-a"):
    return compose_scientific_institutions_snapshot(
        metric_inputs(),
        run_id=RUN,
        publication_id=publication_id,
        input_revision="rev-1",
        boundary_tick=64,
    )


def test_publish_read_latest_and_idempotence(tmp_path) -> None:
    store = FilesystemScientificInstitutionsStore(tmp_path)
    first = store.publish(_snapshot("pub-a"))
    assert first.stored is True
    assert first.digest
    again = store.publish(_snapshot("pub-a"))
    assert again.stored is False
    assert again.reason == "published"
    second = store.publish(_snapshot("pub-b"))
    assert second.stored is True
    assert store.list_publications(RUN) == ("pub-a", "pub-b")
    assert store.latest_publication_id(RUN) == "pub-b"
    assert store.read(RUN) == _snapshot("pub-b")
    assert store.read(RUN, "pub-a") == _snapshot("pub-a")


def test_conflicting_publication_id_is_rejected(tmp_path) -> None:
    store = FilesystemScientificInstitutionsStore(tmp_path)
    store.publish(_snapshot("pub-a"))
    with pytest.raises(ValueError):
        store.publish(
            compose_scientific_institutions_snapshot(
                metric_inputs(),
                run_id=RUN,
                publication_id="pub-a",
                input_revision="rev-2",
                boundary_tick=65,
            )
        )


def test_publication_quota_and_index_cap(tmp_path) -> None:
    options = ScientificInstitutionsPublicationOptions(max_publications=1)
    store = FilesystemScientificInstitutionsStore(tmp_path, options=options)
    assert store.publish(_snapshot("pub-a")).stored is True
    quota = store.publish(_snapshot("pub-b"))
    assert quota.stored is False
    assert quota.reason == "quota_exceeded"


def test_corruption_and_unindexed_blobs_are_not_visible(tmp_path) -> None:
    store = FilesystemScientificInstitutionsStore(tmp_path)
    store.publish(_snapshot("pub-a"))
    run_dir = tmp_path / RUN
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    digest = state["publications"][0]["digest"]
    blob = run_dir / "blobs" / f"{digest}.json"
    blob.write_bytes(b"{}")
    with pytest.raises(ValueError):
        store.read(RUN, "pub-a")
    # A stray unindexed blob never appears as a publication.
    (run_dir / "blobs" / f"{'f' * 64}.json").write_bytes(b"{}")
    assert store.list_publications(RUN) == ("pub-a",)


def test_older_publication_remains_readable_after_newer_commit(tmp_path) -> None:
    store = FilesystemScientificInstitutionsStore(tmp_path)
    first = _snapshot("pub-a")
    store.publish(first)
    store.publish(_snapshot("pub-b"))
    assert store.read(RUN, "pub-a") == first
    assert store.read(RUN, "pub-b") == _snapshot("pub-b")


def test_reader_ignores_temp_files_and_unknown_publications(tmp_path) -> None:
    store = FilesystemScientificInstitutionsStore(tmp_path)
    store.publish(_snapshot("pub-a"))
    run_dir = tmp_path / RUN
    (run_dir / "blobs" / ".tmp-stale").write_bytes(b"not-a-snapshot")
    assert store.read(RUN, "missing") is None
    assert store.latest_publication_id(RUN) == "pub-a"


def test_retry_reuses_verified_unindexed_blob(tmp_path) -> None:
    import hashlib

    from simulation.scientific_institutions_codec import (
        canonical_scientific_institutions_json,
    )

    store = FilesystemScientificInstitutionsStore(tmp_path)
    snapshot = _snapshot("pub-orphan")
    material = canonical_scientific_institutions_json(snapshot)
    digest = hashlib.sha256(material).hexdigest()
    run_dir = tmp_path / RUN
    blobs = run_dir / "blobs"
    blobs.mkdir(parents=True)
    (blobs / f"{digest}.json").write_bytes(material)
    (run_dir / "state.json").write_text(
        json.dumps(
            {
                "version": "scientific-institutions-store-v1",
                "publications": [],
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    assert store.list_publications(RUN) == ()
    receipt = store.publish(snapshot)
    assert receipt.stored is True
    assert store.list_publications(RUN) == ("pub-orphan",)
    assert store.read(RUN, "pub-orphan") == snapshot


def test_concurrent_publishes_respect_cumulative_quota(tmp_path) -> None:
    import threading

    options = ScientificInstitutionsPublicationOptions(max_publications=1)
    store = FilesystemScientificInstitutionsStore(tmp_path, options=options)
    results: list[bool] = []

    def _publish(publication_id: str) -> None:
        results.append(store.publish(_snapshot(publication_id)).stored)

    first = threading.Thread(target=_publish, args=("pub-a",))
    second = threading.Thread(target=_publish, args=("pub-b",))
    first.start()
    second.start()
    first.join()
    second.join()
    assert results.count(True) == 1
    assert len(store.list_publications(RUN)) == 1
