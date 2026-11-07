import { apiFetch } from './client'

export const CAPABILITY = 'subjective_debug'

export type BordersSummary = {
  run_id: string
  publication_id: string
  digest: string
  schema_version: string
  candidate_count: number
  claim_count: number
  agreement_count: number
  dispute_count: number
  physical_row_count: number
  pattern_count: number
  coverage: string
}

export type BorderClaim = {
  claim_token: string
  owner_token: string
  domain_token: string
  location_tokens: string[]
  boundary_edge_tokens: [string, string][]
  status: string
  strength: number
  anchor_token: string
}

export type BorderAgreement = {
  agreement_token: string
  domain_token: string
  counterparty_token: string
  provision_tokens: string[]
  status: string
  recognition: string
  effective_tick?: number | null
  expiry_tick?: number | null
}

export type BorderControlRow = {
  layer: string
  location_token?: string | null
  window_start?: number | null
  window_end?: number | null
  actor_count: number
  action_count: number
  hostile_count: number
  assistance_count: number
  presence_ticks: number
  classification?: string | null
  pattern_token?: string | null
  domain_token?: string | null
  location_tokens: string[]
  pattern?: string | null
  physical_actions: number
  claim_count: number
  agreement_count: number
  dispute_count: number
}

export type Page<T> = {
  items: T[]
  next_cursor?: string | null
}

function base(runId: string): string {
  return `/v1/simulations/${encodeURIComponent(runId)}/borders`
}

export function fetchBordersSummary(runId: string): Promise<BordersSummary> {
  return apiFetch<BordersSummary>(base(runId), { capability: CAPABILITY })
}

export function fetchBorderClaims(
  runId: string,
  cursor?: string,
  limit = 200,
): Promise<Page<BorderClaim>> {
  return apiFetch<Page<BorderClaim>>(`${base(runId)}/claims`, {
    capability: CAPABILITY,
    query: { limit, cursor },
  })
}

export function fetchBorderAgreements(
  runId: string,
  cursor?: string,
  limit = 200,
): Promise<Page<BorderAgreement>> {
  return apiFetch<Page<BorderAgreement>>(`${base(runId)}/agreements`, {
    capability: CAPABILITY,
    query: { limit, cursor },
  })
}

export function fetchBorderControl(
  runId: string,
  layer: 'physical' | 'analytical' | 'all' = 'all',
  cursor?: string,
  limit = 200,
): Promise<Page<BorderControlRow>> {
  return apiFetch<Page<BorderControlRow>>(`${base(runId)}/control`, {
    capability: CAPABILITY,
    query: { layer, limit, cursor },
  })
}
