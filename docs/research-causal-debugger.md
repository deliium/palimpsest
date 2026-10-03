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
Observation → memories → reconstruction → beliefs → emotion → goals
→ Theory of Mind → imagined futures → counterfactuals (when available)
→ intention → action
```

Counterfactuals / prediction provenance use locked read sources only: cognition-trace refs → optional experiment/result harvest summaries → `unavailable`. No new Alembic tables or `cognition-trace-v2` for full audit blobs in this surface.

## Non-goals

- Private CoT, prompts, utterance / memory / belief text bodies
- Mutating, reseeding, or inverse-replaying history
- Causal assembly in Godot
- New `V2CapabilityFlags` slot or `multi_hop_testimony_tracking`
- Folding traces into `EvidenceManifest`

## See also

- [Cognition and agent runtime](cognition-runtime.md)
- [Godot observer](godot-observer.md)
- [Research API](research-api.md)
- [Read-only observer](observer.md)
