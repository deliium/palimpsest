"""V4-09 representation composition, atomic store, and CLI options."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from agents.cognition import (
    RepresentationDurationKind,
    RepresentationPrincipalKind,
    RepresentationProvenance,
    RepresentationScopeKind,
    default_representation_policy,
)
from agents.cognition.delegation_representation import (
    RepresentationLedger,
    apply_representation_update,
)
from agents.cognition.delegation_representation_communication import (
    RepresentationAct,
    RepresentationFrame,
)
from experiments.delegation_representation_harvest import (
    build_completed_run_representation_harvest,
)
from experiments.delegation_representation_publication import (
    RepresentationHarvestResult,
    build_representation_harvest_result,
    publish_representation_snapshot,
    representations_publication_document,
)
from persistence.delegation_representation_filesystem import (
    DELEGATION_REPRESENTATION_STORE_SCHEMA,
    FilesystemDelegationRepresentationPublisher,
    create_delegation_representation_reader,
)
from research_runner.delegation_representation_composition import (
    RepresentationProducerOptions,
    producer_options_from_args,
    publish_representation_harvest,
    write_representation_receipt,
)
from simulation.delegation_representation_codec import (
    encode_delegation_representation_snapshot,
    finalize_delegation_representation_snapshot,
)
from simulation.delegation_representation_models import (
    DelegationRepresentationArtifactError,
)
from simulation.delegation_representation_ports import (
    DelegationRepresentationPublication,
)
from simulation.runner_models import RunnerStopReasonCode

pytestmark = pytest.mark.unit

_OWNER = "agent-owner"
_PRINCIPAL = "agent-principal"
_REP = "agent-representative"


def _ledger() -> RepresentationLedger:
    frame = RepresentationFrame(
        act=RepresentationAct.CLAIM,
        principal_kind=RepresentationPrincipalKind.AGENT,
        principal_ref=_PRINCIPAL,
        representative_ref=_REP,
        scope_kind=RepresentationScopeKind.SPEAK_FOR,
        scope_subject="border",
        duration_kind=RepresentationDurationKind.UNTIL_REVOKED,
        provenance=RepresentationProvenance.SELF_DECLARED,
        actor_ref=_REP,
    )
    return apply_representation_update(
        owner_id=_OWNER,
        tick=1,
        observation=None,
        prior=None,
        frames=(frame,),
        policy=default_representation_policy(),
    )


def _result(
    ledger: Any | None = None,
    *,
    stop: RunnerStopReasonCode = RunnerStopReasonCode.MAX_TICKS,
) -> Any:
    return SimpleNamespace(
        run_id=SimpleNamespace(value="run-representation-publication"),
        ticks_committed=4,
        stop_reason=stop,
        representation_ledgers=() if ledger is None else (ledger,),
    )


def _built() -> RepresentationHarvestResult:
    harvest = build_completed_run_representation_harvest(_result(_ledger()))
    return build_representation_harvest_result(
        harvest=harvest, stop_reason=RunnerStopReasonCode.MAX_TICKS
    )


def test_disabled_and_unavailable_paths() -> None:
    empty = build_completed_run_representation_harvest(_result())
    disabled = build_representation_harvest_result(
        harvest=empty, stop_reason=RunnerStopReasonCode.MAX_TICKS
    )
    assert disabled.receipt["status"] == "disabled"
    assert disabled.published is False

    unavailable = build_representation_harvest_result(
        harvest=empty, stop_reason=RunnerStopReasonCode.CANCELLED
    )
    assert unavailable.receipt["status"] == "unavailable"
    assert unavailable.receipt["reason"] == "representation_run_incomplete"


def test_ready_result_has_exact_receipt_keys() -> None:
    built = _built()
    assert built.snapshot is not None
    assert built.receipt["status"] == "ready"
    assert set(built.receipt) == {
        "status",
        "reason",
        "publication_id",
        "digest",
        "mandates",
        "positions",
        "revocations",
        "coverage",
    }
    document = representations_publication_document(built)
    assert document["mandates"] == 1
    assert "principal_token" not in document


def test_filesystem_round_trip_and_reader_parity(tmp_path: Path) -> None:
    built = _built()
    assert built.snapshot is not None
    publisher = FilesystemDelegationRepresentationPublisher(tmp_path)
    published = publish_representation_snapshot(built, publisher)
    assert published.receipt["status"] == "published"
    assert DELEGATION_REPRESENTATION_STORE_SCHEMA == (
        "delegation-representation-store-v1"
    )
    reader = create_delegation_representation_reader(tmp_path)
    assert reader is not None
    summary = reader.summary(run_id=built.snapshot.run_id)
    assert summary.mandate_count == 1
    assert summary.publication_id == built.snapshot.publication_id
    page = reader.mandates(run_id=built.snapshot.run_id, offset=0, limit=10)
    assert len(page.rows) == 1
    candidates = reader.candidates(run_id=built.snapshot.run_id, offset=0, limit=10)
    detail = reader.candidate(
        run_id=built.snapshot.run_id,
        candidate_id=cast(Any, candidates.rows[0]).candidate_id,
    )
    assert detail.mandate_count == 1


def test_duplicate_publication_is_idempotent_or_conflicting(tmp_path: Path) -> None:
    import json

    built = _built()
    assert built.snapshot is not None
    publisher = FilesystemDelegationRepresentationPublisher(tmp_path)
    publish_representation_snapshot(built, publisher)
    publish_representation_snapshot(built, publisher)
    state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert len(state["publications"]) == 1
    assert state["publications"][0]["publication_id"] == built.snapshot.publication_id


def test_publication_quotas(tmp_path: Path) -> None:
    from simulation.delegation_representation_codec import (
        finalize_delegation_representation_snapshot,
    )

    built = _built()
    assert built.snapshot is not None
    publisher = FilesystemDelegationRepresentationPublisher(
        tmp_path, max_publications=1, max_bytes=10_000_000
    )
    publish_representation_snapshot(built, publisher)
    second_snapshot = finalize_delegation_representation_snapshot(
        replace(
            built.snapshot,
            generated_tick=5,
            digest="",
            publication_id="",
        )
    )
    second = replace(built, snapshot=second_snapshot)
    failed = publish_representation_snapshot(second, publisher)
    assert failed.receipt["status"] == "failed"
    assert failed.receipt["reason"] == "representation_size_limit"


def _distinct(
    built: RepresentationHarvestResult, *, generated_tick: int
) -> RepresentationHarvestResult:
    assert built.snapshot is not None
    snapshot = finalize_delegation_representation_snapshot(
        replace(
            built.snapshot,
            generated_tick=generated_tick,
            digest="",
            publication_id="",
        )
    )
    return replace(built, snapshot=snapshot)


def test_conflicting_duplicate_publication_is_rejected(tmp_path: Path) -> None:
    built = _built()
    assert built.snapshot is not None
    snapshot = built.snapshot
    publisher = FilesystemDelegationRepresentationPublisher(tmp_path)
    assert publish_representation_snapshot(built, publisher).published

    modified = _distinct(built, generated_tick=snapshot.generated_tick + 1)
    assert modified.snapshot is not None
    conflicting = replace(modified.snapshot, publication_id=snapshot.publication_id)
    payload = encode_delegation_representation_snapshot(conflicting)
    publication = DelegationRepresentationPublication(
        run_id=snapshot.run_id,
        publication_id=snapshot.publication_id,
        snapshot_digest=conflicting.digest,
        payload=payload,
        generated_tick=conflicting.generated_tick,
    )
    with pytest.raises(DelegationRepresentationArtifactError) as excinfo:
        publisher.publish(publication)
    assert excinfo.value.code == "delegation_representation_publication_exists"


def test_concurrent_publications_are_serialized(tmp_path: Path) -> None:
    import json

    built = _built()
    publisher = FilesystemDelegationRepresentationPublisher(tmp_path)
    candidates = [_distinct(built, generated_tick=tick) for tick in range(5, 9)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        published = list(
            pool.map(
                lambda candidate: publish_representation_snapshot(candidate, publisher),
                candidates,
            )
        )
    assert all(result.receipt["status"] == "published" for result in published)
    state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert len(state["publications"]) == 4


def test_byte_quota_counts_cumulative_publications(tmp_path: Path) -> None:
    built = _built()
    assert built.snapshot is not None
    payload = encode_delegation_representation_snapshot(built.snapshot)
    publisher = FilesystemDelegationRepresentationPublisher(
        tmp_path,
        max_publications=16,
        max_bytes=len(payload) + len(payload) // 2,
    )
    assert publish_representation_snapshot(built, publisher).published
    second = _distinct(built, generated_tick=99)
    failed = publish_representation_snapshot(second, publisher)
    assert failed.receipt["status"] == "failed"
    assert failed.receipt["reason"] == "representation_size_limit"


def test_cli_options_and_receipt(tmp_path: Path) -> None:
    args = SimpleNamespace(
        representation_root=str(tmp_path),
        representation_max_publications=16,
        representation_max_bytes=8_388_608,
    )
    options = producer_options_from_args(args)
    assert options.enabled is True
    receipt = publish_representation_harvest(_result(_ledger()), options)
    assert receipt["status"] in {"published", "ready"}
    path = write_representation_receipt(
        tmp_path, "run-representation-publication", receipt
    )
    assert path is not None and path.exists()

    disabled = publish_representation_harvest(
        _result(_ledger()), RepresentationProducerOptions(root=None)
    )
    assert disabled["status"] == "disabled"


def test_cli_failure_does_not_change_scientific_result(tmp_path: Path) -> None:
    result = _result(_ledger())
    before = (result.stop_reason, result.ticks_committed)
    options = RepresentationProducerOptions(root=tmp_path, max_bytes=10)
    receipt = publish_representation_harvest(result, options)
    assert receipt["status"] == "failed"
    assert (result.stop_reason, result.ticks_committed) == before
