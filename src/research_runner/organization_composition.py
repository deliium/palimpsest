"""Opt-in completed-run organization publication for the research CLI."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from experiments.organization_harvest import build_completed_run_organization_harvest
from experiments.organization_publication import (
    build_organization_harvest_result,
    organization_publication_document,
    publish_organization_snapshot,
)
from persistence.organization_filesystem import create_organization_publisher
from simulation.organization_models import OrganizationArtifactError
from simulation.runner_models import RunnerStopReasonCode, runner_stop_is_failure

__all__ = [
    "OrganizationProducerOptions",
    "producer_options_from_args",
    "publish_organization_harvest",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "research_runner.organization_composition"
)

_MAX_PUBLICATIONS_LIMIT: Final[int] = 1024
_MAX_BYTES_LIMIT: Final[int] = 256 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class OrganizationProducerOptions:
    root: Path | None
    max_publications: int = 16
    max_artifact_bytes: int = 8 * 1024 * 1024

    def __post_init__(self) -> None:
        if type(self.max_publications) is not int or not (
            1 <= self.max_publications <= _MAX_PUBLICATIONS_LIMIT
        ):
            raise ValueError("organization_max_publications")
        if type(self.max_artifact_bytes) is not int or not (
            1 <= self.max_artifact_bytes <= _MAX_BYTES_LIMIT
        ):
            raise ValueError("organization_max_bytes")

    @property
    def enabled(self) -> bool:
        return self.root is not None


def producer_options_from_args(args: object) -> OrganizationProducerOptions:
    """Read the opt-in organization publication options from CLI args."""
    root = getattr(args, "organization_root", None)
    return OrganizationProducerOptions(
        root=None if root is None else Path(root),
        max_publications=getattr(args, "organization_max_publications", 16),
        max_artifact_bytes=getattr(args, "organization_max_bytes", 8_388_608),
    )


def publish_organization_harvest(
    runner_result: object,
    *,
    run_id: str,
    input_revision: str,
    generated_tick: int,
    options: OrganizationProducerOptions,
) -> dict[str, object]:
    """Publish after completion; a failure changes only this receipt."""
    if not options.enabled:
        return {"status": "disabled", "reason_code": "organization_disabled"}
    stop_reason = getattr(runner_result, "stop_reason", None)
    if not isinstance(stop_reason, RunnerStopReasonCode) or runner_stop_is_failure(
        stop_reason
    ):
        return {"status": "unavailable", "reason_code": "organization_run_incomplete"}
    try:
        harvest = build_completed_run_organization_harvest(
            runner_result,
            run_id=run_id,
            input_revision=input_revision,
            generated_tick=generated_tick,
        )
        built = build_organization_harvest_result(harvest)
        publisher = create_organization_publisher(
            options.root,
            max_publications=options.max_publications,
            max_artifact_bytes=options.max_artifact_bytes,
        )
        if publisher is None:
            return {"status": "disabled", "reason_code": "organization_disabled"}
        publish_organization_snapshot(built, publisher)
    except OrganizationArtifactError as exc:
        _LOG.warning(
            "organization_publication_failed run_id=%s reason=%s", run_id, exc.code
        )
        return {"status": "failed", "reason_code": exc.code}
    except (ValueError, OSError) as exc:
        _LOG.warning(
            "organization_publication_failed run_id=%s reason=%s",
            run_id,
            type(exc).__name__,
        )
        return {"status": "failed", "reason_code": "organization_publication_failed"}
    receipt = organization_publication_document(built)
    _LOG.info(
        "organization_publication_published run_id=%s publication_id=%s",
        run_id,
        built.publication_id,
    )
    return receipt
