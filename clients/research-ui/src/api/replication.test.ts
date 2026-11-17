import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  buildReplicationQuery,
  getReplicationPage,
  validateReplicationQuery,
} from './replication'

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('replication client', () => {
  it('builds only supplied filters', () => {
    expect(buildReplicationQuery()).toBe('')
    expect(buildReplicationQuery({ limit: 5 })).toBe('?limit=5')
    expect(
      buildReplicationQuery({
        publicationId: 'srep-1',
        cursor: 'abc',
        windowIndex: 2,
      }),
    ).toBe('?publication_id=srep-1&cursor=abc&limit=&window_index=2'.replace('limit=&', ''))
  })

  it('rejects unsupported filter combinations', () => {
    expect(() =>
      validateReplicationQuery('results', { designToken: 'rpd-1' }),
    ).toThrow('scientific_replication_filter_invalid')
    expect(() =>
      validateReplicationQuery('designs', { collaborationToken: 'rpc-1' }),
    ).toThrow('scientific_replication_filter_invalid')
    expect(() =>
      validateReplicationQuery('comparisons', { designToken: 'rpd-1' }),
    ).not.toThrow()
  })

  it('forwards publication and cursor and parses a page', async () => {
    const page = {
      run_id: 'run-1',
      publication_id: 'srep-1',
      internal_digest: 'a'.repeat(64),
      policy_version: 'scientific-replication.v1',
      coverage: 'partial',
      availability: 'available',
      rows: [],
      next_cursor: null,
      truncated: false,
    }
    const urls: string[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) => {
        urls.push(url)
        return Promise.resolve(json(page))
      }),
    )
    const result = await getReplicationPage('run-1', 'results', {
      publicationId: 'srep-1',
      cursor: 'abc',
      limit: 5,
    })
    expect(result.publication_id).toBe('srep-1')
    expect(urls[0]).toContain('/scientific-replication/results?')
    expect(urls[0]).toContain('publication_id=srep-1')
    expect(urls[0]).toContain('cursor=abc')
  })
})
