"""SUBJECTIVE narrative hop projection omits content tokens."""

from __future__ import annotations

from types import SimpleNamespace

from observer.narrative_hops import project_narrative_hop_overlay


def test_projects_hop_fields_without_content() -> None:
    ledger = SimpleNamespace(
        variants=(
            SimpleNamespace(
                variant_id="aa" * 16,
                status=SimpleNamespace(value="active"),
                origin=SimpleNamespace(value="retold_story"),
                carrier_agent_ids=("ada", "bo"),
                location_ids=("loc-camp",),
                parent_variant_ids=("bb" * 16,),
                merged_into_id=None,
                transmission_root_id="cc" * 16,
                source_event_id="evt-1",
                last_communication_id="evt-2",
                strength=0.8,
                content=SimpleNamespace(concepts=("secret-story-token",)),
                content_fingerprint="dd" * 16,
            ),
        )
    )
    overlay = project_narrative_hop_overlay("ada", ledger)
    assert overlay.count == 1
    assert overlay.evidence_class == "SUBJECTIVE_TO_SELECTED_AGENT"
    row = overlay.variants[0]
    assert row.carrier_agent_ids == ("ada", "bo")
    assert row.location_ids == ("loc-camp",)
    assert row.strength_band == "high"
    payload = str(row)
    assert "secret-story-token" not in payload


def test_empty_ledger_is_empty_selector() -> None:
    overlay = project_narrative_hop_overlay("ada", None)
    assert overlay.count == 0
