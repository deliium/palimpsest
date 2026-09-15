"""Simulation-owned admission from agent commands to bound requests.

Only this path binds authenticated agent identity and world/revision context.
Commands and proposals remain non-authoritative.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from agents.contracts import IdentityTranslator
from agents.models import AgentId
from simulation.identifiers import derive_proposal_id, derive_request_id
from simulation.models import SimulationRunConfig
from world.actions import (
    ActionProposal,
    ActionRequest,
    AgentCommand,
    require_agent_command,
)
from world.identifiers import WorldId, WorldRevision


def admit_agent_command(
    *,
    config: SimulationRunConfig,
    agent_id: AgentId,
    command: object,
    translator: IdentityTranslator,
    world_id: WorldId,
    revision: WorldRevision,
    keys: Sequence[str],
) -> tuple[ActionProposal, ActionRequest]:
    """Admit an exact command under authenticated agent context.

    Allocates deterministic proposal/request IDs, translates the agent to a
    world entity, and returns a non-authoritative bound request. Callers cannot
    supply actor IDs or operational request metadata.
    """
    if type(config) is not SimulationRunConfig:
        raise TypeError("admit_agent_command requires SimulationRunConfig")
    if type(agent_id) is not AgentId:
        raise TypeError("admit_agent_command requires authenticated AgentId")
    if type(world_id) is not WorldId:
        raise TypeError("admit_agent_command requires WorldId")
    if type(revision) is not WorldRevision:
        raise TypeError("admit_agent_command requires WorldRevision")
    if isinstance(command, Mapping):
        raise TypeError("raw mappings cannot be admitted as agent commands")
    typed_command: AgentCommand = require_agent_command(command)
    actor_id = translator.to_entity_id(agent_id)
    round_trip = translator.to_agent_id(actor_id)
    if round_trip != agent_id:
        raise ValueError("identity translation mismatch for admitted agent")
    key_tuple = tuple(keys)
    if not key_tuple:
        raise ValueError("admission requires at least one canonical key")
    for key in key_tuple:
        if not isinstance(key, str) or key == "":
            raise ValueError("admission keys must be non-empty strings")
    proposal_id = derive_proposal_id(config, "admit", *key_tuple)
    request_id = derive_request_id(config, "admit", *key_tuple)
    proposal = ActionProposal(proposal_id=proposal_id, command=typed_command)
    request = ActionRequest(
        request_id=request_id,
        proposal_id=proposal_id,
        world_id=world_id,
        actor_id=actor_id,
        revision=revision,
        command=typed_command,
    )
    return proposal, request
