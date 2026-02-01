# Change: 飞书网关与 Callback 服务分离

## Why

当前架构将飞书事件订阅处理、卡片回调处理、权限决策处理都耦合在同一个 Python 服务中。这导致：

1. **部署不灵活**：无法为多个 Claude Code 实例共享一个飞书应用
2. **扩展困难**：新增 Claude Code 实例需要重新配置飞书应用的请求地址
3. **资源浪费**：每个 callback 服务都需要管理自己的飞书 token

用户需求：**一个飞书网关中心 + 多个 callback 后端**。

## What Changes

### 架构变更

```
当前架构（紧耦合）：
┌─────────────────────────────────────────────────┐
│  Callback Server (main.py)                      │
│  ├─ HTTP Handler (callback.py)                  │
│  │   ├─ /allow, /deny, /always, /interrupt      │
│  │   └─ /feishu/send                            │
│  ├─ Feishu Handler (feishu.py)                  │
│  │   ├─ url_verification                        │
│  │   └─ card.action.trigger                     │
│  ├─ Request Manager                             │
│  └─ Unix Socket (与 permission.sh 通信)          │
└─────────────────────────────────────────────────┘

分离后架构：
┌─────────────────────────────────────────────────┐
│  Feishu Gateway (新服务)                         │
│  ├─ 接收飞书事件订阅                              │
│  │   ├─ url_verification                        │
│  │   ├─ im.message.receive_v1                   │
│  │   └─ card.action.trigger                     │
│  ├─ 发送飞书消息 (OpenAPI)                        │
│  │   ├─ Token 管理                              │
│  │   └─ /feishu/send                            │
│  └─ 路由回调到 Callback Server                   │
│      └─ 根据 request 中的 callback_url 转发       │
└─────────────────────────────────────────────────┘
        │
        │ HTTP 转发 (根据 callback_url)
        ▼
┌───────────────────────────────────────┐
│  Callback Server A                    │
│  ├─ HTTP Handler                      │
│  │   └─ /callback/decision            │
│  ├─ Request Manager                   │
│  └─ Unix Socket                       │
└───────────────────────────────────────┘
┌───────────────────────────────────────┐
│  Callback Server B                    │
│  ├─ (同上)                            │
└───────────────────────────────────────┘
```

### 核心变更点

1. **新增 `CALLBACK_SERVER_URL` 携带到飞书卡片**
   - 飞书卡片按钮的 `value` 中增加 `callback_url` 字段
   - 用户点击按钮时，飞书网关根据此字段转发请求

2. **飞书网关独立配置**
   - 新增 `FEISHU_GATEWAY_URL` 配置（Shell 端用于发送消息）
   - 网关负责管理 App Token，callback 服务无需飞书凭证

3. **Callback 服务简化**
   - 移除飞书事件处理逻辑
   - 仅保留决策处理和 Socket 通信
   - 新增 `/callback/decision` 端点接收网关转发的决策

4. **消息发送路由**
   - Shell 脚本通过 `FEISHU_GATEWAY_URL/feishu/send` 发送消息
   - 网关统一使用 OpenAPI 发送

## Impact

- **Affected specs**: `permission-notify`, `card-callback`
- **Affected code**:
  - `src/server/main.py` - 拆分为两个服务
  - `src/server/handlers/feishu.py` - 移至网关
  - `src/server/services/feishu_api.py` - 移至网关
  - `src/lib/feishu.sh` - 支持 `FEISHU_GATEWAY_URL`
  - `.env.example` - 新增配置项

## Configuration Changes

### 新增配置项

| 配置项 | 用途 | 默认值 |
|--------|------|--------|
| `FEISHU_GATEWAY_URL` | 飞书网关地址 | 空（不启用分离模式） |
| `CALLBACK_SERVER_ID` | Callback 服务标识（用于日志和调试） | 空 |

### 配置场景

**场景 1: 单机部署（向后兼容）**
```bash
# 不配置 FEISHU_GATEWAY_URL，使用当前架构
FEISHU_SEND_MODE=openapi
FEISHU_APP_ID=xxx
FEISHU_APP_SECRET=xxx
CALLBACK_SERVER_URL=http://localhost:8080
```

**场景 2: 分离部署**
```bash
# Feishu Gateway 配置
FEISHU_APP_ID=xxx
FEISHU_APP_SECRET=xxx
FEISHU_GATEWAY_PORT=8080

# Callback Server 配置
FEISHU_GATEWAY_URL=http://gateway:8080
CALLBACK_SERVER_URL=http://callback-a:8081
CALLBACK_SERVER_PORT=8081
```

## Questions for Discussion

1. **请求路由策略**：飞书卡片按钮点击后，网关如何知道转发到哪个 callback？
   - 方案 A: 在按钮 `value` 中携带 `callback_url`（推荐）
   - 方案 B: 使用 request_id 前缀编码 callback 地址
   - 方案 C: 网关维护请求路由表

2. **向后兼容**：是否需要支持当前的单机部署模式？
   - 建议：是，通过 `FEISHU_GATEWAY_URL` 是否配置来区分

3. **安全性**：callback 服务的 `/callback/decision` 端点是否需要认证？
   - 可选：共享密钥、IP 白名单、或信任内网

4. **服务发现**：是否需要支持动态注册 callback 服务？
   - 当前方案不需要，每个请求自带 callback_url
