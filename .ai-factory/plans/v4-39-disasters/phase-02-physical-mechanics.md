# Phase 2: Physical Mechanics

Plan: [index.md](index.md)  
Tasks: 2–3  
Depends on: Phase 1 / Task 1 (for each task independently)

## Objective

Implement six deterministic outcomes conditional on explicitly configured inputs and current physical facts. All edits are to a private tick candidate, never to published state.

## Current-Code Evidence

| Path | Symbols | Why it matters |
|---|---|---|
| `src/world/_physical.py`, `src/world/_ecological_resources.py` | `apply_autonomous_physical_step`, `EcologicalStockRow`, `effective_capacity_tenths`, `advance_stock_damage` | Need to avoid treating shock loss as agent withdrawal. |
| `src/world/_state.py` | `WorldState`, `rebuild_world_state`, `validate_finalized_boundary` | Validated immutable candidate state and local bounds. |
| `src/world/_infrastructure.py` | `_status_for`, `event_detail_for_asset`, `sync_infrastructure_with_structures` | Existing integrity, status, topology and tombstone semantics. |
| `src/world/_travel_network.py`, `src/world/travel_network.py` | route admission and route-condition calculation | Existing recalculation consumes infrastructure; already-admitted moves do not change retroactively. |
| `src/world/_disease.py`, `src/simulation/engine.py` | `advance_disease_pass`, `_apply_disease_pass` | Existing private fictional condition eligibility and progression. |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `src/world/_disasters.py` | Create in Task 2 | Private stock reducer and stock-effect projection; Task 4 composes it with the independent Task 3 helpers. |
| `src/world/_infrastructure.py` | Modify | Private single-asset destruction reducer using catalog and event conventions. |
| `src/world/_disease.py` | Modify | Private optional extra-opportunity callback within the ordinary fictional condition loop and attributed counts. |
| `src/simulation/disasters_randomness.py` | Modify | Named draw adapter for the fictional surge only. |
| `tests/unit/test_disaster_stock_effects.py`, `tests/unit/test_disaster_channel_effects.py` | Create | Deterministic effects, qualification guards, noninterference and limits. |

## Task 2: Implement stock shock effects

### Intent

Give each stock shock a closed, observable mechanic without changing weather, bodies, topology, or the preexisting ecology model.

### Implementation Steps

1. Add `apply_stock_disaster(state, candidate) -> (state, effect_or_skip)` in private world code. Read the resource and its ecological row and evaluate against current working weather at that resource's location. Call it after ordinary physical/renewal and before routes, so any renewal is complete and no loss can enter the just-finished pressure budget. Next tick starts from the shocked quantity.
2. Apply the table in exact tenths. Rebuild the resource and optional capacity damage row atomically. Preserve baseline maximum, minimum capacity floor, IDs, location, resource kind and rate. Do not alter `ActiveHazard`, `ShortageWindow`, or resource/route membership.

   | Kind | In-tick eligibility | Immediate effect |
   |---|---|---|
   | `flood_like` | Managed `FOOD`; local weather `RAIN` or `STORM` | One inundation pulse subtracts `min(quantity, loss_tenths)` from the selected stock. |
   | `fire` | Managed `FOOD` or `MATERIAL`; local weather `CLEAR` | One burn pulse subtracts `min(quantity, loss_tenths)` from that configured combustible stock proxy. |
   | `drought` | Managed `WATER`; local weather `CLEAR` | One dry-interval net water loss subtracts `min(quantity, loss_tenths)` after ordinary renewal; no persistent weather or renewal modifier. |
   | `resource_collapse` | Any managed stock; no weather gate | Set quantity to zero; increase row damage by `min(capacity_damage_tenths, effective_capacity - floor)`. Both net effects land together; the resource stays registered and can recover through ordinary ecology. |

3. Produce one closed stock effect with configured target, quantity before/after, damage before/after, and an outcome code. If no field changes, emit no mutated state and report `no_effect`; if weather does not qualify (including missing local weather), report `weather_ineligible`. Static-invalid target is a configuration error; a vanished bound target/row is an engine invariant failure, not a skip.
4. Add a replay-oriented apply function that checks recorded before values against the working state, verifies local target, monotone loss/damage, kind shape and capacity bounds, and applies exactly the after values without policy or RNG. For a positive-to-zero crossing, emit the existing `ResourceNodeDepleted` witness immediately after the effect, using `node_quantity_witness`; this is not a second mutation. Do not use `ResourcePressureRecorded`, `ResourceRegenerated`, or a withdrawal command to represent the pulse.

### Required Interfaces and Contracts

- Units are exact integer tenths using existing round/validation helpers. Whole-state validators run once at the ordinary boundary; do not install an alternative physical model.
- All non-targeted stocks, effective capacities and statuses are unchanged by the pulse. The collapse with zero quantity is still applied if capacity damage increased; a floored capacity and already-empty stock is a no-op.
- Fixed physical order within the stock/infrastructure tranche: scheduled then spontaneous, `rule_id` ascending. Different rules hitting the same stock use the preceding candidate's after-state. Replay checks the same chain.

### Requirement Evidence

- Original Request: no arbitrary narrative events; explicit target, weather gate, loss and capacity clamps. Existing ecology and overexploitation separate healthy renewal, current balance and command-driven pressure.

### Error Handling and Logging

- Stable `weather_ineligible`/`no_effect`; malformed effects or unexpected missing state fail the candidate validation and do not partially commit. DEBUG uses tick, kind, origin and outcome code; no IDs, raw stock maps or narrative.

### Tests

- `test_disaster_stock_effects.py`: wet/dry boundaries, exact losses, clamp at empty, capacity at floor, capacity-only applied, distinct nodes and same-node order; Hypothesis checks nonnegative monotone net losses, floor bounds and preservation of unrelated state. A drought fixture verifies loss after renewal, not a second debit or a pressure receipt.

### Acceptance Criteria

- All four outcomes are effectful on eligible fixtures, skip in ineligible ones, and preserve ordinary ecological conservation and recovery semantics.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_disaster_stock_effects.py tests/unit/test_ecological_resources_engine.py tests/unit/test_overexploitation_physics.py -q`

## Task 3: Implement infrastructure and fictional disease effects

### Intent

Use existing objective durability and fictional condition semantics rather than inventing hazard actors, arbitrary health writes or parallel lifecycle policies.

### Implementation Steps

1. Add `destroy_infrastructure_for_disaster` in `world._infrastructure`: find non-destroyed assets matching the closed kind and topology (node exact location; edge canonical endpoint match using existing topology semantics), requiring exactly one live match. No match yields `no_live_asset`; multiple matches yield `asset_ambiguous` and no mutation. Set that asset's integrity to zero, derive `DESTROYED` through `_status_for`, keep the tombstone and all other fields. The linked structure/project is not destroyed, and the same asset is not charged through both identities. Existing synchronization must not resurrect this tombstone. Emit existing `InfrastructureDestroyed` effect via `event_detail_for_asset`; the disaster receipt is attribution only, not a duplicate mutation.
2. Keep this effect in the post-physical/pre-route tranche. Route change therefore follows existing formulas that tick, and already admitted journeys, resource renewal and exposure are not recomputed retroactively. Any infrastructure-driven physical bonus is absent from the subsequent ordinary calculation.
3. Give `advance_disease_pass` one optional `extra_opportunity(location_id, entity_id)` callback defaulting to no extra opportunity, and extend its private result with transient per-location recipient identities for *additional* latent entries. Invoke it only when the existing pass finds a start-active local source and a susceptible candidate already satisfying ordinary alive, settled, unchanged-location eligibility, and only after normal exposure fails. A false callback leaves the old path unchanged; a true callback only supplies exposure opportunity, then the unchanged ordinary transmission gate still applies. Record only a resulting latent transition that needed the callback. Do not override symptoms, immunity, clocks or terminal rules. The ordinary disease state-change events remain the only per-body mutation evidence.
4. In Task 4, `_apply_disease_pass` supplies the mapped due surge candidates and the pure draw provider: keyed `StreamScope("disasters.v1", (str(tick), rule_id, entity_id.value, "fictional-opportunity"))`, `randrange(1000) < extra_opportunity_milli`. With no candidate at that location, immediately return false; disease continues normally. No candidate, draw or receipt changes the existing disease RNG stream. After existing dead-body reconciliation, intersect transient recipients with finalized absent-to-latent transitions and keep only the count. Positive count means applied; zero means `no_effect`. A skipped scheduled surge still records its objective attempt, but nothing about private per-body outcomes. Append surge receipts after the private disease net events.

### Required Interfaces and Contracts

- Existing disease conditions are fictional, private, single-channel. No new condition, strain, infection command, bodily injury, diagnostic attribute, or real-world disease parameters. No candidate writes directly to disease rows.
- A surge cannot introduce a source, target an individual through config, operate during travel, remove immunity, or cause a same-tick transmission chain. Process in the existing pass once per tick; schedule uniqueness prevents two surge rules for the same location.
- Infrastructure emits the existing exact after-row detail plus a private receipt identifying the same resolved asset and trigger; the observer may see only ordinary physical infrastructure consequences it could already see. A wave of disease receipts exposes no IDs or counts through API, observer, cognition, prompts or memory.

### Requirement Evidence

- Original Request: named infrastructure and epidemic effects must follow configured mechanics. Existing `WORLD` authority, infrastructure catalog and owner-only symptom boundary constrain the output.

### Error Handling and Logging

- Expected configuration/runtime ineligibility uses enumerated codes. Impossible guards such as a physically invalid asset or injected callback without active disease are invariant errors; abort the candidate. Log aggregate shock counts, stable codes and tick only; never log presenter/owner identities or attributable condition rows.

### Tests

- `test_disaster_channel_effects.py`: node and edge match, no-live and ambiguous skips, intact linked structure and no resurrection; independent route/asset; eligible fictional source and candidate, absent source, arrival/moved/journey/dead/immune exclusions, unchanged ordinary cases, no duplicate draw or double count and no same-tick chain. Include zero normal opportunity + configured maximum extra opportunity and allowed ordinary transmission for one synthetic fixture; zero ordinary transmission must still prevent additional state changes.

### Acceptance Criteria

- Infrastructure reaches an ordinary tombstone with existing route semantics; a qualifying fictional surge adds only new ordinary latent transitions, without relaxing eligible participants or publishing new private data.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_disaster_channel_effects.py tests/unit/test_infrastructure_lifecycle.py tests/unit/test_travel_network_tick.py tests/unit/test_disease_perception.py -q`

## Phase Risks and Mitigations

- Introducing pulse loss before the normal pressure tranche would double-charge ecological damage. Apply shocks afterward and test the receipts and post-shock next tick together.
- Replacing or advancing the existing disease pass would fork legacy behavior. Default the callback off and keep all transitions and draw streams in the original pass.

## Phase Completion Checklist

- Both tasks meet acceptance, off-path reducer behavior is unchanged, and the task ledger is updated after verification.
