"""Publication encoders must not share a warmed allocator during RSS measurement."""

import os
from pathlib import Path

import pytest

from tests.benchmarks.test_cultural_publication_rss import _measure_publication


def test_measurements_run_in_fresh_workers_and_preserve_exact_bytes(
    tmp_path: Path,
) -> None:
    streamed_path = tmp_path / "stream.json"
    legacy_path = tmp_path / "legacy.json"
    streamed = _measure_publication(128, "stream", streamed_path)
    legacy = _measure_publication(128, "legacy", legacy_path)

    assert streamed.worker_pid != os.getpid()
    assert legacy.worker_pid != os.getpid()
    assert streamed.artifact_bytes == streamed_path.stat().st_size
    assert legacy.artifact_bytes == legacy_path.stat().st_size
    assert streamed_path.read_bytes() == legacy_path.read_bytes()
    assert streamed.elapsed_seconds > 0
    assert legacy.elapsed_seconds > 0
    assert streamed.rss_delta_bytes >= 0
    assert legacy.rss_delta_bytes >= 0


@pytest.mark.parametrize("timeout", [0.0, -1.0])
def test_nonpositive_worker_budget_is_rejected(tmp_path: Path, timeout: float) -> None:
    with pytest.raises(ValueError, match="publication_worker_timeout_must_be_positive"):
        _measure_publication(
            128, "stream", tmp_path / "unused.json", timeout_seconds=timeout
        )
    assert not (tmp_path / "unused.json").exists()


def test_failed_worker_is_not_reported_as_a_zero_memory_measurement(
    tmp_path: Path,
) -> None:
    path = tmp_path / "missing-parent" / "evidence.json"
    with pytest.raises(
        RuntimeError, match="publication_worker_measurement_unavailable"
    ):
        _measure_publication(128, "stream", path)
    assert not path.exists()
