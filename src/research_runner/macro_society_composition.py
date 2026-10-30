"""Opt-in macro-society publication composition for ``research_runner``.

Publication is a completed-run, opt-in sidecar. A storage failure changes only
the receipt, never the scientific result.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from experiments.macro_society_publication import (
    MacroSocietyHarvest,
    build_macro_society_harvest_result,
    macro_society_publication_document,
)
from persistence.macro_society_filesystem import create_macro_society_publisher
from simulation.macro_society_codec import encode_macro_society_snapshot
from simulation.macro_society_models import MacroSocietyArtifactError
from simulation.macro_society_ports import MacroSocietyPublication

__all__ = [
    "MacroSocietyProducerOptions",
    "producer_options_from_args",
    "publish_macro_society_harvest",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "research_runner.macro_society_composition"
)


@dataclass(frozen=True, slots=True)
class MacroSocietyProducerOptions:
    """Publication root and quotas; ``root=None`` disables publication."""

    root: Path | None
    max_publications: int = 16
    max_artifact_bytes: int = 8 * 1024 * 1024

    @property
    def enabled(self) -> bool:
        return self.root is not None


def producer_options_from_args(args: object) -> MacroSocietyProducerOptions:
    """Build options from parsed CLI arguments."""
    root = getattr(args, "macro_society_root", None)
    max_publications = getattr(args, "macro_society_max_publications", 16)
    max_artifact_bytes = getattr(args, "macro_society_max_bytes", 8 * 1024 * 1024)
    for name, value, cap in (
        ("max_publications", max_publications, 1024),
        ("max_artifact_bytes", max_artifact_bytes, 256 * 1024 * 1024),
    ):
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise ValueError(f"macro-society {name} must be a positive integer")
        if value > cap:
            raise ValueError(f"macro-society {name} is outside the supported range")
    return MacroSocietyProducerOptions(
        root=None if root is None else Path(root),
        max_publications=max_publications,
        max_artifact_bytes=max_artifact_bytes,
    )


def publish_macro_society_harvest(
    *,
    options: MacroSocietyProducerOptions,
    harvest: MacroSocietyHarvest | None,
) -> dict[str, object]:
    """Publish one completed-run harvest and return a safe receipt."""
    if not options.enabled:
        _LOG.info("macro_society_publish_skipped reason=disabled")
        return {
            "status": "disabled",
            "reason_code": "macro_society_publication_disabled",
        }
    if harvest is None:
        _LOG.warning("macro_society_publish_unavailable reason=harvest_unavailable")
        return {
            "status": "unavailable",
            "reason_code": "macro_society_harvest_unavailable",
        }
    try:
        result = build_macro_society_harvest_result(harvest)
        publisher = create_macro_society_publisher(
            options.root,
            max_publications=options.max_publications,
            max_artifact_bytes=options.max_artifact_bytes,
        )
        if publisher is None:
            return {
                "status": "disabled",
                "reason_code": "macro_society_publication_disabled",
            }
        payload = encode_macro_society_snapshot(result.snapshot)
        publisher.publish(
            MacroSocietyPublication(
                snapshot=result.snapshot,
                payload=payload,
                created_at_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            )
        )
        document = macro_society_publication_document(result)
        return {"status": "published", **document}
    except MacroSocietyArtifactError as exc:
        _LOG.error(
            "macro_society_publish_failed run=%s reason_code=%s",
            harvest.run_id,
            exc.reason_code,
        )
        return {"status": "failed", "reason_code": exc.reason_code}
    except (ValueError, OSError) as exc:
        reason = getattr(exc, "reason_code", "macro_society_publish_failed")
        _LOG.error(
            "macro_society_publish_failed run=%s reason_code=%s",
            harvest.run_id,
            reason,
        )
        return {"status": "failed", "reason_code": reason}
