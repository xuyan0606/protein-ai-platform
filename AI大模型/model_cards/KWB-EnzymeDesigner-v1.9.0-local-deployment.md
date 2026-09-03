# KWB-EnzymeDesigner v1.9.0 Local Deployment

状态：门控版 KWB-EnzymeDesigner 已部署到本机，未接入生产平台，未同步服务器。

## 地址

- `http://127.0.0.1:8766`
- `GET /health`
- `POST /v1/enzyme-design`

## 验证

- health：`ok`
- 上传结构且编号已确认：`completed`
- 仅序列且结构预测未完成：`pending_structure`
- production integration：`false`
- HTTP smoke：`ok`

## 运行边界

该服务使用本地 gated adapter 和规则 MVP。它用于验证调用顺序、结构门控和事件合同，不代表真实五头预测模型已经训练完成，也不代表线上平台已经接入。
