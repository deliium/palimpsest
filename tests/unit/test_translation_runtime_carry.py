"""Runtime carry and blank-slate behavior for translation ledgers."""

from __future__ import annotations

import pytest

from agents.cognition.semantic_naming import NamingReferentKind
from agents.cognition.translation import (
    TranslationFit,
    TranslationLedger,
    TranslationMapping,
    TranslationMappingStatus,
    TranslationSourceKind,
    TranslationTarget,
    empty_translation_ledger,
    require_owner_translation,
    translation_mapping_id,
    translation_source_digest,
)
from agents.models import AgentId
from simulation.agent_runtime import AgentRuntime
from simulation.new_agent_initialization import (
    BLANK_SLATE_SUBJECTIVE_STORES,
    SUBJECTIVE_COPY_DENY_LIST,
)


def test_runtime_slot_and_owner_guard() -> None:
    assert "_translation" in AgentRuntime.__slots__
    owner = AgentId("alice")
    ledger = empty_translation_ledger(owner)
    require_owner_translation(ledger, owner, field_name="translation")
    with pytest.raises(ValueError, match="owner_id mismatch"):
        require_owner_translation(
            ledger, AgentId("bob"), field_name="translation"
        )


def test_blank_slate_denies_translation() -> None:
    assert "translation" in SUBJECTIVE_COPY_DENY_LIST
    assert "translation" in BLANK_SLATE_SUBJECTIVE_STORES


def test_ledger_round_trips_without_raw_metric_fields() -> None:
    owner = AgentId("alice")
    digest = translation_source_digest("foreign_a")
    mapping = TranslationMapping(
        mapping_id=translation_mapping_id(owner, digest),
        owner_id=owner,
        source_token="foreign_a",
        source_digest=digest,
        source_kind=TranslationSourceKind.LABEL,
        targets=(
            TranslationTarget(
                binding_id="a" * 64,
                label_token="own_a",
                referent_kind=NamingReferentKind.LOCATION,
                weight=0.5,
            ),
        ),
        status=TranslationMappingStatus.ACTIVE,
        fit=TranslationFit.RESOLVED,
        strength=0.5,
        evidence_count=3,
        first_tick=1,
        last_tick=2,
    )
    ledger = TranslationLedger(owner_id=owner, mappings=(mapping,))
    assert ledger.mappings[0].source_token == "foreign_a"
    assert not hasattr(mapping, "correct")
