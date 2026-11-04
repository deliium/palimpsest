import { apiFetch } from './client'

export const CAPABILITY = 'subjective_debug'

export type DiplomacySummary = {
  run_id: string
  publication_id: string
  snapshot_digest: string
  relation_count: number
  party_count: number
  contact_count: number
  envoy_count: number
  negotiation_count: number
  instrument_count: number
  declaration_count: number
  misrepresentation_count: number
  termination_count: number
  conflict_count: number
  candidate_count: number
  lineage_edge_count: number
  coverage: string
}

export type DiplomacyRelation = {
  relation_id: string
  owner_token: string
  party_tokens: string[]
  opened_tick: number
  last_tick: number
  provenance: string
}

export type DiplomacyInstrument = {
  instrument_id: string
  relation_id: string
  owner_token: string
  party_tokens: string[]
  instrument_kind: string
  term_kind: string
  subject_token?: string | null
  opener_envoy_token?: string | null
  opened_tick: number
  end_tick?: number | null
  anchor_refs: string[]
  provenance: string
}

export type DiplomacyLineage = {
  edge_id: string
  from_candidate_id: string
  to_candidate_id: string
  kind: string
  tick: number
}

export type DiplomacyParty = {
  party_id: string
  owner_token: string
  party_token?: string | null
  party_kind: string
  resolution: string
  first_seen_tick: number
  provenance: string
}

export type DiplomacyEnvoy = {
  envoy_id: string
  relation_id: string
  owner_token: string
  party_token?: string | null
  envoy_token: string
  mandate_token?: string | null
  status: string
  accredited_tick: number
  end_tick?: number | null
  provenance: string
}

export type DiplomacyTermination = {
  termination_id: string
  owner_token: string
  target_kind: string
  target_ref: string
  kind: string
  tick: number
  provenance: string
}

export type DiplomacyMisrepresentation = {
  misrepresentation_id: string
  instrument_id: string
  owner_token: string
  kind: string
  observed_tick: number
  envoy_token: string
  party_token?: string | null
  provenance: string
}

export type DiplomacyRelationDetail = {
  relation: DiplomacyRelation
  parties: DiplomacyParty[]
  contacts: unknown[]
  envoys: DiplomacyEnvoy[]
  negotiations: unknown[]
  instruments: DiplomacyInstrument[]
  declarations: unknown[]
  misrepresentations: DiplomacyMisrepresentation[]
  terminations: DiplomacyTermination[]
  truncated: boolean
}

export type DiplomacyInstrumentDetail = {
  instrument: DiplomacyInstrument
  declarations: unknown[]
  misrepresentations: DiplomacyMisrepresentation[]
  terminations: DiplomacyTermination[]
  truncated: boolean
}

type Page<T> = { items: T[]; next_cursor: string | null }

function base(runId: string): string {
  return `/v1/simulations/${encodeURIComponent(runId)}/diplomacy`
}

export function getDiplomacySummary(runId: string): Promise<DiplomacySummary> {
  return apiFetch<DiplomacySummary>(base(runId), { capability: CAPABILITY })
}

export function getDiplomacyRelations(
  runId: string,
  cursor?: string,
): Promise<Page<DiplomacyRelation>> {
  return apiFetch<Page<DiplomacyRelation>>(`${base(runId)}/relations`, {
    capability: CAPABILITY,
    query: { limit: 200, cursor },
  })
}

export function getDiplomacyRelation(
  runId: string,
  relationId: string,
): Promise<DiplomacyRelationDetail> {
  return apiFetch<DiplomacyRelationDetail>(
    `${base(runId)}/relations/${encodeURIComponent(relationId)}`,
    { capability: CAPABILITY },
  )
}

export function getDiplomacyInstruments(
  runId: string,
  cursor?: string,
): Promise<Page<DiplomacyInstrument>> {
  return apiFetch<Page<DiplomacyInstrument>>(`${base(runId)}/instruments`, {
    capability: CAPABILITY,
    query: { limit: 200, cursor },
  })
}

export function getDiplomacyInstrument(
  runId: string,
  instrumentId: string,
): Promise<DiplomacyInstrumentDetail> {
  return apiFetch<DiplomacyInstrumentDetail>(
    `${base(runId)}/instruments/${encodeURIComponent(instrumentId)}`,
    { capability: CAPABILITY },
  )
}

export function getDiplomacyLineage(
  runId: string,
  cursor?: string,
): Promise<Page<DiplomacyLineage>> {
  return apiFetch<Page<DiplomacyLineage>>(`${base(runId)}/lineage`, {
    capability: CAPABILITY,
    query: { limit: 200, cursor },
  })
}
