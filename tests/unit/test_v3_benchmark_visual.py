"""Visual acceptance marker selection for the V3 release fixture."""

from __future__ import annotations

from types import SimpleNamespace

from experiments.civilization_benchmark_evidence import OwnerStoreSnapshot
from experiments.civilization_benchmark_visual import (
    VisualMarkerKind,
    VisualMarkerStatus,
    build_visual_marker_manifest,
    require_all_visual_markers,
)


def _owner() -> OwnerStoreSnapshot:
    return OwnerStoreSnapshot(
        owner_id="agent-a",
        entity_id="body-a",
        generation_index=0,
        living=True,
        invocation_count=1,
        counts=(("practical_knowledge", 2),),
        measured_stores=("practical_knowledge",),
        unmeasured_stores=(),
        teaching_audits=1,
        cultural_audits=1,
    )


def test_eight_markers_come_from_real_evidence_channels() -> None:
    owner = _owner()
    owner_b = OwnerStoreSnapshot(
        owner_id="agent-b",
        entity_id="body-b",
        generation_index=1,
        living=True,
        invocation_count=1,
        counts=(("practical_knowledge", 0),),
        measured_stores=("practical_knowledge",),
        unmeasured_stores=(),
        cultural_audits=1,
    )
    observations = [
        SimpleNamespace(boundary_tick=0, owners=(owner,), new_owners=(owner,)),
        SimpleNamespace(
            boundary_tick=4, owners=(owner, owner_b), new_owners=(owner_b,)
        ),
    ]
    probe = SimpleNamespace(
        observations=observations,
        death_ticks_by_body=(("body-b", 3),),
        event_total=lambda kind: 1 if kind == "JourneyStarted" else 2,
    )
    office = SimpleNamespace(
        owner_id=SimpleNamespace(value="agent-a"),
        concepts=(SimpleNamespace(succession=(object(),)),),
    )
    markers = build_visual_marker_manifest(
        probe,  # type: ignore[arg-type]
        SimpleNamespace(office_concept_ledgers=(office,)),
    )
    assert {marker.kind for marker in markers} == set(VisualMarkerKind)
    assert all(marker.status is VisualMarkerStatus.AVAILABLE for marker in markers)
    assert require_all_visual_markers(markers) == ()
    by_kind = {marker.kind: marker for marker in markers}
    assert by_kind[VisualMarkerKind.CULTURAL_DIFFERENTIATION].owner_ids == (
        "agent-a",
        "agent-b",
    )
    assert by_kind[VisualMarkerKind.OFFICE_SUCCESSION].owner_ids == ("agent-a",)


def test_missing_channels_stay_explicitly_unavailable() -> None:
    empty = SimpleNamespace(
        observations=[],
        death_ticks_by_body=(),
        event_total=lambda kind: 0,
    )
    markers = build_visual_marker_manifest(
        empty,  # type: ignore[arg-type]
        SimpleNamespace(office_concept_ledgers=()),
    )
    assert len(markers) == len(VisualMarkerKind)
    assert all(marker.status is VisualMarkerStatus.UNAVAILABLE for marker in markers)
    assert set(require_all_visual_markers(markers)) == {
        kind.value for kind in VisualMarkerKind
    }
