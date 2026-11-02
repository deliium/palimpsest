# Architecture: Structured Modules (Technical Layer / Bounded Packages)

## Overview

Palimpsest is a Python modular monolith for reproducible multi-agent society
experiments. Its technical concerns are bounded packages, not per-feature
Controllers/Services/Repositories folders. This document deliberately describes
the existing layout; it does not prescribe a package migration.

The Structured Modules label describes organization, not weaker dependency
rules. Palimpsest additionally enforces inward-facing ports, framework-free
domain policy, and machine-checked authority boundaries. `WorldEngine` alone
mutates objective state; cognition receives owner-safe observations; subjective
beliefs, analysis, and presentation never acquire world authority.

## Decision Rationale

- **Project type:** Contracts-first research simulation with complex objective
  and subjective state, deterministic replay, and optional cognitive channels.
- **Tech stack:** Python >=3.12, uv/Hatchling, FastAPI, async SQLAlchemy,
  PostgreSQL/pgvector; separate Godot observer and Svelte research clients.
- **Key factor:** Preserve enforceable trust boundaries and reproducibility
  without introducing distributed services or unrelated structural rewrites.
- **Selected organization:** Existing bounded packages by technical concern,
  with domain rules in their owning models/policies and orchestration in runtime
  services. Immutable DTOs do not need artificial behavior to fit a template.

## Folder Structure

```text
src/
  world/                 # public observations, commands, events, IDs, communication
                         # private _* state, perception, rules, operations, replay
  agents/                # identity and hierarchical goals
    cognition/           # CognitiveLoop, stage policies, owner-scoped ledgers
  memory/                # episodic traces, reconstructive recall, semantic beliefs
  social/                # communication envelopes and directed relationships
  llm/                   # validated provider-neutral output, prompts, recording
  simulation/            # WorldEngine, AgentRuntime, runner, codecs, replay, ports
  observer/              # detached frames, layouts, semantic event presentation
  experiments/           # trusted scenarios, collection, matrices, composition
  research_runner/       # palimpsest-matrix CLI composition; no HTTP
  persistence/           # SQLAlchemy adapters implementing inner ports
  analysis/              # detached metrics and retrospective evidence joins
  api/                   # FastAPI composition, control, inspection, streaming
  infrastructure/        # settings, logging, database resource lifecycle
clients/
  godot-observer/        # read-only Godot client; not a Python package
  research-ui/           # Svelte research SPA; not a Python package
alembic/versions/        # durable schema migrations
tests/                   # unit, architecture, integration, compose, typecheck, fakes
docs/                    # contributor-facing contracts and operational guidance
```

## Dependency Rules

The following are allowlists, not permissions to expose another agent's data or
private authority. Cross-package imports use declared public facades / `__all__`;
documented public submodules remain valid, private or transitive exports do not.

| Package | Allowed first-party dependencies |
| --- | --- |
| `world` | No other bounded package |
| base `agents` | Agent-facing `world`; never `agents.cognition` |
| `memory`, `social` | `world`, base `agents`; independent of each other |
| `llm` | No domain, simulation, API, persistence, or infrastructure package |
| `agents.cognition` | Public `agents`, `world`, `memory`, `social`, `llm` |
| `simulation` | Public domain/cognition/LLM contracts; no outer adapters |
| `observer` | Public `world` and detached `simulation` facts; not the engine |
| `experiments` | Public simulation/domain contracts and read-only analysis |
| `research_runner` | `experiments`, `simulation`, `persistence`, `infrastructure`, `analysis` |
| `persistence` | Public `simulation`, `memory`, `social`, `infrastructure`, `experiments.persistence` ports |
| `analysis` | Read-only `world`, `simulation`, `memory` contracts |
| `api` | `simulation`, `infrastructure`, `persistence`, `observer` |
| `infrastructure` | No domain policy |

- Only `simulation.engine`, `simulation.bootstrap`, and private `world._*`
  modules may import private world authority. Do not re-export those internals.
- `simulation` must not import `api`, `analysis`, `experiments`,
  `infrastructure`, `persistence`, or `observer`.
- `experiments` must not import API, infrastructure, or concrete persistence.
  `experiments.composition` maps neutral detached persistence snapshots into
  analysis-owned sources; adapters implement experiment ports, not the reverse.
- `research_runner` must not import `api` or start an HTTP server.
- `analysis` and `persistence` must not import each other; API must not import
  analysis. Analysis results never feed live cognition, prompts, or memory.
- Persistence obtains subjective identity types from `memory.models` (including
  re-exported `EntityId`), not by importing `world`.
- Domain packages import neither infrastructure nor FastAPI/Pydantic/ORM stacks.
  Pydantic structured-output validation belongs at the LLM boundary.
- Only infrastructure and persistence may import SQLAlchemy/Alembic/asyncpg.
  Vendor LLM SDKs are forbidden throughout `src/`; use the HTTP adapter.
- Python code never imports either client. API serves their prebuilt trees;
  research static routing mounts `/research/` before the Godot root.

Import-linter contracts in `pyproject.toml` and AST checks under
`tests/architecture/` enforce these boundaries. The reference architecture's
generic permission for modules to import infrastructure does **not** apply here.

## Layer/Module Communication

### Objective authority and runtime

```text
WorldEngine.observe() -> detached observations + engine-issued token
  -> AgentRuntime -> owner-safe perspective -> CognitiveLoop
  -> one AgentCommand -> ActionSubmission(token, actor, command)
  -> ordered engine admission/resolution -> atomic objective commit
  -> next observation window / detached exports / read-only consumers
```

Private perception uses tick-start state and prior committed events. Repeated
observation within an open tick is stable. Cognition never receives `WorldState`,
an engine snapshot, the token, another owner's observation, or an all-agent batch.
Ordered submissions resolve against evolving state; autonomous physical effects
follow. `AgentRuntime` owns invocation, command submission, and deferred
owner-scoped subjective finalization through `SubjectiveStateService`.

### Memory, testimony, and subjective concepts

- Perception does not itself form memories or beliefs. Recall reconstructs
  owner-scoped traces; reconsolidation appends lineage without overwriting sources.
- Agents, cognition, memory, and reconstructors may carry opaque `EventId`
  correlation, never `WorldEvent` bodies, event repositories, or replay services.
- `Talk`/`Ask`/`Tell` prove eligible delivery only. Declared source lineage is
  testimony. Every receiver creates a fresh communicated trace, not a copy of a
  sender's memory, belief, reconstruction, or relationship state.
- Reports sharing one root are not independent corroboration. Bare
  `COMMUNICATE` does not silently become belief-grounded `Tell`.
- Relationships are directed low-level assessments, not predefined friend,
  enemy, leader, group, morality, or culture labels. `SelfModel` is an emergent,
  revisable projection rather than a personality class or second belief store.
- Cultural features, terminology, narratives, translation, norms, offices,
  collective decisions, and mediation remain owner-scoped beliefs. Analytical
  classifications do not install global cultural or institutional registries.

### LLM and outer composition

`LLMProvider.generate(LLMRequest[T])` returns strict `StructuredOutput` plus safe
normalized metadata. Validation proves shape, not truth, identity, policy, or
authority. Cognition translates validated decision schemas into fresh commands;
ordinary admission still applies. The LLM package never performs that translation.
Use HTTP transport, versioned prompt resources, deterministic fakes, or recorded
exchanges; exact external-LLM reproduction requires recorded outputs or stubs.

API owns settings, database lifespan, recoverable simulation management, and
durable-outbox WebSocket catch-up. Provider construction remains standalone in
`llm.factory`; API provider lifecycle composition is deferred until owned by a
cognition consumer. Matrix batches compose through `research_runner`, not HTTP.

Research capabilities separate control, objective inspection, agent-visible
projection, and default-disabled subjective debug. Credentials use headers or
WebSocket subprotocols, never query strings. Observer coordinates and overlays
are presentation only; neither client advances the simulation.

## Key Principles

1. Objective state, owner-scoped belief, and retrospective analysis are different
   authorities; never collapse them into one truth model.
2. Deterministic seeds, namespaced IDs, and injected logical clocks define domain
   identity. No global RNG, Python `hash()`, wall-clock, or UUID defaults in domain
   behavior. Operational timestamps/request IDs remain infrastructure metadata.
3. Domain contracts are frozen or defensively detached; boundary schemas reject
   unknown fields and fail closed on unsupported modes or ambiguous targets.
4. Optional channels default off and must leave off-path behavior unchanged.
   Do not script civilization, kinship affection, caregiving, culture, leadership,
   or institutions into existence.
5. Operational logs contain safe IDs, counts, reason codes, and bounded metadata;
   never credentials, DSNs, prompts, messages, propositions, narratives, memories,
   embeddings, or fingerprints used as payload surrogates. LLM uses stdlib logging
   with a metadata allowlist, not payload-bearing exceptions or structlog.
6. Eleven drives, hierarchical goals, emotion, and multi-criteria selection remain
   distinct mechanisms, not a single reward scalar or permanent death penalty.

## Versioned Extension Contract

### Current baseline through V3-43

| Surface | Current contract |
| --- | --- |
| Default runner write | `runner-config-v4`; newer writes selected by enabled features |
| Latest feature runner | `runner-config-v55` for generational runs |
| Closed commands / observer semantic types | 43 / 73 |
| Metric families | 146 (including the V3-36 comparison, six V3-37 cultural families, four V4-02 macro-society families, four V4-03 organization families, and two V4-04 organization-operation families) |
| Latest replay / codec pair | `EVENT_SCHEMA_REPLAY_V22` / `v20` for cultural contact; channel-selected, not universal |
| Alembic head | `0017` |
| Stable API / observer protocol | `/v1` / `observer-protocol-v1` |

These are a dated baseline, not grounds to rewrite legacy runs. The executable
version taxonomy is `simulation.compatibility`; version-specific codecs and
feature gates determine accepted inputs and actual writes. Older sections of
`docs/architecture.md` and the roadmap retain historical counts; do not treat
those as current pins or silently drop their legacy accepted versions.

### Capability ownership

- Owned V2 flags: `extended_self_model`, `predictive_world_model`,
  `short_term_emotional_state`, `advanced_social_inference`.
  `multi_hop_testimony_tracking` remains unowned and fails closed with
  `capability_unimplemented`.
- Owned V3 flags: `generational_population`, `kinship_inheritance`,
  `cultural_historical_memory`, `multi_polity_migration`.
  `institutional_economy` remains unowned and fails closed.
- Per-agent modes and optional run-level specs are not automatically capability
  flags. New behavior must use its owned, versioned configuration seam.

### Important V3 seams

- Population entry is engine-admitted with blank-slate initialization. Development
  and objective stages do not auto-write identity or social authority. Dependency
  care permits shared/non-kin care and neglect; parenthood is not a care mandate.
- Kinship is objective genealogy, not affection, trust, inheritance rights, or
  automatic knowledge transfer. Kinship cultural handoff remains deferred.
- Physical records/repositories preserve marks, custody, access, and lineage,
  never guaranteed meaning or truth. Practical knowledge remains distinct from
  objective capability and retrospective research lineage; no global encyclopedia.
- Possession succession is corpse custody, not inheritance law. Commitments are
  speech, not enforced debt. Valuations are private; exchanges move named items.
- Collective projects and public goods record work and benefits, not leadership,
  moral roles, or automatic access grants. Regional journeys and cultural contact
  model movement/co-presence, not citizenship, borders, or polities.
- Symbolic composition, semantic drift, translation, and generational narratives
  use owner evidence. Historical alignment and cross-owner comparisons are
  analysis-only; agents never receive ground truth from those reports.
- V3-29 institution concepts (`v49`) carry six closed pattern channels under
  `institution-concepts.v1`, not predefined institution types or objective offices.
- V3-30 offices (`v50`, `offices-succession.v1`) maintain stable owner-local role
  identity and revisable occupant/support claims. Duties and expected authority
  are not permissions. Explicit `species_default_offices_v1` newborns start empty;
  existing species profiles remain office-disabled.
- V3-31 decisions (`v51`, `collective-decisions.v1`) carry proposals, positions,
  one-hop delegation, withdrawal, coordination, and claimed outcomes in existing
  speech. No objective electorate, quorum, majority, or binding resolution exists.
- V3-32 mediation (`v52`, `mediation.v1`) carries cases/accounts, six speech acts,
  responses, and recommendations in existing communication. No court, verdict,
  binding settlement, forced transfer, or global dispute registry exists.
  `mediation_actions` compiles only the acting owner's independently selected,
  exactly supported undertaking (initially `Give`).
- V3-28 through V3-32 add no world command, event, observer semantic type, replay
  marker, codec marker, or migration. Their experiments remain off the V1 gate.

### Requirements for later changes

Civilization presentation contracts live in `simulation.civilization_models`,
`civilization_rows`, and `civilization_ports`, with strict canonical encoding in
`civilization_codec` and pure bounded selection in `civilization_paging`. These
independent sidecars distinguish objective map sections, owner-scoped claims,
and detached analytical layers. Read and publication ports are separate; no
contract grants world authority or changes the legacy observer protocol.
The GET-only `/observer/civilization/map` API uses `api.civilization_service`,
independent strict schemas and purpose-specific HMAC cursors. It delegates
historical restoration to `ObserverReadService.resolve_objective_history`,
requires objective inspection before reads, and never publishes capture data.
`simulation.civilization_capture` strips committed events to closed metadata
receipts and projects bounded owner inventories plus exact observed grounding
witnesses; `simulation.civilization_owner_export` performs the metadata-only
ledger projection without private labels or raw content.
`experiments.civilization_capture` provides bounded event-lane retention
independent of snapshot cadence. `civilization_boundaries` builds physical-only
detached inputs and isolates callbacks installed through
`SimulationRunner.set_civilization_boundary_sink`. Initial and fully finalized
boundaries share one quota with event receipts. Recovered event evidence is
journal-proven under a fixed event/byte bound; a missing or mismatched commit is
an explicit gap, never a known-empty tick. Missing owner observations suppress
grounding witnesses rather than reconstructing them. Capture is not
automatically installed and cannot affect scientific execution when its sink
fails.

`persistence.civilization_filesystem` implements separate read/publication ports
with a single atomic `state.json` commit and child-first shard/manifest/
catalogue-index hashing. `research_runner.civilization_composition` is the
opt-in producer bridge; it installs capture before execution and publishes only
after successful scientific completion, recording publication readiness
separately from scientific status. The API never imports the producer or
analysis.

`analysis.civilization_overlays` contains the pure detached calculators for
settlements, completed-exchange trade, migration, culture, technology, groups,
institutions and boundary markers. `experiments.civilization_publication` is the
only composition bridge from retained capture to those calculators; it emits
exact finalized `CivilizationBoundaryPublication` values and never runs inside
simulation, API or persistence.

1. Use accepted-set and exact-key-set schema evolution. A new write version must
   preserve legacy decoding; never silently widen an existing schema identifier.
2. Command changes co-land admission, operation rules, event details, replay
   codecs, and tests. Observation changes require explicit versioned seams and
   live/restored canonical observation parity, including prior-event windows.
3. Keep `tests/unit/test_v1_regression_gate.py` and
   `tests/unit/test_v2_scientific_invariants.py` green with later flags off.
   Keep feature experiments reproducible and separate from the V1 A–E gate.
4. Subjective checkpoints, optional cognition traces, analytical rows, and
   control-plane branch lineage stay outside the objective event fold. Preserve
   append-only authoritative history and evidence high-water boundaries.
5. V3 flags remain runner JSON. Add SQL columns/migrations only for a proven
   persistence or indexed-inspection need, not automatically for each feature.
6. Preserve `prepare_parallel=False`, API/protocol identity, and observer
   read-only behavior unless an explicitly scoped plan changes the contract.
7. Register roadmap milestones through `/aif-roadmap`; architectural guidance
   does not independently create or close milestones. Later V3 plan stems use
   the `v3-` prefix. See the downstream checklists in `docs/architecture.md`.

## Code Organization Note

- **New features:** Follow these package boundaries and public interfaces; keep
  policy with its owning domain/cognitive module, not API or persistence glue.
- **Existing code:** Prefer these conventions when changing relevant code; do
  not refactor unrelated packages merely to match a textbook folder tree.
- **Interoperability:** Inject adapters through existing ports at composition
  roots. Do not allocate providers or open database connections at import time.
- **Tests:** Add focused tests with changes, including Hypothesis invariants when
  useful. Default unit tests are network-free and require neither Docker nor
  PostgreSQL. Integration tests use disposable database names containing
  `palimpsest_test` and fail closed on ambiguous migration targets. Keep coverage
  enabled when running the project's coverage checks.

## Code Examples

### Public facades and explicit public contracts

```python
from agents.cognition import CognitiveLoop
from llm import LLMProvider, LLMRequest, LLMResult, StructuredOutput
from memory import MemoryRecallRequest, MemoryService
from simulation import AgentRuntime, WorldEngine, build_perspective
from world import Observation, Talk, Tell, Wait
from world.communications import origin_utterance, retell_utterance
```

### Authority stays private

```python
# Forbidden outside simulation.engine/bootstrap and private world internals:
from world._state import WorldState
from world._perception import PerceptionService

# Persistence identity mapping uses the documented memory export:
from memory.models import EntityId
```

Cognition consumes `Observation` and owner-scoped recalled evidence; a memory
reconstructor does not accept `WorldEvent`. LLM results have no authoritative
`to_agent_command()` shortcut. Detached analysis may correlate events and
subjective exports after the run, never while forming the owner's beliefs.

## Anti-Patterns

- Passing structured LLM output directly to admission or world operations.
- Treating an `ActionRequest`, delivered testimony, cultural label, office claim,
  collective outcome, or mediation recommendation as world-verified authority.
- Sharing mutable or copied subjective state across owners, including newborns.
- Exposing private events, all-agent observations, objective collectors, or
  analysis truth specifications to cognition or reconstructive memory.
- Correcting recall against ground truth or overwriting source traces.
- Letting analysis/observer commit ticks, or client layout affect physics.
- Putting domain policy in HTTP handlers, SQLAlchemy adapters, or logging glue.
- Introducing vendor SDKs, global RNG, import-time secrets, or infrastructure
  dependencies into the domain.
- Introducing microservices, Kafka, Celery, or extra vector databases without an
  explicitly authorized architectural change.

## See Also

- `docs/architecture.md` — contributor contracts and downstream checklists
- `docs/configuration.md` — exact configuration versions and feature gates
- `docs/persistence.md` — event history, codecs, checkpoints, and migrations
- `docs/cognition-runtime.md` — runtime stages and subjective finalization
- `docs/memory-reconstruction.md` — recall, reconsolidation, and evidence
- `docs/social-communication.md` — delivery, testimony, and owner derivation
- `docs/mediation.md` — owner-scoped mediation and voluntary follow-through
- `docs/development.md` — verification commands and client checks


### V3-33 institutional memory seam

`runner-config-v53` adds only per-agent `institutional_memory_mode` on the exact
v52 cognition keyset. Each enabled owner requires its own office-succession or
institution-concept mode. Information is owner-local, learned only from a
current interpreted record or an actual addressed delivery, and carried in
bounded marks/speech. Declared roots are testimony, never lookup keys; occupant
succession never transfers entries. Runtime checkpoints preserve one owner's
ledger but do not constitute durable subjective restart. Detached
`institutional_memory_continuity@1` and `institutional_memory_provenance@1`
raise the catalog to 126. No new command, event, observer semantic, write-pair,
migration, or capability ownership exists; `institutional_economy` remains
unowned.


### V3-34 institutional decay seam

`runner-config-v54` adds only per-agent `institutional_decay_mode` on the exact
v53 cognition keyset. Each enabled owner requires its own institution concepts.
Decay is private cognition: it adjusts concept strengths/status before ordinary
office inference and planning and never creates an objective institution, command,
or permission. The sidecar carries bounded raw samples, receipts, and absolute
identity witnesses through the owner-safe perspective/snapshot path and supported
runtime checkpoints. Admission copies nothing; the v53 memory profile stays
decay-disabled.

Detached analysis owns four-tick windows, lifecycle classification, and lineage.
Collapse requires prior confirmed stability plus two complete low/no-renewal
windows; missing evidence is censored. Episode IDs use absolute activity-span and
structural-revision witnesses, never moving-history ordinals. Three families
raise the catalog to 129: `institutional_decay@1`, `institution_lifecycle@1`,
`institution_lineage@1`. Detailed graphs/trajectories are canonical JSON strings
inside scalar metric values; the shared metric model/codec is unchanged.
Experiment BK is off the V1 gate. No new command, event, observer semantic,
write-pair, migration, API route, or capability ownership exists;
`institutional_economy` remains unowned.

### V3-36 generational experiments seam

Experiment BM (`generational_comparison@1`) and the generational matrix factors
compose existing `runner-config-v55` fields into closed paired comparisons. They
add no v56, command, event, observer semantic, write-pair, API route, migration,
or capability flag, and they do not acquire simulation authority. A pair must
share seed, stochastic identity, world layout, founder roster, stop horizon,
generation schedule, and initialization; only the declared axis differs.
Contradictory matrix combinations fail with `incompatible_factor_combination`,
and generational factors on a non-v55 base fail with `generational_base_required`.

Detached `analysis.generational_cohort` folds finalized `PopulationProgress` into
`generational_cohort_comparison@1`, raising the metric catalog to 130. The
family is scalar-only, analysis-only, and absent for non-generational runs. Cross-
arm comparison remains `matrix-metric-summary-v1`; no paired statistical layer
exists.


### V3-37 cultural evolution metrics seam

Opt-in capture installs a bounded, immutable boundary recorder in the trusted
experiment layer. It stores normalized owner-local evidence after complete
finalization and never feeds commands, perception, world state, stop criteria,
memory, prompts, or observer semantics. Six additive analysis families cover
trait dynamics, transmission, population structure, narrative survival,
vocabulary differentiation, and technology continuity; each dimension keeps its
own estimand and denominator, and no composite culture score exists.

`cultural-capture` is composition-only and default off. Completed cells may
carry `cultural-evolution-evidence-v1` and `cultural-cell-metrics-v1` siblings;
`aggregate --cultural-summary` may add `cultural-metric-comparison-v1`. These
are sibling artifacts, not runner/archive schema changes. A capture-required
cell without a verified matching pair fails preflight without rerunning
objective history; sealed archives are never reopened to recover capture.
Repeated-seed inference uses a Student-t interval over distinct numeric-seed
blocks, with duplicate seeds/replicas averaged inside a block. Paired contrasts
require exactly one declared matrix factor and are re-materialized through the
registered applicators; actual channel selectors determine shared/mixed/unknown
stream alignment. Legacy metric-summary `p05`/`p95` values remain percentile
ranges.

V3-37 adds no capability flag, runner schema (no v56), command, event, observer
semantic type, write-pair, API route, or migration; default runner writes remain
v4/result v2, commands stay 43, observer semantic types stay 73, replay stays
`EVENT_SCHEMA_REPLAY_V22`/`v20` for feature-selected runs, and Alembic head stays
`0017`.


### V3-38 historical contingency seam

`historical_contingency@1` is an opt-in grouped experiment protocol, not a runner capability. `experiments` owns predeclared designs, treatment-blind slots, eligibility, ordinary-admission arbiters, bounded finalized evidence collection, detached outcome projection, and strict sibling artifacts. `analysis` owns selector calculators and paired seed-block comparison over detached rows and never imports experiments or live services. `research_runner` composes the CLI and read-only objective presence; it never starts HTTP. Common prefix state is process-local only: completed children may be adopted, but durable subjective restart is not claimed and an unused planned child requires exact deterministic prefix reconstruction. No runner v56, capability flag, command/event, observer semantic, write-pair, API route, migration, or metric family is added.


### V3-39 lineage explorer seam

`simulation.lineage_*` owns qualified eight-family DTOs, pure projections, bounded
traversal, canonical `lineage-snapshot-v1` artifacts, catalogue discovery and the
neutral capture session. Objective genealogy/record evidence uses
`OBJECTIVE_INSPECTION`; subjective and analytical evidence uses `SUBJECTIVE_DEBUG`.
`persistence.lineage_filesystem` implements separate reader/publisher ports with a
single atomic `state.json.committed_ref` publication point and cumulative per-run
quotas. `experiments.lineage_publication` is the trusted analytical composer;
`research_runner` owns the opt-in CLI producer. HTTP is GET-only under
`/v1/simulations/{run_id}/lineage`; API reads never build, repair or mutate
lineage artifacts and never import analysis. This feature adds no command, event,
observer semantic, metric family, runner/result version, SQL migration, capability
ownership or `/v2` route; Alembic stays `0017` and default writes stay v4/v2.

### V3-40 through V3-42 presentation seams

Godot generational observation, Godot civilization overlays, and the generational
Research UI are read-only presentation work over already-published evidence. They
add no command, event, observer semantic, metric family, runner/result schema,
replay/codec marker, SQL migration, capability ownership, or `/v2` route. Python
modules still never import either client; the API only serves their prebuilt
trees, and `/research/` mounts before the Godot root. The release image builds
both trees in pinned build stages (Godot export and Node/pnpm SPA build) and
runs them as static assets; the runtime image contains no editor, Node, pnpm, or
export templates. Presentation selection,
layout, overlays, focus, and deep links never mutate world state or obtain capture
or subjective authority beyond their existing inspection/debug credentials.

### V3-43 long-horizon scalability seam

Benchmark-only helpers under `tests/benchmarks` own workload definitions,
measurement/supervision artifacts, the `v3-scale-envelope-v1` report and
composition trials. They never participate in runner configuration, capability
negotiation or scientific schema validation. Optional `RuntimeRetentionPolicy`
is composition-only and default off: terminal, objectively dead and fully
finalized fork-capable owners may release live cognition/service graphs into a
complete frozen process-local record. Historical objective/captured evidence
remains queryable; durable subjective restart is still not claimed.

Optional cold history archives, append-only evidence spools and physical
`lineage-store-index-v2` / `civilization-store-index-v2` layouts are separate
versioned siblings. Old publications remain readable, source rows stay
append-only, and derived analytical views never feed cognition. No command,
event, observer semantic, metric family, runner/result schema, replay/codec
marker, SQL migration, capability ownership or `/v2` route is added. The
verified scale envelope stops at 10k for measured lanes; 100k attempts remain
incomplete and real-browser playback is unverified.

### V3-44 generational civilization benchmark seam

`experiments.civilization_benchmark_*` owns the immutable thirty-case registry,
domain fixtures, evidence checks and the thin seed-block comparison composer.
`research_runner.civilization_benchmark_{cli,composition}` owns the bounded CLI,
domain builder/arbiter dispatch, supervised execution, isolated artifact roots
and immutable publication. Simulation still imports none of these modules and
the benchmark never grants world authority, installs a global culture/technology/
office registry or feeds research comparisons into cognition, prompts or stop
selectors.

Artifacts are sibling `civilization-benchmark-run-v1`/`suite-v1` documents with
canonical hashes; they do not alter runner/result/archive schemas. The controlled
mechanism lane may schedule normally admitted commands and must pass its declared
checks. The unassisted research lane records legal nulls as explicit
`unexecuted` checks with complete/partial evidence; a strict suite verification
therefore fails for an honest null, while integrity verification succeeds.
Founder-roster effects stay founder-scoped, initializer differences are composite
treatments with every changed mode declared, and grouped forks delegate to the
existing path-dependence estimator.

V3-44 adds no capability flag, runner schema, command, event, observer semantic,
metric family, write-pair, API route, SQL migration or `/v2` route. Pins remain
runner v4/result v2, latest feature runner v55, 43 commands, 73 observer semantic
types, 136 metric families, replay-v22/codec v20 when selected, Alembic `0017`,
`/v1` and `observer-protocol-v1`. `institutional_economy` and
`multi_hop_testimony_tracking` remain unowned.

### V4-01 open-ended civilizations architecture seam

`simulation.v4_architecture`, `simulation.versioning`, `simulation.migration_plan`,
`simulation.scale`, and `observer.capabilities` publish the V4 vocabulary without
implementing behavior. Fourteen contexts are declared: twelve closed capability
flags plus analysis-only `societal_resilience` and `macro_society_identity`;
the registry revision is `v4-context-map-v2`. Every context names one authority
(`objective_world`, `owner_scoped`, `detached_analysis`, `presentation_only`),
owning packages, prerequisites, and non-goals; no context declares an
organization, market, polity, institution, or civilization actor, and no global
registry exists.

`V4CapabilityFlags` is closed and unowned: enabling any flag requires
`runner-config-v56` (the active v55 family keyset plus one exact
`v4_capability_flags` sibling; generational siblings follow the selected family)
and then fails closed at `SimulationRunner.from_config` with
`capability_unimplemented` and `stage="v4_capability_flags"`. Default write stays
`runner-config-v4`, the latest feature runner stays `runner-config-v55`, and
feature selection never emits v56. Decoding v1–v55 synthesizes all-off V4 flags.

Four write pairs are reserved (events 23–26, codecs `v21`–`v24`) for
`infrastructure_networks`, `epidemics`, `ecological_feedback`, and `disasters`;
the other nine contexts must reuse existing events. Six migration stages are
ordered and evidence-gated; head stays `0017` and no `0018` file exists. Scale
partitioning is a pure function of a versioned namespace and agent id, with
declarative budgets and an opt-in measurement lane that makes no capacity claim.

`GET /version` additively advertises supported protocols, layout, and
advertised/reserved capability **names**; it never exposes capability-flag values
or configuration payloads, and `observer-protocol-v1` remains the only served
protocol. Both clients stay read-only.

V4-01 adds no command, event, observer semantic type, metric family, write-pair
activation, API route, migration, or behavior. Historical "no v56" sentences
inside the V3 seam sections are scoped to those plans and are not current pins;
the pin table above is unchanged.

### V4-02 macro-society identity seam

`analysis.macro_society_*` owns the closed vocabulary, evidence adapters,
deterministic per-lane and cross-lane detection, stable `msoc-` identity,
forward-only split/merge lineage, three-layer projection, and four metric
families (catalog 136 -> 140). `simulation.macro_society_*` owns the bounded
`macro-society-snapshot-v1` contract, canonical codec, paging, and read/
publication ports. `experiments.macro_society_publication` is the only bridge
from analysis to artifact; `persistence.macro_society_filesystem` stores snapshots
atomically with quotas; `api.routes.macro_society` serves four GET-only `/v1`
routes under `SUBJECTIVE_DEBUG`; the Svelte client adds a read-only panel.

Candidates may overlap, be disputed, be fragmented, or lack self-identification.
Membership is never a partition, and no country, nation, polity, civilization,
government, or organization entity or registry exists. `WorldEngine` authority,
observer protocol, Godot, commands (43), observer semantic types (73), replay
`EVENT_SCHEMA_REPLAY_V22`, codec `v20`, runner v4/v55/v56, and Alembic `0017`
are unchanged. No capability flag is claimed.


### V4-03 organizations seam

`organizations` is the first owned V4 capability flag and requires the accepted
`runner-config-v56` seam; there is no v57 and no per-agent runner key.
`agents.cognition.organization_*` owns a closed owner-scoped ledger of nine
aspects (perceived members, roles, goals, referenced resources, procedures,
records, internal commitments, identity concepts, bounded history) under
`organization-concepts.v1`. Roles reference owner-local offices; goals reference
collective proposals/projects; resources and records reference objective anchors;
commitments reference owner interpretations. Membership is never a partition:
`explicit`, `perceived`, `disputed`, `unknown`, and `former` coexist, overlap is
legal, and temporary claims expire explicitly. Bounded `org_v1` claims travel
inside existing `Talk`/`Tell`; no command, event, observer semantic type, or
write pair is added.

`analysis.organization_*` is detached and read-only: harvest from exported
ledgers, overlapping candidate detection, stable creation-evidence `org-`
identities, three strictly separated layers (objective counts, owner claims,
analytical candidates), forward-only `continued/transformed/split/merge/
dissolved/emerged` lineage, and four metric families (catalog 140 -> 144).
`simulation.organization_*` owns the bounded canonical
`organization-snapshot-v1` and separate read/publication ports;
`experiments.organization_*` is the only bridge from analysis to artifact;
`persistence.organization_filesystem` stores publications atomically with locks
and quotas; four GET-only `/v1` routes require `SUBJECTIVE_DEBUG`; the Svelte
client adds a read-only Organizations panel. No organization actor, objective
roster, treasury, resource pool, global registry, peer-ledger read, or
independent cognition engine exists. No capability flag beyond `organizations`,
command, event, observer semantic type, write pair, API version, or migration is
added; `institutional_economy` and `multi_hop_testimony_tracking` remain unowned.

### V4-04 organizations operations seam

V4-04 deepens the single owned V4 flag `organizations`; it adds no flag, runner
schema, root field, or per-agent mode. `agents.cognition.organization_operations`
owns a second owner-scoped ledger keyed by existing `orgc-` concept ids under
`organization-operations.v1`. Eight domains — resource control, storage, record
keeping, membership admission, membership departure, role assignment, procedure
action, and internal commitment — are beliefs with provenance, never objective
state or permissions. Objective custody and storage remain `holder_id`,
`location_id`, `custodian_repository_id`, and `stored_quantity`.

No operation helper returns, constructs, submits, or resolves an `AgentCommand`;
every physical effect is an ordinary command admitted by `WorldEngine`. Owner
disagreement about membership, authority, resource legitimacy, or procedures is
retained as `disputed` with `contest_count`; no consensus gate exists.
Owner-local `orgd-` decisions and `orga-` actions carry authority basis,
evidence refs, and closed provenance codes; publication mints `orgop-` records
from publication-visible content only.

`analysis.organization_*` harvests operation rows, joins them to existing `org-`
candidates without creating or changing identity/lineage, keeps objective
counts, owner claims, and analytical summaries in three separated types, and
adds two families (catalog 144 -> 146). `simulation.organization_*` adds
canonical `organization-snapshot-v2` while v1 stays decodable and
byte-verifiable; `experiments.organization_*` upgrades and composes v2;
`persistence.organization_filesystem` serves v1/v2; five GET-only `/v1` routes
require `SUBJECTIVE_DEBUG`; the Svelte client adds a read-only operations view.
No command, event, observer semantic type, write pair, `/v2` route, or migration
is added.

### V4-05 organization collective-agency seam

V4-05 deepens the single owned V4 flag `organizations`; it adds no flag, runner
schema, root field, or per-agent mode. `agents.cognition.organization_agency`
owns a third owner-scoped sidecar keyed by existing `orgc-` concept ids under
`organization-agency.v1`: proposals, positions, abstention, amendments,
recognized procedures, collective decision records, and per-actor
implementation/compliance/refusal/owner-attributed sabotage. A collective
decision is an owner belief about a recognized process, never an organization
will, quorum, binding resolution, permission, or global OrganizationLLM.
Bounded `org_ca_v1` claims travel inside existing `Talk`/`Tell`; no organization
object constructs, submits, or executes a command, and silence is never refusal
or sabotage.

`analysis.organization_agency` harvests exported ledgers into detached rows,
joins them to existing `org-` candidates without creating or changing identity,
and adds two families (`organization_collective_agency@1`,
`organization_collective_implementation@1`; metric families 148).
`simulation.organization_*` adds canonical `organization-snapshot-v3` while v1
and v2 remain decodable; six GET-only `/v1` routes require `SUBJECTIVE_DEBUG`;
the Svelte client adds a read-only collective-agency view. No command, event,
observer semantic type, write pair, `/v2` route, or migration is added.
