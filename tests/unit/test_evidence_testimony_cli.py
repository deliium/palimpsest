"""V4-08 opt-in CLI producer receipts and option bounds."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

from research_runner.evidence_testimony_composition import (
    EVIDENCE_ROOT_ENV,
    EvidenceTestimonyProducerOptions,
    producer_options_from_args,
    publish_evidence_testimony_harvest,
    write_evidence_testimony_receipt,
)
from tests.unit.evidence_testimony_helpers import make_parts

pytestmark = pytest.mark.unit


@dataclass(frozen=True)
class _StopReason:
    value: str


@dataclass(frozen=True)
class _RunnerResult:
    evidence_ledgers: tuple[object, ...]
    run_id: str = "run-evidence-cli"
    ticks_committed: int = 2
    stop_reason: _StopReason = _StopReason("completed")


def _result() -> _RunnerResult:
    return _RunnerResult((make_parts().ledger(),))


def test_no_root_is_disabled() -> None:
    receipt = publish_evidence_testimony_harvest(
        _result(), EvidenceTestimonyProducerOptions(root=None)
    )
    assert receipt["status"] == "disabled"
    assert receipt["reason_code"] == "evidence_testimony_disabled"


def test_incomplete_run_is_unavailable(tmp_path: Path) -> None:
    result = _RunnerResult(
        (make_parts().ledger(),), stop_reason=_StopReason("cancelled")
    )
    receipt = publish_evidence_testimony_harvest(
        result, EvidenceTestimonyProducerOptions(root=tmp_path)
    )
    assert receipt["status"] == "unavailable"
    assert receipt["reason_code"] == "evidence_testimony_unavailable"


def test_storage_failure_is_isolated(tmp_path: Path) -> None:
    blocker = tmp_path / "blocked"
    blocker.write_text("not a directory", encoding="utf-8")
    receipt = publish_evidence_testimony_harvest(
        _result(), EvidenceTestimonyProducerOptions(root=blocker)
    )
    assert receipt["status"] == "failed"
    assert receipt["published"] is False


def test_successful_publication_and_receipt(tmp_path: Path) -> None:
    root = tmp_path / "evidence"
    receipt = publish_evidence_testimony_harvest(
        _result(), EvidenceTestimonyProducerOptions(root=root)
    )
    assert receipt["status"] == "published"
    assert receipt["publication_id"].startswith("evid-pub-")

    path = write_evidence_testimony_receipt(tmp_path, "run-evidence-cli", receipt)
    assert path is not None and path.exists()
    assert path.name.startswith("evidence-publication-")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["status"] == "published"
    assert payload["candidate_count"] == 1


def test_option_bounds_and_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(EVIDENCE_ROOT_ENV, raising=False)
    options = producer_options_from_args(
        SimpleNamespace(
            evidence_root=None,
            evidence_max_publications=16,
            evidence_max_bytes=8_388_608,
        )
    )
    assert options.enabled is False

    monkeypatch.setenv(EVIDENCE_ROOT_ENV, "/tmp/evidence")
    options = producer_options_from_args(
        SimpleNamespace(
            evidence_root=None,
            evidence_max_publications=4,
            evidence_max_bytes=1024,
        )
    )
    assert options.root == Path("/tmp/evidence")

    with pytest.raises(ValueError):
        producer_options_from_args(
            SimpleNamespace(
                evidence_root=None,
                evidence_max_publications=0,
                evidence_max_bytes=1024,
            )
        )
    with pytest.raises(ValueError):
        producer_options_from_args(
            SimpleNamespace(
                evidence_root=None,
                evidence_max_publications=1,
                evidence_max_bytes=0,
            )
        )


def test_parser_help_includes_evidence_flags_and_rejects_bounds() -> None:
    from research_runner.cli import build_parser

    build_parser()
    text = (
        Path(__file__).resolve().parents[2] / "src" / "research_runner" / "cli.py"
    ).read_text(encoding="utf-8")
    assert 'add_argument("--evidence-root", default=None)' in text
    assert 'add_argument("--evidence-max-publications", type=int, default=16)' in text
    assert 'add_argument("--evidence-max-bytes", type=int, default=8_388_608)' in text

    with pytest.raises(ValueError):
        producer_options_from_args(
            SimpleNamespace(
                evidence_root=None,
                evidence_max_publications=2048,
                evidence_max_bytes=1024,
            )
        )
