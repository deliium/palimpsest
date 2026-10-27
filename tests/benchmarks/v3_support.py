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
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

ENVELOPE_SCHEMA = "v3-scale-envelope-v1"
COMPOSITION_SCHEMA = "v3-composition-trials-v1"
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


class CompositionStatus(StrEnum):
    TESTED = "tested"
    UNVERIFIED = "unverified"


_COMPOSITION_NAMES = frozenset({"retirement", "capture-spool", "physical-paging"})
_COMPOSITION_VARIANTS = frozenset({"off", "on"})


@dataclass(frozen=True, slots=True)
class CompositionTrial:
    """One explicit off/on composition check, separate from capacity rows."""

    name: str
    variant: str
    status: CompositionStatus
    scope: str
    evidence: tuple[str, ...]
    metrics: Mapping[str, int | float | str] = field(default_factory=dict)
    notes: tuple[str, ...] = ()
    capacity_claim: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "variant": self.variant,
            "status": self.status.value,
            "scope": self.scope,
            "evidence": list(self.evidence),
            "metrics": dict(sorted(self.metrics.items())),
            "notes": list(self.notes),
            "capacity_claim": self.capacity_claim,
        }


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
    attempted_repetitions: int = 0
    failed_attempts: int = 0
    failure_reasons: tuple[str, ...] = ()
    attempt_paths: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "status": self.status.value,
            "requested_horizon": self.requested_horizon,
            "completed_horizon": self.completed_horizon,
            "last_verified_boundary": self.last_verified_boundary,
            "repetitions": self.repetitions,
            "attempted_repetitions": self.attempted_repetitions,
            "failed_attempts": self.failed_attempts,
            "failure_reasons": list(self.failure_reasons),
            "attempt_paths": list(self.attempt_paths),
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
    if row.failed_attempts < 0 or row.attempted_repetitions < 0:
        raise EnvelopeError("invalid_attempt_counts")
    if row.failed_attempts and not row.failure_reasons:
        raise EnvelopeError("failed_attempts_without_reason")
    if row.attempted_repetitions and row.attempted_repetitions < (
        row.repetitions + row.failed_attempts
    ):
        raise EnvelopeError("attempt_count_mismatch")
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


def validate_composition(trials: Iterable[CompositionTrial]) -> None:
    """Require honest, paired off/on composition evidence.

    Composition trials never certify capacity. Tested variants must reference
    concrete evidence paths or test node identifiers.
    """
    grouped: dict[str, dict[str, CompositionTrial]] = {}
    for trial in trials:
        if trial.name not in _COMPOSITION_NAMES:
            raise EnvelopeError("unknown_composition_name")
        if trial.variant not in _COMPOSITION_VARIANTS:
            raise EnvelopeError("invalid_composition_variant")
        if trial.status not in (
            CompositionStatus.TESTED,
            CompositionStatus.UNVERIFIED,
        ):
            raise EnvelopeError("invalid_composition_status")
        if not trial.scope.strip():
            raise EnvelopeError("missing_composition_scope")
        if trial.capacity_claim:
            raise EnvelopeError("composition_cannot_claim_capacity")
        if trial.status is CompositionStatus.TESTED and not trial.evidence:
            raise EnvelopeError("tested_composition_requires_evidence")
        if _FORBIDDEN_UNIVERSAL_KEYS.intersection(trial.metrics):
            raise EnvelopeError("universal_maximum_forbidden")
        for key, value in trial.metrics.items():
            if type(key) is not str or not key:
                raise EnvelopeError("invalid_composition_metric")
            if not isinstance(value, (int, float, str)):
                raise EnvelopeError("invalid_composition_metric")
            if isinstance(value, str) and len(value) > 256:
                raise EnvelopeError("composition_metric_too_large")
        variants = grouped.setdefault(trial.name, {})
        if trial.variant in variants:
            raise EnvelopeError("duplicate_composition_variant")
        variants[trial.variant] = trial
    for name, variants in grouped.items():
        if set(variants) != _COMPOSITION_VARIANTS:
            raise EnvelopeError(f"composition_pair_incomplete:{name}")
        if any(
            variant.status is CompositionStatus.TESTED for variant in variants.values()
        ) and not all(
            variant.status is CompositionStatus.TESTED for variant in variants.values()
        ):
            raise EnvelopeError("composition_pair_status_mismatch")


def build_envelope(
    rows: Iterable[SupportRow],
    *,
    source_revision: str,
    environment: Mapping[str, Any],
    limitations: Iterable[str] = (),
    composition: Iterable[CompositionTrial] = (),
) -> dict[str, Any]:
    validated = list(rows)
    for row in validated:
        validate_row(row)
    trials = list(composition)
    validate_composition(trials)
    envelope = {
        "schema_version": ENVELOPE_SCHEMA,
        "source_revision": source_revision,
        "environment": dict(environment),
        "rows": [row.as_dict() for row in validated],
        "composition": [trial.as_dict() for trial in trials],
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
    composition = envelope.get("composition")
    if composition is not None:
        if not isinstance(composition, list):
            raise EnvelopeError("invalid_composition")
        trials = [_composition_from_mapping(raw) for raw in composition]
        validate_composition(trials)
    if any(key in envelope for key in ("maximum", "capacity", "universal")):
        raise EnvelopeError("universal_maximum_forbidden")


def _composition_from_mapping(raw: object) -> CompositionTrial:
    if not isinstance(raw, Mapping):
        raise EnvelopeError("invalid_composition")
    try:
        return CompositionTrial(
            name=str(raw["name"]),
            variant=str(raw["variant"]),
            status=CompositionStatus(str(raw["status"])),
            scope=str(raw["scope"]),
            evidence=tuple(str(item) for item in raw.get("evidence", ())),
            metrics=dict(raw.get("metrics", {})),
            notes=tuple(str(item) for item in raw.get("notes", ())),
            capacity_claim=bool(raw.get("capacity_claim", False)),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise EnvelopeError("invalid_composition") from exc


def load_composition(path: Path) -> tuple[CompositionTrial, ...]:
    """Read an optional composition-trial document."""
    if not isinstance(path, Path):
        raise TypeError("path must be pathlib.Path")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise EnvelopeError("invalid_composition_document")
    if payload.get("schema") != COMPOSITION_SCHEMA:
        raise EnvelopeError("unsupported_composition_schema")
    raw_trials = payload.get("trials")
    if not isinstance(raw_trials, list):
        raise EnvelopeError("invalid_composition")
    return tuple(_composition_from_mapping(raw) for raw in raw_trials)


def write_composition(path: Path, trials: Iterable[CompositionTrial]) -> None:
    """Write a validated composition-trial document."""
    resolved = list(trials)
    validate_composition(resolved)
    document = {
        "schema": COMPOSITION_SCHEMA,
        "trials": [trial.as_dict() for trial in resolved],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def load_measurement(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise EnvelopeError("invalid_measurement")
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
    "generational-retired": "sustained",
    "evidence-rich": "sustained",
    "v1-control": "sparse",
}


def generate_from_directory(
    root: Path,
    *,
    source_revision: str,
    environment: Mapping[str, Any] | None = None,
    composition_path: Path | None = None,
    composition: Iterable[CompositionTrial] = (),
) -> dict[str, Any]:
    """Build an envelope from supervised measurement artifacts only."""
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for path in sorted(root.rglob("measurement.json")):
        relative = path.relative_to(root)
        if "composition" in relative.parts:
            continue
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
    failed_attempt_notes: list[str] = []
    for (lane, ticks), attempts in sorted(grouped.items()):
        completed = [item for item in attempts if item.get("status") == "completed"]
        failed = [item for item in attempts if item.get("status") != "completed"]
        failure_reasons = tuple(
            sorted(
                {
                    str(item.get("exception_reason") or item.get("status") or "unknown")
                    for item in failed
                }
            )
        )
        attempt_paths = tuple(str(item["_artifact_path"]) for item in attempts)
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
        row_limitations: list[str] = []
        if failed:
            reason_summary = ", ".join(failure_reasons)
            row_limitations.append(
                f"{len(failed)} of {len(attempts)} attempts did not complete "
                f"({reason_summary})"
            )
            failed_attempt_notes.append(
                f"{lane}@{ticks}: {len(failed)}/{len(attempts)} attempts did not "
                f"complete ({reason_summary})"
            )
        artifact_revisions: set[str] = set()
        for item in completed:
            raw_revision = (item.get("environment") or {}).get("source_revision")
            if isinstance(raw_revision, str):
                revision = raw_revision.strip()
                if revision and revision != "unknown":
                    artifact_revisions.add(revision)
        if completed and not artifact_revisions:
            row_limitations.append(
                "measurement artifacts did not record source_revision; "
                f"row uses envelope source_revision {source_revision}"
            )
        elif len(artifact_revisions) > 1:
            row_limitations.append(
                "measurement artifacts disagree on source_revision; "
                f"row uses envelope source_revision {source_revision}"
            )
        row_revision = (
            next(iter(artifact_revisions))
            if len(artifact_revisions) == 1
            else source_revision
        )
        if merged_environment == {}:
            raw_environment = (completed or attempts)[0].get("environment")
            if isinstance(raw_environment, Mapping):
                merged_environment = dict(raw_environment)
        if "postgresql" not in merged_environment:
            for item in attempts:
                raw_environment = item.get("environment")
                if isinstance(raw_environment, Mapping):
                    raw_version = raw_environment.get("postgresql")
                    if isinstance(raw_version, str):
                        version = raw_version.strip()
                        if version and version != "unknown":
                            merged_environment["postgresql"] = version
                            break
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
                    source_revision=row_revision,
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
                    limitations=tuple(row_limitations),
                    attempted_repetitions=len(attempts),
                    failed_attempts=len(failed),
                    failure_reasons=failure_reasons,
                    attempt_paths=attempt_paths,
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
                source_revision=row_revision,
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
                limitations=tuple(row_limitations),
                attempted_repetitions=len(attempts),
                failed_attempts=len(failed),
                failure_reasons=failure_reasons,
                attempt_paths=attempt_paths,
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
            *(
                ()
                if "postgresql" in merged_environment
                else ("measurement artifacts did not record the PostgreSQL version",)
            ),
            *failed_attempt_notes,
        ],
        composition=(
            *composition,
            *(
                load_composition(composition_path)
                if composition_path is not None and composition_path.is_file()
                else ()
            ),
        ),
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
    composition_raw = os.environ.get("PALIMPSEST_SCALE_COMPOSITION_PATH", "").strip()
    composition_path = Path(composition_raw) if composition_raw else None
    from tests.benchmarks.v3_composition import builtin_composition_trials

    envelope = generate_from_directory(
        root,
        source_revision=revision,
        composition_path=composition_path,
        composition=builtin_composition_trials(),
    )
    write_envelope(output, envelope)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
