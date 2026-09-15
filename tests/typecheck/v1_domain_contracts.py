"""Mypy fixtures for V1 domain command and request contracts."""

from __future__ import annotations

from world.actions import (
    ActionProposal,
    ActionRequest,
    AgentCommand,
    Move,
    Wait,
    require_agent_command,
)
from world.identifiers import (
    EntityId,
    ProposalId,
    RequestId,
    WorldId,
    WorldRevision,
)


def _accepted_command() -> AgentCommand:
    return require_agent_command(Wait())


def _proposal_and_request() -> tuple[ActionProposal, ActionRequest]:
    command: AgentCommand = Move(EntityId("loc-1"))
    proposal = ActionProposal(proposal_id=ProposalId("p-1"), command=command)
    request = ActionRequest(
        request_id=RequestId("r-1"),
        proposal_id=proposal.proposal_id,
        world_id=WorldId("world-1"),
        actor_id=EntityId("body-1"),
        revision=WorldRevision(0),
        command=command,
    )
    return proposal, request


def _admission_uses_agent_command() -> AgentCommand:
    from agents.models import AgentId
    from simulation.actions import admit_agent_command
    from simulation.models import SimulationRunConfig

    class _Translator:
        def to_entity_id(self, agent_id: AgentId) -> EntityId:
            return EntityId(agent_id.value)

        def to_agent_id(self, entity_id: EntityId) -> AgentId:
            return AgentId(entity_id.value)

    _proposal, request = admit_agent_command(
        config=SimulationRunConfig(seed=1),
        agent_id=AgentId("agent-1"),
        command=Wait(),
        translator=_Translator(),
        world_id=WorldId("world-1"),
        revision=WorldRevision(0),
        keys=("k",),
    )
    return request.command
