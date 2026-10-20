# Conflict mediation

Optional, owner-scoped mediation lets an agent interpret a dispute involving
other agents, hear competing accounts, offer compromises, vouch, facilitate,
and recommend voluntary restitution. It is not adjudication, law, a court,
a verdict, a binding settlement, or a global dispute registry.

## Six speech acts

`hear_dispute`, `request_accounts`, `propose_compromise`, `vouch`, `mediate`,
and `recommend_restitution` travel as bounded namespaced relations inside the
existing `Talk`/`Ask`/`Tell` speech. They add no world command, event,
observation, observer semantic type, API route, replay/codec marker, or
migration. Delivery proves only that speech happened.

Responses use a closed vocabulary: `account`, `accept`, `refuse`, `defer`,
`counterpropose`, `withdraw`, and `claim_settlement`. Auxiliary
`invite_mediator`, `endorse_role`, and `withdraw_role_endorsement` relations
are separate from recommendation responses. Ignoring is a legal behavioral
choice; silence is unknown, not consent.

## Authority and autonomy

Each recipient appraises a mediator relative to its own evidence:

1. directed relationship dimensions (never symmetrized),
2. target-scoped reputation dimensions (reliability, harm, generosity,
   competence) with same-root deduplication,
3. recognized facilitation roles with occupant/supporter evidence,
4. matched procedural norms,
5. contextually linked institution beliefs.

Missing or disabled sources stay unavailable. No component grants binding
authority, and an available component never forces acceptance. Runtime
selection appraises the originator of an owner-directed recommendation and
emits a revision-scoped response: positive available evidence may accept,
weak or negative evidence refuses, moderate evidence counterproposes, and
unavailable evidence defers. Participants may ignore, withdraw, or act for
unrelated reasons.

Cases are created only from owner-visible evidence: a contention occurrence
or incompatible claims by two or more speakers. Co-presence alone is not a
dispute. Delivered account requests are answered with a bounded account
response; the selected act may otherwise be hearing, asking a party, vouching,
mediating, or proposing terms.

## Voluntary follow-through

A typed allowlist compiles only the acting owner's independently selected
recommendation. The initial supported action is an exact owner-controlled
`Give(item_id=..., recipient_id=...)` for a named held item. Unsupported terms
remain discussion; nothing substitutes another item, target, `Feed`, project,
or arbitrary feasible command. Recommendations never bypass custody,
colocation, admission, survival, lifecycle, or project gates.

## Configuration and compatibility

`mediation_mode` defaults to `DISABLED` for every agent, including newborn
profiles. `runner-config-v52` is emitted only when at least one agent enables
mediation; it is the full v51 keyset plus `mediation_mode`. Historical schemas
reject the key and any non-disabled mode. Disabled runs keep their prior
writer, bytes, fingerprints, RNG use, and command stream.

Runtime carry, in-memory checkpoints/forks, and detached result export are
supported. Durable SQL restart is not. A disabled owner rejects non-`None`
mediation checkpoint state, and a rejected restore leaves runtime state and
runner cursors unchanged.

## Detached measurement

Two analysis-only families are available:

- `conflict_mediation@1`: distinct claimed cases, recommendations, responses,
  attempted versus matched follow-through, ambiguous matches, unresolved /
  partial / disputed / apparently settled outcomes, and ignored or unknown
  uptake.
- `mediation_role_emergence@1`: transient assistance, repeated activity,
  candidate recognition, stable recognition (requiring recurrence, independent
  support, and temporal span), contested recognition, and lost support.

Rows are harvested from completed result exports after execution. One
objective effect cannot fulfill multiple recommendations, and a matched
transfer does not prove agreement or conflict resolution. Pruned histories and
open windows are published as partial coverage or right-censored observations,
not as proof of stable roles.

Experiment BI (`mediation_opportunities@1`) exposes baseline, prior-schema
off-control, mediation-on, and opportunity-limited arms. It seeds no dispute,
account, mediator role, acceptance, or settlement.
