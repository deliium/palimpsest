/** Institution concept/office/episode lanes with owner-qualified identity. */

export type InstitutionLane = 'concept' | 'office' | 'episode'

export type InstitutionTimelineRow = {
  key: string
  lane: InstitutionLane
  ownerId: string | null
  nativeId: string
  kind: string
  status: string
  rowId: string
  nativeOwnerId: string | null
  evidenceTick: number | null
  structuralRevision: string | null
}

export function institutionLane(kind: string): InstitutionLane {
  if (kind === 'office') return 'office'
  if (kind === 'episode') return 'episode'
  return 'concept'
}

export function institutionRows(
  rows: readonly Record<string, unknown>[],
): InstitutionTimelineRow[] {
  return rows.map((row) => {
    const context =
      row.context !== null && typeof row.context === 'object'
        ? (row.context as Record<string, unknown>)
        : {}
    const history =
      row.history !== null && typeof row.history === 'object'
        ? (row.history as Record<string, unknown>)
        : {}
    const kind = String(row.kind ?? 'concept')
    const ownerId = String(row.native_owner_id ?? '') || null
    const nativeId = String(row.native_id ?? row.institution_id ?? '')
    const structuralRevision =
      typeof row.structural_revision === 'string'
        ? row.structural_revision
        : typeof row.native_id === 'string'
          ? row.native_id
          : null
    return {
      key: [
        ownerId ?? 'shared',
        nativeId,
        kind,
        String(context.row_id ?? ''),
        String(row.status ?? ''),
      ].join(':'),
      lane: institutionLane(kind),
      ownerId,
      nativeId,
      kind,
      status: String(row.status ?? '—'),
      rowId: String(context.row_id ?? ''),
      nativeOwnerId: ownerId,
      evidenceTick:
        typeof history.boundary_tick === 'number' ? history.boundary_tick : null,
      structuralRevision,
    }
  })
}

export function laneRows(
  rows: readonly InstitutionTimelineRow[],
  lane: InstitutionLane,
): InstitutionTimelineRow[] {
  return rows
    .filter((row) => row.lane === lane)
    .sort(
      (left, right) =>
        (left.evidenceTick ?? -1) - (right.evidenceTick ?? -1) ||
        left.key.localeCompare(right.key),
    )
}

export function officeClaims(
  rows: readonly InstitutionTimelineRow[],
): InstitutionTimelineRow[] {
  return laneRows(rows, 'office').filter((row) =>
    [
      'recognized',
      'uncertain',
      'vacant',
      'contested',
      'lost',
      'disputed',
      'relinquished',
    ].includes(row.status),
  )
}

export function timelineGaps(
  rows: readonly InstitutionTimelineRow[],
): number[] {
  const ticks = rows
    .map((row) => row.evidenceTick)
    .filter((tick): tick is number => tick !== null)
    .sort((left, right) => left - right)
  const gaps: number[] = []
  for (let index = 1; index < ticks.length; index += 1) {
    const previous = ticks[index - 1]!
    const next = ticks[index]!
    if (next - previous > 1) {
      gaps.push(next)
    }
  }
  return gaps
}

export function focusKindForLane(lane: InstitutionLane): string {
  return lane === 'office' ? 'office' : lane
}
