/** Read-only organization snapshot client. */

import { apiFetch } from './client'

export type OrganizationCoverage = {
  observed: number
  expected: number
  ratio: number | null
}

export type OrganizationSummary = {
  run_id: string
  publication_id: string
  schema_version: string
  generated_tick: number
  candidate_count: number
  edge_count: number
  window_count: number
  coverage: OrganizationCoverage
  provenance_code: string
}

export type OrganizationMember = {
  member_id: string
  status: string
  basis: string
  temporal_scope: string
  first_tick: number
  last_tick: number
  expires_tick: number | null
  strength: number
  owner_support_count: number
}

export type OrganizationStructural = {
  kind: string
  anchor_id: string
  status: string
  first_tick: number
  last_tick: number
  resolved: boolean
}

export type OrganizationCandidate = {
  organization_id: string
  creation_tick: number
  first_tick: number
  last_tick: number
  status: string
  temporal_scope: string
  self_identified: boolean
  member_count: number
  role_count: number
  goal_count: number
  resource_count: number
  procedure_count: number
  record_count: number
  commitment_count: number
  identity_count: number
  structural_channel_count: number
  window_indexes: number[]
}

export type OrganizationCandidateDetail = OrganizationCandidate & {
  members: OrganizationMember[]
  structure: OrganizationStructural[]
}

export type OrganizationCandidatePage = {
  publication_id: string
  items: OrganizationCandidate[]
  next_cursor: string | null
  truncated: boolean
}

export type OrganizationLineageEdge = {
  kind: string
  tick: number
  from_id: string | null
  to_id: string | null
  jaccard: number | null
  containment: number | null
}

export type OrganizationLineagePage = {
  publication_id: string
  items: OrganizationLineageEdge[]
  next_cursor: string | null
  truncated: boolean
}

const CAPABILITY = 'subjective_debug' as const

function base(runId: string): string {
  return `/v1/simulations/${encodeURIComponent(runId)}/organizations`
}

export function getOrganizationSummary(runId: string): Promise<OrganizationSummary> {
  return apiFetch<OrganizationSummary>(base(runId), { capability: CAPABILITY })
}

export function getOrganizationCandidates(
  runId: string,
  options: { status?: string; limit?: number; cursor?: string } = {},
): Promise<OrganizationCandidatePage> {
  return apiFetch<OrganizationCandidatePage>(`${base(runId)}/candidates`, {
    capability: CAPABILITY,
    query: {
      status: options.status,
      limit: options.limit,
      cursor: options.cursor,
    },
  })
}

export function getOrganizationCandidate(
  runId: string,
  organizationId: string,
): Promise<OrganizationCandidateDetail> {
  return apiFetch<OrganizationCandidateDetail>(
    `${base(runId)}/candidates/${encodeURIComponent(organizationId)}`,
    { capability: CAPABILITY },
  )
}

export function getOrganizationLineage(
  runId: string,
  options: { kind?: string; limit?: number; cursor?: string } = {},
): Promise<OrganizationLineagePage> {
  return apiFetch<OrganizationLineagePage>(`${base(runId)}/lineage`, {
    capability: CAPABILITY,
    query: { kind: options.kind, limit: options.limit, cursor: options.cursor },
  })
}
