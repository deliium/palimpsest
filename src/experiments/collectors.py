"""Versioned experiment collectors (metrics stubs for A–E families)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from experiments.coordinator import ExperimentArmResult

COLLECTOR_SCHEMA_VERSION: Final[str] = "experiment-collector-v1"


@dataclass(frozen=True, slots=True)
class CollectorMetricDocument:
    """Canonical metric envelope (no narrative payloads)."""

    schema_version: str
    family: str
    run_id: str
    condition_id: str
    fields: tuple[tuple[str, str | int | float], ...]


def collect_arm_summary(arm: ExperimentArmResult) -> CollectorMetricDocument:
    """Minimal post-run summary shared by all experiment families."""
    return CollectorMetricDocument(
        schema_version=COLLECTOR_SCHEMA_VERSION,
        family="summary",
        run_id=arm.assignment.run_id.value,
        condition_id=arm.assignment.condition_id,
        fields=(
            ("ticks_committed", arm.runner_result.ticks_committed),
            ("stop_reason", arm.runner_result.stop_reason.value),
            ("attempt_count", len(arm.runner_result.attempt_receipts)),
            ("config_fingerprint_prefix", arm.config_fingerprint[:12]),
        ),
    )
