"""Themes derive only from observed kinds and lineage inheritance."""

from __future__ import annotations

from agents.cognition.cultural_narratives import (
    CULTURAL_NARRATIVE_POLICY_VERSION_V2,
    NarrativeContent,
    NarrativeLedger,
    NarrativeOrigin,
    NarrativeStatus,
    NarrativeTheme,
    NarrativeThemeBasis,
    NarrativeVariant,
    apply_narrative_update,
    default_generational_narrative_policy,
    narrative_content_fingerprint,
    narrative_variant_id,
)
from agents.models import AgentId
from tests.unit.test_cultural_narratives import _identity, _observation

_OWNER = AgentId("alice")


def _ledger(*variants: NarrativeVariant) -> NarrativeLedger:
    return NarrativeLedger(
        owner_id=_OWNER,
        policy_version=CULTURAL_NARRATIVE_POLICY_VERSION_V2,
        variants=variants,
    )


def _variant(**overrides: object) -> NarrativeVariant:
    content = overrides.pop(
        "content", NarrativeContent(concepts=("water", "gone"), text="tell_story")
    )
    assert isinstance(content, NarrativeContent)
    values: dict[str, object] = {
        "variant_id": narrative_variant_id(
            _OWNER, narrative_content_fingerprint(content), 0, ""
        ),
        "owner_id": _OWNER,
        "content": content,
        "content_fingerprint": narrative_content_fingerprint(content),
        "origin": NarrativeOrigin.OBSERVED_EVENT,
        "status": NarrativeStatus.ACTIVE,
        "strength": 0.5,
        "repetition_count": 2,
        "first_tick": 1,
        "last_tick": 1,
        "themes": (NarrativeTheme.FOUNDERS,),
        "theme_basis": NarrativeThemeBasis.OBSERVED_OCCURRENCE_KIND,
    }
    values.update(overrides)
    return NarrativeVariant(**values)  # type: ignore[arg-type]


def test_merge_inherits_parent_themes_and_transition() -> None:
    left = _variant(
        content=NarrativeContent(
            concepts=("water", "gone", "river"), text="tell_story"
        ),
    )
    right = _variant(
        content=NarrativeContent(
            concepts=("water", "gone", "river", "fish"), text="tell_story"
        ),
        themes=(NarrativeTheme.DISASTERS,),
        theme_basis=NarrativeThemeBasis.OBSERVED_OCCURRENCE_KIND,
    )
    ledger = apply_narrative_update(
        observation=_observation(tick=2),
        identity=_identity(),
        previous=_ledger(left, right),
        policy=default_generational_narrative_policy(),
    )
    merged = next(
        variant
        for variant in ledger.variants
        if variant.content.text == "merge_story"
    )
    assert merged.themes == (
        NarrativeTheme.FOUNDERS,
        NarrativeTheme.DISASTERS,
    )
    assert merged.theme_basis is NarrativeThemeBasis.INHERITED_LINEAGE
    assert any(
        transition.kind.value == "merged" for transition in merged.transitions
    )


def test_unmapped_observation_remains_unclassified() -> None:
    from tests.unit.test_cultural_narratives import _occurrence

    ledger = apply_narrative_update(
        observation=_observation(
            tick=2, occurrences=(_occurrence("talk", 2, "evt-talk"),)
        ),
        identity=_identity(),
        previous=_ledger(),
        policy=default_generational_narrative_policy(),
    )
    variant = ledger.variants[0]
    assert variant.themes == ()
    assert variant.theme_basis is NarrativeThemeBasis.UNCLASSIFIED


def test_reconstruction_inherits_parent_theme() -> None:
    from agents.cognition.cultural_narratives import NarrativeCueSummary

    parent = _variant(transmission_root_id="root-1")
    ledger = apply_narrative_update(
        observation=_observation(tick=2),
        identity=_identity(),
        previous=_ledger(parent),
        cues=NarrativeCueSummary(
            reconstructions=(
                (
                    "recon-1",
                    ("memory-1",),
                    ("river", "flood"),
                    (),
                ),
            )
        ),
        policy=default_generational_narrative_policy(),
    )
    child = next(
        variant
        for variant in ledger.variants
        if variant.variant_id != parent.variant_id
    )
    assert NarrativeTheme.FOUNDERS in child.themes
    assert child.theme_basis is NarrativeThemeBasis.INHERITED_LINEAGE
