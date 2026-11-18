"""V4-29 private-physics and owner-input boundaries."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from agents.cognition import Perspective
from simulation.serialization import required_domain_schema
from world.actions import CalibrateInstrument, Measure
from world.identifiers import EntityId
from world.measurement import MeasurementQuantity

pytestmark = pytest.mark.architecture

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"

_PRIVATE_IMPORTS = (
    "world._measurement",
    "world._state",
    "world._operations",
    "world._rules",
    "world._replay",
)
_FORBIDDEN_OBJECTIVE_NAMES = (
    "InstrumentState",
    "MeasurementReference",
    "MeasurementRuleContext",
    "MeasurementTaken",
    "InstrumentCalibrated",
    "sample_measurement_target",
    "resolve_measurement",
    "resolve_instrument_calibration",
)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            names.add(node.module)
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return names


@pytest.mark.parametrize(
    "path",
    sorted((SRC / "agents" / "cognition").glob("measurement*.py")),
)
def test_cognition_measurement_modules_never_import_private_physics(
    path: Path,
) -> None:
    names = _imports(path)
    for private in _PRIVATE_IMPORTS:
        assert private not in names
    for forbidden in _FORBIDDEN_OBJECTIVE_NAMES:
        assert not any(
            name == forbidden or name.endswith(f".{forbidden}") for name in names
        )


def test_private_measurement_modules_have_no_cognition_or_analysis_importers() -> None:
    for directory in (SRC / "agents", SRC / "analysis", SRC / "api"):
        for path in directory.rglob("*.py"):
            names = _imports(path)
            assert "world._measurement" not in names
            assert "world._ambient" not in names


def test_public_physical_contracts_are_not_perspective_inputs() -> None:
    fields = set(Perspective.__dataclass_fields__)
    assert "instrument_state" not in fields
    assert "measurement_reference" not in fields


def test_measurement_commands_require_envelope_two() -> None:
    measure = Measure(
        EntityId("item-instrument"),
        EntityId("loc-1"),
        MeasurementQuantity.AMBIENT_TEMPERATURE,
    )
    calibrate = CalibrateInstrument(
        EntityId("item-instrument"), EntityId("item-reference")
    )
    assert required_domain_schema(measure) == 2
    assert required_domain_schema(calibrate) == 2
