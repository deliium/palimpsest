<script lang="ts">
  import { ApiClientError } from '../api/client'
  import {
    getScientificHypothesesSummary,
    getScientificHypotheses,
    getScientificHypothesisEvidence,
    getScientificHypothesisTests,
    getScientificHypothesisRevisions,
    getScientificHypothesisSources,
    getScientificHypothesisCoverage,
    type ScientificHypothesesSummary,
    type ScientificHypothesisRow,
    type ScientificHypothesisEvidenceRow,
    type ScientificHypothesisTestRow,
    type ScientificHypothesisRevisionRow,
    type ScientificHypothesisSourceRow,
    type ScientificHypothesisCoverageRow,
  } from '../api/scientificHypotheses'
  import type { ResearchSelection } from '../research/selection'

  interface Props {
    runId: string
    selection: ResearchSelection
  }

  let { runId }: Props = $props()

  type Status = 'loading' | 'ready' | 'empty' | 'unavailable' | 'error'
  let status = $state<Status>('loading')
  let reason = $state<string | null>(null)
  let summary = $state<ScientificHypothesesSummary | null>(null)
  let hypotheses = $state<ScientificHypothesisRow[]>([])
  let evidence = $state<ScientificHypothesisEvidenceRow[]>([])
  let tests = $state<ScientificHypothesisTestRow[]>([])
  let revisions = $state<ScientificHypothesisRevisionRow[]>([])
  let sources = $state<ScientificHypothesisSourceRow[]>([])
  let coverage = $state<ScientificHypothesisCoverageRow[]>([])

  function pairs(value: [string, string][] | undefined): string {
    return (value ?? []).map(([slot, token]) => `${slot}=${token}`).join(', ')
  }

  async function load(): Promise<void> {
    status = 'loading'
    reason = null
    try {
      summary = await getScientificHypothesesSummary(runId)
      const [h, e, t, r, s, c] = await Promise.all([
        getScientificHypotheses(runId),
        getScientificHypothesisEvidence(runId),
        getScientificHypothesisTests(runId),
        getScientificHypothesisRevisions(runId),
        getScientificHypothesisSources(runId),
        getScientificHypothesisCoverage(runId),
      ])
      hypotheses = h.rows
      evidence = e.rows
      tests = t.rows
      revisions = r.rows
      sources = s.rows
      coverage = c.rows
      status = hypotheses.length > 0 ? 'ready' : 'empty'
    } catch (error) {
      if (error instanceof ApiClientError) {
        reason = error.code
        status =
          error.code === 'scientific_hypotheses_disabled' || error.code === 'http_503'
            ? 'unavailable'
            : 'error'
      } else {
        reason = error instanceof Error ? error.message : 'error'
        status = 'error'
      }
    }
  }

  $effect(() => {
    void runId
    void load()
  })
</script>

<section class="scientific-hypotheses" data-testid="scientific-hypotheses-panel">
  <header>
    <h2>Scientific hypotheses</h2>
    {#if summary}
      <p class="meta">
        {summary.hypothesis_count} hypotheses · {summary.contradicted_count} contradicted ·
        {summary.trial_count} trials · {summary.coverage}
      </p>
    {/if}
  </header>

  {#if status === 'loading'}
    <p>Loading…</p>
  {:else if status === 'unavailable'}
    <p>Scientific hypotheses are disabled.</p>
  {:else if status === 'error'}
    <p>Unable to load scientific hypotheses: {reason ?? 'error'}</p>
  {:else if status === 'empty'}
    <p>No scientific hypotheses were published for this run.</p>
  {:else}
    {#if summary}
      <section data-testid="scientific-hypotheses-summary">
        <h3>Summary</h3>
        <p>
          window {summary.window_tick} · active {summary.active_count} ·
          supported {summary.supported_count} · contradicted {summary.contradicted_count} ·
          inconclusive {summary.inconclusive_count} · revisions {summary.revision_count}
        </p>
      </section>
    {/if}

    <section data-testid="scientific-hypotheses-hypotheses">
      <h3>Hypotheses</h3>
      <table>
        <thead>
          <tr>
            <th>Claim</th><th>Lineage</th><th>Prediction</th><th>Confidence</th>
            <th>Status</th><th>Source</th><th>Created</th><th>Conditions</th>
          </tr>
        </thead>
        <tbody>
          {#each hypotheses as row}
            <tr>
              <td>{row.claim_token}</td>
              <td>{row.causal_hypothesis_token}</td>
              <td>{row.predicted_outcome}</td>
              <td>{row.confidence_milli}/1000</td>
              <td>{row.status}</td>
              <td>{row.source_kind}</td>
              <td>{row.created_tick}</td>
              <td>{pairs(row.condition_pairs)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </section>

    <section data-testid="scientific-hypotheses-evidence">
      <h3>Evidence</h3>
      <ul>
        {#each evidence as row}
          <li>
            {row.hypothesis_token}: support {row.support_observation_count} ·
            contradictions {row.contradiction_count} ·
            events {row.evidence_event_count} · unlinked {row.unlinked_event_count}
          </li>
        {/each}
      </ul>
    </section>

    <section data-testid="scientific-hypotheses-tests">
      <h3>Tests</h3>
      <ul>
        {#each tests as row}
          <li>
            {row.hypothesis_token}: trials {row.trial_count} · matched {row.matched_count} ·
            mismatched {row.mismatched_count} · inconclusive {row.inconclusive_count} ·
            last {row.last_trial_tick}
          </li>
        {/each}
      </ul>
    </section>

    <section data-testid="scientific-hypotheses-revisions">
      <h3>Revisions</h3>
      <ul>
        {#each revisions as row}
          <li>
            #{row.revision_index} at {row.revision_tick} · {row.reason} ·
            {row.claim_token} · {row.predicted_outcome} ·
            {row.confidence_milli}/1000 · {pairs(row.condition_pairs)}
          </li>
        {/each}
      </ul>
    </section>

    <section data-testid="scientific-hypotheses-sources">
      <h3>Sources</h3>
      <ul>
        {#each sources as row}
          <li>
            {row.source_kind}: {row.hypothesis_count} hypotheses · adopted {row.adopted_count}
          </li>
        {/each}
      </ul>
    </section>

    <section data-testid="scientific-hypotheses-coverage">
      <h3>Coverage</h3>
      <ul>
        {#each coverage as row}
          <li>
            window {row.window_index} · events {row.event_count} · owners {row.owner_count} ·
            hypotheses {row.hypothesis_count} · revisions {row.revision_count} ·
            trials {row.trial_count} · {row.coverage} · {row.availability}
          </li>
        {/each}
      </ul>
    </section>
  {/if}
</section>
