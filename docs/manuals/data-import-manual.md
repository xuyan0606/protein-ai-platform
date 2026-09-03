# 数据导入手册

适用版本：0.1.0

## 标准目录

真实数据统一放入项目根目录下的 `deploy_data/`：

```text
deploy_data/
  annotations/
  sifts/
  foldseek/
  pdb/
  alphafold/
  smoke/
    query.pdb
```

## 当前支持的数据

- annotations：本地注释、InterPro、M-CSA、SignalP 等 JSON/CSV/TSV
- SIFTS：PDB residue 到 UniProt residue 的映射
- Foldseek DB：结构搜索数据库
- PDB：实验结构
- AlphaFold：预测结构，建议优先使用 `.cif`，PAE 用 `.json`

## 导入流程

1. 准备真实数据目录。
2. 使用导入脚本复制或链接到标准目录。
3. 生成 env 覆盖。
4. 运行 readiness 和 smoke。

示例：

```bash
python3 scripts/import_deploy_data.py \
  --annotations /path/to/annotations \
  --sifts /path/to/sifts \
  --foldseek-root /path/to/foldseek \
  --smoke-pdb /path/to/query.pdb

make write-deploy-env
make check-deploy-data
make deploy-preflight
```

真实上线前必须通过：

```bash
make deploy-live-gate
```

## 导入边界

- `scripts/import_deploy_data.py` 只负责把外部文件 stage/copy/symlink 到 `deploy_data/`，不是训练集导出。
- `backend/scripts/import_domain_sqlite_to_pg.py` 是 SQLite 到 PostgreSQL 的 domain 表全量 restore，不做 A-only、hold、reviewed-label 或 training-safe 筛选。
- 高置信导出只能使用明确的 export-safe 入口，例如 compact enzyme DB 的 `/api/data/enzyme-dbs/{family}/export-safe/measurements`。
- `/api/data/stats` 和普通 browse/search 接口是浏览/审计视图，可能包含非导出、hold、B、medium、preprint 或 review 边界数据。

## AlphaFold 文件格式

主要文件：

- `AF-<UniProt>-F1-model_v4.cif`：结构模型，推荐用于结构搜索和展示
- `AF-<UniProt>-F1-predicted_aligned_error_v4.json`：PAE 置信度矩阵

可选文件：

- `.pdb`：兼容工具使用，但 AlphaFold 官方主推 mmCIF

## Foldseek DB

Foldseek DB 用于结构相似性搜索，不替代 PostgreSQL、Redis、MinIO、ChromaDB。

常用构建入口：

```bash
make build-foldseek-pdb-db
make build-foldseek-alphafold-db
make materialize-foldseek-db
```

容器部署前建议运行 `materialize-foldseek-db`，避免宿主机软链接在容器内失效。

## 数据状态检查

```bash
make check-deploy-data
make backend-readiness
make backend-smoke-demo
make backend-smoke-live
```

`demo-ready` 只能说明 demo 数据可跑通，不等于真实数据上线可用。

## 定期更新编排

真实数据更新以 `deploy_data/live_manifest.json` 为入口，维护 PDB ID 和 UniProt ID：

```json
{
  "schema_version": 2,
  "pdb_ids": ["1QHP", "1QHO"],
  "uniprot_ids": ["P00692", "P19531"],
  "alphafold_structure_format": "cif",
  "download_pae_json": true,
  "required_live_components": ["annotations", "sifts", "pdb", "alphafold", "foldseek", "smoke_query"],
  "expected_datasets": {
    "pdb": {"source": "RCSB PDB", "expected_from": "pdb_ids"},
    "sifts": {"source": "PDBe UniProt mappings", "expected_from": "pdb_ids"},
    "alphafold": {"source": "AlphaFold DB", "expected_from": "uniprot_ids"},
    "annotations": {"source": "UniProt/InterPro plus curated exports", "expected_from": "uniprot_ids"},
    "foldseek": {"depends_on": ["pdb", "alphafold"]}
  }
}
```

上线前先看计划，不联网、不写入：

```bash
make deploy-data-update-plan
python3 scripts/run_deploy_data_update.py --plan-only --json
python3 scripts/check_deploy_data.py --plan-only --json
```

`check_deploy_data.py --plan-only` 只读取本机文件和 `live_manifest.json`，不会下载或重建数据库。输出中重点看：

- `expected_count` / `actual_count`：manifest 期望数量与本机已 staging 文件数量。
- `missing_items`：按 PDB ID、UniProt ID 或组件列出的缺失项。
- `next_actions`：下一步应由人工 staging、联网数据主机下载，还是重建 Foldseek。
- `planned_commands`：可在具备网络和 Foldseek runtime 的数据主机上执行的命令预览。
- `version_comparison`：manifest 版本与本机组件更新时间的只读对照。

本机 plan-only 工作只允许生成报告和命令预览；不要在无批准时下载真实大数据。

真实执行一轮更新：

```bash
make deploy-data-update
```

执行后会写入：

```text
deploy_data/updates/deploy_data_update_<timestamp>.json
```

该记录包含执行状态、命令、耗时、stdout/stderr 尾部和 `check_deploy_data` 结果，供管理后台更新记录与上线复核使用。

建议定时任务示例：

```cron
0 3 * * 0 cd /path/to/酶蛋白AI平台 && python3 scripts/run_deploy_data_update.py --manifest deploy_data/live_manifest.json
```

如果现场网络不可用，但文件已经由其他方式同步到 `deploy_data/`，可以跳过下载，仅重建 Foldseek/env/check：

```bash
python3 scripts/run_deploy_data_update.py --skip-downloads
```

## 截图与维护窗口

截图版操作说明见 [截图版操作手册（文字占位版）](screenshot-operation-placeholder-manual.md)。

待真实浏览器补齐的截图：

- `data-readiness.png`：`/data` 数据资产 readiness 总览。
- `data-update-history.png`：数据更新记录、状态和失败原因。
- `data-import-dry-run.png`：导入 dry-run 或确认前预览。

不需要维护窗口：

- `make deploy-data-update-plan`
- `python3 scripts/run_deploy_data_update.py --plan-only --json`
- 查看 `/data` readiness 和更新历史

必须维护窗口执行：

- 真实替换生产 `deploy_data/`
- 重建并切换生产 Foldseek DB
- 切换 `.env.deploy-data` 或生产挂载
- 真实 live gate 后需要重启服务的导入流程
