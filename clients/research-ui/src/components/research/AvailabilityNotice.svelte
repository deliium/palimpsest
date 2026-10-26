<script lang="ts">
  interface Props {
    status:
      | 'loading'
      | 'available'
      | 'empty'
      | 'partial'
      | 'unavailable'
      | 'forbidden'
      | 'error'
    reason: string | null
    requestedTick?: number | null
    resolvedTick?: number | null
    coverage?: number | null
    continuation?: string | null
    onLoadMore?: () => void
  }

  let {
    status,
    reason,
    requestedTick = null,
    resolvedTick = null,
    coverage = null,
    continuation = null,
    onLoadMore,
  }: Props = $props()
</script>

{#if status !== 'available' || continuation !== null}
  <div class="notice" data-status={status} role={status === 'error' ? 'alert' : 'status'}>
    <strong>
      {#if status === 'loading'}Loading{/if}
      {#if status === 'empty'}Complete empty evidence{/if}
      {#if status === 'partial'}Partial evidence{/if}
      {#if status === 'unavailable'}Evidence unavailable{/if}
      {#if status === 'forbidden'}Credential required{/if}
      {#if status === 'error'}Evidence error{/if}
      {#if status === 'available'}More evidence available{/if}
    </strong>
    {#if reason}<span class="code">{reason}</span>{/if}
    {#if requestedTick !== null}<span>requested tick {requestedTick}</span>{/if}
    {#if resolvedTick !== null}<span>resolved tick {resolvedTick}</span>{/if}
    {#if coverage !== null}<span>coverage {(coverage * 100).toFixed(0)}%</span>{/if}
    {#if continuation !== null && onLoadMore}
      <button type="button" onclick={onLoadMore}>Load more</button>
    {/if}
  </div>
{/if}

<style>
  .notice {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem 0.75rem;
    align-items: center;
    border-left: 4px solid #2e5c6e;
    padding: 0.45rem 0.7rem;
    background: rgba(255, 255, 255, 0.55);
    font-size: 0.9rem;
  }

  .notice[data-status='unavailable'],
  .notice[data-status='forbidden'],
  .notice[data-status='error'] {
    border-left-color: #8a3030;
  }

  .notice[data-status='partial'] {
    border-left-color: #8a6a30;
  }

  .code {
    font-family: ui-monospace, monospace;
    color: #5a6a72;
  }

  button {
    font: inherit;
    cursor: pointer;
  }
</style>
