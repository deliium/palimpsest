# V4 Architecture: Open-Ended Civilizations

## Status and scope

V4-01 is scaffolding only. It declares a closed context vocabulary, an accepted
runner schema, reserved wire versions, an ordered migration posture, a
deterministic scale contract, and additive presentation negotiation. It
implements no V4 social mechanic.

Every V4 capability flag is closed. V4-01 declared all of them unowned and
fail-closed at runtime construction (`capability_unimplemented`, stage
`v4_capability_flags`); a later V4 plan must claim ownership explicitly before a
flag can enable behavior. Today five flags are owned — `organizations`
(V4-03/V4-04/V4-05), `formal_rules` (V4-06), `legal_disputes` (V4-07),
`diplomacy` (V4-10/V4-11), and `organized_conflict` (V4-12) — and the other
seven remain unowned and fail closed. Enabling an unowned flag is an error, not
an experiment.

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

Fourteen bounded contexts. Twelve carry a closed capability flag; two
(`societal_resilience` and `macro_society_identity`) are analysis-only and have no
flag. Context identifiers are stable ASCII lowercase snake_case and are the same
identifiers used by the machine-readable registry in `simulation.v4_architecture`.
The registry revision is `v4-context-map-v2`.

| Context | Capability flag | Authority | Owning packages | Existing mechanism | Event strategy | Measurement |
| --- | --- | --- | --- | --- | --- | --- |
| `organizations` | `organizations` | owner-scoped | `agents.cognition`, `social`, `simulation` | collective projects, public goods, mentorship, institution concepts, offices, institutional memory, collective decisions, structured commitments, group formation, possession legitimacy | reuse | V4-03/V4-04 implementation |
| `formal_rules` | `formal_rules` | owner-scoped | `agents.cognition`, `simulation` | norms, conventions, durable records | reuse | V4-06 implementation |
| `legal_disputes` | `legal_disputes` | owner-scoped | `agents.cognition`, `simulation` | mediation, formal rules, offices, organizations | reuse | V4-07 implementation |
| `diplomacy` | `diplomacy` | owner-scoped | `agents.cognition`, `social`, `simulation` | contact, migration, commitments | reuse | V4-10 implementation |
| `organized_conflict` | `organized_conflict` | objective-world | `world`, `simulation`, `agents.cognition` | physical harm/attack commands | reuse | V4-12 implementation |
| `infrastructure_networks` | `infrastructure_networks` | objective-world | `world`, `simulation` | new physical network graph | event 23 / codec `v21` | owned by V4-16 |
| `supply_chains` | `supply_chains` | objective-world | `world`, `simulation` | production, storage, transport | reuse | deferred to V4-02+ |
| `markets_credit` | `markets_credit` | owner-scoped | `agents.cognition`, `simulation` | exchange profile, commitments | reuse | deferred to V4-02+ |
| `science` | `science` | owner-scoped | `agents.cognition`, `simulation` | experimentation, practical knowledge, repositories | reuse | deferred to V4-02+ |
| `epidemics` | `epidemics` | objective-world | `world`, `simulation`, `agents.cognition` | new host/transmission state | reserve event 24 / codec `v22` | deferred to V4-02+ |
| `ecological_feedback` | `ecological_feedback` | objective-world | `world`, `simulation` | resource regeneration/depletion | reserve event 25 / codec `v23` | deferred to V4-02+ |
| `disasters` | `disasters` | objective-world | `world`, `simulation` | environmental hazards | reserve event 26 / codec `v24` | deferred to V4-02+ |
| `societal_resilience` | — (analysis-only) | detached-analysis | `analysis` | new detached classification | reuse | deferred to V4-02+ |
| `macro_society_identity` | — (analysis-only) | detached-analysis | `analysis` | candidate-community analysis, cultural/institutional evidence joins, group persistence | reuse | V4-02 implementation |

Reservations are not implementations. A reserved event number or codec version
carries no semantics and no payload; a later plan must still prove
effect-complete details, replay, and a persistence need.

### organizations

**Owned by V4-03/V4-04 on `runner-config-v56`.** Collective action is objective
work plus owner-scoped membership and operation beliefs. An organization exists
only as far as agents believe in it, talk about it, and act through ordinary
commands. Objective facts are limited to the physical effects of those commands.
V4-04 adds an operation sidecar across eight domains (resource control, storage,
record keeping, admission, departure, role assignment, procedure action, internal
commitment) with provenance and retained disagreement. Objective possession stays
separate and unchanged; no organization actor, roster, treasury, automatic
resource pool, teleport helper, command executor, or global registry is created.

### formal_rules

**Owned by V4-06 on `runner-config-v56`.** A rule is a private expectation about
conduct, inferred from norms, conventions, and records. It can carry scope,
proponents, recognized authority, written representation anchors, expected
sanctions, exceptions, and historical versions. Objective facts are the durable
records agents choose to create and the physical consequences of compliance or
violation. No world-law object, policy engine, or automatic sanction exists.

The progression `habit -> expectation -> norm -> documented ->
recognized_enforcement` is monotone per owner rule. Bounded `fr_v1` claims travel
inside existing `Talk`/`Tell`; declared responses are not objective compliance
findings. Competing systems coexist without precedence. Detached analysis
publishes `formal-rule-snapshot-v1` and three metric families (148 -> 151); six
GET-only routes serve it under `SUBJECTIVE_DEBUG`. `WorldEngine` never reads the
ledger.

### legal_disputes

V4-07 owns `legal_disputes` on the accepted `runner-config-v56` seam. A dispute
is one owner's belief about attributed claims, counterclaims, testimony,
evidence references, rule interpretations, mediation links, authority
references, and proposed or declared resolutions. Claims stay separate and
attributed; agents may sincerely disagree because remembered evidence differs.
Rule references resolve only against the owner's formal-rule ledger
(`resolved`, `orphaned`, `version_mismatch`, `contested`, `retired`); mediation
links only cite the owner's mediation ledger.

Resolutions are proposals. Per-party `accept`/`reject` declarations never bind
anyone, and `apparently_accepted` requires every named party's active
declaration observed after a prior committed tick. The only supported
undertaking path delegates to `compile_mediation_undertaking`; every physical
effect remains an ordinary admitted command. `WorldEngine` never reads a dispute
ledger, a socially disputed but physically possible command is still admitted,
and a physically impossible command is still rejected by existing world rules.
Detached analysis may classify researcher-only objective alignment
(`supported`, `unresolved`, `inconsistent`, `not_applicable`) and publishes
`dispute-resolution-snapshot-v1`; six GET-only routes serve it under
`SUBJECTIVE_DEBUG`. No court, judge, verdict, binding settlement, forced
transfer, or global dispute registry exists.

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
owned by the engine. V4-16 activates the reserved write pair (event 23 /
codec `v21`) for persistent `infra-` assets built through collective projects.
No abstract "grid" authority, planner, or automatic maintenance policy is
created. See [infrastructure networks](infrastructure-networks.md).

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

### macro_society_identity

Macro-society identity is a retrospective analytical classification over
detached evidence. This context owns only `analysis`, has no capability flag, and
has no mutable world seam. A candidate is an analysis-output label with an
`msoc-` identifier; it is never a nation, state, polity, civilization, or actor,
and no global registry exists. Candidates may overlap, be disputed, be
fragmented, or lack self-identification. Findings never feed cognition, memory
formation, prompts, admission, observations, or stop criteria.

V4-02 implements the context in `analysis.macro_society_*` (evidence, detection,
identity, lineage, layers, metrics), `simulation.macro_society_*` (snapshot DTOs,
canonical codec, bounded paging, read/publication ports),
`experiments.macro_society_publication`, `persistence.macro_society_filesystem`,
and four GET-only `/v1` routes. It adds no capability flag, command, event,
observer semantic type, write pair, or migration. See
[Macro-societies](macro-societies.md).

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
| Event schema | `EVENT_SCHEMA_REPLAY_V23` (23) when infrastructure channel active; prior maxima remain accepted | `world.events` |
| Persistence codec | `v21` when infrastructure channel active; `v20` remains accepted; epidemic `v22` unaccepted | `simulation.persistence` |
| Alembic head | `0017` | `alembic/versions` |
| Commands | 43 | `world.actions` / `world._rules` |
| Observer semantic types | 73 | `observer.version` |
| Observer protocol | `observer-protocol-v1` | `observer.version` |
| Observer layout schema | `observer-layout-v1` | `observer.version` |
| Metric catalog | 188 families (V4-16 appends four infrastructure families after V4-15's 184) | `analysis.specifications` |
| Border routes | six GET routes under `/v1/simulations/{run_id}/borders` | `api.routes.borders` |
| Migration routes | six GET routes under `/v1/simulations/{run_id}/migration` | `api.routes.migration_displacement` |
| Infrastructure routes | six GET routes under `/v1/simulations/{run_id}/infrastructure-networks` | `api.routes.infrastructure_networks` |
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

- V4-01 does not implement organizations, rules, disputes,
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

## Diplomacy (V4-10)

`diplomacy` is owned by V4-10 on the accepted `runner-config-v56` seam. It is
owner-scoped and reuses existing events, with `organizations` as a planning-order
prerequisite rather than a runtime gate. Relations, parties, contacts, envoys,
negotiations, instruments, declarations, misrepresentation observations,
terminations, and conflicts are retained owner beliefs. There is no polity,
border, citizenship, treaty store, treaty authority, envoy registry, army, war
state, or bilateral score. Detached analysis derives six independent lanes and
four metric families (catalog 160 -> 164). Canonical `diplomacy-snapshot-v1` and
`diplomacy-store-v1` publications are served by six GET-only routes under
`SUBJECTIVE_DEBUG`. See `docs/diplomacy.md`.

## V4-11 treaties and ceasefires seam

V4-11 deepens the owned `diplomacy` context on `runner-config-v56`; it adds no
flag, context, runner schema/root field, command, event, observer semantic type,
write pair, `/v2` route, or migration. Treaties are owner beliefs with ordered
participants, immutable parent-linked versions, declarations, recollections,
opaque record/institutional-memory anchors, and retained terminations and
conflicts. Recognized representatives are derived from the owner representation
ledger; `apparently_accepted` binds nobody. `diplomacy-snapshot-v2` is canonical,
`diplomacy-snapshot-v1` remains decodable, `diplomacy-store-v1` is unchanged, and
eight GET-only diplomacy routes require `SUBJECTIVE_DEBUG`. `WorldEngine` and
every enforcement path never read a treaty ledger.

## V4-12 organized conflict seam

`organized_conflict` is the fifth owned V4 capability flag on
`runner-config-v56`. It requires `diplomacy`. Owner-scoped plans,
participations, observations, interpretations, outcomes, contradictions, and
terminations compile only to existing commands through the deterministic
`Wait` replacement. Detached detection classifies `individual_violence`,
`coordinated_conflict`, and `persistent_inter_group_conflict` from committed
events. `organized-conflict-snapshot-v1` and `organized-conflict-store-v1` are
additive; diplomacy v1/v2 and its store are unchanged. See
[organized conflict](organized-conflict.md).

## V4-13 — Borders and claims

V4-13 deepens the owned `organizations` context with owner-scoped domain claims
over logical location sets, observed boundary edges, access expectations, border
agreements, and disputes. It adds no flag, context, `runner-config-v57`, runner
root field, per-agent runner key, command, event, write pair, observer semantic
type, `/v2` route, or migration. Detached analysis adds four layers and four
metric families (172 -> 176), `borders-snapshot-v1`, `borders-store-v1`, six GET
routes, a Research UI panel, and four presentation overlays. See
[borders and claims](borders-and-claims.md).

## V4-14 — Migration and displacement

V4-14 deepens the owned `organizations` context and the V3 regional-migration
seam with owner-scoped migration intents, routes, causes, clusters, integration
beliefs, and wave observations. It adds no flag, context, `runner-config-v57`,
runner root field, per-agent runner key, command, event, write pair, observer
semantic type, `/v2` route, or SQL migration. Physical movement stays ordinary
`Move`/`Transport`/`Flee` admission. Detached analysis adds four layers and four
metric families (176 -> 180), `migration-displacement-snapshot-v1`,
`migration-displacement-store-v1`, six GET routes, a Research UI panel, and four
presentation overlays. See
[migration and displacement](migration-displacement.md).
