"""Distribution and baked presentation versions."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends

from api.dependencies import get_settings
from api.presentation_static import version_payload
from infrastructure.logging import get_logger
from infrastructure.settings import Settings

router = APIRouter()
_LOGGER = get_logger("api.routes.version")


@router.get("/version")
def get_version(
    settings: Settings = Depends(get_settings),
) -> dict[str, str | bool | None]:
    started = time.perf_counter()
    payload = version_payload(settings)
    _LOGGER.info(
        "route_version",
        status=200,
        duration_ms=round((time.perf_counter() - started) * 1000, 3),
    )
    return payload
