<script lang="ts">
  import { ApiClientError } from '../api/client'
  import {
    getRepresentationLineage,
    getRepresentationMandate,
    getRepresentationMandates,
    getRepresentationPositions,
    getRepresentationRevocations,
    getRepresentationSummary,
    type RepresentationLineage,
    type RepresentationMandate,
    type RepresentationPosition,
    type RepresentationRevocation,
    type RepresentationSummary,
  } from '../api/representation'
  import type { ResearchSelection } from '../research/selection'

  interface Props {
    runId: string
    selection: ResearchSelection
  }

  let { runId }: Props = $props()

  type Status = 'loading' | 'available' | 'empty' | 'unavailable' | 'error'

  let status = $state<Status>('loading')
  let reason = $state<string | null>(null)
  let summary = $state<RepresentationSummary | null>(null)
  let mandates = $state<RepresentationMandate[]>([])
  let lineage = $state<RepresentationLineage[]>([])
  let selectedId = $state<string | null>(null)
  let selected = $state<RepresentationMandate | null>(null)
  let positions = $state<RepresentationPosition[]>([])
  let revocations = $state<RepresentationRevocation[]>([])

  function label(value: string | null | undefined): string {
    return value ? value.replaceAll('_', ' ') : 'unknown'
  }

  async function load(): Promise<void> {
    status = 'loading'
    reason = null
    summary = null
    mandates = []
    lineage = []
    selectedId = null
    selected = null
    positions = []
    revocations = []
    try {
      summary = await getRepresentationSummary(runId)
      const page = await getRepresentationMandates(runId)
      mandates = page.items
      const edges = await getRepresentationLineage(runId)
      lineage = edges.items
      status = mandates.length === 0 ? 'empty' : 'available'
    } catch (error) {
      if (error instanceof ApiClientError) {
        reason = error.code
        status = error.code === 'representation_disabled' ? 'unavailable' : 'error'
        return
      }
      reason = 'representation_read_failed'
      status = 'error'
    }
  }

  async function selectMandate(mandateId: string): Promise<void> {
    selectedId = mandateId
    try {
      selected = await getRepresentationMandate(runId, mandateId)
      const [positionPage, revocationPage] = await Promise.all([
        getRepresentationPositions(runId, mandateId),
        getRepresentationRevocations(runId, mandateId),
      ])
      positions = positionPage.items
      revocations = revocationPage.items
    } catch (error) {
      reason = error instanceof ApiClientError ? error.code : 'representation_read_failed'
      status = 'error'
    }
  }

  $effect(() => {
    void runId
    void load()
  })
</script>

<section class="representation">
  <header>
    <h1>Delegation and representation</h1>
    <p class="note">
      Owner beliefs only — not legitimacy. Recognition, rejection, contestation,
      and revocation are this owner's beliefs; the panel never derives authority
      or a winning representative.
    </p>
  </header>

  {#if status === 'loading'}
    <p>Loading representation…</p>
  {:else if status === 'unavailable'}
    <p class="unavailable">
      Representation publication is unavailable: {label(reason)}.
    </p>
  {:else if status === 'error'}
    <p class="error">Representation read failed: {label(reason)}.</p>
  {:else if status === 'empty'}
    <p>No representation was published for this run.</p>
  {:else if summary}
    <dl class="counts">
      <div><dt>Mandates</dt><dd>{summary.mandate_count}</dd></div>
      <div><dt>Positions</dt><dd>{summary.position_count}</dd></div>
      <div><dt>Revocations</dt><dd>{summary.revocation_count}</dd></div>
      <div><dt>Conflicts</dt><dd>{summary.conflict_count}</dd></div>
      <div><dt>Coverage</dt><dd>{label(summary.coverage)}</dd></div>
    </dl>

    <ul class="mandates">
      {#each mandates as mandate (mandate.mandate_id)}
        <li>
          <button
            type="button"
            class:selected={selectedId === mandate.mandate_id}
            onclick={() => void selectMandate(mandate.mandate_id)}
          >
            <strong>{label(mandate.principal_kind)}</strong>
            <span>{label(mandate.scope_kind)}</span>
            <span>{label(mandate.duration_kind)}</span>
            <span>{label(mandate.status)}</span>
            <span>{label(mandate.recognition_basis)}</span>
            <span>support {mandate.support_roots}</span>
            <span>opposition {mandate.opposition_roots}</span>
          </button>
        </li>
      {/each}
    </ul>

    {#if selected}
      <section class="detail">
        <h2>{label(selected.principal_kind)} · {label(selected.scope_kind)}</h2>
        <p class="belief">owner belief — not legitimacy</p>
        <p>Status: {label(selected.status)}</p>
        <p>Recognition basis: {label(selected.recognition_basis)}</p>
        <p>Revocations: {revocations.length}</p>
        <h3>Positions</h3>
        <ul>
          {#each positions as position (position.position_id)}
            <li>
              {label(position.stance)} · {label(position.provenance)} ·
              tick {position.tick}
            </li>
          {/each}
        </ul>
        <h3>Revocations</h3>
        <ul>
          {#each revocations as revocation (revocation.revocation_id)}
            <li>
              {label(revocation.kind)} · {label(revocation.provenance)} ·
              {revocation.contested ? 'contested' : 'authorized belief'}
            </li>
          {/each}
        </ul>
        <h3>Lineage</h3>
        <ul>
          {#each lineage as edge (edge.edge_id)}
            <li>{label(edge.kind)} · tick {edge.tick}</li>
          {/each}
        </ul>
      </section>
    {/if}
  {/if}
</section>

<style>
  .representation {
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
  .mandates {
    list-style: none;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  button {
    display: flex;
    flex-wrap: wrap;
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
  .belief {
    font-weight: 600;
  }
  .unavailable,
  .error {
    color: #9b2c2c;
  }
</style>
