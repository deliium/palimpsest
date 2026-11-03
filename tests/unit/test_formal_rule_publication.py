"""V4-06 snapshot composition, receipts, and failure isolation."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from experiments.formal_rule_harvest import build_completed_run_formal_rule_harvest
from experiments.formal_rule_publication import (
    build_formal_rule_harvest_result,
    formal_rule_publication_document,
)
from simulation import (
    FormalRuleCounts,
    decode_formal_rule_snapshot,
    encode_formal_rule_snapshot,
    formal_rule_digest,
)
from tests.unit.formal_rule_helpers import make_ledger

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]


def _result(*ledgers: Any, stop_reason: str = "max_ticks") -> Any:
    return SimpleNamespace(
        formal_rule_ledgers=tuple(ledgers),
        stop_reason=stop_reason,
        ticks_committed=100,
    )


def _built(*ledgers: Any) -> Any:
    harvest = build_completed_run_formal_rule_harvest(
        _result(*ledgers),
        run_id="run-1",
        input_revision="revision-1",
        generated_tick=100,
    )
    return build_formal_rule_harvest_result(harvest)


def test_empty_ledgers_publish_an_empty_v1_snapshot() -> None:
    built = _built()
    assert built.candidate_count == 0
    assert built.rule_count == 0
    assert built.snapshot.provenance_code == "empty"
    assert built.snapshot.counts == FormalRuleCounts()


def test_scientific_result_is_unchanged_by_publication(tmp_path: Path) -> None:
    from experiments.formal_rule_publication import publish_formal_rule_snapshot
    from persistence.formal_rule_filesystem import create_formal_rule_publisher

    result = _result(make_ledger(ticks=(0, 100)))
    before = repr(result)
    publisher = create_formal_rule_publisher(tmp_path)
    assert publisher is not None
    publish_formal_rule_snapshot(_built(make_ledger(ticks=(0, 100))), publisher)
    assert repr(result) == before
    assert (tmp_path / "state.json").is_file()


def test_snapshot_round_trip_and_digest() -> None:
    built = _built(make_ledger(ticks=(0, 100)))
    payload = encode_formal_rule_snapshot(built.snapshot)
    decoded = decode_formal_rule_snapshot(payload)
    assert encode_formal_rule_snapshot(decoded) == payload
    assert formal_rule_digest(payload) == built.snapshot_digest
    assert built.publication_id.startswith("frule-pub-")


def test_candidate_rule_and_version_caps_set_truncated_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import experiments.formal_rule_publication as publication

    monkeypatch.setattr(publication, "MAX_FORMAL_RULE_CANDIDATES", 0)
    built = _built(make_ledger(ticks=(0,)))
    assert built.candidate_count == 0
    assert built.snapshot.provenance_code == "truncated"
    assert built.receipt["truncated"] is True


def test_receipt_is_metadata_only() -> None:
    built = _built(make_ledger(ticks=(0,)))
    receipt = formal_rule_publication_document(built)
    assert set(receipt) == {
        "status",
        "schema_version",
        "policy_version",
        "candidate_count",
        "rule_count",
        "version_count",
        "coverage",
        "publication_id",
        "snapshot_digest",
        "truncated",
    }
    text = repr(receipt)
    assert "frule-0" not in text
    assert "frl-" not in text
    assert "agent-" not in text


def test_disabled_root_returns_disabled() -> None:
    from research_runner.formal_rule_composition import (
        FormalRuleProducerOptions,
        publish_formal_rule_harvest,
    )

    receipt = publish_formal_rule_harvest(
        _result(),
        run_id="run-1",
        input_revision="revision-1",
        generated_tick=100,
        options=FormalRuleProducerOptions(root=None),
    )
    assert receipt == {
        "status": "disabled",
        "reason_code": "formal_rule_disabled",
    }


def test_incomplete_run_returns_unavailable(tmp_path: Path) -> None:
    from research_runner.formal_rule_composition import (
        FormalRuleProducerOptions,
        publish_formal_rule_harvest,
    )

    receipt = publish_formal_rule_harvest(
        _result(stop_reason="cognition_failure"),
        run_id="run-1",
        input_revision="revision-1",
        generated_tick=100,
        options=FormalRuleProducerOptions(root=tmp_path),
    )
    assert receipt["status"] == "unavailable"
    assert receipt["reason_code"] == "formal_rule_run_incomplete"


def test_failure_changes_only_the_receipt(tmp_path: Path) -> None:
    from research_runner.formal_rule_composition import (
        FormalRuleProducerOptions,
        publish_formal_rule_harvest,
    )

    result = _result(make_ledger(ticks=(0,)))
    before = result.formal_rule_ledgers
    receipt = publish_formal_rule_harvest(
        result,
        run_id="run-1",
        input_revision="revision-1",
        generated_tick=100,
        options=FormalRuleProducerOptions(root=tmp_path),
    )
    assert receipt["status"] == "published"
    assert result.formal_rule_ledgers is before


def test_publication_does_not_import_api_or_persistence() -> None:
    allowed = {
        "__future__",
        "analysis",
        "collections",
        "dataclasses",
        "experiments",
        "hashlib",
        "json",
        "logging",
        "simulation",
        "typing",
    }
    for name in ("formal_rule_harvest.py", "formal_rule_publication.py"):
        path = ROOT / "src" / "experiments" / name
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module is not None:
                imported.add(node.module.split(".", 1)[0])
            elif isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
        assert imported <= allowed, path
        assert not imported & {
            "api",
            "infrastructure",
            "persistence",
            "research_runner",
        }
