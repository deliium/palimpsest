import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushSync, render } from '../test/mount'
import MatrixPanel from './MatrixPanel.svelte'

const digest = 'a'.repeat(64)
const calls: string[] = []

function json(body: unknown, status = 200, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json', ...headers },
  })
}

async function settle(): Promise<void> {
  await Promise.resolve()
  await new Promise((resolve) => setTimeout(resolve, 0))
  await Promise.resolve()
  await Promise.resolve()
  flushSync()
}

afterEach(() => {
  vi.unstubAllGlobals()
  calls.length = 0
})

describe('matrix panel metrics', () => {
  it('renders real scalar and cultural metric facets with binding', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input)
        calls.push(url)
        if (url.endsWith('/v1/research/matrices')) {
          return json({
            items: [
              {
                matrix_id: 'm1',
                schema_version: 'experiment-matrix-v1',
                has_aggregate: false,
                has_metric_summary: false,
              },
            ],
            count: 1,
            availability: 'available',
          })
        }
        if (url.includes('/manifest')) {
          return json({ schema_version: 'experiment-matrix-v1', matrix_id: 'm1' })
        }
        if (url.includes('/cells/') && url.endsWith('/metrics')) {
          return json([
            {
              metric_family: 'generational_cohort_comparison@1',
              availability: 'present',
              values: { mean_generation: 2.5 },
            },
          ])
        }
        if (url.includes('/cultural-metrics')) {
          return json(
            {
              schema_version: 'cultural-cell-metrics-v1',
              cell_id: 'cell-a',
              matrix_fingerprint: digest,
              cell_fingerprint: digest,
              config_fingerprint: digest,
              run_id: 'run-1',
              capture_policy: { enabled: true, max_frames: 1, max_rows: 1 },
              analysis_window: { baseline_boundary: 0, end_boundary: 1 },
              evidence_digest: digest,
              documents: [
                {
                  metric_family: 'cultural_trait_dynamics@1',
                  availability: 'present',
                  values: {
                    rows_json:
                      '[{"row_id":"r1","measurement_id":"trait_frequency","dimension":"belief","representation":"fraction","scope":"owner","population_basis":"owners","denominator_code":"eligible","baseline_tick":0,"end_tick":10,"units":"ratio","value":0.5,"availability":"present"}]',
                  },
                },
              ],
              digest,
            },
            200,
            { 'X-Palimpsest-Artifact-Binding': 'runtime_bound' },
          )
        }
        if (url.includes('/cultural-comparison')) {
          return json(
            {
              schema_version: 'cultural-metric-comparison-v1',
              matrix_fingerprint: digest,
              confidence: 0.95,
              method: 'student_t_seed_block_mean',
              conditions: [
                {
                  condition_id: 'control',
                  measurements: [
                    {
                      measurement: {
                        family: 'cultural_trait_dynamics',
                        measurement_id: 'trait_frequency',
                        dimension: 'belief',
                        representation: 'fraction',
                        scope: 'owner',
                        partition_id: 'p',
                        population_basis: 'owners',
                        denominator_code: 'eligible',
                        baseline_tick: 0,
                        end_tick: 10,
                        units: 'ratio',
                      },
                      method: 'student_t_seed_block_mean',
                      confidence: 0.95,
                      n: 2,
                      raw_cell_count: 2,
                      duplicate_cell_count: 0,
                      mean: 0.5,
                      ci_low: 0.1,
                      ci_high: 0.9,
                      df: 1,
                      inference_status: 'present',
                    },
                  ],
                },
              ],
              contrasts: [],
            },
            200,
            { 'X-Palimpsest-Artifact-Binding': 'legacy_unverified' },
          )
        }
        if (url.includes('/cells/') && !url.endsWith('/cells')) {
          return json({ cell_id: 'cell-a', run_id: 'run-1', state: 'completed' })
        }
        if (url.endsWith('/cells')) {
          return json({ matrix_id: 'm1', cell_ids: ['cell-a'], count: 1 })
        }
        return json({}, 404)
      }),
    )
    const mounted = render(MatrixPanel as never, { matrixId: 'm1' })
    await settle()
    await settle()
    expect(mounted.target.textContent).toContain('generational_cohort_comparison@1')
    expect(mounted.target.textContent).toContain('cultural_trait_dynamics')
    expect(mounted.target.textContent).toContain('0.100000 … 0.900000')
    expect(mounted.target.textContent).toContain('runtime_bound')
    expect(mounted.target.textContent).toContain('legacy_unverified')
    expect(mounted.target.textContent).toContain('Open run run-1')
    mounted.cleanup()
  })
})
