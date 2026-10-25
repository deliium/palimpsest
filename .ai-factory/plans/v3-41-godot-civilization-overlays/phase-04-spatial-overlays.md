# Phase 4: Physical context and evidence-scoped spatial overlays

Plan: [index.md](index.md)  
Tasks: 10–12  
Depends on: Tasks 1–9

## Objective

Render societal change as location-anchored, state-derived presentation, keeping objective infrastructure distinct from subjective claims and analytical classifications.

## Current-Code Evidence

| Path | Symbols | Consequence |
|---|---|---|
| `clients/godot-observer/scripts/view/world_view.gd` | `show_world`, `replace_sought_frame`, `play_event` | Central location centers/agent positions and authoritative frame replacement. |
| `clients/godot-observer/scripts/view/location_layer.gd` | region-envelope drawing | Region rectangles do not create adjacency. |
| `clients/godot-observer/scripts/view/object_layer.gd` | `structures_plan`, `paint_plan`, `ground_point` | Existing physical facility anchors; reuse positions, not simulation coordinates. |
| `clients/godot-observer/scripts/view/metric_overlay.gd` | `_extract_markers` | Generic origin fallback is unsafe for unlocated institutions/cultural summaries. |
| `clients/godot-observer/scripts/protocol/reducer.gd` | journey reductions | Participant bodies remain at origin until arrival. |
| `clients/godot-observer/tests/test_regional_travel.gd` | journey and seek assertions | Existing regional migration presentation invariant. |

## Files to Change

Create client `scripts/view/civilization_facilities.gd`, `scripts/view/civilization_flows.gd`, `scripts/view/civilization_beliefs.gd`, `scripts/presentation/civilization_plan.gd` and `tests/test_civilization_rendering.gd`.

Modify `clients/godot-observer/scripts/view/world_view.gd`, `scripts/main.gd`, `scenes/world_view.tscn`, `scripts/ui/civilization_panel.gd`, and `tests/run_protocol.gd`. Small extensions to `object_layer.gd` may expose existing `ground_point` lookup, not new physics. Keep new layers siblings, not edits to domain world models/reducers for inferred entities.

## Shared Rendering Contract

`CivilizationRenderPlan.build_semantic(world, layer_state, display_cursor)` first returns canonical sorted logical rows with identities, counts, status, source/coverage/evidence, anchor IDs and click targets, independent of LOD. `CivilizationRenderPlan.draw_plan(semantic_plan, lod)` then selects/aggregates glyphs, labels, line patterns and disposable effects within display caps; Node2D layers draw it. Draw plans may legitimately differ at1× and16×. Neither stage fetches, merges owners, classifies settlements, calculates cultural proportions or infers causal edges. Reject mismatched cursors before building. Equality tests compare semantic state at a shared cursor; compare actual drawings only after both runs rebuild at the same paused LOD. Never include transient positions/tween clocks in scientific equality.

Resolve anchors against current accepted objective locations/structures/repositories and retained event-time points. Never attach an old event to a participant's present location. A missing physical anchor remains unplaced with an explanation. Positions exist only in client presentation memory; there are no new world x/y fields or simulation effects.

## Task 10: Render regions, settlement growth and physical civic facilities

### Intent

Make multiple inhabited locations and civic infrastructure legible without inventing objective societies or headquarters.

### Implementation Steps

1. Add `CivilizationFacilities` sibling to existing location/object layers. Draw configured route links separately from ordinary world-neighbor edges and region envelopes, with a legend. No layout overlap is interpreted as adjacency. Use existing stable location centers.
2. Population view reuses demographic totals and Task 2 location counts: count badges/size bands show living population at each location, with separate dead/present-unregistered explanations. At a prefix use objective scene counts, not a future full-boundary demographic total. Do not turn missing lifecycle metadata into age/generation values.
3. Settlement-candidate glyphs use Task 5 IDs/statuses and ANALYTICAL styling; show population and intact-infrastructure counts beside candidate criterion/window. Two qualifying locations produce two separate glyphs; same location identity remains stable across seeks/reactivation. Outside complete supported windows use uncertainty/gap styling, not a confirmed vanished settlement.
4. Draw collective project kind/status/progress bars at actual project locations, public-good acts/benefits with separate icons, and linked structure outlines. Clamp visual progress but retain raw numerator/denominator in inspector; zero denominator is N/A. Counts of contributions are not memberships, leadership, entitlement or morality.
5. Draw repositories as physical containers and records by physical placement/custody; label the category `Records / repositories (archive evidence)`. Cultural archive classification is not objective. Respect damaged/destroyed/neglected states. Never display record marks or interpreted meaning as map truth.
6. Click chooses a safe read-only inspector row/source ref; no inferred glyph gains a command surface. Rebuild from complete current render inputs after seek; remove deleted/destroyed glyphs and reused pooled effects.

### Requirement Evidence

Original Request — regions, multiple settlements, projects, public goods, archives; architecture — objective containers versus institution labels; Task 5 — explicit candidate criterion. Supported combinations include legacy/no regions, multi-location, zero population, destroyed structure and partial capture.

### Error Handling and Logging

Unknown location or incomplete anchor → nonspatial row and safe reason; never origin placement. DEBUG render-plan counts only, WARN bounded unresolved-anchor code once per source revision. No per-frame log flood or private payload.

### Tests

Pure plan tests assert exact locations, stable keys, two settlements, growth/status changes at historical boundaries, removal on backward seek, project/public-act distinction, repository destruction/damage, no mark leakage, no objective settlement class and no extra neighbor links.

### Acceptance Criteria and Verification

Pinned headless protocol suite passes with new render tests and `test_regional_travel.gd`. Render plans match the Task 2 wire fixtures; turning overlays off restores base map without retained glyphs.

## Task 11: Render migration, exchange, culture and technology diffusion

### Intent

Represent flows and changing inventories without fabricating travel, markets or knowledge transmission.

### Implementation Steps

1. Add `CivilizationFlows`: active journeys show preparing/capacity-wait at origin plus a dashed intention link to destination. Completed journey history shows an outcome link/count within its explicit window; at arrival snap bodies through the existing objective frame/reducer. No mid-edge authoritative position or route invented for an ended journey.
2. Trade overlay shows completed exchange counts/item counts with ANALYTICAL summary badge and OBJECTIVE event drill-down. Co-located exchanges use local loops/counters; genuine endpoint locations require event-time evidence. Display gifts/transfers separately and do not imply transport between settlements merely because the two agents now reside apart. No shared scalar value across heterogeneous item kinds.
3. Culture overlay paints translucent/hatch analytical badges at supported location/region anchors for one selected exact trait/representation and partition. Render server-provided proportion with carrier/denominator/unknown counts, policy and boundary. No permanent terrain recoloring, ethnic borders or aggregate marker at map origin. Global/nonspatial rows remain in the panel.
4. Technology diffusion draws only retained attributable source→acquisition edges, qualified by owner/content identity and acquisition evidence time. Use different patterns for teaching/artifact/other supported modality; unknown-source or independent rediscovery is a node/list badge, not an invented arrow. Snapshots before acquisition have no future edge. Knowledge carriage is not objective production capability.
5. Cap visible flow segments to 400 and glyphs to 800 per plan, selected targets first then stable ID. Summarize suppressed counts and set display-truncated status; never change authoritative totals or silently hide selected rows. Filters reset fetch scope and render plan; no cross-trait normalization disguised as one culture scale.

### Required Interfaces and Contracts

All flow effects are disposable decorations over a state-derived plan; remove them on seek/source changes. A displayed aggregate's exact window remains visible even at high speed. No client-side grouping/calculation substitutes for missing server coverage or diffusion provenance.

### Requirement Evidence

Original Request — migration/trade/technology spread/cultural frequency; `ExchangeCompleted` — actual two-bundle holder changes; cultural metrics docs — carriage/attribution limits. Test completed exchange versus gift and communication attempt versus knowledge acquisition.

### Error Handling and Logging

Missing/destroyed event-time endpoint gives nonspatial evidence, not present-location fallback. Partial counts remain partial. DEBUG displayed/suppressed counts/window; no IDs derived from private content or payload traces. Cancel tweens without emitting scientific events.

### Tests

Preparing/wait/arrival/ended journeys; co-located exchange and unrelated gift; per-kind counts; trait zero/missing/partial denominator; global row; identical labels/different traits; knowledge source unknown/ambiguous/rediscovery; before/after acquisition; 401 flow rows and cap disclosure; stale render input rejected.

### Acceptance Criteria and Verification

Pinned headless suite passes. Captured row→plan→visible draw tests prove endpoints/counts/evidence class; technology arrows are absent for speech-only fixtures. No observer protocol/world event semantic count changes.

## Task 12: Render scoped groups and physically grounded institution evidence

### Intent

Show social/institutional interpretations without turning them into world entities, permissions or mandatory places.

### Implementation Steps

1. `CivilizationBeliefs` selected-owner group mode highlights only that owner's native member IDs, resolved through accepted registrations. Two owners' contradictory memberships never merge. Other owners' private belief rows are not accepted by the plan builder.
2. In inferred-community mode draw candidate membership halos using backend IDs/basis. Disclose missing interaction/trust/residence lanes; do not call a cluster a state/nation or assign territory from a convex hull. Stable colors derive from bounded identifiers, not Python hash or label meaning; changed membership identity may change color and does not prove historical continuity.
3. Institution selected-owner mode lists concepts/offices/status/strength evidence as SUBJECTIVE; inferred mode lists existing episode/lifecycle classifications as ANALYTICAL. Vacant/contested/lost occupant claims do not create authoritative current occupants or access controls.
4. Plot institution evidence pins only from typed grounding witnesses. Use source structure/project/repository ground points and a dashed association label `institution evidence at this site`; multiple supported sites may appear without asserting exclusive headquarters. If the physical source is absent at display time, retain its historical evidence location only with explicit evidence-time badge; do not resurrect the building. No witness means unplaced card, not owner position, nearest archive or `(0,0)`.
5. Appearance/disappearance follows captured concept/episode state and complete coverage. Use a separate missing-evidence gap style for absent snapshots. A vanished holder, destroyed archive or changed label alone is not institutional collapse. Timeline and map use the same backend row identity.
6. Hover/click exposes evidence class, owner/provenance, policy, coverage, physical association basis and safe source refs; link to existing lineage explorer requests when a qualified lineage ref exists. Do not manufacture lineage refs by label or ID guessing.

### Requirement Evidence

Original Request — social groups/institutions/physically meaningful locations/history; architecture — private office concepts and analytical institutions; Task 4 — exact grounding witnesses. Supported combinations: subjective owner disagreement, inferred group, unplaced institution, witnessed multiple sites, missing boundary and confirmed transition.

### Error Handling and Logging

Owner mismatch clears the layer and emits a safe scope error; unresolved binding remains visible in list but not map. DEBUG owner-presence boolean/counts, not belief text or content. No analytical row enters `WorldModel` as an objective entity.

### Tests

Two owner-scoped groups with same local IDs; owner switch clears highlights; analytic community separate class; no objective institution class; one/two/no grounding sites; destroyed source versus institution continuity; contested office; missing capture versus confirmed disappearance; safe lineage target routing.

### Acceptance Criteria and Verification

Pinned headless protocol suite passes with institution/group rendering assertions and evidence-class tests. Inspector and map agree on scope/time; nonspatial summaries never generate map-origin markers.

## Phase Risks and Completion

Visual styling can silently promote inference into reality: test rendered badges/line styles and keep inferred rows out of base world state. Spatial information is scarce; unplaced is a valid state, but the positive grounding path must be exercised with real observation-derived witnesses. Update Tasks 10–12 in `index.md` only after verification.
