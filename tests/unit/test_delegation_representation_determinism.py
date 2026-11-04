"""V4-09 determinism: stable ordering, digests, and no ambient randomness."""

from __future__ import annotations

from pathlib import Path

import pytest

from agents.cognition import (
    REPRESENTATION_POLICY_VERSION,
    RepresentationDurationKind,
    RepresentationPrincipalKind,
    RepresentationProvenance,
    RepresentationScopeKind,
    default_representation_policy,
)
from agents.cognition.delegation_representation import (
    apply_representation_update,
    representation_ledger_digest,
)
from agents.cognition.delegation_representation_communication import (
    RepresentationAct,
    RepresentationFrame,
)

pytestmark = pytest.mark.unit

_OWNER = "agent-owner"
_SRC = Path(__file__).resolve().parents[2] / "src"


def _frame(representative: str, actor: str) -> RepresentationFrame:
    return RepresentationFrame(
        act=RepresentationAct.CLAIM,
        principal_kind=RepresentationPrincipalKind.AGENT,
        principal_ref="agent-principal",
        representative_ref=representative,
        scope_kind=RepresentationScopeKind.SPEAK_FOR,
        scope_subject="border",
        duration_kind=RepresentationDurationKind.UNTIL_REVOKED,
        provenance=RepresentationProvenance.SELF_DECLARED,
        actor_ref=actor,
    )


def test_permuted_frames_produce_identical_digests() -> None:
    first = _frame("agent-a", "agent-a")
    second = _frame("agent-b", "agent-b")
    values = []
    for frames in ((first, second), (second, first)):
        ledger = apply_representation_update(
            owner_id=_OWNER,
            tick=1,
            observation=None,
            prior=None,
            frames=frames,
            policy=default_representation_policy(),
        )
        values.append(representation_ledger_digest(ledger))
    assert values[0] == values[1]
    assert REPRESENTATION_POLICY_VERSION == "delegation-representation.v1"


def test_new_modules_have_no_ambient_randomness_or_clock() -> None:
    for name in (
        "delegation_representation.py",
        "delegation_representation_communication.py",
    ):
        text = (
            Path(__file__).resolve().parents[2] / "src" / "agents" / "cognition" / name
        ).read_text(encoding="utf-8")
        assert "hash(" not in text
        assert "uuid" not in text
        assert "random." not in text
        assert "datetime.now" not in text
