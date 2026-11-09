"""Closed ISR contract: domains, forbid-list, and ``isr-`` identity."""

from __future__ import annotations

import hashlib
import json

import pytest

from analysis.diplomacy_contract import DIPLOMACY_FORBIDDEN_RESULT_FIELDS
from analysis.inter_society_relations_contract import (
    CULTURAL_SIMILARITY_ALLOWED_VALUE_KEYS,
    INTER_SOCIETY_DOMAIN_KEYS,
    INTER_SOCIETY_RELATION_WINDOW_TICKS,
    INTER_SOCIETY_RELATIONS_FORBIDDEN_RESULT_FIELDS,
    INTER_SOCIETY_RELATIONS_ID_NAMESPACE,
    InterSocietyAvailability,
    InterSocietyDomain,
    InterSocietyRelationsError,
    assert_no_forbidden_fields,
    derive_inter_society_pair_id,
    ordered_society_pair,
    require_inter_society_pair_id,
    validate_cultural_similarity_keys,
)
from analysis.macro_society_contract import MacroSocietyLane, derive_macro_society_id

pytestmark = pytest.mark.unit

MEMBERS_A = ("person-1", "person-2", "person-3", "person-4")
MEMBERS_B = ("person-5", "person-6", "person-7", "person-8")
LANES = (MacroSocietyLane.CULTURE.value, MacroSocietyLane.EXCHANGE.value)


def _msoc(members: tuple[str, ...], *, tick: int = 0) -> str:
    return derive_macro_society_id(
        creation_tick=tick,
        founding_member_ids=members,
        lane_signature=LANES,
    )


def test_eight_closed_domains_and_availability() -> None:
    assert INTER_SOCIETY_DOMAIN_KEYS == {
        "cooperation",
        "hostility",
        "exchange",
        "migration",
        "trust_proxy",
        "agreement",
        "conflict",
        "cultural_similarity",
    }
    assert set(InterSocietyDomain) and len(InterSocietyDomain) == 8
    assert {item.value for item in InterSocietyAvailability} == {
        "present",
        "partial",
        "absent",
    }
    assert INTER_SOCIETY_RELATION_WINDOW_TICKS == 32


def test_forbid_list_extends_diplomacy() -> None:
    assert (
        DIPLOMACY_FORBIDDEN_RESULT_FIELDS
        <= INTER_SOCIETY_RELATIONS_FORBIDDEN_RESULT_FIELDS
    )
    for name in (
        "civilization_relationship_score",
        "alliance_score",
        "enmity_score",
        "score",
        "composite",
        "bilateral_score",
        "trust",
    ):
        assert name in INTER_SOCIETY_RELATIONS_FORBIDDEN_RESULT_FIELDS


def test_pair_id_shape_and_reproducible_digest() -> None:
    society_a = _msoc(MEMBERS_A)
    society_b = _msoc(MEMBERS_B, tick=1)
    left, right = ordered_society_pair(society_a, society_b)
    value = derive_inter_society_pair_id(
        window_tick=32,
        society_a=society_b,
        society_b=society_a,
        domain_signature=("exchange", "cooperation"),
    )
    assert value.startswith("isr-")
    assert len(value) == len("isr-") + 16
    payload = {
        "namespace": INTER_SOCIETY_RELATIONS_ID_NAMESPACE,
        "window_tick": 32,
        "society_a": left,
        "society_b": right,
        "domain_signature": ["cooperation", "exchange"],
    }
    expected = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:16]
    assert value == f"isr-{expected}"
    assert require_inter_society_pair_id(value) == value


def test_ordered_pair_rejects_identical_societies() -> None:
    society = _msoc(MEMBERS_A)
    with pytest.raises(
        InterSocietyRelationsError, match="inter_society_relations_invalid_pair"
    ):
        ordered_society_pair(society, society)


def test_forbidden_and_cultural_keys() -> None:
    with pytest.raises(
        InterSocietyRelationsError,
        match="inter_society_relations_forbidden_result_field",
    ):
        assert_no_forbidden_fields({"alliance_score": 1})
    validate_cultural_similarity_keys(
        {
            "overlap_count": 1,
            "union_count": 2,
            "jaccard": 0.5,
            "trait_mean_pairwise_similarity": 0.25,
            "availability": "present",
        }
    )
    assert "score" not in CULTURAL_SIMILARITY_ALLOWED_VALUE_KEYS
    with pytest.raises(
        InterSocietyRelationsError,
        match="inter_society_relations_forbidden_result_field",
    ):
        validate_cultural_similarity_keys({"score": 0.0})
