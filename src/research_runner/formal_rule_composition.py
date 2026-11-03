"""Opt-in research CLI producer for formal-rule publications."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from experiments.formal_rule_harvest import (
    build_completed_run_formal_rule_harvest,
)
from experiments.formal_rule_publication import (
    FormalRuleHarvestResult,
    build_formal_rule_harvest_result,
    formal_rule_publication_document,
    publish_formal_rule_snapshot,
)
from persistence.formal_rule_filesystem import create_formal_rule_publisher
from simulation.formal_rule_models import FormalRuleArtifactError

__all__ = [
    "FormalRuleProducerOptions",
    "producer_options_from_args",
    "publish_formal_rule_harvest",
    "write_formal_rule_receipt",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "research_runner.formal_rule_composition"
)

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
class FormalRuleProducerOptions:
    root: Path | None
    max_publications: int = 16
    max_artifact_bytes: int = 8 * 1024 * 1024

    @property
    def enabled(self) -> bool:
        return self.root is not None


def producer_options_from_args(args: object) -> FormalRuleProducerOptions:
    root = getattr(args, "formal_rule_root", None)
    max_publications = getattr(args, "formal_rule_max_publications", 16)
    max_artifact_bytes = getattr(args, "formal_rule_max_bytes", 8_388_608)
    if root is not None and not isinstance(root, (str, Path)):
        raise TypeError("formal_rule_root must be a path or None")
    if type(max_publications) is not int or not 1 <= max_publications <= 1024:
        raise ValueError("formal rule publication cap is outside the supported range")
    if (
        type(max_artifact_bytes) is not int
        or not 1 <= max_artifact_bytes <= 268_435_456
    ):
        raise ValueError("formal rule byte cap is outside the supported range")
    return FormalRuleProducerOptions(
        root=None if root is None else Path(root),
        max_publications=max_publications,
        max_artifact_bytes=max_artifact_bytes,
    )


def publish_formal_rule_harvest(
    runner_result: object,
    *,
    run_id: str,
    input_revision: str,
    generated_tick: int,
    options: FormalRuleProducerOptions,
) -> dict[str, object]:
    """Publish one completed run; never change the scientific result."""
    if not options.enabled:
        return {"status": "disabled", "reason_code": "formal_rule_disabled"}
    stop_reason = getattr(runner_result, "stop_reason", None)
    stop_code = getattr(stop_reason, "value", stop_reason)
    if stop_code is None or stop_code in _INCOMPLETE_STOP_CODES:
        return {
            "status": "unavailable",
            "reason_code": "formal_rule_run_incomplete",
        }
    try:
        publisher = create_formal_rule_publisher(
            options.root,
            max_publications=options.max_publications,
            max_artifact_bytes=options.max_artifact_bytes,
        )
        if publisher is None:
            return {"status": "disabled", "reason_code": "formal_rule_disabled"}
        harvest = build_completed_run_formal_rule_harvest(
            runner_result,
            run_id=run_id,
            input_revision=input_revision,
            generated_tick=generated_tick,
        )
        built: FormalRuleHarvestResult = build_formal_rule_harvest_result(harvest)
        publish_formal_rule_snapshot(built, publisher)
        return formal_rule_publication_document(built)
    except FormalRuleArtifactError as exc:
        _LOG.warning(
            "formal_rule_publication_failed run_id=%s reason=%s", run_id, exc.code
        )
        return {"status": "failed", "reason_code": exc.code}
    except (ValueError, OSError) as exc:
        _LOG.warning(
            "formal_rule_publication_failed run_id=%s reason=%s",
            run_id,
            type(exc).__name__,
        )
        return {
            "status": "failed",
            "reason_code": "formal_rule_publication_failed",
        }


def write_formal_rule_receipt(
    artifact_root: str | Path,
    *,
    run_id: str,
    receipt: Mapping[str, object],
) -> Path | None:
    """Write one metadata-only receipt next to the research artifacts.

    A receipt-write failure is logged and ignored so it can never change the
    scientific result. Only the publication status, reason code, counts, and
    publication id are ever written.
    """
    path = Path(artifact_root) / f"formal-rule-publication-{run_id}.json"
    try:
        path.write_text(
            json.dumps(dict(receipt), sort_keys=True, separators=(",", ":"))
            + "\n",
            encoding="utf-8",
        )
    except OSError:
        _LOG.warning("formal_rule_receipt_write_failed run=%s", run_id)
        return None
    return path
