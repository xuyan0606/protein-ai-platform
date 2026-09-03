# Matvenus 会话复盘手册

用于把已登录浏览器中的 Matvenus agent 会话导出为本地 JSON，再离线提取为 Markdown 复盘稿。不要导出或粘贴 Cookie、token、密码。

## 1. 浏览器导出 JSON

在已登录的 Matvenus 会话页面打开 DevTools Console，执行：

```js
const id = "08b460b1-3d8c-4235-8a20-136f9f50eb4e";
const res = await fetch(`/session/${id}`, { credentials: "include" });
const data = await res.json();
copy(JSON.stringify(data, null, 2));
```

将复制结果保存到项目根目录，例如：

```text
matvenus-session-08b460.json
```

## 2. 本地生成复盘稿

```bash
python3 scripts/extract_matvenus_session.py \
  matvenus-session-08b460.json \
  -o matvenus-session-08b460.review.md
```

脚本会提取：

- human / agent 对话内容
- `text` / `report` spans
- `step` 标题与推理轨迹
- `tool_call` 名称与脱敏后的参数摘要

敏感字段名包含 `token`、`cookie`、`authorization`、`password`、`secret`、`api_key` 时会自动替换为 `[REDACTED]`。

## 3. 复盘重点

阅读生成的 Markdown 时优先看：

- `Reusable Analysis Trace`：agent 使用的分析步骤顺序
- `Tool Calls`：调用了哪些工具或数据源
- agent 最后的 report：最终结论和建议
- human prompt：用户是如何约束目标、输入和输出格式的

复盘内容可以沉淀为本平台的提示词、SOP 模板或工具编排策略，但外部会话 JSON 只作为参考材料，不直接写入生产数据库。
