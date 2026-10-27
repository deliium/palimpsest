"""Pinned boundary sampling, one-snapshot reuse and neutral page contracts."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from experiments.composition import load_paged_analysis_snapshot
from experiments.persistence import (
    ObjectiveEventPage,
    PersistedAnalysisSnapshot,
    PersistedDerivationEdge,
    PersistedReconstructionRow,
    PersistedRegionalContext,
    PersistedRegionalInitialPlacement,
    PersistedRegionalLocation,
    SubjectiveEvidencePage,
    iter_subjective_evidence_pages,
)
from research_runner.generational_composition import PostgresCommunitySampleProvider
from simulation.evidence import (
    EvidenceHighWaterMarks,
    EvidenceManifest,
    build_evidence_manifest,
)
from simulation.generational_models import GenerationalBoundary, PopulationProgress

pytestmark = pytest.mark.unit

_RUN = "run-community-loading"
_OWNER = "agent-1"


def _snapshot(
    *,
    run_id: str = _RUN,
    owner_id: str = _OWNER,
    high_water: int = 6,
    events: tuple[object, ...] = (),
) -> PersistedAnalysisSnapshot:
    return PersistedAnalysisSnapshot(
        experiment_id="",
        run_id=run_id,
        owner_id=owner_id,
        traces=(),
        reconstructions=(),
        derivation_edges=(),
        events=events,
        regional_context=PersistedRegionalContext(
            region_ids=("region-1",),
            known_location_ids=("loc-1",),
            locations=(PersistedRegionalLocation("loc-1", "region-1"),),
            initial_placements=(
                PersistedRegionalInitialPlacement("body-1", "loc-1", True),
            ),
            owner_ids=(owner_id,),
            residence_min_ticks=1,
        ),
        objective_complete_through_boundary=high_water,
    )


def _reconstruction(reconstruction_id: str) -> PersistedReconstructionRow:
    return PersistedReconstructionRow(
        reconstruction_id=reconstruction_id,
        source_memory_ids=(),
        created_tick=1,
        generation=0,
        policy_id="policy-1",
        policy_version="1",
        used_provider=False,
        fallback_used=False,
        prompt_version=None,
        schema_version=None,
        payload_sha256="a" * 64,
    )


def _edge(derived_memory_id: str) -> PersistedDerivationEdge:
    return PersistedDerivationEdge(
        derived_memory_id=derived_memory_id,
        source_memory_id="memory-0",
        ordinal=0,
        reconstruction_id=None,
    )


def _boundary(tick: int) -> GenerationalBoundary:
    return GenerationalBoundary(
        progress=PopulationProgress(
            boundary_tick=tick,
            living_population=1,
            total_admitted=1,
            total_deaths=0,
            max_generation_index_seen=0,
        ),
        objective_revision=tick,
        last_completed_tick=max(0, tick - 1),
    )


class _CountingLoader:
    def __init__(self, snapshot: PersistedAnalysisSnapshot) -> None:
        self.snapshot = snapshot
        self.calls: list[tuple[str, str]] = []

    async def load(self, *, run_id: str, owner_id: str) -> object:
        self.calls.append((run_id, owner_id))
        return self.snapshot


def _created_event(
    tick: int,
    body: str,
    agent: str,
    *,
    generation: int = 0,
    cohort: str = "cohort-0",
) -> object:
    return SimpleNamespace(
        tick=SimpleNamespace(value=tick),
        details=SimpleNamespace(
            kind="agent_created",
            body_id=SimpleNamespace(value=body),
            agent_id=agent,
            generation_index=generation,
            cohort_id=cohort,
        ),
    )


@pytest.mark.asyncio
async def test_sample_uses_one_snapshot_and_caches_exact_boundary() -> None:
    loader = _CountingLoader(_snapshot(high_water=6))
    provider = PostgresCommunitySampleProvider(
        loader=loader,
        run_id=_RUN,
        owner_id=_OWNER,
    )
    first = await provider.sample(_boundary(5))
    second = await provider.sample(_boundary(5))
    assert loader.calls == [(_RUN, _OWNER)]
    assert second == first
    await provider.sample(_boundary(6))
    assert loader.calls == [(_RUN, _OWNER), (_RUN, _OWNER)]
    assert provider._sample_cache[(5, provider.input_revision)] == first


def test_identities_are_pinned_and_stable_after_death() -> None:
    events = (
        _created_event(1, "body-1", "agent-1"),
        _created_event(3, "body-2", "agent-2", generation=1, cohort="cohort-1"),
        _created_event(5, "body-3", "agent-3", generation=2, cohort="cohort-2"),
    )
    provider = PostgresCommunitySampleProvider(
        loader=object(),
        run_id=_RUN,
        owner_id=_OWNER,
    )
    snapshot = _snapshot(high_water=5, events=events)
    rows_three = provider.identities(_boundary(3), snapshot=snapshot)
    assert [(row.body_id, row.agent_id) for row in rows_three] == [
        ("body-1", "agent-1"),
        ("body-2", "agent-2"),
    ]
    rows_five = provider.identities(_boundary(5), snapshot=snapshot)
    assert [(row.body_id, row.agent_id) for row in rows_five] == [
        ("body-1", "agent-1"),
        ("body-2", "agent-2"),
        ("body-3", "agent-3"),
    ]
    assert provider._identity_high_water == 5
    assert provider.identities(_boundary(4), snapshot=snapshot) == rows_three


def test_identity_index_rebuilds_only_when_high_water_advances() -> None:
    provider = PostgresCommunitySampleProvider(
        loader=object(),
        run_id=_RUN,
        owner_id=_OWNER,
    )
    first = _snapshot(
        high_water=5,
        events=(_created_event(1, "body-1", "agent-1"),),
    )
    provider.identities(_boundary(5), snapshot=first)
    built = provider._identity_rows
    provider.identities(_boundary(5), snapshot=first)
    assert provider._identity_rows is built
    second = _snapshot(
        high_water=7,
        events=(
            _created_event(1, "body-1", "agent-1"),
            _created_event(7, "body-2", "agent-2", generation=1),
        ),
    )
    rows = provider.identities(_boundary(7), snapshot=second)
    assert [row.body_id for row in rows] == ["body-1", "body-2"]
    assert provider._identity_high_water == 7


@pytest.mark.asyncio
async def test_cross_run_and_owner_samples_are_isolated() -> None:
    first_loader = _CountingLoader(_snapshot(run_id="run-a", owner_id="agent-a"))
    second_loader = _CountingLoader(_snapshot(run_id="run-b", owner_id="agent-b"))
    first = PostgresCommunitySampleProvider(
        loader=first_loader, run_id="run-a", owner_id="agent-a"
    )
    second = PostgresCommunitySampleProvider(
        loader=second_loader, run_id="run-b", owner_id="agent-b"
    )
    await first.sample(_boundary(5))
    await second.sample(_boundary(5))
    assert first_loader.calls == [("run-a", "agent-a")]
    assert second_loader.calls == [("run-b", "agent-b")]
    assert first._sample_cache is not second._sample_cache


def test_page_contracts_fail_closed_on_invalid_cursors() -> None:
    page = ObjectiveEventPage(
        run_id=_RUN,
        events=(),
        complete_through_boundary=5,
        next_tick=None,
        next_sequence=None,
    )
    assert page.exhausted is True
    with pytest.raises(ValueError, match="next_tick and next_sequence"):
        ObjectiveEventPage(
            run_id=_RUN,
            events=(),
            complete_through_boundary=5,
            next_tick=1,
            next_sequence=None,
        )
    subjective = SubjectiveEvidencePage(
        run_id=_RUN,
        owner_id=_OWNER,
        lane="direct_traces",
    )
    assert subjective.exhausted is True
    with pytest.raises(ValueError, match="run_id"):
        SubjectiveEvidencePage(
            run_id="",
            owner_id=_OWNER,
            lane="direct_traces",
        )
    with pytest.raises(ValueError, match="invalid_subjective_lane"):
        SubjectiveEvidencePage(
            run_id=_RUN,
            owner_id=_OWNER,
            lane="unknown",
        )
    with pytest.raises(ValueError, match="subjective_page_mixed_lanes"):
        SubjectiveEvidencePage(
            run_id=_RUN,
            owner_id=_OWNER,
            lane="reconstructions",
            reconstructions=(_reconstruction("recon-1"),),
            derivation_edges=(_edge("memory-1"),),
        )
    with pytest.raises(ValueError, match="subjective_page_cursor_shape"):
        SubjectiveEvidencePage(
            run_id=_RUN,
            owner_id=_OWNER,
            lane="reconstructions",
            reconstructions=(_reconstruction("recon-1"),),
            next_id="recon-1",
        )
    with pytest.raises(ValueError, match="subjective_page_empty_with_cursor"):
        SubjectiveEvidencePage(
            run_id=_RUN,
            owner_id=_OWNER,
            lane="direct_traces",
            next_tick=1,
            next_id="memory-1",
        )


@pytest.mark.asyncio
async def test_objective_page_iterator_rejects_boundary_and_cursor_regressions() -> (
    None
):
    from experiments.persistence import iter_objective_event_pages

    class _Reader:
        def __init__(self, pages: list[ObjectiveEventPage]) -> None:
            self.pages = pages
            self.calls: list[dict[str, object]] = []

        async def load_objective_event_page(
            self,
            *,
            run_id: str,
            manifest: EvidenceManifest | None = None,
            after_tick: int | None = None,
            after_sequence: int | None = None,
            limit: int = 1_000,
        ) -> ObjectiveEventPage:
            self.calls.append(
                {
                    "run_id": run_id,
                    "manifest": manifest,
                    "after_tick": after_tick,
                    "after_sequence": after_sequence,
                    "limit": limit,
                }
            )
            return self.pages.pop(0)

        async def load_subjective_evidence_page(
            self,
            *,
            run_id: str,
            owner_id: str,
            manifest: EvidenceManifest | None = None,
            lane: str = "direct_traces",
            after_tick: int | None = None,
            after_id: str | None = None,
            after_ordinal: int | None = None,
            limit: int = 1_000,
        ) -> SubjectiveEvidencePage:
            return SubjectiveEvidencePage(run_id=run_id, owner_id=owner_id, lane=lane)

    def _page(
        events: tuple[object, ...],
        *,
        boundary: int = 5,
        next_tick: int | None = None,
        next_sequence: int | None = None,
    ) -> ObjectiveEventPage:
        return ObjectiveEventPage(
            run_id=_RUN,
            events=events,
            complete_through_boundary=boundary,
            next_tick=next_tick,
            next_sequence=next_sequence,
        )

    reader = _Reader(
        [
            _page(("e1", "e2"), next_tick=2, next_sequence=3),
            _page(("e3",)),
        ]
    )
    events = [
        event
        async for event in iter_objective_event_pages(reader, run_id=_RUN, limit=2)
    ]
    assert events == ["e1", "e2", "e3"]
    assert reader.calls[1]["after_tick"] == 2
    assert reader.calls[1]["after_sequence"] == 3

    changed = _Reader(
        [
            _page(("e1",), next_tick=1, next_sequence=0),
            _page(("e2",), boundary=6),
        ]
    )
    with pytest.raises(ValueError, match="page_boundary_changed"):
        async for _event in iter_objective_event_pages(changed, run_id=_RUN):
            pass

    nonadvancing = _Reader(
        [
            _page(("e1",), next_tick=2, next_sequence=3),
            _page(("e2",), next_tick=2, next_sequence=3),
            _page(("e3",)),
        ]
    )
    with pytest.raises(ValueError, match="page_cursor_nonadvancing"):
        async for _event in iter_objective_event_pages(nonadvancing, run_id=_RUN):
            pass


@pytest.mark.asyncio
async def test_sample_cache_respects_byte_budget() -> None:
    loader = _CountingLoader(_snapshot(high_water=6))
    provider = PostgresCommunitySampleProvider(
        loader=loader, run_id=_RUN, owner_id=_OWNER
    )
    provider._cache_byte_limit = 1
    await provider.sample(_boundary(5))
    await provider.sample(_boundary(5))
    assert loader.calls == [(_RUN, _OWNER), (_RUN, _OWNER)]
    assert provider._sample_cache == {}
    assert provider._sample_cache_bytes == {}

    provider._cache_byte_limit = 8 * 1024 * 1024
    await provider.sample(_boundary(6))
    assert provider._sample_cache_bytes[(6, provider.input_revision)] > 0
    assert sum(provider._sample_cache_bytes.values()) <= provider._cache_byte_limit


def _manifest() -> EvidenceManifest:
    return build_evidence_manifest(
        run_id=_RUN,
        objective_commit_hash="b" * 64,
        high_water=EvidenceHighWaterMarks(
            direct_memories=1,
            communicated_memories=0,
            reconstructions=0,
            beliefs=0,
            relationships=0,
            goals=0,
            resolutions=0,
            truth_specs=0,
        ),
    )


class _PagedReader:
    def __init__(
        self,
        *,
        pages: list[ObjectiveEventPage],
        context: PersistedRegionalContext | None,
        subjective_pages: list[SubjectiveEvidencePage] | None = None,
    ) -> None:
        self.pages = list(pages)
        self.context = context
        self.subjective_pages = list(subjective_pages or ())
        self.objective_calls: list[tuple[int | None, int | None]] = []
        self.subjective_calls: list[str] = []
        self.load_calls = 0

    async def load(self, **kwargs: object) -> object:
        self.load_calls += 1
        return _snapshot()

    async def load_regional_context(self, *, run_id: str) -> object:
        assert run_id == _RUN
        return self.context

    async def load_objective_event_page(
        self,
        *,
        run_id: str,
        manifest: EvidenceManifest | None = None,
        after_tick: int | None = None,
        after_sequence: int | None = None,
        limit: int = 1_000,
    ) -> ObjectiveEventPage:
        self.objective_calls.append((after_tick, after_sequence))
        if not self.pages:
            return ObjectiveEventPage(
                run_id=run_id,
                events=(),
                complete_through_boundary=5,
                next_tick=None,
                next_sequence=None,
            )
        return self.pages.pop(0)

    async def load_subjective_evidence_page(
        self,
        *,
        run_id: str,
        owner_id: str,
        manifest: EvidenceManifest | None = None,
        lane: str = "direct_traces",
        after_tick: int | None = None,
        after_id: str | None = None,
        after_ordinal: int | None = None,
        limit: int = 1_000,
    ) -> SubjectiveEvidencePage:
        self.subjective_calls.append(lane)
        for index, page in enumerate(self.subjective_pages):
            if page.lane == lane:
                return self.subjective_pages.pop(index)
        return SubjectiveEvidencePage(
            run_id=run_id,
            owner_id=owner_id,
            lane=lane,
            manifest_hash=None if manifest is None else manifest.manifest_hash,
        )


@pytest.mark.asyncio
async def test_paged_snapshot_streams_objective_pages_without_full_load() -> None:
    first = _created_event(1, "body-1", "agent-1")
    second = _created_event(2, "body-2", "agent-2")
    third = _created_event(3, "body-3", "agent-3")
    context = _snapshot().regional_context
    reader = _PagedReader(
        pages=[
            ObjectiveEventPage(
                run_id=_RUN,
                events=(first, second),
                complete_through_boundary=5,
                next_tick=2,
                next_sequence=7,
            ),
            ObjectiveEventPage(
                run_id=_RUN,
                events=(third,),
                complete_through_boundary=5,
            ),
        ],
        context=context,
    )
    snapshot = await load_paged_analysis_snapshot(
        reader,
        run_id=_RUN,
        owner_id=_OWNER,
        page_limit=2,
        include_subjective=False,
    )
    assert snapshot.events == (first, second, third)
    assert snapshot.traces == ()
    assert snapshot.reconstructions == ()
    assert snapshot.derivation_edges == ()
    assert snapshot.regional_context == context
    assert snapshot.objective_complete_through_boundary == 5
    assert reader.objective_calls == [(None, None), (2, 7)]
    assert reader.load_calls == 0
    assert reader.subjective_calls == []


@pytest.mark.asyncio
async def test_paged_snapshot_collects_subjective_lanes_in_order() -> None:
    reconstruction = _reconstruction("recon-1")
    edge = _edge("memory-1")
    reader = _PagedReader(
        pages=[
            ObjectiveEventPage(
                run_id=_RUN,
                events=(),
                complete_through_boundary=5,
            )
        ],
        context=_snapshot().regional_context,
        subjective_pages=[
            SubjectiveEvidencePage(
                run_id=_RUN,
                owner_id=_OWNER,
                lane="reconstructions",
                reconstructions=(reconstruction,),
            ),
            SubjectiveEvidencePage(
                run_id=_RUN,
                owner_id=_OWNER,
                lane="derivation_edges",
                derivation_edges=(edge,),
            ),
        ],
    )
    snapshot = await load_paged_analysis_snapshot(
        reader, run_id=_RUN, owner_id=_OWNER, include_subjective=True
    )
    assert snapshot.events == ()
    assert snapshot.reconstructions == (reconstruction,)
    assert snapshot.derivation_edges == (edge,)
    assert reader.subjective_calls == [
        "direct_traces",
        "communicated_traces",
        "reconstructions",
        "derivation_edges",
    ]


@pytest.mark.asyncio
async def test_paged_snapshot_falls_back_to_full_load_for_legacy_reader() -> None:
    loader = _CountingLoader(_snapshot(high_water=6))
    snapshot = await load_paged_analysis_snapshot(
        loader, run_id=_RUN, owner_id=_OWNER, include_subjective=False
    )
    assert loader.calls == [(_RUN, _OWNER)]
    assert snapshot.objective_complete_through_boundary == 6


@pytest.mark.asyncio
async def test_subjective_page_iterator_rejects_lane_and_cursor_regressions() -> None:
    manifest = _manifest()

    class _Reader:
        def __init__(self, pages: list[SubjectiveEvidencePage]) -> None:
            self.pages = list(pages)
            self.calls: list[dict[str, object]] = []

        async def load_subjective_evidence_page(
            self, **kwargs: object
        ) -> SubjectiveEvidencePage:
            self.calls.append(kwargs)
            lane = kwargs["lane"]
            manifest_arg = kwargs.get("manifest")
            manifest_hash = (
                None
                if manifest_arg is None
                else getattr(manifest_arg, "manifest_hash", None)
            )
            for index, page in enumerate(self.pages):
                if page.lane == lane:
                    return self.pages.pop(index)
            return SubjectiveEvidencePage(
                run_id=_RUN,
                owner_id=_OWNER,
                lane=str(lane),
                manifest_hash=manifest_hash,
            )

    class _FixedReader:
        def __init__(self, page: SubjectiveEvidencePage) -> None:
            self.page = page

        async def load_subjective_evidence_page(
            self, **kwargs: object
        ) -> SubjectiveEvidencePage:
            return self.page

    wrong_lane = _FixedReader(
        SubjectiveEvidencePage(
            run_id=_RUN,
            owner_id=_OWNER,
            lane="reconstructions",
            manifest_hash=manifest.manifest_hash,
        )
    )
    with pytest.raises(ValueError, match="page_lane_mismatch"):
        async for _page in iter_subjective_evidence_pages(
            wrong_lane, run_id=_RUN, owner_id=_OWNER, manifest=manifest
        ):
            pass

    nonadvancing = _Reader(
        [
            SubjectiveEvidencePage(
                run_id=_RUN,
                owner_id=_OWNER,
                lane="reconstructions",
                reconstructions=(_reconstruction("recon-2"),),
                next_tick=1,
                next_id="recon-2",
                manifest_hash=manifest.manifest_hash,
            ),
            SubjectiveEvidencePage(
                run_id=_RUN,
                owner_id=_OWNER,
                lane="reconstructions",
                reconstructions=(_reconstruction("recon-3"),),
                next_tick=1,
                next_id="recon-2",
                manifest_hash=manifest.manifest_hash,
            ),
        ]
    )
    with pytest.raises(ValueError, match="page_cursor_nonadvancing"):
        async for _page in iter_subjective_evidence_pages(
            nonadvancing, run_id=_RUN, owner_id=_OWNER, manifest=manifest
        ):
            pass
    assert nonadvancing.calls[0]["lane"] == "direct_traces"
    assert nonadvancing.calls[1]["lane"] == "communicated_traces"

    changed_manifest = _Reader(
        [
            SubjectiveEvidencePage(
                run_id=_RUN,
                owner_id=_OWNER,
                lane="reconstructions",
                reconstructions=(_reconstruction("recon-2"),),
                next_tick=1,
                next_id="recon-2",
                manifest_hash=manifest.manifest_hash,
            ),
            SubjectiveEvidencePage(
                run_id=_RUN,
                owner_id=_OWNER,
                lane="reconstructions",
                reconstructions=(_reconstruction("recon-3"),),
                manifest_hash="c" * 64,
            ),
        ]
    )
    with pytest.raises(ValueError, match="page_manifest_changed"):
        async for _page in iter_subjective_evidence_pages(
            changed_manifest, run_id=_RUN, owner_id=_OWNER, manifest=manifest
        ):
            pass

    advancing = _Reader(
        [
            SubjectiveEvidencePage(
                run_id=_RUN,
                owner_id=_OWNER,
                lane="reconstructions",
                reconstructions=(_reconstruction("recon-2"),),
                next_tick=1,
                next_id="recon-2",
                manifest_hash=manifest.manifest_hash,
            ),
            SubjectiveEvidencePage(
                run_id=_RUN,
                owner_id=_OWNER,
                lane="reconstructions",
                reconstructions=(_reconstruction("recon-3"),),
                manifest_hash=manifest.manifest_hash,
            ),
        ]
    )
    pages = [
        page
        async for page in iter_subjective_evidence_pages(
            advancing, run_id=_RUN, owner_id=_OWNER, manifest=manifest
        )
    ]
    assert [page.lane for page in pages].count("reconstructions") == 2
    recon_calls = [
        call for call in advancing.calls if call["lane"] == "reconstructions"
    ]
    assert recon_calls[1]["after_tick"] == 1
    assert recon_calls[1]["after_id"] == "recon-2"


@pytest.mark.asyncio
async def test_provider_builds_paged_snapshot_without_full_load() -> None:
    event = _created_event(1, "body-1", "agent-1")
    reader = _PagedReader(
        pages=[
            ObjectiveEventPage(
                run_id=_RUN,
                events=(event,),
                complete_through_boundary=5,
            )
        ],
        context=_snapshot().regional_context,
    )
    provider = PostgresCommunitySampleProvider(
        loader=reader, run_id=_RUN, owner_id=_OWNER, page_limit=10
    )
    snapshot = await provider._snapshot()
    assert isinstance(snapshot, PersistedAnalysisSnapshot)
    assert snapshot.events == (event,)
    assert reader.load_calls == 0
    assert reader.subjective_calls == []


def test_identity_index_extends_only_through_new_events() -> None:
    provider = PostgresCommunitySampleProvider(
        loader=object(), run_id=_RUN, owner_id=_OWNER
    )
    first_event = _created_event(1, "body-1", "agent-1")
    first = _snapshot(high_water=5, events=(first_event,))
    assert [
        (row.body_id, row.agent_id)
        for row in provider.identities(_boundary(5), snapshot=first)
    ] == [("body-1", "agent-1")]
    assert provider._identity_event_count == 1
    second_event = _created_event(3, "body-2", "agent-2", generation=1)
    second = _snapshot(high_water=7, events=(first_event, second_event))
    rows = provider.identities(_boundary(7), snapshot=second)
    assert [(row.body_id, row.agent_id) for row in rows] == [
        ("body-1", "agent-1"),
        ("body-2", "agent-2"),
    ]
    assert provider._identity_event_count == 2
    assert [
        row.body_id for row in provider.identities(_boundary(1), snapshot=second)
    ] == ["body-1"]


def test_identity_index_rebuilds_when_prefix_changes() -> None:
    provider = PostgresCommunitySampleProvider(
        loader=object(), run_id=_RUN, owner_id=_OWNER
    )
    first = _snapshot(high_water=5, events=(_created_event(1, "body-1", "agent-1"),))
    provider.identities(_boundary(5), snapshot=first)
    assert provider._identity_event_count == 1
    rewritten = _snapshot(
        high_water=7,
        events=(_created_event(2, "body-9", "agent-9"),),
    )
    rows = provider.identities(_boundary(7), snapshot=rewritten)
    assert [(row.body_id, row.agent_id) for row in rows] == [
        ("body-9", "agent-9"),
    ]
    assert provider._identity_event_count == 1
