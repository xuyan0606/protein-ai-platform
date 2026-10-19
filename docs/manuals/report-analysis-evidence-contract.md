# Report Analysis Evidence Contract

报告中的证据对象使用固定的五类 `evidence_type`：`experimental_fact`、
`database_evidence`、`computed_result`、`inference` 和 `hypothesis`。

每条证据必须带 `status`。`completed`、`completed_no_hit` 和
`completed_with_hits` 才能标记为完成；`waiting`、`submitted`、`failed`、
`not_run` 和 `not_available` 始终以未完成、失败、未运行或不可用显示，不能
渲染成已完成。`inference` 与 `hypothesis` 必须列出至少一个
`derived_from` 上游证据 ID。

报告 manifest 保存报告 schema 版本、输入文件 SHA-256、公开的工具/模型/数据库
标识、运行时和生成时间。`token`、`Authorization`、`Cookie`、API key、secret
和 password 等字段会被丢弃，不写入 manifest。manifest 使用排序后的紧凑 JSON
计算 SHA-256，因此同一内容重复生成时哈希稳定。

## 示例

```json
{
  "evidence_type": "hypothesis",
  "status": "completed",
  "derived_from": ["structure-001"],
  "render_status": "已完成"
}
```

假设和推断只能作为待验证的工作假说；没有实验事实时，不得写成
`experimentally_validated`、提高活性或提高稳定性等已验证结论。实验建议应列出
读出、对照、重复和升级条件，直到新的实验事实进入报告。
