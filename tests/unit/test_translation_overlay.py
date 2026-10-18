"""Researcher-only digest translation overlay."""

from __future__ import annotations

import hashlib

from agents.cognition.semantic_naming import NamingReferentKind
from agents.cognition.translation import (
    TranslationMappingStatus,
    TranslationSourceKind,
    TranslationTarget,
    translation_mapping_id,
    translation_source_digest,
)
from observer.labels import project_translation_overlay


class _FakeMapping:
    def __init__(self) -> None:
        source = "foreign_a"
        digest = translation_source_digest(source)
        self.source_token = source
        self.source_digest = digest
        self.source_kind = TranslationSourceKind.LABEL
        self.mapping_id = translation_mapping_id(
            __import__("agents.models", fromlist=["AgentId"]).AgentId("alice"), digest
        )
        self.targets = (
            TranslationTarget(
                binding_id="a" * 64,
                label_token="own_a",
                referent_kind=NamingReferentKind.LOCATION,
                weight=0.6,
            ),
        )
        self.status = TranslationMappingStatus.ACTIVE
        self.fit = __import__(
            "agents.cognition.translation", fromlist=["TranslationFit"]
        ).TranslationFit.RESOLVED
        self.strength = 0.6
        self.evidence_count = 3
        self.usage_count = 1
        self.evidence = ()
        self.first_tick = 1
        self.last_tick = 3


class _FakeLedger:
    def __init__(self) -> None:
        self.mappings = (_FakeMapping(),)


def test_overlay_exposes_only_digests() -> None:
    overlay = project_translation_overlay("alice", _FakeLedger())
    assert len(overlay.mappings) == 1
    reading = overlay.mappings[0]
    assert reading.source_digest == hashlib.sha256(
        b"translation|foreign_a"
    ).hexdigest()[:16]
    assert reading.target_label_digests[0] == hashlib.sha256(
        b"label|own_a"
    ).hexdigest()[:16]
    assert "foreign_a" not in repr(reading)
    assert "own_a" not in repr(reading)
    assert reading.status == "active"
    assert reading.fit == "resolved"


def test_disabled_owner_returns_empty_overlay() -> None:
    overlay = project_translation_overlay("alice", None)
    assert overlay.mappings == ()
