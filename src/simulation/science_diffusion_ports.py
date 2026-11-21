"""Separate read and publication ports for diffusion snapshots."""

from __future__ import annotations

from typing import Protocol

from simulation.science_diffusion_models import ScienceDiffusionSnapshot

__all__ = [
    "ScienceDiffusionPublicationPort",
    "ScienceDiffusionReadPort",
]


class ScienceDiffusionReadPort(Protocol):
    def read(
        self, run_id: str, publication_id: str | None = None
    ) -> ScienceDiffusionSnapshot | None: ...

    def list_publications(self, run_id: str) -> tuple[str, ...]: ...

    def latest_publication_id(self, run_id: str) -> str | None: ...


class ScienceDiffusionPublicationPort(Protocol):
    def publish(self, snapshot: ScienceDiffusionSnapshot) -> object: ...
