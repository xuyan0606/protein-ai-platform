# KWB-EnzymeDesigner 运行面板设计

## 目标

把真实模型和工具运行过程显示成专业、可信、先进的推理链路。  
不伪造模型思考，不展示虚假内部推理，只展示可审计状态、工具阶段、证据来源和评分结果。

## 页面模块

### 1. 顶部状态条

```text
KWB-EnzymeDesigner v0.1.0-rule-mvp
Multi-objective enzyme optimization
Status: Running / Completed / Blocked / Failed
Data: KWB-EnzymeDB local-dev
```

显示项：

- 模型名和版本。
- 数据版本。
- 当前状态。
- 本轮 task_id。
- 是否使用私有数据。

### 2. 推理链路时间线

```text
[done] Input parsing
[done] Structure gate
[done] Residue numbering
[running] Evidence retrieval
[pending] Multi-head scoring
[pending] Candidate ranking
[pending] Experiment planning
```

阶段定义：

| 阶段 | 说明 |
|---|---|
| Input parsing | 识别序列、结构、底物、目标和实验条件 |
| Structure gate | 判断上传结构、PDB、AlphaFold、ESMFold 来源 |
| Residue numbering | 确认链、编号体系和映射 |
| Evidence retrieval | 查询 KWB-EnzymeDB、公开数据库和工具结果 |
| Multi-head scoring | 多任务 head 评分 |
| Candidate ranking | 综合排序和 Go/Watch/No-Go |
| Experiment planning | 下一轮实验建议 |

前端事件建议展示字段：

| 字段 | 展示方式 |
|---|---|
| `stage_title` | 时间线主标签 |
| `progress_percent` | 顶部细进度条 |
| `status` | 图标状态：running/completed/blocked/failed |
| `evidence_counts` | 证据计数徽标 |
| `display_metrics` | 候选数量、Go/Watch/No-Go 数量、结构门控状态 |
| `quality_flags` | 本地-only、非泄漏、需实验验证等审计标记 |

### 3. 多头评分面板

每个候选突变展示：

```text
A42P
Overall: 78
Stability: 82
Activity Risk: 70
Substrate Fit: 64
Assay Success: 68
Decision: Watch
Confidence: 0.66
```

视觉建议：

- `Overall` 用主色。
- `Stability` 用蓝色。
- `Activity Risk` 用红/橙风险色。
- `Substrate Fit` 用紫色。
- `Assay Success` 用绿色。
- `No-Go` 候选必须明显标记，不进入默认推荐。

### 4. 证据来源面板

```text
Evidence used
- KWB private records: 12
- Public database records: 8
- Structure evidence: uploaded PDB, numbering verified
- Tool results: Foldseek, annotation bundle, catalytic-site guardrail
```

证据分层：

- 实验结构证据。
- 预测结构证据。
- 序列级证据。
- KWB 私有实验数据。
- 公开数据库/文献证据。
- 工具预测证据。
- 模型推断。

### 4.1 外部模型矩阵

显示国外工具链的真实状态，不把未安装或许可受限工具伪装成已运行。

```text
External model matrix
MMseqs2       MSA/conservation        not installed
Boltz-2       structure + affinity    not installed
Chai-1        complex prediction      license review required
ThermoMPNN    stability ddG proxy     not installed
CLEAN         EC/function check       not installed
LigandMPNN    ligand-aware design     license review required
AlphaFold 3   benchmark only          restricted
ESM3-open     benchmark/research      restricted
```

展示规则：

- `ready_for_local_evaluation` 才显示为可运行。
- `license_review_required` 显示为待合规评审。
- `non_commercial_or_restricted` 显示为 benchmark-only/restricted。
- `not_installed` 显示安装缺口和下一步，不显示运行中。
- 所有外部工具输出必须标记 evidence level，不能伪装成 KWB 湿实验结果。

### 5. 风险旗标

风险类型：

- `protected_catalytic`
- `near_active_site`
- `near_pocket`
- `numbering_uncertain`
- `low_structure_confidence`
- `activity_tradeoff`
- `substrate_fit_uncertain`
- `needs_wet_lab_validation`

### 6. 结构位点高亮

如果有结构 viewer：

- 候选突变：蓝色。
- 催化残基：红色。
- 口袋位点：紫色。
- 信号肽/结构域：绿色/黄色。
- 编号不确定区域：灰色。

## 运行事件格式

前端建议消费 `tool_event.schema.json` 风格事件：

```json
{
  "event_id": "evt_001",
  "session_id": "local-demo",
  "tool_name": "kwb_enzyme_designer",
  "status": "running",
  "quality_flags": [],
  "created_at": "2026-07-24T00:00:00+08:00"
}
```

## 禁止展示

- 不展示“模型正在思考”类不可验证内容。
- 不写“模拟了数十亿突变”这类虚假描述。
- 不把预测分数伪装为实验结果。
- 不隐藏 blocked/failed 原因。

## 最小前端交付

第一版只需要：

- 时间线。
- 多头评分表。
- 证据来源计数。
- 风险标签。
- Go/Watch/No-Go。

后续再接结构 3D 高亮。

## 本地演示事件

可用脚本生成前端演示事件：

```bash
python3 scripts/generate_runtime_trace_demo.py
```

输出：

```text
reports/runtime_trace_demo.jsonl
```
