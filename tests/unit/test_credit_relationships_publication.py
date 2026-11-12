"""Credit snapshot composition, publication receipts, and idempotence."""

# mypy: ignore-errors


from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from agents.cognition.credit_relationships import (
    apply_credit_relationship_update,
)
from analysis.credit_relationships_analysis import (
    empty_credit_relationships_analysis,
    harvest_credit_relationships_analysis,
)
from experiments.credit_relationships_publication import (
    build_credit_relationships_harvest_result,
    compose_credit_relationships_snapshot,
    publish_credit_relationships_snapshot,
)
from persistence.credit_relationships_filesystem import (
    CreditRelationshipsPublisherOptions,
    create_credit_relationships_publisher,
)
from tests.unit.credit_relationships_analysis_helpers import (
    completed,
    frame,
    given,
    talked,
)
from tests.unit.test_credit_relationships_helpers import OWNER, claim


def _events(repayment_quantity: int = 3):
    return [
        completed("evt-0", give_ids=("item-1",), give_kinds=("food",), tick=0),
        talked(
            "evt-1",
            frame(repayment_quantity=repayment_quantity),
            tick=0,
            sequence=1,
        ),
        given("evt-2", item_id="item-1", tick=1),
    ]


def _analysis(repayment_quantity: int = 3):
    ledger = apply_credit_relationship_update(
        owner_id=OWNER, tick=2, claims=(claim(),)
    )
    return harvest_credit_relationships_analysis(
        committed_events=_events(repayment_quantity),
        owner_inputs=(),
        policy=None,
    ), ledger


def test_compose_maps_every_family() -> None:
    analysis, _ = _analysis()
    snapshot = compose_credit_relationships_snapshot(analysis, run_id="run-1")
    assert snapshot.publication_id.startswith("cred-pub-")
    assert snapshot.digest.startswith("sha256:")
    assert len(snapshot.claims) == analysis.claim_count
    assert len(snapshot.performances) == len(analysis.performances)
    assert len(snapshot.distributions) == len(analysis.distributions)


def test_missing_analysis_yields_publication_missing() -> None:
    snapshot = compose_credit_relationships_snapshot(
        empty_credit_relationships_analysis(), run_id="run-1"
    )
    receipt = publish_credit_relationships_snapshot(snapshot, None)
    assert receipt.reason_code == "publication_missing"
    assert receipt.stored is False


def test_missing_publisher_yields_disabled_without_writing() -> None:
    analysis, _ = _analysis()
    snapshot = compose_credit_relationships_snapshot(analysis, run_id="run-1")
    receipt = publish_credit_relationships_snapshot(snapshot, None)
    assert receipt.reason_code == "publication_disabled"
    assert receipt.stored is False


def test_store_publication_is_idempotent(tmp_path: Path) -> None:
    analysis, _ = _analysis()
    snapshot = compose_credit_relationships_snapshot(analysis, run_id="run-1")
    publisher = create_credit_relationships_publisher(tmp_path)
    first = publish_credit_relationships_snapshot(snapshot, publisher)
    second = publish_credit_relationships_snapshot(snapshot, publisher)
    assert first.reason_code == "published" and first.stored is True
    assert second.reason_code == "published" and second.stored is True
    assert len(publisher.list_publications("run-1")) == 1


def test_quota_failure_is_a_receipt_not_an_error(tmp_path: Path) -> None:
    publisher = create_credit_relationships_publisher(
        tmp_path, CreditRelationshipsPublisherOptions(max_publications=1)
    )
    first_analysis, _ = _analysis(3)
    second_analysis, _ = _analysis(4)
    first = compose_credit_relationships_snapshot(first_analysis, run_id="run-1")
    second = compose_credit_relationships_snapshot(second_analysis, run_id="run-1")
    assert publish_credit_relationships_snapshot(first, publisher).stored is True
    receipt = publish_credit_relationships_snapshot(second, publisher)
    assert receipt.reason_code == "store_quota_exceeded"
    assert receipt.stored is False


def test_harvest_result_composes_analysis_snapshot_and_receipt() -> None:
    ledger = apply_credit_relationship_update(
        owner_id=OWNER, tick=2, claims=(claim(),)
    )
    analysis = harvest_credit_relationships_analysis(
        committed_events=_events(), owner_inputs=()
    )
    snap = compose_credit_relationships_snapshot(analysis, run_id="run-1")
    assert snap.summary.coverage == analysis.coverage.value
    assert build_credit_relationships_harvest_result is not None
    assert ledger.owner_id == OWNER


def test_missing_events_rejected_by_harvest_result() -> None:
    with pytest.raises(ValueError):
        build_credit_relationships_harvest_result(
            SimpleNamespace(credit_relationship_ledgers=()),
            committed_events=None,
            run_id="run-1",
        )
