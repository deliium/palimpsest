# Research API

[← Architecture](architecture.md) · [Simulation runner](simulation-runner.md) · [Persistence](persistence.md) · [Back to README](../README.md)

Palimpsest V1 exposes a FastAPI **research and inspection** surface — not a production public service. A researcher SPA is served at **`/research/`** when `PALIMPSEST_RESEARCH_WEB_ROOT` is configured (see [Research UI](research-ui.md)). Godot remains at `/`. Mount `/research/` before the presentation catch-all.

## Capabilities

Separate credentials gate four capability classes (`PALIMPSEST_API_*`):

| Capability | Purpose |
| --- | --- |
| Simulation control | create / configure / start / tick / run / stop / list / status |
| Objective inspection | world projection, commits/events, agent-visible observations, metrics catalog/documents, replay, inspect run index, matrix FS |
| Streaming | resumable WebSocket progress/events from the durable outbox |
| Subjective debug | owner-scoped memories / beliefs / relationships, projections, graph summaries, debugger (disabled by default) |

Secrets use strong `SecretStr` values. Query-string secrets are rejected. Prefer header or WebSocket subprotocol transport.

## REST (`/v1`)

- `POST /v1/simulations` — create/configure with canonical runner-config payload
- `POST /v1/simulations/{run_id}/start|tick|run|stop`
- `GET /v1/simulations` / `GET /v1/simulations/{run_id}` — list/status (`simulation_control`)
- `GET /v1/research/runs` — inspect-scoped read-only run index (`objective_inspection`; Research UI default discovery)
- Objective world, commits/events (keyset pagination), agent-visible observation
- Metric catalog and immutable metric documents
- Subjective **projections** under `subjective_debug`: goals, emotional-state, self-model (identity/goals projection — not a second belief store), theory-of-mind, group-formation, social-norms, social-conventions, cultural-narratives; plus metadata-safe `memories/summary` and `beliefs/summary` for graphs (count-only `SubjectivePageOut` pages stay for existing clients)
- Read-only matrix filesystem under `PALIMPSEST_RESEARCH_MATRIX_ROOT`: `GET /v1/research/matrices` and allowlisted `manifest.json` / `cells/*` / `aggregate.json` / `metric-summary.json` (path traversal fail-closed; no `analysis` import; no batch starts)
- Formal-rule reads require `subjective_debug`; seven GET-only routes serve a published `formal-rule-snapshot-v1`, return `503 formal_rule_disabled` when `PALIMPSEST_FORMAL_RULE_ROOT` is unset, and use purpose-bound cursors bound to the publication digest:
  - `GET /v1/simulations/{run_id}/formal-rules`
  - `GET /v1/simulations/{run_id}/formal-rules/candidates`
  - `GET /v1/simulations/{run_id}/formal-rules/candidates/{candidate_id}`
  - `GET /v1/simulations/{run_id}/formal-rules/candidates/{candidate_id}/rules`
  - `GET /v1/simulations/{run_id}/formal-rules/candidates/{candidate_id}/versions`
  - `GET /v1/simulations/{run_id}/formal-rules/lineage`

  A changed run, filter, publication, or digest yields `400 formal_rule_cursor_invalid`; an expired cursor yields `410 formal_rule_cursor_expired`.
- Dispute-resolution reads require `SUBJECTIVE_DEBUG` (the `subjective_debug` capability); seven GET-only routes serve a published `dispute-resolution-snapshot-v1`, return `503 dispute_disabled` when `PALIMPSEST_DISPUTE_ROOT` is unset, and never expose capability flags:
  - `GET /v1/simulations/{run_id}/disputes`
  - `GET /v1/simulations/{run_id}/disputes/candidates`
  - `GET /v1/simulations/{run_id}/disputes/candidates/{candidate_id}`
  - `GET /v1/simulations/{run_id}/disputes/candidates/{candidate_id}/claims`
  - `GET /v1/simulations/{run_id}/disputes/candidates/{candidate_id}/resolutions`
  - `GET /v1/simulations/{run_id}/disputes/lineage`

  Every paged route uses a purpose-bound cursor bound to the publication digest; a changed run, filter, publication, or digest yields `400 dispute_cursor_invalid`, and an expired cursor yields `410 dispute_cursor_expired`. `PALIMPSEST_DISPUTE_CURSOR_KEY` keeps cursors restart-stable. See [Disputes](disputes.md).
- Evidence-testimony reads require `SUBJECTIVE_DEBUG` (the `subjective_debug` capability); seven GET-only routes serve a published `evidence-testimony-snapshot-v1`, return `503 evidence_testimony_disabled` when `PALIMPSEST_EVIDENCE_ROOT` is unset, and never expose capability flags or owner ids:
  - `GET /v1/simulations/{run_id}/evidence`
  - `GET /v1/simulations/{run_id}/evidence/candidates`
  - `GET /v1/simulations/{run_id}/evidence/candidates/{candidate_id}`
  - `GET /v1/simulations/{run_id}/evidence/candidates/{candidate_id}/sources`
  - `GET /v1/simulations/{run_id}/evidence/candidates/{candidate_id}/contradictions`
  - `GET /v1/simulations/{run_id}/evidence/lineage`

  Cursor purposes are exactly `summary`, `candidates`, `candidate`, `sources`, `contradictions`, and `lineage`; TTL is 900 seconds. A changed run, filter, publication, or digest yields `400 evidence_testimony_cursor_invalid`, and an expired cursor yields `410 evidence_testimony_cursor_expired`. Each response is charged against a 2 MiB budget. `PALIMPSEST_EVIDENCE_CURSOR_KEY` keeps cursors restart-stable. See [Evidence and testimony](evidence-testimony.md).
- Delegation-representation reads require `SUBJECTIVE_DEBUG`; seven GET-only routes serve a published `delegation-representation-snapshot-v1`, return `503 representation_disabled` when `PALIMPSEST_REPRESENTATION_ROOT` is unset, and expose only hashed owner/principal/representative/actor tokens:
  - `GET /v1/simulations/{run_id}/representation`
  - `GET /v1/simulations/{run_id}/representation/mandates`
  - `GET /v1/simulations/{run_id}/representation/mandates/{mandate_id}`
  - `GET /v1/simulations/{run_id}/representation/mandates/{mandate_id}/positions`
  - `GET /v1/simulations/{run_id}/representation/mandates/{mandate_id}/revocations`
  - `GET /v1/simulations/{run_id}/representation/lineage`
  Cursor purposes are exactly `summary`, `mandates`, `mandate`, `positions`, `revocations`, and `lineage`; TTL is 900 seconds. A changed run, filter, publication, or digest yields `400 representation_cursor_invalid`, and an expired cursor yields `410 representation_cursor_expired`. Each response is charged against a 2 MiB budget. See [Delegation and representation](delegation-representation.md).
- Organization reads under `/v1/simulations/{run_id}/organizations[/candidates|/lineage|/operations|/collective-agency]` require `subjective_debug`; seven GET-only routes serve a published `organization-snapshot-v3` (v1/v2 remain readable), return `503 organization_disabled` when `PALIMPSEST_ORGANIZATION_ROOT` is unset, and never expose capability flags. The operations route filters by `domain` and `organization_id`; the collective-agency route filters by `recognition` and `organization_id`. Every paged route uses a purpose-bound cursor bound to the publication digest; a changed filter, run, publication, or digest yields `400 organization_cursor_invalid`, and an expired cursor yields `410 organization_cursor_expired`. `PALIMPSEST_ORGANIZATION_CURSOR_KEY` keeps cursors restart-stable.
- Macro-society reads under `/v1/simulations/{run_id}/macro-societies[/candidates|/lineage]` require `subjective_debug`; four GET-only routes serve a published `macro-society-snapshot-v1`, return `503 macro_society_disabled` when `PALIMPSEST_MACRO_SOCIETY_ROOT` is unset, and never expose capability flags. `PALIMPSEST_MACRO_SOCIETY_CURSOR_KEY` keeps cursors restart-stable; when absent a per-process key is used. See [Macro-societies](macro-societies.md).
- Replay-to-tick endpoints (detached projection; never live `WorldEngine`)
- Read-only observer manifest, state, events, ticks, run metadata, and live stream. See [Read-only observer](observer.md). Presentation coordinates are not simulation coordinates. Researcher relationship summaries stay on the debug capability.
- Observer event pages accept additive optional filters (`agent_id`, `event_type`, `location_id`) and `catch_up=true` for multi-page reconnect fill within `PALIMPSEST_API_MAX_PAGE_SIZE`. Filter `agent_id` matches events where that id equals **`actor_id` or `target_id`** after adapt (presentation filter; includes target-only rows such as `AGENT_DIED`). Protocol remains `observer-protocol-v1` — no layout/protocol rename for scale.
- Godot observer branch navigation uses the existing lineage GETs (`/branches`, `/branch`, `/branch/fork-point`) under `objective_inspection` and replaces one `ObserverSource` at a time. Local researcher bookmarks stay in the client (`user://`); they are not authoritative history and have no server API.
- Research causal debugger GET routes under `/v1/simulations/{run_id}/debugger/…` require `subjective_debug` (observational; tracing-off → `200` + `unavailable`). See [Research causal debugger](research-causal-debugger.md).
- Research **simulation branches** (deterministic forks):
  - `POST /v1/simulations/{parent_run_id}/branches` — create one child from `fork_tick` + exactly one closed `ResearchIntervention` (`simulation_control`; idempotent on identical fingerprint)
  - `GET /v1/simulations/{run_id}/branches` — list children (keyset)
  - `GET /v1/simulations/{run_id}/branch` — parent lineage or `404`/`branch_root`
  - `GET /v1/simulations/{run_id}/branch/fork-point` / `…/branch/state` — fork cursor + thin run envelope
  - `POST /v1/simulations/branches/compare` — detached journal timeline compare (`objective_inspection`)
  - Research forks are **not** agent `CounterfactualScenario` / prospective rollouts; parent history is never rewritten.

Stable problem-detail errors carry closed reason codes. Lifecycle conflicts return conflict responses without leaking configuration or evidence payloads.

### API versioning (V2 scaffolding)

- Keep **`/v1`** stable. Do **not** introduce `/v2` HTTP routes in this scaffolding plan.
- Introduce `/v2` only when a request/response shape cannot be expressed as optional additive fields on `/v1`.
- WebSocket subprotocol remains `palimpsest.v1` (credentials via header / subprotocol only — never query strings).
- `SimulationManager` stores opaque `config_payload` + fingerprint; decode happens at runner construction.
- Accepted runner config wire versions: `runner-config-v1`…`runner-config-v56` (mode-driven), with default write **`runner-config-v4`** (default-off `V2CapabilityFlags` + disabled tracing). Accepted `runner-config-v23` carries sibling root `v3_capability_flags` (V3 scaffolding; writers emit v23 only when some V3 flag is true; flags-on fail closed at runner construction until owned). Accepted `runner-config-v56` is V4 scaffolding: the active v55 family keyset plus one closed `v4_capability_flags` sibling, with generational siblings present only when a generational run is present. Five V4 flags are owned — `organizations` (V4-03/V4-04/V4-05), `formal_rules` (V4-06), `legal_disputes` (V4-07), `diplomacy` (V4-10/V4-11), and `organized_conflict` (V4-12) — and the other seven remain unowned and fail closed. Legacy v1/v2 payloads must remain creatable/configurable and constructible.
- Observer protocol stays `observer-protocol-v1` / `observer-layout-v1` (Godot↔Python mirror pin). Prefer additive optional fields and semantic types. V2/V3 deliberately kept `GET /version` minimal; V4-01 refined that policy to advertise protocol, layout, and capability **metadata** additively (`supported_observer_protocols`, `observer_layout_version`, `observer_capabilities`, `observer_reserved_capabilities`). It still exposes no capability-flag values or configuration payloads, and `observer-protocol-v2` is reserved but not served.

## Debug security

Subjective debug routes are **disabled by default**. Enabling requires:

- `PALIMPSEST_API_DEBUG_ENABLED=true`
- `PALIMPSEST_API_DEBUG_CREDENTIAL` (required when enabled)

Owner/run scoped, paginated, and absent from logs (no memories, beliefs, relationships, or credentials).

## WebSocket stream

`/v1/simulations/{run_id}/stream`

- Authenticated pre-accept
- Versioned envelopes, one durable monotonic cursor
- Catch-up then live handoff from the PostgreSQL outbox
- Eventless ticks, status/metric/result/error/completion frames
- Bounded per-subscriber queues; slow consumers disconnect without blocking simulation
- Heartbeats and graceful shutdown

`LISTEN/NOTIFY` may wake pollers but is never authoritative.

Observer live WebSocket (`/v1/simulations/{run_id}/observer/stream`) uses the same backpressure pattern: per-subscriber bounded queues (`PALIMPSEST_OBSERVER_STREAM_QUEUE_SIZE`), catch-up batch size (`PALIMPSEST_OBSERVER_CATCHUP_PAGE_SIZE`, capped by `api_max_page_size`), and `slow_consumer` disconnect of that subscriber only. Simulation ticks must not await observer drains. After a client discard-behind-live, reconnect via `GET .../observer/events` (optionally `catch_up=true`) then resume the socket — scientific history stays complete; presentation coalescing lives only in Godot / observer projection helpers.

## Long-run research settings (opt-in)

Defaults preserve short V1 runs. Scale knobs are settings / helpers, not capability flags:

| Knob | Role |
| --- | --- |
| `long_run_checkpoint_policy` / `long_run_persistence_spec` | Enable write-time snapshot cadence (e.g. every 100/500/1000 ticks); no in-DB snapshot DELETE |
| `PALIMPSEST_OBSERVER_STREAM_QUEUE_SIZE` / `PALIMPSEST_OBSERVER_CATCHUP_PAGE_SIZE` | Observer WS backpressure and reconnect batching |
| `PALIMPSEST_MEMORY_RETRIEVE_MAX_CANDIDATES` | SQL candidate cap before `rank_traces` (default 4096) |
| `PALIMPSEST_LLM_MAX_CONCURRENCY` | Process-wide `generate` semaphore (default 1); parallel agent prepare stays off |
| `PALIMPSEST_COGNITION_TRACE_SOFT_CAP_*` | Optional soft stop-append for traces (fail-soft; never DELETE rows) |

See [Persistence](persistence.md), [Observer](observer.md), [Memory reconstruction](memory-reconstruction.md), and [Development](development.md) (`pytest -m scale`) for details. Do not prune append-only tables in place; do not introduce Kafka/K8s for this surface.

## Logging

INFO records route template / method / status / request/run IDs and bounded counts. Never log raw paths, query strings, bodies, tokens, seeds, evidence, metrics, prompts, or exception text.

## Verification

```bash
uv run --frozen --python 3.12.14 pytest \
  tests/unit/test_api_simulation_manager.py \
  tests/unit/test_api_simulation_routes.py \
  tests/unit/test_api_inspection_routes.py \
  tests/unit/test_api_replay_routes.py \
  tests/unit/test_api_streaming.py -q

# Opt-in PostgreSQL
PALIMPSEST_TEST_DATABASE_URL=<disposable-palimpsest_test-dsn> \
uv run --frozen --python 3.12.14 pytest -m integration \
  tests/integration/test_api_simulation_lifecycle.py \
  tests/integration/test_api_event_pagination.py \
  tests/integration/test_api_debug_scope.py \
  tests/integration/test_api_stream_resume.py \
  tests/integration/test_api_stream_backpressure.py \
  tests/integration/test_v1_api_e2e.py -q
```

## Researcher symbolic-language overlay

`GET /v1/simulations/{run_id}/observer/agents/{agent_id}/symbolic-language`
returns an additive researcher-only overlay from the owner runtime checkpoint.
It exposes composition ids, part digests, operator, status, strength band, usage
count, and meaning revision. It never returns raw symbol tokens, referent entity
labels, message bodies, or objective-frame fields. Objective observer frames
still reject symbolic fields; no Godot protocol or semantic type changes.


### Translation overlay

`GET /v1/simulations/{run_id}/observer/agents/{agent_id}/translation` returns a
researcher-only, digest-only overlay of one owner's translation mappings:
source digest, target label digests, referent kinds/digests, status, fit,
strength band, channel counts, usage count, and tick range. It reads the owner
runtime checkpoint and never exposes raw foreign tokens, target tokens, message
bodies, or another owner's mapping. It is not part of objective frames.

## Researcher generational narrative overlay

`GET /v1/simulations/{run_id}/owners/{owner_id}/cultural-narratives/generational`
returns `research-generational-narratives-v1` behind the existing debug
dependency. It exposes variant IDs, status, origin, themes, subjectively
observed source-loss state/reason, witness/dead/record/transition counts,
carrier count, hop count, first/last tick, and opaque root/source IDs.

The existing `/cultural-narratives` route is unchanged. The overlay reads only
the owner checkpoint, never another owner's ledger, record text, mark bodies,
or story tokens. No observer semantic type, protocol, or Godot layout changes.

## Generational research reads (V3-42)

These are read-only, additive `/v1` routes. They do not start runs, repair
artifacts, enable capture, or run analysis inside HTTP.

### Cultural artifact endpoints

- `GET /v1/research/matrices/{matrix_id}/cultural-comparison`
- `GET /v1/research/matrices/{matrix_id}/cells/{cell_id}/cultural-metrics`
- `GET /v1/research/matrices/{matrix_id}/cells/{cell_id}/cultural-evidence?section=boundaries|traits|transmission|groups|archives&…`

The first two return stored document bodies unchanged with
`X-Palimpsest-Artifact-Binding: runtime_bound|legacy_unverified` and
`Cache-Control: no-store`. Comparison reads bind `matrix_fingerprint` to a real
runtime manifest or are visibly legacy-unverified; no self-digest is invented.
Cell metrics require a completed runtime state and matching
`cells/{cell_id}.completion.json`; completed state alone is `409
research_cell_incomplete`. Structural read validation is not trusted scientific
re-verification.

The evidence page requires `subjective_debug` and returns
`research-cultural-evidence-page-v1`. Page inputs: `section`, inclusive
`from_tick`, exclusive `to_tick`, `owner_id`, `dimension` (boundaries/traits
only), `limit` (default 100, max 200), and a signed `cursor`. Pages are bounded
to 2 MiB; oversized pages shrink before encoding and a single oversized row is
`413 research_artifact_too_large`. Changed pair bytes return `409
research_snapshot_changed`; expired/tampered/filter-mismatched cursors return
`400 invalid_research_cursor`.

Outer JSON is bounded to 64 MiB/depth 32 and nested `values.rows_json` to
16 MiB/depth 32, with duplicate-key and non-finite rejection. Over-size is `413
research_artifact_too_large`; missing root is `503`; missing artifact is `404
matrix_file_missing`; corrupt/unsupported content uses a safe `400` code.

### Retained semantic history

`GET /v1/simulations/{run_id}/observer/agents/{agent_id}/semantic-history`
requires `subjective_debug`.

Query: `source=label|composition`, optional checkpoint `tick`, inclusive
`from_tick`, exclusive `to_tick`, signed `after`, `limit` (max 200). The
`observer-semantic-history-v1` envelope names the requested tick, checkpoint
tick, retained first/last tick, `retained_only=true`, conservative
`prefix_complete=false`, per-term retained first ordinal/current revision, and
rows. Different checkpoint ticks return an explicit unavailable state; a changed
checkpoint or credential scope returns `409 semantic_checkpoint_changed` or
`400 invalid_research_cursor`. No arbitrary historical subjective restart is
claimed, and no label tokens, composition parts or raw referent IDs are exposed.

### Manifest compatibility

Matrix listing/cell discovery accepts both exported `experiment-matrix-v1`
manifests and real producer `matrix-manifest-v1` documents with
`matrix_schema_version=experiment-matrix-v1`. Runtime listings use only declared
cell IDs; legacy exports exclude `.completion.json`, `.metrics.json`,
`.cultural-evidence.json`, `.cultural-metrics.json` and other known sidecars.

## Diplomacy routes

Seven GET-only routes require `SUBJECTIVE_DEBUG`:

| Route | Result |
| --- | --- |
| `GET /v1/simulations/{run_id}/diplomacy` | summary |
| `GET /v1/simulations/{run_id}/diplomacy/relations` | paged relations |
| `GET /v1/simulations/{run_id}/diplomacy/relations/{relation_id}` | relation detail with retained terminations |
| `GET /v1/simulations/{run_id}/diplomacy/instruments` | paged instruments |
| `GET /v1/simulations/{run_id}/diplomacy/instruments/{instrument_id}` | instrument detail |
| `GET /v1/simulations/{run_id}/diplomacy/lineage` | paged lineage |

`PALIMPSEST_DIPLOMACY_ROOT` and `PALIMPSEST_DIPLOMACY_CURSOR_KEY` enable the
read model; an unconfigured deployment returns 503 `diplomacy_disabled`. Unknown
published ids return 404, cursor mismatch 400, and cursor expiry 410. Responses
contain only content-addressed ids, hashed owner/party/envoy/actor tokens, and
owner-safe `orgc-`/region anchors.

### Treaty routes (V4-11)

| Route | Response |
| --- | --- |
| `GET /v1/simulations/{run_id}/diplomacy/treaties` | paged treaty anchors with derived status |
| `GET /v1/simulations/{run_id}/diplomacy/treaties/{treaty_id}` | treaty detail with versions, declarations, recollections, misrepresentations, and lineage |

Both require `SUBJECTIVE_DEBUG`, use the existing publication-bound cursors, and
return tokens, content-addressed record IDs, closed values, and
composer-derived status labels only. The diplomacy GET route total is eight.

## Organized-conflict routes (V4-12)

Seven GET-only routes under `/v1/simulations/{run_id}/organized-conflict` require
`SUBJECTIVE_DEBUG`, return `503 organized_conflict_disabled` when publication is
not configured, and `404 organized_conflict_not_found` for unknown published
runs. Cursor mismatch is `400 organized_conflict_cursor_invalid`; expiry is
`410 organized_conflict_cursor_expired`. The six purposes are `summary`,
`episodes`, `episode`, `plans`, `plan`, and `interpretations`. No `/v2` route
exists.

## Border routes (V4-13)

Seven GET-only routes under `/v1/simulations/{run_id}/borders` require
`SUBJECTIVE_DEBUG`:

| Route | Result |
| --- | --- |
| `GET .../borders` | summary |
| `GET .../borders/claims` | paged claims |
| `GET .../borders/claims/{claim_id}` | claim detail |
| `GET .../borders/agreements` | paged agreements |
| `GET .../borders/agreements/{agreement_id}` | agreement detail |
| `GET .../borders/control` | physical and/or analytical rows via `layer=physical|analytical|all` |

`PALIMPSEST_BORDERS_ROOT` and `PALIMPSEST_BORDERS_CURSOR_KEY` enable the read
model. An unconfigured deployment returns 503 `borders_disabled`; unknown
published runs return 404 `borders_publication_not_found`; unknown records return
404 `borders_record_not_found`; cursor mismatch is 400 `borders_cursor_invalid`
and expiry is 410 `borders_cursor_expired`. A corrupt published store fails with
500 `borders_store_corrupt` rather than a false not-found response. Responses
contain hashed tokens and closed labels only.

## Migration-displacement routes (V4-14)

Seven GET-only routes under `/v1/simulations/{run_id}/migration` require
`SUBJECTIVE_DEBUG`:

| Route | Result |
| --- | --- |
| `GET .../migration` | summary |
| `GET .../migration/waves` | paged analytical waves |
| `GET .../migration/waves/{wave_id}` | wave detail with lineage/alignment tokens |
| `GET .../migration/routes` | paged route beliefs |
| `GET .../migration/causes` | paged cause evidence |
| `GET .../migration/outcomes` | paged integration outcomes |

`PALIMPSEST_MIGRATION_DISPLACEMENT_ROOT` and
`PALIMPSEST_MIGRATION_DISPLACEMENT_CURSOR_KEY` enable the read model. An
unconfigured deployment returns 503 `migration_displacement_disabled`; unknown
published runs or wave tokens return 404 `migration_displacement_not_found`;
cursor mismatch is 400 `migration_displacement_cursor_invalid` and expiry is 410
`migration_displacement_cursor_expired`. A corrupt published store fails with
500 `migration_displacement_store_corrupt` rather than a false not-found
response. The six cursor purposes are `summary`, `waves`, `wave`, `routes`,
`causes`, and `outcomes`. Page `limit` defaults to 100 and is capped at 500.
Optional filters include wave `classification` / `origin_token` /
`destination_token` / `cluster_token`, route `origin_token` /
`destination_token`, cause `cause_kind`, and outcome `outcome` /
`destination_token`. Responses contain hashed tokens and closed labels only; no
raw identities, route bodies, cause text, or refugee/asylum/forced status
fields.

## Inter-society relations routes (V4-15)

Seven GET-only routes under `/v1/simulations/{run_id}/inter-society-relations`
require `SUBJECTIVE_DEBUG`:

| Route | Result |
| --- | --- |
| `GET .../inter-society-relations` | summary |
| `GET .../inter-society-relations/pairs` | paged pairs |
| `GET .../inter-society-relations/pairs/{pair_id}` | pair detail |
| `GET .../inter-society-relations/pairs/{pair_id}/series` | pair time series |
| `GET .../inter-society-relations/comparison` | pair×pair or pair×window comparison |
| `GET .../inter-society-relations/windows` | paged windows |

Both `PALIMPSEST_INTER_SOCIETY_RELATIONS_ROOT` and
`PALIMPSEST_INTER_SOCIETY_RELATIONS_CURSOR_KEY` (≥32 UTF-8 bytes) are required to
attach the reader. An unconfigured deployment returns 503
`inter_society_relations_disabled`; unknown published runs or pair tokens return
404; cursor mismatch is 400 `inter_society_relations_cursor_invalid` and expiry
is 410 `inter_society_relations_cursor_expired`. A corrupt published store fails
with 500 `inter_society_relations_store_corrupt`. Comparison operands are
mutually exclusive: either `pair_a`+`pair_b` or `pair_id`+`window_a`+`window_b`;
mixed or incomplete sets return 400
`inter_society_relations_comparison_invalid`. Cursor purposes are `summary`,
`pairs`, `pair`, `series`, `windows`, and `comparison`. Responses expose domain
counts/availability and vectorial deltas only — never a civilization
relationship score. See [inter-society relations](inter-society-relations.md).

## Infrastructure networks routes (V4-16)

Seven GET-only routes under `/v1/simulations/{run_id}/infrastructure-networks`
require `SUBJECTIVE_DEBUG`:

| Route | Result |
| --- | --- |
| `GET .../infrastructure-networks` | summary |
| `GET .../infrastructure-networks/assets` | paged assets |
| `GET .../infrastructure-networks/edges` | paged edge assets |
| `GET .../infrastructure-networks/condition` | paged condition rows |
| `GET .../infrastructure-networks/effects` | paged effect coverage rows |
| `GET .../infrastructure-networks/maintenance` | paged maintenance rows |
| `GET .../infrastructure-networks/routes` | paged travel-network objective route-condition rows; includes `fingerprint` and `publication` and a purpose-bound `next_cursor` |

The routes page is the only infrastructure page that exposes `fingerprint` and
`publication`; the other six retain their existing page shape.

Both `PALIMPSEST_INFRASTRUCTURE_NETWORKS_ROOT` and
`PALIMPSEST_INFRASTRUCTURE_NETWORKS_CURSOR_KEY` (≥32 UTF-8 bytes) are required to
attach the reader. An unconfigured deployment returns 503
`infrastructure_networks_disabled`. Responses expose objective asset counts and
status fields only — never an infrastructure or civilization score. See
[infrastructure networks](infrastructure-networks.md).

## Trade networks (V4-18)

Seven GET-only routes expose a published `trade-networks-snapshot-v1` under
`SUBJECTIVE_DEBUG`:

```text
/v1/simulations/{run_id}/trade-networks
/v1/simulations/{run_id}/trade-networks/corridors
/v1/simulations/{run_id}/trade-networks/flows
/v1/simulations/{run_id}/trade-networks/locations
/v1/simulations/{run_id}/trade-networks/dependence
/v1/simulations/{run_id}/trade-networks/cross-society
/v1/simulations/{run_id}/trade-networks/networks
```

Paged routes accept `cursor`, `limit`, and an optional `window_index` filter
bound into the 900-second purpose-bound cursor fingerprint. Unconfigured
storage returns `503 trade_networks_disabled`; a corrupt payload returns
`500 trade_networks_store_corrupt`; an absent run returns
`404 trade_networks_run_not_found`. No trade route mutates state.

### Market-like institutions (V4-20)

Seven GET-only routes under `/v1/simulations/{run_id}/market-institutions` serve
the published `market-institutions-snapshot-v1` artifact:

- `/v1/simulations/{run_id}/market-institutions`
- `/v1/simulations/{run_id}/market-institutions/venues`
- `/v1/simulations/{run_id}/market-institutions/gatherings`
- `/v1/simulations/{run_id}/market-institutions/expectations`
- `/v1/simulations/{run_id}/market-institutions/roles`
- `/v1/simulations/{run_id}/market-institutions/records`
- `/v1/simulations/{run_id}/market-institutions/markets`

All require `SUBJECTIVE_DEBUG` and the dual market-institution settings;
`window_index` is bounded to `0..511`, default page size is 100, and maximum is
500. Failure codes are `market_institutions_disabled`,
`market_institutions_store_corrupt`, `market_institutions_cursor_invalid`, and
`market_institutions_cursor_expired`.

### Emergent prices (V4-21)

Seven GET-only routes under `/v1/simulations/{run_id}/emergent-prices` serve the
published `emergent-prices-snapshot-v1` artifact:

- `/v1/simulations/{run_id}/emergent-prices`
- `/v1/simulations/{run_id}/emergent-prices/units`
- `/v1/simulations/{run_id}/emergent-prices/expectations`
- `/v1/simulations/{run_id}/emergent-prices/quotes`
- `/v1/simulations/{run_id}/emergent-prices/distributions`
- `/v1/simulations/{run_id}/emergent-prices/markets`
- `/v1/simulations/{run_id}/emergent-prices/relations`

All require `SUBJECTIVE_DEBUG` and both
`PALIMPSEST_EMERGENT_PRICES_ROOT` / `PALIMPSEST_EMERGENT_PRICES_CURSOR_KEY`
settings. `window_index` is bounded to `0..511`, default page size is 100, and
maximum is 500. Cursors bind the window filter. Failure codes are
`emergent_prices_disabled`, `emergent_prices_run_not_found`,
`emergent_prices_store_corrupt`, `emergent_prices_cursor_invalid`, and
`emergent_prices_cursor_expired`. Distributions expose `sample_source`, five
`bin_shares_milli`, and quantiles; relations expose `overlap_milli` and a closed
relation token. No route returns a canonical price, score, ranking, severity, or
recommendation. See [emergent prices](emergent-prices.md).

### Credit relationships

Seven GET-only routes under `/v1/simulations/{run_id}/credit-relationships`
serve the published `credit-relationships-snapshot-v1` artifact:

- `/v1/simulations/{run_id}/credit-relationships`
- `/v1/simulations/{run_id}/credit-relationships/relationships`
- `/v1/simulations/{run_id}/credit-relationships/claims`
- `/v1/simulations/{run_id}/credit-relationships/performances`
- `/v1/simulations/{run_id}/credit-relationships/distributions`
- `/v1/simulations/{run_id}/credit-relationships/counterparties`
- `/v1/simulations/{run_id}/credit-relationships/alignment`

All require `SUBJECTIVE_DEBUG` and both
`PALIMPSEST_CREDIT_RELATIONSHIPS_ROOT` /
`PALIMPSEST_CREDIT_RELATIONSHIPS_CURSOR_KEY` settings. `window_index` is bounded
to `0..511`, default page size is 100, and maximum is 500. Cursors bind the
window filter. Failure codes are `credit_relationships_disabled`,
`credit_relationships_run_not_found`, `credit_relationships_store_corrupt`,
`credit_relationships_cursor_invalid`, and `credit_relationships_cursor_expired`.
No route returns a bank, money, enforceable debt, credit score, ranking, or
canonical credit. See [credit relationships](credit-relationships.md).

Current catalog: 220 metric families; 43 commands; 73 observer semantic types; Alembic `0017`.

## V4-23 accounting ledger routes

Seven GET-only routes under `/v1/simulations/{run_id}/accounting-ledgers`
serve the published sibling snapshot: summary, entries, records, conditions,
flows, counterparties, and alignment. All require `SUBJECTIVE_DEBUG` and both
`PALIMPSEST_ACCOUNTING_LEDGERS_ROOT` and
`PALIMPSEST_ACCOUNTING_LEDGERS_CURSOR_KEY`; otherwise they return
`accounting_ledgers_disabled`. Default limit is 100 and maximum is 500. Cursors
bind purpose and `window_index`. See [Accounting ledgers](accounting-ledgers.md).
