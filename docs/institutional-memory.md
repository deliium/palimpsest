# Institutional memory

Owner-scoped information associated with a long-lived role or recurring
procedure. There is no institution-owned mind, global archive, objective office
registry, or telepathic inheritance. Information exists through ordinary
artifacts, addressed speech, and teaching; it is always learned by a particular
owner from a particular observation or delivery.

Trade ledgers, archives, project records, decision records, and succession
histories are uses of ordinary artifacts and public claims, not new institution
types.

## Modes and configuration

`institutional_memory_mode` is per-agent and defaults to `disabled`. When at
least one owner enables `deterministic`, the runner writes
`runner-config-v53` with the exact v52 cognition keyset plus
`institutional_memory_mode`. Each enabled owner must also enable its own local
`office_succession_mode` or `institution_concept_mode`; another owner's mode
does not satisfy the dependency. `runner-config-v52` remains the mediation
surface, and v53 may compose mediation without requiring it.

The explicit `species_default_institutional_memory_v1` initialization profile
is v53-only. It enables empty office, institutional-memory, artifact-reading,
and teaching modes for an admitted learner. It transfers no channel, entry,
role identity, access privilege, or skill content. Existing newborn profiles
remain institutional-memory-disabled.

Pins remain commands 43, observer semantic types 73, replay `V22`, codec `v20`
where the selected objective channel requires it, Alembic `0017`, `/v1`, and
`observer-protocol-v1`. Metric families are 126. `institutional_economy` remains
unowned.

## Channels and entries

Role channels use the owner's stable `OfficeConcept.office_id`, so an occupant
change does not reset the channel. Procedure channels are minted from locally
evidenced procedure anchors and retained only across a unique overlap. No
incoming sender office or concept identity is imported. Unknown or ambiguous
associations remain unbound.

Entries are fallible owner-local records with one to three ordered claim triples,
acquisition tick, confidence, partial/distorted/ignored flags, provenance, and a
declared fact count. Competing entries are retained; there is no last-writer
truth election. Caps prune deterministically and mark coverage partial.

## Physical and speech frames

Records use the fixed `im_v1` mark header: binding kind, function token,
`c_<16 hex context>`, declared root `r_<24 hex>`, declared parent `p_<24 hex>`
or `p_none`, `n_1|n_2|n_3`, then consecutive subject/predicate/object triples
(up to 16 marks). Speech uses one existing communication relation with subject
`im_v1` and predicate `im_transmit` or `im_teach`. Frames are syntax, not truth.
Body facts are not duplicated into artifact relations.

A declared institutional root is testimony and never a remote lookup key. The
outer utterance envelope and the institutional frame root are separate
namespaces. Retransmission preserves the native envelope and can add delivery
edges without manufacturing an independent institutional source.

## Learning and use

Acquisition requires a current visible interpreted reading at the observed
revision or an actual addressed delivery. Teaching additionally requires the
receiver's teaching mode. No reading, hidden or destroyed carrier, stale
reading, repository-without-content, unaddressed message, or unresolved speaker
acquires facts. Previously learned entries remain personal after the carrier is
lost.

Consultation selects at most one active, nonignored, bound entry. A winning
`Talk`/`Tell` can transmit or teach it; an already selected empty `Inscribe` can
record it. Ignore/unignore is an owner decision completed through the normal
loop result path, not an admin or observer side channel. A changed or suppressed
command records consultation/superseded rather than fabricating an emission.

## A path

1. A inscribes a record containing bounded claims.
2. B observes and interprets that revision, creating B's own local entry.
3. B later teaches the retained frame to C through addressed speech.
4. C creates another local entry with its own delivery provenance.

If B never sees the record, or C never receives the delivery, the later owner
learns nothing. Succession or office recognition alone grants no information.

## Limitations

Repository retrieval or mutation permission is not reading confidentiality:
colocated visible marks may be observable under existing perception. No office
claim grants access. Frame validity does not imply correctness; wrong and
conflicting claims are preserved. Damaged facts are not reconstructed from
lineage or metadata. A surviving record may still be ignored. Runtime
checkpoint continuation preserves one owner's ledger, but it is not a durable
restart guarantee for every subjective store; objective records persist and
replay through the existing codecs.
