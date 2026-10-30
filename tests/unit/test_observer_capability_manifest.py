"""Observer capability manifest: closed sets, v1-only serving, no frame change."""

from __future__ import annotations

import ast
import json
from dataclasses import replace
from pathlib import Path

import pytest

from observer.capabilities import (
    OBSERVER_CAPABILITIES,
    RESERVED_OBSERVER_CAPABILITIES,
    RESERVED_OBSERVER_PROTOCOL_VERSION,
    SUPPORTED_OBSERVER_PROTOCOLS,
    ObserverCapability,
    ObserverCapabilityManifest,
    observer_capability_manifest,
    observer_capability_payload,
)
from observer.version import (
    OBSERVER_LAYOUT_SCHEMA_VERSION,
    OBSERVER_PROTOCOL_VERSION,
    SEMANTIC_EVENT_TYPES,
)

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "src" / "observer" / "capabilities.py"

FORBIDDEN_IMPORTS = (
    "world",
    "simulation",
    "agents",
    "api",
    "persistence",
    "infrastructure",
)


def test_manifest_is_read_only_and_v1_only() -> None:
    manifest = observer_capability_manifest()
    assert manifest.read_only is True
    assert manifest.protocol_version == OBSERVER_PROTOCOL_VERSION
    assert manifest.layout_schema_version == OBSERVER_LAYOUT_SCHEMA_VERSION
    assert SUPPORTED_OBSERVER_PROTOCOLS == ("observer-protocol-v1",)
    assert RESERVED_OBSERVER_PROTOCOL_VERSION not in manifest.supported_protocols


def test_advertised_and_reserved_capabilities_are_disjoint_and_complete() -> None:
    advertised = {capability.value for capability in OBSERVER_CAPABILITIES}
    reserved = {capability.value for capability in RESERVED_OBSERVER_CAPABILITIES}
    assert advertised == {
        "structured_manifest",
        "replay_cursors",
        "aggregate_demographics",
        "civilization_overlays",
    }
    assert advertised.isdisjoint(reserved)
    assert advertised | reserved == {
        capability.value for capability in ObserverCapability
    }
    assert len(ObserverCapability) == 10


def test_payload_is_json_serializable() -> None:
    payload = observer_capability_payload()
    assert json.loads(json.dumps(payload)) == payload
    assert payload["supported_protocols"] == ["observer-protocol-v1"]
    assert payload["read_only"] is True
    assert isinstance(payload["capabilities"], list)
    assert isinstance(payload["reserved_capabilities"], list)


def test_semantic_event_types_are_unchanged() -> None:
    assert len(SEMANTIC_EVENT_TYPES) == 73
    assert len(set(SEMANTIC_EVENT_TYPES)) == 73


def test_invalid_manifests_are_rejected() -> None:
    with pytest.raises(ValueError, match="observer_reserved_protocol_served"):
        ObserverCapabilityManifest(
            supported_protocols=(
                OBSERVER_PROTOCOL_VERSION,
                RESERVED_OBSERVER_PROTOCOL_VERSION,
            )
        )
    with pytest.raises(ValueError, match="observer_protocols_empty"):
        ObserverCapabilityManifest(supported_protocols=())
    with pytest.raises(ValueError, match="observer_protocol_not_supported"):
        ObserverCapabilityManifest(supported_protocols=("observer-protocol-v1-other",))
    with pytest.raises(ValueError, match="observer_capabilities_overlap"):
        ObserverCapabilityManifest(
            capabilities=("structured_manifest",),
            reserved_capabilities=("structured_manifest",),
        )
    with pytest.raises(ValueError, match="observer_capabilities_duplicate"):
        ObserverCapabilityManifest(capabilities=("replay_cursors", "replay_cursors"))
    with pytest.raises(ValueError, match="observer_manifest_not_read_only"):
        replace(observer_capability_manifest(), read_only=False)


def test_module_imports_no_runtime_packages() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            roots.add(node.module.split(".", 1)[0])
        elif isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
    assert roots & set(FORBIDDEN_IMPORTS) == set()
