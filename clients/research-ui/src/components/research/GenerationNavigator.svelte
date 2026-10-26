<script lang="ts">
  import type { ResearchSelection } from '../../research/selection'
  import type { GenerationMarker } from '../../research/generationTypes'
  import { generationTickMismatch, resolveGeneration } from '../../research/population'

  interface Props {
    selection: ResearchSelection
    markers: GenerationMarker[]
    highWater: number | null
    markerStatus: 'loading' | 'available' | 'unavailable' | 'error'
    markerReason?: string | null
    onSelectionChange: (
      patch: Partial<ResearchSelection>,
      historyMode?: 'push' | 'replace',
    ) => void
    onRefreshMarkers?: () => void
  }

  let {
    selection,
    markers,
    highWater,
    markerStatus,
    markerReason = null,
    onSelectionChange,
    onRefreshMarkers,
  }: Props = $props()

  let tickInput = $state('')
  let tickError = $state<string | null>(null)

  $effect(() => {
    tickInput = selection.tick === null ? '' : String(selection.tick)
    tickError = null
  })

  const generation = $derived(
    selection.generationIndex === null
      ? null
      : resolveGeneration(markers, selection.generationIndex),
  )

  const mismatch = $derived(
    generationTickMismatch(
      markers,
      selection.generationIndex,
      selection.tick,
    ),
  )

  const unresolvedGeneration = $derived(
    selection.generationIndex !== null && generation === null,
  )

  const currentIndex = $derived(
    generation === null ? -1 : markers.findIndex((item) => item === generation),
  )

  const disabled = $derived(markerStatus !== 'available' || markers.length === 0)

  function selectGeneration(index: number): void {
    const marker = markers[index]
    if (marker === undefined) {
      return
    }
    onSelectionChange({
      generationIndex: marker.generation_index,
      tick: marker.seek_tick,
      eventId: null,
      sequence: null,
    })
  }

  function previous(): void {
    if (currentIndex > 0) {
      selectGeneration(currentIndex - 1)
    }
  }

  function next(): void {
    if (currentIndex >= 0 && currentIndex + 1 < markers.length) {
      selectGeneration(currentIndex + 1)
    } else if (currentIndex < 0 && markers.length > 0) {
      selectGeneration(0)
    }
  }

  function submitTick(): void {
    const text = tickInput.trim()
    if (!/^(0|[1-9][0-9]*)$/.test(text)) {
      tickError = 'invalid_tick'
      return
    }
    const value = Number.parseInt(text, 10)
    if (!Number.isSafeInteger(value)) {
      tickError = 'invalid_tick'
      return
    }
    tickError = null
    onSelectionChange({ tick: value }, 'replace')
  }

  function moveToFullBoundary(): void {
    onSelectionChange({
      eventId: null,
      sequence: null,
      tick: selection.tick ?? highWater,
    })
  }
</script>

<section class="navigator" aria-label="Generation and tick navigation">
  <div class="group">
    <label for="generation-select">Generation</label>
    <div class="controls">
      <button
        type="button"
        onclick={previous}
        disabled={disabled || currentIndex <= 0}
        aria-label="Previous generation"
      >
        Previous
      </button>
      <select
        id="generation-select"
        value={selection.generationIndex ?? ''}
        onchange={(event) =>
          selectGeneration(Number.parseInt(event.currentTarget.value, 10))}
        disabled={disabled}
      >
        <option value="">Not selected</option>
        {#each markers as marker (marker.generation_index)}
          <option value={marker.generation_index}>
            Generation {marker.generation_index}
            {marker.label_code === 'founders' ? '(founders)' : ''}
            · tick {marker.seek_tick}
          </option>
        {/each}
      </select>
      <button
        type="button"
        onclick={next}
        disabled={disabled || (currentIndex >= 0 && currentIndex + 1 >= markers.length)}
        aria-label="Next generation"
      >
        Next
      </button>
    </div>
  </div>

  <div class="group">
    <label for="tick-input">Tick</label>
    <div class="controls">
      <input
        id="tick-input"
        inputmode="numeric"
        bind:value={tickInput}
        onchange={submitTick}
      />
      <button type="button" onclick={submitTick}>Go</button>
    </div>
  </div>

  <div class="group">
    <span class="label">Discovery high-water</span>
    <div class="controls">
      <strong>{highWater ?? '—'}</strong>
      {#if onRefreshMarkers}
        <button type="button" onclick={onRefreshMarkers}>Refresh markers</button>
      {/if}
      <span class="muted">view tick {selection.tick ?? '—'}</span>
    </div>
  </div>

  {#if markerStatus === 'loading'}
    <p class="notice" role="status">Discovering actual admissions…</p>
  {:else if markerStatus === 'unavailable' || markerStatus === 'error'}
    <p class="notice" role="status">
      Generation discovery unavailable{markerReason ? ` (${markerReason})` : ''}.
      Tick navigation remains usable.
    </p>
  {:else if highWater === null}
    <p class="notice" role="status">
      Discovery pending: finalized high-water H is unknown.
    </p>
  {/if}

  {#if unresolvedGeneration}
    <p class="notice warning" role="status">
      Generation {selection.generationIndex} has no admitted marker at discovery
      high-water {highWater ?? '—'}.
    </p>
  {/if}

  {#if mismatch}
    <p class="notice warning" role="alert">
      generation_tick_mismatch: the explicit tick is preserved and the generation
      label is not rewritten.
    </p>
  {/if}

  {#if tickError !== null}
    <p class="notice error" role="alert">{tickError}</p>
  {/if}

  {#if selection.sequence !== null}
    <p class="notice warning">
      Event-prefix selection cannot drive finalized lineage or capture panels.
      <button type="button" onclick={moveToFullBoundary}>
        Move to full boundary
      </button>
    </p>
  {/if}
</section>

<style>
  .navigator {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem 1.25rem;
    align-items: end;
    border: 1px solid rgba(28, 36, 40, 0.15);
    padding: 0.6rem 0.75rem;
    background: rgba(255, 255, 255, 0.45);
  }

  .group {
    display: grid;
    gap: 0.2rem;
  }

  label,
  .label {
    font-size: 0.75rem;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: #5a6a72;
  }

  .controls {
    display: flex;
    gap: 0.35rem;
    align-items: center;
  }

  button,
  select,
  input {
    font: inherit;
    padding: 0.25rem 0.45rem;
    border: 1px solid rgba(28, 36, 40, 0.25);
    background: rgba(255, 255, 255, 0.8);
  }

  input {
    width: 7rem;
  }

  .muted {
    color: #5a6a72;
    font-size: 0.8rem;
  }

  .notice {
    flex-basis: 100%;
    margin: 0;
    font-size: 0.85rem;
  }

  .warning {
    color: #6a5420;
  }

  .error {
    color: #8a3030;
  }
</style>
