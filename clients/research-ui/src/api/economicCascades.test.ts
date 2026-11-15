import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  buildEconomicCascadesQuery,
  getEconomicCascadesChains,
  getEconomicCascadesSummary,
} from './economicCascades'

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('economicCascades client', () => {
  it('builds a query with only supplied parameters', () => {
    expect(buildEconomicCascadesQuery()).toBe('')
    expect(buildEconomicCascadesQuery({ limit: 5 })).toBe('?limit=5')
    expect(
      buildEconomicCascadesQuery({
        limit: 5,
        cursor: 'abc',
        windowIndex: 2,
      }),
    ).toBe('?limit=5&cursor=abc&window_index=2')
    expect(buildEconomicCascadesQuery({ cursor: '', windowIndex: undefined })).toBe(
      '',
    )
  })

  it('parses the summary and a paged envelope', async () => {
    const summary = {
      run_id: 'run-1',
      publication_id: 'ecasc-1',
      digest: 'sha256:' + 'a'.repeat(64),
      snapshot_version: 'economic-cascades-snapshot-v1',
      policy_version: 'economic-cascades.v1',
      generated_from_tick: 31,
      window_tick: 0,
      window_count: 1,
      coverage: 'complete',
      availability: 'available',
      event_count: 2,
      disruption_count: 1,
      stage_count: 1,
      dependency_edge_count: 1,
      chain_count: 1,
      linked_chain_count: 1,
      disruption_kind_count: 1,
      max_depth: 1,
    }
    const urls: string[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input)
        urls.push(url)
        if (url.endsWith('/economic-cascades')) return json(summary)
        return json({
          run_id: 'run-1',
          publication_id: 'ecasc-1',
          window_index: 0,
          rows: [],
          next_cursor: null,
          coverage: 'complete',
        })
      }),
    )
    expect(await getEconomicCascadesSummary('run-1')).toEqual(summary)
    const page = await getEconomicCascadesChains('run-1', {
      limit: 2,
      windowIndex: 0,
    })
    expect(page.rows).toEqual([])
    expect(urls[1]).toContain('/economic-cascades/chains?limit=2&window_index=0')
  })
})
