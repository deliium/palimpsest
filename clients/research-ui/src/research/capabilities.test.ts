import { describe, expect, it } from 'vitest'
import {
  PANEL_SOURCES,
  PANEL_SOURCE_IDS,
  classifySourceAccess,
  classifySourceOutcome,
  sourcesForPanel,
  type SourceResponse,
} from './capabilities'

function response(overrides: Partial<SourceResponse> = {}): SourceResponse {
  return {
    source: 'demographics',
    evidenceClass: 'objective',
    hasCredential: true,
    itemCount: 3,
    ...overrides,
  }
}

describe('source registry', () => {
  it('is closed and declares endpoint, capability and temporal semantics', () => {
    for (const id of PANEL_SOURCE_IDS) {
      const entry = PANEL_SOURCES[id]
      expect(entry.endpoint.length).toBeGreaterThan(0)
      expect(entry.evidenceClasses.length).toBeGreaterThan(0)
      expect(entry.temporal.length).toBeGreaterThan(0)
      for (const evidence of entry.evidenceClasses) {
        expect(entry.capabilities[evidence]).toBeDefined()
      }
    }
  })

  it('maps panels to lazy sources', () => {
    expect(sourcesForPanel('population')).toEqual([
      'demographics',
      'generation_markers',
    ])
    expect(sourcesForPanel('unknown')).toEqual([])
  })
})

describe('source access', () => {
  it('requires debug without downgrading subjective evidence', () => {
    const access = classifySourceAccess('lineage', 'subjective', false)
    expect(access.allowed).toBe(false)
    expect(access.capability).toBe('subjective_debug')
    expect(access.outcome?.status).toBe('forbidden')
    expect(access.outcome?.credentialEntryOffered).toBe(true)
  })

  it('rejects unsupported evidence classes', () => {
    const access = classifySourceAccess('demographics', 'analytical', true)
    expect(access.allowed).toBe(false)
    expect(access.outcome?.reasonCode).toBe('unsupported_evidence_class')
  })
})

describe('outcome normalization', () => {
  it('distinguishes availability states from zero', () => {
    expect(classifySourceOutcome(response({ loading: true })).status).toBe('loading')
    expect(classifySourceOutcome(response()).status).toBe('available')
    expect(classifySourceOutcome(response({ itemCount: 0 })).status).toBe('empty')
    expect(
      classifySourceOutcome(response({ source: 'demographics', reasonCode: 'capture_disabled' }))
        .status,
    ).toBe('unavailable')
    expect(
      classifySourceOutcome(response({ source: 'demographics', reasonCode: 'lifecycle_disabled' }))
        .status,
    ).toBe('unavailable')
    expect(
      classifySourceOutcome(response({ hasCredential: false })).status,
    ).toBe('forbidden')
    expect(classifySourceOutcome(response({ httpStatus: 403 })).status).toBe('forbidden')
    expect(
      classifySourceOutcome(response({ coverage: 0.5 })).status,
    ).toBe('partial')
    expect(
      classifySourceOutcome(
        response({ reasonCode: 'uncaptured_boundary' }),
      ).status,
    ).toBe('unavailable')
    expect(classifySourceOutcome(response({ httpStatus: 410 })).status).toBe(
      'unavailable',
    )
    expect(classifySourceOutcome(response({ httpStatus: 503 })).status).toBe(
      'unavailable',
    )
    expect(
      classifySourceOutcome(
        response({ wireEvidenceClass: 'MYSTERY' }),
      ).status,
    ).toBe('error')
    expect(
      classifySourceOutcome(
        response({ itemCount: 0, continuation: 'cursor-1' }),
      ).status,
    ).toBe('partial')
  })

  it('keeps continuation and coverage metadata on the outcome', () => {
    const outcome = classifySourceOutcome(
      response({
        itemCount: 0,
        continuation: 'cursor-1',
        coverage: 0.25,
        requestedTick: 3,
        resolvedTick: 4,
        publicationId: 'pub-1',
      }),
    )
    expect(outcome.continuation).toBe('cursor-1')
    expect(outcome.coverage).toBe(0.25)
    expect(outcome.requestedTick).toBe(3)
    expect(outcome.resolvedTick).toBe(4)
    expect(outcome.publicationId).toBe('pub-1')
  })
})
