import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  buildScientificModelsQuery,
  getScientificModelsPage,
  getScientificModelsSummary,
} from './scientificModels'

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('scientific models client', () => {
  it('builds only supplied filters', () => {
    expect(buildScientificModelsQuery()).toBe('')
    expect(buildScientificModelsQuery({ limit: 5 })).toBe('?limit=5')
    expect(
      buildScientificModelsQuery({
        publicationId: 'pub-1',
        cursor: 'abc',
        issuedFromTick: 3,
        issuedThroughTick: 9,
      }),
    ).toBe(
      '?publication_id=pub-1&cursor=abc&issued_from_tick=3&issued_through_tick=9',
    )
  })

  it('forwards publication and parses summary and page', async () => {
    const summary = {
      run_id: 'run-1',
      publication_id: 'pub-1',
      snapshot_digest: 'a'.repeat(64),
      schema_version: 'scientific-models-snapshot-v1',
      policy_version: 'scientific-models-publication.v1',
      finalized_through_tick: 9,
      coverage_status: 'complete',
      counts: { predictions: 2 },
      publications: ['pub-1'],
    }
    const urls: string[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) => {
        urls.push(url)
        if (url.includes('/predictions')) {
          return Promise.resolve(
            json({
              run_id: 'run-1',
              publication_id: 'pub-1',
              snapshot_digest: 'a'.repeat(64),
              section: 'predictions',
              rows: [{ prediction_token: 'p1' }],
              next_cursor: null,
              truncated: false,
            }),
          )
        }
        return Promise.resolve(json(summary))
      }),
    )
    const loaded = await getScientificModelsSummary('run-1', 'pub-1')
    expect(loaded.publication_id).toBe('pub-1')
    expect(loaded.counts.predictions).toBe(2)
    const page = await getScientificModelsPage('run-1', 'predictions', {
      publicationId: 'pub-1',
      limit: 2,
    })
    expect(page.rows).toEqual([{ prediction_token: 'p1' }])
    expect(urls[0]).toContain('/scientific-models?publication_id=pub-1')
    expect(urls[1]).toContain('/scientific-models/predictions?publication_id=pub-1&limit=2')
  })
})
