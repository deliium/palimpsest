"""End-to-end: harvest to published snapshot and layer separation."""

from __future__ import annotations

from pathlib import Path

from analysis.macro_society_contract import MacroSocietyLane
from analysis.macro_society_evidence import (
    MacroSocietyEdge,
    MacroSocietyToken,
    MacroSocietyWindowEvidence,
)
from experiments.macro_society_publication import (
    MacroSocietyHarvest,
    build_macro_society_harvest_result,
)
from persistence.macro_society_filesystem import (
    create_macro_society_publisher,
    create_macro_society_reader,
)
from simulation.macro_society_codec import encode_macro_society_snapshot
from simulation.macro_society_ports import MacroSocietyPublication

PERSONS = tuple(f"person-{index}" for index in range(1, 13))


def _clique(members: tuple[str, ...], tick: int) -> tuple[MacroSocietyEdge, ...]:
    return tuple(
        MacroSocietyEdge(MacroSocietyLane.INTERACTION, source, target, tick)
        for index, source in enumerate(members)
        for target in members[index + 1 :]
    )


def _window(
    index: int, members: tuple[str, ...], *, token: str | None = None
) -> MacroSocietyWindowEvidence:
    tokens = (
        tuple(
            MacroSocietyToken(MacroSocietyLane.CULTURE, person, token)
            for person in members
        )
        if token is not None
        else ()
    )
    return MacroSocietyWindowEvidence(
        window_index=index,
        tick_start=index * 10,
        tick_end=index * 10 + 9,
        person_ids=PERSONS,
        edges=_clique(members, index * 10),
        tokens=tokens,
    )


def _harvest() -> MacroSocietyHarvest:
    windows = (
        _window(0, PERSONS[:6]),
        _window(1, PERSONS[:6], token="trait-1"),
        _window(2, PERSONS[:3]),
        _window(3, (PERSONS[0], PERSONS[1], PERSONS[2], PERSONS[6])),
        _window(4, PERSONS[6:12]),
    )
    return MacroSocietyHarvest(
        run_id="run-1",
        input_revision="rev-1",
        windows=windows,
        objective_rows=(
            {"region_id": "region-a", "tick": 0, "population_count": 12},
            {"region_id": "region-b", "tick": 0, "population_count": 6},
        ),
        subjective_rows=(
            {"owner_id": "person-1", "lane": "culture", "local_token_id": "trait-1"},
        ),
        generated_tick=49,
    )


def test_harvest_publishes_and_reads_back(tmp_path: Path) -> None:
    result = build_macro_society_harvest_result(_harvest())
    publisher = create_macro_society_publisher(tmp_path)
    reader = create_macro_society_reader(tmp_path)
    assert publisher is not None and reader is not None
    publisher.publish(
        MacroSocietyPublication(
            snapshot=result.snapshot,
            payload=encode_macro_society_snapshot(result.snapshot),
            created_at_utc="2026-10-30T00:00:00Z",
        )
    )
    summary = reader.read_summary("run-1")
    assert summary.window_count == 5
    assert summary.candidate_count >= 1
    assert summary.publication_id == result.publication_id
    rows, _ = reader.read_candidates("run-1", publication_id=None, offset=0, limit=50)
    assert rows
    lineage, _ = reader.read_lineage("run-1", publication_id=None, offset=0, limit=50)
    kinds = {edge.kind for edge in lineage}
    assert "split" in kinds or "dissolved" in kinds


def test_layers_remain_separate_in_the_analysis() -> None:
    result = build_macro_society_harvest_result(_harvest())
    view = result.analysis.layer_view
    assert view is not None
    for objective_row in view.objective_rows:
        assert not objective_row.region_id.startswith("msoc-")
    candidate_ids = set(view.candidate_ids)
    for subjective_row in view.subjective_rows:
        assert subjective_row.local_token_id not in candidate_ids
        assert not subjective_row.local_token_id.startswith("msoc-")


def test_objective_rows_survive_publication_as_counts() -> None:
    result = build_macro_society_harvest_result(_harvest())
    regions = {row.region_id for row in result.snapshot.objective_rows}
    assert regions == {"region-a", "region-b"}
    assert all(row.population_count > 0 for row in result.snapshot.objective_rows)
