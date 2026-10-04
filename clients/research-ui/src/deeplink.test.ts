import { describe, expect, it } from 'vitest'
import { buildResearchUiQuery, parseResearchUiQuery } from './deeplink'

describe('research ui deeplink', () => {
  it('rejects credential-like query keys', () => {
    const result = parseResearchUiQuery('run_id=run-1&token=secret')
    expect(result.ok).toBe(false)
    if (!result.ok) {
      expect(result.reasonCode).toBe('query_string_secret')
    }
  })

  it('requires run_id for run-scoped views', () => {
    const result = parseResearchUiQuery('view=graphs')
    expect(result.ok).toBe(false)
    if (!result.ok) {
      expect(result.reasonCode).toBe('run_id_missing')
    }
  })

  it('defaults unknown view to overview with warning', () => {
    const result = parseResearchUiQuery('run_id=run-1&view=nope')
    expect(result.ok).toBe(true)
    if (result.ok) {
      expect(result.state.view).toBe('overview')
      expect(result.warnings).toContain('unknown_view')
    }
  })

  it('allows matrix without run_id', () => {
    const result = parseResearchUiQuery('view=matrix')
    expect(result.ok).toBe(true)
    if (result.ok) {
      expect(result.state.view).toBe('matrix')
      expect(result.state.runId).toBeNull()
    }
  })

  it('builds credential-free query strings', () => {
    const q = buildResearchUiQuery({
      runId: 'run-1',
      tick: 12,
      eventId: 'evt-1',
      sequence: 3,
      agentId: 'alice',
      view: 'traces',
    })
    expect(q).toContain('run_id=run-1')
    expect(q).toContain('view=traces')
    expect(q).not.toContain('token')
  })
})
