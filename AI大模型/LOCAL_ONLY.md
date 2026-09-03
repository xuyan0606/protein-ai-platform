# 本地研发边界

本目录是本地研发区。

## 严格限制

- 不允许自动同步到服务器。
- 不允许自动执行 `ssh`、`scp`、`rsync`、远端 `docker compose`、远端构建或远端重启。
- 不允许自动修改 `/opt/protein-ai-platform/current`。
- 不允许自动更新线上数据库、OSS、RDS、Redis 或 ECS 文件。

## 允许操作

- 本地文档设计。
- 本地 schema 设计。
- 本地 prototype 代码。
- 本地测试脚本。
- 本地小样本 benchmark。

## 发布条件

只有在用户明确下达类似“同步到服务器 / 部署上线 / 发布到 ECS”的指令后，才允许进入远端同步流程。

