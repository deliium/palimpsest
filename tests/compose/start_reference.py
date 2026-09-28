"""Start the reference world on a running API and wait until camp is visible.

Location ids are on the observer state frame. The manifest confirms the run
is readable. This script does not use the empty runner-config-v2 body.
"""

from __future__ import annotations

import argparse
import base64
import logging
import sys
import uuid

import httpx

from experiments.reference_scenario import build_reference_scenario
from simulation.runner_serialization import (
    encode_runner_config,
    runner_config_fingerprint,
)

_LOGGER = logging.getLogger("palimpsest.compose.reference")
_MAX_TICKS = 6


def start_reference(base_url: str, *, run_id: str | None = None) -> str:
    """Post the reference bundle, start it, and tick until camp is listed."""
    chosen = run_id or f"ref-{uuid.uuid4().hex[:12]}"
    bundle = build_reference_scenario()
    payload = encode_runner_config(bundle.config)
    fingerprint = runner_config_fingerprint(bundle.config)
    schema = bundle.config.schema_version
    body = {
        "run_id": chosen,
        "config_schema_version": schema,
        "config_fingerprint": fingerprint,
        "config_payload_b64": base64.b64encode(payload).decode("ascii"),
    }
    root = base_url.rstrip("/")
    _LOGGER.info(
        "reference_start_posted run_id=%s schema=%s",
        chosen,
        schema,
    )
    with httpx.Client(base_url=root, timeout=30.0) as client:
        created = client.post("/v1/simulations", json=body)
        if created.status_code not in {200, 201}:
            raise RuntimeError(f"reference_create_failed status={created.status_code}")
        started = client.post(f"/v1/simulations/{chosen}/start")
        if started.status_code not in {200, 202}:
            raise RuntimeError(f"reference_start_failed status={started.status_code}")
        for _ in range(_MAX_TICKS):
            ticked = client.post(f"/v1/simulations/{chosen}/tick")
            if ticked.status_code != 200:
                raise RuntimeError(f"reference_tick_failed status={ticked.status_code}")
            manifest = client.get(
                f"/v1/simulations/{chosen}/observer/manifest",
            )
            state = client.get(f"/v1/simulations/{chosen}/observer/state")
            if manifest.status_code != 200 or state.status_code != 200:
                continue
            locations = state.json().get("world", {}).get("locations", [])
            ids = {item.get("location_id") for item in locations}
            if "loc-camp" in ids and manifest.json().get("layout_id") == "reference-v1":
                _LOGGER.info("reference_camp_visible run_id=%s", chosen)
                return chosen
    raise RuntimeError("reference_camp_missing")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        print(start_reference(args.base_url, run_id=args.run_id))
    except RuntimeError as exc:
        _LOGGER.error("reference_start_failed reason_code=%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
