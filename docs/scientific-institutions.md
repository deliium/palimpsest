# Scientific institutions

V4-32 composes the owned `science` and `organizations` contexts into a detached
research read model. It never creates a University, Academy, profession,
authority, permission, or live science-institution ledger.

## What the read model observes

- **Objective receipts.** Admitted deliberate experiments (`ExperimentResolved`
  with `discovery_mode="deliberate"`) and committed durable-carrier service:
  record creation/annotation, repository deposit/retrieval, and copies as
  provenance.
- **Owner context.** Existing organization concepts, roles, goals, procedures,
  records, offices, institutional memory, teaching audits, replication
  ledgers, and physical instrument use.
- **Analytical links.** An exact, contemporaneous participant-to-concept join
  with an accepted `ProjectContributed` witness on the concept's
  `collective_project` goal. Old observations, unrelated projects, later
  contributions, and refused attempts do not qualify.

No row claims that an archive contains a particular experimental result, that a
tool was used in a specific trial, or that observed co-occurrence is causal.

## Stability rule

Windows are absolute half-open intervals of 32 ticks. A practice row is keyed by
`(existing organization identity, operator, process_token, window)`.

- `supported`: at least one committed deliberate execution and one matched
  durable-carrier service in a complete window, with the carrier alive at
  window end.
- `stable`: the second of two adjacent complete supported windows when the same
  organization and activity key recur, at least one exact surviving typed
  carrier is shared, and the union has at least two distinct eligible actors
  with committed linked actions.
- `observed_only`: execution without matched carrier service.
- `not_observed`: a previously observed key in a complete window without a
  joined execution.
- `unavailable`: a mandatory coverage gap for a known key.

Complete-empty, partial, unavailable, ambiguous, and stable windows remain
distinct. Ambiguous cross-organization receipts are counted outside candidates
and never decide a label. Stability is never backdated.

## Lineage

Episodes use separate `sci-inst-` analytical identities. The read model records
`emerged`, `continued`, `lapsed`, `continuity_unknown`,
`reobserved_after_gap`, and confirmed cross-organization `handoff`, `split`,
`merged`, and `split_merged` edges.

A handoff needs a stable source, a supported target, an existing upstream
organization transition, and a later stable target on the same typed carrier.
Confirmation is known only at `w+2`. Missing coverage blocks an edge; gaps and
cross-run links are never bridged.

## Output

`scientific-institutions-snapshot-v1` carries `windows`, `practice`, `signals`,
and `lineage`. Window rows expose half-open ranges, mandatory and optional
coverage, and unassigned/ambiguous counts. Practice rows expose opaque
run-scoped organization, actor, occurrence, and carrier tokens. Signal rows
describe experimenters, record keepers, teachers, replication expectations,
archives, shared instruments, procedures, institutional memory, and offices as
contextual descriptions, never preset actor classes or votes.

Three metric families append the catalog (268 → 271):

- `scientific_institution_practice@1`
- `scientific_institution_roles_and_carriers@1`
- `scientific_institution_lineage@1`

## Configuration and reads

Reads are opt-in and require both settings:

```dotenv
PALIMPSEST_SCIENTIFIC_INSTITUTIONS_ROOT=/data/scientific-institutions
PALIMPSEST_SCIENTIFIC_INSTITUTIONS_CURSOR_KEY=<at least 32 UTF-8 bytes>
```

Neither set means disabled; a half-pair is a startup error. All routes require
the `SUBJECTIVE_DEBUG` capability:

- `GET /v1/simulations/{run_id}/scientific-institutions` — summary, latest by
  default;
- `GET /v1/simulations/{run_id}/scientific-institutions/windows`
- `.../practice`
- `.../signals`
- `.../lineage`

Section reads require an explicit `publication_id` on the first page. The
summary returns the publication ID and digest; clients pass them through so
paging stays pinned even when a newer publication is committed. Section cursors
are purpose-bound and reject tampering, expiry, cross-section use, and
cross-publication use.

## Running explicitly

The off-gate experiment `scientific_institutions@1` declares four 96-tick arms:

- `institutions-combined-v56` — organizations + science, durable records,
  repositories, collective projects, deterministic teaching/communication;
- `institutions-org-off` — matched v56 with `organizations=False`;
- `institutions-science-off` — matched v56 with `science=False`;
- `institutions-instruments-v57` — combined configuration plus the existing
  measurement-instrument spec.

`experiments.scientific_institutions_capture.run_with_scientific_institution_capture`
initializes boundary zero, captures full nonterminal windows, finishes the run
once, and only then exports the terminal endpoint. It installs no runtime sink
and publishes nothing automatically. The caller composes and stores a snapshot
explicitly.

Focused checks:

```bash
uv run --frozen --python 3.12.14 pytest \
  tests/unit/test_scientific_institutions_*.py \
  tests/architecture/test_scientific_institutions_boundaries.py -q
uv run --frozen --python 3.12.14 pytest -q -m integration \
  tests/integration/test_scientific_institutions_runner.py
```

## Evidence limits

The controlled lane proves that ordinary admitted actions can produce the exact
joins. It does not prove that autonomous civilization runs will produce stable
practice; an autonomous zero is valid and distinct from unavailable evidence.
A stable label is repeat practice evidence, not scientific quality, consensus,
prevalence, a causal culture, or an institutional type. There is no composite
score, ranking, truth verdict, or recommendation.
