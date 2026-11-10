# 热稳定性报告格式修复与发布验收（2026-11-10）

实际运行源码为 `81bd6622b162b42130efa7a4dda60803c2e61b07`，发布目录为 `/opt/protein-ai-platform/releases/20261110-thermal-report-81bd6622b/protein-ai-platform`，上一版本为 `16ac244b1`。本轮报告修复增加稳定目标摘要，保留此前候选分布限制与A→V几何排查。前端代码未改，静态资源沿用已接受版本。

## 报告与真实执行

线上真实登录、486残基PDB副本上传及归属校验后，确认签名策略并执行实际工具。报告精确包含“热处理条件：95℃，5 min；残余酶活：30% → 目标：≥60%。”，流式文本与保存的最终消息相同，共19575 UTF-8字节。会话令牌、Cookie、刷新及完整AI结构摘要验收通过。

旧脚本首先因要求标题“热稳定性候选流程”而中断；实际为“热稳定性探索分析”。随后审查发现其还要求正文出现内部字段`min_activity_retention_pct`，该缺项保存在结构化`evidence_gaps`中。修订验收分别检查精确目标摘要、结构化字段和流式持久化一致性，保留原失败记录，没有删除数值或单位校验，也没有重新提交科学任务。

- 结构特征：486行，未使用预览替代完整筛选。
- DDGun实际60条评分，执行返回码0；ESM-2 650M实际60条评分。
- 最终12个独立位置；每类替换最多4个，A→V4、M→L4、L→I3、I→L1，短缺0。
- 11个A→V因严重几何重叠被排除，2个负DDGun候选未用于多样性补位；独立核对候选列表与审计分布一致。
- 最终聊天状态仍为`blocked`；工作流为`partial`、`research_only_exploration`，`candidate_output_allowed=false`，正式候选和实验集合为空。身份未确认、保护位点及测定信息缺失仍限制正式输出。探索评分不证明热稳定性、残余酶活或实验收益。

## 运行与数据保护

本轮重新运行相关回归16项通过。只读核验八服务均running/healthy、重启0；四后端服务各264源码文件与Git清单完全一致；11个前端静态文件经发布目录、容器和实际HTTP三方哈希核对一致。健康、登录及聊天路由HTTP200。五个替换服务的环境、启动参数、健康配置、网络及持久挂载均保持，原容器实际存在且停止。

备份123984552字节，SHA-256 `637193ea25744051edf2de0ddcd7dc8f4106c2c72193be09588a2087031714c9`，断网隔离恢复51张表、Alembic `20260917_0004`。生产库未恢复、未迁移。两临时账号禁用、一临时会话和一上传删除、一测试BLAST任务取消；原消息/输入/BLAST保持，旧Bearer已拒绝。20261103快照校验和保持。

## 版本与回退

权威记录为服务器`/opt/protein-ai-platform/production-version.json`及本地`docs/baselines/current-production.json`。逐文件清单为`production-source-manifest-20261110-report.json`，725个非可变归档文件参与本地校验；历史清单保留。源码分支`release/production-20261110-report`和固定标签`production/20261110-81bd6622b`记录本轮源码与发布元数据，旧标签和旧生产分支不移动。元数据提交与应用源码提交81bd6622b分别记录。

应用级回退入口（未执行回退演练）：

```sh
python3.11 /opt/protein-ai-platform/releases/20261110-thermal-report-81bd6622b/protein-ai-platform/scripts/prepare_thermostability_release.py --rollback-runtime /opt/protein-ai-platform/candidates/thermal-report-81bd6622b-runtime-private-2
```

回退保留最新数据库和上传，仅恢复本轮切换前应用容器。`current`指针仍陈旧，不能据此重建。OSS凭据、可信TLS和registry摘要既有例外仍保留。本轮未重新执行真实浏览器检查，不把历史浏览器/全量测试数量当成本轮结果。

证据目录：`/Users/keweibo/output/thermal-report-81bd6622b-verification/`。包括原始计划/执行SSE、保存会话、报告、结构化回执、清理、备份恢复、版本记录及只读运行核验。原始证据含用户输入，仅本地/服务器私有保存，不提交源码远端。
