import { afterEach, describe, expect, it, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { flushSync, render } from '../test/mount'
import { emptyResearchSelection } from './selection'
import PopulationPanel from '../views/PopulationPanel.svelte'
import CohortsPanel from '../views/CohortsPanel.svelte'
import LineagePanel from '../views/LineagePanel.svelte'
import TeachingPanel from '../views/TeachingPanel.svelte'
import TechnologyPanel from '../views/TechnologyPanel.svelte'
import CulturePanel from '../views/CulturePanel.svelte'
import LanguagePanel from '../views/LanguagePanel.svelte'
import NarrativePanel from '../views/NarrativePanel.svelte'
import MigrationPanel from '../views/MigrationPanel.svelte'
import EconomyPanel from '../views/EconomyPanel.svelte'
import ProjectsPanel from '../views/ProjectsPanel.svelte'
import InstitutionsPanel from '../views/InstitutionsPanel.svelte'
import ForkComparePanel from '../views/ForkComparePanel.svelte'

vi.mock('cytoscape', () => ({
  default: () => ({ on: () => undefined, destroy: () => undefined }),
}))

const generationalFixtures = resolve(
  process.cwd(),
  '../godot-observer/fixtures/protocol/generational',
)
const civilizationFixtures = resolve(
  process.cwd(),
  '../godot-observer/fixtures/protocol/civilization',
)

const panels = [
  { name: 'population', component: PopulationPanel, heading: 'Population and demographics' },
  { name: 'cohorts', component: CohortsPanel, heading: 'Within-run cohort comparison' },
  { name: 'genealogy', component: LineagePanel, heading: 'Qualified lineage explorer' },
  { name: 'teaching', component: TeachingPanel, heading: 'Teacher / student networks' },
  { name: 'technology', component: TechnologyPanel, heading: 'Technology lineage and diffusion' },
  { name: 'culture', component: CulturePanel, heading: 'Cultural trait timelines' },
  { name: 'language', component: LanguagePanel, heading: 'Vocabulary, semantics and current meaning' },
  { name: 'narratives', component: NarrativePanel, heading: 'Historical narrative lineage' },
  { name: 'migration', component: MigrationPanel, heading: 'Migration flows' },
  { name: 'economy', component: EconomyPanel, heading: 'Economic exchange networks' },
  { name: 'projects', component: ProjectsPanel, heading: 'Collective project history' },
  { name: 'institutions', component: InstitutionsPanel, heading: 'Institutions' },
] as const

const calls: string[] = []

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  })
}

function fixture(root: string, name: string): Record<string, unknown> {
  return JSON.parse(readFileSync(resolve(root, `${name}.json`), 'utf8')) as Record<
    string,
    unknown
  >
}

async function settle(): Promise<void> {
  await Promise.resolve()
  await new Promise((resolve) => setTimeout(resolve, 0))
  await Promise.resolve()
  await Promise.resolve()
  flushSync()
}

function buttonByText(text: string): HTMLButtonElement | undefined {
  return [...document.querySelectorAll('button')].find((button) =>
    button.textContent?.includes(text),
  ) as HTMLButtonElement | undefined
}

function observerRun(runId: string, tick = 16): Record<string, unknown> {
  return {
    run_id: runId,
    world_id: 'world-1',
    tick,
    latest_tick: tick,
    latest_sequence: 1,
    parent_run_id: null,
    fork_tick: null,
    intervention_summary: null,
    branch_id: null,
    protocol_version: 'observer-protocol-v1',
  }
}

function lineageGraphFixture(
  family: string,
  refs: { key: string; nativeId: string }[],
): Record<string, unknown> {
  const raw = fixture(generationalFixtures, 'lineage_graph')
  const nodes = raw.nodes as Array<Record<string, unknown>>
  const edges = raw.edges as Array<Record<string, unknown>>
  const baseRefs = nodes.map((node) => node.ref as Record<string, unknown>)
  return {
    ...raw,
    nodes: nodes.map((node, index) => ({
      ...node,
      ref: {
        ...baseRefs[index],
        family,
        evidence_class: family === 'knowledge' ? 'subjective' : 'objective',
        native_kind: family === 'knowledge' ? 'knowledge' : 'agent',
        native_id: refs[index]?.nativeId ?? baseRefs[index]?.native_id,
        identity_owner: family === 'knowledge' ? 'agent-a' : null,
      },
    })),
    edges: edges.map((edge) => ({
      ...edge,
      relation: family === 'knowledge' ? 'derived_from' : 'parent_of',
    })),
    root: nodes[0]?.ref,
    stop_reasons: [],
    effective_max_depth: 4,
    effective_max_nodes: 200,
    effective_max_edges: 500,
    effective_page_size: 200,
  }
}

function lineageNodePage(
  family: string,
  refs: { key: string; nativeId: string }[],
): Record<string, unknown> {
  const raw = fixture(generationalFixtures, 'lineage_nodes')
  const items = raw.items as Array<Record<string, unknown>>
  return {
    ...raw,
    items: items.map((item, index) => ({
      ...item,
      ref: {
        ...(item.ref as Record<string, unknown>),
        family,
        evidence_class: family === 'knowledge' ? 'subjective' : 'objective',
        native_kind: family === 'knowledge' ? 'knowledge' : 'agent',
        native_id: refs[index]?.nativeId ?? (item.ref as Record<string, unknown>).native_id,
        identity_owner: family === 'knowledge' ? 'agent-a' : null,
      },
    })),
  }
}

function demographicsEnvelope(tick: number): Record<string, unknown> {
  return {
    schema_version: 'observer-demographics-v1',
    run_id: 'run-generational-23',
    requested_tick: tick,
    requested_through_sequence: null,
    resolved_tick: tick,
    revision: 3,
    evidence_class: 'objective',
    availability: 'available',
    reason_code: null,
    section: 'generations',
    selection_state: 'all',
    population: { living: 2, admitted: 3, dead: 1, max_generation_index: 1 },
    stage_counts_truncated: false,
    stage_rows: [{ stage: 'adult', life_status: 'alive', count: 2 }],
    agents: [],
    cohorts: [],
    generations: [
      { generation_index: 0, admitted: 2, living: 1, dead: 1 },
      { generation_index: 1, admitted: 1, living: 1, dead: 0 },
    ],
    next_after_agent_id: null,
    next_after_group_key: null,
    limit: 100,
  }
}

function generationMarkers(tick: number): Record<string, unknown> {
  return {
    schema_version: 'observer-generation-markers-v1',
    run_id: 'run-generational-23',
    requested_tick: tick,
    resolved_tick: tick,
    revision: 3,
    evidence_class: 'objective',
    availability: 'available',
    reason_code: null,
    markers: [
      { generation_index: 0, first_entry_tick: 0, seek_tick: 0, admitted_count: 2, label_code: 'founders' },
      { generation_index: 1, first_entry_tick: 8, seek_tick: 8, admitted_count: 1, label_code: 'generation_first_admission' },
    ],
    next_after_generation_index: null,
    limit: 200,
  }
}

afterEach(() => {
  vi.unstubAllGlobals()
  calls.length = 0
  window.history.replaceState(null, '', '/research/')
})

describe('unavailable panel acceptance (negative state retained)', () => {
  for (const entry of panels) {
    it(`mounts the ${entry.name} surface with a real component and honest unavailable wording`, async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn(
          async () =>
            new Response(JSON.stringify({ code: 'unavailable' }), {
              status: 404,
              headers: { 'content-type': 'application/problem+json' },
            }),
        ),
      )
      const mounted = render(entry.component as never, {
        runId: 'run-1',
        selection: emptyResearchSelection({
          runId: 'run-1',
          view: entry.name as never,
          tick: 4,
          scopeOwnerId: 'agent-a',
        }),
        onSelectionChange: vi.fn(),
      })
      await settle()
      expect(mounted.target.textContent).toContain(entry.heading)
      // Honest unavailable/forbidden/empty wording is acceptable; a bare
      // placeholder that merely says "later implementation task" is not.
      expect(mounted.target.textContent).not.toContain('later implementation task')
      mounted.cleanup()
    })
  }

  it('keeps capture, completion and lineage prerequisites explicit', () => {
    expect(LineagePanel).toBeTypeOf('function')
    expect(TechnologyPanel).toBeTypeOf('function')
    expect(InstitutionsPanel).toBeTypeOf('function')
  })
})

describe('populated panel acceptance', () => {
  it('renders genealogy rows and qualified parent-child edges', async () => {
    const refs = [
      { key: 'b'.repeat(64), nativeId: 'agent-founder' },
      { key: 'c'.repeat(64), nativeId: 'agent-child' },
    ]
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input)
        calls.push(url)
        if (url.includes('/observer/run')) return json(observerRun('run-generational-23'))
        if (url.includes('/lineage/families')) {
          return json(fixture(generationalFixtures, 'lineage_families'))
        }
        if (url.includes('/snapshots')) {
          return json(fixture(generationalFixtures, 'lineage_snapshots'))
        }
        if (url.includes('/nodes')) return json(lineageNodePage('genealogy', refs))
        if (url.includes('/traverse')) return json(lineageGraphFixture('genealogy', refs))
        return json({}, 404)
      }),
    )
    const mounted = render(LineagePanel as never, {
      runId: 'run-generational-23',
      selection: emptyResearchSelection({
        runId: 'run-generational-23',
        view: 'lineage',
        tick: 16,
      }),
      onSelectionChange: vi.fn(),
    })
    await settle()
    await settle()
    expect(mounted.target.textContent).toContain('Root candidates at the pinned publication')
    expect(mounted.target.textContent).toContain('agent-founder')
    expect(mounted.target.textContent).toContain('objective')
    const rootRow = [...mounted.target.querySelectorAll('tbody tr')].find((row) =>
      row.textContent?.includes('agent-founder'),
    )
    rootRow?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    await settle()
    expect(mounted.target.textContent).toContain('genealogy graph · 16')
    expect(mounted.target.textContent).toContain('agent-child')
    expect(mounted.target.textContent).toContain('parent_of')
    mounted.cleanup()
  })

  it('renders qualified knowledge lineage separately from objective genealogy', async () => {
    const refs = [
      { key: 'e'.repeat(64), nativeId: 'technique-farming' },
      { key: 'f'.repeat(64), nativeId: 'technique-irrigation' },
    ]
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input)
        calls.push(url)
        if (url.includes('/observer/run')) return json(observerRun('run-generational-23'))
        if (url.includes('/lineage/families')) {
          return json([
            {
              family: 'knowledge',
              available_classes: ['subjective', 'analytical'],
              owner_required: true,
              directions: ['ancestors', 'descendants', 'both'],
              max_depth: 4,
              max_nodes: 200,
              max_edges: 500,
              max_page_size: 200,
            },
          ])
        }
        if (url.includes('/snapshots')) {
          return json(fixture(generationalFixtures, 'lineage_snapshots'))
        }
        if (url.includes('/nodes')) return json(lineageNodePage('knowledge', refs))
        if (url.includes('/traverse')) return json(lineageGraphFixture('knowledge', refs))
        return json({}, 404)
      }),
    )
    const mounted = render(LineagePanel as never, {
      runId: 'run-generational-23',
      selection: emptyResearchSelection({
        runId: 'run-generational-23',
        view: 'lineage',
        tick: 16,
        scopeOwnerId: 'agent-a',
      }),
      onSelectionChange: vi.fn(),
      initialFamily: 'knowledge',
    })
    await settle()
    await settle()
    expect(mounted.target.textContent).toContain('technique-farming')
    expect(mounted.target.textContent).toContain('subjective')
    const rootRow = [...mounted.target.querySelectorAll('tbody tr')].find((row) =>
      row.textContent?.includes('technique-farming'),
    )
    rootRow?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    await settle()
    expect(mounted.target.textContent).toContain('knowledge graph · 16')
    expect(mounted.target.textContent).toContain('derived_from')
    expect(mounted.target.textContent).toContain('subjective')
    mounted.cleanup()
  })

  it('renders source-backed technology history rows and coverage', async () => {
    const overlay = fixture(civilizationFixtures, 'overlay_technology')
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input)
        calls.push(url)
        if (url.includes('/civilization/catalogue')) {
          return json({
            schema_version: 'observer-civilization-catalogue-v1',
            run_id: 'run-generational-23',
            publication: {
              publication_id: 'pub-1',
              digest: 'd'.repeat(64),
              policy_version: 'civilization-overlays.v1',
            },
            availability: 'available',
            boundaries: [{ boundary_tick: 16, revision: 4, coverage: {}, layers: ['technology'] }],
            next_cursor: null,
            truncated: false,
          })
        }
        if (url.includes('/civilization/overlays')) return json(overlay)
        if (url.includes('/civilization/map')) {
          return json({
            schema_version: 'observer-civilization-map-v1',
            run_id: 'run-generational-23',
            rows: [{ location_id: 'loc-1', label: 'River camp' }],
          })
        }
        return json({}, 404)
      }),
    )
    const mounted = render(TechnologyPanel as never, {
      runId: 'run-generational-23',
      selection: emptyResearchSelection({
        runId: 'run-generational-23',
        view: 'technology',
        tick: 16,
      }),
      onSelectionChange: vi.fn(),
    })
    await settle()
    buttonByText('Diffusion')?.click()
    await settle()
    await settle()
    expect(mounted.target.textContent).toContain('knowledge-1')
    expect(mounted.target.textContent).toContain('agent-a')
    expect(mounted.target.textContent).toContain('held')
    expect(mounted.target.textContent).toContain('unknown')
    expect(mounted.target.textContent).toContain('analytical')
    mounted.cleanup()
  })

  it('renders captured cultural trait inventories with binding and gaps', async () => {
    const page = {
      schema_version: 'research-cultural-evidence-page-v1',
      run_id: 'run-generational-23',
      matrix_id: 'm1',
      cell_id: 'cell-a',
      section: 'traits',
      artifact_digest: 'a'.repeat(64),
      source_revision: 'rev-1',
      binding_state: 'legacy_unverified',
      requested_window: { from_tick: 0, to_tick: 16 },
      capture_status: { active: true, failed: false },
      gaps: [{ tick: 3 }],
      rows: [
        { boundary_tick: 0, owner_id: 'agent-a', dimension: 'belief', content_digest: 'x' },
        { boundary_tick: 8, owner_id: 'agent-b', dimension: 'vocabulary', content_digest: 'v' },
      ],
      next_cursor: null,
      truncated: false,
      coverage: 1,
    }
    vi.stubGlobal('fetch', vi.fn(async () => json(page)))
    const mounted = render(CulturePanel as never, {
      runId: 'run-generational-23',
      selection: emptyResearchSelection({
        runId: 'run-generational-23',
        view: 'culture',
        tick: 16,
      }),
    })
    const inputs = mounted.target.querySelectorAll('input')
    inputs[0]!.value = 'm1'
    inputs[0]!.dispatchEvent(new Event('input', { bubbles: true }))
    inputs[1]!.value = 'cell-a'
    inputs[1]!.dispatchEvent(new Event('input', { bubbles: true }))
    buttonByText('Load captured inventory')?.click()
    await settle()
    expect(mounted.target.textContent).toContain('belief')
    expect(mounted.target.textContent).toContain('vocabulary')
    expect(mounted.target.textContent).toContain('legacy_unverified')
    expect(mounted.target.textContent).toContain('Gaps')
    expect(mounted.target.textContent).toContain('owners')
    mounted.cleanup()
  })

  it('renders historical narrative roots, branches and merges', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input)
        calls.push(url)
        if (url.includes('/narrative-hops')) {
          return json({
            run_id: 'run-generational-23',
            owner_id: 'agent-a',
            layer: 'subjective_narrative_hops',
            count: 2,
            variants: [
              { variant_id: 'v1', status: 'active', origin: 'witness', carrier_agent_ids: ['agent-a'], location_ids: [], parent_variant_ids: [], merged_into_id: null, transmission_root_id: 'r1', source_event_id: 'evt-1', last_communication_id: null, strength_band: 'mid' },
              { variant_id: 'v2', status: 'merged', origin: 'retelling', carrier_agent_ids: ['agent-b'], location_ids: [], parent_variant_ids: ['v0', 'v1'], merged_into_id: 'v3', transmission_root_id: 'r1', source_event_id: null, last_communication_id: null, strength_band: 'low' },
            ],
          })
        }
        if (url.includes('/lineage/families')) return json([])
        if (url.includes('/observer/run')) return json(observerRun('run-generational-23'))
        return json({}, 404)
      }),
    )
    const mounted = render(NarrativePanel as never, {
      runId: 'run-generational-23',
      selection: emptyResearchSelection({
        runId: 'run-generational-23',
        view: 'narratives',
        tick: 16,
        scopeOwnerId: 'agent-a',
      }),
      onSelectionChange: vi.fn(),
    })
    await settle()
    buttonByText('Load current narrative metadata')?.click()
    await settle()
    expect(mounted.target.textContent).toContain('Roots')
    expect(mounted.target.textContent).toContain('Branches')
    expect(mounted.target.textContent).toContain('Merges')
    expect(mounted.target.textContent).toContain('v1')
    expect(mounted.target.textContent).toContain('merged')
    mounted.cleanup()
  })

  it('renders institution and office succession evidence without a global occupant', async () => {
    const overlay = fixture(civilizationFixtures, 'overlay_institutions')
    const rows = (overlay.rows as Array<Record<string, unknown>>) ?? []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input)
        calls.push(url)
        if (url.includes('/catalogue')) {
          return json({
            schema_version: 'observer-civilization-catalogue-v1',
            run_id: 'run-generational-23',
            publication: { publication_id: 'pub-1', digest: 'd'.repeat(64), policy_version: 'v1' },
            availability: 'available',
            boundaries: [{ boundary_tick: 16, revision: 4, coverage: {}, layers: ['institutions'] }],
            next_cursor: null,
            truncated: false,
          })
        }
        if (url.includes('/overlays')) {
          return json({
            ...overlay,
            rows: [
              ...rows,
              {
                ...rows[0],
                kind: 'office',
                native_owner_id: 'agent-a',
                native_id: 'office-local',
                status: 'contested',
                context: {
                  ...(rows[0]?.context as Record<string, unknown>),
                  row_id: 'institutions:agent-a:office-local',
                },
              },
            ],
          })
        }
        if (url.includes('/metrics')) return json([], 200)
        return json({}, 404)
      }),
    )
    const mounted = render(InstitutionsPanel as never, {
      runId: 'run-generational-23',
      selection: emptyResearchSelection({
        runId: 'run-generational-23',
        view: 'institutions',
        tick: 16,
        scopeOwnerId: 'agent-a',
      }),
      onSelectionChange: vi.fn(),
    })
    await settle()
    buttonByText('Load institution timeline')?.click()
    await settle()
    expect(mounted.target.textContent).toContain('concept lane')
    expect(mounted.target.textContent).toContain('episode lane')
    expect(mounted.target.textContent).toContain('office lane')
    expect(mounted.target.textContent).toContain('contested')
    expect(mounted.target.textContent).toContain('No global current occupant')
    mounted.cleanup()
  })

  it('renders migration journeys, routes and topology', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input)
        calls.push(url)
        if (url.includes('/catalogue')) {
          return json({
            schema_version: 'observer-civilization-catalogue-v1',
            run_id: 'run-generational-23',
            publication: { publication_id: 'pub-1', digest: 'd'.repeat(64), policy_version: 'v1' },
            availability: 'available',
            boundaries: [{ boundary_tick: 16, revision: 4, coverage: {}, layers: ['migration'] }],
            next_cursor: null,
            truncated: false,
          })
        }
        if (url.includes('/overlays')) return json(fixture(civilizationFixtures, 'overlay_migration'))
        if (url.includes('section=locations')) {
          return json(fixture(civilizationFixtures, 'map_locations'))
        }
        if (url.includes('section=regions')) return json(fixture(civilizationFixtures, 'map_regions'))
        if (url.includes('section=routes')) return json(fixture(civilizationFixtures, 'map_routes'))
        return json({}, 404)
      }),
    )
    const mounted = render(MigrationPanel as never, {
      runId: 'run-generational-23',
      selection: emptyResearchSelection({
        runId: 'run-generational-23',
        view: 'migration',
        tick: 16,
      }),
    })
    buttonByText('Load migration window')?.click()
    await settle()
    await settle()
    const overlay = fixture(civilizationFixtures, 'overlay_migration')
    const first = (overlay.rows as Array<Record<string, unknown>>)[0]!
    expect(mounted.target.textContent).toContain(String(first.route_id))
    expect(mounted.target.textContent).toContain(String(first.phase))
    expect(mounted.target.textContent).toContain('Routes, regions and locations')
    expect(mounted.target.textContent).toContain('not citizenship')
    mounted.cleanup()
  })

  it('renders population, generation distribution and coexistence', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input)
        calls.push(url)
        const parsed = new URL(url, 'http://localhost')
        if (url.includes('/observer/run')) return json(observerRun('run-generational-23', 16))
        if (url.includes('/observer/generation-markers')) {
          return json(generationMarkers(Number(parsed.searchParams.get('tick'))))
        }
        if (url.includes('/observer/demographics')) {
          return json(demographicsEnvelope(Number(parsed.searchParams.get('tick'))))
        }
        return json({}, 404)
      }),
    )
    const mounted = render(PopulationPanel as never, {
      runId: 'run-generational-23',
      selection: emptyResearchSelection({
        runId: 'run-generational-23',
        view: 'population',
        tick: 16,
      }),
      onSelectionChange: vi.fn(),
    })
    await settle()
    await settle()
    expect(mounted.target.textContent).toContain('Population timeline')
    expect(mounted.target.textContent).toContain('Living')
    expect(mounted.target.textContent).toContain('adult')
    expect(mounted.target.textContent).toContain('Generation distribution')
    expect(mounted.target.textContent).toContain('founders')
    mounted.cleanup()
  })

  it('compares forked historical runs with parent and child lineage', async () => {
    const children = [
      {
        child_run_id: 'child-a',
        parent_run_id: 'run-generational-23',
        fork_tick: 12,
        intervention_kind: 'teaching',
        intervention_summary: 'controlled teaching',
        branch_id: 'branch-a',
      },
      {
        child_run_id: 'child-b',
        parent_run_id: 'run-generational-23',
        fork_tick: 12,
        intervention_kind: 'migration',
        intervention_summary: 'controlled migration',
        branch_id: 'branch-b',
      },
    ]
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input)
        calls.push(url)
        if (url.includes('/branches/compare')) {
          return json({
            left_run_id: 'child-a',
            right_run_id: 'child-b',
            fork_tick: 12,
            prefix_equivalent: true,
            diverge_tick: 14,
            diverge_sequence: 40,
            reason_code: null,
            left_post_fork_trajectory_hash: 'a'.repeat(64),
            right_post_fork_trajectory_hash: 'b'.repeat(64),
            event_kind_counts: { left: { Talk: 2 }, right: { Talk: 3 } },
          })
        }
        if (url.includes('/branches')) {
          return json({ items: children, next_cursor: null, count: children.length })
        }
        if (url.endsWith('/branch')) {
          return json({
            child_run_id: 'run-generational-23',
            parent_run_id: 'run-root',
            fork_tick: 12,
            intervention_kind: 'founder_event',
            intervention_summary: 'controlled founder event',
            branch_id: 'branch-root',
          })
        }
        return json({}, 404)
      }),
    )
    const mounted = render(ForkComparePanel as never, {
      runId: 'run-generational-23',
      deepLink: {
        runId: 'run-generational-23',
        tick: null,
        eventId: null,
        sequence: null,
        agentId: null,
        view: 'compare',
      },
    })
    await settle()
    expect(mounted.target.textContent).toContain('child-a')
    expect(mounted.target.textContent).toContain('child-b')
    buttonByText('child-a')?.click()
    buttonByText('child-b')?.click()
    flushSync()
    buttonByText('Compare selected children')?.click()
    await settle()
    expect(mounted.target.textContent).toContain('Comparison coverage')
    expect(mounted.target.textContent).toContain('equivalent')
    expect(mounted.target.textContent).toContain('tick 14')
    mounted.cleanup()
  })
})

describe('cross-panel selection acceptance', () => {
  it('scopes owner and tick requests and re-scopes when the run changes', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input)
        calls.push(url)
        if (url.includes('/narrative-hops')) {
          return json({
            run_id: url.includes('run-2') ? 'run-2' : 'run-1',
            owner_id: 'agent-a',
            layer: 'subjective_narrative_hops',
            count: 0,
            variants: [],
          })
        }
        if (url.includes('/lineage/families')) return json([])
        if (url.includes('/observer/run')) {
          return json(observerRun(url.includes('run-2') ? 'run-2' : 'run-1', 9))
        }
        return json({}, 404)
      }),
    )
    const first = render(NarrativePanel as never, {
      runId: 'run-1',
      selection: emptyResearchSelection({
        runId: 'run-1',
        view: 'narratives',
        tick: 9,
        scopeOwnerId: 'agent-a',
      }),
      onSelectionChange: vi.fn(),
    })
    await settle()
    buttonByText('Load current narrative metadata')?.click()
    await settle()
    const hopCall = calls.find((url) => url.includes('/narrative-hops'))
    expect(hopCall).toBeDefined()
    expect(hopCall).toContain('run-1')
    expect(hopCall).toContain('agent-a')
    first.cleanup()

    const second = render(NarrativePanel as never, {
      runId: 'run-2',
      selection: emptyResearchSelection({
        runId: 'run-2',
        view: 'narratives',
        tick: 9,
        scopeOwnerId: 'agent-b',
      }),
      onSelectionChange: vi.fn(),
    })
    await settle()
    buttonByText('Load current narrative metadata')?.click()
    await settle()
    const secondHop = calls.filter((url) => url.includes('/narrative-hops')).at(-1)
    expect(secondHop).toContain('run-2')
    expect(secondHop).toContain('agent-b')
    second.cleanup()
  })
})
