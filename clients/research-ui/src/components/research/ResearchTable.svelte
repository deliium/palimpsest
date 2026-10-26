<script lang="ts">
  export type ResearchColumn = {
    key: string
    label: string
    numeric?: boolean
  }

  export type ResearchRow = Record<string, string | number | null>

  interface Props {
    caption: string
    columns: ResearchColumn[]
    rows: ResearchRow[]
    rowKey: (row: ResearchRow) => string
    onRowSelect?: (row: ResearchRow) => void
    emptyLabel?: string
  }

  let {
    caption,
    columns,
    rows,
    rowKey,
    onRowSelect,
    emptyLabel = 'No rows.',
  }: Props = $props()
</script>

<table>
  <caption>{caption}</caption>
  <thead>
    <tr>
      {#each columns as column (column.key)}
        <th scope="col" class:numeric={column.numeric}>{column.label}</th>
      {/each}
    </tr>
  </thead>
  <tbody>
    {#if rows.length === 0}
      <tr><td colspan={columns.length}>{emptyLabel}</td></tr>
    {:else}
      {#each rows as row (rowKey(row))}
        <tr
          tabindex={onRowSelect ? 0 : undefined}
          role={onRowSelect ? 'button' : undefined}
          onclick={() => onRowSelect?.(row)}
          onkeydown={(event) => {
            if (onRowSelect && (event.key === 'Enter' || event.key === ' ')) {
              event.preventDefault()
              onRowSelect(row)
            }
          }}
        >
          {#each columns as column (column.key)}
            <td class:numeric={column.numeric}>{row[column.key] ?? '—'}</td>
          {/each}
        </tr>
      {/each}
    {/if}
  </tbody>
</table>

<style>
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.9rem;
  }

  caption {
    text-align: left;
    font-weight: 600;
    padding-bottom: 0.3rem;
  }

  th,
  td {
    border-bottom: 1px solid rgba(28, 36, 40, 0.12);
    padding: 0.3rem 0.45rem;
    text-align: left;
  }

  .numeric {
    text-align: right;
    font-variant-numeric: tabular-nums;
  }

  tbody tr[role='button'] {
    cursor: pointer;
  }

  tbody tr[role='button']:focus-visible {
    outline: 2px solid #2e5c6e;
  }
</style>
