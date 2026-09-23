"""Unit tests for cognition-trace persistence factory (no DB)."""

from __future__ import annotations

import pytest

from persistence import create_cognition_trace_repository
from persistence.errors import PersistenceAdapterError


def test_create_cognition_trace_repository_requires_session_factory() -> None:
    with pytest.raises(PersistenceAdapterError) as exc:
        create_cognition_trace_repository(None)
    assert exc.value.code == "missing_session_factory"
