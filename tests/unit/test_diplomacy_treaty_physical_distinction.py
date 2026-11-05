# mypy: ignore-errors
"""V4-11 treaties never become world authority or enforcement."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agents.cognition import (
    TreatyAct,
    TreatyChangeKind,
    TreatyProvisionKind,
    TreatySubjectKind,
    apply_diplomacy_update,
)
from agents.cognition.diplomacy_communication import TreatyFrame
from agents.models import AgentId
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionResolutionStatus, ActionSubmission
from simulation.models import SimulationRunConfig
from tests.unit.test_diplomacy_physical_distinction import _bootstrap
from world.actions import Give, Take
from world.identifiers import EntityId

pytestmark = pytest.mark.unit

OBS = SimpleNamespace(communications=(), occurrences=())


def _ledger():
    frame = TreatyFrame(
        act=TreatyAct.TREATY_PROPOSE,
        participant_refs=("agent:agent-e2e-a", "agent:agent-e2e-b"),
        subject_kind=TreatySubjectKind.CEASEFIRE,
        change_kind=TreatyChangeKind.ORIGINAL,
        provision_kinds=(TreatyProvisionKind.NON_HOSTILITY,),
        terms_digest="a" * 64,
        effective_tick=1,
        envoy_ref="agent-e2e-a",
    )
    return apply_diplomacy_update(
        owner_id="agent-e2e-a", tick=1, observation=OBS, prior=None, frames=(frame,)
    )


def test_treaty_belief_does_not_change_admission() -> None:
    ledger = _ledger()
    assert ledger.treaties
    engine = WorldEngine(config=SimulationRunConfig(seed=41), bootstrap=_bootstrap())
    batch = engine.observe()
    possible = engine.resolve_tick(
        (
            ActionSubmission(
                token=batch.token,
                agent_id=AgentId("agent-e2e-a"),
                command=Give(
                    recipient_id=EntityId("body-e2e-b"),
                    item_id=EntityId("item-e2e"),
                ),
            ),
        )
    )
    assert possible.resolutions[0].status is not ActionResolutionStatus.REJECTED


def test_treaty_belief_does_not_make_impossible_command_possible() -> None:
    ledger = _ledger()
    assert ledger.treaties
    engine = WorldEngine(config=SimulationRunConfig(seed=42), bootstrap=_bootstrap())
    batch = engine.observe()
    impossible = engine.resolve_tick(
        (
            ActionSubmission(
                token=batch.token,
                agent_id=AgentId("agent-e2e-a"),
                command=Take(item_id=EntityId("item-missing")),
            ),
        )
    )
    assert impossible.resolutions[0].status is ActionResolutionStatus.REJECTED


def test_treaty_modules_never_construct_or_resolve_commands() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "src"
    for path in (
        *root.glob("agents/cognition/diplomacy*.py"),
        *root.glob("analysis/diplomacy*.py"),
        *root.glob("simulation/diplomacy*.py"),
        *root.glob("experiments/diplomacy*.py"),
        *root.glob("persistence/diplomacy*.py"),
        *root.glob("research_runner/diplomacy*.py"),
    ):
        source = path.read_text(encoding="utf-8")
        for forbidden in (
            "AgentCommand(",
            "ActionSubmission(",
            "submit_command(",
            "resolve_command(",
            "admit(",
        ):
            assert forbidden not in source, (path.name, forbidden)
