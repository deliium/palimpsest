"""Price ledger carry: loop prepare, fork state, perspective, and result."""

# mypy: ignore-errors


from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest

from agents.cognition import (
    EmergentPriceError,
    EmergentPriceLedger,
    Perspective,
    build_cognitive_loop,
    empty_emergent_prices,
)
from agents.cognition.configuration import (
    CognitionLoopConfig,
    CognitionPriceMode,
)
from agents.cognition.fork_state import (
    CognitiveLoopForkState,
    CognitiveLoopForkStateError,
)
from agents.cognition.models import CognitiveLoopInput
from tests.unit.emergent_prices_helpers import OWNER, PEER, valuations
from world.identifiers import EntityId
from world.values import ItemKind

pytestmark = pytest.mark.unit

BODY = EntityId("body-1")
PEER_BODY = EntityId("body-2")


def _occurrence(*, tick: int = 2):
    return SimpleNamespace(
        kind="exchange_completed",
        public_facts={
            "kind": "exchange_completed",
            "act": "accept",
            "give_item_ids": ("item-a",),
            "take_item_ids": ("item-b",),
            "give_item_kinds": ("food",),
            "take_item_kinds": ("water",),
        },
        actor_id=BODY,
        other_entity_id=PEER_BODY,
        provenance=SimpleNamespace(source_tick=tick),
    )


def _observation(*occurrences: object):
    return SimpleNamespace(
        tick=5,
        observer_id=BODY,
        self_body=SimpleNamespace(location_id=EntityId("loc-a"), entity_id=BODY),
        occurrences=occurrences,
        communications=(),
    )


def test_disabled_loop_prepares_no_ledger() -> None:
    loop = build_cognitive_loop(CognitionLoopConfig())
    loop_input = cast(
        CognitiveLoopInput,
        SimpleNamespace(
            agent_id=OWNER,
            observation=_observation(_occurrence()),
            snapshot=None,
        ),
    )
    assert loop._prepare_emergent_prices(loop_input, None, None) is None
    assert loop._prepared_emergent_prices is None


def test_enabled_loop_prepares_one_owner_ledger() -> None:
    loop = build_cognitive_loop(
        CognitionLoopConfig(price_expectation_mode=CognitionPriceMode.DETERMINISTIC)
    )
    loop_input = cast(
        CognitiveLoopInput,
        SimpleNamespace(
            agent_id=OWNER,
            observation=_observation(_occurrence()),
            snapshot=None,
        ),
    )
    prepared = loop._prepare_emergent_prices(
        loop_input,
        valuations((ItemKind.WATER, ItemKind.FOOD, 1)),
        None,
    )
    assert type(prepared) is EmergentPriceLedger
    assert prepared.owner_id == OWNER
    assert len(prepared.rows) == 1
    assert prepared.rows[0].observation_count == 1
    assert loop.export_fork_state().prepared_emergent_prices is prepared


def test_fork_state_carries_the_prepared_ledger() -> None:
    prepared = empty_emergent_prices(OWNER)
    loop = build_cognitive_loop(
        CognitionLoopConfig(price_expectation_mode=CognitionPriceMode.DETERMINISTIC)
    )
    state = loop.export_fork_state()
    carried = CognitiveLoopForkState(
        **{
            **{
                name: getattr(state, name)
                for name in state.__dataclass_fields__
                if name != "prepared_emergent_prices"
            },
            "prepared_emergent_prices": prepared,
        }
    )
    loop.restore_fork_state(carried)
    assert loop._prepared_emergent_prices is prepared


def test_fork_state_rejects_a_wrong_price_type() -> None:
    loop = build_cognitive_loop(CognitionLoopConfig())
    state = loop.export_fork_state()
    with pytest.raises(CognitiveLoopForkStateError):
        CognitiveLoopForkState(
            **{
                **{
                    name: getattr(state, name)
                    for name in state.__dataclass_fields__
                    if name != "prepared_emergent_prices"
                },
                "prepared_emergent_prices": object(),
            }
        )


def test_perspective_accepts_only_the_owner_ledger() -> None:
    from tests.cognition_helpers import build_observation

    prepared = empty_emergent_prices(OWNER)
    Perspective(
        agent_id=OWNER,
        observation=build_observation(),
        memories=(),
        beliefs=(),
        inbox=(),
        emergent_prices=prepared,
    )
    with pytest.raises(EmergentPriceError):
        Perspective(
            agent_id=PEER,
            observation=build_observation(),
            memories=(),
            beliefs=(),
            inbox=(),
            emergent_prices=prepared,
        )
    with pytest.raises(TypeError):
        Perspective(
            agent_id=OWNER,
            observation=build_observation(),
            memories=(),
            beliefs=(),
            inbox=(),
            emergent_prices=object(),
        )


def test_foreign_owner_ledger_is_rejected_on_carry() -> None:
    from agents.cognition import require_owner_emergent_prices

    with pytest.raises(EmergentPriceError):
        require_owner_emergent_prices(empty_emergent_prices(PEER), OWNER)


def test_cap_violation_is_rejected() -> None:
    from agents.cognition import (
        PriceExpectationLevel,
        PriceExpectationRow,
        PriceUnitSource,
        price_belief_id,
        validate_emergent_price_caps,
    )

    row = PriceExpectationRow(
        item_kind=ItemKind.FOOD,
        unit_kind=ItemKind.WATER,
        unit_source=PriceUnitSource.EXCHANGE_COUNTERPART,
        expected_ratio_milli=1_000,
        confidence_milli=100,
        level=PriceExpectationLevel.NONE,
        valuation_reservation=0,
        observation_count=0,
        quote_count=0,
        first_tick=0,
        last_tick=0,
        observations=(),
        quotes=(),
        row_id=price_belief_id(OWNER, ItemKind.FOOD, "water"),
    )
    ledger = EmergentPriceLedger(OWNER, rows=(row,))
    validate_emergent_price_caps(ledger)
