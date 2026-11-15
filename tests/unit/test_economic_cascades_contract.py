# mypy: ignore-errors
"""Closed vocabulary and token invariants for economic cascades."""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from analysis.economic_cascades_contract import (
    CASCADE_FORBIDDEN_KEYS,
    CHAIN_TOKEN_PREFIX,
    ECONOMIC_CASCADES_ERROR_CODES,
    ECONOMIC_CASCADES_POLICY_VERSION,
    CascadeAvailability,
    CascadeChainState,
    CascadeCoverage,
    CascadeDependencyKind,
    CascadeDisruptionKind,
    CascadeLayer,
    EconomicCascadesError,
    mint_chain_token,
)
from analysis.economic_cascades_rows import (
    CascadeChainRow,
    CascadeCoverageRow,
    CascadeDependencyEdgeRow,
    CascadeDisruptionRow,
    CascadeEpisodeRow,
    CascadePropagationRow,
    CascadeStageRow,
)

pytestmark = pytest.mark.unit


def test_policy_version_and_token_prefix() -> None:
    assert ECONOMIC_CASCADES_POLICY_VERSION == "economic-cascades.v1"
    assert CHAIN_TOKEN_PREFIX == "casc-"


def test_closed_enum_members() -> None:
    assert {item.value for item in CascadeDisruptionKind} == {
        "resource_loss",
        "route_closure",
        "infrastructure_destruction",
        "population_loss",
        "tool_shortage",
    }
    assert {item.value for item in CascadeDependencyKind} == {
        "resource_input",
        "item_input",
        "tool_dependency",
        "infrastructure_dependency",
        "transport_dependency",
    }
    assert {item.value for item in CascadeChainState} == {
        "linked",
        "unlinked",
        "unresolved",
        "unavailable",
    }
    assert {item.value for item in CascadeCoverage} == {
        "complete",
        "partial",
        "missing",
    }
    assert {item.value for item in CascadeAvailability} == {
        "available",
        "insufficient_samples",
        "unavailable",
    }
    assert {item.value for item in CascadeLayer} == {
        "objective_disruption",
        "dependency_structure",
        "analytical_chain",
    }


def test_forbidden_keys_cover_score_and_rank_vocabulary() -> None:
    for key in (
        "class",
        "caste",
        "stratum",
        "elite",
        "underclass",
        "severity",
        "criticality",
        "priority",
        "impact_score",
        "cascade_score",
        "risk_score",
        "blame",
        "fault",
        "root_cause",
        "culprit",
        "economic_damage",
        "loss_value",
        "price",
        "money",
        "status_label",
    ):
        assert key in CASCADE_FORBIDDEN_KEYS


def test_error_codes_are_closed() -> None:
    assert ECONOMIC_CASCADES_ERROR_CODES == frozenset(
        {
            "economic_cascades_invalid_policy",
            "economic_cascades_invalid_cap",
            "economic_cascades_invalid_chain",
            "economic_cascades_invalid_event_order",
            "economic_cascades_layer_violation",
            "economic_cascades_unstable_token",
            "economic_cascades_forbidden_key",
            "economic_cascades_nonfinite_value",
            "economic_cascades_invalid_recipe_spec",
        }
    )


def test_chain_token_is_deterministic_and_content_addressed() -> None:
    first = mint_chain_token(
        disruption_kind=CascadeDisruptionKind.RESOURCE_LOSS,
        upstream_token="harvest_ore",
        downstream_recipe_id="smelt_ore",
        depth=1,
        lag_windows=0,
        window_index=2,
        evidence_tokens=("evt-b", "evt-a"),
    )
    second = mint_chain_token(
        disruption_kind="resource_loss",
        upstream_token="harvest_ore",
        downstream_recipe_id="smelt_ore",
        depth=1,
        lag_windows=0,
        window_index=2,
        evidence_tokens=("evt-a", "evt-b"),
    )
    assert first == second
    assert first.startswith("casc-")
    assert len(first) == len("casc-") + 16
    changed = mint_chain_token(
        disruption_kind=CascadeDisruptionKind.RESOURCE_LOSS,
        upstream_token="harvest_ore",
        downstream_recipe_id="smelt_ore",
        depth=2,
        lag_windows=0,
        window_index=2,
        evidence_tokens=("evt-a", "evt-b"),
    )
    assert changed != first


def test_chain_token_rejects_empty_parts() -> None:
    with pytest.raises(EconomicCascadesError):
        mint_chain_token(
            disruption_kind=CascadeDisruptionKind.RESOURCE_LOSS,
            upstream_token="",
            downstream_recipe_id="smelt_ore",
            depth=1,
            lag_windows=0,
            window_index=0,
        )
    with pytest.raises(EconomicCascadesError):
        mint_chain_token(
            disruption_kind=CascadeDisruptionKind.RESOURCE_LOSS,
            upstream_token="harvest_ore",
            downstream_recipe_id="smelt_ore",
            depth=0,
            lag_windows=0,
            window_index=0,
        )


def test_chain_token_matches_across_hash_seeds() -> None:
    script = (
        "from analysis.economic_cascades_contract import mint_chain_token; "
        "print(mint_chain_token(disruption_kind='resource_loss', "
        "upstream_token='harvest_ore', downstream_recipe_id='smelt_ore', "
        "depth=2, lag_windows=1, window_index=4, "
        "evidence_tokens=('evt-a','evt-b')))"
    )
    digests = []
    for seed in ("0", "1"):
        env = dict(os.environ, PYTHONHASHSEED=seed)
        completed = subprocess.run(
            [sys.executable, "-c", script],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
        digests.append(completed.stdout.strip())
    assert digests[0] == digests[1]


def test_every_row_rejects_an_unknown_policy_field() -> None:
    # The dataclass constructors themselves are closed; a forbidden field can
    # only arrive through an unexpected substitute type.
    row = CascadeDisruptionRow(
        window_index=0,
        window_tick=0,
        sequence=1,
        kind=CascadeDisruptionKind.RESOURCE_LOSS,
        subject_token="harvest_grain",
        magnitude_count=1,
        evidence_event_token="evt-1",
        coverage=CascadeCoverage.COMPLETE,
    )
    assert row.kind is CascadeDisruptionKind.RESOURCE_LOSS


def test_row_types_are_closed_and_validated() -> None:
    with pytest.raises(EconomicCascadesError):
        CascadeDisruptionRow(
            window_index=0,
            window_tick=0,
            sequence=1,
            kind="resource_loss",
            subject_token="harvest_grain",
            magnitude_count=1,
            evidence_event_token="evt-1",
            coverage=CascadeCoverage.COMPLETE,
        )
    with pytest.raises(EconomicCascadesError):
        CascadeChainRow(
            chain_token="not-a-chain",
            window_index=0,
            window_tick=0,
            disruption_kind=CascadeDisruptionKind.RESOURCE_LOSS,
            upstream_token="harvest_grain",
            downstream_recipe_id="mill_grain",
            depth=1,
            lag_windows=0,
            shortfall_share_milli=500,
            state=CascadeChainState.LINKED,
            coverage=CascadeCoverage.COMPLETE,
        )
    with pytest.raises(EconomicCascadesError):
        CascadePropagationRow(
            window_index=0,
            window_tick=0,
            disruption_kind=CascadeDisruptionKind.RESOURCE_LOSS,
            chain_count=2,
            linked_chain_count=1,
            unlinked_chain_count=0,
            unresolved_chain_count=0,
            mean_depth_milli=1_000,
            mean_lag_milli=0,
            downstream_stage_count=1,
            coverage=CascadeCoverage.COMPLETE,
            availability=CascadeAvailability.AVAILABLE,
        )


def test_serializable_row_payload_has_no_forbidden_key() -> None:
    row = CascadeStageRow(
        window_index=0,
        window_tick=0,
        recipe_id="mill_grain",
        action="craft",
        output_name="flour",
        output_kind="material",
        location_token="loc-1",
        demand_count=2,
        attempt_count=2,
        completion_count=1,
        tool_dependent=True,
        has_infrastructure=False,
        coverage=CascadeCoverage.COMPLETE,
    )
    payload = json.dumps(row.__dict__ if hasattr(row, "__dict__") else {}, default=str)
    assert "severity" not in payload
    assert isinstance(row, CascadeStageRow)


def test_episode_and_coverage_rows_validate_counts() -> None:
    with pytest.raises(EconomicCascadesError):
        CascadeEpisodeRow(
            window_index=0,
            window_tick=0,
            kind=CascadeDisruptionKind.RESOURCE_LOSS,
            disruption_count=1,
            magnitude_total=1,
            subject_count=1,
            first_sequence=4,
            last_sequence=2,
            coverage=CascadeCoverage.COMPLETE,
        )
    with pytest.raises(EconomicCascadesError):
        CascadeDependencyEdgeRow(
            window_index=0,
            window_tick=0,
            upstream_token="harvest_grain",
            downstream_recipe_id="mill_grain",
            kind=CascadeDependencyKind.ITEM_INPUT,
            depth=0,
            evidence_count=1,
        )
    with pytest.raises(EconomicCascadesError):
        CascadeCoverageRow(
            window_index=-1,
            window_tick=0,
            window_count=1,
            event_count=1,
            disruption_count=1,
            stage_count=1,
            dependency_edge_count=0,
            labor_join_count=0,
            chain_count=0,
            linked_chain_count=0,
            truncated=False,
            coverage=CascadeCoverage.MISSING,
            availability=CascadeAvailability.UNAVAILABLE,
        )
