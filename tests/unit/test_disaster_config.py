# mypy: ignore-errors

"""runner-config-v63 disasters seam and inherited family preservation."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from simulation.compatibility import COMPATIBILITY_MATRIX, V4_OWNED_CAPABILITY_FLAGS
from simulation.disasters_config import (
    DISASTERS_POLICY_ID,
    DisastersConfigError,
    DisastersSpec,
    decode_disasters,
    encode_disasters,
    policy_sha256_for_disasters,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V56,
    RUNNER_SCHEMA_VERSION_V62,
    RUNNER_SCHEMA_VERSION_V63,
    SUPPORTED_RUNNER_SCHEMA_VERSIONS,
    V4CapabilityFlags,
)
from simulation.runner_serialization import (
    RunnerSerializationError,
    decode_runner_config,
    encode_runner_config,
    runner_config_fingerprint,
)
from tests.unit.test_commons_governance_config import _as_v62
from tests.unit.test_ecological_resources_config import _as_v60, _ecology_base
from world.disasters import (
    DisasterCollapseEffect,
    DisasterInfrastructureEffect,
    DisasterInfrastructureTarget,
    DisasterKind,
    DisasterLocationTarget,
    DisasterLossEffect,
    DisasterResourceTarget,
    DisasterRule,
    DisasterScheduleEntry,
    DisasterSurgeEffect,
)
from world.identifiers import EntityId
from world.infrastructure import InfrastructureKind
from world.values import ResourceKind

pytestmark = pytest.mark.unit

_BASELINE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "runner_configs"
    / "bf_baseline_v4.json"
)


def _doc(config) -> dict:
    return json.loads(encode_runner_config(config).decode("utf-8"))


def _loss_rule(
    rule_id: str = "drought-a",
    *,
    kind: DisasterKind = DisasterKind.DROUGHT,
    resource_id: str = "res-food",
    chance_ppm: int = 0,
    loss_tenths: int = 10,
) -> DisasterRule:
    return DisasterRule(
        rule_id=rule_id,
        kind=kind,
        chance_ppm=chance_ppm,
        target=DisasterResourceTarget(resource_id=EntityId(resource_id)),
        effect=DisasterLossEffect(loss_tenths=loss_tenths),
    )


def _collapse_rule(
    rule_id: str = "collapse-a",
    *,
    resource_id: str = "res-food",
    chance_ppm: int = 0,
) -> DisasterRule:
    return DisasterRule(
        rule_id=rule_id,
        kind=DisasterKind.RESOURCE_COLLAPSE,
        chance_ppm=chance_ppm,
        target=DisasterResourceTarget(resource_id=EntityId(resource_id)),
        effect=DisasterCollapseEffect(capacity_damage_tenths=25),
    )


def _infra_rule(
    rule_id: str = "infra-a",
    *,
    location_id: str = "loc-a",
    endpoint: str | None = None,
    kind: InfrastructureKind = InfrastructureKind.WELL,
    chance_ppm: int = 0,
) -> DisasterRule:
    return DisasterRule(
        rule_id=rule_id,
        kind=DisasterKind.INFRASTRUCTURE_DESTRUCTION,
        chance_ppm=chance_ppm,
        target=DisasterInfrastructureTarget(
            location_id=EntityId(location_id),
            endpoint_location_id=None if endpoint is None else EntityId(endpoint),
            infrastructure_kind=kind,
        ),
        effect=DisasterInfrastructureEffect(),
    )


def _surge_rule(
    rule_id: str = "surge-a",
    *,
    location_id: str = "loc-a",
    chance_ppm: int = 0,
    milli: int = 100,
) -> DisasterRule:
    return DisasterRule(
        rule_id=rule_id,
        kind=DisasterKind.EPIDEMIC_SURGE,
        chance_ppm=chance_ppm,
        target=DisasterLocationTarget(location_id=EntityId(location_id)),
        effect=DisasterSurgeEffect(extra_opportunity_milli=milli),
    )


def _disasters_spec(
    *rules: DisasterRule,
    schedule: tuple[DisasterScheduleEntry, ...] = (),
) -> DisastersSpec:
    ordered = tuple(sorted(rules or (_loss_rule(),), key=lambda rule: rule.rule_id))
    return DisastersSpec(
        policy_id=DISASTERS_POLICY_ID,
        rules=ordered,
        schedule=schedule,
    )


def _as_v63(
    config,
    *,
    disasters: DisastersSpec | None = None,
    with_overexploitation: bool = False,
    with_commons: bool = False,
    with_disease: bool = False,
):
    if with_commons:
        base = _as_v62(config, with_disease=with_disease)
        return replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V63,
            disasters=disasters
            or _disasters_spec(_loss_rule(resource_id="res-water")),
            v4_capability_flags=replace(
                base.v4_capability_flags,
                disasters=True,
            ),
        )
    if with_overexploitation:
        from tests.unit.test_overexploitation_config import (
            _as_v61,
            _overexploitation_spec,
        )

        base = _as_v61(config)
        return replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V63,
            overexploitation=_overexploitation_spec(),
            disasters=disasters or _disasters_spec(),
            v4_capability_flags=replace(
                base.v4_capability_flags,
                disasters=True,
            ),
        )
    base = _as_v60(config, with_disease=with_disease)
    return replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V63,
        disasters=disasters or _disasters_spec(),
        v4_capability_flags=replace(
            base.v4_capability_flags,
            disasters=True,
        ),
    )


def test_v63_is_supported_and_disasters_owned() -> None:
    assert RUNNER_SCHEMA_VERSION_V63 == "runner-config-v63"
    assert RUNNER_SCHEMA_VERSION_V63 in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    entry = COMPATIBILITY_MATRIX["runner_config"]
    assert RUNNER_SCHEMA_VERSION_V63 in entry.bump_trigger
    assert "disasters" in entry.bump_trigger
    assert "disasters" in V4_OWNED_CAPABILITY_FLAGS


def test_six_kind_round_trips_and_digest() -> None:
    rules = (
        _loss_rule("drought-a", kind=DisasterKind.DROUGHT, resource_id="res-water"),
        _loss_rule("fire-a", kind=DisasterKind.FIRE, resource_id="res-food"),
        _loss_rule("flood-a", kind=DisasterKind.FLOOD_LIKE, resource_id="res-grain"),
        _infra_rule("infra-a"),
        _collapse_rule("resource-a", resource_id="res-material"),
        _surge_rule("surge-a"),
    )
    spec = DisastersSpec(
        policy_id=DISASTERS_POLICY_ID,
        rules=tuple(sorted(rules, key=lambda rule: rule.rule_id)),
        schedule=(),
    )
    encoded = encode_disasters(spec)
    assert decode_disasters(encoded) == spec
    digest = policy_sha256_for_disasters(spec)
    assert len(digest) == 64
    assert digest == policy_sha256_for_disasters(decode_disasters(encoded))


def test_spec_rejects_invalid_shapes() -> None:
    good = encode_disasters(_disasters_spec())
    with pytest.raises(DisastersConfigError) as excinfo:
        decode_disasters({**good, "extra": True})
    assert excinfo.value.code == "disasters_spec_invalid"
    with pytest.raises(DisastersConfigError) as excinfo:
        decode_disasters({"policy_id": "wrong", "rules": good["rules"], "schedule": []})
    assert excinfo.value.code == "disasters_policy_invalid"
    with pytest.raises(DisastersConfigError) as excinfo:
        decode_disasters(
            {
                "policy_id": DISASTERS_POLICY_ID,
                "rules": [
                    {
                        "rule_id": "drought-a",
                        "kind": "drought",
                        "chance_ppm": True,
                        "target": {"resource_id": "res-water"},
                        "effect": {"loss_tenths": 10},
                    }
                ],
                "schedule": [],
            }
        )
    assert excinfo.value.code == "disaster_chance_ppm_invalid"
    with pytest.raises(DisastersConfigError) as excinfo:
        DisastersSpec(
            policy_id=DISASTERS_POLICY_ID,
            rules=(_loss_rule("b-second"), _loss_rule("a-first")),
            schedule=(),
        )
    assert excinfo.value.code == "disaster_rule_order_invalid"


def test_schedule_requires_zero_chance_and_canonical_order() -> None:
    with pytest.raises(DisastersConfigError) as excinfo:
        DisastersSpec(
            policy_id=DISASTERS_POLICY_ID,
            rules=(_loss_rule(chance_ppm=1),),
            schedule=(DisasterScheduleEntry(tick=3, rule_id="drought-a"),),
        )
    assert excinfo.value.code == "disaster_scheduled_chance_nonzero"
    with pytest.raises(DisastersConfigError) as excinfo:
        DisastersSpec(
            policy_id=DISASTERS_POLICY_ID,
            rules=(
                _loss_rule("alpha"),
                _collapse_rule("beta", resource_id="res-water"),
            ),
            schedule=(
                DisasterScheduleEntry(tick=2, rule_id="beta"),
                DisasterScheduleEntry(tick=1, rule_id="alpha"),
            ),
        )
    assert excinfo.value.code == "disaster_schedule_order_invalid"


def test_v63_round_trip_and_legacy_rejection() -> None:
    base = _ecology_base()
    config = _as_v63(base)
    encoded = encode_runner_config(config)
    document = json.loads(encoded.decode("utf-8"))
    assert document["schema_version"] == RUNNER_SCHEMA_VERSION_V63
    assert "disasters" in document
    decoded = decode_runner_config(encoded)
    assert decoded.schema_version == RUNNER_SCHEMA_VERSION_V63
    assert decoded.disasters == config.disasters
    assert runner_config_fingerprint(decoded) == runner_config_fingerprint(config)

    legacy = encode_runner_config(_as_v62(base))
    legacy_doc = json.loads(legacy.decode("utf-8"))
    with pytest.raises(RunnerSerializationError):
        decode_runner_config(
            json.dumps(
                {**legacy_doc, "disasters": encode_disasters(_disasters_spec())},
                separators=(",", ":"),
            ).encode()
        )

    flags = V4CapabilityFlags(
        disasters=True, ecological_feedback=True, supply_chains=True
    )
    assert flags.owned_enabled_names() == (
        "supply_chains",
        "ecological_feedback",
        "disasters",
    )
    v60_doc = _doc(_as_v60(base))
    assert "disasters" not in v60_doc
    with pytest.raises(RunnerSerializationError):
        decode_runner_config(
            json.dumps(
                {
                    **v60_doc,
                    "schema_version": RUNNER_SCHEMA_VERSION_V56,
                    "disasters": encode_disasters(_disasters_spec()),
                },
                separators=(",", ":"),
            ).encode()
        )


def test_v63_optional_siblings_and_default_v4_unchanged() -> None:
    base = _ecology_base()
    with_over = _as_v63(base, with_overexploitation=True)
    assert with_over.overexploitation is not None
    encoded = _doc(with_over)
    assert "overexploitation" in encoded
    decoded_over = decode_runner_config(encode_runner_config(with_over))
    assert decoded_over.overexploitation is not None

    with_commons = _as_v63(base, with_commons=True)
    assert with_commons.commons_governance is not None
    encoded_commons = _doc(with_commons)
    assert "commons_governance" in encoded_commons

    v4 = decode_runner_config(_BASELINE.read_bytes())
    assert v4.schema_version == RUNNER_SCHEMA_VERSION_V4
    assert "disasters" not in _doc(v4)


def test_target_binding_prerequisites() -> None:
    base = _ecology_base()
    # Ecology fixture names res-food but defaults kind=WATER; flood requires FOOD.
    bad = _disasters_spec(
        _loss_rule(
            "flood-bad",
            kind=DisasterKind.FLOOD_LIKE,
            resource_id="res-food",
        )
    )
    with pytest.raises(ValueError, match="disaster_stock_kind_mismatch"):
        _as_v63(base, disasters=bad)

    surge = _disasters_spec(_surge_rule())
    with pytest.raises(ValueError, match="disasters_epidemic_required"):
        _as_v63(base, disasters=surge)

    infra = _disasters_spec(_infra_rule())
    with pytest.raises(ValueError, match="disasters_infrastructure_required"):
        _as_v63(base, disasters=infra)

    far = _disasters_spec(
        _loss_rule(),
        schedule=(DisasterScheduleEntry(tick=10_000, rule_id="drought-a"),),
    )
    with pytest.raises(ValueError, match="disaster_schedule_tick_out_of_range"):
        _as_v63(base, disasters=far)

    unmanaged = _disasters_spec(
        _loss_rule("orphan", resource_id="res-water")
    )
    with pytest.raises(ValueError, match="disaster_stock_unmanaged"):
        _as_v63(base, disasters=unmanaged)

    ok = _as_v63(base, disasters=_disasters_spec(_loss_rule()))
    assert ok.disasters is not None
    assert base.scenario.resources[0].kind is ResourceKind.WATER


def test_v62_canonical_bytes_unchanged() -> None:
    base = _ecology_base()
    v62 = _as_v62(base)
    encoded = encode_runner_config(v62)
    document = json.loads(encoded.decode("utf-8"))
    assert document["schema_version"] == RUNNER_SCHEMA_VERSION_V62
    assert "disasters" not in document
    again = encode_runner_config(decode_runner_config(encoded))
    assert again == encoded
