[← Organizations](organizations.md) · [Back to README](../README.md) · [Macro-societies →](macro-societies.md)

# Formal social rules

Formal social rules extend V2/V3 norms and conventions into explicit,
socially recognized constraints. A formal rule is **one owner's belief** about
a socially recognized constraint. It is never an objective law, statute,
jurisdiction, court order, verdict, permission, prohibition, sanction engine,
or rule engine.

## What a rule can and cannot do

A rule belief can label an action as prohibited, obligated, or permitted **for
its owner**. It can bias existing plan candidates, select a declared response,
and anchor itself to an observed written record.

It cannot change physical admission. `WorldEngine` never reads a formal-rule
ledger. A socially prohibited but physically possible command is still admitted;
a physically impossible command is still rejected by the existing action rules,
with no formal-rule attribution.

## Progression

One owner rule advances monotonically:

```text
habit → expectation → norm → documented → recognized_enforcement
```

| Stage | Real owner-visible evidence |
| --- | --- |
| `habit` | Active convention or repeated own action |
| `expectation` | Norm candidate or repeated claim |
| `norm` | Active norm belief |
| `documented` | Norm/expectation plus an observed durable record whose interpreted action or scope matches |
| `recognized_enforcement` | Documented plus recurrence and enough distinct proponents, with recognized authority or explicit recognition claims |

Promotion is versioned. A version is appended only when stage, constraint,
scope, authority, recognition, written representation, sanctions, exceptions,
or status changes. Out-of-order amendments keep the prior version and append a
`formal_rule_version_out_of_order` notice.

## Recorded dimensions

| Dimension | Representation |
| --- | --- |
| Scope | Closed scope kind plus bounded sorted anchor references and a digest |
| Proponents | Owner-local `frp-` positions with stance and provenance |
| Recognized authority | Office, organization procedure, collective decision, written record, custom, or unknown |
| Written representation | Observed artifact id/revision/genre/repository and integrity status; content is never parsed into law |
| Expected sanction | Closed sanction kinds with quantized severity; a belief only |
| Exceptions | Owner-local `frx-` records; an exception never removes a prohibition |
| Historical versions | Owner-local `frv-` records with contiguous numbering and supersedes links |
| Status | `candidate`, `active`, `contested`, `superseded`, `retired` |

## Responses and competing systems

Agents may declare `follow`, `violate`, `challenge`, `reinterpret`, or `ignore`.
These are **declarations**, not objective compliance findings. Silence is never
a violation. A response selector returns a record only; it never constructs,
suppresses, or rewrites an `AgentCommand`.

Multiple competing systems may cover the same scope or action with incompatible
constraints. They retain separate identities, symmetric competing links, and
`contested` status. No precedence, majority, quorum, or consensus gate resolves
them.

## Speech

Bounded `fr_v1` claims travel inside existing `Talk`/`Tell` relations. Acts are
`fr_assert`, `fr_support`, `fr_oppose`, `fr_challenge`, `fr_reinterpret`,
`fr_amend`, `fr_withdraw`, `fr_recognize`, and `fr_report`. Existing `org_v1`,
`org_op_v1`, `org_ca_v1`, and collective-decision frames are unchanged. No new
command, event, observer semantic type, or free-text payload is added.

## Snapshot, publication, and routes

Detached analysis harvests exported ledgers, builds bounded windows, detects
overlapping candidates, assigns stable `frule-` identities, derives forward-only
lineage, and keeps objective counts, owner claims, and analytical candidates in
three separated layers.

`formal-rule-snapshot-v1` is an independent canonical artifact. Publication is
opt-in, post-completion, atomic, quota-bounded, and isolated from scientific
status. Six GET-only routes require `SUBJECTIVE_DEBUG`:

| Route | Purpose |
| --- | --- |
| `GET /v1/simulations/{run_id}/formal-rules` | Summary |
| `GET /v1/simulations/{run_id}/formal-rules/candidates` | Candidate page |
| `GET /v1/simulations/{run_id}/formal-rules/candidates/{candidate_id}` | Candidate detail |
| `GET /v1/simulations/{run_id}/formal-rules/candidates/{candidate_id}/rules` | Rule page |
| `GET /v1/simulations/{run_id}/formal-rules/candidates/{candidate_id}/versions` | Version page |
| `GET /v1/simulations/{run_id}/formal-rules/lineage` | Lineage page |

An unset `PALIMPSEST_FORMAL_RULE_ROOT` returns `503 formal_rule_disabled`.
Cursors bind run, publication, digest, purpose, filter, and offset; changed
bindings fail with `400 formal_rule_cursor_invalid`, and expiry with
`410 formal_rule_cursor_expired`.

## Metrics

The catalog grows from 148 to 151 with three appended families:

- `formal_rule_development@1`
- `formal_rule_authority@1`
- `formal_rule_response@1`

The first 148 families keep their ids, order, versions, and value keys.

## Configuration

| Setting | Purpose |
| --- | --- |
| `PALIMPSEST_FORMAL_RULE_ROOT` | Published snapshot root for read-only routes |
| `PALIMPSEST_FORMAL_RULE_CURSOR_KEY` | At least 32 UTF-8 bytes; keeps cursors restart-stable |
| `--formal-rule-root` | Research CLI publication root (opt-in) |
| `--formal-rule-max-publications` | Publication quota (default 16) |
| `--formal-rule-max-bytes` | Artifact byte quota (default 8 MiB) |

## Limits and non-goals

The cognition ledger is bounded to 8 systems, 32 rules, 16 versions per rule,
512 total records, 384 frame characters, and 32 relations per utterance.
Published snapshots are bounded to 2048 candidates, 4096 rules, 8192 versions,
4 MiB per artifact, and 500 rows per page; truncation is explicit.

No court, police, government, jurisdiction, global registry, rule engine, or
sanction engine exists. A rule never becomes a world law, admission gate,
objective permission, or automatic enforcement procedure.

## Non-claims

A rule belief is not objective law, guilt, compliance truth, enforcement, or a
world permission. Counts describe detached candidates under stated coverage.
The feature claims no prevalence, emergence probability, predictive power,
capacity, throughput, or composite civilization score.

## See also

- [Organizations](organizations.md)
- [Social communication](social-communication.md)
- [V4 architecture](v4-architecture.md)
- [Configuration](configuration.md)
- [Research API](research-api.md)
- [Research UI](research-ui.md)

Current catalog: 216 metric families; 43 commands; 73 observer semantic types; Alembic `0017`.
