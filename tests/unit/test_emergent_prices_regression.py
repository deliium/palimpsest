"""Flag-off regression: price mode changes no existing trajectory surface."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest

from agents.cognition import build_cognitive_loop
from agents.cognition.configuration import CognitionLoopConfig, CognitionPriceMode
from agents.cognition.models import CognitiveLoopInput
from agents.models import AgentId
from world.identifiers import EntityId

pytestmark = pytest.mark.unit

OWNER = AgentId("agent-1")
BODY = EntityId("body-1")


def test_price_fields_are_absent_from_default_fingerprint() -> None:
    material = CognitionLoopConfig().condition_fingerprint_material()
    assert "price_expectation_mode" not in material
    assert "price_expectation_policy_version" not in material


def test_default_loop_has_no_prepared_price_ledger() -> None:
    loop = build_cognitive_loop(CognitionLoopConfig())
    loop_input = cast(
        CognitiveLoopInput,
        SimpleNamespace(
            agent_id=OWNER,
            observation=SimpleNamespace(
                tick=1,
                observer_id=BODY,
                self_body=SimpleNamespace(location_id=EntityId("loc-a")),
                occurrences=(),
                communications=(),
            ),
            snapshot=None,
        ),
    )
    assert loop._prepare_emergent_prices(loop_input, None, None) is None
    assert loop._prepared_emergent_prices is None


def test_market_only_mode_stays_price_disabled() -> None:
    from agents.cognition.configuration import CognitionMarketMode

    config = CognitionLoopConfig(
        market_institution_mode=CognitionMarketMode.DETERMINISTIC
    )
    assert config.price_expectation_mode is CognitionPriceMode.DISABLED
    material = config.condition_fingerprint_material()
    assert "market_institution_policy_version" in material
    assert "price_expectation_policy_version" not in material
