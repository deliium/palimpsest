# mypy: ignore-errors
"""V4-32 canonical snapshot composition, codec, and reference validation."""

from __future__ import annotations

import json

import pytest

from experiments.scientific_institutions_publication import (
    ScientificInstitutionsSnapshotOverflow,
    compose_scientific_institutions_snapshot,
)
from simulation.scientific_institutions_codec import (
    canonical_scientific_institutions_json,
    decode_scientific_institutions_snapshot,
    encode_scientific_institutions_snapshot,
    scientific_institutions_digest,
)
from simulation.scientific_institutions_models import (
    MAX_SECTION_ROWS,
    ScientificInstitutionsRow,
    ScientificInstitutionsSnapshot,
)
from tests.unit.scientific_institutions_publication_helpers import (
    RUN,
    metric_inputs,
)

pytestmark = pytest.mark.unit


def _snapshot():
    return compose_scientific_institutions_snapshot(
        metric_inputs(),
        run_id=RUN,
        publication_id="pub-a",
        input_revision="rev-1",
        boundary_tick=64,
    )


def test_snapshot_headers_sections_and_counts() -> None:
    snapshot = _snapshot()
    assert snapshot.run_id == RUN
    assert snapshot.publication_id == "pub-a"
    assert snapshot.input_revision == "rev-1"
    assert snapshot.boundary_tick == 64
    assert len(snapshot.windows) == 2
    assert len(snapshot.practice) == 2
    assert len(snapshot.signals) == 1
    assert len(snapshot.lineage) == 3
    assert dict(snapshot.summary)["stable_row_count"] == 2
    assert dict(snapshot.summary)["episode_count"] == 1


def test_snapshot_uses_run_scoped_organization_tokens() -> None:
    snapshot = _snapshot()
    text = canonical_scientific_institutions_json(snapshot).decode("ascii")
    assert "org-0123456789abcdef" not in text
    assert "organization_token" in text
    assert "artifact-1" not in text


def test_canonical_bytes_and_digest_are_deterministic() -> None:
    first = _snapshot()
    second = _snapshot()
    assert canonical_scientific_institutions_json(first) == (
        canonical_scientific_institutions_json(second)
    )
    assert scientific_institutions_digest(first) == (
        scientific_institutions_digest(second)
    )
    decoded = decode_scientific_institutions_snapshot(
        json.loads(canonical_scientific_institutions_json(first))
    )
    assert decoded == first
    assert encode_scientific_institutions_snapshot(decoded) == (
        encode_scientific_institutions_snapshot(first)
    )


def test_decode_rejects_unknown_and_missing_keys() -> None:
    payload = encode_scientific_institutions_snapshot(_snapshot())
    payload["extra"] = 1
    with pytest.raises(ValueError):
        decode_scientific_institutions_snapshot(payload)
    payload = encode_scientific_institutions_snapshot(_snapshot())
    del payload["windows"]
    with pytest.raises(ValueError):
        decode_scientific_institutions_snapshot(payload)


def test_snapshot_rejects_duplicate_row_keys_and_row_cap() -> None:
    row = ScientificInstitutionsRow(
        section="windows",
        window_index=0,
        row_key="windows:0",
        fields=(),
    )
    with pytest.raises(ValueError):
        ScientificInstitutionsSnapshot(
            run_id=RUN,
            publication_id="pub-a",
            policy_version="scientific-institutions.v1",
            input_revision="rev-1",
            boundary_tick=0,
            windows=(row, row),
        )
    rows = tuple(
        ScientificInstitutionsRow(
            section="windows",
            window_index=index,
            row_key=f"windows:{index}",
            fields=(),
        )
        for index in range(MAX_SECTION_ROWS + 1)
    )
    with pytest.raises(ValueError):
        ScientificInstitutionsSnapshot(
            run_id=RUN,
            publication_id="pub-a",
            policy_version="scientific-institutions.v1",
            input_revision="rev-1",
            boundary_tick=0,
            windows=rows,
        )


def test_overflow_is_explicit_not_trimmed() -> None:
    class Broken:
        pass

    with pytest.raises(ScientificInstitutionsSnapshotOverflow):
        compose_scientific_institutions_snapshot(
            Broken(),  # type: ignore[arg-type]
            run_id=RUN,
            publication_id="pub-a",
            input_revision="rev-1",
            boundary_tick=64,
        )
