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
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Final

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


def test_streamed_publication_rss_stays_below_artifact_size(
    tmp_path: Path,
) -> None:
    frames = int(os.environ.get(_FRAMES_ENV, "0"))
    if frames < _MIN_FRAMES:
        pytest.skip(f"set {_FRAMES_ENV} to at least {_MIN_FRAMES} frames")

    inputs = cultural_evolution_inputs_from_capture(
        _frames(frames),
        run_id="run-publication-scale",
        source_revision="rev-publication-scale",
        window=CulturalAnalysisWindow(end_boundary=frames - 1),
    )
    status = CulturalCaptureStatus(active=True, failed=False)
    options = {"enabled": True, "max_frames": frames, "max_rows": 1_000_000}
    fingerprint = "e" * 64
    artifact_path = tmp_path / "evidence.json"

    def _stream() -> int:
        with artifact_path.open("wb") as handle:
            write_cultural_evolution_evidence(
                handle,
                inputs,
                config_fingerprint=fingerprint,
                capture_options=options,
                capture_status=status,
            )
        return artifact_path.stat().st_size

    size, streamed_delta, streamed_seconds, supported = _measure_peak_rss(_stream)
    legacy, legacy_delta, legacy_seconds, _ = _measure_peak_rss(
        lambda: encode_cultural_evolution_evidence(
            inputs,
            config_fingerprint=fingerprint,
            capture_options=options,
            capture_status=status,
        )
    )
    assert size == len(legacy)
    assert artifact_path.read_bytes() == legacy
    assert streamed_seconds > 0
    _LOG.info(
        "cultural_publication_scale frames=%s boundaries=%s artifact_bytes=%s "
        "streamed_peak_rss_delta_bytes=%s legacy_peak_rss_delta_bytes=%s "
        "streamed_seconds=%.4f legacy_seconds=%.4f streamed_mib_per_s=%.2f "
        "rss_supported=%s",
        frames,
        len(inputs.boundaries),
        size,
        streamed_delta,
        legacy_delta,
        streamed_seconds,
        legacy_seconds,
        (size / (1024 * 1024)) / streamed_seconds,
        supported,
    )
    if not supported:
        pytest.skip("process RSS sampling is unavailable on this platform")
    assert streamed_delta < size
    assert streamed_delta < legacy_delta
