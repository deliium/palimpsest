"""Cognitive loop translation wiring and fingerprint material."""

from __future__ import annotations

import pytest

from agents.cognition.configuration import (
    CognitionLoopConfig,
    CognitionSemanticNamingMode,
    CognitionTranslationMode,
)
from agents.cognition.loop import CognitiveLoop


def test_loop_slots_and_config_default_disabled() -> None:
    assert "_translation_mode" in CognitiveLoop.__slots__
    assert "_translation_policy" in CognitiveLoop.__slots__
    config = CognitionLoopConfig()
    assert config.translation_mode is CognitionTranslationMode.DISABLED
    assert config.translation_policy is None


def test_translation_requires_naming_in_config() -> None:
    with pytest.raises(ValueError, match="translation_requires_semantic_naming"):
        CognitionLoopConfig(
            translation_mode=CognitionTranslationMode.DETERMINISTIC,
            semantic_naming_mode=CognitionSemanticNamingMode.DISABLED,
        )
    config = CognitionLoopConfig(
        translation_mode=CognitionTranslationMode.DETERMINISTIC,
        semantic_naming_mode=CognitionSemanticNamingMode.DETERMINISTIC,
    )
    assert config.translation_policy is not None


def test_fingerprint_material_separates_translation_modes() -> None:
    disabled = CognitionLoopConfig()
    enabled = CognitionLoopConfig(
        translation_mode=CognitionTranslationMode.DETERMINISTIC,
        semantic_naming_mode=CognitionSemanticNamingMode.DETERMINISTIC,
    )
    disabled_material = disabled.condition_fingerprint_material()
    enabled_material = enabled.condition_fingerprint_material()
    assert disabled_material["translation_mode"] == "disabled"
    assert enabled_material["translation_mode"] == "deterministic"
    assert disabled_material["translation_policy_version"] is None
    assert enabled_material["translation_policy_version"] == "translation.v1"
