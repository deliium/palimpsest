"""Closed macro-society contract: ids, coverage, and fail-closed validation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from analysis.macro_society_contract import (
    MACRO_SOCIETY_ID_NAMESPACE,
    MacroSocietyCoverage,
    MacroSocietyError,
    MacroSocietyLane,
    derive_macro_society_id,
    require_macro_society_id,
    validate_member_ids,
)

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_MODULE = ROOT / "src" / "analysis" / "macro_society_contract.py"

MEMBERS = ("person-1", "person-2", "person-3", "person-4", "person-5")
LANES = (MacroSocietyLane.CULTURE.value, MacroSocietyLane.INTERACTION.value)


def _derive(
    *,
    tick: int = 10,
    members: tuple[str, ...] = MEMBERS,
    lanes: tuple[str, ...] = LANES,
) -> str:
    return derive_macro_society_id(
        creation_tick=tick,
        founding_member_ids=members,
        lane_signature=lanes,
    )


def test_id_shape_and_reproducible_digest() -> None:
    value = _derive()
    assert value.startswith("msoc-")
    assert len(value) == len("msoc-") + 16

    expected_payload = {
        "namespace": MACRO_SOCIETY_ID_NAMESPACE,
        "creation_tick": 10,
        "founding_member_ids": list(MEMBERS),
        "lane_signature": sorted(LANES),
    }
    expected = hashlib.sha256(
        json.dumps(
            expected_payload, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()[:16]
    assert value == f"msoc-{expected}"


def test_id_is_order_independent() -> None:
    reversed_evidence = _derive(
        members=tuple(reversed(MEMBERS)), lanes=tuple(reversed(LANES))
    )
    assert reversed_evidence == _derive()


def test_id_changes_with_creation_evidence() -> None:
    base = _derive()
    assert _derive(tick=11) != base
    assert _derive(members=(*MEMBERS[:-1], "person-9")) != base
    assert _derive(lanes=(MacroSocietyLane.CULTURE.value,)) != base


@pytest.mark.parametrize(
    ("members", "code"),
    [
        ((), "macro_society_empty_member_set"),
        (("person-1", "person-1"), "macro_society_duplicate_member"),
        (("person-1", 7), "macro_society_content_payload_rejected"),
        (("person-1 ",), "macro_society_invalid_member"),
    ],
)
def test_invalid_members_fail_closed(
    members: tuple[object, ...], code: str
) -> None:
    with pytest.raises(MacroSocietyError, match=code):
        derive_macro_society_id(
            creation_tick=0,
            founding_member_ids=members,  # type: ignore[arg-type]
            lane_signature=(MacroSocietyLane.CULTURE.value,),
        )


def test_content_payload_and_unknown_lane_are_rejected() -> None:
    with pytest.raises(
        MacroSocietyError, match="macro_society_content_payload_rejected"
    ):
        validate_member_ids("members", "person-1")
    with pytest.raises(MacroSocietyError, match="macro_society_unknown_lane"):
        derive_macro_society_id(
            creation_tick=0,
            founding_member_ids=("person-1",),
            lane_signature=("not_a_lane",),
        )
    with pytest.raises(MacroSocietyError, match="macro_society_unknown_lane"):
        derive_macro_society_id(
            creation_tick=0,
            founding_member_ids=("person-1",),
            lane_signature=(),
        )


def test_negative_tick_is_rejected() -> None:
    with pytest.raises(ValueError):
        _derive(tick=-1)


@pytest.mark.parametrize(
    "value",
    [
        "msoc-0123456789ABCDEF",
        "msoc-0123456789abcde",
        "msoc-0123456789abcdef0",
        "msocc-0123456789abcdef",
        "",
    ],
)
def test_require_macro_society_id_rejects_invalid_values(value: str) -> None:
    with pytest.raises(MacroSocietyError, match="macro_society_invalid_id"):
        require_macro_society_id(value)


def test_require_macro_society_id_accepts_derived_value() -> None:
    assert require_macro_society_id(_derive()) == _derive()


def test_coverage_derives_ratio_and_rejects_inconsistent_values() -> None:
    coverage = MacroSocietyCoverage.of(3, 4)
    assert coverage.observed == 3
    assert coverage.expected == 4
    assert coverage.ratio == 0.75

    absent = MacroSocietyCoverage.of(0, 0)
    assert absent.ratio is None

    with pytest.raises(MacroSocietyError, match="macro_society_invalid_coverage"):
        MacroSocietyCoverage(observed=5, expected=4, ratio=None)
    with pytest.raises(MacroSocietyError, match="macro_society_invalid_coverage"):
        MacroSocietyCoverage(observed=1, expected=4, ratio=0.5)


def test_contract_source_has_no_hash_or_uuid_shortcuts() -> None:
    source = CONTRACT_MODULE.read_text(encoding="utf-8")
    assert "hash(" not in source
    assert "import uuid" not in source
    assert "uuid4" not in source
