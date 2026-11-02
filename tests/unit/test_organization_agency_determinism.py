"""Deterministic collective-agency updates and identity stability."""

from __future__ import annotations

import ast
import random
from pathlib import Path

import pytest

from agents.cognition import (
    OrganizationAgencyAct,
    OrganizationAgencyClaim,
    OrganizationAgencyLedger,
    apply_organization_agency_update,
    organization_agency_claim_relation,
)
from tests.unit.organization_agency_helpers import (
    OWNER,
    FakeCommunication,
    FakeContent,
    FakeObservation,
    FakeUtterance,
    concept_ledger,
)
from tests.unit.test_organization_agency_update import (
    _position_claim,
    _propose_claim,
)
from world.identifiers import EntityId

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
MODULES = (
    ROOT / "src" / "agents" / "cognition" / "organization_agency.py",
    ROOT / "src" / "agents" / "cognition" / "organization_agency_actions.py",
    ROOT / "src" / "agents" / "cognition" / "organization_agency_communication.py",
)


def _run(
    claims: list[OrganizationAgencyClaim], *, seed: int = 7
) -> OrganizationAgencyLedger:
    random.Random(seed).shuffle(claims)
    communications = tuple(
        FakeCommunication(
            speaker_id=EntityId(
                "body-agent-2"
                if claim.act is not OrganizationAgencyAct.OPPOSE
                else "body-agent-3"
            ),
            listener_id=EntityId("body-agent-1"),
            utterance=FakeUtterance(
                content=FakeContent(
                    relations=(organization_agency_claim_relation(claim),)
                )
            ),
        )
        for claim in claims
    )
    return apply_organization_agency_update(
        owner_id=OWNER,
        tick=1,
        observation=FakeObservation(
            observer_id=EntityId("body-agent-1"), communications=communications
        ),
        prior=None,
        organization_concepts=concept_ledger(
            member_ids=("agent-1", "agent-2", "agent-3")
        ),
    )


def test_repeated_updates_are_identical() -> None:
    claims = [_propose_claim()]
    assert _run(claims) == _run(claims)


def test_shuffled_communications_produce_the_same_ledger() -> None:
    claims = [
        _propose_claim(),
        _position_claim(OrganizationAgencyAct.SUPPORT),
        _position_claim(OrganizationAgencyAct.OPPOSE),
    ]
    assert _run(claims, seed=1) == _run(claims, seed=99)


def test_agency_modules_use_no_global_nondeterminism() -> None:
    forbidden = {"hash", "uuid4", "now", "time"}
    for path in MODULES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = getattr(func, "id", None) or getattr(func, "attr", None)
                assert name not in forbidden, (path, name)
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name not in {"uuid", "random"}, (
                        path,
                        alias.name,
                    )


def test_decision_identity_is_reproducible() -> None:
    first = _run([_propose_claim()])
    second = _run([_propose_claim()])
    assert first.concepts[0].proposals[0].proposal_id == (
        second.concepts[0].proposals[0].proposal_id
    )
    assert first.notices == second.notices
