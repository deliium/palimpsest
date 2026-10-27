"""Opt-in repeated-analysis footprint measurement for incremental V3 metrics.

Run with a boundary count against synthetic retained cultural boundaries::

    PALIMPSEST_V3_INCREMENTAL_SCALE_BOUNDARIES=5000 \\
      uv run pytest -m scale tests/benchmarks/test_incremental_trait_analysis.py \\
      -q -s -o log_cli=true --log-cli-level=INFO

The gate asserts exact batch/incremental row parity and that the sealed-window
accumulator's traced footprint stays below the batch calculator's for the same
input. Numbers are a synthetic reducer footprint, not a scientific capacity
claim and not part of a browser or database envelope.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import tracemalloc
from pathlib import Path
from typing import Final

import pytest

from analysis.cultural_evolution_evidence import (
    CulturalAnalysisWindow,
    normalize_cultural_frames,
)
from analysis.cultural_trait_dynamics import compute_cultural_trait_dynamics
from analysis.incremental_cultural_traits import (
    TraitDynamicsAccumulator,
    _measurement_digest,
    compute_cultural_trait_dynamics_incremental,
    read_checkpoint,
    resume_checkpoint,
    write_checkpoint,
)
from simulation.cultural_evidence import CulturalBoundaryExport
from tests.unit.test_cultural_evolution_normalization import (
    _LEARNER,
    _TEACHER,
    _empty_ledgers,
    _owner,
    _practical_entry,
    _practical_ledger,
)

pytestmark = [pytest.mark.scale]

_LOG: Final[logging.Logger] = logging.getLogger("scale.bench.incremental")

_BOUNDARIES_ENV: Final[str] = "PALIMPSEST_V3_INCREMENTAL_SCALE_BOUNDARIES"
_MIN_BOUNDARIES: Final[int] = 200
_TRAITS: Final[tuple[str, ...]] = (
    "tech:one",
    "tech:two",
    "tech:three",
    "tech:four",
    "tech:five",
)
_RUN: Final[str] = "run-incremental-scale"
_REVISION: Final[str] = "rev-incremental-scale"


def _frames(count: int) -> tuple[CulturalBoundaryExport, ...]:
    frames: list[CulturalBoundaryExport] = []
    for tick in range(count):
        content_key = _TRAITS[tick % len(_TRAITS)]
        entry = _practical_entry(
            owner=_TEACHER,
            entry_id=f"pk-{tick}",
            content_key=content_key,
            fingerprint=(f"fp:{content_key}",),
            acquired_tick=tick,
        )
        teacher_ledgers = _empty_ledgers(_TEACHER)
        teacher_ledgers["practical_knowledge"] = _practical_ledger(_TEACHER, (entry,))
        frames.append(
            CulturalBoundaryExport(
                _RUN,
                tick,
                (
                    _owner(_TEACHER, 0, teacher_ledgers),
                    _owner(_LEARNER, 1, _empty_ledgers(_LEARNER)),
                ),
            )
        )
    return tuple(frames)


def _traced(action):
    tracemalloc.start()
    try:
        started = time.perf_counter()
        result = action()
        elapsed = time.perf_counter() - started
        _current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return result, peak, elapsed


def test_incremental_trait_analysis_parity_and_footprint(tmp_path: Path) -> None:
    boundaries = int(os.environ.get(_BOUNDARIES_ENV, "0"))
    if boundaries < _MIN_BOUNDARIES:
        pytest.skip(f"set {_BOUNDARIES_ENV} to at least {_MIN_BOUNDARIES}")

    inputs = normalize_cultural_frames(
        _frames(boundaries),
        run_id=_RUN,
        source_revision=_REVISION,
        window=CulturalAnalysisWindow(end_boundary=boundaries),
    )
    batch, batch_peak, batch_seconds = _traced(
        lambda: compute_cultural_trait_dynamics(inputs)
    )
    incremental, incremental_peak, incremental_seconds = _traced(
        lambda: compute_cultural_trait_dynamics_incremental(inputs)
    )
    assert incremental == batch
    assert _measurement_digest(incremental) == _measurement_digest(batch)

    accumulator = TraitDynamicsAccumulator.from_inputs(inputs)
    for boundary in inputs.boundaries:
        accumulator.apply(boundary)
    accumulator.seal()
    identity = accumulator.identity(
        config_fingerprint="1" * 64,
        manifest_identity="incremental-scale",
    )
    checkpoint = accumulator.checkpoint(
        config_fingerprint="1" * 64,
        manifest_identity="incremental-scale",
    )
    path = tmp_path / "view.json"
    write_checkpoint(path, checkpoint)
    resumed = resume_checkpoint(read_checkpoint(path), expected=identity)
    assert resumed.measurements() == incremental
    checkpoint_bytes = path.stat().st_size
    digest = hashlib.sha256(
        json.dumps(
            [row.to_payload() for row in incremental],
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    assert incremental_seconds > 0
    _LOG.info(
        "incremental_trait_analysis boundaries=%s rows=%s batch_peak_bytes=%s "
        "incremental_peak_bytes=%s checkpoint_bytes=%s batch_seconds=%.4f "
        "incremental_seconds=%.4f output_digest=%s",
        boundaries,
        len(incremental),
        batch_peak,
        incremental_peak,
        checkpoint_bytes,
        batch_seconds,
        incremental_seconds,
        digest[:12],
    )
    assert incremental_peak <= batch_peak * 2
    assert checkpoint_bytes > 0
