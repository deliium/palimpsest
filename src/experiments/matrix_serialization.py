"""Strict canonical JSON codecs for experiment-matrix-v1 documents."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from typing import Any, Final

from experiments.matrix_models import (
    EXPERIMENT_MATRIX_SCHEMA_VERSION,
    ExperimentMatrixSpec,
    GroupRole,
    MatrixCatalogBase,
    MatrixConstraints,
    MatrixEmbeddedBase,
    MatrixExcludeCombo,
    MatrixExecutionPolicy,
    MatrixFactor,
    MatrixFactorId,
    MatrixFactorLevel,
    MatrixGroupOverlay,
    MatrixValidationError,
    RetryPolicy,
    RunVersionIdentity,
)
from experiments.models import ExperimentSeedMatrix
from simulation.runner_serialization import (
    decode_runner_config,
    encode_runner_config,
)

_LOG: Final[logging.Logger] = logging.getLogger("experiments.matrix_serialization")


class MatrixSerializationError(ValueError):
    """Strict codec failure with stable reason code + JSON path."""

    def __init__(self, code: str, path: str) -> None:
        self.code = code
        self.path = path
        super().__init__(f"{code}:{path}")
        _LOG.error(
            "matrix_serialization_failed",
            extra={"experiment": {"reason_code": code, "path": path}},
        )


def _canonical_dumps(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise MatrixSerializationError("duplicate_key", "$")
        result[key] = value
    return result


def _require_keys(data: Mapping[str, Any], required: set[str], *, path: str) -> None:
    keys = set(data)
    if required - keys:
        raise MatrixSerializationError("missing_field", path)
    if keys - required:
        raise MatrixSerializationError("invalid_fields", path)


def _str_field(data: Mapping[str, Any], key: str, *, path: str) -> str:
    value = data[key]
    if not isinstance(value, str):
        raise MatrixSerializationError("invalid_string", f"{path}.{key}")
    return value


def _bool_field(data: Mapping[str, Any], key: str, *, path: str) -> bool:
    value = data[key]
    if type(value) is not bool:
        raise MatrixSerializationError("invalid_bool", f"{path}.{key}")
    return value


def _int_field(data: Mapping[str, Any], key: str, *, path: str) -> int:
    value = data[key]
    if isinstance(value, bool) or type(value) is not int:
        raise MatrixSerializationError("invalid_int", f"{path}.{key}")
    return value


def encode_matrix_spec_document(spec: ExperimentMatrixSpec) -> dict[str, object]:
    """Encode a matrix spec to a plain JSON-ready mapping (includes execution)."""
    if type(spec) is not ExperimentMatrixSpec:
        raise TypeError("encode_matrix_spec_document requires ExperimentMatrixSpec")
    if type(spec.base) is MatrixEmbeddedBase:
        base_doc: dict[str, object] = {
            "kind": "embedded",
            "runner_config": json.loads(
                encode_runner_config(spec.base.runner_config).decode("utf-8")
            ),
        }
    else:
        base_doc = {
            "kind": "catalog",
            "builder_id": spec.base.builder_id,
            "params": {key: value for key, value in spec.base.params},
        }
    return {
        "matrix_id": spec.matrix_id,
        "schema_version": spec.schema_version,
        "base": base_doc,
        "factors": [
            {
                "factor_id": factor.factor_id.value,
                "levels": [
                    {
                        "level_id": level.level_id,
                        "label_code": level.label_code,
                        "group_role": level.group_role.value,
                    }
                    for level in factor.levels
                ],
            }
            for factor in spec.factors
        ],
        "seed_matrix": {
            "seeds": list(spec.seed_matrix.seeds),
            "replicates_per_seed": spec.seed_matrix.replicates_per_seed,
        },
        "constraints": {
            "exclude_combos": [
                dict(combo.levels) for combo in spec.constraints.exclude_combos
            ]
        },
        "execution": {
            "max_concurrency": spec.execution.max_concurrency,
            "stop_on_first_error": spec.execution.stop_on_first_error,
            "retry_policy": {
                "max_attempts": spec.execution.retry_policy.max_attempts,
                "transient_reason_codes": list(
                    spec.execution.retry_policy.transient_reason_codes
                ),
            },
        },
        "groups": [
            {
                "group_id": group.group_id,
                "level_match": dict(group.level_match),
                "group_role": group.group_role.value,
            }
            for group in spec.groups
        ],
    }


def encode_matrix_spec(spec: ExperimentMatrixSpec) -> bytes:
    """Encode a matrix spec to strict canonical UTF-8 JSON bytes."""
    document = encode_matrix_spec_document(spec)
    _LOG.debug(
        "matrix_spec_encoded",
        extra={
            "experiment": {
                "matrix_id": spec.matrix_id,
                "schema_version": spec.schema_version,
                "factor_count": len(spec.factors),
            }
        },
    )
    return _canonical_dumps(document)


def encode_run_version_identity(identity: RunVersionIdentity) -> bytes:
    """Encode RunVersionIdentity to strict canonical JSON bytes."""
    if type(identity) is not RunVersionIdentity:
        raise TypeError("encode_run_version_identity requires RunVersionIdentity")
    document = {
        "package_version": identity.package_version,
        "runner_schema_version": identity.runner_schema_version,
        "experiment_schema_version": identity.experiment_schema_version,
        "matrix_schema_version": identity.matrix_schema_version,
        "derivation_version": identity.derivation_version,
        "matrix_fingerprint": identity.matrix_fingerprint,
        "cell_fingerprint": identity.cell_fingerprint,
        "config_fingerprint": identity.config_fingerprint,
        "code_revision": identity.code_revision,
    }
    return _canonical_dumps(document)


def decode_run_version_identity(payload: bytes) -> RunVersionIdentity:
    """Decode RunVersionIdentity from strict canonical JSON bytes."""
    if type(payload) is not bytes:
        raise MatrixSerializationError("invalid_payload", "$")
    try:
        decoder = json.JSONDecoder(object_pairs_hook=_reject_duplicate_keys)
        data = decoder.decode(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MatrixSerializationError("invalid_json", "$") from exc
    if not isinstance(data, dict):
        raise MatrixSerializationError("invalid_object", "$")
    required = {
        "package_version",
        "runner_schema_version",
        "experiment_schema_version",
        "matrix_schema_version",
        "derivation_version",
        "matrix_fingerprint",
        "cell_fingerprint",
        "config_fingerprint",
        "code_revision",
    }
    _require_keys(data, required, path="$")
    try:
        return RunVersionIdentity(
            package_version=_str_field(data, "package_version", path="$"),
            runner_schema_version=_str_field(data, "runner_schema_version", path="$"),
            experiment_schema_version=_str_field(
                data, "experiment_schema_version", path="$"
            ),
            matrix_schema_version=_str_field(data, "matrix_schema_version", path="$"),
            derivation_version=_str_field(data, "derivation_version", path="$"),
            matrix_fingerprint=_str_field(data, "matrix_fingerprint", path="$"),
            cell_fingerprint=_str_field(data, "cell_fingerprint", path="$"),
            config_fingerprint=_str_field(data, "config_fingerprint", path="$"),
            code_revision=_str_field(data, "code_revision", path="$"),
        )
    except MatrixValidationError as exc:
        raise MatrixSerializationError(exc.code, "$") from exc


def _decode_seed_matrix(data: Mapping[str, Any], *, path: str) -> ExperimentSeedMatrix:
    _require_keys(data, {"seeds", "replicates_per_seed"}, path=path)
    seeds_raw = data["seeds"]
    if not isinstance(seeds_raw, list):
        raise MatrixSerializationError("invalid_array", f"{path}.seeds")
    seeds: list[int] = []
    for index, seed in enumerate(seeds_raw):
        if isinstance(seed, bool) or type(seed) is not int:
            raise MatrixSerializationError("invalid_int", f"{path}.seeds[{index}]")
        seeds.append(seed)
    return ExperimentSeedMatrix(
        seeds=tuple(seeds),
        replicates_per_seed=_int_field(data, "replicates_per_seed", path=path),
    )


def _decode_retry_policy(data: Mapping[str, Any], *, path: str) -> RetryPolicy:
    _require_keys(data, {"max_attempts", "transient_reason_codes"}, path=path)
    codes_raw = data["transient_reason_codes"]
    if not isinstance(codes_raw, list):
        raise MatrixSerializationError(
            "invalid_array", f"{path}.transient_reason_codes"
        )
    codes: list[str] = []
    for index, code in enumerate(codes_raw):
        if type(code) is not str:
            raise MatrixSerializationError(
                "invalid_string", f"{path}.transient_reason_codes[{index}]"
            )
        codes.append(code)
    try:
        return RetryPolicy(
            max_attempts=_int_field(data, "max_attempts", path=path),
            transient_reason_codes=tuple(codes),
        )
    except MatrixValidationError as exc:
        raise MatrixSerializationError(exc.code, path) from exc


def _decode_execution(data: Mapping[str, Any], *, path: str) -> MatrixExecutionPolicy:
    _require_keys(
        data,
        {"max_concurrency", "stop_on_first_error", "retry_policy"},
        path=path,
    )
    retry_raw = data["retry_policy"]
    if not isinstance(retry_raw, dict):
        raise MatrixSerializationError("invalid_object", f"{path}.retry_policy")
    try:
        return MatrixExecutionPolicy(
            max_concurrency=_int_field(data, "max_concurrency", path=path),
            stop_on_first_error=_bool_field(data, "stop_on_first_error", path=path),
            retry_policy=_decode_retry_policy(retry_raw, path=f"{path}.retry_policy"),
        )
    except MatrixValidationError as exc:
        raise MatrixSerializationError(exc.code, path) from exc


def _decode_factor(data: Mapping[str, Any], *, path: str) -> MatrixFactor:
    _require_keys(data, {"factor_id", "levels"}, path=path)
    factor_id_raw = _str_field(data, "factor_id", path=path)
    try:
        factor_id = MatrixFactorId(factor_id_raw)
    except ValueError as exc:
        raise MatrixSerializationError(
            "unknown_factor_id", f"{path}.factor_id"
        ) from exc
    levels_raw = data["levels"]
    if not isinstance(levels_raw, list) or not levels_raw:
        raise MatrixSerializationError("invalid_array", f"{path}.levels")
    levels: list[MatrixFactorLevel] = []
    for index, level_raw in enumerate(levels_raw):
        level_path = f"{path}.levels[{index}]"
        if not isinstance(level_raw, dict):
            raise MatrixSerializationError("invalid_object", level_path)
        _require_keys(
            level_raw, {"level_id", "label_code", "group_role"}, path=level_path
        )
        role_raw = _str_field(level_raw, "group_role", path=level_path)
        try:
            role = GroupRole(role_raw)
        except ValueError as exc:
            raise MatrixSerializationError(
                "unknown_group_role", f"{level_path}.group_role"
            ) from exc
        try:
            levels.append(
                MatrixFactorLevel(
                    level_id=_str_field(level_raw, "level_id", path=level_path),
                    label_code=_str_field(level_raw, "label_code", path=level_path),
                    group_role=role,
                )
            )
        except (MatrixValidationError, ValueError) as exc:
            code = getattr(exc, "code", "invalid_level")
            raise MatrixSerializationError(code, level_path) from exc
    try:
        return MatrixFactor(factor_id=factor_id, levels=tuple(levels))
    except MatrixValidationError as exc:
        raise MatrixSerializationError(exc.code, path) from exc


def _decode_base(
    data: Mapping[str, Any], *, path: str
) -> MatrixEmbeddedBase | MatrixCatalogBase:
    if "kind" not in data:
        raise MatrixSerializationError("missing_field", f"{path}.kind")
    kind = _str_field(data, "kind", path=path)
    if kind == "embedded":
        _require_keys(data, {"kind", "runner_config"}, path=path)
        config_raw = data["runner_config"]
        if not isinstance(config_raw, dict):
            raise MatrixSerializationError("invalid_object", f"{path}.runner_config")
        try:
            config = decode_runner_config(_canonical_dumps(config_raw))
        except Exception as exc:
            raise MatrixSerializationError(
                "invalid_runner_config", f"{path}.runner_config"
            ) from exc
        return MatrixEmbeddedBase(runner_config=config)
    if kind == "catalog":
        _require_keys(data, {"kind", "builder_id", "params"}, path=path)
        params_raw = data["params"]
        if not isinstance(params_raw, dict):
            raise MatrixSerializationError("invalid_object", f"{path}.params")
        try:
            return MatrixCatalogBase(
                builder_id=_str_field(data, "builder_id", path=path),
                params=tuple(sorted((str(k), v) for k, v in params_raw.items())),
            )
        except (MatrixValidationError, ValueError) as exc:
            code = getattr(exc, "code", "invalid_catalog_base")
            raise MatrixSerializationError(code, path) from exc
    raise MatrixSerializationError("unknown_base_kind", f"{path}.kind")


def _decode_constraints(data: Mapping[str, Any], *, path: str) -> MatrixConstraints:
    allowed = {"exclude_combos"}
    keys = set(data)
    if keys - allowed:
        raise MatrixSerializationError("unknown_constraint_ops", path)
    _require_keys(data, {"exclude_combos"}, path=path)
    combos_raw = data["exclude_combos"]
    if not isinstance(combos_raw, list):
        raise MatrixSerializationError("invalid_array", f"{path}.exclude_combos")
    combos: list[MatrixExcludeCombo] = []
    for index, combo_raw in enumerate(combos_raw):
        combo_path = f"{path}.exclude_combos[{index}]"
        if not isinstance(combo_raw, dict):
            raise MatrixSerializationError("invalid_object", combo_path)
        try:
            items = tuple((str(k), str(v)) for k, v in combo_raw.items())
            combos.append(MatrixExcludeCombo(levels=items))
        except MatrixValidationError as exc:
            raise MatrixSerializationError(exc.code, combo_path) from exc
    return MatrixConstraints(exclude_combos=tuple(combos))


def _decode_groups(
    raw: object, *, path: str
) -> tuple[MatrixGroupOverlay, ...]:
    if not isinstance(raw, list):
        raise MatrixSerializationError("invalid_array", path)
    groups: list[MatrixGroupOverlay] = []
    for index, group_raw in enumerate(raw):
        group_path = f"{path}[{index}]"
        if not isinstance(group_raw, dict):
            raise MatrixSerializationError("invalid_object", group_path)
        _require_keys(
            group_raw, {"group_id", "level_match", "group_role"}, path=group_path
        )
        match_raw = group_raw["level_match"]
        if not isinstance(match_raw, dict):
            raise MatrixSerializationError(
                "invalid_object", f"{group_path}.level_match"
            )
        role_raw = _str_field(group_raw, "group_role", path=group_path)
        try:
            role = GroupRole(role_raw)
        except ValueError as exc:
            raise MatrixSerializationError(
                "unknown_group_role", f"{group_path}.group_role"
            ) from exc
        try:
            groups.append(
                MatrixGroupOverlay(
                    group_id=_str_field(group_raw, "group_id", path=group_path),
                    level_match=tuple(
                        (str(k), str(v)) for k, v in match_raw.items()
                    ),
                    group_role=role,
                )
            )
        except (MatrixValidationError, ValueError) as exc:
            code = getattr(exc, "code", "invalid_group")
            raise MatrixSerializationError(code, group_path) from exc
    return tuple(groups)


def decode_matrix_spec(payload: bytes) -> ExperimentMatrixSpec:
    """Decode strict canonical matrix spec bytes."""
    if type(payload) is not bytes:
        raise MatrixSerializationError("invalid_payload", "$")
    try:
        decoder = json.JSONDecoder(object_pairs_hook=_reject_duplicate_keys)
        data = decoder.decode(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MatrixSerializationError("invalid_json", "$") from exc
    if not isinstance(data, dict):
        raise MatrixSerializationError("invalid_object", "$")
    required = {
        "matrix_id",
        "schema_version",
        "base",
        "factors",
        "seed_matrix",
        "constraints",
        "execution",
        "groups",
    }
    _require_keys(data, required, path="$")
    schema_version = _str_field(data, "schema_version", path="$")
    if schema_version != EXPERIMENT_MATRIX_SCHEMA_VERSION:
        raise MatrixSerializationError("unsupported_matrix_schema", "$.schema_version")
    base_raw = data["base"]
    if not isinstance(base_raw, dict):
        raise MatrixSerializationError("invalid_object", "$.base")
    factors_raw = data["factors"]
    if not isinstance(factors_raw, list):
        raise MatrixSerializationError("invalid_array", "$.factors")
    decoded_factors: list[MatrixFactor] = []
    for index, item in enumerate(factors_raw):
        if not isinstance(item, dict):
            raise MatrixSerializationError("invalid_object", f"$.factors[{index}]")
        decoded_factors.append(_decode_factor(item, path=f"$.factors[{index}]"))
    seed_raw = data["seed_matrix"]
    if not isinstance(seed_raw, dict):
        raise MatrixSerializationError("invalid_object", "$.seed_matrix")
    constraints_raw = data["constraints"]
    if not isinstance(constraints_raw, dict):
        raise MatrixSerializationError("invalid_object", "$.constraints")
    execution_raw = data["execution"]
    if not isinstance(execution_raw, dict):
        raise MatrixSerializationError("invalid_object", "$.execution")
    try:
        spec = ExperimentMatrixSpec(
            matrix_id=_str_field(data, "matrix_id", path="$"),
            schema_version=schema_version,
            base=_decode_base(base_raw, path="$.base"),
            factors=tuple(decoded_factors),
            seed_matrix=_decode_seed_matrix(seed_raw, path="$.seed_matrix"),
            constraints=_decode_constraints(constraints_raw, path="$.constraints"),
            execution=_decode_execution(execution_raw, path="$.execution"),
            groups=_decode_groups(data["groups"], path="$.groups"),
        )
    except MatrixValidationError as exc:
        raise MatrixSerializationError(exc.code, "$") from exc
    _LOG.debug(
        "matrix_spec_decoded",
        extra={
            "experiment": {
                "matrix_id": spec.matrix_id,
                "schema_version": spec.schema_version,
                "factor_count": len(spec.factors),
            }
        },
    )
    return spec


__all__ = [
    "MatrixSerializationError",
    "decode_matrix_spec",
    "decode_run_version_identity",
    "encode_matrix_spec",
    "encode_matrix_spec_document",
    "encode_run_version_identity",
]
