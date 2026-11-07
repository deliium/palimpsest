"""Canonical borders snapshot codec."""

from __future__ import annotations

from simulation.borders_codec import (
    borders_publication_id,
    borders_snapshot_digest,
    decode_borders_snapshot,
    encode_borders_snapshot,
    finalize_borders_snapshot,
)
from simulation.borders_models import empty_borders_snapshot


def test_empty_snapshot_round_trip_is_canonical() -> None:
    snapshot = finalize_borders_snapshot(
        empty_borders_snapshot(
            "run-1", publication_id="bd-pub-pending", digest="0" * 64
        )
    )
    assert snapshot.publication_id.startswith("bd-pub-")
    assert len(snapshot.digest) == 64
    assert decode_borders_snapshot(encode_borders_snapshot(snapshot)) == snapshot


def test_digest_and_publication_id_are_stable() -> None:
    snapshot = finalize_borders_snapshot(
        empty_borders_snapshot(
            "run-1", publication_id="bd-pub-pending", digest="0" * 64
        )
    )
    assert borders_snapshot_digest(snapshot) == snapshot.digest
    assert borders_publication_id(snapshot.digest) == snapshot.publication_id
