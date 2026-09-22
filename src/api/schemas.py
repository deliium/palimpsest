"""Strict Pydantic request/response schemas for the research API.

Schemas never embed live engines, private world state, seeds as free text,
or subjective narrative payloads on public surfaces.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

STREAM_ENVELOPE_VERSION: Literal["stream-envelope-v1"] = "stream-envelope-v1"
MAX_CONFIG_BYTES: int = 1_048_576


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class LifecycleStateOut(StrEnum):
    CONFIGURED = "configured"
    READY = "ready"
    PAUSED = "paused"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    COMPLETED = "completed"
    FAILED = "failed"
    FENCED = "fenced"
    RECOVERY_REQUIRED = "recovery-required"
    INTERRUPTED = "interrupted"


class ConfigAvailabilityOut(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class CreateSimulationRequest(StrictModel):
    run_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._-]+$")
    config_schema_version: str = Field(
        default="runner-config-v2", min_length=1, max_length=64
    )
    config_fingerprint: str = Field(
        min_length=64, max_length=64, pattern=r"^[a-f0-9]+$"
    )
    config_payload_b64: str = Field(min_length=1, max_length=2_000_000)


class ConfigureSimulationRequest(StrictModel):
    config_schema_version: str = Field(min_length=1, max_length=64)
    config_fingerprint: str = Field(
        min_length=64, max_length=64, pattern=r"^[a-f0-9]+$"
    )
    config_payload_b64: str = Field(min_length=1, max_length=2_000_000)
    expected_version: int = Field(ge=0)


class IdempotencyHeaderModel(StrictModel):
    """Marker type documenting idempotency-key expectations."""

    idempotency_key: str = Field(min_length=1, max_length=128)


class RunControlStatusOut(StrictModel):
    run_id: str
    lifecycle_state: LifecycleStateOut
    lifecycle_version: int = Field(ge=0)
    config_availability: ConfigAvailabilityOut
    ticks_committed: int = Field(ge=0)
    progress_cursor: int = Field(ge=0)
    config_schema_version: str | None = None
    config_fingerprint: str | None = None
    has_lease: bool
    terminal_reason_code: str | None = None


class RunListOut(StrictModel):
    items: tuple[RunControlStatusOut, ...]
    next_cursor: str | None = None
    count: int = Field(ge=0)


class TickResultOut(StrictModel):
    run_id: str
    lifecycle_state: LifecycleStateOut
    ticks_committed: int = Field(ge=0)
    progress_cursor: int = Field(ge=0)
    stop_reason: str | None = None


class AvailabilityOut(StrEnum):
    AVAILABLE = "available"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class EventCursorIn(StrictModel):
    tick: int = Field(ge=0)
    sequence: int = Field(ge=0)


class EventSummaryOut(StrictModel):
    tick: int = Field(ge=0)
    sequence: int = Field(ge=0)
    kind: str = Field(min_length=1, max_length=128)


class EventPageOut(StrictModel):
    run_id: str
    limit: int = Field(ge=0)
    count: int = Field(ge=0)
    next_cursor: EventCursorIn | None = None
    availability: AvailabilityOut
    manifest_hash: str | None = None
    # Opaque event summaries: kind + tick + sequence only (no payloads).
    events: tuple[EventSummaryOut, ...] = ()


class ObjectiveWorldOut(StrictModel):
    run_id: str
    tick: int = Field(ge=0)
    revision: int = Field(ge=0)
    availability: AvailabilityOut
    body_count: int = Field(ge=0)
    location_count: int = Field(ge=0)


class AgentVisibleOut(StrictModel):
    run_id: str
    tick: int = Field(ge=0)
    agent_id: str
    entity_id: str
    surface: Literal["public"] = "public"
    availability: AvailabilityOut
    occurrence_count: int = Field(ge=0)
    communication_count: int = Field(ge=0)


class ExperimentalStateOut(StrictModel):
    """Metadata-only experiment membership (never condition values/seeds)."""

    run_id: str
    experiment_id: str | None = None
    membership_source: str | None = None
    has_assignment: bool = False
    availability: AvailabilityOut = AvailabilityOut.UNAVAILABLE


class SubjectivePageOut(StrictModel):
    run_id: str
    owner_id: str
    limit: int = Field(ge=0)
    item_count: int = Field(ge=0)
    next_cursor: str | None = None
    availability: AvailabilityOut
    surface: Literal["debug"] = "debug"
    content_available: bool = False
    kind: Literal["memories", "beliefs", "relationships"]


class MetricCatalogItemOut(StrictModel):
    metric_set_id: str
    metric_family: str
    evidence_manifest_hash: str
    schema_version: str
    content_hash_prefix: str = Field(min_length=1, max_length=16)


class MetricCatalogOut(StrictModel):
    run_id: str
    items: tuple[MetricCatalogItemOut, ...]
    count: int = Field(ge=0)
    availability: AvailabilityOut


class MetricDocumentOut(StrictModel):
    """Opaque metric document metadata + base64 payload for research clients."""

    run_id: str
    metric_set_id: str
    metric_family: str
    evidence_manifest_hash: str
    schema_version: str
    content_hash: str
    payload_b64: str
    availability: AvailabilityOut = AvailabilityOut.AVAILABLE


class ReplayRequest(StrictModel):
    to_tick: int = Field(ge=0)
    agent_id: str | None = Field(default=None, max_length=128)


class ReplayResultOut(StrictModel):
    run_id: str
    status: str
    availability: AvailabilityOut
    ticks_replayed: int = Field(ge=0)
    objective: ObjectiveWorldOut | None = None
    agent_visible: AgentVisibleOut | None = None
    reason_code: str | None = None


class StreamFrameKind(StrEnum):
    STATUS = "status"
    EVENTLESS_TICK = "eventless_tick"
    EVENT = "event"
    METRIC = "metric"
    RESULT = "result"
    ERROR = "error"
    COMPLETION = "completion"
    HEARTBEAT = "heartbeat"


class StreamEnvelopeOut(StrictModel):
    """Versioned WebSocket frame. Body is opaque base64 — never logged."""

    envelope_version: Literal["stream-envelope-v1"] = STREAM_ENVELOPE_VERSION
    run_id: str
    cursor: int = Field(ge=0)
    kind: StreamFrameKind
    related_tick: int | None = Field(default=None, ge=0)
    content_hash_prefix: str | None = Field(default=None, max_length=16)
    payload_b64: str | None = None
    high_water: int | None = Field(default=None, ge=0)


class StreamSubscribeIn(StrictModel):
    after_cursor: int = Field(default=0, ge=0)

    @field_validator("after_cursor")
    @classmethod
    def non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("after_cursor must be >= 0")
        return value


def stable_jsonable(value: Any) -> Any:
    """Convert nested structures for JSON without leaking bytes."""
    if isinstance(value, bytes):
        return f"<bytes:{len(value)}>"
    return value
