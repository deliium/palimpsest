"""Resume classification and prefix reconstruction for path dependence."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, Protocol

from experiments.path_dependence_artifacts import (
    PathDependenceArtifactError,
    PathDependenceArtifactStore,
    VerifiedPathDependenceBranch,
    verify_path_dependence_branch,
)

_LOG: Final[logging.Logger] = logging.getLogger("experiments.path_dependence_resume")


class ResumeDecision(StrEnum):
    ADOPT_COMPLETED = "adopt_completed"
    RECONSTRUCT_FOR_UNCREATED_SLOT = "reconstruct_for_uncreated_slot"
    INELIGIBLE_PREFIX = "ineligible_prefix"
    FAILED_PARTIAL = "failed_partial"
    BLOCKED = "blocked"


class ResumeRepositoryReader(Protocol):
    def exists(self, run_id: str) -> bool: ...

    def terminal(self, run_id: str) -> Mapping[str, object] | None: ...


@dataclass(frozen=True, slots=True)
class ResumeClassification:
    decision: ResumeDecision
    ensemble_id: str
    child_scientific_id: str
    child_attempt_id: str
    fork_tick: int
    reason_code: str | None = None
    branch: VerifiedPathDependenceBranch | None = None


@dataclass(frozen=True, slots=True)
class PrefixReconstruction:
    checkpoint: object
    complete_state_digest: str
    reconstructed_from_prefix: str


class PathDependenceResumeError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _fallback_tick(value: object) -> int:
    if isinstance(value, bool) or type(value) is not int or value < 0:
        return 0
    return value


def _expected_fields(expected: Mapping[str, object]) -> tuple[str, str, str, int]:
    ensemble_id = expected.get("ensemble_id")
    child_id = expected.get("child_id")
    child_attempt = expected.get("child_attempt")
    fork_tick = expected.get("fork_tick")
    if (
        type(ensemble_id) is not str
        or not ensemble_id
        or type(child_id) is not str
        or not child_id
        or type(child_attempt) is not str
        or not child_attempt
        or isinstance(fork_tick, bool)
        or type(fork_tick) is not int
        or fork_tick < 0
    ):
        raise PathDependenceResumeError("prefix_unsealed")
    return ensemble_id, child_id, child_attempt, fork_tick


def classify_path_dependence_resume(
    *,
    expected: Mapping[str, object],
    store: PathDependenceArtifactStore,
    repositories: ResumeRepositoryReader,
) -> ResumeClassification:
    """Classify one planned slot from sealed files and objective presence."""
    try:
        ensemble_id, child_id, child_attempt, fork_tick = _expected_fields(expected)
        parent_id = expected.get("parent_id")
        parent_attempt = expected.get("parent_attempt")
        if (
            type(parent_id) is not str
            or not parent_id
            or type(parent_attempt) is not str
            or not parent_attempt
        ):
            raise PathDependenceResumeError("prefix_unsealed")
        ensemble = store.read_ensemble(ensemble_id)
        if ensemble.get("spec_fingerprint") != expected.get("spec_fingerprint"):
            raise PathDependenceResumeError("resume_spec_conflict")
        prefix = store.read_prefix(
            ensemble_id=ensemble_id,
            parent_id=parent_id,
            attempt_id=parent_attempt,
            fork_tick=fork_tick,
        )
    except PathDependenceArtifactError as exc:
        return ResumeClassification(
            decision=ResumeDecision.BLOCKED,
            ensemble_id=str(expected.get("ensemble_id", "unknown")),
            child_scientific_id=str(expected.get("child_id", "unknown")),
            child_attempt_id=str(expected.get("child_attempt", "unknown")),
            fork_tick=_fallback_tick(expected.get("fork_tick")),
            reason_code=exc.code,
        )
    except PathDependenceResumeError as exc:
        return ResumeClassification(
            decision=ResumeDecision.BLOCKED,
            ensemble_id=str(expected.get("ensemble_id", "unknown")),
            child_scientific_id=str(expected.get("child_id", "unknown")),
            child_attempt_id=str(expected.get("child_attempt", "unknown")),
            fork_tick=_fallback_tick(expected.get("fork_tick")),
            reason_code=exc.code,
        )
    if prefix.get("kind") != "eligible":
        return ResumeClassification(
            decision=ResumeDecision.INELIGIBLE_PREFIX,
            ensemble_id=ensemble_id,
            child_scientific_id=child_id,
            child_attempt_id=child_attempt,
            fork_tick=fork_tick,
            reason_code="prefix_ineligible",
        )
    if repositories.exists(child_id):
        try:
            branch = verify_path_dependence_branch(
                expected=expected, store=store, repositories=repositories
            )
        except PathDependenceArtifactError as exc:
            return ResumeClassification(
                decision=ResumeDecision.FAILED_PARTIAL,
                ensemble_id=ensemble_id,
                child_scientific_id=child_id,
                child_attempt_id=child_attempt,
                fork_tick=fork_tick,
                reason_code=exc.code,
            )
        _LOG.info(
            "path_dependence_resume_adopt ensemble_id=%s child_id=%s",
            ensemble_id,
            child_id,
        )
        return ResumeClassification(
            decision=ResumeDecision.ADOPT_COMPLETED,
            ensemble_id=ensemble_id,
            child_scientific_id=child_id,
            child_attempt_id=child_attempt,
            fork_tick=fork_tick,
            branch=branch,
        )
    try:
        preparation = store.read_branch(
            ensemble_id=ensemble_id,
            child_id=child_id,
            attempt_id=child_attempt,
            kind="preparation",
        )
    except PathDependenceArtifactError as exc:
        return ResumeClassification(
            decision=ResumeDecision.BLOCKED,
            ensemble_id=ensemble_id,
            child_scientific_id=child_id,
            child_attempt_id=child_attempt,
            fork_tick=fork_tick,
            reason_code=exc.code,
        )
    if preparation.get("prefix_digest") != prefix.get("digest"):
        return ResumeClassification(
            decision=ResumeDecision.BLOCKED,
            ensemble_id=ensemble_id,
            child_scientific_id=child_id,
            child_attempt_id=child_attempt,
            fork_tick=fork_tick,
            reason_code="prefix_unsealed",
        )
    _LOG.info(
        "path_dependence_resume_reconstruct ensemble_id=%s child_id=%s",
        ensemble_id,
        child_id,
    )
    return ResumeClassification(
        decision=ResumeDecision.RECONSTRUCT_FOR_UNCREATED_SLOT,
        ensemble_id=ensemble_id,
        child_scientific_id=child_id,
        child_attempt_id=child_attempt,
        fork_tick=fork_tick,
    )


async def reconstruct_prefix(
    *,
    expected: Mapping[str, object],
    store: PathDependenceArtifactStore,
    reconstruct: Callable[[Mapping[str, object]], Awaitable[object]],
    digest_of: Callable[[object], str],
) -> PrefixReconstruction:
    """Re-execute a sealed prefix and require an exact complete-state digest."""
    ensemble_id, child_id, child_attempt, fork_tick = _expected_fields(expected)
    parent_id = expected.get("parent_id")
    parent_attempt = expected.get("parent_attempt")
    if (
        type(parent_id) is not str
        or not parent_id
        or type(parent_attempt) is not str
        or not parent_attempt
    ):
        raise PathDependenceResumeError("prefix_unsealed")
    prefix = store.read_prefix(
        ensemble_id=ensemble_id,
        parent_id=parent_id,
        attempt_id=parent_attempt,
        fork_tick=fork_tick,
    )
    if prefix.get("kind") != "eligible":
        raise PathDependenceResumeError("prefix_unsealed")
    checkpoint = await reconstruct(expected)
    actual = digest_of(checkpoint)
    if actual != prefix.get("complete_state_digest"):
        _LOG.error(
            "path_dependence_prefix_reconstruction_mismatch ensemble_id=%s child_id=%s",
            ensemble_id,
            child_id,
        )
        raise PathDependenceResumeError("prefix_reconstruction_mismatch")
    del child_attempt
    return PrefixReconstruction(
        checkpoint=checkpoint,
        complete_state_digest=actual,
        reconstructed_from_prefix=str(prefix["digest"]),
    )


__all__ = [
    "PathDependenceResumeError",
    "PrefixReconstruction",
    "ResumeClassification",
    "ResumeDecision",
    "classify_path_dependence_resume",
    "reconstruct_prefix",
]
