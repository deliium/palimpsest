"""V4-06 CLI producer options and opt-in behavior."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from research_runner.formal_rule_composition import (
    FormalRuleProducerOptions,
    producer_options_from_args,
    publish_formal_rule_harvest,
)

pytestmark = pytest.mark.unit

CLI = Path(__file__).resolve().parents[2] / "src" / "research_runner" / "cli.py"


def test_cli_flags_are_opt_in_and_default_off() -> None:
    text = CLI.read_text(encoding="utf-8")
    assert 'add_argument("--formal-rule-root", default=None)' in text
    assert (
        'add_argument("--formal-rule-max-publications", type=int, default=16)'
        in text
    )
    assert (
        'add_argument("--formal-rule-max-bytes", type=int, default=8_388_608)'
        in text
    )
    options = producer_options_from_args(
        SimpleNamespace(
            formal_rule_root=None,
            formal_rule_max_publications=16,
            formal_rule_max_bytes=8_388_608,
        )
    )
    assert options.enabled is False


def test_producer_options_read_paths_and_caps() -> None:
    options = producer_options_from_args(
        SimpleNamespace(
            formal_rule_root="/tmp/formal",
            formal_rule_max_publications=2,
            formal_rule_max_bytes=1024,
        )
    )
    assert options.root == Path("/tmp/formal")
    assert options.max_publications == 2
    assert options.max_artifact_bytes == 1024
    with pytest.raises(ValueError):
        producer_options_from_args(
            SimpleNamespace(
                formal_rule_root="/tmp/formal",
                formal_rule_max_publications=0,
                formal_rule_max_bytes=1024,
            )
        )


def test_disabled_producer_returns_disabled() -> None:
    receipt = publish_formal_rule_harvest(
        SimpleNamespace(),
        run_id="run-1",
        input_revision="revision-1",
        generated_tick=0,
        options=FormalRuleProducerOptions(root=None),
    )
    assert receipt == {
        "status": "disabled",
        "reason_code": "formal_rule_disabled",
    }


def test_receipt_json_is_metadata_only(tmp_path: Path) -> None:
    from experiments.formal_rule_harvest import (
        build_completed_run_formal_rule_harvest,
    )
    from experiments.formal_rule_publication import (
        build_formal_rule_harvest_result,
        formal_rule_publication_document,
    )
    from tests.unit.formal_rule_helpers import make_ledger

    result = SimpleNamespace(
        formal_rule_ledgers=(make_ledger(ticks=(0,)),),
        stop_reason="max_ticks",
        ticks_committed=1,
    )
    harvest = build_completed_run_formal_rule_harvest(
        result,
        run_id="run-1",
        input_revision="revision-1",
        generated_tick=1,
    )
    built = build_formal_rule_harvest_result(harvest)
    receipt = formal_rule_publication_document(built)
    assert receipt["status"] == "published"
    assert "rule_id" not in repr(receipt)
    assert "owner_id" not in repr(receipt)


def test_receipt_written_next_to_artifacts(tmp_path: Path) -> None:
    from research_runner.formal_rule_composition import (
        write_formal_rule_receipt,
    )

    receipt = {
        "status": "published",
        "reason_code": "formal_rule_published",
        "publication_id": "frule-pub-0123456789abcdef",
    }
    path = write_formal_rule_receipt(tmp_path, run_id="run-1", receipt=receipt)
    assert path == tmp_path / "formal-rule-publication-run-1.json"
    assert path is not None
    assert path.read_text(encoding="utf-8") == (
        '{"publication_id":"frule-pub-0123456789abcdef",'
        '"reason_code":"formal_rule_published","status":"published"}\n'
    )


def test_receipt_write_failure_does_not_fail_run(tmp_path: Path) -> None:
    from research_runner.formal_rule_composition import (
        write_formal_rule_receipt,
    )

    occupied = tmp_path / "artifact-root"
    occupied.write_text("occupied", encoding="utf-8")
    assert (
        write_formal_rule_receipt(
            occupied, run_id="run-1", receipt={"status": "published"}
        )
        is None
    )
    composition = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "research_runner"
        / "formal_rule_composition.py"
    ).read_text(encoding="utf-8")
    assert "formal_rule_receipt_write_failed" in composition
    assert "except OSError:" in composition
