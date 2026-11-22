# Disease Mechanics

[← Measurement instruments](measurement-instruments.md) · [Back to README](../README.md) · [Next Page →](economic-cascades.md)

Optional abstract disease channel owned by V4-34 under the reserved
`epidemics` capability. One fictional condition per enabled run. The engine
holds objective infection state; agents and observer presentation never receive
diagnosis, phase, immune status, or transmission attribution.

## Scope

| Transition | Behavior |
| --- | --- |
| Exposure / transmission | Abstract per-opportunity draws over discrete settled co-presence |
| Latent | Incubation-like private phase with a due tick |
| Active | Optional coarse owner-only `unwell` symptom cue |
| Recovery / mortality | Active ends in recovery (optional run-scoped immunity) or ordinary death |
| Disabled | No private rows, no cue, legacy version selection unchanged |

Not modeled: real pathogens, medical calibration, travel-path exposure,
intervention optimizers, automatic behavior response, or dedicated HTTP/UI
overlays.

## Configuration

Requires `runner-config-v58`, `epidemics=true`, owned
`infrastructure_networks` (and its collective-projects prerequisite), plus the
exact `disease_mechanics` sibling:

```json
{
  "policy_id": "disease-mechanics.v1",
  "initial_latent_entity_ids": ["body-a"],
  "exposure_chance_milli": 1000,
  "transmission_chance_milli": 1000,
  "symptom_chance_milli": 1000,
  "mortality_chance_milli": 0,
  "latent_ticks": 1,
  "active_ticks": 2,
  "immunity_after_recovery": true
}
```

Milli chances are integers in `[0, 1000]`. Latent/active durations are positive
integers. Founders must be unique living scenario bodies in lexical order.
Flag/spec mismatch, missing infrastructure, or older runner versions fail
closed before runtime objects are created.

## Perception and reads

- Owners may see `ObservedSelf.symptom_cue = "unwell"` or its absence.
- Co-presence and ordinary death events remain ordinary observable evidence.
- Private `disease_state_changed` net effects are redacted from observer list,
  detail, tick summary, frame, and WebSocket surfaces (`observer_event_not_found`
  on direct lookup). Authorized objective inspection stays unfiltered.
- Observer death presentation carries no disease cause/family payload.

## Persistence and replay

Enabled runs select reserved write pair event schema **24** / codec **`v22`**.
Checkpoints store a mandatory `disease_mechanics` section (`rows` +
`policy_sha256`). Historical replay folds recorded effects without live policy
draws. Continuation at the durable head requires a verified matching
`DiseaseMechanicsSpec` on `ReplayRequest`; without it the result stays
read-only and `open_durable` rejects. Mismatched policy digests fail closed.
No Alembic migration; head remains `0017`.

## Experiment

Off-gate `disease_mechanics@1` exposes two paired arms that differ only at
`transmission_chance_milli` (`no-transmission` = 0, `contact-enabled` = 1000).
Both keep disease enabled, shared seed/topology/founders, eight-tick Wait
horizon, mortality 0, latent 1, active 2, immunity on. Fixture success is not
epidemiological validation.

```bash
uv run --frozen --python 3.12.14 pytest tests/unit/test_disease_*.py -q
```

Disposable-DB durability (skipped when unset):

```bash
PALIMPSEST_TEST_DATABASE_URL=... uv run --frozen --python 3.12.14 \
  pytest -m integration tests/integration/test_disease_durable_replay.py -q
```

## Known limitations

- Single fictional condition; no multi-pathogen catalog.
- No real-world prevalence, forecasting, or efficacy claims.
- No new command, public disease route, metric family, or Godot overlay.
- Agents cannot query infection state or confirm transmission.
- V4-35 may add subjective explanations and ordinary interventions on
  `runner-config-v59`, but it never adds a fictional cure or changes objective
  disease policy.

## See Also

- [Configuration](configuration.md)
- [Architecture](architecture.md)
- [Physical Simulation](physical-simulation.md)
- [Measurement instruments](measurement-instruments.md)
- [Medical beliefs](medical-beliefs.md)
- [Persistence](persistence.md)
