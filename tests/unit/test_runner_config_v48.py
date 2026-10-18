"""runner-config-v48 gates the run-level generational narrative channel."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from experiments.matrix_schema import finalize_matrix_cell_config
from experiments.regional_migration_scenario import regional_migration_scenario
from simulation.new_agent_initialization import (
    default_new_agent_initialization_spec,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V47,
    RUNNER_SCHEMA_VERSION_V48,
    SUPPORTED_RUNNER_SCHEMA_VERSIONS,
    CulturalNarrativeMode,
    GenerationalNarrativesSpec,
    V3CapabilityFlags,
    example_cultural_feature_provenance_spec,
    example_population_lifecycle_spec,
)
from simulation.runner_serialization import (
    decode_runner_config,
    encode_runner_config,
)

_OFF_ARM = regional_migration_scenario().conditions[0].runner_config


def _agents(config, *, narrative: bool = True):
    return tuple(
        replace(
            agent,
            cognition=replace(
                agent.cognition,
                cultural_narrative_mode=(
                    CulturalNarrativeMode.DETERMINISTIC
                    if narrative
                    else CulturalNarrativeMode.DISABLED
                ),
            ),
        )
        for agent in config.agents
    )


def _v48(**overrides: object):
    values: dict[str, object] = {
        "schema_version": RUNNER_SCHEMA_VERSION_V48,
        "agents": _agents(_OFF_ARM),
        "v3_capability_flags": V3CapabilityFlags(
            generational_population=True,
            cultural_historical_memory=True,
        ),
        "population_lifecycle": example_population_lifecycle_spec(),
        "new_agent_initialization": default_new_agent_initialization_spec(),
        "cultural_feature_provenance": (
            example_cultural_feature_provenance_spec()
        ),
        "generational_narratives": GenerationalNarrativesSpec(),
    }
    values.update(overrides)
    return replace(_OFF_ARM, **values)  # type: ignore[arg-type]


def test_v48_is_supported_and_round_trips() -> None:
    assert RUNNER_SCHEMA_VERSION_V48 in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    config = _v48()
    document = json.loads(encode_runner_config(config))
    assert document["schema_version"] == RUNNER_SCHEMA_VERSION_V48
    assert document["generational_narratives"] == {
        "generational_narratives_mode": "deterministic",
        "source_loss_policy": "observed_evidence_only",
        "theme_policy": "observed_kind_and_lineage",
        "max_witnesses": 8,
        "max_records": 8,
        "max_transitions": 16,
        "max_declared_chain": 8,
    }
    decoded = decode_runner_config(encode_runner_config(config))
    assert decoded.schema_version == RUNNER_SCHEMA_VERSION_V48
    assert decoded.generational_narratives == GenerationalNarrativesSpec()


def test_v48_requires_generational_narratives() -> None:
    with pytest.raises(ValueError, match="v48_requires_generational_narratives"):
        _v48(generational_narratives=None)


def test_generational_narratives_requires_v48() -> None:
    with pytest.raises(ValueError, match="generational_narratives_requires_v48"):
        _v48(schema_version=RUNNER_SCHEMA_VERSION_V47)


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        (
            {"population_lifecycle": None},
            "generational_narratives_requires_lifecycle",
        ),
        (
            {"cultural_feature_provenance": None},
            "generational_narratives_requires_cultural_provenance",
        ),
        (
            {
                "v3_capability_flags": V3CapabilityFlags(
                    cultural_historical_memory=True
                )
            },
            "generational_narratives_requires_flag",
        ),
        (
            {"agents": _agents(_OFF_ARM, narrative=False)},
            "generational_narratives_requires_narrative_mode",
        ),
    ],
)
def test_v48_fails_closed_without_prerequisites(
    overrides: dict[str, object], code: str
) -> None:
    with pytest.raises(ValueError, match=code):
        _v48(**overrides)


def test_generational_spec_rejects_invalid_caps_and_modes() -> None:
    with pytest.raises(ValueError):
        GenerationalNarrativesSpec(max_witnesses=0)
    with pytest.raises(ValueError):
        GenerationalNarrativesSpec(max_records=9)
    with pytest.raises(ValueError):
        GenerationalNarrativesSpec(max_transitions=17)
    with pytest.raises(ValueError):
        GenerationalNarrativesSpec(generational_narratives_mode="disabled")
    with pytest.raises(ValueError):
        GenerationalNarrativesSpec(source_loss_policy="objective")
    with pytest.raises(ValueError):
        GenerationalNarrativesSpec(theme_policy="freeform")


def test_v48_does_not_imply_optional_siblings() -> None:
    config = _v48()
    document = json.loads(encode_runner_config(config))
    for sibling in (
        "durable_records",
        "knowledge_repositories",
        "historical_memory_layers",
        "cultural_contact",
    ):
        assert sibling not in document


def test_lifecycle_and_cultural_without_spec_does_not_emit_v48() -> None:
    from experiments.matrix_factors import clone_runner_config

    config = clone_runner_config(
        _v48(), schema_version=RUNNER_SCHEMA_VERSION_V4
    )
    config = clone_runner_config(
        config, generational_narratives=None
    )
    finalized = finalize_matrix_cell_config(config)
    assert finalized.schema_version != RUNNER_SCHEMA_VERSION_V48
    decoded = decode_runner_config(encode_runner_config(finalized))
    assert decoded.schema_version != RUNNER_SCHEMA_VERSION_V48
    assert decoded.generational_narratives is None


def test_matrix_finalize_selects_v48_only_for_generational_narratives() -> None:
    from experiments.matrix_factors import clone_runner_config

    config = clone_runner_config(_v48(), schema_version=RUNNER_SCHEMA_VERSION_V4)
    finalized = finalize_matrix_cell_config(config)
    assert finalized.schema_version == RUNNER_SCHEMA_VERSION_V48
    without = clone_runner_config(
        _v48(), schema_version=RUNNER_SCHEMA_VERSION_V4
    )
    without = clone_runner_config(without, generational_narratives=None)
    assert (
        finalize_matrix_cell_config(without).schema_version
        != RUNNER_SCHEMA_VERSION_V48
    )
