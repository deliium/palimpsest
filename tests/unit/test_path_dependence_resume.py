"""Resume classification and prefix reconstruction policy."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest

from experiments.path_dependence_artifacts import (
    PathDependenceArtifactStore,
    build_branch_document,
    build_ensemble_document,
    build_outcomes_document,
    build_prefix_document,
)
from experiments.path_dependence_resume import (
    PathDependenceResumeError,
    ResumeDecision,
    classify_path_dependence_resume,
    reconstruct_prefix,
)
from experiments.path_dependence_scenario import historical_contingency_scenario

pytestmark = pytest.mark.unit

DIGEST_A = "a" * 64
DIGEST_B = "b" * 64
PARENT = "pd-parent-unit"
CHILD = "child-unit"
ATTEMPT = "attempt-1"


class _Reader:
    def __init__(self, run_ids: set[str], terminal: dict[str, object] | None) -> None:
        self._run_ids = run_ids
        self._terminal = terminal

    def exists(self, run_id: str) -> bool:
        return run_id in self._run_ids

    def terminal(self, run_id: str) -> dict[str, object] | None:
        return self._terminal


def _ensemble() -> dict[str, object]:
    return build_ensemble_document(
        historical_contingency_scenario(profile="smoke"),
        source_revision="resume-source",
        source_artifact_digest=DIGEST_A,
    )


def _prefix(ensemble: dict[str, object], *, eligible: bool = True) -> dict[str, object]:
    return build_prefix_document(
        ensemble_id=str(ensemble["ensemble_id"]),
        parent_scientific_id=PARENT,
        parent_attempt_id=ATTEMPT,
        fork_tick=4,
        boundary_revision=14,
        config_fingerprint=str(ensemble["config_fingerprint"]),
        source_revision="resume-source",
        provider_identity="deterministic_fake",
        complete_state_digest=DIGEST_B,
        checkpoint_format_version="runner-fork-checkpoint-v1",
        bootstrap_hash="c" * 64,
        snapshot_hash="d" * 64,
        objective_head_hash="e" * 64,
        common_setup_digest="f" * 64,
        eligible=eligible,
        eligibility_reason="eligible" if eligible else "prefix_ineligible",
    )


def _base_details() -> dict[str, object]:
    return {
        "kind": "preparation",
        "ensemble_id": "",
        "parent_scientific_id": PARENT,
        "parent_attempt_id": ATTEMPT,
        "fork_tick": 4,
        "child_scientific_id": CHILD,
        "child_attempt_id": ATTEMPT,
        "slot_ordinal": 0,
        "arm_id": "share",
        "action_schedule_digest": "1" * 64,
        "assignment_seed": 7,
        "assignment_policy": "permuted-treatment-blind-slots-v1",
        "prefix_digest": "",
    }


def _documents(
    ensemble: dict[str, object], prefix: dict[str, object]
) -> tuple[dict[str, object], dict[str, object], dict[str, object], dict[str, object]]:
    base = _base_details()
    base["ensemble_id"] = ensemble["ensemble_id"]
    base["prefix_digest"] = prefix["digest"]
    preparation = build_branch_document(
        kind="preparation",
        ensemble_id=str(ensemble["ensemble_id"]),
        parent_scientific_id=PARENT,
        parent_attempt_id=ATTEMPT,
        fork_tick=4,
        child_scientific_id=CHILD,
        child_attempt_id=ATTEMPT,
        slot_ordinal=0,
        arm_id="share",
        action_schedule_digest="1" * 64,
        assignment_seed=7,
        assignment_policy="permuted-treatment-blind-slots-v1",
        prefix_digest=str(prefix["digest"]),
        details={"expected_checkpoint_digest": DIGEST_B},
    )
    outcomes = build_outcomes_document(
        ensemble_id=str(ensemble["ensemble_id"]),
        child_scientific_id=CHILD,
        child_attempt_id=ATTEMPT,
        slot_ordinal=0,
        fork_tick=4,
        rows=(),
        coverage={"complete": True},
        evidence_refs=("boundary:4",),
    )
    result = build_branch_document(
        kind="result",
        ensemble_id=str(ensemble["ensemble_id"]),
        parent_scientific_id=PARENT,
        parent_attempt_id=ATTEMPT,
        fork_tick=4,
        child_scientific_id=CHILD,
        child_attempt_id=ATTEMPT,
        slot_ordinal=0,
        arm_id="share",
        action_schedule_digest="1" * 64,
        assignment_seed=7,
        assignment_policy="permuted-treatment-blind-slots-v1",
        prefix_digest=str(prefix["digest"]),
        details={
            "child_run_id": CHILD,
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
    completion = build_branch_document(
        kind="completion",
        ensemble_id=str(ensemble["ensemble_id"]),
        parent_scientific_id=PARENT,
        parent_attempt_id=ATTEMPT,
        fork_tick=4,
        child_scientific_id=CHILD,
        child_attempt_id=ATTEMPT,
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
    return preparation, result, outcomes, completion


def _store(
    tmp_path: Path, *, eligible: bool = True
) -> tuple[PathDependenceArtifactStore, dict[str, object], dict[str, object]]:
    store = PathDependenceArtifactStore(tmp_path)
    ensemble = _ensemble()
    prefix = _prefix(ensemble, eligible=eligible)
    store.write_ensemble(ensemble)
    store.write_prefix(
        ensemble_id=str(ensemble["ensemble_id"]),
        parent_id=PARENT,
        attempt_id=ATTEMPT,
        fork_tick=4,
        document=prefix,
    )
    return store, ensemble, prefix


def _expected(ensemble: dict[str, object]) -> dict[str, object]:
    return {
        "ensemble_id": ensemble["ensemble_id"],
        "spec_fingerprint": ensemble["spec_fingerprint"],
        "parent_id": PARENT,
        "parent_attempt": ATTEMPT,
        "child_id": CHILD,
        "child_attempt": ATTEMPT,
        "fork_tick": 4,
    }


def test_uncreated_slot_requires_preparation_then_reconstructs(
    tmp_path: Path,
) -> None:
    store, ensemble, prefix = _store(tmp_path)
    expected = _expected(ensemble)
    missing = classify_path_dependence_resume(
        expected=expected, store=store, repositories=_Reader(set(), None)
    )
    assert missing.decision is ResumeDecision.BLOCKED
    preparation, _result, _outcomes, _completion = _documents(ensemble, prefix)
    store.write_branch(
        ensemble_id=str(ensemble["ensemble_id"]),
        child_id=CHILD,
        attempt_id=ATTEMPT,
        kind="preparation",
        document=preparation,
    )
    decision = classify_path_dependence_resume(
        expected=expected, store=store, repositories=_Reader(set(), None)
    )
    assert decision.decision is ResumeDecision.RECONSTRUCT_FOR_UNCREATED_SLOT
    assert decision.reason_code is None


def test_existing_child_without_completion_is_failed_partial(tmp_path: Path) -> None:
    store, ensemble, prefix = _store(tmp_path)
    preparation, _result, _outcomes, _completion = _documents(ensemble, prefix)
    store.write_branch(
        ensemble_id=str(ensemble["ensemble_id"]),
        child_id=CHILD,
        attempt_id=ATTEMPT,
        kind="preparation",
        document=preparation,
    )
    decision = classify_path_dependence_resume(
        expected=_expected(ensemble),
        store=store,
        repositories=_Reader({CHILD}, None),
    )
    assert decision.decision is ResumeDecision.FAILED_PARTIAL
    assert decision.reason_code == "branch_unsealed"


def test_completed_branch_is_adopted_without_rerun(tmp_path: Path) -> None:
    store, ensemble, prefix = _store(tmp_path)
    preparation, result, outcomes, completion = _documents(ensemble, prefix)
    for kind, document in (
        ("preparation", preparation),
        ("result", result),
        ("completion", completion),
    ):
        store.write_branch(
            ensemble_id=str(ensemble["ensemble_id"]),
            child_id=CHILD,
            attempt_id=ATTEMPT,
            kind=kind,
            document=document,
        )
    store.write_outcomes(
        ensemble_id=str(ensemble["ensemble_id"]),
        child_id=CHILD,
        attempt_id=ATTEMPT,
        document=outcomes,
    )
    decision = classify_path_dependence_resume(
        expected=_expected(ensemble),
        store=store,
        repositories=_Reader(
            {CHILD},
            {"terminal_tick": 8, "terminal_revision": 18, "head_hash": "9" * 64},
        ),
    )
    assert decision.decision is ResumeDecision.ADOPT_COMPLETED
    assert decision.branch is not None
    assert decision.branch.outcomes["schema_version"] == "path-dependence-outcomes-v1"


def test_ineligible_prefix_and_reconstruction_mismatch(tmp_path: Path) -> None:
    store, ensemble, _prefix_doc = _store(tmp_path, eligible=False)
    decision = classify_path_dependence_resume(
        expected=_expected(ensemble),
        store=store,
        repositories=_Reader(set(), None),
    )
    assert decision.decision is ResumeDecision.INELIGIBLE_PREFIX

    good_store, good_ensemble, _ = _store(tmp_path / "good")
    expected = _expected(good_ensemble)

    class _Checkpoint:
        pass

    async def _reconstruct(_expected: Mapping[str, object]) -> object:
        return _Checkpoint()

    with pytest.raises(PathDependenceResumeError, match="prefix_reconstruction"):
        import asyncio

        asyncio.run(
            reconstruct_prefix(
                expected=expected,
                store=good_store,
                reconstruct=_reconstruct,
                digest_of=lambda _value: "0" * 64,
            )
        )
