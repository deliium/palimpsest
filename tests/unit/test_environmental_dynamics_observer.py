"""Observer frames carry current environment tokens and no calendar."""

from __future__ import annotations

import ast
from pathlib import Path

from observer.adapt import adapt_event
from observer.version import OBSERVER_PROTOCOL_VERSION, SEMANTIC_EVENT_TYPES
from simulation.observer_facts import environment_view
from tests.simulation_helpers import make_location, make_weather
from tests.unit.test_environmental_dynamics_events import (
    _environment_details,
    _event,
    _system,
)
from world.effects import SystemEffectFamily
from world.environment import (
    ActiveHazard,
    HazardKind,
    example_environmental_dynamics,
)
from world.events import EVENT_SCHEMA_REPLAY_V7
from world.models import default_physical_rules


def test_semantic_catalog_gains_six_environment_types() -> None:
    assert OBSERVER_PROTOCOL_VERSION == "observer-protocol-v1"
    assert len(SEMANTIC_EVENT_TYPES) == 32
    assert SEMANTIC_EVENT_TYPES[-6:] == (
        "SEASON_CHANGED",
        "TEMPERATURE_BAND_CHANGED",
        "RESOURCE_NODE_DEPLETED",
        "RESOURCE_NODE_RECOVERED",
        "ENVIRONMENTAL_HAZARD_STARTED",
        "ENVIRONMENTAL_HAZARD_ENDED",
    )


def test_adapted_events_publish_tokens_only_when_set() -> None:
    cause = _system(SystemEffectFamily.SEASON, "loc-a")
    for details in _environment_details():
        adapted = adapt_event(
            _event(details, schema_version=EVENT_SCHEMA_REPLAY_V7, cause=cause)
        )
        mapping = adapted.public_mapping()
        assert adapted.type in SEMANTIC_EVENT_TYPES
        assert "pixels" not in mapping
        assert "color" not in mapping
        if adapted.type == "SEASON_CHANGED":
            assert mapping["season"] == "summer"
        else:
            assert "season" not in mapping


def test_absent_spec_omits_environment_tokens() -> None:
    season, bands, hazards = environment_view(
        spec=None,
        tick=6,
        locations=(make_location(),),
        weather=(make_weather(),),
        active_hazards=(),
        rules=default_physical_rules(),
    )
    assert season is None
    assert bands == ()
    assert hazards == ()


def test_present_spec_derives_the_current_band_and_hazard() -> None:
    spec = example_environmental_dynamics()
    hazard = ActiveHazard(
        location_id=make_location().entity_id,
        kind=HazardKind.HEAT,
        start_tick=54,
        duration_ticks=6,
    )
    season, bands, hazards = environment_view(
        spec=spec,
        tick=54,
        locations=(make_location(),),
        weather=(make_weather(),),
        active_hazards=(hazard,),
        rules=default_physical_rules(),
    )
    assert season == "summer"
    assert bands == (("loc-1", "hot"),)
    assert hazards == (("loc-1", "heat", 6),)


def test_observer_package_does_not_import_the_spec() -> None:
    root = Path("src/observer")
    for path in root.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("world.environment")
            if isinstance(node, ast.Import):
                assert all(
                    not alias.name.startswith("world.environment")
                    for alias in node.names
                )
