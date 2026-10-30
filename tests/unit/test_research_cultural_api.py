"""Read-only cultural artifact API contracts."""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from api.app import DatabaseResourcesLike, DisposableEngine, create_app
from infrastructure.logging import reset_logging_for_tests
from infrastructure.settings import Settings, load_settings

pytestmark = pytest.mark.unit

_MP = "a" * 64
_CP = "b" * 64
_CFP = "c" * 64
_ED = "d" * 64


class FakeEngine:
    async def dispose(self) -> None:
        return None


class FakeResources:
    def __init__(self, engine: DisposableEngine) -> None:
        self.engine = engine

    @property
    def session_factory(self) -> object:
        """Keep persistence unavailable in this artifact-only API fake."""
        raise AttributeError("engine-only resources have no session factory")


@pytest.fixture
def logging_sandbox() -> Iterator[None]:
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    try:
        yield
    finally:
        reset_logging_for_tests(original_handlers, original_level)


def _factory(_settings: Settings) -> DatabaseResourcesLike:
    return FakeResources(engine=FakeEngine())


def _settings(**overrides: object) -> Settings:
    return load_settings(env_file=False, **overrides)


def _app(**overrides: object) -> FastAPI:
    return create_app(settings=_settings(**overrides), database_factory=_factory)


@asynccontextmanager
async def running_client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            yield client


def _canonical(payload: object) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _metrics_payload(
    *,
    cell_id: str = "cell-a",
    matrix_fingerprint: str = _MP,
    run_id: str = "run-1",
    rows_json: str = "[]",
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "cultural-cell-metrics-v1",
        "cell_id": cell_id,
        "matrix_fingerprint": matrix_fingerprint,
        "cell_fingerprint": _CFP,
        "config_fingerprint": _CP,
        "run_id": run_id,
        "capture_policy": {"enabled": True, "max_frames": 10, "max_rows": 100},
        "analysis_window": {"baseline_boundary": 0, "end_boundary": 10},
        "evidence_digest": _ED,
        "documents": [
            {
                "schema_version": "1",
                "metric_family": "cultural_trait_dynamics",
                "values": {"rows_json": rows_json},
            }
        ],
    }
    payload["digest"] = hashlib.sha256(_canonical(payload)).hexdigest()
    return payload


def _comparison_payload(*, matrix_fingerprint: str = _MP) -> dict[str, object]:
    return {
        "schema_version": "cultural-metric-comparison-v1",
        "matrix_fingerprint": matrix_fingerprint,
        "confidence": 0.95,
        "method": "student_t_seed_block_mean",
        "conditions": [],
        "contrasts": [],
        "excluded_cells": [],
        "reasons": [],
    }


def _write_runtime_matrix(root: Path, matrix_id: str = "m1") -> Path:
    matrix = root / matrix_id
    cells = matrix / "cells"
    cells.mkdir(parents=True)
    (matrix / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "matrix-manifest-v1",
                "matrix_schema_version": "experiment-matrix-v1",
                "matrix_id": matrix_id,
                "matrix_fingerprint": _MP,
                "cell_ids": ["cell-a", "cell-b"],
            }
        ),
        encoding="utf-8",
    )
    (cells / "cell-a.json").write_text(
        json.dumps(
            {
                "cell_id": "cell-a",
                "state": "completed",
                "cell_fingerprint": _CFP,
                "config_fingerprint": _CP,
                "run_id": "run-1",
            }
        ),
        encoding="utf-8",
    )
    (cells / "cell-a.completion.json").write_text(
        json.dumps(
            {
                "cell_id": "cell-a",
                "run_id": "run-1",
                "stop_reason": "max_ticks",
                "version_identity": {
                    "matrix_fingerprint": _MP,
                    "cell_fingerprint": _CFP,
                    "config_fingerprint": _CP,
                },
            }
        ),
        encoding="utf-8",
    )
    (cells / "cell-a.cultural-metrics.json").write_text(
        json.dumps(_metrics_payload()), encoding="utf-8"
    )
    (matrix / "cultural-metric-comparison.json").write_text(
        json.dumps(_comparison_payload()), encoding="utf-8"
    )
    return matrix


def _write_legacy_matrix(root: Path, matrix_id: str = "legacy") -> Path:
    matrix = root / matrix_id
    cells = matrix / "cells"
    cells.mkdir(parents=True)
    (matrix / "manifest.json").write_text(
        json.dumps({"schema_version": "experiment-matrix-v1", "matrix_id": matrix_id}),
        encoding="utf-8",
    )
    for name in (
        "cell-a.json",
        "cell-a.metrics.json",
        "cell-a.completion.json",
        "cell-a.cultural-evidence.json",
        "cell-a.cultural-metrics.json",
    ):
        (cells / name).write_text("{}", encoding="utf-8")
    (cells / "cell-a.cultural-metrics.json").write_text(
        json.dumps(_metrics_payload()), encoding="utf-8"
    )
    (matrix / "cultural-metric-comparison.json").write_text(
        json.dumps(_comparison_payload()), encoding="utf-8"
    )
    return matrix


@pytest.mark.usefixtures("logging_sandbox")
@pytest.mark.asyncio
async def test_runtime_cultural_artifacts_are_served_unchanged(tmp_path: Path) -> None:
    root = tmp_path / "matrices"
    root.mkdir()
    matrix = _write_runtime_matrix(root)
    metrics_raw = (matrix / "cells" / "cell-a.cultural-metrics.json").read_bytes()
    app = _app(research_matrix_root=root)
    async with running_client(app) as client:
        metrics = await client.get(
            "/v1/research/matrices/m1/cells/cell-a/cultural-metrics"
        )
        assert metrics.status_code == 200
        assert metrics.headers["x-palimpsest-artifact-binding"] == "runtime_bound"
        assert metrics.headers["cache-control"] == "no-store"
        assert metrics.content == metrics_raw
        comparison = await client.get("/v1/research/matrices/m1/cultural-comparison")
        assert comparison.status_code == 200
        assert comparison.headers["x-palimpsest-artifact-binding"] == "runtime_bound"
        assert comparison.json()["matrix_fingerprint"] == _MP


@pytest.mark.usefixtures("logging_sandbox")
@pytest.mark.asyncio
async def test_runtime_cell_requires_completion_proof(tmp_path: Path) -> None:
    root = tmp_path / "matrices"
    root.mkdir()
    matrix = _write_runtime_matrix(root)
    (matrix / "cells" / "cell-a.completion.json").unlink()
    app = _app(research_matrix_root=root)
    async with running_client(app) as client:
        response = await client.get(
            "/v1/research/matrices/m1/cells/cell-a/cultural-metrics"
        )
        assert response.status_code == 409
        assert response.json()["code"] == "research_cell_incomplete"


@pytest.mark.usefixtures("logging_sandbox")
@pytest.mark.asyncio
async def test_runtime_cell_rejects_mismatched_completion(tmp_path: Path) -> None:
    root = tmp_path / "matrices"
    root.mkdir()
    matrix = _write_runtime_matrix(root)
    completion = json.loads(
        (matrix / "cells" / "cell-a.completion.json").read_text(encoding="utf-8")
    )
    completion["run_id"] = "run-2"
    (matrix / "cells" / "cell-a.completion.json").write_text(
        json.dumps(completion), encoding="utf-8"
    )
    app = _app(research_matrix_root=root)
    async with running_client(app) as client:
        response = await client.get(
            "/v1/research/matrices/m1/cells/cell-a/cultural-metrics"
        )
        assert response.status_code == 409
        assert response.json()["code"] == "research_cell_incomplete"


@pytest.mark.usefixtures("logging_sandbox")
@pytest.mark.asyncio
async def test_legacy_export_binding_is_unverified(tmp_path: Path) -> None:
    root = tmp_path / "matrices"
    root.mkdir()
    _write_legacy_matrix(root)
    app = _app(research_matrix_root=root)
    async with running_client(app) as client:
        metrics = await client.get(
            "/v1/research/matrices/legacy/cells/cell-a/cultural-metrics"
        )
        assert metrics.status_code == 200
        assert metrics.headers["x-palimpsest-artifact-binding"] == "legacy_unverified"
        comparison = await client.get(
            "/v1/research/matrices/legacy/cultural-comparison"
        )
        assert comparison.status_code == 200
        assert (
            comparison.headers["x-palimpsest-artifact-binding"] == "legacy_unverified"
        )


@pytest.mark.usefixtures("logging_sandbox")
@pytest.mark.asyncio
async def test_cell_listing_uses_runtime_declarations_and_excludes_sidecars(
    tmp_path: Path,
) -> None:
    root = tmp_path / "matrices"
    root.mkdir()
    matrix = _write_runtime_matrix(root)
    (matrix / "cells" / "cell-a.metrics.json").write_text("{}", encoding="utf-8")
    app = _app(research_matrix_root=root)
    async with running_client(app) as client:
        runtime = await client.get("/v1/research/matrices/m1/cells")
        assert runtime.status_code == 200
        assert runtime.json()["cell_ids"] == ["cell-a"]

        _write_legacy_matrix(root)
        legacy = await client.get("/v1/research/matrices/legacy/cells")
        assert legacy.status_code == 200
        assert legacy.json()["cell_ids"] == ["cell-a"]


@pytest.mark.usefixtures("logging_sandbox")
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("name", "writer", "code"),
    [
        (
            "unsupported schema",
            lambda p: p.write_text(
                json.dumps({"schema_version": "nope"}), encoding="utf-8"
            ),
            "unsupported_schema",
        ),
        (
            "duplicate key",
            lambda p: p.write_text(
                '{"schema_version":"cultural-metric-comparison-v1",'
                '"schema_version":"cultural-metric-comparison-v1"}',
                encoding="utf-8",
            ),
            "duplicate_key",
        ),
        (
            "nonfinite",
            lambda p: p.write_text(
                json.dumps(_comparison_payload()).replace("0.95", "NaN"),
                encoding="utf-8",
            ),
            "nonfinite_number",
        ),
    ],
)
async def test_comparison_structural_failures(
    tmp_path: Path, name: str, writer: Callable[[Path], object], code: str
) -> None:
    del name
    root = tmp_path / "matrices"
    root.mkdir()
    matrix = root / "m1"
    matrix.mkdir()
    (matrix / "manifest.json").write_text(
        json.dumps({"schema_version": "experiment-matrix-v1"}),
        encoding="utf-8",
    )
    writer(matrix / "cultural-metric-comparison.json")
    app = _app(research_matrix_root=root)
    async with running_client(app) as client:
        response = await client.get("/v1/research/matrices/m1/cultural-comparison")
        assert response.status_code == 400
        assert response.json()["code"] == code


@pytest.mark.usefixtures("logging_sandbox")
@pytest.mark.asyncio
async def test_nested_rows_json_is_validated(tmp_path: Path) -> None:
    root = tmp_path / "matrices"
    root.mkdir()
    matrix = root / "legacy"
    cells = matrix / "cells"
    cells.mkdir(parents=True)
    (matrix / "manifest.json").write_text(
        json.dumps({"schema_version": "experiment-matrix-v1"}),
        encoding="utf-8",
    )
    for rows_json, code in (
        ('[{"value": 1, "value": 2}]', "duplicate_key"),
        ('[{"value": NaN}]', "nonfinite_number"),
        ('[{"value": {"nested": 1}}]', "invalid_rows_json"),
    ):
        (cells / "cell-a.cultural-metrics.json").write_text(
            json.dumps(_metrics_payload(rows_json=rows_json)), encoding="utf-8"
        )
        app = _app(research_matrix_root=root)
        async with running_client(app) as client:
            response = await client.get(
                "/v1/research/matrices/legacy/cells/cell-a/cultural-metrics"
            )
            assert response.status_code == 400
            assert response.json()["code"] == code


@pytest.mark.usefixtures("logging_sandbox")
@pytest.mark.asyncio
async def test_oversize_artifact_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "matrices"
    root.mkdir()
    _write_legacy_matrix(root)
    monkeypatch.setattr("api.research_cultural_service.MAX_OUTER_ARTIFACT_BYTES", 10)
    app = _app(research_matrix_root=root)
    async with running_client(app) as client:
        response = await client.get("/v1/research/matrices/legacy/cultural-comparison")
        assert response.status_code == 413
        assert response.json()["code"] == "research_artifact_too_large"


@pytest.mark.usefixtures("logging_sandbox")
@pytest.mark.asyncio
async def test_symlink_escape_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "matrices"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "manifest.json").write_text(
        json.dumps({"schema_version": "experiment-matrix-v1"}), encoding="utf-8"
    )
    (root / "escape").symlink_to(outside, target_is_directory=True)
    app = _app(research_matrix_root=root)
    async with running_client(app) as client:
        response = await client.get("/v1/research/matrices/escape/manifest")
        assert response.status_code == 400
        assert response.json()["code"] == "path_traversal"


@pytest.mark.usefixtures("logging_sandbox")
@pytest.mark.asyncio
async def test_missing_root_and_artifact_are_distinct(tmp_path: Path) -> None:
    app = _app(research_matrix_root=None)
    async with running_client(app) as client:
        response = await client.get("/v1/research/matrices/m1/cultural-comparison")
        assert response.status_code == 503
        assert response.json()["code"] == "research_cultural_unavailable"


def test_optional_service_attach_does_not_require_persistence() -> None:
    from api.app import _attach_research_cultural_service

    root = Path("/tmp") / "palimpsest-cultural-bare"
    bare = FastAPI()
    bare.state.settings = _settings(research_matrix_root=root)
    _attach_research_cultural_service(bare)
    assert bare.state.research_cultural_service is not None

    empty = FastAPI()
    empty.state.settings = _settings(research_matrix_root=None)
    _attach_research_cultural_service(empty)
    assert getattr(empty.state, "research_cultural_service", None) is None


def _evidence_payload(
    *,
    run_id: str = "run-1",
    config_fingerprint: str = _CP,
    trait_rows: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    if trait_rows is None:
        trait_rows = [
            {
                "boundary_tick": index % 10,
                "owner_id": f"agent-{index % 3}",
                "local_entry_id": f"entry-{index:03d}",
                "dimension": "belief",
                "content_digest": f"{index:064x}"[-64:],
                "lineage_key": None,
                "acquisition_tick": 0,
                "parent_refs": [],
                "source_refs": [],
                "status": "active",
            }
            for index in range(250)
        ]
    payload: dict[str, object] = {
        "schema_version": "cultural-evolution-evidence-v1",
        "run_id": run_id,
        "config_fingerprint": config_fingerprint,
        "source_revision": "rev-1",
        "policy_version": "cultural-evolution.v1",
        "capture_options": {"enabled": True, "max_frames": 10, "max_rows": 100},
        "analysis_window": {"baseline_boundary": 0, "end_boundary": 10},
        "boundaries": [
            {
                "boundary_tick": 0,
                "living_owner_ids": ["agent-0", "agent-1"],
                "generation_by_owner": {"agent-0": 0, "agent-1": 0},
                "owner_dimension_coverage": [
                    ["agent-0", "belief", "complete"],
                    ["agent-1", "belief", "partial"],
                ],
            },
            {
                "boundary_tick": 5,
                "living_owner_ids": ["agent-0", "agent-2"],
                "generation_by_owner": {"agent-0": 0, "agent-2": 1},
                "owner_dimension_coverage": [
                    ["agent-0", "belief", "complete"],
                    ["agent-2", "belief", "complete"],
                ],
            },
        ],
        "trait_rows": trait_rows,
        "transmission_edges": [
            {
                "edge_id": f"edge-{index}",
                "source_owner_id": "agent-0",
                "receiver_owner_id": "agent-1",
                "source_local_id": "entry-000",
                "receiver_local_id": "entry-001",
                "acquisition_boundary": index,
                "modality": "teaching",
                "attribution_status": "attributed",
                "generation_class": "horizontal",
                "kin_vertical": False,
                "source_digest": f"{index + 1:064x}"[-64:],
                "target_digest": f"{index + 2:064x}"[-64:],
                "mutated": False,
                "recombined": False,
                "evidence_ids": [f"ev-{index}"],
            }
            for index in range(3)
        ],
        "group_memberships": [],
        "archive_states": [],
        "evidence_pointers": [],
        "gaps": [],
        "capture_status": {
            "active": True,
            "failed": False,
            "failure_boundary": None,
            "failure_code": None,
            "missing_prefix_through": None,
        },
    }
    payload["digest"] = hashlib.sha256(_canonical(payload)).hexdigest()
    return payload


def _write_evidence_matrix(
    root: Path, *, trait_rows: list[dict[str, object]] | None = None
) -> tuple[Path, str]:
    matrix = _write_runtime_matrix(root)
    evidence = _evidence_payload(trait_rows=trait_rows)
    digest = str(evidence["digest"])
    metrics = _metrics_payload()
    metrics["evidence_digest"] = digest
    metrics["digest"] = hashlib.sha256(
        _canonical({key: value for key, value in metrics.items() if key != "digest"})
    ).hexdigest()
    cells = matrix / "cells"
    (cells / "cell-a.cultural-evidence.json").write_text(
        json.dumps(evidence), encoding="utf-8"
    )
    (cells / "cell-a.cultural-metrics.json").write_text(
        json.dumps(metrics), encoding="utf-8"
    )
    return matrix, digest


def _debug_app(root: Path) -> FastAPI:
    from pydantic import SecretStr

    return create_app(
        settings=_settings(
            research_matrix_root=root,
            api_debug_enabled=True,
            api_debug_credential=SecretStr("debug-secret-" + "x" * 24),
        ),
        database_factory=_factory,
    )


def _debug_headers() -> dict[str, str]:
    return {"x-palimpsest-token": "debug-secret-" + "x" * 24}


@pytest.mark.usefixtures("logging_sandbox")
@pytest.mark.asyncio
async def test_cultural_evidence_pages_full_union(tmp_path: Path) -> None:
    root = tmp_path / "matrices"
    root.mkdir()
    _write_evidence_matrix(root)
    app = _debug_app(root)
    async with running_client(app) as client:
        first = await client.get(
            "/v1/research/matrices/m1/cells/cell-a/cultural-evidence",
            params={"section": "traits", "limit": 200},
            headers=_debug_headers(),
        )
        assert first.status_code == 200
        body = first.json()
        assert body["schema_version"] == "research-cultural-evidence-page-v1"
        assert body["binding_state"] == "runtime_bound"
        assert len(body["rows"]) == 200
        assert body["truncated"] is True
        assert body["next_cursor"]

        second = await client.get(
            "/v1/research/matrices/m1/cells/cell-a/cultural-evidence",
            params={"section": "traits", "limit": 200, "cursor": body["next_cursor"]},
            headers=_debug_headers(),
        )
        assert second.status_code == 200
        body2 = second.json()
        assert len(body2["rows"]) == 50
        assert body2["truncated"] is False
        seen = {(row["owner_id"], row["local_entry_id"]) for row in body["rows"]}
        seen |= {(row["owner_id"], row["local_entry_id"]) for row in body2["rows"]}
        assert len(seen) == 250


@pytest.mark.usefixtures("logging_sandbox")
@pytest.mark.asyncio
async def test_cultural_evidence_filters_order_and_coverage(tmp_path: Path) -> None:
    root = tmp_path / "matrices"
    root.mkdir()
    _write_evidence_matrix(root)
    app = _debug_app(root)
    async with running_client(app) as client:
        response = await client.get(
            "/v1/research/matrices/m1/cells/cell-a/cultural-evidence",
            params={
                "section": "traits",
                "owner_id": "agent-1",
                "dimension": "belief",
                "from_tick": 2,
                "to_tick": 6,
            },
            headers=_debug_headers(),
        )
        assert response.status_code == 200
        rows = response.json()["rows"]
        assert rows
        assert all(row["owner_id"] == "agent-1" for row in rows)
        assert all(2 <= row["boundary_tick"] < 6 for row in rows)
        assert [
            (
                row["boundary_tick"],
                row["owner_id"],
                row["dimension"],
                row["local_entry_id"],
            )
            for row in rows
        ] == sorted(
            (
                row["boundary_tick"],
                row["owner_id"],
                row["dimension"],
                row["local_entry_id"],
            )
            for row in rows
        )
        assert response.json()["coverage"] is not None

        transmission = await client.get(
            "/v1/research/matrices/m1/cells/cell-a/cultural-evidence",
            params={"section": "transmission"},
            headers=_debug_headers(),
        )
        assert transmission.status_code == 200
        assert [row["edge_id"] for row in transmission.json()["rows"]] == [
            "edge-0",
            "edge-1",
            "edge-2",
        ]


@pytest.mark.usefixtures("logging_sandbox")
@pytest.mark.asyncio
async def test_cultural_evidence_cursor_is_bound_and_expires(tmp_path: Path) -> None:
    from api.research_cultural_cursor import CulturalCursorCodec

    root = tmp_path / "matrices"
    root.mkdir()
    _write_evidence_matrix(root)
    app = _debug_app(root)
    app.state.research_cultural_cursor_codec = CulturalCursorCodec.from_secret(
        b"x" * 32
    )
    async with running_client(app) as client:
        first = await client.get(
            "/v1/research/matrices/m1/cells/cell-a/cultural-evidence",
            params={"section": "traits", "limit": 10},
            headers=_debug_headers(),
        )
        cursor = first.json()["next_cursor"]

        wrong_section = await client.get(
            "/v1/research/matrices/m1/cells/cell-a/cultural-evidence",
            params={"section": "boundaries", "cursor": cursor},
            headers=_debug_headers(),
        )
        assert wrong_section.status_code == 400
        assert wrong_section.json()["code"] == "invalid_research_cursor"

        wrong_filter = await client.get(
            "/v1/research/matrices/m1/cells/cell-a/cultural-evidence",
            params={
                "section": "traits",
                "limit": 10,
                "owner_id": "agent-0",
                "cursor": cursor,
            },
            headers=_debug_headers(),
        )
        assert wrong_filter.status_code == 400
        assert wrong_filter.json()["code"] == "invalid_research_cursor"

        expired = app.state.research_cultural_cursor_codec.encode(
            {
                "matrix_id": "m1",
                "cell_id": "cell-a",
                "section": "traits",
                "evidence_digest": "a" * 64,
                "metrics_digest": "b" * 64,
                "filters": {
                    "from_tick": None,
                    "to_tick": None,
                    "owner_id": None,
                    "dimension": None,
                },
                "offset": 10,
            },
            now=0,
        )
        expired_response = await client.get(
            "/v1/research/matrices/m1/cells/cell-a/cultural-evidence",
            params={"section": "traits", "limit": 10, "cursor": expired},
            headers=_debug_headers(),
        )
        assert expired_response.status_code == 400
        assert expired_response.json()["code"] == "invalid_research_cursor"


@pytest.mark.usefixtures("logging_sandbox")
@pytest.mark.asyncio
async def test_cultural_evidence_changed_pair_conflicts(tmp_path: Path) -> None:
    root = tmp_path / "matrices"
    root.mkdir()
    matrix, _ = _write_evidence_matrix(root)
    app = _debug_app(root)
    async with running_client(app) as client:
        first = await client.get(
            "/v1/research/matrices/m1/cells/cell-a/cultural-evidence",
            params={"section": "traits", "limit": 10},
            headers=_debug_headers(),
        )
        cursor = first.json()["next_cursor"]
        evidence = _evidence_payload(
            trait_rows=[
                {
                    "boundary_tick": 0,
                    "owner_id": "agent-0",
                    "local_entry_id": "entry-new",
                    "dimension": "belief",
                    "content_digest": "e" * 64,
                    "lineage_key": None,
                    "acquisition_tick": 0,
                    "parent_refs": [],
                    "source_refs": [],
                    "status": "active",
                }
            ]
        )
        metrics = _metrics_payload()
        metrics["evidence_digest"] = evidence["digest"]
        metrics["digest"] = hashlib.sha256(
            _canonical(
                {key: value for key, value in metrics.items() if key != "digest"}
            )
        ).hexdigest()
        cells = matrix / "cells"
        (cells / "cell-a.cultural-evidence.json").write_text(
            json.dumps(evidence), encoding="utf-8"
        )
        (cells / "cell-a.cultural-metrics.json").write_text(
            json.dumps(metrics), encoding="utf-8"
        )
        response = await client.get(
            "/v1/research/matrices/m1/cells/cell-a/cultural-evidence",
            params={"section": "traits", "limit": 10, "cursor": cursor},
            headers=_debug_headers(),
        )
        assert response.status_code == 409
        assert response.json()["code"] == "research_snapshot_changed"


@pytest.mark.usefixtures("logging_sandbox")
@pytest.mark.asyncio
async def test_cultural_evidence_rejects_oversized_single_row(tmp_path: Path) -> None:
    root = tmp_path / "matrices"
    root.mkdir()
    huge = "x" * (2 * 1024 * 1024 + 1)
    _write_evidence_matrix(
        root,
        trait_rows=[
            {
                "boundary_tick": 0,
                "owner_id": "agent-0",
                "local_entry_id": "entry-huge",
                "dimension": "belief",
                "content_digest": "f" * 64,
                "lineage_key": None,
                "acquisition_tick": 0,
                "parent_refs": [],
                "source_refs": [huge],
                "status": "active",
            }
        ],
    )
    app = _debug_app(root)
    async with running_client(app) as client:
        response = await client.get(
            "/v1/research/matrices/m1/cells/cell-a/cultural-evidence",
            params={"section": "traits"},
            headers=_debug_headers(),
        )
        assert response.status_code == 413
        assert response.json()["code"] == "research_artifact_too_large"


@pytest.mark.usefixtures("logging_sandbox")
@pytest.mark.asyncio
async def test_cultural_evidence_requires_debug_before_read(tmp_path: Path) -> None:
    root = tmp_path / "matrices"
    root.mkdir()
    _write_evidence_matrix(root)
    app = _debug_app(root)
    async with running_client(app) as client:
        response = await client.get(
            "/v1/research/matrices/m1/cells/cell-a/cultural-evidence",
            params={"section": "traits"},
        )
        assert response.status_code == 401
        assert response.json()["code"] == "missing_credential"
