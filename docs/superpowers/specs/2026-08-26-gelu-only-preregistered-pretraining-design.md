# GELU-only 预注册序列预训练实验设计

## 1. 目标与结论边界

下一轮实验只回答一个问题：在其他条件不变时，将当前线性上下文路径 `Conv1d(hidden)` 改为 `GELU(Conv1d(hidden))` 是否能稳定降低 masked-amino-acid NLL，且不导致 masked-token accuracy 不可接受的回退。

实验结论最多只能是 `promote_pretraining_baseline`、`retain_incumbent` 或 `invalid_experiment`。即使候选通过，也仍然是无标签自监督预训练资产，不得推导酶功能、活性、稳定性、亲和力、突变效应或任何生产能力。`safe_for_supervised_training`、`safe_for_model_claim` 和 `release_ready` 始终为 `false`。

## 2. 已知问题与设计选择

现有 residual 候选同时引入了 `hidden + context` 和 GELU，因此无法将 accuracy 小幅增益归因给 skip connection 或非线性。GELU-only 候选不增加参数或 state-dict key，是拆解该混杂实验的最小变更。

现有 1,334 条验证序列已被 epoch、学习率、hidden dimension、kernel 和 residual 扫描反复使用，它将被标记为历史 dev，不再充当独立测试证据。新实验从 12,830 条去重序列重新生成冻结的 train/dev/sealed-test 分割，incumbent 和 candidate 都必须从头训练，不直接沿用 v6 checkpoint。

## 3. 冻结数据分割

1. 输入固定为 `AI大模型/datasets/derived/msa_sequences_deduplicated.fasta`，预期 SHA-256 为 `19fdb1bb614ec4a9ed2397a49f2eb4e2eee197b0c835dde5c6618eaa7efc516e`、记录数为 12,830。builder 必须重算并严格匹配，同时绑定去重脚本 SHA-256 和词表 `ACDEFGHIKLMNPQRSTVWY`。
2. FASTA 每条 header 必须唯一、非空，以 `|` 分隔后必须恰有一个非空 `source=` 字段；缺失、重复或空 source 直接使分割无效，不允许回退到整段 header。序列按大写、删除 `-` 规范化，只允许固定词表；规范化序列重复也使分割无效。record ID 是完整 header 的 SHA-256。
3. source group 是不可拆分单元。对每个 source 计算 `SHA256("20260827:" + source)` 的无符号大端整数并对 100 取模：`0..79=train`、`80..89=dev`、`90..99=sealed-test`。不得根据实际比例或后续指标重排。
4. 必须输出 source membership manifest、sequence membership manifest 和每个分区的 canonical JSONL SHA-256。canonical JSONL 使用 UTF-8、LF、record ID 升序、无多余空白。三个分区要求 exact sequence overlap=0、source overlap=0；每区至少 10 个 sources 且序列非空；train 序列比例必须在 70%..90%，dev/test 各在 5%..20%，否则 `invalid_split`。`invalid_split` 会阻止 preregistration 和训练，在实验级汇总中统一映射为 `invalid_experiment`，不是第四种最终结论。
5. 本轮不声称跨 source 同源隔离，因为本地尚无 MMseqs2/CD-HIT。报告必须显式记录 `homology_cluster_isolation_verified=false`。该限制不使实验无效，但禁止将结果描述为跨同源家族泛化能力。
6. sealed-test 成员可以在分割 manifest 中被绑定，但在 dev 决策通过前不得运行模型评估或生成 test 指标。

## 4. 预注册与不可变实验合同

任何正式训练前，先生成并单独提交 preregistration JSON。先提交全部实现代码并得到 `training_code_commit`；然后在其直接子提交中只加入冻结 manifests/preregistration，该提交是 `preregistration_commit`。preregistration JSON 绑定父提交 `training_code_commit`，不尝试绑定自身未知的 commit ID。训练只能在 clean worktree 的 `preregistration_commit` checkout 上启动，运行 ledger 另行记录实际 `preregistration_commit`。该文件必须绑定：

- 实验 ID、创建时间、`training_code_commit`、输入与分割 manifest SHA-256。
- incumbent 架构：hidden=32、kernel=3、dilation=1、residual=false、context_gelu=false。两 arm 的 canonical resolved-config 必须做 JSON Pointer diff，唯一允许差异是 `/model/context_gelu`。
- candidate 架构：仅 `context_gelu=true`，其他字段与 incumbent 相同。
- epochs=3、learning_rate=5e-4、mask_probability=0.15；AdamW `weight_decay=0.01, betas=(0.9,0.999), eps=1e-8, amsgrad=false`；无 scheduler、无梯度裁剪、每条序列一次 optimizer update。序列不截断，position index 仍在 511 处 clamp。checkpoint 固定为第 3 epoch 最后一次 update，不做 best-checkpoint 选择。
- 五个配对训练 seeds：`20260827..20260831`。同一 seed 的两个 arm 必须使用相同训练顺序与遮盖随机流。
- dev mask-bank seeds 固定为 `3030001..3030005`，sealed-test 为 `4040001..4040005`。对每个 token 计算 `SHA256(bank_seed + ":" + record_id + ":" + zero_based_token_index)`，将 digest 解为无符号大端整数；小于 `floor(0.15 * 2^256)` 时遮盖。全 false 时使用 `SHA256("fallback:" + bank_seed + ":" + record_id)` 对序列长度取模。每个 bank 以 record ID 升序输出 zero-based mask indices 的 canonical JSONL 并绑定 SHA-256，两 arm 共用同一文件。
- 训练序列顺序用 `SHA256("order:" + seed + ":" + epoch + ":" + record_id)` 升序确定；训练 mask 把上述 token digest 前缀替换为 `"train-mask:" + seed + ":" + epoch` 并使用同一阈值/fallback 规则，保证两 arm 逐 update 配对。
- 环境锁必须记录 Python/PyTorch 完整版本、OS/architecture、CPU device、float32、`torch.use_deterministic_algorithms(true)` 和 torch threads=1；两 arm 必须字节级一致。
- 下文第 6 节的指标、方向、阈值、统计方法和失败处理。

预注册后任何冻结字段变化都使当前实验变为 `invalid_experiment`。需要修改时必须创建新实验 ID 和新预注册提交，不得覆盖原记录。

## 5. 模型与兼容性

`build_encoder` 新增显式 `context_gelu: bool = false`。路径语义固定为：

- `residual=false, context_gelu=false`: `context`，完全兼容 v6。
- `residual=false, context_gelu=true`: `GELU(context)`，本轮唯一候选。
- `residual=true`: `GELU(hidden + context)`，保持已有 residual checkpoint 语义；此时 `context_gelu` 必须为 false，否则配置无效并 fail-closed。

新 checkpoint 显式保存 `hidden_dim`、`kernel_size`、`dilation`、`residual` 和 `context_gelu`。旧 checkpoint 对每个缺失字段分别回退：`hidden_dim=32`、`kernel_size=3`、`dilation=1`、`residual=false`、`context_gelu=false`；已存在字段绝不被其他缺失字段覆盖。字段存在但类型非法时不得使用 Python truthiness 猜测，而是拒绝加载。

训练、独立评测、embedding export 和 index builder 必须调用同一配置解析器。评测报告必须写回 resolved config。配置不一致、无法加载或运行中非有限值都使实验无效。

## 6. 评测与决策规则

唯一主指标是 masked-token mean NLL，按所有遮盖 token 的 loss sum / token count 聚合，越低越好。Perplexity 只是 NLL 的单调变换，不参与独立选择。masked-token accuracy 仅是非劣门。

每个 seed 先在五个共享 mask banks 上汇总原始 loss sum、correct count 和 masked-token count。seed NLL = total loss sum / total masked-token count，seed accuracy = total correct / total masked-token count；再计算 candidate-incumbent 配对差 `d_i`。对五个 `d_i` 使用未舍入的 float64 计算 `mean`、样本标准差 `s`（ddof=1）和 `mean ± 2.776*s/sqrt(5)`；零方差时上下界均等于 mean。阈值比较在任何展示舍入前进行。

决策是两级状态机。第一级 validity gate 先检查预注册、hash、配置 diff、5/5 seeds、5/5 banks、原始计数、有限值、资源对称和访问纪律；任一失败只能输出 `invalid_experiment`，不进入效果门。第二级 efficacy/noninferiority gate 只对 valid 实验运行。

dev 阶段只有同时满足以下条件才能进入 sealed-test：

1. mean paired ΔNLL(candidate-incumbent) ≤ -0.005。
2. ΔNLL 95% CI upper < 0。
3. accuracy Δ 的 95% CI lower > -0.001（绝对 accuracy，即 -0.1 个百分点）。
4. 至少 4/5 seeds 的 ΔNLL < 0。

对已通过 validity gate 的实验，任一效果条件不满足即 `retain_incumbent`，不打开 sealed-test。dev 通过后，sealed-test 只允许评估一次，并使用完全相同的四条效果判定规则。sealed-test 任一效果条件失败仍为 `retain_incumbent`，不得回看 dev 更改阈值。这里的“稳定”只限于五个预注册训练 seeds、冻结语料和 mask-bank 协议，不扩展到其他数据集或同源家族。

## 7. 证据链与 fail-closed

必须生成：预注册及其 SHA-256、代码/环境锁、分割 manifests 与重叠审计、mask-bank manifests、两个 arm 的逐 seed 配置/报告/checkpoint SHA-256、逐 seed×bank 原始计数、配对差与 CI、运行异常 ledger、dev decision receipt，以及在 dev 通过时才能出现的 sealed-test access receipt 和 final decision。所有 JSON/JSONL 必须有 JSON Schema 和 validator；validator 要求无未知字段、必填字段齐全并重算所有派生计数/hash。

sealed-test runner 只在 dev receipt 为 `promote_to_sealed_test` 且其 hash 匹配时启动。它必须在读取任何 sealed-test 序列前，使用 exclusive-create 原子生成 attempt receipt；无论成功、中断或异常都立即消耗唯一次尝试，已存在 receipt 时拒绝第二次运行。attempt 状态以 append-only JSONL 记录并绑定到 final decision。该机制只保证受治理 runner 的 fail-closed 语义，不声称能抵抗拥有文件系统写权限的恶意篡改；删除/改写 receipt 会导致后续 hash/manifest 验证失败并强制 `invalid_experiment`。

以下任一情况强制 `invalid_experiment`：缺少或迟到的预注册；输入、代码、分割、mask bank 或冻结配置 hash 不一致；canonical config diff 不是唯一 `/model/context_gelu`；分区交叉；seed/bank 缺失；checkpoint cherry-pick；指标、方向、阈值或聚合方式事后变更；非有限值；两 arm 资源或训练预算不对称；dev 决策前访问 sealed-test 指标；或尝试将 MLM 结果升级为下游生物能力/生产声明。

官方 run 不允许重试或从中间 checkpoint 恢复；OOM、进程中断、硬件或文件系统故障都使当前实验 `invalid_experiment`。如需重跑，必须建立新实验 ID、新 preregistration，并重跑两 arm 的全部五个 seeds；原失败 ledger 保留不删除。

## 8. 测试与执行顺序

1. 先对分割、配置解析、GELU-only 数学路径、训练/评测/index/export 配置接线、mask bank 确定性、原始计数聚合、CI 和决策门编写失败测试。
2. 实现后固定运行 `PYTHONPATH=AI大模型/scripts python3 -m unittest discover -s AI大模型/tests -q`、`python3 -m py_compile AI大模型/scripts/*.py` 和 `git diff --check`。
3. 生成并提交分割/mask-bank manifests 和 preregistration；提交时不得存在本轮训练或 dev/test 指标产物。
4. 按 seed 成对训练 incumbent/candidate，不交叉择优，不删除失败运行证据。
5. 只评估 dev 并运行机器决策门。未通过则终止；通过才生成一次性 sealed-test access receipt 并评估 sealed-test。
6. 最终仅在全部证据完整且门槛通过时更新当前 pretraining baseline manifest；所有发布与能力声明门仍保持关闭。
