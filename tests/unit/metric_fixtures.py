"""Known-answer and degenerate fixtures for V1 metric specifications.

Structured expected values for Tasks 11-15. Does not run full simulations.
Fixtures may import reference-scenario helpers; analysis code must not.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from analysis.models import MetricAvailability
from analysis.numerical import quantize_float
from analysis.specifications import (
    MetricFamilyId,
    action_resolution_rate_spec,
    all_metric_specifications,
    metric_specification,
)
from tests.reference_scenario_helpers import (
    REFERENCE_AGENT_IDS,
    make_reference_bundle,
)

__all__ = [
    "FixtureKind",
    "KnownAnswerFixture",
    "all_known_answer_fixtures",
    "degenerate_fixtures",
    "reference_derived_fixtures",
]


class FixtureKind(StrEnum):
    """Origin of a known-answer case."""

    REFERENCE_DERIVED = "reference_derived"
    DEGENERATE = "degenerate"


@dataclass(frozen=True, slots=True)
class KnownAnswerFixture:
    """Small structured expected outputs for one metric family formula set."""

    fixture_id: str
    family_id: MetricFamilyId
    algorithm_version: str
    kind: FixtureKind
    availability: MetricAvailability
    expected_values: Mapping[str, object]
    notes_code: str
    input_summary_code: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "expected_values", MappingProxyType(dict(self.expected_values))
        )

    @property
    def version_identifier(self) -> str:
        return f"{self.family_id.value}@{self.algorithm_version}"

    def __repr__(self) -> str:
        return (
            f"KnownAnswerFixture(fixture_id={self.fixture_id!r}, "
            f"family_id={self.family_id.value!r}, kind={self.kind.value!r}, "
            f"availability={self.availability.value!r})"
        )


def _q(value: float) -> float:
    return quantize_float(value)


def reference_derived_fixtures() -> tuple[KnownAnswerFixture, ...]:
    """Fixtures whose populations mirror Task 9 reference scenario shape."""
    bundle = make_reference_bundle()
    n_agents = len(REFERENCE_AGENT_IDS)
    death_tick = bundle.death_tick
    max_ticks = bundle.config.stop_policy.max_ticks
    # One early death among five -> survival at T = 4/5.
    survival_rate = _q(float(n_agents - 1) / float(n_agents))

    ri = metric_specification(MetricFamilyId.RESOURCE_INEQUALITY)
    # Toy inventory counts derived from scenario roles: one food holder vs zeros.
    # Sorted [0,0,0,0,1] -> gini = (2*(0+0+0+0+5)-(6)*1)/(5*1)= (10-6)/5=0.8
    gini_five = _q(0.8)

    return (
        KnownAnswerFixture(
            fixture_id="ref-resource-inequality-inventory-skew",
            family_id=MetricFamilyId.RESOURCE_INEQUALITY,
            algorithm_version=ri.algorithm_version,
            kind=FixtureKind.REFERENCE_DERIVED,
            availability=MetricAvailability.PRESENT,
            expected_values={
                "gini": gini_five,
                # [0,0,0,0,1]: mu=0.2; T=(1/5)*5*ln(5)=ln(5)
                "theil_t": _q(math.log(5.0)),
                "atkinson_eps_1": 1.0,
                "share_top_1": 1.0,
                "population_size": n_agents,
                "measure_id": "inventory_count",
            },
            notes_code="reference_one_item_holder",
            input_summary_code="inventory_counts_four_zero_one_one",
        ),
        KnownAnswerFixture(
            fixture_id="ref-survival-early-death",
            family_id=MetricFamilyId.SURVIVAL,
            algorithm_version=metric_specification(
                MetricFamilyId.SURVIVAL
            ).algorithm_version,
            kind=FixtureKind.REFERENCE_DERIVED,
            availability=MetricAvailability.PRESENT,
            expected_values={
                "survival_rate_at_T": survival_rate,
                "deaths": 1,
                "censored_alive": n_agents - 1,
                "median_survival_tick": None,
                "population_size": n_agents,
                "death_tick": death_tick,
                "max_ticks": max_ticks,
            },
            notes_code="reference_single_early_death",
            input_summary_code="five_agents_one_death_before_midpoint",
        ),
        KnownAnswerFixture(
            fixture_id="ref-conflict-lethal-attack-present",
            family_id=MetricFamilyId.CONFLICT,
            algorithm_version=metric_specification(
                MetricFamilyId.CONFLICT
            ).algorithm_version,
            kind=FixtureKind.REFERENCE_DERIVED,
            availability=MetricAvailability.PARTIAL,
            expected_values={
                "conflict_event_count_min": 1,
                "attack_occurrence_rate_gt": 0.0,
            },
            notes_code="reference_milestone_lethal_attack",
            input_summary_code="at_least_one_applied_attack_event",
        ),
        KnownAnswerFixture(
            fixture_id="ref-knowledge-diffusion-tell-observe",
            family_id=MetricFamilyId.KNOWLEDGE_DIFFUSION,
            algorithm_version=metric_specification(
                MetricFamilyId.KNOWLEDGE_DIFFUSION
            ).algorithm_version,
            kind=FixtureKind.REFERENCE_DERIVED,
            availability=MetricAvailability.PARTIAL,
            expected_values={
                "root_count_min": 1,
                "reach_world_delivery_gt": 0.0,
            },
            notes_code="reference_tell_milestone",
            input_summary_code="structured_tell_delivery_exists",
        ),
    )


def degenerate_fixtures() -> tuple[KnownAnswerFixture, ...]:
    """Empty / one / all-zero / unknown edge cases for formula policy."""
    ri = metric_specification(MetricFamilyId.RESOURCE_INEQUALITY)
    coop = metric_specification(MetricFamilyId.COOPERATION)
    spec_behav = metric_specification(MetricFamilyId.BEHAVIORAL_SPECIALIZATION)
    belief = metric_specification(MetricFamilyId.BELIEF_ACCURACY)
    trust = metric_specification(MetricFamilyId.TRUST_NETWORK_STRUCTURE)
    community = metric_specification(MetricFamilyId.GROUP_COMMUNITY_STRUCTURE)
    shared = action_resolution_rate_spec()

    return (
        KnownAnswerFixture(
            fixture_id="deg-resource-empty-population",
            family_id=MetricFamilyId.RESOURCE_INEQUALITY,
            algorithm_version=ri.algorithm_version,
            kind=FixtureKind.DEGENERATE,
            availability=MetricAvailability.UNKNOWN,
            expected_values={},
            notes_code="empty_population",
            input_summary_code="n_eq_0",
        ),
        KnownAnswerFixture(
            fixture_id="deg-resource-one-agent",
            family_id=MetricFamilyId.RESOURCE_INEQUALITY,
            algorithm_version=ri.algorithm_version,
            kind=FixtureKind.DEGENERATE,
            availability=MetricAvailability.PRESENT,
            expected_values={
                "gini": 0.0,
                "theil_t": 0.0,
                "atkinson_eps_1": 0.0,
                "share_top_1": 1.0,
                "population_size": 1,
                "measure_id": "inventory_count",
            },
            notes_code="singleton_population",
            input_summary_code="n_eq_1_value_any",
        ),
        KnownAnswerFixture(
            fixture_id="deg-resource-all-zero",
            family_id=MetricFamilyId.RESOURCE_INEQUALITY,
            algorithm_version=ri.algorithm_version,
            kind=FixtureKind.DEGENERATE,
            availability=MetricAvailability.PRESENT,
            expected_values={
                "gini": 0.0,
                "theil_t": 0.0,
                "share_top_1": 0.0,
                "population_size": 3,
                "measure_id": "inventory_count",
            },
            notes_code="all_zero_holdings",
            input_summary_code="values_0_0_0",
        ),
        KnownAnswerFixture(
            fixture_id="deg-resource-two-agent-gini",
            family_id=MetricFamilyId.RESOURCE_INEQUALITY,
            algorithm_version=ri.algorithm_version,
            kind=FixtureKind.DEGENERATE,
            availability=MetricAvailability.PRESENT,
            expected_values={
                "gini": _q(0.5),
                "share_top_1": 1.0,
                "population_size": 2,
                "measure_id": "inventory_count",
            },
            notes_code="two_agent_0_and_10",
            input_summary_code="values_0_10",
        ),
        KnownAnswerFixture(
            fixture_id="deg-cooperation-no-events",
            family_id=MetricFamilyId.COOPERATION,
            algorithm_version=coop.algorithm_version,
            kind=FixtureKind.DEGENERATE,
            availability=MetricAvailability.UNKNOWN,
            expected_values={},
            notes_code="zero_applied_events",
            input_summary_code="no_action_events",
        ),
        KnownAnswerFixture(
            fixture_id="deg-specialization-one-agent",
            family_id=MetricFamilyId.BEHAVIORAL_SPECIALIZATION,
            algorithm_version=spec_behav.algorithm_version,
            kind=FixtureKind.DEGENERATE,
            availability=MetricAvailability.PARTIAL,
            expected_values={
                "mean_normalized_entropy": 0.0,
                "mean_js_divergence": None,
                "agents_scored": 1,
            },
            notes_code="singleton_js_unknown",
            input_summary_code="one_agent_uniform_or_single_kind",
        ),
        KnownAnswerFixture(
            fixture_id="deg-belief-accuracy-no-truth-specs",
            family_id=MetricFamilyId.BELIEF_ACCURACY,
            algorithm_version=belief.algorithm_version,
            kind=FixtureKind.DEGENERATE,
            availability=MetricAvailability.ABSENT,
            expected_values={
                "evaluable_count": 0,
                "unknown_excluded_count": 0,
            },
            notes_code="no_claim_truth_spec",
            input_summary_code="empty_truth_catalog",
        ),
        KnownAnswerFixture(
            fixture_id="deg-trust-single-node",
            family_id=MetricFamilyId.TRUST_NETWORK_STRUCTURE,
            algorithm_version=trust.algorithm_version,
            kind=FixtureKind.DEGENERATE,
            availability=MetricAvailability.PARTIAL,
            expected_values={
                "density": None,
                "weak_components": 1,
                "node_count": 1,
                "edge_count": 0,
                "mean_in_degree_weight": 0.0,
                "mean_out_degree_weight": 0.0,
            },
            notes_code="singleton_graph",
            input_summary_code="n_eq_1_no_edges",
        ),
        KnownAnswerFixture(
            fixture_id="deg-community-no-edges",
            family_id=MetricFamilyId.GROUP_COMMUNITY_STRUCTURE,
            algorithm_version=community.algorithm_version,
            kind=FixtureKind.DEGENERATE,
            availability=MetricAvailability.PRESENT,
            expected_values={
                "community_count": 3,
                "modularity": 0.0,
                "largest_community_share": _q(1.0 / 3.0),
                "node_count": 3,
            },
            notes_code="three_isolates",
            input_summary_code="n_eq_3_zero_edges",
        ),
        KnownAnswerFixture(
            fixture_id="deg-action-resolution-empty",
            family_id=MetricFamilyId.COOPERATION,
            algorithm_version=shared.algorithm_version,
            kind=FixtureKind.DEGENERATE,
            availability=MetricAvailability.ABSENT,
            expected_values={},
            notes_code="shared_action_resolution_empty",
            input_summary_code="no_action_resolution_rows",
        ),
        KnownAnswerFixture(
            fixture_id="deg-action-resolution-partition",
            family_id=MetricFamilyId.CONFLICT,
            algorithm_version=shared.algorithm_version,
            kind=FixtureKind.DEGENERATE,
            availability=MetricAvailability.PRESENT,
            expected_values={
                "attempt_count": 4,
                "applied_rate": _q(0.5),
                "rejected_rate": _q(0.25),
                "conflicted_rate": _q(0.25),
            },
            notes_code="shared_action_resolution_2_1_1",
            input_summary_code="two_applied_one_rejected_one_conflicted",
        ),
        KnownAnswerFixture(
            fixture_id="deg-memory-drift-no-chains",
            family_id=MetricFamilyId.MEMORY_DRIFT,
            algorithm_version=metric_specification(
                MetricFamilyId.MEMORY_DRIFT
            ).algorithm_version,
            kind=FixtureKind.DEGENERATE,
            availability=MetricAvailability.ABSENT,
            expected_values={
                "chain_count": 0,
            },
            notes_code="no_reconstruction_chains",
            input_summary_code="empty_owner_memory",
        ),
        KnownAnswerFixture(
            fixture_id="deg-false-belief-no-onsets",
            family_id=MetricFamilyId.FALSE_BELIEF_PERSISTENCE,
            algorithm_version=metric_specification(
                MetricFamilyId.FALSE_BELIEF_PERSISTENCE
            ).algorithm_version,
            kind=FixtureKind.DEGENERATE,
            availability=MetricAvailability.ABSENT,
            expected_values={
                "onset_count": 0,
            },
            notes_code="no_false_onsets",
            input_summary_code="empty_false_belief_set",
        ),
        KnownAnswerFixture(
            fixture_id="deg-motifs-no-tokens",
            family_id=MetricFamilyId.REPEATED_CONVENTIONS,
            algorithm_version=metric_specification(
                MetricFamilyId.REPEATED_CONVENTIONS
            ).algorithm_version,
            kind=FixtureKind.DEGENERATE,
            availability=MetricAvailability.UNKNOWN,
            expected_values={},
            notes_code="empty_token_stream",
            input_summary_code="no_applied_actions",
        ),
        KnownAnswerFixture(
            fixture_id="deg-rumor-no-hops",
            family_id=MetricFamilyId.RUMOR_DISTORTION,
            algorithm_version=metric_specification(
                MetricFamilyId.RUMOR_DISTORTION
            ).algorithm_version,
            kind=FixtureKind.DEGENERATE,
            availability=MetricAvailability.ABSENT,
            expected_values={
                "distortion_edge_count": 0,
            },
            notes_code="no_multi_hop_pairs",
            input_summary_code="single_hop_or_empty",
        ),
        KnownAnswerFixture(
            fixture_id="deg-goal-completion-empty",
            family_id=MetricFamilyId.GOAL_COMPLETION,
            algorithm_version=metric_specification(
                MetricFamilyId.GOAL_COMPLETION
            ).algorithm_version,
            kind=FixtureKind.DEGENERATE,
            availability=MetricAvailability.ABSENT,
            expected_values={
                "goals_total": 0,
            },
            notes_code="no_goal_receipts",
            input_summary_code="empty_goal_transitions",
        ),
        KnownAnswerFixture(
            fixture_id="deg-relationship-stability-empty",
            family_id=MetricFamilyId.RELATIONSHIP_STABILITY,
            algorithm_version=metric_specification(
                MetricFamilyId.RELATIONSHIP_STABILITY
            ).algorithm_version,
            kind=FixtureKind.DEGENERATE,
            availability=MetricAvailability.ABSENT,
            expected_values={
                "active_edge_count": 0,
                "retired_edge_count": 0,
            },
            notes_code="no_relationship_revisions",
            input_summary_code="empty_relationship_store",
        ),
    )


def all_known_answer_fixtures() -> tuple[KnownAnswerFixture, ...]:
    """Union of reference-derived and degenerate fixtures."""
    return reference_derived_fixtures() + degenerate_fixtures()


# Smoke: catalog size used by tests without importing builders twice.
EXPECTED_FAMILY_COUNT: Final[int] = len(all_metric_specifications())
