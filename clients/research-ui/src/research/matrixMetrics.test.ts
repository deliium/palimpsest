import { describe, expect, it } from 'vitest'
import {
  culturalComparisonFacets,
  incompatibleSelectors,
  intervalUsable,
  scalarMetricFacets,
} from './matrixMetrics'

describe('matrix metric adapters', () => {
  it('reads scalar generational values from stored documents', () => {
    const facets = scalarMetricFacets('cell-a', [
      {
        metric_family: 'generational_cohort_comparison@1',
        availability: 'present',
        values: { mean_generation: 2.5, lagged: 1 },
      },
    ])
    expect(facets.map((facet) => facet.measurementId)).toEqual([
      'mean_generation',
      'lagged',
    ])
    expect(facets[0]?.value).toBe(2.5)
  })

  it('reads nested rows_json rows and preserves PARTIAL availability', () => {
    const facets = scalarMetricFacets('cell-a', {
      documents: [
        {
          metric_family: 'cultural_trait_dynamics@1',
          availability: 'partial',
          values: {
            rows_json:
              '[{"row_id":"r1","measurement_id":"trait_frequency","dimension":"belief","representation":"fraction","scope":"owner","population_basis":"owners","denominator_code":"eligible","baseline_tick":0,"end_tick":10,"units":"ratio","value":0.5,"availability":"partial","coverage_observed":1}]',
          },
        },
      ],
    })
    expect(facets[0]?.measurementId).toBe('trait_frequency')
    expect(facets[0]?.availability).toBe('partial')
    expect(facets[0]?.selectorsComplete).toBe(true)
  })

  it('renders intervals only with a supplied compatible status', () => {
    const comparison = {
      schema_version: 'cultural-metric-comparison-v1',
      matrix_fingerprint: 'a'.repeat(64),
      confidence: 0.95,
      method: 'student_t_seed_block_mean',
      conditions: [
        {
          condition_id: 'control',
          measurements: [
            {
              measurement: {
                family: 'cultural_trait_dynamics',
                measure_id: 'trait_frequency',
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
    }
    const facets = culturalComparisonFacets(null, comparison)
    expect(facets[0]?.measurementId).toBe('trait_frequency')
    expect(intervalUsable(facets[0]!)).toBe(true)
    expect(
      intervalUsable({ ...facets[0]!, inferenceStatus: 'insufficient_evidence' }),
    ).toBe(false)
  })

  it('separates incompatible selectors instead of merging them', () => {
    const base = scalarMetricFacets('cell-a', {
      documents: [
        {
          metric_family: 'f',
          values: {
            rows_json:
              '[{"measurement_id":"m","dimension":"a","representation":"r","scope":"s","population_basis":"p","denominator_code":"d","baseline_tick":0,"end_tick":1,"units":"u","value":1},{"measurement_id":"m","dimension":"b","representation":"r","scope":"s","population_basis":"p","denominator_code":"d","baseline_tick":0,"end_tick":1,"units":"u","value":2}]',
          },
        },
      ],
    })
    expect(incompatibleSelectors(base)).toEqual([['f', 'm']])
  })
})
