"""V4-10 atomic diplomacy filesystem store and producer."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from agents.cognition import (
    DiplomacyFrame,
    DiplomaticAct,
    DiplomaticPartyKind,
    DiplomaticTermKind,
    apply_diplomacy_update,
)
from experiments.diplomacy_harvest import build_completed_run_diplomacy_harvest
from experiments.diplomacy_publication import (
    DiplomacyHarvestResult,
    build_diplomacy_harvest_result,
    publish_diplomacy_snapshot,
)
from persistence.diplomacy_filesystem import (
    DIPLOMACY_STORE_SCHEMA,
    create_diplomacy_publisher,
    create_diplomacy_reader,
)
from research_runner.diplomacy_composition import (
    producer_options_from_args,
    publish_diplomacy_harvest,
)
from simulation.diplomacy_ports import DiplomacyPortError

pytestmark = pytest.mark.unit

_SRC = Path(__file__).resolve().parents[2] / "src"


def _observation() -> SimpleNamespace:
    return SimpleNamespace(
        occurrences=(),
        communications=(),
        regional_context=None,
        self_body=None,
        exits=(),
    )


def _runner_result(tick: int = 1) -> SimpleNamespace:
    ledger = apply_diplomacy_update(
        owner_id="agent-a",
        tick=tick,
        observation=_observation(),
        prior=None,
        frames=(
            DiplomacyFrame(
                act=DiplomaticAct.PROPOSE,
                envoy_ref="agent-a",
                actor_ref="agent-a",
                party_kind=DiplomaticPartyKind.AGENT,
                party_ref="agent-b",
                topic_subject="trade",
                term_kind=DiplomaticTermKind.MATERIAL_EXCHANGE,
                revision=0,
            ),
        ),
    )
    return SimpleNamespace(
        run_id=SimpleNamespace(value="run-1"),
        ticks_committed=tick,
        stop_reason=SimpleNamespace(value="max_ticks"),
        diplomacy_ledgers=(ledger,),
    )


def _result(tick: int = 1) -> DiplomacyHarvestResult:
    harvest = build_completed_run_diplomacy_harvest(_runner_result(tick))
    return build_diplomacy_harvest_result(
        harvest, run_id="run-1", revision="rev-1", window_end=tick
    )


def test_publish_and_read(tmp_path: Path) -> None:
    publisher = create_diplomacy_publisher(tmp_path)
    result = _result()
    published = publish_diplomacy_snapshot(result, publisher)
    assert published.published
    reader = create_diplomacy_reader(tmp_path)
    summary = reader.read_summary("run-1")
    assert result.snapshot is not None
    assert summary.publication_id == result.snapshot.publication_id
    assert summary.summary.relation_count == 1
    relations = reader.read_relations("run-1")
    assert relations
    relation_id = relations[0].relation_id
    detail = reader.read_relation("run-1", relation_id)
    assert detail.relation.relation_id == relation_id
    with pytest.raises(DiplomacyPortError):
        reader.read_relation("run-1", "dpl-" + "f" * 16)


def test_quota_rejection_preserves_prior_publications(tmp_path: Path) -> None:
    publisher = create_diplomacy_publisher(tmp_path, max_publications=1)
    first = publish_diplomacy_snapshot(_result(1), publisher)
    assert first.published
    second = publish_diplomacy_snapshot(_result(2), publisher)
    assert not second.published
    assert second.receipt["reason"] == "diplomacy_quota_exceeded"
    reader = create_diplomacy_reader(tmp_path)
    assert first.snapshot is not None
    assert first.snapshot is not None
    assert reader.read_summary("run-1").publication_id == first.snapshot.publication_id


def test_tampered_publication_is_rejected(tmp_path: Path) -> None:
    publisher = create_diplomacy_publisher(tmp_path)
    result = _result()
    publish_diplomacy_snapshot(result, publisher)
    assert result.snapshot is not None
    path = tmp_path / "publications" / f"{result.snapshot.publication_id}.json"
    payload = path.read_bytes()
    path.write_bytes(payload.replace(result.snapshot.digest.encode(), b"0" * 64))
    with pytest.raises(DiplomacyPortError):
        create_diplomacy_reader(tmp_path).read_summary("run-1")


def test_unset_root_disables_the_producer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PALIMPSEST_DIPLOMACY_ROOT", raising=False)
    options = producer_options_from_args(SimpleNamespace())
    assert options.enabled is False
    receipt = publish_diplomacy_harvest(_runner_result(), options)
    assert receipt["status"] == "disabled"


def test_store_schema_and_imports(tmp_path: Path) -> None:
    assert DIPLOMACY_STORE_SCHEMA == "diplomacy-store-v1"
    source = (_SRC / "research_runner" / "diplomacy_composition.py").read_text()
    tree = ast.parse(source)
    modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert "api" not in modules
    assert "simulation.runner" not in modules
    assert "world" not in modules
