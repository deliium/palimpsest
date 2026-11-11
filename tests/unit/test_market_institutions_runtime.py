"""Market ledger carry: loop prepare, fork state, and perspective scope."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest

from agents.cognition import (
    MarketInstitutionError,
    MarketInstitutionLedger,
    Perspective,
    build_cognitive_loop,
    empty_market_institutions,
)
from agents.cognition.configuration import (
    CognitionLoopConfig,
    CognitionMarketMode,
)
from agents.cognition.fork_state import (
    CognitiveLoopForkState,
    CognitiveLoopForkStateError,
)
from agents.cognition.models import CognitiveLoopInput
from tests.unit.market_institutions_helpers import (
    OWNER,
    PEER,
    PEER_ENTITY,
    A,
    observation,
    occurrence,
)

pytestmark = pytest.mark.unit


def test_disabled_loop_prepares_no_ledger() -> None:
    loop = build_cognitive_loop(CognitionLoopConfig())
    loop_input = cast(
        CognitiveLoopInput,
        SimpleNamespace(
            agent_id=OWNER,
            observation=observation(),
            snapshot=None,
        ),
    )
    assert loop._prepare_market_institutions(loop_input, None, None) is None
    assert loop._prepared_market_institutions is None


def test_enabled_loop_prepares_one_ledger() -> None:
    loop = build_cognitive_loop(
        CognitionLoopConfig(market_institution_mode=CognitionMarketMode.DETERMINISTIC)
    )
    loop_input = cast(
        CognitiveLoopInput,
        SimpleNamespace(
            agent_id=OWNER,
            observation=observation(occurrences=(occurrence(source_tick=2),)),
            snapshot=None,
        ),
    )
    prepared = loop._prepare_market_institutions(loop_input, None, None)
    assert type(prepared) is MarketInstitutionLedger
    assert prepared.owner_id == OWNER
    assert len(prepared.venues) == 1


def test_fork_state_carries_the_prepared_ledger() -> None:
    prepared = empty_market_institutions(OWNER)
    loop = build_cognitive_loop(
        CognitionLoopConfig(market_institution_mode=CognitionMarketMode.DETERMINISTIC)
    )
    state = loop.export_fork_state()
    carried = CognitiveLoopForkState(
        **{
            **{
                name: getattr(state, name)
                for name in state.__dataclass_fields__
                if name != "prepared_market_institutions"
            },
            "prepared_market_institutions": prepared,
        }
    )
    loop.restore_fork_state(carried)
    assert loop._prepared_market_institutions is prepared


def test_fork_state_rejects_a_wrong_market_type() -> None:
    loop = build_cognitive_loop(CognitionLoopConfig())
    state = loop.export_fork_state()
    with pytest.raises(CognitiveLoopForkStateError):
        CognitiveLoopForkState(
            **{
                **{
                    name: getattr(state, name)
                    for name in state.__dataclass_fields__
                    if name != "prepared_market_institutions"
                },
                "prepared_market_institutions": object(),
            }
        )


def test_perspective_accepts_only_the_owner_ledger() -> None:
    from tests.cognition_helpers import build_observation

    prepared = empty_market_institutions(OWNER)
    Perspective(
        agent_id=OWNER,
        observation=build_observation(),
        memories=(),
        beliefs=(),
        inbox=(),
        market_institutions=prepared,
    )
    with pytest.raises(MarketInstitutionError):
        Perspective(
            agent_id=PEER,
            observation=build_observation(),
            memories=(),
            beliefs=(),
            inbox=(),
            market_institutions=prepared,
        )
    with pytest.raises(TypeError):
        Perspective(
            agent_id=OWNER,
            observation=build_observation(),
            memories=(),
            beliefs=(),
            inbox=(),
            market_institutions=object(),
        )


def test_ledger_fold_reads_only_own_observation_location() -> None:
    value = empty_market_institutions(OWNER)
    assert value.venues == ()
    from agents.cognition.market_institutions import apply_market_institution_update

    updated = apply_market_institution_update(
        owner_id=OWNER,
        tick=3,
        observation=observation(location=PEER_ENTITY, exits=(A,)),
        prior=value,
    )
    assert updated.venues == ()
