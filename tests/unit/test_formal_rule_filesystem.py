"""V4-06 filesystem publication store, quotas, and read ports."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from experiments.formal_rule_harvest import build_completed_run_formal_rule_harvest
from experiments.formal_rule_publication import (
    build_formal_rule_harvest_result,
    publish_formal_rule_snapshot,
)
from persistence.formal_rule_filesystem import (
    create_formal_rule_publisher,
    create_formal_rule_reader,
)
from simulation import (
    FormalRuleArtifactError,
    FormalRulePublication,
    encode_formal_rule_snapshot,
)
from tests.unit.formal_rule_helpers import make_ledger

pytestmark = pytest.mark.unit


def _built(run_id: str = "run-1", ticks: tuple[int, ...] = (0, 100)) -> Any:
    result = SimpleNamespace(
        formal_rule_ledgers=(make_ledger(ticks=ticks),),
        stop_reason="max_ticks",
        ticks_committed=100,
    )
    harvest = build_completed_run_formal_rule_harvest(
        result,
        run_id=run_id,
        input_revision="revision-1",
        generated_tick=100,
    )
    return build_formal_rule_harvest_result(harvest)


def test_publish_is_atomic_and_reader_serves_six_page_kinds(tmp_path: Path) -> None:
    built = _built()
    publisher = create_formal_rule_publisher(tmp_path)
    assert publisher is not None
    publish_formal_rule_snapshot(built, publisher)
    reader = create_formal_rule_reader(tmp_path)
    assert reader is not None

    summary = reader.summary("run-1")
    assert summary.publication_id == built.publication_id
    assert summary.candidate_count == 1
    assert summary.rule_count == 1
    assert summary.version_count == 2

    candidates = reader.candidates(
        "run-1", status=None, offset=0, limit=10
    )
    assert len(candidates.rows) == 1
    candidate_id = cast(Any, candidates.rows[0]).candidate_id
    candidate = reader.candidate("run-1", candidate_id)
    assert candidate.candidate_id == candidate_id

    rules = reader.rules(
        "run-1", candidate_id=candidate_id, stage=None, offset=0, limit=10
    )
    assert rules.rows
    rule_id = cast(Any, rules.rows[0]).rule_id
    versions = reader.versions(
        "run-1",
        candidate_id=candidate_id,
        rule_id=rule_id,
        offset=0,
        limit=10,
    )
    assert len(versions.rows) == 2
    lineage = reader.lineage("run-1", kind=None, offset=0, limit=10)
    assert isinstance(lineage.rows, tuple)


def test_duplicate_publication_with_different_bytes_is_rejected(tmp_path: Path) -> None:
    built = _built()
    publisher = create_formal_rule_publisher(tmp_path)
    assert publisher is not None
    publish_formal_rule_snapshot(built, publisher)
    payload = encode_formal_rule_snapshot(built.snapshot)
    tampered = FormalRulePublication(
        run_id="run-1",
        publication_id=built.publication_id,
        snapshot_digest=built.snapshot_digest,
        payload=payload + b"\n",
        generated_tick=100,
    )
    with pytest.raises(FormalRuleArtifactError) as excinfo:
        publisher.publish(tampered)
    assert excinfo.value.code == "formal_rule_publication_exists"


def test_publication_and_byte_quotas(tmp_path: Path) -> None:
    publisher = create_formal_rule_publisher(
        tmp_path, max_publications=1, max_artifact_bytes=8 * 1024 * 1024
    )
    assert publisher is not None
    publish_formal_rule_snapshot(_built("run-1"), publisher)
    with pytest.raises(FormalRuleArtifactError) as excinfo:
        publish_formal_rule_snapshot(_built("run-2"), publisher)
    assert excinfo.value.code == "formal_rule_size_limit"

    tiny = create_formal_rule_publisher(tmp_path / "tiny", max_artifact_bytes=10)
    assert tiny is not None
    with pytest.raises(FormalRuleArtifactError) as excinfo:
        publish_formal_rule_snapshot(_built(), tiny)
    assert excinfo.value.code == "formal_rule_size_limit"


def test_path_traversal_and_unsafe_tokens_are_rejected(tmp_path: Path) -> None:
    publisher = create_formal_rule_publisher(tmp_path)
    assert publisher is not None
    unsafe = FormalRulePublication(
        run_id="../escape",
        publication_id="frule-pub-0123456789abcdef",
        snapshot_digest="a" * 64,
        payload=b"{}",
        generated_tick=0,
    )
    with pytest.raises(FormalRuleArtifactError) as excinfo:
        publisher.publish(unsafe)
    assert excinfo.value.code == "formal_rule_invalid_value"


def test_unset_root_returns_none() -> None:
    assert create_formal_rule_publisher(None) is None
    assert create_formal_rule_reader(None) is None
