# KWB-EnzymeDesigner 前端组件规格

## 目标组件

```text
KWBEnzymeDesignerCard
KWBRuntimeTimeline
KWBMultiHeadScoreGrid
KWBEvidenceSummary
KWBRiskFlags
```

## `KWBEnzymeDesignerCard`

职责：

- 展示模型版本和数据版本。
- 展示候选突变排序。
- 展示 Go/Watch/No-Go。
- 展示证据来源和风险。

## `KWBRuntimeTimeline`

状态：

- `pending`
- `running`
- `completed`
- `blocked`
- `failed`

阶段：

- Input parsing
- Structure gate
- Residue numbering
- Evidence retrieval
- Multi-head scoring
- Candidate ranking
- Experiment planning

## `KWBMultiHeadScoreGrid`

列：

- Mutation
- Overall
- Stability
- Activity Risk
- Substrate Fit
- Assay Success
- Confidence
- Decision

## `KWBEvidenceSummary`

展示：

- KWB private records
- Public database records
- Structure evidence
- Sequence-level only
- Requires wet-lab validation
- Evidence refs

## `KWBRiskFlags`

风险标签：

- `protected_catalytic`
- `near_active_site`
- `near_pocket`
- `numbering_uncertain`
- `low_structure_confidence`
- `activity_tradeoff`
- `substrate_fit_uncertain`
- `needs_wet_lab_validation`

## 视觉原则

- 使用平台现有 `bg-card`、`border-border`、`text-muted-foreground`、`bg-primary` token。
- 不做虚假“思考过程”。
- 显示真实工具状态和证据数量。
- No-Go 使用明确风险色。
- Watch 使用 amber。
- Go 使用 emerald。

