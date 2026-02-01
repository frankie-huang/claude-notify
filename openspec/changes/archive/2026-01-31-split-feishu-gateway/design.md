## Context

当前系统中，飞书事件处理和权限回调处理在同一个 Python 服务中。用户希望能够：
- 部署一个统一的飞书网关接收所有飞书事件
- 部署多个 callback 服务处理不同 Claude Code 实例的权限请求
- 新增 Claude Code 实例时只需启动新的 callback 服务，无需修改飞书应用配置

## Goals / Non-Goals

**Goals:**
- 支持飞书网关与 callback 服务分离部署
- 保持向后兼容，单机部署仍可正常工作
- 请求自动路由到正确的 callback 服务

**Non-Goals:**
- 不实现 callback 服务的动态注册/发现
- 不实现 callback 服务的负载均衡
- 不修改 permission.sh 与 callback 服务之间的 Socket 通信机制

## Decisions

### Decision 1: 请求路由使用按钮 value 携带 callback_url

**选择方案 A**：在飞书卡片按钮的 `value` 中携带 `callback_url`

```json
// 当前按钮 value 格式
{
  "action": "allow",
  "request_id": "1234567890-abcd1234"
}

// 新按钮 value 格式
{
  "action": "allow",
  "request_id": "1234567890-abcd1234",
  "callback_url": "http://callback-a:8081"
}
```

**理由：**
- 无状态设计，网关无需维护路由表
- 每个请求自包含路由信息
- 实现简单，兼容性好

**Alternatives considered:**
- 方案 B (request_id 编码): 会使 request_id 变得很长，且需要特殊解析
- 方案 C (路由表): 增加网关复杂度，需要处理请求过期

### Decision 2: 网关转发使用标准 HTTP

网关收到 card.action.trigger 事件后，通过 HTTP POST 转发到 callback 服务：

```
POST {callback_url}/callback/decision
Content-Type: application/json

{
  "action": "allow",
  "request_id": "1234567890-abcd1234",
  "project_dir": "/path/to/project"
}
```

Callback 服务响应：

```json
{
  "success": true,
  "toast": {
    "type": "success",
    "content": "已批准运行"
  }
}
```

网关将 toast 返回给飞书。

### Decision 3: 消息发送统一通过网关

Shell 脚本发送飞书消息的流程：

```
# 分离模式
FEISHU_GATEWAY_URL 已配置
  → POST ${FEISHU_GATEWAY_URL}/feishu/send
  → 网关使用 OpenAPI 发送

# 单机模式（向后兼容）
FEISHU_GATEWAY_URL 未配置
  → 使用 FEISHU_SEND_MODE 决定发送方式
  → webhook: 直接 POST 到 FEISHU_WEBHOOK_URL
  → openapi: POST 到 ${CALLBACK_SERVER_URL}/feishu/send
```

### Decision 4: 配置优先级

```
判断逻辑：
if FEISHU_GATEWAY_URL is set:
    → 分离模式
    → 消息发送: POST FEISHU_GATEWAY_URL/feishu/send
    → 按钮 callback_url: CALLBACK_SERVER_URL
else:
    → 单机模式
    → 按原有逻辑运行
```

## Data Flow

### 分离模式下的权限请求流程

```
1. Claude Code 触发 PermissionRequest hook
   ↓
2. permission.sh 执行
   ├─ 生成 request_id
   ├─ 构建飞书卡片 JSON
   │   └─ 按钮 value 包含 callback_url: ${CALLBACK_SERVER_URL}
   ├─ POST ${FEISHU_GATEWAY_URL}/feishu/send 发送卡片
   └─ 通过 Unix Socket 注册请求到本地 callback 服务，阻塞等待
   ↓
3. Feishu Gateway 收到 /feishu/send
   ├─ 使用 OpenAPI 发送卡片到飞书
   └─ 返回 message_id
   ↓
4. 用户在飞书中点击按钮
   ↓
5. Feishu Gateway 收到 card.action.trigger 事件
   ├─ 解析 action.value.callback_url
   ├─ POST {callback_url}/callback/decision
   │   body: { action, request_id, project_dir }
   └─ 将 callback 响应的 toast 返回给飞书
   ↓
6. Callback Server 收到 /callback/decision
   ├─ 通过 request_id 找到 Socket 连接
   ├─ 发送决策给 permission.sh
   └─ 返回 toast 响应给网关
   ↓
7. permission.sh 收到决策
   ├─ 输出决策 JSON 到 stdout
   └─ 退出
   ↓
8. Claude Code 继续执行
```

## API Specification

### Feishu Gateway API

#### POST /feishu/send
发送飞书消息（与现有 API 保持一致）

Request:
```json
{
  "msg_type": "interactive",
  "content": { /* 卡片 JSON */ }
}
```

Response:
```json
{
  "success": true,
  "message_id": "om_xxx"
}
```

#### POST / (飞书事件订阅)
接收飞书事件，处理或转发

### Callback Server API

#### POST /callback/decision
接收网关转发的决策请求

Request:
```json
{
  "action": "allow|always|deny|interrupt",
  "request_id": "1234567890-abcd1234",
  "project_dir": "/path/to/project"
}
```

Response:
```json
{
  "success": true,
  "toast": {
    "type": "success",
    "content": "已批准运行"
  }
}
```

## Risks / Trade-offs

### Risk 1: 网络延迟增加
- **问题**: 分离部署增加一次 HTTP 调用
- **影响**: 用户点击按钮后响应时间略有增加（约 50-100ms）
- **缓解**: 内网部署时影响可忽略

### Risk 2: callback_url 泄露
- **问题**: 按钮 value 在飞书日志中可能被记录
- **影响**: 知道 callback_url 可以伪造决策
- **缓解**:
  - 建议内网部署
  - 可选实现请求签名验证

### Risk 3: 网关单点故障
- **问题**: 网关宕机会影响所有 callback 服务
- **缓解**:
  - 网关是无状态的，可以部署多实例
  - 可配置飞书应用使用多个请求地址

## Migration Plan

### Phase 1: 增加 callback_url 支持（向后兼容）
1. 修改 `src/lib/feishu.sh`，按钮 value 中增加 `callback_url`
2. 修改 `src/server/handlers/feishu.py`，支持读取 `callback_url` 并转发
3. 当 `callback_url` 与当前服务相同时，直接处理

### Phase 2: 拆分网关服务
1. 创建独立的网关服务代码
2. 迁移飞书 API 服务到网关
3. callback 服务保留决策处理逻辑

### Phase 3: 配置和文档更新
1. 更新 `.env.example` 增加新配置项
2. 更新 README 说明分离部署方式
3. 提供 docker-compose 示例

## Open Questions

1. **是否需要支持 Webhook 模式的分离部署？**
   - 当前设计假设分离模式使用 OpenAPI
   - Webhook 模式下按钮是普通 URL，用户直接访问 callback 服务

2. **是否需要支持多个飞书应用？**
   - 当前设计一个网关对应一个飞书应用
   - 如需多应用，需要在消息发送时指定 app 标识
