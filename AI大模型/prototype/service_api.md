# KWB-EnzymeDesigner 本地服务接口草案

建议先把模型封装为本地 HTTP 服务，平台后端后续可通过 `ToolRegistry` 调用。

## 健康检查

```http
GET /health
```

响应：

```json
{
  "status": "ok",
  "model": "KWB-EnzymeDesigner",
  "version": "0.1.0-local"
}
```

## 推理接口

```http
POST /v1/enzyme-design
Content-Type: application/json
```

请求体参考：

```json
{
  "enzyme_name": "lipase",
  "sequence": "M...",
  "structure_object": "uploads/user_1/example.pdb",
  "substrate": "p-nitrophenyl palmitate",
  "objective": "improve thermostability while preserving activity",
  "assay_condition": {
    "ph": 7.5,
    "temperature_c": 55,
    "expression_system": "Pichia pastoris"
  },
  "known_mutations": ["A128P"],
  "protected_sites": [
    {
      "position": 152,
      "reason": "catalytic residue",
      "source": "KWB-EnzymeDB"
    }
  ]
}
```

响应体必须符合 `contracts/kwb_enzyme_designer.schema.json` 的 `result` 部分。

## 平台接入方向

后续平台新增工具：

```text
backend/app/tools/kwb_enzyme_designer.py
```

工具名称：

```text
kwb_enzyme_designer
```

模型运行状态在前端显示为：

```text
KWB-EnzymeDesigner v0.1.0-local
Multi-objective enzyme optimization
```

