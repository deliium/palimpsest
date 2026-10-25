# Civilization protocol fixtures

These files are the committed, canonical presentation fixtures consumed by the
Godot civilization parser/render/timeline suites. They are **not** scientific
evidence and they are **not** produced by a live simulation run.

## Provenance

All committed files in this directory are **constructed presentation evidence**:
they exercise strict schemas, evidence classes, cursor windows, pagination,
unavailable states and rendering paths. They must not be cited as proof of
spontaneous emergence or as a real long-horizon run.

| Fixture | Kind | Evidence | Identity |
| --- | --- | --- | --- |
| `map_locations.json` | objective map section | OBJECTIVE | `run-physical` / `world-physical`, B=4 |
| `map_regions.json` | objective map section | OBJECTIVE | `run-physical` / `world-physical`, B=4 |
| `map_routes.json` | objective map section | OBJECTIVE | `run-physical` / `world-physical`, B=4 |
| `map_projects.json` | objective map section | OBJECTIVE | `run-physical` / `world-physical`, B=4 |
| `map_repositories.json` | objective map section | OBJECTIVE | `run-physical` / `world-physical`, B=4 |
| `map_records.json` | objective map section | OBJECTIVE | `run-physical` / `world-physical`, B=4 |
| `overlay_settlements.json` | captured overlay | ANALYTICAL | `run-capture` / `world-capture`, B=4 |
| `overlay_migration.json` | captured overlay | OBJECTIVE | `run-capture` / `world-capture`, B=4 |
| `overlay_trade.json` | captured overlay | ANALYTICAL | `run-capture` / `world-capture`, B=4 |
| `overlay_culture.json` | captured overlay | ANALYTICAL | `run-capture` / `world-capture`, B=4 |
| `overlay_technology.json` | captured overlay | ANALYTICAL | `run-capture` / `world-capture`, B=4 |
| `overlay_social_groups.json` | captured overlay | ANALYTICAL | `run-capture` / `world-capture`, B=4 |
| `overlay_institutions.json` | captured overlay | SUBJECTIVE (owner `agent-a`) | `run-capture` / `world-capture`, B=4 |
| `overlay_unavailable.json` | explicit unavailable overlay | ANALYTICAL | `run-capture` / `world-capture`, B=4 |
| `catalogue.json` | pinned catalogue | ANALYTICAL | `run-capture` / `world-capture`, boundary 4 |
| `markers_positive.json` | marker page 1 | SUBJECTIVE (owner `agent-a`) | `run-capture` / `world-capture`, window 3..6 |
| `markers_positive_page2.json` | marker continuation | SUBJECTIVE (owner `agent-a`) | `run-capture` / `world-capture`, window 3..6 |

Schema identifiers: `observer-civilization-map-v1`,
`observer-civilization-catalogue-v1`, `observer-civilization-overlay-v1`,
`observer-civilization-markers-v1`. Captured rows use policy
`civilization-overlays.v1`; objective map rows use `objective-map-v1`.
Publication identity in captured fixtures is `pub-1` with the digests recorded
in each file. Marker boundary `seek_boundary` values are post-event finalized
boundaries, never current/latest state.

The fixtures intentionally include complete, empty, partial-coverage, missing
interval, unavailable, continuation and owner-scoped examples. Missing
intervals are disclosed as gaps; they are never converted into collapse or
zero-prevalence claims.

## Generation and producers

Fixture JSON is a strict serializer artifact: the Python and Godot suites parse
it through the closed DTO/contract vocabulary, and the checksum manifest pins
the committed bytes. Regeneration is an explicit test operation in
`tests/unit/test_civilization_fixtures.py` (set
`PALIMPSEST_REGENERATE_CIVILIZATION_FIXTURES=1`); it is never performed at
runtime.

Real producer packs use `tests/compose/start_civilization.py` and keep identities
beginning `civ-real-`; they are produced from a durable manager/runner/database
run with the real civilization capture/publisher. Constructed packs use
`tests/compose/seed_civilization_evidence.py` and keep identities beginning
`civ-constructed-`; their artifacts are marked constructed presentation
evidence. The two namespaces must never be mixed.

## Bounds

Marker/catalogue consumers cap display at 200 rows/boundaries, eight pages per
explicit window, four cached windows and bounded response/cache bytes. Objective
map/overlay consumers cap 800 rows, eight pages, 32 boundary windows and the
Task 8 physical/decoded budgets. None of these client caps alters scientific
totals.
