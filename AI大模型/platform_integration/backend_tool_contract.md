# `kwb_enzyme_designer` 后端工具接入合同

本文件描述后续如何把本地研发的 `KWB-EnzymeDesigner` 接入现有酶蛋白 AI 平台。当前只作为本地研发设计，不修改线上服务。

## 接入点

目标文件：

```text
backend/app/tools/kwb_enzyme_designer.py
backend/app/tools/registry.py
backend/app/core/agent_graph.py
frontend/src/components/chat/ToolCallCard.tsx
frontend/src/components/analysis/KWBEnzymeDesignerCard.tsx
```

## 工具名称

```text
kwb_enzyme_designer
```

## 工具类别

```text
enzyme_engineering
```

## 与 GPT-5.6 的关系

- GPT-5.6：主控、任务拆解、工具编排、报告合成。
- KWB-EnzymeDesigner：专业酶改造模型，返回候选突变、多头分数、证据、风险和下一步实验。
- 两者不冲突；平台应把 KWB 模型注册为工具，而不是替换主控模型。

本地 adapter 草案：

```text
platform_integration/kwb_tool_adapter_stub.py
```

## 必须前置条件

至少满足一个：

- 有 `sequence`。
- 有 `structure_object`。
- 有 `pdb_id`。
- 有 `uniprot_id`。

结构依赖强结论必须满足：

- 上传结构已解析。
- 链 ID 明确。
- 残基编号门控完成。

## 参数 schema 草案

```json
{
  "type": "object",
  "properties": {
    "enzyme_name": { "type": "string" },
    "sequence": { "type": "string" },
    "structure_object": { "type": "string" },
    "pdb_id": { "type": "string" },
    "substrate": { "type": "string" },
    "objective": { "type": "string" },
    "assay_condition": { "type": "object" },
    "known_mutations": {
      "type": "array",
      "items": { "type": "string" }
    },
    "evidence_context": {
      "type": "array",
      "items": { "type": "object" }
    },
    "tool_result_refs": {
      "type": "array",
      "items": { "type": "string" }
    }
  },
  "required": ["objective"]
}
```

## 返回合同

返回 `contracts/kwb_enzyme_designer.schema.json` 中 `result` 对象：

- `model`
- `candidates`
- `evidence_summary`

## Agent 规划规则

### 上传结构

```text
parse uploaded file
-> residue_numbering_gate
-> annotation_bundle
-> structure_search_foldseek
-> kwb_enzyme_designer
```

### 仅序列

```text
predict_properties
-> esmfold_folding
-> annotation_bundle
-> kwb_enzyme_designer
```

### 有配体

```text
ligand_preprocess
-> docking or ligand readiness
-> kwb_enzyme_designer
```

## 错误合同

| code | reason | recovery |
|---|---|---|
| `missing_sequence_or_structure` | 缺少序列或结构 | 请求用户提供 FASTA/PDB/PDB ID/UniProt ID |
| `numbering_not_verified` | 编号未确认 | 先调用 `residue_numbering_gate` |
| `insufficient_evidence` | 证据不足 | 降级为 `watch`，要求实验验证 |
| `model_runtime_unavailable` | KWB 模型服务不可用 | 回退到规则 MVP 或现有工具报告 |

## 审计字段

每次调用必须记录：

- user_id
- project_id
- conversation_id
- session_id
- request_turn_id
- task_id
- model version
- data version
- input hash
- selected candidates
- decision distribution
- evidence refs
- runtime status
