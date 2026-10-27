"""Reject unsupported or extrapolated V3 scale support claims."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.benchmarks.v3_support import (
    CompositionStatus,
    CompositionTrial,
    EnvelopeError,
    SupportRow,
    SupportStatus,
    build_envelope,
    generate_from_directory,
    validate_envelope,
)


def _row(**overrides: object) -> SupportRow:
    values: dict[str, object] = {
        "category": "generational",
        "status": SupportStatus.VERIFIED,
        "requested_horizon": 10_000,
        "completed_horizon": 10_000,
        "last_verified_boundary": 9_999,
        "repetitions": 3,
        "run_ids": ("v3-43-generational-ticks-10000-seed-23",),
        "artifact_paths": ("/tmp/opencode/v3-43-scale/task19-10k/a.json",),
        "source_revision": "3930540",
        "scientific": True,
        "density": "sustained",
        "generations": 5,
        "evidence_volume": 5_241,
        "warm_samples": 0,
        "correctness_passed": True,
        "capture_requested": False,
        "capture_publications": 0,
        "browser_verified": False,
        "reason": None,
        "limitations": (),
    }
    values.update(overrides)
    return SupportRow(**values)  # type: ignore[arg-type]


def _browser_row() -> SupportRow:
    return _row(
        category="observer-playback",
        requested_horizon=10_000,
        completed_horizon=10_000,
        status=SupportStatus.UNVERIFIED,
        run_ids=("v3-43-generational-ticks-10000-seed-23",),
        artifact_paths=(),
        browser_verified=False,
        reason="browser_gate_not_run",
    )


def test_verified_row_builds_measured_through_not_universal_maximum() -> None:
    envelope = build_envelope(
        [_row(), _browser_row()],
        source_revision="3930540",
        environment={"platform": "linux", "database": "guarded"},
        limitations=["100k dense lanes timed out"],
    )
    assert envelope["measured_through_horizon"] == 10_000
    assert "max_supported_ticks" not in envelope
    assert envelope["rows"][0]["status"] == "verified"
    assert envelope["rows"][1]["status"] == "unverified"
    validate_envelope(envelope)


def test_sparse_lane_cannot_certify_dense_history() -> None:
    with pytest.raises(EnvelopeError) as exc:
        _validated(
            _row(
                density="sparse",
                requested_horizon=100_000,
                completed_horizon=100_000,
                last_verified_boundary=99_999,
            )
        )
    assert exc.value.code == "sparse_cannot_certify_dense"


def test_10k_completion_cannot_certify_100k() -> None:
    with pytest.raises(EnvelopeError) as exc:
        _validated(_row(requested_horizon=100_000, completed_horizon=10_000))
    assert exc.value.code == "incomplete_horizon_cannot_be_verified"


def test_insufficient_repetitions_are_rejected() -> None:
    with pytest.raises(EnvelopeError) as exc:
        _validated(_row(repetitions=2))
    assert exc.value.code == "insufficient_repetitions"


def test_paired_identity_mismatch_is_rejected() -> None:
    with pytest.raises(EnvelopeError) as exc:
        _validated(_row(run_ids=("run-a", "run-b")))
    assert exc.value.code == "paired_identity_mismatch"


def test_query_claims_require_checked_warm_samples() -> None:
    with pytest.raises(EnvelopeError) as exc:
        _validated(
            _row(
                category="historical-query",
                requested_horizon=10_000,
                completed_horizon=10_000,
                warm_samples=3,
            )
        )
    assert exc.value.code == "insufficient_warm_query_samples"


def test_browser_playback_requires_browser_evidence() -> None:
    with pytest.raises(EnvelopeError) as exc:
        _validated(
            _row(
                category="observer-playback",
                browser_verified=False,
            )
        )
    assert exc.value.code == "browser_evidence_required"


def test_truncated_capture_cannot_certify_evidence_rich_lane() -> None:
    with pytest.raises(EnvelopeError) as exc:
        _validated(
            _row(
                category="evidence-rich",
                capture_requested=True,
                capture_publications=0,
            )
        )
    assert exc.value.code == "truncated_capture_cannot_be_verified"


def test_failed_correctness_overrides_fast_timing() -> None:
    with pytest.raises(EnvelopeError) as exc:
        _validated(_row(correctness_passed=False))
    assert exc.value.code == "correctness_required_for_verified"


def test_extrapolated_values_cannot_be_verified() -> None:
    with pytest.raises(EnvelopeError) as exc:
        _validated(_row(limitations=("extrapolated storage projection",)))
    assert exc.value.code == "extrapolated_cannot_be_verified"


def test_envelope_rejects_universal_maximum_language() -> None:
    envelope = build_envelope(
        [_row()],
        source_revision="3930540",
        environment={"platform": "linux"},
    )
    envelope["max_supported_ticks"] = 100_000
    with pytest.raises(EnvelopeError) as exc:
        validate_envelope(envelope)
    assert exc.value.code == "universal_maximum_forbidden"


def test_all_unverified_envelope_is_valid() -> None:
    envelope = build_envelope(
        [_browser_row()],
        source_revision="3930540",
        environment={"platform": "linux"},
    )
    assert envelope["rows"][0]["status"] == "unverified"


def _trial(
    name: str = "retirement", variant: str = "off", **overrides: object
) -> CompositionTrial:
    values: dict[str, object] = {
        "name": name,
        "variant": variant,
        "status": CompositionStatus.TESTED,
        "scope": "192-tick-single-pair",
        "evidence": (f"/tmp/{name}-{variant}.json",),
        "metrics": {"retired_owner_count": 0},
        "notes": (),
        "capacity_claim": False,
    }
    values.update(overrides)
    return CompositionTrial(**values)  # type: ignore[arg-type]


def test_composition_requires_off_on_pairs() -> None:
    with pytest.raises(EnvelopeError) as exc:
        build_envelope(
            [_browser_row()],
            source_revision="3930540",
            environment={"platform": "linux"},
            composition=[_trial("retirement", "off")],
        )
    assert exc.value.code == "composition_pair_incomplete:retirement"


def test_composition_pair_with_evidence_is_valid() -> None:
    envelope = build_envelope(
        [_browser_row()],
        source_revision="3930540",
        environment={"platform": "linux"},
        composition=[_trial("retirement", "off"), _trial("retirement", "on")],
    )
    composition = envelope["composition"]
    assert [item["variant"] for item in composition] == ["off", "on"]
    assert all(item["capacity_claim"] is False for item in composition)
    validate_envelope(envelope)


def test_tested_composition_requires_evidence() -> None:
    with pytest.raises(EnvelopeError) as exc:
        build_envelope(
            [_browser_row()],
            source_revision="3930540",
            environment={"platform": "linux"},
            composition=[
                _trial("retirement", "off", evidence=()),
                _trial("retirement", "on"),
            ],
        )
    assert exc.value.code == "tested_composition_requires_evidence"


def test_composition_cannot_claim_capacity() -> None:
    with pytest.raises(EnvelopeError) as exc:
        build_envelope(
            [_browser_row()],
            source_revision="3930540",
            environment={"platform": "linux"},
            composition=[
                _trial("retirement", "off", capacity_claim=True),
                _trial("retirement", "on"),
            ],
        )
    assert exc.value.code == "composition_cannot_claim_capacity"


def test_generator_skips_composition_measurements_and_loads_trials(
    tmp_path: Path,
) -> None:
    import json

    path = tmp_path / "gen" / "measurement.json"
    path.parent.mkdir()
    path.write_text(
        json.dumps(
            _measurement(
                lane="generational",
                ticks=10_000,
                run_id="v3-43-generational-ticks-10000-seed-23",
                status="completed",
                completed=10_000,
                boundary=9_999,
            )
        ),
        encoding="utf-8",
    )
    composition_measurement = (
        tmp_path / "composition" / "retirement" / "off" / "measurement.json"
    )
    composition_measurement.parent.mkdir(parents=True)
    composition_measurement.write_text(
        json.dumps(
            _measurement(
                lane="generational-retired",
                ticks=192,
                run_id="retirement-off",
                status="completed",
                completed=192,
                boundary=191,
            )
        ),
        encoding="utf-8",
    )
    from tests.benchmarks.v3_support import write_composition

    composition_path = tmp_path / "composition" / "composition.json"
    write_composition(
        composition_path,
        [_trial("retirement", "off"), _trial("retirement", "on")],
    )
    envelope = generate_from_directory(
        tmp_path,
        source_revision="3930540",
        composition_path=composition_path,
    )
    assert all(row["category"] != "generational-retired" for row in envelope["rows"])
    assert len(envelope["composition"]) == 2


def test_builtin_composition_covers_spool_and_paging_pairs() -> None:
    from tests.benchmarks.v3_composition import builtin_composition_trials

    trials = builtin_composition_trials()
    names = {(trial.name, trial.variant) for trial in trials}
    assert ("capture-spool", "off") in names
    assert ("capture-spool", "on") in names
    assert ("physical-paging", "off") in names
    assert ("physical-paging", "on") in names
    envelope = build_envelope(
        [_browser_row()],
        source_revision="3930540",
        environment={"platform": "linux"},
        composition=trials,
    )
    assert len(envelope["composition"]) == 4
    assert all(item["capacity_claim"] is False for item in envelope["composition"])


def _validated(row: SupportRow) -> None:
    build_envelope(
        [row, _browser_row()],
        source_revision="3930540",
        environment={"platform": "linux"},
    )


def _measurement(
    *,
    lane: str,
    ticks: int,
    run_id: str,
    status: str,
    completed: int,
    boundary: int,
    environment: dict[str, str] | None = None,
    exception_reason: str | None = None,
) -> dict[str, object]:
    return {
        "schema": "v3-scale-measurement-v1",
        "lane": lane,
        "requested_ticks": ticks,
        "run_id": run_id,
        "status": status,
        "completed_ticks": completed,
        "last_verified_boundary": boundary,
        "completed_cohorts": 5 if status == "completed" else 0,
        "events": 5_241 if status == "completed" else 0,
        "exception_reason": exception_reason,
        "environment": (
            {"platform": "linux", "database": "guarded"}
            if environment is None
            else environment
        ),
    }


def test_generator_surfaces_failed_attempts_and_artifact_revision(
    tmp_path: Path,
) -> None:
    import json

    environment = {
        "platform": "linux",
        "database": "guarded",
        "source_revision": "3930540",
        "postgresql": "17.5",
    }
    for repetition in range(3):
        path = tmp_path / f"gen-{repetition}" / "measurement.json"
        path.parent.mkdir()
        path.write_text(
            json.dumps(
                _measurement(
                    lane="generational",
                    ticks=10_000,
                    run_id="v3-43-generational-ticks-10000-seed-23",
                    status="completed",
                    completed=10_000,
                    boundary=9_999,
                    environment=environment,
                )
            ),
            encoding="utf-8",
        )
    failed = tmp_path / "gen-failed" / "measurement.json"
    failed.parent.mkdir()
    failed.write_text(
        json.dumps(
            _measurement(
                lane="generational",
                ticks=10_000,
                run_id="v3-43-generational-ticks-10000-seed-23",
                status="failed",
                completed=0,
                boundary=0,
                environment=environment,
                exception_reason="worker_error_RunnerConstructionError",
            )
        ),
        encoding="utf-8",
    )

    envelope = generate_from_directory(tmp_path, source_revision="1c5c18c")
    row = envelope["rows"][0]
    assert row["status"] == "verified"
    assert row["repetitions"] == 3
    assert row["attempted_repetitions"] == 4
    assert row["failed_attempts"] == 1
    assert row["failure_reasons"] == ["worker_error_RunnerConstructionError"]
    assert len(row["attempt_paths"]) == 4
    assert row["source_revision"] == "3930540"
    assert envelope["environment"]["postgresql"] == "17.5"
    assert any("1 of 4 attempts" in item for item in row["limitations"])
    assert any("1/4 attempts" in item for item in envelope["limitations"])


def test_generator_discloses_missing_artifact_revision(tmp_path: Path) -> None:
    import json

    for repetition in range(3):
        path = tmp_path / f"gen-{repetition}" / "measurement.json"
        path.parent.mkdir()
        path.write_text(
            json.dumps(
                _measurement(
                    lane="generational",
                    ticks=10_000,
                    run_id="v3-43-generational-ticks-10000-seed-23",
                    status="completed",
                    completed=10_000,
                    boundary=9_999,
                )
            ),
            encoding="utf-8",
        )

    envelope = generate_from_directory(tmp_path, source_revision="1c5c18c")
    row = envelope["rows"][0]
    assert row["source_revision"] == "1c5c18c"
    assert any("did not record source_revision" in item for item in row["limitations"])
    assert any(
        "did not record the PostgreSQL version" in item
        for item in envelope["limitations"]
    )


def test_generator_uses_only_traceable_repeated_artifacts(tmp_path: Path) -> None:
    import json

    for repetition in range(3):
        path = tmp_path / f"gen-{repetition}" / "measurement.json"
        path.parent.mkdir()
        path.write_text(
            json.dumps(
                _measurement(
                    lane="generational",
                    ticks=10_000,
                    run_id="v3-43-generational-ticks-10000-seed-23",
                    status="completed",
                    completed=10_000,
                    boundary=9_999,
                )
            ),
            encoding="utf-8",
        )
    incomplete = tmp_path / "gen-100k" / "measurement.json"
    incomplete.parent.mkdir()
    incomplete.write_text(
        json.dumps(
            _measurement(
                lane="generational",
                ticks=100_000,
                run_id="v3-43-generational-ticks-100000-seed-23",
                status="timed_out",
                completed=2_229,
                boundary=2_228,
            )
            | {"exception_reason": "deadline_exceeded"}
        ),
        encoding="utf-8",
    )
    envelope = generate_from_directory(tmp_path, source_revision="3930540")
    rows = {
        (row["category"], row["requested_horizon"]): row for row in envelope["rows"]
    }
    verified = rows[("generational", 10_000)]
    assert verified["status"] == "verified"
    assert verified["repetitions"] == 3
    assert rows[("generational", 100_000)]["status"] == "tested_incomplete"
    assert rows[("observer-playback", None)]["status"] == "unverified"
    assert envelope["measured_through_horizon"] == 10_000
    assert all(
        row["status"] != "verified"
        for row in envelope["rows"]
        if row["completed_horizon"] is not None
        and row["completed_horizon"] < (row["requested_horizon"] or 0)
    )


def test_generator_does_not_promote_mismatched_identities(tmp_path: Path) -> None:
    import json

    for repetition, run_id in enumerate(("run-a", "run-b", "run-c")):
        path = tmp_path / f"rep-{repetition}" / "measurement.json"
        path.parent.mkdir()
        path.write_text(
            json.dumps(
                _measurement(
                    lane="generation" if False else "generational",
                    ticks=10_000,
                    run_id=run_id,
                    status="completed",
                    completed=10_000,
                    boundary=9_999,
                )
            ),
            encoding="utf-8",
        )
    envelope = generate_from_directory(tmp_path, source_revision="3930540")
    generational = next(
        row for row in envelope["rows"] if row["category"] == "generational"
    )
    assert generational["status"] == "tested_incomplete"
    assert generational["reason"] == "insufficient_repetitions"
