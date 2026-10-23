"""Strict sibling artifacts for historical-contingency experiments."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.path_dependence_artifacts import (
    BRANCH_SCHEMA_VERSION,
    PathDependenceArtifactError,
    PathDependenceArtifactStore,
    build_branch_document,
    build_comparison_document,
    build_ensemble_document,
    build_outcomes_document,
    build_prefix_document,
    canonical_bytes,
    verify_path_dependence_branch,
)
from experiments.path_dependence_scenario import historical_contingency_scenario

pytestmark = pytest.mark.unit

DIGEST_A = "a" * 64
DIGEST_B = "b" * 64


class _Reader:
    def __init__(self, terminal: dict[str, object] | None) -> None:
        self._terminal = terminal

    def exists(self, run_id: str) -> bool:
        return self._terminal is not None

    def terminal(self, run_id: str) -> dict[str, object] | None:
        return self._terminal


def _ensemble() -> dict[str, object]:
    return build_ensemble_document(
        historical_contingency_scenario(profile="smoke"),
        source_revision="unit-source",
        source_artifact_digest=DIGEST_A,
    )


def _prefix(ensemble: dict[str, object], *, fork_tick: int = 4) -> dict[str, object]:
    return build_prefix_document(
        ensemble_id=str(ensemble["ensemble_id"]),
        parent_scientific_id="pd-parent-unit",
        parent_attempt_id="attempt-1",
        fork_tick=fork_tick,
        boundary_revision=10 + fork_tick,
        config_fingerprint=str(ensemble["config_fingerprint"]),
        source_revision="unit-source",
        provider_identity="deterministic_fake",
        complete_state_digest=DIGEST_B,
        checkpoint_format_version="runner-fork-checkpoint-v1",
        bootstrap_hash="c" * 64,
        snapshot_hash="d" * 64,
        objective_head_hash="e" * 64,
        common_setup_digest="f" * 64,
        eligible=True,
        eligibility_reason="eligible",
    )


def _preparation(
    ensemble: dict[str, object], prefix: dict[str, object]
) -> dict[str, object]:
    return build_branch_document(
        kind="preparation",
        ensemble_id=str(ensemble["ensemble_id"]),
        parent_scientific_id="pd-parent-unit",
        parent_attempt_id="attempt-1",
        fork_tick=4,
        child_scientific_id="child-unit",
        child_attempt_id="attempt-1",
        slot_ordinal=0,
        arm_id="share",
        action_schedule_digest="1" * 64,
        assignment_seed=7,
        assignment_policy="permuted-treatment-blind-slots-v1",
        prefix_digest=str(prefix["digest"]),
        details={"expected_checkpoint_digest": DIGEST_B},
    )


def _outcomes(ensemble: dict[str, object]) -> dict[str, object]:
    return build_outcomes_document(
        ensemble_id=str(ensemble["ensemble_id"]),
        child_scientific_id="child-unit",
        child_attempt_id="attempt-1",
        slot_ordinal=0,
        fork_tick=4,
        rows=(
            {
                "selector_id": "norms.active_beliefs",
                "window_id": "post",
                "value": 0.0,
                "availability": "known_zero",
            },
        ),
        coverage={"complete": True},
        evidence_refs=("boundary:4", "boundary:8"),
    )


def _result(
    ensemble: dict[str, object],
    prefix: dict[str, object],
    outcomes: dict[str, object],
) -> dict[str, object]:
    return build_branch_document(
        kind="result",
        ensemble_id=str(ensemble["ensemble_id"]),
        parent_scientific_id="pd-parent-unit",
        parent_attempt_id="attempt-1",
        fork_tick=4,
        child_scientific_id="child-unit",
        child_attempt_id="attempt-1",
        slot_ordinal=0,
        arm_id="share",
        action_schedule_digest="1" * 64,
        assignment_seed=7,
        assignment_policy="permuted-treatment-blind-slots-v1",
        prefix_digest=str(prefix["digest"]),
        details={
            "child_run_id": "child-unit",
            "requested_actions": 1,
            "treatment_ledger": (),
            "stop_reason": "horizon_reached",
            "terminal_tick": 8,
            "terminal_revision": 18,
            "pre_treatment_state_digest": DIGEST_B,
            "channel_manifest": ("objective",),
            "outcomes_digest": str(outcomes["digest"]),
        },
    )


def _completion(
    ensemble: dict[str, object],
    prefix: dict[str, object],
    result: dict[str, object],
    outcomes: dict[str, object],
) -> dict[str, object]:
    return build_branch_document(
        kind="completion",
        ensemble_id=str(ensemble["ensemble_id"]),
        parent_scientific_id="pd-parent-unit",
        parent_attempt_id="attempt-1",
        fork_tick=4,
        child_scientific_id="child-unit",
        child_attempt_id="attempt-1",
        slot_ordinal=0,
        arm_id="share",
        action_schedule_digest="1" * 64,
        assignment_seed=7,
        assignment_policy="permuted-treatment-blind-slots-v1",
        prefix_digest=str(prefix["digest"]),
        details={
            "result_digest": str(result["digest"]),
            "outcomes_digest": str(outcomes["digest"]),
            "objective_head_hash": "9" * 64,
            "terminal_tick": 8,
            "terminal_revision": 18,
        },
    )


def _write_branch(
    store: PathDependenceArtifactStore,
    ensemble: dict[str, object],
    kinds: dict[str, dict[str, object]],
) -> None:
    for kind, document in kinds.items():
        store.write_branch(
            ensemble_id=str(ensemble["ensemble_id"]),
            child_id="child-unit",
            attempt_id="attempt-1",
            kind=kind,
            document=document,
        )


def test_ensemble_and_multi_f_prefix_paths_round_trip(tmp_path: Path) -> None:
    store = PathDependenceArtifactStore(tmp_path)
    ensemble = _ensemble()
    store.write_ensemble(ensemble)
    assert store.read_ensemble(str(ensemble["ensemble_id"])) == ensemble
    prefix = _prefix(ensemble)
    for fork_tick in (4, 8):
        document = _prefix(ensemble, fork_tick=fork_tick)
        path = store.write_prefix(
            ensemble_id=str(ensemble["ensemble_id"]),
            parent_id="pd-parent-unit",
            attempt_id="attempt-1",
            fork_tick=fork_tick,
            document=document,
        )
        assert f"fork-{fork_tick}" in path.as_posix()
    assert (
        store.read_prefix(
            ensemble_id=str(ensemble["ensemble_id"]),
            parent_id="pd-parent-unit",
            attempt_id="attempt-1",
            fork_tick=4,
        )
        == prefix
    )


def test_all_branch_kinds_round_trip_and_verify(tmp_path: Path) -> None:
    store = PathDependenceArtifactStore(tmp_path)
    ensemble = _ensemble()
    prefix = _prefix(ensemble)
    outcomes = _outcomes(ensemble)
    result = _result(ensemble, prefix, outcomes)
    completion = _completion(ensemble, prefix, result, outcomes)
    preparation = _preparation(ensemble, prefix)
    store.write_ensemble(ensemble)
    store.write_prefix(
        ensemble_id=str(ensemble["ensemble_id"]),
        parent_id="pd-parent-unit",
        attempt_id="attempt-1",
        fork_tick=4,
        document=prefix,
    )
    _write_branch(
        store,
        ensemble,
        {
            "preparation": preparation,
            "result": result,
            "completion": completion,
        },
    )
    store.write_outcomes(
        ensemble_id=str(ensemble["ensemble_id"]),
        child_id="child-unit",
        attempt_id="attempt-1",
        document=outcomes,
    )
    verified = verify_path_dependence_branch(
        expected={
            "ensemble_id": ensemble["ensemble_id"],
            "parent_id": "pd-parent-unit",
            "parent_attempt": "attempt-1",
            "child_id": "child-unit",
            "child_attempt": "attempt-1",
            "fork_tick": 4,
        },
        store=store,
        repositories=_Reader(
            {
                "terminal_tick": 8,
                "terminal_revision": 18,
                "head_hash": "9" * 64,
            }
        ),
    )
    assert verified.completion["kind"] == "completion"
    assert verified.result["child_run_id"] == "child-unit"


def test_tampered_identity_and_terminal_head_are_rejected(tmp_path: Path) -> None:
    store = PathDependenceArtifactStore(tmp_path)
    ensemble = _ensemble()
    prefix = _prefix(ensemble)
    outcomes = _outcomes(ensemble)
    result = _result(ensemble, prefix, outcomes)
    completion = _completion(ensemble, prefix, result, outcomes)
    store.write_ensemble(ensemble)
    store.write_prefix(
        ensemble_id=str(ensemble["ensemble_id"]),
        parent_id="pd-parent-unit",
        attempt_id="attempt-1",
        fork_tick=4,
        document=prefix,
    )
    _write_branch(
        store,
        ensemble,
        {
            "preparation": _preparation(ensemble, prefix),
            "result": result,
            "completion": completion,
        },
    )
    store.write_outcomes(
        ensemble_id=str(ensemble["ensemble_id"]),
        child_id="child-unit",
        attempt_id="attempt-1",
        document=outcomes,
    )
    with pytest.raises(PathDependenceArtifactError, match="objective_completion"):
        verify_path_dependence_branch(
            expected={
                "ensemble_id": ensemble["ensemble_id"],
                "parent_id": "pd-parent-unit",
                "parent_attempt": "attempt-1",
                "child_id": "child-unit",
                "child_attempt": "attempt-1",
                "fork_tick": 4,
            },
            store=store,
            repositories=_Reader(
                {
                    "terminal_tick": 8,
                    "terminal_revision": 18,
                    "head_hash": "8" * 64,
                }
            ),
        )
    path = (
        tmp_path
        / str(ensemble["ensemble_id"])
        / "branches"
        / "child-unit"
        / "attempt-1"
        / "completion.json"
    )
    data = json.loads(path.read_text())
    data["terminal_tick"] = 9
    path.write_text(json.dumps(data))
    with pytest.raises(PathDependenceArtifactError, match="artifact_hash_mismatch"):
        store.read_branch(
            ensemble_id=str(ensemble["ensemble_id"]),
            child_id="child-unit",
            attempt_id="attempt-1",
            kind="completion",
        )


def test_identical_publication_is_idempotent_and_conflicts_fail(
    tmp_path: Path,
) -> None:
    store = PathDependenceArtifactStore(tmp_path)
    ensemble = _ensemble()
    path = store.write_ensemble(ensemble)
    store.write_ensemble(ensemble)
    changed = build_ensemble_document(
        historical_contingency_scenario(profile="smoke"),
        source_revision="different-source",
        source_artifact_digest=DIGEST_B,
    )
    with pytest.raises(PathDependenceArtifactError, match="artifact_conflict"):
        store.write_ensemble(changed)
    assert path.exists()


def test_unsafe_paths_duplicate_keys_and_nonfinite_values_fail(
    tmp_path: Path,
) -> None:
    store = PathDependenceArtifactStore(tmp_path)
    ensemble = _ensemble()
    with pytest.raises(PathDependenceArtifactError, match="artifact_path_unsafe"):
        store.write_prefix(
            ensemble_id=str(ensemble["ensemble_id"]),
            parent_id="../escape",
            attempt_id="attempt-1",
            fork_tick=4,
            document=_prefix(ensemble),
        )
    path = tmp_path / str(ensemble["ensemble_id"]) / "ensemble.json"
    path.parent.mkdir(parents=True)
    path.write_text('{"schema_version":"x","schema_version":"y"}')
    with pytest.raises(PathDependenceArtifactError, match="artifact_conflict"):
        store.read_ensemble(str(ensemble["ensemble_id"]))
    path.write_text('{"schema_version":"x","digest":"' + "0" * 64 + '","bad":NaN}')
    with pytest.raises(PathDependenceArtifactError, match="artifact_identity_mismatch"):
        store.read_ensemble(str(ensemble["ensemble_id"]))


def test_comparison_and_outcomes_documents_are_sealed(tmp_path: Path) -> None:
    store = PathDependenceArtifactStore(tmp_path)
    ensemble = _ensemble()
    outcomes = _outcomes(ensemble)
    store.write_outcomes(
        ensemble_id=str(ensemble["ensemble_id"]),
        child_id="child-unit",
        attempt_id="attempt-1",
        document=outcomes,
    )
    comparison = build_comparison_document(
        comparison_id="comparison-1",
        ensemble_id=str(ensemble["ensemble_id"]),
        spec_fingerprint=str(ensemble["spec_fingerprint"]),
        input_digests=(str(outcomes["digest"]),),
        contrasts=({"contrast_id": "share-vs-withhold", "mean": None},),
        formula_versions={"outcomes": "path-dependence-outcome-row-v1"},
    )
    store.write_comparison(
        ensemble_id=str(ensemble["ensemble_id"]),
        comparison_id="comparison-1",
        document=comparison,
    )
    assert (
        store.read_comparison(
            ensemble_id=str(ensemble["ensemble_id"]),
            comparison_id="comparison-1",
        )
        == comparison
    )
    assert comparison["causal_claim"] is False
    assert canonical_bytes(comparison).startswith(b"{")
    assert comparison["schema_version"] == "path-dependence-comparison-v1"
    assert BRANCH_SCHEMA_VERSION == "path-dependence-branch-v1"


def _failure(
    ensemble: dict[str, object], prefix: dict[str, object]
) -> dict[str, object]:
    return build_branch_document(
        kind="failure",
        ensemble_id=str(ensemble["ensemble_id"]),
        parent_scientific_id="pd-parent-unit",
        parent_attempt_id="attempt-1",
        fork_tick=4,
        child_scientific_id="child-unit",
        child_attempt_id="attempt-1",
        slot_ordinal=0,
        arm_id="share",
        action_schedule_digest="1" * 64,
        assignment_seed=7,
        assignment_policy="permuted-treatment-blind-slots-v1",
        prefix_digest=str(prefix["digest"]),
        details={
            "last_durable_tick": 6,
            "stage": "cognition",
            "committed_status": "committed",
            "reason_code": "technical_failure",
        },
    )


def test_failure_is_not_a_completion_and_substituted_child_is_rejected(
    tmp_path: Path,
) -> None:
    store = PathDependenceArtifactStore(tmp_path)
    ensemble = _ensemble()
    prefix = _prefix(ensemble)
    store.write_ensemble(ensemble)
    store.write_prefix(
        ensemble_id=str(ensemble["ensemble_id"]),
        parent_id="pd-parent-unit",
        attempt_id="attempt-1",
        fork_tick=4,
        document=prefix,
    )
    store.write_branch(
        ensemble_id=str(ensemble["ensemble_id"]),
        child_id="child-unit",
        attempt_id="attempt-1",
        kind="failure",
        document=_failure(ensemble, prefix),
    )
    with pytest.raises(PathDependenceArtifactError, match="branch_unsealed"):
        verify_path_dependence_branch(
            expected={
                "ensemble_id": ensemble["ensemble_id"],
                "parent_id": "pd-parent-unit",
                "parent_attempt": "attempt-1",
                "child_id": "child-unit",
                "child_attempt": "attempt-1",
                "fork_tick": 4,
            },
            store=store,
            repositories=_Reader(None),
        )
    with pytest.raises(PathDependenceArtifactError, match="branch_unsealed"):
        verify_path_dependence_branch(
            expected={
                "ensemble_id": ensemble["ensemble_id"],
                "parent_id": "pd-parent-unit",
                "parent_attempt": "attempt-1",
                "child_id": "replacement-child",
                "child_attempt": "attempt-1",
                "fork_tick": 4,
            },
            store=store,
            repositories=_Reader(None),
        )
