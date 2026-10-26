import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import {
  buildResearchSelectionQuery,
  godotFocusOptions,
  parseResearchSelection,
  resolveCohortCandidate,
  type ResearchSelection,
} from './selection'

type FixtureFocus = {
  kind: string
  source: string
  native_id: string
  family: string | null
  native_kind: string | null
  identity_owner: string | null
  node_key: string | null
  row_id: string | null
  publication_id: string | null
}

type FixtureState = {
  run_id: string | null
  view: string
  tick: number | null
  event_id: string | null
  sequence: number | null
  generation_index: number | null
  cohort: {
    cohort_generation_index: number
    cohort_entry_tick: number
    cohort_id: string
  } | null
  owner_id: string | null
  evidence_class: string | null
  focus: FixtureFocus | null
}

type Fixture = {
  valid: { name: string; query: string; state: FixtureState; canonical_query: string }[]
  invalid: { name: string; query: string; reason_code: string }[]
}

const corpus = JSON.parse(
  readFileSync(resolve(process.cwd(), 'fixtures/research-links.json'), 'utf8'),
) as Fixture

function normalize(selection: ResearchSelection): FixtureState {
  const focus = selection.focus
  let fixtureFocus: FixtureFocus | null = null
  if (focus?.kind === 'agent') {
    fixtureFocus =
      focus.source === 'objective'
        ? {
            kind: 'agent',
            source: 'objective',
            native_id: focus.agentId,
            family: null,
            native_kind: null,
            identity_owner: null,
            node_key: null,
            row_id: null,
            publication_id: null,
          }
        : {
            kind: 'agent',
            source: 'lineage',
            native_id: focus.nativeId,
            family: focus.family,
            native_kind: focus.nativeKind,
            identity_owner: focus.identityOwner,
            node_key: focus.nodeKey,
            row_id: null,
            publication_id: focus.publicationId,
          }
  } else if (focus?.kind === 'location') {
    fixtureFocus = {
      kind: 'location',
      source: 'objective',
      native_id: focus.locationId,
      family: null,
      native_kind: null,
      identity_owner: null,
      node_key: null,
      row_id: null,
      publication_id: null,
    }
  } else if (focus !== null && focus !== undefined) {
    fixtureFocus = {
      kind: focus.kind,
      source: focus.source,
      native_id: focus.nativeId,
      family: focus.source === 'lineage' ? focus.family : null,
      native_kind: focus.nativeKind,
      identity_owner: focus.identityOwner,
      node_key: focus.source === 'lineage' ? focus.nodeKey : null,
      row_id: focus.source === 'civilization' ? focus.rowId : null,
      publication_id: focus.publicationId,
    }
  }
  return {
    run_id: selection.runId,
    view: selection.view,
    tick: selection.tick,
    event_id: selection.eventId,
    sequence: selection.sequence,
    generation_index: selection.generationIndex,
    cohort:
      selection.cohort === null
        ? null
        : {
            cohort_generation_index: selection.cohort.generationIndex,
            cohort_entry_tick: selection.cohort.entryTick,
            cohort_id: selection.cohort.cohortId,
          },
    owner_id: selection.scopeOwnerId,
    evidence_class: selection.evidenceClass,
    focus: fixtureFocus,
  }
}

describe('canonical research selection corpus', () => {
  for (const entry of corpus.valid) {
    it(`round-trips ${entry.name}`, () => {
      const result = parseResearchSelection(entry.query)
      expect(result.ok).toBe(true)
      if (!result.ok) {
        return
      }
      expect(normalize(result.selection)).toEqual(entry.state)
      expect(buildResearchSelectionQuery(result.selection)).toBe(entry.canonical_query)
      const again = parseResearchSelection(entry.canonical_query)
      expect(again.ok).toBe(true)
      if (again.ok) {
        expect(normalize(again.selection)).toEqual(entry.state)
      }
    })
  }

  for (const entry of corpus.invalid) {
    it(`rejects ${entry.name}`, () => {
      const result = parseResearchSelection(entry.query)
      expect(result.ok).toBe(false)
      if (!result.ok) {
        expect(result.reasonCode).toBe(entry.reason_code)
      }
    })
  }
})

describe('cohort selection', () => {
  it('never takes the first match for a reused cohort id', () => {
    const rows = [
      { generationIndex: 2, entryTick: 10, cohortId: 'cohort-a' },
      { generationIndex: 3, entryTick: 50, cohortId: 'cohort-a' },
    ]
    expect(resolveCohortCandidate('cohort-a', rows)).toBe('ambiguous')
    expect(resolveCohortCandidate('missing', rows)).toBeNull()
    const only = rows[0]
    expect(only).toBeDefined()
    if (only !== undefined) {
      expect(resolveCohortCandidate('cohort-a', [only])).toEqual(only)
    }
  })

  it('keeps generation navigation independent from cohort identity', () => {
    const first = parseResearchSelection(
      '?run_id=run-1&view=cohorts&generation_index=2&cohort_generation_index=3&cohort_entry_tick=50&cohort_id=cohort-a',
    )
    expect(first.ok).toBe(true)
    if (first.ok) {
      expect(first.selection.generationIndex).toBe(2)
      expect(first.selection.cohort?.generationIndex).toBe(3)
    }
  })
})

describe('godot focus options', () => {
  it('keeps subject concepts in civilization and analytical episodes owner-qualified', () => {
    const concept = parseResearchSelection(
      '?run_id=run-1&institution_id=concept-1&entity_source=civilization&native_kind=concept&civilization_row_id=row-1&owner_id=agent-a&identity_owner=agent-a&evidence_class=subjective',
    )
    expect(concept.ok).toBe(true)
    if (concept.ok) {
      const options = godotFocusOptions(concept.selection)
      expect(options.entity_source).toBe('civilization')
      expect(options.civilization_row_id).toBe('row-1')
      expect(options.lineage_publication_id).toBeUndefined()
      expect(options.owner_id).toBe('agent-a')
    }
    const episode = parseResearchSelection(
      '?run_id=run-1&institution_id=episode-1&entity_source=lineage&native_kind=institution_episode&lineage_family=institution&identity_owner=agent-b&evidence_class=analytical',
    )
    expect(episode.ok).toBe(true)
    if (episode.ok) {
      const options = godotFocusOptions(episode.selection)
      expect(options.owner_id).toBeUndefined()
      expect(options.identity_owner).toBe('agent-b')
    }
  })
})

describe('selection hardening', () => {
  it('warns on unknown view but keeps a safe fallback', () => {
    const result = parseResearchSelection('?run_id=run-1&view=nope')
    expect(result.ok).toBe(true)
    if (result.ok) {
      expect(result.selection.view).toBe('overview')
      expect(result.warnings).toContain('unknown_view')
    }
  })

  it('rejects credentials without echoing them', () => {
    const result = parseResearchSelection('?run_id=run-1&access_token=abc')
    expect(result).toEqual({ ok: false, reasonCode: 'query_string_secret' })
  })
})
