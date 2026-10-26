/** Objective collective-project state and retained contribution receipts. */

export type ProjectContribution = {
  actorId: string
  tick: number
  laborUnits: number
  materialCount: number
  itemId: string | null
  identity: string
}

export type ProjectRow = {
  key: string
  projectId: string
  locationId: string
  kind: string
  status: string
  laborProgress: number
  laborRequired: number
  materialProgress: number
  materialRequired: number
  materialKind: string
  acceptedContributionCount: number
  retainedContributions: ProjectContribution[]
  linkedStructureId: string | null
  linkedStructureKind: string | null
  shortageCount: number
  publicActs: Record<string, number>
  boundaryTick: number | null
  detailTruncated: boolean
}

function contributions(value: unknown): ProjectContribution[] {
  if (!Array.isArray(value)) return []
  const result: ProjectContribution[] = []
  for (const raw of value) {
    if (raw === null || typeof raw !== 'object') continue
    const row = raw as Record<string, unknown>
    const actorId = String(row.actor_id ?? '')
    const tick = Number(row.tick ?? 0)
    const labor = Number(row.labor_units ?? 0)
    const material = Number(row.material_count ?? 0)
    const itemId = typeof row.item_id === 'string' ? row.item_id : null
    result.push({
      actorId,
      tick,
      laborUnits: labor,
      materialCount: material,
      itemId,
      identity: [actorId, tick, labor, material, itemId ?? ''].join(':'),
    })
  }
  return result
}

export function projectRows(
  rows: readonly Record<string, unknown>[],
): ProjectRow[] {
  const seen = new Map<string, ProjectRow>()
  for (const row of rows) {
    const context =
      row.context !== null && typeof row.context === 'object'
        ? (row.context as Record<string, unknown>)
        : {}
    const history =
      row.history !== null && typeof row.history === 'object'
        ? (row.history as Record<string, unknown>)
        : {}
    const boundaryTick =
      typeof history.boundary_tick === 'number' ? history.boundary_tick : null
    const projectId = String(row.project_id ?? '')
    const key = `${projectId}:${String(context.row_id ?? '')}:${boundaryTick ?? ''}`
    if (seen.has(key)) continue
    const acts =
      row.public_acts !== null && typeof row.public_acts === 'object'
        ? (row.public_acts as Record<string, unknown>)
        : {}
    seen.set(key, {
      key,
      projectId,
      locationId: String(row.location_id ?? ''),
      kind: String(row.kind ?? ''),
      status: String(row.status ?? ''),
      laborProgress: Number(row.labor_progress ?? 0),
      laborRequired: Number(row.labor_required ?? 0),
      materialProgress: Number(row.material_progress ?? 0),
      materialRequired: Number(row.material_required ?? 0),
      materialKind: String(row.material_kind ?? ''),
      acceptedContributionCount: Number(row.accepted_contribution_count ?? 0),
      retainedContributions: contributions(row.accepted_contributions),
      linkedStructureId:
        typeof row.linked_structure_id === 'string'
          ? row.linked_structure_id
          : null,
      linkedStructureKind:
        typeof row.linked_structure_kind === 'string'
          ? row.linked_structure_kind
          : null,
      shortageCount: Number(row.shortage_count ?? 0),
      publicActs: Object.fromEntries(
        Object.entries(acts).map(([key, value]) => [
          key,
          typeof value === 'number' ? value : 0,
        ]),
      ),
      boundaryTick,
      detailTruncated: context.detail_truncated === true,
    })
  }
  return [...seen.values()]
}

export function sampledProgress(
  rows: readonly ProjectRow[],
): Array<{ tick: number; laborProgress: number; materialProgress: number }> {
  return rows
    .filter(
      (row): row is ProjectRow & { boundaryTick: number } =>
        row.boundaryTick !== null,
    )
    .sort((left, right) => left.boundaryTick - right.boundaryTick)
    .map((row) => ({
      tick: row.boundaryTick,
      laborProgress: row.laborProgress,
      materialProgress: row.materialProgress,
    }))
}

export function progressDifference(
  from: ProjectRow,
  to: ProjectRow,
): { labor: number; material: number } | null {
  if (
    from.projectId !== to.projectId ||
    from.boundaryTick === null ||
    to.boundaryTick === null ||
    to.boundaryTick <= from.boundaryTick
  ) {
    return null
  }
  return {
    labor: to.laborProgress - from.laborProgress,
    material: to.materialProgress - from.materialProgress,
  }
}
