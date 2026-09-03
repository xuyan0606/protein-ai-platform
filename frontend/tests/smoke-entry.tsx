import { createRoot } from 'react-dom/client'
import { AnnotationBundleCard } from '@/components/analysis/AnnotationBundleCard'
import { MDResultView } from '@/components/analysis/MDResultView'
import { MutationScoreCard } from '@/components/analysis/MutationScoreCard'
import { ToolCallCard } from '@/components/chat/ToolCallCard'
import { MarkdownView } from '@/components/chat/MarkdownView'
import '@/index.css'

const bundlePayload = {
  found: true,
  evidence_source: {
    source: 'annotation_bundle',
    status: 'degraded',
    mode: 'local_database_or_heuristic_bundle',
    live_query_executed: false,
    reason: 'Smoke fixture uses local annotation data.',
  },
  query: {
    uniprot_id: 'DEMO388A',
    sequence_length: 388,
    has_curated_enzyme: true,
  },
  interpro: {
    found: true,
    query: { uniprot_id: 'DEMO388A', sequence_length: 388 },
    summary: {
      curated_interpro_count: 3,
      pfam_domain_count: 1,
      heuristic_count: 0,
    },
    annotations: [
      {
        interpro_id: 'IPR000073',
        name: 'Alpha/beta hydrolase',
        entry_type: 'family',
        source: 'interpro',
        regions: [{ start: 240, end: 310 }],
        go_terms: ['GO:0016787 hydrolase activity'],
      },
    ],
  },
  catalytic_sites: {
    found: true,
    query: { uniprot_id: 'DEMO388A', sequence_length: 388 },
    curated_sites: [
      {
        source: 'M-CSA',
        mechanism_name: 'Ser-His-Asp triad',
        residues: [{ position: 252, residue: 'S', role: 'nucleophile', confidence: 0.98 }],
      },
    ],
    inferred_guardrails: [],
    protected_positions: [252],
  },
  signal_peptide: {
    found: true,
    query: { uniprot_id: 'DEMO388A', sequence_length: 388 },
    has_signal_peptide: false,
    confidence: 0.22,
    predicted_type: 'Sec/SPI',
    cleavage_site: null,
    regions: {
      n_region: { start: 1, end: 3, positive_residues: 1 },
      h_region: { start: 4, end: 10, hydrophobic_ratio: 0.71 },
      c_region: { start: 11, end: 18 },
    },
    model: 'heuristic-v1',
  },
}

const errorPayload = {
  found: false,
  error: 'Provide sequence or uniprot_id',
  interpro: {},
  catalytic_sites: {},
  signal_peptide: {},
}

const mdPayload = {
  status: 'completed',
  is_real_md: true,
  engine: 'GROMACS',
  ensemble: 'NVT',
  pressure_bar: 1.0,
  salt_concentration_m: 0.15,
  wild_type: {
    simulation_parameters: {
      sequence_length: null,
      simulation_time_ns: 0.01,
      temperature_k: 310,
      force_field: 'amber99sb-ildn',
      water_model: 'tip3p',
      estimated_atom_count: 2833,
    },
    structural_stability: {
      rmsd_equilibrated_nm: 0.12,
      rmsd_final_nm: 0.14,
      rmsd_drift_nm: 0.02,
      mean_rmsf_nm: 0.08,
      is_stable: true,
    },
    compactness: {
      radius_of_gyration_initial_nm: 1.62,
      radius_of_gyration_final_nm: 1.58,
      rg_change_nm: -0.04,
      sasa_initial_nm2: 118.5,
      sasa_final_nm2: 115.1,
    },
    interactions: {
      intra_protein_hbonds: null,
      protein_solvent_hbonds: null,
    },
    energetics: {
      potential_energy_kjmol: null,
      kinetic_energy_kjmol: null,
      total_energy_kjmol: null,
    },
    flexible_regions: [
      { residues: '45', mean_rmsf_nm: 0.16, interpretation: 'high-mobility residue from real RMSF analysis' },
    ],
    note: 'Fixture MD result',
  },
  artifacts: [
    {
      name: 'rmsd.xvg',
      size: 828,
      object_name: 'md/93f6c13748fc4b8e86a898ef857d3918/1d837466febe496594e75e0d672b7412.xvg',
      download_url: '/api/files/md/93f6c13748fc4b8e86a898ef857d3918/1d837466febe496594e75e0d672b7412.xvg/download?filename=rmsd.xvg',
      category: 'analysis',
    },
  ],
  artifact_manifest: {
    version: 1,
    total_count: 38,
    total_size: 24764044,
    groups: {
      analysis: [
        {
          name: 'rmsd.xvg',
          size: 828,
          object_name: 'md/93f6c13748fc4b8e86a898ef857d3918/1d837466febe496594e75e0d672b7412.xvg',
          download_url: '/api/files/md/93f6c13748fc4b8e86a898ef857d3918/1d837466febe496594e75e0d672b7412.xvg/download?filename=rmsd.xvg',
        },
      ],
    },
  },
}

const mutationPayload = {
  sequence_length: 388,
  sequence_preview: 'APAQIVGRSTFQIDQVASGKVYKNGPMAMMQTYNKYAHVGAVAPAAVVAAAAAAQT...',
  engineering_goal: 'thermostability',
  active_site_positions: [86, 275],
  active_site_position_sources: {
    '86': ['identity_profile'],
    '275': ['identity_profile'],
  },
  candidate_table_status: 'exploratory_requires_objective_evidence',
  objective_gate: {
    status: 'blocked',
    objective: 'thermostability',
    module: 'thermostability',
    candidate_output_allowed: false,
    missing_evidence: ['Provide baseline Tm, half-life, or thermal residual activity context.'],
  },
  summary: {
    total_positions: 388,
    tier_1_count: 2,
    tier_2_count: 1,
    tier_3_count: 385,
    never_mutate_count: 2,
    never_mutate_positions: [86, 275],
    catalytic_guardrail_enabled: true,
    candidate_table_status: 'exploratory_requires_objective_evidence',
  },
  guardrails: {
    protected_positions: [86, 275],
    rule: 'Protected catalytic positions and adjacent residues are penalized or blocked from recommendation.',
  },
  strategy: {
    objective: '提高热稳定性，同时尽量保持催化活性、表达和可溶性。',
    design_principle: '优先加固非催化、可突变的柔性环和局部疏松区域。',
    screening_logic: ['排除催化位点', '优先表面暴露残基', '先做单点验证，再逐步组合'],
    experiment_plan: [
      { priority: 'P1', scope: '单点候选', purpose: '验证最高优先级位点', gate: 'Tm 或热处理残余活性改善且活性保留' },
      { priority: 'P2', scope: '第二梯队单点', purpose: '扩展机制不同的候选', gate: '表达、稳定性和活性复核通过' },
    ],
    confidence_boundary: '位点排序是计算筛选假设，不等同于实测 ΔTm。',
  },
  tier_1_candidates: [
    {
      position: 42,
      user_position: 'A:42',
      pdb_position: 'A:42',
      uniprot_position: 42,
      numbering_status: 'PDB/UniProt 已映射',
      wild_type: 'G',
      composite_priority: 8.4,
      tier: 1,
      mutation_type: '增加loop刚性',
      logic: '位于非催化柔性区，表面暴露且远离 D86/D275 保护位点；Gly->Pro 可降低 loop 构象熵。',
      recommended_mutations: [
        { mutation: 'G42P', type: 'loop rigidification', purpose: '降低局部构象熵，提高热稳定性' },
      ],
      active_site_distance_residues: 44,
      expected_effect: '候选用于提高局部结构稳定性；Tm/热处理残余活性需实验确认',
      risk_flags: ['Gly->Pro可能误伤必要柔性', '目标实验上下文不足，候选为探索性排单'],
      experiment_priority: 'P1',
      experiment_action: '构建 G42P 单点；同步检测表达、可溶性、Tm、热处理残余活性和比活。',
      candidate_evidence_status: 'exploratory_requires_objective_evidence',
      objective_missing_evidence: ['Provide baseline Tm, half-life, or thermal residual activity context.'],
    },
    {
      position: 118,
      user_position: 118,
      pdb_position: null,
      uniprot_position: 118,
      numbering_status: 'PDB 未映射；使用用户/UniProt 编号排单',
      wild_type: 'K',
      composite_priority: 7.8,
      tier: 1,
      mutation_type: '表面电荷网络优化',
      logic: '表面 Lys 位点，保守性低，适合测试盐桥/氢键网络方向。',
      recommended_mutations: [
        { mutation: 'K118E', type: 'surface charge', purpose: '测试表面电荷网络增稳' },
        { mutation: 'K118Q', type: 'surface polarity', purpose: '降低局部正电荷扰动' },
      ],
      active_site_distance_residues: 32,
      expected_effect: '候选用于提高局部结构稳定性；Tm/热处理残余活性需实验确认',
      risk_flags: ['需复测表达和活性保持'],
      experiment_priority: 'P1',
      experiment_action: '并行构建 K118E/K118Q；先做小规模表达和热稳定性初筛。',
      candidate_evidence_status: 'exploratory_requires_objective_evidence',
      objective_missing_evidence: ['Provide baseline Tm, half-life, or thermal residual activity context.'],
    },
  ],
  tier_2_candidates: [
    {
      position: 211,
      user_position: 211,
      pdb_position: null,
      uniprot_position: null,
      numbering_status: '未映射',
      wild_type: 'S',
      composite_priority: 6.2,
      tier: 2,
      mutation_type: '表面电荷优化',
      logic: '表面位点，适合做第二梯队单点验证。',
      recommended_mutations: [
        { mutation: 'S211T', type: 'polar tuning', purpose: '保守调整局部氢键网络' },
      ],
      active_site_distance_residues: 64,
      expected_effect: '目标性质改善方向需实验验证',
      risk_flags: ['第二梯队候选，优先级低于 P1'],
      experiment_priority: 'P2',
      experiment_action: 'Watch：仅在 P1 无明显收益或需要机制补充时构建 S211T。',
      candidate_evidence_status: 'exploratory_requires_objective_evidence',
      objective_missing_evidence: ['Provide baseline Tm, half-life, or thermal residual activity context.'],
    },
  ],
  all_positions: [
    { position: 86, wild_type: 'D', composite_priority: 0, tier: 3, logic: '催化保护位点', recommended_mutations: [], is_protected: true, risk_flags: ['催化/功能保护位点，禁止作为首轮候选'], experiment_priority: 'No-Go' },
    { position: 275, wild_type: 'D', composite_priority: 0, tier: 3, logic: '催化保护位点', recommended_mutations: [], is_protected: true, risk_flags: ['催化/功能保护位点，禁止作为首轮候选'], experiment_priority: 'No-Go' },
  ],
}

const blockedMutationPayload = {
  ...mutationPayload,
  candidate_table_status: 'blocked_by_identity_gate',
  identity_gate: {
    status: 'blocked',
    identity_status: 'unresolved',
    reason: 'enzyme identity or residue numbering is not confirmed enough',
  },
  summary: {
    ...mutationPayload.summary,
    tier_1_count: 0,
    tier_2_count: 0,
    tier_3_count: 0,
    never_mutate_count: 0,
    never_mutate_positions: [],
  },
  active_site_positions: [],
  tier_1_candidates: [],
  tier_2_candidates: [],
  all_positions: [],
}

const root = document.getElementById('root')

if (!root) {
  throw new Error('Missing root element for smoke tests')
}

createRoot(root).render(
  <main className="min-h-screen bg-slate-50 p-6 text-slate-900">
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <section data-testid="mutation-score-card">
        <MutationScoreCard data={mutationPayload} />
      </section>

      <section data-testid="blocked-mutation-score-card">
        <MutationScoreCard data={blockedMutationPayload} />
      </section>

      <section data-testid="markdown-card" className="rounded-xl border border-slate-200 bg-white p-5">
        <MarkdownView
          content={`# 388 aa 蛋白稳定性提升实验执行清单

## 目标

在尽量不损伤功能前提下，筛选出稳定性更高的突变体。

---

## 数据记录模板

| 变体 | 设计类型 | 表达 | 可溶性 | Tm | 活性保留 |
|---|---|---|---|---|---|
| WT | 基线 | 基线 | 基线 | 基线 | 基线 |
| M1 | 环区刚化 | 待测 | 待测 | 待测 | 待测 |

## Go / No-Go 决策标准

- 表达正常
- 可溶性不下降
- Tm 提升 >= 2°C
- 活性保留 >= 80-90%

## 最终输出目标

第一轮结束后，应输出优质单点突变和组合突变候选。`}
        />
      </section>

      <section data-testid="streaming-table-card" className="rounded-xl border border-slate-200 bg-white p-5">
        <MarkdownView
          streaming
          content={`| 结果 | 置信度 |---
|---|---||
| Unknown enzyme family | 无有效分类 | enzyme_function
| 待补充序列 | 需要用户确认 | input_required`}
        />
      </section>

      <section data-testid="ec-table-card" className="rounded-xl border border-slate-200 bg-white p-5">
        <MarkdownView
          content={`| EC编号 | 级别 | 信心 | 名称 |
|---|---|---|---|---|
| 1 | 3.1.1.3 | 水解酶 | 媒介 | 脂肪酶/酯酶 |`}
        />
      </section>

      <section data-testid="fragmented-table-card" className="rounded-xl border border-slate-200 bg-white p-5">
        <MarkdownView
          content={`维度

| 当前判断 | 置信度 | 依据与限制 | |---

| --- | ---: | --- | | 热稳定性

| 未定 | 极低 | 缺少 DSF/DSC、热失活和结构柔性分析 | | 酸稳定性

| 未定 | 极低 | 缺少 pH-残余活性曲线、pI 和表面电荷分布 | | 碱稳定性

| 未定 | 极低 | 同上 | | 酶家族/催化位点

| 未定 | 极低 | Foldseek 失败，未提供序列注释或配体信息 | | 可工程化表面位点

| 未定 | 极低 | 缺少溶剂可及面积、盐桥和保守性数据 |`}
        />
      </section>

      <section data-testid="toolcall-card">
        <ToolCallCard
          toolCall={{
            id: 'tool-1',
            name: 'annotation_bundle',
            status: 'completed',
            duration: 1.2,
            resultPreview: JSON.stringify(bundlePayload),
          }}
        />
      </section>

      <section data-testid="bundle-card">
        <AnnotationBundleCard data={bundlePayload} />
      </section>

      <section data-testid="bundle-error-card">
        <AnnotationBundleCard data={errorPayload} />
      </section>

      <section data-testid="md-card">
        <MDResultView
          data={mdPayload}
          taskId="8015c0e6-f073-47ee-910d-b1fbe8d0d12d"
        />
      </section>
    </div>
  </main>
)
