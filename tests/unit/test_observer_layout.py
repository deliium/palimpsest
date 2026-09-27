"""Presentation catalogs stay off the simulation graph."""

from __future__ import annotations

import pytest

from experiments.reference_scenario import (
    LOC_CAMP,
    LOC_GROVE,
    LOC_RIDGE,
    LOC_SPRING,
    _build_locations,
)
from observer.layout import (
    LocationVisualSpec,
    ObserverLayoutError,
    assign_slots,
    load_layout,
    validate_layout,
)
from observer.version import OBSERVER_LAYOUT_SCHEMA_VERSION
from tests.simulation_helpers import make_location

pytestmark = pytest.mark.unit


def test_reference_layout_matches_canonical_locations() -> None:
    catalog = load_layout("reference-v1")
    assert catalog.schema_version == OBSERVER_LAYOUT_SCHEMA_VERSION
    assert catalog.layout_id == "reference-v1"
    validate_layout(catalog, _build_locations())
    assert catalog.spec_for(LOC_CAMP) is not None
    assert catalog.spec_for(LOC_SPRING) is not None
    assert catalog.spec_for(LOC_GROVE) is not None
    assert catalog.spec_for(LOC_RIDGE) is not None
    first = catalog.content_hash()
    assert load_layout("reference-v1").content_hash() == first


def test_unknown_location_and_visual_edge_fail_closed() -> None:
    catalog = load_layout("reference-v1")
    camp = make_location(LOC_CAMP, name="Camp", adjacent=(LOC_SPRING,))
    with pytest.raises(ObserverLayoutError) as unknown:
        validate_layout(catalog, (camp,))
    assert unknown.value.reason_code == "unknown_location_id"
    broken = catalog.spec_for(LOC_CAMP)
    assert broken is not None
    bad = type(catalog)(
        layout_id="reference-v1",
        schema_version=OBSERVER_LAYOUT_SCHEMA_VERSION,
        specs=(
            LocationVisualSpec(
                location_id=LOC_CAMP,
                display_name="Camp",
                screen_position=broken.screen_position,
                visual_bounds=broken.visual_bounds,
                theme=broken.theme,
                icon_ref=broken.icon_ref,
                background_ref=broken.background_ref,
                connection_anchors=(("loc-nowhere", broken.slot_anchors[0]),),
                slot_anchors=broken.slot_anchors,
            ),
        ),
    )
    with pytest.raises(ObserverLayoutError) as edge:
        validate_layout(bad, (camp,))
    assert edge.value.reason_code == "visual_edge_not_in_graph"


def test_slots_are_deterministic_and_omit_coords_without_bounds() -> None:
    catalog = load_layout("reference-v1")
    spec = catalog.spec_for(LOC_CAMP)
    assert spec is not None
    first = assign_slots(LOC_CAMP, ("body-b", "body-a", "body-c", "body-d"), spec)
    second = assign_slots(LOC_CAMP, ("body-d", "body-a", "body-c", "body-b"), spec)
    assert first == second
    assert [item.entity_id for item in first] == [
        "body-a",
        "body-b",
        "body-c",
        "body-d",
    ]
    assert first[0].slot_index == 0
    assert first[0].local_x == spec.slot_anchors[0].x
    assert first[3].local_x is not None
    bare = LocationVisualSpec(
        location_id=LOC_CAMP,
        display_name="Camp",
        screen_position=None,
        visual_bounds=None,
        theme=None,
        icon_ref=None,
        background_ref=None,
        connection_anchors=(),
        slot_anchors=(),
    )
    empty = assign_slots(LOC_CAMP, ("body-b", "body-a"), bare)
    assert empty[0].slot_index == 0
    assert empty[0].local_x is None
    assert empty[0].local_y is None
    assert empty[1].local_x is None
