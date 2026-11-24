# mypy: ignore-errors

"""runner-config-v62 commons-governance seam and inherited family preservation."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from simulation.commons_governance_config import (
    COMMONS_GOVERNANCE_POLICY_ID,
    CommonsGovernanceConfigError,
    CommonsGovernanceSpec,
    decode_commons_governance,
    encode_commons_governance,
)
from simulation.compatibility import COMPATIBILITY_MATRIX
from simulation.medical_beliefs_config import MEDICAL_BELIEFS_POLICY_ID
from simulation.overexploitation_config import OVEREXPLOITATION_POLICY_ID
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V61,
    RUNNER_SCHEMA_VERSION_V62,
    SUPPORTED_RUNNER_SCHEMA_VERSIONS,
    InstitutionConceptMode,
    SocialNormMode,
)
from simulation.runner_serialization import (
    RunnerSerializationError,
    decode_runner_config,
    encode_runner_config,
    runner_config_fingerprint,
)
from tests.simulation_helpers import make_resource
from tests.unit.test_disease_config import _as_v58
from tests.unit.test_ecological_resources_config import (
    _as_v60,
    _ecology_base,
    _ecology_spec,
)
from tests.unit.test_medical_beliefs_config import _medical_spec
from tests.unit.test_overexploitation_config import _as_v61, _overexploitation_spec
from world.identifiers import EntityId
from world.values import ResourceKind

pytestmark = pytest.mark.unit

_BASELINE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "runner_configs"
    / "bf_baseline_v4.json"
)


def _commons_spec(*stock_ids: str) -> CommonsGovernanceSpec:
    ids = stock_ids or ("res-water",)
    return CommonsGovernanceSpec(
        policy_id=COMMONS_GOVERNANCE_POLICY_ID,
        stock_ids=tuple(
            EntityId(stock_id)
            for stock_id in sorted(ids)
        ),
    )


def _with_commons_modes(config):
    agents = tuple(
        replace(
            agent,
            cognition=replace(
                agent.cognition,
                social_norm_mode=SocialNormMode.DETERMINISTIC,
                institution_concept_mode=InstitutionConceptMode.DETERMINISTIC,
            ),
        )
        for agent in config.agents
    )
    return replace(
        config,
        agents=agents,
        v4_capability_flags=replace(
            config.v4_capability_flags,
            formal_rules=True,
        ),
    )


def _as_v62(
    config,
    *,
    stock_ids: tuple[str, ...] = ("res-water",),
    with_disease: bool = False,
    with_medical: bool = False,
    with_instruments: bool = False,
):
    v60 = _as_v60(
        config,
        spec=_ecology_spec(*stock_ids),
        with_disease=with_disease or with_medical,
        with_medical=with_medical,
        with_instruments=with_instruments,
    )
    v61 = replace(
        v60,
        schema_version=RUNNER_SCHEMA_VERSION_V61,
        overexploitation=_overexploitation_spec(),
    )
    prepared = _with_commons_modes(v61)
    return replace(
        prepared,
        schema_version=RUNNER_SCHEMA_VERSION_V62,
        commons_governance=_commons_spec(*stock_ids),
    )


def test_v62_is_supported() -> None:
    assert RUNNER_SCHEMA_VERSION_V62 == "runner-config-v62"
    assert RUNNER_SCHEMA_VERSION_V62 in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    entry = COMPATIBILITY_MATRIX["runner_config"]
    assert RUNNER_SCHEMA_VERSION_V62 in entry.bump_trigger
    assert "commons_governance" in entry.bump_trigger


def test_spec_round_trip_and_rejects() -> None:
    spec = _commons_spec("res-water")
    encoded = encode_commons_governance(spec)
    assert encoded == {
        "policy_id": COMMONS_GOVERNANCE_POLICY_ID,
        "stock_ids": ["res-water"],
    }
    assert decode_commons_governance(encoded) == spec
    with pytest.raises(CommonsGovernanceConfigError) as excinfo:
        decode_commons_governance({**encoded, "extra": True})
    assert excinfo.value.code == "commons_governance_spec_invalid"
    with pytest.raises(CommonsGovernanceConfigError) as excinfo:
        decode_commons_governance(
            {"policy_id": "wrong", "stock_ids": ["res-water"]}
        )
    assert excinfo.value.code == "commons_governance_policy_invalid"
    with pytest.raises(CommonsGovernanceConfigError) as excinfo:
        decode_commons_governance(
            {
                "policy_id": COMMONS_GOVERNANCE_POLICY_ID,
                "stock_ids": ["res-b", "res-a"],
            }
        )
    assert excinfo.value.code == "commons_governance_stock_order_invalid"
    with pytest.raises(CommonsGovernanceConfigError) as excinfo:
        decode_commons_governance(
            {
                "policy_id": COMMONS_GOVERNANCE_POLICY_ID,
                "stock_ids": ["res-a", "res-a"],
            }
        )
    assert excinfo.value.code == "commons_governance_stock_duplicate"


def test_bf_baseline_v4_unchanged() -> None:
    payload = _BASELINE.read_bytes()
    decoded = decode_runner_config(payload)
    assert decoded.schema_version == RUNNER_SCHEMA_VERSION_V4
    assert decoded.commons_governance is None
    assert decoded.overexploitation is None
    assert encode_runner_config(decoded) == payload


def test_v61_bytes_and_fingerprint_stable() -> None:
    config = _as_v61(_ecology_base())
    payload = encode_runner_config(config)
    document = json.loads(payload)
    assert document["schema_version"] == RUNNER_SCHEMA_VERSION_V61
    assert "commons_governance" not in document
    assert encode_runner_config(decode_runner_config(payload)) == payload
    fingerprint = runner_config_fingerprint(config)
    assert len(fingerprint) == 64


def test_v62_round_trip_plain() -> None:
    config = _as_v62(_ecology_base())
    payload = encode_runner_config(config)
    document = json.loads(payload)
    assert document["schema_version"] == RUNNER_SCHEMA_VERSION_V62
    assert document["commons_governance"] == {
        "policy_id": COMMONS_GOVERNANCE_POLICY_ID,
        "stock_ids": ["res-water"],
    }
    assert document["overexploitation"] == {
        "policy_id": OVEREXPLOITATION_POLICY_ID
    }
    assert "ecological_resources" in document
    assert "disease_mechanics" not in document
    assert "medical_beliefs" not in document
    decoded = decode_runner_config(payload)
    assert decoded.schema_version == RUNNER_SCHEMA_VERSION_V62
    assert decoded.commons_governance == config.commons_governance
    assert decoded.overexploitation == config.overexploitation
    assert encode_runner_config(decoded) == payload
    assert runner_config_fingerprint(decoded) != runner_config_fingerprint(
        _as_v61(_ecology_base())
    )


def test_v62_with_inherited_channels_round_trip() -> None:
    from tests.unit.test_disease_config import _science_infra_base
    from world.environment import example_environmental_dynamics
    from world.production import example_production_catalog
    from world.supply_chain import supply_chain_production_catalog

    science = _as_v58(_science_infra_base(with_travel=True), with_instruments=True)
    location_id = science.scenario.locations[0].entity_id.value
    water = make_resource(
        "res-water",
        name="Water",
        location_id=location_id,
        quantity=3.0,
        maximum_quantity=3.0,
        regeneration_per_tick=0.5,
        kind=ResourceKind.WATER,
    )
    resources = tuple(
        sorted(
            (*science.scenario.resources, water),
            key=lambda resource: resource.entity_id.value,
        )
    )
    agent = science.agents[0]
    catalog = supply_chain_production_catalog(example_production_catalog())
    config = replace(
        science,
        schema_version=RUNNER_SCHEMA_VERSION_V62,
        scenario=replace(science.scenario, resources=resources),
        environmental_dynamics=example_environmental_dynamics(),
        ecological_resources=_ecology_spec("res-water"),
        overexploitation=_overexploitation_spec(),
        commons_governance=_commons_spec("res-water"),
        medical_beliefs=_medical_spec(),
        agents=(
            replace(
                agent,
                cognition=replace(
                    agent.cognition,
                    production_catalog=catalog,
                    social_norm_mode=SocialNormMode.DETERMINISTIC,
                    institution_concept_mode=InstitutionConceptMode.DETERMINISTIC,
                ),
            ),
        ),
        v4_capability_flags=replace(
            science.v4_capability_flags,
            supply_chains=True,
            ecological_feedback=True,
            epidemics=True,
            infrastructure_networks=True,
            science=True,
            formal_rules=True,
        ),
    )
    assert config.regions_migration is not None
    assert config.measurement_instruments is not None
    assert config.disease_mechanics is not None
    payload = encode_runner_config(config)
    document = json.loads(payload)
    assert "disease_mechanics" in document
    assert "measurement_instruments" in document
    assert document["medical_beliefs"] == {
        "policy_id": MEDICAL_BELIEFS_POLICY_ID
    }
    assert document["commons_governance"]["stock_ids"] == ["res-water"]
    decoded = decode_runner_config(payload)
    assert decoded.disease_mechanics == config.disease_mechanics
    assert decoded.measurement_instruments == config.measurement_instruments
    assert decoded.medical_beliefs == _medical_spec()
    assert decoded.commons_governance == config.commons_governance
    assert encode_runner_config(decoded) == payload


def test_activation_matrix_fails_closed() -> None:
    base = _ecology_base()
    v61_water = replace(
        _as_v61(base),
        ecological_resources=_ecology_spec("res-water"),
    )
    with pytest.raises(ValueError, match="code=commons_governance_spec_required"):
        replace(
            _with_commons_modes(v61_water),
            schema_version=RUNNER_SCHEMA_VERSION_V62,
            commons_governance=None,
        )
    with pytest.raises(ValueError, match="code=commons_governance_schema_mismatch"):
        replace(
            v61_water,
            commons_governance=_commons_spec(),
        )
    with pytest.raises(
        ValueError, match="code=commons_governance_requires_formal_rules"
    ):
        replace(
            v61_water,
            schema_version=RUNNER_SCHEMA_VERSION_V62,
            commons_governance=_commons_spec(),
            agents=tuple(
                replace(
                    agent,
                    cognition=replace(
                        agent.cognition,
                        social_norm_mode=SocialNormMode.DETERMINISTIC,
                        institution_concept_mode=InstitutionConceptMode.DETERMINISTIC,
                    ),
                )
                for agent in v61_water.agents
            ),
            v4_capability_flags=replace(
                v61_water.v4_capability_flags,
                formal_rules=False,
            ),
        )
    with pytest.raises(
        ValueError, match="code=commons_governance_requires_social_norms"
    ):
        replace(
            v61_water,
            schema_version=RUNNER_SCHEMA_VERSION_V62,
            commons_governance=_commons_spec(),
            v4_capability_flags=replace(
                v61_water.v4_capability_flags,
                formal_rules=True,
            ),
            agents=tuple(
                replace(
                    agent,
                    cognition=replace(
                        agent.cognition,
                        social_norm_mode=SocialNormMode.DISABLED,
                        institution_concept_mode=InstitutionConceptMode.DETERMINISTIC,
                    ),
                )
                for agent in v61_water.agents
            ),
        )
    with pytest.raises(
        ValueError, match="code=commons_governance_stock_unmanaged"
    ):
        replace(
            _as_v62(base),
            commons_governance=_commons_spec("res-missing"),
            ecological_resources=_ecology_spec("res-water"),
        )
    food_only = replace(
        base,
        scenario=replace(
            base.scenario,
            resources=(
                make_resource(
                    "res-food",
                    name="Food",
                    location_id="loc-a",
                    quantity=4.0,
                    maximum_quantity=4.0,
                    regeneration_per_tick=1.0,
                    kind=ResourceKind.FOOD,
                ),
            ),
        ),
    )
    v61_food = replace(
        _as_v61(food_only),
        ecological_resources=_ecology_spec("res-food"),
    )
    with pytest.raises(ValueError, match="code=commons_governance_stock_nonwater"):
        replace(
            _with_commons_modes(v61_food),
            schema_version=RUNNER_SCHEMA_VERSION_V62,
            commons_governance=_commons_spec("res-food"),
        )


def test_v61_plus_extra_commons_key_rejected_on_decode() -> None:
    config = _as_v61(_ecology_base())
    document = json.loads(encode_runner_config(config))
    document["commons_governance"] = {
        "policy_id": COMMONS_GOVERNANCE_POLICY_ID,
        "stock_ids": ["res-water"],
    }
    with pytest.raises(RunnerSerializationError):
        decode_runner_config(json.dumps(document, separators=(",", ":")).encode())


def test_v60_plus_extra_commons_key_rejected_on_decode() -> None:
    config = _as_v60(_ecology_base())
    document = json.loads(encode_runner_config(config))
    document["commons_governance"] = {
        "policy_id": COMMONS_GOVERNANCE_POLICY_ID,
        "stock_ids": ["res-water"],
    }
    with pytest.raises(RunnerSerializationError):
        decode_runner_config(json.dumps(document, separators=(",", ":")).encode())
