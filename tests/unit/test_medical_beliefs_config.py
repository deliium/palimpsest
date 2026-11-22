# mypy: ignore-errors

"""runner-config-v59 medical-belief seam and v58 preservation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace

import pytest

from experiments.catalog import experiment_disease_mechanics
from simulation.medical_beliefs_config import (
    MEDICAL_BELIEFS_POLICY_ID,
    MedicalBeliefsConfigError,
    MedicalBeliefsSpec,
    decode_medical_beliefs,
    encode_medical_beliefs,
)
from simulation.persistence import checkpoint_schema_for_production
from simulation.runner_models import (
    RESULT_SCHEMA_VERSION,
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V58,
    RUNNER_SCHEMA_VERSION_V59,
    SUPPORTED_RUNNER_SCHEMA_VERSIONS,
    SimulationRunnerConfig,
    V4CapabilityFlags,
)
from simulation.runner_serialization import (
    RunnerSerializationError,
    cognition_fingerprint,
    decode_runner_config,
    encode_runner_config,
    runner_config_fingerprint,
    scenario_fingerprint,
)
from tests.unit.test_disease_config import (
    _as_v58,
    _infra_base,
    _science_infra_base,
)
from world.events import EVENT_SCHEMA_REPLAY_V24

pytestmark = pytest.mark.unit

_V58_INFRA_SHA = "8c20a3886e870c97b9170b2ce08719e009d594ded3d964fde02f2da5c4177985"
_V58_TRAVEL_SHA = "1542d87b04b99c9f4b274585f86e738c39c963307f3dc2111b13ae78cbc269f3"
_V58_INSTRUMENTS_SHA = (
    "d4271d250a3659db1ef24a5b76173c6542e6ffbcd22ae0b96e3fcae9e8680a61"
)
_V58_TRAVEL_INSTRUMENTS_SHA = (
    "9e450cd4198043cbfa489aceb558f0f4a690f090e56c94e71abe76552bd94feb"
)
_V58_COGNITION = "cee17d03df0923199d77c4aa02bdb74da272c6f0d56df9610dabe42ff22cf1ee"
_V58_INFRA_SCENARIO = (
    "2511d55e6ee81b3b933ae515bdc7acf77ee745f8482a3d1bf1156ba83b76bc6d"
)
_V58_INSTRUMENTS_SCENARIO = (
    "ce72bb3b2d31bdab896bcadfa1bbfe740a25cb8495ee3bb55ab16715b9b95059"
)


def _medical_spec() -> MedicalBeliefsSpec:
    return MedicalBeliefsSpec(policy_id=MEDICAL_BELIEFS_POLICY_ID)


def _contact_v58() -> SimulationRunnerConfig:
    definition = experiment_disease_mechanics(_infra_base(), max_ticks=8)
    return next(
        condition.runner_config
        for condition in definition.conditions
        if condition.condition_id == "contact-enabled"
    )


def _as_v59(config: SimulationRunnerConfig) -> SimulationRunnerConfig:
    return replace(
        config,
        schema_version=RUNNER_SCHEMA_VERSION_V59,
        medical_beliefs=_medical_spec(),
    )


def test_v59_is_supported_and_v60_is_not() -> None:
    assert RUNNER_SCHEMA_VERSION_V59 == "runner-config-v59"
    assert RUNNER_SCHEMA_VERSION_V59 in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    assert "runner-config-v60" not in SUPPORTED_RUNNER_SCHEMA_VERSIONS


def test_medical_spec_round_trip_and_rejects_bad_shapes() -> None:
    spec = _medical_spec()
    encoded = encode_medical_beliefs(spec)
    assert encoded == {"policy_id": MEDICAL_BELIEFS_POLICY_ID}
    assert decode_medical_beliefs(encoded) == spec
    with pytest.raises(MedicalBeliefsConfigError) as excinfo:
        decode_medical_beliefs({**encoded, "extra": True})
    assert excinfo.value.code == "medical_beliefs_spec_invalid"
    with pytest.raises(MedicalBeliefsConfigError):
        MedicalBeliefsSpec(policy_id="medical-beliefs.v2")


def _assert_v59_round_trip(
    config: SimulationRunnerConfig, *, expect_instruments: bool
) -> None:
    payload = encode_runner_config(config)
    document = json.loads(payload)
    assert document["schema_version"] == RUNNER_SCHEMA_VERSION_V59
    assert document["medical_beliefs"] == {
        "policy_id": MEDICAL_BELIEFS_POLICY_ID
    }
    assert "disease_mechanics" in document
    assert ("measurement_instruments" in document) is expect_instruments
    decoded = decode_runner_config(payload)
    assert decoded.schema_version == RUNNER_SCHEMA_VERSION_V59
    assert decoded.medical_beliefs == _medical_spec()
    assert decoded.disease_mechanics == config.disease_mechanics
    assert (decoded.measurement_instruments is not None) is expect_instruments
    assert encode_runner_config(decoded) == payload


def test_v59_round_trip_from_disease_builder() -> None:
    _assert_v59_round_trip(_as_v59(_contact_v58()), expect_instruments=False)


def test_v59_round_trip_with_instruments() -> None:
    base = _as_v58(_science_infra_base(with_travel=False), with_instruments=True)
    _assert_v59_round_trip(_as_v59(base), expect_instruments=True)


def test_v59_round_trip_with_travel_and_instruments() -> None:
    base = _as_v58(_science_infra_base(with_travel=True), with_instruments=True)
    _assert_v59_round_trip(_as_v59(base), expect_instruments=True)


def test_activation_matrix_fails_closed() -> None:
    contact = _contact_v58()
    with pytest.raises(ValueError, match="code=medical_beliefs_spec_required"):
        replace(
            contact,
            schema_version=RUNNER_SCHEMA_VERSION_V59,
        )
    with pytest.raises(ValueError, match="code=medical_beliefs_schema_mismatch"):
        replace(contact, medical_beliefs=_medical_spec())
    with pytest.raises(ValueError, match="code=medical_beliefs_requires_epidemics"):
        replace(
            contact,
            schema_version=RUNNER_SCHEMA_VERSION_V59,
            v4_capability_flags=V4CapabilityFlags(
                infrastructure_networks=True
            ),
            disease_mechanics=None,
            medical_beliefs=_medical_spec(),
        )
    with pytest.raises(ValueError, match="unsupported runner schema_version"):
        replace(
            contact,
            schema_version="runner-config-v60",
            medical_beliefs=_medical_spec(),
        )


def test_v58_rejects_medical_sibling() -> None:
    payload = encode_runner_config(_as_v58(_infra_base(), founders=()))
    document = json.loads(payload)
    document["medical_beliefs"] = encode_medical_beliefs(_medical_spec())
    with pytest.raises(RunnerSerializationError):
        decode_runner_config(
            json.dumps(document, separators=(",", ":"), sort_keys=True).encode(
                "utf-8"
            )
        )


def test_v58_bytes_and_fingerprints_are_unchanged() -> None:
    cases = (
        (_as_v58(_infra_base(), founders=()), _V58_INFRA_SHA, _V58_INFRA_SCENARIO),
        (
            _as_v58(_infra_base(with_travel=True), founders=()),
            _V58_TRAVEL_SHA,
            _V58_INFRA_SCENARIO,
        ),
        (
            _as_v58(
                _science_infra_base(with_travel=False), with_instruments=True
            ),
            _V58_INSTRUMENTS_SHA,
            _V58_INSTRUMENTS_SCENARIO,
        ),
        (
            _as_v58(_science_infra_base(with_travel=True), with_instruments=True),
            _V58_TRAVEL_INSTRUMENTS_SHA,
            _V58_INSTRUMENTS_SCENARIO,
        ),
    )
    for config, expected_sha, expected_scenario in cases:
        payload = encode_runner_config(config)
        assert hashlib.sha256(payload).hexdigest() == expected_sha
        assert runner_config_fingerprint(config) == expected_sha
        assert cognition_fingerprint(config) == _V58_COGNITION
        assert scenario_fingerprint(config) == expected_scenario
        assert b"medical_beliefs" not in payload


def test_v58_and_v59_twins_differ_only_in_cognition_identity() -> None:
    v58 = _contact_v58()
    v59 = _as_v59(v58)
    assert scenario_fingerprint(v58) == scenario_fingerprint(v59)
    assert runner_config_fingerprint(v58) != runner_config_fingerprint(v59)
    assert cognition_fingerprint(v58) != cognition_fingerprint(v59)
    assert checkpoint_schema_for_production(
        production_active=False, disease_active=True
    ) == (EVENT_SCHEMA_REPLAY_V24, "v22")
    assert v58.schema_version == RUNNER_SCHEMA_VERSION_V58
    assert RESULT_SCHEMA_VERSION == "runner-result-v2"
    assert SimulationRunnerConfig.__dataclass_fields__["schema_version"].default == (
        RUNNER_SCHEMA_VERSION_V4
    )
