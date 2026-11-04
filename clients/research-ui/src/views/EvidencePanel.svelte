<script lang="ts">
  import { ApiClientError } from '../api/client'
  import {
    getEvidenceCandidate,
    getEvidenceCandidates,
    getEvidenceContradictions,
    getEvidenceLineage,
    getEvidenceSources,
    getEvidenceSummary,
    type EvidenceCandidate,
    type EvidenceCandidateDetail,
    type EvidenceContradiction,
    type EvidenceLineageEdge,
    type EvidenceSource,
    type EvidenceSummary,
  } from '../api/evidence'
  import type { ResearchSelection } from '../research/selection'

  interface Props {
    runId: string
    selection: ResearchSelection
  }

  let { runId }: Props = $props()

  type Status = 'loading' | 'available' | 'empty' | 'unavailable' | 'error'

  let status = $state<Status>('loading')
  let reason = $state<string | null>(null)
  let summary = $state<EvidenceSummary | null>(null)
  let candidates = $state<EvidenceCandidate[]>([])
  let lineage = $state<EvidenceLineageEdge[]>([])
  let selectedId = $state<string | null>(null)
  let detail = $state<EvidenceCandidateDetail | null>(null)
  let sources = $state<EvidenceSource[]>([])
  let contradictions = $state<EvidenceContradiction[]>([])

  function label(value: string | null | undefined): string {
    return value ? value.replaceAll('_', ' ') : 'unknown'
  }

  async function load(): Promise<void> {
    status = 'loading'
    reason = null
    summary = null
    candidates = []
    lineage = []
    selectedId = null
    detail = null
    sources = []
    contradictions = []
    try {
      summary = await getEvidenceSummary(runId)
      const page = await getEvidenceCandidates(runId)
      candidates = page.items
      const edges = await getEvidenceLineage(runId)
      lineage = edges.items
      status = candidates.length === 0 ? 'empty' : 'available'
    } catch (error) {
      if (error instanceof ApiClientError) {
        reason = error.code
        status = error.code === 'evidence_testimony_disabled' ? 'unavailable' : 'error'
        return
      }
      reason = 'evidence_read_failed'
      status = 'error'
    }
  }

  async function selectCandidate(candidateId: string): Promise<void> {
    selectedId = candidateId
    try {
      detail = await getEvidenceCandidate(runId, candidateId)
      const [sourcePage, contradictionPage] = await Promise.all([
        getEvidenceSources(runId, candidateId),
        getEvidenceContradictions(runId, candidateId),
      ])
      sources = sourcePage.items
      contradictions = contradictionPage.items
    } catch (error) {
      reason = error instanceof ApiClientError ? error.code : 'evidence_read_failed'
      status = 'error'
    }
  }

  $effect(() => {
    void runId
    void load()
  })
</script>

<section class="evidence">
  <header>
    <h1>Evidence and testimony</h1>
    <p class="note">
      Owner beliefs only. Evidence is never truth: witnesses may misremember,
      records may be wrong, and artifacts may be misinterpreted. Objective
      alignment is researcher-only and never a verdict or a winning account.
    </p>
  </header>

  {#if status === 'loading'}
    <p>Loading evidence…</p>
  {:else if status === 'unavailable'}
    <p class="unavailable">
      Evidence publication is unavailable: {label(reason)}.
    </p>
  {:else if status === 'error'}
    <p class="error">Evidence read failed: {label(reason)}.</p>
  {:else if status === 'empty'}
    <p>No evidence was published for this run.</p>
  {:else if summary}
    <dl class="counts">
      <div><dt>Candidates</dt><dd>{summary.candidate_count}</dd></div>
      <div><dt>Sources</dt><dd>{summary.source_count}</dd></div>
      <div><dt>Testimony</dt><dd>{summary.testimony_count}</dd></div>
      <div><dt>Items</dt><dd>{summary.item_count}</dd></div>
      <div><dt>Contradictions</dt><dd>{summary.contradiction_count}</dd></div>
      <div><dt>Coverage</dt><dd>{label(summary.coverage)}</dd></div>
    </dl>

    <ul class="candidates">
      {#each candidates as candidate (candidate.candidate_id)}
        <li>
          <button
            type="button"
            class:selected={selectedId === candidate.candidate_id}
            onclick={() => void selectCandidate(candidate.candidate_id)}
          >
            <strong>{candidate.subject_token}</strong>
            <span>{label(candidate.status)}</span>
            <span>{candidate.owner_count} owner(s)</span>
            <span>{candidate.contradiction_count} contradiction(s)</span>
          </button>
        </li>
      {/each}
    </ul>

    {#if detail}
      <section class="detail">
        <h2>{detail.candidate.subject_token}</h2>
        <p>Alignment: {label(detail.alignment_label)}</p>
        <p>
          Custody: complete {detail.custody_complete_count}, incomplete
          {detail.custody_incomplete_count}, conflicting
          {detail.custody_conflicting_count}
        </p>
        <h3>Sources</h3>
        <ul>
          {#each sources as source (source.local_id)}
            <li>
              {label(source.source_kind)} · {label(source.provenance)} ·
              custody {label(source.custody_status)}
            </li>
          {/each}
        </ul>
        <h3>Contradictions</h3>
        <ul>
          {#each contradictions as contradiction (contradiction.local_id)}
            <li>{label(contradiction.kind)} · {label(contradiction.status)}</li>
          {/each}
        </ul>
        <h3>Lineage</h3>
        <ul>
          {#each lineage as edge (edge.edge_id)}
            <li>{label(edge.kind)} · window {edge.window_index}</li>
          {/each}
        </ul>
      </section>
    {/if}
  {/if}
</section>

<style>
  .evidence {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }
  .note {
    color: #555;
  }
  .counts {
    display: flex;
    flex-wrap: wrap;
    gap: 1rem;
  }
  .candidates {
    list-style: none;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  button {
    display: flex;
    gap: 0.75rem;
    width: 100%;
    text-align: left;
  }
  button.selected {
    outline: 2px solid #2b6cb0;
  }
  .detail {
    border-top: 1px solid #ddd;
    padding-top: 1rem;
  }
  .unavailable,
  .error {
    color: #9b2c2c;
  }
</style>
