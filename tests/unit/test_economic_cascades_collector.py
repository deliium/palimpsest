# mypy: ignore-errors
"""Collector gate and injection for economic-cascade analysis."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import experiments.economic_cascades_completed_run as completed_run
from analysis.economic_cascades_analysis import empty_economic_cascades_analysis
from experiments.collectors import assemble_arm_metric_bundle
from tests.unit.test_economic_cascades_analysis import _harvest_events
from world.production import example_production_catalog
from world.supply_chain import supply_chain_production_catalog

pytestmark = pytest.mark.unit

_CASCADE_FAMILIES = {
    "resource_loss_cascade",
    "route_closure_cascade",
    "infrastructure_destruction_cascade",
    "population_loss_cascade",
    "tool_shortage_cascade",
    "cascade_dependency_structure",
    "cascade_propagation",
    "cascade_coverage",
}


def _arm(*, supply_chains: bool):
    config = SimpleNamespace(
        agents=(),
        v4_capability_flags=SimpleNamespace(supply_chains=supply_chains),
        regions_migration=None,
        scenario=None,
    )
    result = SimpleNamespace(
        ticks_committed=0,
        committed_events=[],
        runner_config=config,
    )
    return SimpleNamespace(
        config_fingerprint="fingerprint-1",
        assignment=SimpleNamespace(
            run_id=SimpleNamespace(value="run-1"), runner_config=config
        ),
        runner_result=result,
        committed_events=[],
        macro_society_analysis=None,
    )


def _cascade_families(bundle) -> set[str]:
    return {
        document.metric_family
        for document in bundle.documents
        if document.metric_family in _CASCADE_FAMILIES
    }


def test_gate_off_emits_no_cascade_documents() -> None:
    bundle = assemble_arm_metric_bundle(_arm(supply_chains=False))
    assert _cascade_families(bundle) == set()


def test_gate_on_injects_the_analysis(monkeypatch: pytest.MonkeyPatch) -> None:
    analysis = empty_economic_cascades_analysis()
    monkeypatch.setattr(
        completed_run,
        "build_completed_run_economic_cascades_analysis",
        lambda *args, **kwargs: analysis,
    )
    bundle = assemble_arm_metric_bundle(_arm(supply_chains=True))
    assert _cascade_families(bundle) == _CASCADE_FAMILIES


def test_builder_failure_leaves_the_bundle_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def explode(*args, **kwargs):
        raise ValueError("economic_cascades_invalid_chain")

    monkeypatch.setattr(
        completed_run,
        "build_completed_run_economic_cascades_analysis",
        explode,
    )
    bundle = assemble_arm_metric_bundle(_arm(supply_chains=True))
    assert _cascade_families(bundle) == set()


def test_real_builder_emits_all_cascade_families() -> None:
    catalog = supply_chain_production_catalog(example_production_catalog())
    agent = SimpleNamespace(
        agent_id=SimpleNamespace(value="agent-1"),
        cognition=SimpleNamespace(production_catalog=catalog),
    )
    config = SimpleNamespace(
        agents=(agent,),
        v4_capability_flags=SimpleNamespace(supply_chains=True),
        regions_migration=None,
        scenario=None,
    )
    events = list(_harvest_events())
    result = SimpleNamespace(
        ticks_committed=1,
        committed_events=events,
        runner_config=config,
        final_infrastructure_assets=(),
    )
    arm = SimpleNamespace(
        config_fingerprint="fingerprint-1",
        assignment=SimpleNamespace(
            run_id=SimpleNamespace(value="run-1"), runner_config=config
        ),
        runner_result=result,
        committed_events=events,
        macro_society_analysis=None,
    )
    bundle = assemble_arm_metric_bundle(arm)
    assert _cascade_families(bundle) == _CASCADE_FAMILIES
