"""Deterministic V3 long-horizon workload definitions and manifests.

These helpers build supported runner configurations only. They do not add new
scientific mechanisms, mutate runner/result schemas, or start benchmark work by
default. Measurements are emitted by :mod:`tests.benchmarks.v3_measurement`.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Final

from experiments.generational_axes import apply_generational_level
from experiments.generational_comparison_models import GenerationalComparisonAxis
from experiments.generational_runner_scenario import generational_runner_scenario
from simulation.models import RunId, StochasticIdentity
from simulation.runner_models import (
    RunnerCheckpointPolicy,
    RunnerPersistenceSpec,
    SimulationRunnerConfig,
)
from simulation.runner_serialization import (
    runner_config_fingerprint,
    scenario_fingerprint,
)
from tests.benchmarks.harness import build_scale_config
from world.lifecycle import LifecycleStageId, LifecycleStageThreshold

_LOG: Final[logging.Logger] = logging.getLogger("scale.v3.workloads")

WORKLOAD_SCHEMA_VERSION: Final[str] = "v3-scale-workload-v1"
SMOKE_TICKS: Final[int] = 64
STANDARD_TICKS: Final[int] = 10_000
EXTENDED_TICKS: Final[int] = 100_000
SUPPORTED_HORIZONS: Final[tuple[int, ...]] = (
    SMOKE_TICKS,
    STANDARD_TICKS,
    EXTENDED_TICKS,
)


class V3ScaleLane(StrEnum):
    """Closed benchmark lanes from the V3-43 request."""

    CONTROL = "v1-control"
    GENERATIONAL = "generational"
    EVIDENCE = "evidence-rich"
    HISTORICAL_QUERY = "historical-query"


_LANE_ORDER: Final[tuple[V3ScaleLane, ...]] = (
    V3ScaleLane.CONTROL,
    V3ScaleLane.GENERATIONAL,
    V3ScaleLane.EVIDENCE,
    V3ScaleLane.HISTORICAL_QUERY,
)


@dataclass(frozen=True, slots=True)
class V3ScaleWorkload:
    """One benchmark lane with a stable scientific identity.

    ``config`` is available to in-process test drivers. It is intentionally not
    serialized into the manifest; fingerprints identify it without dumping a
    runner payload into benchmark artifacts.
    """

    workload_id: str
    lane: V3ScaleLane
    horizon_ticks: int
    run_id: RunId
    seed: int
    stochastic_identity: str
    config_fingerprint: str
    scenario_fingerprint: str
    cognitive_architecture_id: str
    checkpoint_cadence: int | None
    capture_modes: tuple[str, ...]
    tracing_enabled: bool
    min_completed_cohorts: int
    executes: bool
    source_lane: V3ScaleLane | None
    config: SimulationRunnerConfig

    def __post_init__(self) -> None:
        if not isinstance(self.lane, V3ScaleLane):
            raise TypeError("lane must be V3ScaleLane")
        if type(self.workload_id) is not str or not self.workload_id.strip():
            raise ValueError("workload_id must be a non-empty string")
        _require_positive_int("horizon_ticks", self.horizon_ticks)
        if type(self.run_id) is not RunId:
            raise TypeError("run_id must be RunId")
        if type(self.seed) is not int or self.seed < 0:
            raise ValueError("seed must be a non-negative integer")
        if not self.stochastic_identity:
            raise ValueError("stochastic_identity must be non-empty")
        for name, value in (
            ("config_fingerprint", self.config_fingerprint),
            ("scenario_fingerprint", self.scenario_fingerprint),
        ):
            if not _is_sha256(value):
                raise ValueError(f"{name} must be a lowercase SHA-256 digest")
        if not self.cognitive_architecture_id:
            raise ValueError("cognitive_architecture_id must be non-empty")
        if self.checkpoint_cadence is not None:
            _require_positive_int("checkpoint_cadence", self.checkpoint_cadence)
        if type(self.capture_modes) is not tuple:
            raise TypeError("capture_modes must be a tuple")
        for mode in self.capture_modes:
            if type(mode) is not str or not mode.strip():
                raise ValueError("capture_modes entries must be non-empty strings")
        if type(self.tracing_enabled) is not bool:
            raise TypeError("tracing_enabled must be bool")
        if type(self.min_completed_cohorts) is not int:
            raise TypeError("min_completed_cohorts must be int")
        if self.min_completed_cohorts < 0:
            raise ValueError("min_completed_cohorts must be >= 0")
        if type(self.executes) is not bool:
            raise TypeError("executes must be bool")
        if self.source_lane is not None and not isinstance(
            self.source_lane, V3ScaleLane
        ):
            raise TypeError("source_lane must be V3ScaleLane or None")
        if type(self.config) is not SimulationRunnerConfig:
            raise TypeError("config must be SimulationRunnerConfig")
        if not self.executes and self.source_lane is None:
            raise ValueError("non-executing lanes require a source lane")

    def manifest(self) -> dict[str, object]:
        """Return the canonical, payload-free workload manifest."""
        return {
            "schema": WORKLOAD_SCHEMA_VERSION,
            "workload_id": self.workload_id,
            "lane": self.lane.value,
            "horizon_ticks": self.horizon_ticks,
            "run_id": self.run_id.value,
            "seed": self.seed,
            "stochastic_identity": self.stochastic_identity,
            "config_fingerprint": self.config_fingerprint,
            "scenario_fingerprint": self.scenario_fingerprint,
            "cognitive_architecture_id": self.cognitive_architecture_id,
            "checkpoint_cadence": self.checkpoint_cadence,
            "capture_modes": list(self.capture_modes),
            "tracing_enabled": self.tracing_enabled,
            "min_completed_cohorts": self.min_completed_cohorts,
            "executes": self.executes,
            "source_lane": None if self.source_lane is None else self.source_lane.value,
        }

    def manifest_fingerprint(self) -> str:
        return _canonical_sha256(self.manifest())

    def assert_same_scientific_identity(self, other: V3ScaleWorkload) -> None:
        """Fail closed when paired attempts differ in domain identity."""
        if type(other) is not V3ScaleWorkload:
            raise TypeError("other must be V3ScaleWorkload")
        for name in (
            "workload_id",
            "lane",
            "horizon_ticks",
            "run_id",
            "seed",
            "stochastic_identity",
            "config_fingerprint",
            "scenario_fingerprint",
            "cognitive_architecture_id",
        ):
            left = getattr(self, name)
            right = getattr(other, name)
            if left != right:
                raise ValueError(f"scientific_identity_mismatch:{name}")


def build_workload(
    lane: V3ScaleLane | str,
    *,
    ticks: int,
    seed: int = 23,
    run_id: RunId | None = None,
) -> V3ScaleWorkload:
    """Build one supported V3 workload for an explicit horizon."""
    resolved = _require_lane(lane)
    _require_positive_int("ticks", ticks)
    if type(seed) is not int or seed < 0:
        raise ValueError("seed must be a non-negative integer")
    active_run_id = run_id or _default_run_id(resolved, seed=seed, ticks=ticks)
    if type(active_run_id) is not RunId:
        raise TypeError("run_id must be RunId")
    if resolved is V3ScaleLane.CONTROL:
        config = build_scale_config(
            max_ticks=ticks,
            checkpoint_cadence=_checkpoint_cadence(ticks),
            seed=seed,
        )
        return _workload(
            lane=resolved,
            ticks=ticks,
            seed=seed,
            run_id=active_run_id,
            config=config,
            architecture="v1-reference",
            cohorts=0,
            capture=(),
            source=None,
            executes=True,
        )
    if resolved is V3ScaleLane.GENERATIONAL:
        config = _generational_config(seed=seed, ticks=ticks)
        return _workload(
            lane=resolved,
            ticks=ticks,
            seed=seed,
            run_id=active_run_id,
            config=config,
            architecture="v55-generational-unassisted",
            cohorts=2,
            capture=("population-lifecycle", "generational-progress"),
            source=None,
            executes=True,
        )
    if resolved is V3ScaleLane.EVIDENCE:
        config = _evidence_config(seed=seed, ticks=ticks)
        return _workload(
            lane=resolved,
            ticks=ticks,
            seed=seed,
            run_id=active_run_id,
            config=config,
            architecture="v55-evidence-rich-teaching",
            cohorts=2,
            capture=(
                "population-lifecycle",
                "generational-progress",
                "durable-records",
                "cultural-provenance",
                "institution-concepts",
                "office-succession",
                "teaching-uptake",
            ),
            source=None,
            executes=True,
        )
    source = build_workload(
        V3ScaleLane.EVIDENCE, ticks=ticks, seed=seed, run_id=active_run_id
    )
    return replace(
        source,
        workload_id=f"{resolved.value}-{ticks}",
        lane=resolved,
        capture_modes=(*source.capture_modes, "historical-lineage"),
        executes=False,
        source_lane=V3ScaleLane.EVIDENCE,
    )


def build_workloads(
    *,
    ticks: int,
    seed: int = 23,
    lanes: tuple[V3ScaleLane, ...] = _LANE_ORDER,
) -> tuple[V3ScaleWorkload, ...]:
    """Build the requested lanes for one horizon, preserving lane order."""
    resolved = tuple(_require_lane(lane) for lane in lanes)
    if len(set(resolved)) != len(resolved):
        raise ValueError("lanes must not contain duplicates")
    source_run: RunId | None = None
    workloads: list[V3ScaleWorkload] = []
    for lane in resolved:
        if lane is V3ScaleLane.HISTORICAL_QUERY:
            if source_run is None:
                source = build_workload(
                    V3ScaleLane.EVIDENCE, ticks=ticks, seed=seed
                )
                source_run = source.run_id
            workloads.append(
                build_workload(lane, ticks=ticks, seed=seed, run_id=source_run)
            )
            continue
        workload = build_workload(lane, ticks=ticks, seed=seed)
        if lane is V3ScaleLane.EVIDENCE:
            source_run = workload.run_id
        workloads.append(workload)
    return tuple(workloads)


def required_lane_count(workload: V3ScaleWorkload) -> int:
    """Return the minimum completed cohort count for a sustained lane."""
    if type(workload) is not V3ScaleWorkload:
        raise TypeError("workload must be V3ScaleWorkload")
    return workload.min_completed_cohorts


def _workload(
    *,
    lane: V3ScaleLane,
    ticks: int,
    seed: int,
    run_id: RunId,
    config: SimulationRunnerConfig,
    architecture: str,
    cohorts: int,
    capture: tuple[str, ...],
    source: V3ScaleLane | None,
    executes: bool,
) -> V3ScaleWorkload:
    checkpoint = config.persistence.checkpoint
    cadence = checkpoint.cadence_ticks if checkpoint.enabled else None
    tracing = config.cognition_trace is not None
    workload = V3ScaleWorkload(
        workload_id=f"{lane.value}-{ticks}",
        lane=lane,
        horizon_ticks=ticks,
        run_id=run_id,
        seed=seed,
        stochastic_identity=config.stochastic_identity.value,
        config_fingerprint=runner_config_fingerprint(config),
        scenario_fingerprint=scenario_fingerprint(config),
        cognitive_architecture_id=architecture,
        checkpoint_cadence=cadence,
        capture_modes=capture,
        tracing_enabled=tracing,
        min_completed_cohorts=cohorts,
        executes=executes,
        source_lane=source,
        config=config,
    )
    _LOG.debug(
        "v3_workload_built lane=%s ticks=%s cadence=%s cohorts_min=%s",
        workload.lane.value,
        workload.horizon_ticks,
        workload.checkpoint_cadence,
        workload.min_completed_cohorts,
    )
    return workload


def _generational_config(*, seed: int, ticks: int) -> SimulationRunnerConfig:
    definition = generational_runner_scenario(seed=seed, max_ticks=ticks)
    config = next(
        condition.runner_config
        for condition in definition.conditions
        if condition.condition_id == "bl-generational-unassisted"
    )
    return _tune_generational(config, ticks=ticks)


def _evidence_config(*, seed: int, ticks: int) -> SimulationRunnerConfig:
    config = _generational_config(seed=seed, ticks=ticks)
    for axis, level in (
        (GenerationalComparisonAxis.RECORD_AVAILABILITY, "present"),
        (GenerationalComparisonAxis.INSTITUTION_SUPPORT, "on"),
        (GenerationalComparisonAxis.TEACHING_FREQUENCY, "high"),
    ):
        config = apply_generational_level(config, axis, level)
    return config


def _tune_generational(
    config: SimulationRunnerConfig, *, ticks: int
) -> SimulationRunnerConfig:
    lifecycle = config.population_lifecycle
    if lifecycle is None:
        raise ValueError("generational_workload_requires_lifecycle")
    interval = max(1, min(1_000, ticks // 8))
    lifespan = max(4, interval * 3)
    adult_age = lifespan - 1
    juvenile_age = min(5, max(2, adult_age - 1))
    infant_age = max(1, juvenile_age - 1)
    if not infant_age < juvenile_age < adult_age:
        raise ValueError("generational_workload_stage_thresholds_invalid")
    params = dict(lifecycle.demographic_policy_params)
    params.update(
        {
            "interval_ticks": interval,
            "entries_per_interval": 1,
            "generation_length_ticks": interval,
        }
    )
    lifecycle = replace(
        lifecycle,
        lifespan_ticks=lifespan,
        stage_thresholds=(
            LifecycleStageThreshold(LifecycleStageId("infant"), infant_age),
            LifecycleStageThreshold(LifecycleStageId("juvenile"), juvenile_age),
            LifecycleStageThreshold(LifecycleStageId("adult"), adult_age),
        ),
        demographic_policy_params=params,
        max_population=max(8, lifecycle.max_population),
    )
    generational = config.generational_run
    if generational is None:
        raise ValueError("generational_workload_requires_generational_run")
    cadence = _checkpoint_cadence(ticks)
    generational = replace(
        generational,
        max_generation_index=None,
        stop_on_extinction=False,
        criterion_cadence_ticks=1,
    )
    return replace(
        config,
        stochastic_identity=StochasticIdentity(config.stochastic_identity.value),
        population_lifecycle=lifecycle,
        generational_run=generational,
        persistence=RunnerPersistenceSpec(
            durable=True,
            checkpoint=RunnerCheckpointPolicy(
                enabled=True, cadence_ticks=cadence
            ),
        ),
    )


def _checkpoint_cadence(ticks: int) -> int:
    return max(1, min(1_000, ticks // 10 or 1))


def _default_run_id(lane: V3ScaleLane, *, seed: int, ticks: int) -> RunId:
    return RunId(
        f"v3-43-{lane.value.replace('_', '-')}-ticks-{ticks}-seed-{seed}"
    )


def _require_lane(value: V3ScaleLane | str) -> V3ScaleLane:
    if isinstance(value, V3ScaleLane):
        return value
    if type(value) is str:
        try:
            return V3ScaleLane(value)
        except ValueError as exc:
            raise ValueError(f"unknown V3 scale lane: {value!r}") from exc
    raise TypeError("lane must be V3ScaleLane or str")


def _require_positive_int(name: str, value: object) -> None:
    if type(value) is not int or value < 1:
        raise ValueError(f"{name} must be a positive integer")


def _is_sha256(value: object) -> bool:
    if type(value) is not str or len(value) != 64:
        return False
    return all(character in "0123456789abcdef" for character in value)


def _canonical_sha256(document: object) -> str:
    payload = json.dumps(
        document,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


__all__ = [
    "EXTENDED_TICKS",
    "SMOKE_TICKS",
    "STANDARD_TICKS",
    "SUPPORTED_HORIZONS",
    "WORKLOAD_SCHEMA_VERSION",
    "V3ScaleLane",
    "V3ScaleWorkload",
    "build_workload",
    "build_workloads",
    "required_lane_count",
]
