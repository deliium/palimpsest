"""Authority-facing world state. Not part of the public world facade."""

from __future__ import annotations

from world.identifiers import WorldRevision

__all__: list[str] = ["WorldState"]


class WorldState:
    """Authoritative world aggregate. Not visible to agents."""

    __slots__ = ("_revision",)

    def __init__(self, revision: WorldRevision) -> None:
        self._revision = revision

    @property
    def revision(self) -> WorldRevision:
        return self._revision
