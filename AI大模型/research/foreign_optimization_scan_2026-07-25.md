# 国外先进方案优化调研

日期：2026-07-25

范围：KWB-EnzymeDesigner 本地研发优化建议。仅做调研和路线规划，不代表已接入生产。

## 总结

国外先进路线继续证明：酶蛋白 AI 平台不应把能力压成一个聊天模型，而应形成“主控 LLM + 专业结构/功能/设计/评测工具链”。

对科为博当前最值得优化的不是继续增加模型名称，而是补齐 6 条工程能力：

1. 商业可用的结构与复合物预测后端。
2. 蛋白-底物/配体结合亲和力和口袋评估。
3. 结构条件序列设计和配体环境序列设计。
4. 酶功能/EC 号交叉校验。
5. 本地 MSA/保守性执行器。
6. 真实湿实验反馈闭环和失败样本保留。

## 值得优先评估的国外工具

### Boltz-2

定位：结构 + 结合亲和力联合预测。

价值：

- MIT license，适合商业研发评估。
- 相比 AlphaFold 3，更适合作为科为博本地可控结构/亲和力候选后端。
- 对 `KWB-SubstrateFitModel` 和底物 fit head 有直接价值。

建议：

- 建本地 adapter，输入蛋白序列/结构 + 小分子，输出 complex structure、binding affinity proxy、confidence。
- 输出只作为预测结构/预测亲和力证据，不和实验结构/实验活性混用。

参考：

- https://github.com/jwohlwend/boltz
- https://pmc.ncbi.nlm.nih.gov/articles/PMC12262699/

### Chai-1

定位：多模态分子结构预测，覆盖蛋白、小分子、DNA、RNA 等。

价值：

- 能作为 AlphaFold 3 的可运行替代评估对象。
- 支持无 MSA 运行，也建议使用 MSA 提升性能。

限制：

- GPU 要求较高，推荐 A100/H100，大复合物成本不低。

参考：

- https://huggingface.co/chaidiscovery/chai-1

### AlphaFold 3

定位：强结构/相互作用预测基准。

价值：

- 应作为国际对标基准，不应直接作为商业本地模型基础。

限制：

- 官方源码和参数是非商业许可；商业研发使用必须谨慎。
- AlphaFold 3 输出也不应被用来训练类似结构预测模型。

参考：

- https://github.com/google-deepmind/alphafold3
- https://github.com/google-deepmind/alphafold3/blob/main/WEIGHTS_TERMS_OF_USE.md

### ProteinMPNN / LigandMPNN

定位：给定结构/配体环境的序列设计。

价值：

- ProteinMPNN 适合结构约束下的候选突变组合生成。
- LigandMPNN 更适合酶，因为它显式建模小分子、金属、核酸等非蛋白原子上下文。

建议：

- 在 KWB 中放在“生成候选”阶段，而不是直接给 Go/No-Go。
- 生成候选后必须经过稳定性、保守性、催化残基保护、底物 fit 和实验可行性过滤。

参考：

- https://pmc.ncbi.nlm.nih.gov/articles/PMC9997061/
- https://pmc.ncbi.nlm.nih.gov/articles/PMC11978504/

### RFdiffusion

定位：骨架生成、motif scaffolding、active-site scaffolding。

价值：

- 更偏 de novo design 和 active-site scaffold，不是当前突变排序的第一优先级。
- 适合未来做“新酶骨架/新口袋”方向。

建议：

- 当前先不接入主流程；先作为 research sandbox，避免对常规酶改造流程造成复杂度。

参考：

- https://www.nature.com/articles/s41586-023-06415-8

### CLEAN

定位：酶 EC 号/功能预测。

价值：

- 可补 `ActivityRiskModel` 的功能一致性检查。
- 对未表征或多功能酶可做 EC 号候选和功能偏移风险提示。

建议：

- 建立 `enzyme_function_consistency` 子模块：输入序列，输出 EC 候选、置信度、与用户目标功能是否冲突。

参考：

- https://github.com/tttianhao/CLEAN
- https://moleculemaker.org/datasets/enzyme-function-prediction-using-contrastive-learning/

### ESM3 / ESMC

定位：蛋白语言模型和序列表示。

价值：

- 适合做 embedding、突变先验、序列生成候选和远缘同源表征。

限制：

- ESM3-open 是非商业许可；商业用途需评估许可。
- 可优先评估 ESMC 或 API/商业许可路径，不直接把非商业权重用于商业训练。

参考：

- https://www.evolutionaryscale.ai/
- https://github.com/evolutionaryscale/esm

### MMseqs2 / ColabFold MSA

定位：本地同源搜索、聚类、MSA 生成。

价值：

- 直接解除当前 `MSA 0/158` 阻塞。
- MMseqs2 是最务实的本地第一步。

建议：

- 先安装/配置 MMseqs2。
- 建本地 database manifest，记录 UniRef/Swiss-Prot/Pfam 数据库版本、日期、checksum。
- 先对 158 个 target 生成 MSA hit table 和 conservation features，再接入 safe pipeline。

参考：

- https://github.com/soedinglab/MMseqs2
- https://github.com/sokrypton/ColabFold

### ThermoMPNN

定位：蛋白点突变稳定性 ddG 预测。

价值：

- 可作为 `KWB-StabilityPredictor` 的外部 baseline 或 teacher feature。
- MIT license，适合商业研发评估。

建议：

- 本地 adapter 输出 ddG proxy、方向、置信度。
- 不把 ddG proxy 当实验标签，只作为模型特征或候选过滤信号。

参考：

- https://github.com/Kuhlman-Lab/ThermoMPNN

## 推荐落地顺序

### 第一优先级：MSA 解阻

先装 MMseqs2 或配置可信 MSA cache。原因：当前 158 个 MSA job 全部 blocked，没有保守性特征，直接影响 mutation rank 和 stability。

交付物：

- `config/msa_sources.local.json`
- `datasets/curation/msa_hits/*.m8`
- `datasets/curation/msa_conservation_features.jsonl`
- conservation feature validation report

### 第二优先级：Boltz-2 / Chai-1 结构候选评估

Boltz-2 更适合优先评估，因为商业许可更清晰，且覆盖 binding affinity。

交付物：

- `platform_integration/structure_backend_registry.py`
- `scripts/run_structure_backend_benchmark.py`
- Boltz/Chai/ESMFold/上传结构统一 evidence envelope

### 第三优先级：LigandMPNN 候选生成

只有在结构链映射、底物/配体输入和编号门控稳定后接入。

交付物：

- ligand-aware candidate generation adapter
- catalytic residue protection filter
- substrate-contact residue mutation guardrail

### 第四优先级：CLEAN 功能一致性

用于防止推荐突变导致功能偏移，尤其是多功能酶和低注释酶。

交付物：

- EC candidate report
- function-shift risk score
- 与用户目标功能冲突的 hard warning

### 第五优先级：ThermoMPNN 稳定性 baseline

作为外部 baseline 和 teacher feature，不替代自有实验反馈训练。

交付物：

- ddG proxy feature table
- 与现有 25 条 strict labels 的 sanity benchmark
- 与未来 KWB wet-lab 标签的 calibration report

## 对当前平台的具体优化建议

1. 运行面板增加“模型矩阵”展示：
   - Sequence prior: ESM/ESMC/KWB sequence head
   - Structure backend: uploaded PDB / ESMFold / Boltz / Chai
   - Conservation: MMseqs2 MSA
   - Function: CLEAN/DeepFRI-like EC check
   - Design: ProteinMPNN/LigandMPNN
   - KWB decision: five-head ranker

2. 结果层增加 evidence level：
   - sequence-only
   - predicted structure
   - experimental structure
   - MSA-supported
   - wet-lab-supported

3. 底物 fit 不应只用底物名称：
   - 需要 SMILES/InChI/结构文件。
   - 需要 protein-ligand pose 或 Boltz/Chai 预测复合物。
   - 需要口袋 residue contact 和 LigandMPNN 风格 ligand-context features。

4. 生成模型只生成候选，不直接决策：
   - RFdiffusion/ProteinMPNN/LigandMPNN 产生候选。
   - KWB 五头模型排序。
   - GPT-5.6 解释证据和实验计划。

5. 所有外部模型必须有 license gate：
   - AlphaFold 3、ESM3-open 这类非商业许可模型不能默认进入商业生产。
   - Boltz-2、ThermoMPNN、MMseqs2 等 MIT/open-source 工具可优先进入本地评估。

## 当前不建议做

- 不建议训练“科为博大基础模型”从零开始替代 AlphaFold/ESM。
- 不建议把 AlphaFold 3 或 ESM3 非商业输出用于商业模型训练。
- 不建议把文献摘要、模型预测、聊天记录自动当作实验反馈。
- 不建议在没有 chain mapping 和 MSA 的情况下训练对外宣称质量的模型。
