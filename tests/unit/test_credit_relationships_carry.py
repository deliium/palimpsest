"""Credit ledger carry: loop prepare, fork state, perspective, and result."""

# mypy: ignore-errors


from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest

from agents.cognition import (
    CreditRelationshipError,
    CreditRelationshipLedger,
    Perspective,
    build_cognitive_loop,
    empty_credit_relationships,
    require_owner_credit_relationships,
)
from agents.cognition.configuration import (
    CognitionCreditMode,
    CognitionLoopConfig,
)
from agents.cognition.fork_state import (
    CognitiveLoopForkState,
    CognitiveLoopForkStateError,
)
from agents.cognition.models import CognitiveLoopInput
from agents.models import AgentId
from tests.unit.test_credit_relationships_helpers import (
    OWNER,
    commitment,
)
from world.identifiers import EntityId

pytestmark = pytest.mark.unit

BODY = EntityId("body-1")


def _observation() -> SimpleNamespace:
    return SimpleNamespace(
        tick=5,
        observer_id=OWNER,
        self_body=SimpleNamespace(location_id=EntityId("loc-a"), entity_id=BODY),
        occurrences=(),
        communications=(),
    )


def test_disabled_loop_prepares_no_ledger() -> None:
    loop = build_cognitive_loop(CognitionLoopConfig())
    loop_input = cast(
        CognitiveLoopInput,
        SimpleNamespace(
            agent_id=OWNER,
            observation=_observation(),
            snapshot=None,
        ),
    )
    assert loop._prepare_credit_relationships(loop_input, commitment(), None) is None
    assert loop._prepared_credit_relationships is None


def test_enabled_loop_prepares_one_owner_ledger() -> None:
    loop = build_cognitive_loop(
        CognitionLoopConfig(
            credit_relationship_mode=CognitionCreditMode.DETERMINISTIC
        )
    )
    loop_input = cast(
        CognitiveLoopInput,
        SimpleNamespace(
            agent_id=OWNER,
            observation=_observation(),
            snapshot=None,
        ),
    )
    prepared = loop._prepare_credit_relationships(
        loop_input, commitment(), None
    )
    assert type(prepared) is CreditRelationshipLedger
    assert prepared.owner_id == OWNER
    assert len(prepared.rows) == 1
    assert prepared.rows[0].promise_count == 1
    assert loop.export_fork_state().prepared_credit_relationships is prepared


def test_fork_state_carries_the_prepared_ledger() -> None:
    prepared = empty_credit_relationships(OWNER)
    loop = build_cognitive_loop(
        CognitionLoopConfig(
            credit_relationship_mode=CognitionCreditMode.DETERMINISTIC
        )
    )
    state = loop.export_fork_state()
    carried = CognitiveLoopForkState(
        **{
            **{
                name: getattr(state, name)
                for name in state.__dataclass_fields__
                if name != "prepared_credit_relationships"
            },
            "prepared_credit_relationships": prepared,
        }
    )
    loop.restore_fork_state(carried)
    assert loop._prepared_credit_relationships is prepared


def test_fork_state_rejects_a_wrong_credit_type() -> None:
    loop = build_cognitive_loop(CognitionLoopConfig())
    state = loop.export_fork_state()
    with pytest.raises(CognitiveLoopForkStateError):
        CognitiveLoopForkState(
            **{
                **{
                    name: getattr(state, name)
                    for name in state.__dataclass_fields__
                    if name != "prepared_credit_relationships"
                },
                "prepared_credit_relationships": object(),
            }
        )


def test_perspective_accepts_only_the_owner_ledger() -> None:
    from tests.cognition_helpers import build_observation

    prepared = empty_credit_relationships(OWNER)
    Perspective(
        agent_id=OWNER,
        observation=build_observation(),
        memories=(),
        beliefs=(),
        inbox=(),
        credit_relationships=prepared,
    )
    with pytest.raises(CreditRelationshipError):
        Perspective(
            agent_id=AgentId("agent-2"),
            observation=build_observation(),
            memories=(),
            beliefs=(),
            inbox=(),
            credit_relationships=prepared,
        )
    with pytest.raises(TypeError):
        Perspective(
            agent_id=OWNER,
            observation=build_observation(),
            memories=(),
            beliefs=(),
            inbox=(),
            credit_relationships=object(),
        )


def test_foreign_owner_ledger_is_rejected_on_carry() -> None:
    with pytest.raises(CreditRelationshipError):
        require_owner_credit_relationships(
            empty_credit_relationships(AgentId("agent-2")), OWNER
        )
