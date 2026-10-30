"""Completed-run bridge: mapping, identity, and non-interference."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from analysis.macro_society_contract import MacroSocietyError, MacroSocietyLane
from analysis.macro_society_evidence import (
    MacroSocietyEdge,
    MacroSocietyToken,
    MacroSocietyWindowEvidence,
)
from experiments.macro_society_publication import (
    MacroSocietyHarvest,
    build_macro_society_harvest_result,
    macro_society_publication_document,
    publish_macro_society_snapshot,
)
from simulation.macro_society_models import MacroSocietySnapshotRef
from simulation.macro_society_ports import MacroSocietyPublication

ROOT = Path(__file__).resolve().parents[2]
PERSONS = tuple(f"person-{index}" for index in range(1, 9))


def _edges(members: tuple[str, ...]) -> tuple[MacroSocietyEdge, ...]:
    return tuple(
        MacroSocietyEdge(MacroSocietyLane.INTERACTION, source, target, 0)
        for index, source in enumerate(members)
        for target in members[index + 1 :]
    )


def _harvest() -> MacroSocietyHarvest:
    first = MacroSocietyWindowEvidence(
        window_index=0,
        tick_start=0,
        tick_end=9,
        person_ids=PERSONS,
        edges=_edges(PERSONS[:4]),
    )
    second = MacroSocietyWindowEvidence(
        window_index=1,
        tick_start=10,
        tick_end=19,
        person_ids=PERSONS,
        edges=_edges(PERSONS[:4]),
        tokens=tuple(
            MacroSocietyToken(MacroSocietyLane.CULTURE, person, "trait-1")
            for person in PERSONS[:4]
        ),
    )
    return MacroSocietyHarvest(
        run_id="run-1",
        input_revision="rev-1",
        windows=(first, second),
        objective_rows=(
            {"region_id": "region-a", "tick": 0, "population_count": 8},
        ),
        subjective_rows=(
            {"owner_id": "person-1", "lane": "culture", "local_token_id": "trait-1"},
        ),
        generated_tick=19,
    )


def test_harvest_builds_one_snapshot_with_stable_publication_id() -> None:
    first = build_macro_society_harvest_result(_harvest())
    second = build_macro_society_harvest_result(_harvest())
    assert first.snapshot == second.snapshot
    assert first.publication_id == second.publication_id
    assert first.publication_id.startswith("msoc-edge-")
    assert len(first.snapshot.windows) == 2
    assert len(first.snapshot.candidates) == 1
    assert first.snapshot.candidates[0].member_ids == PERSONS[:4]
    assert first.snapshot.objective_rows[0].population_count == 8
    assert first.snapshot.coverage.observed == 4
    assert first.snapshot.provenance_code == "ok"


def test_receipt_contains_no_member_or_owner_ids() -> None:
    result = build_macro_society_harvest_result(_harvest())
    document = macro_society_publication_document(result)
    assert "person-" not in repr(document)
    assert document["candidate_count"] == 1
    assert document["snapshot_bytes"] == result.snapshot_bytes


def test_member_list_truncation_is_disclosed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "experiments.macro_society_publication.MAX_SNAPSHOT_MEMBERS", 3
    )
    result = build_macro_society_harvest_result(_harvest())
    assert result.snapshot.provenance_code == "member_list_truncated"
    assert len(result.snapshot.candidates) == 1
    assert len(result.snapshot.candidates[0].member_ids) == 3


def test_empty_harvest_is_rejected() -> None:
    with pytest.raises(MacroSocietyError, match="macro_society_empty_window"):
        MacroSocietyHarvest(
            run_id="run-1", input_revision="rev-1", windows=()
        )


def test_non_monotonic_harvest_is_rejected() -> None:
    windows = _harvest().windows
    with pytest.raises(MacroSocietyError, match="macro_society_nonmonotonic_window"):
        MacroSocietyHarvest(
            run_id="run-1",
            input_revision="rev-1",
            windows=(windows[1], windows[0]),
        )


def test_publish_hands_exactly_one_publication_to_the_port() -> None:
    recorded: list[MacroSocietyPublication] = []

    class _Port:
        def publish(
            self, publication: MacroSocietyPublication
        ) -> MacroSocietySnapshotRef:
            recorded.append(publication)
            return MacroSocietySnapshotRef(
                publication_id=publication.publication_id,
                digest="c" * 64,
            )

    ref = publish_macro_society_snapshot(
        harvest=_harvest(), port=_Port(), created_at_utc="2026-10-30T00:00:00Z"
    )
    assert len(recorded) == 1
    assert ref.publication_id == recorded[0].publication_id


def test_bridge_does_not_import_api_persistence_or_observer() -> None:
    forbidden = {"api", "persistence", "observer"}
    path = ROOT / "src" / "experiments" / "macro_society_publication.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert node.module.split(".", 1)[0] not in forbidden
        elif isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".", 1)[0] not in forbidden
