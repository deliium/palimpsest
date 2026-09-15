"""Simulation orchestration ports and deterministic primitives."""

from simulation.actions import admit_agent_command
from simulation.clock import LogicalClock, Tick, require_tick
from simulation.contracts import (
    RunConfigurationPort,
    describe_run,
    export_metadata,
    log_invalid_setup,
    log_replay_mismatch,
    log_run_configured,
    make_export,
)
from simulation.identifiers import (
    derive_belief_id,
    derive_entity_id,
    derive_envelope_id,
    derive_event_id,
    derive_goal_id,
    derive_memory_id,
    derive_proposal_id,
    derive_relationship_id,
    derive_request_id,
    derive_run_id,
    derive_scoped_id,
    derive_world_id,
    reject_operational_identifier,
)
from simulation.models import (
    DERIVATION_VERSION,
    LLM_REPLAY_REQUIREMENT,
    ExportMetadata,
    RunId,
    SimulationExport,
    SimulationRunConfig,
)
from simulation.randomness import (
    StreamScope,
    create_named_stream,
    create_rng,
    sample_stream,
)
from simulation.serialization import (
    DomainSerializationError,
    decode_domain,
    encode_domain,
)

__all__ = [
    "DERIVATION_VERSION",
    "LLM_REPLAY_REQUIREMENT",
    "DomainSerializationError",
    "ExportMetadata",
    "LogicalClock",
    "RunConfigurationPort",
    "RunId",
    "SimulationExport",
    "SimulationRunConfig",
    "StreamScope",
    "Tick",
    "admit_agent_command",
    "create_named_stream",
    "create_rng",
    "decode_domain",
    "derive_belief_id",
    "derive_entity_id",
    "derive_envelope_id",
    "derive_event_id",
    "derive_goal_id",
    "derive_memory_id",
    "derive_proposal_id",
    "derive_relationship_id",
    "derive_request_id",
    "derive_run_id",
    "derive_scoped_id",
    "derive_world_id",
    "describe_run",
    "encode_domain",
    "export_metadata",
    "log_invalid_setup",
    "log_replay_mismatch",
    "log_run_configured",
    "make_export",
    "reject_operational_identifier",
    "require_tick",
    "sample_stream",
]
