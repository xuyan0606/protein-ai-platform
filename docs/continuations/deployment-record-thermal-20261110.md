# 热稳定性候选偏向修复上线记录（2026-11-10）

## 版本

- Git 提交：`16ac244b11d8b321ec72d2db0e856ea34ae724f8`
- 发布目录：`/opt/protein-ai-platform/releases/20261110-thermal-candidate-bias-16ac244b1/protein-ai-platform`
- 原生产版本：`20261107-chat-timeout-197bf67c1` / `197bf67c137b4059c88455f81b7e4956e1ef1e8d`
- 数据库：未迁移、未恢复；运行时 Alembic 仍为 `20260917_0004`

## 发布前验证

- 修复相关回归：`292 passed in 5.28s`
- 修复文件服务器哈希与提交一致：
  - `backend/app/services/thermal_structure_hypotheses.py` `69f2fdc2048f8278bd650f883af1e60691195c95fafb760a6ee7954c17122fcb`
  - `backend/app/services/thermostability_workflow.py` `128b489938c59bcb66dbd60138a63f9f574409f96be6f52b7c7dd34effb9c971`
  - `backend/app/tools/thermostability_workflow.py` `fecf46322582aeeb6de0548dfe520f3d196f8594b1b543ce4aeb08582056dbed`
  - `backend/app/services/thermostability_report.py` `27cb5666c823a7fb319303f17c2679bf260b2dd3a63dc7a1f93ea78c6230bd2d`
- 数据库备份演练：自定义格式备份 `123983410` 字节，SHA-256 `4bd0e32617745417ea3d69395a079502a7d9178201b9d93a7a1a43d53d609c5a`；隔离网络恢复通过，51 张公共表，未恢复生产库。

## 上线后验证

- backend、worker、md-worker、frontend、ligand-worker、nginx、chromadb、outline：全部 `running/healthy`，重启计数均为 `0`。
- 旧应用容器保留为 `docker-*-pre-20261109T233648Z`，可执行应用级回退；数据库和持久卷未回退。
- 临时线上会话使用实际 486 残基 PDB，结构特征行 `486`，DDGun 评分候选 `60`，最终独立位置 `12`。
- 自动替换类型上限为 `ceil(12/3)=4`：A→V `4`、M→L `4`、I→L `1`、L→I `3`。A→V 几何排除 `11` 个；负 DDGun 候选 `2` 个未用于多样性补位；短缺 `0`。
- 线上回执仍标记 `research_only_exploration`、`candidate_output_allowed=false`，没有把候选升级为可直接实验集合，也没有声明增稳效果。
- 登录、PDB 上传归属、计划确认、实际工具执行、会话刷新和原始数据保护检查通过。清理结果：2 个临时账号禁用、1 个临时会话删除、1 个上传删除、1 个测试任务取消；原有消息、输入和 BLAST 记录哈希保持不变，旧令牌已失效。

验收脚本中的报告文字断言曾因单位/HTML 转义差异中断；结构化工具回执已经完整落盘并通过上述字段核验，该断言差异不影响发布结果，后续应修正脚本断言为结构化字段检查。
