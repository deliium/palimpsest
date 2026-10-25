"""Independent strict HTTP schema; legacy observer frames are not widened."""

from __future__ import annotations

from typing import Literal, Self, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from simulation.civilization_models import (
    CivilizationCoverage,
    CivilizationCoverageState,
    CivilizationCursor,
    CivilizationEvidenceClass,
    CivilizationLayer,
    CivilizationMarker,
    CivilizationPublicationRef,
    CivilizationScope,
    CivilizationSection,
    CivilizationWindow,
)
from simulation.civilization_ports import CivilizationPage
from simulation.civilization_rows import CivilizationCapturedRow, CivilizationMapRow

__all__ = [
    "CivilizationAvailabilityReason",
    "CivilizationCatalogueBoundaryOut",
    "CivilizationCatalogueOut",
    "CivilizationCatalogueScopeOut",
    "CivilizationMapOut",
    "CivilizationMarkersOut",
    "CivilizationOverlayOut",
    "CivilizationRequestedCursorOut",
    "civilization_map_out",
]

type CivilizationAvailabilityReason = Literal[
    "capture_off",
    "channel_absent",
    "boundary_not_captured",
    "publication_pending",
    "capture_gap",
    "capture_limit",
    "partial_owner_coverage",
    "missing_denominator",
    "grounding_unavailable",
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


class CivilizationCatalogueScopeOut(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    evidence_class: CivilizationEvidenceClass
    owner_id: str | None = Field(default=None, max_length=512)
    layer: CivilizationLayer | None = None


class CivilizationCatalogueBoundaryOut(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    boundary_tick: int = Field(ge=0)
    revision: int = Field(ge=0)
    coverage: CivilizationCoverage
    layers: tuple[CivilizationLayer, ...] = Field(max_length=7)


class CivilizationCatalogueOut(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    schema_version: Literal["observer-civilization-catalogue-v1"] = (
        "observer-civilization-catalogue-v1"
    )
    run_id: str
    world_id: str
    scope: CivilizationCatalogueScopeOut
    publication: CivilizationPublicationRef | None
    availability: Literal["available", "unavailable"]
    reason: CivilizationAvailabilityReason | None
    coverage: CivilizationCoverage
    boundaries: tuple[CivilizationCatalogueBoundaryOut, ...] = Field(max_length=200)
    next_cursor: str | None = Field(max_length=4096)
    truncated: bool

    @model_validator(mode="after")
    def validate_catalogue(self) -> Self:
        if self.truncated != (self.next_cursor is not None):
            raise ValueError("invalid_civilization_catalogue")
        ticks = [boundary.boundary_tick for boundary in self.boundaries]
        if ticks != sorted(set(ticks)):
            raise ValueError("invalid_civilization_catalogue")
        for boundary in self.boundaries:
            if any(
                layer
                not in _catalogue_layers(self.scope.evidence_class, self.scope.layer)
                for layer in boundary.layers
            ):
                raise ValueError("invalid_civilization_scope")
        if self.availability == "available":
            if (
                self.publication is None
                or self.reason is not None
                or self.coverage.state is CivilizationCoverageState.DISABLED
            ):
                raise ValueError("invalid_civilization_availability")
        elif (
            self.boundaries
            or self.next_cursor is not None
            or self.truncated
            or self.reason is None
            or self.coverage.state
            in (CivilizationCoverageState.COMPLETE, CivilizationCoverageState.PARTIAL)
        ):
            raise ValueError("invalid_civilization_availability")
        return self


class CivilizationOverlayOut(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, strict=True, allow_inf_nan=False
    )
    schema_version: Literal["observer-civilization-overlay-v1"] = (
        "observer-civilization-overlay-v1"
    )
    run_id: str
    world_id: str
    scope: CivilizationScope
    requested_tick: int = Field(ge=0)
    requested_publication_id: str | None = Field(default=None, max_length=512)
    publication: CivilizationPublicationRef | None
    availability: Literal["available", "unavailable"]
    reason: CivilizationAvailabilityReason | None
    resolved_cursor: CivilizationCursor | None
    window: CivilizationWindow | None
    coverage: CivilizationCoverage
    rows: tuple[CivilizationCapturedRow, ...] = Field(max_length=200)
    next_cursor: str | None = Field(max_length=4096)
    truncated: bool
    source_revision: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_overlay(self) -> Self:
        if type(self.scope.layer) is not CivilizationLayer:
            raise ValueError("invalid_civilization_scope")
        if self.truncated != (self.next_cursor is not None):
            raise ValueError("invalid_civilization_overlay")
        if self.availability == "available":
            if (
                self.publication is None
                or self.reason is not None
                or self.resolved_cursor is None
                or self.window is None
                or self.source_revision is None
                or self.resolved_cursor.boundary_tick != self.requested_tick
                or self.resolved_cursor.run_id != self.run_id
                or self.resolved_cursor.world_id != self.world_id
                or self.source_revision != self.resolved_cursor.revision
                or self.coverage.state
                in (
                    CivilizationCoverageState.DISABLED,
                    CivilizationCoverageState.UNAVAILABLE,
                )
            ):
                raise ValueError("invalid_civilization_availability")
            keys = [row.context.row_id for row in self.rows]
            if keys != sorted(set(keys)):
                raise ValueError("invalid_civilization_overlay")
            for row in self.rows:
                if (
                    row.history.scope != self.scope
                    or row.history.boundary_tick != self.requested_tick
                    or row.history.window != self.window
                ):
                    raise ValueError("invalid_civilization_scope")
        elif (
            self.rows
            or self.next_cursor is not None
            or self.truncated
            or self.reason is None
            or self.coverage.state
            in (CivilizationCoverageState.COMPLETE, CivilizationCoverageState.PARTIAL)
        ):
            raise ValueError("invalid_civilization_availability")
        return self


class CivilizationMarkersOut(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, strict=True, allow_inf_nan=False
    )
    schema_version: Literal["observer-civilization-markers-v1"] = (
        "observer-civilization-markers-v1"
    )
    run_id: str
    world_id: str
    scope: CivilizationCatalogueScopeOut
    requested_window: CivilizationWindow
    publication: CivilizationPublicationRef | None
    availability: Literal["available", "unavailable"]
    reason: CivilizationAvailabilityReason | None
    markers: tuple[CivilizationMarker, ...] = Field(max_length=200)
    missing_intervals: tuple[CivilizationWindow, ...] = Field(max_length=200)
    coverage: CivilizationCoverage
    next_cursor: str | None = Field(max_length=4096)
    truncated: bool

    @model_validator(mode="after")
    def validate_markers(self) -> Self:
        if self.truncated != (self.next_cursor is not None):
            raise ValueError("invalid_civilization_markers")
        keys = [(marker.seek_boundary, marker.marker_id) for marker in self.markers]
        if keys != sorted(set(keys)):
            raise ValueError("invalid_civilization_markers")
        window = self.requested_window
        for marker in self.markers:
            if not window.start_tick <= marker.seek_boundary < window.end_tick:
                raise ValueError("invalid_civilization_markers")
            scope = CivilizationScope(
                marker.layer, marker.evidence_class, marker.owner_id
            )
            if (
                marker.evidence_class is not self.scope.evidence_class
                or marker.owner_id != self.scope.owner_id
                or (
                    self.scope.layer is not None
                    and marker.layer is not self.scope.layer
                )
                or (
                    self.scope.layer is None
                    and marker.layer
                    not in _catalogue_layers(
                        self.scope.evidence_class, self.scope.layer
                    )
                )
                or scope.owner_id != self.scope.owner_id
            ):
                raise ValueError("invalid_civilization_scope")
        if self.availability == "available":
            if (
                self.publication is None
                or self.reason is not None
                or self.coverage.state
                in (
                    CivilizationCoverageState.DISABLED,
                    CivilizationCoverageState.UNAVAILABLE,
                )
            ):
                raise ValueError("invalid_civilization_availability")
        elif (
            self.markers
            or self.next_cursor is not None
            or self.truncated
            or self.reason is None
            or self.coverage.state
            in (CivilizationCoverageState.COMPLETE, CivilizationCoverageState.PARTIAL)
        ):
            raise ValueError("invalid_civilization_availability")
        return self


def _catalogue_layers(
    evidence_class: CivilizationEvidenceClass, layer: CivilizationLayer | None
) -> set[CivilizationLayer]:
    if layer is not None:
        return {layer}
    if evidence_class is CivilizationEvidenceClass.OBJECTIVE:
        return {CivilizationLayer.MIGRATION}
    if evidence_class is CivilizationEvidenceClass.SUBJECTIVE:
        return {
            CivilizationLayer.TECHNOLOGY,
            CivilizationLayer.SOCIAL_GROUPS,
            CivilizationLayer.INSTITUTIONS,
        }
    return {
        CivilizationLayer.SETTLEMENTS,
        CivilizationLayer.TRADE,
        CivilizationLayer.CULTURE,
        CivilizationLayer.TECHNOLOGY,
        CivilizationLayer.SOCIAL_GROUPS,
        CivilizationLayer.INSTITUTIONS,
    }
