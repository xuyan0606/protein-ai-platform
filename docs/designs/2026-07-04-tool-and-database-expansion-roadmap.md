# 酶蛋白AI平台 2.0 — 工具与数据库扩展路线图

> 产品 + 技术联合视角，2026-07-04
>
> 历史路线图：本文的工具数量和实施状态均为 2026-07-04 的设计快照，不是当前线上能力清单。当前验收仅以交付包 v2、`tool_baseline_manifest` 和线上 `/api/tools` 实测为准（catalog 55 条、线上 33 个、缺失 22 个）。

## 当前实施状态

截至 `2026-07-04`，以下能力已完成第一阶段落地并接入平台：

- 已落地后端工具：
  - `interpro_annotation`
  - `catalytic_site_lookup`
  - `signal_peptide_predict`
- 已落地数据库表：
  - `interpro_entries`
  - `enzyme_interpro_links`
  - `catalytic_sites`
  - `catalytic_residues`
  - `signal_peptide_predictions`
- 已完成前端展示：
  - `InterProAnnotationCard`
  - `CatalyticSiteCard`
  - `SignalPeptideCard`
  - `MutationScoreCard` 已接入催化位点保护护栏展示
- 已完成策略增强：
  - `mutation_priority_score` 已接入催化位点保护规则
  - 保护位点会强制降级为 `Tier 3`
  - 保护位点不再生成推荐突变
- 已完成平台稳态增强：
  - `/auth/oidc` 已作为 Wiki/OIDC 浏览器入口，统一引导 Outline 授权链
  - 后端鉴权支持从 `pa_token` cookie 恢复浏览器会话
  - `/api/tools/{name}/submit` 与 `/api/tools/tasks/{task_id}` 已提供异步工具提交和轮询 MVP
  - 异步工具任务归属已从进程内存映射迁移到 Redis-backed metadata，API 重启后仍可校验任务 owner
  - 已提供 `POST /api/tools/tasks/{task_id}/cancel`，仅任务 owner 可请求取消异步任务，轮询状态会返回取消请求 metadata
  - `gromacs_md` 已路由到专用 `md_cpu` Celery queue，并由独立 `md-worker` 以默认并发 1 消费
  - `/pdb` 页面已接入 `gromacs_md` 异步提交、状态轮询、任务取消和结果展示
- 已完成真实 MD 基线：
  - `gromacs_md` 已从随机/占位结果切换为真实 GROMACS 管线
  - 缺少 GROMACS 或有效 PDB 时明确失败，不再伪造 MD 指标
  - Docker backend runtime 已安装 GROMACS，并验证真实前处理链可执行
  - 已返回按用途分组的 `artifact_manifest`，前端可展示结构、拓扑、轨迹、分析、参数和日志工件

当前仍处于 Phase 1。
下一步重点不是继续堆工具数量，而是补齐高质量本地数据灌库，让前端卡片从启发式提示升级为真实注释结果。

同时，真实 MD 当前应视为“可执行基础设施已打通，但仍需长任务治理”的状态。后续重点包括轨迹工件归档、队列资源限制、长轨迹参数模板和可复现实验记录，而不是回退到假数据或同步阻塞执行。

## 一、目标

在现有平台基础上，补齐更适合酶工程研发场景的外部数据库与分析工具，使平台从“能做基础分析”升级为“能做功能注释、位点保护、结构比对、表达可行性筛选、通路语义解释”的一体化工作台。

核心原则：

1. 优先补齐当前链路缺口，不重复建设已有能力。
2. 优先选择可直接提升突变建议质量和报告可信度的数据源。
3. 新增能力要能接入现有 `ToolRegistry + PostgreSQL + Redis + MinIO + ChromaDB + Wiki` 架构。

---

## 二、现状盘点

### 2.1 已有数据底座

当前项目已经覆盖并具备一定接入能力的数据源：

- UniProt
- Pfam
- PDB
- AlphaFold
- BRENDA
- ProThermDB
- PubChem
- Rhea
- EnzEngDB

### 2.2 已有工具能力

历史快照中已注册 33 个工具，覆盖：

- `analysis`
- `search`
- `structure`
- `engineering`
- `prediction`
- `docking`
- `design`
- `simulation`
- `data`

### 2.3 主要缺口

从酶蛋白研发实际流程看，当前仍缺以下关键层：

1. 家族/功能注释整合层
2. 催化位点与机理保护层
3. 结构相似性搜索层
4. 分泌/跨膜蛋白筛选层
5. 通路/生物过程解释层
6. 酶专属知识库深挖层

---

## 三、推荐新增数据源与工具

按“与项目匹配度 + 实施价值 + 对现有结果提升幅度”排序。

### P0：应优先落地

#### 1. InterPro / InterProScan

**定位**：
Pfam 的上位整合层，补 family / domain / repeat / site / GO 映射。

**为什么适合当前项目**：

- 现有 `Pfam` 只有结构域信息，不足以支撑统一功能解释。
- `/pdb` 页面、报告页、工程改造建议都需要更强的注释归因。
- 可直接增强 `enzyme_function`、`protein_benchmark`、`data_lookup` 输出。

**建议新增工具**：

- `interpro_annotation`
- `interpro_domain_architecture`
- `interpro_go_mapping`

**建议新增表**：

- `interpro_entries`
- `enzyme_interpro_links`

**建议新增 API**：

- `GET /api/data/interpro/{uniprot_id}`
- `POST /api/tools/interpro_annotation/call`

**前端新增卡片**：

- `InterProDomainCard`
- `FunctionAnnotationCard`

---

#### 2. M-CSA（Mechanism and Catalytic Site Atlas）

**定位**：
催化位点、反应机理、关键残基保护层。

**为什么适合当前项目**：

- 你当前最核心的场景是酶工程改造。
- 现在报告里会给突变位点，但缺一层“绝对不能动”的高可信保护约束。
- 对 `mutation_priority_score`、`mutation_scan`、`工程改造建议` 价值极高。

**建议新增工具**：

- `catalytic_site_lookup`
- `active_site_guardrail`
- `mechanism_summary`

**建议新增表**：

- `catalytic_sites`
- `catalytic_residues`
- `reaction_mechanisms`

**建议新增 API**：

- `GET /api/data/catalytic-sites/{uniprot_id}`
- `POST /api/tools/active_site_guardrail/call`

**前端新增卡片**：

- `CatalyticSiteCard`
- `MutationRiskGuardCard`

---

#### 3. SIFTS

**定位**：
UniProt ↔ PDB 残基级映射层。

**为什么适合当前项目**：

- 当前平台里结构、序列、突变建议、PDB 可视化已经并存。
- 但残基编号跨 UniProt / PDB / 链号转换仍可能错位。
- 对 `/pdb` 页面、活性位点映射、结构标注、下载结构文件都很关键。

**建议新增工具**：

- `residue_mapping_sifts`
- `structure_annotation_map`

**建议新增表**：

- `structure_residue_mappings`

**建议新增 API**：

- `GET /api/pdb/{structure_id}/mapping`

**前端新增能力**：

- 结构视图残基 hover 显示 UniProt 位点
- 报告中的突变位点可跳转到 3D 结构高亮

**当前已落地状态**：

- `residue_mapping_sifts` 已支持本地 JSON / CSV / TSV mapping 文件源。
- `SIFTS_MAPPING_PATH` 命中时，`/api/pdb/mapping` 与 `/api/pdb/mapping-by-name` 会优先返回真实映射记录。
- 只有缺少映射文件时，工具才回落到 `uniprot_start + coordinate_order` 推断。
- `local_annotations` 也已支持结构化 `base/interpro/mcsa/signalp` 的 JSON / CSV / TSV 导入，便于直接接真实导出文件而不必先手工转成单一 demo JSON。
- `backend/scripts/smoke_structure_data.py` 已提供 env-driven smoke：
  未配置真实数据源时输出 `SKIP`，配置 Foldseek/SIFTS env 后执行 live 验证。
  同时支持 `SIFTS_SMOKE_USE_DEMO=1` 与 `FOLDSEEK_SMOKE_USE_DEMO=1`，分别验证 bundled SIFTS 文件源与 Foldseek `summary_only` 降级路径。

---

### P1：强烈建议第二批落地

#### 4. Foldseek

**定位**：
结构相似性搜索。

**为什么适合当前项目**：

- 现有 `sequence_search` 和 `blast_search` 只能做序列层检索。
- 蛋白工程里经常出现“序列不像，但折叠像”的情形。
- 非常适合和 `PDB / AlphaFold / ESMFold` 结果联动。

**建议新增工具**：

- `structure_search_foldseek`
- `template_structure_suggest`

**当前已落地状态**：

- 已有 `structure_search_foldseek` 工具、PDB 专用 API 与前端结果卡片。
- 当前运行支持两种真实接线方式：
  - `FOLDSEEK_API_URL` 指向远端 HTTP service
  - `FOLDSEEK_BINARY` + 本地 DB path 走 CLI wrapper
- 两者都未配置时，工具会明确返回 degraded local structure summary，而不是伪造命中结果。

**建议新增表**：

- 可不落库，优先做在线查询 + Redis 缓存

**建议新增 API**：

- `POST /api/tools/structure_search_foldseek/call`

**前端新增卡片**：

- `StructureSearchResultCard`

---

#### 5. SignalP 6.0

**定位**：
信号肽预测。

**为什么适合当前项目**：

- 工业酶、胞外酶、分泌表达构建非常常见。
- 当前平台缺“这个序列是不是分泌蛋白”的快速判断。
- 对表达设计、载体构建、截短策略有直接价值。

**建议新增工具**：

- `signal_peptide_predict`

**建议新增表**：

- `signal_peptide_predictions`

**建议新增前端卡片**：

- `SignalPeptideCard`

---

#### 6. DeepTMHMM

**定位**：
跨膜拓扑预测。

**为什么适合当前项目**：

- 可先把不适合当前酶工程流程的膜蛋白筛出去。
- 避免把跨膜蛋白误送入普通可溶酶优化链。
- 对 `/chat/agent` 路由也有帮助，可自动切换分析策略。

**建议新增工具**：

- `topology_predict`
- `membrane_filter`

**建议新增表**：

- `topology_predictions`

**建议新增前端卡片**：

- `TopologyCard`

---

### P2：建议作为知识增强层

#### 7. Gene Ontology

**定位**：
功能语义层。

**建议新增工具**：

- `go_annotation_summary`
- `go_enrichment`

**价值**：

- 增强报告摘要
- 强化知识库检索标签
- 让项目 Wiki 页面更适合沉淀长期知识

---

#### 8. KEGG / Reactome

**定位**：
通路层解释。

**建议新增工具**：

- `pathway_lookup`
- `reaction_context`

**价值**：

- 从“这个酶是什么”升级为“这个酶在通路里干什么”
- 更适合项目级研究而不仅是单条序列分析

---

#### 9. CAZy

**定位**：
糖活性酶专属家族库。

**适用条件**：

- 如果你们平台后续重点做糖苷水解酶、纤维素酶、木聚糖酶、淀粉酶，这一项优先级可直接提升到 P0。

**建议新增工具**：

- `cazy_family_lookup`
- `substrate_specificity_hint`

---

## 四、与现有模块的映射关系

| 新能力 | 主要增强模块 | 当前问题 | 增强后效果 |
|------|------|------|------|
| InterPro | `enzyme_function` / `protein_benchmark` / `/pdb` | 注释层偏弱 | 家族、结构域、GO 解释更完整 |
| M-CSA | `mutation_priority_score` / `mutation_scan` | 活性位点保护不够强 | 降低错误突变建议 |
| SIFTS | `/pdb` / `PDBAnalysisCard` / 下载结构 | 残基编号可能错位 | 序列-结构位点统一 |
| Foldseek | `sequence_search` 的结构补充 | 只有序列相似性 | 可做折叠级模板发现 |
| SignalP | 项目分析 / 表达构建建议 | 无分泌判断 | 更贴近工业酶表达场景 |
| DeepTMHMM | 路由 / 序列预筛选 | 误把膜蛋白当可溶酶分析 | 分析链更稳 |
| GO | 报告与知识库 | 语义标签薄弱 | 结果更易索引/检索 |
| KEGG/Reactome | 项目研究 / 文献综述 | 通路上下文缺失 | 报告更像科研分析 |
| CAZy | 酶家族细分 | 某些酶类粒度不够 | 糖酶分析更专业 |

---

## 五、建议新增数据模型

优先做最小增量，不破坏现有表。

### 5.1 注释类

```sql
CREATE TABLE interpro_entries (
    id              INTEGER PRIMARY KEY,
    interpro_id     VARCHAR(32) UNIQUE NOT NULL,
    entry_type      VARCHAR(32),
    name            TEXT,
    description     TEXT,
    source_db       VARCHAR(32),
    go_terms        JSON,
    metadata_json   JSON
);

CREATE TABLE enzyme_interpro_links (
    id              INTEGER PRIMARY KEY,
    enzyme_id       INTEGER NOT NULL REFERENCES enzyme_records(id) ON DELETE CASCADE,
    interpro_id     INTEGER NOT NULL REFERENCES interpro_entries(id) ON DELETE CASCADE,
    start_pos       INTEGER,
    end_pos         INTEGER,
    score           FLOAT,
    evidence        VARCHAR(32)
);
```

### 5.2 催化位点类

```sql
CREATE TABLE catalytic_sites (
    id              INTEGER PRIMARY KEY,
    enzyme_id       INTEGER NOT NULL REFERENCES enzyme_records(id) ON DELETE CASCADE,
    source          VARCHAR(32) NOT NULL,
    mechanism_name  TEXT,
    reaction_text   TEXT,
    evidence_json   JSON
);

CREATE TABLE catalytic_residues (
    id              INTEGER PRIMARY KEY,
    site_id         INTEGER NOT NULL REFERENCES catalytic_sites(id) ON DELETE CASCADE,
    residue_pos     INTEGER NOT NULL,
    residue_aa      VARCHAR(2),
    role            VARCHAR(64),
    confidence      FLOAT,
    pdb_chain       VARCHAR(8),
    pdb_residue_no  VARCHAR(16)
);
```

### 5.3 预测类

```sql
CREATE TABLE signal_peptide_predictions (
    id              INTEGER PRIMARY KEY,
    enzyme_id       INTEGER REFERENCES enzyme_records(id) ON DELETE CASCADE,
    sequence_hash   VARCHAR(64) NOT NULL,
    has_signal      BOOLEAN,
    cleavage_site   VARCHAR(32),
    model_name      VARCHAR(64),
    raw_json        JSON
);

CREATE TABLE topology_predictions (
    id              INTEGER PRIMARY KEY,
    enzyme_id       INTEGER REFERENCES enzyme_records(id) ON DELETE CASCADE,
    sequence_hash   VARCHAR(64) NOT NULL,
    topology_type   VARCHAR(32),
    tm_count        INTEGER,
    regions_json    JSON,
    model_name      VARCHAR(64),
    raw_json        JSON
);
```

---

## 六、建议新增 API

### 6.1 数据 API

- `GET /api/data/interpro/{uniprot_id}`
- `GET /api/data/catalytic-sites/{uniprot_id}`
- `GET /api/data/pathways/{uniprot_id}`
- `GET /api/pdb/{structure_id}/mapping`

### 6.2 工具 API

- `POST /api/tools/interpro_annotation/call`
- `POST /api/tools/catalytic_site_lookup/call`
- `POST /api/tools/residue_mapping_sifts/call`
- `POST /api/tools/structure_search_foldseek/call`
- `POST /api/tools/signal_peptide_predict/call`
- `POST /api/tools/topology_predict/call`
- `POST /api/tools/pathway_lookup/call`
- `POST /api/tools/cazy_family_lookup/call`

---

## 七、前端建议新增卡片

面向 `http://localhost:4200/chat/agent` 和 `/pdb`：

- `InterProDomainCard`
- `CatalyticSiteCard`
- `StructureMappingCard`
- `StructureSearchResultCard`
- `SignalPeptideCard`
- `TopologyCard`
- `PathwayContextCard`
- `CAZyFamilyCard`

显示原则：

1. 卡片优先摘要，不直接堆原始 JSON。
2. 关键风险位点用显著样式展示。
3. 可与现有 Markdown 报告统一排版。
4. 可发布到 Wiki 时保留结构化小节。

---

## 八、实施顺序

### Phase 1：最快出价值

1. InterPro
2. M-CSA
3. SIFTS

**原因**：

- 直接提升当前酶分析报告质量
- 直接减少错误突变建议
- 与当前 `/pdb` 页面改造最匹配

### Phase 2：提升搜索和筛选能力

1. Foldseek
2. SignalP
3. DeepTMHMM

**原因**：

- 显著提升结构探索能力
- 避免错误样本进入错误分析链
- 对工业酶研发场景很实用

### Phase 3：知识图谱与项目沉淀增强

1. GO
2. KEGG / Reactome
3. CAZy

**原因**：

- 更适合项目研究、报告发布、Wiki 沉淀
- 适合做长期知识库和语义检索增强

---

## 九、最小可执行版本（建议直接开工）

先做 3 个工具，性价比最高：

1. `interpro_annotation`
2. `catalytic_site_lookup`
3. `signal_peptide_predict`

理由：

- 一个补功能注释
- 一个补催化保护
- 一个补表达场景

这 3 个完成后，平台的“科研可信度”和“工程可操作性”会明显上一个台阶。

---

## 十、下一步开发任务拆分

### 任务包 A：InterPro

- 新增 ingestor / service
- 新增 `interpro_entries` / `enzyme_interpro_links`
- 新增 `interpro_annotation` 工具
- 前端新增 `InterProDomainCard`

### 任务包 B：M-CSA

- 新增催化位点数据模型
- 新增 `catalytic_site_lookup` 和 `active_site_guardrail`
- 将 guardrail 接入 `mutation_priority_score`
- 前端新增 `CatalyticSiteCard`

### 任务包 C：SignalP + DeepTMHMM

- 新增在线查询或缓存代理
- 新增预测结果表
- 路由层增加“膜蛋白/分泌蛋白”预警
- 前端新增 `SignalPeptideCard` / `TopologyCard`

---

## 十一、结论

从当前项目形态看，最匹配的扩展方向不是盲目继续堆模型，而是：

1. 用 `InterPro` 补注释层
2. 用 `M-CSA` 补催化保护层
3. 用 `SIFTS` 补残基映射层
4. 用 `Foldseek` 补结构搜索层
5. 用 `SignalP / DeepTMHMM` 补表达与拓扑筛选层

这条路线和现有数据库、工具注册机制、Wiki 沉淀链路都高度兼容，属于可以持续迭代、不会推翻当前架构的增强方案。
