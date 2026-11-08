# Delegation and representation

V4-09 deepens the owned `organizations` V4 context with one owner's beliefs
about who may act or speak for a principal. The gate is exactly
`runner-config-v56` plus `v4_capability_flags.organizations = true`; there is no
new capability flag, `runner-config-v57`, per-agent runner key, command, event,
observer semantic type, write pair, `/v2` route, or SQL migration.

## What representation is

Representation is one owner's belief (owner belief) about **standing to act or
speak for a principal**. A mandate records the delegator, representative, scope, duration,
provenance, support, opposition, revocation, and derived recognition. Every row
belongs to one owner. No global representative registry, objective mandate,
permission service, or legitimacy oracle exists.

## What it is not

Representation is **not** authority, permission, legitimacy (not legitimacy),
authenticity, a
verdict, a court order, a binding mandate, or a truth finding. `WorldEngine`,
perception, admission, stop selectors, memory, prompts, and observer semantics
never read a representation ledger. A socially rejected or contested
representative does not block a physically possible command, and a physically
impossible command is still rejected by existing world rules. No representation
helper returns, constructs, submits, or resolves an `AgentCommand`.

## Principal kinds

The principal kinds are closed:

| Kind | Required anchor |
| --- | --- |
| `agent` | An owner-observed stable agent id; the representative must differ from the principal. |
| `organization` | The owner's own existing `orgc-` collective concept. |
| `coalition` | The owner's own existing `orgc-` collective concept; no coalition entity exists. |
| `settlement` | An owner-visible region id from the current observation. |
| `unknown` | No anchor and never resolved. |

A missing concept or unobserved region leaves the claim `claimed` with an
explicit notice. No collective, settlement, polity, or citizenship object is
invented.

## Scope and duration

Scope is a closed belief: `speak_for`, `negotiate`, `carry_message`,
`coordinate_project`, `transact`, `decide`, and `unknown`. No scope value makes
a command admissible.

Duration is closed: `single_act` (same tick), `occasion` (bounded window),
`until_tick` (deterministic boundary expiry), `until_revoked`, and `unknown`.
Expiry is a retained state, never a deletion. `until_revoked` never expires by
tick.

## Support, opposition, and recognition

Recognition is derived from the owner's retained beliefs, never asserted by a
claim. The precedence is:

1. revocation, expiry, or supersession;
2. unresolved principal stays `claimed` (or `unknown` for `unknown`);
3. a verified agent principal's declaration gives
   `recognized` / `principal_declaration`;
4. an office basis with at least one independent root gives
   `recognized` / `office_authority`;
5. a collective-decision basis with at least one independent root gives
   `recognized` / `collective_decision`;
6. a written-rule basis with at least one independent root gives
   `recognized` / `written_authorization`;
7. at least two independent support roots with lower opposition gives
   `recognized` / `independent_support`;
8. opposition without support, or greater opposition, gives `rejected`;
9. mixed support and opposition gives `contested`;
10. otherwise the mandate stays `claimed` with basis `none`.

Independence uses `root_ref` when present and the actor otherwise. Two retellings
sharing one root count once. The owner's own support is excluded. A self-claim
alone is never `recognized`. Rejection and contestation are legal and retained.

## Revocation, resignation, and conflicts

`principal_revoked` requires the verified agent principal;
`representative_resigned` requires the verified representative;
`collective_decision_revoked` requires an owner decision reference; and
`office_lost` requires an office reference absent from the owner's office
ledger. An unauthorized attempt is retained as a contested revocation and a
`revocation_dispute` conflict; the mandate stays active.

Duplicate mandates, contradictory scopes, conflicting principals, and
revocation disputes stay `unresolved`. Two recognized mandates may coexist.
A newly recognized mandate supersedes an older claimed/contested/rejected
mandate for the same principal and scope; history is retained.

## Speech frames

Bounded `rep_v1` frames travel inside existing `Talk`/`Ask`/`Tell` relations.
The closed acts are `rep_claim`, `rep_delegate`, `rep_accept`, `rep_reject`,
`rep_support`, `rep_oppose`, `rep_abstain`, `rep_revoke`, `rep_resign`, and
`rep_report`. The serialized object carries mandate reference, principal kind and
reference, representative reference, scope kind and subject, duration and end
tick, provenance, and revision. It is capped at 256 characters.

The verified speaker rules are strict: a claim or resignation must come from the
named representative; an agent delegation must come from the principal and name
a different representative; acceptance or rejection must come from the agent
principal; revocation must come from the principal or representative. A
collective "accept" is recorded as support, not as principal acceptance. Forged,
malformed, over-cap, or mismatched frames are dropped with a safe notice.

## Collective decisions and later diplomacy

V3-31 collective-decision delegation remains proposal-scoped. Representation is
standing to act or speak and consults the owner's decision, office, and
formal-rule ledgers read-only. `representation_standing_summary` is a read-only
projection for a later diplomacy plan; V4-09 adds no diplomacy flag, treaty,
negotiation protocol, or polity object.

## Analysis and metrics

Detached analysis harvests exported ledgers only. It keeps three separated
layers: aggregate objective counts, owner-token subjective counts, and
analytical `rep-` candidates with forward-only lineage. Candidate statuses are
`claimed`, `recognized`, `contested`, `fragmented`, `dissolved`, and `unknown`.
Researcher-only scope alignment classifies `consistent`, `unresolved`,
`inconsistent`, and `not_applicable`; `not_applicable` is never counted as
`consistent`, and the classification is never a legitimacy finding and never
reaches cognition.

The catalog appends three families, raising the count from 157 to **160**:

- `representation_mandate_structure@1`
- `representation_recognition_support@1`
- `representation_scope_alignment@1`

The first 157 families keep their ids, order, versions, and value keys. Pins
remain runner v4/v55/v56, result v2/v3, 43 commands, 73 observer semantic types,
180 metric families, replay-v22/codec v20, `/v1`, `observer-protocol-v1`, and
Alembic `0017`.

## Publication and inspection

The canonical artifact is `delegation-representation-snapshot-v1`, stored
atomically as `delegation-representation-store-v1`. Its rows carry hashed
`owner_token`, `principal_token`, `representative_token`, and `actor_token`
values; raw agent ids and free-text scope subjects are never published.
Publication is opt-in and post-completion. A storage or composition failure
changes only the receipt, never the scientific result.

Six GET-only routes require `SUBJECTIVE_DEBUG`:

- `GET /v1/simulations/{run_id}/representation`
- `GET /v1/simulations/{run_id}/representation/mandates`
- `GET /v1/simulations/{run_id}/representation/mandates/{mandate_id}`
- `GET /v1/simulations/{run_id}/representation/mandates/{mandate_id}/positions`
- `GET /v1/simulations/{run_id}/representation/mandates/{mandate_id}/revocations`
- `GET /v1/simulations/{run_id}/representation/lineage`

Cursors are purpose-bound HMAC tokens with a 900-second TTL. Reuse against a
different run, publication, digest, purpose, or filter returns
`representation_cursor_invalid` (400); expiry returns
`representation_cursor_expired` (410). An unconfigured server returns
`representation_disabled` (503).

## Configuration

Representation activates only through `organizations`. Publication and
inspection use:

- `PALIMPSEST_REPRESENTATION_ROOT`
- `PALIMPSEST_REPRESENTATION_CURSOR_KEY` (at least 32 UTF-8 bytes)
- `--representation-root`
- `--representation-max-publications` (default 16)
- `--representation-max-bytes` (default 8,388,608)

Publication receipts use `disabled`, `unavailable`, `ready`, `published`, or
`failed` with a safe reason.

## Limits

The owner ledger caps 32 mandates, 32 positions per mandate, 8 revocations and
8 conflicts per mandate, 8 evidence/decision/office/rule references, 16 region
anchors, and 320 total records. Truncation is deterministic and explicitly
marks `representation_truncated` or `representation_capacity_reached`. The
snapshot caps 8,192 mandates, 16,384 positions, 4,096 conflicts, 8,192 lineage
edges, and 4 MiB.

## Non-claims

V4-09 makes no prevalence, emergence-probability, predictive, accuracy,
reliability, moral-correctness, legitimacy, or diplomatic-capacity claim. It
does not implement diplomacy, organized conflict, markets, supply chains,
science, infrastructure, epidemics, ecological feedback, disasters, resilience,
or macro-society behavior.

## See also

- [Organizations](organizations.md)
- [Dispute resolution](disputes.md)
- [Evidence and testimony](evidence-testimony.md)
- [Analysis metrics](analysis-metrics.md)
- [Research API](research-api.md)
- [Research UI](research-ui.md)

See also: [Diplomacy](diplomacy.md) derives envoy standing from this owner-scoped representation ledger and never treats accreditation as authority.

V4-13 added four border families (catalog 172 -> 176). V4-14 raises the catalog
to **180** families. See [borders and claims](borders-and-claims.md) and
[migration and displacement](migration-displacement.md).
