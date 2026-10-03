"""Immutable experiment-matrix-v1 contracts and fingerprints.

Matrix documents expand into ``experiment-definition-v1`` arms. Factor ids and
control/treatment labels are researcher metadata only — never world roles.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from experiments.models import ExperimentSeedMatrix
from simulation.runner_models import RunnerStopReasonCode, SimulationRunnerConfig
from simulation.runner_serialization import runner_config_fingerprint
from world.identifiers import require_stable_id

_LOG: Final[logging.Logger] = logging.getLogger("experiments.matrix_models")

EXPERIMENT_MATRIX_SCHEMA_VERSION: Final[str] = "experiment-matrix-v1"

DEFAULT_SUCCESS_STOP_REASONS: Final[tuple[RunnerStopReasonCode, ...]] = (
    RunnerStopReasonCode.MAX_TICKS,
    RunnerStopReasonCode.ALL_AGENTS_TERMINAL,
    RunnerStopReasonCode.INJECTED_STOP,
)

# Locked level-id tables for the v1 factor registry (Task 2 applies them).
LOCKED_FACTOR_LEVEL_IDS: Final[Mapping[str, frozenset[str]]] = {
    "memory_type": frozenset({"reference", "reconstructive", "reconstructive_v2"}),
    "mortality": frozenset({"disabled", "enabled"}),
    "imagination": frozenset({"disabled", "enabled"}),
    "reflection": frozenset({"disabled", "deterministic"}),
    "tom": frozenset({"off", "on"}),
    "resource_scarcity": frozenset({"scarce", "abundant"}),
    "seasonality": frozenset({"off", "on"}),
    "cognitive_budget": frozenset({"disabled", "low_cost", "high_cost"}),
}


class MatrixFactorId(StrEnum):
    """Closed research axes for experiment-matrix-v1."""

    MEMORY_TYPE = "memory_type"
    MORTALITY = "mortality"
    IMAGINATION = "imagination"
    REFLECTION = "reflection"
    TOM = "tom"
    RESOURCE_SCARCITY = "resource_scarcity"
    SEASONALITY = "seasonality"
    COGNITIVE_BUDGET = "cognitive_budget"


class GroupRole(StrEnum):
    """Researcher-facing control/treatment/neutral labels (not world roles)."""

    CONTROL = "control"
    TREATMENT = "treatment"
    NEUTRAL = "neutral"


class MatrixCellState(StrEnum):
    """Filesystem-manifest cell lifecycle states."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED_VALID = "skipped_valid"


class MatrixValidationError(ValueError):
    """Fail-closed matrix validation with a stable reason code."""

    def __init__(self, code: str, message: str = "") -> None:
        self.code = code
        detail = message or code
        super().__init__(detail)
        _LOG.error(
            "matrix_validation_failed",
            extra={"experiment": {"reason_code": code}},
        )


def _canonical_dumps(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _require_ordered_mapping(
    name: str, value: object
) -> tuple[tuple[str, str], ...]:
    if isinstance(value, (set, frozenset)):
        raise MatrixValidationError("unordered_mapping", f"{name} must be ordered")
    if not isinstance(value, Mapping):
        raise MatrixValidationError("invalid_mapping", f"{name} must be a mapping")
    items: list[tuple[str, str]] = []
    for key, raw in value.items():
        if type(key) is not str or type(raw) is not str:
            raise MatrixValidationError(
                "invalid_mapping_entry",
                f"{name} entries must be str→str",
            )
        items.append((key, raw))
    return tuple(items)


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Retry only configured transient reason codes (not validation errors)."""

    max_attempts: int = 1
    transient_reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.max_attempts) is not int or self.max_attempts < 1:
            raise MatrixValidationError(
                "invalid_retry_max_attempts",
                "max_attempts must be a positive int",
            )
        if isinstance(self.transient_reason_codes, (set, frozenset)):
            raise MatrixValidationError(
                "unordered_transient_codes",
                "transient_reason_codes must be ordered",
            )
        if isinstance(self.transient_reason_codes, (str, bytes)) or not isinstance(
            self.transient_reason_codes, Sequence
        ):
            raise MatrixValidationError(
                "invalid_transient_codes",
                "transient_reason_codes must be an ordered sequence",
            )
        codes = tuple(self.transient_reason_codes)
        seen: set[str] = set()
        for code in codes:
            if type(code) is not str or not code:
                raise MatrixValidationError(
                    "invalid_transient_code",
                    "transient reason codes must be non-empty str",
                )
            if code in seen:
                raise MatrixValidationError(
                    "duplicate_transient_code",
                    "transient reason codes must be unique",
                )
            seen.add(code)
        object.__setattr__(self, "transient_reason_codes", codes)


@dataclass(frozen=True, slots=True)
class MatrixExecutionPolicy:
    """Process-local concurrency and failure policy for a matrix batch."""

    max_concurrency: int = 1
    retry_policy: RetryPolicy = RetryPolicy()
    stop_on_first_error: bool = False

    def __post_init__(self) -> None:
        if type(self.max_concurrency) is not int or self.max_concurrency < 1:
            raise MatrixValidationError(
                "invalid_max_concurrency",
                "max_concurrency must be a positive int",
            )
        if type(self.retry_policy) is not RetryPolicy:
            raise TypeError("retry_policy must be RetryPolicy")
        if type(self.stop_on_first_error) is not bool:
            raise MatrixValidationError(
                "invalid_stop_on_first_error",
                "stop_on_first_error must be bool",
            )


@dataclass(frozen=True, slots=True)
class MatrixFactorLevel:
    """One closed level on a matrix factor axis."""

    level_id: str
    label_code: str
    group_role: GroupRole = GroupRole.NEUTRAL

    def __post_init__(self) -> None:
        require_stable_id("level_id", self.level_id)
        require_stable_id("label_code", self.label_code)
        if type(self.group_role) is not GroupRole:
            raise TypeError("group_role must be GroupRole")


@dataclass(frozen=True, slots=True)
class MatrixFactor:
    """Ordered factor axis with at least one locked level."""

    factor_id: MatrixFactorId
    levels: tuple[MatrixFactorLevel, ...]

    def __post_init__(self) -> None:
        if type(self.factor_id) is not MatrixFactorId:
            raise TypeError("factor_id must be MatrixFactorId")
        if isinstance(self.levels, (set, frozenset)):
            raise MatrixValidationError("unordered_levels", "levels must be ordered")
        if isinstance(self.levels, (str, bytes)) or not isinstance(
            self.levels, Sequence
        ):
            raise MatrixValidationError(
                "invalid_levels",
                "levels must be an ordered sequence",
            )
        levels = tuple(self.levels)
        if not levels:
            raise MatrixValidationError("empty_levels", "levels must be non-empty")
        allowed = LOCKED_FACTOR_LEVEL_IDS[self.factor_id.value]
        seen: set[str] = set()
        for level in levels:
            if type(level) is not MatrixFactorLevel:
                raise TypeError("levels entries must be MatrixFactorLevel")
            if level.level_id not in allowed:
                raise MatrixValidationError(
                    "unknown_level_id",
                    f"level_id {level.level_id!r} not locked for {self.factor_id}",
                )
            if level.level_id in seen:
                raise MatrixValidationError(
                    "duplicate_level_id",
                    "level_id must be unique within a factor",
                )
            seen.add(level.level_id)
        object.__setattr__(self, "levels", levels)


@dataclass(frozen=True, slots=True)
class MatrixExcludeCombo:
    """One exclude_combos entry: factor_id → level_id partial match."""

    levels: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        if not self.levels:
            raise MatrixValidationError(
                "empty_exclude_combo",
                "exclude_combos entries must be non-empty",
            )
        seen: set[str] = set()
        for factor_id, level_id in self.levels:
            if type(factor_id) is not str or type(level_id) is not str:
                raise MatrixValidationError(
                    "invalid_exclude_combo_entry",
                    "exclude_combos entries must be str→str",
                )
            try:
                MatrixFactorId(factor_id)
            except ValueError as exc:
                raise MatrixValidationError(
                    "unknown_constraint_factor",
                    f"unknown factor in exclude_combos: {factor_id}",
                ) from exc
            if factor_id in seen:
                raise MatrixValidationError(
                    "duplicate_exclude_factor",
                    "exclude_combos entry has duplicate factor keys",
                )
            seen.add(factor_id)
            allowed = LOCKED_FACTOR_LEVEL_IDS[factor_id]
            if level_id not in allowed:
                raise MatrixValidationError(
                    "unknown_constraint_level",
                    f"unknown level {level_id!r} for factor {factor_id}",
                )
        object.__setattr__(
            self,
            "levels",
            tuple(sorted(self.levels, key=lambda item: item[0])),
        )


@dataclass(frozen=True, slots=True)
class MatrixConstraints:
    """Locked constraint DSL: exclude_combos only."""

    exclude_combos: tuple[MatrixExcludeCombo, ...] = ()

    def __post_init__(self) -> None:
        if isinstance(self.exclude_combos, (set, frozenset)):
            raise MatrixValidationError(
                "unordered_exclude_combos",
                "exclude_combos must be ordered",
            )
        if isinstance(self.exclude_combos, (str, bytes)) or not isinstance(
            self.exclude_combos, Sequence
        ):
            raise MatrixValidationError(
                "invalid_exclude_combos",
                "exclude_combos must be an ordered sequence",
            )
        combos = tuple(self.exclude_combos)
        for combo in combos:
            if type(combo) is not MatrixExcludeCombo:
                raise TypeError("exclude_combos entries must be MatrixExcludeCombo")
        object.__setattr__(self, "exclude_combos", combos)


@dataclass(frozen=True, slots=True)
class MatrixGroupOverlay:
    """Optional named overlay that overrides derived cell group_role."""

    group_id: str
    level_match: tuple[tuple[str, str], ...]
    group_role: GroupRole

    def __post_init__(self) -> None:
        require_stable_id("group_id", self.group_id)
        if type(self.group_role) is not GroupRole:
            raise TypeError("group_role must be GroupRole")
        if not self.level_match:
            raise MatrixValidationError(
                "empty_group_match",
                "groups level_match must be non-empty",
            )
        seen: set[str] = set()
        for factor_id, level_id in self.level_match:
            try:
                MatrixFactorId(factor_id)
            except ValueError as exc:
                raise MatrixValidationError(
                    "unknown_group_factor",
                    f"unknown factor in groups: {factor_id}",
                ) from exc
            if factor_id in seen:
                raise MatrixValidationError(
                    "duplicate_group_factor",
                    "groups level_match has duplicate factor keys",
                )
            seen.add(factor_id)
            if level_id not in LOCKED_FACTOR_LEVEL_IDS[factor_id]:
                raise MatrixValidationError(
                    "unknown_group_level",
                    f"unknown level {level_id!r} for factor {factor_id}",
                )
        object.__setattr__(
            self,
            "level_match",
            tuple(sorted(self.level_match, key=lambda item: item[0])),
        )


@dataclass(frozen=True, slots=True)
class MatrixEmbeddedBase:
    """Base runner config embedded as canonical runner JSON."""

    runner_config: SimulationRunnerConfig

    def __post_init__(self) -> None:
        if type(self.runner_config) is not SimulationRunnerConfig:
            raise TypeError("runner_config must be SimulationRunnerConfig")


@dataclass(frozen=True, slots=True)
class MatrixCatalogBase:
    """Reference to a catalog base builder id plus frozen params."""

    builder_id: str
    params: tuple[tuple[str, object], ...] = ()

    def __post_init__(self) -> None:
        require_stable_id("builder_id", self.builder_id)
        if isinstance(self.params, (set, frozenset)):
            raise MatrixValidationError("unordered_params", "params must be ordered")
        if not isinstance(self.params, Sequence) or isinstance(
            self.params, (str, bytes)
        ):
            # Allow Mapping at construction via helper; store as ordered tuples.
            if isinstance(self.params, Mapping):
                items = tuple(sorted((str(k), v) for k, v in self.params.items()))
                object.__setattr__(self, "params", items)
                return
            raise MatrixValidationError("invalid_params", "params must be ordered")
        params = tuple(self.params)
        seen: set[str] = set()
        for item in params:
            if not isinstance(item, tuple) or len(item) != 2:
                raise MatrixValidationError(
                    "invalid_param_entry",
                    "params entries must be (key, value)",
                )
            key, _value = item
            if type(key) is not str or not key:
                raise MatrixValidationError(
                    "invalid_param_key",
                    "param keys must be non-empty str",
                )
            if key in seen:
                raise MatrixValidationError(
                    "duplicate_param_key",
                    "param keys must be unique",
                )
            seen.add(key)
        object.__setattr__(self, "params", params)


MatrixBase = MatrixEmbeddedBase | MatrixCatalogBase


@dataclass(frozen=True, slots=True)
class ExperimentMatrixSpec:
    """Configuration-driven multi-factor experiment matrix (experiment-matrix-v1)."""

    matrix_id: str
    schema_version: str
    base: MatrixBase
    factors: tuple[MatrixFactor, ...]
    seed_matrix: ExperimentSeedMatrix
    constraints: MatrixConstraints = MatrixConstraints()
    execution: MatrixExecutionPolicy = MatrixExecutionPolicy()
    groups: tuple[MatrixGroupOverlay, ...] = ()

    def __post_init__(self) -> None:
        require_stable_id("matrix_id", self.matrix_id)
        if self.schema_version != EXPERIMENT_MATRIX_SCHEMA_VERSION:
            raise MatrixValidationError(
                "unsupported_matrix_schema",
                "unsupported experiment matrix schema_version",
            )
        if type(self.base) not in (MatrixEmbeddedBase, MatrixCatalogBase):
            raise TypeError("base must be MatrixEmbeddedBase or MatrixCatalogBase")
        if type(self.seed_matrix) is not ExperimentSeedMatrix:
            raise TypeError("seed_matrix must be ExperimentSeedMatrix")
        if type(self.constraints) is not MatrixConstraints:
            raise TypeError("constraints must be MatrixConstraints")
        if type(self.execution) is not MatrixExecutionPolicy:
            raise TypeError("execution must be MatrixExecutionPolicy")
        if isinstance(self.factors, (set, frozenset)):
            raise MatrixValidationError("unordered_factors", "factors must be ordered")
        if isinstance(self.factors, (str, bytes)) or not isinstance(
            self.factors, Sequence
        ):
            raise MatrixValidationError(
                "invalid_factors",
                "factors must be an ordered sequence",
            )
        factors = tuple(self.factors)
        if not factors:
            raise MatrixValidationError("empty_factors", "factors must be non-empty")
        seen_factors: set[MatrixFactorId] = set()
        for factor in factors:
            if type(factor) is not MatrixFactor:
                raise TypeError("factors entries must be MatrixFactor")
            if factor.factor_id in seen_factors:
                raise MatrixValidationError(
                    "duplicate_factor_id",
                    "factor_id must be unique within a matrix",
                )
            seen_factors.add(factor.factor_id)
        object.__setattr__(self, "factors", factors)
        if isinstance(self.groups, (set, frozenset)):
            raise MatrixValidationError("unordered_groups", "groups must be ordered")
        if isinstance(self.groups, (str, bytes)) or not isinstance(
            self.groups, Sequence
        ):
            raise MatrixValidationError(
                "invalid_groups",
                "groups must be an ordered sequence",
            )
        groups = tuple(self.groups)
        seen_groups: set[str] = set()
        for group in groups:
            if type(group) is not MatrixGroupOverlay:
                raise TypeError("groups entries must be MatrixGroupOverlay")
            if group.group_id in seen_groups:
                raise MatrixValidationError(
                    "duplicate_group_id",
                    "group_id must be unique",
                )
            seen_groups.add(group.group_id)
        object.__setattr__(self, "groups", groups)
        _LOG.debug(
            "matrix_spec_validated",
            extra={
                "experiment": {
                    "matrix_id": self.matrix_id,
                    "schema_version": self.schema_version,
                    "factor_count": len(factors),
                    "level_count": sum(len(f.levels) for f in factors),
                    "group_count": len(groups),
                    "max_concurrency": self.execution.max_concurrency,
                }
            },
        )


@dataclass(frozen=True, slots=True)
class MatrixCell:
    """One expanded matrix cell (factor combo x seed x replicate)."""

    cell_id: str
    condition_id: str
    factor_levels: tuple[tuple[str, str], ...]
    group_role: GroupRole
    seed: int
    seed_ordinal: int
    replicate_index: int
    cell_fingerprint: str
    config_fingerprint: str

    def __post_init__(self) -> None:
        require_stable_id("cell_id", self.cell_id)
        require_stable_id("condition_id", self.condition_id)
        if type(self.group_role) is not GroupRole:
            raise TypeError("group_role must be GroupRole")
        if type(self.seed) is not int or isinstance(self.seed, bool) or self.seed < 0:
            raise MatrixValidationError("invalid_seed", "seed must be non-negative int")
        if (
            type(self.seed_ordinal) is not int
            or isinstance(self.seed_ordinal, bool)
            or self.seed_ordinal < 0
        ):
            raise MatrixValidationError(
                "invalid_seed_ordinal",
                "seed_ordinal must be non-negative int",
            )
        if (
            type(self.replicate_index) is not int
            or isinstance(self.replicate_index, bool)
            or self.replicate_index < 0
        ):
            raise MatrixValidationError(
                "invalid_replicate_index",
                "replicate_index must be non-negative int",
            )
        if type(self.cell_fingerprint) is not str or len(self.cell_fingerprint) != 64:
            raise MatrixValidationError(
                "invalid_cell_fingerprint",
                "cell_fingerprint must be sha256 hex",
            )
        if (
            type(self.config_fingerprint) is not str
            or len(self.config_fingerprint) != 64
        ):
            raise MatrixValidationError(
                "invalid_config_fingerprint",
                "config_fingerprint must be sha256 hex",
            )
        levels = _require_ordered_mapping("factor_levels", dict(self.factor_levels))
        object.__setattr__(self, "factor_levels", levels)


@dataclass(frozen=True, slots=True)
class RunVersionIdentity:
    """Frozen per-run version identity (metadata only; never agent-visible)."""

    package_version: str
    runner_schema_version: str
    experiment_schema_version: str
    matrix_schema_version: str
    derivation_version: str
    matrix_fingerprint: str
    cell_fingerprint: str
    config_fingerprint: str
    code_revision: str = ""

    def __post_init__(self) -> None:
        for name in (
            "package_version",
            "runner_schema_version",
            "experiment_schema_version",
            "matrix_schema_version",
            "derivation_version",
        ):
            value = getattr(self, name)
            if type(value) is not str or not value:
                raise MatrixValidationError(
                    "invalid_version_identity_field",
                    f"{name} must be a non-empty str",
                )
        for name in (
            "matrix_fingerprint",
            "cell_fingerprint",
            "config_fingerprint",
        ):
            value = getattr(self, name)
            if type(value) is not str or len(value) != 64:
                raise MatrixValidationError(
                    "invalid_version_fingerprint",
                    f"{name} must be sha256 hex",
                )
        if type(self.code_revision) is not str:
            raise MatrixValidationError(
                "invalid_code_revision",
                "code_revision must be str",
            )
        if self.matrix_schema_version != EXPERIMENT_MATRIX_SCHEMA_VERSION:
            raise MatrixValidationError(
                "unsupported_matrix_schema",
                "RunVersionIdentity.matrix_schema_version mismatch",
            )


def factor_levels_document(
    levels: Sequence[tuple[str, str]],
) -> list[dict[str, str]]:
    """Canonical ordered factor-level pairs for fingerprints."""
    return [{"factor_id": fid, "level_id": lid} for fid, lid in levels]


def cell_factor_fingerprint(
    *,
    condition_id: str,
    factor_levels: Sequence[tuple[str, str]],
    group_role: GroupRole,
) -> str:
    """SHA-256 of canonical cell factor identity (no seeds)."""
    document = {
        "condition_id": condition_id,
        "factor_levels": factor_levels_document(factor_levels),
        "group_role": group_role.value,
    }
    digest = _sha256_hex(_canonical_dumps(document))
    _LOG.debug(
        "cell_factor_fingerprint",
        extra={
            "experiment": {
                "condition_id_prefix": condition_id[:32],
                "fingerprint_prefix": digest[:12],
            }
        },
    )
    return digest


def matrix_identity_document(spec: ExperimentMatrixSpec) -> dict[str, object]:
    """Canonical matrix identity document (excludes execution runtime policy)."""
    if type(spec) is not ExperimentMatrixSpec:
        raise TypeError("matrix_identity_document requires ExperimentMatrixSpec")
    if type(spec.base) is MatrixEmbeddedBase:
        base_doc: dict[str, object] = {
            "kind": "embedded",
            "config_fingerprint": runner_config_fingerprint(spec.base.runner_config),
        }
    else:
        base_doc = {
            "kind": "catalog",
            "builder_id": spec.base.builder_id,
            "params": [{"key": k, "value": v} for k, v in spec.base.params],
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
        "groups": [
            {
                "group_id": group.group_id,
                "level_match": dict(group.level_match),
                "group_role": group.group_role.value,
            }
            for group in spec.groups
        ],
    }


def matrix_spec_fingerprint(spec: ExperimentMatrixSpec) -> str:
    """SHA-256 of canonical matrix identity (excludes execution runtime state)."""
    document = matrix_identity_document(spec)
    digest = _sha256_hex(_canonical_dumps(document))
    _LOG.debug(
        "matrix_spec_fingerprint",
        extra={
            "experiment": {
                "matrix_id": spec.matrix_id,
                "fingerprint_prefix": digest[:12],
            }
        },
    )
    return digest


def config_fingerprint_for_cell(config: SimulationRunnerConfig) -> str:
    """Delegate to runner config fingerprint (exact-version identity)."""
    if type(config) is not SimulationRunnerConfig:
        raise TypeError("config must be SimulationRunnerConfig")
    return runner_config_fingerprint(config)


__all__ = [
    "DEFAULT_SUCCESS_STOP_REASONS",
    "EXPERIMENT_MATRIX_SCHEMA_VERSION",
    "LOCKED_FACTOR_LEVEL_IDS",
    "ExperimentMatrixSpec",
    "GroupRole",
    "MatrixBase",
    "MatrixCatalogBase",
    "MatrixCell",
    "MatrixCellState",
    "MatrixConstraints",
    "MatrixEmbeddedBase",
    "MatrixExcludeCombo",
    "MatrixExecutionPolicy",
    "MatrixFactor",
    "MatrixFactorId",
    "MatrixFactorLevel",
    "MatrixGroupOverlay",
    "MatrixValidationError",
    "RetryPolicy",
    "RunVersionIdentity",
    "cell_factor_fingerprint",
    "config_fingerprint_for_cell",
    "factor_levels_document",
    "matrix_identity_document",
    "matrix_spec_fingerprint",
]
