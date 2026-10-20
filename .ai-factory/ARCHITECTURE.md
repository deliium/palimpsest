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

### Current baseline through V3-32

| Surface | Current contract |
| --- | --- |
| Default runner write | `runner-config-v4`; newer writes selected by enabled features |
| Latest feature runner | `runner-config-v52` for per-agent `mediation_mode` |
| Closed commands / observer semantic types | 43 / 73 |
| Metric families | 124 (including the two V3-32 mediation families) |
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
