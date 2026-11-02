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
  snapshot_digest: string
  operation_count: number
  collective_proposal_count: number
  collective_amendment_count: number
  collective_support_count: number
  collective_oppose_count: number
  collective_abstain_count: number
  collective_decision_count: number
  collective_implementation_count: number
  unimplemented_decision_count: number
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
  operation_count: number
  contested_operation_count: number
  collective_proposal_count: number
  collective_amendment_count: number
  collective_support_count: number
  collective_oppose_count: number
  collective_abstain_count: number
  collective_decision_count: number
  collective_implementation_count: number
  unimplemented_decision_count: number
  contested_decision_count: number
}

export type OrganizationOperation = {
  operation_id: string
  domain: string
  act: string
  stance: string
  authority_basis: string
  provenance_code: string
  outcome: string
  command_kind: string
  target_kind: string
  anchor_kind: string
  anchor_id: string | null
  tick: number
  first_tick: number
  last_tick: number
  support_count: number
  contest_count: number
  resolved: boolean
}

export type OrganizationCollectiveImplementation = {
  implementation_id: string
  actor_ref: string
  status: string
  effect: string
  observed_tick: number
  provenance_code: string
  resolved: boolean
}

export type OrganizationCollectiveDecision = {
  decision_id: string
  organization_id: string
  proposal_ref: string
  revision: number
  procedure_ref: string | null
  recognition: string
  authority_basis: string
  support_count: number
  oppose_count: number
  abstain_count: number
  contest_count: number
  implementation_mode: string
  effect: string
  target_kind: string
  target_ref: string | null
  decided_tick: number
  window_end_tick: number
  implementation_status: string
  provenance_code: string
  resolved: boolean
  implementations: OrganizationCollectiveImplementation[]
}

export type OrganizationCollectiveAgencyPage = {
  publication_id: string
  items: OrganizationCollectiveDecision[]
  next_cursor: string | null
  truncated: boolean
}

export type OrganizationCandidateDetail = OrganizationCandidate & {
  members: OrganizationMember[]
  structure: OrganizationStructural[]
  operations: OrganizationOperation[]
  collective_decisions: OrganizationCollectiveDecision[]
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

export type OrganizationOperationPage = {
  publication_id: string
  items: OrganizationOperation[]
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

export function getOrganizationOperations(
  runId: string,
  options: {
    domain?: string
    organizationId?: string
    limit?: number
    cursor?: string
  } = {},
): Promise<OrganizationOperationPage> {
  return apiFetch<OrganizationOperationPage>(`${base(runId)}/operations`, {
    capability: CAPABILITY,
    query: {
      domain: options.domain,
      organization_id: options.organizationId,
      limit: options.limit,
      cursor: options.cursor,
    },
  })
}

export function getOrganizationCollectiveAgency(
  runId: string,
  options: {
    recognition?: string
    organizationId?: string
    limit?: number
    cursor?: string
  } = {},
): Promise<OrganizationCollectiveAgencyPage> {
  return apiFetch<OrganizationCollectiveAgencyPage>(
    `${base(runId)}/collective-agency`,
    {
      capability: CAPABILITY,
      query: {
        recognition: options.recognition,
        organization_id: options.organizationId,
        limit: options.limit,
        cursor: options.cursor,
      },
    },
  )
}
