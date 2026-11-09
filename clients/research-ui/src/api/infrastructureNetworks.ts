import { apiFetch } from './client'

export const CAPABILITY = 'subjective_debug'

export type InfrastructureNetworksSummary = {
  run_id: string
  publication_id: string
  digest: string
  schema_version: string
  asset_count: number
  node_count: number
  edge_count: number
  operational_count: number
  damaged_count: number
  destroyed_count: number
  effects_active_count: number
  coverage: string
  route_count?: number
  route_open_count?: number
  route_restricted_count?: number
  route_closed_count?: number
  route_weather_count?: number
  route_seasonal_count?: number
  route_hazard_count?: number
}

export type TravelRoute = {
  origin_location_id: string
  destination_location_id: string
  status: string
  seasonal_availability: string
  blockage_cause: string
  duration_ticks: number
  fatigue_cost: number
  capacity: number
  risk: number
  infrastructure_quality: number
  as_of_tick: number
}

export type InfrastructureAsset = {
  asset_id: string
  kind: string
  topology: string
  status: string
  integrity: number
  location_id: string
  endpoint_location_id: string | null
  effects_active: boolean
  created_tick: number
  last_maintained_tick: number
  ticks_since_maintained: number
  linked_project_id: string
  linked_structure_id: string | null
}

export type Page<T> = {
  items: T[]
  next_cursor?: string | null
}

export type InfrastructureListOptions = {
  cursor?: string
  limit?: number
}

function base(runId: string): string {
  return `/v1/simulations/${encodeURIComponent(runId)}/infrastructure-networks`
}

export function fetchInfrastructureNetworksSummary(
  runId: string,
): Promise<InfrastructureNetworksSummary> {
  return apiFetch<InfrastructureNetworksSummary>(base(runId), {
    capability: CAPABILITY,
  })
}

function fetchPage(
  runId: string,
  purpose: string,
  options: InfrastructureListOptions = {},
): Promise<Page<InfrastructureAsset>> {
  return apiFetch<Page<InfrastructureAsset>>(`${base(runId)}/${purpose}`, {
    capability: CAPABILITY,
    query: {
      cursor: options.cursor,
      limit: options.limit ?? 200,
    },
  })
}

export function fetchInfrastructureAssets(
  runId: string,
  options: InfrastructureListOptions = {},
): Promise<Page<InfrastructureAsset>> {
  return fetchPage(runId, 'assets', options)
}

export function fetchInfrastructureEdges(
  runId: string,
  options: InfrastructureListOptions = {},
): Promise<Page<InfrastructureAsset>> {
  return fetchPage(runId, 'edges', options)
}

export function fetchInfrastructureCondition(
  runId: string,
  options: InfrastructureListOptions = {},
): Promise<Page<InfrastructureAsset>> {
  return fetchPage(runId, 'condition', options)
}

export function fetchInfrastructureEffects(
  runId: string,
  options: InfrastructureListOptions = {},
): Promise<Page<InfrastructureAsset>> {
  return fetchPage(runId, 'effects', options)
}

export function fetchInfrastructureMaintenance(
  runId: string,
  options: InfrastructureListOptions = {},
): Promise<Page<InfrastructureAsset>> {
  return fetchPage(runId, 'maintenance', options)
}

export function fetchTravelRoutes(
  runId: string,
  options: InfrastructureListOptions = {},
): Promise<Page<TravelRoute>> {
  return apiFetch<Page<TravelRoute>>(`${base(runId)}/routes`, {
    capability: CAPABILITY,
    query: {
      cursor: options.cursor,
      limit: options.limit ?? 200,
    },
  })
}
