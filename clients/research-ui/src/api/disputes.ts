/** Read-only dispute-resolution snapshot client. */

import { apiFetch } from './client'

const CAPABILITY = 'subjective_debug' as const

export type DisputeCoverage = {
  observed: number
  expected: number
  ratio: number | null
  note: string
}

export type DisputeSummary = {
  run_id: string
  publication_id: string
  schema_version: string
  generated_tick: number
  candidate_count: number
  case_count: number
  claim_count: number
  counterclaim_count: number
  testimony_count: number
  evidence_count: number
  resolution_count: number
  accepted_count: number
  rejected_count: number
  edge_count: number
  window_count: number
  coverage: DisputeCoverage
  provenance_code: string
  snapshot_digest: string
}

export type DisputeCandidate = {
  candidate_id: string
  kind: string
  subject_token: string
  party_count: number
  owner_count: number
  case_count: number
  claim_count: number
  counterclaim_count: number
  testimony_count: number
  evidence_count: number
  resolution_count: number
  disagreement_count: number
  status: string
  first_tick: number
  last_tick: number
  coverage: DisputeCoverage
}

export type DisputeClaim = {
  claim_id: string
  case_ref: string
  claimant_id: string
  respondent_id: string
  role: string
  claim_kind: string
  polarity: string
  subject_token: string
  counters_claim_ref: string | null
  evidence_count: number
  first_tick: number
  last_tick: number
  candidate_id: string
}

export type DisputeTestimony = {
  testimony_id: string
  case_ref: string
  claim_id: string
  speaker_id: string
  channel: string
  root_token: string
  independently_evidenced: boolean
  tick: number
}

export type DisputeEvidence = {
  evidence_id: string
  case_ref: string
  claim_id: string
  channel: string
  reference_kind: string
  reference_token: string
  tick: number
  independently_evidenced: boolean
}

export type DisputeRuleReference = {
  rule_reference_id: string
  case_ref: string
  claim_ref: string
  system_token: string
  rule_token: string
  version_number: number
  applicability: string
  interpretation: string
  status: string
}

export type DisputeAuthorityReference = {
  authority_reference_id: string
  case_ref: string
  authority_kind: string
  reference_token: string
  strength: number
  uncertainty: number
  dissenting: boolean
}

export type DisputeMediationReference = {
  mediation_reference_id: string
  case_ref: string
  mediation_case_token: string
  recommendation_token: string | null
  response_token: string | null
  outcome_token: string | null
  link_status: string
}

export type DisputeResolution = {
  resolution_id: string
  resolution_ref: string
  case_ref: string
  proposer_id: string
  source: string
  terms_digest: string
  status: string
  first_tick: number
  last_tick: number
  expires_tick: number | null
  accepted_party_count: number
  rejected_party_count: number
  candidate_id: string
}

export type DisputeResolutionResponse = {
  response_id: string
  resolution_ref: string
  party_id: string
  kind: string
  tick: number
  terms_digest: string
  active: boolean
}

export type DisputeLineageEdge = {
  edge_id: string
  source: string
  target: string
  kind: string
  tick: number
}

export type DisputeCandidateDetail = {
  candidate: DisputeCandidate
  coverage: DisputeCoverage
  testimony: DisputeTestimony[]
  evidence: DisputeEvidence[]
  rule_references: DisputeRuleReference[]
  authority_references: DisputeAuthorityReference[]
  mediation_references: DisputeMediationReference[]
  responses: DisputeResolutionResponse[]
  truncated: boolean
}

type Page<T> = { items: T[]; next_cursor: string | null; truncated: boolean }

function base(runId: string): string {
  return `/v1/simulations/${encodeURIComponent(runId)}/disputes`
}

export function getDisputeSummary(runId: string): Promise<DisputeSummary> {
  return apiFetch<DisputeSummary>(base(runId), { capability: CAPABILITY })
}

export function getDisputeCandidates(
  runId: string,
  cursor?: string,
): Promise<Page<DisputeCandidate>> {
  return apiFetch<Page<DisputeCandidate>>(`${base(runId)}/candidates`, {
    capability: CAPABILITY,
    query: { limit: 200, cursor },
  })
}

export function getDisputeCandidate(
  runId: string,
  candidateId: string,
): Promise<DisputeCandidateDetail> {
  return apiFetch<DisputeCandidateDetail>(
    `${base(runId)}/candidates/${encodeURIComponent(candidateId)}`,
    { capability: CAPABILITY },
  )
}

export function getDisputeClaims(
  runId: string,
  candidateId: string,
  cursor?: string,
): Promise<Page<DisputeClaim>> {
  return apiFetch<Page<DisputeClaim>>(
    `${base(runId)}/candidates/${encodeURIComponent(candidateId)}/claims`,
    { capability: CAPABILITY, query: { limit: 200, cursor } },
  )
}

export function getDisputeResolutions(
  runId: string,
  candidateId: string,
  cursor?: string,
): Promise<Page<DisputeResolution>> {
  return apiFetch<Page<DisputeResolution>>(
    `${base(runId)}/candidates/${encodeURIComponent(candidateId)}/resolutions`,
    { capability: CAPABILITY, query: { limit: 200, cursor } },
  )
}

export function getDisputeLineage(
  runId: string,
  cursor?: string,
): Promise<Page<DisputeLineageEdge>> {
  return apiFetch<Page<DisputeLineageEdge>>(`${base(runId)}/lineage`, {
    capability: CAPABILITY,
    query: { limit: 200, cursor },
  })
}
