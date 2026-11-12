# V4 Versioning and Compatibility

V4-01 declares a version vocabulary without implementing any V4 behavior. Every
number below is an executable pin in `simulation.compatibility`,
`simulation.runner_models`, `world.events`, `observer.version`,
`analysis.specifications`, or `simulation.v4_architecture`.

## Current surfaces

| Surface | Current value | Owner |
| --- | --- | --- |
| Default runner write | `runner-config-v4` | `simulation.runner_models` |
| Latest feature runner | `runner-config-v55` | `simulation.runner_models` |
| Accepted runner range | `runner-config-v1` … `runner-config-v56` | `simulation.runner_serialization` |
| Accepted scaffolding runner | `runner-config-v56` (never emitted) | `simulation.runner_models` |
| Default result write | `runner-result-v2` | `simulation.runner_models` |
| Generational result | `runner-result-v3` | `simulation.runner_models` |
| Event schema | `EVENT_SCHEMA_REPLAY_V22` (22) | `world.events` |
| Persistence codec | `v20` | `simulation.persistence` |
| Alembic head | `0017` | `alembic/versions` |
| Commands | 43 | `world._rules` |
| Observer protocol | `observer-protocol-v1` | `observer.version` |
| Observer layout | `observer-layout-v1` | `observer.version` |
| Observer semantic types | 73 | `observer.version` |
| Metric catalog | 136 families | `analysis.specifications` |
| HTTP API | `/v1` | `api` |

## Rules

1. **Additive first.** Extend a document with optional siblings before inventing a
   new identifier; introduce a new write version only when the shape cannot stay
   additive.
2. **Exact keys.** Runner configuration documents use exact key sets. Missing,
   unknown, duplicate, or wrong-typed keys are serialization errors, never
   defaults.
3. **Accepted-set discipline.** A new write version joins
   `SUPPORTED_RUNNER_SCHEMA_VERSIONS` (or the matching accepted set) in the same
   change that adds its encoder and decoder.
4. **Legacy decode.** An older payload never stops decoding. New fields
   synthesize their documented defaults for older versions.
5. **Co-landing.** A new write version lands admission, codec, replay, and tests
   together. Half a wire version is not a version.
6. **No silent widening.** An existing schema identifier never gains a new key
   without a new identifier.

## `runner-config-v56`

`runner-config-v56` uses the active v55 family root keyset plus exactly one
sibling: `v4_capability_flags`, an object with the twelve closed booleans
declared by `V4CapabilityFlags`. The generational siblings
(`population_lifecycle`, `new_agent_initialization`, `generational_run`) follow
the selected family: when a generational run is present, v55's prerequisites
remain mandatory; when it is absent, they are absent exactly as on the lower
family. v56 never adds a generational run by itself.

- V4-01 accepts it for explicit scaffolding identity. Feature selection and
  matrix finalization never emit it on their own.
- Default writes stay `runner-config-v4`; the latest feature runner stays
  `runner-config-v55`.
- Every V4 flag is unowned. Enabling any flag requires v56 and then fails closed
  at `SimulationRunner.from_config` with `capability_unimplemented` and
  `stage="v4_capability_flags"`.
- Decoding a v1–v55 payload synthesizes `V4CapabilityFlags()` (all off).

## Reserved write pairs

A reservation is a number, not semantics. `simulation.versioning` reserves:

| Context | Event schema | Codec | Prerequisite flags | Owner |
| --- | --- | --- | --- | --- |
| `infrastructure_networks` | 23 | `v21` | `infrastructure_networks`, `supply_chains` | `world` |
| `epidemics` | 24 | `v22` | `epidemics` | `world` |
| `ecological_feedback` | 25 | `v23` | `ecological_feedback` | `world` |
| `disasters` | 26 | `v24` | `disasters` | `world` |

The other nine contexts are declared event-reusing
(`V4_EVENT_REUSING_CONTEXTS`): they must express their phenomena through existing
commands, events, records, and speech. A later plan that activates a reservation
must still prove effect-complete details, replay, and a persistence need.

## Observer negotiation

`GET /version` is unauthenticated and additive. It reports:

- `protocol_version` (the active protocol),
- `supported_observer_protocols` (currently `["observer-protocol-v1"]`),
- `observer_layout_version`,
- `observer_capabilities` (four implemented names),
- `observer_reserved_capabilities` (six reserved names).

Advertised and reserved sets are disjoint and advisory. `observer-protocol-v2` is
reserved but not served, and the clients accept only v1. `/version` never exposes
capability-flag values, configuration payloads, or run content. A v2 protocol may
be served only after a plan lands its frames, mirror pins, and client support.

## Deprecation

- No V1–V3 surface is deprecated by V4-01.
- A deprecation requires a documented replacement, a dual-read window, and a
  passing legacy decode test for the retired version.
- Removing an accepted version is a compatibility break and needs an explicit,
  scoped architectural decision.

Current catalog: 220 metric families; 43 commands; 73 observer semantic types; Alembic `0017`.
