<script lang="ts">
  import EpistemicBadge from '../EpistemicBadge.svelte'
  import type { EpistemicClass } from '../../epistemic'

  interface Props {
    label: string
    value: string
    unit?: string | null
    evidenceClass: EpistemicClass
    ownerId?: string | null
    coverage?: number | null
    note?: string | null
  }

  let {
    label,
    value,
    unit = null,
    evidenceClass,
    ownerId = null,
    coverage = null,
    note = null,
  }: Props = $props()
</script>

<article class="card">
  <p class="label">{label}</p>
  <p class="value">{value}{#if unit}<span class="unit"> {unit}</span>{/if}</p>
  <div class="meta">
    <EpistemicBadge epistemic={evidenceClass} />
    {#if ownerId}<span>owner {ownerId}</span>{/if}
    {#if coverage !== null}<span>coverage {(coverage * 100).toFixed(0)}%</span>{/if}
  </div>
  {#if note}<p class="note">{note}</p>{/if}
</article>

<style>
  .card {
    border: 1px solid rgba(28, 36, 40, 0.15);
    background: rgba(255, 255, 255, 0.45);
    padding: 0.6rem 0.75rem;
    display: grid;
    gap: 0.2rem;
  }

  .label,
  .value,
  .note {
    margin: 0;
  }

  .label {
    color: #5a6a72;
    font-size: 0.8rem;
  }

  .value {
    font-size: 1.3rem;
    font-variant-numeric: tabular-nums;
  }

  .unit {
    font-size: 0.85rem;
    color: #5a6a72;
  }

  .meta {
    display: flex;
    gap: 0.5rem;
    align-items: center;
    font-size: 0.8rem;
    color: #5a6a72;
  }

  .note {
    font-size: 0.8rem;
    color: #5a6a72;
  }
</style>
