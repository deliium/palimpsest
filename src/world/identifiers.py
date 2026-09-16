"""Opaque world identifiers. These are not operational request IDs or UUIDs."""

from __future__ import annotations

from dataclasses import dataclass
from unicodedata import category

from world._freeze import require_bounded_text, require_ordered_unique

_STABLE_ID_MIN_LEN = 1
_STABLE_ID_MAX_LEN = 128

__all__ = [
    "EntityId",
    "EventId",
    "ProposalId",
    "RequestId",
    "WorldId",
    "WorldRevision",
    "require_bounded_text",
    "require_exact_nonneg_int",
    "require_ordered_unique",
    "require_stable_id",
]


def require_exact_nonneg_int(name: str, value: object) -> int:
    """Accept only exact non-boolean ``int`` values ``>= 0``."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be a non-negative integer")
    if value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def require_stable_id(name: str, value: object) -> str:
    """Validate a stable domain ID.

    Accepts only exact ``str`` values of 1-128 Unicode code points. Rejects
    leading/trailing whitespace and control characters. Accepted values are
    preserved verbatim with no normalization.
    """
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a str")
    length = len(value)
    if length < _STABLE_ID_MIN_LEN or length > _STABLE_ID_MAX_LEN:
        raise ValueError(
            f"{name} must be between {_STABLE_ID_MIN_LEN} and "
            f"{_STABLE_ID_MAX_LEN} Unicode code points"
        )
    if value != value.strip():
        raise ValueError(f"{name} must not have leading or trailing whitespace")
    if any(category(char) == "Cc" for char in value):
        raise ValueError(f"{name} must not contain control characters")
    return value


@dataclass(frozen=True, slots=True)
class EntityId:
    """Opaque world identity. Agents never mint or inspect internal structure."""

    value: str

    def __post_init__(self) -> None:
        require_stable_id("EntityId.value", self.value)


@dataclass(frozen=True, slots=True)
class WorldId:
    """Stable identity for a world aggregate. Distinct from revision tokens."""

    value: str

    def __post_init__(self) -> None:
        require_stable_id("WorldId.value", self.value)


@dataclass(frozen=True, slots=True)
class ProposalId:
    """Stable identity for a non-authoritative action proposal."""

    value: str

    def __post_init__(self) -> None:
        require_stable_id("ProposalId.value", self.value)


@dataclass(frozen=True, slots=True)
class RequestId:
    """Stable identity for a non-authoritative action request."""

    value: str

    def __post_init__(self) -> None:
        require_stable_id("RequestId.value", self.value)


@dataclass(frozen=True, slots=True)
class EventId:
    """Stable identity for an immutable world event."""

    value: str

    def __post_init__(self) -> None:
        require_stable_id("EventId.value", self.value)


@dataclass(frozen=True, slots=True)
class WorldRevision:
    """Monotonic world revision token. Not a wall-clock or HTTP correlation ID."""

    value: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "value",
            require_exact_nonneg_int("WorldRevision.value", self.value),
        )
