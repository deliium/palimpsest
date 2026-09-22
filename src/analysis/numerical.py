"""Deterministic numerical policy for analysis metrics.

Log-free. Claims **canonical quantized output**, not unconstrained
BLAS/platform bit identity across machines or library builds.

Supported runtime dependency floors (see ``pyproject.toml`` / ``uv.lock``):

- NumPy >= 2
- pandas >= 2
- SciPy >= 1.11
- NetworkX >= 3
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from decimal import ROUND_HALF_EVEN, Decimal
from types import MappingProxyType
from typing import Any, Final

import networkx as nx
import numpy as np
import pandas as pd
import scipy

__all__ = [
    "ACCUMULATION_POLICY",
    "CANONICAL_FLOAT_DECIMAL_PLACES",
    "CANONICAL_OUTPUT_CLAIM",
    "GRAPH_NODE_ORDER_POLICY",
    "INTERMEDIATE_DTYPE",
    "MINIMUM_LIBRARY_VERSIONS",
    "PANDAS_NULL_SENTINEL_POLICY",
    "SCIPY_DEGENERATE_POLICY",
    "SUPPORTED_COMMUNITY_ALGORITHM",
    "NumericalPolicyError",
    "canonical_python_scalar",
    "library_versions",
    "normalize_signed_zero",
    "quantize_float",
    "quantize_mapping",
    "quantize_sequence",
    "require_finite",
    "require_sorted_ids",
    "sorted_graph_nodes",
    "stable_seed_tuple",
]

CANONICAL_OUTPUT_CLAIM: Final[str] = (
    "canonical_quantized_output_not_blas_platform_bit_identity"
)
INTERMEDIATE_DTYPE: Final[np.dtype[np.floating[Any]]] = np.dtype(np.float64)
CANONICAL_FLOAT_DECIMAL_PLACES: Final[int] = 12
PANDAS_NULL_SENTINEL_POLICY: Final[str] = (
    "pandas_na_is_unknown_never_coerce_to_zero; "
    "sort_keys_before_aggregation; "
    "stable_mergesort_for_ties"
)
GRAPH_NODE_ORDER_POLICY: Final[str] = "lexicographic_sorted_node_ids"
SUPPORTED_COMMUNITY_ALGORITHM: Final[str] = (
    "networkx.community.greedy_modularity_communities"
    "(deterministic_tie_break_via_sorted_nodes; nonnegative_weight_projection)"
)

MINIMUM_LIBRARY_VERSIONS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "numpy": "2",
        "pandas": "2",
        "scipy": "1.11",
        "networkx": "3",
    }
)


class NumericalPolicyError(ValueError):
    """Fail-closed numerical policy error with a stable ``code`` only."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def library_versions() -> Mapping[str, str]:
    """Record installed scientific library versions for metric documents."""
    return MappingProxyType(
        {
            "numpy": str(np.__version__),
            "pandas": str(pd.__version__),
            "scipy": str(scipy.__version__),
            "networkx": str(nx.__version__),
        }
    )


def normalize_signed_zero(value: float) -> float:
    """Map IEEE signed zero to ``+0.0`` for canonical export."""
    if type(value) is not float:
        raise NumericalPolicyError("invalid_float_type")
    if value == 0.0:
        return 0.0
    return value


def require_finite(value: float, *, code: str = "non_finite") -> float:
    """Reject NaN/Inf; never silently coerce non-finite values to zero."""
    if type(value) is not float:
        raise NumericalPolicyError("invalid_float_type")
    if value != value or value in (float("inf"), float("-inf")):
        raise NumericalPolicyError(code)
    return normalize_signed_zero(value)


def quantize_float(
    value: float, *, decimal_places: int = CANONICAL_FLOAT_DECIMAL_PLACES
) -> float:
    """Quantize a finite float to fixed decimal places (banker's rounding)."""
    finite = require_finite(value)
    if decimal_places < 0:
        raise NumericalPolicyError("invalid_decimal_places")
    quant = Decimal("1").scaleb(-decimal_places)
    quantized = Decimal(str(finite)).quantize(quant, rounding=ROUND_HALF_EVEN)
    result = float(quantized)
    return normalize_signed_zero(result)


def canonical_python_scalar(value: object) -> bool | int | float | str | None:
    """Convert NumPy/pandas scalars to plain Python types; reject non-finite."""
    if value is None:
        return None
    if type(value) is bool:
        return value
    if isinstance(value, np.bool_):
        return bool(value)
    if type(value) is int:
        return value
    if isinstance(value, np.integer):
        return int(value)
    if type(value) is float or isinstance(value, np.floating):
        return quantize_float(float(value))
    if isinstance(value, str):
        return value
    if value is pd.NA:
        raise NumericalPolicyError("non_finite")
    raise NumericalPolicyError("unsupported_scalar")


def quantize_sequence(values: Sequence[float]) -> tuple[float, ...]:
    """Sort then quantize a finite float sequence for deterministic export."""
    ordered = sorted(require_finite(float(item)) for item in values)
    return tuple(quantize_float(item) for item in ordered)


def quantize_mapping(values: Mapping[str, float]) -> dict[str, float]:
    """Sort keys then quantize float values for deterministic export."""
    return {
        key: quantize_float(require_finite(float(values[key])))
        for key in sorted(values)
    }


def require_sorted_ids(
    ids: Iterable[str], *, code: str = "unsorted_ids"
) -> tuple[str, ...]:
    """Require lexicographic order before aggregation; return a tuple copy."""
    items = tuple(ids)
    if items != tuple(sorted(items)):
        raise NumericalPolicyError(code)
    return items


def sorted_graph_nodes(nodes: Iterable[str]) -> tuple[str, ...]:
    """Canonical NetworkX node order: lexicographic sorted string IDs."""
    return tuple(sorted(nodes))


def stable_seed_tuple(*parts: int) -> tuple[int, ...]:
    """Build an explicit seed tuple for deterministic graph algorithms."""
    seeds: list[int] = []
    for part in parts:
        if type(part) is not int or isinstance(part, bool) or part < 0:
            raise NumericalPolicyError("invalid_seed")
        seeds.append(part)
    return tuple(seeds)


# SciPy degenerate behavior policy (documentary constants for later metric tasks).
SCIPY_DEGENERATE_POLICY: Final[str] = (
    "empty_or_single_sample_distributions_mark_unknown; "
    "never_coerce_empty_entropy_or_divergence_to_zero; "
    "ties_broken_by_sorted_input_order"
)

# Accumulation policy: float64 intermediates, sort inputs, quantize on export.
ACCUMULATION_POLICY: Final[str] = (
    "float64_intermediate; sort_inputs_before_reduce; "
    "quantize_on_canonical_export_only"
)
