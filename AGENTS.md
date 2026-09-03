# AGENTS.md — 酶蛋白 AI 平台项目记忆

后续 agent 进入本项目时，先读取：

- `task_plan.md`
- `findings.md`
- `progress.md`
- `docs/project-experience-memory.md`

## 必守边界

- 不使用 Codex `view_image` 工具；本机模型不支持图像输入。需要图片元数据时用 `sips`、`file`、`mdls`、`ls -lh`。
- Codex 只使用 `4200-4299` 端口范围；本项目默认前端入口是 `http://localhost:4200`。
- 不要声称真实 GPU/GROMACS 长 MD、真实突变体 topology、真实 Vina docking、真实 ligand topology 已完成，除非实际在具备工具链的服务器上跑过并有日志/测试结果。
- 阿里云 GPU 服务器尚未提供；GPU/长 MD/live gate 任务必须继续等待用户提供服务器后再执行。
- 本机当前缺少 `gmx/gmx_mpi`、`obabel`、`vina`、`acpype`、`antechamber`，只能做代码层、smoke、受控 blocked 合同和本地单测。
- `Structure2D_COMPOUND_CID_5478883.sdf` 是 2D SDF，不可直接对接或进入 GROMACS。
- 运行后端主回归和 `scripts/run_release_acceptance.py` 时串行执行，避免 SQLite 测试库冲突。
- `docker compose config` 会展开 `.env` 明文；优先使用 `config --quiet`，不要把密钥输出到终端或日志。
- 工作区可能很脏；不要回滚或删除用户/其他 agent 的改动。

## 当前长期方向

- 真实数据层继续按 `PDB -> AlphaFold -> Foldseek DB` 顺序补齐。
- 配体/底物链路按 `2D SDF -> 3D -> PDBQT -> Vina -> ACPYPE/Antechamber topology -> GROMACS` 顺序推进。
- MD 长任务、topology live gate、真实 batch ranking 等待阿里云 GPU/GROMACS 节点。
