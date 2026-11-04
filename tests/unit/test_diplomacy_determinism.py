"""V4-10 determinism: stable digests, ordering, and no wall-clock identity."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from agents.cognition import (
    DiplomacyFrame,
    DiplomaticAct,
    DiplomaticPartyKind,
    DiplomaticTermKind,
    apply_diplomacy_update,
    diplomacy_ledger_digest,
)

pytestmark = pytest.mark.unit

_SRC = Path(__file__).resolve().parents[2] / "src"


def _observation() -> SimpleNamespace:
    return SimpleNamespace(
        occurrences=(),
        communications=(),
        regional_context=None,
        self_body=None,
        exits=(),
    )


def _update():
    return apply_diplomacy_update(
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


def test_identical_inputs_produce_identical_digests() -> None:
    first = _update()
    second = _update()
    assert diplomacy_ledger_digest(first) == diplomacy_ledger_digest(second)
    assert first.relations[0].party_ids == second.relations[0].party_ids
    assert [row.contact_id for row in first.contacts] == [
        row.contact_id for row in second.contacts
    ]


def test_row_order_is_canonical() -> None:
    ledger = _update()
    assert list(ledger.parties) == sorted(
        ledger.parties, key=lambda row: (row.first_seen_tick, row.party_id)
    )
    assert list(ledger.instruments) == sorted(
        ledger.instruments, key=lambda row: (row.opened_tick, row.instrument_id)
    )


def test_no_wall_clock_uuid_or_hash_in_diplomacy_modules() -> None:
    for name in ("diplomacy.py", "diplomacy_communication.py"):
        source = (_SRC / "agents" / "cognition" / name).read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                called = (
                    func.id
                    if isinstance(func, ast.Name)
                    else func.attr
                    if isinstance(func, ast.Attribute)
                    else ""
                )
                assert called not in {"hash", "uuid4", "uuid1", "now", "utcnow"}
        assert "random" not in source
