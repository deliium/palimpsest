<script lang="ts">
  import { ApiClientError } from '../api/client'
  import {
    getDiplomacyInstruments,
    getDiplomacyLineage,
    getDiplomacyRelation,
    getDiplomacyRelations,
    getDiplomacySummary,
    type DiplomacyEnvoy,
    type DiplomacyInstrument,
    type DiplomacyLineage,
    type DiplomacyMisrepresentation,
    type DiplomacyRelation,
    type DiplomacyRelationDetail,
    type DiplomacySummary,
    type DiplomacyTermination,
  } from '../api/diplomacy'
  import type { ResearchSelection } from '../research/selection'

  interface Props {
    runId: string
    selection: ResearchSelection
  }

  let { runId }: Props = $props()

  type Status = 'loading' | 'available' | 'empty' | 'unavailable' | 'error'

  let status = $state<Status>('loading')
  let reason = $state<string | null>(null)
  let summary = $state<DiplomacySummary | null>(null)
  let relations = $state<DiplomacyRelation[]>([])
  let instruments = $state<DiplomacyInstrument[]>([])
  let lineage = $state<DiplomacyLineage[]>([])
  let selected = $state<DiplomacyRelationDetail | null>(null)
  let selectedId = $state<string | null>(null)

  function label(value: string | null | undefined): string {
    return value ? value.replaceAll('_', ' ') : 'unknown'
  }

  async function load(): Promise<void> {
    status = 'loading'
    reason = null
    selected = null
    selectedId = null
    try {
      summary = await getDiplomacySummary(runId)
      const [relationPage, instrumentPage, lineagePage] = await Promise.all([
        getDiplomacyRelations(runId),
        getDiplomacyInstruments(runId),
        getDiplomacyLineage(runId),
      ])
      relations = relationPage.items
      instruments = instrumentPage.items
      lineage = lineagePage.items
      status = relations.length === 0 ? 'empty' : 'available'
    } catch (error) {
      if (error instanceof ApiClientError) {
        reason = error.code
        status = error.code === 'diplomacy_disabled' ? 'unavailable' : 'error'
        return
      }
      reason = 'diplomacy_read_failed'
      status = 'error'
    }
  }

  async function selectRelation(relationId: string): Promise<void> {
    selectedId = relationId
    try {
      selected = await getDiplomacyRelation(runId, relationId)
    } catch (error) {
      reason = error instanceof ApiClientError ? error.code : 'diplomacy_read_failed'
      selected = null
    }
  }

  $effect(() => {
    void runId
    void load()
  })
</script>

<section class="diplomacy-panel">
  <header>
    <h2>Diplomacy</h2>
    <button type="button" onclick={load}>Refresh</button>
  </header>

  {#if status === 'loading'}
    <p>Loading diplomacy beliefs…</p>
  {:else if status === 'unavailable'}
    <p>Diplomacy publication is disabled for this deployment ({label(reason)}).</p>
  {:else if status === 'error'}
    <p>Diplomacy publication could not be read ({label(reason)}).</p>
  {:else if status === 'empty'}
    <p>No retained diplomacy relations were published for this run.</p>
  {:else if summary}
    <dl>
      <dt>Relations</dt><dd>{summary.relation_count}</dd>
      <dt>Parties</dt><dd>{summary.party_count}</dd>
      <dt>Contacts</dt><dd>{summary.contact_count}</dd>
      <dt>Instruments</dt><dd>{summary.instrument_count}</dd>
      <dt>Terminations</dt><dd>{summary.termination_count}</dd>
      <dt>Coverage</dt><dd>{label(summary.coverage)}</dd>
    </dl>

    <table>
      <thead><tr><th>Relation</th><th>Parties</th><th>Opened</th><th>Last</th></tr></thead>
      <tbody>
        {#each relations as relation (relation.relation_id)}
          <tr class:selected={selectedId === relation.relation_id}>
            <td><button type="button" onclick={() => selectRelation(relation.relation_id)}>{relation.relation_id}</button></td>
            <td>{relation.party_tokens.join(', ')}</td>
            <td>{relation.opened_tick}</td>
            <td>{relation.last_tick}</td>
          </tr>
        {/each}
      </tbody>
    </table>

    {#if selected}
      <h3>Relation detail</h3>
      <p>Truncated: {selected.truncated ? 'yes' : 'no'}</p>
      <h4>Parties</h4>
      <ul>
        {#each selected.parties as party (party.party_id)}
          <li>{party.party_token ?? 'unknown'} · {label(party.party_kind)} · {label(party.resolution)}</li>
        {/each}
      </ul>
      <h4>Envoys</h4>
      <ul>
        {#each selected.envoys as envoy (envoy.envoy_id)}
          <li>{envoy.envoy_token} · standing: {label(envoy.status)}</li>
        {/each}
      </ul>
      <h4>Instruments</h4>
      <ul>
        {#each selected.instruments as instrument (instrument.instrument_id)}
          <li>{instrument.instrument_id} · {label(instrument.instrument_kind)} · {label(instrument.term_kind)}</li>
        {/each}
      </ul>
      <h4>Retained misrepresentation observations</h4>
      <ul>
        {#each selected.misrepresentations as row (row.misrepresentation_id)}
          <li>{label(row.kind)} · observed at tick {row.observed_tick}</li>
        {/each}
      </ul>
      <h4>Retained terminations</h4>
      <ul>
        {#each selected.terminations as row (row.termination_id)}
          <li>{label(row.kind)} · {label(row.target_kind)} · tick {row.tick}</li>
        {/each}
      </ul>
    {/if}

    <h3>Instruments</h3>
    <table>
      <thead><tr><th>Instrument</th><th>Kind</th><th>Terms</th><th>Opened</th></tr></thead>
      <tbody>
        {#each instruments as instrument (instrument.instrument_id)}
          <tr>
            <td>{instrument.instrument_id}</td>
            <td>{label(instrument.instrument_kind)}</td>
            <td>{label(instrument.term_kind)}</td>
            <td>{instrument.opened_tick}</td>
          </tr>
        {/each}
      </tbody>
    </table>

    <h3>Lineage</h3>
    <ul>
      {#each lineage as edge (edge.edge_id)}
        <li>{edge.from_candidate_id} → {edge.to_candidate_id} · {label(edge.kind)} · tick {edge.tick}</li>
      {/each}
    </ul>
  {/if}
</section>

<style>
  .diplomacy-panel { display: flex; flex-direction: column; gap: 0.75rem; }
  table { width: 100%; border-collapse: collapse; }
  th, td { text-align: left; padding: 0.25rem 0.5rem; }
  tr.selected { background: rgba(0, 0, 0, 0.06); }
</style>
