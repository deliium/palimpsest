"""Separate read and publication ports for scientific-model snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from simulation.scientific_models_models import ScientificModelsSnapshot

__all__ = [
    "ScientificModelsPage",
    "ScientificModelsPublicationOptions",
    "ScientificModelsPublisher",
    "ScientificModelsReader",
    "ScientificModelsStoreReceipt",
]


@dataclass(frozen=True, slots=True)
class ScientificModelsPublicationOptions:
    """Programmatic publication intent; never a runner or capability field."""

    enabled: bool = False
    max_bytes: int = 8 * 1024 * 1024

    def __post_init__(self) -> None:
        if type(self.enabled) is not bool:
            raise ValueError("enabled: invalid_type")
        if isinstance(self.max_bytes, bool) or type(self.max_bytes) is not int:
            raise ValueError("max_bytes: invalid_type")
        if self.max_bytes < 1:
            raise ValueError("max_bytes: invalid_range")


@dataclass(frozen=True, slots=True)
class ScientificModelsStoreReceipt:
    publication_id: str
    stored: bool
    byte_size: int
    reason: str | None = None

    def __post_init__(self) -> None:
        if type(self.publication_id) is not str or not self.publication_id:
            raise ValueError("publication_id: invalid")
        if type(self.stored) is not bool:
            raise ValueError("stored: invalid_type")
        if isinstance(self.byte_size, bool) or type(self.byte_size) is not int:
            raise ValueError("byte_size: invalid_type")
        if self.byte_size < 0:
            raise ValueError("byte_size: invalid_range")
        if self.reason is not None and type(self.reason) is not str:
            raise ValueError("reason: invalid_type")


@dataclass(frozen=True, slots=True)
class ScientificModelsPage:
    rows: tuple[object, ...]
    next_offset: int | None
    total: int

    def __post_init__(self) -> None:
        if not isinstance(self.rows, tuple):
            raise ValueError("rows: invalid_type")
        for name in ("next_offset", "total"):
            value = getattr(self, name)
            if value is not None and (
                isinstance(value, bool) or type(value) is not int or value < 0
            ):
                raise ValueError(f"{name}: invalid_offset")


class ScientificModelsReader(Protocol):
    def list_publications(self, run_token: str) -> tuple[str, ...]: ...

    def read_publication(
        self, run_token: str, publication_id: str
    ) -> ScientificModelsSnapshot: ...


class ScientificModelsPublisher(Protocol):
    def publish(
        self, snapshot: ScientificModelsSnapshot
    ) -> ScientificModelsStoreReceipt: ...
