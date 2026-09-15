"""Deep copies that detach domain values from caller-owned containers.

Only the closed V1 content grammar is accepted. Unsupported values fail
closed instead of passing through.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence, Set
from types import MappingProxyType
from unicodedata import category

_INT64_MIN = -(2**63)
_INT64_MAX = 2**63 - 1
_SURROGATE_START = 0xD800
_SURROGATE_END = 0xDFFF


def _reject_surrogates(value: str) -> str:
    if any(_SURROGATE_START <= ord(char) <= _SURROGATE_END for char in value):
        raise ValueError("strings must not contain surrogate code points")
    return value


def freeze(value: object) -> object:
    """Return a deeply immutable copy of ``value`` using the closed grammar."""
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        if value < _INT64_MIN or value > _INT64_MAX:
            raise ValueError("integers must fit in signed 64-bit range")
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("floats must be finite")
        return 0.0 if value == 0.0 else value
    if isinstance(value, str):
        return _reject_surrogates(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        raise TypeError("bytes-like values are not allowed in domain content")
    if isinstance(value, Set):
        raise TypeError("sets are not allowed in domain content")
    if isinstance(value, Mapping):
        frozen: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("mapping keys must be strings")
            _reject_surrogates(key)
            frozen[key] = freeze(item)
        return MappingProxyType(frozen)
    if isinstance(value, Sequence):
        return tuple(freeze(item) for item in value)
    raise TypeError(
        f"unsupported domain content type {type(value).__name__}"
    )


def freeze_mapping(value: Mapping[str, object]) -> Mapping[str, object]:
    frozen = freeze(dict(value))
    if not isinstance(frozen, Mapping):
        raise TypeError("payload must freeze to a mapping")
    return frozen


def require_non_empty(name: str, value: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a str")
    if not value:
        raise ValueError(f"{name} must be a non-empty string")
    _reject_surrogates(value)
    return value


def require_bounded_text(
    name: str, value: object, *, max_length: int = 4096
) -> str:
    """Exact text: non-blank, no controls, length-bounded, preserved verbatim."""
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a str")
    length = len(value)
    if length < 1 or length > max_length:
        raise ValueError(
            f"{name} must be between 1 and {max_length} Unicode code points"
        )
    if value.strip() == "":
        raise ValueError(f"{name} must not be whitespace-only")
    if any(category(char) == "Cc" for char in value):
        raise ValueError(f"{name} must not contain control characters")
    _reject_surrogates(value)
    return value


def require_ordered_unique(
    name: str, values: object, *, item_type: type
) -> tuple[object, ...]:
    """Copy an ordered sequence to a tuple; reject sets and duplicates."""
    if isinstance(values, (set, frozenset, Mapping)):
        raise TypeError(f"{name} must be an ordered sequence")
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise TypeError(f"{name} must be an ordered sequence")
    items = tuple(values)
    for item in items:
        if type(item) is not item_type:
            raise TypeError(
                f"{name} items must be exact {item_type.__name__} values"
            )
    if len(set(items)) != len(items):
        raise ValueError(f"{name} must not contain duplicate values")
    return items
