"""HTTP route modules."""

from api.routes.debugger import router as debugger_router
from api.routes.branches import router as branches_router
from api.routes.health import router as health_router
from api.routes.inspection import router as inspection_router
from api.routes.observer import router as observer_router
from api.routes.observer_stream import router as observer_stream_router
from api.routes.replay import router as replay_router
from api.routes.simulations import router as simulations_router
from api.routes.streams import router as streams_router
from api.routes.version import router as version_router

__all__ = [
    "branches_router",
    "debugger_router",
    "health_router",
    "inspection_router",
    "observer_router",
    "observer_stream_router",
    "replay_router",
    "simulations_router",
    "streams_router",
    "version_router",
]
