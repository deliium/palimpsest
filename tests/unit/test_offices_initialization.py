"""Explicit office newborn profile enables empty office cognition only."""

from __future__ import annotations

from agents.cognition.configuration import (
    CognitionInstitutionConceptMode,
    CognitionOfficeSuccessionMode,
)
from agents.models import AgentId
from simulation.new_agent_initialization import (
    SPECIES_DEFAULT_DEVELOPMENTAL_V1,
    SPECIES_DEFAULT_OFFICES_V1,
    SPECIES_DEFAULT_V1,
    BlankSlateStoreCounts,
    assert_blank_slate_subjective_state,
    species_defaults_for,
)
from simulation.runner import _cognition_config_for
from simulation.runner_models import (
    AgentRunnerSpec,
    MortalityMode,
    V2CapabilityFlags,
)
from world.identifiers import EntityId


def test_offices_profile_enables_only_office_capability() -> None:
    pack = species_defaults_for(SPECIES_DEFAULT_OFFICES_V1, agent_id=AgentId("new"))
    assert pack.cognition.office_succession_mode.value == "deterministic"
    assert pack.cognition.institution_concept_mode.value == "disabled"
    spec = AgentRunnerSpec(
        agent_id=AgentId("new"),
        entity_id=EntityId("body-new"),
        cognition=pack.cognition,
        name="new",
        initial_goals=(),
    )
    cognition = _cognition_config_for(
        spec.cognition,
        mortality_mode=MortalityMode.DISABLED,
        capability_flags=V2CapabilityFlags(),
    )
    assert (
        cognition.office_succession_mode is CognitionOfficeSuccessionMode.DETERMINISTIC
    )
    assert cognition.office_concept_policy is not None
    assert (
        cognition.institution_concept_mode is CognitionInstitutionConceptMode.DISABLED
    )


def test_existing_species_profiles_remain_office_disabled() -> None:
    for profile in (SPECIES_DEFAULT_V1, SPECIES_DEFAULT_DEVELOPMENTAL_V1):
        pack = species_defaults_for(profile, agent_id=AgentId("new"))
        assert pack.cognition.office_succession_mode.value == "disabled"


def test_blank_slate_requires_empty_office_content() -> None:
    assert_blank_slate_subjective_state(AgentId("new"), BlankSlateStoreCounts())
    try:
        assert_blank_slate_subjective_state(
            AgentId("new"), BlankSlateStoreCounts(office_concepts=1)
        )
    except ValueError as exc:
        assert "office_concepts" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("office content must fail blank-slate")
