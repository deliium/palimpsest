# V4 Architecture: Open-Ended Civilizations

## Status and scope

V4-01 is scaffolding only. It declares a closed context vocabulary, an accepted
runner schema, reserved wire versions, an ordered migration posture, a
deterministic scale contract, and additive presentation negotiation. It
implements no V4 social mechanic.

Every V4 capability flag is closed, unowned, and fails closed at runtime
construction (`capability_unimplemented`, stage `v4_capability_flags`). Enabling
any of them in V4-01 is an error, not an experiment. A later V4 plan must claim
ownership explicitly before a flag can enable behavior.

`institutional_economy` and `multi_hop_testimony_tracking` remain unowned from
V2/V3. V4 does not silently claim them, and they keep failing closed exactly as
they do today.

Current implementation status: V4-01 scaffolding is implemented — closed flags,
accepted `runner-config-v56`, reserved write pairs, an ordered migration
sequence, observer capability negotiation, and the scale contract. No V4 mechanic
exists. Details: [versioning and compatibility](v4-versioning.md),
[migration sequence](v4-migration-sequence.md), and
[scale contract](v4-scale.md).

## Authority model

Four authorities exist, and every V4 context declares exactly one:

| Authority | Meaning | Mutation rights |
| --- | --- | --- |
| `objective_world` | Engine-owned physical facts | `WorldEngine` only |
| `owner_scoped` | One agent's beliefs and records | The owning agent's cognition and ordinary commands |
| `detached_analysis` | Retrospective measurement over committed evidence | None; read-only |
| `presentation_only` | Layout, selection, and rendering in clients | None; clients never advance the simulation |

Only `WorldEngine` mutates objective state. Events remain immutable, perception is
the only route from objective state to an agent, and subjective state never
becomes objective authority.

No organization, market, polity, institution, or civilization is an actor. There
is no global organization registry, no money object, no central bank, no court,
no army, no border authority, and no world-law object. Those phenomena are
owner-scoped beliefs plus ordinary agent-mediated commands, records, and physical
facts. Nothing in this document authorizes a "society" service that decides for
agents.

## Context map

Thirteen bounded contexts. Twelve carry a closed capability flag; one
(`societal_resilience`) is analysis-only and has no flag. Context identifiers are
stable ASCII lowercase snake_case and are the same identifiers used by the
machine-readable registry in `simulation.v4_architecture`.

| Context | Capability flag | Authority | Owning packages | Existing mechanism | Event strategy | Measurement |
| --- | --- | --- | --- | --- | --- | --- |
| `organizations` | `organizations` | owner-scoped | `agents.cognition`, `social`, `simulation` | collective projects, public goods, mentorship | reuse | deferred to V4-02+ |
| `formal_rules` | `formal_rules` | owner-scoped | `agents.cognition`, `simulation` | norms, conventions, durable records | reuse | deferred to V4-02+ |
| `legal_disputes` | `legal_disputes` | owner-scoped | `agents.cognition`, `simulation` | mediation | reuse | deferred to V4-02+ |
| `diplomacy` | `diplomacy` | owner-scoped | `agents.cognition`, `social`, `simulation` | contact, migration, commitments | reuse | deferred to V4-02+ |
| `organized_conflict` | `organized_conflict` | objective-world | `world`, `simulation`, `agents.cognition` | physical harm/attack commands | reuse | deferred to V4-02+ |
| `infrastructure_networks` | `infrastructure_networks` | objective-world | `world`, `simulation` | new physical network graph | reserve event 23 / codec `v21` | deferred to V4-02+ |
| `supply_chains` | `supply_chains` | objective-world | `world`, `simulation` | production, storage, transport | reuse | deferred to V4-02+ |
| `markets_credit` | `markets_credit` | owner-scoped | `agents.cognition`, `simulation` | exchange profile, commitments | reuse | deferred to V4-02+ |
| `science` | `science` | owner-scoped | `agents.cognition`, `simulation` | experimentation, practical knowledge, repositories | reuse | deferred to V4-02+ |
| `epidemics` | `epidemics` | objective-world | `world`, `simulation`, `agents.cognition` | new host/transmission state | reserve event 24 / codec `v22` | deferred to V4-02+ |
| `ecological_feedback` | `ecological_feedback` | objective-world | `world`, `simulation` | resource regeneration/depletion | reserve event 25 / codec `v23` | deferred to V4-02+ |
| `disasters` | `disasters` | objective-world | `world`, `simulation` | environmental hazards | reserve event 26 / codec `v24` | deferred to V4-02+ |
| `societal_resilience` | — (analysis-only) | detached-analysis | `analysis` | new detached classification | reuse | deferred to V4-02+ |

Reservations are not implementations. A reserved event number or codec version
carries no semantics and no payload; a later plan must still prove
effect-complete details, replay, and a persistence need.

### organizations

Collective action is objective work plus owner-scoped membership beliefs. An
organization exists only as far as agents believe in it, talk about it, and act
through ordinary commands. Objective facts are limited to the physical effects of
those commands. No organization actor, roster, treasury, automatic resource pool,
or global registry is created.

### formal_rules

A rule is a private expectation about conduct, inferred from norms,
conventions, and records. Objective facts are the durable records agents choose
to create and the physical consequences of compliance or violation. No world-law
object, policy engine, or automatic sanction exists.

### legal_disputes

Disputes, accounts, recommendations, and outcomes stay owner-scoped. The only
objective facts are the physical effects of voluntarily selected commands such as
a supported `Give`. No court, verdict, binding settlement, forced transfer, or
global dispute registry is created.

### diplomacy

Diplomacy is communication and movement between agents who already hold
owner-scoped beliefs about other groups. Objective facts are contact co-presence,
journeys, and the physical effects of ordinary commands. No polity, treaty
authority, border, citizenship, or treaty store is created.

### organized_conflict

Organized conflict uses existing physical harm and attack commands. Objective
facts are injuries, deaths, and destroyed or moved physical entities. No war
state, army actor, command hierarchy, or conflict registry is created; group
coordination remains owner-scoped belief plus ordinary speech.

### infrastructure_networks

Infrastructure is a physical network of locations, structures, and connections
owned by the engine. It reserves a future write pair because the network graph is
new objective state. No abstract "grid" authority, planner, or automatic
maintenance policy is created in V4-01.

### supply_chains

Production, storage, and transport already move named items through engine rules.
Supply chains are the observable path those items take. Objective facts are
inventories, structures, and journeys. No central planner, quota, or automatic
allocation is created.

### markets_credit

Exchange profiles, valuations, commitments, and credit are owner-scoped beliefs
and structured speech. Objective facts are the items that actually move when an
agent selects a supported command. No money object, price index, ledger authority,
central bank, or enforced debt is created.

### science

Experimentation, practical knowledge, repositories, and technique lineages stay
owner-scoped or detached. Objective facts are the physical experiments, records,
and their custody. No objective truth registry, global encyclopedia, or
automatic discovery is created.

### epidemics

Host and transmission state would be objective, engine-owned, and learned by
agents only through perception and records. It reserves a future write pair. No
disease actor, global outbreak registry, or automatic policy response is created
in V4-01.

### ecological_feedback

Resource regeneration and depletion already exist as engine rules. Ecological
feedback is the observable coupling between consumption and renewal. It reserves
a future write pair for additional state. No ecological actor or automatic
carrying-capacity policy is created.

### disasters

Environmental hazards already exist as engine-owned state transitions. Disasters
would extend that seam and reserve a future write pair. No disaster actor, scripted
catastrophe, or narrative event injection is created.

### societal_resilience

Resilience and collapse are retrospective classifications over committed
evidence. This context owns only `analysis`, has no capability flag, and has no
mutable world seam. Its findings never feed cognition, memory formation, prompts,
admission, observations, or stop criteria.

## Cross-context contracts

- Owner-scoped constructs travel only through ordinary commands, perception,
  durable records, and addressed communication. There is no side channel between
  owners and no shared mutable belief store.
- Communication proves delivery only. Declared lineage is testimony, and every
  receiver forms a fresh trace.
- Analysis reads committed objective evidence and owner exports after the fact.
  It never feeds cognition, prompts, memory, or world state.
- Clients are presentation-only. Layout, overlays, focus, and scale selection
  never mutate world state or obtain authority beyond their existing
  inspection/debug credentials.
- A context may not import a package outside its declared owner set. Objective
  contexts must list `world`; analysis-only contexts own only `analysis`.

## Scale model

Partitioning is a pure function of a versioned namespace and an agent identifier.
It preserves declaration order, uses no `hash()`, no global state, and no
wall-clock input, and produces identical output for identical inputs across
processes.

Per-tick work budgets are declarative and bounded. V4-01 adds no runtime
enforcement and claims no capacity: the scale lane measures partition mapping
only, and any throughput statement must come from a later benchmark receipt.

Multi-scale presentation levels are `agent`, `cohort`, `settlement`, `region`,
and `civilization`. They are a shared vocabulary between the Python contracts and
the Godot client, not a server aggregation contract and not engine semantics.

## Version surfaces

| Surface | V4-01 pin | Owner |
| --- | --- | --- |
| Default runner write | `runner-config-v4` | `simulation.runner_models` |
| Latest feature runner | `runner-config-v55` | `simulation.runner_models` |
| Accepted scaffolding runner | `runner-config-v56` (accepted, never emitted) | `simulation.runner_models` / `simulation.runner_serialization` |
| Default result write | `runner-result-v2` | `simulation.runner_models` |
| Generational result | `runner-result-v3` | `simulation.runner_models` |
| Event schema | `EVENT_SCHEMA_REPLAY_V22` (22) | `world.events` |
| Persistence codec | `v20` | `simulation.persistence` |
| Alembic head | `0017` | `alembic/versions` |
| Commands | 43 | `world.actions` / `world._rules` |
| Observer semantic types | 73 | `observer.version` |
| Observer protocol | `observer-protocol-v1` | `observer.version` |
| Observer layout schema | `observer-layout-v1` | `observer.version` |
| Metric catalog | 136 families | `analysis.specifications` |
| HTTP API | `/v1` | `api` |

## Compatibility and deprecation policy

- Evolution is additive first. A new write version must preserve legacy decoding
  and may not silently widen an existing schema identifier.
- Runner configuration versions use exact key sets: an unknown, missing, or extra
  key is a serialization error rather than a default.
- `runner-config-v56` is accepted for explicit scaffolding identity only. Feature
  selection never emits it, and the default write stays `runner-config-v4`.
- Legacy payloads decode with the V4 flag object synthesized as all-off.
- Reserved write pairs (events 23-26, codecs `v21`-`v24`) are numbers without
  semantics. Activating one requires a plan that lands admission, replay, and
  tests together.
- Deprecation of any V1-V3 surface is out of scope for V4-01.

## Migration posture

V4-01 adds no migration. Alembic head stays `0017`.

Future migrations are ordered and evidence-gated. Each stage names the trigger,
its prerequisites, the owning context, and the authority impact; a stage without
a proven persistence or indexed-inspection need is not implemented. Capability
flags remain runner JSON, not SQL columns.

The ordered V4 stages are declared in `simulation.migration_plan` and validated
by tests; a stage may not be reordered, duplicated, or referenced without a known
context or flag.

## Presentation policy

Both clients are read-only. The API serves their prebuilt trees and never imports
them.

`GET /version` advertises supported observer protocols, the layout schema, and
the advertised/reserved capability *names*. It never exposes capability-flag
values, configuration payloads, or any run content. Unknown capability names are
shown as counts rather than guessed.

`observer-protocol-v1` remains the only served protocol. A future `v2` is
reserved but not served, and no semantic type or frame changes in V4-01.

## Non-goals

- Implementing any V4 social mechanic, including organizations, rules, disputes,
  diplomacy, conflict, infrastructure, supply chains, markets, credit, science,
  epidemics, ecological feedback, disasters, or resilience.
- Adding a command, event, observer semantic type, metric family, API version,
  SQL migration, or global registry to make V4 scaffolding pass.
- Claiming a capacity or throughput envelope; the scale lane measures partitioning
  only.
- Making a flag owned, or enabling a deferred V2/V3 flag
  (`multi_hop_testimony_tracking`, `institutional_economy`).
- Durable subjective restart, recorded/live LLM forks, scripted emergence
  helpers, or any forced social outcome.
- Serving `observer-protocol-v2` or adding `/v2` routes.
- Introducing a new top-level Python package, distributed infrastructure, or a
  vendor LLM SDK.

## Downstream V4 plan checklist

Before a V4-02+ plan may enable any V4 flag it must declare:

1. The owning context id and the exact authority it keeps.
2. The event strategy: reuse an existing event kind or claim a reserved write
   pair with effect-complete details.
3. Replay proof: decode, projection, and round-trip tests for the claimed pair.
4. The metric families the behavior adds, or an explicit statement that it adds
   none.
5. The observer rows or presentation surfaces it changes, staying read-only.
6. The migration need, or an explicit statement that head `0017` is unchanged.
7. Null-capable tests: legal absence of the phenomenon is a valid outcome.
8. The V1/V2/V3 regression suites green with V4 flags off.
