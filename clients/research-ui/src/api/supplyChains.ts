import { apiFetch } from './client'

export const CAPABILITY = 'subjective_debug'

export type SupplyChainSummary = {
  run_id: string
  publication_id: string
  digest: string
  schema_version: string
  window_tick: number
  stage_count: number
  edge_count: number
  chain_count: number
  lineage_count: number
  bottleneck_count: number
  location_count: number
  organization_count: number
  sustained_chain_count: number
  max_depth: number
  coverage: string
  truncated: boolean
}

export type SupplyStage = {
  stage_token: string
  window_index: number
  recipe_id: string
  action: string
  location_token: string
  actor_token: string
  item_names: string[]
  completed: boolean
  attempt: boolean
  duration_ticks: number
  created_item_token: string
  cause: string
  coverage: string
}

export type SupplyDependency = {
  edge_token: string
  window_index: number
  from_kind: string
  from_token: string
  to_kind: string
  to_token: string
  edge_kind: string
  recipe_id: string
  observed_count: number
  completed_count: number
  share_milli: number
  created_elsewhere_count: number
  coverage: string
}

export type SupplyChain = {
  chain_token: string
  window_index: number
  stage_tokens: string[]
  edge_tokens: string[]
  depth: number
  completed_count: number
  coverage: string
}

export type SupplyLineage = {
  chain_token: string
  window_index: number
  status: string
  predecessor_tokens: string[]
  successor_tokens: string[]
  shared_edge_count: number
  overlap_milli: number
  coverage: string
}

export type SupplyBottleneck = {
  bottleneck_token: string
  window_index: number
  kind: string
  stage_token: string
  edge_token: string
  observed_count: number
  demand_count: number
  supply_count: number
  ratio_milli: number
  location_token: string
  organization_token: string
  skill_domain: string
  coverage: string
}

export type SupplyLocation = {
  location_token: string
  window_index: number
  observed_count: number
  completed_count: number
  coverage: string
}

export type SupplyOrganization = {
  organization_token: string
  window_index: number
  actor_count: number
  claim_count: number
  completed_count: number
  coverage: string
}

export type Page<T> = {
  items: T[]
  next_cursor?: string | null
}

export type SupplyListOptions = {
  cursor?: string | undefined
  limit?: number | undefined
  windowIndex?: number | undefined
}

function base(runId: string): string {
  return `/v1/simulations/${encodeURIComponent(runId)}/supply-chains`
}

function query(options: SupplyListOptions): Record<string, string | number | undefined> {
  return {
    cursor: options.cursor,
    limit: options.limit ?? 100,
    window_index: options.windowIndex,
  }
}

export function fetchSupplyChainSummary(runId: string): Promise<SupplyChainSummary> {
  return apiFetch<SupplyChainSummary>(base(runId), { capability: CAPABILITY })
}

export function fetchSupplyStages(
  runId: string,
  options: SupplyListOptions = {},
): Promise<Page<SupplyStage>> {
  return apiFetch<Page<SupplyStage>>(`${base(runId)}/stages`, {
    capability: CAPABILITY,
    query: query(options),
  })
}

export function fetchSupplyDependencies(
  runId: string,
  options: SupplyListOptions = {},
): Promise<Page<SupplyDependency>> {
  return apiFetch<Page<SupplyDependency>>(`${base(runId)}/dependencies`, {
    capability: CAPABILITY,
    query: query(options),
  })
}

export function fetchSupplyChains(
  runId: string,
  options: SupplyListOptions = {},
): Promise<Page<SupplyChain>> {
  return apiFetch<Page<SupplyChain>>(`${base(runId)}/chains`, {
    capability: CAPABILITY,
    query: query(options),
  })
}

export function fetchSupplyBottlenecks(
  runId: string,
  options: SupplyListOptions = {},
): Promise<Page<SupplyBottleneck>> {
  return apiFetch<Page<SupplyBottleneck>>(`${base(runId)}/bottlenecks`, {
    capability: CAPABILITY,
    query: query(options),
  })
}

export function fetchSupplyLocations(
  runId: string,
  options: SupplyListOptions = {},
): Promise<Page<SupplyLocation>> {
  return apiFetch<Page<SupplyLocation>>(`${base(runId)}/locations`, {
    capability: CAPABILITY,
    query: query(options),
  })
}

export function fetchSupplyOrganizations(
  runId: string,
  options: SupplyListOptions = {},
): Promise<Page<SupplyOrganization>> {
  return apiFetch<Page<SupplyOrganization>>(`${base(runId)}/organizations`, {
    capability: CAPABILITY,
    query: query(options),
  })
}
