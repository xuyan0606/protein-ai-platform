/* eslint-disable @typescript-eslint/no-explicit-any */

const STYLES = `
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; font-size: 13px; line-height: 1.6; color: #1a1a1a; max-width: 900px; margin: 0 auto; padding: 40px 24px; }
  h1 { font-size: 22px; margin-bottom: 4px; }
  h2 { font-size: 16px; margin: 28px 0 12px; padding-bottom: 6px; border-bottom: 2px solid #e5e7eb; }
  h3 { font-size: 14px; margin: 16px 0 8px; }
  table { width: 100%; border-collapse: collapse; margin: 8px 0 16px; }
  th { text-align: left; font-size: 11px; text-transform: uppercase; color: #6b7280; padding: 8px 12px; background: #f9fafb; border-bottom: 2px solid #e5e7eb; }
  td { padding: 8px 12px; border-bottom: 1px solid #f3f4f6; font-size: 12px; }
  .badge { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 11px; font-weight: 600; }
  .badge-green { background: #d1fae5; color: #065f46; }
  .badge-amber { background: #fef3c7; color: #92400e; }
  .badge-red { background: #fee2e2; color: #991b1b; }
  .metric-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; margin: 8px 0; }
  .metric-card { background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px; }
  .metric-label { font-size: 10px; color: #6b7280; text-transform: uppercase; }
  .metric-value { font-size: 18px; font-weight: 700; font-family: 'SF Mono', monospace; margin-top: 4px; }
  .code { font-family: 'SF Mono', 'Fira Code', monospace; background: #f3f4f6; padding: 1px 6px; border-radius: 4px; font-size: 12px; }
  .motif-row { display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; background: #f9fafb; border-radius: 6px; margin: 4px 0; }
  .rec-card { border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; margin: 8px 0; }
  .bar-wrap { height: 6px; background: #e5e7eb; border-radius: 4px; margin: 4px 0; overflow: hidden; }
  .bar-fill { height: 100%; border-radius: 4px; }
  .muted { color: #6b7280; font-size: 12px; }
  footer { margin-top: 40px; padding-top: 16px; border-top: 1px solid #e5e7eb; font-size: 11px; color: #9ca3af; text-align: center; }
  @media print { body { padding: 20px; } }
</style>
`

export function escapeHtml(value: unknown): string {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function escapeAttr(value: unknown): string {
  return escapeHtml(value).replace(/`/g, '&#96;')
}

function h(tag: string, attrs: Record<string, string> = {}, ...children: string[]): string {
  const attrStr = Object.entries(attrs).map(([k, v]) => ` ${k}="${escapeAttr(v)}"`).join('')
  return `<${tag}${attrStr}>${children.join('')}</${tag}>`
}

function renderList(items: unknown, emptyText = 'none'): string {
  const values = Array.isArray(items) ? items.filter((item) => String(item ?? '').trim()) : []
  if (!values.length) return h('p', { class: 'muted' }, escapeHtml(emptyText))
  let list = '<ul>'
  values.slice(0, 8).forEach((item) => {
    list += h('li', { class: 'muted' }, escapeHtml(item))
  })
  list += '</ul>'
  return list
}

function renderAnalysisScope(scope: any): string {
  if (!scope || typeof scope !== 'object' || Array.isArray(scope)) return ''
  const evidenceInputs = scope.evidence_inputs && typeof scope.evidence_inputs === 'object'
    ? scope.evidence_inputs
    : {}
  const projectLabel = scope.project_name
    ? `${scope.project_name} (${scope.project_id || 'no project id'})`
    : scope.project_id || 'all projects'
  let html = h('h2', {}, 'Analysis Scope')
  html += '<div class="rec-card">'
  html += '<table><tbody>'
  html += `<tr><td class="code">schema_version</td><td>${escapeHtml(scope.schema_version || 'unknown')}</td></tr>`
  html += `<tr><td class="code">hash_input_policy</td><td>${escapeHtml(scope.hash_input_policy || 'unknown')}</td></tr>`
  html += `<tr><td class="code">scientific_boundary</td><td>${escapeHtml(scope.scientific_boundary || 'audit metadata only')}</td></tr>`
  html += `<tr><td class="code">generated_at</td><td>${escapeHtml(scope.generated_at || 'unknown')}</td></tr>`
  html += `<tr><td class="code">scope_hash</td><td>${escapeHtml(scope.scope_hash || 'unknown')}</td></tr>`
  html += `<tr><td class="code">project</td><td>${escapeHtml(projectLabel)}</td></tr>`
  html += `<tr><td class="code">enzyme_filter</td><td>${escapeHtml(scope.enzyme_filter || 'all enzymes')}</td></tr>`
  html += `<tr><td class="code">decision_filter</td><td>${escapeHtml(scope.decision_filter || 'all decisions')}</td></tr>`
  html += `<tr><td class="code">record_count</td><td>${escapeHtml(scope.record_count ?? 0)}</td></tr>`
  html += `<tr><td class="code">validated_single_mutant_count</td><td>${escapeHtml(scope.validated_single_mutant_count ?? 0)}</td></tr>`
  html += `<tr><td class="code">feedback_record_fingerprint</td><td>${escapeHtml(scope.feedback_record_fingerprint || 'empty')}</td></tr>`
  html += `<tr><td class="code">validated_mutation_fingerprint</td><td>${escapeHtml(scope.validated_mutation_fingerprint || 'empty')}</td></tr>`
  Object.entries(evidenceInputs).forEach(([key, value]) => {
    html += `<tr><td class="code">evidence.${escapeHtml(key)}</td><td>${escapeHtml(value)}</td></tr>`
  })
  html += '</tbody></table>'
  html += '</div>'
  return html
}

// --- Benchmark Report ---

function renderBenchmark(data: any): string {
  const f = (n: number, d = 2) => n?.toFixed(d) ?? '—'
  let html = ''

  // Header
  html += h('h1', {}, `蛋白基准报告`)
  html += h('p', { class: 'muted' }, escapeHtml(`${data.query_info?.length || '?'} residues · ${data.family?.ec || 'EC unknown'} · ${data.family?.mechanism || ''}`))

  // Properties
  html += h('h2', {}, '理化性质')
  const p = data.properties || {}
  html += '<div class="metric-grid">'
  html += h('div', { class: 'metric-card' }, h('div', { class: 'metric-label' }, 'MW') + h('div', { class: 'metric-value' }, `${f(p.molecular_weight_kda, 1)} kDa`))
  html += h('div', { class: 'metric-card' }, h('div', { class: 'metric-label' }, 'pI') + h('div', { class: 'metric-value' }, `${f(p.isoelectric_point)}`))
  html += h('div', { class: 'metric-card' }, h('div', { class: 'metric-label' }, 'GRAVY') + h('div', { class: 'metric-value' }, `${f(p.gravy, 4)}`))
  html += h('div', { class: 'metric-card' }, h('div', { class: 'metric-label' }, 'Gly→Pro Candidates') + h('div', { class: 'metric-value' }, `${p.gly_count || 0}`))
  html += '</div>'

  // Conservation
  const cons = data.conservation_analysis || {}
  html += h('h2', {}, '保守性分析')
  html += h('p', { class: 'muted' }, escapeHtml(`高保守位点：${cons.highly_conserved_count} | 可变位点：${cons.variable_count}`))

  // Motifs
  if (data.family_motifs?.length) {
    html += h('h2', {}, '保守模体')
    data.family_motifs.forEach((m: any) => {
      const found = !m.found_at?.includes('not detected')
      html += `<div class="motif-row"><span><strong>${escapeHtml(m.region)}</strong> ${escapeHtml(m.pattern || '')}</span><span class="badge ${found ? 'badge-green' : 'badge-red'}">${found ? 'Found' : 'Not detected'}</span></div>`
    })
  }

  // Recommendations
  if (data.recommendations?.length) {
    html += h('h2', {}, '工程建议')
    data.recommendations.forEach((r: any) => {
      html += `<div class="rec-card">`
      html += h('strong', {}, escapeHtml(`[P${r.priority}] ${r.category} — ${r.action}`))
      if (r.rationale) html += h('p', { class: 'muted' }, escapeHtml(r.rationale))
      if (r.candidates?.length) html += h('p', { class: 'muted' }, escapeHtml(`前列候选：${r.candidates.slice(0, 5).map((c: any) => c.mutation).join(', ')}`))
      html += '</div>'
    })
  }

  return html
}

// --- Mutation Score Report ---

function renderMutationScore(data: any): string {
  const f = (n: number, d = 1) => n?.toFixed(d) ?? '—'
  let html = ''

  html += h('h1', {}, '突变优先级报告')
  html += h('p', { class: 'muted' }, escapeHtml(`${data.summary?.total_positions || '?'} positions scanned · Goal: ${data.engineering_goal || 'general'}`))

  // Summary
  html += h('h2', {}, '汇总')
  html += '<div class="metric-grid">'
  html += h('div', { class: 'metric-card' }, h('div', { class: 'metric-label' }, '一级候选') + h('div', { class: 'metric-value', style: 'color:#059669' }, `${data.summary?.tier_1_count || 0}`))
  html += h('div', { class: 'metric-card' }, h('div', { class: 'metric-label' }, '二级候选') + h('div', { class: 'metric-value', style: 'color:#d97706' }, `${data.summary?.tier_2_count || 0}`))
  html += h('div', { class: 'metric-card' }, h('div', { class: 'metric-label' }, '禁止突变') + h('div', { class: 'metric-value', style: 'color:#dc2626' }, `${data.summary?.never_mutate_count || 0}`))
  html += '</div>'

  if (data.summary?.never_mutate_positions?.length) {
    html += h('p', { class: 'muted' }, escapeHtml(`Never mutate positions: ${data.summary.never_mutate_positions.join(', ')}`))
  }

  const renderList = (items: unknown, emptyText = 'none') => {
    const values = Array.isArray(items) ? items.filter((item) => String(item ?? '').trim()) : []
    if (!values.length) return h('p', { class: 'muted' }, escapeHtml(emptyText))
    let list = '<ul>'
    values.slice(0, 8).forEach((item) => {
      list += h('li', { class: 'muted' }, escapeHtml(item))
    })
    list += '</ul>'
    return list
  }

  const renderObjectRows = (value: unknown) => {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return ''
    let rows = ''
    Object.entries(value as Record<string, unknown>).forEach(([key, item]) => {
      rows += `<tr><td class="code">${escapeHtml(key)}</td><td>${escapeHtml(item)}</td></tr>`
    })
    return rows
  }

  const contractBadgeClass = (status: unknown) => {
    const normalized = String(status || '').toLowerCase()
    if (['ready', 'passed', 'success'].includes(normalized)) return 'badge-green'
    if (['blocked', 'failed', 'missing', 'conflict'].some((item) => normalized.includes(item))) return 'badge-red'
    return 'badge-amber'
  }

  const renderCandidateFeatureCompleteness = (candidate: any) => {
    const completeness = candidate?.feature_completeness && typeof candidate.feature_completeness === 'object'
      ? candidate.feature_completeness
      : {}
    const missing = Array.isArray(completeness.missing_feature_reasons)
      ? completeness.missing_feature_reasons
      : Array.isArray(candidate?.missing_feature_reasons)
        ? candidate.missing_feature_reasons
        : []
    const status = completeness.status || 'not_reported'
    const available = typeof completeness.available_feature_count === 'number'
      ? completeness.available_feature_count
      : null
    const missingCount = typeof completeness.missing_feature_count === 'number'
      ? completeness.missing_feature_count
      : missing.length
    const schemaVersion = completeness.schema_version || 'candidate_feature_completeness_v1'
    const badgeClass = missingCount === 0 && ['ready', 'complete', 'available'].includes(status)
      ? 'badge-green'
      : status === 'not_reported'
        ? 'badge-amber'
        : 'badge-red'
    const countLabel = available == null ? `${missingCount} missing` : `${available} available / ${missingCount} missing`
    let cell = `<span class="badge ${badgeClass}">${escapeHtml(status)}</span>`
    cell += h('div', { class: 'muted' }, escapeHtml(countLabel))
    cell += h('div', { class: 'code' }, escapeHtml(schemaVersion))
    if (missing.length) {
      cell += h('div', { class: 'muted' }, escapeHtml(`Missing: ${missing.slice(0, 5).join('; ')}`))
    }
    return cell
  }

  const p2Contract = data.p2_engineering_scorecard_contract
  const candidateGeneration = data.candidate_table_generation
  const objectiveContract = data.objective_score_contract
  const candidateReadiness = data.p2_candidate_readiness_summary
  const objectiveReadiness = data.p2_objective_score_readiness_summary
  const structureFeatureGapSummary = data.p2_structure_feature_gap_summary
  const objectiveAssayGapSummary = data.p2_objective_assay_gap_summary
  if (
    p2Contract ||
    candidateGeneration ||
    objectiveContract ||
    candidateReadiness ||
    objectiveReadiness ||
    structureFeatureGapSummary ||
    objectiveAssayGapSummary
  ) {
    html += h('h2', {}, 'P2 合同状态')

    if (objectiveReadiness) {
      html += '<div class="rec-card">'
      html += h('h3', {}, 'Objective Readiness Summary')
      html += `<p><span class="badge ${contractBadgeClass(objectiveReadiness.status)}">${escapeHtml(objectiveReadiness.status || 'unknown')}</span> <span class="muted">${escapeHtml(objectiveReadiness.schema_version || 'p2_objective_score_readiness_summary_v1')}</span></p>`
      html += h('p', { class: 'muted' }, escapeHtml(`Objective rows: ${objectiveReadiness.objective_row_count ?? 0} · aggregation: ${objectiveReadiness.aggregation || 'none'} · no composite score: ${objectiveReadiness.no_composite_score === true ? 'yes' : 'unknown'}`))
      if (Array.isArray(objectiveReadiness.top_unknown_components) && objectiveReadiness.top_unknown_components.length) {
        html += '<table><thead><tr><th>Unknown Objective Component</th><th>Count</th></tr></thead><tbody>'
        objectiveReadiness.top_unknown_components.slice(0, 8).forEach((item: any) => {
          html += `<tr><td class="code">${escapeHtml(item.component || 'unknown')}</td><td>${escapeHtml(item.count ?? 0)}</td></tr>`
        })
        html += '</tbody></table>'
      }
      if (Array.isArray(objectiveReadiness.top_blocking_reasons) && objectiveReadiness.top_blocking_reasons.length) {
        html += '<table><thead><tr><th>Blocking Reason</th><th>Count</th></tr></thead><tbody>'
        objectiveReadiness.top_blocking_reasons.slice(0, 8).forEach((item: any) => {
          html += `<tr><td class="code">${escapeHtml(item.reason || 'unknown')}</td><td>${escapeHtml(item.count ?? 0)}</td></tr>`
        })
        html += '</tbody></table>'
      }
      if (objectiveReadiness.report_action) {
        html += h('p', { class: 'muted' }, escapeHtml(`Report action: ${objectiveReadiness.report_action}`))
      }
      if (Array.isArray(objectiveReadiness.must_not_claim) && objectiveReadiness.must_not_claim.length) {
        html += h('h3', {}, 'Must Not Claim')
        html += renderList(objectiveReadiness.must_not_claim)
      }
      html += '</div>'
    }

    if (structureFeatureGapSummary || objectiveAssayGapSummary) {
      html += '<div class="rec-card">'
      html += h('h3', {}, 'P2 Gap Summary')
      html += '<div class="grid gap-3 md:grid-cols-2">'
      if (structureFeatureGapSummary) {
        html += '<div class="rounded-md border border-border/60 bg-secondary/20 px-3 py-2">'
        html += h('p', { class: 'muted' }, escapeHtml(`${structureFeatureGapSummary.schema_version || 'p2_structure_feature_gap_summary_v1'} · ${structureFeatureGapSummary.status || 'unknown'} · rows ${structureFeatureGapSummary.row_count ?? 0}`))
        if (Array.isArray(structureFeatureGapSummary.top_missing_feature_reasons) && structureFeatureGapSummary.top_missing_feature_reasons.length) {
          html += '<table><thead><tr><th>Missing Structure Feature</th><th>Count</th></tr></thead><tbody>'
          structureFeatureGapSummary.top_missing_feature_reasons.slice(0, 6).forEach((item: any) => {
            html += `<tr><td class="code">${escapeHtml(item.reason || 'unknown')}</td><td>${escapeHtml(item.count ?? 0)}</td></tr>`
          })
          html += '</tbody></table>'
        }
        if (structureFeatureGapSummary.report_action) {
          html += h('p', { class: 'muted' }, escapeHtml(`Report action: ${structureFeatureGapSummary.report_action}`))
        }
        html += '</div>'
      }
      if (objectiveAssayGapSummary) {
        html += '<div class="rounded-md border border-border/60 bg-secondary/20 px-3 py-2">'
        html += h('p', { class: 'muted' }, escapeHtml(`${objectiveAssayGapSummary.schema_version || 'p2_objective_assay_gap_summary_v1'} · ${objectiveAssayGapSummary.status || 'unknown'} · objective rows ${objectiveAssayGapSummary.objective_row_count ?? 0}`))
        if (Array.isArray(objectiveAssayGapSummary.top_assay_gaps) && objectiveAssayGapSummary.top_assay_gaps.length) {
          html += '<table><thead><tr><th>Assay Gap</th><th>Count</th></tr></thead><tbody>'
          objectiveAssayGapSummary.top_assay_gaps.slice(0, 6).forEach((item: any) => {
            html += `<tr><td class="code">${escapeHtml(item.assay || 'unknown')}</td><td>${escapeHtml(item.count ?? 0)}</td></tr>`
          })
          html += '</tbody></table>'
        }
        const feedback = objectiveAssayGapSummary.project_feedback_readiness || {}
        html += h('p', { class: 'muted' }, escapeHtml(`Feedback: ${feedback.status || 'unknown'} · ${feedback.evidence_level || 'unknown'} · n=${feedback.measured_variant_count ?? 0}`))
        if (objectiveAssayGapSummary.report_action) {
          html += h('p', { class: 'muted' }, escapeHtml(`Report action: ${objectiveAssayGapSummary.report_action}`))
        }
        html += '</div>'
      }
      html += '</div>'
      html += '</div>'
    }

    if (candidateReadiness) {
      html += '<div class="rec-card">'
      html += h('h3', {}, 'Candidate Readiness Summary')
      html += `<p><span class="badge ${contractBadgeClass(candidateReadiness.status)}">${escapeHtml(candidateReadiness.status || 'unknown')}</span> <span class="muted">${escapeHtml(candidateReadiness.schema_version || 'p2_candidate_readiness_summary_v1')}</span></p>`
      html += h('p', { class: 'muted' }, escapeHtml(`Candidate table: ${candidateReadiness.candidate_table_status || 'unknown'} · scope: ${candidateReadiness.candidate_row_scope || 'unknown'} · reported ${candidateReadiness.reported_candidate_count ?? 0} / all ${candidateReadiness.all_position_count ?? 0}`))
      if (Array.isArray(candidateReadiness.top_missing_feature_reasons) && candidateReadiness.top_missing_feature_reasons.length) {
        html += '<table><thead><tr><th>Missing P2 Evidence</th><th>Count</th></tr></thead><tbody>'
        candidateReadiness.top_missing_feature_reasons.slice(0, 8).forEach((item: any) => {
          html += `<tr><td class="code">${escapeHtml(item.reason || 'unknown')}</td><td>${escapeHtml(item.count ?? 0)}</td></tr>`
        })
        html += '</tbody></table>'
      }
      if (candidateReadiness.report_action) {
        html += h('p', { class: 'muted' }, escapeHtml(`Report action: ${candidateReadiness.report_action}`))
      }
      if (Array.isArray(candidateReadiness.must_not_claim) && candidateReadiness.must_not_claim.length) {
        html += h('h3', {}, 'Must Not Claim')
        html += renderList(candidateReadiness.must_not_claim)
      }
      html += '</div>'
    }

    if (p2Contract) {
      html += '<div class="rec-card">'
      html += h('h3', {}, 'Engineering Scorecard')
      html += `<p><span class="badge ${contractBadgeClass(p2Contract.status)}">${escapeHtml(p2Contract.status || 'unknown')}</span> <span class="muted">${escapeHtml(p2Contract.schema_version || '')}</span></p>`
      if (p2Contract.component_status) {
        html += '<table><thead><tr><th>Component</th><th>Status</th></tr></thead><tbody>'
        html += renderObjectRows(p2Contract.component_status)
        html += '</tbody></table>'
      }
      if (p2Contract.report_action) {
        html += h('p', { class: 'muted' }, escapeHtml(`Report action: ${p2Contract.report_action}`))
      }
      if (Array.isArray(p2Contract.blocked_reasons) && p2Contract.blocked_reasons.length) {
        html += h('h3', {}, 'Blocked Reasons')
        html += renderList(p2Contract.blocked_reasons)
      }
      if (Array.isArray(p2Contract.must_not_claim) && p2Contract.must_not_claim.length) {
        html += h('h3', {}, 'Must Not Claim')
        html += renderList(p2Contract.must_not_claim)
      }
      html += '</div>'
    }

    if (candidateGeneration) {
      html += '<div class="rec-card">'
      html += h('h3', {}, 'Candidate Table Generation')
      html += `<p><span class="badge ${contractBadgeClass(candidateGeneration.status)}">${escapeHtml(candidateGeneration.status || 'unknown')}</span> <span class="muted">${escapeHtml(candidateGeneration.schema_version || '')}</span></p>`
      if (candidateGeneration.input_contracts) {
        html += '<table><thead><tr><th>Input</th><th>Contract</th></tr></thead><tbody>'
        html += renderObjectRows(candidateGeneration.input_contracts)
        html += '</tbody></table>'
      }
      if (candidateGeneration.output_groups) {
        html += '<table><thead><tr><th>Output Group</th><th>Count</th></tr></thead><tbody>'
        html += renderObjectRows(candidateGeneration.output_groups)
        html += '</tbody></table>'
      }
      if (candidateGeneration.experiment_design_policy) {
        const policy = candidateGeneration.experiment_design_policy
        html += h('h3', {}, 'Experiment Design Policy')
        html += '<table><tbody>'
        html += `<tr><td class="code">schema_version</td><td>${escapeHtml(policy.schema_version || 'experiment_design_schedulability_policy_v1')}</td></tr>`
        html += `<tr><td class="code">excluded_candidate_statuses</td><td>${escapeHtml(Array.isArray(policy.excluded_candidate_statuses) ? policy.excluded_candidate_statuses.join(', ') : 'blocked')}</td></tr>`
        html += `<tr><td class="code">excluded_priorities</td><td>${escapeHtml(Array.isArray(policy.excluded_priorities) ? policy.excluded_priorities.join(', ') : 'No-Go')}</td></tr>`
        html += `<tr><td class="code">requires_recommended_mutation</td><td>${escapeHtml(policy.requires_recommended_mutation === true ? 'yes' : 'unknown')}</td></tr>`
        html += `<tr><td class="code">blocked_rows_excluded_count</td><td>${escapeHtml(policy.blocked_rows_excluded_count ?? 0)}</td></tr>`
        html += `<tr><td class="code">blocked_rows_remain_traceable</td><td>${escapeHtml(policy.blocked_rows_remain_traceable || 'all_positions')}</td></tr>`
        html += '</tbody></table>'
      }
      if (candidateGeneration.boundary) {
        html += h('p', { class: 'muted' }, escapeHtml(candidateGeneration.boundary))
      }
      html += '</div>'
    }

    if (objectiveContract) {
      html += '<div class="rec-card">'
      html += h('h3', {}, 'Objective Score Contract')
      html += h('p', { class: 'muted' }, escapeHtml(`${objectiveContract.schema_version || 'unknown'} · evidence: ${objectiveContract.evidence_level || 'unknown'} · aggregation: ${objectiveContract.aggregation || 'none'}`))
      if (Array.isArray(objectiveContract.assay_required) && objectiveContract.assay_required.length) {
        html += h('h3', {}, 'Assay Required')
        html += renderList(objectiveContract.assay_required)
      }
      if (Array.isArray(objectiveContract.blocking_reason) && objectiveContract.blocking_reason.length) {
        html += h('h3', {}, 'Blocking Reason')
        html += renderList(objectiveContract.blocking_reason)
      }
      html += '</div>'
    }
  }

  function renderTierTable(candidates: any[], tier: number, title: string) {
    if (!candidates?.length) return ''
    let h2 = `<h2>${title}</h2>`
    h2 += '<table><thead><tr><th>Position</th><th>Type</th><th>Score</th><th>Logic</th><th>Recommended</th><th>P2 Evidence</th></tr></thead><tbody>'
    candidates.forEach((c: any) => {
      const muts = Array.isArray(c.recommended_mutations)
        ? c.recommended_mutations.map((m: any) => typeof m === 'string' ? m : m.mutation).join(', ')
        : String(c.recommended_mutations || '')
      const typeTag = c.mutation_type ? `<span class="badge ${tier === 1 ? 'badge-green' : 'badge-amber'}">${escapeHtml(c.mutation_type)}</span>` : '—'
      h2 += `<tr><td class="code">${escapeHtml(`${c.wild_type}${c.position}`)}</td><td>${typeTag}</td><td><strong>${escapeHtml(f(c.composite_priority))}</strong></td><td class="muted" style="max-width:300px">${escapeHtml(c.logic || '')}</td><td class="code">${escapeHtml(muts)}</td><td>${renderCandidateFeatureCompleteness(c)}</td></tr>`
    })
    h2 += '</tbody></table>'
    return h2
  }

  html += renderTierTable(data.tier_1_candidates, 1, '一级候选 - 优先突变')
  html += renderTierTable(data.tier_2_candidates, 2, '二级候选 - 备选突变')

  // matvenus 风格章节：优先级分类突变建议
  const tier1 = data.tier_1_candidates || []
  const tier2 = data.tier_2_candidates || []
  if (tier1.length || tier2.length) {
    html += h('h2', {}, '一、优先级突变建议（结构化）')
    html += '<table><thead><tr><th>优先级</th><th>突变</th><th>目的</th></tr></thead><tbody>'

    tier1.forEach((c: any) => {
      const muts = Array.isArray(c.recommended_mutations) ? c.recommended_mutations : []
      muts.forEach((mut: any) => {
        const mutation = typeof mut === 'string' ? mut : mut.mutation || ''
        const purpose = typeof mut === 'object' && mut.purpose ? mut.purpose : c.design_logic || c.logic || ''
        html += `<tr><td><span class="badge badge-green">高</span></td><td class="code">${escapeHtml(mutation)}</td><td>${escapeHtml(purpose)}</td></tr>`
      })
    })

    tier2.forEach((c: any) => {
      const muts = Array.isArray(c.recommended_mutations) ? c.recommended_mutations : []
      const hasRisk = Array.isArray(c.risk_flags) && c.risk_flags.length > 0
      const priority = hasRisk ? '条件性' : '中'
      const badgeClass = hasRisk ? 'badge-amber' : 'badge-amber'
      muts.forEach((mut: any) => {
        const mutation = typeof mut === 'string' ? mut : mut.mutation || ''
        const purpose = typeof mut === 'object' && mut.purpose ? mut.purpose : c.design_logic || c.logic || ''
        html += `<tr><td><span class="badge ${badgeClass}">${priority}</span></td><td class="code">${escapeHtml(mutation)}</td><td>${escapeHtml(purpose)}</td></tr>`
      })
    })
    html += '</tbody></table>'
  }

  // 二、首轮单点突变策略
  const p1Mutations = tier1.flatMap((c: any) => {
    const muts = Array.isArray(c.recommended_mutations) ? c.recommended_mutations : []
    return muts.map((m: any) => typeof m === 'string' ? m : m.mutation)
  }).filter(Boolean)

  if (p1Mutations.length) {
    html += h('h2', {}, '二、首轮单点突变策略')
    html += h('p', {}, '建议首轮只测试单点突变，确认各位点独立效应后再设计组合。')
    html += '<ul>'
    p1Mutations.slice(0, 15).forEach((mut: string) => {
      html += h('li', { class: 'code' }, escapeHtml(mut))
    })
    html += '</ul>'
    if (p1Mutations.length > 15) {
      html += h('p', { class: 'muted' }, `（共 ${p1Mutations.length} 个候选，上方显示前 15 个）`)
    }
  }

  // 三、必须保护的位点
  const protectedPositions = [
    ...(data.tier_1_candidates || []),
    ...(data.tier_2_candidates || []),
    ...(data.tier_3_candidates || [])
  ].filter((c: any) => c.is_protected || c.experiment_priority === 'No-Go')

  if (protectedPositions.length || data.summary?.never_mutate_positions?.length) {
    html += h('h2', {}, '三、必须保护的位点')

    const byCategory: Record<string, any[]> = {
      catalytic: [],
      substrate: [],
      metal_binding: [],
      disulfide: [],
      other: []
    }

    protectedPositions.forEach((c: any) => {
      const sources = Array.isArray(c.active_site_sources) ? c.active_site_sources : []
      if (sources.includes('catalytic')) byCategory.catalytic.push(c)
      else if (sources.includes('substrate')) byCategory.substrate.push(c)
      else if (sources.includes('metal_binding') || sources.includes('metal')) byCategory.metal_binding.push(c)
      else if (c.wild_type === 'C' && c.risk_flags?.some((f: string) => f.includes('二硫键'))) byCategory.disulfide.push(c)
      else byCategory.other.push(c)
    })

    if (byCategory.catalytic.length) {
      html += h('h3', {}, '催化核心')
      html += '<ul>'
      byCategory.catalytic.forEach((c: any) => {
        html += h('li', { class: 'code' }, `${escapeHtml(c.wild_type)}${escapeHtml(c.position)} — ${escapeHtml(c.active_site_sources?.join(', ') || '催化残基')}`)
      })
      html += '</ul>'
    }

    if (byCategory.substrate.length) {
      html += h('h3', {}, '底物识别')
      html += '<ul>'
      byCategory.substrate.forEach((c: any) => {
        html += h('li', { class: 'code' }, `${escapeHtml(c.wild_type)}${escapeHtml(c.position)} — ${escapeHtml(c.active_site_sources?.join(', '))}`)
      })
      html += '</ul>'
    }

    if (byCategory.metal_binding.length) {
      html += h('h3', {}, '金属配位')
      html += '<ul>'
      byCategory.metal_binding.forEach((c: any) => {
        html += h('li', { class: 'code' }, `${escapeHtml(c.wild_type)}${escapeHtml(c.position)} — ${escapeHtml(c.active_site_sources?.join(', '))}`)
      })
      html += '</ul>'
    }

    if (byCategory.disulfide.length) {
      html += h('h3', {}, '保守二硫键 Cys')
      html += '<ul>'
      byCategory.disulfide.forEach((c: any) => {
        html += h('li', { class: 'code' }, `C${escapeHtml(c.position)}`)
      })
      html += '</ul>'
    }

    if (data.summary?.never_mutate_positions?.length) {
      html += h('p', { class: 'muted' }, `其他禁止突变位点：${escapeHtml(data.summary.never_mutate_positions.join(', '))}`)
    }
  }

  // 四、实验验证方案
  html += h('h2', {}, '四、比活力验证建议')
  const assayGuide = data.summary?.experiment_action || data.experiment_design_policy?.assay_protocol || '需实测比活力、Tm 或目标性质变化'
  html += h('p', {}, escapeHtml(assayGuide))
  html += '<ul>'
  ;['蛋白归一化的比活力测定', 'WT 和突变体同批对照', '≥3 生物学重复', '记录表达量和纯度'].forEach(item => {
    html += h('li', {}, item)
  })
  html += '</ul>'

  return html
}

// --- MD Report ---

function renderMD(data: any): string {
  const f = (n: number, d = 2) => n?.toFixed(d) ?? '—'
  if (data?.status === 'failed') {
    let html = ''
    html += h('h1', {}, '分子动力学报告')
    html += h('p', { class: 'muted' }, data.is_real_md ? '真实 GROMACS 流程失败' : '真实 GROMACS 流程不可用')
    html += h('h2', {}, '失败详情')
    html += h('p', {}, `<strong>${escapeHtml(data.error_code || 'MD_FAILED')}</strong>`)
    html += h('p', { class: 'muted' }, escapeHtml(data.error || 'Unknown error'))
    if (data.note) {
      html += h('p', { class: 'muted' }, escapeHtml(data.note))
    }
    if (Array.isArray(data.required_runtime) && data.required_runtime.length) {
      html += h('h2', {}, '所需运行环境')
      html += '<ul>'
      data.required_runtime.forEach((item: string) => {
        html += h('li', {}, escapeHtml(item))
      })
      html += '</ul>'
    }
    return html
  }
  const wt = data.wild_type || {}
  const s = wt.structural_stability || {}
  const e = wt.energetics || {}
  const p = wt.simulation_parameters || {}
  const subtitle = [
    data.engine || '',
    data.ensemble || '',
    p.simulation_time_ns ? `${p.simulation_time_ns}ns` : '',
    p.temperature_k ? `${p.temperature_k}K` : '',
    p.force_field && p.water_model ? `${p.force_field}/${p.water_model}` : '',
    p.estimated_atom_count ? `${p.estimated_atom_count} atoms` : '',
  ].filter(Boolean).join(' · ')

  let html = ''
  html += h('h1', {}, '分子动力学报告')
  html += h('p', { class: 'muted' }, escapeHtml(subtitle))

  html += h('h2', {}, '结构稳定性')
  html += '<div class="metric-grid">'
  html += h('div', { class: 'metric-card' }, h('div', { class: 'metric-label' }, 'RMSD Final') + h('div', { class: 'metric-value' }, `${f(s.rmsd_final_nm)} nm`))
  html += h('div', { class: 'metric-card' }, h('div', { class: 'metric-label' }, 'RMSD Drift') + h('div', { class: 'metric-value', style: s.is_stable ? 'color:#059669' : 'color:#dc2626' }, `${f(s.rmsd_drift_nm)} nm`))
  html += h('div', { class: 'metric-card' }, h('div', { class: 'metric-label' }, 'Mean RMSF') + h('div', { class: 'metric-value' }, `${f(s.mean_rmsf_nm)} nm`))
  html += h('div', { class: 'metric-card' }, h('div', { class: 'metric-label' }, '是否稳定') + h('div', { class: 'metric-value' }, s.is_stable ? '是' : '否'))
  html += '</div>'

  html += h('h2', {}, '能量项')
  html += `<p><strong>Potential:</strong> ${f(e.potential_energy_kjmol, 0)} kJ/mol &nbsp; <strong>Kinetic:</strong> ${f(e.kinetic_energy_kjmol, 0)} kJ/mol &nbsp; <strong>Total:</strong> ${f(e.total_energy_kjmol, 0)} kJ/mol</p>`

  if (data.mutants?.length) {
    html += h('h2', {}, '突变体比较')
    html += '<table><thead><tr><th>Mutation</th><th>ΔΔG (kJ/mol)</th><th>ΔRMSF (nm)</th><th>Stable</th></tr></thead><tbody>'
    data.mutants.forEach((m: any) => {
      html += `<tr><td class="code">${escapeHtml(m.mutation)}</td><td style="color:${m.stability_delta > 0 ? '#dc2626' : '#059669'}">${escapeHtml(`${m.stability_delta > 0 ? '+' : ''}${m.stability_delta}`)}</td><td>${escapeHtml(f(m.rmsf_change_mean, 3))}</td><td>${m.stable ? 'YES' : 'NO'}</td></tr>`
    })
    html += '</tbody></table>'
  }

  return html
}

// --- Blast Report ---

function renderBlast(data: any): string {
  let html = ''
  html += h('h1', {}, 'BLAST 检索报告')
  html += h('p', { class: 'muted' }, escapeHtml(`${data.program || 'blastp'} against ${data.database || 'nr'} · ${data.results_count || 0} 个命中`))

  if (data.results?.length) {
    html += '<table><thead><tr><th>#</th><th>Hit</th><th>Organism</th><th>Identity</th><th>E-value</th></tr></thead><tbody>'
    data.results.forEach((hit: any) => {
      html += `<tr><td>${escapeHtml(hit.hit_num)}</td><td><strong>${escapeHtml(hit.definition || hit.id)}</strong><br><span class="muted">${escapeHtml(hit.accession)}</span></td><td>${escapeHtml(hit.organism || '—')}</td><td><strong>${escapeHtml(hit.best_identity_percent?.toFixed(1) || '—')}%</strong></td><td class="code">${escapeHtml(hit.best_e_value || '—')}</td></tr>`
    })
    html += '</tbody></table>'
  }

  return html
}

// --- Rosetta ddG Report ---

function renderRosetta(data: any): string {
  let html = ''
  html += h('h1', {}, 'Rosetta ΔΔG 报告')
  html += h('p', { class: 'muted' }, escapeHtml(`${Array.isArray(data?.requested_mutations) ? data.requested_mutations.length : 0} requested mutations`))

  html += h('h2', {}, '解释')
  html += '<table><thead><tr><th>Range (kcal/mol)</th><th>Label</th><th>Meaning</th></tr></thead><tbody>'
  const rows = [
    ['<= -2.0', 'strong_stabilizing', 'Strong stabilizing candidate; manual review required'],
    ['(-2.0, -1.0]', 'stabilizing', 'Likely stabilizing'],
    ['(-1.0, 1.0]', 'neutral_or_uncertain', 'Small effect; do not over-interpret'],
    ['(1.0, 2.0]', 'destabilizing', 'Likely destabilizing'],
    ['> 2.0', 'strong_destabilizing', 'High destabilization risk'],
  ]
  rows.forEach(([range, label, meaning]) => {
    html += `<tr><td class="code">${escapeHtml(range)}</td><td>${escapeHtml(label)}</td><td>${escapeHtml(meaning)}</td></tr>`
  })
  html += '</tbody></table>'

  if (data?.manual_review_checklist?.length) {
    html += h('h2', {}, '人工复核')
    html += '<ul>'
    data.manual_review_checklist.forEach((item: string) => {
      html += h('li', {}, escapeHtml(item))
    })
    html += '</ul>'
  }

  if (Array.isArray(data?.results) && data.results.length) {
    html += h('h2', {}, 'Mutation Results')
    html += '<table><thead><tr><th>Mutation</th><th>ΔΔG</th><th>Class</th><th>Review Flags</th></tr></thead><tbody>'
    data.results.forEach((item: any) => {
      const flags = Array.isArray(item.manual_review_flags) ? item.manual_review_flags.join('; ') : ''
      html += `<tr><td class="code">${escapeHtml(item.mutation || '—')}</td><td class="code">${escapeHtml(item.ddg_kcal_mol ?? '—')}</td><td>${escapeHtml(item.ddg_label || '—')}</td><td class="muted">${escapeHtml(flags)}</td></tr>`
    })
    html += '</tbody></table>'
  } else if (data?.status) {
    html += h('h2', {}, '工具状态')
    html += h('p', { class: 'muted' }, escapeHtml(String(data.status)))
    if (data.reason) html += h('p', { class: 'muted' }, escapeHtml(`Blocked reason: ${data.reason}`))
    if (data.note) html += h('p', { class: 'muted' }, escapeHtml(String(data.note)))
  }

  return html
}

// --- Mutation Epistasis Report ---

function renderMutationEpistasis(data: any): string {
  const contract = data?.report_contract || {}
  const evidenceInputs = contract.evidence_inputs || {}
  let html = ''

  html += h('h1', {}, '组合上位性检查报告')
  html += h('p', { class: 'muted' }, escapeHtml(`${Array.isArray(data?.mutations) ? data.mutations.join(' + ') : 'mutations unknown'} · recommendation: ${data?.recommendation || data?.status || 'unknown'}`))
  html += renderAnalysisScope(data?.analysis_scope)

  if (data?.status === 'blocked') {
    html += h('h2', {}, '阻断原因')
    html += h('p', { class: 'muted' }, escapeHtml(data.blocked_reason || 'blocked'))
  }

  if (data?.summary) {
    html += h('h2', {}, '风险汇总')
    html += '<div class="metric-grid">'
    html += h('div', { class: 'metric-card' }, h('div', { class: 'metric-label' }, 'High Risk') + h('div', { class: 'metric-value', style: 'color:#dc2626' }, escapeHtml(data.summary.high_risk_pairs ?? 0)))
    html += h('div', { class: 'metric-card' }, h('div', { class: 'metric-label' }, 'Watch') + h('div', { class: 'metric-value', style: 'color:#d97706' }, escapeHtml(data.summary.medium_risk_pairs ?? 0)))
    html += h('div', { class: 'metric-card' }, h('div', { class: 'metric-label' }, 'Risk Score') + h('div', { class: 'metric-value' }, escapeHtml(data.summary.risk_score_total ?? 0)))
    html += '</div>'
  }

  if (Array.isArray(data?.pairwise_risks) && data.pairwise_risks.length) {
    html += h('h2', {}, 'Pairwise Risks')
    html += '<table><thead><tr><th>Pair</th><th>Risk</th><th>Score</th><th>Distance</th><th>Distance Source</th><th>Reasons</th></tr></thead><tbody>'
    data.pairwise_risks.forEach((risk: any) => {
      const distance = risk.distance_angstrom == null ? 'unknown' : `${risk.distance_angstrom} A`
      const reasons = Array.isArray(risk.reasons) ? risk.reasons.join('; ') : ''
      html += `<tr><td class="code">${escapeHtml((risk.pair || []).join(' + '))}</td><td>${escapeHtml(risk.risk || 'unknown')}</td><td>${escapeHtml(risk.score ?? '')}</td><td>${escapeHtml(distance)}</td><td>${escapeHtml(risk.distance_source || 'not_available')}</td><td class="muted">${escapeHtml(reasons)}</td></tr>`
    })
    html += '</tbody></table>'
  }

  html += h('h2', {}, '报告合同')
  html += '<div class="rec-card">'
  html += h('h3', {}, escapeHtml(contract.schema_version || 'mutation_epistasis_check_report_contract_v1'))
  if (Object.keys(evidenceInputs).length) {
    html += '<table><thead><tr><th>Evidence Input</th><th>Status</th></tr></thead><tbody>'
    Object.entries(evidenceInputs).forEach(([key, value]) => {
      html += `<tr><td class="code">${escapeHtml(key)}</td><td>${escapeHtml(value)}</td></tr>`
    })
    html += '</tbody></table>'
  }
  if (Array.isArray(contract.distance_source_priority) && contract.distance_source_priority.length) {
    html += h('p', { class: 'muted' }, escapeHtml(`Distance source priority: ${contract.distance_source_priority.join(' > ')}`))
  }
  const missing = Array.isArray(data?.required_missing_evidence) ? data.required_missing_evidence : contract.required_missing_evidence
  if (Array.isArray(missing) && missing.length) {
    html += h('h3', {}, 'Required Missing Evidence')
    html += '<ul>'
    missing.forEach((item: string) => {
      html += h('li', { class: 'muted' }, escapeHtml(item))
    })
    html += '</ul>'
  }
  if (Array.isArray(contract.must_not_claim) && contract.must_not_claim.length) {
    html += h('h3', {}, 'Must Not Claim')
    html += '<ul>'
    contract.must_not_claim.forEach((item: string) => {
      html += h('li', { class: 'muted' }, escapeHtml(item))
    })
    html += '</ul>'
  }
  if (contract.boundary) {
    html += h('p', { class: 'muted' }, escapeHtml(contract.boundary))
  }
  html += '</div>'

  if (Array.isArray(data?.gradient_experiment_plan) && data.gradient_experiment_plan.length) {
    html += h('h2', {}, '梯度实验计划')
    html += '<table><thead><tr><th>Step</th><th>Variant</th><th>Purpose</th></tr></thead><tbody>'
    data.gradient_experiment_plan.forEach((step: any) => {
      html += `<tr><td>${escapeHtml(step.step)}</td><td class="code">${escapeHtml(step.variant || '')}</td><td>${escapeHtml(step.purpose || '')}</td></tr>`
    })
    html += '</tbody></table>'
  }

  return html
}

// --- DBTL Trace Report ---

function renderProjectDbtlTrace(data: any): string {
  const summary = data?.trace_summary || {}
  const counts = summary.counts || {}
  const projectModel = data?.project_model || {}
  const learning = data?.learning_readiness || {}
  const nextRound = data?.next_round_library_design || {}
  const combinationContract = nextRound.combination_evidence_contract || {}
  const sourceEvidence = nextRound.source_evidence || {}
  const p4Readiness = summary.p4_closed_loop_readiness || {}
  const readinessBridge = summary.readiness_bridge || {}
  const projectMemoryReadiness = summary.project_memory_readiness || {}
  const feedbackReadiness = summary.feedback_readiness || {}
  const formalDbtlTablesExist = 'formal_dbtl_tables_exist'
  let html = ''

  html += h('h1', {}, 'DBTL 项目追踪报告')
  html += h('p', { class: 'muted' }, escapeHtml(`${data?.project_id || 'project unknown'} · ${summary.status || 'status unknown'} · ${data?.round_key || 'all rounds'}`))

  html += h('h2', {}, 'Trace Summary')
  html += '<div class="metric-grid">'
  html += h('div', { class: 'metric-card' }, h('div', { class: 'metric-label' }, 'Project Memory') + h('div', { class: 'metric-value' }, escapeHtml(summary.project_memory_status || 'unknown')))
  html += h('div', { class: 'metric-card' }, h('div', { class: 'metric-label' }, 'Learning') + h('div', { class: 'metric-value' }, escapeHtml(summary.learning_status || 'unknown')))
  html += h('div', { class: 'metric-card' }, h('div', { class: 'metric-label' }, 'Next Round') + h('div', { class: 'metric-value' }, escapeHtml(summary.next_round_status || 'unknown')))
  html += h('div', { class: 'metric-card' }, h('div', { class: 'metric-label' }, 'Formal Decision') + h('div', { class: 'metric-value' }, escapeHtml(summary.formal_decision_status || 'unknown')))
  html += '</div>'
  html += h('p', { class: 'muted' }, escapeHtml(`Rounds ${counts.rounds ?? 0} · Variants ${counts.variants ?? 0} · Feedback ${counts.feedback_records ?? 0} · Training-ready ${counts.training_eligible_feedback_records ?? 0}`))
  html += h('p', { class: 'muted' }, escapeHtml(`Structural distance source: ${summary.next_round_structural_distance_source || 'none'} · Combination evidence: ${summary.next_round_combination_evidence_status || 'unknown'}`))

  if (Object.keys(readinessBridge).length > 0) {
    html += h('h2', {}, 'Readiness Bridge')
    html += '<div class="rec-card">'
    html += h('p', { class: 'muted' }, escapeHtml(`${readinessBridge.schema_version || 'dbtl_readiness_bridge_v1'} · ${readinessBridge.status || 'unknown'} · read-only: ${readinessBridge.read_only === true ? 'yes' : 'unknown'}`))
    html += h('p', { class: 'muted' }, escapeHtml(`project memory: ${readinessBridge.project_memory_readiness_status || 'unknown'} · feedback: ${readinessBridge.feedback_readiness_status || 'unknown'} · next round: ${readinessBridge.next_round_constraint_status || 'unknown'}`))
    html += h('p', { class: 'muted' }, escapeHtml(`combination evidence: ${readinessBridge.combination_evidence_status || 'unknown'}`))
    if (Array.isArray(readinessBridge.required_actions) && readinessBridge.required_actions.length) {
      html += '<h3>Required Actions</h3>'
      html += renderList(readinessBridge.required_actions)
    }
    html += '</div>'
  }

  html += h('h2', {}, 'Project Memory Readiness')
  html += '<div class="rec-card">'
  html += h('p', { class: 'muted' }, escapeHtml(`${projectMemoryReadiness.schema_version || 'dbtl_project_memory_readiness_v1'} · ${projectMemoryReadiness.status || 'unknown'} · read-only: ${projectMemoryReadiness.read_only === true ? 'yes' : 'unknown'} · ready ${projectMemoryReadiness.ready_entity_count ?? 0} / missing ${projectMemoryReadiness.missing_entity_count ?? 0}`))
  if (projectMemoryReadiness.entity_status) {
    html += '<table><thead><tr><th>Entity</th><th>Status</th><th>Count</th></tr></thead><tbody>'
    Object.entries(projectMemoryReadiness.entity_status).forEach(([entity, value]: [string, any]) => {
      html += `<tr><td class="code">${escapeHtml(entity)}</td><td>${escapeHtml(value?.status || 'unknown')}</td><td>${escapeHtml(value?.count ?? 0)}</td></tr>`
    })
    html += '</tbody></table>'
  }
  if (Array.isArray(projectMemoryReadiness.must_not_claim) && projectMemoryReadiness.must_not_claim.length) {
    html += h('p', { class: 'muted' }, escapeHtml(`Must not claim: ${projectMemoryReadiness.must_not_claim.join(', ')}`))
  }
  html += '</div>'

  html += h('h2', {}, 'Feedback Readiness')
  html += '<div class="rec-card">'
  html += h('p', { class: 'muted' }, escapeHtml(`${feedbackReadiness.schema_version || 'dbtl_feedback_readiness_summary_v1'} · ${feedbackReadiness.status || 'unknown'} · read-only: ${feedbackReadiness.read_only === true ? 'yes' : 'unknown'} · records ${feedbackReadiness.record_count ?? 0} · training-ready ${feedbackReadiness.training_eligible_count ?? 0} / ${feedbackReadiness.training_batch_minimum ?? 12}`))
  html += '<!-- wet_lab_validated_by_trace_summary -->'
  html += h('p', { class: 'muted' }, escapeHtml(`Next round constraint: ${feedbackReadiness.next_round_constraint_status || 'blocked_by_feedback_import_contract'}`))
  const assayQc = feedbackReadiness.assay_qc_summary || {}
  if (assayQc.qc_status_counts || assayQc.assay_condition_counts || assayQc.replicate_counts || assayQc.measured_metric_counts) {
    html += '<table><thead><tr><th>Group</th><th>Counts</th></tr></thead><tbody>'
    ;([
      ['qc_status_counts', assayQc.qc_status_counts],
      ['formal_decision_counts', assayQc.formal_decision_counts],
      ['assay_condition_counts', assayQc.assay_condition_counts],
      ['replicate_counts', assayQc.replicate_counts],
      ['measured_metric_counts', assayQc.measured_metric_counts],
    ] as Array<[string, any]>).forEach(([group, values]) => {
      const rendered = values && typeof values === 'object'
        ? Object.entries(values).map(([key, value]) => `${key}: ${value}`).join(', ')
        : ''
      html += `<tr><td class="code">${escapeHtml(group)}</td><td>${escapeHtml(rendered)}</td></tr>`
    })
    html += '</tbody></table>'
  }
  if (Array.isArray(feedbackReadiness.top_missing_for_training) && feedbackReadiness.top_missing_for_training.length) {
    html += '<table><thead><tr><th>Missing Training Evidence</th><th>Count</th></tr></thead><tbody>'
    feedbackReadiness.top_missing_for_training.forEach((item: any) => {
      html += `<tr><td class="code">${escapeHtml(item.reason || '')}</td><td>${escapeHtml(item.count ?? 0)}</td></tr>`
    })
    html += '</tbody></table>'
  }
  if (Array.isArray(feedbackReadiness.must_not_claim) && feedbackReadiness.must_not_claim.length) {
    html += h('p', { class: 'muted' }, escapeHtml(`Must not claim: ${feedbackReadiness.must_not_claim.join(', ')}`))
  }
  html += '</div>'

  html += h('h2', {}, 'P4 Closed Loop Readiness')
  html += '<div class="rec-card">'
  html += h('p', { class: 'muted' }, escapeHtml(`${p4Readiness.schema_version || 'p4_closed_loop_readiness_v1'} · ${p4Readiness.status || 'blocked'} · read-only: ${p4Readiness.read_only === true ? 'yes' : 'unknown'}`))
  html += '<!-- p4_active_learning_batch_contract_v1 p4_model_calibration_registry_contract_v1 p4_manufacturing_constraint_schema_v1 model_retrained -->'
  const p4Contracts = [
    ['active_learning_batch_contract', p4Readiness.active_learning_batch_contract],
    ['model_calibration_registry_contract', p4Readiness.model_calibration_registry_contract],
    ['manufacturing_constraint_contract', p4Readiness.manufacturing_constraint_contract],
    ['operator_review_contract', p4Readiness.operator_review_contract],
  ] as Array<[string, any]>
  html += '<table><thead><tr><th>P4 Contract</th><th>Status</th><th>Blocked Reasons</th><th>Schema</th></tr></thead><tbody>'
  p4Contracts.forEach(([name, contract]) => {
    html += `<tr><td class="code">${escapeHtml(name)}</td><td>${escapeHtml(contract?.status || 'missing_contract')}</td><td>${escapeHtml(Array.isArray(contract?.blocked_reasons) ? contract.blocked_reasons.join(', ') : '')}</td><td class="code">${escapeHtml(contract?.schema_version || '')}</td></tr>`
  })
  html += '</tbody></table>'
  if (p4Readiness.gates) {
    html += '<table><thead><tr><th>Gate</th><th>Status</th><th>Requires</th></tr></thead><tbody>'
    Object.entries(p4Readiness.gates).forEach(([gate, value]: [string, any]) => {
      html += `<tr><td class="code">${escapeHtml(gate)}</td><td>${escapeHtml(value?.status || 'unknown')}</td><td>${escapeHtml(Array.isArray(value?.requires) ? value.requires.join(', ') : '')}</td></tr>`
    })
    html += '</tbody></table>'
  }
  if (Array.isArray(p4Readiness.must_not_claim) && p4Readiness.must_not_claim.length) {
    html += h('p', { class: 'muted' }, escapeHtml(`Must not claim: ${p4Readiness.must_not_claim.join(', ')}`))
  }
  html += '</div>'

  if (Array.isArray(summary.required_actions) && summary.required_actions.length) {
    html += h('h2', {}, 'Required Actions')
    const actionContract = summary.required_action_contract || {}
    html += h('p', { class: 'muted' }, escapeHtml(`${actionContract.schema_version || 'dbtl_required_action_contract_v1'} · ${actionContract.status || 'action_required'} · read-only follow-up categories`))
    html += '<table><thead><tr><th>Action</th><th>Category</th><th>Priority</th><th>Reason</th><th>Blocks</th></tr></thead><tbody>'
    summary.required_actions.forEach((item: any) => {
      html += `<tr><td class="code">${escapeHtml(item.action || '')}</td><td>${escapeHtml(item.category || 'general')}</td><td>${escapeHtml(item.priority || 'P2')}</td><td>${escapeHtml(item.reason || '')}</td><td>${escapeHtml(Array.isArray(item.blocks) ? item.blocks.join(', ') : '')}</td></tr>`
    })
    html += '</tbody></table>'
  }

  html += h('h2', {}, 'Project Memory')
  html += '<div class="rec-card">'
  html += h('p', { class: 'muted' }, escapeHtml(`${projectModel.schema_version || 'dbtl_project_model_v1'} · ${projectModel.status || 'unknown'} · read-only: ${projectModel.read_only === true ? 'yes' : 'unknown'}`))
  html += `<!-- ${formalDbtlTablesExist} -->`
  if (Array.isArray(projectModel.missing_entities) && projectModel.missing_entities.length) {
    html += h('p', { class: 'muted' }, escapeHtml(`Missing entities: ${projectModel.missing_entities.join(', ')}`))
  }
  html += '</div>'

  html += h('h2', {}, 'Learning Readiness')
  html += '<div class="rec-card">'
  html += h('p', { class: 'muted' }, escapeHtml(`${learning.schema_version || 'dbtl_learning_readiness_v1'} · ${learning.status || 'unknown'} · training eligible ${learning.training_eligible_count ?? 0}`))
  if (learning.missing_for_training_counts) {
    html += '<table><thead><tr><th>Missing Reason</th><th>Count</th></tr></thead><tbody>'
    Object.entries(learning.missing_for_training_counts).forEach(([key, value]) => {
      html += `<tr><td class="code">${escapeHtml(key)}</td><td>${escapeHtml(value)}</td></tr>`
    })
    html += '</tbody></table>'
  }
  html += '</div>'

  html += h('h2', {}, 'Next Round Library')
  html += '<div class="rec-card">'
  html += h('p', { class: 'muted' }, escapeHtml(`${nextRound.schema_version || 'next_round_library_design_v1'} · ${nextRound.status || 'unknown'} · objective ${nextRound.objective || 'unknown'}`))
  html += h('p', { class: 'muted' }, escapeHtml(`Validated singletons ${sourceEvidence.validated_single_mutants ?? 0} · Eligible pairs ${sourceEvidence.eligible_pair_candidates ?? 0} · Data quality ${sourceEvidence.data_quality_level || 'unknown'}`))
  if (Array.isArray(nextRound.single_point_pool) && nextRound.single_point_pool.length) {
    html += h('h3', {}, 'Single Point Pool')
    html += '<table><thead><tr><th>Mutation</th><th>Variant</th><th>Use</th></tr></thead><tbody>'
    nextRound.single_point_pool.forEach((item: any) => {
      html += `<tr><td class="code">${escapeHtml(item.mutation || '')}</td><td>${escapeHtml(item.variant_name || '')}</td><td>${escapeHtml(item.use || '')}</td></tr>`
    })
    html += '</tbody></table>'
  }
  if (Array.isArray(nextRound.combination_pool) && nextRound.combination_pool.length) {
    html += h('h3', {}, 'Combination Pool')
    html += '<table><thead><tr><th>Mutations</th><th>Status</th><th>Recommendation</th><th>Distance Sources</th></tr></thead><tbody>'
    nextRound.combination_pool.forEach((item: any) => {
      html += `<tr><td class="code">${escapeHtml(Array.isArray(item.mutations) ? item.mutations.join(' + ') : '')}</td><td>${escapeHtml(item.status || '')}</td><td>${escapeHtml(item.epistasis_recommendation || '')}</td><td>${escapeHtml(Array.isArray(item.distance_sources) ? item.distance_sources.join(', ') : '')}</td></tr>`
    })
    html += '</tbody></table>'
  }
  html += '</div>'

  html += h('h2', {}, 'Combination Evidence Contract')
  html += '<div class="rec-card">'
  html += h('p', { class: 'muted' }, escapeHtml(`${combinationContract.schema_version || 'next_round_combination_evidence_contract_v1'} · ${combinationContract.status || 'unknown'} · structural source ${combinationContract.structural_distance_source || 'none'}`))
  if (Array.isArray(combinationContract.pair_contracts) && combinationContract.pair_contracts.length) {
    html += '<table><thead><tr><th>Pair</th><th>Label</th><th>Recommendation</th><th>Distance Sources</th></tr></thead><tbody>'
    combinationContract.pair_contracts.forEach((item: any) => {
      html += `<tr><td class="code">${escapeHtml(Array.isArray(item.mutations) ? item.mutations.join(' + ') : '')}</td><td>${escapeHtml(item.label || '')}</td><td>${escapeHtml(item.epistasis_recommendation || '')}</td><td>${escapeHtml(Array.isArray(item.distance_sources) ? item.distance_sources.join(', ') : '')}</td></tr>`
    })
    html += '</tbody></table>'
  }
  if (Array.isArray(combinationContract.must_not_claim) && combinationContract.must_not_claim.length) {
    html += h('h3', {}, 'Must Not Claim')
    html += '<ul>'
    combinationContract.must_not_claim.forEach((item: string) => {
      html += h('li', { class: 'muted' }, escapeHtml(item))
    })
    html += '</ul>'
  }
  if (combinationContract.boundary) {
    html += h('p', { class: 'muted' }, escapeHtml(combinationContract.boundary))
  }
  html += '</div>'

  if (summary.report_contract) {
    html += h('h2', {}, 'Report Contract')
    html += '<div class="rec-card">'
    html += h('p', { class: 'muted' }, escapeHtml(`Must label computational outputs as hypothesis: ${summary.report_contract.must_label_computational_outputs_as_hypothesis === true ? 'yes' : 'unknown'}`))
    html += h('p', { class: 'muted' }, escapeHtml(`Must not claim training or wet-lab validation: ${summary.report_contract.must_not_claim_training_or_wet_lab_validation === true ? 'yes' : 'unknown'}`))
    if (summary.boundary) html += h('p', { class: 'muted' }, escapeHtml(summary.boundary))
    html += '</div>'
  }

  return html
}

// --- Feedback Iteration Plan Report ---

function renderFeedbackIterationPlan(data: any): string {
  const quality = data?.data_quality || {}
  const library = data?.next_round_library_design || {}
  const sourceEvidence = library.source_evidence || {}
  const combinationContract = library.combination_evidence_contract || {}
  let html = ''

  html += h('h1', {}, '湿实验下一轮设计预览报告')
  html += h('p', { class: 'muted' }, escapeHtml(`${data?.status || 'status unknown'} · objective ${data?.objective || library.objective || 'unknown'} · ${data?.planner_mode || 'planner mode unknown'}`))
  html += renderAnalysisScope(data?.analysis_scope)

  if (data?.blocked_reason) {
    html += h('h2', {}, '阻断原因')
    html += h('p', { class: 'muted' }, escapeHtml(data.blocked_reason))
  }

  html += h('h2', {}, 'Data Quality')
  html += '<div class="metric-grid">'
  html += h('div', { class: 'metric-card' }, h('div', { class: 'metric-label' }, 'Validated Singletons') + h('div', { class: 'metric-value' }, escapeHtml(quality.validated_single_mutants ?? 0)))
  html += h('div', { class: 'metric-card' }, h('div', { class: 'metric-label' }, 'Single Records') + h('div', { class: 'metric-value' }, escapeHtml(quality.single_mutant_records ?? 0)))
  html += h('div', { class: 'metric-card' }, h('div', { class: 'metric-label' }, 'Effect Fraction') + h('div', { class: 'metric-value' }, escapeHtml(quality.effect_disambiguation_fraction ?? 'unknown')))
  html += h('div', { class: 'metric-card' }, h('div', { class: 'metric-label' }, 'Quality') + h('div', { class: 'metric-value' }, escapeHtml(quality.quality_level || 'unknown')))
  html += '</div>'

  html += h('h2', {}, 'Next Round Library')
  html += '<div class="rec-card">'
  html += h('p', { class: 'muted' }, escapeHtml(`${library.schema_version || 'next_round_library_design_v1'} · ${library.status || 'unknown'} · structural source ${library.structural_distance_source || data?.structural_distance_source || 'none'}`))
  html += h('p', { class: 'muted' }, escapeHtml(`Validated singletons ${sourceEvidence.validated_single_mutants ?? 0} · Eligible pairs ${sourceEvidence.eligible_pair_candidates ?? 0} · Training eligible records ${sourceEvidence.training_eligible_feedback_records ?? 0}`))
  if (Array.isArray(library.single_point_pool) && library.single_point_pool.length) {
    html += h('h3', {}, 'Single Point Pool')
    html += '<table><thead><tr><th>Mutation</th><th>Variant</th><th>Use</th></tr></thead><tbody>'
    library.single_point_pool.forEach((item: any) => {
      html += `<tr><td class="code">${escapeHtml(item.mutation || '')}</td><td>${escapeHtml(item.variant_name || '')}</td><td>${escapeHtml(item.use || '')}</td></tr>`
    })
    html += '</tbody></table>'
  }
  if (Array.isArray(library.combination_pool) && library.combination_pool.length) {
    html += h('h3', {}, 'Combination Pool')
    html += '<table><thead><tr><th>Mutations</th><th>Status</th><th>Recommendation</th><th>Distance Sources</th></tr></thead><tbody>'
    library.combination_pool.forEach((item: any) => {
      html += `<tr><td class="code">${escapeHtml(Array.isArray(item.mutations) ? item.mutations.join(' + ') : '')}</td><td>${escapeHtml(item.status || '')}</td><td>${escapeHtml(item.epistasis_recommendation || '')}</td><td>${escapeHtml(Array.isArray(item.distance_sources) ? item.distance_sources.join(', ') : '')}</td></tr>`
    })
    html += '</tbody></table>'
  }
  html += '</div>'

  html += h('h2', {}, 'Combination Evidence Contract')
  html += '<div class="rec-card">'
  html += h('p', { class: 'muted' }, escapeHtml(`${combinationContract.schema_version || 'next_round_combination_evidence_contract_v1'} · ${combinationContract.status || 'unknown'}`))
  if (Array.isArray(combinationContract.pair_contracts) && combinationContract.pair_contracts.length) {
    html += '<table><thead><tr><th>Pair</th><th>Label</th><th>Recommendation</th><th>Distance Sources</th></tr></thead><tbody>'
    combinationContract.pair_contracts.forEach((item: any) => {
      html += `<tr><td class="code">${escapeHtml(Array.isArray(item.mutations) ? item.mutations.join(' + ') : '')}</td><td>${escapeHtml(item.label || '')}</td><td>${escapeHtml(item.epistasis_recommendation || '')}</td><td>${escapeHtml(Array.isArray(item.distance_sources) ? item.distance_sources.join(', ') : '')}</td></tr>`
    })
    html += '</tbody></table>'
  }
  if (Array.isArray(combinationContract.required_missing_evidence) && combinationContract.required_missing_evidence.length) {
    html += h('h3', {}, 'Required Missing Evidence')
    html += '<ul>'
    combinationContract.required_missing_evidence.forEach((item: string) => {
      html += h('li', { class: 'muted' }, escapeHtml(item))
    })
    html += '</ul>'
  }
  if (Array.isArray(combinationContract.must_not_claim) && combinationContract.must_not_claim.length) {
    html += h('h3', {}, 'Must Not Claim')
    html += '<ul>'
    combinationContract.must_not_claim.forEach((item: string) => {
      html += h('li', { class: 'muted' }, escapeHtml(item))
    })
    html += '</ul>'
  }
  if (combinationContract.boundary) html += h('p', { class: 'muted' }, escapeHtml(combinationContract.boundary))
  html += '</div>'

  if (Array.isArray(data?.required_next_measurements) && data.required_next_measurements.length) {
    html += h('h2', {}, 'Required Next Measurements')
    html += '<ul>'
    data.required_next_measurements.forEach((item: string) => {
      html += h('li', { class: 'muted' }, escapeHtml(item))
    })
    html += '</ul>'
  }
  if (data?.combination_rule) html += h('p', { class: 'muted' }, escapeHtml(data.combination_rule))
  if (data?.scientific_boundary || library.boundary) html += h('p', { class: 'muted' }, escapeHtml(data.scientific_boundary || library.boundary))

  return html
}

// --- Public API ---

export type ReportType = 'benchmark' | 'mutation_score' | 'rosetta_ddg' | 'md' | 'blast' | 'mutation_epistasis' | 'project_dbtl_trace' | 'feedback_iteration_plan'

const RENDERERS: Record<ReportType, (data: any) => string> = {
  benchmark: renderBenchmark,
  mutation_score: renderMutationScore,
  rosetta_ddg: renderRosetta,
  md: renderMD,
  blast: renderBlast,
  mutation_epistasis: renderMutationEpistasis,
  project_dbtl_trace: renderProjectDbtlTrace,
  feedback_iteration_plan: renderFeedbackIterationPlan,
}

const TITLES: Record<ReportType, string> = {
  benchmark: '蛋白基准报告',
  mutation_score: '突变优先级报告',
  rosetta_ddg: 'Rosetta ΔΔG 报告',
  md: '分子动力学报告',
  blast: 'BLAST 检索报告',
  mutation_epistasis: '组合上位性检查报告',
  project_dbtl_trace: 'DBTL 项目追踪报告',
  feedback_iteration_plan: '湿实验下一轮设计预览报告',
}

export function generateReport(type: ReportType, data: unknown): string {
  // 前置检查：数据有效性和 blocked 状态
  if (!data || typeof data !== 'object') {
    return renderBlockedReport(type, '工具未返回有效数据')
  }

  const payload = data as Record<string, any>
  const isBlocked =
    payload.status === 'blocked' ||
    payload.status === 'not_available' ||
    payload.foundation_gate?.status === 'blocked' ||
    payload.guardrail?.status === 'blocked'

  if (isBlocked) {
    const reason =
      payload.blocked_reason ||
      payload.reason ||
      payload.foundation_gate?.message ||
      payload.guardrail?.reason ||
      '未知原因'
    const missing = Array.isArray(payload.missing_evidence) ? payload.missing_evidence : []
    return renderBlockedReport(type, reason, missing)
  }

  const render = RENDERERS[type]
  const body = render(data)
  return `<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><title>${TITLES[type]}</title>${STYLES}</head><body>${body}<footer>由 Protein AI Platform 生成 &mdash; ${new Date().toISOString().slice(0, 10)}</footer></body></html>`
}

function renderBlockedReport(type: ReportType, reason: string, missingEvidence: string[] = []): string {
  const prerequisites: Record<ReportType, string[]> = {
    mutation_score: [
      '运行 enzyme_identity_profile 确认酶家族和编号',
      '确保输入序列或结构已通过预检',
      '检查 protein_benchmark 是否返回家族保护位点',
    ],
    benchmark: [
      '确保提供了有效的蛋白序列或结构',
      '检查 UniProt ID 或 PDB ID 是否正确',
    ],
    mutation_epistasis: [
      '确保已有单点突变的结构或评分数据',
      '检查突变位点坐标是否可用',
    ],
    rosetta_ddg: [
      '确保提供了有效的 PDB 结构',
      '检查突变列表格式是否正确',
    ],
    md: [
      '确保提供了有效的 PDB 结构',
      '检查分子动力学运行环境',
    ],
    blast: [
      '确保提供了有效的序列',
      '检查 BLAST 数据库连接',
    ],
    project_dbtl_trace: [
      '确保项目 ID 存在',
      '检查是否有实验反馈数据',
    ],
    feedback_iteration_plan: [
      '确保有湿实验反馈数据',
      '检查项目历史记录',
    ],
  }

  const steps = prerequisites[type] || ['检查工具执行日志']
  let body = h('h1', {}, TITLES[type])
  body += '<div class="rec-card">'
  body += h('h2', {}, '报告生成受阻')
  body += h('p', { class: 'muted' }, `原因：${escapeHtml(reason)}`)

  if (missingEvidence.length > 0) {
    body += h('h3', {}, '缺失的证据')
    body += '<ul>'
    missingEvidence.forEach(item => {
      body += h('li', { class: 'muted' }, escapeHtml(item))
    })
    body += '</ul>'
  }

  body += h('h3', {}, '需要的前置步骤')
  body += '<ul>'
  steps.forEach(s => {
    body += h('li', {}, escapeHtml(s))
  })
  body += '</ul>'
  body += '</div>'

  return `<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><title>${TITLES[type]}</title>${STYLES}</head><body>${body}<footer>由 Protein AI Platform 生成 &mdash; ${new Date().toISOString().slice(0, 10)}</footer></body></html>`
}

function defaultReportFilename(type: ReportType, data: unknown): string {
  const payload = data && typeof data === 'object' && !Array.isArray(data)
    ? data as Record<string, any>
    : {}
  const scope = payload.analysis_scope && typeof payload.analysis_scope === 'object' && !Array.isArray(payload.analysis_scope)
    ? payload.analysis_scope as Record<string, any>
    : null
  if (!scope) return `protein-${type}-report-${Date.now()}.html`
  const generatedAt = String(scope.generated_at || new Date().toISOString())
    .replace(/[:.]/g, '')
    .replace(/[^0-9TZ-]/g, '')
    .slice(0, 16)
  const scopeHash = String(scope.scope_hash || 'unknown')
    .replace(/[^a-zA-Z0-9_-]/g, '')
    .slice(0, 24) || 'unknown'
  return `protein-${type}-scope-${scopeHash}-${generatedAt}.html`
}

export function downloadReport(type: ReportType, data: unknown, filename?: string) {
  const html = generateReport(type, data)
  const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename || defaultReportFilename(type, data)
  a.click()
  URL.revokeObjectURL(url)
}

export function printReport(type: ReportType, data: unknown) {
  const html = generateReport(type, data)
  const win = window.open('', '_blank', 'width=900,height=700')
  if (win) {
    win.document.write(html)
    win.document.close()
    win.focus()
    setTimeout(() => win.print(), 500)
  }
}
