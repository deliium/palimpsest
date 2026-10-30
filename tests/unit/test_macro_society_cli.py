"""research_runner macro-society producer options and non-interfering receipts."""

from __future__ import annotations

import argparse
import ast
from pathlib import Path

import pytest

from analysis.macro_society_contract import MacroSocietyLane
from analysis.macro_society_evidence import MacroSocietyEdge, MacroSocietyWindowEvidence
from experiments.macro_society_publication import MacroSocietyHarvest
from research_runner.macro_society_composition import (
    MacroSocietyProducerOptions,
    producer_options_from_args,
    publish_macro_society_harvest,
)

ROOT = Path(__file__).resolve().parents[2]
PERSONS = tuple(f"person-{index}" for index in range(1, 9))


def _harvest() -> MacroSocietyHarvest:
    edges = tuple(
        MacroSocietyEdge(MacroSocietyLane.INTERACTION, source, target, 0)
        for index, source in enumerate(PERSONS[:4])
        for target in PERSONS[:4][index + 1 :]
    )
    return MacroSocietyHarvest(
        run_id="run-1",
        input_revision="rev-1",
        windows=(
            MacroSocietyWindowEvidence(
                window_index=0,
                tick_start=0,
                tick_end=9,
                person_ids=PERSONS,
                edges=edges,
            ),
        ),
        objective_rows=(
            {"region_id": "region-a", "tick": 0, "population_count": 8},
        ),
        generated_tick=9,
    )


def _args(**overrides: object) -> argparse.Namespace:
    values: dict[str, object] = {
        "macro_society_root": None,
        "macro_society_max_publications": 16,
        "macro_society_max_bytes": 8_388_608,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_options_parse_and_validate() -> None:
    options = producer_options_from_args(_args(macro_society_root="/tmp/x"))
    assert options.enabled
    assert options.root == Path("/tmp/x")
    assert not producer_options_from_args(_args()).enabled
    with pytest.raises(ValueError):
        producer_options_from_args(_args(macro_society_max_publications=0))
    with pytest.raises(ValueError):
        producer_options_from_args(_args(macro_society_max_bytes=300_000_000))


def test_disabled_options_write_nothing(tmp_path: Path) -> None:
    receipt = publish_macro_society_harvest(
        options=MacroSocietyProducerOptions(root=None), harvest=_harvest()
    )
    assert receipt["status"] == "disabled"
    assert not any(tmp_path.iterdir())


def test_missing_harvest_is_unavailable_not_success(tmp_path: Path) -> None:
    receipt = publish_macro_society_harvest(
        options=MacroSocietyProducerOptions(root=tmp_path), harvest=None
    )
    assert receipt["status"] == "unavailable"
    assert receipt["reason_code"] == "macro_society_harvest_unavailable"


def test_published_receipt_is_id_free(tmp_path: Path) -> None:
    receipt = publish_macro_society_harvest(
        options=MacroSocietyProducerOptions(root=tmp_path), harvest=_harvest()
    )
    assert receipt["status"] == "published"
    assert receipt["candidate_count"] == 1
    assert "person-" not in repr(receipt)


def test_storage_failure_becomes_a_failed_receipt(tmp_path: Path) -> None:
    blocked = tmp_path / "not-a-directory"
    blocked.write_text("x", encoding="utf-8")
    receipt = publish_macro_society_harvest(
        options=MacroSocietyProducerOptions(root=blocked), harvest=_harvest()
    )
    assert receipt["status"] == "failed"
    assert isinstance(receipt["reason_code"], str)


def test_cli_module_does_not_import_api() -> None:
    path = ROOT / "src" / "research_runner" / "macro_society_composition.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert node.module.split(".", 1)[0] != "api"
        elif isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".", 1)[0] != "api"
