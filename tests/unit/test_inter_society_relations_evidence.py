"""Eight-domain ISR evidence adapters."""

from __future__ import annotations

import pytest

from analysis.inter_society_relations_contract import (
    InterSocietyAvailability,
    InterSocietyDomain,
    InterSocietyRelationsError,
)
from analysis.inter_society_relations_evidence import (
    InterSocietyEvidenceInputs,
    build_domain_panels,
    harvest_domain_evidence_rows,
)
from analysis.macro_society_contract import MacroSocietyLane, derive_macro_society_id

pytestmark = pytest.mark.unit


def _msoc(seed: str) -> str:
    members = tuple(f"{seed}-person-{index}" for index in range(1, 5))
    return derive_macro_society_id(
        creation_tick=0 if seed == "a" else 1,
        founding_member_ids=members,
        lane_signature=(MacroSocietyLane.EXCHANGE.value,),
    )


def test_missing_lanes_are_absent_not_zero_hostility() -> None:
    panels = build_domain_panels(InterSocietyEvidenceInputs())
    by_domain = {panel.domain: panel for panel in panels}
    assert len(panels) == 8
    assert by_domain[InterSocietyDomain.HOSTILITY].availability is (
        InterSocietyAvailability.ABSENT
    )
    assert by_domain[InterSocietyDomain.HOSTILITY].event_count == 0
    assert by_domain[InterSocietyDomain.CULTURAL_SIMILARITY].availability is (
        InterSocietyAvailability.ABSENT
    )
    assert "score" not in by_domain[InterSocietyDomain.CULTURAL_SIMILARITY].values


def test_exchange_present_and_cultural_keys() -> None:
    panels = build_domain_panels(
        InterSocietyEvidenceInputs(
            exchange_event_count=3,
            cultural_overlap_count=2,
            cultural_union_count=4,
            cultural_trait_mean_pairwise_similarity=0.5,
        )
    )
    by_domain = {panel.domain: panel for panel in panels}
    assert by_domain[InterSocietyDomain.EXCHANGE].availability is (
        InterSocietyAvailability.PRESENT
    )
    cultural = by_domain[InterSocietyDomain.CULTURAL_SIMILARITY]
    assert cultural.values["overlap_count"] == 2
    assert cultural.values["union_count"] == 4
    assert cultural.values["jaccard"] == 0.5
    assert "trait_mean_pairwise_similarity" in cultural.values
    assert "score" not in cultural.values


def test_trust_only_inside_one_society_stays_absent() -> None:
    panels = build_domain_panels(
        InterSocietyEvidenceInputs(
            trust_edge_count=None,
            domain_coverage={"trust_proxy": "absent"},
        )
    )
    trust = next(
        panel for panel in panels if panel.domain is InterSocietyDomain.TRUST_PROXY
    )
    assert trust.availability is InterSocietyAvailability.ABSENT


def test_evidence_rows_never_use_isr_prefix() -> None:
    rows = harvest_domain_evidence_rows(
        society_a=_msoc("a"),
        society_b=_msoc("b"),
        tick=10,
        inputs=InterSocietyEvidenceInputs(exchange_event_count=1),
    )
    assert rows
    assert all(not row.token.startswith("isr-") for row in rows)


def test_cultural_score_key_rejected_on_panel() -> None:
    from analysis.inter_society_relations_evidence import InterSocietyDomainPanel

    with pytest.raises(
        InterSocietyRelationsError,
        match="inter_society_relations_forbidden_result_field",
    ):
        InterSocietyDomainPanel(
            domain=InterSocietyDomain.CULTURAL_SIMILARITY,
            event_count=0,
            availability=InterSocietyAvailability.ABSENT,
            coverage_observed=0,
            coverage_expected=0,
            values={"score": 0.0, "availability": "absent"},
        )
