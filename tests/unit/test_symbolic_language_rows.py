"""Detached symbolic rows are digest-only and validate closed values."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agents.models import AgentId
from analysis.symbolic_language_metrics import (
    SymbolicCompositionRow,
    SymbolicMessageRow,
    symbolic_surface_digest,
)
from experiments.composition import (
    symbolic_analysis_inputs_from_harvest,
    symbolic_composition_rows_from_ledgers,
    symbolic_message_rows_from_events,
)
from world.communications import CommunicationRelation, origin_utterance
from world.events import Talked
from world.identifiers import EntityId, EventId


def _ledger() -> SimpleNamespace:
    composition = SimpleNamespace(
        owner_id=AgentId("a"),
        composition_id="c" * 64,
        kind=SimpleNamespace(value="relational"),
        parts=("alpha", "beta"),
        referent_hypothesis=SimpleNamespace(
            referent_kind=SimpleNamespace(value="location")
        ),
        status=SimpleNamespace(value="active"),
        strength=0.5,
        usage_count=2,
        first_tick=1,
        last_tick=3,
        interpretations=(),
    )
    return SimpleNamespace(compositions=(composition,), interpretations=())


def test_surface_digest_is_stable_and_owner_independent() -> None:
    assert symbolic_surface_digest("alpha") == symbolic_surface_digest("alpha")
    assert symbolic_surface_digest("alpha") != symbolic_surface_digest("beta")
    assert len(symbolic_surface_digest("alpha")) == 16


def test_composition_rows_never_carry_tokens() -> None:
    rows = symbolic_composition_rows_from_ledgers((_ledger(),))
    assert len(rows) == 1
    assert rows[0].part_digests == (
        symbolic_surface_digest("alpha"),
        symbolic_surface_digest("beta"),
    )
    assert "alpha" not in repr(rows[0])
    assert rows[0].strength_band == "mid"


def test_invalid_rows_fail_closed() -> None:
    with pytest.raises(ValueError, match="invalid_kind"):
        SymbolicCompositionRow(
            owner_id="a",
            composition_id="c" * 64,
            kind="nested",
            part_digests=("a", "b"),
            referent_kind=None,
            status="active",
            strength_band="mid",
            usage_count=0,
            tick_range=(0, 0),
        )
    with pytest.raises(ValueError, match="invalid_parse_outcome"):
        SymbolicMessageRow(
            message_id="m",
            speaker_id="s",
            listener_id="l",
            tick=1,
            kind="relational",
            part_digests=("a", "b"),
            parse_outcome="correct",
            declared_confidence_band=None,
        )


def test_message_rows_come_from_delivered_events() -> None:
    utterance = origin_utterance(
        text="call",
        speaker_id=EntityId("body-1"),
        relations=(
            CommunicationRelation(subject="alpha", predicate="call", object="location"),
            CommunicationRelation(
                subject="alpha", predicate="relational", object="beta"
            ),
        ),
    )
    event = SimpleNamespace(
        event_id=EventId("e1"),
        tick=1,
        actor_id=EntityId("body-1"),
        details=Talked(recipient_id=EntityId("body-2"), utterance=utterance),
    )
    rows = symbolic_message_rows_from_events((event,))
    assert len(rows) == 1
    assert rows[0].listener_id == "body-2"
    assert rows[0].kind == "relational"


def test_harvest_marks_missing_inputs_as_empty_not_zero_rows() -> None:
    inputs = symbolic_analysis_inputs_from_harvest(ledgers=None)
    assert inputs.compositions == ()
    assert inputs.messages == ()
