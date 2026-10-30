"""Opt-in source-backed cultural publication RSS/throughput measurement.

This gate measures publication of a large synthetic capture through the real
streamed canonical writer and compares it with the legacy whole-artifact
encoder. It needs no database, browser or Docker, but it is opt-in because the
frame count is deliberately large::

    PALIMPSEST_V3_PUBLICATION_SCALE_FRAMES=20000 \\
      uv run pytest -m scale tests/benchmarks/test_cultural_publication_rss.py \\
      -q -s -o log_cli=true --log-cli-level=INFO

The assertion is bounded-memory evidence, not a supported capacity promise:
streamed publication must not grow resident memory by the complete artifact
size and must stay below the legacy materializing encoder for the same input.
Each encoder runs in a fresh spawned interpreter so allocator reuse and earlier
tests cannot warm the second encoder's baseline. Each worker has a 300-second
budget; coverage-enabled parents also collect separate worker coverage data.
"""

from __future__ import annotations

import logging
import multiprocessing
import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from multiprocessing.connection import Connection
from pathlib import Path
from typing import Final, Literal

import coverage
import pytest

from analysis.cultural_evolution_evidence import CulturalAnalysisWindow
from experiments.cultural_evidence import cultural_evolution_inputs_from_capture
from experiments.cultural_evidence_serialization import (
    encode_cultural_evolution_evidence,
    write_cultural_evolution_evidence,
)
from simulation.cultural_evidence import (
    CulturalBoundaryExport,
    CulturalCaptureStatus,
)
from tests.benchmarks.v3_profiling import RssSampler

pytestmark = [pytest.mark.scale]

_LOG: Final[logging.Logger] = logging.getLogger("scale.bench.publication")

_FRAMES_ENV: Final[str] = "PALIMPSEST_V3_PUBLICATION_SCALE_FRAMES"
_MIN_FRAMES: Final[int] = 1_000
_SAMPLE_INTERVAL_SECONDS: Final[float] = 0.002
_WORKER_TIMEOUT_SECONDS: Final[float] = 300.0


@dataclass(frozen=True, slots=True)
class _PublicationMeasurement:
    worker_pid: int
    artifact_bytes: int
    rss_delta_bytes: int
    elapsed_seconds: float
    rss_supported: bool


def _frames(count: int) -> tuple[CulturalBoundaryExport, ...]:
    return tuple(
        CulturalBoundaryExport("run-publication-scale", tick, ())
        for tick in range(count)
    )


def _measure_peak_rss[T](
    action: Callable[[], T],
) -> tuple[T, int, float, bool]:
    """Run ``action`` while sampling process RSS; return result, delta, seconds."""
    sampler = RssSampler(capacity=4096)
    baseline = sampler.sample()
    stop = threading.Event()

    def _sample() -> None:
        while not stop.is_set():
            sampler.sample()
            time.sleep(_SAMPLE_INTERVAL_SECONDS)

    thread = threading.Thread(target=_sample, name="rss-sampler", daemon=True)
    thread.start()
    started = time.perf_counter()
    try:
        result = action()
        elapsed = time.perf_counter() - started
    finally:
        stop.set()
        thread.join(timeout=5.0)
    sampler.sample()
    peak = sampler.peak_kb
    if baseline is None or peak is None:
        return result, 0, elapsed, False
    return result, max(0, peak - baseline) * 1024, elapsed, True


def _publication_worker(
    sender: Connection,
    frames: int,
    mode: Literal["stream", "legacy"],
    path: Path,
    coverage_enabled: bool,
) -> None:
    """Use a fresh interpreter/allocator for each encoding implementation."""
    collector = coverage.Coverage(data_suffix=True) if coverage_enabled else None
    try:
        if collector is not None:
            collector.start()
        inputs = cultural_evolution_inputs_from_capture(
            _frames(frames),
            run_id="run-publication-scale",
            source_revision="rev-publication-scale",
            window=CulturalAnalysisWindow(end_boundary=frames - 1),
        )
        status = CulturalCaptureStatus(active=True, failed=False)
        options = {"enabled": True, "max_frames": frames, "max_rows": 1_000_000}
        fingerprint = "e" * 64

        def stream() -> int:
            with path.open("wb") as handle:
                write_cultural_evolution_evidence(
                    handle,
                    inputs,
                    config_fingerprint=fingerprint,
                    capture_options=options,
                    capture_status=status,
                )
            return path.stat().st_size

        if mode == "stream":
            size, delta, elapsed, supported = _measure_peak_rss(stream)
        else:
            body, delta, elapsed, supported = _measure_peak_rss(
                lambda: encode_cultural_evolution_evidence(
                    inputs,
                    config_fingerprint=fingerprint,
                    capture_options=options,
                    capture_status=status,
                )
            )
            size = len(body)
            path.write_bytes(body)
        sender.send(
            _PublicationMeasurement(os.getpid(), size, delta, elapsed, supported)
        )
    except Exception as exc:
        # Do not send exception messages, artifact contents or arbitrary payloads.
        sender.send(type(exc).__name__)
    finally:
        if collector is not None:
            collector.stop()
            collector.save()
        sender.close()


def _measure_publication(
    frames: int,
    mode: Literal["stream", "legacy"],
    path: Path,
    *,
    timeout_seconds: float = _WORKER_TIMEOUT_SECONDS,
) -> _PublicationMeasurement:
    if timeout_seconds <= 0:
        raise ValueError("publication_worker_timeout_must_be_positive")
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(
        target=_publication_worker,
        args=(sender, frames, mode, path, coverage.Coverage.current() is not None),
    )
    process.start()
    sender.close()
    try:
        if not receiver.poll(timeout_seconds):
            raise RuntimeError("publication_worker_timeout")
        try:
            result = receiver.recv()
        except EOFError:
            raise RuntimeError("publication_worker_exited_without_result") from None
        process.join(timeout=30.0)
        if process.is_alive() or process.exitcode != 0:
            raise RuntimeError("publication_worker_failed")
        if not isinstance(result, _PublicationMeasurement):
            raise RuntimeError("publication_worker_measurement_unavailable")
        return result
    finally:
        receiver.close()
        if process.is_alive():
            process.terminate()
            process.join(timeout=5.0)
            if process.is_alive():
                process.kill()
                process.join()


def test_streamed_publication_rss_stays_below_artifact_size(
    tmp_path: Path,
) -> None:
    frames = int(os.environ.get(_FRAMES_ENV, "0"))
    if frames < _MIN_FRAMES:
        pytest.skip(f"set {_FRAMES_ENV} to at least {_MIN_FRAMES} frames")

    artifact_path = tmp_path / "evidence.json"
    legacy_path = tmp_path / "legacy-evidence.json"
    streamed = _measure_publication(frames, "stream", artifact_path)
    legacy = _measure_publication(frames, "legacy", legacy_path)
    assert streamed.worker_pid != os.getpid()
    assert legacy.worker_pid != os.getpid()
    assert streamed.artifact_bytes == legacy.artifact_bytes
    assert artifact_path.read_bytes() == legacy_path.read_bytes()
    assert streamed.elapsed_seconds > 0
    _LOG.info(
        "cultural_publication_scale frames=%s boundaries=%s artifact_bytes=%s "
        "streamed_peak_rss_delta_bytes=%s legacy_peak_rss_delta_bytes=%s "
        "streamed_seconds=%.4f legacy_seconds=%.4f streamed_mib_per_s=%.2f "
        "rss_supported=%s",
        frames,
        frames,
        streamed.artifact_bytes,
        streamed.rss_delta_bytes,
        legacy.rss_delta_bytes,
        streamed.elapsed_seconds,
        legacy.elapsed_seconds,
        (streamed.artifact_bytes / (1024 * 1024)) / streamed.elapsed_seconds,
        streamed.rss_supported and legacy.rss_supported,
    )
    if not streamed.rss_supported or not legacy.rss_supported:
        pytest.skip("process RSS sampling is unavailable on this platform")
    assert streamed.rss_delta_bytes < streamed.artifact_bytes
    assert streamed.rss_delta_bytes < legacy.rss_delta_bytes
