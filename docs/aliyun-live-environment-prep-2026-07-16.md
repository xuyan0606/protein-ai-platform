# 酶蛋白 AI 平台阿里云上线环境准备清单

日期：2026-07-16  
目标：先完成上线前调研、环境准备和风险收敛，暂不修改生产数据。  
安全约束：本文档不保存明文密码、AccessKey Secret、数据库密码或 Redis 密码。

## 1. 当前资源信息

### ECS 应用服务器

| 项 | 内容 |
|---|---|
| 实例 ID | `i-m5e2p0s13lqjgv359n5n` |
| 地域 | `cn-qingdao` |
| 公网 IP | `120.27.108.138` |
| 私网 IP | `172.22.106.198` |
| 主机名 | `iZm5e2p0s13lqjgv359n5nZ` |
| 用途 | 酶蛋白 AI 平台应用节点 |

### RDS PostgreSQL

| 项 | 内容 |
|---|---|
| 实例 ID | `pgm-bp14shfmqveu8o4h` |
| 地域 | `cn-hangzhou` |
| 端口 | `5432` |
| 当前提供地址 | `pgm-bp14shfmqveu8o4h.pg.rds.aliyuncs.com` |
| 用途 | 平台业务库、Outline 数据库 |

待确认：

1. 是否已创建应用专用数据库账号，例如 `protein_ai`。
2. 是否已创建数据库：`protein_ai`、`outline`、`outline_test`。
3. 是否允许青岛 ECS 公网 IP 访问，或是否已配置跨地域 VPC/CEN 内网互通。

### Redis

| 项 | 内容 |
|---|---|
| 实例 ID | `r-bp1pbb3itre15i8nm5` |
| 地域 | `cn-hangzhou` |
| 用户 | 已提供，部署时写入 ECS 本机 `.env` |
| 用途 | Celery broker、任务状态、缓存、Outline Redis |

待确认：

1. Redis 连接地址和端口。
2. 是否启用用户名认证格式。
3. 是否允许青岛 ECS 访问，或是否已有跨地域内网互通。

### OSS

| 项 | 内容 |
|---|---|
| Bucket | `crvab` |
| 当前控制台地域线索 | `oss-cn-beijing` |
| 用途 | 平台文件、分析结果、报告、附件、备份 |

待确认：

1. Bucket 实际地域是否为 `cn-beijing`。
2. ECS 在青岛，若访问北京 OSS 应使用公网 endpoint 或确认内网 endpoint 是否可用。
3. 是否使用 RAM Role，还是使用 AccessKey ID / AccessKey Secret。
4. 是否单 bucket 存储平台文件和 Outline 附件，还是拆分 `crvab` / `crvab-outline`。

## 2. 关键拓扑风险

当前资源跨地域：

| 资源 | 地域 |
|---|---|
| ECS | 青岛 `cn-qingdao` |
| RDS | 杭州 `cn-hangzhou` |
| Redis | 杭州 `cn-hangzhou` |
| OSS | 北京 `oss-cn-beijing` 线索 |

风险：

1. ECS 不能默认通过内网访问杭州 RDS/Redis。
2. 如果走公网访问 RDS/Redis，需要配置白名单和安全策略。
3. 跨地域访问会增加延迟，后续生产建议统一地域或配置专线/CEN。
4. OSS endpoint 要按 bucket 地域配置；错误地域会导致上传失败或签名错误。

建议：

1. 试运行阶段可以先走公网白名单，但仅放行 ECS 公网 IP `120.27.108.138`。
2. 正式生产阶段建议统一资源地域，或开通阿里云 CEN/VPC 对等互通。
3. 账号权限采用最小权限原则，禁止直接使用主账号 AccessKey。

## 3. 上线前必须确认项

### 账号与权限

- [ ] ECS root 密码上线前改为强密码。
- [ ] 配置 SSH Key 登录。
- [ ] 禁止长期使用弱 root 密码。
- [ ] 创建非 root 部署用户，例如 `proteinai`。
- [ ] RDS 创建平台专用账号，不使用高权限管理账号跑业务。
- [ ] Redis 确认业务访问账号和密码。
- [ ] OSS 使用 RAM 子账号或 ECS RAM Role。

### 网络与安全组

- [ ] ECS 安全组开放 22，仅限管理员 IP。
- [ ] ECS 安全组开放 80/443，供用户访问。
- [ ] 当前 app compose 默认映射 `4200/4280/4243`；若临时使用这些端口，需要在安全组放行。
- [ ] 若要标准 `80/443`，启动前设置 `APP_HTTP_PORT=80`、`APP_HTTPS_PORT=443` 或在外层 SLB/Nginx 做转发。
- [ ] RDS 白名单放行 ECS 公网 IP 或 VPC 网段。
- [ ] Redis 白名单放行 ECS 公网 IP 或 VPC 网段。
- [ ] OSS Bucket 权限保持私有。

### 数据库

- [ ] 创建数据库 `protein_ai`。
- [ ] 创建数据库 `outline`。
- [ ] 创建数据库 `outline_test`。
- [ ] 确认 RDS 连接串支持 asyncpg。
- [ ] 执行 Alembic migration 前先做空库确认。

### 运行环境

- [ ] ECS 安装 Docker。
- [ ] ECS 安装 Docker Compose plugin。
- [ ] ECS 安装 Git、curl、make、tar、rsync。
- [ ] 磁盘空间不少于 40GB 可用。
- [ ] `/opt/protein-ai-platform` 作为部署目录。
- [ ] `/opt/protein-ai-platform/deploy_data` 挂载真实数据目录。

### 应用配置

- [ ] `PUBLIC_BASE_URL` 确定：先用 IP，正式用域名。
- [ ] `SECRET_KEY`、`OIDC_CLIENT_SECRET`、`OUTLINE_SECRET_KEY`、`OUTLINE_UTILS_SECRET` 使用随机强密钥。
- [ ] `/opt/protein-ai-platform/shared/secrets/oidc_private_key.pem` 与 `oidc_public_key.pem` 已生成，并通过 compose secrets 挂载到后端。
- [ ] LLM API Key 填入 ECS 本机 `.env`，不提交仓库。
- [ ] RDS、Redis、OSS 凭据只写入 ECS 本机 `.env.aliyun.app`。

## 4. 本机准备动作

优先在本机完成：

1. 运行发布 readiness。
2. 运行部署包 dry-run。
3. 生成不含密钥的 env 模板。
4. 验证阿里云 compose config 不打印 secret。
5. 打包源码部署包。
6. 准备上传到 ECS。

推荐命令：

```bash
python3 scripts/check_upgrade_readiness.py
python3 scripts/package_deploy_bundle.py --dry-run
python3 scripts/init_deployment.py --profile aliyun-app --public-base-url http://120.27.108.138:4200 --dry-run
cd docker && docker compose --env-file .env --env-file .env.deploy-data --env-file .env.aliyun.app -f docker-compose.aliyun-app.yml config --quiet
```

## 5. ECS 远端准备动作

登录 ECS 后建议执行：

```bash
hostname
cat /etc/os-release
uname -a
df -h
free -h
docker --version
docker compose version
curl -fsS http://127.0.0.1 || true
```

如 Docker 未安装，按系统发行版安装 Docker Engine 和 Compose plugin。

### Workbench 可复制执行方式

当前 ECS 终端 SSH 未开放密码认证，推荐先通过阿里云 Workbench 执行远端预检。

本机复制脚本到剪贴板：

```bash
pbcopy < scripts/ecs_app_preflight.sh
```

进入 Workbench 后粘贴为远端脚本：

```bash
cat > /tmp/ecs_app_preflight.sh <<'EOF'
# 在这里粘贴 scripts/ecs_app_preflight.sh 的完整内容
EOF
bash /tmp/ecs_app_preflight.sh 2>&1 | tee /tmp/protein-ai-ecs-preflight.log
```

需要准备 Docker 时，同样复制准备脚本：

```bash
pbcopy < scripts/ecs_app_prepare.sh
```

Workbench 中粘贴：

```bash
cat > /tmp/ecs_app_prepare.sh <<'EOF'
# 在这里粘贴 scripts/ecs_app_prepare.sh 的完整内容
EOF
bash /tmp/ecs_app_prepare.sh 2>&1 | tee /tmp/protein-ai-ecs-prepare.log
```

脚本用途：

- `scripts/ecs_app_preflight.sh`：只读检查，不修改服务器。
- `scripts/ecs_app_prepare.sh`：安装基础工具和 Docker、创建部署目录，不启动应用。

建议顺序：

```bash
# 1. 先只读预检
bash /tmp/ecs_app_preflight.sh 2>&1 | tee /tmp/protein-ai-ecs-preflight.log

# 2. 如果 Docker 缺失，再执行准备脚本
bash /tmp/ecs_app_prepare.sh 2>&1 | tee /tmp/protein-ai-ecs-prepare.log

# 3. 准备后再跑一次只读预检
bash /tmp/ecs_app_preflight.sh 2>&1 | tee /tmp/protein-ai-ecs-preflight-after-prepare.log
```

把 `/tmp/protein-ai-ecs-preflight.log` 和 `/tmp/protein-ai-ecs-prepare.log` 的输出发回后，再决定是否上传部署包和启动应用。

## 6. 首次部署建议流程

1. 创建目录：`/opt/protein-ai-platform`。
2. 上传部署包和 checksum。
3. 解压到版本目录，例如 `/opt/protein-ai-platform/releases/<timestamp>`。
4. 部署包内固定包含顶层 `protein-ai-platform/`，因此 `/opt/protein-ai-platform/current` 必须指向 `/opt/protein-ai-platform/releases/<timestamp>/protein-ai-platform`。
5. 在 `current/docker` 下创建 `.env`、`.env.deploy-data`、`.env.aliyun.app`。
6. 执行 compose config 校验。
7. 启动服务。
8. 检查 `/api/health`。
9. 执行数据库 migration。
10. 创建管理员账号或确认现有账号迁移。
11. 执行登录、PDB、数据页、报告导出、文件上传下载 smoke。

推荐使用安装脚本，避免把 `current` 指到 release 父目录：

```bash
DEPLOY_ROOT=/opt/protein-ai-platform \
  /opt/protein-ai-platform/current/scripts/install_release_bundle.sh \
  /opt/protein-ai-platform/incoming/protein-ai-platform-<release>.tar.gz
```

## 7. 当前阻塞项

| 阻塞项 | 说明 |
|---|---|
| ECS SSH 登录方式 | 已通过 Workbench 安装部署公钥，本机可使用 `/Users/xuyan/.ssh/protein_ai_aliyun_ed25519` 登录 root；密码登录仍关闭 |
| RDS 应用账号/密码 | 当前只看到实例和连接地址，缺业务账号密码 |
| RDS 数据库名 | 需要确认是否已创建 `protein_ai`、`outline`、`outline_test` |
| RDS 网络地址 | 当前 `pgm-bp14shfmqveu8o4h.pg.rds.aliyuncs.com` 解析到 `172.31.12.83` 内网地址，从本机和 ECS 访问 5432 均超时；ECS 在青岛，需确认跨地域 VPC/CEN 互通或申请公网连接地址并配置白名单 |
| Redis endpoint | 当前缺正式连接地址 |
| OSS AccessKey 或 RAM Role | 当前只有 bucket 名，缺访问凭据或角色策略 |
| OSS endpoint | `oss-cn-beijing.aliyuncs.com:443` 公网可达，`oss-cn-beijing-internal.aliyuncs.com:443` 从本机不可达；跨地域 ECS 建议先使用公网 endpoint，或确认内网链路 |
| 域名与证书 | 当前可先用 IP+端口，正式上线需域名和 HTTPS |
| 跨地域网络 | ECS 青岛，RDS/Redis 杭州，OSS 北京，需要白名单或网络互通策略 |

## 9. 2026-07-16 ECS 准备结果

已完成：

1. 通过 Workbench 安装部署 SSH 公钥，本机现在可直接 SSH 到 ECS。
2. ECS 系统确认为 Alibaba Cloud Linux 3.2104 U13.2。
3. 安装基础工具：`git`、`rsync`、`nc`、`make`。
4. Docker 官方源下载失败后，已切换为阿里云 Docker CE 镜像源。
5. 安装 Docker Engine `26.1.3` 和 Docker Compose plugin `v2.27.0`。
6. Docker 服务已启动并设置开机自启。
7. 创建部署用户 `proteinai`。
8. 创建部署目录：
   - `/opt/protein-ai-platform/incoming`
   - `/opt/protein-ai-platform/releases`
   - `/opt/protein-ai-platform/current`
   - `/opt/protein-ai-platform/shared`
   - `/opt/protein-ai-platform/backups`
   - `/opt/protein-ai-platform/deploy_data`
9. 上传并校验源码部署包：
   - `protein-ai-platform-20260716T025349Z-25679eb.tar.gz`
   - sha256 `8c7551c3e26c74d1713146a3d1fe2d81a67a53c08d2bb6bf6240af0c583c603d`
10. 早期包解压到 `/opt/protein-ai-platform/releases/20260716T025349Z-25679eb`；后续已统一要求 `current` 指向包内 `protein-ai-platform` 子目录。
11. 创建 ECS 上的占位 env 文件，并通过阿里云 app compose config 校验。
12. 新增 4G `/swapfile` 并写入 `/etc/fstab`，降低 1.8GiB 小内存实例在 Docker 构建/启动时 OOM 的风险。

当前 ECS 状态：

| 项 | 状态 |
|---|---|
| Docker | ready，`26.1.3` |
| Docker Compose | ready，`v2.27.0` |
| 磁盘 | `/` 197G，总可用约 184G |
| 内存 | 1.8GiB + 4G swap，总体仍偏小，构建镜像和运行多服务时需观察 |
| 本地防火墙 | firewalld inactive，iptables 默认 INPUT ACCEPT |
| 容器 | 尚未启动任何容器 |
| RDS 5432 | 从 ECS 访问超时 |
| OSS 443 | 从 ECS 访问成功 |

启动前仍需补齐：

1. RDS 网络可达性。
2. RDS 应用账号/密码和数据库。
3. Redis endpoint、认证和白名单。
4. OSS AccessKey/RAM Role。
5. ECS 安全组按实际端口放行：默认 `4200/4280/4243`，或显式改为 `80/443`。
6. 真实 `deploy_data` 是否上传，当前本机约 1.7G。

## 10. 2026-07-16 镜像构建与启动前 smoke

已完成：

1. 当前 release 已更新为 `/opt/protein-ai-platform/releases/20260716T060541Z-25679eb/protein-ai-platform`。
2. `protein-ai-frontend:aliyun` 构建完成。
3. `protein-ai-backend:aliyun` 构建完成，镜像约 `1.18GB`。
4. backend 镜像内 `gmx --version` 可执行，GROMACS 版本为 `2025.2-Debian_2025.2_1`。
5. backend 镜像内 `foldseek version` 可执行。
6. OIDC signing key 改为 runtime secret 挂载：
   - `/opt/protein-ai-platform/shared/secrets/oidc_private_key.pem`
   - `/opt/protein-ai-platform/shared/secrets/oidc_public_key.pem`
7. `.dockerignore` 已排除 OIDC key，私钥不进入镜像。
8. `docker compose ... run --rm --no-deps backend python -c "import app.main"` 已通过。
9. 当前可复现部署包为 `protein-ai-platform-20260716T060541Z-25679eb.tar.gz`，sha256 `3c029bf4a17f4606152a0f0c9a2669eb9ec7426c0afa96a6d809a1bd8de010fe`。

仍未执行：

1. 未执行 `docker compose up`。
2. 未执行数据库 migration。
3. 未创建管理员账号。
4. 未做浏览器登录 smoke。

原因：RDS/Redis/OSS 真实网络和凭据仍未闭环，提前启动会得到不可用服务或反复重启容器。

## 11. 2026-07-16 继续准备结果

已完成：

1. 当前 release 已更新为 `/opt/protein-ai-platform/releases/20260716T062302Z-25679eb/protein-ai-platform`。
2. 当前可复现部署包为 `protein-ai-platform-20260716T062302Z-25679eb.tar.gz`，sha256 `75186efaeb291fa0d00b316e3951e7b29e1c6939482084e903526e720e9c1949`。
3. 新增 `scripts/install_release_bundle.sh`，安装包时会校验顶层目录并将 `current` 指到包内 `protein-ai-platform` 子目录。
4. ECS `.env.aliyun.app` 已生成应用内部随机密钥，不再使用默认 `CHANGE_ME`。
5. Redis endpoint 已按可解析域名预填为 `r-bp1pbb3itre15i8nm5.redis.rds.aliyuncs.com`。
6. 后端与 compose 已支持 Redis username/password 和完整 Redis URL，等待 Redis 网络/密码确认。
7. backend 镜像已重建，`import app.main` smoke 通过。

当前复测：

| 项 | 结果 |
|---|---|
| RDS | `pgm-bp14shfmqveu8o4h.pg.rds.aliyuncs.com:5432` 超时 |
| Redis | `r-bp1pbb3itre15i8nm5.redis.rds.aliyuncs.com:6379` 超时 |
| OSS 公网 | `oss-cn-beijing.aliyuncs.com:443` 可达 |
| OSS internal | `oss-cn-beijing-internal.aliyuncs.com:443` 超时 |
| ECS 容器 | 未启动业务容器 |

仍需人工或云控制台处理：

1. RDS 放通 ECS 到 5432：公网地址白名单或 CEN/VPC 跨地域互通。
2. Redis 放通 ECS 到 6379，并确认 ACL 用户名/密码格式。
3. 填写 RDS 三个连接串。
4. 填写 OSS AccessKey 或配置 ECS RAM Role。
5. 填写 DashScope API Key。
6. 决定入口端口：继续 `4200/4280/4243`，或改成 `80/443` 并配置安全组。

## 12. 2026-07-16 试运行启动结果

已完成：

1. RDS 公网地址、Redis 公网地址、OSS、DashScope 和安全组放行已完成试运行配置。
2. ECS 应用栈已启动，容器状态为 healthy：
   - backend
   - frontend
   - nginx
   - outline
   - worker
   - chromadb
3. 当前入口为 `http://120.27.108.138:4200`。
4. 黑盒 smoke 通过：
   - ECS 本机 `http://127.0.0.1:4200/api/health` -> 200
   - 公网 `http://120.27.108.138:4200/api/health` -> 200
   - `/` 前端入口 -> 200
   - `/wiki` SPA 入口 -> 200

本轮修复点：

1. Outline 要求 `OUTLINE_SECRET_KEY` 和 `OUTLINE_UTILS_SECRET` 为 hex 字符串；初始化脚本已改为生成 64 字符 hex。
2. 当前 RDS 不支持 SSL 连接，`ALIYUN_OUTLINE_PGSSLMODE` 需设为 `disable`。
3. Outline 迁移需要 PostgreSQL 扩展 `uuid-ossp`、`unaccent`、`pg_trgm`；已用 RDS Super 账号在 `outline` 库预创建。
4. 当前入口使用 HTTP `4200`，`OUTLINE_FORCE_HTTPS=false`；正式域名和 HTTPS 证书就绪后再改为 `true`。

账号级 smoke：

1. 已创建初始管理员账号 `admin@crvab.com`。
2. 初始密码只保存在 ECS：`/opt/protein-ai-platform/shared/secrets/admin-initial-credentials.txt`。
3. API smoke 已通过：
   - 登录
   - `/api/auth/me`
   - `/api/auth/admin/ping`
   - OSS 文件上传/下载
   - `residue_numbering_gate` 轻量工具调用
   - OIDC discovery、JWKS、authorize 授权码签发
   - `/wiki/auth/oidc` 入口

仍需上线前确认：

1. 使用真实浏览器人工登录管理员账号，补后台截图。
2. 绑定正式域名和 HTTPS 证书后，将入口从临时 `4200` 切到生产 `80/443`。
3. 评估 ECS 规格；当前 1.8GiB 内存依赖 4G swap，试运行可用但生产建议升配。

## 13. 2026-07-17 ECS 升配后复验

已完成：

1. ECS 已升配，当前资源：
   - 8 vCPU
   - 30GiB 内存
   - 197G 系统盘，当前使用约 14G
   - 4G swap，当前未使用
2. 升配后应用栈已恢复，容器状态为 healthy：
   - backend
   - frontend
   - nginx
   - outline
   - worker
   - chromadb
3. 修复 nginx 证书目录丢失问题：
   - 当前 release 生成了临时自签 `docker/ssl/server.crt` 和 `server.key`。
   - 强制重建 nginx 容器后恢复健康。
   - `scripts/install_release_bundle.sh` 已补充继承旧 release 的 `docker/ssl` 目录，防止后续发布再次丢证书。
4. 升配后 smoke 通过：
   - 公网 `http://120.27.108.138:4200/api/health` -> 200
   - 公网 `https://120.27.108.138:4243/api/health` -> 200
   - 管理员登录、`/api/auth/me`、`/api/auth/admin/ping` -> 200
   - OSS 上传/下载 -> 200
   - OIDC discovery、JWKS、authorize -> 通过
5. 最近 10 分钟 backend、nginx、outline 日志未见 error/traceback/exception/emerg。

当前边界：

1. 4243 当前使用临时自签证书，仅用于技术验证。
2. 正式域名和正式 CA 证书仍未配置。
3. `PUBLIC_BASE_URL` 仍为 `http://120.27.108.138:4200`。
4. `OUTLINE_FORCE_HTTPS=false` 仍适配当前临时 HTTP 入口；正式 HTTPS 域名就绪后再改为 `true`。

## 14. 2026-07-17 公网 IP 直接上线

用户确认先不等待正式域名，直接使用公网 IP 上线。

当前主入口：

```text
http://120.27.108.138
```

当前配置：

```text
PUBLIC_BASE_URL=http://120.27.108.138
OUTLINE_PUBLIC_URL=http://120.27.108.138/wiki
OUTLINE_FORCE_HTTPS=false
APP_HTTP_PORT=80
APP_HTTP_REDIRECT_PORT=4280
APP_HTTPS_PORT=4243
```

当前验证：

1. `http://120.27.108.138/api/health` -> 200。
2. `http://120.27.108.138/` -> 200。
3. `http://120.27.108.138/wiki` -> 200。
4. 管理员登录、`/api/auth/me`、admin ping、OSS 上传/下载均通过。
5. OIDC discovery issuer 为 `http://120.27.108.138`。
6. OIDC authorize 能签发授权码并带回原始 state。
7. backend、frontend、nginx、outline、worker、chromadb 全部 healthy。

端口说明：

| 端口 | 用途 | 状态 |
|---|---|---|
| 80 | 用户主入口 | 已启用 |
| 4243 | HTTPS 技术验证，自签证书 | 已启用，不作为主入口 |
| 4280 | nginx redirect 入口 | 保留 |
| 4200 | 旧临时入口 | 已不再监听 |

当前边界：

1. 当前没有正式域名，因此不启用可信 HTTPS。
2. 后续如需正式 HTTPS，需要先绑定域名和证书，再改 `PUBLIC_BASE_URL`、`OUTLINE_PUBLIC_URL` 和 `OUTLINE_FORCE_HTTPS=true`。

## 15. 2026-07-17 `/data` 数据资产恢复

现象：

1. `http://120.27.108.138/data` 页面可访问，但 `/api/data/readiness` 返回 `summary=empty`。
2. ECS `/opt/protein-ai-platform/deploy_data` 只有 `4.0K`。
3. 本地项目 `deploy_data` 为 `1.7G`，说明此前上线 release 包未包含大数据资产。

处理：

1. 将本地 `deploy_data/` 同步到 ECS 持久目录：

```text
/opt/protein-ai-platform/deploy_data
```

2. 将本地 lipase SQLite 数据库同步到：

```text
/opt/protein-ai-platform/deploy_data/lipase/lipase.db
```

3. 在 ECS `current/docker/.env.aliyun.app` 固定数据挂载配置：

```text
DEPLOY_DATA_HOST_PATH=/opt/protein-ai-platform/deploy_data
LIPASE_DB_PATH=/app/deploy_data/lipase/lipase.db
```

4. 重建 backend、worker，使新挂载生效。

验证：

1. `/api/data/readiness` -> `summary=live-ready`。
2. annotations、sifts、pdb、alphafold、foldseek、smoke_query 全部 ready。
3. `/api/data/lipase/status` -> `status=ready`，SQLite integrity check 为 `ok`。
4. D223G evidence context 返回 exact=1、position=1、strongest=`article_level`。
5. backend、worker 均 healthy。

后续要求：

1. `deploy_data` 不进入 release 压缩包，继续放在 `/opt/protein-ai-platform/deploy_data`。
2. 新 release 只需继承 `.env.aliyun.app` 中的 `DEPLOY_DATA_HOST_PATH` 和 `LIPASE_DB_PATH`。
3. 发版后必须重新检查 `/api/data/readiness` 和 `/api/data/lipase/status`。

## 8. 最小可上线配置建议

试运行最小方案：

1. 先使用公网 IP `http://120.27.108.138:4200` 作为 `PUBLIC_BASE_URL`。
2. 安全组放行 4200 或使用 Nginx 80 反代到容器。
3. RDS/Redis 白名单仅放行 `120.27.108.138`。
4. OSS 使用公网 endpoint。
5. 所有密钥只保存在 ECS 本机 `.env` 文件，不进入 Git。

正式生产优化：

1. 绑定域名并启用 HTTPS。
2. 统一云资源地域。
3. 配置非 root 部署用户。
4. 配置自动备份和恢复演练。
5. 配置日志、监控和告警。
