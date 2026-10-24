"""Start the real Experiment BL generational run on a published API."""

from __future__ import annotations

import argparse
import base64
import logging
import sys
import uuid
from dataclasses import dataclass

import httpx

from experiments.generational_runner_scenario import generational_runner_scenario
from simulation.runner_models import SimulationRunnerConfig
from simulation.runner_serialization import (
    encode_runner_config,
    runner_config_fingerprint,
)

_LOGGER = logging.getLogger("palimpsest.compose.generational")
_MAX_TICKS = 16
_CONDITION_ID = "bl-generational-unassisted"


@dataclass(frozen=True, slots=True)
class GenerationalExpectation:
    run_id: str
    boundary_tick: int
    admitted: int
    living: int
    dead: int
    max_generation_index: int
    stage_change_count: int


def bl_config() -> SimulationRunnerConfig:
    definition = generational_runner_scenario(seed=23, max_ticks=_MAX_TICKS)
    for condition in definition.conditions:
        if condition.condition_id == _CONDITION_ID:
            return condition.runner_config
    raise RuntimeError("generational_bl_condition_missing")


def start_bl_generational(
    base_url: str,
    *,
    control_token: str = "",
    inspection_token: str = "",
    run_id: str | None = None,
) -> GenerationalExpectation:
    chosen = run_id or f"bl-gen-{uuid.uuid4().hex[:12]}"
    config = bl_config()
    payload = encode_runner_config(config)
    body = {
        "run_id": chosen,
        "config_schema_version": config.schema_version,
        "config_fingerprint": runner_config_fingerprint(config),
        "config_payload_b64": base64.b64encode(payload).decode("ascii"),
    }
    root = base_url.rstrip("/")
    control = {"x-palimpsest-token": control_token} if control_token else {}
    inspection = {"x-palimpsest-token": inspection_token} if inspection_token else {}
    with httpx.Client(base_url=root, timeout=120.0) as client:
        created = client.post("/v1/simulations", json=body, headers=control)
        if created.status_code not in {200, 201}:
            raise RuntimeError(
                f"generational_create_failed status={created.status_code}"
            )
        started = client.post(f"/v1/simulations/{chosen}/start", headers=control)
        if started.status_code not in {200, 202}:
            raise RuntimeError(
                f"generational_start_failed status={started.status_code}"
            )
        boundary = _MAX_TICKS
        for _ in range(_MAX_TICKS):
            ticked = client.post(f"/v1/simulations/{chosen}/tick", headers=control)
            if ticked.status_code == 409:
                break
            if ticked.status_code != 200:
                raise RuntimeError(
                    f"generational_tick_failed status={ticked.status_code}"
                )
            boundary = int(ticked.json().get("ticks_committed", boundary))
        demographics = client.get(
            f"/v1/simulations/{chosen}/observer/demographics",
            params={"tick": boundary},
            headers=inspection,
        )
        if demographics.status_code != 200:
            raise RuntimeError(
                f"generational_demographics_failed status={demographics.status_code}"
            )
        document = demographics.json()
        if document.get("availability") != "available":
            raise RuntimeError("generational_demographics_unavailable")
        population = document["population"]
        if population["dead"] < 1:
            raise RuntimeError("generational_death_missing")
        if population["max_generation_index"] < 2:
            raise RuntimeError("generational_two_generations_missing")
        events = client.get(
            f"/v1/simulations/{chosen}/observer/events",
            params={
                "event_type": "LIFECYCLE_STAGE_CHANGED",
                "limit": 50,
                "catch_up": True,
            },
            headers=inspection,
        )
        if events.status_code != 200:
            raise RuntimeError(
                f"generational_stage_events_failed status={events.status_code}"
            )
        stage_change_count = len(events.json().get("events", []))
        if stage_change_count < 1:
            raise RuntimeError("generational_stage_change_missing")
        return GenerationalExpectation(
            run_id=chosen,
            boundary_tick=int(document["resolved_tick"]),
            admitted=int(population["admitted"]),
            living=int(population["living"]),
            dead=int(population["dead"]),
            max_generation_index=int(population["max_generation_index"]),
            stage_change_count=stage_change_count,
        )


def start_generational(
    base_url: str,
    *,
    control_token: str = "",
    inspection_token: str = "",
    run_id: str | None = None,
) -> GenerationalExpectation:
    """Layout-compatible generational reference run for browser acceptance."""
    from dataclasses import replace

    from experiments.reference_scenario import build_reference_scenario
    from simulation.new_agent_initialization import (
        default_new_agent_initialization_spec,
    )
    from simulation.runner_models import (
        RUNNER_SCHEMA_VERSION_V26,
        MortalityMode,
        RunnerStopPolicy,
        V3CapabilityFlags,
        example_population_lifecycle_spec,
    )

    chosen = run_id or f"gen-{uuid.uuid4().hex[:12]}"
    lifecycle = example_population_lifecycle_spec(
        lifespan_ticks=12,
        max_population=12,
        policy_id="fixed_interval_entry",
    )
    lifecycle = replace(
        lifecycle,
        demographic_policy_params={
            **lifecycle.demographic_policy_params,
            "spawn_location_id": "loc-camp",
        },
    )
    config = replace(
        build_reference_scenario().config,
        schema_version=RUNNER_SCHEMA_VERSION_V26,
        mortality_mode=MortalityMode.DISABLED,
        stop_policy=RunnerStopPolicy(max_ticks=_MAX_TICKS),
        v3_capability_flags=V3CapabilityFlags(generational_population=True),
        population_lifecycle=lifecycle,
        new_agent_initialization=default_new_agent_initialization_spec(),
    )
    payload = encode_runner_config(config)
    body = {
        "run_id": chosen,
        "config_schema_version": config.schema_version,
        "config_fingerprint": runner_config_fingerprint(config),
        "config_payload_b64": base64.b64encode(payload).decode("ascii"),
    }
    root = base_url.rstrip("/")
    control = {"x-palimpsest-token": control_token} if control_token else {}
    inspection = {"x-palimpsest-token": inspection_token} if inspection_token else {}
    with httpx.Client(base_url=root, timeout=120.0) as client:
        created = client.post("/v1/simulations", json=body, headers=control)
        if created.status_code not in {200, 201}:
            raise RuntimeError(
                f"generational_create_failed status={created.status_code}"
            )
        started = client.post(f"/v1/simulations/{chosen}/start", headers=control)
        if started.status_code not in {200, 202}:
            raise RuntimeError(
                f"generational_start_failed status={started.status_code}"
            )
        boundary = _MAX_TICKS
        for _ in range(_MAX_TICKS):
            ticked = client.post(f"/v1/simulations/{chosen}/tick", headers=control)
            if ticked.status_code == 409:
                break
            if ticked.status_code != 200:
                raise RuntimeError(
                    f"generational_tick_failed status={ticked.status_code}"
                )
            boundary = int(ticked.json().get("ticks_committed", boundary))
        demographics = client.get(
            f"/v1/simulations/{chosen}/observer/demographics",
            params={"tick": boundary},
            headers=inspection,
        )
        if demographics.status_code != 200:
            raise RuntimeError(
                f"generational_demographics_failed status={demographics.status_code}"
            )
        document = demographics.json()
        if document.get("availability") != "available":
            raise RuntimeError("generational_demographics_unavailable")
        population = document["population"]
        if population["max_generation_index"] < 1:
            raise RuntimeError("generational_two_generations_missing")
        return GenerationalExpectation(
            run_id=chosen,
            boundary_tick=int(document["resolved_tick"]),
            admitted=int(population["admitted"]),
            living=int(population["living"]),
            dead=int(population["dead"]),
            max_generation_index=int(population["max_generation_index"]),
            stage_change_count=0,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--control-token", default="")
    parser.add_argument("--inspection-token", default="")
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        expectation = start_generational(
            args.base_url,
            control_token=args.control_token,
            inspection_token=args.inspection_token,
            run_id=args.run_id,
        )
    except RuntimeError as exc:
        _LOGGER.error("generational_start_failed reason_code=%s", exc)
        return 1
    print(
        f"run_id={expectation.run_id} boundary={expectation.boundary_tick} "
        f"admitted={expectation.admitted} living={expectation.living} "
        f"dead={expectation.dead} "
        f"max_generation={expectation.max_generation_index} "
        f"stage_changes={expectation.stage_change_count}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
