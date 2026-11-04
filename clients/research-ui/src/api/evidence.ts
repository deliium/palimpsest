import { apiFetch } from './client'

export const CAPABILITY = 'subjective_debug'

export type EvidenceSummary = {
  run_id: string
  publication_id: string
  snapshot_digest: string
  generated_tick: number
  candidate_count: number
  source_count: number
  testimony_count: number
  item_count: number
  custody_link_count: number
  contradiction_count: number
  evaluation_count: number
  edge_count: number
  coverage: string
  schema_version: string
  window_count: number
  provenance_code: string
}

export type EvidenceCandidate = {
  candidate_id: string
  subject_token: string
  source_kind_family: string
  owner_count: number
  item_count: number
  source_count: number
  testimony_count: number
  contradiction_count: number
  status: string
  coverage: string
  first_tick: number
  last_tick: number
}

export type EvidenceSource = {
  owner_token: string
  local_id: string
  source_kind: string
  reference_kind: string
  provenance: string
  confidence_band: string
  tick: number
  subject_token: string
  custody_status: string
  root_ref?: string | null
  correlation_token?: string | null
}

export type EvidenceContradiction = {
  owner_token: string
  local_id: string
  candidate_id: string
  first_ref: string
  second_ref: string
  kind: string
  status: string
  tick: number
}

export type EvidenceLineageEdge = {
  edge_id: string
  kind: string
  source_ids: string[]
  target_ids: string[]
  window_index: number
}

export type EvidenceCandidateDetail = {
  candidate: EvidenceCandidate
  sources: EvidenceSource[]
  contradictions: EvidenceContradiction[]
  custody_complete_count: number
  custody_incomplete_count: number
  custody_conflicting_count: number
  sources_truncated: boolean
  contradictions_truncated: boolean
  alignment_label: string
}

type Page<T> = { items: T[]; next_cursor: string | null; truncated: boolean }

function base(runId: string): string {
  return `/v1/simulations/${encodeURIComponent(runId)}/evidence`
}

export function getEvidenceSummary(runId: string): Promise<EvidenceSummary> {
  return apiFetch<EvidenceSummary>(base(runId), { capability: CAPABILITY })
}

export function getEvidenceCandidates(
  runId: string,
  cursor?: string,
): Promise<Page<EvidenceCandidate>> {
  return apiFetch<Page<EvidenceCandidate>>(`${base(runId)}/candidates`, {
    capability: CAPABILITY,
    query: { limit: 200, cursor },
  })
}

export function getEvidenceCandidate(
  runId: string,
  candidateId: string,
): Promise<EvidenceCandidateDetail> {
  return apiFetch<EvidenceCandidateDetail>(
    `${base(runId)}/candidates/${encodeURIComponent(candidateId)}`,
    { capability: CAPABILITY },
  )
}

export function getEvidenceSources(
  runId: string,
  candidateId: string,
  cursor?: string,
): Promise<Page<EvidenceSource>> {
  return apiFetch<Page<EvidenceSource>>(
    `${base(runId)}/candidates/${encodeURIComponent(candidateId)}/sources`,
    { capability: CAPABILITY, query: { limit: 200, cursor } },
  )
}

export function getEvidenceContradictions(
  runId: string,
  candidateId: string,
  cursor?: string,
): Promise<Page<EvidenceContradiction>> {
  return apiFetch<Page<EvidenceContradiction>>(
    `${base(runId)}/candidates/${encodeURIComponent(candidateId)}/contradictions`,
    { capability: CAPABILITY, query: { limit: 200, cursor } },
  )
}

export function getEvidenceLineage(
  runId: string,
  cursor?: string,
): Promise<Page<EvidenceLineageEdge>> {
  return apiFetch<Page<EvidenceLineageEdge>>(`${base(runId)}/lineage`, {
    capability: CAPABILITY,
    query: { limit: 200, cursor },
  })
}
