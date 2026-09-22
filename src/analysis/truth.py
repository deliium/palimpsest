"""Claim-level truth contracts for metric evaluation only.

Truth specifications never enter cognition, runner configuration, prompts, or
memory formation. Domain and simulation packages must not import this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "CLAIM_TRUTH_SCHEMA_VERSION",
    "ClaimExpectedValue",
    "ClaimTruthSpec",
    "ClaimValueKind",
    "TruthEvaluatorPolicy",
]

CLAIM_TRUTH_SCHEMA_VERSION: Final[str] = "claim-truth-v1"


class ClaimValueKind(StrEnum):
    """Closed set of typed expected-value shapes for claim evaluation."""

    BOOLEAN = "boolean"
    CATEGORICAL = "categorical"
    NUMERIC = "numeric"


class TruthEvaluatorPolicy(StrEnum):
    """How a metric evaluator compares observed claims to expected values."""

    EXACT_MATCH = "exact_match"
    NUMERIC_TOLERANCE = "numeric_tolerance"
    CATEGORICAL_MEMBERSHIP = "categorical_membership"


@dataclass(frozen=True, slots=True)
class ClaimExpectedValue:
    """Typed expected value payload for one claim identity."""

    kind: ClaimValueKind
    boolean_value: bool | None = None
    categorical_value: str | None = None
    numeric_value: float | None = None

    def __post_init__(self) -> None:
        if type(self.kind) is not ClaimValueKind:
            raise TypeError("ClaimExpectedValue.kind: invalid_type")
        if self.kind is ClaimValueKind.BOOLEAN:
            if type(self.boolean_value) is not bool:
                raise TypeError("ClaimExpectedValue.boolean_value: required_bool")
            if self.categorical_value is not None or self.numeric_value is not None:
                raise ValueError("ClaimExpectedValue: boolean_exclusive")
        elif self.kind is ClaimValueKind.CATEGORICAL:
            if self.categorical_value is None:
                raise ValueError("ClaimExpectedValue.categorical_value: required")
            object.__setattr__(
                self,
                "categorical_value",
                require_stable_id(
                    "ClaimExpectedValue.categorical_value", self.categorical_value
                ),
            )
            if self.boolean_value is not None or self.numeric_value is not None:
                raise ValueError("ClaimExpectedValue: categorical_exclusive")
        elif self.kind is ClaimValueKind.NUMERIC:
            if type(self.numeric_value) is not float:
                raise TypeError("ClaimExpectedValue.numeric_value: required_float")
            if self.numeric_value != self.numeric_value or self.numeric_value in (
                float("inf"),
                float("-inf"),
            ):
                raise ValueError("ClaimExpectedValue.numeric_value: non_finite")
            if self.boolean_value is not None or self.categorical_value is not None:
                raise ValueError("ClaimExpectedValue: numeric_exclusive")
        else:  # pragma: no cover - closed enum
            raise ValueError("ClaimExpectedValue.kind: unknown")

    def __repr__(self) -> str:
        return f"ClaimExpectedValue(kind={self.kind.value!r})"


@dataclass(frozen=True, slots=True)
class ClaimTruthSpec:
    """Versioned claim identity with typed expected value and evaluator policy.

    Analysis-only. Never inject into agents, cognition, memory, or prompts.
    """

    claim_id: str
    schema_version: str
    expected: ClaimExpectedValue
    valid_from_tick: int
    valid_to_tick: int | None
    unit: str | None
    tolerance: float | None
    evaluator_policy: TruthEvaluatorPolicy
    intervention_id: str | None
    objective_provenance: str | None
    concept_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "claim_id",
            require_stable_id("ClaimTruthSpec.claim_id", self.claim_id),
        )
        object.__setattr__(
            self,
            "schema_version",
            require_stable_id("ClaimTruthSpec.schema_version", self.schema_version),
        )
        if self.schema_version != CLAIM_TRUTH_SCHEMA_VERSION:
            raise ValueError("ClaimTruthSpec.schema_version: unsupported")
        if type(self.expected) is not ClaimExpectedValue:
            raise TypeError("ClaimTruthSpec.expected: invalid_type")
        object.__setattr__(
            self,
            "valid_from_tick",
            require_exact_nonneg_int(
                "ClaimTruthSpec.valid_from_tick", self.valid_from_tick
            ),
        )
        if self.valid_to_tick is not None:
            object.__setattr__(
                self,
                "valid_to_tick",
                require_exact_nonneg_int(
                    "ClaimTruthSpec.valid_to_tick", self.valid_to_tick
                ),
            )
            if self.valid_to_tick < self.valid_from_tick:
                raise ValueError("ClaimTruthSpec: invalid_validity_interval")
        if self.unit is not None:
            object.__setattr__(
                self,
                "unit",
                require_stable_id("ClaimTruthSpec.unit", self.unit),
            )
        if self.tolerance is not None:
            if type(self.tolerance) is not float:
                raise TypeError("ClaimTruthSpec.tolerance: invalid_type")
            if (
                self.tolerance != self.tolerance
                or self.tolerance in (float("inf"), float("-inf"))
                or self.tolerance < 0.0
            ):
                raise ValueError("ClaimTruthSpec.tolerance: invalid")
        if type(self.evaluator_policy) is not TruthEvaluatorPolicy:
            raise TypeError("ClaimTruthSpec.evaluator_policy: invalid_type")
        if (
            self.evaluator_policy is TruthEvaluatorPolicy.NUMERIC_TOLERANCE
            and self.tolerance is None
        ):
            raise ValueError("ClaimTruthSpec.tolerance: required_for_policy")
        if (
            self.evaluator_policy is TruthEvaluatorPolicy.NUMERIC_TOLERANCE
            and self.expected.kind is not ClaimValueKind.NUMERIC
        ):
            raise ValueError("ClaimTruthSpec.evaluator_policy: numeric_required")
        if self.intervention_id is not None:
            object.__setattr__(
                self,
                "intervention_id",
                require_stable_id(
                    "ClaimTruthSpec.intervention_id", self.intervention_id
                ),
            )
        if self.objective_provenance is not None:
            object.__setattr__(
                self,
                "objective_provenance",
                require_stable_id(
                    "ClaimTruthSpec.objective_provenance", self.objective_provenance
                ),
            )
        codes = tuple(
            require_stable_id(f"ClaimTruthSpec.concept_codes[{index}]", code)
            for index, code in enumerate(self.concept_codes)
        )
        object.__setattr__(self, "concept_codes", codes)

    def __repr__(self) -> str:
        return (
            f"ClaimTruthSpec(claim_id={self.claim_id!r}, "
            f"schema_version={self.schema_version!r}, "
            f"kind={self.expected.kind.value!r}, "
            f"valid_from_tick={self.valid_from_tick}, "
            f"valid_to_tick={self.valid_to_tick!r}, "
            f"evaluator_policy={self.evaluator_policy.value!r}, "
            f"intervention_id={self.intervention_id!r}, "
            f"concept_count={len(self.concept_codes)})"
        )
