# mypy: ignore-errors
"""No objective/owner leakage in cascade rows, snapshots, or routes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from analysis.economic_cascades_analysis import harvest_economic_cascades_analysis
from analysis.economic_cascades_contract import CASCADE_FORBIDDEN_KEYS
from experiments.economic_cascades_publication import (
    compose_economic_cascades_snapshot,
)
from simulation.economic_cascades_codec import encode_economic_cascades_snapshot
from tests.unit.test_economic_cascades_analysis import (
    _harvest_events,
    _recipes,
    _stage,
)

pytestmark = pytest.mark.unit

_OWNER_FIELDS = {"owner_token", "actor_token", "body_token", "agent_token"}


def _analysis():
    return harvest_economic_cascades_analysis(
        events=_harvest_events(),
        recipe_specs=_recipes(),
        stages=[_stage(completions=1), _stage(completions=0, sequence=1)],
    )


def test_objective_and_dependency_rows_do_not_claim_a_chain_state() -> None:
    analysis = _analysis()
    for row in (*analysis.disruptions, *analysis.stages, *analysis.edges):
        names = set(row.__dataclass_fields__)
        assert "chain_token" not in names
        assert "state" not in names
        assert not (names & CASCADE_FORBIDDEN_KEYS)


def test_analytical_rows_carry_no_owner_or_body_fields() -> None:
    analysis = _analysis()
    for row in (*analysis.episodes, *analysis.chains, *analysis.propagation_rows):
        names = set(row.__dataclass_fields__)
        assert not (names & _OWNER_FIELDS)


def test_snapshot_payload_has_no_forbidden_vocabulary() -> None:
    analysis = _analysis()
    snapshot = compose_economic_cascades_snapshot(analysis, run_id="run-1")
    payload = encode_economic_cascades_snapshot(snapshot).decode()
    for key in CASCADE_FORBIDDEN_KEYS:
        assert f'"{key}"' not in payload
    assert "body-" not in payload


@pytest.mark.asyncio
async def test_route_responses_have_no_forbidden_keys(tmp_path: Path) -> None:
    from tests.unit.test_economic_cascades_routes import (
        HEADERS,
        PATHS,
        RUN,
        _client,
        _seed,
    )

    _seed(tmp_path)
    async with _client(tmp_path) as client:
        for path in PATHS:
            response = await client.get(path.format(run_id=RUN), headers=HEADERS)
            body = json.dumps(response.json())
            for key in CASCADE_FORBIDDEN_KEYS:
                assert f'"{key}"' not in body
            assert "body-" not in body
