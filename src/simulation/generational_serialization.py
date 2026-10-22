"""Exact-key-set codecs for generational run contracts.

The mappings here are children of ``runner-config-v55`` and
``runner-result-v3``. They intentionally avoid importing
``runner_serialization`` at module import time; the fail-closed error type is
resolved lazily so the two codec modules can depend on the shared models
without a cycle.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from simulation.generational_models import (
    BoundaryEventFact,
    CohortPopulationRow,
    ExperimentCriterionEvaluationStatus,
    ExperimentCriterionIdentity,
    ExperimentCriterionSpec,
    GenerationalBoundary,
    GenerationalRunSpec,
    GenerationPopulationRow,
    PopulationProgress,
    PopulationThresholdComparison,
    PopulationThresholdSpec,
    StopEvidence,
)

_GENERATIONAL_RUN_KEYS = {
    "criterion_cadence_ticks",
    "experiment_criteria",
    "historical_checkpoint_cadence_ticks",
    "max_generation_index",
    "population_threshold",
    "sample_on_generation_change",
    "stop_on_extinction",
}
_THRESHOLD_KEYS = {"comparison", "value"}
_CRITERION_KEYS = {"criterion_id", "params", "version"}
_PROGRESS_KEYS = {
    "boundary_tick",
    "cohorts",
    "generations",
    "living_population",
    "max_generation_index_seen",
    "total_admitted",
    "total_deaths",
}
_COHORT_KEYS = {
    "admitted",
    "cohort_id",
    "dead",
    "entry_tick",
    "generation_index",
    "living",
}
_GENERATION_KEYS = {"admitted", "dead", "generation_index", "living"}
_BOUNDARY_KEYS = {
    "event_facts",
    "last_completed_tick",
    "objective_commit_id",
    "objective_revision",
    "progress",
}
_EVENT_FACT_KEYS = {"actor_id", "event_id", "kind", "target_id", "tick"}
_STOP_EVIDENCE_KEYS = {
    "boundary",
    "criterion_evaluation_status",
    "failed_stage",
    "failure_reason_code",
    "matched_condition_codes",
    "matched_criteria",
    "measurements",
    "primary_condition_code",
}
_CRITERION_IDENTITY_KEYS = {"criterion_id", "version"}


def _error(code: str, path: str) -> Exception:
    from simulation.runner_serialization import RunnerSerializationError

    return RunnerSerializationError(code, path)


def _require_exact_keys(
    data: object, expected: set[str], *, path: str
) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise _error("invalid_object", path)
    actual = set(data)
    if actual != expected:
        raise _error("invalid_keys", path)
    return data


def _str_field(data: Mapping[str, Any], key: str, *, path: str) -> str:
    value = data[key]
    if type(value) is not str:
        raise _error("invalid_string", f"{path}.{key}")
    return value


def _optional_str_field(
    data: Mapping[str, Any], key: str, *, path: str
) -> str | None:
    value = data[key]
    if value is None:
        return None
    if type(value) is not str:
        raise _error("invalid_string", f"{path}.{key}")
    return value


def _bool_field(data: Mapping[str, Any], key: str, *, path: str) -> bool:
    value = data[key]
    if type(value) is not bool:
        raise _error("invalid_boolean", f"{path}.{key}")
    return value


def _int_field(data: Mapping[str, Any], key: str, *, path: str) -> int:
    value = data[key]
    if isinstance(value, bool) or type(value) is not int:
        raise _error("invalid_integer", f"{path}.{key}")
    return value


def _optional_int_field(
    data: Mapping[str, Any], key: str, *, path: str
) -> int | None:
    value = data[key]
    if value is None:
        return None
    if isinstance(value, bool) or type(value) is not int:
        raise _error("invalid_integer", f"{path}.{key}")
    return value


def _array(value: object, *, path: str) -> list[object]:
    if not isinstance(value, list):
        raise _error("invalid_array", path)
    return value


def _measurement_value(value: object, *, path: str) -> object:
    if type(value) in (bool, int):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise _error("invalid_number", path)
        return value
    raise _error("invalid_number", path)


def encode_population_threshold(value: PopulationThresholdSpec) -> dict[str, Any]:
    return {"comparison": value.comparison.value, "value": value.value}


def decode_population_threshold(
    data: object, *, path: str
) -> PopulationThresholdSpec:
    document = _require_exact_keys(data, _THRESHOLD_KEYS, path=path)
    comparison_raw = _str_field(document, "comparison", path=path)
    try:
        comparison = PopulationThresholdComparison(comparison_raw)
    except ValueError as exc:
        raise _error("invalid_enum", f"{path}.comparison") from exc
    try:
        return PopulationThresholdSpec(
            comparison=comparison,
            value=_int_field(document, "value", path=path),
        )
    except (TypeError, ValueError) as exc:
        raise _error("invalid_value", path) from exc


def encode_experiment_criterion(value: ExperimentCriterionSpec) -> dict[str, Any]:
    return {
        "criterion_id": value.criterion_id,
        "params": _thaw(value.params),
        "version": value.version,
    }


def _thaw(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def decode_experiment_criterion(
    data: object, *, path: str
) -> ExperimentCriterionSpec:
    document = _require_exact_keys(data, _CRITERION_KEYS, path=path)
    params = document["params"]
    if not isinstance(params, dict):
        raise _error("invalid_object", f"{path}.params")
    try:
        return ExperimentCriterionSpec(
            criterion_id=_str_field(document, "criterion_id", path=path),
            version=_str_field(document, "version", path=path),
            params=params,
        )
    except (TypeError, ValueError) as exc:
        raise _error("invalid_value", path) from exc


def encode_experiment_criterion_identity(
    value: ExperimentCriterionIdentity,
) -> dict[str, Any]:
    return {"criterion_id": value.criterion_id, "version": value.version}


def decode_experiment_criterion_identity(
    data: object, *, path: str
) -> ExperimentCriterionIdentity:
    document = _require_exact_keys(data, _CRITERION_IDENTITY_KEYS, path=path)
    try:
        return ExperimentCriterionIdentity(
            criterion_id=_str_field(document, "criterion_id", path=path),
            version=_str_field(document, "version", path=path),
        )
    except (TypeError, ValueError) as exc:
        raise _error("invalid_value", path) from exc


def encode_generational_run(value: GenerationalRunSpec) -> dict[str, Any]:
    return {
        "criterion_cadence_ticks": value.criterion_cadence_ticks,
        "experiment_criteria": [
            encode_experiment_criterion(item) for item in value.experiment_criteria
        ],
        "historical_checkpoint_cadence_ticks": (
            value.historical_checkpoint_cadence_ticks
        ),
        "max_generation_index": value.max_generation_index,
        "population_threshold": (
            None
            if value.population_threshold is None
            else encode_population_threshold(value.population_threshold)
        ),
        "sample_on_generation_change": value.sample_on_generation_change,
        "stop_on_extinction": value.stop_on_extinction,
    }


def decode_generational_run(data: object, *, path: str) -> GenerationalRunSpec:
    document = _require_exact_keys(data, _GENERATIONAL_RUN_KEYS, path=path)
    threshold_raw = document["population_threshold"]
    threshold = (
        None
        if threshold_raw is None
        else decode_population_threshold(
            threshold_raw, path=f"{path}.population_threshold"
        )
    )
    criteria = tuple(
        decode_experiment_criterion(
            item, path=f"{path}.experiment_criteria[{index}]"
        )
        for index, item in enumerate(
            _array(document["experiment_criteria"], path=f"{path}.experiment_criteria")
        )
    )
    try:
        return GenerationalRunSpec(
            max_generation_index=_optional_int_field(
                document, "max_generation_index", path=path
            ),
            stop_on_extinction=_bool_field(
                document, "stop_on_extinction", path=path
            ),
            population_threshold=threshold,
            experiment_criteria=criteria,
            criterion_cadence_ticks=_int_field(
                document, "criterion_cadence_ticks", path=path
            ),
            historical_checkpoint_cadence_ticks=_optional_int_field(
                document, "historical_checkpoint_cadence_ticks", path=path
            ),
            sample_on_generation_change=_bool_field(
                document, "sample_on_generation_change", path=path
            ),
        )
    except (TypeError, ValueError) as exc:
        raise _error("invalid_value", path) from exc


def encode_cohort_population_row(value: CohortPopulationRow) -> dict[str, Any]:
    return {
        "admitted": value.admitted,
        "cohort_id": value.cohort_id,
        "dead": value.dead,
        "entry_tick": value.entry_tick,
        "generation_index": value.generation_index,
        "living": value.living,
    }


def decode_cohort_population_row(
    data: object, *, path: str
) -> CohortPopulationRow:
    document = _require_exact_keys(data, _COHORT_KEYS, path=path)
    try:
        return CohortPopulationRow(
            generation_index=_int_field(document, "generation_index", path=path),
            entry_tick=_int_field(document, "entry_tick", path=path),
            cohort_id=_str_field(document, "cohort_id", path=path),
            admitted=_int_field(document, "admitted", path=path),
            living=_int_field(document, "living", path=path),
            dead=_int_field(document, "dead", path=path),
        )
    except (TypeError, ValueError) as exc:
        raise _error("invalid_value", path) from exc


def encode_generation_population_row(
    value: GenerationPopulationRow,
) -> dict[str, Any]:
    return {
        "admitted": value.admitted,
        "dead": value.dead,
        "generation_index": value.generation_index,
        "living": value.living,
    }


def decode_generation_population_row(
    data: object, *, path: str
) -> GenerationPopulationRow:
    document = _require_exact_keys(data, _GENERATION_KEYS, path=path)
    try:
        return GenerationPopulationRow(
            generation_index=_int_field(document, "generation_index", path=path),
            admitted=_int_field(document, "admitted", path=path),
            living=_int_field(document, "living", path=path),
            dead=_int_field(document, "dead", path=path),
        )
    except (TypeError, ValueError) as exc:
        raise _error("invalid_value", path) from exc


def encode_population_progress(value: PopulationProgress) -> dict[str, Any]:
    return {
        "boundary_tick": value.boundary_tick,
        "cohorts": [encode_cohort_population_row(item) for item in value.cohorts],
        "generations": [
            encode_generation_population_row(item) for item in value.generations
        ],
        "living_population": value.living_population,
        "max_generation_index_seen": value.max_generation_index_seen,
        "total_admitted": value.total_admitted,
        "total_deaths": value.total_deaths,
    }


def decode_population_progress(data: object, *, path: str) -> PopulationProgress:
    document = _require_exact_keys(data, _PROGRESS_KEYS, path=path)
    cohorts = tuple(
        decode_cohort_population_row(item, path=f"{path}.cohorts[{index}]")
        for index, item in enumerate(
            _array(document["cohorts"], path=f"{path}.cohorts")
        )
    )
    generations = tuple(
        decode_generation_population_row(
            item, path=f"{path}.generations[{index}]"
        )
        for index, item in enumerate(
            _array(document["generations"], path=f"{path}.generations")
        )
    )
    try:
        return PopulationProgress(
            boundary_tick=_int_field(document, "boundary_tick", path=path),
            living_population=_int_field(
                document, "living_population", path=path
            ),
            total_admitted=_int_field(document, "total_admitted", path=path),
            total_deaths=_int_field(document, "total_deaths", path=path),
            max_generation_index_seen=_int_field(
                document, "max_generation_index_seen", path=path
            ),
            cohorts=cohorts,
            generations=generations,
        )
    except (TypeError, ValueError) as exc:
        raise _error("invalid_value", path) from exc


def encode_boundary_event_fact(value: BoundaryEventFact) -> dict[str, Any]:
    return {
        "actor_id": value.actor_id,
        "event_id": value.event_id,
        "kind": value.kind,
        "target_id": value.target_id,
        "tick": value.tick,
    }


def decode_boundary_event_fact(
    data: object, *, path: str
) -> BoundaryEventFact:
    document = _require_exact_keys(data, _EVENT_FACT_KEYS, path=path)
    try:
        return BoundaryEventFact(
            event_id=_str_field(document, "event_id", path=path),
            kind=_str_field(document, "kind", path=path),
            tick=_int_field(document, "tick", path=path),
            actor_id=_optional_str_field(document, "actor_id", path=path),
            target_id=_optional_str_field(document, "target_id", path=path),
        )
    except (TypeError, ValueError) as exc:
        raise _error("invalid_value", path) from exc


def encode_generational_boundary(value: GenerationalBoundary) -> dict[str, Any]:
    return {
        "event_facts": [
            encode_boundary_event_fact(item) for item in value.event_facts
        ],
        "last_completed_tick": value.last_completed_tick,
        "objective_commit_id": value.objective_commit_id,
        "objective_revision": value.objective_revision,
        "progress": encode_population_progress(value.progress),
    }


def decode_generational_boundary(
    data: object, *, path: str
) -> GenerationalBoundary:
    document = _require_exact_keys(data, _BOUNDARY_KEYS, path=path)
    facts = tuple(
        decode_boundary_event_fact(
            item, path=f"{path}.event_facts[{index}]"
        )
        for index, item in enumerate(
            _array(document["event_facts"], path=f"{path}.event_facts")
        )
    )
    try:
        return GenerationalBoundary(
            progress=decode_population_progress(
                document["progress"], path=f"{path}.progress"
            ),
            objective_revision=_int_field(
                document, "objective_revision", path=path
            ),
            last_completed_tick=_optional_int_field(
                document, "last_completed_tick", path=path
            ),
            objective_commit_id=_optional_str_field(
                document, "objective_commit_id", path=path
            ),
            event_facts=facts,
        )
    except (TypeError, ValueError) as exc:
        raise _error("invalid_value", path) from exc


def encode_stop_evidence(value: StopEvidence) -> dict[str, Any]:
    return {
        "boundary": encode_generational_boundary(value.boundary),
        "criterion_evaluation_status": value.criterion_evaluation_status.value,
        "failed_stage": value.failed_stage,
        "failure_reason_code": value.failure_reason_code,
        "matched_condition_codes": list(value.matched_condition_codes),
        "matched_criteria": [
            encode_experiment_criterion_identity(item)
            for item in value.matched_criteria
        ],
        "measurements": {
            key: value.measurements[key] for key in sorted(value.measurements)
        },
        "primary_condition_code": value.primary_condition_code,
    }


def decode_stop_evidence(data: object, *, path: str) -> StopEvidence:
    document = _require_exact_keys(data, _STOP_EVIDENCE_KEYS, path=path)
    status_raw = _str_field(document, "criterion_evaluation_status", path=path)
    try:
        status = ExperimentCriterionEvaluationStatus(status_raw)
    except ValueError as exc:
        raise _error("invalid_enum", f"{path}.criterion_evaluation_status") from exc
    codes = tuple(
        _str_value(item, path=f"{path}.matched_condition_codes[{index}]")
        for index, item in enumerate(
            _array(
                document["matched_condition_codes"],
                path=f"{path}.matched_condition_codes",
            )
        )
    )
    criteria = tuple(
        decode_experiment_criterion_identity(
            item, path=f"{path}.matched_criteria[{index}]"
        )
        for index, item in enumerate(
            _array(document["matched_criteria"], path=f"{path}.matched_criteria")
        )
    )
    measurements_raw = document["measurements"]
    if not isinstance(measurements_raw, dict):
        raise _error("invalid_object", f"{path}.measurements")
    measurements = {
        key: _measurement_value(
            value, path=f"{path}.measurements.{key}"
        )
        for key, value in measurements_raw.items()
    }
    try:
        return StopEvidence(
            boundary=decode_generational_boundary(
                document["boundary"], path=f"{path}.boundary"
            ),
            matched_condition_codes=codes,
            primary_condition_code=_str_field(
                document, "primary_condition_code", path=path
            ),
            matched_criteria=criteria,
            criterion_evaluation_status=status,
            failed_stage=_optional_str_field(document, "failed_stage", path=path),
            failure_reason_code=_optional_str_field(
                document, "failure_reason_code", path=path
            ),
            measurements=measurements,
        )
    except (TypeError, ValueError) as exc:
        raise _error("invalid_value", path) from exc


def _str_value(value: object, *, path: str) -> str:
    if type(value) is not str:
        raise _error("invalid_string", path)
    return value


__all__ = [
    "decode_boundary_event_fact",
    "decode_cohort_population_row",
    "decode_experiment_criterion",
    "decode_experiment_criterion_identity",
    "decode_generation_population_row",
    "decode_generational_boundary",
    "decode_generational_run",
    "decode_population_progress",
    "decode_population_threshold",
    "decode_stop_evidence",
    "encode_boundary_event_fact",
    "encode_cohort_population_row",
    "encode_experiment_criterion",
    "encode_experiment_criterion_identity",
    "encode_generation_population_row",
    "encode_generational_boundary",
    "encode_generational_run",
    "encode_population_progress",
    "encode_population_threshold",
    "encode_stop_evidence",
]
