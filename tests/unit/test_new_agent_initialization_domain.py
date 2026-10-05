"""Unit tests for NewAgentInitialization domain types."""

from __future__ import annotations

import logging

import pytest

from agents.models import AgentId, DriveKind
from simulation.new_agent_initialization import (
    ALLOWED_OBJECTIVE_INHERITANCE_KEYS,
    CreationProvenance,
    CreationReasonCode,
    DependencyBindingPolicy,
    InnateDrivePolicy,
    NewAgentInitializationSpec,
    ObjectiveInheritancePolicy,
    OriginRef,
    ParameterDistributionSpec,
    PhysicalConditionPolicy,
    ProvenancePolicy,
    SpawnLocationPolicy,
    creation_config_fingerprint,
    default_new_agent_initialization_spec,
)

_LOG = logging.getLogger("tests.new_agent_initialization_domain")


def _spec(**overrides: object) -> NewAgentInitializationSpec:
    base = default_new_agent_initialization_spec()
    fields = {
        "species_defaults_id": base.species_defaults_id,
        "parameter_distributions": base.parameter_distributions,
        "innate_drive_policy": base.innate_drive_policy,
        "physical_condition_policy": base.physical_condition_policy,
        "spawn_location_policy": base.spawn_location_policy,
        "dependency_binding": base.dependency_binding,
        "objective_inheritance": base.objective_inheritance,
        "creation_reason_policy": base.creation_reason_policy,
        "provenance_policy": base.provenance_policy,
    }
    fields.update(overrides)
    return NewAgentInitializationSpec(**fields)  # type: ignore[arg-type]


def test_default_spec_construction_and_fingerprint() -> None:
    _LOG.debug("case_id=default_spec_construction_and_fingerprint")
    spec = default_new_agent_initialization_spec()
    assert spec.species_defaults_id == "species_default_v1"
    assert spec.parameter_distributions.distribution_id == "none"
    assert spec.objective_inheritance.allowed_keys == ()
    payload = spec.canonical_payload()
    assert set(payload.keys()) == {
        "species_defaults_id",
        "parameter_distributions",
        "innate_drive_policy",
        "physical_condition_policy",
        "spawn_location_policy",
        "dependency_binding",
        "objective_inheritance",
        "creation_reason_policy",
        "provenance_policy",
    }
    fp = creation_config_fingerprint(spec)
    assert fp.startswith("nai-")
    assert creation_config_fingerprint(spec) == fp
    assert (
        creation_config_fingerprint(spec, demographic_policy_id="fixed_interval_entry")
        != fp
    )


def test_origin_ref_rejects_kinship_roles() -> None:
    _LOG.debug("case_id=origin_ref_rejects_kinship_roles")
    with pytest.raises(ValueError, match="origin_ref_kinship_forbidden"):
        OriginRef(role="parent", agent_id="agent-1")
    ref = OriginRef(role="experimental_source", agent_id="agent-1")
    assert ref.canonical_payload() == {
        "role": "experimental_source",
        "agent_id": "agent-1",
    }
    provenance = CreationProvenance(
        creation_reason=CreationReasonCode.DEMOGRAPHIC_POLICY,
        origin_refs=(ref,),
    )
    assert provenance.creation_reason is CreationReasonCode.DEMOGRAPHIC_POLICY


def test_objective_inheritance_rejects_forbidden_keys() -> None:
    _LOG.debug("case_id=objective_inheritance_rejects_forbidden_keys")
    with pytest.raises(ValueError, match="subjective_copy_forbidden"):
        ObjectiveInheritancePolicy(allowed_keys=("episodic_memory",))
    with pytest.raises(ValueError, match="objective_inheritance_key_forbidden"):
        ObjectiveInheritancePolicy(allowed_keys=("health",))
    ok = ObjectiveInheritancePolicy(allowed_keys=("carry_capacity",))
    assert ok.allowed_keys == ("carry_capacity",)
    assert "carry_capacity" in ALLOWED_OBJECTIVE_INHERITANCE_KEYS


def test_parameter_distribution_exact_keys() -> None:
    _LOG.debug("case_id=parameter_distribution_exact_keys")
    with pytest.raises(ValueError, match="parameter_distribution_params_key_set"):
        ParameterDistributionSpec(distribution_id="none", params={"extra": 1})
    with pytest.raises(ValueError, match="unknown_parameter_distribution_id"):
        ParameterDistributionSpec(distribution_id="gaussian", params={})
    with pytest.raises(ValueError, match="parameter_distribution_params_key_set"):
        ParameterDistributionSpec(
            distribution_id="uniform_drive_delta",
            params={"drive_kind": DriveKind.CURIOSITY.value},
        )
    dist = ParameterDistributionSpec(
        distribution_id="uniform_drive_delta",
        params={
            "drive_kind": DriveKind.CURIOSITY.value,
            "min_delta": 0.0,
            "max_delta": 0.2,
        },
    )
    assert dist.params["drive_kind"] == "curiosity"


def test_unknown_species_defaults_rejected() -> None:
    _LOG.debug("case_id=unknown_species_defaults_rejected")
    with pytest.raises(ValueError, match="unknown_species_defaults_id"):
        _spec(species_defaults_id="species_default_v99")


def test_spawn_and_dependency_policies() -> None:
    _LOG.debug("case_id=spawn_and_dependency_policies")
    defer = SpawnLocationPolicy(policy_id="defer_to_candidate")
    assert defer.allowlist_ids() is None
    fixed = SpawnLocationPolicy(
        policy_id="fixed", params={"location_id": "loc-1"}
    )
    assert fixed.allowlist_ids() == frozenset({"loc-1"})
    with pytest.raises(ValueError, match="unknown_dependency_binding_id"):
        DependencyBindingPolicy(policy_id="copy_from_parent")
    assert DependencyBindingPolicy().policy_id == "from_lifecycle_stage"
    _ = InnateDrivePolicy(policy_id="species_baseline")
    _ = PhysicalConditionPolicy(policy_id="default_entrant")
    _ = ProvenancePolicy(record_origin_refs=False, allowed_roles=())
    with pytest.raises(ValueError, match="origin_ref_kinship_forbidden"):
        ProvenancePolicy(record_origin_refs=True, allowed_roles=("parent",))
