<script lang="ts">
  import { untrack } from 'svelte'
  import { ApiClientError } from '../api/client'
  import {
    getCulturalEvidence,
    getLabels,
    getSemanticHistory,
    getSymbolicLanguage,
    getTranslation,
  } from '../api/research'
  import AvailabilityNotice from '../components/research/AvailabilityNotice.svelte'
  import ResearchTable from '../components/research/ResearchTable.svelte'
  import SeriesChart from '../components/research/SeriesChart.svelte'
  import {
    culturalSeries,
    summarizeCulturalPage,
    type CulturalPageSummary,
  } from '../research/culture'
  import {
    currentMetadataCard,
    semanticTimeline,
    type CurrentSemanticCard,
    type SemanticTimeline,
  } from '../research/language'
  import type { ResearchSelection } from '../research/selection'

  interface Props {
    runId: string
    selection: ResearchSelection
  }

  let { runId, selection }: Props = $props()

  let mode = $state<'vocabulary' | 'semantics' | 'current'>('vocabulary')
  let matrixId = $state('')
  let cellId = $state('')
  let vocabulary = $state<CulturalPageSummary | null>(null)
  let vocabularyStatus = $state<'loading' | 'available' | 'empty' | 'partial' | 'unavailable' | 'forbidden' | 'error'>('unavailable')
  let vocabularyReason = $state<string | null>(null)
  let ownerId = $state(untrack(() => selection.scopeOwnerId ?? ''))

  $effect(() => {
    ownerId = selection.scopeOwnerId ?? ''
  })
  let source = $state<'label' | 'composition'>('label')
  let timeline = $state<SemanticTimeline | null>(null)
  let semanticStatus = $state<'loading' | 'available' | 'empty' | 'unavailable' | 'forbidden' | 'error'>('unavailable')
  let semanticReason = $state<string | null>(null)
  let cards = $state<CurrentSemanticCard[]>([])

  async function loadVocabulary(more = false): Promise<void> {
    if (matrixId.trim() === '' || cellId.trim() === '') {
      vocabularyStatus = 'unavailable'
      vocabularyReason = 'matrix_cell_required'
      return
    }
    vocabularyStatus = 'loading'
    try {
      const page = await getCulturalEvidence(matrixId.trim(), cellId.trim(), {
        section: 'traits',
        dimension: 'vocabulary',
        limit: 200,
        cursor: more ? null : null,
      })
      if (String(page.run_id ?? '') !== runId) {
        vocabularyStatus = 'error'
        vocabularyReason = 'matrix_run_mismatch'
        return
      }
      vocabulary = summarizeCulturalPage(page)
      vocabularyStatus =
        vocabulary.dimensions.length === 0
          ? 'empty'
          : vocabulary.partial
            ? 'partial'
            : 'available'
      vocabularyReason = null
    } catch (err) {
      vocabularyStatus = err instanceof ApiClientError && err.status === 403 ? 'forbidden' : 'error'
      vocabularyReason = err instanceof ApiClientError ? err.code : 'fetch_failed'
    }
  }

  async function loadSemantics(): Promise<void> {
    if (ownerId.trim() === '') {
      semanticStatus = 'unavailable'
      semanticReason = 'owner_required'
      return
    }
    semanticStatus = 'loading'
    try {
      const history = await getSemanticHistory(runId, ownerId.trim(), {
        source,
        tick: selection.tick,
        limit: 200,
      })
      timeline = semanticTimeline(history)
      semanticStatus =
        timeline.availability === 'available'
          ? timeline.groups.length === 0
            ? 'empty'
            : 'available'
          : 'unavailable'
      semanticReason = timeline.reason
    } catch (err) {
      semanticStatus = err instanceof ApiClientError && err.status === 403 ? 'forbidden' : 'error'
      semanticReason = err instanceof ApiClientError ? err.code : 'fetch_failed'
    }
  }

  async function loadCurrent(): Promise<void> {
    if (ownerId.trim() === '') {
      return
    }
    const found: CurrentSemanticCard[] = []
    try {
      const labels = await getLabels(runId, ownerId.trim(), selection.tick)
      found.push(
        currentMetadataCard(
          labels,
          'labels',
          'Current checkpoint labels are not restored historical state.',
        ),
      )
    } catch {
      // Lane-local failure only.
    }
    try {
      const symbolic = await getSymbolicLanguage(runId, ownerId.trim(), selection.tick)
      found.push(
        currentMetadataCard(
          symbolic,
          'symbolic',
          'Current composition metadata; no composition parts are exposed.',
        ),
      )
    } catch {
      // Lane-local failure only.
    }
    try {
      const translation = await getTranslation(runId, ownerId.trim(), selection.tick)
      found.push(
        currentMetadataCard(
          translation,
          'translation',
          'Current private translation claims, not shared meaning.',
        ),
      )
    } catch {
      // Lane-local failure only.
    }
    cards = found
  }
</script>

<section class="page">
  <header>
    <p class="eyebrow">Language</p>
    <h1>Vocabulary, semantics and current meaning</h1>
    <p class="lede">
      Vocabulary is an inventory measurement; semantics is retained checkpoint
      evidence; current labels are not restored history.
    </p>
  </header>

  <div class="controls" role="tablist" aria-label="Language modes">
    <button type="button" role="tab" aria-selected={mode === 'vocabulary'} class:active={mode === 'vocabulary'} onclick={() => (mode = 'vocabulary')}>Vocabulary</button>
    <button type="button" role="tab" aria-selected={mode === 'semantics'} class:active={mode === 'semantics'} onclick={() => (mode = 'semantics')}>Semantics</button>
    <button type="button" role="tab" aria-selected={mode === 'current'} class:active={mode === 'current'} onclick={() => { mode = 'current'; void loadCurrent() }}>Current metadata</button>
  </div>

  <div class="controls">
    {#if mode !== 'current'}
      <label>Matrix <input bind:value={matrixId} /></label>
      <label>Cell <input bind:value={cellId} /></label>
    {/if}
    <label>Owner <input bind:value={ownerId} /></label>
    {#if mode === 'semantics'}
      <label>
        Source
        <select bind:value={source}>
          <option value="label">label</option>
          <option value="composition">composition</option>
        </select>
      </label>
    {/if}
    {#if mode === 'vocabulary'}
      <button type="button" onclick={() => void loadVocabulary()}>Load vocabulary</button>
    {:else if mode === 'semantics'}
      <button type="button" onclick={() => void loadSemantics()}>Load semantics</button>
    {:else}
      <button type="button" onclick={() => void loadCurrent()}>Load current metadata</button>
    {/if}
  </div>

  {#if mode === 'vocabulary'}
    <AvailabilityNotice status={vocabularyStatus} reason={vocabularyReason} requestedTick={selection.tick} />
    {#if vocabulary !== null}
      <p class="muted">
        Binding {vocabulary.binding} · run {vocabulary.runId}
        {#if vocabulary.partial}· partial inventory{/if}
      </p>
      <SeriesChart
        title="Vocabulary distinct forms"
        description="Distinct opaque content digests in dimension vocabulary. Missing capture remains a gap."
        series={culturalSeries(vocabulary, 'distinctForms')}
      />
      <ResearchTable
        caption="Vocabulary dimensions"
        columns={[
          { key: 'dimension', label: 'Dimension' },
          { key: 'tick', label: 'Tick', numeric: true },
          { key: 'forms', label: 'Distinct forms', numeric: true },
          { key: 'status', label: 'Status' },
        ]}
        rows={vocabulary.dimensions.flatMap((dimension) =>
          dimension.points.map((point) => ({
            dimension: dimension.dimension,
            tick: point.tick,
            forms: point.distinctForms,
            status: point.complete ? 'complete' : 'partial',
          })),
        )}
        rowKey={(row) => `${row.dimension}:${row.tick}`}
      />
      {#if vocabulary.binding === 'legacy_unverified'}
        <p class="warning" role="status">
          legacy_unverified: runtime completion is not established.
        </p>
      {/if}
    {/if}
  {:else if mode === 'semantics'}
    <AvailabilityNotice status={semanticStatus} reason={semanticReason} requestedTick={selection.tick} />
    {#if timeline !== null}
      <p class="muted">
        Checkpoint tick {timeline.checkpointTick ?? '—'} · retained-only
        {timeline.retainedOnly ? 'yes' : 'no'} · prefix complete
        {timeline.prefixComplete ? 'yes' : 'unknown'}
      </p>
      <ResearchTable
        caption="Retained sense groups"
        columns={[
          { key: 'owner', label: 'Owner' },
          { key: 'source', label: 'Source' },
          { key: 'local', label: 'Local ID' },
          { key: 'term', label: 'Term digest' },
          { key: 'rows', label: 'Rows', numeric: true },
          { key: 'first', label: 'First ordinal', numeric: true },
        ]}
        rows={timeline.groups.map((group) => ({
          owner: group.ownerId,
          source: group.source,
          local: group.localId,
          term: group.termDigest,
          rows: group.rows.length,
          first: Number(group.rows[0]?.ordinal ?? 0),
        }))}
        rowKey={(row) => String(row.local) + String(row.term)}
      />
      <ResearchTable
        caption="Retained sense transitions"
        columns={[
          { key: 'from', label: 'From tick', numeric: true },
          { key: 'to', label: 'To tick', numeric: true },
          { key: 'trigger', label: 'Trigger' },
          { key: 'changed', label: 'Referent changed' },
          { key: 'confidence', label: 'Confidence', numeric: true },
        ]}
        rows={timeline.transitions.map((transition) => ({
          from: transition.fromTick,
          to: transition.toTick,
          trigger: transition.trigger,
          changed: transition.changed ? 'yes' : 'no',
          confidence: transition.confidence,
        }))}
        rowKey={(row) => `${row.from}:${row.to}:${row.trigger}`}
      />
      {#if timeline.transitions.length === 0}
        <p class="muted">
          No retained transitions in this bounded history. This is not proof of
          lifetime semantic stability.
        </p>
      {/if}
    {/if}
  {:else}
    {#if cards.length === 0}
      <p class="muted">No current metadata cards loaded (owner and tick required).</p>
    {:else}
      <div class="cards">
        {#each cards as card (card.layer)}
          <article>
            <h2>{card.layer}</h2>
            <p>owner {card.ownerId} · {card.count} item(s)</p>
            <p class="muted">Current checkpoint only. {card.note}</p>
          </article>
        {/each}
      </div>
    {/if}
  {/if}
</section>

<style>
  .page { display: grid; gap: 0.9rem; }
  .eyebrow { margin: 0 0 0.2rem; font-size: 0.75rem; letter-spacing: 0.08em; text-transform: uppercase; color: #5a6a72; }
  h1 { margin: 0 0 0.3rem; font-size: 1.35rem; }
  h2 { margin: 0 0 0.2rem; font-size: 0.95rem; }
  .lede { margin: 0; color: #3a474e; }
  .controls { display: flex; flex-wrap: wrap; gap: 0.6rem; align-items: end; }
  label { display: grid; gap: 0.2rem; font-size: 0.8rem; color: #5a6a72; }
  input, select, button { font: inherit; padding: 0.25rem 0.45rem; }
  button.active { border-color: #2e5c6e; color: #2e5c6e; font-weight: 600; }
  .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr)); gap: 0.6rem; }
  .cards article { border: 1px solid rgba(28, 36, 40, 0.15); padding: 0.5rem 0.7rem; background: rgba(255,255,255,0.45); }
  .muted { color: #5a6a72; font-size: 0.85rem; }
  .warning { margin: 0; color: #6a5420; font-size: 0.85rem; }
</style>
