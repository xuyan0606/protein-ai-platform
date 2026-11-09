# 20261103 比活力报告修复发布

用户在复核真实报告后要求“解决这些问题”，本轮将本地修复部署并验证完整业务链路。发布源码为`2b46baee8f0926b04e547e2e2063355ef8620097`，包含报告修复`3d10e280e`及二次切换保护。版本目录为`/opt/protein-ai-platform/releases/20261103-activity-2b46baee8/protein-ai-platform`。

已上线并验收，状态`accepted_with_recorded_exceptions`；服务器与本地当前生产记录均已同步，验收时间为2026-11-03 12:06（北京时间）。

## 交付范围

对匿名SWISS-MODEL比活力请求，复用已有坐标序列先收集身份与测定条件，遵守本地/联网限制，暂停缺少前置证据的排序、扫描和启发式kcat。异步检索未完成时生成阶段进展并保持`NEEDS_REVIEW`。执行失败、门控与后台等待分别呈现；扫描保留诊断原因；结构摘要保留GMQE等模型元数据，长度截断不发布半句。

完整根因和本地修复见 [缺陷修复记录](platform-activity-report-fix-20261103.md)。本次没有确认目标酶身份、找到有效突变或证明比活力改善。

## 发布准备

- 本轮重新执行后端全量：`1780 passed, 1 warning in 178.80s`；发布保护与模型HTTP服务测试：`16 passed`。
- 包内376个文件逐项哈希核验，归档SHA-256：`ef040fc4e8de577f997e2ee9ca9cc6b12fed91a44217dc23d447f3ce6d8e0d20`。
- 与线上源码逐文件比较，应用仅改变5个文件；数据库模型/迁移和前端发布文件未改。
- 在线上实际镜像依赖、`--network none`隔离容器中编译新源码并重放原案例成功。镜像没有pytest，未为测试安装依赖；首轮验证脚本的SQLite配置与0600私有文件读取不适合该容器，调整为不可连接的假PostgreSQL配置与标准输入后通过，不改应用代码或私有文件权限。
- 切换前后台active/reserved/scheduled均为空。新备份122246558 bytes，SHA-256：`4226f3d40c632361a795c9a3e9ece56ec26733b3c100a94eabed234683bad134`；已仅在隔离临时PostgreSQL恢复并核对51表、迁移号`20260917_0004`。
- 基于当前生产记录核对容器ID、镜像及只读源码挂载，保存新检查点。原20261103快照与首次发布回退容器均保留。

## 线上验收

切换前用两个临时测试账号验证登录、真实336 aa PDB解析与文件哈希、所有者隔离，记录原报告哈希与原BLAST任务编号。

- 五个应用容器替换成功；八容器healthy、重启0。四个后端服务各258个源码/迁移文件逐项哈希与候选一致。
- 原Bearer、Cookie、刷新令牌、新登录、切换前上传与所有者隔离通过；所有启动命令、环境、镜像、资源限制及持久卷保留。
- 实际`analyze-by-name`调用生成完整AI摘要，保留GMQE=0.99。
- 临时账号通过公网所用HTTP接口执行“上传真实PDB副本→六步签名策略→确认执行→实际工具→BLAST后台回执→阶段进展报告”，不再要求重复FASTA，不执行无前置证据的kcat/排序/扫描，交付状态不是READY。
- 实际浏览器登录、会话内新报告呈现、刷新保持、390像素宽度报告通过；文档宽度390，无横向溢出，记录到的浏览器/HTTP错误均0。
- 11个前端静态文件HTTP哈希一致，模型HTTP健康；生产数据库只读核对仍51表、迁移号20260917_0004。
- 原BLAST仍保留相同RID，补充检查时处于waiting，不将其记作无同源命中。验收未通过时不重复提交原搜索。

两个临时账号已禁用，旧Bearer实测返回403；测试会话、上传和测试任务已清理，任务审计保留。原报告哈希不变，原BLAST任务与RID保留。本机临时登录凭据已删除。

浏览器脚本先遇到同名会话/账号严格定位冲突，再遇到在Node上下文直接读取`innerWidth`；修正定位与网页上下文后重新完整执行通过。模型健康验收脚本误从Settings读取环境变量，改为已有环境变量后通过；这些是验收脚本修正，未改动发布源码。

## 回退与接续

本轮私有配置/切换回执：`/opt/protein-ai-platform/candidates/activity-2b46baee8-private/`；临时账号验收材料：`candidates/activity-2b46baee8-acceptance/`。不得提交其中的凭据、用户结构或原始会话。

应用回退入口：

```sh
python3.11 /opt/protein-ai-platform/releases/20261103-activity-2b46baee8/protein-ai-platform/scripts/prepare_thermostability_release.py \
  --rollback-runtime /opt/protein-ai-platform/candidates/activity-2b46baee8-private
```

默认保留最新数据库、文件和所有持久卷；回退后须核对服务与更新生产事实记录。没有执行生产回退演练。`current`仍是陈旧链接，后续重建使用实际容器和`production-version.json`。可信TLS及镜像registry RepoDigest的既有例外沿用，不因本次修复被视为关闭。
