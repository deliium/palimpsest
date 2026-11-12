<script lang="ts">
  import { ApiClientError } from '../api/client'
  import {
    getAlignment,
    getConditions,
    getCounterparties,
    getEntries,
    getFlows,
    getRecords,
    getSummary,
    type AccountingAlignment,
    type AccountingCondition,
    type AccountingCounterparty,
    type AccountingEntry,
    type AccountingFlow,
    type AccountingLedgersSummary,
    type AccountingRecord,
  } from '../api/accountingLedgers'
  import type { ResearchSelection } from '../research/selection'

  interface Props {
    runId: string
    selection: ResearchSelection
  }

  let { runId }: Props = $props()

  type Status = 'loading' | 'ready' | 'empty' | 'unavailable' | 'error'
  let status = $state<Status>('loading')
  let reason = $state<string | null>(null)
  let summary = $state<AccountingLedgersSummary | null>(null)
  let entries = $state<AccountingEntry[]>([])
  let records = $state<AccountingRecord[]>([])
  let conditions = $state<AccountingCondition[]>([])
  let flows = $state<AccountingFlow[]>([])
  let counterparties = $state<AccountingCounterparty[]>([])
  let alignments = $state<AccountingAlignment[]>([])
  let windowInput = $state('')

  function label(value: string | null | undefined): string {
    return value ? value.replaceAll('_', ' ') : 'unknown'
  }

  function windowIndex(): number | undefined {
    const raw = String(windowInput ?? '')
    if (raw.trim() === '') return undefined
    const parsed = Number(raw)
    return Number.isInteger(parsed) && parsed >= 0 && parsed <= 511
      ? parsed
      : undefined
  }

  async function load(): Promise<void> {
    status = 'loading'
    reason = null
    const index = windowIndex()
    try {
      summary = await getSummary(runId)
      const [entryPage, recordPage, conditionPage, flowPage, partyPage, alignPage] =
        await Promise.all([
          getEntries(runId, { windowIndex: index }),
          getRecords(runId, { windowIndex: index }),
          getConditions(runId, { windowIndex: index }),
          getFlows(runId, { windowIndex: index }),
          getCounterparties(runId, { windowIndex: index }),
          getAlignment(runId, { windowIndex: index }),
        ])
      entries = entryPage.rows
      records = recordPage.rows
      conditions = conditionPage.rows
      flows = flowPage.rows
      counterparties = partyPage.rows
      alignments = alignPage.rows
      const hasRows =
        entries.length +
          records.length +
          conditions.length +
          flows.length +
          counterparties.length +
          alignments.length >
        0
      status = hasRows ? 'ready' : 'empty'
    } catch (error) {
      if (error instanceof ApiClientError) {
        reason = error.code
        status =
          error.code === 'accounting_ledgers_disabled' || error.code === 'http_503'
            ? 'unavailable'
            : 'error'
      } else {
        reason = error instanceof Error ? error.message : 'error'
        status = 'error'
      }
    }
  }

  $effect(() => {
    void runId
    void load()
  })
</script>

<section class="accounting-ledgers" data-testid="accounting-ledgers-panel">
  <header>
    <h2>Accounting ledgers</h2>
    <p data-testid="accounting-disclaimer">
      Accounting entries are owner beliefs. “consistent” does not mean true and
      “suspected fraudulent” does not mean proven fraud.
    </p>
    <label>
      Window
      <input aria-label="Window filter" bind:value={windowInput} />
    </label>
  </header>

  {#if status === 'loading'}
    <p>Loading accounting ledgers…</p>
  {:else if status === 'unavailable'}
    <p>Accounting ledgers are disabled for this deployment.</p>
  {:else if status === 'error'}
    <p>Accounting ledgers unavailable: {reason ?? 'error'}</p>
  {:else if status === 'empty'}
    <p>No accounting ledgers were published for this run.</p>
  {:else if summary}
    <dl>
      <dt>Entry coverage</dt><dd>{label(summary.entry_coverage)}</dd>
      <dt>Record coverage</dt><dd>{label(summary.record_coverage)}</dd>
      <dt>Alignment coverage</dt><dd>{label(summary.alignment_coverage)}</dd>
      <dt>Condition coverage</dt><dd>{label(summary.condition_coverage)}</dd>
      <dt>Flow coverage</dt><dd>{label(summary.flow_coverage)}</dd>
      <dt>Counterparty coverage</dt><dd>{label(summary.counterparty_coverage)}</dd>
      <dt>Entries</dt><dd>{summary.entry_count}</dd>
      <dt>Records</dt><dd>{summary.record_count}</dd>
      <dt>Conditions</dt><dd>{summary.condition_count}</dd>
      <dt>Flows</dt><dd>{summary.flow_count}</dd>
      <dt>Counterparties</dt><dd>{summary.counterparty_count}</dd>
      <dt>Alignments</dt><dd>{summary.alignment_count}</dd>
      <dt>Truncated</dt><dd>{summary.truncated ? 'yes' : 'no'}</dd>
    </dl>

    <h3>Entries</h3>
    {#if entries.length === 0}
      <p>No entry rows.</p>
    {:else}
      <table>
        <thead><tr><th>Kind</th><th>Direction</th><th>Item</th><th>Quantity</th><th>Assessment</th></tr></thead>
        <tbody>
          {#each entries as row (row.entry_token + String(row.window_index))}
            <tr>
              <td>{label(row.entry_kind)}</td>
              <td>{label(row.direction)}</td>
              <td>{label(row.item_kind)}</td>
              <td>{row.quantity}</td>
              <td>{label(row.assessment)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}

    <h3>Records</h3>
    {#if records.length === 0}
      <p>No record rows.</p>
    {:else}
      <table>
        <thead><tr><th>Genre</th><th>Integrity</th><th>Revision</th><th>Tombstoned</th></tr></thead>
        <tbody>
          {#each records as row (row.record_token + String(row.window_index))}
            <tr>
              <td>{label(row.record_genre)}</td>
              <td>{label(row.observed_integrity)}</td>
              <td>{row.content_revision}</td>
              <td>{row.tombstoned ? 'yes' : 'no'}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}

    <h3>Conditions</h3>
    {#if conditions.length === 0}
      <p>No condition rows.</p>
    {:else}
      <table>
        <thead><tr><th>Condition</th><th>Records</th><th>Share milli</th></tr></thead>
        <tbody>
          {#each conditions as row (row.condition + String(row.window_index))}
            <tr>
              <td>{label(row.condition)}</td>
              <td>{row.record_count}</td>
              <td>{row.share_milli}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}

    <h3>Flows</h3>
    {#if flows.length === 0}
      <p>No flow rows.</p>
    {:else}
      <table>
        <thead><tr><th>Kind</th><th>Direction</th><th>Events</th><th>Claim sum</th></tr></thead>
        <tbody>
          {#each flows as row (row.flow_token + String(row.window_index))}
            <tr>
              <td>{label(row.entry_kind)}</td>
              <td>{label(row.direction)}</td>
              <td>{row.event_count}</td>
              <td>{row.quantity_sum}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}

    <h3>Counterparties</h3>
    {#if counterparties.length === 0}
      <p>No counterparty rows.</p>
    {:else}
      <table>
        <thead><tr><th>Entries</th><th>Kinds</th><th>First tick</th><th>Last tick</th></tr></thead>
        <tbody>
          {#each counterparties as row (row.counterparty_token + String(row.window_index))}
            <tr>
              <td>{row.entry_count}</td>
              <td>{row.kinds.map(label).join(', ')}</td>
              <td>{row.first_tick}</td>
              <td>{row.last_tick}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}

    <h3>Alignment</h3>
    {#if alignments.length === 0}
      <p>No alignment rows.</p>
    {:else}
      <table>
        <thead><tr><th>Alignment</th><th>Gap milli</th></tr></thead>
        <tbody>
          {#each alignments as row (row.alignment_token + String(row.window_index))}
            <tr>
              <td>{label(row.alignment)}</td>
              <td>{row.gap_milli}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  {/if}
</section>
