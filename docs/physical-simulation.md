# V1 Physical Simulation

[← LLM providers](llm-providers.md) · [Back to README](../README.md) · [Next Page →](configuration.md)

Objective physical rules for a small discrete world (about 5–10 agents, 10–20 locations, several resource kinds). Physical death is authoritative in `WorldEngine`. Subjective fear-of-death appraisal, beliefs, goals, and drive activations live in cognition only — they never rewrite physical rules or declare an agent dead. See [Cognition and agent runtime](cognition-runtime.md).

## Topology and capacities

- Locations form an undirected connected graph with ordered unique adjacency (no self-edges, dangling edges, or asymmetric edges).
- Each location has positive `body_capacity`, non-negative `item_capacity`, base ambient temperature, shelter ∈ [0, 1], and base visibility ∈ [0, 1].
- All bodies (including dead) count toward body capacity. Ground items count toward item capacity; held items and resource nodes do not.
- Every portable item has positive integer load and exactly one placement (ground or held). Body `carry_capacity` bounds Take/Give.

## Conservation

- Item identity is conserved: ground, held, or consumed by an immutable event.
- Resource quantity never goes negative; harvest/drink decrement the amount recorded on the event; regeneration cannot exceed maximum.
- Extraction requires quantity ≥ 1.0; values in (0, 1) are present but depleted for Search and resource Drink.

## Time, weather, visibility

- One tick = one simulated hour. `hour = tick % 24`; day hours 06–17, night 18–05.
- Effective visibility = clamp(location_base × phase × weather, 0, 1): day 1.0 / night 0.5; clear 1.0, cloudy 0.9, rain 0.7, storm 0.5.
- Contents (ground items, resources, other bodies) expose only when visibility ≥ 0.5. Exits, self, weather, hour, phase, and visibility modifier always expose.
- Weather stores condition only. Ambient = location base + weather offset + phase offset. Transitions when `(tick + 1) % 6 == 0` per location from the ordered transition matrix.
- Agent-facing projections use dedicated observation DTOs (not objective models): exact self physiology may appear via `ObservedSelf`; nearby bodies are coarse; resource max/regen and location capacities never appear. Full matrix and audience rules: [Architecture — Perception boundary](architecture.md#perception-boundary).

## Observation timing

An observation for open tick `N` is projected from the tick-start snapshot plus committed occurrences from tick `N−1`. Current-tick submissions and outcomes never appear early. Eventless prior windows are empty but still carried for live/restored parity. Live and restored engines at the same tick emit equal observations (including canonical serialization).

**Domain-contract evolution gate:** any future Observation / command / communications wire bump must keep live/restored observation parity green (`test_live_and_restored_observations_match_with_prior_events` and related checkpoint tests). Policy details: [Architecture — Domain-contract evolution](architecture.md#domain-contract-evolution-observation--commands--communications).

## Actions (all applied / rejected / conflicted — none deferred)

| Action | Summary |
| --- | --- |
| Move | Adjacent free body slot; +5 fatigue |
| Search | Eligible local resource + free ground slot; Bernoulli success; miss is event-only; success extracts 1.0 and creates a ground item |
| Take / Drop / Give | Capacity-checked atomic transfers |
| Eat / Drink | Consume held food / held water or local water resource; hunger −30 / thirst −40 |
| Sleep | Fatigue −30 this tick (shelter does not gate). Recovery does not depend on consolidation mode. |
| Attack | Hit 0.75, damage [10, 20]; miss event-only; lethal hit emits Attacked then Died under the same action cause |
| Flee | Success 0.80 then uniform eligible destination; +10 fatigue on success |
| Help | Target health +10 (cap 100), helper +5 fatigue; no revival |
| Wait / Talk / Ask / Tell | Event-only; still receive autonomous physiology |

Structural impossibility is REJECTED (starting state) or CONFLICTED (earlier effect). Stochastic misses are APPLIED without mutation.

## Learnable skills

`SkillLearningMode` defaults to `DISABLED`. Off uses today's search, move, flee, and help formulas and does not call the skill helpers. `DETERMINISTIC` is opt-in and is not a capability flag. Objective levels live in a private ledger that only `WorldEngine` reads, and only while resolving an action that already has a probability or an efficiency constant. A level is a float in `[0, 1]`, quantized after every write with `round(value / 1e-6) * 1e-6`. Every enabled body starts at `0` in each domain. Level `0` is identity with today's constants.

Closed domains: `foraging`, `navigation`, `resource_detection`, `crafting`, `building`, `healing`, `communication`, `teaching`.

Search splits by the command. Untargeted search is foraging and multiplies only `search_base_probability`. Targeted search is resource detection and multiplies only the visibility term. The multiplier is `(1 + probability_gain * level)` with `probability_gain` `0.50`, then `clamp_unit_interval`. The Bernoulli purpose stays `search_success`. Move fatigue and flee fatigue are divided by `(1 + efficiency_gain * navigation_level)` before `round_physical`. Help health gain is multiplied by `(1 + efficiency_gain * healing_level)` before `round_physical`. Helper fatigue is unchanged. At level `0` those values stay `5.0`, `10.0`, and `10.0`. Crafting, building, and communication keep a multiplier of exactly `1`. Teaching scales instruction transfer only.

Growth folds committed facts. One tick uses start-of-tick levels and the start-of-tick world for witnesses. Deltas for that tick are summed per body and domain, quantized once, then clamped to `[0, 1]`. Practice is an admitted applied action: untargeted search, targeted search, move, flee, help, delivered talk/ask/tell, and delivered instruction on the speaker's teaching domain. Success adds `success_rate` on that domain. Stochastic search or flee misses add `failure_rate`. Rejected, conflicted, and deferred actions add nothing, and a rejected action is not a failure. Instruction is a delivered utterance with exactly one `instruct` relation whose object is one domain token. Transfer to the recipient is `instruction_rate * teacher_teaching_level` from the teacher's start-of-tick teaching level. A teacher at `0` transfers `0` and still practices teaching. A living enabled body at the action's origin location witnesses a successful public search, move, flee, or help when that location's effective visibility is at least `0.5`, and gains `observation_rate` on that action's domain. Same-tick moves do not change the witness set. Talk, ask, and tell are recipient-private. Crafting and building grow only through instruction. Attack adds nothing. A disabled actor in a mixed run uses the bypass formulas and is not written into the ledger.

Replay rebuilds the ledger by grouping committed events by tick, projecting earlier ticks, then folding tick T. World-snapshot JSON has no skill key. An unknown snapshot field still fails with `unknown_field`. A committed search stores the found resource, so resume classifies a search as foraging only when the caller passes that request id in `skill_untargeted_request_ids`. Omitting the set leaves a successful untargeted search on resource detection.

## Physiology and death

Close-of-tick order for living bodies: needs (+2 hunger, +3 thirst, +1 fatigue) → combined needs damage → optional Died(`combined_needs`) → else temperature lerp with shelter → exposure damage → optional Died(`exposure`). Health clamps to 0. Death is terminal; dead bodies occupy capacity and keep inventory.

## Tick finalization

Action resolution then autonomous effects accumulate pending details/causes/occurrence context against one evolving state. One finalizer decides mutation, advances revision at most once, assigns contiguous sequences and deterministic event IDs, and freezes schema-v4 `WorldEvent` values with action or system causes plus event-time audience context (origin, destination, affected entity, private recipient as applicable).

## Seeds and schemas

- Named streams: run, world, tick, ordinal or system entity, purpose, derivation-v2 (rules fingerprint). Never module-global RNG or Python `hash()`.
- **Never log seeds**, random draws, inventories, event payloads, observation contents, communication text, or full snapshots.
- Audit schema v1: decode/export only. Replay schema v2: legacy projector. Replay schema v3: physical runs without occurrence context (readable). Replay schema v4: physical runs with occurrence context (new writes). Runs do not mix replay schemas.

## Snapshot contents

Checkpoints capture locations (adjacency/capacities/environment), bodies (physiology + carry capacity), items (kind/load/placement), resources (kind/quantity/max/regen), weather (condition), revision, next tick, and integrity hashes. Physical rules version/fingerprint/canonical bytes persist on the run.

## Tests

```bash
uv run --frozen --python 3.12.14 pytest tests/unit
uv run --frozen --python 3.12.14 pytest tests/unit/physical -q
# Optional Postgres integration:
# PALIMPSEST_TEST_DATABASE_URL=... uv run --frozen --python 3.12.14 pytest -m integration tests/integration
```

## See also

- [Architecture](architecture.md)
- [LLM providers](llm-providers.md)
- [Persistence](persistence.md)
- [Development](development.md)
