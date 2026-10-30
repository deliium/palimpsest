"""A committed metric transition must not fail while logging its new version."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from experiments.persistence import MetricSetLifecycle
from persistence import metric_sqlalchemy
from persistence.orm import MetricSetOrm


async def test_metric_transition_logs_expected_and_resulting_versions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = MetricSetOrm(
        run_id="metric-run",
        metric_set_id="metric-set",
        lifecycle_state=MetricSetLifecycle.PENDING.value,
        evidence_manifest_hash="c" * 64,
        lifecycle_version=0,
    )
    session = AsyncMock(spec=AsyncSession)
    session.get.return_value = row
    logger = Mock()

    @asynccontextmanager
    async def scope(
        _factory: async_sessionmaker[AsyncSession],
    ) -> AsyncIterator[AsyncSession]:
        yield cast(AsyncSession, session)

    monkeypatch.setattr(metric_sqlalchemy, "session_scope", scope)
    monkeypatch.setattr(metric_sqlalchemy, "_LOGGER", logger)
    repository = metric_sqlalchemy.create_metric_set_repository(
        async_sessionmaker[AsyncSession]()
    )

    result = await repository.transition_metric_set(
        run_id="metric-run",
        metric_set_id="metric-set",
        expected_version=0,
        to_state=MetricSetLifecycle.RUNNING,
    )

    assert result.lifecycle_state is MetricSetLifecycle.RUNNING
    assert result.lifecycle_version == 1
    session.commit.assert_awaited_once()
    logger.info.assert_called_once_with(
        "metric_set_transitioned",
        operation="transition_metric_set",
        run_id="metric-run",
        revision_id="metric-set",
        lifecycle_code=MetricSetLifecycle.RUNNING.value,
        version=0,
        resulting_version=1,
    )
