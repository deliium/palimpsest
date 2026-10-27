"""Exact incremental V3 metric reducers and disposable derived view checkpoints."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from agents.models import AgentId
from analysis import compute_generational_cohort_comparison
from analysis.cultural_evolution_evidence import (
    CulturalAnalysisWindow,
    normalize_cultural_frames,
)
from analysis.cultural_trait_dynamics import (
    compute_cultural_trait_dynamics,
    trait_sort_key,
)
from analysis.incremental_cultural_traits import (
    AnalyticalViewMismatch,
    TraitDynamicsAccumulator,
    compute_cultural_trait_dynamics_incremental,
    read_checkpoint,
    resume_checkpoint,
    write_checkpoint,
)
from analysis.incremental_generational import (
    GenerationalProgressAccumulator,
    IncrementalProgressError,
    fold_generational_progress,
)
from simulation.cultural_evidence import (
    CULTURAL_EVIDENCE_BASIS_UNAVAILABLE,
    CULTURAL_EVIDENCE_CHANNEL_PRACTICAL_KNOWLEDGE,
    CULTURAL_EVIDENCE_COVERAGE_MISSING,
    CulturalBoundaryExport,
    CulturalCaptureStatus,
    CulturalChannelExport,
    CulturalOwnerExport,
)
from simulation.generational_models import (
    CohortPopulationRow,
    GenerationPopulationRow,
    PopulationProgress,
)
from tests.unit.test_cultural_evolution_normalization import (
    _LEARNER,
    _TEACHER,
    _empty_ledgers,
    _owner,
    _practical_entry,
    _practical_ledger,
)

pytestmark = pytest.mark.unit

_RUN = "run-incremental"
_REVISION = "rev-incremental"
_FINGERPRINT = "f" * 64
_MANIFEST = "manifest-incremental"


def _boundary(
    tick: int,
    *,
    teacher_entries: tuple[Any, ...] = (),
    learner_entries: tuple[Any, ...] = (),
    learner_living: bool = True,
    learner_practical_missing: bool = False,
) -> CulturalBoundaryExport:
    teacher_ledgers = _empty_ledgers(_TEACHER)
    teacher_ledgers[CULTURAL_EVIDENCE_CHANNEL_PRACTICAL_KNOWLEDGE] = _practical_ledger(
        _TEACHER, teacher_entries
    )
    learner_ledgers = _empty_ledgers(_LEARNER)
    learner_ledgers[CULTURAL_EVIDENCE_CHANNEL_PRACTICAL_KNOWLEDGE] = _practical_ledger(
        _LEARNER, learner_entries
    )
    teacher = _owner(_TEACHER, 0, teacher_ledgers)
    learner = (
        _owner(_LEARNER, 1, learner_ledgers)
        if learner_living
        else _dead_owner(_LEARNER, 1, learner_ledgers)
    )
    if learner_practical_missing:
        missing = CulturalChannelExport(
            channel=CULTURAL_EVIDENCE_CHANNEL_PRACTICAL_KNOWLEDGE,
            enabled=True,
            coverage=CULTURAL_EVIDENCE_COVERAGE_MISSING,
            basis=CULTURAL_EVIDENCE_BASIS_UNAVAILABLE,
        )
        teacher = _replace_channel(
            teacher,
            CULTURAL_EVIDENCE_CHANNEL_PRACTICAL_KNOWLEDGE,
            missing,
        )
        learner = _replace_channel(
            learner,
            CULTURAL_EVIDENCE_CHANNEL_PRACTICAL_KNOWLEDGE,
            missing,
        )
    return CulturalBoundaryExport(_RUN, tick, (teacher, learner))


def _dead_owner(
    owner: AgentId,
    generation: int,
    ledgers: dict[str, object | None],
) -> CulturalOwnerExport:
    living = _owner(owner, generation, ledgers)
    return CulturalOwnerExport(owner, generation, False, living.channels)


def _replace_channel(
    owner: CulturalOwnerExport,
    channel: str,
    replacement: CulturalChannelExport,
) -> CulturalOwnerExport:
    return CulturalOwnerExport(
        owner.owner_id,
        owner.generation_index,
        owner.living,
        tuple(
            replacement if item.channel == channel else item for item in owner.channels
        ),
    )


def _entry(
    owner: AgentId,
    *,
    entry_id: str,
    content_key: str,
    acquired_tick: int,
    source: AgentId | None = None,
) -> object:
    return _practical_entry(
        owner=owner,
        entry_id=entry_id,
        content_key=content_key,
        fingerprint=(f"fp:{content_key}",),
        acquired_tick=acquired_tick,
        source=source,
    )


def _late_trait_frames() -> tuple[CulturalBoundaryExport, ...]:
    late = _entry(
        _TEACHER,
        entry_id="pk-late",
        content_key="tech:late",
        acquired_tick=2,
    )
    return (
        _boundary(0),
        _boundary(1),
        _boundary(2, teacher_entries=(late,)),
    )


def _inputs(
    frames: tuple[CulturalBoundaryExport, ...],
    *,
    gaps: tuple[str, ...] = (),
) -> Any:
    return normalize_cultural_frames(
        frames,
        run_id=_RUN,
        source_revision=_REVISION,
        window=CulturalAnalysisWindow(end_boundary=len(frames)),
        gaps=gaps,
    )


def test_trait_incremental_matches_batch_and_emits_earlier_zero_rows() -> None:
    inputs = _inputs(_late_trait_frames())
    batch = compute_cultural_trait_dynamics(inputs)
    incremental = compute_cultural_trait_dynamics_incremental(inputs)
    assert incremental == batch
    assert list(incremental) == sorted(incremental, key=trait_sort_key)
    early = [
        row
        for row in incremental
        if row.measurement_id == "trait_frequency"
        and row.dimension == "technology"
        and row.end_tick < 2
    ]
    assert early
    assert {row.numerator for row in early} == {0.0}


@pytest.mark.parametrize(
    "learner_living,missing",
    [(True, False), (False, False), (True, True)],
)
def test_trait_incremental_matches_batch_for_coverage_and_death_cases(
    learner_living: bool,
    missing: bool,
) -> None:
    trait = _entry(
        _LEARNER,
        entry_id="pk-learner",
        content_key="tech:late",
        acquired_tick=1,
        source=_TEACHER,
    )
    frames = (
        _boundary(0),
        _boundary(
            1,
            teacher_entries=(
                _entry(
                    _TEACHER,
                    entry_id="pk-teacher",
                    content_key="tech:late",
                    acquired_tick=0,
                ),
            ),
            learner_entries=(trait,),
            learner_living=learner_living,
            learner_practical_missing=missing,
        ),
        _boundary(
            3,
            teacher_entries=(
                _entry(
                    _TEACHER,
                    entry_id="pk-teacher",
                    content_key="tech:late",
                    acquired_tick=0,
                ),
            ),
            learner_entries=(trait,),
            learner_practical_missing=missing,
        ),
    )
    inputs = _inputs(frames, gaps=("capture_truncated",))
    assert compute_cultural_trait_dynamics_incremental(
        inputs
    ) == compute_cultural_trait_dynamics(inputs)


@settings(max_examples=15, deadline=None)
@given(
    acquisitions=st.lists(
        st.tuples(
            st.integers(min_value=0, max_value=1),
            st.integers(min_value=0, max_value=2),
            st.sampled_from(["tech:a", "tech:b", "tech:c"]),
            st.booleans(),
        ),
        max_size=6,
    )
)
def test_trait_incremental_hypothesis_matches_batch(
    acquisitions: list[tuple[int, int, str, bool]],
) -> None:
    owner_by_index = (_TEACHER, _LEARNER)
    unique: dict[tuple[int, str], tuple[int, bool]] = {}
    for owner_index, acquired_tick, content_key, transmitted in acquisitions:
        key = (owner_index, content_key)
        existing = unique.get(key)
        if existing is None or acquired_tick < existing[0]:
            unique[key] = (acquired_tick, transmitted)
    entries: dict[int, list[Any]] = {0: [], 1: []}
    for ordinal, (
        (owner_index, content_key),
        (acquired_tick, transmitted),
    ) in enumerate(sorted(unique.items())):
        owner = owner_by_index[owner_index]
        entries[owner_index].append(
            _entry(
                owner,
                entry_id=f"pk-{owner_index}-{ordinal}-{acquired_tick}",
                content_key=content_key,
                acquired_tick=acquired_tick,
                source=_TEACHER if transmitted and owner_index == 1 else None,
            )
        )
    frames = tuple(
        _boundary(
            tick,
            teacher_entries=tuple(
                entry for entry in entries[0] if entry.acquired_tick <= tick
            ),
            learner_entries=tuple(
                entry for entry in entries[1] if entry.acquired_tick <= tick
            ),
        )
        for tick in range(3)
    )
    inputs = _inputs(frames)
    assert compute_cultural_trait_dynamics_incremental(
        inputs
    ) == compute_cultural_trait_dynamics(inputs)


def test_trait_checkpoint_prefix_and_final_resume(tmp_path: Path) -> None:
    inputs = _inputs(_late_trait_frames())
    accumulator = TraitDynamicsAccumulator.from_inputs(inputs)
    accumulator.apply(inputs.boundaries[0])
    accumulator.apply(inputs.boundaries[1])
    prefix_identity = accumulator.identity(
        config_fingerprint=_FINGERPRINT,
        manifest_identity=_MANIFEST,
    )
    prefix_checkpoint = accumulator.checkpoint(
        config_fingerprint=_FINGERPRINT,
        manifest_identity=_MANIFEST,
    )
    path = tmp_path / "view" / "prefix.json"
    write_checkpoint(path, prefix_checkpoint)
    resumed = resume_checkpoint(
        read_checkpoint(path),
        expected=prefix_identity,
    )
    assert resumed.sealed is False
    assert resumed.states == accumulator.states
    resumed.apply(inputs.boundaries[2])
    resumed.seal()
    assert resumed.measurements() == compute_cultural_trait_dynamics(inputs)

    final_identity = resumed.identity(
        config_fingerprint=_FINGERPRINT,
        manifest_identity=_MANIFEST,
    )
    final_checkpoint = resumed.checkpoint(
        config_fingerprint=_FINGERPRINT,
        manifest_identity=_MANIFEST,
    )
    final_path = tmp_path / "view" / "final.json"
    write_checkpoint(final_path, final_checkpoint)
    final_resumed = resume_checkpoint(
        read_checkpoint(final_path),
        expected=final_identity,
    )
    assert final_resumed.sealed is True
    assert final_resumed.measurements() == resumed.measurements()


def test_trait_checkpoint_rejects_mismatch_and_tamper(tmp_path: Path) -> None:
    inputs = _inputs(_late_trait_frames())
    accumulator = TraitDynamicsAccumulator.from_inputs(inputs)
    for boundary in inputs.boundaries:
        accumulator.apply(boundary)
    accumulator.seal()
    identity = accumulator.identity(
        config_fingerprint=_FINGERPRINT,
        manifest_identity=_MANIFEST,
    )
    checkpoint = accumulator.checkpoint(
        config_fingerprint=_FINGERPRINT,
        manifest_identity=_MANIFEST,
    )
    path = tmp_path / "view.json"
    write_checkpoint(path, checkpoint)

    mismatched = replace(
        identity,
        config_fingerprint="a" * 64,
        gaps=identity.gaps,
        gaps_digest=identity.gaps_digest,
    )
    with pytest.raises(AnalyticalViewMismatch, match="view_identity_mismatch"):
        resume_checkpoint(read_checkpoint(path), expected=mismatched)

    document = json.loads(path.read_bytes())
    document["identity"]["run_id"] = "run-changed"
    path.write_text(json.dumps(document))
    with pytest.raises(AnalyticalViewMismatch, match="view_digest_mismatch"):
        read_checkpoint(path)


def _progress(
    tick: int,
    *,
    cohorts: tuple[CohortPopulationRow, ...],
    generations: tuple[GenerationPopulationRow, ...],
) -> PopulationProgress:
    return PopulationProgress(
        boundary_tick=tick,
        living_population=sum(row.living for row in cohorts),
        total_admitted=sum(row.admitted for row in cohorts),
        total_deaths=sum(row.dead for row in cohorts),
        max_generation_index_seen=max(
            (row.generation_index for row in generations), default=0
        ),
        cohorts=cohorts,
        generations=generations,
    )


def _snapshots() -> tuple[PopulationProgress, PopulationProgress, PopulationProgress]:
    return (
        _progress(
            2,
            cohorts=(CohortPopulationRow(0, 0, "cohort-0", 3, 3, 0),),
            generations=(GenerationPopulationRow(0, 3, 3, 0),),
        ),
        _progress(
            5,
            cohorts=(
                CohortPopulationRow(0, 0, "cohort-0", 3, 2, 1),
                CohortPopulationRow(1, 4, "cohort-1", 2, 2, 0),
            ),
            generations=(
                GenerationPopulationRow(0, 3, 2, 1),
                GenerationPopulationRow(1, 2, 2, 0),
            ),
        ),
        _progress(
            9,
            cohorts=(
                CohortPopulationRow(0, 0, "cohort-0", 3, 1, 2),
                CohortPopulationRow(1, 4, "cohort-1", 2, 1, 1),
            ),
            generations=(
                GenerationPopulationRow(0, 3, 1, 2),
                GenerationPopulationRow(1, 2, 1, 1),
            ),
        ),
    )


def test_generational_incremental_matches_batch_and_deltas() -> None:
    first, second, third = _snapshots()
    batch = compute_generational_cohort_comparison(
        third,
        run_id="run-bm",
        input_revision="rev-bm",
        window_end=9,
    )
    assert (
        fold_generational_progress(
            (first, second, third),
            run_id="run-bm",
            input_revision="rev-bm",
            window_end=9,
        )
        == batch
    )
    accumulator = GenerationalProgressAccumulator()
    accumulator.apply(first)
    assert accumulator.apply(second) is not None
    delta = accumulator.apply(third)
    assert delta is not None
    assert delta.admitted_delta == 0
    assert delta.deaths_delta == 2
    assert delta.living_delta == -2
    assert (
        accumulator.document(
            run_id="run-bm",
            input_revision="rev-bm",
            window_end=9,
        )
        == batch
    )


def test_generational_incremental_replay_and_conflicts() -> None:
    first, second, _third = _snapshots()
    accumulator = GenerationalProgressAccumulator()
    accumulator.apply(first)
    assert accumulator.apply(first) is None
    accumulator.apply(second)
    assert len(accumulator.deltas) == 1
    with pytest.raises(IncrementalProgressError, match="progress_conflict"):
        accumulator.apply(
            _progress(
                5,
                cohorts=(CohortPopulationRow(0, 0, "cohort-0", 4, 4, 0),),
                generations=(GenerationPopulationRow(0, 4, 4, 0),),
            )
        )
    with pytest.raises(IncrementalProgressError, match="progress_nonadvancing"):
        accumulator.apply(first)
    with pytest.raises(IncrementalProgressError, match="admitted_nonmonotonic"):
        accumulator.apply(
            _progress(
                6,
                cohorts=(CohortPopulationRow(0, 0, "cohort-0", 3, 2, 1),),
                generations=(GenerationPopulationRow(0, 3, 2, 1),),
            )
        )


def test_derived_checkpoint_never_claims_capture_status() -> None:
    status = CulturalCaptureStatus(active=True, failed=False)
    assert status.failed is False
    inputs = _inputs(_late_trait_frames())
    identity = TraitDynamicsAccumulator.from_inputs(inputs).identity(
        config_fingerprint=_FINGERPRINT,
        manifest_identity=_MANIFEST,
    )
    assert identity.metric_family == "cultural_trait_dynamics"
    assert identity.stage == "first_pass"


def test_trait_checkpoint_prefix_rejects_changed_algorithm() -> None:
    inputs = _inputs(_late_trait_frames())
    accumulator = TraitDynamicsAccumulator.from_inputs(inputs)
    accumulator.apply(inputs.boundaries[0])
    identity = accumulator.identity(
        config_fingerprint=_FINGERPRINT,
        manifest_identity=_MANIFEST,
    )
    checkpoint = accumulator.checkpoint(
        config_fingerprint=_FINGERPRINT,
        manifest_identity=_MANIFEST,
    )
    changed = replace(identity, algorithm_version="other-algorithm@1")
    with pytest.raises(
        AnalyticalViewMismatch, match="view_prefix_mismatch:algorithm_version"
    ):
        resume_checkpoint(checkpoint, expected=changed)


def test_trait_checkpoint_interrupted_write_keeps_previous_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os

    inputs = _inputs(_late_trait_frames())
    first = TraitDynamicsAccumulator.from_inputs(inputs)
    first.apply(inputs.boundaries[0])
    checkpoint = first.checkpoint(
        config_fingerprint=_FINGERPRINT,
        manifest_identity=_MANIFEST,
    )
    path = tmp_path / "view.json"
    write_checkpoint(path, checkpoint)
    previous = path.read_bytes()

    def _interrupt(source: object, target: object) -> None:
        raise OSError("interrupted")

    monkeypatch.setattr(os, "replace", _interrupt)
    with pytest.raises(OSError, match="interrupted"):
        write_checkpoint(path, checkpoint)
    assert path.read_bytes() == previous
    assert read_checkpoint(path) == checkpoint


def test_trait_checkpoint_size_budget_fails_before_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import analysis.incremental_cultural_traits as module

    inputs = _inputs(_late_trait_frames())
    accumulator = TraitDynamicsAccumulator.from_inputs(inputs)
    accumulator.apply(inputs.boundaries[0])
    checkpoint = accumulator.checkpoint(
        config_fingerprint=_FINGERPRINT,
        manifest_identity=_MANIFEST,
    )
    monkeypatch.setattr(module, "MAX_CHECKPOINT_BYTES", 16)
    path = tmp_path / "view.json"
    with pytest.raises(AnalyticalViewMismatch, match="checkpoint_too_large"):
        write_checkpoint(path, checkpoint)
    assert not path.exists()


def test_trait_incremental_handles_cycle_and_missing_baseline() -> None:
    trait = _entry(
        _TEACHER,
        entry_id="pk-cycle",
        content_key="tech:cycle",
        acquired_tick=0,
    )
    frames = (
        _boundary(0, teacher_entries=(trait,)),
        _boundary(1),
        _boundary(2, teacher_entries=(trait,)),
        _boundary(3),
    )
    cyclic = normalize_cultural_frames(
        frames,
        run_id=_RUN,
        source_revision=_REVISION,
        window=CulturalAnalysisWindow(baseline_boundary=0, end_boundary=3),
    )
    assert compute_cultural_trait_dynamics_incremental(
        cyclic
    ) == compute_cultural_trait_dynamics(cyclic)

    missing = normalize_cultural_frames(
        frames,
        run_id=_RUN,
        source_revision=_REVISION,
        window=CulturalAnalysisWindow(baseline_boundary=4, end_boundary=6),
    )
    assert compute_cultural_trait_dynamics_incremental(
        missing
    ) == compute_cultural_trait_dynamics(missing)


def test_trait_incremental_handles_baseline_death() -> None:
    frames = (
        _boundary(0, learner_living=False),
        _boundary(1),
        _boundary(2, learner_living=False),
    )
    inputs = normalize_cultural_frames(
        frames,
        run_id=_RUN,
        source_revision=_REVISION,
        window=CulturalAnalysisWindow(baseline_boundary=0, end_boundary=2),
    )
    assert compute_cultural_trait_dynamics_incremental(
        inputs
    ) == compute_cultural_trait_dynamics(inputs)
