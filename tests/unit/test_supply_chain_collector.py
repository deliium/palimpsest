# mypy: ignore-errors

"""Completed-run collector wiring and detached input extraction."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from experiments.supply_chain_completed_run import (
    build_completed_run_supply_chain_analysis,
    supply_chain_infrastructure,
    supply_chain_organization_claims,
    supply_chain_recipe_specs,
    supply_chain_skill_levels,
)
from tests.unit.test_supply_chain_mechanics import _v56_config_with_catalog
from world.production import example_production_catalog
from world.supply_chain import supply_chain_production_catalog

pytestmark = pytest.mark.unit


def _config():
    return _v56_config_with_catalog(
        supply_chain_production_catalog(example_production_catalog())
    )


def test_builder_requires_events() -> None:
    with pytest.raises(ValueError, match="supply_chain_requires_events"):
        build_completed_run_supply_chain_analysis(
            None, committed_events=None, run_id="run-1"
        )


def test_recipe_specs_from_config() -> None:
    specs = supply_chain_recipe_specs(_config())
    assert len(specs) == 12
    assert "harvest_grain" in {spec.recipe_id for spec in specs}


def test_objective_skill_rows_only() -> None:
    class Side:
        def __init__(self, value: str) -> None:
            self.value = value

    result = SimpleNamespace(
        skill_audits=(
            SimpleNamespace(
                side=Side("subjective"),
                agent_id=SimpleNamespace(value="body-1"),
                domain="crafting",
                level=0.9,
            ),
            SimpleNamespace(
                side=Side("objective"),
                agent_id=SimpleNamespace(value="body-1"),
                domain="crafting",
                level=0.4,
            ),
        )
    )
    levels = supply_chain_skill_levels(result)
    assert len(levels) == 1
    assert levels[0].level == 0.4


def test_operational_assets_only() -> None:
    class Status:
        def __init__(self, value: str) -> None:
            self.value = value

    result = SimpleNamespace(
        final_infrastructure_assets=(
            SimpleNamespace(
                status=Status("retired"),
                location_id=SimpleNamespace(value="loc-1"),
                kind=SimpleNamespace(value="well"),
            ),
            SimpleNamespace(
                status=Status("operational"),
                location_id=SimpleNamespace(value="loc-1"),
                kind=SimpleNamespace(value="well"),
            ),
        )
    )
    assert [
        (fact.location_token, fact.kinds)
        for fact in supply_chain_infrastructure(result)
    ] == [("loc-1", ("well",))]


def test_collector_survives_missing_events() -> None:
    assert supply_chain_organization_claims(SimpleNamespace()) == ()


def test_organization_claims_iterate_bundles(monkeypatch) -> None:
    import experiments.supply_chain_completed_run as module

    rows = [
        SimpleNamespace(
            procedures=(
                SimpleNamespace(
                    organization_id="org-1",
                    command_kind="craft",
                    actor_id="body-1",
                    first_tick=1,
                    last_tick=2,
                ),
            )
        ),
        SimpleNamespace(
            procedures=(
                SimpleNamespace(
                    organization_id="org-1",
                    command_kind="harvest",
                    actor_id="body-2",
                    first_tick=3,
                    last_tick=4,
                ),
            )
        ),
    ]
    monkeypatch.setattr(
        module, "harvest_organization_operation_rows", lambda ledgers: rows
    )
    claims = module.supply_chain_organization_claims(SimpleNamespace())
    assert len(claims) == 1
    assert claims[0].organization_token == "org-1"
    assert claims[0].command_kinds == ("craft", "harvest")
    assert claims[0].actor_tokens == ("body-1", "body-2")
    assert claims[0].claim_count == 2


def test_organization_claim_has_no_recipe_or_location() -> None:
    import dataclasses

    from analysis.supply_chain_events import SupplyOrganizationClaim

    names = {field.name for field in dataclasses.fields(SupplyOrganizationClaim)}
    assert "recipe_id" not in names
    assert "location_token" not in names


def test_digest_mismatch_sets_notice(caplog) -> None:
    import logging

    base = _config()
    other = _v56_config_with_catalog(example_production_catalog())
    config = SimpleNamespace(
        agents=(base.agents[0], other.agents[0]),
    )
    with caplog.at_level(logging.WARNING):
        supply_chain_recipe_specs(config)
    assert "supply_chain_recipe_catalog_mismatch" in caplog.text


def test_collector_does_not_read_nonexistent_result_field() -> None:
    import inspect

    import experiments.collectors as collectors

    source = inspect.getsource(collectors)
    assert "supply_chain_analysis=supply_analysis" in source
    assert "runner_result.supply_chain_analysis" not in source


def test_builder_returns_analysis_from_events() -> None:
    from tests.unit.test_supply_chain_graph import _RECIPES, _harvest

    analysis = build_completed_run_supply_chain_analysis(
        None,
        committed_events=(_harvest("harvest_grain", "item-grain"),),
        run_id="run-1",
        recipe_specs=_RECIPES,
    )
    assert analysis.stage_count == 1
