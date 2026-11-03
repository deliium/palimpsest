"""V4-07 dispute snapshot composition, receipts, and failure isolation."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

import experiments
import experiments.dispute_publication as publication
from experiments.dispute_harvest import build_completed_run_dispute_harvest
from experiments.dispute_publication import (
    build_dispute_harvest_result,
    dispute_publication_document,
    publish_dispute_snapshot,
)
from simulation import (
    DisputeArtifactError,
    compute_dispute_publication_id,
    decode_dispute_snapshot,
    encode_dispute_snapshot,
)
from tests.unit import dispute_helpers as helpers

pytestmark = pytest.mark.unit


def _result(*ledgers: Any) -> Any:
    return SimpleNamespace(
        dispute_ledgers=tuple(ledgers),
        committed_events=(),
        stop_reason="max_ticks",
        ticks_committed=100,
    )


def _ledgers() -> tuple[Any, Any]:
    owner_case = helpers.make_case(
        owner=helpers.OWNER,
        parties=(helpers.OWNER, helpers.OTHER),
    )
    other_case = helpers.make_case(
        owner=helpers.OTHER,
        parties=(helpers.OWNER, helpers.OTHER),
    )
    claim = helpers.make_claim(
        owner=helpers.OWNER,
        case=owner_case,
        claimant=helpers.OWNER,
        respondent=helpers.OTHER,
        role="claim",
        claim_kind="debt_owed",
        polarity="affirm",
        evidence_ids=("event-1",),
    )
    counterclaim = helpers.make_claim(
        owner=helpers.OTHER,
        case=other_case,
        claimant=helpers.OTHER,
        respondent=helpers.OWNER,
        role="counterclaim",
        claim_kind="debt_owed",
        polarity="deny",
        counters=claim.claim_ref,
    )
    testimony = helpers.make_testimony(
        owner=helpers.OWNER,
        claim=claim,
        speaker=helpers.OWNER,
        channel="direct",
    )
    evidence = helpers.make_evidence(
        owner=helpers.OWNER,
        claim=claim,
        reference_kind="observed_occurrence",
        reference_id="event-1",
    )
    rule = helpers.make_rule_reference(owner=helpers.OWNER, claim=claim)
    mediation = helpers.make_mediation_reference(owner=helpers.OWNER, case=owner_case)
    resolution = helpers.make_resolution(
        owner=helpers.OWNER,
        case=owner_case,
        proposer=helpers.OWNER,
        terms_digest="terms-1",
    )
    other_resolution = helpers.make_resolution(
        owner=helpers.OTHER,
        case=other_case,
        proposer=helpers.OWNER,
        terms_digest="terms-1",
    )
    owner_ledger = helpers.make_ledger(
        owner=helpers.OWNER,
        cases=(owner_case,),
        claims=(claim,),
        testimony=(testimony,),
        evidence=(evidence,),
        rule_references=(rule,),
        mediation_references=(mediation,),
        resolutions=(resolution,),
        responses=(
            helpers.make_response(
                owner=helpers.OWNER,
                resolution=resolution,
                party=helpers.OWNER,
                kind="accept",
            ),
        ),
    )
    other_ledger = helpers.make_ledger(
        owner=helpers.OTHER,
        cases=(other_case,),
        claims=(counterclaim,),
        resolutions=(other_resolution,),
        responses=(
            helpers.make_response(
                owner=helpers.OTHER,
                resolution=other_resolution,
                party=helpers.OTHER,
                kind="accept",
            ),
        ),
    )
    return owner_ledger, other_ledger


def _built(*ledgers: Any) -> Any:
    harvest = build_completed_run_dispute_harvest(
        _result(*ledgers),
        run_id="run-1",
        input_revision="revision-1",
        generated_tick=100,
    )
    return build_dispute_harvest_result(harvest)


def test_empty_run_produces_empty_snapshot() -> None:
    built = _built()
    assert built.published is True
    assert built.snapshot.provenance_code == "empty"
    assert built.snapshot.counts.candidate_count == 0
    assert built.snapshot.coverage.observed == 0
    assert built.snapshot.coverage.expected == 0
    receipt = dispute_publication_document(built)
    assert receipt["status"] == "empty"
    assert receipt["reason_code"] is None
    assert receipt["candidate_count"] == 0


def test_completed_run_builds_candidates_claims_and_resolutions() -> None:
    owner_ledger, other_ledger = _ledgers()
    built = _built(owner_ledger, other_ledger)
    snapshot = built.snapshot
    assert built.published is True
    assert snapshot.provenance_code == "ok"
    assert len(snapshot.candidates) == 1
    assert len(snapshot.cases) == 1
    assert len(snapshot.claims) == 2
    assert snapshot.counts.counterclaim_count == 1
    assert len(snapshot.testimony) == 1
    assert len(snapshot.evidence) == 1
    assert len(snapshot.rule_references) == 1
    assert len(snapshot.mediation_references) == 1
    assert len(snapshot.resolutions) == 1
    assert snapshot.counts.accepted_count == 2
    assert snapshot.counts.rejected_count == 0
    assert snapshot.claims[0].candidate_id == snapshot.candidates[0].candidate_id
    assert built.receipt["status"] == "published"
    assert built.receipt["reason_code"] == "dispute_published"


def test_truncation_is_explicit_and_bounded() -> None:
    case = helpers.make_case(owner=helpers.OWNER)
    claims = tuple(
        helpers.make_claim(
            owner=helpers.OWNER,
            case=case,
            claimant=f"agent-{index:02d}",
            respondent=helpers.OTHER,
            role="claim",
            claim_kind="debt_owed",
            polarity="affirm",
        )
        for index in range(65)
    )
    built = _built(
        helpers.make_ledger(owner=helpers.OWNER, cases=(case,), claims=claims)
    )
    snapshot = built.snapshot
    assert len(snapshot.claims) == 64
    assert snapshot.candidates[0].claim_count == 64
    assert snapshot.coverage.note == "dispute_truncated"
    assert snapshot.provenance_code == "truncated"
    assert built.receipt["reason_code"] == "dispute_truncated"


def test_oversize_snapshot_fails_without_mutating_runner_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner_ledger, other_ledger = _ledgers()
    result = _result(owner_ledger, other_ledger)
    before = repr(result)
    monkeypatch.setattr(publication, "MAX_DISPUTE_CLAIMS", 1)
    harvest = build_completed_run_dispute_harvest(
        result,
        run_id="run-1",
        input_revision="revision-1",
        generated_tick=100,
    )
    with pytest.raises(DisputeArtifactError) as excinfo:
        build_dispute_harvest_result(harvest)
    assert excinfo.value.code == "dispute_size_limit"
    assert repr(result) == before


def test_case_and_byte_limits_fail_without_publication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import simulation.dispute_codec as codec

    owner_ledger, other_ledger = _ledgers()
    harvest = build_completed_run_dispute_harvest(
        _result(owner_ledger, other_ledger),
        run_id="run-1",
        input_revision="revision-1",
        generated_tick=100,
    )
    monkeypatch.setattr(publication, "MAX_DISPUTE_CASES", 0)
    with pytest.raises(DisputeArtifactError) as excinfo:
        build_dispute_harvest_result(harvest)
    assert excinfo.value.code == "dispute_size_limit"

    monkeypatch.setattr(publication, "MAX_DISPUTE_CASES", 4096)
    monkeypatch.setattr(codec, "MAX_DISPUTE_SNAPSHOT_BYTES", 100)
    with pytest.raises(DisputeArtifactError) as excinfo:
        build_dispute_harvest_result(harvest)
    assert excinfo.value.code == "dispute_size_limit"


def test_entity_mapping_produces_objective_rows() -> None:
    owner_ledger, other_ledger = _ledgers()
    event = SimpleNamespace(
        tick=2,
        actor_id=SimpleNamespace(value="entity-1"),
        details=SimpleNamespace(
            kind="give",
            recipient_id=SimpleNamespace(value="entity-2"),
            item_id=SimpleNamespace(value="item-1"),
            quantity=1,
        ),
    )
    result = SimpleNamespace(
        dispute_ledgers=(owner_ledger, other_ledger),
        committed_events=(event,),
        stop_reason="max_ticks",
        ticks_committed=100,
    )
    harvest = build_completed_run_dispute_harvest(
        result,
        run_id="run-1",
        input_revision="revision-1",
        generated_tick=100,
        entity_to_agent={"entity-1": "agent-1", "entity-2": "agent-2"},
    )
    built = build_dispute_harvest_result(harvest)
    assert built.snapshot.objective_rows
    assert built.snapshot.objective_rows[0].observed_transfer_count == 1


def test_publish_is_called_once() -> None:
    owner_ledger, other_ledger = _ledgers()
    built = _built(owner_ledger, other_ledger)
    published: list[Any] = []

    class _Port:
        def publish(self, item: Any) -> str:
            published.append(item)
            return str(item.publication_id)

    assert publish_dispute_snapshot(built, _Port()) is True
    assert len(published) == 1
    assert published[0].publication_id == built.snapshot.ref.publication_id
    assert decode_dispute_snapshot(published[0].payload) == built.snapshot


def test_publication_failure_leaves_scientific_result_unchanged() -> None:
    owner_ledger, other_ledger = _ledgers()
    result = _result(owner_ledger, other_ledger)
    before = repr(result)
    built = _built(owner_ledger, other_ledger)

    class _Port:
        def publish(self, item: Any) -> str:
            raise OSError("disk unavailable")

    with pytest.raises(OSError):
        publish_dispute_snapshot(built, _Port())
    assert repr(result) == before


def test_receipt_contains_no_private_content() -> None:
    built = _built(*_ledgers())
    receipt = dispute_publication_document(built)
    assert set(receipt) == {
        "run_id",
        "publication_id",
        "snapshot_digest",
        "generated_tick",
        "candidate_count",
        "case_count",
        "claim_count",
        "resolution_count",
        "coverage",
        "status",
        "reason_code",
    }
    text = repr(receipt)
    for token in (
        "agent-1",
        "agent-2",
        "claim-",
        "dcl-",
        "dsc-",
        "resolution-",
        "terms-",
        "frule-",
        "mediation-case-1",
    ):
        assert token not in text


def test_experiments_facade_exports_dispute_publication() -> None:
    for name in (
        "DisputeHarvest",
        "DisputeHarvestResult",
        "build_completed_run_dispute_harvest",
        "build_dispute_harvest_result",
        "dispute_publication_document",
        "publish_dispute_snapshot",
    ):
        assert name in experiments.__all__
        assert hasattr(experiments, name)


def test_publication_document_round_trips_snapshot_bytes() -> None:
    built = _built(*_ledgers())
    payload = encode_dispute_snapshot(built.snapshot)
    assert compute_dispute_publication_id(built.snapshot) == (
        built.snapshot.ref.publication_id
    )
    assert decode_dispute_snapshot(payload) == built.snapshot
