import { apiFetch } from './client'

export const CAPABILITY = 'subjective_debug'

export type RepresentationSummary = {
  run_id: string
  publication_id: string
  snapshot_digest: string
  generated_tick: number
  mandate_count: number
  position_count: number
  revocation_count: number
  conflict_count: number
  candidate_count: number
  lineage_edge_count: number
  owner_count: number
  coverage: string
  schema_version: string
}

export type RepresentationMandate = {
  mandate_id: string
  owner_token: string
  principal_kind: string
  principal_token?: string | null
  representative_token: string
  scope_kind: string
  scope_subject_token?: string | null
  duration_kind: string
  start_tick: number
  end_tick?: number | null
  provenance: string
  status: string
  recognition_basis: string
  support_roots: number
  opposition_roots: number
  confidence_band: string
  coverage: string
}

export type RepresentationPosition = {
  position_id: string
  mandate_id: string
  owner_token: string
  actor_token: string
  stance: string
  provenance: string
  tick: number
  active: boolean
}

export type RepresentationRevocation = {
  revocation_id: string
  mandate_id: string
  owner_token: string
  actor_token: string
  kind: string
  provenance: string
  tick: number
  contested: boolean
}

export type RepresentationLineage = {
  edge_id: string
  from_candidate_id: string
  to_candidate_id: string
  kind: string
  tick: number
}

type Page<T> = { items: T[]; next_cursor: string | null; truncated: boolean }

function base(runId: string): string {
  return `/v1/simulations/${encodeURIComponent(runId)}/representation`
}

export function getRepresentationSummary(
  runId: string,
): Promise<RepresentationSummary> {
  return apiFetch<RepresentationSummary>(base(runId), { capability: CAPABILITY })
}

export function getRepresentationMandates(
  runId: string,
  cursor?: string,
  candidateId?: string,
): Promise<Page<RepresentationMandate>> {
  return apiFetch<Page<RepresentationMandate>>(`${base(runId)}/mandates`, {
    capability: CAPABILITY,
    query: { limit: 200, cursor, candidate_id: candidateId },
  })
}

export function getRepresentationMandate(
  runId: string,
  mandateId: string,
): Promise<RepresentationMandate> {
  return apiFetch<RepresentationMandate>(
    `${base(runId)}/mandates/${encodeURIComponent(mandateId)}`,
    { capability: CAPABILITY },
  )
}

export function getRepresentationPositions(
  runId: string,
  mandateId: string,
  cursor?: string,
): Promise<Page<RepresentationPosition>> {
  return apiFetch<Page<RepresentationPosition>>(
    `${base(runId)}/mandates/${encodeURIComponent(mandateId)}/positions`,
    { capability: CAPABILITY, query: { limit: 200, cursor } },
  )
}

export function getRepresentationRevocations(
  runId: string,
  mandateId: string,
  cursor?: string,
): Promise<Page<RepresentationRevocation>> {
  return apiFetch<Page<RepresentationRevocation>>(
    `${base(runId)}/mandates/${encodeURIComponent(mandateId)}/revocations`,
    { capability: CAPABILITY, query: { limit: 200, cursor } },
  )
}

export function getRepresentationLineage(
  runId: string,
  cursor?: string,
): Promise<Page<RepresentationLineage>> {
  return apiFetch<Page<RepresentationLineage>>(`${base(runId)}/lineage`, {
    capability: CAPABILITY,
    query: { limit: 200, cursor },
  })
}
