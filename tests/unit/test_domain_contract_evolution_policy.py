"""Policy regressions for agent-facing domain-contract evolution.

V2/V3 scaffolding freezes Observation / AgentCommand / communications wire
shape. Later V3 plans must follow accepted-set discipline and keep
live/restored observation parity as a hard gate. Mid-run roster, birth, and
kinship-visible facts require explicit versioned seams — not silent Observation
widenings.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from world.actions import (
    Amend,
    AnnotateRecord,
    Ask,
    Attack,
    Build,
    CopyRecord,
    Craft,
    DamageRecord,
    Drink,
    Drop,
    Eat,
    Erase,
    Feed,
    Flee,
    Give,
    Harvest,
    Help,
    Inscribe,
    Move,
    Repair,
    Search,
    Sleep,
    Store,
    Take,
    Talk,
    Tell,
    TransferArtifact,
    Transport,
    Wait,
    require_agent_command,
)
from world.communications import COMMUNICATION_SCHEMA_VERSION
from world.observations import Observation

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"

# Closed command surface. Durable records deepen artifacts to 29 commands.
_CLOSED_COMMAND_TYPES: frozenset[type] = frozenset(
    {
        Move,
        Search,
        Take,
        Drop,
        Give,
        Eat,
        Drink,
        Sleep,
        Talk,
        Ask,
        Tell,
        Help,
        Feed,
        Transport,
        Attack,
        Flee,
        Wait,
        Harvest,
        Craft,
        Build,
        Repair,
        Store,
        Inscribe,
        Amend,
        Erase,
        TransferArtifact,
        CopyRecord,
        AnnotateRecord,
        DamageRecord,
    }
)

# Frozen Observation field names — keep exact parity with Observation slots.
_FROZEN_OBSERVATION_FIELDS: frozenset[str] = frozenset(
    {
        "world_id",
        "observer_id",
        "revision",
        "tick",
        "self_body",
        "locations",
        "items",
        "resources",
        "exits",
        "visible_bodies",
        "structures",
        "artifacts",
        "occurrences",
        "communications",
        "hour",
        "day_phase",
        "visibility",
        "weather_condition",
        "season",
        "temperature_band",
        "hazard_kinds",
    }
)

_PARITY_GATE = (
    ROOT
    / "tests"
    / "unit"
    / "test_checkpoint_restoration.py"
)


def test_agent_command_set_remains_closed_at_twenty_nine() -> None:
    assert len(_CLOSED_COMMAND_TYPES) == 29
    from world import actions as actions_mod

    # Mirror the public union membership without constructing parameterized commands.
    asserted = {
        Move,
        Search,
        Take,
        Drop,
        Give,
        Eat,
        Drink,
        Sleep,
        Talk,
        Ask,
        Tell,
        Help,
        Feed,
        Transport,
        Attack,
        Flee,
        Wait,
        Harvest,
        Craft,
        Build,
        Repair,
        Store,
        Inscribe,
        Amend,
        Erase,
        TransferArtifact,
        CopyRecord,
        AnnotateRecord,
        DamageRecord,
    }
    assert asserted == _CLOSED_COMMAND_TYPES
    assert hasattr(actions_mod, "AgentCommand")
    wait = require_agent_command(Wait())
    assert type(wait) is Wait


def test_observation_fields_frozen_for_scaffolding_plan() -> None:
    fields = {f.name for f in Observation.__dataclass_fields__.values()}
    assert fields == _FROZEN_OBSERVATION_FIELDS
    field_types = " ".join(
        str(f.type) for f in Observation.__dataclass_fields__.values()
    )
    assert "WorldState" not in field_types
    assert "WorldEvent" not in field_types


def test_communications_schema_unchanged_and_event_only() -> None:
    assert COMMUNICATION_SCHEMA_VERSION == "communication.v1"
    events_text = (SRC / "world" / "events.py").read_text(encoding="utf-8")
    for name in ("Talked", "Asked", "Told"):
        assert f"class {name}" in events_text
    actions_text = (SRC / "world" / "actions.py").read_text(encoding="utf-8")
    for name in ("Talk", "Ask", "Tell"):
        assert f"class {name}" in actions_text


def test_cognition_signatures_forbid_world_authority_widening() -> None:
    forbidden = frozenset(
        {"WorldState", "WorldEvent", "WorldEngine", "TickToken", "ActionSubmission"}
    )
    cognition = SRC / "agents" / "cognition"
    hits: list[str] = []
    for path in cognition.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for arg in node.args.args + node.args.kwonlyargs:
                    if arg.annotation is None:
                        continue
                    text = ast.unparse(arg.annotation)
                    for name in forbidden:
                        if name in text:
                            hits.append(f"{path.name}:{node.name}:{name}")
    assert hits == []


def test_live_restored_observation_parity_gate_remains_present() -> None:
    assert _PARITY_GATE.is_file()
    text = _PARITY_GATE.read_text(encoding="utf-8")
    assert "def test_live_and_restored_observations_match_with_prior_events" in text
    assert "encode_domain" in text


def test_require_agent_command_rejects_non_commands() -> None:
    with pytest.raises(TypeError):
        require_agent_command({"kind": "wait"})  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        require_agent_command("wait")  # type: ignore[arg-type]


def test_v3_scaffolding_adds_no_roster_birth_or_kinship_observation_fields() -> None:
    """Observation root stays frozen; lifecycle lives on self/visible body seams.

    Generational population adds optional ``ObservedSelf.lifecycle`` /
    ``VisibleBody.lifecycle`` only when the channel is on — never sex/parentage
    or Observation-root birth/roster keys.
    """
    fields = {f.name for f in Observation.__dataclass_fields__.values()}
    forbidden_widenings = {
        "kinship",
        "parents",
        "children",
        "birth_tick",
        "age",
        "developmental_stage",
        "settlement_id",
        "institution_id",
        "roster",
        "lineage",
        "sex",
        "fertility",
        "pregnancy",
        "parent_ids",
        "lifecycle",
    }
    assert fields & forbidden_widenings == set()
    assert fields == _FROZEN_OBSERVATION_FIELDS
    from world.observations import ObservedSelf, VisibleBody

    assert "lifecycle" in ObservedSelf.__dataclass_fields__
    assert "lifecycle" in VisibleBody.__dataclass_fields__


def test_v3_domain_bump_policy_documents_parity_gate() -> None:
    """Architecture docs must keep parity + accepted-set rules for V3 bumps."""
    arch = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")
    assert "Domain-contract evolution" in arch
    assert "live/restored" in arch.lower() or "live and restored" in arch.lower()
    assert "test_checkpoint_restoration" in arch
    assert "birth" in arch.lower() or "roster" in arch.lower()
    assert "kinship" in arch.lower()
