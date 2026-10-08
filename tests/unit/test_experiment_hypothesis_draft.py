"""Closed experiment drafts cannot name physics."""

from __future__ import annotations

import logging

import pytest

from agents.cognition.experimentation import (
    ExperimentCognitionBinding,
    compile_experiment_command,
    empty_experiment_ledger,
    parse_experiment_draft,
)
from agents.cognition.models import ActionDirection
from agents.models import AgentId
from llm.prompts.loader import load_prompt
from world.actions import Experiment

_OWNER = AgentId("owner-1")


class _Seen:
    def __init__(self, entity_id: str) -> None:
        self.entity_id = type("Id", (), {"value": entity_id})()


class _Observation:
    def __init__(self, *ids: str, tick: int = 2) -> None:
        self.tick = tick
        self.items = tuple(_Seen(item) for item in ids)
        self.resources = ()
        self.structures = ()
        self.artifacts = ()


def _ledger() -> object:
    return empty_experiment_ledger(
        _OWNER,
        ExperimentCognitionBinding(
            max_hypotheses=4,
            max_trials_per_tick=1,
            repeat_threshold=2,
            learn_into_genealogy=False,
            allow_provider=False,
        ),
    )


def test_physics_payload_is_rejected_and_emits_no_command(
    caplog: pytest.LogCaptureFixture,
) -> None:
    payload = {
        "operator": "combine",
        "operand_a_id": "item-a",
        "operand_b_id": "item-b",
        "process_token": "none",
        "predicted_outcome": "success",
        "delta": "emit_catalog_product",
        "product_id": "harvest_wood",
    }
    with caplog.at_level(logging.WARNING):
        action, reason = parse_experiment_draft(payload)
        compiled = compile_experiment_command(
            _OWNER,
            _ledger(),  # type: ignore[arg-type]
            _Observation("item-a", "item-b"),
            draft=payload,
            allow_provider=True,
        )
    assert action is None
    assert reason == "experiment_draft_physics"
    assert compiled.command is None
    assert compiled.reason == "experiment_draft_physics"
    assert "experiment_draft_rejected" in caplog.text
    assert "harvest_wood" not in caplog.text
    assert "emit_catalog_product" not in caplog.text


def test_deterministic_proposer_uses_observed_ids_only(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO):
        compiled = compile_experiment_command(
            _OWNER,
            _ledger(),  # type: ignore[arg-type]
            _Observation("item-b", "item-a"),
        )
    command = compiled.command
    assert isinstance(command, Experiment)
    assert command.operand_a_id.value == "item-a"
    assert command.operand_b_id is not None
    assert command.operand_b_id.value == "item-b"
    assert command.hypothesis_id.startswith("hyp:")
    assert not hasattr(command, "delta")
    assert not hasattr(command, "predicted_outcome")
    assert compiled.hypothesis is not None
    assert compiled.hypothesis.predicted_outcome == "success"
    assert "experiment_hypothesis_proposed" in caplog.text


def test_unobserved_operand_is_rejected() -> None:
    compiled = compile_experiment_command(
        _OWNER,
        _ledger(),  # type: ignore[arg-type]
        _Observation("item-a"),
        draft={
            "operator": "combine",
            "operand_a_id": "item-a",
            "operand_b_id": "item-missing",
            "process_token": "none",
            "predicted_outcome": "failure",
        },
        allow_provider=True,
    )
    assert compiled.command is None
    assert compiled.reason == "experiment_operand_not_observed"


def test_provider_draft_is_off_by_default() -> None:
    compiled = compile_experiment_command(
        _OWNER,
        _ledger(),  # type: ignore[arg-type]
        _Observation("item-a", "item-b"),
        draft={
            "operator": "combine",
            "operand_a_id": "item-a",
            "operand_b_id": "item-b",
            "process_token": "none",
        },
    )
    assert compiled.reason == "experiment_provider_disabled"
    assert compiled.command is None


def test_action_direction_membership_is_unchanged() -> None:
    assert tuple(item.value for item in ActionDirection) == (
        "wait",
        "move",
        "search",
        "drink",
        "eat",
        "sleep",
        "flee",
        "communicate",
        "help",
        "feed",
        "transport",
        "attack",
    )


def test_experiment_hypothesis_prompt_loads() -> None:
    loaded = load_prompt("experiment_hypothesis", "v1")
    assert loaded.name == "experiment_hypothesis"
    assert loaded.version == "v1"
    assert "delta" not in loaded.templates[0].text
    joined = " ".join(template.text for template in loaded.templates)
    assert "{{schema_name}}" in joined
    assert "product" in loaded.templates[0].text
