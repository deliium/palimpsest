"""V2 compatibility taxonomy for schema and protocol versions.

Single source of truth for write versions, accepted restore sets, bump
triggers, and owning packages. Cross-package version strings are mirrored as
literals here so ``simulation`` never imports ``analysis``, ``experiments``,
``api``, or Alembic. Unit tests assert those mirrors stay in sync.

Reserved decisions for this V2 scaffolding plan:
- Event schema write remains replay-v5 (no v6 bump in this plan).
- Alembic migration head remains ``0012`` (no ``0013``).
- Runner config write becomes ``runner-config-v3`` in the capability-flags task
  while keeping v1/v2 decode.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from simulation.evidence import EVIDENCE_MANIFEST_SCHEMA_VERSION
from simulation.models import (
    DERIVATION_VERSION,
    DERIVATION_VERSION_V1,
    DERIVATION_VERSION_V2,
    DERIVATION_VERSION_V3,
)
from simulation.persistence import (
    ACCEPTED_EVENT_SCHEMA_VERSIONS,
    ACCEPTED_PERSISTENCE_CODEC_VERSIONS,
    ACCEPTED_PROJECTOR_VERSIONS,
    EVENT_SCHEMA_VERSION,
    PERSISTENCE_CODEC_VERSION,
    PROJECTOR_VERSION,
)
from simulation.run_control import (
    FINALIZATION_COMMAND_CODEC_VERSION,
    STREAM_RECORD_SCHEMA_VERSION,
)
from simulation.runner_models import (
    COGNITION_POLICY_VERSION,
    RESULT_SCHEMA_VERSION,
    RESULT_SCHEMA_VERSION_V1,
    RESULT_SCHEMA_VERSION_V2,
    RUNNER_SCHEMA_VERSION,
    RUNNER_SCHEMA_VERSION_V3,
    SUPPORTED_RESULT_SCHEMA_VERSIONS,
    SUPPORTED_RUNNER_SCHEMA_VERSIONS,
)
from simulation.subjective_serialization import SUBJECTIVE_SCHEMA_VERSION
from world.events import (
    EVENT_SCHEMA_REPLAY_V2,
    EVENT_SCHEMA_REPLAY_V3,
    EVENT_SCHEMA_REPLAY_V4,
    EVENT_SCHEMA_REPLAY_V5,
)

_LOG: Final[logging.Logger] = logging.getLogger("simulation.compatibility")

# Mirrored literals — owning packages must keep these equal (tested).
ALEMBIC_HEAD_REVISION: Final[str] = "0012"
EXPERIMENT_DEFINITION_SCHEMA_VERSION: Final[str] = "experiment-definition-v1"
METRIC_DOCUMENT_SCHEMA_VERSION: Final[str] = "1"
METRIC_CATALOG_VERSION: Final[str] = "metric-catalog-v1"
STREAM_ENVELOPE_VERSION: Final[str] = "stream-envelope-v1"
WS_PROTOCOL_VERSION: Final[str] = "palimpsest.v1"
API_HTTP_PREFIX: Final[str] = "/v1"
LEGACY_PENDING_FINALIZATION_CODEC_VERSION: Final[str] = "pending-finalization-v1"
COMMUNICATION_SCHEMA_VERSION: Final[str] = "communication.v1"

__all__ = [
    "ALEMBIC_HEAD_REVISION",
    "API_HTTP_PREFIX",
    "COMMUNICATION_SCHEMA_VERSION",
    "COMPATIBILITY_MATRIX",
    "EXPERIMENT_DEFINITION_SCHEMA_VERSION",
    "LEGACY_PENDING_FINALIZATION_CODEC_VERSION",
    "METRIC_CATALOG_VERSION",
    "METRIC_DOCUMENT_SCHEMA_VERSION",
    "RUNNER_SCHEMA_VERSION_V3",
    "STREAM_ENVELOPE_VERSION",
    "WS_PROTOCOL_VERSION",
    "CompatibilityEntry",
    "compatibility_entry",
    "list_compatibility_ids",
]


@dataclass(frozen=True, slots=True)
class CompatibilityEntry:
    """One row of the V2 version taxonomy."""

    entry_id: str
    write_version: str
    accepted_restore: frozenset[str]
    bump_trigger: str
    owner_package: str
    v1_fixture_impact: str


def _versions(*values: object) -> frozenset[str]:
    return frozenset(str(value) for value in values)


_MATRIX: dict[str, CompatibilityEntry] = {
    "event_schema": CompatibilityEntry(
        entry_id="event_schema",
        write_version=str(EVENT_SCHEMA_VERSION),
        accepted_restore=_versions(
            EVENT_SCHEMA_REPLAY_V2,
            EVENT_SCHEMA_REPLAY_V3,
            EVENT_SCHEMA_REPLAY_V4,
            EVENT_SCHEMA_REPLAY_V5,
        ),
        bump_trigger=(
            "Wire shape change for WorldEvent / occurrence details; "
            "requires new ACCEPTED_* member and replay fixtures. "
            "V2 scaffolding: stay at replay-v5 (no v6)."
        ),
        owner_package="world.events / simulation.persistence",
        v1_fixture_impact="Schemas 2-5 fixtures must remain restoreable",
    ),
    "projector": CompatibilityEntry(
        entry_id="projector",
        write_version=PROJECTOR_VERSION,
        accepted_restore=_versions(*sorted(ACCEPTED_PROJECTOR_VERSIONS)),
        bump_trigger="Private world projector semantics change",
        owner_package="simulation.persistence / world._replay",
        v1_fixture_impact="v1 and v2 projector restores remain accepted",
    ),
    "persistence_codec": CompatibilityEntry(
        entry_id="persistence_codec",
        write_version=PERSISTENCE_CODEC_VERSION,
        accepted_restore=_versions(*sorted(ACCEPTED_PERSISTENCE_CODEC_VERSIONS)),
        bump_trigger="Canonical JSON codec for manifests/snapshots/commits changes",
        owner_package="simulation.persistence / simulation.journal",
        v1_fixture_impact="Codec v1 and v2 restores remain accepted",
    ),
    "derivation": CompatibilityEntry(
        entry_id="derivation",
        write_version=DERIVATION_VERSION,
        accepted_restore=_versions(
            DERIVATION_VERSION_V1,
            DERIVATION_VERSION_V2,
            DERIVATION_VERSION_V3,
        ),
        bump_trigger="Seed/stream/ID derivation identity formula changes",
        owner_package="simulation.models / simulation.identifiers",
        v1_fixture_impact="Legacy derivation versions remain decodable for old runs",
    ),
    "runner_config": CompatibilityEntry(
        entry_id="runner_config",
        write_version=RUNNER_SCHEMA_VERSION,
        accepted_restore=_versions(*sorted(SUPPORTED_RUNNER_SCHEMA_VERSIONS)),
        bump_trigger=(
            "New runner fields require a versioned exact key set "
            f"(write {RUNNER_SCHEMA_VERSION_V3} for V2 capability flags; "
            "v1/v2 decode + default-off upgrade retained)."
        ),
        owner_package="simulation.runner_models / simulation.runner_serialization",
        v1_fixture_impact=(
            "Golden runner-config-v1/v2 fixtures must decode; "
            "config_fingerprint may change under v3 write"
        ),
    ),
    "runner_result": CompatibilityEntry(
        entry_id="runner_result",
        write_version=RESULT_SCHEMA_VERSION,
        accepted_restore=_versions(*sorted(SUPPORTED_RESULT_SCHEMA_VERSIONS)),
        bump_trigger=(
            "Prefer leaving runner-result-v2; bump only if flag digests must "
            "appear in results (prefer diagnostics/fingerprints instead)"
        ),
        owner_package="simulation.runner_models / simulation.runner_serialization",
        v1_fixture_impact=(
            f"{RESULT_SCHEMA_VERSION_V1}/{RESULT_SCHEMA_VERSION_V2} remain accepted"
        ),
    ),
    "cognition_policy": CompatibilityEntry(
        entry_id="cognition_policy",
        write_version=COGNITION_POLICY_VERSION,
        accepted_restore=_versions(COGNITION_POLICY_VERSION),
        bump_trigger="Agent cognition policy contract fields change",
        owner_package="simulation.runner_models",
        v1_fixture_impact="Do not bump unless policy wire shape changes",
    ),
    "subjective_codec": CompatibilityEntry(
        entry_id="subjective_codec",
        write_version=SUBJECTIVE_SCHEMA_VERSION,
        accepted_restore=_versions(SUBJECTIVE_SCHEMA_VERSION),
        bump_trigger="Subjective belief/relationship/receipt codec shape changes",
        owner_package="simulation.subjective_serialization",
        v1_fixture_impact="Outside authoritative replay; keep subjective-v1 stable",
    ),
    "stream_record": CompatibilityEntry(
        entry_id="stream_record",
        write_version=STREAM_RECORD_SCHEMA_VERSION,
        accepted_restore=_versions(STREAM_RECORD_SCHEMA_VERSION),
        bump_trigger="Durable outbox stream record shape changes",
        owner_package="simulation.run_control",
        v1_fixture_impact="stream-record-v1 clients remain compatible",
    ),
    "stream_envelope": CompatibilityEntry(
        entry_id="stream_envelope",
        write_version=STREAM_ENVELOPE_VERSION,
        accepted_restore=_versions(STREAM_ENVELOPE_VERSION),
        bump_trigger="API WebSocket stream envelope shape changes",
        owner_package="api.schemas",
        v1_fixture_impact="Keep stream-envelope-v1; no /v2 routes in scaffolding",
    ),
    "finalization_command": CompatibilityEntry(
        entry_id="finalization_command",
        write_version=FINALIZATION_COMMAND_CODEC_VERSION,
        accepted_restore=_versions(
            FINALIZATION_COMMAND_CODEC_VERSION,
            LEGACY_PENDING_FINALIZATION_CODEC_VERSION,
        ),
        bump_trigger="Pending finalization command wire shape changes",
        owner_package="simulation.run_control / simulation.persistence",
        v1_fixture_impact="pending-finalization-v1 legacy decode retained",
    ),
    "evidence_manifest": CompatibilityEntry(
        entry_id="evidence_manifest",
        write_version=EVIDENCE_MANIFEST_SCHEMA_VERSION,
        accepted_restore=_versions(EVIDENCE_MANIFEST_SCHEMA_VERSION),
        bump_trigger="Evidence high-water mark envelope shape changes",
        owner_package="simulation.evidence",
        v1_fixture_impact="Counts/hashes only; never truth payloads",
    ),
    "experiment_definition": CompatibilityEntry(
        entry_id="experiment_definition",
        write_version=EXPERIMENT_DEFINITION_SCHEMA_VERSION,
        accepted_restore=_versions(EXPERIMENT_DEFINITION_SCHEMA_VERSION),
        bump_trigger="Trusted experiment catalog document shape changes",
        owner_package="experiments.models",
        v1_fixture_impact=(
            "Stay on experiment-definition-v1; flags ride inside runner JSON"
        ),
    ),
    "metric_document": CompatibilityEntry(
        entry_id="metric_document",
        write_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        accepted_restore=_versions(METRIC_DOCUMENT_SCHEMA_VERSION),
        bump_trigger="Analysis metric document schema changes",
        owner_package="analysis.models",
        v1_fixture_impact="Schema \"1\" documents remain loadable",
    ),
    "metric_catalog": CompatibilityEntry(
        entry_id="metric_catalog",
        write_version=METRIC_CATALOG_VERSION,
        accepted_restore=_versions(METRIC_CATALOG_VERSION),
        bump_trigger="Metric family catalog identity changes",
        owner_package="analysis.specifications",
        v1_fixture_impact="metric-catalog-v1 family IDs remain stable",
    ),
    "api_http": CompatibilityEntry(
        entry_id="api_http",
        write_version=API_HTTP_PREFIX,
        accepted_restore=_versions(API_HTTP_PREFIX),
        bump_trigger=(
            "Introduce /v2 only when request/response shape cannot be "
            "expressed as optional additive fields on /v1"
        ),
        owner_package="api",
        v1_fixture_impact="/v1/simulations/* + /health remain stable in scaffolding",
    ),
    "ws_protocol": CompatibilityEntry(
        entry_id="ws_protocol",
        write_version=WS_PROTOCOL_VERSION,
        accepted_restore=_versions(WS_PROTOCOL_VERSION),
        bump_trigger="WebSocket subprotocol negotiation identity changes",
        owner_package="api.security",
        v1_fixture_impact="palimpsest.v1 credentials stay header/subprotocol only",
    ),
    "alembic_head": CompatibilityEntry(
        entry_id="alembic_head",
        write_version=ALEMBIC_HEAD_REVISION,
        accepted_restore=_versions(ALEMBIC_HEAD_REVISION),
        bump_trigger=(
            "New indexed SQL columns required for inspection; "
            "V2 scaffolding: no 0013 — flags live in runner JSON only"
        ),
        owner_package="alembic/versions",
        v1_fixture_impact="Head pin 0012; authoritative table semantics unchanged",
    ),
    "communication": CompatibilityEntry(
        entry_id="communication",
        write_version=COMMUNICATION_SCHEMA_VERSION,
        accepted_restore=_versions(COMMUNICATION_SCHEMA_VERSION),
        bump_trigger=(
            "Structured utterance / declared transmission wire shape changes; "
            "domain-contract evolution rules apply (no bump in scaffolding)"
        ),
        owner_package="world.communications",
        v1_fixture_impact="communication.v1 + legacy text decode remain",
    ),
}

COMPATIBILITY_MATRIX: Final[Mapping[str, CompatibilityEntry]] = MappingProxyType(
    _MATRIX
)

_LOG.debug(
    "compatibility_matrix_loaded",
    extra={
        "entry_count": len(COMPATIBILITY_MATRIX),
        "event_write": str(EVENT_SCHEMA_VERSION),
        "runner_write": RUNNER_SCHEMA_VERSION,
        "runner_planned_v3": RUNNER_SCHEMA_VERSION_V3,
        "alembic_head": ALEMBIC_HEAD_REVISION,
        "accepted_event_count": len(ACCEPTED_EVENT_SCHEMA_VERSIONS),
    },
)


def compatibility_entry(entry_id: str) -> CompatibilityEntry:
    """Return one matrix row; fail closed on unknown ids."""
    try:
        return COMPATIBILITY_MATRIX[entry_id]
    except KeyError as exc:
        _LOG.error(
            "compatibility_entry_unknown",
            extra={"entry_id": entry_id, "reason_code": "unknown_compatibility_id"},
        )
        raise KeyError(f"unknown_compatibility_id:{entry_id}") from exc


def list_compatibility_ids() -> tuple[str, ...]:
    """Stable ordered entry ids for docs and tests."""
    return tuple(sorted(COMPATIBILITY_MATRIX))
