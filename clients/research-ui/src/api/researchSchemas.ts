/** Handwritten runtime guards for the research read contracts we consume. */

export class ResearchSchemaError extends Error {
  readonly code: string

  constructor(code = 'invalid_research_response') {
    super(code)
    this.name = 'ResearchSchemaError'
    this.code = code
  }
}

function fail(code = 'invalid_research_response'): never {
  throw new ResearchSchemaError(code)
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}

export function requireRecord(value: unknown): Record<string, unknown> {
  return isRecord(value) ? value : fail()
}

export function requireString(
  value: unknown,
  { allowEmpty = false }: { allowEmpty?: boolean } = {},
): string {
  if (typeof value !== 'string' || (!allowEmpty && value.length === 0)) {
    fail()
  }
  return value
}

export function requireOptionalString(value: unknown): string | null {
  if (value === null || value === undefined) {
    return null
  }
  return requireString(value)
}

export function requireNonNegInt(value: unknown): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 0) {
    fail()
  }
  return value
}

export function requireFinite(value: unknown): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    fail()
  }
  return value
}

export function requireArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : fail()
}

export function requireBoolean(value: unknown): boolean {
  if (typeof value !== 'boolean') {
    fail()
  }
  return value
}

export function requireSchema(
  value: unknown,
  expected: string,
): Record<string, unknown> {
  const body = requireRecord(value)
  if (body.schema_version !== expected) {
    fail('unsupported_research_schema')
  }
  return body
}

export function requireOneOf<T extends string>(
  value: unknown,
  allowed: readonly T[],
): T {
  if (typeof value !== 'string' || !allowed.includes(value as T)) {
    fail()
  }
  return value as T
}

export type DemographicsEnvelope = {
  schema_version: 'observer-demographics-v1'
  run_id: string
  requested_tick: number
  requested_through_sequence: number | null
  resolved_tick: number
  revision: number
  evidence_class: 'objective'
  availability: 'available' | 'unavailable'
  reason_code: string | null
  section: 'agents' | 'cohorts' | 'generations'
  selection_state: string
  population: {
    living: number
    admitted: number
    dead: number
    max_generation_index: number
  } | null
  stage_counts_truncated: boolean
  stage_rows: Array<{
    stage: string
    life_status: 'alive' | 'dead'
    count: number
  }>
  agents: Array<{
    agent_id: string
    entity_id: string
    entry_tick: number
    generation_index: number
    cohort_id: string
    stage: string
    dependency_status: 'dependent' | 'independent'
    life_status: 'alive' | 'dead'
    age_ticks: number | null
  }>
  cohorts: Array<{
    generation_index: number
    entry_tick: number
    cohort_id: string
    admitted: number
    living: number
    dead: number
  }>
  generations: Array<{
    generation_index: number
    admitted: number
    living: number
    dead: number
  }>
  next_after_agent_id: string | null
  next_after_group_key: string | null
  limit: number
}

export function ensureDemographics(value: unknown): DemographicsEnvelope {
  const body = requireSchema(value, 'observer-demographics-v1')
  const population = body.population
  return {
    ...body,
    schema_version: 'observer-demographics-v1',
    run_id: requireString(body.run_id),
    requested_tick: requireNonNegInt(body.requested_tick),
    requested_through_sequence:
      body.requested_through_sequence === null
        ? null
        : requireNonNegInt(body.requested_through_sequence),
    resolved_tick: requireNonNegInt(body.resolved_tick),
    revision: requireNonNegInt(body.revision),
    evidence_class: 'objective',
    availability: requireOneOf(body.availability, [
      'available',
      'unavailable',
    ] as const),
    reason_code: requireOptionalString(body.reason_code),
    section: requireOneOf(body.section, [
      'agents',
      'cohorts',
      'generations',
    ] as const),
    selection_state: requireString(body.selection_state),
    population:
      population === null
        ? null
        : {
            living: requireNonNegInt(requireRecord(population).living),
            admitted: requireNonNegInt(requireRecord(population).admitted),
            dead: requireNonNegInt(requireRecord(population).dead),
            max_generation_index: requireNonNegInt(
              requireRecord(population).max_generation_index,
            ),
          },
    stage_counts_truncated: requireBoolean(body.stage_counts_truncated),
    stage_rows: requireArray(body.stage_rows).map((row) => {
      const item = requireRecord(row)
      return {
        stage: requireString(item.stage),
        life_status: requireOneOf(item.life_status, ['alive', 'dead'] as const),
        count: requireNonNegInt(item.count),
      }
    }),
    agents: requireArray(body.agents).map((row) => {
      const item = requireRecord(row)
      return {
        agent_id: requireString(item.agent_id),
        entity_id: requireString(item.entity_id),
        entry_tick: requireNonNegInt(item.entry_tick),
        generation_index: requireNonNegInt(item.generation_index),
        cohort_id: requireString(item.cohort_id),
        stage: requireString(item.stage),
        dependency_status: requireOneOf(item.dependency_status, [
          'dependent',
          'independent',
        ] as const),
        life_status: requireOneOf(item.life_status, ['alive', 'dead'] as const),
        age_ticks:
          item.age_ticks === null ? null : requireNonNegInt(item.age_ticks),
      }
    }),
    cohorts: requireArray(body.cohorts).map((row) => {
      const item = requireRecord(row)
      return {
        generation_index: requireNonNegInt(item.generation_index),
        entry_tick: requireNonNegInt(item.entry_tick),
        cohort_id: requireString(item.cohort_id),
        admitted: requireNonNegInt(item.admitted),
        living: requireNonNegInt(item.living),
        dead: requireNonNegInt(item.dead),
      }
    }),
    generations: requireArray(body.generations).map((row) => {
      const item = requireRecord(row)
      return {
        generation_index: requireNonNegInt(item.generation_index),
        admitted: requireNonNegInt(item.admitted),
        living: requireNonNegInt(item.living),
        dead: requireNonNegInt(item.dead),
      }
    }),
    next_after_agent_id: requireOptionalString(body.next_after_agent_id),
    next_after_group_key: requireOptionalString(body.next_after_group_key),
    limit: requireNonNegInt(body.limit),
  } as DemographicsEnvelope
}

export type GenerationMarkersEnvelope = {
  schema_version: 'observer-generation-markers-v1'
  run_id: string
  requested_tick: number
  resolved_tick: number
  revision: number
  evidence_class: 'objective'
  availability: 'available' | 'unavailable'
  reason_code: string | null
  markers: Array<{
    generation_index: number
    first_entry_tick: number
    seek_tick: number
    admitted_count: number
    label_code: 'founders' | 'generation_first_admission'
  }>
  next_after_generation_index: number | null
  limit: number
}

export function ensureGenerationMarkers(
  value: unknown,
): GenerationMarkersEnvelope {
  const body = requireSchema(value, 'observer-generation-markers-v1')
  return {
    ...body,
    schema_version: 'observer-generation-markers-v1',
    run_id: requireString(body.run_id),
    requested_tick: requireNonNegInt(body.requested_tick),
    resolved_tick: requireNonNegInt(body.resolved_tick),
    revision: requireNonNegInt(body.revision),
    evidence_class: 'objective',
    availability: requireOneOf(body.availability, [
      'available',
      'unavailable',
    ] as const),
    reason_code: requireOptionalString(body.reason_code),
    markers: requireArray(body.markers).map((row) => {
      const item = requireRecord(row)
      return {
        generation_index: requireNonNegInt(item.generation_index),
        first_entry_tick: requireNonNegInt(item.first_entry_tick),
        seek_tick: requireNonNegInt(item.seek_tick),
        admitted_count: requireNonNegInt(item.admitted_count),
        label_code: requireOneOf(item.label_code, [
          'founders',
          'generation_first_admission',
        ] as const),
      }
    }),
    next_after_generation_index:
      body.next_after_generation_index === null
        ? null
        : requireNonNegInt(body.next_after_generation_index),
    limit: requireNonNegInt(body.limit),
  } as GenerationMarkersEnvelope
}

export type LineageFamilyDescriptor = {
  family: string
  available_classes: string[]
  owner_required: boolean
  directions: string[]
  max_depth: number
  max_nodes: number
  max_edges: number
  max_page_size: number
}

export function ensureLineageFamilies(value: unknown): LineageFamilyDescriptor[] {
  return requireArray(value).map((row) => {
    const item = requireRecord(row)
    return {
      family: requireString(item.family),
      available_classes: requireArray(item.available_classes).map((entry) =>
        requireString(entry),
      ),
      owner_required: requireBoolean(item.owner_required),
      directions: requireArray(item.directions).map((entry) =>
        requireString(entry),
      ),
      max_depth: requireNonNegInt(item.max_depth),
      max_nodes: requireNonNegInt(item.max_nodes),
      max_edges: requireNonNegInt(item.max_edges),
      max_page_size: requireNonNegInt(item.max_page_size),
    }
  })
}

export type LineageSnapshot = {
  publication_id: string
  digest: string
  boundary_tick: number
  schema_version: string
}

export type LineageNodeRef = {
  run_id: string
  family: string
  evidence_class: string
  native_kind: string
  native_id: string
  identity_owner: string | null
  key: string
}

export type LineageNode = {
  ref: LineageNodeRef
  state: string
  living: boolean | null
  observed_tick: number | null
  evidence_refs: Array<Record<string, unknown>>
  counts: Record<string, number>
}

function ensureLineageRef(value: unknown): LineageNodeRef {
  const item = requireRecord(value)
  return {
    run_id: requireString(item.run_id),
    family: requireString(item.family),
    evidence_class: requireString(item.evidence_class),
    native_kind: requireString(item.native_kind),
    native_id: requireString(item.native_id),
    identity_owner: requireOptionalString(item.identity_owner),
    key: requireString(item.key),
  }
}

function ensureLineageSnapshot(value: unknown): LineageSnapshot {
  const item = requireRecord(value)
  return {
    publication_id: requireString(item.publication_id),
    digest: requireString(item.digest),
    boundary_tick: requireNonNegInt(item.boundary_tick),
    schema_version: requireString(item.schema_version),
  }
}

function ensureLineageNode(value: unknown): LineageNode {
  const item = requireRecord(value)
  return {
    ref: ensureLineageRef(item.ref),
    state: requireString(item.state),
    living: item.living === null ? null : requireBoolean(item.living),
    observed_tick:
      item.observed_tick === null ? null : requireNonNegInt(item.observed_tick),
    evidence_refs:
      item.evidence_refs === undefined
        ? []
        : requireArray(item.evidence_refs).map((entry) => requireRecord(entry)),
    counts: isRecord(item.counts)
      ? Object.fromEntries(
          Object.entries(item.counts).map(([key, count]) => [
            key,
            requireNonNegInt(count),
          ]),
        )
      : {},
  }
}

export type LineageSnapshotPage = {
  schema_version: string
  items: LineageSnapshot[]
  declared_count: number
  next_cursor: string | null
  coverage: Record<string, unknown> | null
}

export function ensureLineageSnapshots(value: unknown): LineageSnapshotPage {
  const body = requireRecord(value)
  requireOneOf(body.schema_version, [
    'lineage-snapshot-list-v1',
  ] as const)
  return {
    schema_version: 'lineage-snapshot-list-v1',
    items: requireArray(body.items).map(ensureLineageSnapshot),
    declared_count: requireNonNegInt(body.declared_count),
    next_cursor: requireOptionalString(body.next_cursor),
    coverage: isRecord(body.coverage) ? body.coverage : null,
  }
}

export type LineageNodePage = {
  schema_version: string
  snapshot: LineageSnapshot
  items: LineageNode[]
  matched_node_keys: string[]
  context_only_node_keys: string[]
  declared_count: number
  next_cursor: string | null
  coverage: Record<string, unknown> | null
  requested_boundary_tick: number | null
  captured_boundary_tick: number
  effective_page_size: number
}

export function ensureLineageNodes(value: unknown): LineageNodePage {
  const body = requireRecord(value)
  requireOneOf(body.schema_version, ['lineage-node-list-v1'] as const)
  return {
    schema_version: 'lineage-node-list-v1',
    snapshot: ensureLineageSnapshot(body.snapshot),
    items: requireArray(body.items).map(ensureLineageNode),
    matched_node_keys: requireArray(body.matched_node_keys).map((entry) =>
      requireString(entry),
    ),
    context_only_node_keys: requireArray(body.context_only_node_keys).map(
      (entry) => requireString(entry),
    ),
    declared_count: requireNonNegInt(body.declared_count),
    next_cursor: requireOptionalString(body.next_cursor),
    coverage: isRecord(body.coverage) ? body.coverage : null,
    requested_boundary_tick:
      body.requested_boundary_tick === null
        ? null
        : requireNonNegInt(body.requested_boundary_tick),
    captured_boundary_tick: requireNonNegInt(body.captured_boundary_tick),
    effective_page_size: requireNonNegInt(body.effective_page_size),
  }
}

export type LineageEdge = {
  edge_key: string
  source_key: string
  target_key: string
  relation: string
  native_kind: string
  native_id: string
  claim_owner_id: string | null
  observed_tick: number | null
  status_code: string | null
  confidence_code: string | null
  confidence_value: number | null
  source_presence: string
  evidence_refs: Array<Record<string, unknown>>
}

export type LineageGraph = {
  schema_version: string
  root: LineageNodeRef
  snapshot: LineageSnapshot
  nodes: LineageNode[]
  edges: LineageEdge[]
  matched_node_keys: string[]
  context_only_node_keys: string[]
  stop_reasons: string[]
  coverage: Record<string, unknown>
  next_cursor: string | null
  captured_boundary_tick: number
  effective_max_depth: number
  effective_max_nodes: number
  effective_max_edges: number
  effective_page_size: number
}

export function ensureLineageGraph(value: unknown): LineageGraph {
  const body = requireRecord(value)
  requireOneOf(body.schema_version, ['lineage-graph-page-v1'] as const)
  return {
    schema_version: 'lineage-graph-page-v1',
    root: ensureLineageRef(body.root),
    snapshot: ensureLineageSnapshot(body.snapshot),
    nodes: requireArray(body.nodes).map(ensureLineageNode),
    edges: requireArray(body.edges).map((row) => {
      const item = requireRecord(row)
      return {
        edge_key: requireString(item.edge_key),
        source_key: requireString(item.source_key),
        target_key: requireString(item.target_key),
        relation: requireString(item.relation),
        native_kind: requireString(item.native_kind),
        native_id: requireString(item.native_id),
        claim_owner_id: requireOptionalString(item.claim_owner_id),
        observed_tick:
          item.observed_tick === undefined || item.observed_tick === null
            ? null
            : requireNonNegInt(item.observed_tick),
        status_code: requireOptionalString(item.status_code),
        confidence_code: requireOptionalString(item.confidence_code),
        confidence_value:
          item.confidence_value === undefined || item.confidence_value === null
            ? null
            : requireFinite(item.confidence_value),
        source_presence:
          item.source_presence === undefined
            ? 'unknown'
            : requireString(item.source_presence),
        evidence_refs:
          item.evidence_refs === undefined
            ? []
            : requireArray(item.evidence_refs).map((entry) => requireRecord(entry)),
      }
    }),
    matched_node_keys: requireArray(body.matched_node_keys).map((entry) =>
      requireString(entry),
    ),
    context_only_node_keys: requireArray(body.context_only_node_keys).map(
      (entry) => requireString(entry),
    ),
    stop_reasons: requireArray(body.stop_reasons).map((entry) =>
      requireString(entry),
    ),
    coverage: requireRecord(body.coverage),
    next_cursor: requireOptionalString(body.next_cursor),
    captured_boundary_tick: requireNonNegInt(body.captured_boundary_tick),
    effective_max_depth: requireNonNegInt(body.effective_max_depth),
    effective_max_nodes: requireNonNegInt(body.effective_max_nodes),
    effective_max_edges: requireNonNegInt(body.effective_max_edges),
    effective_page_size: requireNonNegInt(body.effective_page_size),
  }
}

export type CivilizationEnvelope = {
  schema_version: string
  run_id: string
  availability?: string
  reason?: string | null
  rows?: Array<Record<string, unknown>>
  boundaries?: Array<Record<string, unknown>>
  markers?: Array<Record<string, unknown>>
  publication?: Record<string, unknown> | null
  coverage?: Record<string, unknown>
  next_cursor?: string | null
  truncated?: boolean
}

export function ensureCivilization(
  value: unknown,
  schema:
    | 'observer-civilization-map-v1'
    | 'observer-civilization-catalogue-v1'
    | 'observer-civilization-overlay-v1'
    | 'observer-civilization-markers-v1',
): CivilizationEnvelope {
  const body = requireSchema(value, schema)
  const withRunId = {
    ...body,
    schema_version: schema,
    run_id: requireString(body.run_id),
  } as CivilizationEnvelope
  for (const key of ['rows', 'boundaries', 'markers'] as const) {
    if (body[key] !== undefined) {
      withRunId[key] = requireArray(body[key]).map(requireRecord)
    }
  }
  if (body.next_cursor !== undefined) {
    withRunId.next_cursor = requireOptionalString(body.next_cursor)
  }
  if (body.availability !== undefined) {
    withRunId.availability = requireOneOf(body.availability, [
      'available',
      'unavailable',
    ] as const)
  }
  return withRunId
}

export type CulturalArtifactMeta = {
  binding: 'runtime_bound' | 'legacy_unverified'
}

export function ensureCulturalArtifactBinding(
  header: string | null,
): CulturalArtifactMeta {
  if (header !== 'runtime_bound' && header !== 'legacy_unverified') {
    fail('invalid_research_response')
  }
  return { binding: header }
}

export function ensureCulturalComparison(value: unknown): Record<string, unknown> {
  const body = requireSchema(value, 'cultural-metric-comparison-v1')
  requireString(body.matrix_fingerprint)
  requireFinite(body.confidence)
  requireString(body.method)
  requireArray(body.conditions)
  requireArray(body.contrasts)
  return body
}

export function ensureCulturalCellMetrics(
  value: unknown,
  decodeRowsJson: (raw: string) => unknown,
): Record<string, unknown> {
  const body = requireSchema(value, 'cultural-cell-metrics-v1')
  requireString(body.cell_id)
  requireString(body.matrix_fingerprint)
  requireString(body.evidence_digest)
  const documents = requireArray(body.documents)
  for (const document of documents) {
    const item = requireRecord(document)
    const values = item.values
    if (isRecord(values) && values.rows_json !== undefined) {
      const raw = requireString(values.rows_json, { allowEmpty: true })
      try {
        decodeRowsJson(raw)
      } catch (err) {
        throw new ResearchSchemaError(
          err instanceof Error && 'code' in err
            ? String((err as { code: unknown }).code)
            : 'invalid_research_response',
        )
      }
    }
  }
  return body
}

export function ensureCulturalEvidencePage(
  value: unknown,
): Record<string, unknown> {
  const body = requireSchema(value, 'research-cultural-evidence-page-v1')
  requireString(body.run_id)
  requireString(body.matrix_id)
  requireString(body.cell_id)
  requireString(body.section)
  requireString(body.artifact_digest)
  requireOneOf(body.binding_state, [
    'runtime_bound',
    'legacy_unverified',
  ] as const)
  requireArray(body.rows).forEach(requireRecord)
  requireArray(body.gaps)
  return body
}

export function ensureSemanticHistory(
  value: unknown,
): Record<string, unknown> {
  const body = requireSchema(value, 'observer-semantic-history-v1')
  requireString(body.run_id)
  requireString(body.agent_id)
  requireOneOf(body.source, ['label', 'composition'] as const)
  requireBoolean(body.retained_only)
  requireBoolean(body.prefix_complete)
  requireOneOf(body.availability, ['available', 'unavailable'] as const)
  requireArray(body.terms).forEach(requireRecord)
  requireArray(body.rows).forEach(requireRecord)
  requireNonNegInt(body.count)
  return body
}

export function ensureLabelOverlay(value: unknown): Record<string, unknown> {
  const body = requireRecord(value)
  requireString(body.run_id)
  requireString(body.agent_id)
  requireOneOf(body.layer, ['subjective_labels'] as const)
  requireArray(body.readings).forEach(requireRecord)
  return body
}

export function ensureSymbolicOverlay(value: unknown): Record<string, unknown> {
  const body = requireRecord(value)
  requireString(body.run_id)
  requireString(body.agent_id)
  requireOneOf(body.layer, ['subjective_symbolic_language'] as const)
  requireArray(body.compositions).forEach(requireRecord)
  return body
}

export function ensureTranslationOverlay(value: unknown): Record<string, unknown> {
  const body = requireRecord(value)
  requireString(body.run_id)
  requireString(body.agent_id)
  requireOneOf(body.layer, ['subjective_translation'] as const)
  requireArray(body.mappings).forEach(requireRecord)
  return body
}

export function ensureNarrativeHops(value: unknown): Record<string, unknown> {
  const body = requireRecord(value)
  requireString(body.run_id)
  requireString(body.owner_id)
  requireArray(body.variants).forEach(requireRecord)
  return body
}
