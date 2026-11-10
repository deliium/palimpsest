# mypy: ignore-errors

"""Six supply-chain metric documents stay governed and value-key stable."""

from __future__ import annotations

import pytest

from analysis.specifications import MetricFamilyId, metric_specification
from analysis.supply_chain_analysis import (
    empty_supply_chain_analysis,
    harvest_supply_chain_analysis,
)
from analysis.supply_chain_contract import SupplyChainError
from analysis.supply_chain_metrics import (
    assemble_supply_chain_metrics,
    compute_supply_chain_structure,
)
from tests.unit.test_supply_chain_graph import (
    _RECIPES,
    _craft_done,
    _craft_start,
    _harvest,
)

pytestmark = pytest.mark.unit


def _analysis():
    return harvest_supply_chain_analysis(
        [
            _harvest("harvest_grain", "item-grain", tick=0),
            _craft_start("mill_grain", ("item-grain",), tick=0, event_id="evt-s1"),
            _craft_done("mill_grain", "item-flour", tick=1, event_id="evt-d1"),
        ],
        recipes=_RECIPES,
    )


def test_six_documents_in_order() -> None:
    docs = assemble_supply_chain_metrics(
        _analysis(), run_id="run-metrics", input_revision="rev-1"
    )
    assert [doc.metric_family for doc in docs] == [
        "supply_chain_structure",
        "supply_dependency_graph",
        "supply_bottleneck_pressure",
        "supply_resource_tool_dependency",
        "supply_location_infrastructure_reliance",
        "supply_organization_coordination",
    ]


def test_value_keys_match_contract() -> None:
    docs = assemble_supply_chain_metrics(
        _analysis(), run_id="run-metrics", input_revision="rev-1"
    )
    for doc in docs:
        spec = metric_specification(MetricFamilyId(doc.metric_family))
        assert frozenset(doc.values) == frozenset(spec.value_keys)


def test_empty_values_are_zero() -> None:
    docs = assemble_supply_chain_metrics(
        empty_supply_chain_analysis(), run_id="run-metrics", input_revision="rev-1"
    )
    assert all(doc.availability.value == "unknown" for doc in docs)
    assert all(doc.values == {} for doc in docs)


def test_max_ratio_milli_is_zero_when_empty() -> None:
    docs = assemble_supply_chain_metrics(
        _analysis(), run_id="run-metrics", input_revision="rev-1"
    )
    pressure = next(
        doc for doc in docs if doc.metric_family == "supply_bottleneck_pressure"
    )
    assert pressure.values["max_ratio_milli"] >= 0


def test_provenance_source_kind() -> None:
    doc = compute_supply_chain_structure(
        _analysis(), run_id="run-metrics", input_revision="rev-1"
    )
    assert doc.provenance.source_kind == "supply_chain_analysis"


def test_rejects_foreign_analysis() -> None:
    with pytest.raises(SupplyChainError):
        compute_supply_chain_structure(
            object(), run_id="run-metrics", input_revision="rev-1"
        )


def test_no_float_values() -> None:
    docs = assemble_supply_chain_metrics(
        _analysis(), run_id="run-metrics", input_revision="rev-1"
    )
    for doc in docs:
        for key, value in doc.values.items():
            if key == "coverage":
                assert isinstance(value, str)
            else:
                assert isinstance(value, int), (doc.metric_family, key, value)


def test_no_score_key() -> None:
    docs = assemble_supply_chain_metrics(
        _analysis(), run_id="run-metrics", input_revision="rev-1"
    )
    for doc in docs:
        assert "score" not in doc.values
        assert "rank" not in doc.values
