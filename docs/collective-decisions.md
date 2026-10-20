# Collective decisions

Owner-scoped collective decisions are an opt-in, subjective primitive for
proposing a shared course of action, expressing support or opposition,
delegating a bounded preference, withdrawing support, and coordinating
individual attempts. They are **not** a political-system simulator and add no
world permission.

## Six acts, six topics

| Act | Meaning |
| --- | --- |
| `propose` | Offer bounded terms/action for a shared course. |
| `support` | Express a revisable position on an identified revision. |
| `oppose` | Express disagreement with those terms. |
| `delegate` | Express a one-hop, proposal-scoped preference to follow another. |
| `withdraw_support` | Retract one's own prior support or delegation by reference. |
| `coordinate` | Suggest a bounded action/target/window and report a claimed course. |

Topics are `collective_project`, `resource_allocation`, `migration`,
`shared_defense`, `storage`, and `norm_enforcement`. They describe subject
matter, never government types, jurisdictions, membership, or moral
correctness.

## Configuration

The per-agent `collective_decision_mode` (`disabled` by default,
`deterministic` opt-in) is emitted only on `runner-config-v51`. At least one
owner must enable it; v51 is rejected when every owner stays disabled. V51
extends the exact v50 cognition keyset with `collective_decision_mode` and
composes offices, institutions, narratives, regions, and lifecycle modes.
Decisions work without offices or institutions. Default writes remain
`runner-config-v4`; replay `EVENT_SCHEMA_REPLAY_V22`, codec `v20`, commands
43, observer semantic types 73, and Alembic `0017` are unchanged.

## Speech

The six acts travel as bounded `CommunicationRelation` atoms inside ordinary
`Talk`/`Ask`/`Tell` speech (`collective-decisions-communication.v1`). A policy
marker relation names the locked policy. The verified observed speaker is the
actor; payload actors and declared roots are never authentication. A relayed
proposal or endorsement is testimony, not direct support. Delivery proves
speech only, and the receiver creates fresh local evidence rather than copying
a sender ledger.

## Evidence and limits

Updates read only the owner's observation, owner-safe identity projection,
prepared `RetrievedMemoryContext` episode facts, and the previous ledger. They
never read `WorldState`, `WorldEvent`, another owner's ledger, or analysis rows.
Proposal references are finite and fresh-bounded; expired or retired references
cannot be reactivated, and pruned history reports partial coverage. Conflicts,
failed attempts, silence, noncompliance, abandonment, and no decision are all
legal outcomes.

A support or coordination act performs no world action by itself. Topic
adapters allow only existing commands, one ordinary admitted command per actor
per tick. `oppose` never emits `OpposePublicGood` and never coerces another
actor.

Influence attribution is a local algorithmic comparison over the same prepared
candidate set with only the decision preference disabled. Runtime planning
records a bounded audit whenever the preference filters the candidate
directions; after the final command and any late replacement are known, the
loop appends `preference_changed` or `final_command_changed`. Unchanged
candidate sets produce no attribution, and an overwritten command is never
credited as executed. Unsupported comparisons report `unavailable`. This is not
proof of real-world causation.

## Runtime and analysis

The ledger carries through prepared proposals, deferred finalization, runtime
checkpoints, forks, runner results, and detached exports. Disabled owners export
nothing; enabled owners export even an empty ledger. Checkpoint tests cover
runtime checkpoint objects, not durable process restart.

Detached analysis adds `collective_decision_process@1`,
`collective_decision_outcomes@1`, and `collective_decision_disagreement@1`
(families 119 → 122). Cross-owner alignment is analytical inference over topic,
action, and window evidence; owner-local references are not shared keys.
Ambiguous or unmatched cases are excluded from denominators and counted.

Detached analysis may also join committed effect facts to a supported course
window. A join proves that an observable effect happened; it never proves
acceptance, legitimacy, or a legitimate winner.

Experiment BH (`collective_decisions@1`) is off the V1 gate:

```python
from experiments.collective_decisions_scenario import collective_decisions_scenario
from experiments.coordinator import ExperimentCoordinator

definition = collective_decisions_scenario(seed=23, max_ticks=16)
results = await ExperimentCoordinator(definition).run_all()
```
