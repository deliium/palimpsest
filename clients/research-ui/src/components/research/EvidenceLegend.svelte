<script lang="ts">
  import { EPISTEMIC_LABELS, type EpistemicClass } from '../../epistemic'

  interface Entry {
    label: string
    evidenceClass: EpistemicClass
    ownerId?: string | null
    source?: string | null
    window?: string | null
    coverage?: number | null
  }

  interface Props {
    entries: Entry[]
  }

  let { entries }: Props = $props()
</script>

<ul class="legend" aria-label="Evidence legend">
  {#each entries as entry (entry.label)}
    <li>
      <span class="badge">{EPISTEMIC_LABELS[entry.evidenceClass]}</span>
      <span>{entry.label}</span>
      {#if entry.ownerId}<span class="muted">owner {entry.ownerId}</span>{/if}
      {#if entry.source}<span class="muted">source {entry.source}</span>{/if}
      {#if entry.window}<span class="muted">window {entry.window}</span>{/if}
      {#if entry.coverage !== null && entry.coverage !== undefined}
        <span class="muted">coverage {(entry.coverage * 100).toFixed(0)}%</span>
      {/if}
    </li>
  {/each}
</ul>

<style>
  .legend {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem 1rem;
    margin: 0;
    padding: 0;
    list-style: none;
    font-size: 0.85rem;
  }

  .legend li {
    display: flex;
    gap: 0.35rem;
    align-items: center;
  }

  .badge {
    border: 1px solid rgba(28, 36, 40, 0.25);
    padding: 0.05rem 0.3rem;
    font-size: 0.7rem;
  }

  .muted {
    color: #5a6a72;
  }
</style>
