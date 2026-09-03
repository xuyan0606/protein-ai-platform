# ProteinMCP 临时源码下载审计

日期：2026-07-31

用户授权边界：可以临时下载 `charlesxu90/ProteinMCP` 做研究借鉴，完成后删除。

## 执行结果

重新下载已成功。本轮通过 GitHub codeload zip 临时取得源码，完成静态源码审计后删除临时源码目录和 zip。

临时下载信息：

- 下载路径：`/private/tmp/proteinmcp-source-audit.zip`
- 解压路径：`/private/tmp/proteinmcp-source-audit`
- zip sha256：`50e3c4b37bcddb798ba1b5430b3117f1f9bf2d08fec62cc8a1204f25ea02328f`
- 解压后文件数：93
- 解压后目录大小：7.1M
- zip 大小：4.0M
- license 文件：MIT License，仍只代表源码许可初步识别，不代表 KWB 生产集成批准。

## 下载尝试

1. `git clone --depth 1 https://github.com/charlesxu90/ProteinMCP.git /private/tmp/proteinmcp-source-audit`
   - 结果：失败。
   - 原因：当前环境将 GitHub 连接落到 SSH 路径后断开，报 `Could not read from remote repository`。

2. `curl -L https://github.com/charlesxu90/ProteinMCP/archive/refs/heads/main.zip -o /private/tmp/proteinmcp-source-audit.zip`
   - 结果：失败。
   - 原因：`LibreSSL SSL_connect: SSL_ERROR_SYSCALL in connection to github.com:443`。

3. `curl -L https://codeload.github.com/charlesxu90/ProteinMCP/zip/refs/heads/main -o /private/tmp/proteinmcp-source-audit.zip`
   - 结果：失败。
   - 原因：`LibreSSL SSL_connect: SSL_ERROR_SYSCALL in connection to codeload.github.com:443`。

4. `GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null git clone --depth 1 https://github.com/charlesxu90/ProteinMCP.git /private/tmp/proteinmcp-source-audit`
   - 结果：失败。
   - 原因：`LibreSSL SSL_connect: SSL_ERROR_SYSCALL in connection to github.com:443`。

5. `curl --http1.1 --retry 3 --retry-all-errors --connect-timeout 30 -L https://codeload.github.com/charlesxu90/ProteinMCP/zip/refs/heads/main -o /private/tmp/proteinmcp-source-audit.zip`
   - 结果：成功。
   - 后续动作：解压到 `/private/tmp/proteinmcp-source-audit`，只做静态源码审计，不安装、不运行、不注册 MCP。

## 源码审计范围

已阅读：

- `README.md`
- `docs/architecture.md`
- `tool-mcps/README.md`
- `src/mcp_cli.py`
- `src/skill_cli.py`
- `src/mcp/mcp.py`
- `src/mcp/mcp_manager.py`
- `src/mcp/install_mcp.py`
- `src/mcp/status_cache.py`
- `src/mcp/create_mcp.py`
- `src/mcp/mcp_creator.py`
- `src/skill/skill.py`
- `src/skill/skill_manager.py`
- `src/skill/configs.yaml`
- `workflow-skills/fitness_modeling.md`
- `mcp-skills/mcp_creation_validator.md`
- `src/prompts/step6_wrap_mcp_prompt.md`
- `src/prompts/step7_test_integration_prompt.md`
- `src/prompts/step8_create_readme_prompt.md`

源码审计结论已写入：`platform_integration/proteinmcp_deep_research_2026_07_31.md`。

## 清理状态

已执行清理：

- `/private/tmp/proteinmcp-source-audit`
- `/private/tmp/proteinmcp-source-audit.zip`
- `/private/tmp/ProteinMCP-main`

最终复核：上述三个路径均不存在。

## 对 KWB 的影响

1. 本轮没有保留 ProteinMCP 源码。
2. 本轮没有安装 ProteinMCP。
3. 本轮没有启用外部 MCP、Docker、GPU runtime、第三方工具或权重。
4. 本轮没有导入训练标签、没有修改模型 claim、没有打开 release。
5. `proteinmcp_deep_research_2026_07_31.md` 已升级为源码级架构借鉴报告。

## 后续建议

如后续要真正借鉴实现，应先建设 KWB 自有 staging gate，而不是直接安装或注册 ProteinMCP。仍需保持：

- `safe_for_model_claim=false`
- `release_ready=false`
- `production_execution_allowed=false`
