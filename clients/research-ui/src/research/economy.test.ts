import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { itemSummary, tradeNetwork, tradeRows } from './economy'

const fixture = JSON.parse(
  readFileSync(
    resolve(process.cwd(), '../godot-observer/fixtures/protocol/civilization/overlay_trade.json'),
    'utf8',
  ),
) as Record<string, unknown>

const rows = (fixture.rows as Record<string, unknown>[]) ?? []

describe('economy adapters', () => {
  it('deduplicates repeated cumulative windows and preserves window identity', () => {
    const parsed = tradeRows([...rows, ...rows])
    expect(parsed).toHaveLength(rows.length)
    expect(parsed[0]?.window.end).toBe(4)
    expect(parsed[0]?.completedExchanges).toBeGreaterThan(0)
  })

  it('renders a hub network instead of a clique of invented bilateral trades', () => {
    const network = tradeNetwork(tradeRows(rows))
    expect(network.hubs).toBe(rows.length)
    expect(network.edges.every((edge) => edge.source.startsWith('exchange:'))).toBe(true)
    expect(network.edges.some((edge) => edge.label === 'participant')).toBe(true)
  })

  it('summarizes item kinds without prices or balances', () => {
    const parsed = tradeRows(rows)
    expect(itemSummary(parsed[0]?.forwardItems ?? [])).not.toContain('price')
    expect(itemSummary([])).toBe('—')
  })
})
