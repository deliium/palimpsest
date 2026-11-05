# mypy: ignore-errors
"""V4-11 treaty updates are deterministic and content-addressed."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from agents.cognition import (
    TreatyAct,
    TreatyChangeKind,
    TreatyProvisionKind,
    TreatySubjectKind,
    apply_diplomacy_update,
    diplomacy_ledger_digest,
)
from agents.cognition.diplomacy_communication import TreatyFrame

OBS = SimpleNamespace(communications=(), occurrences=())


def _frame(*, tick: int = 1) -> TreatyFrame:
    return TreatyFrame(
        act=TreatyAct.TREATY_PROPOSE,
        participant_refs=("agent:alice", "agent:bob"),
        subject_kind=TreatySubjectKind.CEASEFIRE,
        change_kind=TreatyChangeKind.ORIGINAL,
        provision_kinds=(TreatyProvisionKind.NON_HOSTILITY,),
        terms_digest="a" * 64,
        effective_tick=tick,
        envoy_ref="alice",
    )


def _ledger(tick: int = 1):
    return apply_diplomacy_update(
        owner_id="alice", tick=tick, observation=OBS, prior=None, frames=(_frame(),)
    )


def test_repeated_update_is_byte_identical_for_equal_ledgers() -> None:
    first = _ledger()
    second = _ledger()
    assert first == second
    assert diplomacy_ledger_digest(first) == diplomacy_ledger_digest(second)
    assert first.treaties[0].treaty_id == second.treaties[0].treaty_id
    assert first.treaty_versions[0].version_id == second.treaty_versions[0].version_id


def test_input_frame_order_does_not_change_rows() -> None:
    first = _frame()
    second = TreatyFrame(
        act=TreatyAct.TREATY_PROPOSE,
        participant_refs=("agent:alice", "agent:carol"),
        subject_kind=TreatySubjectKind.TRADE,
        change_kind=TreatyChangeKind.ORIGINAL,
        provision_kinds=(TreatyProvisionKind.EXCHANGE,),
        terms_digest="b" * 64,
        effective_tick=1,
        envoy_ref="alice",
    )
    forward = apply_diplomacy_update(
        owner_id="alice",
        tick=1,
        observation=OBS,
        prior=None,
        frames=(first, second),
    )
    reverse = apply_diplomacy_update(
        owner_id="alice",
        tick=1,
        observation=OBS,
        prior=None,
        frames=(second, first),
    )
    assert forward == reverse
    assert diplomacy_ledger_digest(forward) == diplomacy_ledger_digest(reverse)


def test_one_field_change_changes_the_digest() -> None:
    ledger = _ledger()
    baseline = diplomacy_ledger_digest(ledger)
    changed = apply_diplomacy_update(
        owner_id="alice",
        tick=1,
        observation=OBS,
        prior=None,
        frames=(
            replace(
                _frame(),
                provision_kinds=(TreatyProvisionKind.PASSAGE,),
            ),
        ),
    )
    assert diplomacy_ledger_digest(changed) != baseline


def test_treaty_modules_have_no_wall_clock_or_unseeded_randomness() -> None:
    root = Path(__file__).resolve().parents[2] / "src"
    for path in (
        *root.glob("agents/cognition/diplomacy*.py"),
        *root.glob("analysis/diplomacy*.py"),
        *root.glob("simulation/diplomacy*.py"),
    ):
        source = path.read_text(encoding="utf-8")
        for forbidden in ("hash(", "uuid", "datetime.now", "time.time"):
            assert forbidden not in source, (path.name, forbidden)
