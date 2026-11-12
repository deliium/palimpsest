# Palimpsest

Reproducible, discrete, text-based multi-agent AI society experiments.

This repository is a **Python 3.12+ modular monolith**. It establishes package boundaries, V1 typed domain contracts, an authoritative deterministic `WorldEngine` tick loop with V1 physical simulation rules, an explicit cognitive loop and per-agent runtime, schema-versioned event persistence and replay, configuration, an HTTP liveness API, observability, and containers. LLM invocation stays outside the engine behind a provider-neutral structured boundary. Agent recall is reconstructive and subjective; optional reconsolidation is append-only and never mutates objective history.

## Requirements

- Python **3.12.14** (reference pin in `.python-version`; `requires-python = ">=3.12"`)
- [uv](https://docs.astral.sh/uv/) with a committed `uv.lock`
- Optional: PostgreSQL 17 with pgvector for integration tests
- Optional: Docker Compose v2 for the development stack

## Install

```bash
uv sync --frozen --python 3.12.14
```

Locked installs do not re-resolve dependencies. Copy `.env.example` to `.env` only when you need local overrides.

## Quick start

```bash
./run.sh
```

Then open `http://127.0.0.1:8080/` (`PALIMPSEST_API_PUBLISH_PORT` when set). That start pulls the published image and does not install Godot, open the editor, install export templates, export, or copy web files. `docker compose up -d` on `compose.yaml` is the same path.

```bash
# Host API with Compose Postgres only (reload)
./scripts/api.sh

# Unit and architecture tests (no Docker, no PostgreSQL, no Godot)
uv run --frozen --python 3.12.14 pytest
```

`GET /health` returns exactly `{"status":"ok"}`.

| Script | Purpose |
| --- | --- |
| `./run.sh` | Pull the published image and start the stack |
| `./run-dev.sh` | Contributor build, including the web export |
| `./scripts/up.sh` | Same pull path as `./run.sh` |
| `./scripts/api.sh` | Host Uvicorn + Compose `db`, migrate, `--reload` |
| `./scripts/migrate.sh` | `alembic upgrade head` against configured DSN |
| `./scripts/down.sh` | `docker compose down` (add `--volumes` to drop data) |
| `uv run palimpsest-matrix` | Resumable experiment-matrix CLI (no HTTP; see [Experiments](docs/experiments.md)) |

Development credentials in `compose.yaml` are **not production**. `docker compose config` expands values and is **not secret-safe**.

## Documentation

| Borders and claims | `docs/borders-and-claims.md` | Owner-scoped domain beliefs, bdr_v1, four layers, snapshot/store/routes |
| Migration and displacement | `docs/migration-displacement.md` | Owner-scoped migration beliefs, mdp_v1, four layers, snapshot/store/routes |
| Inter-society relations | `docs/inter-society-relations.md` | Researcher-only society-pair panels, `isr-` ids, eight domains, time series/comparison, six GET routes |
| Infrastructure networks | `docs/infrastructure-networks.md` | V4-16 objective `infra-` assets, write pair 23/`v21`, catalog effects, dual-gate research surfaces |
| Travel network | `docs/travel-network.md` | V4-17 route conditions, write pair 27/`v25`, movement enforcement, fallible route beliefs, snapshot v2 |
| Trade networks | `docs/trade-networks.md` | V4-18 event-sourced flows, directed corridors, dependence, major exchange locations, network lineage, snapshot and seven GET routes |
| Supply chains | `docs/supply-chains.md` | V4-19 multi-stage production chains, dependency graph, bottlenecks, lineage, snapshot and seven GET routes |
| Market-like institutions | `docs/market-like-institutions.md` | V4-20 owner-scoped meetings, schedules, emergent roles and records, venue persistence, market lineage, snapshot and seven GET routes |
| Emergent prices | `docs/emergent-prices.md` | V4-21 owner-scoped price expectations, `prc_v1` quotes, analytical distributions, market convergence, snapshot/store and seven GET routes |
| Credit relationships | `docs/credit-relationships.md` | V4-22 owner-scoped credit terms, `crd_v1` claims, repayment performance, researcher-only alignment, snapshot/store and seven GET routes |
| Regions and migration | `docs/regions-migration.md` | V3 regional travel substrate and V4-14 belief deepening |


| Page | Contents |
| --- | --- |
| [Architecture](docs/architecture.md) | Bounded packages, `WorldEngine` lifecycle, perception boundary, eleven invariants, V2/V3 seams + downstream plan contracts |
| [V4 architecture](docs/v4-architecture.md) | V4 bounded contexts, four authorities, reserved wire/migration posture, scale contract, presentation policy, downstream V4 checklist |
| [V4 versioning](docs/v4-versioning.md) | Surface pins, `runner-config-v56`, reserved write pairs, observer negotiation, deprecation |
| [V4 migration sequence](docs/v4-migration-sequence.md) | Six ordered evidence-gated stages, head `0017`, authority impact |
| [V4 scale contract](docs/v4-scale.md) | Deterministic partitioning, declarative budgets, opt-in measurement lane, no capacity claim |
| [Simulation runner](docs/simulation-runner.md) | Config-driven `SimulationRunner`, V2/V3/V4 capability flags, fingerprint vs trajectory identity |
| [Generational runner](docs/generational-runner.md) | `runner-config-v55`/`runner-result-v3`, cohorts, stop selectors, archives, historical inspection, CLI |
| [Historical contingency](docs/historical-contingency.md) | Experiment BN forked replay, intervention lineage, seven outcome domains, seed-block statistics |
| [Experiments](docs/experiments.md) | Trusted A–E catalog, `v1_regression_profile` / `v2_regression_profile` / `v3_scaffolding_profile`, coordinator, generational comparison (BM) axes and matrix factors, persistence (`0017`) |
| [V2 benchmark suite](docs/v2-benchmark-suite.md) | Sixteen composition scenarios, observer graphical fixture, zero-install + scientific gates (off V1 gate) |
| [V3 benchmark suite](docs/v3-benchmark-suite.md) | Thirty generational civilization cases, controlled/autonomous lanes, seed-block comparison, qualification matrix, measured envelope |
| [Analysis metrics](docs/analysis-metrics.md) | V1 metric catalog, populations/denominators, numerical policy, known-answer fixtures |
| [Cultural evolution metrics](docs/cultural-evolution-metrics.md) | Opt-in owner-level capture, six cultural families, repeated-seed intervals, paired contrasts, provenance limits |
| [Research API](docs/research-api.md) | FastAPI control/inspection/debug, WebSocket cursors/backpressure, capability credentials |
| [Research UI](docs/research-ui.md) | Researcher SPA at `/research/`, epistemic chrome, graphs/metrics/matrix, generational research surfaces, Godot deep links |
| [Read-only observer](docs/observer.md) | Observer protocol, frames, and the read-only HTTP and WebSocket routes |
| [Godot observer](docs/godot-observer.md) | Prebuilt Web client served by the API, version strip, deep-link `?run_id=` / debugger params, default-off population/lineage overlays and memory-only inspection/debug credentials |
| [Godot civilization overlays](docs/godot-civilization-overlays.md) | Optional read-only region/settlement/migration/trade/project/public-good/repository/culture/technology/group/institution overlays, evidence classes, captured history, cursors and deployment |
| [Research causal debugger](docs/research-causal-debugger.md) | Read-only event→cognition chain, lineage GET APIs, Godot Explain panel |
| [Institutional decay](docs/institutional-decay.md) | Opt-in owner-scoped weakening, lifecycle and lineage evidence (v54, BK, three detached families) |
| [Institutional memory](docs/institutional-memory.md) | Opt-in owner-scoped role/procedure information learned through records, transmission, and teaching; v53 and detached continuity/provenance metrics |
| [Conflict mediation](docs/mediation.md) | Opt-in owner-scoped disputes, accounts, compromises, vouching, voluntary restitution, and detached mediation metrics |
| [Collective decisions](docs/collective-decisions.md) | Opt-in owner-scoped proposals, support/opposition, one-hop delegation, coordination, compliance, and detached metrics |
| [Cognition and agent runtime](docs/cognition-runtime.md) | `CognitiveLoop`, drives/goals, subjective imagination/motivation/intention, `AgentRuntime`, metadata-only logs |
| [Memory reconstruction](docs/memory-reconstruction.md) | Subjective recall, reconsolidation, lineage, drift analysis, Alembic `0006`/`0007`/`0008`, safe logging |
| [Social communication](docs/social-communication.md) | Talk/Ask/Tell delivery vs testimony, owner-scoped traces, trust-weighted beliefs, transmission analysis |
| [LLM providers](docs/llm-providers.md) | Structured `LLMProvider`, modes, retries, prompts, local OpenAI-compatible config, fakes |
| [Physical simulation](docs/physical-simulation.md) | Topology, capacities, actions, physiology, death, schema-v4, tests |
| [Configuration](docs/configuration.md) | `PALIMPSEST_` settings (including `PALIMPSEST_LLM_*`), logging, redaction, seeds, identifiers, clocks |
| [Development](docs/development.md) | Tests, migrations (head `0017`), local and Docker workflows, exact commands |
| [Organizations](docs/organizations.md) | Owner-scoped organization beliefs, nine aspects, operational state across eight domains, membership and identity rules, forward-only lineage, `organization-snapshot-v2`, five GET-only routes and the Research UI panel |
| [Formal social rules](docs/formal-rules.md) | Owner-scoped formal-rule beliefs, monotone progression, recognized authority, written anchors, exceptions, competing systems, declared responses, `formal-rule-snapshot-v1`, six GET-only routes and the Research UI panel |
| [Disputes](docs/disputes.md) | Owner-scoped claims, counterclaims, testimony, evidence and rule references, mediation links, proposed/accepted/rejected resolutions, `dispute-resolution-snapshot-v1`, six GET-only routes and the Research UI panel |
| [Evidence and testimony](docs/evidence-testimony.md) | Owner-scoped sources, provenance, custody beliefs, confidence, interpretations, retained contradictions, owner-relative trust evaluation, researcher-only objective alignment, `evidence-testimony-snapshot-v1`, six GET-only routes and the Research UI panel |
| [Delegation and representation](docs/delegation-representation.md) | Owner-scoped principals, representatives, scope, duration, support, opposition, revocation, conflicts, derived recognition, `rep_v1` frames, `delegation-representation-snapshot-v1`, six GET-only routes and the Research UI panel |
| [Organized conflict](docs/organized-conflict.md) | Owner-scoped coordination beliefs, eight operation-to-command primitives, deterministic `Wait` replacement, `ocf_v1` frames, individual/coordinated/persistent detection, `organized-conflict-snapshot-v1`, six GET-only routes |
| [Diplomacy](docs/diplomacy.md) | Owner-scoped long-running relations, parties, contacts, envoys, negotiations, proposals, promises, agreement views, disputes, shared projects, retained terminations, `dip_v1` frames, multi-party treaties with versions, lineage, declarations and recollections, `diplomacy-snapshot-v2`, `diplomacy-store-v1`, eight GET-only routes and the Research UI panel |
| [Macro-societies](docs/macro-societies.md) | Analysis-only overlapping macro-society candidates, stable `msoc-` ids, split/merge lineage, snapshot artifact, read-only routes and Research UI |
| [Inter-society relations](docs/inter-society-relations.md) | Researcher-only `isr-` society-pair panels over `msoc-` endpoints, eight evidence domains, window time series, vectorial comparison, dual-gate publication, six GET-only routes and Research UI panel |
| [Trade networks](docs/trade-networks.md) | Event-sourced food/material/tool/record/media flows, directed corridors, observed dependence, major exchange locations, cross-society flows, forward-only network lineage, `trade-networks-snapshot-v1`, seven GET-only routes and Research UI panel |
| [Supply chains](docs/supply-chains.md) | Multi-stage production chain catalog, tool-assisted harvest, local stage readiness, ten dependency edge kinds, bounded chains and lineage, seven bottleneck kinds, `supply-chains-snapshot-v1`, seven GET-only routes and Research UI panel |
| [Market-like institutions](docs/market-like-institutions.md) | Owner-observed exchange venues, meeting expectations, social schedules, emergent broker-like roles, record anchors, venue persistence, forward-only market lineage, `market-institutions-snapshot-v1`, seven GET-only routes and Research UI panel |
| [Emergent prices](docs/emergent-prices.md) | Owner-scoped price expectations, `prc_v1` quoted offers, paired exchange ratios, analytical distributions with five bin shares, market convergence/divergence, `emergent-prices-snapshot-v1`, seven GET-only routes and Research UI panel |
| [Credit relationships](docs/credit-relationships.md) | Owner-scoped credit beliefs, `crd_v1` acts, repayment performances and distributions, researcher-only alignment, `credit-relationships-snapshot-v1`, seven GET-only routes and Research UI panel |
| [Long-horizon scalability](docs/long-horizon-scalability.md) | Measured 10k/100k lanes, historical query/latency evidence, verified envelope, retirement/archive/client limits |
| [Persistence](docs/persistence.md) | Event store, Alembic through `0017`, subjective + scientific evidence, run control, stream outbox, replay |

## Invariants (summary)

1. World state is authoritative.
2. Agents receive immutable, agent-specific observations, never `WorldState`.
3. Objective world state and subjective agent state remain separate.
4. Every agent action is a closed typed command resolved by `WorldEngine` through private world rules.
5. LLM output is untrusted and cannot mutate world state directly (structurally validated `LLMResult` still requires explicit cognition translation).
6. Objective `WorldEvent` values are immutable closed occurrence facts.
7. Agent memories and beliefs are mutable and may be incorrect.
8. Memory is agent- and run-scoped and is never shared automatically.
9. Information crosses agent boundaries only through perception and explicit communication.
10. Randomness is injected and derived from an explicit simulation seed.
11. Cognition is a strategy protocol that returns `AgentCommand` over the same world contracts.

See [docs/architecture.md](docs/architecture.md) and [docs/physical-simulation.md](docs/physical-simulation.md) for the engine lifecycle and physical rules.

## License

CC0-1.0

## Historical lineage explorer

See `docs/lineage-explorer.md` for the eight-family read-only graph API, capture flags, cursors, availability semantics, and bounded native participant queries. The Godot observer exposes default-off generational controls; see `docs/godot-observer.md`.

Optional V3 civilization overlays (regions, settlements, migration, completed-exchange trade, projects, public goods, repositories, culture, technology, groups, and grounded institutions) are documented in `docs/godot-civilization-overlays.md`, including evidence classes, captured-history cursors, and the optional `compose.civilization.yaml` deployment.
