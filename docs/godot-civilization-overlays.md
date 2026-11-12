# Godot civilization overlays

[← Godot observer](godot-observer.md) · [Back to README](../README.md) · [Research causal debugger →](research-causal-debugger.md)

Optional, read-only overlays for long-horizon V3 evidence: regions, migration,
multiple settlements, completed-exchange trade, collective projects, public
goods, physical repositories and records, attributable technology diffusion,
owner-scoped groups, and physically grounded institutions. The overlays are
presentation only. They do not create objective settlements, institutions,
trade routes, coordinates, permissions, or a client write path.

The controls are default off. Captured history is optional and produced outside
the API; a run without a publication remains usable as an objective map.

## Evidence classes

| Class | Meaning | Examples | Authorization |
| --- | --- | --- | --- |
| **OBJECTIVE** | Committed physical facts | regions, routes, location counts, journeys, projects, public-good acts, repositories, records | `objective_inspection` |
| **SUBJECTIVE** | One owner's stored claim | selected-owner groups, technology knowledge beliefs, institution concepts/offices | `subjective_debug` + selected owner |
| **ANALYTICAL / INFERRED** | Detached measurement or classification | settlement candidates, completed-exchange trade, culture frequencies, technology diffusion, inferred communities and institution episodes | `subjective_debug` |

Badges never rely on color alone. A subjective row always carries its owner;
analytical rows never merge several owners into a peer consensus.

## What each visualization means

| Visualization | Class | Rule |
| --- | --- | --- |
| Regions / routes / locations | OBJECTIVE | Exact configured membership and routes. Overlapping region envelopes are not adjacency. Unassigned locations stay unassigned. |
| Population / location counts | OBJECTIVE | Exact living body counts from the displayed cursor. Missing rows are unknown, not zero. |
| Settlement candidates | ANALYTICAL | Four complete occupancy boundaries plus at least one intact structure at boundary `B`. Status is `active`, `inactive`, `censored`, or `insufficient_history`. There is no objective settlement entity. |
| Migration journeys | OBJECTIVE | Bodies stay at the origin until arrival. `preparing`, `capacity_wait`, `arrived`, and `ended` are distinct; a failed/ended journey is not a completed move. No invented mid-edge position. |
| Trade | ANALYTICAL | Only committed `ExchangeCompleted` events count. Gifts, proposals, withdrawals, and co-location are not market exchange; no invented transport route or value. |
| Collective projects | OBJECTIVE | Work/material contributions and completion are physical facts. They are not leadership, a crew, access rights, or an institution. |
| Public goods | OBJECTIVE | Benefit/maintenance/opposition acts are receipts. A benefit is not an access grant or a moral role. |
| Repositories / records | OBJECTIVE | Custody, membership, retrieval, damage, destruction, and neglect are physical. Marks/records do not prove meaning, truth, or a Library institution. |
| Culture | ANALYTICAL | Exact trait identities, living carriers, eligible denominators, and present-location partitions. A partial inventory keeps unknown carriers unknown and a null complete proportion; it is never terrain or `0%`. |
| Technology | ANALYTICAL | Only retained, attributable knowledge acquisition evidence creates source→holder edges. Unknown/ambiguous/rediscovery rows stay separate badges. Knowledge is not performability. |
| Social groups | SUBJECTIVE or ANALYTICAL | Subjective groups show only the selected owner's claims. Inferred communities draw per-member halos with explicit missing interaction/trust/residence lanes; no territory, hull, or nation label. |
| Institutions | SUBJECTIVE or ANALYTICAL | Concepts/offices and lifecycle episodes remain private or detached classifications. A physical pin requires an exact typed project/repository/structure witness. No witness means an unplaced row, never an owner-position or guessed headquarters. |

## HTTP sidecars

All routes are GET, return `Cache-Control: no-store`, and use independent
`observer-civilization-*-v1` envelopes. They do not widen
`observer-protocol-v1` frames, event pages, or WebSocket envelopes.

| Path | Selectors | Notes |
| --- | --- | --- |
| `/v1/simulations/{run_id}/observer/civilization/map` | `section` (`regions`, `routes`, `locations`, `projects`, `repositories`, `records`), `tick`, optional `through_sequence`, `entity_id`, `limit`, `cursor` | Exact objective map at the displayed cursor. |
| `/v1/simulations/{run_id}/observer/civilization/catalogue` | `evidence_class`, optional `owner_id`, `layer`, `limit`, `cursor` | Sorted pinned finalized boundaries for history navigation. |
| `/v1/simulations/{run_id}/observer/civilization/overlays` | `tick`, `layer`, `evidence_class`, optional `owner_id`, `location_id`, `region_id`, `entity_id`, `limit`, `cursor`, `publication_id` | Exact finalized boundary `B`; analytical and subjective evidence. |
| `/v1/simulations/{run_id}/observer/civilization/markers` | `evidence_class`, `from_tick`, `to_tick`, optional `layer`, `owner_id`, `publication_id`, `limit`, `cursor` | Post-event boundary markers; missing intervals stay gaps. |

Layers for overlays are `settlements`, `migration`, `trade`, `culture`,
`technology`, `social_groups`, and `institutions`. The map sections are not
overlay layers.

### Cursors and bounds

- Default page 100 rows; maximum 200 and no more than the API page ceiling.
- Per request: 2,000 decoded/scanned rows, 16 physical files, 12 MiB physical
  reads, 1 MiB response; inline details have their own caps.
- Stored caps: 200 rows/1 MiB per shard, 64 MiB encoded boundary, 10,000
  boundaries, 1,000,000 retained rows, 256 MiB cumulative per run.
- Opaque HMAC cursors bind run, world, purpose, publication digest, scope,
  filters, exact window/boundary, limit, and last scanned key. A page cannot be
  combined with a different publication or filter set.
- `through_sequence` is a required pair with `tick`; an incomplete pair is
  `incomplete_event_cursor`.

### Availability and errors

Unavailable is not empty. The client shows the reason and never substitutes
zero, nearest, or latest data.

| State/code | Meaning |
| --- | --- |
| `publication_pending` | No finished-run publication is visible for this run. Objective map still works. |
| `boundary_not_captured` | The requested exact boundary is absent. No nearest-boundary fallback. |
| `channel_absent` | The publication has no rows for that evidence class/layer at the boundary. |
| `capture_gap` / missing interval | Evidence is incomplete or censored; not extinction or zero prevalence. |
| `restricted` / `debug_disabled` | Debug or selected-owner evidence is unavailable. |
| `invalid_civilization_scope` / `invalid_civilization_query` | Rejected selector combination (400). |
| `cursor_ahead_of_high_water` | Cursor is at or past the committed high water (409). |
| `civilization_context_gone` / `civilization_publication_gone` | Cursor or publication no longer matches (410; restart). |
| `civilization_storage_unavailable` / `civilization_read_budget` / `civilization_storage_corrupt` | Storage or budget failure (503). |

## Capture and publication

Capture is composition-only and default off.

- The API reads `PALIMPSEST_CIVILIZATION_ROOT` through a read-only port. It never
  builds, repairs, or writes a publication, and it does not import the producer
  or analysis.
- `PALIMPSEST_CIVILIZATION_CURSOR_KEY` is a persistent signing key of at least
  32 UTF-8 bytes for restart-stable cursors.
- The trusted producer is the ordinary `research_runner` / `palimpsest-matrix`
  path with `--civilization-overlays-root` and the bounded
  `--civilization-cadence`, `--civilization-max-boundaries`,
  `--civilization-max-rows`, and `--civilization-max-bytes` options
  (defaults: cadence 1, 10,000 boundaries, 1,000,000 rows, 268,435,456 bytes).
- Browser-targeted capture requires an existing durable run in the API's
  configured database. It does not silently switch persistence, mutate a
  scientific config, or rerun a completed run.
- Capture starts before execution. Publication happens only after successful
  scientific completion. Scientific completion and publication readiness are
  separate statuses: a publication failure preserves the scientific artifacts
  and never triggers a backfill or hidden rerun.
- Event receipts are kept every finalized tick independently of inventory
  snapshot cadence. A missing recovered-event interval and a missing private
  snapshot are separate gaps; neither repairs the other.
- Completed runs may be adopted. Archived data is not a durable subjective
  restart. Missing required capture fails preflight; no offline-only browser
  analytics path is claimed.

### Optional Web deployment

Plain `./run.sh` and `compose.yaml` remain the zero-install baseline with no
civilization mount. To browse a separately produced host root, use the optional
override against the same database:

```bash
PALIMPSEST_CIVILIZATION_HOST_ROOT=<host-root> \
PALIMPSEST_CIVILIZATION_CURSOR_KEY=<32+-byte-secret> \
PALIMPSEST_API_INSPECTION_CREDENTIAL=<inspection-secret> \
PALIMPSEST_API_DEBUG_ENABLED=true \
PALIMPSEST_API_DEBUG_CREDENTIAL=<debug-secret> \
docker compose -f compose.yaml -f compose.civilization.yaml up -d --wait
```

The override mounts the host root read-only into the API container (UID 1001)
and configures the same database. The producer writes the host root separately;
the API cannot write it. Do not put credentials in URLs. The plain
`./run.sh` workflow does not need Godot, an editor, natives, or threads.

Open the observer with `?run_id=<run_id>`. Credentials are entered in the
memory-only UI. New analytical/subjective layers use debug; existing aggregate
metric permissions are unchanged.

## Historical playback

- A full frame is a finalized boundary `B`. Overlays require that exact `B`.
- A prefix `(T,S)` shows the objective map only; it cannot be joined to live
  metadata or promoted to a captured overlay.
- Missing exact boundaries are explicit unavailable states, never a nearest or
  latest substitution.
- **Recorded boundaries only** advances between pinned catalogue boundaries,
  displays the exact accepted `B`/target, and disables itself on an empty
  catalogue. Ordinary objective playback is unchanged.
- Automatic presentation stages one frame plus matching first-page sidecars. It
  waits at most 2 seconds for the sidecars, displays matching intermediate
  bundles, and marks timed-out layers unavailable without discarding ready
  layers. A timed-out layer is not zero or disappearance.
- High speed simplifies drawing, not event history. Detail tiers are
  `full`, `reduced`, `snap` (at 8×), and `aggregate` (at 16×). Transient effects
  are capped; flow/link/glyph caps are disclosed when suppressed. Semantic state
  is compared at a common cursor; drawings are compared at a common paused LOD.

## Verification handoff

Measured on the current worktree (HEAD `7037aa0`, uncommitted Task 17 changes)
with locally built image `palimpsest-api:ci`
(`sha256:2a013ffb787d5f5158be3d2b733c4947d315217214f032b315cddbb8ff272282`) and
pinned Godot **4.7.2-stable**.

| Check | Result |
| --- | --- |
| Published-image browser suites (`observer`, `generational`, `civilization`) | 5 passed |
| Real `civ-real-` run | 256 ticks, 257 boundaries, positive exchange/project/public-good/repository evidence |
| Real full vs aggregate LOD semantic digest | equal |
| Browser feedback budget | 20 interactions, p95 ≤ 250 ms |
| 50 browser seeks | ≤ 2 in-flight, bounded queued/state counts |
| Dense 2,000-row render pack | 10 bounded pages, read p95 28.266 ms, 50 repeated reads bounded |
| Task 16 authority/privacy/compatibility gate | 552 passed |
| Task 17 pin/fixture/mirror checks | 14 passed |
| `ruff check src tests`, `mypy src`, `lint-imports` | pass (25 contracts kept) |
| Pinned Godot editor + `tests/run_protocol.gd` | pass, `failed=0`, includes three intermediate playback bundles |

Provenance: `civ-real-` is a real durable 256-tick AY/BL producer run.
`civ-constructed-` is separate **constructed presentation evidence** published
through the real composer/filesystem reader; it proves rendering and API
provenance, not spontaneous civilization behavior. The dense 2,000-row pack is a
rendering/reader load fixture, not a scientific long run.

Known unexecuted release gate: none from the Task 17 functional/browser/Godot
checks above. The image was built locally rather than pulled from the registry;
no commit, push, or deployment was performed.

## See Also

- [Godot observer](godot-observer.md) — credentials, timeline, playback, zero-install client
- [Read-only observer](observer.md) — protocol frames and sidecar routes
- [Lineage explorer](lineage-explorer.md) — related capture/cursor/availability semantics
- [Cultural evolution metrics](cultural-evolution-metrics.md) — culture denominators and windows
- [Configuration](configuration.md) — civilization reader settings and deployment

## Border overlays (V4-13)

Four default-off overlay kinds preserve the three evidence classes:

| Overlay kind | Evidence class | Visual |
| --- | --- | --- |
| `border_physical` | `OBJECTIVE` | solid marker |
| `border_claims` | `SUBJECTIVE_TO_SELECTED_AGENT` | dashed outline |
| `border_agreements` | `SUBJECTIVE_TO_SELECTED_AGENT` | double outline plus badge |
| `border_patterns` | `ANALYTICAL_INFERRED` | dotted marker |

Agreement remains a distinct subjective overlay, not a fourth evidence class.
Tokens never appear in a URL; the debug capability travels in the header.

## Migration overlays (V4-14)

Four default-off overlay kinds preserve the same three evidence classes:

| Overlay kind | Evidence class | Role |
| --- | --- | --- |
| `migration_route` | `OBJECTIVE` | published route tokens |
| `migration_cause` | `SUBJECTIVE_TO_SELECTED_AGENT` | owner cause evidence |
| `migration_wave` | `ANALYTICAL_INFERRED` | wave / displacement_like classification |
| `migration_integration` | `ANALYTICAL_INFERRED` | integration outcome counts |

Cause and wave stay visually distinct. Integration is analytical, not a fourth
evidence class. The observer protocol, capabilities, `/version`, and three-class
evidence model are unchanged.

Current catalog: 216 metric families; 43 commands; 73 observer semantic types; Alembic `0017`.
