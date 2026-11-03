<script lang="ts">
  import { ApiClientError } from '../api/client'
  import {
    getFormalRuleCandidate,
    getFormalRuleCandidates,
    getFormalRuleLineage,
    getFormalRuleRules,
    getFormalRuleSummary,
    getFormalRuleVersions,
    type FormalRule,
    type FormalRuleCandidate,
    type FormalRuleCandidateDetail,
    type FormalRuleLineageEdge,
    type FormalRuleSummary,
    type FormalRuleVersion,
  } from '../api/formalRules'
  import type { ResearchSelection } from '../research/selection'

  interface Props {
    runId: string
    selection: ResearchSelection
  }

  let { runId }: Props = $props()

  type Status = 'loading' | 'available' | 'empty' | 'unavailable' | 'error'

  let status = $state<Status>('loading')
  let reason = $state<string | null>(null)
  let summary = $state<FormalRuleSummary | null>(null)
  let candidates = $state<FormalRuleCandidate[]>([])
  let lineage = $state<FormalRuleLineageEdge[]>([])
  let detail = $state<FormalRuleCandidateDetail | null>(null)
  let rules = $state<FormalRule[]>([])
  let versions = $state<FormalRuleVersion[]>([])

  async function load(): Promise<void> {
    status = 'loading'
    reason = null
    detail = null
    try {
      summary = await getFormalRuleSummary(runId)
      const page = await getFormalRuleCandidates(runId, { limit: 200 })
      candidates = page.items
      const edges = await getFormalRuleLineage(runId, { limit: 200 })
      lineage = edges.items
      status = candidates.length === 0 ? 'empty' : 'available'
    } catch (error) {
      if (error instanceof ApiClientError) {
        reason = error.code
        status = error.code === 'formal_rule_disabled' ? 'unavailable' : 'error'
        return
      }
      reason = 'formal_rule_read_failed'
      status = 'error'
    }
  }

  async function selectCandidate(candidateId: string): Promise<void> {
    try {
      detail = await getFormalRuleCandidate(runId, candidateId)
      const rulePage = await getFormalRuleRules(runId, candidateId, { limit: 200 })
      rules = rulePage.items
      const versionPage = await getFormalRuleVersions(runId, candidateId, {
        limit: 200,
      })
      versions = versionPage.items
    } catch (error) {
      reason = error instanceof ApiClientError ? error.code : 'formal_rule_read_failed'
      status = 'error'
    }
  }

  $effect(() => {
    void runId
    void load()
  })
</script>

<section class="formal-rules">
  <header>
    <h1>Formal social rules</h1>
    <p class="note">
      Owner beliefs about socially recognized constraints. Not objective law,
      world permission, or enforcement. A social prohibition never changes
      physical admission.
    </p>
  </header>

  {#if status === 'loading'}
    <p>Loading formal-rule snapshot…</p>
  {:else if status === 'unavailable'}
    <p class="unavailable">Formal-rule publication is disabled ({reason}).</p>
  {:else if status === 'empty'}
    <p class="empty">No published formal-rule snapshot for this run.</p>
  {:else if status === 'error'}
    <p class="error">Formal-rule read failed ({reason}).</p>
  {:else if summary !== null}
    <dl class="summary">
      <div><dt>Candidates</dt><dd>{summary.candidate_count}</dd></div>
      <div><dt>Rules</dt><dd>{summary.rule_count}</dd></div>
      <div><dt>Versions</dt><dd>{summary.version_count}</dd></div>
      <div><dt>Windows</dt><dd>{summary.window_count}</dd></div>
      <div>
        <dt>Coverage</dt>
        <dd>{summary.coverage.observed}/{summary.coverage.expected}</dd>
      </div>
      <div><dt>Publication</dt><dd>{summary.publication_id}</dd></div>
    </dl>

    <table class="candidates">
      <thead>
        <tr>
          <th>Candidate</th>
          <th>Status</th>
          <th>Stage</th>
          <th>Constraint</th>
          <th>Authority</th>
          <th>Competing</th>
        </tr>
      </thead>
      <tbody>
        {#each candidates as candidate (candidate.candidate_id)}
          <tr>
            <td><button onclick={() => selectCandidate(candidate.candidate_id)}>{candidate.candidate_id}</button></td>
            <td>{candidate.status}</td>
            <td>{candidate.stage}</td>
            <td>{candidate.constraint_kinds.join(', ')}</td>
            <td>{candidate.authority_kinds.join(', ')}</td>
            <td>{candidate.competing_candidate_ids.join(', ') || 'none'}</td>
          </tr>
        {/each}
      </tbody>
    </table>

    {#if detail !== null}
      <section class="detail">
        <h2>Candidate {detail.candidate.candidate_id}</h2>
        <h3>Rules</h3>
        <table class="rules">
          <thead>
            <tr>
              <th>Rule</th>
              <th>Stage</th>
              <th>Constraint</th>
              <th>Authority</th>
              <th>Recognition</th>
              <th>Written</th>
              <th>Sanctions</th>
              <th>Exceptions</th>
              <th>Versions</th>
            </tr>
          </thead>
          <tbody>
            {#each rules as rule (rule.rule_id)}
              <tr>
                <td>{rule.rule_id}</td>
                <td>{rule.stage}</td>
                <td>{rule.constraint_kind}</td>
                <td>{rule.authority_kind}</td>
                <td>{rule.recognition}</td>
                <td>{rule.written_representation.status}</td>
                <td>{rule.sanction_kinds.join(', ') || 'none'}</td>
                <td>{rule.exception_count}</td>
                <td>{rule.version_count}</td>
              </tr>
            {/each}
          </tbody>
        </table>
        <h3>Versions</h3>
        <table class="versions">
          <thead>
            <tr>
              <th>Version</th>
              <th>Number</th>
              <th>Stage</th>
              <th>Revision</th>
              <th>Supersedes</th>
            </tr>
          </thead>
          <tbody>
            {#each versions as version (version.version_id)}
              <tr>
                <td>{version.version_id}</td>
                <td>{version.version_number}</td>
                <td>{version.stage}</td>
                <td>{version.revision_kind}</td>
                <td>{version.supersedes_version_id ?? 'none'}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </section>
    {/if}

    <h3>Lineage</h3>
    <table class="lineage">
      <thead>
        <tr><th>Edge</th><th>Kind</th><th>Source</th><th>Target</th></tr>
      </thead>
      <tbody>
        {#each lineage as edge (edge.edge_id)}
          <tr>
            <td>{edge.edge_id}</td>
            <td>{edge.kind}</td>
            <td>{edge.source_candidate_id}</td>
            <td>{edge.target_candidate_id}</td>
          </tr>
        {/each}
      </tbody>
    </table>

    <p class="declared-responses">
      Declared responses, not objective compliance. Silence is never a violation.
    </p>
  {/if}
</section>
