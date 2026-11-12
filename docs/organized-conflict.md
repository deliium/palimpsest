# Organized conflict

V4-12 owns the already-declared `organized_conflict` V4 context on the accepted
`runner-config-v56` seam. It enables coordinated violent behavior through
low-level mechanics. It does **not** add `world.at_war`, a war state, a conflict
registry, an army actor, a command hierarchy, a new command, a new event, a
write pair, a `/v2` route, or a SQL migration.

Activation requires `runner-config-v56`,
`v4_capability_flags.organized_conflict`, and the declared prerequisite
`v4_capability_flags.diplomacy`. A conflict-only v56 configuration fails closed
with `v4_prerequisite_missing` at `stage="v4_capability_flags"`.

## What it controls

- One owner's retained conflict beliefs: plans, participations, observations,
  interpretations, outcomes, contradictions, terminations, and local episodes.
- A deterministic `Wait` replacement that may turn one active plan into one
  existing command.
- Detached research detection of sustained conflict from committed event
  patterns.

## What it never controls

A plan, role, side, participation claim, interpretation, contradiction, or
alignment is never a permission, obligation, prohibition, truth, guilt finding,
liability, enforcement, legitimacy, score, or winner. `WorldEngine`, perception,
admission, stop selectors, memory, prompts, observer semantics, and the Godot
client never read a conflict ledger. A physically possible command is still
admitted; a physically impossible command is still rejected by existing rules.

## Eight operation primitives

The operations are closed descriptive categories. They compile only to existing
command names:

| Operation | Existing commands |
| --- | --- |
| `coordinated_attack` | `attack` |
| `defense` | `attack`, `help`, `move` |
| `movement_group` | `move`, `transport` |
| `resource_capture` | `take`, `give` |
| `structure_attack` | `oppose_public_good`, `attack` |
| `route_blocking` | `move`, `attack`, `flee`, `help` |
| `retreat` | `flee` |
| `assistance` | `help`, `feed`, `transport` |

Honest bounds:

- Defense is assistance or counterattack; there is no damage mitigation, guard,
  shield, armor, or interception state.
- Resource capture is `Take` from ground/corpse custody or voluntary `Give`;
  there is no seizure from a living holder and no ownership transfer.
- Structure attack is `OpposePublicGood` on a completed public-good project, or
  attacks on occupants; there is no generic structure damage.
- Route blocking is coordinated presence and attack/flee at endpoints; routes
  have no mutable blocked or closed state.
- Movement groups are independent `Move`/`Transport` commands; there is no
  group-move command.
- Retreat is independent `Flee`; assistance is `Help`/`Feed`/`Transport`.

## Deterministic `Wait` replacement

Only an exact `Wait` selection may be replaced. A non-`Wait` selection is
returned unchanged. The screen
`organized_conflict_actions.organized_conflict_wait_replacement` returns one
existing command value and never submits, resolves, blocks, or executes it.
Every physical effect remains ordinary `WorldEngine` admission.

## `ocf_v1` speech

`ocf_v1` is exactly 12 fields and at most 256 characters. It travels as at most
one relation inside existing `Talk`/`Ask`/`Tell`; the utterance text is the fixed
subject `ocf_v1`, never free text. Malformed, oversize, or speaker-mismatched
frames are dropped. Peer-supplied targets, sides, roles, plan references, and
declared provenance are untrusted; the receiver verifies the speaker and assigns
provenance locally.

## Detection

Detached analysis reads committed events only and keeps three layers separate:
objective counts, owner-token rows, and analytical candidates. Detection is
independent of owner interpretations and uses the locked
`organized-conflict-analysis.v1` policy:

- `individual_violence`: one attacker, one target, no shared co-participation,
  no recurrence.
- `coordinated_conflict`: at least two actors on one side and at least two
  hostile events in a six-tick window.
- `persistent_inter_group_conflict`: at least two sides with at least two actors
  each, reciprocal hostile windows, and the sustained span/event/active-tick
  thresholds.

Interpretation alignment (`consistent`, `unresolved`, `inconsistent`,
`not_applicable`) is researcher-only and never reaches cognition.

## Owner ledger

Each owner keeps immutable plans, participations, observations, interpretations,
outcomes, contradictions, terminations, and local episodes under
`organized-conflict.v1`. Rows use content-addressed `oce-`, `ocp-`, `ocm-`,
`oco-`, `oci-`, `ocx-`, `occ-`, and `oct-` ids and a canonical ledger digest.
The update order is collect observations and frames, derive plans and
participations, interpret, derive outcomes, retain contradictions, expire, and
enforce limits. Caps prune observations first, then old unreferenced
interpretations and episodes, then terminal plans; active plans, participations,
contradictions, and terminations remain, and an overflow with nothing droppable
fails closed. Caps are cognition policy, not runner configuration.

## Snapshot, store, API, and UI

`organized-conflict-snapshot-v1` is canonical, bounded at 4 MiB and row caps,
and immutable after publication. `organized-conflict-store-v1` writes atomically
under a lock, preserves quotas, and rejects a duplicate publication id with
different bytes. Publication is opt-in, post-completion, and non-interfering: a
storage or composition failure changes only the receipt. Six GET-only routes
under `/v1/simulations/{run_id}/organized-conflict` require `SUBJECTIVE_DEBUG`,
return `organized_conflict_disabled` when unconfigured, and return 404 for
unknown published records. Cursors bind run, publication, digest, purpose, and
filters; a changed binding is 400 and expiry is 410. The Research UI conflict
panel is read-only and renders episodes, plans, interpretations, and outcomes
without authority, legitimacy, enforcement, score, winner, or war status.

## Non-goals

No `world.at_war`, war/peace field, conflict registry, army actor, battle,
front, command hierarchy, damage mitigation, living-holder seizure, generic
structure damage, route closure, group-move command, new event, new command,
write pair, observer semantic type, `/v2` route, or SQL migration exists.
Physical structure damage and physical route closure require a separate plan
that extends world semantics.

Current catalog: 216 metric families; 43 commands; 73 observer semantic types; Alembic `0017`.
