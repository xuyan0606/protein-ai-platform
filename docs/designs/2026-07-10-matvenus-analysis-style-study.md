# Matvenus 分析方法与输出样式学习记录

## 当前可确认内容

已读取 Matvenus 公开前端资源：

- `/chat/assets/index-6pT-r_0V.js`
- `/chat/assets/index-BY3Tx2Ah.css`
- `/chat/assets/message-list-CxaGCmlw.js`
- `/chat/assets/message-list-CbbCOFk9.css`
- `/chat/assets/markdown-vpF-Mdw0.js`
- `/chat/assets/markdown-DqhFadIZ.css`

已通过当前 Chrome 登录态读取真实会话：

- Session ID：`08b460b1-3d8c-4235-8a20-136f9f50eb4e`
- 标题：`SD改造+数据反馈`
- 状态：`completed`
- 工具：`read_file`、`venusx_functional_residue_prediction`、`venusrem_mutation_prediction`
- 复盘稿：`matvenus-session-08b460.review.md`
- 原始流事件：`matvenus-session-08b460.stream-events.json`

注意：会话中外部 agent 给出的突变收益、距离、成功率等属于模型/工具预测与解释，迁移到本平台时必须标注为“计算假设”，不能替代结构测量、动力学验证和湿实验结果。

## 消息数据结构

Matvenus 消息围绕 `completedMessages` 和 streaming message 渲染。关键字段：

- `sender`：区分 human / agent。
- `spans`：消息内容片段数组。
- `msg_id`：消息 ID。
- `model`：agent 回复模型标识。
- `node_name`：deep research 场景下的节点名。
- `agent_type`：agent 类型。

前端复制函数会提取以下 spans：

- `text`：直接拼接 `content`。
- `step`：拼接 `title`，再拼接内部 `text` spans。
- `report`：拼接 `content`。
- `tool_call`：用于判断工具调用和交互卡片，但复制文本不直接拼接参数。

真实 session API 还会返回 `stream_events`：

- `/session/{id}`：只返回会话元数据。
- `/session/{id}/stream-events`：返回会话元数据加 `stream_events`。
- `stream_events[].event`：如 `msg_user`、`msg_chunk`、`tool_call`。
- `stream_events[].data.content`：列表形式，元素类型包括 `text`、`reasoning`、`tool_call_chunk`、`file`。
- `stream_events[].data.tool_name/tool_args`：工具调用卡片数据。
- `stream_events[].data.msg_id`：可按消息聚合用户输入、assistant 分段输出和工具调用。

这说明它的输出不是单纯 Markdown 字符串，而是“结构化事件 + Markdown 渲染 + 工具卡片”的组合。可迁移策略是：本平台保留 Markdown 正文，同时在后续 agent graph 中增加 step/report/tool_call 的结构化事件，便于复盘和导出。

## 分析思路模式

从前端结构可确认其 agent 输出强调：

1. 先分步展示执行过程，而不是只给最终答案。
2. 工具调用和正文分离，工具结果以卡片或折叠摘要呈现。
3. 最终 report 独立承载结论，便于复制、导出 PDF/DOCX。
4. 对 deep research 类任务，用 `node_name` 区分 coordinator、planner、evaluator、outline_reporter、section_writer 等节点。
5. 用户侧可编辑、重试、从某条消息重新生成，说明输出应支持“局部修订”。

迁移到酶蛋白 AI 平台时，建议将复杂蛋白工程任务组织为：

1. 任务理解：目标、成功标准、禁改区。
2. 数据准备：序列编号、PDB/AlphaFold、活性口袋、SASA、保守性、柔性区、已知文献证据。
3. 位点筛选：按稳定化机制分桶，例如环区刚化、表面电性、核心极性修复、化学不稳定热点。
4. 风险过滤：催化残基、底物口袋、金属/辅因子位点、保守 Gly/Pro、结构域界面。
5. 实验执行：构建、表达、纯化、SEC/DLS、DSF/nanoDSF、活性验证。
6. Go / No-Go：用阈值表收口。
7. 下一轮组合策略：只组合有效、空间分离、机制互补且不伤活性的单点。

## 真实会话中的蛋白工程分析模式

该会话围绕一个 388 aa 酶的比活力和热稳定性提升展开，实际流程可以拆成四层：

1. **预检和输入校正**
   - 先读取 protein-design 工具说明。
   - 先尝试以 PDB 作为 VenusX 输入，发现工具需要 FASTA 后改为从 PDB 提取序列。
   - 对 VenusREM 稳定性/活性任务做 `preflight_only` 参数校验，再请求用户确认提交。

2. **全扫描建立候选池**
   - 用 VenusREM 分别跑结构驱动稳定性扫描和活性扫描。
   - 用 VenusX 标记功能残基/高保守区，用于识别禁改区。
   - 输出方式不是只给一个排名，而是拆成“双收益位点”“单热稳定性位点”“单比活力位点”。

3. **用户指定突变复核**
   - 对 T32A、S60T、E103Q、W124F、L174I、T191K、K212R、A215T、S272A、P338T 做定向复核。
   - 输出表格包含：热稳定性预测、比活力预测、提升概率、推荐等级、说明。
   - 只把 T191K 判为高优先级，其余多为中性或风险位点。

4. **实验反馈后的机制重构**
   - 用户反馈 P338T 实验表现为比活力提升 30% 以上、稳定性下降约 40%。
   - 外部 agent 没有固守原始“P338T 不推荐”的预测结论，而是把它重新归因为活力-稳定性权衡。
   - 解释逻辑：Pro->Thr 解除了局部构象锁，稳定性下降；但如果 P338 位于底物通道/门控 loop 附近，去刚性化可能降低底物进出和产物释放阻力，导致 kcat 或表观比活提升。
   - 后续策略从“替换 P338T”变为“保留 P338T 的活性收益，再用周边补偿突变恢复稳定性”。

## 可迁移到本平台的输出模板

复杂酶改造任务建议固定输出以下结构：

```markdown
## 核心结论
- 本轮目标：
- 最优先验证突变：
- 不建议突变：
- 需要实验复核的假设：

## 数据来源与置信度
| 数据 | 来源 | 用途 | 置信度 | 风险 |
|------|------|------|--------|------|

## 禁改区
| 区域/残基 | 原因 | 证据 |
|-----------|------|------|

## 候选突变
| 突变 | 设计类型 | 稳定性预期 | 活性预期 | 风险 | 优先级 |
|------|----------|------------|----------|------|--------|

## 机制解释
1. 结构机制：
2. 动力学/别构机制：
3. 化学稳定性机制：
4. 与实验反馈是否一致：

## 组合策略
| 组合 | 目的 | 空间关系 | 预期收益 | 风险 |
|------|------|----------|----------|------|

## 实验执行
| 变体 | 构建 | 表达 | 纯化 | Tm | 活性 | SEC | 结论 |
|------|------|------|------|----|------|-----|------|

## Go / No-Go
- Go：
- No-Go：
- 下一轮：
```

## 对 P338T 类反馈的专用分析框架

当实验反馈出现“活性升、稳定性降”时，本平台 agent 应按以下顺序处理：

1. **承认预测偏差**：把原预测、实验反馈和不一致点并排列出。
2. **重定义目标**：不是回退高活性突变，而是保留活性收益并补偿稳定性损失。
3. **机制分解**：
   - 原残基是否提供主链刚性、疏水 packing、盐桥或氢键。
   - 新残基是否增加局部柔性、改变门控 loop、底物通道或产物释放。
   - 活性提升更像 kcat、Km 还是表达/溶解性变化。
4. **空间筛选补偿位点**：
   - 避开过近位点，避免抹掉有利柔性。
   - 选择 6-10 A 周边、稳定性得分高、活性不负向的位点。
   - 优先机制互补：氢键锚定、疏水填洞、表面电荷缓和、二级结构端帽。
5. **梯度实验**：
   - 单点补偿：最低成本验证。
   - 双点补偿：稳定性回补不足时追加。
   - 多点补偿：只在前两层成立后推进。

## 样式迁移结论

真实会话的内容组织和前端样式是一致的：短段落、明确标题、表格承载候选位点、分隔线切分阶段、最终用“核心结论/优化建议/避坑提醒”收口。本平台 MarkdownView 已完成字体和表格样式迁移，后续应继续把工具调用和推理步骤结构化展示，而不是只渲染成一段长 Markdown。

## 已接入本平台的代码位置

- `backend/app/core/agent_roles.py`
  - 新增 `ENZYME_ENGINEERING_REPORT_PROTOCOL`。
  - `SC_SYSTEM_PROMPT` 已拼接该协议，报告合成阶段会优先按该协议组织酶工程输出。
- `backend/app/core/agent_graph.py`
  - `_synthesize_sc()` 的用户指令已要求酶活、热稳定性、突变筛选和实验反馈任务使用该协议。
  - `_chat_reply()` 的 SOP/清单/模板类文档回复已复用该协议，避免普通聊天生成过短或过泛的实验清单。
- `backend/tests/test_agent_binder.py`
  - 新增测试保护协议关键词：预测与 wet-lab feedback 冲突、activity-stability trade-off、Go/No-Go。
- `backend/tests/test_matvenus_session_extractor.py`
  - 新增 `stream_events` 解析回归测试。

## 输出格式样式

Matvenus Markdown 输出样式特点：

- 字体：系统 sans-serif，优先 `ui-sans-serif, system-ui`，中文环境使用系统中文字体。
- 正文颜色：接近 `rgb(31,35,41)`。
- 正文字号：主要 `14px` / `15px`。
- 正文行高：`leading-relaxed`。
- 标题：不使用 serif；`font-semibold`，`tracking-tight`，层级克制。
- 有序列表：缩进更大，marker 使用 primary 色。
- 引用：左边框 `#bbbfc4`，浅灰背景，右圆角，非斜体。
- 行内代码：primary 色，浅 primary 背景，圆角，小内边距。
- 代码块：浅灰背景、细边框、`rounded-xl`，字号约 `12px`。
- 表格：细边框、浅灰表头、`px-4 py-3`，不使用大写表头。
- agent 名称：`启明星`，`text-lg font-semibold`，颜色 `#4BA4F8`。
- agent 消息：左对齐、透明背景。
- human 消息：右对齐，并在桌面端留出约 30% 左侧缩进。
- 消息宽度：`max-w-2xl` 起，随断点到 `lg:max-w-3xl / xl:max-w-4xl / 2xl:max-w-5xl`。

## 本轮已迁移到本平台

`frontend/src/components/chat/MarkdownView.tsx` 已调整：

- streaming / rendered Markdown 均改为系统字体风格的 `rgb(31,35,41)`。
- 标题去掉 `font-serif` 和厚重分隔线，改为紧凑 `font-semibold`。
- 正文、列表、li 改为 Matvenus 风格的 relaxed 行高和更紧凑段落间距。
- blockquote 改为浅灰左边框样式。
- inline code 改为 primary 轻背景。
- code block 改为浅灰卡片、细边框。
- table 改为细边框、浅灰表头、紧凑圆角。

## 已完成真实 JSON 验证

- 已确认真实会话通过 `stream_events` 表达完整对话。
- 已确认该会话调用 protein design 相关工具，而不是 deep research 多节点 writer。
- 已确认最终输出包含候选突变表、用户指定突变复核表、P338T 机制解释、补偿突变表和梯度实验方案。
- 已将 `stream_events` 支持加入本地提取器，并新增回归测试。
