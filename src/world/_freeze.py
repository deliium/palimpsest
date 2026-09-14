"""Deep copies that detach domain values from caller-owned containers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence, Set
from types import MappingProxyType

_IMMUTABLE_SCALARS = (str, bytes, int, float, bool, type(None))


def freeze(value: object) -> object:
    """Return a deeply immutable copy of ``value``."""
    if isinstance(value, _IMMUTABLE_SCALARS):
        return value
    if isinstance(value, Mapping):
        return MappingProxyType({key: freeze(item) for key, item in value.items()})
    if isinstance(value, Set) and not isinstance(value, (str, bytes)):
        return frozenset(freeze(item) for item in value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return tuple(freeze(item) for item in value)
    if isinstance(value, bytearray):
        return bytes(value)
    return value


def freeze_mapping(value: Mapping[str, object]) -> Mapping[str, object]:
    frozen = freeze(dict(value))
    if not isinstance(frozen, Mapping):
        raise TypeError("payload must freeze to a mapping")
    return frozen


def require_non_empty(name: str, value: str) -> str:
    if not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value
