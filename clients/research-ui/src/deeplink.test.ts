import { describe, expect, it } from 'vitest'
import {
  buildGodotObserverUrl,
  buildResearchUiQuery,
  parseResearchUiQuery,
} from './deeplink'

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


describe('godot focus links', () => {
  it('preserves source-specific publication and qualified focus fields', () => {
    const url = buildGodotObserverUrl({
      runId: 'run-1',
      tick: 4,
      eventId: null,
      sequence: null,
      agentId: null,
      debugger: false,
      options: {
        institution_id: 'concept-1',
        entity_source: 'civilization',
        native_kind: 'concept',
        evidence_class: 'subjective',
        identity_owner: 'agent-a',
        owner_id: 'agent-a',
        civilization_row_id: 'row-1',
        civilization_publication_id: 'pub-1',
        lineage_publication_id: undefined,
        cohort_generation_index: 2,
        cohort_entry_tick: 10,
        cohort_id: 'cohort-a',
      },
    })
    expect(url).toContain('institution_id=concept-1')
    expect(url).toContain('civilization_publication_id=pub-1')
    expect(url).not.toContain('lineage_publication_id')
    expect(url).toContain('cohort_entry_tick=10')
    expect(url).not.toContain('token=')
    expect(url).not.toContain('secret')
  })
})
