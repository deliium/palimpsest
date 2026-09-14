"""Live database lifecycle checks against a disposable test database."""

from __future__ import annotations

import pytest
from sqlalchemy import text

from infrastructure.database import DatabaseResources, check_readiness, session_scope

pytestmark = pytest.mark.integration


async def test_readiness_and_session_lifecycle_against_test_database(
    database_resources: DatabaseResources,
) -> None:
    await check_readiness(database_resources.engine)
    async with session_scope(database_resources.session_factory) as session:
        result = await session.execute(text("SELECT 1"))
        assert result.scalar_one() == 1
    async with session_scope(database_resources.session_factory) as second:
        result = await second.execute(text("SELECT 1"))
        assert result.scalar_one() == 1
