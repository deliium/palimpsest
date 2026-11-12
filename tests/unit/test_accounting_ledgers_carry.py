"""Accounting ledger carry: loop prepare, fork state, perspective, result."""

# mypy: ignore-errors


from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest

from agents.cognition import (
    AccountingLedger,
    AccountingLedgerError,
    Perspective,
    build_cognitive_loop,
    empty_accounting_ledger,
    require_owner_accounting_ledger,
)
from agents.cognition.configuration import (
    CognitionAccountingLedgerMode,
    CognitionLoopConfig,
)
from agents.cognition.fork_state import (
    CognitiveLoopForkState,
    CognitiveLoopForkStateError,
)
from agents.cognition.models import CognitiveLoopInput
from agents.models import AgentId
from world.identifiers import EntityId

pytestmark = pytest.mark.unit

OWNER = AgentId("agent-owner")


def _artifact() -> SimpleNamespace:
    return SimpleNamespace(
        entity_id=EntityId("artifact-1"),
        record_genre=SimpleNamespace(value="agreement"),
        integrity=SimpleNamespace(value="intact"),
        content_revision=0,
        content=SimpleNamespace(
            relations=(
                SimpleNamespace(
                    subject="xch_food", predicate="acc_v1", object="in3"
                ),
            )
        ),
    )


def _observation() -> SimpleNamespace:
    return SimpleNamespace(
        tick=5,
        observer_id=OWNER,
        self_body=SimpleNamespace(
            location_id=EntityId("loc-a"), entity_id=EntityId("body-1")
        ),
        artifacts=(_artifact(),),
        repositories=(),
        occurrences=(),
        communications=(),
        collective_projects=(),
    )


def test_disabled_loop_prepares_no_ledger() -> None:
    loop = build_cognitive_loop(CognitionLoopConfig())
    loop_input = cast(
        CognitiveLoopInput,
        SimpleNamespace(agent_id=OWNER, observation=_observation(), snapshot=None),
    )
    assert (
        loop._prepare_accounting_ledgers(
            loop_input,
            structured_commitments=None,
            subjective_valuations=None,
            organizations=None,
        )
        is None
    )
    assert loop._prepared_accounting_ledger is None


def test_enabled_loop_prepares_one_owner_ledger() -> None:
    loop = build_cognitive_loop(
        CognitionLoopConfig(
            accounting_ledger_mode=CognitionAccountingLedgerMode.DETERMINISTIC
        )
    )
    loop_input = cast(
        CognitiveLoopInput,
        SimpleNamespace(agent_id=OWNER, observation=_observation(), snapshot=None),
    )
    prepared = loop._prepare_accounting_ledgers(
        loop_input,
        structured_commitments=None,
        subjective_valuations=None,
        organizations=None,
    )
    assert type(prepared) is AccountingLedger
    assert prepared.owner_id == OWNER
    assert len(prepared.entries) == 1
    assert loop.export_fork_state().prepared_accounting_ledger is prepared


def test_fork_state_carries_the_prepared_ledger() -> None:
    prepared = empty_accounting_ledger(OWNER)
    loop = build_cognitive_loop(
        CognitionLoopConfig(
            accounting_ledger_mode=CognitionAccountingLedgerMode.DETERMINISTIC
        )
    )
    state = loop.export_fork_state()
    carried = CognitiveLoopForkState(
        **{
            **{
                name: getattr(state, name)
                for name in state.__dataclass_fields__
                if name != "prepared_accounting_ledger"
            },
            "prepared_accounting_ledger": prepared,
        }
    )
    loop.restore_fork_state(carried)
    assert loop._prepared_accounting_ledger is prepared


def test_fork_state_rejects_a_wrong_accounting_type() -> None:
    loop = build_cognitive_loop(CognitionLoopConfig())
    state = loop.export_fork_state()
    with pytest.raises(CognitiveLoopForkStateError):
        CognitiveLoopForkState(
            **{
                **{
                    name: getattr(state, name)
                    for name in state.__dataclass_fields__
                    if name != "prepared_accounting_ledger"
                },
                "prepared_accounting_ledger": object(),
            }
        )


def test_perspective_accepts_only_the_owner_ledger() -> None:
    from tests.cognition_helpers import build_observation

    prepared = empty_accounting_ledger(OWNER)
    Perspective(
        agent_id=OWNER,
        observation=build_observation(),
        memories=(),
        beliefs=(),
        inbox=(),
        accounting_ledger=prepared,
    )
    with pytest.raises(AccountingLedgerError):
        Perspective(
            agent_id=AgentId("agent-2"),
            observation=build_observation(),
            memories=(),
            beliefs=(),
            inbox=(),
            accounting_ledger=prepared,
        )
    with pytest.raises(TypeError):
        Perspective(
            agent_id=OWNER,
            observation=build_observation(),
            memories=(),
            beliefs=(),
            inbox=(),
            accounting_ledger=object(),
        )


def test_foreign_owner_ledger_is_rejected_on_carry() -> None:
    with pytest.raises(AccountingLedgerError):
        require_owner_accounting_ledger(
            empty_accounting_ledger(AgentId("agent-2")), OWNER
        )
