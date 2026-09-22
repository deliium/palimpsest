"""Trusted experiment orchestration package.

Coordinates public ``simulation`` and read-only ``analysis`` contracts.
Domain packages (world, agents, cognition, memory, social) must never import
this package or receive its collectors, truth specs, or results.
"""

from experiments.catalog import (
    experiment_a_memory,
    experiment_b_imagination,
    experiment_c_mortality,
    experiment_d_drives,
    experiment_e_false_story,
)
from experiments.collectors import (
    CollectorMetricDocument,
    collect_arm_summary,
    collect_drive_outcomes,
    collect_for_experiment,
    collect_imagination_outcomes,
    collect_memory_drift,
    collect_mortality_outcomes,
    collect_propagation,
    collect_trajectory_stats,
)
from experiments.coordinator import (
    ExperimentArmResult,
    ExperimentAssignment,
    ExperimentCoordinator,
    materialize_assignments,
)
from experiments.interventions import (
    StoryIntervention,
    StoryInterventionArbiter,
    StoryTruthSpec,
    make_false_story_intervention,
)
from experiments.memory_repository import InMemoryExperimentRecordRepository
from experiments.models import (
    ExperimentCondition,
    ExperimentDefinition,
    ExperimentSeedMatrix,
    condition_fingerprint,
    definition_fingerprint,
)
from experiments.persistence import (
    EXPERIMENT_RECORD_SCHEMA_VERSION,
    ExperimentAssignmentRecord,
    ExperimentDefinitionRecord,
    ExperimentRecordRepository,
    ExperimentResultRecord,
)

__all__ = [
    "EXPERIMENT_RECORD_SCHEMA_VERSION",
    "CollectorMetricDocument",
    "ExperimentArmResult",
    "ExperimentAssignment",
    "ExperimentAssignmentRecord",
    "ExperimentCondition",
    "ExperimentCoordinator",
    "ExperimentDefinition",
    "ExperimentDefinitionRecord",
    "ExperimentRecordRepository",
    "ExperimentResultRecord",
    "ExperimentSeedMatrix",
    "InMemoryExperimentRecordRepository",
    "StoryIntervention",
    "StoryInterventionArbiter",
    "StoryTruthSpec",
    "collect_arm_summary",
    "collect_drive_outcomes",
    "collect_for_experiment",
    "collect_imagination_outcomes",
    "collect_memory_drift",
    "collect_mortality_outcomes",
    "collect_propagation",
    "collect_trajectory_stats",
    "condition_fingerprint",
    "definition_fingerprint",
    "experiment_a_memory",
    "experiment_b_imagination",
    "experiment_c_mortality",
    "experiment_d_drives",
    "experiment_e_false_story",
    "make_false_story_intervention",
    "materialize_assignments",
]
