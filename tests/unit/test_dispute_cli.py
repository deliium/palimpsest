"""V4-07 CLI producer options, receipts, and opt-in behavior."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from research_runner.dispute_composition import (
    DisputeProducerOptions,
    producer_options_from_args,
    publish_dispute_harvest,
    write_dispute_receipt,
)
from tests.unit.test_dispute_publication import _ledgers, _result

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "src" / "research_runner" / "cli.py"
COMPOSITION = ROOT / "src" / "research_runner" / "dispute_composition.py"


def test_cli_flags_are_opt_in_and_default_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    text = CLI.read_text(encoding="utf-8")
    assert 'add_argument("--dispute-root", default=None)' in text
    assert 'add_argument("--dispute-max-publications", type=int, default=16)' in text
    assert 'add_argument("--dispute-max-bytes", type=int, default=8_388_608)' in text
    monkeypatch.delenv("PALIMPSEST_DISPUTE_ROOT", raising=False)
    options = producer_options_from_args(
        SimpleNamespace(
            dispute_root=None,
            dispute_max_publications=16,
            dispute_max_bytes=8_388_608,
        )
    )
    assert options.enabled is False
    monkeypatch.setenv("PALIMPSEST_DISPUTE_ROOT", "/tmp/disputes")
    assert producer_options_from_args(SimpleNamespace()).enabled is True


def test_producer_options_read_paths_and_caps() -> None:
    options = producer_options_from_args(
        SimpleNamespace(
            dispute_root="/tmp/disputes",
            dispute_max_publications=2,
            dispute_max_bytes=1024,
        )
    )
    assert options.root == Path("/tmp/disputes")
    assert options.max_publications == 2
    assert options.max_bytes == 1024
    with pytest.raises(ValueError):
        producer_options_from_args(
            SimpleNamespace(
                dispute_root="/tmp/disputes",
                dispute_max_publications=0,
                dispute_max_bytes=1024,
            )
        )


def test_disabled_root_writes_disabled_receipt(tmp_path: Path) -> None:
    receipt = publish_dispute_harvest(
        _result(),
        DisputeProducerOptions(root=None),
    )
    assert receipt == {"status": "disabled", "reason_code": "dispute_disabled"}
    path = write_dispute_receipt(tmp_path, "run-1", receipt)
    assert path == tmp_path / "dispute-publication-run-1.json"
    assert json.loads(path.read_text(encoding="utf-8")) == receipt


def test_incomplete_run_is_unavailable(tmp_path: Path) -> None:
    result = SimpleNamespace(
        dispute_ledgers=(),
        committed_events=(),
        stop_reason="cancelled",
        ticks_committed=10,
    )
    receipt = publish_dispute_harvest(
        result,
        DisputeProducerOptions(root=tmp_path),
        run_id="run-1",
        input_revision="revision-1",
    )
    assert receipt["status"] == "unavailable"
    assert receipt["reason_code"] == "dispute_unavailable"
    assert not (tmp_path / "state.json").exists()


def test_publication_failure_is_failed_but_science_preserved(
    tmp_path: Path,
) -> None:
    runner_result = _result(*_ledgers())
    before = repr(runner_result)
    receipt = publish_dispute_harvest(
        runner_result,
        DisputeProducerOptions(root=tmp_path, max_bytes=1),
        run_id="run-1",
        input_revision="revision-1",
        generated_tick=100,
    )
    assert receipt["status"] == "failed"
    assert receipt["reason_code"] == "dispute_quota_exceeded"
    assert repr(runner_result) == before


def test_receipt_is_written_next_to_artifacts(tmp_path: Path) -> None:
    receipt: dict[str, Any] = {
        "status": "published",
        "reason_code": "dispute_published",
        "publication_id": "disp-pub-0123456789abcdef",
    }
    path = write_dispute_receipt(tmp_path / "artifacts", "run-1", receipt)
    assert path is not None
    assert path == tmp_path / "artifacts" / "dispute-publication-run-1.json"
    assert path.read_text(encoding="utf-8") == (
        '{"publication_id":"disp-pub-0123456789abcdef",'
        '"reason_code":"dispute_published","status":"published"}\n'
    )


def test_receipt_write_failure_does_not_fail_run(tmp_path: Path) -> None:
    occupied = tmp_path / "artifact-root"
    occupied.write_text("occupied", encoding="utf-8")
    assert write_dispute_receipt(occupied, "run-1", {"status": "published"}) is None
    assert "dispute_receipt_failed" in COMPOSITION.read_text(encoding="utf-8")


def test_cli_has_no_http_or_api_import() -> None:
    forbidden = {
        "api",
        "fastapi",
        "starlette",
        "uvicorn",
        "aiohttp",
        "http",
    }
    for path in (CLI, COMPOSITION):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module is not None:
                imported.add(node.module.split(".", 1)[0])
            elif isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
        assert not imported & forbidden, path
