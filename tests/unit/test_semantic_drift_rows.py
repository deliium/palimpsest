"""Detached semantic rows carry digests only and join usage to prior senses."""

from __future__ import annotations

from types import SimpleNamespace

from agents.models import AgentId
from analysis.semantic_drift_metrics import (
    SemanticAnalysisInputs,
    semantic_analysis_inputs_from_harvest,
    semantic_sense_rows_from_ledgers,
    semantic_term_digest,
    semantic_usage_rows_from_ledgers,
)


def _kind(value: str) -> SimpleNamespace:
    return SimpleNamespace(value=value)


def _record(kind: str, referent: str, tick: int, trigger: str = "promoted"):
    return SimpleNamespace(
        ordinal=tick,
        tick=tick,
        trigger=_kind(trigger),
        referent_kind=_kind(kind),
        referent_id=referent,
        associated_ids=(),
    )


def _naming_ledger(owner: str, token: str) -> SimpleNamespace:
    binding = SimpleNamespace(
        owner_id=AgentId(owner),
        label_token=token,
        referent_kind=_kind("location"),
        sense_revision=1,
        sense_history=(
            _record("location", "loc-a", 2),
            _record("location", "loc-b", 4, "shifted"),
        ),
        evidence=(
            SimpleNamespace(
                tick=1, channel=_kind("observed"), actor_id=None
            ),
            SimpleNamespace(
                tick=5, channel=_kind("communicated"), actor_id=AgentId("speaker")
            ),
        ),
    )
    return SimpleNamespace(bindings=(binding,))


def _symbolic_ledger(owner: str) -> SimpleNamespace:
    composition = SimpleNamespace(
        owner_id=AgentId(owner),
        kind=_kind("relational"),
        parts=("alpha", "beta"),
        sense_revision=0,
        sense_history=(
            SimpleNamespace(
                ordinal=0,
                tick=3,
                trigger=_kind("promoted"),
                referent_kind=_kind("location"),
                confidence=0.5,
                associated_ids=("loc-a", "loc-b"),
            ),
        ),
        evidence=(SimpleNamespace(tick=3, channel=_kind("self_use"), speaker_id=None),),
    )
    return SimpleNamespace(compositions=(composition,))


def test_missing_ledgers_yield_empty_inputs_not_zeros() -> None:
    inputs = semantic_analysis_inputs_from_harvest()
    assert type(inputs) is SemanticAnalysisInputs
    assert inputs.senses == ()
    assert inputs.usages == ()
    assert inputs.generation_index_by_owner is None


def test_same_surface_form_has_the_same_digest_across_owners() -> None:
    label = semantic_term_digest("label", label_token="place_alpha")
    assert label == semantic_term_digest("label", label_token="place_alpha")
    composition = semantic_term_digest(
        "composition", kind="relational", parts=("alpha", "beta")
    )
    assert len(composition) == 16
    assert composition != semantic_term_digest(
        "composition", kind="attributive", parts=("alpha", "beta")
    )


def test_sense_rows_join_naming_and_composition_without_raw_tokens() -> None:
    naming = _naming_ledger("owner-a", "place_alpha")
    symbolic = _symbolic_ledger("owner-a")
    rows = semantic_sense_rows_from_ledgers(
        naming_ledgers=(naming,), symbolic_ledgers=(symbolic,)
    )
    assert len(rows) == 3
    assert {row.term_source for row in rows} == {"label", "composition"}
    assert all("place_alpha" not in repr(row) for row in rows)
    assert all("alpha" not in repr(row) for row in rows)
    shifted = [row for row in rows if row.trigger == "shifted"]
    assert len(shifted) == 1
    assert shifted[0].referent_kind == "location"


def test_usage_rows_use_the_latest_prior_sense_or_none() -> None:
    naming = _naming_ledger("owner-a", "place_alpha")
    rows = semantic_usage_rows_from_ledgers(naming_ledgers=(naming,))
    assert len(rows) == 2
    first, second = rows
    assert first.tick == 1
    assert first.referent_digest is None
    assert second.tick == 5
    assert second.referent_digest is not None
    assert second.channel == "communicated"
    assert second.actor_digest is not None


def test_usage_rows_are_sorted_and_owner_ids_stay_owner_scoped() -> None:
    naming = (
        _naming_ledger("owner-b", "place_beta"),
        _naming_ledger("owner-a", "place_alpha"),
    )
    rows = semantic_usage_rows_from_ledgers(naming_ledgers=naming)
    assert [row.owner_id for row in rows] == [
        "owner-a",
        "owner-a",
        "owner-b",
        "owner-b",
    ]
