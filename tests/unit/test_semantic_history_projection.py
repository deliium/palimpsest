"""Retained semantic history projection contracts."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from analysis.semantic_drift_metrics import (
    _referent_digest,
    _symbolic_referent_digest,
    semantic_term_digest,
)
from observer.semantic_history import (
    project_semantic_history,
    referent_digest,
)
from observer.semantic_history import (
    semantic_term_digest as observer_term_digest,
)
from observer.semantic_history import (
    symbolic_referent_digest as observer_symbolic_digest,
)

pytestmark = pytest.mark.unit


def _enum(value: str) -> SimpleNamespace:
    return SimpleNamespace(value=value)


def _owner(value: str) -> SimpleNamespace:
    return SimpleNamespace(value=value)


def _binding(
    *,
    owner: str = "agent-a",
    token: str = "river",
    binding_id: str = "a" * 64,
    revision: int = 2,
    history: tuple[SimpleNamespace, ...] = (),
) -> SimpleNamespace:
    return SimpleNamespace(
        owner_id=_owner(owner),
        label_token=token,
        binding_id=binding_id,
        sense_revision=revision,
        sense_history=history,
    )


def _label_record(
    *,
    ordinal: int,
    tick: int,
    referent_id: str = "loc-1",
    associated: tuple[str, ...] = ("loc-2",),
    trigger: str = "promoted",
    confidence: float = 0.5,
) -> SimpleNamespace:
    return SimpleNamespace(
        ordinal=ordinal,
        tick=tick,
        trigger=_enum(trigger),
        referent_kind=_enum("entity"),
        referent_id=referent_id,
        associated_ids=associated,
        confidence=confidence,
    )


def _composition(
    *,
    owner: str = "agent-a",
    composition_id: str = "b" * 64,
    revision: int = 4,
    history: tuple[SimpleNamespace, ...] = (),
    parts: tuple[str, str] = ("river", "hill"),
) -> SimpleNamespace:
    return SimpleNamespace(
        owner_id=_owner(owner),
        composition_id=composition_id,
        kind=_enum("compound"),
        parts=parts,
        sense_revision=revision,
        sense_history=history,
    )


def _composition_record(
    *, ordinal: int, tick: int, associated: tuple[str, ...] = ("x", "y")
) -> SimpleNamespace:
    return SimpleNamespace(
        ordinal=ordinal,
        tick=tick,
        trigger=_enum("merged"),
        referent_kind=None,
        associated_ids=associated,
        confidence=None,
    )


def _checkpoint(
    *,
    bindings: tuple[SimpleNamespace, ...] = (),
    compositions: tuple[SimpleNamespace, ...] = (),
    tick: int = 9,
) -> SimpleNamespace:
    return SimpleNamespace(
        semantic_naming=SimpleNamespace(bindings=bindings),
        symbolic_language=SimpleNamespace(compositions=compositions),
        last_observation_key=(tick, 1),
    )


def test_label_projection_matches_analysis_digests_and_hides_payloads() -> None:
    binding = _binding(
        history=(
            _label_record(ordinal=5, tick=3),
            _label_record(ordinal=6, tick=4, referent_id="loc-3"),
        )
    )
    projected = project_semantic_history(
        "agent-a", _checkpoint(bindings=(binding,)), "label"
    )
    assert [row.ordinal for row in projected.rows] == [5, 6]
    assert projected.rows[0].term_digest == semantic_term_digest(
        "label", label_token="river"
    )
    assert projected.rows[0].referent_digest == _referent_digest("entity", "loc-1")
    assert projected.rows[0].associated_digests == (
        _referent_digest("entity", "loc-2"),
    )
    assert projected.terms[0].first_ordinal == 5
    assert projected.terms[0].current_sense_revision == 2
    rendered = repr(projected)
    assert "river" not in rendered
    assert "loc-1" not in rendered
    assert "loc-3" not in rendered


def test_symbolic_projection_has_optional_referent() -> None:
    composition = _composition(history=(_composition_record(ordinal=2, tick=7),))
    projected = project_semantic_history(
        "agent-a", _checkpoint(compositions=(composition,)), "composition"
    )
    assert projected.rows[0].term_digest == semantic_term_digest(
        "composition", kind="compound", parts=("river", "hill")
    )
    assert projected.rows[0].referent_digest == _symbolic_referent_digest(("x", "y"))
    assert projected.rows[0].referent_kind is None
    assert projected.rows[0].confidence is None
    assert "river" not in repr(projected)


def test_owner_scope_never_merges_reused_local_ids() -> None:
    first = _binding(owner="agent-a", history=(_label_record(ordinal=0, tick=1),))
    second = _binding(owner="agent-b", history=(_label_record(ordinal=0, tick=1),))
    checkpoint = _checkpoint(bindings=(first, second))
    projected = project_semantic_history("agent-b", checkpoint, "label")
    assert len(projected.rows) == 1
    assert projected.rows[0].local_id == second.binding_id
    assert projected.rows[0].referent_digest == referent_digest("entity", "loc-1")


def test_empty_ledger_projects_complete_empty_inventory() -> None:
    projected = project_semantic_history("agent-a", _checkpoint(), "label")
    assert projected.rows == ()
    assert projected.terms == ()
    assert projected.history_first_tick is None


def test_digest_helpers_match_analysis_implementation() -> None:
    assert observer_term_digest("label", label_token="river") == semantic_term_digest(
        "label", label_token="river"
    )
    assert observer_symbolic_digest(("x", "y")) == _symbolic_referent_digest(("x", "y"))
