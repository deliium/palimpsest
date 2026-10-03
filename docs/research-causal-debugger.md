# Research causal debugger

[← Cognition and agent runtime](cognition-runtime.md) · [Godot observer](godot-observer.md) · [Back to README](../README.md)

Read-only research surface that answers **why a selected graphical event happened** from stored cognition-trace stages and subjective provenance. It does not mutate runs, invent free-text rationales, or expose prompts / chain-of-thought.

## Addressing

| Field | Role |
| --- | --- |
| `run_id` | Simulation run |
| `tick` | Logical tick |
| `event_id` | Opaque committed event id (**preferred** stable key) |
| `sequence` | Intra-tick sequence; UI phrase “event N” means this field |
| `agent_id` | Acting / owning agent (usually `actor_id`) |

Resolution is deterministic: load the committed event → require an actor → map semantic/detail type to `command_kind` → pick the matching cognition-trace invocation (lexicographic `invocation_id` tie-break with `ambiguity=true` when needed). Missing traces return `availability=unavailable` with a stable reason code — never synthesized stages.

## Command map (semantic → `command_kind`)

Closed mapping used by the resolver (agent-authored actions). Secondary effects such as `AGENT_DIED` without an attacking `actor_id` are `not_applicable`; a lethal attack is explained via the `AGENT_ATTACKED` occurrence’s actor.

| Semantic / detail | `command_kind` |
| --- | --- |
| `AGENT_MOVED` / `move` | `move` |
| `AGENT_SEARCHED` / `search` | `search` |
| `AGENT_TOOK_ITEM` / `take` | `take` |
| `AGENT_DROPPED_ITEM` / `drop` | `drop` |
| `AGENT_GAVE_ITEM` / `give` | `give` |
| `AGENT_ATE_ITEM` / `eat` | `eat` |
| `AGENT_DRANK` / `drink` | `drink` |
| `AGENT_SLEPT` / `sleep` | `sleep` |
| `AGENT_TALKED` / `talk` | `talk` |
| `AGENT_ASKED` / `ask` | `ask` |
| `AGENT_TOLD` / `tell` | `tell` |
| `AGENT_HELPED` / `help` | `help` |
| `AGENT_ATTACKED` / `attack` | `attack` |
| `AGENT_FLED` / `flee` | `flee` |
| `AGENT_WAITED` / `wait` | `wait` |
| `RESOURCE_HARVESTED` / `harvest` | `harvest` |
| `CRAFT_STARTED` / `ITEM_CRAFTED` / `craft` | `craft` |
| `STRUCTURE_BUILT` / `build` | `build` |
| `STRUCTURE_REPAIRED` / `repair` | `repair` |
| `ITEM_STORED` / `store` | `store` |
| `ARTIFACT_CREATED` / `inscribe` | `inscribe` |
| `ARTIFACT_MODIFIED` / `amend` | `amend` |
| `ARTIFACT_MOVED` / `transfer_artifact` | `transfer_artifact` |
| `ARTIFACT_DESTROYED` / `erase` | `erase` |

Unknown semantics log `unmapped_semantic_type` and do not invent a kind.

## HTTP (`subjective_debug`)

All routes are GET-only under `/v1/simulations/{run_id}/debugger/…`:

| Route | Purpose |
| --- | --- |
| `…/debugger/events/{event_id}/causal-trace` | Chain by opaque event id |
| `…/debugger/causal-trace?tick=&sequence=` | Chain by cursor |
| `…/debugger/agents/{agent_id}/invocations?tick=` | Invocation listing |
| `…/debugger/lineage/{kind}/{id}` | Closed lineage kinds |

| Status | Meaning |
| --- | --- |
| `403` | Capability missing |
| `404` | Addressed event not found |
| `200` + `availability=unavailable` | Event exists; traces / optional lineage missing |

Wire field `observer_focus` carries `{run_id, tick, sequence, event_id}` handles for Godot seek/focus. Credentials stay in headers / WS subprotocol — never query strings.

## Researcher chain

```text
Observation → relevant_memories → reconstruction → beliefs → emotional_state
→ goals → theory_of_mind → imagined_futures → counterfactuals
→ selected_intention → action
```

Optional supporting nodes (`situation_model`, `budget_summary`) may appear as secondary; they do not replace this order.

Counterfactuals / prediction provenance use locked read sources only:

1. Structured refs / counts on the selected cognition-trace invocation
2. Else closed fields from an optional experiment/result harvest
3. Else `unavailable` with an explicit reason code

No new Alembic tables or `cognition-trace-v2` for full audit blobs in this surface.

## Lineage kinds

Closed `kind` enum for `GET …/debugger/lineage/{kind}/{id}` (owner-scoped; `owner_id` query required):

| `kind` | Source | Subject id |
| --- | --- | --- |
| `belief_evidence` | Semantic belief evidence rows | belief id |
| `memory_derivation` | Memory derivation sources | derived memory id |
| `communication` | Transmission meta on memory traces | communication id |
| `narrative` | Owner `NarrativeLedger` via runtime checkpoint (same path as narrative-hops) | variant id |
| `goal_ancestry` | Checkpoint `goals` / `parent_goal_id` chain | goal id |
| `prediction` | Task 1c trace refs → harvest → unavailable | opaque subject key |

Entries carry stable ids, optional `observer_focus`, parent/related ids, counts, and status codes — never proposition, narrative, or goal description text. Missing checkpoint → `checkpoint_unavailable`; missing ledger → `narrative_ledger_missing`.

## Non-goals

- Private CoT, prompts, utterance / memory / belief text bodies
- Mutating, reseeding, or inverse-replaying history
- Causal assembly in Godot
- New `V2CapabilityFlags` slot or `multi_hop_testimony_tracking`
- Folding traces into `EvidenceManifest`

Godot presentation labels (Observed…Acted, expanded chain names, artifact-kind chrome) are **client-side only**. They map server `stage_code` values for researchers and must not be read as chain-of-thought, free-text rationales, or ground truth. See [Godot observer — Causal debugger](godot-observer.md#causal-debugger).

## See also

- [Cognition and agent runtime](cognition-runtime.md)
- [Godot observer](godot-observer.md)
- [Research API](research-api.md)
- [Read-only observer](observer.md)
