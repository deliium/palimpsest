"""Unit tests for the V2 compatibility matrix."""

from __future__ import annotations

from pathlib import Path

import pytest

from simulation.compatibility import (
    ALEMBIC_HEAD_REVISION,
    API_HTTP_PREFIX,
    COMMUNICATION_SCHEMA_VERSION,
    COMPATIBILITY_MATRIX,
    EXPERIMENT_DEFINITION_SCHEMA_VERSION,
    METRIC_CATALOG_VERSION,
    METRIC_DOCUMENT_SCHEMA_VERSION,
    OBSERVER_LAYOUT_SCHEMA_VERSION,
    OBSERVER_PROTOCOL_VERSION,
    PLANNED_RUNNER_SCHEMA_VERSION_V23,
    RESEARCH_UI_MOUNT,
    STREAM_ENVELOPE_VERSION,
    V3_CAPABILITY_FLAG_NAMES,
    V3_CAPABILITY_FLAGS_WIRE_KEY,
    WS_PROTOCOL_VERSION,
    CompatibilityEntry,
    compatibility_entry,
    list_compatibility_ids,
)
from simulation.persistence import (
    ACCEPTED_EVENT_SCHEMA_VERSIONS,
    EVENT_SCHEMA_VERSION,
    PERSISTENCE_CODEC_VERSION,
    PROJECTOR_VERSION,
)
from simulation.runner_models import (
    RESULT_SCHEMA_VERSION,
    RUNNER_SCHEMA_VERSION,
    RUNNER_SCHEMA_VERSION_V1,
    RUNNER_SCHEMA_VERSION_V2,
    RUNNER_SCHEMA_VERSION_V3,
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V12,
    RUNNER_SCHEMA_VERSION_V18,
    RUNNER_SCHEMA_VERSION_V19,
    RUNNER_SCHEMA_VERSION_V20,
    RUNNER_SCHEMA_VERSION_V21,
    RUNNER_SCHEMA_VERSION_V22,
    SUPPORTED_RUNNER_SCHEMA_VERSIONS,
)

ROOT = Path(__file__).resolve().parents[2]


def test_matrix_covers_required_taxonomy_ids() -> None:
    required = {
        "event_schema",
        "projector",
        "persistence_codec",
        "derivation",
        "runner_config",
        "runner_result",
        "cognition_trace",
        "cognition_policy",
        "subjective_codec",
        "stream_record",
        "stream_envelope",
        "finalization_command",
        "evidence_manifest",
        "experiment_definition",
        "metric_document",
        "metric_catalog",
        "api_http",
        "ws_protocol",
        "alembic_head",
        "communication",
        "observer_protocol",
        "observer_layout",
        "research_ui_mount",
        "v3_capability_flags",
    }
    assert set(COMPATIBILITY_MATRIX) == required
    assert list_compatibility_ids() == tuple(sorted(required))


def test_compatibility_entry_lookup_and_fail_closed() -> None:
    entry = compatibility_entry("event_schema")
    assert isinstance(entry, CompatibilityEntry)
    assert entry.write_version == str(EVENT_SCHEMA_VERSION)
    assert entry.accepted_restore == frozenset(
        str(v) for v in ACCEPTED_EVENT_SCHEMA_VERSIONS
    )
    with pytest.raises(KeyError, match="unknown_compatibility_id"):
        compatibility_entry("not-a-real-entry")


def test_event_schema_stays_at_v5_write() -> None:
    entry = compatibility_entry("event_schema")
    assert entry.write_version == "5"
    bump = entry.bump_trigger.lower()
    assert "replay-v5" in bump
    assert "2-8" in entry.v1_fixture_impact or "2-8" in entry.bump_trigger


def test_runner_config_write_is_v4_with_legacy_accepted() -> None:
    entry = compatibility_entry("runner_config")
    assert entry.write_version == RUNNER_SCHEMA_VERSION
    assert RUNNER_SCHEMA_VERSION == RUNNER_SCHEMA_VERSION_V4
    assert RUNNER_SCHEMA_VERSION_V4 == "runner-config-v4"
    assert RUNNER_SCHEMA_VERSION_V4 in entry.bump_trigger
    assert RUNNER_SCHEMA_VERSION_V3 in entry.bump_trigger
    assert RUNNER_SCHEMA_VERSION_V1 in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    assert RUNNER_SCHEMA_VERSION_V2 in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    assert RUNNER_SCHEMA_VERSION_V3 in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    assert RUNNER_SCHEMA_VERSION_V4 in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    assert RUNNER_SCHEMA_VERSION_V3 in entry.accepted_restore
    assert RUNNER_SCHEMA_VERSION_V4 in entry.accepted_restore
    assert "runner-config-v5" in entry.accepted_restore
    assert "runner-config-v6" in entry.accepted_restore
    assert "runner-config-v7" in entry.accepted_restore
    assert "runner-config-v8" in entry.accepted_restore
    assert RUNNER_SCHEMA_VERSION_V12 == "runner-config-v12"
    assert RUNNER_SCHEMA_VERSION_V12 in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    assert "runner-config-v12" in entry.accepted_restore
    assert "teaching interaction mode is deterministic" in entry.bump_trigger
    assert "consolidation-only" in entry.bump_trigger
    assert "runner-config-v14" in entry.accepted_restore
    assert "environmental dynamics spec is set" in entry.bump_trigger
    assert RUNNER_SCHEMA_VERSION_V18 == "runner-config-v18"
    assert RUNNER_SCHEMA_VERSION_V19 == "runner-config-v19"
    assert RUNNER_SCHEMA_VERSION_V20 == "runner-config-v20"
    assert RUNNER_SCHEMA_VERSION_V21 == "runner-config-v21"
    assert RUNNER_SCHEMA_VERSION_V22 == "runner-config-v22"
    assert RUNNER_SCHEMA_VERSION_V18 in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    assert RUNNER_SCHEMA_VERSION_V19 in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    assert RUNNER_SCHEMA_VERSION_V20 in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    assert RUNNER_SCHEMA_VERSION_V21 in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    assert RUNNER_SCHEMA_VERSION_V22 in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    assert "runner-config-v18" in entry.accepted_restore
    assert "runner-config-v19" in entry.accepted_restore
    assert "runner-config-v20" in entry.accepted_restore
    assert "runner-config-v21" in entry.accepted_restore
    assert "runner-config-v22" in entry.accepted_restore
    assert "artifact interpretation mode is deterministic" in entry.bump_trigger
    assert "semantic naming mode is deterministic" in entry.bump_trigger
    assert "cultural narrative mode is deterministic" in entry.bump_trigger
    assert "cognitive budget mode is enforced" in entry.bump_trigger
    assert "artifacts-only" in entry.bump_trigger
    assert "conventions-only" in entry.bump_trigger
    assert "naming-only" in entry.bump_trigger
    assert "narratives-only" in entry.bump_trigger
    assert PLANNED_RUNNER_SCHEMA_VERSION_V23 in entry.bump_trigger
    assert V3_CAPABILITY_FLAGS_WIRE_KEY in entry.bump_trigger
    assert "v22 keyset" in entry.bump_trigger
    assert "A-E" in entry.v1_fixture_impact
    assert "extended_self_model" in entry.v1_fixture_impact
    assert "V1 gate" in entry.v1_fixture_impact
    assert "V3 flags" in entry.v1_fixture_impact
    assert entry.write_version == "runner-config-v4"


def test_v3_scaffolding_matrix_rows() -> None:
    flags = compatibility_entry("v3_capability_flags")
    assert flags.write_version == V3_CAPABILITY_FLAGS_WIRE_KEY
    assert flags.accepted_restore == frozenset(V3_CAPABILITY_FLAG_NAMES)
    assert len(V3_CAPABILITY_FLAG_NAMES) == 5
    assert "capability_unimplemented" in flags.bump_trigger
    assert PLANNED_RUNNER_SCHEMA_VERSION_V23 in flags.bump_trigger

    protocol = compatibility_entry("observer_protocol")
    assert protocol.write_version == OBSERVER_PROTOCOL_VERSION == "observer-protocol-v1"
    assert "no V3 fields on GET /version" in protocol.v1_fixture_impact

    layout = compatibility_entry("observer_layout")
    assert layout.write_version == OBSERVER_LAYOUT_SCHEMA_VERSION
    assert OBSERVER_LAYOUT_SCHEMA_VERSION == "observer-layout-v1"

    research = compatibility_entry("research_ui_mount")
    assert research.write_version == RESEARCH_UI_MOUNT == "/research/"

    alembic = compatibility_entry("alembic_head")
    assert alembic.write_version == "0017"
    assert "no 0018" in alembic.bump_trigger
    assert "0017" in alembic.v1_fixture_impact


def test_alembic_head_pin_and_0017_exists() -> None:
    entry = compatibility_entry("alembic_head")
    assert entry.write_version == ALEMBIC_HEAD_REVISION == "0017"
    versions = ROOT / "alembic" / "versions"
    assert (versions / "0016_long_run_event_indexes.py").is_file()
    assert (versions / "0017_memory_embedding_hnsw.py").is_file()
    assert sorted(versions.glob("0018_*.py")) == []


def test_cross_package_mirrors_stay_in_sync() -> None:
    from analysis.models import (
        METRIC_DOCUMENT_SCHEMA_VERSION as analysis_metric_doc,
    )
    from analysis.specifications import METRIC_CATALOG_VERSION as analysis_catalog
    from api.schemas import STREAM_ENVELOPE_VERSION as api_envelope
    from api.security import WS_PROTOCOL_VERSION as api_ws
    from experiments.models import EXPERIMENT_SCHEMA_VERSION
    from observer.version import (
        OBSERVER_LAYOUT_SCHEMA_VERSION as observer_layout,
    )
    from observer.version import (
        OBSERVER_PROTOCOL_VERSION as observer_protocol,
    )
    from world.communications import (
        COMMUNICATION_SCHEMA_VERSION as world_comm,
    )

    assert EXPERIMENT_DEFINITION_SCHEMA_VERSION == EXPERIMENT_SCHEMA_VERSION
    assert METRIC_DOCUMENT_SCHEMA_VERSION == analysis_metric_doc
    assert METRIC_CATALOG_VERSION == analysis_catalog
    assert STREAM_ENVELOPE_VERSION == api_envelope
    assert WS_PROTOCOL_VERSION == api_ws
    assert API_HTTP_PREFIX == "/v1"
    assert COMMUNICATION_SCHEMA_VERSION == world_comm
    assert OBSERVER_PROTOCOL_VERSION == observer_protocol
    assert OBSERVER_LAYOUT_SCHEMA_VERSION == observer_layout
    assert PLANNED_RUNNER_SCHEMA_VERSION_V23 == "runner-config-v23"
    assert compatibility_entry("projector").write_version == PROJECTOR_VERSION
    assert (
        compatibility_entry("persistence_codec").write_version
        == PERSISTENCE_CODEC_VERSION
    )
    assert compatibility_entry("runner_result").write_version == RESULT_SCHEMA_VERSION


def test_facade_reexports_compatibility_surface() -> None:
    import simulation

    assert "COMPATIBILITY_MATRIX" in simulation.__all__
    assert "RUNNER_SCHEMA_VERSION_V3" in simulation.__all__
    assert "RUNNER_SCHEMA_VERSION_V4" in simulation.__all__
    assert "CognitionTraceSpec" in simulation.__all__
    assert "ALEMBIC_HEAD_REVISION" in simulation.__all__
    assert "PLANNED_RUNNER_SCHEMA_VERSION_V23" in simulation.__all__
    assert "OBSERVER_PROTOCOL_VERSION" in simulation.__all__
    assert "V3_CAPABILITY_FLAG_NAMES" in simulation.__all__
    assert simulation.compatibility_entry is compatibility_entry
    assert simulation.RUNNER_SCHEMA_VERSION_V3 == RUNNER_SCHEMA_VERSION_V3
    assert simulation.RUNNER_SCHEMA_VERSION_V4 == RUNNER_SCHEMA_VERSION_V4
    assert (
        simulation.PLANNED_RUNNER_SCHEMA_VERSION_V23
        == PLANNED_RUNNER_SCHEMA_VERSION_V23
    )
