"""Independent strict HTTP schema; legacy observer frames are not widened."""

from __future__ import annotations

from typing import Literal, Self, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from simulation.civilization_models import (
    CivilizationCoverage,
    CivilizationCursor,
    CivilizationEvidenceClass,
    CivilizationScope,
    CivilizationSection,
)
from simulation.civilization_ports import CivilizationPage
from simulation.civilization_rows import CivilizationMapRow

__all__ = [
    "CivilizationMapOut",
    "CivilizationRequestedCursorOut",
    "civilization_map_out",
]


class CivilizationRequestedCursorOut(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    tick: int | None = Field(ge=0)
    through_sequence: int | None = Field(ge=0)

    @model_validator(mode="after")
    def complete_pair(self) -> Self:
        if self.through_sequence is not None and self.tick is None:
            raise ValueError("incomplete_event_cursor")
        return self


class CivilizationMapOut(BaseModel):
    # Config propagates to the nested standard-library frozen dataclasses.
    model_config = ConfigDict(
        extra="forbid", frozen=True, strict=True, allow_inf_nan=False
    )
    schema_version: Literal["observer-civilization-map-v1"] = (
        "observer-civilization-map-v1"
    )
    run_id: str
    world_id: str
    requested_cursor: CivilizationRequestedCursorOut
    resolved_cursor: CivilizationCursor
    section: CivilizationSection
    scope: CivilizationScope
    coverage: CivilizationCoverage
    rows: tuple[CivilizationMapRow, ...] = Field(max_length=200)
    next_cursor: str | None = Field(max_length=4096)
    truncated: bool
    source_revision: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_map(self) -> Self:
        if (
            self.scope.layer is not self.section
            or self.scope.evidence_class is not CivilizationEvidenceClass.OBJECTIVE
            or self.scope.owner_id is not None
            or self.run_id != self.resolved_cursor.run_id
            or self.world_id != self.resolved_cursor.world_id
        ):
            raise ValueError("invalid_civilization_scope")
        CivilizationPage(
            self.resolved_cursor,
            self.resolved_cursor,
            self.scope,
            self.coverage,
            self.rows,
            self.next_cursor,
            self.truncated,
            self.source_revision,
        )
        return self


def civilization_map_out(
    page: CivilizationPage, *, tick: int | None, through_sequence: int | None
) -> CivilizationMapOut:
    """Explicit new envelope; no legacy serializer or payload dictionary."""
    if not isinstance(page.scope.layer, CivilizationSection):
        raise ValueError("invalid_civilization_scope")
    return CivilizationMapOut(
        run_id=page.resolved_cursor.run_id,
        world_id=page.resolved_cursor.world_id,
        requested_cursor=CivilizationRequestedCursorOut(
            tick=tick, through_sequence=through_sequence
        ),
        resolved_cursor=page.resolved_cursor,
        section=page.scope.layer,
        scope=page.scope,
        coverage=page.coverage,
        rows=cast(tuple[CivilizationMapRow, ...], page.rows),
        next_cursor=page.next_cursor,
        truncated=page.truncated,
        source_revision=page.source_revision,
    )
