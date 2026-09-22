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
    STREAM_ENVELOPE_VERSION,
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
    assert "no v6" in bump or "stay at replay-v5" in bump


def test_runner_config_write_is_v3_with_legacy_accepted() -> None:
    entry = compatibility_entry("runner_config")
    assert entry.write_version == RUNNER_SCHEMA_VERSION
    assert RUNNER_SCHEMA_VERSION == RUNNER_SCHEMA_VERSION_V3
    assert RUNNER_SCHEMA_VERSION_V3 == "runner-config-v3"
    assert RUNNER_SCHEMA_VERSION_V3 in entry.bump_trigger
    assert RUNNER_SCHEMA_VERSION_V1 in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    assert RUNNER_SCHEMA_VERSION_V2 in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    assert RUNNER_SCHEMA_VERSION_V3 in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    assert RUNNER_SCHEMA_VERSION_V3 in entry.accepted_restore


def test_alembic_head_pin_and_no_0013() -> None:
    entry = compatibility_entry("alembic_head")
    assert entry.write_version == ALEMBIC_HEAD_REVISION == "0012"
    versions = ROOT / "alembic" / "versions"
    assert (versions / "0012_v1_scientific_evidence.py").is_file()
    stray = sorted(versions.glob("0013_*.py"))
    assert stray == [], f"unexpected Alembic 0013 migration: {stray}"


def test_cross_package_mirrors_stay_in_sync() -> None:
    from analysis.models import (
        METRIC_DOCUMENT_SCHEMA_VERSION as analysis_metric_doc,
    )
    from analysis.specifications import METRIC_CATALOG_VERSION as analysis_catalog
    from api.schemas import STREAM_ENVELOPE_VERSION as api_envelope
    from api.security import WS_PROTOCOL_VERSION as api_ws
    from experiments.models import EXPERIMENT_SCHEMA_VERSION
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
    assert "ALEMBIC_HEAD_REVISION" in simulation.__all__
    assert simulation.compatibility_entry is compatibility_entry
    assert simulation.RUNNER_SCHEMA_VERSION_V3 == RUNNER_SCHEMA_VERSION_V3
