# Change: 添加 WebSocket 长连接隧道模式

## Why

在分离部署模式下，Callback 后端需要被飞书网关通过网络访问。对于在本地电脑（如 MacBook）上开发的用户，其 Callback 后端运行在本地，飞书网关无法直接访问。

当前方案要求每个 Callback 部署在公网可访问的服务器上，这对本地开发用户不友好。

## What Changes

### 新增功能

- 飞书网关在现有 HTTP 端口 (:8080) 上新增 WebSocket Upgrade 支持（路径 `/ws/tunnel`）
- 本地 Callback 后端新增 WebSocket 隧道客户端，主动连接网关并保持心跳
- 网关路由层支持 HTTP 和 WebSocket 双模式分发（优先 WS，fallback HTTP）
- 支持通过 WS 通道完成首次注册（解决本地 Callback 无法被网关 HTTP 回调的问题）

### 架构变化

```
现有模式（HTTP）：
  飞书网关 :8080 --HTTP POST--> Callback (公网/内网可达)

新增模式（WebSocket 隧道）：
  本地 Callback --WS Upgrade--> 飞书网关 :8080/ws/tunnel
  飞书网关 --WS Message--> 本地 Callback（通过长连接）
```

### 配置项

- 复用现有 `FEISHU_GATEWAY_URL`：通过协议头自动检测连接模式
  - `ws://host:port` 或 `wss://host:port` → WS 隧道模式
  - `http://host:port` 或 `https://host:port` → HTTP 回调模式（现有行为）
- 新增派生变量 `FEISHU_GATEWAY_MODE`（`'ws'` 或 `'http'`，代码内部使用，无需用户配置）

## Impact

- **Affected specs**: `gateway-auth`（新增 WebSocket 连接认证和路由逻辑）
- **Affected code**:
  - 新增 `src/server/services/ws_protocol.py`（最小 WebSocket 协议实现，基于标准库，含 SSL 支持）
  - 新增 `src/server/services/ws_registry.py`（连接管理：pending/authenticated 双状态、请求-响应匹配）
  - 新增 `src/server/services/ws_tunnel_client.py`（Callback WS 客户端，含线程池请求处理）
  - 新增 `src/server/handlers/ws_handler.py`（WS 隧道处理器：握手、认证、消息循环）
  - 修改 `src/server/handlers/http_handler.py`（WS Upgrade 路由，委托给 ws_handler）
  - 修改 `src/server/handlers/register.py`（WS 注册/换绑/授权流程）
  - 修改 `src/server/handlers/feishu.py`（统一路由分发：WS 优先 + HTTP fallback）
  - 修改 `src/server/config.py`（协议检测、`FEISHU_GATEWAY_MODE` 派生变量）
  - 修改 `src/server/main.py`（WS 客户端启动、WebSocketRegistry 初始化、优雅关闭）
- **Breaking changes**: 无（HTTP 模式完全兼容，WS 是增量功能）
- **Dependencies**: 无新增外部依赖（使用 Python 标准库 `socket` + `hashlib` + `struct` + `ssl` 实现 WebSocket 协议）
