"""Opt-in research CLI producer for dispute-resolution publications."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from experiments.dispute_harvest import build_completed_run_dispute_harvest
from experiments.dispute_publication import (
    DisputeHarvestResult,
    build_dispute_harvest_result,
    dispute_publication_document,
    publish_dispute_snapshot,
)
from persistence.dispute_filesystem import create_dispute_publisher
from simulation.dispute_models import DisputeArtifactError

__all__ = [
    "DisputeProducerOptions",
    "producer_options_from_args",
    "publish_dispute_harvest",
    "write_dispute_receipt",
]

_LOG: Final[logging.Logger] = logging.getLogger("research_runner.dispute_composition")

_DISPUTE_ROOT_ENV: Final[str] = "PALIMPSEST_DISPUTE_ROOT"

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
class DisputeProducerOptions:
    root: Path | None
    max_publications: int = 16
    max_bytes: int = 8 * 1024 * 1024

    @property
    def enabled(self) -> bool:
        return self.root is not None


def _config_root(args: object) -> object:
    root = getattr(args, "dispute_root", None)
    if root is None:
        root = os.environ.get(_DISPUTE_ROOT_ENV)
    return root


def producer_options_from_args(args: object) -> DisputeProducerOptions:
    root = _config_root(args)
    max_publications = getattr(args, "dispute_max_publications", 16)
    max_bytes = getattr(args, "dispute_max_bytes", 8_388_608)
    if root is not None and not isinstance(root, (str, Path)):
        raise TypeError("dispute_root must be a path or None")
    if type(max_publications) is not int or not 1 <= max_publications <= 1024:
        raise ValueError("dispute publication cap is outside the supported range")
    if type(max_bytes) is not int or not 1 <= max_bytes <= 268_435_456:
        raise ValueError("dispute byte cap is outside the supported range")
    return DisputeProducerOptions(
        root=None if root is None else Path(root),
        max_publications=max_publications,
        max_bytes=max_bytes,
    )


def _text_value(value: object) -> str | None:
    token = getattr(value, "value", value)
    if isinstance(token, str) and token:
        return token
    return None


def _run_id(runner_result: object, explicit: str | None) -> str:
    if explicit is not None:
        return explicit
    value = _text_value(getattr(runner_result, "run_id", None))
    if value is None:
        raise ValueError("run_id is required")
    return value


def _input_revision(runner_result: object, explicit: str | None) -> str:
    if explicit is not None:
        return explicit
    for name in ("input_revision", "config_fingerprint"):
        value = _text_value(getattr(runner_result, name, None))
        if value is not None:
            return value
    return "revision-unknown"


def publish_dispute_harvest(
    runner_result: object,
    options: DisputeProducerOptions,
    *,
    run_id: str | None = None,
    input_revision: str | None = None,
    generated_tick: int | None = None,
    entity_to_agent: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """Publish one completed run; never change the scientific result."""
    if not options.enabled:
        return {"status": "disabled", "reason_code": "dispute_disabled"}
    stop_reason = getattr(runner_result, "stop_reason", None)
    stop_code = getattr(stop_reason, "value", stop_reason)
    if stop_code is None or stop_code in _INCOMPLETE_STOP_CODES:
        return {
            "status": "unavailable",
            "reason_code": "dispute_unavailable",
        }
    try:
        publisher = create_dispute_publisher(
            options.root,
            max_publications=options.max_publications,
            max_artifact_bytes=options.max_bytes,
        )
        if publisher is None:
            return {"status": "disabled", "reason_code": "dispute_disabled"}
        harvest = build_completed_run_dispute_harvest(
            runner_result,
            run_id=_run_id(runner_result, run_id),
            input_revision=_input_revision(runner_result, input_revision),
            generated_tick=(
                _tick_value(generated_tick)
                if generated_tick is not None
                else _int_value(getattr(runner_result, "ticks_committed", 0))
            ),
            entity_to_agent=entity_to_agent,
        )
        built: DisputeHarvestResult = build_dispute_harvest_result(harvest)
        publish_dispute_snapshot(built, publisher)
        return dispute_publication_document(built)
    except DisputeArtifactError as exc:
        _LOG.warning(
            "dispute_publication_failed run_id=%s reason=%s",
            run_id,
            exc.code,
        )
        return {"status": "failed", "reason_code": exc.code, "published": False}
    except (ValueError, OSError) as exc:
        _LOG.warning(
            "dispute_publication_failed run_id=%s reason=%s",
            run_id,
            type(exc).__name__,
        )
        return {
            "status": "failed",
            "reason_code": "dispute_publication_failed",
            "published": False,
        }


def _int_value(value: object) -> int:
    if type(value) is int and not isinstance(value, bool) and value >= 0:
        return value
    return 0


def _tick_value(value: int) -> int:
    if type(value) is not int or isinstance(value, bool) or value < 0:
        raise ValueError("generated_tick must be a non-negative integer")
    return value


def _safe_run_id(run_id: str) -> str | None:
    if not run_id or "/" in run_id or "\\" in run_id or ".." in run_id:
        return None
    return run_id


def write_dispute_receipt(
    root: Path | str,
    run_id: str,
    document: Mapping[str, object],
) -> Path | None:
    """Write one metadata-only receipt next to the research artifacts.

    A receipt-write failure is logged and ignored so it can never change the
    scientific result.
    """
    token = _safe_run_id(run_id)
    if token is None:
        _LOG.warning("dispute_receipt_failed run=%s", run_id)
        return None
    path = Path(root) / f"dispute-publication-{token}.json"
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text(
            json.dumps(dict(document), sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
    except OSError:
        _LOG.warning("dispute_receipt_failed run=%s", run_id)
        try:
            temporary.unlink()
        except OSError:
            pass
        return None
    return path
