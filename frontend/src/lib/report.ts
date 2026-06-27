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

function h(tag: string, attrs: Record<string, string> = {}, ...children: string[]): string {
  const attrStr = Object.entries(attrs).map(([k, v]) => ` ${k}="${v}"`).join('')
  return `<${tag}${attrStr}>${children.join('')}</${tag}>`
}

// --- Benchmark Report ---

function renderBenchmark(data: any): string {
  const f = (n: number, d = 2) => n?.toFixed(d) ?? '—'
  let html = ''

  // Header
  html += h('h1', {}, `Protein Benchmark Report`)
  html += h('p', { class: 'muted' }, `${data.query_info?.length || '?'} residues · ${data.family?.ec || 'EC unknown'} · ${data.family?.mechanism || ''}`)

  // Properties
  html += h('h2', {}, 'Physicochemical Properties')
  const p = data.properties || {}
  html += '<div class="metric-grid">'
  html += h('div', { class: 'metric-card' }, h('div', { class: 'metric-label' }, 'MW') + h('div', { class: 'metric-value' }, `${f(p.molecular_weight_kda, 1)} kDa`))
  html += h('div', { class: 'metric-card' }, h('div', { class: 'metric-label' }, 'pI') + h('div', { class: 'metric-value' }, `${f(p.isoelectric_point)}`))
  html += h('div', { class: 'metric-card' }, h('div', { class: 'metric-label' }, 'GRAVY') + h('div', { class: 'metric-value' }, `${f(p.gravy, 4)}`))
  html += h('div', { class: 'metric-card' }, h('div', { class: 'metric-label' }, 'Gly→Pro Candidates') + h('div', { class: 'metric-value' }, `${p.gly_count || 0}`))
  html += '</div>'

  // Conservation
  const cons = data.conservation_analysis || {}
  html += h('h2', {}, 'Conservation Analysis')
  html += h('p', { class: 'muted' }, `Highly conserved: ${cons.highly_conserved_count} | Variable: ${cons.variable_count}`)

  // Motifs
  if (data.family_motifs?.length) {
    html += h('h2', {}, 'Conserved Motifs')
    data.family_motifs.forEach((m: any) => {
      const found = !m.found_at?.includes('not detected')
      html += `<div class="motif-row"><span><strong>${m.region}</strong> ${m.pattern || ''}</span><span class="badge ${found ? 'badge-green' : 'badge-red'}">${found ? 'Found' : 'Not detected'}</span></div>`
    })
  }

  // Recommendations
  if (data.recommendations?.length) {
    html += h('h2', {}, 'Engineering Recommendations')
    data.recommendations.forEach((r: any) => {
      html += `<div class="rec-card">`
      html += h('strong', {}, `[P${r.priority}] ${r.category} — ${r.action}`)
      if (r.rationale) html += h('p', { class: 'muted' }, r.rationale)
      if (r.candidates?.length) html += h('p', { class: 'muted' }, `Top candidates: ${r.candidates.slice(0, 5).map((c: any) => c.mutation).join(', ')}`)
      html += '</div>'
    })
  }

  return html
}

// --- Mutation Score Report ---

function renderMutationScore(data: any): string {
  const f = (n: number, d = 1) => n?.toFixed(d) ?? '—'
  let html = ''

  html += h('h1', {}, 'Mutation Priority Score Report')
  html += h('p', { class: 'muted' }, `${data.summary?.total_positions || '?'} positions scanned · Goal: ${data.engineering_goal || 'general'}`)

  // Summary
  html += h('h2', {}, 'Summary')
  html += '<div class="metric-grid">'
  html += h('div', { class: 'metric-card' }, h('div', { class: 'metric-label' }, 'Tier 1 (Priority >7)') + h('div', { class: 'metric-value', style: 'color:#059669' }, `${data.summary?.tier_1_count || 0}`))
  html += h('div', { class: 'metric-card' }, h('div', { class: 'metric-label' }, 'Tier 2 (5-7)') + h('div', { class: 'metric-value', style: 'color:#d97706' }, `${data.summary?.tier_2_count || 0}`))
  html += h('div', { class: 'metric-card' }, h('div', { class: 'metric-label' }, 'Never Mutate') + h('div', { class: 'metric-value', style: 'color:#dc2626' }, `${data.summary?.never_mutate_count || 0}`))
  html += '</div>'

  if (data.summary?.never_mutate_positions?.length) {
    html += h('p', { class: 'muted' }, `Never mutate positions: ${data.summary.never_mutate_positions.join(', ')}`)
  }

  function renderTierTable(candidates: any[], tier: number, title: string) {
    if (!candidates?.length) return ''
    let h2 = `<h2>${title}</h2>`
    h2 += '<table><thead><tr><th>Position</th><th>Type</th><th>Score</th><th>Logic</th><th>Recommended</th></tr></thead><tbody>'
    candidates.forEach((c: any) => {
      const muts = Array.isArray(c.recommended_mutations)
        ? c.recommended_mutations.map((m: any) => typeof m === 'string' ? m : m.mutation).join(', ')
        : String(c.recommended_mutations || '')
      const typeTag = c.mutation_type ? `<span class="badge ${tier === 1 ? 'badge-green' : 'badge-amber'}">${c.mutation_type}</span>` : '—'
      h2 += `<tr><td class="code">${c.wild_type}${c.position}</td><td>${typeTag}</td><td><strong>${f(c.composite_priority)}</strong></td><td class="muted" style="max-width:300px">${c.logic || ''}</td><td class="code">${muts}</td></tr>`
    })
    h2 += '</tbody></table>'
    return h2
  }

  html += renderTierTable(data.tier_1_candidates, 1, 'Tier 1 — Priority Candidates')
  html += renderTierTable(data.tier_2_candidates, 2, 'Tier 2 — Optional Candidates')

  return html
}

// --- MD Report ---

function renderMD(data: any): string {
  const f = (n: number, d = 2) => n?.toFixed(d) ?? '—'
  const wt = data.wild_type || {}
  const s = wt.structural_stability || {}
  const c = wt.compactness || {}
  const e = wt.energetics || {}
  const p = wt.simulation_parameters || {}

  let html = ''
  html += h('h1', {}, 'MD Simulation Report')
  html += h('p', { class: 'muted' }, `${data.engine || ''} · ${data.ensemble || ''} · ${p.simulation_time_ns}ns · ${p.temperature_k}K · ${p.force_field}/${p.water_model}`)

  html += h('h2', {}, 'Structural Stability')
  html += '<div class="metric-grid">'
  html += h('div', { class: 'metric-card' }, h('div', { class: 'metric-label' }, 'RMSD Final') + h('div', { class: 'metric-value' }, `${f(s.rmsd_final_nm)} nm`))
  html += h('div', { class: 'metric-card' }, h('div', { class: 'metric-label' }, 'RMSD Drift') + h('div', { class: 'metric-value', style: s.is_stable ? 'color:#059669' : 'color:#dc2626' }, `${f(s.rmsd_drift_nm)} nm`))
  html += h('div', { class: 'metric-card' }, h('div', { class: 'metric-label' }, 'Mean RMSF') + h('div', { class: 'metric-value' }, `${f(s.mean_rmsf_nm)} nm`))
  html += h('div', { class: 'metric-card' }, h('div', { class: 'metric-label' }, 'Stable?') + h('div', { class: 'metric-value' }, s.is_stable ? 'YES' : 'NO'))
  html += '</div>'

  html += h('h2', {}, 'Energetics')
  html += `<p><strong>Potential:</strong> ${f(e.potential_energy_kjmol, 0)} kJ/mol &nbsp; <strong>Kinetic:</strong> ${f(e.kinetic_energy_kjmol, 0)} kJ/mol &nbsp; <strong>Total:</strong> ${f(e.total_energy_kjmol, 0)} kJ/mol</p>`

  if (data.mutants?.length) {
    html += h('h2', {}, 'Mutant Comparison')
    html += '<table><thead><tr><th>Mutation</th><th>ΔΔG (kJ/mol)</th><th>ΔRMSF (nm)</th><th>Stable</th></tr></thead><tbody>'
    data.mutants.forEach((m: any) => {
      html += `<tr><td class="code">${m.mutation}</td><td style="color:${m.stability_delta > 0 ? '#dc2626' : '#059669'}">${m.stability_delta > 0 ? '+' : ''}${m.stability_delta}</td><td>${f(m.rmsf_change_mean, 3)}</td><td>${m.stable ? 'YES' : 'NO'}</td></tr>`
    })
    html += '</tbody></table>'
  }

  return html
}

// --- Blast Report ---

function renderBlast(data: any): string {
  let html = ''
  html += h('h1', {}, 'BLAST Search Report')
  html += h('p', { class: 'muted' }, `${data.program || 'blastp'} against ${data.database || 'nr'} · ${data.results_count || 0} hits`)

  if (data.results?.length) {
    html += '<table><thead><tr><th>#</th><th>Hit</th><th>Organism</th><th>Identity</th><th>E-value</th></tr></thead><tbody>'
    data.results.forEach((hit: any) => {
      html += `<tr><td>${hit.hit_num}</td><td><strong>${hit.definition || hit.id}</strong><br><span class="muted">${hit.accession}</span></td><td>${hit.organism || '—'}</td><td><strong>${hit.best_identity_percent?.toFixed(1) || '—'}%</strong></td><td class="code">${hit.best_e_value || '—'}</td></tr>`
    })
    html += '</tbody></table>'
  }

  return html
}

// --- Public API ---

export type ReportType = 'benchmark' | 'mutation_score' | 'md' | 'blast'

const RENDERERS: Record<ReportType, (data: any) => string> = {
  benchmark: renderBenchmark,
  mutation_score: renderMutationScore,
  md: renderMD,
  blast: renderBlast,
}

const TITLES: Record<ReportType, string> = {
  benchmark: 'Protein Benchmark Report',
  mutation_score: 'Mutation Priority Score Report',
  md: 'MD Simulation Report',
  blast: 'BLAST Search Report',
}

export function generateReport(type: ReportType, data: unknown): string {
  const render = RENDERERS[type]
  const body = render(data)
  return `<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>${TITLES[type]}</title>${STYLES}</head><body>${body}<footer>Generated by Protein AI Platform &mdash; ${new Date().toISOString().slice(0, 10)}</footer></body></html>`
}

export function downloadReport(type: ReportType, data: unknown, filename?: string) {
  const html = generateReport(type, data)
  const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename || `protein-${type}-report-${Date.now()}.html`
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
