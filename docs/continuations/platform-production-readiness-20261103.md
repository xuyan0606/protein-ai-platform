# 20261103 生产现状与可逆应用发布准备

> 后续结果：20261103 已整合并发布真实模型与应用，详见[发布验收记录](platform-thermostability-deployment-20261103.md)。下文为当时的历史检查/交付状态，其中“未部署”“尚未执行”不代表当前状态。

本轮只读生产审计完成，没有停止、重启、发布或恢复生产服务；新增脚本的生产操作模式尚未执行。候选仍在补模型服务，应在最终提交和测试完成后绑定最终源码哈希。机器记录见同名 JSON。

## 可采用的部署方式

使用独立新 release 路径，应用容器基于 20261103 的冻结镜像保留可写层中已有工具与运行依赖，再只读挂载新 `backend/app`、`backend/alembic` 和已构建 `frontend/dist`。保留当前容器环境、启动命令、健康检查、卷、密钥挂载及网络别名。不调用旧 installer，不使用或改写 `current`。

`scripts/prepare_thermostability_release.py` 已实现独立模式：生成只读准备记录；新数据库备份与隔离恢复演练；私有容器创建请求准备；保留原容器的逐服务切换；应用回退。只有显式选择相应参数才执行操作，默认生成记录不会调用 Docker。

## 实际运行与数据库

八容器均 running/healthy，重启数均 0，容器 ID 与快照相同。实际后端是 `20261030T034747Z-identity-evidence-tier`；前端与 nginx 的 Compose 入口来自 `20261021T003826Z-3e8bc016-adaptive-export`；`current` 仍指向另一条陈旧路径。因此不能从 current 复制配置后重建全部服务。

数据库只读事务读取到迁移号 `20260917_0004`、51 表、505 列、123 约束。候选与运行容器的 31 个模型/迁移/数据库入口源码逐文件 SHA-256 一致；所有 ORM 表、列均存在。只读 Alembic metadata 比较发现既有差异：2 个可空性差异、1 个额外列，没有候选引入的模式变化。**可以采用仅代码部署；不得执行 `alembic upgrade` 或 `stamp`。** 启动仍沿用原 `create_all` 行为，现有模型表均已存在，不应创建新表。本次不借发布修复历史迁移图漂移。

## 可执行路径（由主执行者审核后运行）

以下命令均在服务器的新 release 项目目录运行，替换路径中的 `<release>`；目录必须独立、不可复用已有备份/准备目录。脚本不输出连接凭据；私有请求包含现有环境和密钥引用，只存权限 0700/0600 的受限目录，不进 Git。后端容器没有 PostgreSQL CLI，服务器已有本地 `postgres:16` 镜像可作客户端，无需拉镜像。

1. 最终源码/前端构建完整，并检查既有任务结束或已妥善处置后，新备份并隔离恢复。此模式用当前后端 `DATABASE_URL` 的临时受限配置做只读 pg_dump；恢复目标是 `--network none`、无公网端口的独立临时 PostgreSQL 容器。恢复后比较表数及迁移号，清理临时容器及其匿名卷，保留 dump、SHA-256 和回执。既有备份脚本默认本地 Compose postgres，与线上 RDS 连接方式不同，不直接套用。

   ```sh
   python3 scripts/prepare_thermostability_release.py \
     --backup-drill /opt/protein-ai-platform/backups/<release>-fresh \
     --postgres-client-image sha256:80f4c7a5e91618546dce5b4fe60cf03b14c0f9efa7e40157278d122772ced8d2
   ```

2. 准备五个应用服务的私有创建请求。脚本要求线上 ID 与保留快照相同，并使用快照冻结镜像 ID，保留已有运行工具；原始镜像 ID 本身不能覆盖容器可写层。新源码目录须完整并可供现有运行 UID 读取。若最终新增运行配置，如 DDGun URL，应先明确审查并扩展准备逻辑，不能静默修改原环境后仍声称“仅源码挂载”。

   ```sh
   python3 scripts/prepare_thermostability_release.py \
     --prepare-runtime /opt/protein-ai-platform/increments/<release>-runtime \
     --release-path /opt/protein-ai-platform/releases/<release>/protein-ai-platform
   ```

3. 检查私有请求只新增指定源码挂载，确认最终适配器与运行依赖已处理后切换。脚本要求六小时内成功备份和隔离恢复回执、dump 哈希一致、原容器 ID 未变。逐个 stop/rename 原容器并创建同名新容器，保留原容器用于回退；每个替换达到 healthy 才继续。后端和前端 IP 变化后执行原 nginx 容器内的 `nginx -t` 与 reload，保持其容器、配置及端口，因为静态 upstream 解析需要刷新。失败自动回退已涉及的应用容器。

   ```sh
   python3 scripts/prepare_thermostability_release.py \
     --switch-runtime /opt/protein-ai-platform/increments/<release>-runtime \
     --backup-evidence /opt/protein-ai-platform/backups/<release>-fresh/BACKUP-DRILL.json
   ```

4. 进入健康后的功能验收：登录与原会话、上传、原任务/报告/下载、独立用户隔离、前端静态资源哈希、新热稳定性流程真实 DDGun 结果及不可用适配器状态。容器 healthy 不等于完整业务验收；脚本回执明确为 `healthy_pending_functional_acceptance`。失败时应用回退命令如下，保留当前数据库与全部持久卷，不恢复旧 dump。

   ```sh
   python3 scripts/prepare_thermostability_release.py \
     --rollback-runtime /opt/protein-ai-platform/increments/<release>-runtime
   ```

新备份/恢复模式尚未在服务器执行；当前只验证脚本语法与 5 个独立安全用例，包括可变客户端镜像拒绝、私有文件不覆盖、陈旧回执拒绝、回退时原容器名称漂移拒绝及迁移图完整性。发布前主执行者应审阅脚本并运行真实备份/隔离恢复证据。

## TLS 与镜像来源的明确例外

现有 nginx `server_name _`，HTTPS 仅映射 4243，443 未监听。证书 subject/issuer 均 `CN=120.27.108.138`，SAN 只有该 IP，自签；有效期 2026-10-10 至 2027-10-10，SHA-256 指纹 `b3f40c1f88038963da45e377a75fe15d8ad35c5e614e56ef8ee7dd876bdabbd7`。从本机公网带 SNI 检查返回 curl 60 / verify 18；正式信任链验收失败。检查 `/etc/letsencrypt`、`/etc/nginx` 及 shared TLS 库存，仅发现上述证书，没有查到可直接使用的正式域名证书。不能凭空补出域名或公开受信证书。

用户已授权继续上线，主执行者可在明确记录“沿用既有入口、正式 TLS 尚未完成”的条件下继续应用切换；不能把这称为正式 HTTPS 验收通过。正式域名和可信链仍需真实域名控制与相应证书配置。

五个应用服务没有仓库 RepoDigest。冻结镜像 ID 和本地 Docker/OCI config/manifest 哈希可作本地可复现来源证据，**不等于仓库发布摘要**。现有 `RELEASE-MANIFEST.json` 校验器要求仓库 digest，不能伪造 `repo@sha256` 通过它。本次如果采用本地冻结镜像与源码挂载，单独记录镜像 ID、真实 manifest/config 哈希、源码逐文件哈希、配置哈希和切换回执，并把正式 registry provenance 作为制度例外如实记载。

## 保留与回退边界

不得覆盖 `/opt/protein-ai-platform/snapshots/20261103`。切换不会运行 Compose down，不替换 nginx/Chroma/Outline 容器，不修改它们的卷。原应用容器保留且不删除；失败现场容器重命名保留。数据库只做备份，生产库不恢复、不迁移、不 stamp。恢复演练是独立本机 PostgreSQL 验证，不能冒称异地容灾或 OSS/上传卷完整恢复演练。
