# Accounting ledgers

Accounting ledgers are owner-scoped interpretations of external durable records.
They are beliefs about what a record appears to say, never a book of record,
never an objective balance, and never an audit oracle. A later section of one
owner's ledger does not change the world, the artifact, another owner's beliefs,
or the committed record.

## What an accounting ledger is

One owner keeps a bounded `AccountingLedger` of entries. Each entry carries a
descriptive entry kind, owner-relative direction, item-kind quantity, opaque
record and counterparty tokens, an appraisal, observed record integrity,
confidence, retained revisions, evidence references, counts, and bounded
notices. The ledger stores no item id, inventory count, structure quantity,
peer ledger, money, currency, or objective balance.

Records remain objective external marks. The accounting ledger interprets what
the owner can see; it never rewrites a record, repairs damage, or asserts what a
record means. Record content is never parsed from prose or marks: only explicit
`acc_v1` relation triples are read.

## Activation

Accounting cognition activates only when all of the following are true:

- the owned `organizations` V4 capability flag is enabled; and
- the V3-11 `durable_records` spec is present.

The durable-records channel keeps its own existing prerequisites:
`cultural_historical_memory`, a deterministic `CulturalFeatureProvenanceSpec`,
and an accepted runner schema that supports durable records. Accounting does not
relax or re-validate those gates. If either accounting input is absent, no
ledger, no `acc_v1` frame, and no snapshot field is produced, and existing
V3-11, V4-03, V4-04, V4-08, and V4-22 behavior is unchanged.

Optional owner-scoped inputs are the V3-17 `structured_commitments` spec, the
V3-18 `subjective_valuation` spec, the V4-08 `evidence_testimony` ledger, and
V3-20/V3-21 contribution evidence. They add descriptive rows only; none is a
truth source.

## Record kinds

The five kinds are descriptive categories, not permissions, balances, or
ownership:

| Kind | Example |
| --- | --- |
| `exchange` | A record of three food units received from a counterparty. |
| `debt` | A record that two material units are owed to another owner. |
| `inventory` | A record holding one tool at a location. |
| `organizational_resource` | A record naming a resource an organization is believed to control. |
| `contribution` | A record of one owner's labor contribution to a project. |

## Record assessments

Assessments are owner appraisals:

| Assessment | Meaning |
| --- | --- |
| `unassessed` | The owner has not formed an appraisal. |
| `consistent` | Observed integrity is intact and no contradiction is known. |
| `contradicted` | A committed transfer or contribution disagrees with the record claim. |
| `outdated` | A newer revision of the same record was observed. |
| `suspected_fraudulent` | The owner suspects misrepresentation; this is not a finding. |
| `damaged` | The record was observed damaged or partially lost. |

`consistent` is not truth. `suspected_fraudulent` is not proven fraud. No field asserts truth, authenticity, guilt, liability, or an objective
balance. Two records that disagree produce a belief, never a correction command.

## External artifacts

Accounting-like artifacts are existing durable-capable artifacts carrying at
least one `acc_v1` relation triple. The grammar is compact and validated against
the existing artifact token rule:

- subject: `<entry_code>_<item_kind>`, for example `xch_food`;
- predicate: `acc_v1`;
- object: `<direction_code><quantity>`, for example `in3`.

Entry codes are `xch`, `dbt`, `inv`, `org`, and `ctb`. Direction codes are `in`,
`out`, `hold`, `recv`, `pay`, and `ctb`. Quantities are integers 1 through 64.
No new artifact genre, artifact kind, command, or event is added. Accounting
content may extend an already-selected `Inscribe` command through the existing
relation list; the verb, kind, class, and recipient stay identical. Accounting
never selects a command and never replaces a non-`Inscribe` command.

## Speech

`acc_v1` frames travel only inside existing `Talk` or `Tell` utterances. One
relation may be attached to an already-selected utterance; the command class and
recipient are unchanged. The six acts are `declare_entry`, `cite_record`,
`affirm_entry`, `dispute_entry`, `correct_entry`, and `retract_entry`. A receiver
folds a frame as a communicated claim with a reduced confidence; it never copies
the sender's ledger. Malformed or oversize frames are dropped and the simulation
continues.

## Evidence use

`accounting_evidence_candidates` is a pure, opt-in bridge into the existing
V4-08 evidence ledger. It returns at most four owner-scoped candidate references
using the existing evidence DTOs. The cognition stage may fold them; nothing
writes automatically, and the evidence schema is unchanged. A record-backed
candidate's integrity is an evidence belief, not a truth value. An institution
is not a ledger actor: only owner agents keep entries, and organization tokens
are opaque references.

## Analysis

Detached `analysis.accounting_ledgers_*` reads committed events only: artifact
record lifecycle, completed exchanges and transfers, collective contributions,
and `Talked`/`Told` `acc_v1` claims. It joins token-only detached owner exports
and never reads `WorldState`, a runtime, a store object, an API object, or a peer
ledger.

The analysis keeps objective rows, owner claims, and analytical entries in
strictly separated layers. Analytical entries are reconstructed from committed
`acc_v1` claims; record lifecycle metadata contributes coverage and condition
evidence. A record without a committed claim is counted in record coverage but
cannot yield an entry kind or direction because committed artifact events do not
carry relation content. The analysis reports counts, integer claim sums, and
milli shares. Condition rows carry `available` or `insufficient_samples`; fewer
than four entries in a window is `insufficient_samples`, and no quantile is
invented. Four metric families are appended to the catalog:

- `accounting_record_coverage@1`
- `accounting_entry_alignment@1`
- `accounting_record_condition@1`
- `accounting_flow_structure@1`

Owner-versus-evidence alignment is researcher-only and is one of `consistent`,
`unresolved`, `inconsistent`, or `not_applicable`. It never reaches cognition,
prompts, memory, world state, observer semantics, or stop selectors. Fewer than
four samples is `insufficient_samples`; no quantile is invented.

## Artifact and read surface

Completed runs may publish the sibling `accounting-ledgers-snapshot-v1`
document through `accounting-ledgers-store-v1`. The snapshot has a canonical
digest and publication id and no wall-clock field. Publication is programmatic
and post-completion; there is no CLI producer and the scientific run status is
unchanged.

Seven GET-only routes are available under `/v1`:

- `/v1/simulations/{run_id}/accounting-ledgers`
- `/v1/simulations/{run_id}/accounting-ledgers/entries`
- `/v1/simulations/{run_id}/accounting-ledgers/records`
- `/v1/simulations/{run_id}/accounting-ledgers/conditions`
- `/v1/simulations/{run_id}/accounting-ledgers/flows`
- `/v1/simulations/{run_id}/accounting-ledgers/counterparties`
- `/v1/simulations/{run_id}/accounting-ledgers/alignment`

All seven require `SUBJECTIVE_DEBUG`. They fail closed with
`accounting_ledgers_disabled` unless both `PALIMPSEST_ACCOUNTING_LEDGERS_ROOT` and
`PALIMPSEST_ACCOUNTING_LEDGERS_CURSOR_KEY` are set; the cursor key must be at
least 32 UTF-8 bytes. Default limit is 100; maximum is 500; `window_index` is
0 through 511. Cursors are purpose-bound and window-bound. A corrupt payload
returns `accounting_ledgers_store_corrupt`; an unknown run returns
`accounting_ledgers_run_not_found`; malformed or cross-window cursors return
`accounting_ledgers_cursor_invalid`; expired cursors return
`accounting_ledgers_cursor_expired`.

The Research UI adds one read-only accounting panel. Godot adds no overlay.

## Non-goals

There is no double-entry engine, no objective book of record, no tax system, no audit oracle,
global ledger registry, money, currency, interest, bank, credit score, or
enforceable book of record. No command, event, observer semantic type, write
pair, `/v2` route, migration, runner schema, or V4 flag slot is added. No Godot
overlay exists. No money, currency, interest, bank, or credit score exists.

## Pins

The catalog is 220 metric families. Commands stay 43; observer semantic types
stay 73; the maximum replay/write pair is replay-v27 with codec `v25`; Alembic
head stays `0017`; the stable API is `/v1`; the observer protocol stays
`observer-protocol-v1`. V4 remains 14 contexts, 12 flags, eight owned, and four
unowned. The off-gate experiment is `accounting_ledgers@1`.

## See also

- [Organizations](organizations.md)
- [Evidence and testimony](evidence-testimony.md)
- [Credit relationships](credit-relationships.md)
- [Analysis metrics](analysis-metrics.md)
- [Research API](research-api.md)
