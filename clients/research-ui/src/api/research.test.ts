import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { saveCredentials } from '../auth/credentials'
import { ApiClientError } from './client'
import {
  ResearchResolutionError,
  decodeMetricPayloadBase64,
  getCivilizationCatalogue,
  getCulturalEvidence,
  getDemographics,
  getLineageFamilies,
  getLineageNodes,
  getSemanticHistory,
  metricDocumentKey,
  readCulturalCellMetrics,
  readCulturalComparison,
  resolveLineageNode,
} from './research'
import { ResearchSchemaError } from './researchSchemas'

const digest = 'a'.repeat(64)
const fingerprint = 'b'.repeat(64)
const calls: Array<{ url: string; init: RequestInit }> = []

function respond(body: unknown, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'content-type': 'application/json', ...headers },
  })
}

function stub(handler: (url: string) => Response): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
      const url = String(input)
      calls.push({ url, init })
      return handler(url)
    }),
  )
}

function demographics(): Record<string, unknown> {
  return {
    schema_version: 'observer-demographics-v1',
    run_id: 'run-1',
    requested_tick: 0,
    requested_through_sequence: null,
    resolved_tick: 0,
    revision: 1,
    evidence_class: 'objective',
    availability: 'available',
    reason_code: null,
    section: 'generations',
    selection_state: 'all',
    population: { living: 3, admitted: 4, dead: 1, max_generation_index: 1 },
    stage_counts_truncated: false,
    stage_rows: [{ stage: 'adult', life_status: 'alive', count: 3 }],
    agents: [],
    cohorts: [],
    generations: [{ generation_index: 0, admitted: 4, living: 3, dead: 1 }],
    next_after_agent_id: null,
    next_after_group_key: null,
    limit: 100,
  }
}

function snapshot(): Record<string, unknown> {
  return {
    publication_id: 'pub-1',
    digest,
    boundary_tick: 10,
    schema_version: 'lineage-snapshot-v1',
  }
}

function nodeRef(): Record<string, unknown> {
  return {
    run_id: 'run-1',
    family: 'knowledge',
    evidence_class: 'analytical',
    native_kind: 'knowledge_entry',
    native_id: 'entry-1',
    identity_owner: 'agent-bob',
    key: digest,
  }
}

function nodePage(): Record<string, unknown> {
  return {
    schema_version: 'lineage-node-list-v1',
    snapshot: snapshot(),
    items: [
      {
        ref: nodeRef(),
        state: 'present',
        living: true,
        observed_tick: 9,
        evidence_refs: [],
        counts: {},
      },
    ],
    matched_node_keys: [digest],
    context_only_node_keys: [],
    declared_count: 1,
    next_cursor: null,
    coverage: { state: 'complete' },
    requested_boundary_tick: 10,
    captured_boundary_tick: 10,
    effective_page_size: 100,
  }
}

function graphPage(): Record<string, unknown> {
  return {
    schema_version: 'lineage-graph-page-v1',
    root: nodeRef(),
    snapshot: snapshot(),
    nodes: [
      {
        ref: nodeRef(),
        state: 'present',
        living: true,
        observed_tick: 9,
        evidence_refs: [],
        counts: {},
      },
    ],
    edges: [],
    matched_node_keys: [digest],
    context_only_node_keys: [],
    visited_node_count: 1,
    visited_edge_count: 0,
    stop_reasons: [],
    coverage: { state: 'complete' },
    next_cursor: null,
    requested_boundary_tick: 10,
    captured_boundary_tick: 10,
    effective_max_depth: 4,
    effective_max_nodes: 200,
    effective_max_edges: 500,
    effective_page_size: 100,
  }
}

beforeEach(() => {
  calls.length = 0
  saveCredentials({
    simulation_control: '',
    objective_inspection: 'inspect-secret',
    agent_visible: '',
    subjective_debug: 'debug-secret',
  })
})

afterEach(() => {
  vi.unstubAllGlobals()
  saveCredentials({
    simulation_control: '',
    objective_inspection: '',
    agent_visible: '',
    subjective_debug: '',
  })
})

describe('typed research reads', () => {
  it('selects inspection and escapes identifiers', async () => {
    stub(() => respond(demographics()))
    const result = await getDemographics('run/one', { section: 'generations' })
    expect(result.population?.living).toBe(3)
    expect(calls[0]?.url).toContain(
      '/v1/simulations/run%2Fone/observer/demographics',
    )
    expect(
      (calls[0]?.init.headers as Record<string, string>)['x-palimpsest-token'],
    ).toBe('inspect-secret')
  })

  it('rejects unknown schema versions', async () => {
    stub(() => respond({ ...demographics(), schema_version: 'v2' }))
    await expect(getDemographics('run-1')).rejects.toBeInstanceOf(
      ResearchSchemaError,
    )
  })

  it('uses debug for restricted lineage descriptors and bare arrays', async () => {
    stub(() =>
      respond([
        {
          family: 'knowledge',
          available_classes: ['subjective', 'analytical'],
          owner_required: false,
          directions: ['both'],
          max_depth: 4,
          max_nodes: 200,
          max_edges: 500,
          max_page_size: 100,
        },
      ]),
    )
    const families = await getLineageFamilies('run-1', true)
    expect(families[0]?.family).toBe('knowledge')
    expect(calls[0]?.url).toContain('include_restricted=true')
    expect(
      (calls[0]?.init.headers as Record<string, string>)['x-palimpsest-token'],
    ).toBe('debug-secret')
  })

  it('omits scope owner for analytical lineage', async () => {
    stub(() => respond(nodePage()))
    await getLineageNodes(
      'run-1',
      { family: 'knowledge', evidenceClass: 'analytical', ownerId: 'scope-owner' },
      { nativeKind: 'knowledge_entry', nativeId: 'entry-1' },
    )
    expect(calls[0]?.url).not.toContain('owner_id')
    expect(calls[0]?.url).not.toContain('identity_owner')
    expect(calls[0]?.url).not.toContain('publication_id')
    expect(
      (calls[0]?.init.headers as Record<string, string>)['x-palimpsest-token'],
    ).toBe('debug-secret')
  })

  it('resolves publication discovery through snapshots and verifies exact root', async () => {
    stub((url) => {
      if (url.includes('/snapshots')) {
        return respond({
          schema_version: 'lineage-snapshot-list-v1',
          items: [snapshot()],
          declared_count: 1,
          next_cursor: null,
          coverage: { state: 'complete' },
        })
      }
      return respond(graphPage())
    })
    const resolved = await resolveLineageNode({
      runId: 'run-1',
      family: 'knowledge',
      evidenceClass: 'analytical',
      publicationId: 'pub-1',
      nativeKind: 'knowledge_entry',
      nativeId: 'entry-1',
      identityOwner: 'agent-bob',
      nodeKey: digest,
    })
    expect(resolved.node.key).toBe(digest)
    expect(resolved.graph?.schema_version).toBe('lineage-graph-page-v1')
    expect(calls.some((call) => call.url.includes('/traverse'))).toBe(true)
  })

  it('rejects a mismatched returned snapshot', async () => {
    stub((url) => {
      if (url.includes('/snapshots')) {
        return respond({
          schema_version: 'lineage-snapshot-list-v1',
          items: [snapshot()],
          declared_count: 1,
          next_cursor: null,
          coverage: { state: 'complete' },
        })
      }
      const graph = graphPage()
      graph.snapshot = { ...snapshot(), digest: 'c'.repeat(64) }
      return respond(graph)
    })
    await expect(
      resolveLineageNode({
        runId: 'run-1',
        family: 'knowledge',
        evidenceClass: 'analytical',
        publicationId: 'pub-1',
        nativeKind: 'knowledge_entry',
        nativeId: 'entry-1',
        nodeKey: digest,
      }),
    ).rejects.toBeInstanceOf(ResearchResolutionError)
  })

  it('uses debug for subjective civilization concepts and forwards publication', async () => {
    stub(() =>
      respond({
        schema_version: 'observer-civilization-catalogue-v1',
        run_id: 'run-1',
        availability: 'available',
        publication: null,
        boundaries: [],
        next_cursor: null,
        truncated: false,
      }),
    )
    await getCivilizationCatalogue('run-1', {
      evidenceClass: 'SUBJECTIVE',
      ownerId: 'agent-a',
      layer: 'institutions',
    })
    expect(calls[0]?.url).toContain('evidence_class=SUBJECTIVE')
    expect(calls[0]?.url).toContain('owner_id=agent-a')
    expect(
      (calls[0]?.init.headers as Record<string, string>)['x-palimpsest-token'],
    ).toBe('debug-secret')
  })

  it('preserves cultural binding headers and rejects a missing header', async () => {
    stub(() =>
      respond(
        {
          schema_version: 'cultural-metric-comparison-v1',
          matrix_fingerprint: fingerprint,
          confidence: 0.95,
          method: 'student_t_seed_block_mean',
          conditions: [],
          contrasts: [],
          excluded_cells: [],
          reasons: [],
        },
        { 'X-Palimpsest-Artifact-Binding': 'legacy_unverified' },
      ),
    )
    const document = await readCulturalComparison('matrix-1')
    expect(document.binding).toBe('legacy_unverified')

    vi.unstubAllGlobals()
    stub(() =>
      respond({
        schema_version: 'cultural-metric-comparison-v1',
        matrix_fingerprint: fingerprint,
        confidence: 0.95,
        method: 'student_t_seed_block_mean',
        conditions: [],
        contrasts: [],
        excluded_cells: [],
        reasons: [],
      }),
    )
    await expect(readCulturalComparison('matrix-1')).rejects.toBeInstanceOf(
      ResearchSchemaError,
    )
  })

  it('validates nested rows_json inside cell metrics', async () => {
    const payload = {
      schema_version: 'cultural-cell-metrics-v1',
      cell_id: 'cell-a',
      matrix_fingerprint: fingerprint,
      cell_fingerprint: fingerprint,
      config_fingerprint: fingerprint,
      run_id: 'run-1',
      capture_policy: { enabled: true, max_frames: 1, max_rows: 1 },
      analysis_window: { baseline_boundary: 0, end_boundary: 1 },
      evidence_digest: digest,
      documents: [{ values: { rows_json: '[{"a":1,"a":2}]' } }],
      digest,
    }
    stub(() =>
      respond(payload, { 'X-Palimpsest-Artifact-Binding': 'runtime_bound' }),
    )
    await expect(
      readCulturalCellMetrics('matrix-1', 'cell-a'),
    ).rejects.toBeInstanceOf(ResearchSchemaError)
  })

  it('decodes Unicode base64 metric payloads and keys distinct metric sets', () => {
    const text = JSON.stringify({ label: 'café ☕' })
    const bytes = new TextEncoder().encode(text)
    let binary = ''
    for (const byte of bytes) {
      binary += String.fromCharCode(byte)
    }
    const decoded = decodeMetricPayloadBase64(btoa(binary)) as {
      label: string
    }
    expect(decoded.label).toBe('café ☕')
    expect(
      metricDocumentKey({
        metric_set_id: 'set-1',
        metric_family: 'cultural_trait_dynamics',
        schema_version: '1',
      }),
    ).not.toBe(
      metricDocumentKey({
        metric_set_id: 'set-2',
        metric_family: 'cultural_trait_dynamics',
        schema_version: '1',
      }),
    )
  })

  it('keeps semantic history unavailable states distinct', async () => {
    stub(() =>
      respond({
        schema_version: 'observer-semantic-history-v1',
        run_id: 'run-1',
        agent_id: 'agent-a',
        source: 'label',
        requested_tick: null,
        checkpoint_tick: null,
        history_first_tick: null,
        history_last_tick: null,
        retained_only: true,
        prefix_complete: false,
        availability: 'unavailable',
        reason: 'checkpoint_unavailable',
        terms: [],
        rows: [],
        next_cursor: null,
        count: 0,
      }),
    )
    const history = await getSemanticHistory('run-1', 'agent-a', {
      source: 'label',
    })
    expect(history.availability).toBe('unavailable')
    expect(history.reason).toBe('checkpoint_unavailable')
  })

  it('keeps empty evidence pages as partial when continuation remains', async () => {
    stub(() =>
      respond({
        schema_version: 'research-cultural-evidence-page-v1',
        run_id: 'run-1',
        matrix_id: 'matrix-1',
        cell_id: 'cell-a',
        section: 'traits',
        artifact_digest: digest,
        source_revision: 'rev-1',
        binding_state: 'runtime_bound',
        requested_window: { from_tick: null, to_tick: null },
        capture_status: {},
        gaps: [],
        rows: [],
        next_cursor: 'cursor-1',
        truncated: true,
        coverage: null,
      }),
    )
    const page = await getCulturalEvidence('matrix-1', 'cell-a', {
      section: 'traits',
    })
    expect(page.rows).toEqual([])
    expect(page.next_cursor).toBe('cursor-1')
  })

  it('keeps ApiClientError status and safe code', async () => {
    stub(
      () =>
        new Response(JSON.stringify({ code: 'forbidden' }), {
          status: 403,
          headers: { 'content-type': 'application/problem+json' },
        }),
    )
    await expect(getDemographics('run-1')).rejects.toMatchObject({
      code: 'forbidden',
      status: 403,
    })
    await expect(getDemographics('run-1')).rejects.toBeInstanceOf(ApiClientError)
  })
})
