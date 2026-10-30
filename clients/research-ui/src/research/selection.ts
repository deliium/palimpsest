/**
 * Canonical credential-free Research UI selection.
 *
 * One immutable selection backs URL state, panels and cross-client links. The
 * legacy deeplink parser delegates here so the wire contract has one owner.
 */

export const RESEARCH_UI_VIEWS = [
  'overview',
  'graphs',
  'agent',
  'analytics',
  'societies',
  'macro-societies',
  'organizations',
  'institutions',
  'contact',
  'traces',
  'compare',
  'matrix',
  'population',
  'cohorts',
  'lineage',
  'teaching',
  'technology',
  'culture',
  'language',
  'narratives',
  'migration',
  'economy',
  'projects',
] as const

export type ResearchUiView = (typeof RESEARCH_UI_VIEWS)[number]

export const RUN_SCOPED_VIEWS: ReadonlySet<ResearchUiView> = new Set<ResearchUiView>([
  'overview',
  'graphs',
  'agent',
  'analytics',
  'societies',
  'macro-societies',
  'organizations',
  'institutions',
  'contact',
  'traces',
  'compare',
  'population',
  'cohorts',
  'lineage',
  'teaching',
  'technology',
  'culture',
  'language',
  'narratives',
  'migration',
  'economy',
  'projects',
])

export type EvidenceClass = 'objective' | 'subjective' | 'analytical'

export const LINEAGE_FAMILIES = [
  'genealogy',
  'mentorship',
  'technology',
  'knowledge',
  'record',
  'narrative',
  'institution',
  'office_succession',
] as const

export type LineageFamily = (typeof LINEAGE_FAMILIES)[number]

export type EntitySource = 'lineage' | 'civilization'

export type CohortSelection = Readonly<{
  generationIndex: number
  entryTick: number
  cohortId: string
}>

export type AgentFocus = Readonly<{
  kind: 'agent'
  source: 'objective'
  agentId: string
}>

export type LocationFocus = Readonly<{
  kind: 'location'
  source: 'objective'
  locationId: string
}>

export type LineageFocus = Readonly<{
  kind: 'agent' | 'institution' | 'narrative' | 'technology'
  source: 'lineage'
  family: LineageFamily
  nativeKind: string
  nativeId: string
  evidenceClass: EvidenceClass
  identityOwner: string | null
  nodeKey: string | null
  publicationId: string | null
}>

export type CivilizationFocus = Readonly<{
  kind: 'institution' | 'technology'
  source: 'civilization'
  nativeKind: string
  nativeId: string
  rowId: string
  evidenceClass: EvidenceClass
  identityOwner: string | null
  publicationId: string | null
}>

export type EntityFocus = AgentFocus | LocationFocus | LineageFocus | CivilizationFocus

export type ResearchSelection = Readonly<{
  runId: string | null
  view: ResearchUiView
  tick: number | null
  eventId: string | null
  sequence: number | null
  generationIndex: number | null
  cohort: CohortSelection | null
  scopeOwnerId: string | null
  evidenceClass: EvidenceClass | null
  focus: EntityFocus | null
}>

export type SelectionParseResult =
  | { ok: true; selection: ResearchSelection; warnings: string[] }
  | { ok: false; reasonCode: string }

const SECRET_KEYS = new Set([
  'token',
  'credential',
  'credentials',
  'secret',
  'api_key',
  'apikey',
  'authorization',
  'password',
  'access_token',
])

const KNOWN_KEYS = new Set([
  'run_id',
  'view',
  'tick',
  'event_id',
  'event',
  'sequence',
  'generation_index',
  'cohort_generation_index',
  'cohort_entry_tick',
  'cohort_id',
  'agent_id',
  'agent',
  'location_id',
  'institution_id',
  'narrative_id',
  'technology_id',
  'owner_id',
  'identity_owner',
  'evidence_class',
  'entity_source',
  'native_kind',
  'lineage_family',
  'lineage_node_key',
  'lineage_publication_id',
  'civilization_row_id',
  'civilization_publication_id',
])

const OBJECTIVE_FAMILIES: ReadonlySet<LineageFamily> = new Set(['genealogy', 'record'])
const SUBJECTIVE_FAMILIES: ReadonlySet<LineageFamily> = new Set([
  'mentorship',
  'technology',
  'knowledge',
  'narrative',
  'office_succession',
])
const ANALYTICAL_FAMILIES: ReadonlySet<LineageFamily> = new Set([
  'mentorship',
  'technology',
  'knowledge',
  'narrative',
  'institution',
])
const ANALYTICAL_SHARED_KINDS = new Set(['agent', 'event'])

const FOCUS_KEYS = [
  'agent_id',
  'location_id',
  'institution_id',
  'narrative_id',
  'technology_id',
] as const

const LINEAGE_QUALIFIERS = [
  'lineage_family',
  'lineage_node_key',
  'lineage_publication_id',
] as const
const CIVILIZATION_QUALIFIERS = [
  'civilization_row_id',
  'civilization_publication_id',
] as const

const NODE_KEY_PATTERN = /^[0-9a-f]{64}$/

export const CANONICAL_SELECTION_KEYS = [
  'run_id',
  'view',
  'tick',
  'event_id',
  'sequence',
  'generation_index',
  'cohort_generation_index',
  'cohort_entry_tick',
  'cohort_id',
  'agent_id',
  'location_id',
  'institution_id',
  'narrative_id',
  'technology_id',
  'entity_source',
  'native_kind',
  'lineage_family',
  'lineage_node_key',
  'lineage_publication_id',
  'civilization_publication_id',
  'civilization_row_id',
  'owner_id',
  'identity_owner',
  'evidence_class',
] as const

function isView(value: string): value is ResearchUiView {
  return (RESEARCH_UI_VIEWS as readonly string[]).includes(value)
}

function isLineageFamily(value: string): value is LineageFamily {
  return (LINEAGE_FAMILIES as readonly string[]).includes(value)
}

function isEvidenceClass(value: string): value is EvidenceClass {
  return value === 'objective' || value === 'subjective' || value === 'analytical'
}

function optionalText(value: string | null | undefined): string | null {
  if (value === null || value === undefined) {
    return null
  }
  const trimmed = value.trim()
  return trimmed === '' ? null : trimmed
}

function stableId(value: string, field: string): string {
  if (value.length < 1 || value.length > 128) {
    throw new Error(`invalid_${field}`)
  }
  if (value !== value.trim()) {
    throw new Error(`invalid_${field}`)
  }
  for (const char of value) {
    const code = char.codePointAt(0) ?? 0
    if (code <= 0x1f || code === 0x7f) {
      throw new Error(`invalid_${field}`)
    }
  }
  return value
}

function optionalNonNegInt(raw: string | null | undefined, field: string): number | null {
  if (raw === null || raw === undefined || raw.trim() === '') {
    return null
  }
  const text = raw.trim()
  if (!/^(0|[1-9][0-9]*)$/.test(text)) {
    throw new Error(`invalid_${field}`)
  }
  const value = Number.parseInt(text, 10)
  if (!Number.isSafeInteger(value)) {
    throw new Error(`invalid_${field}`)
  }
  return value
}

function resolveAlias(
  params: URLSearchParams,
  canonical: string,
  alias: string,
): string | null {
  const canonicalRaw = optionalText(params.get(canonical))
  const aliasRaw = optionalText(params.get(alias))
  if (canonicalRaw !== null && aliasRaw !== null && canonicalRaw !== aliasRaw) {
    throw new Error('conflicting_query_alias')
  }
  return canonicalRaw ?? aliasRaw
}

function toSourceClass(
  source: EntitySource,
  evidenceClass: EvidenceClass | null,
  family: LineageFamily | null,
  nativeKind: string | null,
  ownerId: string | null,
  identityOwner: string | null,
): string | null {
  if (source === 'civilization') {
    if (family !== null) {
      throw new Error('inconsistent_focus_qualifier')
    }
    if (evidenceClass === null) {
      return 'missing_evidence_class'
    }
    if (evidenceClass === 'objective') {
      if (ownerId !== null || identityOwner !== null) {
        return 'invalid_scope_owner'
      }
      return null
    }
    if (evidenceClass === 'subjective') {
      if (ownerId === null || identityOwner === null || ownerId !== identityOwner) {
        return 'invalid_scope_owner'
      }
      return null
    }
    if (ownerId !== null) {
      return 'invalid_scope_owner'
    }
    if (identityOwner === null) {
      return 'missing_identity_owner'
    }
    return null
  }

  if (evidenceClass === null || family === null || nativeKind === null) {
    return 'missing_lineage_focus_fields'
  }
  if (evidenceClass === 'objective') {
    if (!OBJECTIVE_FAMILIES.has(family)) {
      return 'invalid_lineage_scope'
    }
    if (ownerId !== null || identityOwner !== null) {
      return 'invalid_scope_owner'
    }
    return null
  }
  if (evidenceClass === 'subjective') {
    if (!SUBJECTIVE_FAMILIES.has(family)) {
      return 'invalid_lineage_scope'
    }
    if (ownerId === null || identityOwner === null || ownerId !== identityOwner) {
      return 'invalid_scope_owner'
    }
    return null
  }
  if (!ANALYTICAL_FAMILIES.has(family)) {
    return 'invalid_lineage_scope'
  }
  if (ownerId !== null) {
    return 'invalid_scope_owner'
  }
  if (ANALYTICAL_SHARED_KINDS.has(nativeKind)) {
    if (identityOwner !== null) {
      return 'invalid_scope_owner'
    }
    return null
  }
  if (identityOwner === null) {
    return 'missing_identity_owner'
  }
  return null
}

function validateLineageKind(
  kind: 'institution' | 'narrative' | 'technology',
  family: LineageFamily,
  nativeKind: string,
): string | null {
  if (kind === 'institution') {
    if (family === 'institution' && nativeKind === 'institution_episode') {
      return null
    }
    if (
      family === 'office_succession' &&
      (nativeKind === 'office' ||
        nativeKind === 'office_claim' ||
        nativeKind === 'office_transition')
    ) {
      return null
    }
    return 'unsupported_family_kind'
  }
  if (kind === 'narrative') {
    return family === 'narrative' && nativeKind === 'narrative_variant'
      ? null
      : 'unsupported_family_kind'
  }
  if (family === 'technology' && nativeKind === 'technique') {
    return null
  }
  if (family === 'knowledge' && nativeKind === 'knowledge_entry') {
    return null
  }
  return 'unsupported_family_kind'
}

function validateCivilizationKind(
  kind: 'institution' | 'technology',
  nativeKind: string,
): string | null {
  if (kind === 'institution') {
    return nativeKind === 'concept' || nativeKind === 'office' || nativeKind === 'episode'
      ? null
      : 'unsupported_family_kind'
  }
  return nativeKind === 'technology' ? null : 'unsupported_family_kind'
}

export function parseResearchSelection(
  query: string | URLSearchParams | Record<string, string>,
): SelectionParseResult {
  let params: URLSearchParams
  if (typeof query === 'string') {
    const text = query.startsWith('?') ? query.slice(1) : query
    params = new URLSearchParams(text)
  } else if (query instanceof URLSearchParams) {
    params = query
  } else {
    params = new URLSearchParams(query)
  }

  for (const key of params.keys()) {
    if (SECRET_KEYS.has(key.toLowerCase())) {
      if (import.meta.env.DEV) {
        console.warn('research_selection_rejected reason_code=query_string_secret')
      }
      return { ok: false, reasonCode: 'query_string_secret' }
    }
  }

  for (const key of KNOWN_KEYS) {
    if (params.getAll(key).length > 1) {
      return { ok: false, reasonCode: 'duplicate_query_key' }
    }
  }

  let tick: number | null
  let sequence: number | null
  let generationIndex: number | null
  let cohortGeneration: number | null
  let cohortEntry: number | null
  try {
    tick = optionalNonNegInt(params.get('tick'), 'tick')
    sequence = optionalNonNegInt(params.get('sequence'), 'sequence')
    generationIndex = optionalNonNegInt(params.get('generation_index'), 'generation_index')
    cohortGeneration = optionalNonNegInt(
      params.get('cohort_generation_index'),
      'cohort_generation_index',
    )
    cohortEntry = optionalNonNegInt(params.get('cohort_entry_tick'), 'cohort_entry_tick')
  } catch (err) {
    return {
      ok: false,
      reasonCode: err instanceof Error ? err.message : 'invalid_query',
    }
  }

  if (tick === null && sequence !== null) {
    return { ok: false, reasonCode: 'incomplete_event_cursor' }
  }

  let eventId: string | null
  let agentId: string | null
  try {
    eventId = resolveAlias(params, 'event_id', 'event')
    agentId = resolveAlias(params, 'agent_id', 'agent')
  } catch (err) {
    return {
      ok: false,
      reasonCode: err instanceof Error ? err.message : 'invalid_query',
    }
  }

  const cohortId = optionalText(params.get('cohort_id'))
  const cohortParts = [cohortGeneration, cohortEntry, cohortId]
  const cohortPresent = cohortParts.filter((part) => part !== null).length
  if (cohortPresent !== 0 && cohortPresent !== 3) {
    return { ok: false, reasonCode: 'incomplete_cohort_selection' }
  }
  let cohort: CohortSelection | null = null
  if (cohortPresent === 3) {
    try {
      cohort = {
        generationIndex: cohortGeneration as number,
        entryTick: cohortEntry as number,
        cohortId: stableId(cohortId as string, 'cohort_id'),
      }
    } catch (err) {
      return {
        ok: false,
        reasonCode: err instanceof Error ? err.message : 'invalid_cohort_id',
      }
    }
  }

  const viewRaw = (params.get('view') ?? '').trim().toLowerCase()
  const warnings: string[] = []
  let view: ResearchUiView = 'overview'
  if (viewRaw !== '') {
    if (isView(viewRaw)) {
      view = viewRaw
    } else {
      warnings.push('unknown_view')
      if (import.meta.env.DEV) {
        console.warn('research_selection_rejected reason_code=unknown_view')
      }
    }
  }

  let runId: string | null = null
  let ownerId: string | null = null
  let identityOwner: string | null = null
  try {
    const rawRun = optionalText(params.get('run_id'))
    runId = rawRun === null ? null : stableId(rawRun, 'run_id')
    const rawOwner = optionalText(params.get('owner_id'))
    ownerId = rawOwner === null ? null : stableId(rawOwner, 'owner_id')
    const rawIdentityOwner = optionalText(params.get('identity_owner'))
    identityOwner =
      rawIdentityOwner === null ? null : stableId(rawIdentityOwner, 'identity_owner')
  } catch (err) {
    return {
      ok: false,
      reasonCode: err instanceof Error ? err.message : 'invalid_selection_id',
    }
  }

  if (RUN_SCOPED_VIEWS.has(view) && runId === null) {
    return { ok: false, reasonCode: 'run_id_missing' }
  }

  const evidenceRaw = (params.get('evidence_class') ?? '').trim().toLowerCase()
  let evidenceClass: EvidenceClass | null = null
  if (evidenceRaw !== '') {
    if (!isEvidenceClass(evidenceRaw)) {
      return { ok: false, reasonCode: 'invalid_evidence_class' }
    }
    evidenceClass = evidenceRaw
  }

  const focusValues = FOCUS_KEYS.map(
    (key) =>
      [key, key === 'agent_id' ? agentId : optionalText(params.get(key))] as const,
  )
  const present = focusValues.filter(([, value]) => value !== null)
  if (present.length > 1) {
    return { ok: false, reasonCode: 'ambiguous_entity_focus' }
  }

  const sourceRaw = (params.get('entity_source') ?? '').trim().toLowerCase()
  let entitySource: EntitySource | null = null
  if (sourceRaw !== '') {
    if (sourceRaw !== 'lineage' && sourceRaw !== 'civilization') {
      return { ok: false, reasonCode: 'invalid_entity_source' }
    }
    entitySource = sourceRaw
  }

  const lineageFamilyRaw = (params.get('lineage_family') ?? '').trim().toLowerCase()
  let lineageFamily: LineageFamily | null = null
  if (lineageFamilyRaw !== '') {
    if (!isLineageFamily(lineageFamilyRaw)) {
      return { ok: false, reasonCode: 'invalid_lineage_family' }
    }
    lineageFamily = lineageFamilyRaw
  }
  const nativeKind = optionalText(params.get('native_kind'))
  const nodeKey = optionalText(params.get('lineage_node_key'))
  const rowId = optionalText(params.get('civilization_row_id'))
  const lineagePublicationId = optionalText(params.get('lineage_publication_id'))
  const civilizationPublicationId = optionalText(params.get('civilization_publication_id'))

  if (nodeKey !== null && !NODE_KEY_PATTERN.test(nodeKey)) {
    return { ok: false, reasonCode: 'invalid_lineage_node_key' }
  }
  if (lineagePublicationId !== null && civilizationPublicationId !== null) {
    return { ok: false, reasonCode: 'ambiguous_publication_source' }
  }

  let focus: EntityFocus | null = null
  if (present.length === 0) {
    for (const key of [
      'entity_source',
      'native_kind',
      'lineage_family',
      'lineage_node_key',
      'lineage_publication_id',
      'civilization_row_id',
      'civilization_publication_id',
      'identity_owner',
    ] as const) {
      if (optionalText(params.get(key)) !== null) {
        return { ok: false, reasonCode: 'focus_qualifier_without_focus' }
      }
    }
    if (evidenceClass === 'objective' && ownerId !== null) {
      return { ok: false, reasonCode: 'invalid_scope_owner' }
    }
    if (evidenceClass === 'subjective' && ownerId === null) {
      return { ok: false, reasonCode: 'missing_scope_owner' }
    }
    if (evidenceClass === 'analytical' && ownerId !== null) {
      return { ok: false, reasonCode: 'invalid_scope_owner' }
    }
  } else {
    const firstFocus = present[0]
    if (firstFocus === undefined) {
      return { ok: false, reasonCode: 'invalid_entity_focus' }
    }
    const [focusKey, focusValue] = firstFocus
    if (focusValue === null) {
      return { ok: false, reasonCode: 'invalid_entity_focus' }
    }
    if (focusKey === 'agent_id') {
      const lineageQualified =
        entitySource !== null ||
        lineageFamily !== null ||
        nativeKind !== null ||
        nodeKey !== null ||
        lineagePublicationId !== null
      if (lineageQualified) {
        if (
          entitySource !== 'lineage' ||
          lineageFamily !== 'genealogy' ||
          nativeKind !== 'agent' ||
          evidenceClass !== 'objective' ||
          rowId !== null ||
          civilizationPublicationId !== null
        ) {
          return { ok: false, reasonCode: 'inconsistent_focus_qualifier' }
        }
        const scopeError = toSourceClass(
          'lineage',
          evidenceClass,
          lineageFamily,
          nativeKind,
          ownerId,
          identityOwner,
        )
        if (scopeError !== null) {
          return { ok: false, reasonCode: scopeError }
        }
        try {
          stableId(focusValue, 'agent_id')
          if (lineagePublicationId !== null) {
            stableId(lineagePublicationId, 'lineage_publication_id')
          }
        } catch (err) {
          return {
            ok: false,
            reasonCode: err instanceof Error ? err.message : 'invalid_agent_id',
          }
        }
        focus = {
          kind: 'agent',
          source: 'lineage',
          family: 'genealogy',
          nativeKind: 'agent',
          nativeId: focusValue,
          evidenceClass: 'objective',
          identityOwner: null,
          nodeKey,
          publicationId: lineagePublicationId,
        }
        evidenceClass = 'objective'
      } else {
        if (
          (evidenceClass !== null && evidenceClass !== 'objective') ||
          ownerId !== null ||
          identityOwner !== null ||
          rowId !== null ||
          civilizationPublicationId !== null
        ) {
          return { ok: false, reasonCode: 'inconsistent_focus_qualifier' }
        }
        try {
          focus = {
            kind: 'agent',
            source: 'objective',
            agentId: stableId(focusValue, 'agent_id'),
          }
        } catch (err) {
          return {
            ok: false,
            reasonCode: err instanceof Error ? err.message : 'invalid_agent_id',
          }
        }
        evidenceClass = 'objective'
      }
    } else if (focusKey === 'location_id') {
      if (
        (evidenceClass !== null && evidenceClass !== 'objective') ||
        ownerId !== null ||
        identityOwner !== null ||
        entitySource !== null ||
        lineageFamily !== null ||
        nativeKind !== null ||
        nodeKey !== null ||
        rowId !== null ||
        lineagePublicationId !== null ||
        civilizationPublicationId !== null
      ) {
        return { ok: false, reasonCode: 'inconsistent_focus_qualifier' }
      }
      try {
        focus = {
          kind: 'location',
          source: 'objective',
          locationId: stableId(focusValue, 'location_id'),
        }
      } catch (err) {
        return {
          ok: false,
          reasonCode: err instanceof Error ? err.message : 'invalid_location_id',
        }
      }
      evidenceClass = 'objective'
    } else {
      const kind =
        focusKey === 'institution_id'
          ? 'institution'
          : focusKey === 'narrative_id'
            ? 'narrative'
            : 'technology'
      if (entitySource === 'civilization' && kind === 'narrative') {
        return { ok: false, reasonCode: 'unsupported_family_kind' }
      }
      const civilizationKind = kind as 'institution' | 'technology'
      if (entitySource === null) {
        return { ok: false, reasonCode: 'missing_entity_source' }
      }
      let nativeId: string
      try {
        nativeId = stableId(focusValue, focusKey)
      } catch (err) {
        return {
          ok: false,
          reasonCode: err instanceof Error ? err.message : 'invalid_entity_id',
        }
      }
      if (entitySource === 'lineage') {
        for (const key of CIVILIZATION_QUALIFIERS) {
          if (optionalText(params.get(key)) !== null) {
            return { ok: false, reasonCode: 'inconsistent_focus_qualifier' }
          }
        }
        if (lineagePublicationId !== null) {
          try {
            stableId(lineagePublicationId, 'lineage_publication_id')
          } catch (err) {
            return {
              ok: false,
              reasonCode:
                err instanceof Error ? err.message : 'invalid_lineage_publication_id',
            }
          }
        }
        if (nativeKind === null) {
          return { ok: false, reasonCode: 'missing_lineage_focus_fields' }
        }
        if (lineageFamily === null || evidenceClass === null) {
          return { ok: false, reasonCode: 'missing_lineage_focus_fields' }
        }
        const kindError = validateLineageKind(kind, lineageFamily, nativeKind)
        if (kindError !== null) {
          return { ok: false, reasonCode: kindError }
        }
        const scopeError = toSourceClass(
          'lineage',
          evidenceClass,
          lineageFamily,
          nativeKind,
          ownerId,
          identityOwner,
        )
        if (scopeError !== null) {
          return { ok: false, reasonCode: scopeError }
        }
        focus = {
          kind,
          source: 'lineage',
          family: lineageFamily,
          nativeKind,
          nativeId,
          evidenceClass,
          identityOwner,
          nodeKey,
          publicationId: lineagePublicationId,
        }
      } else {
        for (const key of LINEAGE_QUALIFIERS) {
          if (optionalText(params.get(key)) !== null) {
            return { ok: false, reasonCode: 'inconsistent_focus_qualifier' }
          }
        }
        if (rowId === null || nativeKind === null) {
          return { ok: false, reasonCode: 'missing_civilization_focus_fields' }
        }
        const kindError = validateCivilizationKind(civilizationKind, nativeKind)
        if (kindError !== null) {
          return { ok: false, reasonCode: kindError }
        }
        const scopeError = toSourceClass(
          'civilization',
          evidenceClass,
          null,
          nativeKind,
          ownerId,
          identityOwner,
        )
        if (scopeError !== null) {
          return { ok: false, reasonCode: scopeError }
        }
        if (civilizationPublicationId !== null) {
          try {
            stableId(civilizationPublicationId, 'civilization_publication_id')
          } catch (err) {
            return {
              ok: false,
              reasonCode:
                err instanceof Error ? err.message : 'invalid_civilization_publication_id',
            }
          }
        }
        let stableRow: string
        try {
          stableRow = stableId(rowId, 'civilization_row_id')
        } catch (err) {
          return {
            ok: false,
            reasonCode: err instanceof Error ? err.message : 'invalid_civilization_row_id',
          }
        }
        focus = {
          kind: civilizationKind,
          source: 'civilization',
          nativeKind,
          nativeId,
          rowId: stableRow,
          evidenceClass: evidenceClass as EvidenceClass,
          identityOwner,
          publicationId: civilizationPublicationId,
        }
      }
    }
  }

  const selection: ResearchSelection = {
    runId,
    view,
    tick,
    eventId,
    sequence,
    generationIndex,
    cohort,
    scopeOwnerId: ownerId,
    evidenceClass,
    focus,
  }

  if (import.meta.env.DEV) {
    console.debug(
      `research_selection_parsed run_id=${selection.runId ?? ''} view=${selection.view} focus=${
        selection.focus?.kind ?? 'none'
      }`,
    )
  }

  return { ok: true, selection, warnings }
}

/**
 * Resolve a legacy ID-only cohort reference against already-loaded rows.
 *
 * Returns `ambiguous` when two rows reuse the ID; callers must never take the
 * first match. Selecting a cohort never mutates generation navigation state.
 */
export function resolveCohortCandidate(
  cohortId: string,
  rows: readonly CohortSelection[],
): CohortSelection | 'ambiguous' | null {
  const matches = rows.filter((row) => row.cohortId === cohortId)
  if (matches.length === 0) {
    return null
  }
  if (matches.length > 1) {
    return 'ambiguous'
  }
  return matches[0] ?? null
}

export function buildResearchSelectionQuery(selection: ResearchSelection): string {
  const params = new URLSearchParams()
  if (selection.runId !== null && selection.runId !== '') {
    params.set('run_id', selection.runId)
  }
  if (selection.view !== 'overview') {
    params.set('view', selection.view)
  }
  if (selection.tick !== null) {
    params.set('tick', String(selection.tick))
  }
  if (selection.eventId !== null && selection.eventId !== '') {
    params.set('event_id', selection.eventId)
  }
  if (selection.sequence !== null) {
    params.set('sequence', String(selection.sequence))
  }
  if (selection.generationIndex !== null) {
    params.set('generation_index', String(selection.generationIndex))
  }
  if (selection.cohort !== null) {
    params.set('cohort_generation_index', String(selection.cohort.generationIndex))
    params.set('cohort_entry_tick', String(selection.cohort.entryTick))
    params.set('cohort_id', selection.cohort.cohortId)
  }

  const focus = selection.focus
  if (focus?.kind === 'agent' && focus.source === 'objective') {
    params.set('agent_id', focus.agentId)
  } else if (focus?.kind === 'location') {
    params.set('location_id', focus.locationId)
  } else if (focus !== null && focus !== undefined) {
    const idKey =
      focus.kind === 'agent'
        ? 'agent_id'
        : focus.kind === 'institution'
          ? 'institution_id'
          : focus.kind === 'narrative'
            ? 'narrative_id'
            : 'technology_id'
    params.set(idKey, focus.nativeId)
    params.set('entity_source', focus.source)
    params.set('native_kind', focus.nativeKind)
    if (focus.source === 'lineage') {
      params.set('lineage_family', focus.family)
      if (focus.nodeKey !== null) {
        params.set('lineage_node_key', focus.nodeKey)
      }
      if (focus.publicationId !== null) {
        params.set('lineage_publication_id', focus.publicationId)
      }
    } else if (focus.publicationId !== null) {
      params.set('civilization_publication_id', focus.publicationId)
    }
    if (focus.source === 'civilization') {
      params.set('civilization_row_id', focus.rowId)
    }
  }

  if (selection.scopeOwnerId !== null) {
    params.set('owner_id', selection.scopeOwnerId)
  }
  if (focus !== null && focus !== undefined && 'identityOwner' in focus) {
    if (focus.identityOwner !== null) {
      params.set('identity_owner', focus.identityOwner)
    }
  }
  if (selection.evidenceClass !== null) {
    params.set('evidence_class', selection.evidenceClass)
  }
  const text = params.toString()
  return text === '' ? '' : `?${text}`
}

export function buildResearchSelectionPath(selection: ResearchSelection): string {
  const view = selection.view === 'overview' ? '' : `/${selection.view}`
  const run =
    selection.runId === null ? '' : `/runs/${encodeURIComponent(selection.runId)}${view}`
  return `/research${run}${buildResearchSelectionQuery(selection)}`
}

export function emptyResearchSelection(
  overrides: Partial<ResearchSelection> = {},
): ResearchSelection {
  return {
    runId: null,
    view: 'overview',
    tick: null,
    eventId: null,
    sequence: null,
    generationIndex: null,
    cohort: null,
    scopeOwnerId: null,
    evidenceClass: null,
    focus: null,
    ...overrides,
  }
}

export function godotFocusOptions(
  selection: ResearchSelection,
): Record<string, string | number | null | undefined> {
  const focus = selection.focus
  const options: Record<string, string | number | null | undefined> = {}
  if (focus === null) {
    return options
  }
  if (focus.kind === 'agent' || focus.kind === 'location') {
    return options
  }
  options.entity_source = focus.source
  options.native_kind = focus.nativeKind
  options.evidence_class = focus.evidenceClass
  options.identity_owner = focus.identityOwner ?? undefined
  if (focus.source === 'lineage') {
    options.lineage_family = focus.family
    options.lineage_node_key = focus.nodeKey ?? undefined
    options.lineage_publication_id = focus.publicationId ?? undefined
  } else {
    options.civilization_row_id = focus.rowId
    options.civilization_publication_id = focus.publicationId ?? undefined
  }
  if (focus.kind === 'institution') {
    options.institution_id = focus.nativeId
  } else if (focus.kind === 'narrative') {
    options.narrative_id = focus.nativeId
  } else if (focus.kind === 'technology') {
    options.technology_id = focus.nativeId
  }
  if (selection.scopeOwnerId !== null) {
    options.owner_id = selection.scopeOwnerId
  }
  if (selection.cohort !== null) {
    options.cohort_generation_index = selection.cohort.generationIndex
    options.cohort_entry_tick = selection.cohort.entryTick
    options.cohort_id = selection.cohort.cohortId
  }
  if (selection.generationIndex !== null) {
    options.generation_index = selection.generationIndex
  }
  return options
}
