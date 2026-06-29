# 酶蛋白AI平台 — 项目Wiki化 + 知识库产品设计

> 产品经理视角，2026-06-29

## 一、用户故事

**核心场景**：科研人员创建一个「脂肪酶pH改造」项目 → 在项目中与AI对话分析 → 所有分析结果自动沉淀到项目的Wiki页面和知识库文件中。

```
用户旅程:
  创建项目 → 添加序列 → AI对话分析 → 报告自动发布到Wiki → .md文件存入知识库
     ↓              ↓           ↓              ↓                    ↓
  Project      Sequence    Agent输出     Outline页面         MinIO(.md)
  (PostgreSQL) (PostgreSQL) (Agent引擎)  (自动创建/更新)     (自动上传)
```

**用户价值**：
- 每次分析不丢失，自动成为项目知识资产
- 团队成员可以浏览项目Wiki回顾历史分析
- .md文件可以下载、分享、版本管理
- 项目 = 一站式工作台（序列 + 对话 + 报告 + 文件）

## 二、现状 vs 目标

| 维度 | 现状 | 目标 |
|------|------|------|
| 项目 | 有序列管理和批量分析，但与对话/Agent无关 | 项目是工作容器，对话+分析+Wiki+文件全在项目内 |
| 对话 | 独立于项目，只有 user_id 关联 | 对话属于项目，`conversation.project_id` |
| Agent输出 | 流式输出到聊天窗口，结束后只存Message表 | 输出自动发布为Wiki页面 + .md文件到知识库 |
| Wiki | Outline已集成(iframe+API)，仅用于酶数据库浏览 | 每个项目自动创建Wiki Collection，报告自动成为Document |
| 文件 | MinIO已有上传/下载，无文件元数据表 | 新增 `project_files` 表，.md报告自动入库 |
| 批量分析 | 同步阻塞，结果JSON dump | 异步SSE进度 + 每个序列结果独立Wiki页面 |

## 三、信息架构

```
项目 (Project)
├── 概览 Dashboard
│   ├── 项目描述 + 序列列表
│   ├── Wiki页面数 + 文件数统计
│   └── 最近活动 timeline
│
├── 对话分析 (Chat)
│   ├── 与AI对话（在项目上下文中）
│   ├── Agent分析过程可视化
│   └── 完成后 → 自动触发 Wiki发布 + 文件存储
│
├── Wiki知识库 (Wiki)
│   ├── Outline Collection（项目专属）
│   ├── 页面树形结构：
│   │   ├── 📄 项目概述（自动创建）
│   │   ├── 📁 分析报告/
│   │   │   ├── 📄 2026-06-29 脂肪酶pH改造分析 (Agent报告)
│   │   │   ├── 📄 2026-06-29 突变优先级评分结果
│   │   │   └── 📄 2026-06-29 结构预测与可视化
│   │   ├── 📁 序列分析/
│   │   │   ├── 📄 LipA-WT 理化性质分析
│   │   │   └── 📄 LipA-Mutant-1 对比分析
│   │   └── 📁 批量结果/
│   │       └── 📄 Batch-001 三序列 benchmark 汇总
│   └── 每个页面可编辑、评论、分享
│
└── 文件知识库 (Files)
    ├── .md 报告文件（与Wiki页面对应）
    ├── .pdb 结构文件（工具产出）
    ├── .csv 数据表格（批量结果）
    ├── .fasta 序列文件
    └── 下载/导出全部
```

## 四、数据模型改动

### 4.1 新增/修改表

```sql
-- 修改 conversations 表：关联到项目
ALTER TABLE conversations ADD COLUMN project_id VARCHAR(16) REFERENCES projects(id);

-- 新增：项目文件元数据表
CREATE TABLE project_files (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id    VARCHAR(16) NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    filename      VARCHAR(500) NOT NULL,         -- 显示名称: "2026-06-29_pH分析报告.md"
    object_name   VARCHAR(500) NOT NULL,         -- MinIO路径: "projects/abc123/reports/uuid.md"
    file_type     VARCHAR(20) NOT NULL,           -- md / pdb / csv / fasta / json
    file_size     INTEGER DEFAULT 0,             -- 字节数
    content_hash  VARCHAR(64),                   -- SHA-256 去重
    source        VARCHAR(30) DEFAULT 'agent',   -- agent / upload / batch / manual
    conversation_id INTEGER REFERENCES conversations(id),  -- 产出的对话
    outline_doc_id  VARCHAR(100),                -- Outline文档ID（已发布到Wiki）
    tags          TEXT,                          -- JSON数组: ["pH", "mutation", "report"]
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 修改 projects 表：Wiki关联
ALTER TABLE projects ADD COLUMN outline_collection_id VARCHAR(100);  -- Outline集合ID
ALTER TABLE projects ADD COLUMN outline_root_doc_id VARCHAR(100);    -- 根页面ID
ALTER TABLE projects ADD COLUMN wiki_auto_publish BOOLEAN DEFAULT true;  -- 自动发布开关
```

### 4.2 实体关系

```
User (1) ──< (N) Project
Project (1) ──< (N) Conversation      ← 新增关联
Project (1) ──< (N) ProjectFile       ← 新增表
Project (1) ──< (N) ProjectSequence
Project (1) ──< (N) BatchJob
Project (1) ──> (1) Outline Collection ← 新增关联
Conversation (1) ──< (N) Message
Conversation (1) ──< (N) ProjectFile  ← 文件可关联到对话
```

## 五、核心流程设计

### 5.1 项目创建 → 自动建Wiki

```
用户点击「创建项目」
  │
  ├─→ 后端创建 Project 记录 (PostgreSQL)
  │
  ├─→ 调用 OutlineClient.create_collection(project.name)
  │     └─→ 创建项目专属 Collection
  │
  ├─→ 调用 OutlineClient.create_document("项目概述", 模板内容)
  │     └─→ 创建根页面（包含项目描述、序列列表、后续报告目录）
  │
  └─→ 更新 Project.outline_collection_id + outline_root_doc_id
```

**项目概述模板**：
```markdown
# {项目名称}

> 创建时间：{created_at} | 序列数：{seq_count}

## 项目描述
{description}

## 蛋白序列
| 名称 | 长度 | 添加时间 |
|------|------|---------|
| {seq.name} | {len(seq.sequence)} aa | {seq.created_at} |

## 分析报告
_(AI分析完成后自动更新)_

## 批量结果
_(批量任务完成后自动更新)_
```

### 5.2 Agent对话完成 → 自动发布Wiki + 存文件

```
Agent stream_chat 完成（Stage 5: SYNTHESIZE 产出 final_report）
  │
  ├─→ 1. 生成 .md 文件内容
  │     ├── 标题元数据（YAML front matter）
  │     ├── Agent研究报告（research_notes）
  │     ├── 工具执行结果摘要（tool_results）
  │     ├── 最终分析报告（final_report）
  │     └── 参考引用（literature citations）
  │
  ├─→ 2. 上传到 MinIO 知识库
  │     ├── object_name: "projects/{project_id}/reports/{date}_{title}.md"
  │     ├── 创建 ProjectFile 记录
  │     └── content_type: "text/markdown"
  │
  ├─→ 3. 发布到 Outline Wiki
  │     ├── 在 Collection 下创建子文档（或更新已有文档）
  │     ├── parent_id: outline_root_doc_id（挂在项目根页面下）
  │     ├── title: "{date} {auto_title}"
  │     └── content: Markdown 格式报告
  │
  └─→ 4. 更新项目根页面（追加报告链接到目录）
```

**.md 文件格式**：
```markdown
---
project: "脂肪酶pH改造"
conversation_id: 42
agent_pipeline: [predict_properties, protein_benchmark, mutation_priority_score]
success_rate: 100%
created_at: 2026-06-29T14:30:00
tags: [pH, lipase, mutation_design]
---

# 脂肪酶LipA pH改造分析报告

> 由酶蛋白AI平台 Agent引擎自动生成 | 2026-06-29

## 研究背景 (PI Research)
{research_notes}

## 分析管线
1. ✅ predict_properties — 理化性质基线 (0.3s)
2. ✅ protein_benchmark — 酶家族深度分析 (1.2s)
3. ✅ mutation_priority_score — 多维度突变评分 (0.8s)

## 核心发现
{final_report — SC synthesis}

## 参考文献
- [PMID:12345] Smith et al. (2024). Lipase engineering...
- [PMID:67890] Doe et al. (2025). pH optimization...

## 附录：原始数据
{tool_results JSON summary}
```

### 5.3 批量分析完成 → 汇总Wiki页面

```
BatchJob 完成
  │
  ├─→ 为每个序列生成独立 .md 报告
  │     └─→ "projects/{id}/batch/{job_id}/{seq_name}.md"
  │
  ├─→ 生成汇总页面
  │     └─→ "projects/{id}/batch/{job_id}/summary.md"
  │     └─→ 包含对比表格、排名、最优候选
  │
  ├─→ 批量发布到 Outline（子目录 "批量结果/Batch-{N}/"）
  │
  └─→ 更新项目根页面的批量结果目录
```

## 六、前端改动

### 6.1 项目详情页重构

```
ProjectDetailPage 新布局：4个 Tab

┌─────────────────────────────────────────────────────┐
│  [概览]  [对话分析]  [Wiki知识库]  [文件]            │
├─────────────────────────────────────────────────────┤
│                                                     │
│  概览 Tab:                                          │
│  ├── 项目描述 + 编辑                                 │
│  ├── 序列列表 (现有)                                 │
│  ├── 最近Wiki更新 (最近5个页面)                      │
│  └── 文件统计 (X个文件, Y MB)                        │
│                                                     │
│  对话分析 Tab:                                       │
│  ├── 嵌入式聊天窗口（绑定project_id）                 │
│  └── 历史对话列表（本项目的对话）                     │
│                                                     │
│  Wiki知识库 Tab:                                     │
│  ├── 左侧：页面树 (Outline document tree)            │
│  ├── 右侧：Markdown 渲染预览                         │
│  ├── 工具栏：新建页面 / 刷新 / 打开Outline全屏        │
│  └── 点击页面 → 渲染Markdown + 下载.md按钮           │
│                                                     │
│  文件 Tab:                                           │
│  ├── 文件列表 (表格: 名称/类型/大小/来源/时间)        │
│  ├── 筛选: 类型(md/pdb/csv) / 来源(agent/upload)    │
│  ├── 批量下载 (ZIP)                                  │
│  └── 上传文件 (现有FileUploader)                      │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### 6.2 对话绑定项目

- ChatLayout 增加 `project_id` query param
- 从项目详情页跳转的对话自动带上 `?project_id=xxx`
- 对话创建时写入 `conversation.project_id`
- 对话列表中可按项目筛选

## 七、后端 API 改动

### 7.1 新增 API

```
# Wiki
GET    /api/projects/{id}/wiki/tree         → 页面树 (Outline proxy)
GET    /api/projects/{id}/wiki/pages/{doc}  → 单页内容 (Markdown)
POST   /api/projects/{id}/wiki/pages        → 手动创建页面
PUT    /api/projects/{id}/wiki/pages/{doc}  → 更新页面
DELETE /api/projects/{id}/wiki/pages/{doc}  → 删除页面

# 文件知识库
GET    /api/projects/{id}/files             → 文件列表（含筛选）
GET    /api/projects/{id}/files/{file_id}   → 文件元数据
GET    /api/projects/{id}/files/{file_id}/download → 下载
DELETE /api/projects/{id}/files/{file_id}   → 删除
POST   /api/projects/{id}/files/batch-download → 打包ZIP下载

# 对话绑定
PATCH  /api/conversations/{id}              → 更新 conversation.project_id
GET    /api/projects/{id}/conversations     → 项目下的对话列表
```

### 7.2 修改 API

```
# 项目创建 → 自动建Wiki Collection
POST /api/projects → 增加 Outline collection 创建

# Agent完成 → 自动发布
POST /api/chat/stream → 在 done 事件后触发:
  1. generate_markdown_report()
  2. upload_to_storage(.md)
  3. publish_to_outline()
  4. 返回 file_id + wiki_url 给前端
```

## 八、Agent引擎改动

### 8.1 新增 publish 阶段

```
当前: ROUTE → RESEARCH → PLAN → EXECUTE → REVIEW → SYNTHESIZE → done
新增: ROUTE → RESEARCH → PLAN → EXECUTE → REVIEW → SYNTHESIZE → PUBLISH → done

PUBLISH 阶段:
  1. 将 final_report + research_notes + tool_results 组装为 .md
  2. 上传到 MinIO: "projects/{project_id}/reports/{filename}.md"
  3. 发布到 Outline: create_document(title, md_content, collection_id)
  4. 创建 ProjectFile 记录
  5. 发送 SSE 事件: {type: "published", file_id, wiki_url, filename}
```

### 8.2 Markdown报告生成器

新增 `app/services/report_generator.py`：

```python
class ReportGenerator:
    def generate(
        self,
        task: str,
        research_notes: str,
        plan: list[dict],
        tool_results: list[dict],
        final_report: str,
        citations: list[Citation],
        project_name: str,
    ) -> str:
        """生成带YAML front matter的完整Markdown报告"""
        ...
```

## 九、实施路线

### Phase A（1周）：数据模型 + 项目创建Wiki化
- [ ] `conversations.project_id` FK
- [ ] `project_files` 表 + migration
- [ ] `projects` 增加 outline_collection_id / wiki_auto_publish
- [ ] 项目创建时自动建 Outline Collection + 根页面
- [ ] 单元测试

### Phase B（1周）：Agent输出自动发布
- [ ] `report_generator.py` — Markdown报告生成
- [ ] Agent PUBLISH 阶段 — MinIO上传 + Outline发布
- [ ] SSE `published` 事件 — 前端收到后显示"已发布到Wiki"提示
- [ ] `ProjectFile` 记录创建
- [ ] 无项目时降级：仅存文件，不发Wiki

### Phase C（1周）：前端项目详情页重构
- [ ] 4 Tab 布局（概览/对话/Wiki/文件）
- [ ] Wiki Tab — 页面树 + Markdown渲染
- [ ] 文件 Tab — 列表 + 筛选 + 下载
- [ ] 对话 Tab — 嵌入聊天 + 历史列表
- [ ] 对话绑定 project_id

### Phase D（1周）：批量分析Wiki化 + 联调
- [ ] 批量结果 → 每序列.md + 汇总.md
- [ ] 批量结果 → Outline子目录
- [ ] 项目根页面自动更新目录
- [ ] 端到端联调测试
- [ ] CI/CD 更新

## 十、技术风险与应对

| 风险 | 影响 | 应对 |
|------|------|------|
| Outline 不可用 | Wiki发布失败 | 降级：仅存MinIO文件 + 重试队列 |
| 并发发布冲突 | 根页面目录更新竞态 | 乐观锁：版本号检查 + 重试 |
| 大文件上传慢 | 阻塞Agent响应 | PUBLISH异步执行，不阻塞SSE done |
| Outline Collection 数量上限 | 项目太多 | 限制50个项目/用户 + 归档机制 |
| .md 内容太大 | Outline API 超时 | 截断到100KB + 附录链接到文件 |

## 十一、验收标准

1. ✅ 创建项目后，Outline中出现同名Collection + 根页面
2. ✅ Agent对话完成后，Wiki中自动出现分析报告页面
3. ✅ 报告.md文件可在文件Tab中查看、下载
4. ✅ 批量分析完成后，每个序列有独立报告 + 汇总页面
5. ✅ 项目详情页4个Tab正常工作
6. ✅ 对话可关联到项目，项目下可查看所有相关对话
7. ✅ Outline不可用时，文件仍然存储到MinIO，不丢失
8. ✅ 端到端测试覆盖核心流程
