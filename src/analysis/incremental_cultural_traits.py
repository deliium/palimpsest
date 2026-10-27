"""Exact sealed-window reducer and disposable view checkpoint for trait dynamics.

The reducer is intentionally narrow: only ``cultural_trait_dynamics@1`` gains an
incremental path. Every other cultural family keeps its existing exact batch
calculator. The checkpoint is a rebuildable ``v3-analytical-view-v1`` sidecar
bound to the source, window, algorithm, library identity and pass; it is never
scientific history, cognition input or a stop selector.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from analysis.cultural_evolution_evidence import (
    CULTURAL_EVOLUTION_POLICY_VERSION,
    CulturalAnalysisWindow,
    CulturalEvolutionInputs,
    CulturalMeasurement,
    InventoryBoundary,
)
from analysis.cultural_trait_dynamics import (
    ALL_CULTURAL_DIMENSIONS,
    CULTURAL_TRAIT_DYNAMICS_ALGORITHM_VERSION,
    CULTURAL_TRAIT_DYNAMICS_FAMILY,
    BoundaryTraitState,
    TraitEvidenceIndex,
    compute_cultural_trait_dynamics_from_states,
)
from analysis.numerical import library_versions

_LOG: Final[logging.Logger] = logging.getLogger("analysis.incremental_cultural_traits")

ANALYTICAL_VIEW_SCHEMA_VERSION: Final[str] = "v3-analytical-view-v1"
MAX_CHECKPOINT_BYTES: Final[int] = 64 * 1024 * 1024
MAX_CHECKPOINT_DEPTH: Final[int] = 32
_FIRST_PASS: Final[str] = "first_pass"
_FINAL_ROWS: Final[str] = "final_rows"

__all__ = [
    "ANALYTICAL_VIEW_SCHEMA_VERSION",
    "AnalyticalViewIdentity",
    "AnalyticalViewMismatch",
    "TraitDynamicsAccumulator",
    "TraitDynamicsCheckpoint",
    "compute_cultural_trait_dynamics_incremental",
    "read_checkpoint",
    "resume_checkpoint",
    "write_checkpoint",
]


class AnalyticalViewMismatch(ValueError):
    """A derived checkpoint does not match the exact requested identity."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _digest(value: object) -> str:
    body = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def _require_digest(name: str, value: object) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise AnalyticalViewMismatch(f"invalid_{name}")
    return value


def _states_payload(states: tuple[BoundaryTraitState, ...]) -> list[object]:
    payload: list[object] = []
    for state in states:
        payload.append(
            {
                "boundary_tick": state.boundary_tick,
                "living_owner_ids": list(state.living_owner_ids),
                "owner_dimension_coverage": [
                    list(row) for row in state.owner_dimension_coverage
                ],
                "carriers": [
                    [
                        dimension,
                        [
                            [trait, list(owners)]
                            for trait, owners in state.carriers.get(
                                dimension, {}
                            ).items()
                        ],
                    ]
                    for dimension in ALL_CULTURAL_DIMENSIONS
                ],
                "evidence": [
                    [dimension, trait, list(ids)]
                    for (dimension, trait), ids in sorted(state.evidence.items())
                ],
            }
        )
    return payload


def _state_from_payload(value: object) -> BoundaryTraitState:
    if not isinstance(value, Mapping):
        raise AnalyticalViewMismatch("invalid_checkpoint_state")
    expected = {
        "boundary_tick",
        "living_owner_ids",
        "owner_dimension_coverage",
        "carriers",
        "evidence",
    }
    if set(value) != expected:
        raise AnalyticalViewMismatch("invalid_checkpoint_state")
    tick = value["boundary_tick"]
    if type(tick) is not int or tick < 0:
        raise AnalyticalViewMismatch("invalid_checkpoint_state")
    living = value["living_owner_ids"]
    coverage = value["owner_dimension_coverage"]
    carriers_raw = value["carriers"]
    evidence_raw = value["evidence"]
    if not all(
        isinstance(item, (list, tuple))
        for item in (living, coverage, carriers_raw, evidence_raw)
    ):
        raise AnalyticalViewMismatch("invalid_checkpoint_state")
    carriers: dict[str, Mapping[str, tuple[str, ...]]] = {}
    for dimension, rows in carriers_raw:
        if not isinstance(rows, (list, tuple)):
            raise AnalyticalViewMismatch("invalid_checkpoint_state")
        carriers[dimension] = {
            str(trait): tuple(str(owner) for owner in owners)
            for trait, owners in rows
            if isinstance(owners, (list, tuple))
        }
    evidence: dict[tuple[str, str], tuple[str, ...]] = {}
    for dimension, trait, ids in evidence_raw:
        evidence[(str(dimension), str(trait))] = tuple(str(item) for item in ids)
    return BoundaryTraitState(
        boundary_tick=tick,
        living_owner_ids=tuple(str(owner) for owner in living),
        owner_dimension_coverage=tuple(
            (str(owner), str(dimension), str(code))
            for owner, dimension, code in coverage
        ),
        carriers=carriers,
        evidence=evidence,
    )


@dataclass(frozen=True, slots=True)
class AnalyticalViewIdentity:
    """Exact rebuild/resume identity for a disposable analytical view."""

    schema_version: str
    run_id: str
    source_revision: str
    config_fingerprint: str
    manifest_identity: str
    input_high_water: int
    window_baseline: int
    window_end: int | None
    metric_family: str
    algorithm_version: str
    library_versions_digest: str
    stage: str
    source_prefix_digest: str
    sealed_source_digest: str | None
    coverage_observed: int
    coverage_expected: int
    gaps: tuple[str, ...]
    gaps_digest: str

    def __post_init__(self) -> None:
        if self.schema_version != ANALYTICAL_VIEW_SCHEMA_VERSION:
            raise AnalyticalViewMismatch("unsupported_view_schema")
        for name in (
            "run_id",
            "source_revision",
            "config_fingerprint",
            "manifest_identity",
            "metric_family",
            "algorithm_version",
        ):
            value = getattr(self, name)
            if type(value) is not str or not value:
                raise AnalyticalViewMismatch(f"invalid_{name}")
        if self.stage not in {_FIRST_PASS, _FINAL_ROWS}:
            raise AnalyticalViewMismatch("invalid_stage")
        for name in ("input_high_water", "window_baseline"):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise AnalyticalViewMismatch(f"invalid_{name}")
        if self.window_end is not None and (
            type(self.window_end) is not int or self.window_end < self.window_baseline
        ):
            raise AnalyticalViewMismatch("invalid_window_end")
        for name in ("coverage_observed", "coverage_expected"):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise AnalyticalViewMismatch(f"invalid_{name}")
        _require_digest("source_prefix_digest", self.source_prefix_digest)
        _require_digest("library_versions_digest", self.library_versions_digest)
        _require_digest("gaps_digest", self.gaps_digest)
        if type(self.gaps) is not tuple:
            raise AnalyticalViewMismatch("invalid_gaps")
        if self.stage == _FINAL_ROWS:
            _require_digest("sealed_source_digest", self.sealed_source_digest)
        elif self.sealed_source_digest is not None:
            _require_digest("sealed_source_digest", self.sealed_source_digest)

    def payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "source_revision": self.source_revision,
            "config_fingerprint": self.config_fingerprint,
            "manifest_identity": self.manifest_identity,
            "input_high_water": self.input_high_water,
            "window_baseline": self.window_baseline,
            "window_end": self.window_end,
            "metric_family": self.metric_family,
            "algorithm_version": self.algorithm_version,
            "library_versions_digest": self.library_versions_digest,
            "stage": self.stage,
            "source_prefix_digest": self.source_prefix_digest,
            "sealed_source_digest": self.sealed_source_digest,
            "coverage_observed": self.coverage_observed,
            "coverage_expected": self.coverage_expected,
            "gaps": list(self.gaps),
            "gaps_digest": self.gaps_digest,
        }


@dataclass(frozen=True, slots=True)
class TraitDynamicsCheckpoint:
    """Disposable first-pass/final-row sidecar with an exact identity."""

    identity: AnalyticalViewIdentity
    states: tuple[BoundaryTraitState, ...]
    evidence: TraitEvidenceIndex
    measurements: tuple[CulturalMeasurement, ...]
    digest: str

    def __post_init__(self) -> None:
        if type(self.identity) is not AnalyticalViewIdentity:
            raise AnalyticalViewMismatch("invalid_identity")
        if type(self.states) is not tuple or any(
            type(state) is not BoundaryTraitState for state in self.states
        ):
            raise AnalyticalViewMismatch("invalid_states")
        if type(self.measurements) is not tuple:
            raise AnalyticalViewMismatch("invalid_measurements")
        if type(self.evidence) is not TraitEvidenceIndex:
            raise AnalyticalViewMismatch("invalid_evidence")
        _require_digest("digest", self.digest)
        if self.identity.stage == _FIRST_PASS and self.measurements:
            raise AnalyticalViewMismatch("first_pass_has_final_rows")

    def output_digest(self) -> str:
        return _measurement_digest(self.measurements)


def _measurement_digest(measurements: tuple[CulturalMeasurement, ...]) -> str:
    return _digest([row.to_payload() for row in measurements])


class TraitDynamicsAccumulator:
    """Ordered, idempotent first pass; final rows require a sealed window."""

    __slots__ = (
        "_evidence",
        "_gaps",
        "_run_id",
        "_sealed",
        "_source_revision",
        "_states",
        "_window",
    )

    def __init__(
        self,
        *,
        run_id: str,
        source_revision: str,
        window: CulturalAnalysisWindow,
        gaps: tuple[str, ...] = (),
        evidence: TraitEvidenceIndex,
    ) -> None:
        if type(window) is not CulturalAnalysisWindow:
            raise TypeError("window must be CulturalAnalysisWindow")
        if type(evidence) is not TraitEvidenceIndex:
            raise TypeError("evidence must be TraitEvidenceIndex")
        self._run_id = run_id
        self._source_revision = source_revision
        self._window = window
        self._gaps = tuple(sorted(set(gaps)))
        self._evidence = evidence
        self._states: list[BoundaryTraitState] = []
        self._sealed = False

    @classmethod
    def from_inputs(cls, inputs: CulturalEvolutionInputs) -> TraitDynamicsAccumulator:
        if type(inputs) is not CulturalEvolutionInputs:
            raise TypeError("inputs must be CulturalEvolutionInputs")
        return cls(
            run_id=inputs.run_id,
            source_revision=inputs.source_revision,
            window=inputs.window,
            gaps=inputs.gaps,
            evidence=TraitEvidenceIndex.from_inputs(inputs),
        )

    @property
    def sealed(self) -> bool:
        return self._sealed

    @property
    def states(self) -> tuple[BoundaryTraitState, ...]:
        return tuple(self._states)

    @property
    def high_water(self) -> int:
        return max((state.boundary_tick for state in self._states), default=0)

    def apply(self, boundary: InventoryBoundary) -> None:
        if self._sealed:
            raise AnalyticalViewMismatch("view_already_sealed")
        state = BoundaryTraitState.from_boundary(boundary, self._evidence)
        if self._states:
            previous = self._states[-1]
            if state.boundary_tick == previous.boundary_tick:
                if state != previous:
                    raise AnalyticalViewMismatch("boundary_conflict")
                return
            if state.boundary_tick < previous.boundary_tick:
                raise AnalyticalViewMismatch("boundary_nonadvancing")
        self._states.append(state)

    def seal(self) -> None:
        self._sealed = True

    def restore(
        self,
        states: tuple[BoundaryTraitState, ...],
        *,
        sealed: bool,
    ) -> None:
        """Restore verified checkpoint state without re-reading evidence."""
        if type(states) is not tuple or any(
            type(state) is not BoundaryTraitState for state in states
        ):
            raise AnalyticalViewMismatch("invalid_states")
        ordered = tuple(sorted(states, key=lambda state: state.boundary_tick))
        if len({state.boundary_tick for state in ordered}) != len(ordered):
            raise AnalyticalViewMismatch("duplicate_boundary_tick")
        self._states = list(ordered)
        self._sealed = bool(sealed)

    def measurements(self) -> tuple[CulturalMeasurement, ...]:
        if not self._sealed:
            raise AnalyticalViewMismatch("view_not_sealed")
        return compute_cultural_trait_dynamics_from_states(
            tuple(self._states),
            window=self._window,
            gaps=self._gaps,
        )

    def coverage(self) -> tuple[int, int]:
        observed = 0
        expected = 0
        for state in self._states:
            for dimension in ALL_CULTURAL_DIMENSIONS:
                state_observed, state_expected, _ = state.dimension_population(
                    dimension
                )
                observed += state_observed
                expected += state_expected
        return observed, expected

    def prefix_digest(self) -> str:
        return _digest(_states_payload(tuple(self._states)))

    def sealed_source_digest(self) -> str | None:
        if not self._sealed:
            return None
        return _digest(
            {
                "run_id": self._run_id,
                "source_revision": self._source_revision,
                "window": {
                    "baseline_boundary": self._window.baseline_boundary,
                    "end_boundary": self._window.end_boundary,
                },
                "gaps": list(self._gaps),
                "states_digest": self.prefix_digest(),
            }
        )

    def identity(
        self,
        *,
        config_fingerprint: str,
        manifest_identity: str,
    ) -> AnalyticalViewIdentity:
        observed, expected = self.coverage()
        return AnalyticalViewIdentity(
            schema_version=ANALYTICAL_VIEW_SCHEMA_VERSION,
            run_id=self._run_id,
            source_revision=self._source_revision,
            config_fingerprint=config_fingerprint,
            manifest_identity=manifest_identity,
            input_high_water=self.high_water,
            window_baseline=self._window.baseline_boundary,
            window_end=self._window.end_boundary,
            metric_family=CULTURAL_TRAIT_DYNAMICS_FAMILY,
            algorithm_version=CULTURAL_TRAIT_DYNAMICS_ALGORITHM_VERSION,
            library_versions_digest=_digest(dict(library_versions())),
            stage=_FINAL_ROWS if self._sealed else _FIRST_PASS,
            source_prefix_digest=self.prefix_digest(),
            sealed_source_digest=self.sealed_source_digest(),
            coverage_observed=observed,
            coverage_expected=expected,
            gaps=self._gaps,
            gaps_digest=_digest(list(self._gaps)),
        )

    def checkpoint(
        self,
        *,
        config_fingerprint: str,
        manifest_identity: str,
    ) -> TraitDynamicsCheckpoint:
        measurements = self.measurements() if self._sealed else ()
        identity = self.identity(
            config_fingerprint=config_fingerprint,
            manifest_identity=manifest_identity,
        )
        payload = {
            "schema_version": ANALYTICAL_VIEW_SCHEMA_VERSION,
            "identity": identity.payload(),
            "states": _states_payload(tuple(self._states)),
            "evidence": _evidence_payload(self._evidence),
            "measurements": [row.to_payload() for row in measurements],
        }
        return TraitDynamicsCheckpoint(
            identity=identity,
            states=tuple(self._states),
            evidence=self._evidence,
            measurements=measurements,
            digest=_digest(payload),
        )


def compute_cultural_trait_dynamics_incremental(
    inputs: CulturalEvolutionInputs,
) -> tuple[CulturalMeasurement, ...]:
    """Exact incremental equivalent of the batch trait-dynamics calculator."""
    accumulator = TraitDynamicsAccumulator.from_inputs(inputs)
    for boundary in inputs.boundaries:
        accumulator.apply(boundary)
    accumulator.seal()
    return accumulator.measurements()


def resume_checkpoint(
    checkpoint: TraitDynamicsCheckpoint,
    *,
    expected: AnalyticalViewIdentity,
    allow_prefix: bool = True,
) -> TraitDynamicsAccumulator:
    """Resume only when exact anchors match; otherwise fail closed."""
    if type(checkpoint) is not TraitDynamicsCheckpoint:
        raise TypeError("checkpoint must be TraitDynamicsCheckpoint")
    if type(expected) is not AnalyticalViewIdentity:
        raise TypeError("expected must be AnalyticalViewIdentity")
    identity = checkpoint.identity
    _verify_checkpoint_digest(checkpoint)
    if identity.stage == _FINAL_ROWS:
        if identity != expected:
            raise AnalyticalViewMismatch("view_identity_mismatch")
    else:
        if not allow_prefix:
            raise AnalyticalViewMismatch("prefix_resume_not_allowed")
        prefix_fields = (
            "run_id",
            "source_revision",
            "config_fingerprint",
            "manifest_identity",
            "input_high_water",
            "window_baseline",
            "window_end",
            "metric_family",
            "algorithm_version",
            "library_versions_digest",
            "gaps_digest",
            "source_prefix_digest",
        )
        for field in prefix_fields:
            if getattr(identity, field) != getattr(expected, field):
                raise AnalyticalViewMismatch(f"view_prefix_mismatch:{field}")
    window = CulturalAnalysisWindow(
        baseline_boundary=identity.window_baseline,
        end_boundary=identity.window_end,
    )
    accumulator = TraitDynamicsAccumulator(
        run_id=identity.run_id,
        source_revision=identity.source_revision,
        window=window,
        gaps=identity.gaps,
        evidence=checkpoint.evidence,
    )
    accumulator.restore(
        checkpoint.states,
        sealed=identity.stage == _FINAL_ROWS,
    )
    if identity.stage == _FINAL_ROWS:
        if checkpoint.output_digest() != _measurement_digest(checkpoint.measurements):
            raise AnalyticalViewMismatch("view_output_digest_mismatch")
        if accumulator.measurements() != checkpoint.measurements:
            raise AnalyticalViewMismatch("view_final_rows_mismatch")
    return accumulator


def _evidence_payload(evidence: TraitEvidenceIndex) -> dict[str, object]:
    return {
        "entry_ids": [
            [owner, tick, local_id, pointer_id]
            for (owner, tick, local_id), pointer_id in sorted(
                evidence.entry_ids.items()
            )
        ],
        "roster_ids": [
            [tick, pointer_id]
            for tick, pointer_id in sorted(evidence.roster_ids.items())
        ],
    }


def _evidence_from_payload(value: object) -> TraitEvidenceIndex:
    if not isinstance(value, Mapping) or set(value) != {
        "entry_ids",
        "roster_ids",
    }:
        raise AnalyticalViewMismatch("invalid_evidence")
    raw_entries = value["entry_ids"]
    raw_rosters = value["roster_ids"]
    if not isinstance(raw_entries, list) or not isinstance(raw_rosters, list):
        raise AnalyticalViewMismatch("invalid_evidence")
    entry_ids: dict[tuple[str, int, str], str] = {}
    for row in raw_entries:
        if not isinstance(row, (list, tuple)) or len(row) != 4:
            raise AnalyticalViewMismatch("invalid_evidence")
        owner, tick, local_id, pointer_id = row
        if type(tick) is not int:
            raise AnalyticalViewMismatch("invalid_evidence")
        entry_ids[(str(owner), tick, str(local_id))] = str(pointer_id)
    roster_ids: dict[int, str] = {}
    for row in raw_rosters:
        if not isinstance(row, (list, tuple)) or len(row) != 2:
            raise AnalyticalViewMismatch("invalid_evidence")
        tick, pointer_id = row
        if type(tick) is not int:
            raise AnalyticalViewMismatch("invalid_evidence")
        roster_ids[tick] = str(pointer_id)
    return TraitEvidenceIndex(entry_ids=entry_ids, roster_ids=roster_ids)


def _checkpoint_payload(checkpoint: TraitDynamicsCheckpoint) -> dict[str, object]:
    return {
        "schema_version": ANALYTICAL_VIEW_SCHEMA_VERSION,
        "identity": checkpoint.identity.payload(),
        "states": _states_payload(checkpoint.states),
        "evidence": _evidence_payload(checkpoint.evidence),
        "measurements": [row.to_payload() for row in checkpoint.measurements],
    }


def _verify_checkpoint_digest(checkpoint: TraitDynamicsCheckpoint) -> None:
    if _digest(_checkpoint_payload(checkpoint)) != checkpoint.digest:
        raise AnalyticalViewMismatch("view_digest_mismatch")


def write_checkpoint(path: Path, checkpoint: TraitDynamicsCheckpoint) -> None:
    """Atomically publish a disposable view checkpoint."""
    if not isinstance(path, Path):
        raise TypeError("path must be pathlib.Path")
    if type(checkpoint) is not TraitDynamicsCheckpoint:
        raise TypeError("checkpoint must be TraitDynamicsCheckpoint")
    _verify_checkpoint_digest(checkpoint)
    payload = _checkpoint_payload(checkpoint)
    payload["digest"] = checkpoint.digest
    body = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if len(body) > MAX_CHECKPOINT_BYTES:
        raise AnalyticalViewMismatch("checkpoint_too_large")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    try:
        with temporary.open("wb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    _LOG.info(
        "analytical_view_published family=%s stage=%s boundaries=%s bytes=%s",
        checkpoint.identity.metric_family,
        checkpoint.identity.stage,
        len(checkpoint.states),
        len(body),
    )


def read_checkpoint(path: Path) -> TraitDynamicsCheckpoint:
    """Read and strictly verify one disposable view checkpoint."""
    if not isinstance(path, Path):
        raise TypeError("path must be pathlib.Path")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise AnalyticalViewMismatch("checkpoint_unreadable") from exc
    if len(raw) > MAX_CHECKPOINT_BYTES:
        raise AnalyticalViewMismatch("checkpoint_too_large")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AnalyticalViewMismatch("checkpoint_invalid_json") from exc
    if not isinstance(payload, Mapping):
        raise AnalyticalViewMismatch("checkpoint_invalid")
    expected_keys = {
        "schema_version",
        "identity",
        "states",
        "evidence",
        "measurements",
        "digest",
    }
    if set(payload) != expected_keys:
        raise AnalyticalViewMismatch("checkpoint_key_set_mismatch")
    if payload["schema_version"] != ANALYTICAL_VIEW_SCHEMA_VERSION:
        raise AnalyticalViewMismatch("unsupported_view_schema")
    identity_payload = payload["identity"]
    if not isinstance(identity_payload, Mapping):
        raise AnalyticalViewMismatch("invalid_identity")
    identity_fields = set(AnalyticalViewIdentity.__dataclass_fields__)
    if set(identity_payload) != identity_fields:
        raise AnalyticalViewMismatch("invalid_identity")
    identity = AnalyticalViewIdentity(
        schema_version=identity_payload["schema_version"],
        run_id=identity_payload["run_id"],
        source_revision=identity_payload["source_revision"],
        config_fingerprint=identity_payload["config_fingerprint"],
        manifest_identity=identity_payload["manifest_identity"],
        input_high_water=identity_payload["input_high_water"],
        window_baseline=identity_payload["window_baseline"],
        window_end=identity_payload["window_end"],
        metric_family=identity_payload["metric_family"],
        algorithm_version=identity_payload["algorithm_version"],
        library_versions_digest=identity_payload["library_versions_digest"],
        stage=identity_payload["stage"],
        source_prefix_digest=identity_payload["source_prefix_digest"],
        sealed_source_digest=identity_payload["sealed_source_digest"],
        coverage_observed=identity_payload["coverage_observed"],
        coverage_expected=identity_payload["coverage_expected"],
        gaps=tuple(identity_payload["gaps"]),
        gaps_digest=identity_payload["gaps_digest"],
    )
    states_raw = payload["states"]
    measurements_raw = payload["measurements"]
    if not isinstance(states_raw, list) or not isinstance(measurements_raw, list):
        raise AnalyticalViewMismatch("checkpoint_invalid")
    states = tuple(_state_from_payload(item) for item in states_raw)
    evidence = _evidence_from_payload(payload["evidence"])
    measurements = tuple(_measurement_from_payload(item) for item in measurements_raw)
    checkpoint = TraitDynamicsCheckpoint(
        identity=identity,
        states=states,
        evidence=evidence,
        measurements=measurements,
        digest=payload["digest"],
    )
    _verify_checkpoint_digest(checkpoint)
    return checkpoint


def _measurement_from_payload(value: object) -> CulturalMeasurement:
    if not isinstance(value, Mapping):
        raise AnalyticalViewMismatch("checkpoint_invalid_measurement")
    try:
        return CulturalMeasurement.from_payload(
            value,
            family=CULTURAL_TRAIT_DYNAMICS_FAMILY,
            algorithm_version=CULTURAL_TRAIT_DYNAMICS_ALGORITHM_VERSION,
            policy_version=CULTURAL_EVOLUTION_POLICY_VERSION,
        )
    except ValueError as exc:
        raise AnalyticalViewMismatch("checkpoint_invalid_measurement") from exc
