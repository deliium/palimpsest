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
from experiments.collectors import CollectorMetricDocument, collect_arm_summary
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
from experiments.models import (
    ExperimentCondition,
    ExperimentDefinition,
    ExperimentSeedMatrix,
    condition_fingerprint,
    definition_fingerprint,
)

__all__ = [
    "CollectorMetricDocument",
    "ExperimentArmResult",
    "ExperimentAssignment",
    "ExperimentCondition",
    "ExperimentCoordinator",
    "ExperimentDefinition",
    "ExperimentSeedMatrix",
    "StoryIntervention",
    "StoryInterventionArbiter",
    "StoryTruthSpec",
    "collect_arm_summary",
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
