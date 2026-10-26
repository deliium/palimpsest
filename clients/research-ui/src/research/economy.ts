/** Completed-exchange analytical network adapters. */

export type TradeItemCount = { kind: string; count: number }

export type TradeRow = {
  key: string
  rowId: string
  participants: string[]
  completedExchanges: number
  forwardItems: TradeItemCount[]
  reverseItems: TradeItemCount[]
  locationId: string | null
  boundaryTick: number | null
  window: { start: number | null; end: number | null }
}

function windowIdentity(row: Record<string, unknown>): string {
  const history =
    row.history !== null && typeof row.history === 'object'
      ? (row.history as Record<string, unknown>)
      : {}
  const window =
    history.window !== null && typeof history.window === 'object'
      ? (history.window as Record<string, unknown>)
      : {}
  return `${String(window.start_tick ?? '')}:${String(window.end_tick ?? '')}:${String(history.boundary_tick ?? '')}`
}

function items(value: unknown): TradeItemCount[] {
  if (!Array.isArray(value)) return []
  return value
    .filter(
      (item): item is Record<string, unknown> =>
        item !== null && typeof item === 'object' && !Array.isArray(item),
    )
    .map((item) => ({
      kind: String(item.kind ?? ''),
      count: Number(item.count ?? 0),
    }))
}

export function tradeRows(rows: readonly Record<string, unknown>[]): TradeRow[] {
  const seen = new Map<string, TradeRow>()
  for (const row of rows) {
    const context =
      row.context !== null && typeof row.context === 'object'
        ? (row.context as Record<string, unknown>)
        : {}
    const history =
      row.history !== null && typeof row.history === 'object'
        ? (row.history as Record<string, unknown>)
        : {}
    const window =
      history.window !== null && typeof history.window === 'object'
        ? (history.window as Record<string, unknown>)
        : {}
    const rowId = String(context.row_id ?? '')
    const key = `${rowId}:${windowIdentity(row)}`
    if (seen.has(key)) continue
    seen.set(key, {
      key,
      rowId,
      participants: Array.isArray(row.participant_ids)
        ? row.participant_ids.filter(
            (item): item is string => typeof item === 'string',
          )
        : [],
      completedExchanges: Number(row.completed_exchange_count ?? 0),
      forwardItems: items(row.forward_items),
      reverseItems: items(row.reverse_items),
      locationId:
        typeof row.occurrence_location_id === 'string'
          ? row.occurrence_location_id
          : null,
      boundaryTick:
        typeof history.boundary_tick === 'number' ? history.boundary_tick : null,
      window: {
        start: typeof window.start_tick === 'number' ? window.start_tick : null,
        end: typeof window.end_tick === 'number' ? window.end_tick : null,
      },
    })
  }
  return [...seen.values()]
}

export type TradeNetwork = {
  nodes: Array<{ id: string; label: string; kind: 'agent' | 'hub'; meta?: Record<string, number> }>
  edges: Array<{
    id: string
    source: string
    target: string
    label: string
    evidenceClass: 'analytical'
  }>
  hubs: number
}

export function tradeNetwork(rows: readonly TradeRow[]): TradeNetwork {
  const nodes = new Map<string, TradeNetwork['nodes'][number]>()
  const edges: TradeNetwork['edges'] = []
  let hubs = 0
  for (const row of rows) {
    const hubId = `exchange:${row.key}`
    nodes.set(hubId, {
      id: hubId,
      label: `completed ${row.completedExchanges}`,
      kind: 'hub',
      meta: { completedExchanges: row.completedExchanges },
    })
    hubs += 1
    for (const participant of row.participants) {
      if (!nodes.has(participant)) {
        nodes.set(participant, {
          id: participant,
          label: participant,
          kind: 'agent',
        })
      }
      edges.push({
        id: `${hubId}->${participant}`,
        source: hubId,
        target: participant,
        label: 'participant',
        evidenceClass: 'analytical',
      })
    }
  }
  return { nodes: [...nodes.values()], edges, hubs }
}

export function itemSummary(itemsToShow: readonly TradeItemCount[]): string {
  if (itemsToShow.length === 0) return '—'
  return itemsToShow.map((item) => `${item.kind}:${item.count}`).join(', ')
}
