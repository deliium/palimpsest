"""Capability-anchor string parity against objective SkillDomain values."""

from __future__ import annotations

from agents.cognition.practical_knowledge import (
    PracticalKnowledgeKind,
    resolve_capability_anchor,
)
from world._skills import SkillDomain


def test_capability_anchors_match_skill_domain_values() -> None:
    expected = {
        PracticalKnowledgeKind.FORAGING_METHOD: SkillDomain.FORAGING.value,
        PracticalKnowledgeKind.HEALING_TECHNIQUE: SkillDomain.HEALING.value,
        PracticalKnowledgeKind.CRAFTING_PROCESS: SkillDomain.CRAFTING.value,
        PracticalKnowledgeKind.NAVIGATION_KNOWLEDGE: SkillDomain.NAVIGATION.value,
        PracticalKnowledgeKind.BUILDING_METHOD: SkillDomain.BUILDING.value,
    }
    for kind, skill_value in expected.items():
        assert resolve_capability_anchor(kind) == skill_value
        assert skill_value in {domain.value for domain in SkillDomain}


def test_anchors_do_not_cover_non_technique_skill_domains() -> None:
    technique_anchors = {
        resolve_capability_anchor(kind) for kind in PracticalKnowledgeKind
    }
    assert SkillDomain.RESOURCE_DETECTION.value not in technique_anchors
    assert SkillDomain.COMMUNICATION.value not in technique_anchors
    assert SkillDomain.TEACHING.value not in technique_anchors
