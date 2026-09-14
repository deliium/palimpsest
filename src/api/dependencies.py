"""Injectable FastAPI dependencies. Do not mutate domain state."""

from __future__ import annotations

from typing import cast

from fastapi import Request

from infrastructure.database import DatabaseResources
from infrastructure.settings import Settings


def get_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def get_database_resources(request: Request) -> DatabaseResources:
    return cast(DatabaseResources, request.app.state.database)
