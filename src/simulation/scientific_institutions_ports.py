"""Separate read and publication ports for scientific-institution snapshots."""

from __future__ import annotations

from typing import Protocol

from simulation.scientific_institutions_models import (
    ScientificInstitutionsSnapshot,
)

__all__ = [
    "ScientificInstitutionsPublicationPort",
    "ScientificInstitutionsReadPort",
]


class ScientificInstitutionsReadPort(Protocol):
    def read(
        self, run_id: str, publication_id: str | None = None
    ) -> ScientificInstitutionsSnapshot | None: ...

    def list_publications(self, run_id: str) -> tuple[str, ...]: ...


class ScientificInstitutionsPublicationPort(Protocol):
    def publish(
        self, snapshot: ScientificInstitutionsSnapshot
    ) -> object: ...
