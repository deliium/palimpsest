import { apiFetch } from './client'

export const CAPABILITY = 'subjective_debug'

export type AccountingLedgersSummary = {
  run_id: string
  publication_id: string
  digest: string
  schema_version: string
  entry_count: number
  record_count: number
  condition_count: number
  flow_count: number
  counterparty_count: number
  alignment_count: number
  window_count: number
  entry_coverage: string
  record_coverage: string
  alignment_coverage: string
  condition_coverage: string
  flow_coverage: string
  counterparty_coverage: string
  truncated: boolean
}

export type AccountingLedgersPage<T> = {
  run_id: string
  publication_id: string
  window_index: number | null
  rows: T[]
  next_cursor: string | null
  coverage: string
}

export type AccountingEntry = {
  entry_token: string
  window_index: number
  record_token: string
  entry_kind: string
  direction: string
  item_kind: string
  quantity: number
  assessment: string
  confidence_milli: number
  first_tick: number
  last_tick: number
}

export type AccountingRecord = {
  record_token: string
  window_index: number
  record_genre: string
  observed_integrity: string
  content_revision: number
  author_token: string
  tick: number
  event_ordinal: number
  copy_generation: number
  tombstoned: boolean
}

export type AccountingCondition = {
  condition: string
  window_index: number
  record_count: number
  share_milli: number
  availability: string
}

export type AccountingFlow = {
  flow_token: string
  window_index: number
  entry_kind: string
  direction: string
  event_count: number
  quantity_sum: number
  owner_count: number
  counterparty_count: number
}

export type AccountingCounterparty = {
  counterparty_token: string
  window_index: number
  entry_count: number
  kinds: string[]
  first_tick: number
  last_tick: number
}

export type AccountingAlignment = {
  alignment_token: string
  window_index: number
  entry_token: string
  alignment: string
  gap_milli: number
  record_token: string
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
  `/v1/simulations/${encodeURIComponent(runId)}/accounting-ledgers`

export function getSummary(runId: string): Promise<AccountingLedgersSummary> {
  return apiFetch<AccountingLedgersSummary>(base(runId), {
    capability: CAPABILITY,
  })
}

export function getEntries(
  runId: string,
  options: PageOptions = {},
): Promise<AccountingLedgersPage<AccountingEntry>> {
  return apiFetch<AccountingLedgersPage<AccountingEntry>>(
    `${base(runId)}/entries${query(options)}`,
    { capability: CAPABILITY },
  )
}

export function getRecords(
  runId: string,
  options: PageOptions = {},
): Promise<AccountingLedgersPage<AccountingRecord>> {
  return apiFetch<AccountingLedgersPage<AccountingRecord>>(
    `${base(runId)}/records${query(options)}`,
    { capability: CAPABILITY },
  )
}

export function getConditions(
  runId: string,
  options: PageOptions = {},
): Promise<AccountingLedgersPage<AccountingCondition>> {
  return apiFetch<AccountingLedgersPage<AccountingCondition>>(
    `${base(runId)}/conditions${query(options)}`,
    { capability: CAPABILITY },
  )
}

export function getFlows(
  runId: string,
  options: PageOptions = {},
): Promise<AccountingLedgersPage<AccountingFlow>> {
  return apiFetch<AccountingLedgersPage<AccountingFlow>>(
    `${base(runId)}/flows${query(options)}`,
    { capability: CAPABILITY },
  )
}

export function getCounterparties(
  runId: string,
  options: PageOptions = {},
): Promise<AccountingLedgersPage<AccountingCounterparty>> {
  return apiFetch<AccountingLedgersPage<AccountingCounterparty>>(
    `${base(runId)}/counterparties${query(options)}`,
    { capability: CAPABILITY },
  )
}

export function getAlignment(
  runId: string,
  options: PageOptions = {},
): Promise<AccountingLedgersPage<AccountingAlignment>> {
  return apiFetch<AccountingLedgersPage<AccountingAlignment>>(
    `${base(runId)}/alignment${query(options)}`,
    { capability: CAPABILITY },
  )
}
