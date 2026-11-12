import { apiFetch } from './client'

export const CAPABILITY = 'subjective_debug'

export type CreditRelationship = {
  relationship_id: string
  window_index: number
  owner_token: string
  counterparty_token: string
  direction: string
  anchor_token: string
  principal_kind: string
  principal_quantity: number
  repayment_kind: string
  repayment_quantity: number
  repayment_ratio_milli: number
  due_tick: number | null
  condition: string
  collateral_kind: string
  collateral_quantity: number
  status: string
  confidence_milli: number
  expectation_milli: number
  trust_milli: number
  claim_count: number
  coverage: string
}

export type CreditClaim = {
  claim_id: string
  window_index: number
  event_token: string
  actor_token: string
  counterparty_token: string
  act: string
  direction: string
  anchor_token: string
  principal_kind: string
  principal_quantity: number
  repayment_kind: string
  repayment_quantity: number
  paid_quantity: number
  opened_tick: number
  due_tick: number | null
  condition: string
  collateral_kind: string
  collateral_quantity: number
  confidence_milli: number
  coverage: string
}

export type CreditPerformance = {
  performance_id: string
  window_index: number
  anchor_token: string
  claim_count: number
  repay_claim_count: number
  default_claim_count: number
  forgive_claim_count: number
  dispute_claim_count: number
  renegotiate_claim_count: number
  observed_transfer_count: number
  repaid_quantity: number
  principal_quantity: number
  repayment_quantity: number
  outcome: string
  coverage: string
}

export type CreditDistribution = {
  distribution_id: string
  window_index: number
  principal_kind: string
  repayment_kind: string
  sample_source: string
  sample_count: number
  min_ratio_milli: number
  p25_ratio_milli: number
  median_ratio_milli: number
  p75_ratio_milli: number
  max_ratio_milli: number
  iqr_milli: number
  dispersion_milli: number
  bin_shares_milli: number[]
  status: string
  coverage: string
}

export type CreditCounterparty = {
  counterparty_token: string
  window_index: number
  relationship_count: number
  owner_count: number
  claim_count: number
  repay_claim_count: number
  default_claim_count: number
  forgive_claim_count: number
  dispute_claim_count: number
  observed_transfer_count: number
  coverage: string
}

export type CreditAlignment = {
  alignment_id: string
  window_index: number
  owner_token: string
  anchor_token: string
  alignment: string
  owner_status: string
  analytical_outcome: string
  owner_paid_quantity: number
  declared_repayment_quantity: number
  observed_transfer_count: number
  gap_milli: number
  coverage: string
}

export type CreditRelationshipsSummary = {
  run_id: string
  publication_id: string
  digest: string
  schema_version: string
  window_tick: number
  window_count: number
  relationship_count: number
  claim_count: number
  performance_count: number
  distribution_count: number
  counterparty_count: number
  alignment_count: number
  claim_event_count: number
  transfer_event_count: number
  evidence_coverage: string
  owner_coverage: string
  relationship_coverage: string
  performance_coverage: string
  distribution_coverage: string
  counterparty_coverage: string
  alignment_coverage: string
  coverage: string
  truncated: boolean
}

export type CreditRelationshipsPage<T> = {
  run_id: string
  publication_id: string
  window_index: number | null
  rows: T[]
  next_cursor: string | null
  coverage: string
}

type PageOptions = {
  limit?: number | undefined
  cursor?: string | null | undefined
  windowIndex?: number | undefined
}

function query(options: PageOptions): string {
  const params = new URLSearchParams()
  if (options.limit !== undefined) params.set('limit', String(options.limit))
  if (options.cursor) params.set('cursor', options.cursor)
  if (options.windowIndex !== undefined) {
    params.set('window_index', String(options.windowIndex))
  }
  const text = params.toString()
  return text ? `?${text}` : ''
}

const base = (runId: string): string =>
  `/v1/simulations/${encodeURIComponent(runId)}/credit-relationships`

export function getSummary(runId: string): Promise<CreditRelationshipsSummary> {
  return apiFetch<CreditRelationshipsSummary>(base(runId), {
    capability: CAPABILITY,
  })
}

export function getRelationships(
  runId: string,
  options: PageOptions = {},
): Promise<CreditRelationshipsPage<CreditRelationship>> {
  return apiFetch<CreditRelationshipsPage<CreditRelationship>>(
    `${base(runId)}/relationships${query(options)}`,
    { capability: CAPABILITY },
  )
}

export function getClaims(
  runId: string,
  options: PageOptions = {},
): Promise<CreditRelationshipsPage<CreditClaim>> {
  return apiFetch<CreditRelationshipsPage<CreditClaim>>(
    `${base(runId)}/claims${query(options)}`,
    { capability: CAPABILITY },
  )
}

export function getPerformances(
  runId: string,
  options: PageOptions = {},
): Promise<CreditRelationshipsPage<CreditPerformance>> {
  return apiFetch<CreditRelationshipsPage<CreditPerformance>>(
    `${base(runId)}/performances${query(options)}`,
    { capability: CAPABILITY },
  )
}

export function getDistributions(
  runId: string,
  options: PageOptions = {},
): Promise<CreditRelationshipsPage<CreditDistribution>> {
  return apiFetch<CreditRelationshipsPage<CreditDistribution>>(
    `${base(runId)}/distributions${query(options)}`,
    { capability: CAPABILITY },
  )
}

export function getCounterparties(
  runId: string,
  options: PageOptions = {},
): Promise<CreditRelationshipsPage<CreditCounterparty>> {
  return apiFetch<CreditRelationshipsPage<CreditCounterparty>>(
    `${base(runId)}/counterparties${query(options)}`,
    { capability: CAPABILITY },
  )
}

export function getAlignment(
  runId: string,
  options: PageOptions = {},
): Promise<CreditRelationshipsPage<CreditAlignment>> {
  return apiFetch<CreditRelationshipsPage<CreditAlignment>>(
    `${base(runId)}/alignment${query(options)}`,
    { capability: CAPABILITY },
  )
}
