# KWB-EnzymeDesigner 规则 MVP 设计

## 目标

第一版不训练新模型，先用现有平台工具、KWB 数据库和规则评分实现一个可运行、可解释、可评测的 MVP。

MVP 对外表现为一个工具：

```text
kwb_enzyme_designer
```

它的职责是根据输入和已有工具结果，输出统一候选突变排序、多头评分、证据引用和下一轮实验建议。

## 与 GPT-5.6 的分工

| 模块 | 职责 |
|---|---|
| GPT-5.6 | 用户意图理解、工具规划、报告组织、自然语言解释 |
| KWB-EnzymeDesigner MVP | 专业评分、候选排序、风险门控、证据聚合 |
| 现有工具链 | 结构预测、注释、编号映射、Foldseek、MD、配体预处理 |
| KWB-EnzymeDB | 私有证据、历史实验、文献整理、失败样本 |

## 输入

核心输入来自 `KWB-EnzymeCase`：

- `enzyme.sequence`
- `structure.object_name`
- `substrate.name` / `substrate.smiles`
- `objective.primary_goal`
- `assay_condition`
- `mutations`
- `evidence`
- `tool_results`

## 前置门控

### 上传结构场景

```text
uploaded PDB
  -> parse structure
  -> confirm chain
  -> residue_numbering_gate
  -> annotation_bundle
  -> structure_search_foldseek
  -> KWB-EnzymeDesigner scoring
```

禁止：

- 编号未确认时给出位点级强结论。
- 上传 PDB 可用时优先提交 ESMFold。
- 引用旧任务结构结果。

### 仅序列场景

```text
sequence
  -> predict_properties
  -> esmfold_folding
  -> annotation_bundle
  -> KWB-EnzymeDesigner scoring
```

允许：

- 先做序列级理化性质分析。

禁止：

- 在结构预测前给出口袋、距离、暴露度、催化网络强结论。

### 结构缺失场景

如果既没有序列也没有结构，只返回 `blocked`：

```json
{
  "status": "blocked",
  "blocked_reason": "missing_sequence_or_structure",
  "required_inputs": ["sequence", "uploaded_pdb", "pdb_id", "uniprot_id"]
}
```

## MVP 评分逻辑

总分 0-100。

```text
overall_score =
  0.30 * mutation_rank_score
  + 0.25 * stability_score
  + 0.20 * activity_safety_score
  + 0.15 * substrate_fit_score
  + 0.10 * assay_success_score
```

### `mutation_rank_score`

来源：

- `mutation_priority_score`
- KWB Lipase Evidence DB
- 历史实验反馈
- 同家族文献突变

规则：

- 有同位点正向实验证据：+20。
- 有同类型突变正向证据：+10。
- 多次失败样本：-20。
- 位点编号不确定：-25。

### `stability_score`

来源：

- 氨基酸替换类型。
- 二级结构/loop/表面信息。
- MD 或 plan-only MD 风险。
- 历史 Tm/半衰期数据。

规则：

- loop 刚性增强候选：+10。
- 表面盐桥/电荷网络合理：+8。
- 核心疏水破坏：-20。
- 低置信结构区域：降级置信度。

### `activity_safety_score`

来源：

- `catalytic_site_lookup`
- `annotation_bundle`
- `residue_numbering_gate`
- SIFTS/InterPro/M-CSA 类证据

规则：

- 催化残基：直接 `no_go`。
- 催化邻近核心：最高 `watch`。
- 口袋边缘：保留但加风险标签。
- 无结构证据：不得给低风险强结论。

### `substrate_fit_score`

来源：

- `ligand_preprocess`
- docking score
- 口袋位点
- 底物相关历史记录

规则：

- 无底物输入：标记 `not_evaluated`，不扣总分但降低总置信度。
- 有底物但未对接：仅输出弱推断。
- 对接或复合物证据存在：参与排序。

### `assay_success_score`

来源：

- 数据质量。
- assay 条件完整度。
- 历史相似任务成功率。
- 表达体系风险。

规则：

- assay 条件完整：+10。
- 表达体系有历史成功记录：+10。
- 目标互相冲突未说明：-15。
- 只有预测无实验证据：限制上限。

## 决策规则

| 条件 | 决策 |
|---|---|
| overall >= 80 且无高风险 | `go` |
| overall 60-79 或证据不足 | `watch` |
| 催化核心/编号不确定/历史强负证据 | `no_go` |

## 输出格式

输出必须符合 `contracts/kwb_enzyme_designer.schema.json`。

示例：

```json
{
  "model": {
    "name": "KWB-EnzymeDesigner",
    "version": "0.1.0-rule-mvp",
    "data_version": "local-dev"
  },
  "candidates": [
    {
      "mutation": "A42P",
      "overall_score": 78,
      "stability_score": 82,
      "activity_risk_score": 70,
      "substrate_fit_score": 64,
      "assay_success_score": 68,
      "confidence": 0.66,
      "decision": "watch",
      "rationale": "Loop rigidification candidate with private evidence but near pocket, requires activity assay.",
      "risk_flags": ["near_pocket", "needs_activity_validation"],
      "evidence_refs": ["kwb-private-demo-001", "tool-catalytic-demo-001"],
      "next_experiment": "Test A42P as a single mutant at pH 7.5 and 55C before combination."
    }
  ],
  "evidence_summary": {
    "kwb_private_records": 1,
    "public_database_records": 0,
    "structure_evidence": "uploaded_pdb_numbering_verified",
    "sequence_level_only": false,
    "requires_wet_lab_validation": true
  }
}
```

## 平台接入草案

后端工具文件：

```text
backend/app/tools/kwb_enzyme_designer.py
```

注册：

```python
ToolRegistry.register(
    name="kwb_enzyme_designer",
    description="KWB proprietary multi-objective enzyme optimization model.",
    parameters={...},
    handler=kwb_enzyme_designer,
    is_async=True,
    category="enzyme_engineering",
    timeout_seconds=600,
)
```

Agent 规划规则：

- 有上传结构：`residue_numbering_gate` 完成后调用。
- 仅序列：`esmfold_folding` 完成或被用户明确选择跳过后调用。
- 有底物：配体预处理/对接结果可作为增强证据，但不是硬依赖。
- 缺少序列和结构：阻断并追问。

## MVP 验收

- 跑通 `bench-uploaded-pdb-numbering-001`。
- 跑通 `bench-thermo-sequence-only-001`。
- 对催化核心突变输出 `no_go`。
- 证据不足时输出 `watch` 或 `blocked`，不伪造结论。
- 输出多头评分和证据引用。

