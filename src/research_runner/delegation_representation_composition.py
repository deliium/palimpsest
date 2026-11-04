"""Opt-in research CLI producer for representation publications."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from experiments.delegation_representation_harvest import (
    build_completed_run_representation_harvest,
)
from experiments.delegation_representation_publication import (
    RepresentationHarvestResult,
    build_representation_harvest_result,
    publish_representation_snapshot,
    representations_publication_document,
)
from persistence.delegation_representation_filesystem import (
    create_delegation_representation_publisher,
)
from simulation.delegation_representation_models import (
    DelegationRepresentationArtifactError,
)

__all__ = [
    "REPRESENTATION_ROOT_ENV",
    "RepresentationProducerOptions",
    "producer_options_from_args",
    "publish_representation_harvest",
    "write_representation_receipt",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "research_runner.delegation_representation_composition"
)

REPRESENTATION_ROOT_ENV: Final[str] = "PALIMPSEST_REPRESENTATION_ROOT"
_INCOMPLETE_STOP_CODES: Final[frozenset[str]] = frozenset(
    {
        "cancelled",
        "cognition_failure",
        "authority_failure",
        "finalization_recovery_required",
        "experiment_criterion_failure",
        "historical_artifact_failure",
    }
)


@dataclass(frozen=True, slots=True)
class RepresentationProducerOptions:
    root: Path | None
    max_publications: int = 16
    max_bytes: int = 8 * 1024 * 1024

    @property
    def enabled(self) -> bool:
        return self.root is not None


def _config_root(args: object) -> object:
    root = getattr(args, "representation_root", None)
    if root is None:
        root = os.environ.get(REPRESENTATION_ROOT_ENV)
    return root


def producer_options_from_args(args: object) -> RepresentationProducerOptions:
    root = _config_root(args)
    max_publications = getattr(args, "representation_max_publications", 16)
    max_bytes = getattr(args, "representation_max_bytes", 8_388_608)
    if root is not None and not isinstance(root, (str, Path)):
        raise TypeError("representation_root must be a path or None")
    if type(max_publications) is not int or not 1 <= max_publications <= 1024:
        raise ValueError("representation publication cap is outside range")
    if type(max_bytes) is not int or not 1 <= max_bytes <= 268_435_456:
        raise ValueError("representation byte cap is outside range")
    return RepresentationProducerOptions(
        root=None if root is None else Path(root),
        max_publications=max_publications,
        max_bytes=max_bytes,
    )


def publish_representation_harvest(
    runner_result: object,
    options: RepresentationProducerOptions,
    *,
    committed_events: Sequence[object] = (),
    entity_to_agent: Mapping[str, str] | None = None,
    metric_provenance: Sequence[object] = (),
) -> dict[str, object]:
    """Publish one completed run; never change the scientific result."""

    if not options.enabled:
        return {"status": "disabled", "reason": "representation_disabled"}
    stop_reason = getattr(runner_result, "stop_reason", None)
    stop_code = getattr(stop_reason, "value", stop_reason)
    if stop_code is None or stop_code in _INCOMPLETE_STOP_CODES:
        return {
            "status": "unavailable",
            "reason": "representation_run_incomplete",
        }
    try:
        publisher = create_delegation_representation_publisher(
            options.root,
            max_publications=options.max_publications,
            max_bytes=options.max_bytes,
        )
        if publisher is None:
            return {"status": "disabled", "reason": "representation_disabled"}
        harvest = build_completed_run_representation_harvest(
            runner_result,
            committed_events=committed_events,
            entity_to_agent=entity_to_agent,
        )
        built: RepresentationHarvestResult = build_representation_harvest_result(
            harvest=harvest,
            stop_reason=stop_reason,
            metric_provenance=metric_provenance,
        )
        published = publish_representation_snapshot(built, publisher)
        document = representations_publication_document(published)
        document.update(dict(published.receipt))
        return document
    except DelegationRepresentationArtifactError as exc:
        _LOG.warning("representation_publication_failed reason=%s", exc.code)
        return {"status": "failed", "reason": exc.code, "published": False}
    except (ValueError, OSError) as exc:
        _LOG.warning("representation_publication_failed reason=%s", type(exc).__name__)
        return {
            "status": "failed",
            "reason": "representation_publication_failed",
            "published": False,
        }


def _safe_run_id(run_id: str) -> str | None:
    if not run_id or "/" in run_id or "\\" in run_id or ".." in run_id:
        return None
    return run_id


def write_representation_receipt(
    root: Path | str,
    run_id: str,
    document: Mapping[str, object],
) -> Path | None:
    """Write one metadata-only receipt atomically; failures are ignored."""

    token = _safe_run_id(run_id)
    if token is None:
        _LOG.warning("representation_receipt_failed")
        return None
    path = Path(root) / f"representation-publication-{token}.json"
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text(
            json.dumps(dict(document), sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
    except OSError:
        _LOG.warning("representation_receipt_failed")
        try:
            temporary.unlink()
        except OSError:
            pass
        return None
    return path
