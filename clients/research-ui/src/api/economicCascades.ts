import { apiFetch } from './client'

export const CAPABILITY = 'subjective_debug'

export type EconomicCascadesSummary = {
  run_id: string
  publication_id: string
  digest: string
  snapshot_version: string
  policy_version: string
  generated_from_tick: number
  window_tick: number
  window_count: number
  coverage: string
  availability: string
  event_count: number
  disruption_count: number
  stage_count: number
  dependency_edge_count: number
  chain_count: number
  linked_chain_count: number
  disruption_kind_count: number
  max_depth: number
}

export type EconomicCascadesPage<T> = {
  run_id: string
  publication_id: string
  window_index: number | null
  rows: T[]
  next_cursor: string | null
  coverage: string
}

export type EconomicCascadeDisruptionRow = {
  window_index: number
  window_tick: number
  kind: string
  disruption_count: number
  magnitude_total: number
  subject_count: number
  coverage: string
}

export type EconomicCascadeDependencyRow = {
  window_index: number
  window_tick: number
  upstream_token: string
  downstream_recipe_token: string
  kind: string
  depth: number
  evidence_count: number
}

export type EconomicCascadeChainRow = {
  chain_token: string
  window_index: number
  window_tick: number
  disruption_kind: string
  depth: number
  lag_windows: number
  shortfall_share_milli: number
  state: string
  coverage: string
}

export type EconomicCascadePropagationRow = {
  window_index: number
  window_tick: number
  disruption_kind: string
  chain_count: number
  linked_chain_count: number
  unlinked_chain_count: number
  unresolved_chain_count: number
  mean_depth_milli: number
  mean_lag_milli: number
  downstream_stage_count: number
  coverage: string
  availability: string
}

export type EconomicCascadeCoverageRow = {
  window_index: number
  window_tick: number
  window_count: number
  event_count: number
  disruption_count: number
  stage_count: number
  dependency_edge_count: number
  labor_join_count: number
  chain_count: number
  linked_chain_count: number
  truncated: boolean
  coverage: string
  availability: string
}

export type EconomicCascadeWindowRow = {
  window_index: number
  window_tick: number
}

type PageOptions = {
  limit?: number | undefined
  cursor?: string | null | undefined
  windowIndex?: number | undefined
}

export function buildEconomicCascadesQuery(options: PageOptions = {}): string {
  const params = new URLSearchParams()
  if (options.limit !== undefined) params.set('limit', String(options.limit))
  if (options.cursor) params.set('cursor', options.cursor)
  if (options.windowIndex !== undefined) {
    params.set('window_index', String(options.windowIndex))
  }
  const text = params.toString()
  return text ? `?${text}` : ''
}

const base = (runId: string): string =>
  `/v1/simulations/${encodeURIComponent(runId)}/economic-cascades`

export function getEconomicCascadesSummary(
  runId: string,
): Promise<EconomicCascadesSummary> {
  return apiFetch<EconomicCascadesSummary>(base(runId), {
    capability: CAPABILITY,
  })
}

function getPage<T>(
  runId: string,
  purpose: string,
  options: PageOptions,
): Promise<EconomicCascadesPage<T>> {
  return apiFetch<EconomicCascadesPage<T>>(
    `${base(runId)}/${purpose}${buildEconomicCascadesQuery(options)}`,
    { capability: CAPABILITY },
  )
}

export function getEconomicCascadesDisruptions(
  runId: string,
  options: PageOptions = {},
): Promise<EconomicCascadesPage<EconomicCascadeDisruptionRow>> {
  return getPage(runId, 'disruptions', options)
}

export function getEconomicCascadesDependencies(
  runId: string,
  options: PageOptions = {},
): Promise<EconomicCascadesPage<EconomicCascadeDependencyRow>> {
  return getPage(runId, 'dependencies', options)
}

export function getEconomicCascadesChains(
  runId: string,
  options: PageOptions = {},
): Promise<EconomicCascadesPage<EconomicCascadeChainRow>> {
  return getPage(runId, 'chains', options)
}

export function getEconomicCascadesPropagation(
  runId: string,
  options: PageOptions = {},
): Promise<EconomicCascadesPage<EconomicCascadePropagationRow>> {
  return getPage(runId, 'propagation', options)
}

export function getEconomicCascadesWindows(
  runId: string,
  options: PageOptions = {},
): Promise<EconomicCascadesPage<EconomicCascadeWindowRow>> {
  return getPage(runId, 'windows', options)
}

export function getEconomicCascadesCoverage(
  runId: string,
  options: PageOptions = {},
): Promise<EconomicCascadesPage<EconomicCascadeCoverageRow>> {
  return getPage(runId, 'coverage', options)
}
