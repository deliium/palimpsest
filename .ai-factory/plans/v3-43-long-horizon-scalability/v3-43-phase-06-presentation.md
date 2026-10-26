# Phase 6: Bounded Godot playback and honest Research UI history

Plan: [index.md](index.md)
Tasks: 16–18
Depends on: Tasks 9, 11–12; batch analytics in Task 15 is not a client-paging prerequisite

## Objective

Make long-history interaction bounded and correctly scoped without dropping scientific events, silently skipping page rows or displaying a different historical publication.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `clients/godot-observer/scripts/net/session.gd` | playback request 820; seek 1336; `_begin_seek` 1370 | Existing one in-flight/one staged-frame and seek serial mechanisms should be preserved. |
| `clients/godot-observer/scripts/net/civilization_source.gd` | caps 10+ | Already bounded rows/pages/bytes/cache/in-flight work; raising caps is not the main solution. |
| `clients/godot-observer/scripts/protocol/playback.gd` | LOD thresholds 15+ | Presentation coalescing must not truncate scientific journal pages. |
| `clients/research-ui/src/views/PopulationPanel.svelte` | `loadMarkers` 122; `loadBoundary` 175; `loadAgents` 259; `loadCohorts` 283 | Auto page ceiling can appear complete; agent/cohort accumulation lacks total caps and request epochs. |
| `clients/research-ui/src/research/paging.ts` | `ExplicitPager` 33; cap handling 115–119 | Advancing past a partially consumed page can lose unseen rows. |
| `clients/research-ui/src/research/requests.ts` | `ResearchScopeController` 46; `BoundedRequestPool` 146 | Scope cancellation exists; queue size is not bounded by active concurrency. |
| `clients/research-ui/src/research/sampling.ts` | `MarkerHighWater` 87 | Existing revision/credential pinning should use real generations, not literal zero. |
| `clients/research-ui/src/views/LineagePanel.svelte` | snapshot discovery 124–136 | First-page/first-snapshot fallback can misrepresent requested history. |
| `tests/compose/test_observer_civilization_browser.py` | repeated seeks 341–356 | Existing browser latency/semantic acceptance is separate from backend-only timing. |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `clients/godot-observer/scripts/net/session.gd`, `clients/godot-observer/scripts/net/civilization_source.gd` | modify | Bounded request/byte/cache diagnostics and complete seek/catch-up lifecycle. |
| `clients/godot-observer/tests/test_civilization_playback.gd`, `clients/godot-observer/tests/test_session_cursor.gd` | modify | Repeated seeks, late events, stale responses and bounded cache checks. |
| `clients/research-ui/src/research/paging.ts`, `requests.ts`, `sampling.ts` | modify | Lossless explicit paging, bounded queue and correct scope identity. |
| `clients/research-ui/src/views/PopulationPanel.svelte`, `LineagePanel.svelte` | modify | Explicit continuation, honest availability, scoped requests and exact historical selection. |
| `clients/research-ui/src/api/research.ts` | modify | Reuse bounded publication resolution; propagate scope/signal and continuation status. |
| `clients/research-ui/src/research/paging.test.ts`, `requests.test.ts`, `sampling.test.ts` | modify | Core bounded behavior tests. |
| `clients/research-ui/src/views/PopulationPanel.test.ts`, `LineagePanel.test.ts` | create | View-level stale-response and historical selection regressions. |
| `tests/benchmarks/test_v3_historical_queries.py`, `tests/integration/test_v3_historical_query_safety.py` | create | Cross-surface large-history and long-dead query acceptance. |
| `tests/compose/test_observer_civilization_browser.py` | modify | Actual browser seek/playback/heap measurements, preserving current acceptance. |

## Task 16: Keep Godot replay bounded under long seek/catch-up workloads

### Implementation Steps

1. Instrument existing request, live-event buffer, staged frame, overlay queue and cache lifecycles with counters/byte estimates. Keep the current one in-flight plus one desired target model and bounded civilization cache. Do not retain a frame per visited tick.
2. Exercise 50 alternating early/late seeks over a large committed log and many lineage/civilization publications. Ensure a new seek cancels/invalidates previous work by serial, old overlay responses cannot replace a newer cursor and timed-out/missing layers are explicit. Preserve capture-off objective playback.
3. Use Task 9 indexed event lookup and keyset catch-up for late event IDs; continue pages by exclusive cursor, never assuming an empty filtered page is EOF when a continuation exists. Existing live-buffer discard must show behind-live/catch-up state and cannot block simulation.
4. Keep LOD/coalescing presentation-only. Verify the committed semantic digest and event cursor path are identical at ordinary/reduced/snap/aggregate playback modes, even when not every intermediate animation is rendered.
5. Add debug instrumentation behind existing development controls; no per-event payload logging, credential caching, protocol rename or changes to scientific stream content.

### Required Interfaces and Contracts

Existing server page/read budgets, observer protocol, signed publication cursors and authorization remain. Godot coordinates, speed and focus never affect world state. Do not advertise browser FPS from backend page latency.

### Requirement Evidence

User: Godot replay, historical seek and observer playback. Existing presentation authority/LOD/queue contracts above.

### Error Handling and Logging

Stale responses are discarded by identity, not shown as missing historical facts. Timeouts/capture gaps remain typed availability states. DEBUG counts/durations and safe reason codes; no credentials/query-string authentication or subjective body dumps.

### Tests

Extend protocol tests for 50 repeated alternating seeks, late-ID lookup, eventful/eventless targets, slow/failing overlays, credential change, behind-live reconnect, cancellation and all LOD modes. Assert request/cache/byte counters return to configured bounds after completion and at most one staged frame remains.

### Acceptance Criteria and Verification

Run the pinned Godot 4.7 executable from `docs/development.md`: `"${GODOT_BIN}" --headless --editor --path clients/godot-observer --quit`, then `"${GODOT_BIN}" --headless --path clients/godot-observer --script res://tests/run_protocol.gd`. Run browser acceptance in Task 18; missing pinned engine/browser is an unexecuted gate, never a pass.

## Task 17: Make Research UI historical paging lossless and scope-safe

### Implementation Steps

1. Fix `ExplicitPager` before integrating it broadly. Keep at most one unconsumed page suffix; do not advance the server continuation until every row from the current page has been delivered. At a view/item cap return an explicit `limited` state plus a continuation action. Resetting the window or loading more drains the suffix before fetching the next page. Keep cursor-bound server page size stable.
2. Bound both active and queued work in `BoundedRequestPool`. Queued work is tagged by scope epoch; cancellation removes/rejects old-scope tasks without issuing HTTP. Queue saturation returns a typed limited/busy result, not an unbounded promise chain.
3. Apply `ResearchScopeController` and explicit pagers to agent/cohort/marker loads. Pin identity to actual run/head revision, boundary/publication and credential generation; refresh obtains a fresh head. Abort on run/owner/boundary/credential changes, reject stale responses and clear private cached rows.
4. Replace the silent 25-page marker loop limit with explicit coverage/continuation UI. Existing deterministic history sampling may remain, but label sampled boundary counts and incomplete discovery. Do not render a sampled trend as complete history.
5. Replace `LineagePanel` first-snapshot fallback with exact requested-boundary resolution using the existing bounded resolver/paginated discovery. If not found within the scan budget, show `scan_limited` plus continue/refine action, not the first snapshot or a false claim of absence. Preserve precise evidence class and owner/debug credentials.
6. Keep in-memory view/item/byte caps; do not add localStorage/IndexedDB private historical caches. Reuse existing bounded APIs and no-store rules. Add explicit load-more/window controls rather than silently dropping oldest required rows.

### Required Interfaces and Contracts

No skipped page rows, cross-boundary results or stale credential content. Repeated cursors/publication changes remain errors. Item/cache caps are resource safeguards, not scientific-history deletion. All interface availability/truncation states reflect backend evidence.

Task 17 depends on Tasks 11–12's historical reader contracts, not Task 15's offline batch evidence path. Its existing API/request helpers can be exercised without installing new analytical reducers or batch loaders.

### Requirement Evidence

User: Research UI history, pagination and long-dead historical queryability. Existing `ExplicitPager`, scope controller and publication cursor contracts.

### Error Handling and Logging

Abort is not reported as data absence. Cursor expiry/replacement prompts exact rediscovery and scoped reset. Safe development counters only; no private payload, credential or raw fetch-error dumps.

### Tests

Page size larger than remaining local window; drain buffered suffix exactly once; repeated/empty continuation; scope change while queued/in-flight; aborted queue frees capacity; 25+ marker pages; refreshing head; exact boundary beyond first 200 snapshots; no matching boundary; unavailable debug; long-dead population/cohort row after several explicit continuations. Test the rendered view, not only utility functions.

### Acceptance Criteria and Verification

`pnpm --dir clients/research-ui check` and `pnpm --dir clients/research-ui test` pass. Request-count and retained-row assertions prove fixed bounds; loaded row order/identity equals complete reference paging across many windows.

## Task 18: Exercise real historical safety across backend and clients

### Implementation Steps

1. Extend the Task 1 fixture to publish genuine generational evidence with admissions/deaths, records, genealogy, technology and institutional lineage. Combine one representative existing supported v55 preset with a separately generated high-volume journal; label synthetic log-size tests separately from scientific simulation tests.
2. Test seek at 0/death/cohort/checkpoint/end boundaries, late event ID beyond 10k events, deep lineage adjacency/catalogue cursors and civilization row cursors beyond the old physical-read ceiling. Query long-dead owners after runner teardown using persisted objective/captured evidence and explicitly verify uncaptured subjective availability is unchanged.
3. Test pinned publication replacement, expired/cross-scope cursors, corruption, limited scan, unavailable capture and credential rotation across Python and UI. Inspection cannot read subjective evidence; debug access remains separately required. All history routes remain GET-only/no-store.
4. Run the existing real-browser control-to-visible benchmark plus repeated seek/playback instrumentation. Preserve its existing acceptance threshold; record actual sample counts, frame-time/heap metrics and warm conditions. Backend-only runs are not browser evidence.
5. Test several observers including a stalled consumer while simulation progresses. No subscriber drain blocks commit, no scientific event is coalesced, and successful reconnect traverses every durable event cursor exactly once.

### Required Interfaces and Contracts

Capture failure and science failure remain separate. Tests compare exact objective event hashes before/after observer activity. Durable restart supports objective/captured historical reads, not full subjective continuation. No new API version or client write authority.

### Requirement Evidence

User: measured historical seek, lineage, observer playback and immutable provenance. Architecture: inspection/debug separation and read-only clients.

### Error Handling and Logging

Fail correctness cases on wrong historical identity or permission leakage regardless of speed. Missing browser/database prerequisites record an unexecuted gate. Emit bounded scenario/count/timing summaries, not screenshot/DOM/private evidence contents into logs.

### Tests and Acceptance Criteria

`uv run pytest -m integration tests/integration/test_v3_historical_query_safety.py --cov=api --cov=simulation --cov=persistence --cov-report=term` passes. Run `uv run pytest -m 'integration and scale' tests/benchmarks/test_v3_historical_queries.py --cov=api --cov=persistence --cov=simulation --cov-report=term`, plus configured `-m compose` browser acceptance. Every synthetic, scientific, backend and browser result is labelled separately.

## Phase Risks and Mitigations

- A local cap can silently skip rows: retain one pending suffix and test exact concatenation across windows.
- A fast stale response can show wrong history: enforce scope/epoch/publication checks at both queue and render boundaries.
- Existing client caps are not support limits: measure actual workloads and leave quotas honest.

## Phase Completion Checklist

- Tasks 16–18 pass scoped paging, protocol and real historical query checks.
- Presentation changes leave exact scientific history unchanged.
- Update progress only in `index.md`.
