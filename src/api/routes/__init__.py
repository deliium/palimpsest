"""HTTP route modules."""

from api.routes.borders import router as borders_router
from api.routes.branches import router as branches_router
from api.routes.civilization import router as civilization_router
from api.routes.debugger import router as debugger_router
from api.routes.delegation_representation import (
    router as delegation_representation_router,
)
from api.routes.diplomacy import router as diplomacy_router
from api.routes.dispute import router as dispute_router
from api.routes.evidence_testimony import router as evidence_testimony_router
from api.routes.formal_rule import router as formal_rule_router
from api.routes.health import router as health_router
from api.routes.inspection import research_router as research_router
from api.routes.inspection import router as inspection_router
from api.routes.lineage import router as lineage_router
from api.routes.macro_society import router as macro_society_router
from api.routes.migration_displacement import (
    router as migration_displacement_router,
)
from api.routes.observer import router as observer_router
from api.routes.observer_stream import router as observer_stream_router
from api.routes.organization import router as organization_router
from api.routes.organized_conflict import router as organized_conflict_router
from api.routes.replay import router as replay_router
from api.routes.research_matrix import router as research_matrix_router
from api.routes.simulations import router as simulations_router
from api.routes.streams import router as streams_router
from api.routes.version import router as version_router

__all__ = [
    "borders_router",
    "branches_router",
    "civilization_router",
    "debugger_router",
    "delegation_representation_router",
    "diplomacy_router",
    "dispute_router",
    "evidence_testimony_router",
    "formal_rule_router",
    "health_router",
    "inspection_router",
    "lineage_router",
    "macro_society_router",
    "migration_displacement_router",
    "observer_router",
    "observer_stream_router",
    "organization_router",
    "organized_conflict_router",
    "replay_router",
    "research_matrix_router",
    "research_router",
    "simulations_router",
    "streams_router",
    "version_router",
]
