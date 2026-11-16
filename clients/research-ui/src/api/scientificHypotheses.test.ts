import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  buildScientificHypothesesQuery,
  getScientificHypotheses,
  getScientificHypothesesSummary,
} from './scientificHypotheses'

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('scientificHypotheses client', () => {
  it('builds a query with only supplied parameters', () => {
    expect(buildScientificHypothesesQuery()).toBe('')
    expect(buildScientificHypothesesQuery({ limit: 5 })).toBe('?limit=5')
    expect(
      buildScientificHypothesesQuery({
        limit: 5,
        cursor: 'abc',
        windowIndex: 2,
      }),
    ).toBe('?limit=5&cursor=abc&window_index=2')
    expect(
      buildScientificHypothesesQuery({ cursor: '', windowIndex: undefined }),
    ).toBe('')
  })

  it('parses the summary and a paged envelope', async () => {
    const summary = {
      run_id: 'run-1',
      publication_id: 'schyp-1',
      digest: 'sha256:' + 'a'.repeat(64),
      snapshot_version: 'scientific-hypotheses-snapshot-v1',
      policy_version: 'scientific-hypotheses.v1',
      generated_from_tick: 31,
      window_tick: 0,
      window_count: 1,
      coverage: 'complete',
      availability: 'available',
      owner_count: 1,
      hypothesis_count: 1,
      active_count: 1,
      supported_count: 0,
      contradicted_count: 0,
      inconclusive_count: 0,
      revision_count: 1,
      trial_count: 1,
      matched_count: 1,
      mismatched_count: 0,
    }
    const urls: string[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input)
        urls.push(url)
        if (url.endsWith('/scientific-hypotheses')) {
          return json(summary)
        }
        return json({
          run_id: 'run-1',
          publication_id: 'schyp-1',
          window_index: null,
          rows: [
            {
              window_index: 0,
              window_tick: 0,
              hypothesis_token: 'schyp-1',
              claim_token: 'claim-1',
              causal_hypothesis_token: 'none',
              status: 'provisional',
              predicted_outcome: 'success',
              confidence_milli: 500,
              condition_count: 0,
              condition_pairs: [],
              support_count: 0,
              contradiction_count: 0,
              revision_count: 1,
              source_kind: 'self_formulated',
              active: true,
              created_tick: 0,
              coverage: 'complete',
            },
          ],
          next_cursor: null,
          coverage: 'complete',
        })
      }),
    )
    const gotSummary = await getScientificHypothesesSummary('run-1')
    expect(gotSummary.hypothesis_count).toBe(1)
    const page = await getScientificHypotheses('run-1', { limit: 1 })
    expect(page.rows[0]?.status).toBe('provisional')
    expect(urls[0]).toContain('/v1/simulations/run-1/scientific-hypotheses')
    expect(urls[1]).toContain('limit=1')
  })
})
