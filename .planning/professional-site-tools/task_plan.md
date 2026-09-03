# 专业位点工具深度调研计划

## 目标

确认可真实输出残基位点的专业工具，并制定适合 SWISS-MODEL/PDB/FASTA 多输入的接入顺序。

## 阶段

- [x] 核验工具能力、输入输出与许可
- [x] 对照平台现有工具与运行时
- [x] 形成可执行接入方案与验证矩阵
- [x] 记录研究边界与未验证项
- [x] 接入真实运行时门控的口袋残基工具
- [x] 将口袋工具接入多 PDB 规划和候选证据桥接
- [x] 完成后端结构/规划/工具回归

## 结论

- P0 集成：M-CSA/UniProt + InterProScan/BLAST + SIFTS/sequence alignment。
- 比活力位点：P2Rank/fpocket + PLIP（有配体）+ CAVER（通道）+ HotSpot Wizard（外部设计证据）。
- 热稳定位点：FireProt/PROSS + FoldX/Rosetta 真实 runtime。
- 当前 `mutation_priority_score` 仅能作为 proxy 排序，不能替代上述专业工具。

## 实现决策

- `pocket_residue_lookup` 优先尝试本机 P2Rank，其次 fpocket；未安装时返回 `RUNTIME_UNAVAILABLE`，不生成位点。
- 只有用户明确提出口袋/通道/P2Rank/fpocket 时才加入规划，避免无条件增加深度分析耗时。
- 解析出的口袋残基通过 `pocket_residue_positions` 传入 `mutation_priority_score`，并标记为 `professional_tool_geometry`；仍不升级为催化或湿实验结论。
