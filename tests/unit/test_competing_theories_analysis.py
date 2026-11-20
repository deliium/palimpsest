# mypy: ignore-errors

"""Detached theory support communities and matched performance."""

from __future__ import annotations

import pytest

from analysis.competing_theories_analysis import harvest_competing_theories_analysis
from analysis.competing_theories_models import (
    CompetingTheoryFacts,
    TheoryCitationFact,
    TheoryClaimFact,
    TheoryForecastFact,
    TheoryReceiptFact,
    TheoryStanceFact,
)
from analysis.metric_service import MetricComputationInputs, assemble_metric_documents
from analysis.specifications import METRIC_FAMILY_COUNT
from experiments.competing_theories_publication import (
    compose_competing_theories_snapshot,
)

pytestmark = pytest.mark.unit


def _facts() -> CompetingTheoryFacts:
    return CompetingTheoryFacts(
        run_token="a1",
        owner_tokens=("a2", "a3", "a4", "b2", "b3"),
        claims=(
            TheoryClaimFact("c1", "a2", "d1", "continuity", "spring", 0),
            TheoryClaimFact("c2", "b2", "d1", "recurrence", "summer", 2),
        ),
        stances=(
            TheoryStanceFact("a2", "d1", "c1", 1, "1a"),
            TheoryStanceFact("a3", "d1", "c1", 1, "1b"),
            TheoryStanceFact("a4", "d1", "c1", 1, "1c"),
            TheoryStanceFact("b2", "d1", "c2", 3, "1d"),
            TheoryStanceFact("b3", "d1", "c2", 3, "1e"),
        ),
        citations=(
            TheoryCitationFact(
                "a2", "c1", "supports", "own_observation", "e1", 1, True
            ),
            TheoryCitationFact(
                "b2", "c2", "supports", "own_scored_case", "e2", 2, True
            ),
        ),
        receipts=(
            TheoryReceiptFact(
                "a2", "a3", "d1", "c1", "support", 2, True, "communicated", "1f"
            ),
            TheoryReceiptFact("b2", "b3", "d1", "c2", "teach", 3, True, "taught", "2a"),
        ),
        forecasts=(
            TheoryForecastFact(
                "a2",
                "2b",
                "d1",
                ("spring", "summer"),
                (("c1", "spring", 1000, 500), ("c2", "summer", 1000, 0)),
                1,
                3,
                "scored",
                "summer",
                3,
                vectors=(("c1", (667, 333)), ("c2", (333, 667))),
            ),
        ),
        owner_last_ticks=(("a2", 10), ("a3", 10), ("a4", 10), ("b2", 10), ("b3", 10)),
    )


def test_popularity_and_accuracy_stay_separate() -> None:
    analysis = harvest_competing_theories_analysis(_facts())
    assert analysis.claim_count == 2
    assert analysis.support_edge_count == 5
    assert analysis.community_count >= 2
    assert analysis.failure_count == 1
    assert analysis.scored_count == 2
    assert analysis.teaching_count == 1
    communities = {row.claim_token for row in analysis.communities}
    assert communities == {"c1", "c2"}


def test_missing_data_is_not_zero_support() -> None:
    facts = _facts()
    empty = CompetingTheoryFacts(
        run_token=facts.run_token,
        owner_tokens=facts.owner_tokens,
        claims=facts.claims,
        stances=(),
        citations=(),
        receipts=(),
        forecasts=(),
        owner_last_ticks=facts.owner_last_ticks,
    )
    analysis = harvest_competing_theories_analysis(empty)
    assert analysis.support_edge_count == 0
    assert analysis.community_count == 0
    assert analysis.prediction_count == 0


def test_popular_inaccurate_account_and_accurate_minority_coexist() -> None:
    facts = CompetingTheoryFacts(
        run_token="a1",
        owner_tokens=("a2", "a3", "a4", "a5", "b2"),
        claims=(
            TheoryClaimFact("c1", "a2", "d1", "continuity", "spring", 0),
            TheoryClaimFact("c2", "b2", "d1", "recurrence", "summer", 0),
        ),
        stances=(
            TheoryStanceFact("a2", "d1", "c1", 1, "1a"),
            TheoryStanceFact("a3", "d1", "c1", 1, "1b"),
            TheoryStanceFact("a4", "d1", "c1", 1, "1c"),
            TheoryStanceFact("a5", "d1", "c1", 1, "1d"),
            TheoryStanceFact("b2", "d1", "c2", 1, "1e"),
        ),
        citations=(
            TheoryCitationFact(
                "a2", "c1", "supports", "own_observation", "e1", 1, True
            ),
            TheoryCitationFact(
                "a3", "c1", "supports", "own_observation", "e2", 1, True
            ),
            TheoryCitationFact(
                "b2", "c2", "supports", "own_scored_case", "e3", 1, True
            ),
        ),
        receipts=(),
        forecasts=tuple(
            TheoryForecastFact(
                "a2",
                f"case-{index}",
                "d1",
                ("spring", "summer"),
                (("c1", "spring", 1000, 889778), ("c2", "summer", 1000, 221778)),
                1,
                3,
                "scored",
                "summer",
                3,
                vectors=(("c1", (667, 333)), ("c2", (333, 667))),
                hits=(("c1", False), ("c2", True)),
            )
            for index in range(3)
        ),
        owner_last_ticks=(("a2", 4), ("a3", 4), ("a4", 4), ("a5", 4), ("b2", 4)),
    )
    analysis = harvest_competing_theories_analysis(facts)
    assert analysis.support_edge_count == 5
    assert {row.claim_token for row in analysis.communities} == {"c1", "c2"}
    assert analysis.failure_count == 3
    assert analysis.scored_count == 6
    assert analysis.paired_count == 3
    assert analysis.paired_brier_difference == 3 * (221778 - 889778)
    assert not hasattr(analysis, "rank")
    assert not hasattr(analysis, "winner")
    snapshot = compose_competing_theories_snapshot(
        analysis, run_id="run-1", publication_id="pub-1"
    )
    assert snapshot.summary == (
        ("claim_count", 2),
        ("support_edge_count", 5),
        ("community_count", 5),
        ("citation_count", 3),
        ("prediction_count", 6),
        ("failure_count", 3),
        ("teaching_count", 0),
    )


def test_six_metric_families_extend_the_catalog() -> None:
    analysis = harvest_competing_theories_analysis(_facts())
    bundle = assemble_metric_documents(
        MetricComputationInputs(
            run_id="run-1",
            input_revision="rev-1",
            window_end=0,
            competing_theories_analysis=analysis,
        )
    )
    families = [document.metric_family for document in bundle.documents]
    expected = {
        "competing_theory_structure",
        "competing_theory_support_network",
        "competing_theory_citations",
        "competing_theory_predictions",
        "competing_theory_failures",
        "competing_theory_transmission",
    }
    assert expected.issubset(set(families))
    assert METRIC_FAMILY_COUNT == 268
