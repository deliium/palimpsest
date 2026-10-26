/** Layout-independent spatial adapters and evidence-grounded anchors. */

export type TopologyNode = {
  id: string
  label: string
  kind: 'location' | 'region' | 'route' | 'group' | 'project' | 'agent' | 'hub'
  meta?: Record<string, string | number | null>
}

export type TopologyEdge = {
  id: string
  source: string
  target: string
  label: string
  evidenceClass: 'objective' | 'analytical' | 'subjective'
}

export type GroundedRow = {
  rowId: string
  locationId: string | null
  historical: boolean
  evidenceTick: number | null
  reason: string | null
}

export function topologyFromMap(input: {
  locations?: readonly Record<string, unknown>[]
  regions?: readonly Record<string, unknown>[]
  routes?: readonly Record<string, unknown>[]
}): { nodes: TopologyNode[]; edges: TopologyEdge[] } {
  const nodes: TopologyNode[] = []
  const edges: TopologyEdge[] = []
  for (const row of input.regions ?? []) {
    const id = String(row.region_id ?? '')
    if (id === '') continue
    nodes.push({
      id,
      label: String(row.region_label ?? id),
      kind: 'region',
      meta: { locations: Number(row.location_count ?? 0) },
    })
    const children = Array.isArray(row.location_ids) ? row.location_ids : []
    for (const child of children) {
      if (typeof child === 'string') {
        edges.push({
          id: `${id}->${child}`,
          source: id,
          target: child,
          label: 'contains',
          evidenceClass: 'objective',
        })
      }
    }
  }
  for (const row of input.locations ?? []) {
    const id = String(row.location_id ?? '')
    if (id === '') continue
    nodes.push({
      id,
      label: id,
      kind: 'location',
      meta: {
        living: Number(row.living_body_count ?? 0),
        registered: Number(row.registered_agent_count ?? 0),
        projects: Number(row.project_count ?? 0),
      },
    })
  }
  for (const row of input.routes ?? []) {
    const a = String(row.endpoint_a ?? '')
    const b = String(row.endpoint_b ?? '')
    if (a === '' || b === '') continue
    edges.push({
      id: String(row.route_id ?? `${a}->${b}`),
      source: a,
      target: b,
      label: `route ${Number(row.duration_ticks ?? 0)}t`,
      evidenceClass: 'objective',
    })
  }
  return { nodes, edges }
}

export function groundAnchors(
  rows: readonly Record<string, unknown>[],
  knownLocations: ReadonlySet<string>,
  boundaryTick: number,
): { located: GroundedRow[]; unlocated: GroundedRow[] } {
  const located: GroundedRow[] = []
  const unlocated: GroundedRow[] = []
  for (const row of rows) {
    const context =
      row.context !== null && typeof row.context === 'object'
        ? (row.context as Record<string, unknown>)
        : {}
    const rowId = String(context.row_id ?? row.journey_id ?? '—')
    const anchors = Array.isArray(context.anchors) ? context.anchors : []
    if (anchors.length === 0) {
      unlocated.push({
        rowId,
        locationId: null,
        historical: false,
        evidenceTick: null,
        reason: 'no_published_anchor',
      })
      continue
    }
    for (const raw of anchors) {
      if (raw === null || typeof raw !== 'object') continue
      const anchor = raw as Record<string, unknown>
      const locationId =
        typeof anchor.location_id === 'string'
          ? anchor.location_id
          : typeof anchor.entity_id === 'string'
            ? anchor.entity_id
            : null
      const evidenceTick =
        typeof anchor.evidence_tick === 'number' ? anchor.evidence_tick : null
      if (locationId === null || !knownLocations.has(locationId)) {
        unlocated.push({
          rowId,
          locationId,
          historical: false,
          evidenceTick,
          reason: 'missing_regional_layout',
        })
        continue
      }
      located.push({
        rowId,
        locationId,
        historical: evidenceTick !== null && evidenceTick < boundaryTick,
        evidenceTick,
        reason: null,
      })
    }
  }
  return { located, unlocated }
}

function windowKey(row: Record<string, unknown>): string {
  const history =
    row.history !== null && typeof row.history === 'object'
      ? (row.history as Record<string, unknown>)
      : {}
  const window =
    history.window !== null && typeof history.window === 'object'
      ? (history.window as Record<string, unknown>)
      : {}
  return `${String(window.start_tick ?? '')}:${String(window.end_tick ?? '')}:${String(history.boundary_tick ?? '')}`
}

export type MigrationRow = {
  key: string
  journeyId: string
  routeId: string
  origin: string
  destination: string
  phase: string
  participantCount: number
  participants: string[]
  startedTick: number | null
  arrivedTick: number | null
  endedTick: number | null
  startCount: number
  arrivalCount: number
  capacityWaitCount: number
  endedCount: number
  boundaryTick: number | null
  window: { start: number | null; end: number | null }
}

export function migrationRows(
  rows: readonly Record<string, unknown>[],
): MigrationRow[] {
  const seen = new Map<string, MigrationRow>()
  for (const row of rows) {
    const context =
      row.context !== null && typeof row.context === 'object'
        ? (row.context as Record<string, unknown>)
        : {}
    const history =
      row.history !== null && typeof row.history === 'object'
        ? (row.history as Record<string, unknown>)
        : {}
    const window =
      history.window !== null && typeof history.window === 'object'
        ? (history.window as Record<string, unknown>)
        : {}
    const journeyId = String(row.journey_id ?? '')
    const key = `${String(context.row_id ?? '')}:${journeyId}:${windowKey(row)}`
    if (seen.has(key)) continue
    seen.set(key, {
      key,
      journeyId,
      routeId: String(row.route_id ?? ''),
      origin: String(row.origin_location_id ?? ''),
      destination: String(row.destination_location_id ?? ''),
      phase: String(row.phase ?? ''),
      participantCount: Number(row.participant_count ?? 0),
      participants: Array.isArray(row.participant_ids)
        ? row.participant_ids.filter((item): item is string => typeof item === 'string')
        : [],
      startedTick: typeof row.started_tick === 'number' ? row.started_tick : null,
      arrivedTick: typeof row.arrived_tick === 'number' ? row.arrived_tick : null,
      endedTick: typeof row.ended_tick === 'number' ? row.ended_tick : null,
      startCount: Number(row.start_count ?? 0),
      arrivalCount: Number(row.arrival_count ?? 0),
      capacityWaitCount: Number(row.capacity_wait_count ?? 0),
      endedCount: Number(row.ended_count ?? 0),
      boundaryTick:
        typeof history.boundary_tick === 'number' ? history.boundary_tick : null,
      window: {
        start: typeof window.start_tick === 'number' ? window.start_tick : null,
        end: typeof window.end_tick === 'number' ? window.end_tick : null,
      },
    })
  }
  return [...seen.values()]
}

export type SocietyGroup = {
  groupId: string
  basis: string
  memberCount: number
  members: string[]
  missingLanes: string[]
  policyVersion: string | null
  boundaryTick: number | null
  rowId: string
}

export function societyGroups(
  rows: readonly Record<string, unknown>[],
): SocietyGroup[] {
  return rows.map((row) => {
    const context =
      row.context !== null && typeof row.context === 'object'
        ? (row.context as Record<string, unknown>)
        : {}
    const history =
      row.history !== null && typeof row.history === 'object'
        ? (row.history as Record<string, unknown>)
        : {}
    return {
      groupId: String(row.group_id ?? ''),
      basis: String(row.basis ?? ''),
      memberCount: Number(row.member_count ?? 0),
      members: Array.isArray(row.member_ids)
        ? row.member_ids.filter((item): item is string => typeof item === 'string')
        : [],
      missingLanes: Array.isArray(row.missing_lanes)
        ? row.missing_lanes.filter((item): item is string => typeof item === 'string')
        : [],
      policyVersion:
        typeof history.policy_version === 'string' ? history.policy_version : null,
      boundaryTick:
        typeof history.boundary_tick === 'number' ? history.boundary_tick : null,
      rowId: String(context.row_id ?? ''),
    }
  })
}
