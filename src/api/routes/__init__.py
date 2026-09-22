"""HTTP route modules."""

from api.routes.health import router as health_router
from api.routes.inspection import router as inspection_router
from api.routes.replay import router as replay_router
from api.routes.simulations import router as simulations_router
from api.routes.streams import router as streams_router

__all__ = [
    "health_router",
    "inspection_router",
    "replay_router",
    "simulations_router",
    "streams_router",
]
