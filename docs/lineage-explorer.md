# Historical Lineage Explorer

Read-only backend for navigating captured historical lineage evidence. The same
HTTP contract serves Godot and the Research UI; no client-specific layout or
graph assembly exists on the server.

## Authority and evidence classes

Lineage is **not** one truth graph. Every query selects exactly one family and
one evidence class:

| Family | Objective | Subjective (one owner) | Analytical |
|---|---|---|---|
| `genealogy` | yes | no | no |
| `record` | yes | no | no |
| `mentorship` | no | yes | yes |
| `knowledge` | no | yes | yes |
| `technology` | no | yes | yes |
| `narrative` | no | yes | yes |
| `institution` | no | no | yes |
| `office_succession` | no | yes | no |

Objective evidence uses `OBJECTIVE_INSPECTION`. Every subjective or analytical
query uses `SUBJECTIVE_DEBUG` (debug enabled plus the debug credential). Debug
is not an additional inspect gate, and inspect alone never reveals subjective
metadata or analytical totals.

Node identity is qualified by `(run_id, family, evidence_class,
identity_owner, native_kind, native_id)` and exposed as a SHA-256 `key`.
Analytical agent/event references are shared and ownerless; owner-local entries,
variants, offices and episodes retain their source owner. The same local entry
ID in two owners cannot collide.

## Capture and availability

Capture is opt-in and default off. It runs only after complete subjective
finalization at a boundary `B` and publishes immutable sibling artifacts under
an operator-configured root:

```text
<root>/runs/<sha256(run_id)>/
  state.json
  commits/<commit-ref>/manifest.json
  scopes/<scope-key>/snapshots/<boundary-16-hex>/<publication-id>/
```

`state.json.committed_ref` is the single publication point. Readers ignore
pending, abandoned or unreachable files. Crash recovery is writer-only and
bounded to the explicit pending reservation. Quotas are cumulative per run:
1,000 scoped publication reservations and 256 MiB encoded artifact bytes,
including staging/orphan bytes and a 256 KiB control-record allowance. They are
not a resettable session allowance or an OS disk quota. Abandoned attempts stay
charged; identical successful retries are free.

Capture cadence, `--lineage-max-publications` and `--lineage-max-bytes` are
applied as cumulative per-run limits. A successful scientific run writes an
adjacent `lineage-capture-status-v1` document containing the captured boundary,
published analytical families, unavailable reasons and any capture failure code;
capture failure never changes the simulation result, stop reason or exit status.

Capture cadence can skip boundaries. A missing boundary is unavailable, never a
measured complete zero. Previously observed ancestry may survive ledger
eviction as archived metadata; uncaptured private history cannot be recovered
from replay. Analytic institution/narrative results are published only for
boundaries with detailed valid inputs.

Run capture from the trusted research runner:

```sh
uv run palimpsest-matrix generational \
  --config CONFIG.json --execution-recipe RECIPE.json \
  --artifact-root ARCHIVE --run-id RUN --code-revision REV --source-clean \
  --lineage-root /srv/palimpsest/lineage --lineage-cadence 1 \
  --lineage-max-publications 1000 --lineage-max-bytes 268435456
```

Non-root lineage flags require `--lineage-root`. Runtime capture failure is
warned and does not change scientific results, stop reasons or exit status.
The API setting `PALIMPSEST_LINEAGE_ROOT` is reader-only; it never starts
capture. `PALIMPSEST_LINEAGE_CURSOR_KEY` (at least 32 UTF-8 bytes) is optional
for multi-worker or restart-stable cursors; otherwise a process-local key is
generated.

### Native mentorship participants

`GET /v1/simulations/{run_id}/lineage/mentorship/participants` returns
`lineage-participants-v1`. It is the learner-side discovery path because a
captured mentorship graph does not connect every learner. Required
`evidence_class` (`subjective` or `analytical`) and `agent_id`; subjective also
requires `owner_id`. Optional `role` (`teacher|learner|both`), `boundary_tick`,
opaque `after`, and `limit` (default 100, maximum 200).

The service walks the native node catalogue in canonical key order and examines
at most 200 candidate nodes per request, stopping earlier after `limit` matching
cards. A sparse scan returns an empty page with a continuation and
`scan_limited=true`; it is not a complete "no teacher/student" claim. The cursor
position is the last examined node, not the last match. Physical-read/source-byte
budget exhaustion is an error, never a fabricated continuation. Signed
continuations bind purpose, scope/run/owner/evidence, publication ID/digest,
boundary, filter fingerprint (agent, role, page size), and last examined key,
with the same 15-minute TTL. A replacement publication at the same boundary
cannot reuse an old cursor.

Cards retain native teacher, learner, owner, lineage/root, parent, kind, opaque
content key, hop, acquisition/update ticks, attempt count, learning-evidence
count, confidence, mutation flag, native status, evidence references, policy
version, and observed boundaries. `learning_state` is `attempt_only` when the
evidence count is zero, otherwise `learning_evidence`. A page is ordered by
learning-evidence count descending, attempts descending, acquisition tick
ascending, then qualified node key. This is disclosed evidence priority within
loaded records, not global cultural importance. Attempt-only cards remain a
separate group and never assert successful learning. Owner-local identities are
never merged across owners; analytical cards retain native owner provenance.
Content keys never become knowledge-entry IDs by string matching. The native
catalogue read correction changes completeness of scanning, not the stored
artifact format.

## HTTP

All routes are GET-only and return `Cache-Control: no-store`:

```text
GET /v1/simulations/{run_id}/lineage/families
GET /v1/simulations/{run_id}/lineage/{family}/snapshots
GET /v1/simulations/{run_id}/lineage/{family}/nodes
GET /v1/simulations/{run_id}/lineage/{family}/traverse
GET /v1/simulations/{run_id}/lineage/mentorship/participants
```

Common query parameters: `evidence_class`, `owner_id` (subjective only),
`boundary_tick`, `after` (opaque cursor), `limit` (1–200 graph records).
`nodes` accepts paired `native_kind`/`native_id`; either alone is rejected.
`traverse` accepts `root_key`, `direction` (`ancestors`, `descendants`, `both`),
`max_depth` (0–32), `max_nodes` (1–1,000), `max_edges` (1–4,000) and
`living_only` (genealogy only).

Examples use header credentials; never put credentials in a URL:

```sh
# Which living agents descend from Alice?
ROOT=$(curl -sG -H "x-palimpsest-token: $INSPECT" \
  "$BASE/v1/simulations/$RUN/lineage/genealogy/nodes" \
  --data-urlencode evidence_class=objective \
  --data-urlencode native_kind=agent \
  --data-urlencode native_id=agent-alice | jq -r '.items[0].ref.key')
curl -sG -H "x-palimpsest-token: $INSPECT" \
  "$BASE/v1/simulations/$RUN/lineage/genealogy/traverse" \
  --data-urlencode evidence_class=objective \
  --data-urlencode root_key="$ROOT" \
  --data-urlencode direction=descendants \
  --data-urlencode living_only=true \
  --data-urlencode boundary_tick=100

# Who learned this technique from whom?
curl -sG -H "x-palimpsest-token: $DEBUG" \
  "$BASE/v1/simulations/$RUN/lineage/knowledge/traverse" \
  --data-urlencode evidence_class=analytical \
  --data-urlencode root_key="$TECHNIQUE_ENTRY_KEY" \
  --data-urlencode direction=ancestors

# How did this institution develop?
curl -sG -H "x-palimpsest-token: $DEBUG" \
  "$BASE/v1/simulations/$RUN/lineage/institution/traverse" \
  --data-urlencode evidence_class=analytical \
  --data-urlencode root_key="$EPISODE_KEY" \
  --data-urlencode direction=ancestors

# Which narrative variants descend from the claimed original event?
curl -sG -H "x-palimpsest-token: $DEBUG" \
  "$BASE/v1/simulations/$RUN/lineage/narrative/traverse" \
  --data-urlencode evidence_class=subjective \
  --data-urlencode owner_id=agent-alice \
  --data-urlencode root_key="$VARIANT_KEY" \
  --data-urlencode direction=descendants
```

Traversal records are canonical graph records: one node discovery or one
admitted edge. A page repeats endpoint descriptors as page context when an edge
crosses a page boundary. `matched_node_keys` distinguishes filtering matches;
`context_only_node_keys` marks nodes returned only as context. `living_only`
never hides dead ancestors needed to reach living descendants.

`continuation` / `next_cursor` is opaque and purpose-specific:

- traversal pins snapshot identity/digest, root, effective query fingerprint
  and next record offset;
- node catalogue pins snapshot and native-kind/ID filter and last node key;
- snapshot catalogue pins run commit, catalogue generation and last
  `(boundary_tick, publication_id)` key.

Cursors expire after 15 minutes, are not credentials, and never broaden owner,
run, family or evidence scope. Resume with identical parameters. Traversal
limits are selection limits: page through the selected neighborhood, then
re-root to explore beyond it.

## Errors and limitations

Stable codes include `invalid_lineage_scope`, `invalid_lineage_budget`,
`invalid_lineage_cursor`, `lineage_cursor_expired`, `lineage_run_not_found`,
`lineage_root_not_found`, `snapshot_unavailable`, `lineage_snapshot_corrupt`,
`lineage_storage_unavailable` and `lineage_source_budget`. Missing/disabled
captured history is not reported as a valid empty complete graph.

Out of scope: natural-language queries, name-based identity inference, graph
layout, UI code, a graph database, upload/import endpoints, query-triggered
capture, auto-repair, garbage collection, arbitrary source paths, full
subjective restart and retroactive recovery of uncaptured ledgers. Lineage
artifacts are researcher read models, not world registries or institutional
authority.

## Physical paging and compression

New publications use `lineage-store-index-v2`: a bounded `store/root.json`
authenticates paged directories for the node catalogue, adjacency, identity
lookup and object integrity. Catalogue pages, adjacency pages and identity
objects are content-addressed and reused across publications; quota charging
remains logical. Readers dispatch v1 manifest/object layouts and v2 root/index
layouts, select pages before filtering, and read only the indexed adjacency for
the requested node/direction. Deep cursors and lossless continuation preserve
every edge and witness; v1 publications remain readable. See
[Long-horizon scalability](long-horizon-scalability.md).

## Compatibility

This feature adds no command, event, observer semantic type, metric family,
runner/result version, SQL migration or `/v2` route. Baseline stays SQL head
`0017`, default runner/result v4/v2, latest feature runner v55, 43 commands,
73 observer semantics, 136 metric families, replay-v22/codec v20 when selected,
`/v1` and `observer-protocol-v1`.

Current catalog: 216 metric families; 43 commands; 73 observer semantic types; Alembic `0017`.
