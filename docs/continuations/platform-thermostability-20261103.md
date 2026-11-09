# 热稳定性候选流程修复交付（2026-11-03）

> 后续结果：20261103 已整合并发布真实模型与应用，详见[发布验收记录](platform-thermostability-deployment-20261103.md)。下文为当时的历史检查/交付状态，其中“未部署”“尚未执行”不代表当前状态。

本轮完成本地代码实现、线上源码差异整合和回归验证。**未推送、部署、重启服务或执行数据库迁移。** `20261103` 保留点及原方案文件不改动。

- 工作树：`/Users/keweibo/output/platform-thermostability-20261103`
- 分支：`platform/thermostability-evidence-20261103`
- 已测源码提交：`27958449d1990f9d568cae6e07af356a3f0545fc`
- [机器可读验证记录](platform-thermostability-20261103.json)
- [完整使用说明](../manuals/thermostability-candidate-workflow.md)
- [真实模型服务协议与运行条件](../manuals/thermostability-adapters.md)

## 实际完成

恢复实际运行后端 `20261030-identity-evidence-tier-b728d4ca` 的身份分层、链/模型范围、作者编号、结构证据与报告修复；与候选的上下文隔离、上传策略、blocked 终态和报告治理合并，并保留双方测试。修复合并过程中发现的重复方法覆盖、附件正文误删、附件换序误判任务和模型私有路由泄露。主工作区未提交改动未被覆盖。

新增 `thermostability_candidate_workflow`，接入工具注册、热稳定性 YAML、通用异步 worker、聊天和报告导出。主流程核验测定终点/活性保留、同序列身份与目标授权、WT/成熟肽边界、链和结构编号，再对显式替换、限定位置扫描、同序列来源及本地已知正 ΔTm 记录取并集，保留保护过滤和缺失证据。不再把 MD、结构预测和全部工具接通作为强制前提。

催化/必需功能位置、金属配位几何与现有二硫键按首轮保守规则保护；配体和邻链接触进入人工审查，不能由缺失配体或装配信息推断安全。预测结构的 B-factor 按来源解释 pLDDT，低置信位置只标风险。映射拒绝小数截断、冲突、缺口、WT不符及未确认编号。

ESM 标签改为实际的 WT-marginal；缺候选不再随机抽20个。本地稳定性查询披露真实覆盖、命中/未命中、返回数/可用数/截断、序列哈希、来源和文献，ΔΔG约定缺失时只统计原始正负。组合检查缺距离或单点反馈至少 watch，拒绝互斥替换，始终说明组合收益未验证。

DDGun、ColabFold、EVcouplings 有独立严格 HTTP 适配器，校验输入/输出哈希、版本、候选覆盖、有限数值和原始证据。DDGun保留预测 unfolding ΔΔG 和方向，ESM保留进化偏好；两者不未经校准相加。完整向量可描述 Pareto 取舍，不能充当实验成功率。ColabFold仅缺结构时启用，公共MSA需明确授权；EVcouplings质量不足跳过。离线/禁止工具约束继续作用于复合工具内部。

## 验证结果

- 冻结源码后端全量：**1763 passed，0 failed**，170.54秒；仅passlib依赖的crypt弃用告警。
- 前端 lint、生产 build：通过；上传策略测试：**4/4通过**。
- 覆盖确定性并集、来源哈希、WT/作者编号/插入码、功能保护、pLDDT一致性、假分数拒绝、可选分支失败、离线限制、报告与API、worker部分注册表恢复，以及双方历史回归。
- 全量日志在本工作树忽略目录 `output/thermostability-validation-20261103/backend-full.log`；SHA-256见JSON。

合同测试使用受控返回与HTTP mock；没有把这些结果写成真实模型或企业目标酶的科学验收。

## 运行和发布边界

当前具备有结构/无结构的受控候选编排、证据报告和单点实验交付接口。没有目标序列/测定条件/真实身份材料时仍返回明确缺口。缺少权重、数据库或服务时分支blocked；这不是安装失败后用代理分数替代。

**本轮未提供或部署真实 DDGun/ColabFold/EVcouplings 服务。** 适配器协议需要由锁定版本的算法服务落实，完成真实输入smoke并保存日志后才能声明模型可用。未提供GPU/GROMACS节点的长MD仍未运行。尚未完成目标家族性能验证、实验命中率比较或酶活/热稳定性实验。

使用已有wetlab_result_ingest记录同条件WT和单点反馈，审查后再设计组合。最终价值按相同实验预算下“耐热改善且活性保留”的命中率与人工/简单共识基线比较；不能以API返回率、工具数量或报告完整度替代。

线上版本指针、正式清单、数据库兼容性、HTTPS和生产回滚目标仍需发布前验收。本次不更新 current-production.json、不出正式部署放行记录。

## 回退保留

`snapshot/platform-20261103-local^{commit}` 仍为 `7015ffda4023619eaf6a2c82565dc0dfb5a76c9e`，`snapshot/platform-20261103-record^{commit}` 仍为 `6410c9f13253d08e36c908c921d79798fed87a87`。标签为annotated tag，tag对象哈希与commit哈希不同属正常情况。

本机恢复入口：`/Users/keweibo/output/platform-version-20261103/回退说明_20261103.md`。实际运行镜像和快照保留服务器 `/opt/protein-ai-platform/snapshots/20261103/`，没有执行回退或恢复数据库。
