"""Teaching contracts reject unknown tokens and keep the three stores separate."""

from __future__ import annotations

import logging
import math
from pathlib import Path

import pytest

from agents.cognition.configuration import (
    CognitionLoopConfig,
    CognitionTeachingInteractionMode,
)
from agents.cognition.teaching import (
    AdviceAct,
    AdviceBand,
    AdviceDomain,
    AdviceStore,
    DeclarativeAdvice,
    empty_advice_store,
)
from agents.models import AgentId
from simulation.runner_models import TeachingInteractionMode
from world._skills import SkillDomain
from world._teaching import (
    ClaimBand,
    TeachingAct,
    TeachingInteractionPolicy,
    TeachingOffer,
    default_teaching_interaction_policy,
    parse_teaching_relation,
)
from world.communications import CommunicationRelation
from world.identifiers import EntityId

_ROOT = Path(__file__).resolve().parents[2]
_WORLD_TEACHING = (_ROOT / "src" / "world" / "_teaching.py").read_text(encoding="utf-8")
_COGNITION_TEACHING = (
    _ROOT / "src" / "agents" / "cognition" / "teaching.py"
).read_text(encoding="utf-8")


def _relation(predicate: str, obj: str) -> CommunicationRelation:
    return CommunicationRelation(subject="self", predicate=predicate, object=obj)


def _advice(
    occurrence_id: str,
    *,
    act: AdviceAct = AdviceAct.DEMONSTRATE,
    domain: AdviceDomain = AdviceDomain.FORAGING,
    band: AdviceBand = AdviceBand.UNSPECIFIED,
    tick: int = 1,
) -> DeclarativeAdvice:
    return DeclarativeAdvice(
        occurrence_id=occurrence_id,
        source_agent_id=AgentId("teacher"),
        act=act,
        domain=domain,
        band=band,
        delivery_tick=tick,
    )


def test_policy_defaults_and_construction_log(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="world._teaching")
    policy = default_teaching_interaction_policy()
    assert policy.version == "teaching-interaction-v1"
    assert policy.demonstration_rate == 0.02
    assert policy.practice_together_rate == 0.02
    assert policy.offer_window == 8
    assert policy.belief_explain_rate == 0.08
    assert policy.explain_low_below == 0.34
    assert policy.explain_high_at == 0.67
    assert policy.teaching_response_weight == 0.25
    assert policy.allow_provider is False
    assert "policy_version=teaching-interaction-v1" in caplog.text
    assert "act_count=4" in caplog.text
    assert "INFO" not in caplog.text


def test_policy_rejects_bad_weights(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.ERROR, logger="world._teaching")
    with pytest.raises(ValueError, match="not_finite"):
        TeachingInteractionPolicy(demonstration_rate=math.nan)
    assert "field=demonstration_rate" in caplog.text
    assert "reason_code=not_finite" in caplog.text
    with pytest.raises(ValueError, match="negative_rate"):
        TeachingInteractionPolicy(practice_together_rate=-0.01)
    with pytest.raises(ValueError, match="out_of_range"):
        TeachingInteractionPolicy(explain_low_below=1.5)
    with pytest.raises(ValueError, match="threshold_order"):
        TeachingInteractionPolicy(explain_low_below=0.67, explain_high_at=0.34)
    with pytest.raises(ValueError, match="threshold_order"):
        TeachingInteractionPolicy(explain_low_below=0.5, explain_high_at=0.5)
    with pytest.raises(ValueError, match="offer_window"):
        TeachingInteractionPolicy(offer_window=0)
    with pytest.raises(ValueError, match="offer_window"):
        TeachingInteractionPolicy(offer_window=65)
    with pytest.raises(ValueError, match="invalid_type"):
        TeachingInteractionPolicy(offer_window=True)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="out_of_range"):
        TeachingInteractionPolicy(teaching_response_weight=1.1)
    assert "reason_code=threshold_order" in caplog.text
    assert "reason_code=offer_window" in caplog.text


def test_parse_teaching_relation_accepts_one_closed_act() -> None:
    explain = parse_teaching_relation(_relation("explain", "foraging:high"))
    assert explain == (TeachingAct.EXPLAIN, SkillDomain.FORAGING, ClaimBand.HIGH)
    request = parse_teaching_relation(_relation("request_instruction", "healing"))
    assert request == (
        TeachingAct.REQUEST_INSTRUCTION,
        SkillDomain.HEALING,
        ClaimBand.UNSPECIFIED,
    )
    demonstrate = parse_teaching_relation(_relation("demonstrate", "navigation"))
    assert demonstrate == (
        TeachingAct.DEMONSTRATE,
        SkillDomain.NAVIGATION,
        ClaimBand.UNSPECIFIED,
    )
    practice = parse_teaching_relation(_relation("practice_together", "building"))
    assert practice == (
        TeachingAct.PRACTICE_TOGETHER,
        SkillDomain.BUILDING,
        ClaimBand.UNSPECIFIED,
    )
    assert parse_teaching_relation(_relation("uncertain", "foraging")) is None
    assert parse_teaching_relation("foraging") is None


def test_parse_rejects_bad_claims(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.ERROR, logger="world._teaching")
    assert parse_teaching_relation(_relation("explain", "foraging")) is None
    assert parse_teaching_relation(_relation("explain", "foraging:unspecified")) is None
    assert parse_teaching_relation(_relation("demonstrate", "no-such-domain")) is None
    assert parse_teaching_relation(_relation("demonstrate", "foraging:high")) is None
    assert "reason_code=bad_claim" in caplog.text
    assert "reason_code=unknown_domain" in caplog.text
    assert "foraging:high" not in caplog.text


def test_offer_rejects_non_opening_acts() -> None:
    with pytest.raises(ValueError, match="not_offer"):
        TeachingOffer(
            speaker_id=EntityId("body-a"),
            recipient_id=EntityId("body-b"),
            act=TeachingAct.EXPLAIN,
            domain=SkillDomain.FORAGING,
            delivery_tick=1,
        )
    offer = TeachingOffer(
        speaker_id=EntityId("body-a"),
        recipient_id=EntityId("body-b"),
        act=TeachingAct.DEMONSTRATE,
        domain=SkillDomain.FORAGING,
        delivery_tick=2,
    )
    assert offer.act is TeachingAct.DEMONSTRATE


def test_advice_cursor_drops_oldest_and_skips_known_ids(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="agents.cognition.teaching")
    store = empty_advice_store(AgentId("learner"))
    assert "policy_version=teaching-interaction-v1" in caplog.text
    assert "act_count=4" in caplog.text
    for index in range(33):
        store = store.record(_advice(f"occ-{index}", tick=index))
    assert len(store.rows) == 32
    assert store.rows[0].occurrence_id == "occ-1"
    assert store.rows[-1].occurrence_id == "occ-32"
    again = store.record(_advice("occ-10", tick=99))
    assert again is store
    healing = store.record(_advice("heal-1", domain=AdviceDomain.HEALING, tick=40))
    assert len(healing.rows) == 33
    explain = DeclarativeAdvice(
        occurrence_id="exp-1",
        source_agent_id=AgentId("teacher"),
        act=AdviceAct.EXPLAIN,
        domain=AdviceDomain.CRAFTING,
        band=AdviceBand.LOW,
        delivery_tick=3,
    )
    stored = store.record(explain)
    assert stored.rows[-1].band is AdviceBand.LOW
    with pytest.raises(ValueError, match="bad_claim"):
        DeclarativeAdvice(
            occurrence_id="exp-2",
            source_agent_id=AgentId("teacher"),
            act=AdviceAct.EXPLAIN,
            domain=AdviceDomain.CRAFTING,
            band=AdviceBand.UNSPECIFIED,
            delivery_tick=3,
        )
    with pytest.raises(ValueError, match="unknown_domain"):
        DeclarativeAdvice(
            occurrence_id="bad-domain",
            source_agent_id=AgentId("teacher"),
            act=AdviceAct.DEMONSTRATE,
            domain="foraging",  # type: ignore[arg-type]
            band=AdviceBand.UNSPECIFIED,
            delivery_tick=1,
        )
    overflow = tuple(_advice(f"over-{index}") for index in range(33))
    with pytest.raises(ValueError, match="cursor_overflow"):
        AdviceStore(owner_id=AgentId("learner"), rows=overflow)


def test_modes_lockstep_and_default_disabled() -> None:
    assert {item.value for item in TeachingInteractionMode} == {
        item.value for item in CognitionTeachingInteractionMode
    }
    assert (
        CognitionLoopConfig().teaching_interaction_mode
        is CognitionTeachingInteractionMode.DISABLED
    )
    material = CognitionLoopConfig().condition_fingerprint_material()
    assert material["teaching_interaction_mode"] == "disabled"


def test_modules_do_not_cross_the_boundary() -> None:
    world_imports = [
        line.strip()
        for line in _WORLD_TEACHING.splitlines()
        if line.startswith("import ") or line.startswith("from ")
    ]
    cognition_imports = [
        line.strip()
        for line in _COGNITION_TEACHING.splitlines()
        if line.startswith("import ") or line.startswith("from ")
    ]
    assert all(
        not line.startswith("from agents") and " import agents" not in line
        for line in world_imports
    )
    assert all("world._skills" not in line for line in cognition_imports)
    assert all("world._teaching" not in line for line in cognition_imports)
    assert all("world._state" not in line for line in cognition_imports)
