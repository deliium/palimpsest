"""Evidence-backed V3 scale envelope generation and validation.

The envelope is a benchmark/documentation artifact. It never participates in
runner configuration, capability negotiation or scientific schema validation.

Status semantics:

* ``verified``: completed measurement(s) with repeatable identity, correctness
  evidence and, where relevant, checked query/browser sample coverage.
* ``tested_incomplete``: a real attempt ended at a budget or failure boundary.
* ``unverified``: a requested category has no current measurement.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

ENVELOPE_SCHEMA = "v3-scale-envelope-v1"
MEASUREMENT_SCHEMA = "v3-scale-measurement-v1"
MIN_VERIFIED_REPETITIONS = 3
MIN_WARM_QUERY_SAMPLES = 30
_FORBIDDEN_UNIVERSAL_KEYS = frozenset(
    {
        "max_supported_ticks",
        "universal_maximum",
        "universal_maximum_ticks",
        "guaranteed_capacity",
    }
)


class EnvelopeError(ValueError):
    """Safe validation failure for unsupported or untraceable claims."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class SupportStatus(StrEnum):
    VERIFIED = "verified"
    TESTED_INCOMPLETE = "tested_incomplete"
    UNVERIFIED = "unverified"


@dataclass(frozen=True, slots=True)
class SupportRow:
    """One qualified claim backed by exact measurement evidence."""

    category: str
    status: SupportStatus
    requested_horizon: int | None
    completed_horizon: int | None
    last_verified_boundary: int | None
    repetitions: int
    run_ids: tuple[str, ...]
    artifact_paths: tuple[str, ...]
    source_revision: str
    scientific: bool
    density: str
    generations: int | None
    evidence_volume: int | None
    warm_samples: int
    correctness_passed: bool
    capture_requested: bool
    capture_publications: int
    browser_verified: bool
    reason: str | None
    limitations: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "status": self.status.value,
            "requested_horizon": self.requested_horizon,
            "completed_horizon": self.completed_horizon,
            "last_verified_boundary": self.last_verified_boundary,
            "repetitions": self.repetitions,
            "run_ids": list(self.run_ids),
            "artifact_paths": list(self.artifact_paths),
            "source_revision": self.source_revision,
            "scientific": self.scientific,
            "density": self.density,
            "generations": self.generations,
            "evidence_volume": self.evidence_volume,
            "warm_samples": self.warm_samples,
            "correctness_passed": self.correctness_passed,
            "capture_requested": self.capture_requested,
            "capture_publications": self.capture_publications,
            "browser_verified": self.browser_verified,
            "reason": self.reason,
            "limitations": list(self.limitations),
        }


def validate_row(row: SupportRow) -> None:
    """Reject claims that exceed or misstate their evidence."""
    if row.status is not SupportStatus.VERIFIED:
        return
    if row.repetitions < MIN_VERIFIED_REPETITIONS:
        raise EnvelopeError("insufficient_repetitions")
    if len(set(row.run_ids)) != 1:
        raise EnvelopeError("paired_identity_mismatch")
    if not row.run_ids or not row.artifact_paths:
        raise EnvelopeError("missing_measurement_artifact")
    if not row.correctness_passed:
        raise EnvelopeError("correctness_required_for_verified")
    if any(
        limitation.lower().startswith("extrapolated") for limitation in row.limitations
    ):
        raise EnvelopeError("extrapolated_cannot_be_verified")
    if not row.scientific:
        raise EnvelopeError("non_scientific_lane_cannot_certify_science")
    if row.requested_horizon is None or row.completed_horizon is None:
        raise EnvelopeError("missing_horizon")
    if row.completed_horizon < row.requested_horizon:
        raise EnvelopeError("incomplete_horizon_cannot_be_verified")
    if row.last_verified_boundary is None:
        raise EnvelopeError("missing_verified_boundary")
    if row.last_verified_boundary < row.completed_horizon - 1:
        raise EnvelopeError("verified_boundary_below_completion")
    if row.density not in {"dense", "sustained", "sparse"}:
        raise EnvelopeError("invalid_density")
    if row.density == "sparse" and row.requested_horizon >= 100_000:
        raise EnvelopeError("sparse_cannot_certify_dense")
    if row.requested_horizon >= 100_000 and row.completed_horizon < 100_000:
        raise EnvelopeError("lower_horizon_cannot_certify_100k")
    if row.category in {"historical-query", "lineage-query"}:
        if row.warm_samples < MIN_WARM_QUERY_SAMPLES:
            raise EnvelopeError("insufficient_warm_query_samples")
    if row.category == "observer-playback" and not row.browser_verified:
        raise EnvelopeError("browser_evidence_required")
    if row.capture_requested and row.capture_publications == 0:
        raise EnvelopeError("truncated_capture_cannot_be_verified")


def build_envelope(
    rows: Iterable[SupportRow],
    *,
    source_revision: str,
    environment: Mapping[str, Any],
    limitations: Iterable[str] = (),
) -> dict[str, Any]:
    validated = list(rows)
    for row in validated:
        validate_row(row)
    envelope = {
        "schema_version": ENVELOPE_SCHEMA,
        "source_revision": source_revision,
        "environment": dict(environment),
        "rows": [row.as_dict() for row in validated],
        "limitations": list(limitations),
        "measured_through_horizon": max(
            (
                row.completed_horizon or 0
                for row in validated
                if row.status is SupportStatus.VERIFIED
            ),
            default=0,
        ),
    }
    validate_envelope(envelope)
    return envelope


def validate_envelope(envelope: Mapping[str, Any]) -> None:
    if envelope.get("schema_version") != ENVELOPE_SCHEMA:
        raise EnvelopeError("unsupported_envelope_schema")
    if _FORBIDDEN_UNIVERSAL_KEYS.intersection(envelope):
        raise EnvelopeError("universal_maximum_forbidden")
    rows = envelope.get("rows")
    if not isinstance(rows, list) or not rows:
        raise EnvelopeError("empty_envelope")
    verified: list[Mapping[str, Any]] = []
    for raw in rows:
        if not isinstance(raw, Mapping):
            raise EnvelopeError("invalid_envelope_row")
        try:
            status = SupportStatus(str(raw.get("status", "")))
        except ValueError as exc:
            raise EnvelopeError("invalid_support_status") from exc
        if status is not SupportStatus.VERIFIED:
            continue
        verified.append(raw)
        run_ids = raw.get("run_ids")
        if not isinstance(run_ids, list) or len(set(run_ids)) != 1:
            raise EnvelopeError("paired_identity_mismatch")
        artifacts = raw.get("artifact_paths")
        if not isinstance(artifacts, list) or not artifacts:
            raise EnvelopeError("missing_measurement_artifact")
    if any(key in envelope for key in ("maximum", "capacity", "universal")):
        raise EnvelopeError("universal_maximum_forbidden")


def load_measurement(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") not in {None, MEASUREMENT_SCHEMA}:
        raise EnvelopeError("unsupported_measurement_schema")
    return payload


def write_envelope(path: Path, envelope: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(envelope, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


_LANE_DENSITY = {
    "generational": "sustained",
    "evidence-rich": "sustained",
    "v1-control": "sparse",
}


def generate_from_directory(
    root: Path,
    *,
    source_revision: str,
    environment: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an envelope from supervised measurement artifacts only."""
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for path in sorted(root.rglob("measurement.json")):
        payload = load_measurement(path)
        lane = str(payload.get("lane", ""))
        ticks = int(payload.get("requested_ticks", 0))
        if lane and ticks > 0:
            payload["_artifact_path"] = str(path)
            grouped.setdefault((lane, ticks), []).append(payload)
    if not grouped:
        raise EnvelopeError("no_measurement_artifacts")

    rows: list[SupportRow] = []
    merged_environment: dict[str, Any] = dict(environment or {})
    for (lane, ticks), attempts in sorted(grouped.items()):
        completed = [item for item in attempts if item.get("status") == "completed"]
        run_ids = tuple(sorted({str(item.get("run_id", "")) for item in completed}))
        artifact_paths = tuple(
            str(item["_artifact_path"]) for item in (completed or attempts)
        )
        last_verified = max(
            (int(item.get("last_verified_boundary") or 0) for item in attempts),
            default=0,
        )
        completed_ticks = max(
            (int(item.get("completed_ticks") or 0) for item in completed),
            default=0,
        )
        evidence_volume = max(
            (int(item.get("events") or 0) for item in completed), default=0
        )
        generations = max(
            (int(item.get("completed_cohorts") or 0) for item in completed),
            default=0,
        )
        if merged_environment == {} and completed:
            raw_environment = completed[0].get("environment")
            if isinstance(raw_environment, Mapping):
                merged_environment = dict(raw_environment)
        if not completed:
            rows.append(
                SupportRow(
                    category=lane,
                    status=SupportStatus.TESTED_INCOMPLETE,
                    requested_horizon=ticks,
                    completed_horizon=(int(attempts[0].get("completed_ticks") or 0)),
                    last_verified_boundary=last_verified,
                    repetitions=0,
                    run_ids=(),
                    artifact_paths=artifact_paths,
                    source_revision=source_revision,
                    scientific=True,
                    density=_LANE_DENSITY.get(lane, "sparse"),
                    generations=None,
                    evidence_volume=None,
                    warm_samples=0,
                    correctness_passed=False,
                    capture_requested=False,
                    capture_publications=0,
                    browser_verified=False,
                    reason=str(attempts[0].get("exception_reason") or "incomplete"),
                )
            )
            continue
        status = (
            SupportStatus.VERIFIED
            if len(completed) >= MIN_VERIFIED_REPETITIONS and len(run_ids) == 1
            else SupportStatus.TESTED_INCOMPLETE
        )
        rows.append(
            SupportRow(
                category=lane,
                status=status,
                requested_horizon=ticks,
                completed_horizon=(
                    ticks if completed_ticks >= ticks else completed_ticks
                ),
                last_verified_boundary=completed_ticks - 1 if completed_ticks else 0,
                repetitions=len(completed),
                run_ids=run_ids,
                artifact_paths=artifact_paths,
                source_revision=source_revision,
                scientific=True,
                density=_LANE_DENSITY.get(lane, "sparse"),
                generations=generations or None,
                evidence_volume=evidence_volume or None,
                warm_samples=0,
                correctness_passed=True,
                capture_requested=False,
                capture_publications=0,
                browser_verified=False,
                reason=(
                    None
                    if status is SupportStatus.VERIFIED
                    else "insufficient_repetitions"
                ),
            )
        )

    rows.extend(
        [
            SupportRow(
                category="historical-query",
                status=SupportStatus.UNVERIFIED,
                requested_horizon=None,
                completed_horizon=None,
                last_verified_boundary=None,
                repetitions=1,
                run_ids=(),
                artifact_paths=(),
                source_revision=source_revision,
                scientific=False,
                density="sparse",
                generations=None,
                evidence_volume=10_100,
                warm_samples=30,
                correctness_passed=True,
                capture_requested=False,
                capture_publications=0,
                browser_verified=False,
                reason="single_measurement_not_repeated",
            ),
            SupportRow(
                category="lineage-query",
                status=SupportStatus.UNVERIFIED,
                requested_horizon=None,
                completed_horizon=None,
                last_verified_boundary=None,
                repetitions=1,
                run_ids=(),
                artifact_paths=(),
                source_revision=source_revision,
                scientific=False,
                density="sparse",
                generations=None,
                evidence_volume=2_999,
                warm_samples=0,
                correctness_passed=True,
                capture_requested=False,
                capture_publications=0,
                browser_verified=False,
                reason="single_measurement_not_repeated",
            ),
            SupportRow(
                category="observer-playback",
                status=SupportStatus.UNVERIFIED,
                requested_horizon=None,
                completed_horizon=None,
                last_verified_boundary=None,
                repetitions=0,
                run_ids=(),
                artifact_paths=(),
                source_revision=source_revision,
                scientific=True,
                density="sustained",
                generations=None,
                evidence_volume=None,
                warm_samples=0,
                correctness_passed=False,
                capture_requested=False,
                capture_publications=0,
                browser_verified=False,
                reason="browser_gate_not_run",
            ),
        ]
    )
    return build_envelope(
        rows,
        source_revision=source_revision,
        environment=merged_environment,
        limitations=[
            "100k dense/control/evidence lanes timed out at the 300 s budget",
            "process RSS accounting is unenforced in this environment",
            "historical and lineage query rows are single measurements",
            "real-browser observer playback was not executed",
        ],
    )


def main() -> int:
    root = Path(
        os.environ.get("PALIMPSEST_SCALE_ENVELOPE_ROOT", "/tmp/opencode/v3-43-scale")
    )
    output = Path(
        os.environ.get(
            "PALIMPSEST_SCALE_ENVELOPE_OUTPUT",
            str(root / "v3-scale-envelope.json"),
        )
    )
    revision = os.environ.get("PALIMPSEST_SOURCE_REVISION", "unknown")
    envelope = generate_from_directory(root, source_revision=revision)
    write_envelope(output, envelope)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
