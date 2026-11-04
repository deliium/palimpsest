"""Opt-in research CLI producer for diplomacy publications."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from experiments.diplomacy_harvest import build_completed_run_diplomacy_harvest
from experiments.diplomacy_publication import (
    build_diplomacy_harvest_result,
    publish_diplomacy_snapshot,
)
from persistence.diplomacy_filesystem import create_diplomacy_publisher
from simulation.diplomacy_models import DiplomacyArtifactError

__all__ = [
    "DIPLOMACY_ROOT_ENV",
    "DiplomacyProducerOptions",
    "producer_options_from_args",
    "publish_diplomacy_harvest",
    "write_diplomacy_receipt",
]

_LOG: Final[logging.Logger] = logging.getLogger("research_runner.diplomacy_composition")

DIPLOMACY_ROOT_ENV: Final[str] = "PALIMPSEST_DIPLOMACY_ROOT"
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
class DiplomacyProducerOptions:
    root: Path | None
    max_publications: int = 16
    max_bytes: int = 8 * 1024 * 1024

    @property
    def enabled(self) -> bool:
        return self.root is not None


def _config_root(args: object) -> object:
    root = getattr(args, "diplomacy_root", None)
    if root is None:
        root = os.environ.get(DIPLOMACY_ROOT_ENV)
    return root


def producer_options_from_args(args: object) -> DiplomacyProducerOptions:
    root = _config_root(args)
    max_publications = getattr(args, "diplomacy_max_publications", 16)
    max_bytes = getattr(args, "diplomacy_max_bytes", 8_388_608)
    if root is not None and not isinstance(root, (str, Path)):
        raise TypeError("diplomacy_root must be a path or None")
    if type(max_publications) is not int or not 1 <= max_publications <= 1024:
        raise ValueError("diplomacy publication cap is outside range")
    if type(max_bytes) is not int or not 1 <= max_bytes <= 268_435_456:
        raise ValueError("diplomacy byte cap is outside range")
    return DiplomacyProducerOptions(
        root=None if root is None else Path(root),
        max_publications=max_publications,
        max_bytes=max_bytes,
    )


def publish_diplomacy_harvest(
    runner_result: object,
    options: DiplomacyProducerOptions,
    *,
    committed_events: Sequence[object] = (),
    entity_to_agent: Mapping[str, str] | None = None,
    run_id: str | None = None,
    revision: str = "rev-1",
    window_end: int | None = None,
) -> dict[str, object]:
    """Publish one completed run; never change the scientific result."""

    if not options.enabled:
        return {"status": "disabled", "reason": "diplomacy_disabled"}
    stop_reason = getattr(runner_result, "stop_reason", None)
    stop_code = getattr(stop_reason, "value", stop_reason)
    if stop_code in _INCOMPLETE_STOP_CODES:
        return {"status": "unavailable", "reason": "diplomacy_run_incomplete"}
    resolved_run_id = run_id or getattr(
        getattr(runner_result, "run_id", None), "value", None
    )
    if type(resolved_run_id) is not str or not resolved_run_id:
        return {"status": "unavailable", "reason": "diplomacy_input_unavailable"}
    tick = getattr(runner_result, "ticks_committed", 0)
    resolved_window = (
        window_end
        if window_end is not None
        else (tick if type(tick) is int and tick >= 0 else 0)
    )
    try:
        assert options.root is not None
        publisher = create_diplomacy_publisher(
            options.root,
            max_publications=options.max_publications,
            max_bytes=options.max_bytes,
        )
        harvest = build_completed_run_diplomacy_harvest(
            runner_result,
            committed_events=committed_events,
            entity_to_agent=entity_to_agent,
        )
        built = build_diplomacy_harvest_result(
            harvest,
            run_id=resolved_run_id,
            revision=revision,
            window_end=resolved_window,
            stop_reason=stop_code,
        )
        published = publish_diplomacy_snapshot(built, publisher)
        document = dict(published.receipt)
        document["published"] = published.published
        return document
    except DiplomacyArtifactError as exc:
        _LOG.warning("diplomacy_publication_failed reason=%s", exc.code)
        return {"status": "failed", "reason": exc.code, "published": False}
    except (ValueError, OSError) as exc:
        _LOG.warning("diplomacy_publication_failed reason=%s", type(exc).__name__)
        return {
            "status": "failed",
            "reason": "diplomacy_publication_failed",
            "published": False,
        }


def _safe_run_id(run_id: str) -> str | None:
    if not run_id or "/" in run_id or "\\" in run_id or ".." in run_id:
        return None
    return run_id


def write_diplomacy_receipt(
    root: Path | str, run_id: str, document: Mapping[str, object]
) -> Path | None:
    """Write one metadata-only receipt atomically; failures are ignored."""

    token = _safe_run_id(run_id)
    if token is None:
        _LOG.warning("diplomacy_receipt_failed")
        return None
    path = Path(root) / f"diplomacy-publication-{token}.json"
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text(
            json.dumps(dict(document), sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
    except OSError:
        _LOG.warning("diplomacy_receipt_failed")
        try:
            temporary.unlink()
        except OSError:
            pass
        return None
    return path
