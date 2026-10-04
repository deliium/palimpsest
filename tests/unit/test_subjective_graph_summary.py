"""Metadata-safe subjective graph summary mapping."""

from __future__ import annotations

import pytest

from api.persistence_services import PersistenceInspectionService
from api.schemas import AvailabilityOut
from simulation.inspection import (
    InspectionAvailability,
    MemoryKeysetCursor,
    SubjectiveGraphNodeSummary,
    SubjectiveGraphSummaryPage,
)
from simulation.models import RunId

pytestmark = pytest.mark.unit


class _FakeRuns:
    async def get_run(self, run_id: RunId) -> object:
        return object()


class _FakeSubjective:
    async def load_graph_summary_page(
        self,
        *,
        run_id: str,
        owner_id: str,
        kind: str,
        after: MemoryKeysetCursor | None = None,
        limit: int = 100,
    ) -> SubjectiveGraphSummaryPage:
        del after
        return SubjectiveGraphSummaryPage(
            run_id=run_id,
            owner_id=owner_id,
            kind=kind,
            limit=limit,
            items=(
                SubjectiveGraphNodeSummary(
                    node_id="mem-1",
                    created_tick=2,
                    source_kind="direct_observation",
                    strength=0.8,
                    target_id=None,
                    lineage_ref_ids=("rev-1",),
                ),
            ),
            next_cursor=None,
            availability=InspectionAvailability.AVAILABLE,
        )


class _FakeEvidence:
    def __init__(self) -> None:
        self.subjective = _FakeSubjective()

    @property
    def objective(self) -> object:
        raise AssertionError("objective unused")


class _FakeReplay:
    pass


@pytest.mark.asyncio
async def test_persistence_graph_summary_maps_metadata_only() -> None:
    service = PersistenceInspectionService(
        evidence=_FakeEvidence(),  # type: ignore[arg-type]
        runs=_FakeRuns(),  # type: ignore[arg-type]
        replay=_FakeReplay(),  # type: ignore[arg-type]
    )
    page = await service.graph_summary_page(
        "run-1", "alice", kind="memories", after=None, limit=10
    )
    assert page.availability is AvailabilityOut.AVAILABLE
    assert page.count == 1
    item = page.items[0]
    assert item.node_id == "mem-1"
    assert item.source_kind == "direct_observation"
    assert item.lineage_ref_ids == ("rev-1",)
    blob = str(page.model_dump()).lower()
    for forbidden in ("proposition", "utterance", "prompt", "narrative"):
        assert forbidden not in blob
