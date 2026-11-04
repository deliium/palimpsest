"""Opt-in research CLI producer for evidence-testimony publications."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from experiments.evidence_testimony_harvest import (
    build_completed_run_evidence_harvest,
)
from experiments.evidence_testimony_publication import (
    EvidenceTestimonyHarvestResult,
    build_evidence_testimony_harvest_result,
    evidence_testimony_publication_document,
    publish_evidence_testimony_snapshot,
)
from persistence.evidence_testimony_filesystem import (
    create_evidence_testimony_publisher,
)
from simulation.evidence_testimony_models import EvidenceTestimonyArtifactError

__all__ = [
    "EVIDENCE_ROOT_ENV",
    "EvidenceTestimonyProducerOptions",
    "producer_options_from_args",
    "publish_evidence_testimony_harvest",
    "write_evidence_testimony_receipt",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "research_runner.evidence_testimony_composition"
)

EVIDENCE_ROOT_ENV: Final[str] = "PALIMPSEST_EVIDENCE_ROOT"

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
class EvidenceTestimonyProducerOptions:
    root: Path | None
    max_publications: int = 16
    max_bytes: int = 8 * 1024 * 1024

    @property
    def enabled(self) -> bool:
        return self.root is not None


def _config_root(args: object) -> object:
    root = getattr(args, "evidence_root", None)
    if root is None:
        root = os.environ.get(EVIDENCE_ROOT_ENV)
    return root


def producer_options_from_args(args: object) -> EvidenceTestimonyProducerOptions:
    root = _config_root(args)
    max_publications = getattr(args, "evidence_max_publications", 16)
    max_bytes = getattr(args, "evidence_max_bytes", 8_388_608)
    if root is not None and not isinstance(root, (str, Path)):
        raise TypeError("evidence_root must be a path or None")
    if type(max_publications) is not int or not 1 <= max_publications <= 1024:
        raise ValueError("evidence publication cap is outside the supported range")
    if type(max_bytes) is not int or not 1 <= max_bytes <= 268_435_456:
        raise ValueError("evidence byte cap is outside the supported range")
    return EvidenceTestimonyProducerOptions(
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
    for name in ("input_revision", "config_fingerprint", "revision"):
        value = _text_value(getattr(runner_result, name, None))
        if value is not None:
            return value
    return "revision-unknown"


def _tick_value(value: int) -> int:
    if type(value) is not int or isinstance(value, bool) or value < 0:
        raise ValueError("generated_tick must be a non-negative integer")
    return value


def publish_evidence_testimony_harvest(
    runner_result: object,
    options: EvidenceTestimonyProducerOptions,
    *,
    run_id: str | None = None,
    input_revision: str | None = None,
    generated_tick: int | None = None,
    entity_to_agent: Mapping[str, str] | None = None,
    committed_events: Sequence[object] = (),
) -> dict[str, object]:
    """Publish one completed run; never change the scientific result."""

    if not options.enabled:
        return {"status": "disabled", "reason_code": "evidence_testimony_disabled"}
    stop_reason = getattr(runner_result, "stop_reason", None)
    stop_code = getattr(stop_reason, "value", stop_reason)
    if stop_code is None or stop_code in _INCOMPLETE_STOP_CODES:
        return {
            "status": "unavailable",
            "reason_code": "evidence_testimony_unavailable",
        }
    try:
        publisher = create_evidence_testimony_publisher(
            options.root,
            max_publications=options.max_publications,
            max_bytes=options.max_bytes,
        )
        if publisher is None:
            return {
                "status": "disabled",
                "reason_code": "evidence_testimony_disabled",
            }
        harvest = build_completed_run_evidence_harvest(
            runner_result,
            committed_events=committed_events,
            entity_to_agent=entity_to_agent,
        )
        built: EvidenceTestimonyHarvestResult = build_evidence_testimony_harvest_result(
            harvest
        )
        receipt = publish_evidence_testimony_snapshot(built, publisher)
        document = evidence_testimony_publication_document(built)
        document.update(receipt)
        return document
    except EvidenceTestimonyArtifactError as exc:
        _LOG.warning("evidence_testimony_publication_failed reason=%s", exc.code)
        return {"status": "failed", "reason_code": exc.code, "published": False}
    except (ValueError, OSError) as exc:
        _LOG.warning(
            "evidence_testimony_publication_failed reason=%s",
            type(exc).__name__,
        )
        return {
            "status": "failed",
            "reason_code": "evidence_testimony_publication_failed",
            "published": False,
        }


def _safe_run_id(run_id: str) -> str | None:
    if not run_id or "/" in run_id or "\\" in run_id or ".." in run_id:
        return None
    return run_id


def write_evidence_testimony_receipt(
    root: Path | str,
    run_id: str,
    document: Mapping[str, object],
) -> Path | None:
    """Write one metadata-only receipt atomically; failures are ignored."""

    token = _safe_run_id(run_id)
    if token is None:
        _LOG.warning("evidence_receipt_failed")
        return None
    path = Path(root) / f"evidence-publication-{token}.json"
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text(
            json.dumps(dict(document), sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
    except OSError:
        _LOG.warning("evidence_receipt_failed")
        try:
            temporary.unlink()
        except OSError:
            pass
        return None
    return path
