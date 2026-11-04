"""V4-10 completed-run diplomacy publication composition."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agents.cognition import (
    DiplomacyFrame,
    DiplomaticAct,
    DiplomaticPartyKind,
    DiplomaticTermKind,
    apply_diplomacy_update,
)
from experiments.diplomacy_harvest import (
    DiplomacyHarvest,
    build_completed_run_diplomacy_harvest,
)
from experiments.diplomacy_publication import (
    build_diplomacy_harvest_result,
    diplomacy_publication_document,
    publish_diplomacy_snapshot,
)
from simulation.diplomacy_models import DiplomacyArtifactError

pytestmark = pytest.mark.unit


def _observation() -> SimpleNamespace:
    return SimpleNamespace(
        occurrences=(),
        communications=(),
        regional_context=None,
        self_body=None,
        exits=(),
    )


def _runner_result() -> SimpleNamespace:
    ledger = apply_diplomacy_update(
        owner_id="agent-a",
        tick=1,
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
        ticks_committed=1,
        stop_reason=SimpleNamespace(value="max_ticks"),
        diplomacy_ledgers=(ledger,),
    )


def _harvest() -> DiplomacyHarvest:
    return build_completed_run_diplomacy_harvest(_runner_result())


class _Port:
    def __init__(self, fail: bool = False) -> None:
        self.publications: list[object] = []
        self.fail = fail

    def publish(self, publication: object) -> None:
        if self.fail:
            raise DiplomacyArtifactError("diplomacy_publication_exists")
        self.publications.append(publication)


def test_missing_ledger_is_disabled() -> None:
    result = build_diplomacy_harvest_result(
        None, run_id="run-1", revision="rev-1", window_end=1
    )
    assert result.receipt["status"] == "disabled"
    assert result.snapshot is None


def test_incomplete_run_is_unavailable() -> None:
    result = build_diplomacy_harvest_result(
        _harvest(),
        run_id="run-1",
        revision="rev-1",
        window_end=1,
        stop_reason="cancelled",
    )
    assert result.receipt["status"] == "unavailable"
    assert result.snapshot is None


def test_ready_snapshot_contains_relation_and_termination_rows() -> None:
    result = build_diplomacy_harvest_result(
        _harvest(), run_id="run-1", revision="rev-1", window_end=1
    )
    assert result.receipt["status"] == "ready"
    assert result.snapshot is not None
    assert result.snapshot.relations
    assert result.snapshot.instruments
    assert result.snapshot.summary.relation_count == 1
    assert result.snapshot.summary.instrument_count == 1
    document = diplomacy_publication_document(result.receipt)
    assert document["publication_id"] == result.snapshot.publication_id
    assert "party_token" not in document


def test_publish_is_idempotent_and_failure_isolated() -> None:
    result = build_diplomacy_harvest_result(
        _harvest(), run_id="run-1", revision="rev-1", window_end=1
    )
    port = _Port()
    published = publish_diplomacy_snapshot(result, port)
    assert published.published is True
    assert published.receipt["status"] == "published"
    again = publish_diplomacy_snapshot(result, port)
    assert again.published is True

    failing = publish_diplomacy_snapshot(result, _Port(fail=True))
    assert failing.published is False
    assert failing.receipt["status"] == "failed"
    assert failing.receipt["reason"] == "diplomacy_publication_exists"


def test_scientific_result_is_unchanged() -> None:
    runner_result = _runner_result()
    before = runner_result.ticks_committed
    harvest = build_completed_run_diplomacy_harvest(runner_result)
    build_diplomacy_harvest_result(
        harvest, run_id="run-1", revision="rev-1", window_end=1
    )
    assert runner_result.ticks_committed == before
    assert len(runner_result.diplomacy_ledgers) == 1


def test_recalled_envoy_termination_maps_to_published_envoy_id() -> None:
    ledger = apply_diplomacy_update(
        owner_id="agent-a",
        tick=1,
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
            ),
        ),
    )
    relation_id = ledger.relations[0].relation_id
    ledger = apply_diplomacy_update(
        owner_id="agent-a",
        tick=2,
        observation=_observation(),
        prior=ledger,
        frames=(
            DiplomacyFrame(
                act=DiplomaticAct.ACCREDIT,
                envoy_ref="envoy-e",
                actor_ref="envoy-e",
                party_kind=DiplomaticPartyKind.AGENT,
                party_ref="agent-a",
                mandate_ref="rmd-" + "0" * 16,
                relation_ref=relation_id,
            ),
        ),
    )
    ledger = apply_diplomacy_update(
        owner_id="agent-a",
        tick=3,
        observation=_observation(),
        prior=ledger,
        frames=(
            DiplomacyFrame(
                act=DiplomaticAct.RECALL,
                envoy_ref="envoy-e",
                actor_ref="envoy-e",
                party_kind=DiplomaticPartyKind.AGENT,
                party_ref="agent-a",
                relation_ref=relation_id,
            ),
        ),
    )
    assert any(row.target_kind == "envoy" for row in ledger.terminations)

    runner_result = SimpleNamespace(
        run_id=SimpleNamespace(value="run-1"),
        ticks_committed=3,
        stop_reason=SimpleNamespace(value="max_ticks"),
        diplomacy_ledgers=(ledger,),
    )
    result = build_diplomacy_harvest_result(
        build_completed_run_diplomacy_harvest(runner_result),
        run_id="run-1",
        revision="rev-1",
        window_end=3,
    )
    assert result.snapshot is not None
    published_envoy_ids = {row.envoy_id for row in result.snapshot.envoys}
    envoy_terminations = [
        row for row in result.snapshot.terminations if row.target_kind == "envoy"
    ]
    assert envoy_terminations
    assert all(row.target_ref in published_envoy_ids for row in envoy_terminations)
