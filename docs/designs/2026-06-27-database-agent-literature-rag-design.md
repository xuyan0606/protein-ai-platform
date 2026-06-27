# 酶蛋白AI平台 — 数据库Agent + 文献RAG 升级设计

## 全球前沿调研总结（20+论文/系统）

### 蛋白质工程AI Agent（2024-2026）

| 系统 | 来源 | 核心创新 | 可借鉴点 |
|------|------|---------|---------|
| **ProteinMCP** | [Protein Science 2026](https://onlinelibrary.wiley.com/doi/full/10.1002/pro.70547) / [GitHub](https://github.com/charlesxu90/ProteinMCP) | MCP工具注册 + Claude自主编排蛋白质工程管线 | MCP协议封装工具、Agent自主发现+调用、pskill安装 |
| **ProtAgents** | [Digital Discovery/MIT 2024](https://pubs.rsc.org/en/content/articlelanding/2024/dd/d4dd00013g) | 多Agent协作：物理模拟Agent + ML Agent + 知识检索Agent + 协调Agent | 角色分工的多Agent协作模式 |
| **Nature自主平台** | [Nature Comms 2025](https://www.nature.com/articles/s41467-025-61209-y) | 全自动设计-测试-创建闭环（DBTL），无需人工干预 | 闭环迭代 + 自适应策略 |
| **LDBT重排序** | [Nature Comms 2025](https://www.nature.com/articles/s41467-025-65281-2) | 提出Learn-Design-Build-Test替代DBTL | 先学习再设计的范式 |
| **AI-Native Biofoundry** | [ScienceCast 2026](https://sciencecast.org/casts/vylso64jadmc) | 自然语言控制全自动DBTL循环 | 非专家也能编排完整DBTL |
| **Horizyn-1** | [PNAS 2025](https://www.pnas.org/doi/10.1073/pnas.2520070123) | 双编码器对比学习（CLIP范式）关联反应↔酶序列 | 反应-酶语义匹配 |
| **Baker Lab AI酶** | [Baker Lab 2025](https://www.bakerlab.org/2025/02/13/ai-enzymes-with-complex-active-sites/) | AI生成复杂活性位点的全新酶 | de novo酶设计前沿 |

### 蛋白质RAG + 知识图谱（2025-2026）

| 系统 | 来源 | 核心创新 | 可借鉴点 |
|------|------|---------|---------|
| **Kara** | [ICML 2025](https://proceedings.mlr.press/v267/zhang25cz.html) | PKG三元组 → 向量检索 → 注入蛋白语言模型 | 知识图谱+RAG首次任务导向集成 |
| **RAG-ESM** | [Physical Review 2025](https://link.aps.org/doi/10.1103/db1b-hy16) / [GitHub](https://github.com/Bitbol-Lab/rag-esm) | 检索同源序列条件化ESM2推理 | 同源序列作为RAG检索源 |
| **ProteinHypothesis** | [ICLR 2025](https://iclr.cc/virtual/2025/33146) / [GitHub](https://github.com/adibgpt/ProteinHypothesis) | 物理感知多Agent RAG链 → 蛋白质假说生成 | 多Agent RAG + 物理约束 |
| **RAPM** | [EMNLP 2025](https://aclanthology.org/2025.emnlp-main.1211.pdf) | Bio-Knowledge Database → 检索增强蛋白质建模 | 生物知识库检索增强 |
| **BioGraphRAG** | [Nebula Graph 2025](https://nebula-graph.io/posts/biographrag-biomedical-knowledge-graph-retrieval-augmented-generation) | 专家策划的KG → RAG增强生物医学推理 | KG-RAG工程实践 |
| **BioChatter+BioCypher** | [biochatter.org](https://biochatter.org/0.9.8/vignettes/kg/) / [biocypher.org](https://biocypher.org/) | 开源生态：KG构建(BioCypher) + LLM连接(BioChatter) | 现成的KG-LLM集成框架 |
| **BioStrataKG** | [PMC 2025](https://pmc.ncbi.nlm.nih.gov/articles/PMC12448786/) | LLM构建分层KG → 检索增强深度思考 | 自动化KG构建+RAG |
| **BTE-RAG** | [bioRxiv 2025](https://www.biorxiv.org/content/10.1101/2025.08.01.668022v1) | 联邦知识检索提升LLM生物医学推理 | 多源联邦检索 |
| **ProteinKG65** | [AAAI](https://ojs.aaai.org/index.php/AAAI/article/view/26955) | 多模态蛋白质知识图谱（UniProt+GO+序列） | 蛋白质KG三元组构建方法 |
| **ProtHGT** | [bioRxiv 2025](https://www.biorxiv.org/content/10.1101/2025.04.19.649272v1) | 异构图Transformer自动蛋白质注释 | 异构图神经网络 |
| **OntoProtein** | [ICLR 2022](https://openreview.net/forum?id=yfe1VMYAXa4) | Gene Ontology嵌入 → 蛋白质预训练 | GO知识注入蛋白质模型 |
| **GeOKG** | [PubMed 2025](https://pubmed.ncbi.nlm.nih.gov/40217132/) | 几何感知KG嵌入用于Gene Ontology | 几何空间KG嵌入 |

### 文献检索Agent工具（2025-2026）

| 工具 | 来源 | 能力 |
|------|------|------|
| **BioMCP PubMed** | [biomcp.org](https://biomcp.org/sources/pubmed/) | MCP协议封装PubMed搜索 + PubTator3注释 + PMC全文 |
| **Europe PMC MCP** | [mcpmarket.com](https://mcpmarket.com/server/europe-pmc) | 4000万+文献，免费REST API，无需API Key |
| **ProteinMCP MCP Servers** | [GitHub](https://github.com/charlesxu90/ProteinMCP) | 多个蛋白质MCP服务器：结构查询、设计、分析 |
| **protein-mcp-server** | [cyanheads/GitHub](https://github.com/cyanheads/protein-mcp-server) | RCSB PDB + PDBe + UniProt 3D结构MCP |
| **protein-design-mcp** | [LobeHub](https://lobehub.com/it/mcp/jasonkim8652-protein-design-mcp) | RFdiffusion + ProteinMPNN + ESMFold MCP |
| **protein_hunter_mcp** | [GitHub](https://github.com/longevity-genie/protein_hunter_mcp) | Boltz + Chai-lab + PyRosetta + LigandMPNN MCP |

### 酶数据库前沿（2025-2026）

| 资源 | 更新 | 价值 |
|------|------|------|
| **BRENDA 2026** | [NAR 2025](https://academic.oup.com/nar/article/54/D1/D527/8315798) | 全球核心酶数据资源，新增DSMZ CellDive表达数据 |
| **Rhea** | [NAR](https://academic.oup.com/nar/article/50/D1/D693/6424769) / [Expasy](https://www.expasy.org/resources/rhea) | 反应知识库，UniProtKB酶注释标准词汇表 |
| **UniProt 2025** | [uniprot.org](https://www.uniprot.org/) | 通用蛋白质知识库，与Rhea/BRENDA交叉引用 |
| **酶催化数据驱动** | [Cell Reports 2025](https://www.cell.com/cell-reports-physical-science/fulltext/S2666-3864(25)00065-7) | 反应级+通路级数据驱动酶催化综述 |
| **ML预测生物催化** | [ScienceDirect 2025](https://www.sciencedirect.com/science/article/pii/S0734975025001843) | BRENDA/UniProt/SwissProt数据集ML基线比较 |

---

## 当前平台差距（对照全球前沿）

```
┌─────────────────────────────────────────────────────────────┐
│                    我们的现状 vs 全球前沿                     │
├─────────────────────────────────────────────────────────────┤
│  知识来源: 8个静态SKILL.md ←→ Kara/BioGraphRAG用动态KG      │
│  检索方式: 关键词匹配 ←→ RAG-ESM用同源序列向量检索           │
│  Embedding: ChromaDB 26维 ←→ ESM-2 1280维（已有但未接入）   │
│  文献: 完全空白 ←→ ProteinHypothesis多Agent RAG + PubMed     │
│  记忆: history[-6:] ←→ MLEvolve回溯记忆 + 动态全局记忆       │
│  Agent: 单Agent硬编码 ←→ ProteinMCP多MCP工具 + ProtAgents多Agent│
│  闭环: 无 ←→ Nature DBTL闭环 + LDBT范式 + AI-Native Biofoundry│
│  KG: 无 ←→ ProteinKG65多模态 + ProtHGT异构图 + BioCypher     │
└─────────────────────────────────────────────────────────────┘
```

---

## 推荐方案：四层知识增强架构

融合 Kara（KG-RAG）+ RAG-ESM（向量检索）+ ProteinMCP（MCP工具）+ ProteinHypothesis（多Agent RAG）+ MLEvolve（回溯记忆）

### 总体架构

```
用户任务 → Coordinator (路由 + 编排)
    │
    ├──→ Layer 1: Knowledge Retrieval (并行)
    │       ├── 酶知识图谱查询（跨表关联：UniProt↔BRENDA↔Rhea↔PDB↔Pfam）
    │       ├── ESM-2向量搜索相似酶（Zvec 1280维，已有基础设施）
    │       └── PubMed/Europe PMC文献检索（摘要+MeSH）
    │
    ├──→ Layer 2: PI Research (LLM + 检索结果)
    │       ├── 知识图谱上下文 → 酶家族分类、已知特性
    │       ├── 相似酶分析 → ESM-2近邻酶的功能比较
    │       └── 文献上下文 → 相关研究进展、最新方法
    │
    ├──→ Layer 3: Plan + Execute (LLM规划 + 工具执行)
    │       ├── 动态规划（参考历史经验 + 知识图谱）
    │       ├── 工具管线执行（30个工具）
    │       └── 多轮SC Review迭代
    │
    └──→ Layer 4: Synthesize (带引用的科学报告)
            ├── 注入知识图谱三元组
            ├── 注入相关文献摘要（≥3条）
            ├── 注入SKILL.md领域知识
            ├── 注入相似酶的历史经验
            └── LLM生成带引用的完整报告
```

### 新建组件详细设计

#### 1. 酶知识图谱查询引擎 — `app/services/knowledge_graph.py`

**对标**：Kara的PKG三元组 + BioCypher的KG-LLM连接 + ProteinKG65多模态KG

**核心思路**：不构建独立图数据库，而是**在现有PostgreSQL表上构建虚拟知识图谱层**，通过关联查询模拟图遍历。

```python
# 知识图谱三元组类型
TRIPLE_TYPES = {
    # 酶 → 分类
    "enzyme_has_ec": (EnzymeRecord, ECNumber, enzyme_ec_links),
    "enzyme_from_organism": (EnzymeRecord, Taxonomy, enzyme_records.taxonomy_id),
    
    # 酶 → 结构
    "enzyme_has_pdb": (EnzymeRecord, PDBStructure, pdb_structures.enzyme_id),
    "enzyme_has_alphafold": (EnzymeRecord, AlphaFoldStructure, alphafold_structures.enzyme_id),
    "enzyme_has_domain": (EnzymeRecord, PfamDomain, domain_architecture),
    
    # 酶 → 功能
    "enzyme_has_kinetics": (EnzymeRecord, KineticParameter, kinetic_parameters.enzyme_id),
    "enzyme_has_stability": (EnzymeRecord, StabilityRecord, stability_records.enzyme_id),
    "enzyme_catalyzes_reaction": (EnzymeRecord, ReactionEquation, reaction_equations),
    
    # 酶 → 进化
    "enzyme_has_evolution": (EnzymeRecord, DirectedEvolutionEntry, directed_evolution_entries),
    
    # 化合物 → 反应
    "substrate_in_reaction": (SubstrateCompound, ReactionEquation, reaction_equations),
}

class EnzymeKnowledgeGraph:
    def query_enzyme_context(self, uniprot_id: str) -> dict:
        """一次性获取酶的全部关联知识（类似图遍历1-2跳）"""
        # 返回：EC号、物种、结构、动力学、稳定性、反应、域、进化、文献
        
    def query_by_ec(self, ec_number: str) -> list[dict]:
        """查询EC号下所有酶及其关联"""
        
    def query_similar_enzymes(self, uniprot_id: str, top_k: int) -> list[dict]:
        """通过ESM-2向量找相似酶 + 返回它们的关联知识"""
        
    def query_pathway(self, ec_number: str) -> dict:
        """查询酶参与的代谢通路（通过Rhea反应关联）"""
        
    def to_natural_language(self, context: dict) -> str:
        """将知识图谱查询结果转为LLM可读的自然语言描述"""
```

**数据流**：
```
uniprot_id → EnzymeKnowledgeGraph.query_enzyme_context()
    → 返回结构化dict：
      {
        "enzyme": {...},           # 基本信息
        "ec_numbers": [...],       # EC分类
        "structures": [...],       # PDB + AlphaFold
        "kinetics": [...],         # 动力学参数
        "stability": [...],        # 稳定性数据
        "reactions": [...],        # 催化反应
        "domains": [...],          # Pfam域
        "evolution": [...],        # 定向进化
        "literature_refs": [...],  # 文献引用
        "similar_enzymes": [...],  # ESM-2相似酶
      }
    → to_natural_language() → 注入PI/SC的prompt
```

#### 2. 文献检索客户端 — `app/services/literature_client.py`

**对标**：BioMCP PubMed + Europe PMC MCP + BTE-RAG联邦检索

**核心思路**：封装PubMed E-utilities + Europe PMC REST API，支持关键词、PMID、DOI、MeSH搜索。

```python
class LiteratureClient:
    """PubMed + Europe PMC 文献检索客户端"""
    
    # --- 搜索 ---
    async def search_pubmed(self, query: str, max_results: int = 10) -> list[Paper]:
        """PubMed E-utilities搜索（免费，有API Key速率更高）"""
        
    async def search_europe_pmc(self, query: str, max_results: int = 10) -> list[Paper]:
        """Europe PMC搜索（4000万+文献，免费，无需Key）"""
        
    async def search_by_protein(self, protein_name: str, ec_number: str = None) -> list[Paper]:
        """按蛋白质名称/EC号搜索文献（自动构建MeSH查询）"""
        
    async def resolve_pmid(self, pmid: str) -> Paper | None:
        """解析PMID获取论文元数据"""
        
    async def resolve_doi(self, doi: str) -> Paper | None:
        """解析DOI获取论文元数据"""
    
    # --- 索引 ---
    async def index_to_chromadb(self, papers: list[Paper]):
        """将论文摘要索引到ChromaDB protein_literature collection"""
        
    async def search_similar_papers(self, query: str, top_k: int = 5) -> list[Paper]:
        """语义搜索已索引的论文（BM25 + 向量混合检索）"""
    
    # --- 格式化 ---
    def format_citations(self, papers: list[Paper]) -> str:
        """格式化引用列表，用于注入LLM prompt"""
```

**数据来源优先级**：
1. **已有literature_ref字段**（BRENDA/ProThermDB/EnzEngDB的PMID/DOI）→ resolve_pmid/doi
2. **PubMed E-utilities** → 按蛋白质/EC号搜索
3. **Europe PMC** → 补充全文和引用网络

**数据模型**：
```python
class Paper(Base):
    __tablename__ = "papers"
    pmid: str (PK)
    doi: str | None
    title: str
    authors: str  # JSON array
    journal: str
    year: int
    abstract: Text | None
    mesh_terms: str | None  # JSON array
    citation_count: int | None
    created_at: datetime
    
class EnzymeLiteratureLink(Base):
    __tablename__ = "enzyme_literature_links"
    enzyme_id: int (FK)
    paper_pmid: str (FK)
    relation_type: str  # kinetics/stability/structure/evolution/general
    source: str  # BRENDA/ProThermDB/EnzEngDB/pubmed_search/manual
```

#### 3. ESM-2向量检索接入Agent

**对标**：RAG-ESM同源序列检索 + Kara知识感知检索

**现状**：`app/ml/vector_search.py`已有EnzymeVectorSearch（1280维ESM-2 + Zvec），但只暴露REST API，未被Agent调用。

**改动**：
```python
# 在 _research_pi() 和 _synthesize_sc() 中调用：
from app.ml.vector_search import EnzymeVectorSearch

async def _search_similar_enzymes(self, sequence: str, top_k: int = 5) -> list[dict]:
    """通过ESM-2向量搜索相似酶，返回uniprot_id + cosine距离"""
    vsearch = EnzymeVectorSearch()
    results = await vsearch.search_by_sequence(sequence, top_k)
    # 返回: [(uniprot_id, distance), ...]
    
    # 对每个相似酶查询知识图谱获取上下文
    kg = EnzymeKnowledgeGraph()
    enriched = []
    for uniprot_id, distance in results:
        context = kg.query_enzyme_context(uniprot_id)
        enriched.append({"uniprot_id": uniprot_id, "similarity": 1-distance, **context})
    return enriched
```

#### 4. 回溯记忆系统 — `app/memory/experience_store.py`

**对标**：MLEvolve回溯记忆（冷启动知识库 + 动态全局记忆 + 混合检索）

```python
class ExperienceRecord:
    task_type: str          # design/analyze/research
    protein_family: str     # EC号或蛋白质家族
    sequence_hash: str      # 序列SHA-256
    pipeline: list[str]     # 执行的工具序列
    success_metrics: dict   # 各步骤评分
    total_duration: float
    user_rating: int | None
    round_number: int       # 迭代轮次
    created_at: datetime

class ExperienceStore:
    def record(self, experience: ExperienceRecord):
        """执行后记录经验"""
        
    def search_similar_experiences(self, task_type: str, protein_family: str, 
                                    sequence: str = None, top_k: int = 5) -> list[ExperienceRecord]:
        """检索相似任务的历史经验（结构化查询 + 语义检索）"""
        
    def get_best_pipeline(self, task_type: str, protein_family: str) -> list[str] | None:
        """获取该任务类型的历史最优管线"""
        
    def get_domain_knowledge(self, task_type: str) -> str:
        """获取冷启动领域知识（复用SKILL.md）"""
```

#### 5. Agent改动集成点

**`agent_graph.py` 改动**：

```python
# _research_pi() 增加三层知识检索
async def _research_pi(self, message, history, context, provider, model):
    # 1. 提取蛋白质标识
    sequence = self._extract_sequence(message)
    protein_name = self._extract_protein_name(message)
    
    # 2. 知识图谱查询
    kg = EnzymeKnowledgeGraph()
    kg_context = ""
    if protein_name:
        enzyme = await kg.query_by_name(protein_name)
        if enzyme:
            kg_context = kg.to_natural_language(kg.query_enzyme_context(enzyme.uniprot_id))
    
    # 3. ESM-2向量搜索相似酶
    similar_context = ""
    if sequence:
        similar = await self._search_similar_enzymes(sequence)
        similar_context = f"\nSimilar enzymes found:\n{json.dumps(similar, default=str)[:500]}"
    
    # 4. 文献检索
    lit_client = LiteratureClient()
    papers = await lit_client.search_by_protein(protein_name or "")
    literature_context = lit_client.format_citations(papers[:5])
    
    # 5. 回溯记忆
    exp_store = ExperienceStore()
    past = exp_store.search_similar_experiences("analyze", protein_name)
    memory_context = f"\nPast experiences:\n{json.dumps(past, default=str)[:300]}" if past else ""
    
    # 6. 组合上下文 → PI LLM
    enriched_context = f"{context}\n\n{kg_context}\n{similar_context}\n{literature_context}\n{memory_context}"
    # ... 调用LLM
```

```python
# _synthesize_sc() 注入知识图谱 + 文献
async def _synthesize_sc(self, task, tool_results, research, history, provider, model):
    # 原有: domain_context = self._load_relevant_skills(task)
    # 新增:
    kg = EnzymeKnowledgeGraph()
    kg_context = kg.to_natural_language(kg.query_by_task(task))
    
    lit_client = LiteratureClient()
    papers = await lit_client.search_by_protein(self._extract_protein_name(task))
    literature = lit_client.format_citations(papers[:5])
    
    full_context = f"{SC_SYSTEM_PROMPT}\n{domain_context}\n\n--- KNOWLEDGE GRAPH ---\n{kg_context}\n\n--- RELATED LITERATURE ---\n{literature}"
```

---

## 实施路线图

### Phase 1（2周）：知识图谱 + 文献基础设施
1. ✅ `knowledge_graph.py` — 酶知识图谱查询引擎
2. ✅ `literature_client.py` — PubMed + Europe PMC客户端
3. ✅ `models/literature.py` — Paper + EnzymeLiteratureLink数据模型
4. ✅ Alembic迁移 — papers + enzyme_literature_links表
5. ✅ `literature_store.py` — ChromaDB protein_literature索引
6. ✅ 解析现有literature_ref字段 → 批量resolve PMID/DOI

### Phase 2（2周）：Agent知识注入 + ESM-2接入
7. ✅ `_research_pi()` 增加知识图谱 + 文献 + 向量检索
8. ✅ `_synthesize_sc()` 注入知识图谱 + 文献引用
9. ✅ `vector_search.py` 接入Agent（search_similar_enzymes）
10. ✅ 更新 PI_SYSTEM_PROMPT + SC_SYSTEM_PROMPT

### Phase 3（2周）：回溯记忆 + 迭代优化
11. ✅ `experience_store.py` — 经验记录 + 检索
12. ✅ 规划时查询历史最优管线
13. ✅ 执行后记录经验
14. ✅ 多轮SC迭代（最多3轮）

### Phase 4（2周）：Data/Literature Agent拆分
15. ✅ 拆分Data Agent（数据库+KG查询）
16. ✅ 拆分Literature Agent（文献检索+RAG）
17. ✅ Coordinator编排（并行执行Data+Literature）
18. ✅ 工具执行Agent保留现有MLS角色

### 验证指标
- Agent报告包含 ≥3条相关文献引用（PMID + 标题 + 摘要）
- 知识图谱查询覆盖 ≥80%的已存酶数据
- ESM-2向量搜索找到相似酶（cosine > 0.8）并注入报告
- 第二次分析同类蛋白质时规划参考历史经验
- 端到端：从用户提问到带引用报告 < 60秒

---

## 实现级技术细节

### PubMed E-utilities 实现方案

**参考**：[Biopython Entrez](https://biopython.org/docs/dev/Tutorial/chapter_entrez.html) / [NCBI E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25499/)

```python
# 直接用 httpx 异步调用（不依赖 Biopython 同步 API）
class PubMedClient:
    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    
    async def esearch(self, query: str, retmax: int = 10) -> list[str]:
        """搜索 PubMed，返回 PMID 列表"""
        # GET /esearch.fcgi?db=pubmed&term={query}&retmax={retmax}&retmode=json
        # 酶特异性查询构建：
        # - 按蛋白名: "{protein_name}[Title/Abstract] AND enzyme[MeSH]"
        # - 按EC号:  "EC {ec_number}[Title/Abstract]"
        # - 按MeSH:  "{protein_name}[MeSH Terms] AND kinetics[Subheading]"
        
    async def efetch(self, pmids: list[str]) -> list[dict]:
        """获取论文元数据（标题、作者、摘要、MeSH）"""
        # GET /efetch.fcgi?db=pubmed&id={pmids}&rettype=xml&retmode=xml
        # 解析 XML 提取: title, authors[], abstract, mesh_terms[], journal, year
        
    async def esummary(self, pmids: list[str]) -> list[dict]:
        """快速获取论文摘要信息（比efetch轻量）"""
        # GET /esummary.fcgi?db=pubmed&id={pmids}&retmode=json
```

**速率限制**：无 API Key = 3次/秒；有 NCBI_API_KEY = 10次/秒
**缓存策略**：PMID → 论文元数据缓存到 Redis/LRU（论文元数据不会变）

### Europe PMC REST API 实现方案

**参考**：[Articles RESTful API](https://europepmc.org/RestfulWebService)

```python
class EuropePMCClient:
    BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest"
    
    async def search(self, query: str, page_size: int = 10) -> list[dict]:
        """搜索 Europe PMC（4000万+文献，免费，无需API Key）"""
        # GET /search?query={query}&format=json&resultType=core&pageSize={page_size}
        # 支持的查询语法:
        # - 全文: "enzyme engineering"
        # - 字段: TITLE:"lipase" OR ABSTRACT:"directed evolution"
        # - MeSH: MESH:"enzymes" 
        # - 引用: CITED:50  (被引50次以上)
        # - 组合: (TITLE:"lipase" OR TITLE:"esterase") AND YEAR:[2023 TO 2026]
        
    async def get_article(self, source: str, pmid_or_doi: str) -> dict:
        """获取单篇论文详情"""
        # GET /{source}/{id}?format=json
        # source = "MED" (PubMed) | "DOI" | "PMC"
        
    async def get_citations(self, pmid: str) -> list[dict]:
        """获取引用该论文的文献列表"""
        # GET /MED/{pmid}/citations?format=json
        
    async def get_references(self, pmid: str) -> list[dict]:
        """获取该论文引用的参考文献列表"""
        # GET /MED/{pmid}/references?format=json
```

### ChromaDB 混合检索方案（BM25 + 向量）

**参考**：[ChromaDB Sparse Vector Support](https://www.trychroma.com/project/sparse-vector-search)

ChromaDB 现已原生支持 BM25/SPLADE 稀疏向量，可直接实现混合检索：

```python
class LiteratureStore:
    """文献 ChromaDB 索引 + 混合检索"""
    
    def __init__(self):
        self.collection = chromadb_client.get_or_create_collection(
            name="protein_literature",
            metadata={"hnsw:space": "cosine"},
        )
        # ChromaDB 新版本支持 sparse_vector 字段实现 BM25
    
    async def index_papers(self, papers: list[Paper]):
        """批量索引论文摘要"""
        for paper in papers:
            self.collection.upsert(
                ids=[paper.pmid],
                documents=[paper.abstract or ""],
                embeddings=[embed_text(paper.abstract)],  # dense embedding
                # sparse_vectors=[bm25_encode(paper.abstract)],  # BM25
                metadatas=[{
                    "title": paper.title,
                    "authors": json.dumps(paper.authors),
                    "journal": paper.journal,
                    "year": paper.year,
                    "doi": paper.doi or "",
                    "mesh_terms": json.dumps(paper.mesh_terms or []),
                }]
            )
    
    async def hybrid_search(self, query: str, top_k: int = 5) -> list[dict]:
        """BM25 + 向量混合检索（Reciprocal Rank Fusion）"""
        # 1. Dense vector search
        dense_results = self.collection.query(
            query_embeddings=[embed_text(query)],
            n_results=top_k * 2,
        )
        # 2. Sparse/BM25 search (if supported)
        # sparse_results = self.collection.query(
        #     query_sparse_vectors=[bm25_encode(query)],
        #     n_results=top_k * 2,
        # )
        # 3. RRF fusion: score = sum(1 / (k + rank_i))
        # 4. Return top_k merged results
        
    async def search_by_enzyme(self, protein_name: str, ec_number: str = None, top_k: int = 5) -> list[dict]:
        """按酶名称/EC号搜索已索引文献"""
        query_parts = [protein_name]
        if ec_number:
            query_parts.append(f"EC {ec_number}")
        query = " ".join(query_parts)
        
        # 先用 metadata filter 缩小范围
        results = self.collection.query(
            query_embeddings=[embed_text(query)],
            where={"$or": [
                {"title": {"$contains": protein_name}},
                {"mesh_terms": {"$contains": protein_name}},
            ]},
            n_results=top_k,
        )
        return results
```

### BioCypher 知识图谱方案（可选进阶）

**参考**：[BioCypher](https://biocypher.org/) / [Protein KG Tutorial](https://biocypher.org/BioCypher/learn/tutorials/tutorial_basics_neo4j_offline/tutorial_004_neo4j_offline/)

如果未来需要独立图数据库（Neo4j），BioCypher 提供标准化适配器模式：

```yaml
# schema_config.yaml — 酶知识图谱 Schema
protein:
  represented_as: node
  is_a: biolink:Protein
  input_label: protein
  properties:
    uniprot_id: str
    name: str
    sequence: str
    organism: str

enzyme:
  represented_as: node
  is_a: biolink:Enzyme
  input_label: enzyme
  properties:
    uniprot_id: str
    ec_numbers: list[str]

ec_number:
  represented_as: node
  is_a: biolink:BiologicalEntity
  input_label: ec_class
  properties:
    ec: str
    name: str
    level: int

enzyme_has_ec:
  represented_as: edge
  is_a: biolink:has_participant
  input_label: enzyme_ec_link
  
enzyme_has_structure:
  represented_as: edge
  is_a: biolink:has_3d_structure
  input_label: pdb_link
  
enzyme_has_kinetics:
  represented_as: edge
  is_a: biolink:has_attribute
  input_label: kinetics_link
```

**当前推荐**：不引入 Neo4j，而是在 PostgreSQL 上用 `EnzymeKnowledgeGraph` 类模拟图遍历。理由：
- 已有15张表的关系型数据，JOIN 查询足够
- 避免引入新基础设施依赖
- 未来可无缝迁移到 BioCypher + Neo4j

### 文献 Embedding 模型选择

| 模型 | 维度 | 适用场景 | 推荐度 |
|------|------|---------|--------|
| **text-embedding-3-small** (OpenAI) | 1536 | 通用文本，性价比高 | ⭐⭐⭐ |
| **SPECTER2** (AllenAI) | 768 | 专为科学论文设计 | ⭐⭐⭐⭐ |
| **BioBERT** (DMIS-Lab) | 768 | 生物医学文本 | ⭐⭐⭐⭐ |
| **ESM-2 mean embedding** (已有) | 1280 | 蛋白质序列（非文本） | 用于序列搜索 |
| **sentence-transformers** | 384-768 | 通用文本，本地部署 | ⭐⭐⭐ |

**推荐方案**：
- **Phase 1**：用 LLM provider 的 embedding API（OpenAI/阿里云 text-embedding-v3）
- **Phase 2**：切换到 SPECTER2 或 BioBERT（专为科学文献优化）
- **蛋白质序列**：继续用已有的 ESM-2 1280维（Zvec）

---

## 参考论文索引

1. MLEvolve — [arXiv 2606.06473](https://arxiv.org/abs/2606.06473) / [GitHub](https://github.com/InternScience/MLEvolve)
2. ProteinMCP — [Protein Science 2026](https://onlinelibrary.wiley.com/doi/full/10.1002/pro.70547) / [GitHub](https://github.com/charlesxu90/ProteinMCP)
3. ProtAgents — [Digital Discovery 2024](https://pubs.rsc.org/en/content/articlelanding/2024/dd/d4dd00013g) / [arXiv](https://arxiv.org/html/2402.04268v1)
4. Kara — [ICML 2025](https://proceedings.mlr.press/v267/zhang25cz.html)
5. RAG-ESM — [Physical Review 2025](https://link.aps.org/doi/10.1103/db1b-hy16) / [GitHub](https://github.com/Bitbol-Lab/rag-esm)
6. ProteinHypothesis — [ICLR 2025](https://iclr.cc/virtual/2025/33146) / [GitHub](https://github.com/adibgpt/ProteinHypothesis)
7. BioGraphRAG — [Nebula Graph 2025](https://nebula-graph.io/posts/biographrag-biomedical-knowledge-graph-retrieval-augmented-generation)
8. BioChatter+BioCypher — [biochatter.org](https://biochatter.org/) / [biocypher.org](https://biocypher.org/)
9. ProteinKG65 — [AAAI](https://ojs.aaai.org/index.php/AAAI/article/view/26955)
10. ProtHGT — [bioRxiv 2025](https://www.biorxiv.org/content/10.1101/2025.04.19.649272v1)
11. Horizyn-1 — [PNAS 2025](https://www.pnas.org/doi/10.1073/pnas.2520070123)
12. BRENDA 2026 — [NAR 2025](https://academic.oup.com/nar/article/54/D1/D527/8315798)
13. Nature DBTL闭环 — [Nature Comms 2025](https://www.nature.com/articles/s41467-025-61209-y)
14. LDBT重排序 — [Nature Comms 2025](https://www.nature.com/articles/s41467-025-65281-2)
15. BioMCP PubMed — [biomcp.org](https://biomcp.org/sources/pubmed/)
16. Europe PMC MCP — [mcpmarket.com](https://mcpmarket.com/server/europe-pmc)
17. BioStrataKG — [PMC 2025](https://pmc.ncbi.nlm.nih.gov/articles/PMC12448786/)
18. BTE-RAG — [bioRxiv 2025](https://www.biorxiv.org/content/10.1101/2025.08.01.668022v1)
19. OntoProtein — [ICLR 2022](https://openreview.net/forum?id=yfe1VMYAXa4)
20. GeOKG — [PubMed 2025](https://pubmed.ncbi.nlm.nih.gov/40217132/)
21. RAPM — [EMNLP 2025](https://aclanthology.org/2025.emnlp-main.1211.pdf)
22. AI-Native Biofoundry — [ScienceCast 2026](https://sciencecast.org/casts/vylso64jadmc)
