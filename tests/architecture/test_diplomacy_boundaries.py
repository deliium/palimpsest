"""V4-10 ownership boundary: claim diplomacy without a new schema."""

from __future__ import annotations

from dataclasses import fields, replace
from pathlib import Path
from typing import Any, cast

import pytest

from agents.cognition.diplomacy import DiplomacyLedger
from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from simulation.models import RunId
from simulation.runner import (
    RunnerConstructionError,
    RunnerConstructionErrorCode,
    SimulationRunner,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V56,
    AgentCognitionSpec,
    AgentRunnerSpec,
    SimulationRunnerConfig,
    V4CapabilityFlags,
    WorldScenarioSpec,
)
from simulation.v4_architecture import (
    V4_CAPABILITY_FLAGS,
    V4_CONTEXT_BY_ID,
    V4_CONTEXT_MAP_VERSION,
    V4_CONTEXTS,
    V4Authority,
    V4ContextId,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules

pytestmark = pytest.mark.unit

_SRC = Path(__file__).resolve().parents[2] / "src"
_OWNED_FLAGS = frozenset(
    {"organizations", "formal_rules", "legal_disputes", "diplomacy"}
)


def _base() -> SimulationRunnerConfig:
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return base_runner_config_from_scenario(
        seed=11,
        stochastic_identity="cmp-v4-diplomacy-boundary",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v4-diplomacy-boundary"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(make_location(),),
            bodies=(body,),
            weather=(make_weather(),),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=agent_id,
                entity_id=body.entity_id,
                cognition=AgentCognitionSpec(agent_id=agent_id),
            ),
        ),
        max_ticks=2,
    )


def test_v4_10_owns_diplomacy_without_new_schema() -> None:
    from simulation.compatibility import V4_OWNED_CAPABILITY_FLAGS

    assert V4_CONTEXT_MAP_VERSION == "v4-context-map-v2"
    assert len(V4_CONTEXTS) == 14
    assert len(V4_CAPABILITY_FLAGS) == 12
    assert V4_OWNED_CAPABILITY_FLAGS == _OWNED_FLAGS
    assert len(V4_OWNED_CAPABILITY_FLAGS) == 4

    diplomacy = V4_CONTEXT_BY_ID[V4ContextId.DIPLOMACY]
    assert diplomacy.authority is V4Authority.OWNER_SCOPED
    assert diplomacy.capability_flag == "diplomacy"
    assert diplomacy.owner_packages == (
        "agents.cognition",
        "social",
        "simulation",
    )
    assert diplomacy.uses_existing_events is True
    assert diplomacy.prerequisite_contexts == (V4ContextId.ORGANIZATIONS,)

    assert V4CapabilityFlags(diplomacy=True).owned_enabled_names() == ("diplomacy",)
    assert V4CapabilityFlags(diplomacy=True).unimplemented_enabled_names() == ()

    for spec in (AgentCognitionSpec, AgentRunnerSpec, SimulationRunnerConfig):
        names = {field.name for field in fields(spec)}
        assert "diplomacy_mode" not in names, spec.__name__
        assert "diplomacy" not in names, spec.__name__

    offenders = [
        str(path.relative_to(_SRC))
        for path in sorted(_SRC.rglob("*.py"))
        if "__pycache__" not in path.parts
        and "runner-config-v57" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


@pytest.mark.asyncio
async def test_organized_conflict_still_fails_closed() -> None:
    config = replace(
        _base(),
        schema_version=RUNNER_SCHEMA_VERSION_V56,
        v4_capability_flags=V4CapabilityFlags(organized_conflict=True),
    )

    with pytest.raises(RunnerConstructionError) as excinfo:
        await SimulationRunner.from_config(
            config, run_id=RunId("run-v4-diplomacy-unowned-gate")
        )

    assert excinfo.value.code is RunnerConstructionErrorCode.CAPABILITY_UNIMPLEMENTED
    assert excinfo.value.stage == "v4_capability_flags"


def _sources(patterns: tuple[str, ...]) -> list[Path]:
    files: list[Path] = []
    for pattern in patterns:
        files.extend(sorted(_SRC.glob(pattern)))
    return [path for path in files if "__pycache__" not in path.parts]


def test_diplomacy_has_no_command_path() -> None:
    import ast

    forbidden_calls = {"submit", "admit", "submit_command", "resolve_command"}
    for path in _sources(
        (
            "agents/cognition/diplomacy*.py",
            "analysis/diplomacy*.py",
            "simulation/diplomacy*.py",
            "experiments/diplomacy*.py",
            "api/routes/diplomacy.py",
        )
    ):
        source = path.read_text(encoding="utf-8")
        assert "AgentCommand" not in source, path
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = (
                    func.id
                    if isinstance(func, ast.Name)
                    else func.attr
                    if isinstance(func, ast.Attribute)
                    else ""
                )
                assert name not in forbidden_calls, (path.name, name)


def test_diplomacy_ledger_is_not_world_read() -> None:
    for path in sorted((_SRC / "world").glob("*.py")):
        assert "agents.cognition.diplomacy" not in path.read_text(encoding="utf-8")
    for name in ("engine.py",):
        path = _SRC / "simulation" / name
        source = path.read_text(encoding="utf-8")
        assert "agents.cognition.diplomacy import" not in source
    api_source = (_SRC / "api" / "routes" / "diplomacy.py").read_text()
    assert "agents.cognition.diplomacy" not in api_source
    assert "analysis." not in api_source


def test_no_score_or_oracle_symbol_exists() -> None:
    forbidden = {
        "RelationScore",
        "DiplomacyScore",
        "LegitimacyOracle",
        "TruthEngine",
        "TreatyStore",
        "TreatyAuthority",
        "EnvoyRegistry",
        "Polity",
        "Border",
        "Citizenship",
        "WarState",
        "ArmyActor",
    }
    for path in _sources(
        (
            "agents/cognition/diplomacy*.py",
            "analysis/diplomacy*.py",
            "simulation/diplomacy*.py",
            "experiments/diplomacy*.py",
            "api/routes/diplomacy.py",
        )
    ):
        source = path.read_text(encoding="utf-8")
        for symbol in forbidden:
            assert f"class {symbol}" not in source, (path.name, symbol)


def test_representation_principal_roundness() -> None:
    from agents.cognition import DiplomaticPartyKind
    from agents.cognition.delegation_representation import (
        RepresentationPrincipalKind,
    )

    assert {member.value for member in DiplomaticPartyKind} == {
        member.value for member in RepresentationPrincipalKind
    }
    assert {member.value for member in DiplomaticPartyKind} == {
        "agent",
        "organization",
        "settlement",
        "coalition",
        "unknown",
    }


def test_token_domains_interoperate() -> None:
    from analysis.delegation_representation_contract import representation_owner_token
    from analysis.diplomacy_contract import (
        DiplomacyAnalysisError,
        diplomacy_agent_token,
        diplomacy_party_token,
        require_diplomacy_candidate_id,
    )

    assert diplomacy_agent_token("agent-a") == representation_owner_token("agent-a")
    anchor = "orgc-" + "a" * 16
    assert diplomacy_party_token("organization", anchor) == anchor
    assert diplomacy_party_token("settlement", "region-1") == "region-1"
    import pytest

    with pytest.raises(DiplomacyAnalysisError):
        require_diplomacy_candidate_id("dip-pub-" + "a" * 16)


def test_alignment_stays_researcher_only() -> None:
    for root in ("agents", "world", "observer"):
        for path in sorted((_SRC / root).rglob("*.py")):
            source = path.read_text(encoding="utf-8")
            assert "DiplomacyAlignmentStatus" not in source, path


def test_snapshot_and_store_schemas_exist() -> None:
    from persistence.diplomacy_filesystem import DIPLOMACY_STORE_SCHEMA
    from simulation.diplomacy_models import DIPLOMACY_SNAPSHOT_SCHEMA

    assert DIPLOMACY_SNAPSHOT_SCHEMA == "diplomacy-snapshot-v1"
    assert DIPLOMACY_STORE_SCHEMA == "diplomacy-store-v1"


def test_six_routes_and_six_purposes() -> None:
    from api.routes.diplomacy import router
    from simulation.diplomacy_models import DIPLOMACY_CURSOR_PURPOSES

    routes = [
        route for route in router.routes if getattr(route, "methods", None) is not None
    ]
    assert len(routes) == 6
    assert all(cast(Any, route).methods == {"GET"} for route in routes)
    assert len(DIPLOMACY_CURSOR_PURPOSES) == 6


def test_no_new_wire_surfaces() -> None:
    from analysis.specifications import METRIC_FAMILY_COUNT
    from observer.version import SEMANTIC_EVENT_TYPES
    from simulation.compatibility import ALEMBIC_HEAD_REVISION
    from world._rules import COMMAND_RULE_MATRIX
    from world.events import EVENT_SCHEMA_REPLAY_V22

    assert METRIC_FAMILY_COUNT == 164
    assert EVENT_SCHEMA_REPLAY_V22 == 22
    assert len(COMMAND_RULE_MATRIX) == 43
    assert len(SEMANTIC_EVENT_TYPES) == 73
    assert ALEMBIC_HEAD_REVISION == "0017"
    assert not list((_SRC.parent / "alembic" / "versions").glob("0018_*.py"))
    from simulation.persistence import ACCEPTED_PERSISTENCE_CODEC_VERSIONS

    codecs = ACCEPTED_PERSISTENCE_CODEC_VERSIONS

    assert "v20" in codecs
    assert "v21" not in codecs


def test_no_peer_ledger_reads() -> None:
    import inspect

    from agents.cognition import apply_diplomacy_update, record_diplomacy_utterance

    for callable_obj in (apply_diplomacy_update, record_diplomacy_utterance):
        names = set(inspect.signature(callable_obj).parameters)
        assert names.isdisjoint(
            {
                "peer_ledger",
                "other_owner_ledger",
                "foreign_representation",
                "world_state",
                "event_store",
            }
        )
    source = (_SRC / "agents" / "cognition" / "diplomacy.py").read_text(
        encoding="utf-8"
    )
    assert "require_owner_diplomacy" in source
    assert "other_owner" not in source


def _frame(act: object, **overrides: object) -> object:
    from agents.cognition import DiplomacyFrame

    values: dict[str, object] = {
        "act": act,
        "envoy_ref": "agent-owner",
        "actor_ref": "agent-owner",
    }
    values.update(overrides)
    return DiplomacyFrame(**values)  # type: ignore[arg-type]


def _proposal_ledger() -> DiplomacyLedger:
    from agents.cognition import (
        DiplomaticAct,
        DiplomaticPartyKind,
        DiplomaticTermKind,
        apply_diplomacy_update,
        default_diplomacy_policy,
        empty_diplomacy_ledger,
    )

    policy = default_diplomacy_policy()
    ledger = empty_diplomacy_ledger("agent-owner", tick=0)
    return apply_diplomacy_update(
        owner_id="agent-owner",
        tick=1,
        observation=None,
        prior=ledger,
        frames=(
            _frame(
                DiplomaticAct.PROPOSE,
                party_kind=DiplomaticPartyKind.AGENT,
                party_ref="agent-other",
                topic_subject="trade",
                term_kind=DiplomaticTermKind.MATERIAL_EXCHANGE,
            ),
        ),
        policy=policy,
    )


def test_relation_and_termination_records() -> None:
    from agents.cognition import (
        DiplomaticProvenance,
        DiplomaticTerminationKind,
    )
    from agents.cognition.diplomacy import apply_diplomacy_termination

    ledger = _proposal_ledger()
    assert ledger.relations
    assert ledger.instruments
    relation = ledger.relations[0]
    instrument = ledger.instruments[0]
    self_party = next(
        party for party in ledger.parties if party.anchor_ref == "agent-owner"
    )
    assert relation.party_ids[0] == self_party.party_id
    assert instrument.party_ids == relation.party_ids

    terminated = apply_diplomacy_termination(
        ledger,
        target_kind="instrument",
        target_ref=instrument.instrument_id,
        kind=DiplomaticTerminationKind.PARTY_WITHDREW,
        tick=2,
        provenance=DiplomaticProvenance.SELF_DECLARED,
    )
    assert any(
        row.target_ref == instrument.instrument_id for row in terminated.terminations
    )
    assert instrument.instrument_id in {
        row.instrument_id for row in terminated.instruments
    }


def test_scope_duration_matrix() -> None:
    from agents.cognition import diplomacy_scope_covers

    assert not diplomacy_scope_covers(
        scope_kind="negotiate",
        duration_kind="single_act",
        instrument_kind="agreement",
        scope_subject="trade",
        topic_subject="trade",
    )
    assert not diplomacy_scope_covers(
        scope_kind="negotiate",
        duration_kind="occasion",
        instrument_kind="promise",
        scope_subject="trade",
        topic_subject="trade",
    )
    assert diplomacy_scope_covers(
        scope_kind="negotiate",
        duration_kind="until_revoked",
        instrument_kind="agreement",
        scope_subject="trade",
        topic_subject="trade",
    )
    assert not diplomacy_scope_covers(
        scope_kind="negotiate",
        duration_kind="until_revoked",
        instrument_kind="agreement",
        scope_subject="trade",
        topic_subject="passage",
    )


def test_principal_declaration_and_current_standing() -> None:
    from types import SimpleNamespace

    from agents.cognition import (
        DiplomacyPolicy,
        DiplomaticAct,
        RepresentationStatus,
        apply_diplomacy_update,
        default_diplomacy_policy,
        diplomacy_envoy_status,
    )

    policy: DiplomacyPolicy = default_diplomacy_policy()
    ledger = _proposal_ledger()
    instrument = ledger.instruments[0]
    ledger = apply_diplomacy_update(
        owner_id="agent-owner",
        tick=2,
        observation=None,
        prior=ledger,
        frames=(
            _frame(
                DiplomaticAct.ACCEPT,
                instrument_ref=instrument.instrument_id,
                envoy_ref="agent-owner",
                actor_ref="agent-owner",
            ),
        ),
        policy=policy,
    )
    assert ledger.declarations
    self_party = next(
        party for party in ledger.parties if party.anchor_ref == "agent-owner"
    )
    assert any(
        declaration.declarer_party_id == self_party.party_id
        for declaration in ledger.declarations
    )

    revoked = SimpleNamespace(
        mandate_id="rmd-" + "0" * 16,
        status=RepresentationStatus.REVOKED,
        scope_kind="negotiate",
        duration_kind="until_revoked",
        scope_subject="trade",
        end_tick=None,
        revoked=True,
        superseded=False,
        expired=False,
    )
    from agents.cognition import DiplomaticEnvoy, DiplomaticEnvoyStatus

    envoy = DiplomaticEnvoy(
        envoy_id="dpe-" + "0" * 16,
        relation_id=ledger.relations[0].relation_id,
        party_id=ledger.parties[0].party_id,
        envoy_ref="agent-envoy",
        mandate_ref="rmd-" + "0" * 16,
        status=DiplomaticEnvoyStatus.RECOGNIZED,
        accredited_tick=1,
        end_tick=None,
        revision=0,
        provenance=ledger.parties[0].provenance,
    )
    representation = SimpleNamespace(mandates=(revoked,))
    status = diplomacy_envoy_status(envoy, representation, tick=2, policy=policy)
    assert status.value == "revoked"


def test_derived_row_pipeline() -> None:
    from agents.cognition import (
        DiplomaticAct,
        default_diplomacy_policy,
    )
    from agents.cognition.diplomacy import detect_diplomatic_misrepresentation

    policy = default_diplomacy_policy()
    ledger = _proposal_ledger()
    instrument = ledger.instruments[0]
    from agents.cognition import apply_diplomacy_update

    ledger = apply_diplomacy_update(
        owner_id="agent-owner",
        tick=2,
        observation=None,
        prior=ledger,
        frames=(
            _frame(
                DiplomaticAct.ACCEPT,
                envoy_ref="agent-envoy",
                actor_ref="agent-envoy",
                party_ref="agent-owner",
                instrument_ref=instrument.instrument_id,
            ),
        ),
        policy=policy,
    )
    first = detect_diplomatic_misrepresentation(
        ledger, None, tick=2, policy=policy
    )
    second = detect_diplomatic_misrepresentation(
        ledger, None, tick=2, policy=policy
    )
    assert first.misrepresentations
    assert [row.misrepresentation_id for row in first.misrepresentations] == [
        row.misrepresentation_id for row in second.misrepresentations
    ]
    source = (_SRC / "agents" / "cognition" / "diplomacy.py").read_text(
        encoding="utf-8"
    )
    order = [
        "detect_diplomatic_misrepresentation(",
        "expire_diplomacy_records(",
        "supersede_diplomacy_instruments(",
        "detect_diplomacy_conflicts(",
        "enforce_diplomacy_limits(",
    ]
    start = source.index("def apply_diplomacy_update")
    positions = [source.index(name, start) for name in order]
    assert positions == sorted(positions)


def test_existing_pins_unchanged() -> None:
    from observer.capabilities import ObserverCapability
    from simulation.versioning import V4_WRITE_PAIR_RESERVATIONS

    assert len(V4_WRITE_PAIR_RESERVATIONS) == 4
    assert {reservation.event_schema for reservation in V4_WRITE_PAIR_RESERVATIONS} == {
        23,
        24,
        25,
        26,
    }
    assert ObserverCapability.ORGANIZATION_ROWS.value == "organization_rows"
    for spec in (SimulationRunnerConfig,):
        assert "prepare_parallel" not in {field.name for field in fields(spec)}


def test_no_roadmap_or_client_authority() -> None:
    for path in sorted(_SRC.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        source = path.read_text(encoding="utf-8")
        assert "clients/godot-observer" not in source, path
        assert "clients/research-ui" not in source, path
        assert ".ai-factory/ROADMAP.md" not in source, path
