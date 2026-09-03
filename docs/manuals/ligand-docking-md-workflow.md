# 底物预处理、对接与 MD 前置流程

## 核心结论

`Structure2D_COMPOUND_CID_5478883.sdf` 是 2D 平面 SDF：有化学键和元素信息，但没有可用于对接和分子动力学的真实三维构象。它不能直接进入 AutoDock Vina，也不能直接和蛋白一起送入 GROMACS。

必须先完成：

```text
2D SDF 底物
  -> 生成 3D 构象 + 加氢 + 几何优化
  -> 质子化/分配电荷
  -> 转 PDBQT
  -> Vina 分子对接
  -> 酶-底物 3D 复合物
  -> ACPYPE/Antechamber 生成小分子 GAFF2/ITP 拓扑
  -> GROMACS 组装体系、溶剂化、平衡、生产 MD
```

## 工具合同

| 阶段 | 推荐工具 | 输出 |
|------|----------|------|
| 2D -> 3D | OpenBabel 或 RDKit | `ligand_3d.sdf` / `ligand_3d.mol2` |
| 对接预处理 | OpenBabel / Meeko / MGLTools | `ligand.pdbqt` |
| 口袋盒子 | ChimeraX 辅助查看 | center X/Y/Z + size X/Y/Z |
| 分子对接 | AutoDock Vina | ligand pose / docked complex |
| 小分子拓扑 | ACPYPE + Antechamber / AmberTools | `.itp`、`.gro`、参数文件 |
| MD | GROMACS | `.tpr`、`.xtc`、`.edr`、`.xvg`、报告指标 |

## 当前项目检查入口

非致命检查：

```bash
make backend-ligand-toolchain-smoke
```

部署/live gate：

```bash
make backend-ligand-toolchain-live-gate
```

JSON 输出：

```bash
cd backend
.venv/bin/python scripts/smoke_ligand_toolchain.py --json
```

当前本机预期结果是 `blocked_toolchain_missing`，因为没有安装 OpenBabel/RDKit、Vina、ACPYPE/Antechamber 和 GROMACS。

2026-07-10 本机验证结果：

```text
make backend-ligand-toolchain-smoke
ligand_toolchain_smoke status=blocked_toolchain_missing input_sdf_exists=True is_2d_sdf=True atom_count=111 bond_count=110 missing=conformer_generation,pdbqt_preparation,vina_docking,ligand_topology,gromacs_md
```

这说明输入 SDF 已可被解析并确认是 2D，但本机仍缺少真实 3D 构象、PDBQT、Vina、拓扑和 GROMACS 所需工具链。该结果是安全阻断，不是失败伪造。

## 后端工具入口

平台已新增异步工具 `ligand_preprocess`，可通过通用工具 API 提交：

```bash
POST /api/tools/ligand_preprocess/submit
```

最小请求：

```json
{
  "params": {
    "sdf_object_name": "uploads/user_<id>/ligand.sdf",
    "stages": ["preflight", "generate_3d"],
    "store_outputs": true
  }
}
```

HTTP API 只接受 `sdf_data` 或当前用户拥有的 `sdf_object_name`；`sdf_path` 只允许在受控主机侧脚本/worker 内使用，不允许从 Web 请求透传本地路径。

当前支持的阶段：

| 阶段 | 当前行为 |
|------|----------|
| `preflight` | 检查 SDF 维度和 OpenBabel/Vina/ACPYPE/Antechamber/GROMACS 是否可用 |
| `generate_3d` | OpenBabel 存在时真实执行 `obabel ligand_2d.sdf -O ligand_3d.sdf --gen3d -h`；缺失时返回 `blocked` |
| `prepare_pdbqt` | OpenBabel 存在且有 3D ligand、pH、质子化策略、电荷模型时真实生成 PDBQT；策略仍需人工复核 |
| `vina_docking` | Vina 存在且有 ligand/receptor PDBQT、完整 pocket center/size 时真实对接 |
| `ligand_topology` | 在阿里云 ligand worker 中通过 ACPYPE/AmberTools 真实生成 GROMACS topology；后端失败仍返回 `failed`，不伪造拓扑 |

`ligand_preprocess` 使用独立 `ligand_cpu` 队列，任务审计会脱敏 `sdf_data` 原文，只记录输入类型、队列和结果摘要。

## 部署运行时

平台提供专用 ligand worker 镜像：

```text
docker/Dockerfile.ligand-worker
docker/Dockerfile.ligand-worker.aliyun
```

该镜像安装/封装：

- OpenBabel：2D SDF -> 3D 构象、加氢、格式转换
- RDKit：2D/3D 构象与化学信息处理的备用 Python runtime；当前 Dockerfile 保留检测入口，实际安装需通过受控 wheelhouse/镜像源补齐
- AutoDock Vina：对接运行时
- ACPYPE：小分子拓扑桥接
- AmberTools/Antechamber：GAFF2/BCC 参数后端；阿里云 worker 使用 ACPYPE bundled AmberTools，并检测 `antechamber`、`parmchk2`、`teLeap` 是否能加载
- GROMACS：复合物 MD 前置兼容检查

镜像内置只读检测入口：

```bash
ligand-runtime-check
ligand-runtime-check --require-live
```

`ligand-runtime-check` 只检查 `obabel`、`rdkit`、`vina`、`acpype`、`antechamber`/`parmchk2`/`teLeap`、`gmx`/`gmx_mpi` 的存在性、版本信息和动态库可加载性，不执行真实对接、拓扑或 MD 作业。本机没有完整科学工具链时，预期状态仍是 `blocked_toolchain_missing`；部署节点可用 `--require-live` 作为上线 gate。

运行时边界：

| 边界 | 约束 |
|------|------|
| 队列 | 只消费 `ligand_cpu`，默认并发 `CELERY_LIGAND_WORKER_CONCURRENCY=1` |
| 文件系统 | `deploy_data` 只读挂载到 `/app/deploy_data`；临时/中间产物写入 `/app/storage` 或容器临时目录 |
| 工具链 | OpenBabel/RDKit/Vina/ACPYPE/AmberTools/GROMACS 只允许在 ligand worker 镜像内提供，backend/default worker 不直接 shell out |
| 网络/端口 | ligand worker 不暴露主机端口；Web 入口仍走 Codex 分配范围内的 `4200` |

本地 compose 服务：

```bash
make docker-config-ligand-worker
make docker-build-ligand-worker
```

`docker-config-ligand-worker` 使用 quiet 校验，不打印 `.env` 明文。

2026-07-10 本机 compose 验证：

```text
make docker-config-ligand-worker
# 通过，无明文 env 输出
```

`docker-build-ligand-worker` 需要网络/镜像源和包仓库可用；阿里云 app/gpu compose 使用 `Dockerfile.ligand-worker.aliyun`，从已构建的 `protein-ai-backend:aliyun` 继承，只补 OpenBabel/Vina/ACPYPE/RDKit，减少 ECS 构建时间。部署节点应先执行 `docker-config-ligand-worker`，再执行 build，并在容器内运行：

```bash
ligand-runtime-check
ligand-runtime-check --require-live
```

阿里云 GPU/scientific 节点会同时运行：

| 服务 | 队列 | 用途 |
|------|------|------|
| `md-worker` | `md_cpu` | GROMACS MD 长任务 |
| `ligand-worker` | `ligand_cpu` | 配体 3D、对接预处理、小分子拓扑 |

## 不能省略的边界

- ChimeraX 只负责可视化、检查构象和辅助确定对接盒子，不负责批量把 2D SDF 自动变成可靠 3D 构象。
- 2D SDF 不能直接进入 Vina，也不能直接进入 GROMACS。
- 对接得到的底物 pose 仍然没有 GROMACS 力场参数，必须再做小分子拓扑。
- 没有完成小分子拓扑前，不能把酶-底物复合物结果用于报告级 MD ranking。
