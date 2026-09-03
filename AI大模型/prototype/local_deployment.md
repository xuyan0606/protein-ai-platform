# KWB-EnzymeDesigner 本地部署

当前本地服务：

- 地址：`http://127.0.0.1:8766`
- 浏览器首页：`GET /`
- 健康检查：`GET /health`
- 研发状态：`GET /v1/status`
- 设计接口：`POST /v1/enzyme-design`
- 版本：`0.2.0-gated-local`
- 模式：`local-only-gated`
- 生产平台接入：否

## 已验证

- 上传结构且编号已确认：返回 `completed`，不触发 ESMFold。
- 仅序列且预测结构未完成：返回 `pending_structure`。
- 浏览器首页：返回 `200 OK`，可查看状态并运行示例请求。
- 研发状态接口：返回本地 7 条工作流、训练流水线和当前阻塞项。
- `HEAD /` 和 `HEAD /v1/status`：返回 `200 OK`，避免浏览器或诊断工具误判。
- 运行事件包含当前轮 task_id、依赖关系和 local-only 标记。

启动命令：

```bash
python3 prototype/kwb_enzyme_designer_gated_service.py --host 127.0.0.1 --port 8766
```

Smoke：

```bash
python3 scripts/smoke_gated_local_service.py --endpoint http://127.0.0.1:8766
```
