"""Focused V1/V2 replay and API identity proofs under V3 scaffolding."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from simulation.compatibility import (
    OBSERVER_PROTOCOL_VERSION,
    WS_PROTOCOL_VERSION,
    compatibility_entry,
)
from simulation.persistence import ACCEPTED_EVENT_SCHEMA_VERSIONS, EVENT_SCHEMA_VERSION
from simulation.runner_models import RUNNER_SCHEMA_VERSION_V4, V3CapabilityFlags
from simulation.runner_serialization import decode_runner_config, encode_runner_config

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "runner_configs"


def test_event_schema_write_and_accepted_set_unchanged() -> None:
    entry = compatibility_entry("event_schema")
    assert entry.write_version == str(EVENT_SCHEMA_VERSION) == "5"
    accepted = {str(v) for v in ACCEPTED_EVENT_SCHEMA_VERSIONS}
    assert accepted == {"2", "3", "4", "5", "6", "7", "8"}


def test_legacy_runner_payloads_decode_with_v3_flags_off() -> None:
    for name in ("catalog_a_condition_v2.json", "reference_scenario_v2.json"):
        payload = (FIXTURES / name).read_bytes()
        decoded = decode_runner_config(payload)
        assert decoded.v3_capability_flags == V3CapabilityFlags()
        v4 = replace(
            decoded,
            schema_version=RUNNER_SCHEMA_VERSION_V4,
            v3_capability_flags=V3CapabilityFlags(),
        )
        document = json.loads(encode_runner_config(v4).decode("utf-8"))
        assert document["schema_version"] == RUNNER_SCHEMA_VERSION_V4
        assert "v3_capability_flags" not in document
        assert decode_runner_config(encode_runner_config(v4)).v3_capability_flags == (
            V3CapabilityFlags()
        )


def test_observer_and_ws_identities_unchanged() -> None:
    assert compatibility_entry("observer_protocol").write_version == (
        OBSERVER_PROTOCOL_VERSION
    )
    assert compatibility_entry("ws_protocol").write_version == WS_PROTOCOL_VERSION
    assert OBSERVER_PROTOCOL_VERSION == "observer-protocol-v1"
    assert WS_PROTOCOL_VERSION == "palimpsest.v1"


def test_research_ui_mount_and_api_prefix_stable() -> None:
    assert compatibility_entry("research_ui_mount").write_version == "/research/"
    assert compatibility_entry("api_http").write_version == "/v1"
