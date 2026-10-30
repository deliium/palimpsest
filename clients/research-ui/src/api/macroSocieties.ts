/** Read-only macro-society snapshot client. */

import { apiFetch } from './client'

export type MacroSocietyCoverage = {
  observed: number
  expected: number
  ratio: number | null
}

export type MacroSocietySummary = {
  publication_id: string
  snapshot_digest: string
  schema_version: string
  policy_version: string
  run_id: string
  input_revision: string
  generated_tick: number
  window_count: number
  candidate_count: number
  edge_count: number
  coverage: MacroSocietyCoverage
  provenance_code: string
}

export type MacroSocietyCandidate = {
  macro_society_id: string
  creation_tick: number
  first_tick: number
  last_tick: number
  status: string
  member_count: number
  lane_signature: string[]
  overlap_person_count: number
}

export type MacroSocietyCandidatePage = {
  items: MacroSocietyCandidate[]
  next_cursor: string | null
}

export type MacroSocietyCandidateDetail = {
  macro_society_id: string
  creation_tick: number
  first_tick: number
  last_tick: number
  status: string
  member_ids: string[]
  lane_signature: string[]
  overlap_person_ids: string[]
}

export type MacroSocietyLineageEdge = {
  from_id: string | null
  to_id: string | null
  kind: string
  from_tick: number
  to_tick: number
  jaccard: number | null
}

export type MacroSocietyLineagePage = {
  items: MacroSocietyLineageEdge[]
  next_cursor: string | null
}

const CAPABILITY = 'subjective_debug' as const

function base(runId: string): string {
  return `/v1/simulations/${encodeURIComponent(runId)}/macro-societies`
}

export function getMacroSocietySummary(runId: string): Promise<MacroSocietySummary> {
  return apiFetch<MacroSocietySummary>(base(runId), { capability: CAPABILITY })
}

export function getMacroSocietyCandidates(
  runId: string,
  options: { status?: string; limit?: number; cursor?: string } = {},
): Promise<MacroSocietyCandidatePage> {
  return apiFetch<MacroSocietyCandidatePage>(`${base(runId)}/candidates`, {
    capability: CAPABILITY,
    query: {
      status: options.status,
      limit: options.limit,
      cursor: options.cursor,
    },
  })
}

export function getMacroSocietyCandidate(
  runId: string,
  macroSocietyId: string,
): Promise<MacroSocietyCandidateDetail> {
  return apiFetch<MacroSocietyCandidateDetail>(
    `${base(runId)}/candidates/${encodeURIComponent(macroSocietyId)}`,
    { capability: CAPABILITY },
  )
}

export function getMacroSocietyLineage(
  runId: string,
  options: { kind?: string; limit?: number; cursor?: string } = {},
): Promise<MacroSocietyLineagePage> {
  return apiFetch<MacroSocietyLineagePage>(`${base(runId)}/lineage`, {
    capability: CAPABILITY,
    query: { kind: options.kind, limit: options.limit, cursor: options.cursor },
  })
}
