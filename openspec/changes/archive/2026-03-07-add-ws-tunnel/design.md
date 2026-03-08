# WebSocket 隧道设计文档

## Context

### 背景

分离部署模式下，飞书网关需要主动调用 Callback 后端的 HTTP 接口（如 `/cb/decision`、`/cb/claude/new`）。对于本地开发用户，Callback 运行在本地电脑（如 MacBook），网关无法访问本地网络。

### 约束

- 必须兼容 Python 3.6+
- 必须与现有同步 + threading 架构保持一致（不引入 asyncio）
- HTTP 模式必须继续正常工作（零影响）
- 零外部依赖：仅使用 Python 标准库
- 网络环境兼容性：WebSocket 可能在某些企业防火墙环境下被阻断

### 利益相关方

- 本地开发用户：希望在本地电脑运行 Claude Code 和 Callback
- 远程服务器用户：继续使用现有的 HTTP 模式
- 运维人员：管理飞书网关

## Goals / Non-Goals

### Goals

1. 支持本地 Callback 通过 WebSocket 长连接接入飞书网关
2. 网关支持一对多连接（多个本地用户同时连接）
3. 连接断开后自动重连（带 jitter 防止惊群）
4. HTTP 和 WebSocket 模式共存，路由层透明分发
5. 零外部依赖，使用标准库实现最小 WebSocket 协议

### Non-Goals

1. 不替代 HTTP 模式（WS 是可选增量功能）
2. 不修改现有 Unix Socket 通信协议
3. 不支持连接负载均衡（单网关场景）
4. 不实现完整的 WebSocket 协议（仅支持 text frame、ping/pong、close）

## Decisions

### D1: 使用标准库实现最小 WebSocket 协议

**决定**: 基于 Python 标准库（`socket`、`hashlib`、`struct`、`ssl`）实现最小 WebSocket 协议模块 `ws_protocol.py`

**理由**:
- 零外部依赖，减少部署复杂度（无需 pip install）
- WebSocket 协议（RFC 6455）核心部分不复杂，本项目只需 text frame + ping/pong + close
- 完全控制实现，便于调试
- 代码量约 530 行（含 SSL 支持、高级 API、安全防护）

**实现范围**:
- 客户端握手（HTTP Upgrade 请求 + 响应验证，支持 `ws://` 和 `wss://`）
- 服务端握手（HTTP Upgrade 请求解析 + 101 响应）
- Text frame 收发（opcode 0x1）
- Ping/Pong（opcode 0x9/0xA）
- Close frame（opcode 0x8）
- Client-to-server masking（RFC 要求客户端发送的帧必须 mask）
- 高级 API：`ws_recv_text`（自动处理 ping/pong/close）、`ws_close`（优雅关闭）
- 安全防护：最大帧大小限制（10MB）、握手响应大小限制（16KB）
- client mode 映射管理：使用 `id(sock)` 作为 key 跟踪 socket 是否为客户端模式（含线程安全锁和 `cleanup_socket_state` 清理函数）

**不实现**:
- Binary frame（不需要）
- 分片/续帧（消息足够小，单帧即可）
- 扩展协商（如 permessage-deflate）

**备选方案**:
- `simple-websocket`：同步模型、支持服务端+客户端、Python 3.6+ 兼容，但引入外部依赖
- `websockets`（asyncio）：需要引入事件循环，与现有架构不一致
- `websocket-client` + 自定义 server：需要两个库

### D2: 单端口 HTTP Upgrade（复用现有 :8080）

**决定**: 在现有 HTTP 端口 :8080 上通过 HTTP Upgrade 支持 WebSocket，路径为 `/ws/tunnel`

**理由**:
- 零部署变更：不需要新开端口、改防火墙/安全组、改 Docker 配置
- 复用现有 `ThreadedHTTPServer` 的线程模型：每个 WS 连接自然占用一个线程，与 HTTP 请求处理一致
- 握手阶段可直接复用 HTTP handler 的认证逻辑

**实现方式**:
```python
# http_handler.py 中 do_GET 新增路由，委托给 ws_handler
if path == '/ws/tunnel':
    handle_ws_tunnel(self, params)  # 从 query params 提取 owner_id
    return
# ws_handler.py 中：
# 1. 验证 owner_id 和 Upgrade 头
# 2. 发送 101 Switching Protocols
# 3. 等待 register 消息（含 auth_token 比对）
# 4. 进入 WS 消息循环（阻塞当前线程）
```

**备选方案**:
- 双端口（:8080 HTTP + :8081 WS）：需要额外端口管理，增加部署复杂度

### D3: 统一 register 消息认证（含 token 比对续期/换绑）

**决定**: WebSocket 连接统一使用 register 消息触发认证，每次连接都刷新 auth_token。网关通过比对客户端携带的 auth_token 区分续期和换绑：

1. 客户端连接时 URL 仅携带 `owner_id`
2. 握手后客户端发送 register 消息（含 `owner_id`、已有的 `auth_token`、配置参数）
3. 网关检查 BindingStore 并比对 auth_token：
   - **有绑定 + token 匹配**（同一终端重连）：直接生成新 token，发送 `auth_ok`，等待 `auth_ok_ack`，注册连接
   - **有绑定 + token 不匹配/缺失**（新终端）：添加到 pending，发送飞书**换绑**授权卡片（展示新旧 IP），等待用户授权
   - **无绑定**：添加到 pending，发送飞书授权卡片，等待用户授权
4. BindingStore 更新延迟到收到 `auth_ok_ack` 后执行（确保客户端已确认收到新 token 后再持久化）

**设计理由**:
- auth_token 每次连接时刷新，确保安全性（旧 token 失效）
- token 比对区分续期和换绑，避免同一终端重连时触发授权卡片打扰用户
- 新终端必须经过飞书卡片授权，防止未授权设备接入
- BindingStore 延迟更新保证一致性：如果客户端未收到 token，服务端不会更新绑定记录
- 与 HTTP 注册模式保持一致（HTTP 模式中 callback_url 相同时也是直接刷新 token）

**背景**:
现有 HTTP 注册流程中，网关需要主动回调 Callback 的 `/cb/check-owner` 和 `/cb/register` 接口。
但 WS 隧道的使用场景恰恰是网关无法访问 Callback（如本地开发环境），因此注册流程需要改造为通过 WS 通道完成。

**URL 格式**:
```
ws://gateway:8080/ws/tunnel?owner_id=ou_xxx
```

**register 消息格式**:
```json
{
  "type": "register",
  "owner_id": "ou_xxx",
  "auth_token": "xxx",           // 可选，已有 token 时携带（用于续期/换绑判断）
  "reply_in_thread": false,      // 配置参数
  "claude_commands": ["opus"],   // 配置参数（可选）
  "default_chat_dir": "~/work"   // 配置参数（可选）
}
```

**同一终端重连（token 匹配）流程**:
```
Callback                        Gateway
  │                                │
  │── GET /ws/tunnel               │
  │   ?owner_id=ou_xxx             │
  │   Upgrade: websocket ────────→│
  │                                │
  │←─ 101 Switching Protocols ────│
  │                                │
  │── WS: {"type":"register",  ───→│ 检查 BindingStore: 有绑定
  │        "owner_id":"ou_xxx",   │ 比对 auth_token: 匹配
  │        "auth_token":"old"}    │ 生成新 auth_token
  │                                │ 暂存到 pending_auth_tokens
  │←─ WS: {"type":"auth_ok",  ────│
  │        "auth_token":"new"}    │
  │   存入 AuthTokenStore          │
  │                                │
  │── WS: {"type":"auth_ok_ack"}──→│ 更新 BindingStore
  │                                │ 注册到 WebSocketRegistry
  │  [连接进入已认证状态]             │
```

**新终端换绑（token 不匹配）流程**:
```
Callback                        Gateway                         飞书用户
  │                                │                                │
  │── GET /ws/tunnel               │                                │
  │   ?owner_id=ou_xxx             │                                │
  │   Upgrade: websocket ────────→│                                │
  │                                │                                │
  │←─ 101 Switching Protocols ────│                                │
  │                                │                                │
  │── WS: {"type":"register",  ───→│ 检查 BindingStore: 有绑定      │
  │        "owner_id":"ou_xxx",   │ 比对 auth_token: 不匹配        │
  │        "auth_token":"wrong"}  │ 添加到 pending                 │
  │                                │                                │
  │                                │── 发送飞书换绑授权卡片 ────────→│
  │                                │   (展示旧终端IP + 新终端IP)     │
  │                                │                  用户点击"允许" ─│
  │                                │←──────────────────────────────│
  │                                │  生成 auth_token               │
  │                                │  暂存到 pending_auth_tokens    │
  │←─ WS: {"type":"auth_ok",  ────│                                │
  │        "auth_token":"new"}    │                                │
  │   存入 AuthTokenStore          │                                │
  │                                │                                │
  │── WS: {"type":"auth_ok_ack"}──→│ 更新 BindingStore              │
  │                                │ 从 pending 升级为 authenticated │
  │                                │ 注册到 WebSocketRegistry        │
```

**无绑定时的首次注册流程**:
```
Callback                        Gateway                         飞书用户
  │                                │                                │
  │── GET /ws/tunnel               │                                │
  │   ?owner_id=ou_xxx             │                                │
  │   Upgrade: websocket ────────→│                                │
  │                                │                                │
  │←─ 101 Switching Protocols ────│                                │
  │                                │                                │
  │── WS: {"type":"register",  ───→│ 检查 BindingStore: 无绑定      │
  │        "owner_id":"ou_xxx"}    │ 添加到 pending                 │
  │                                │                                │
  │                                │── 发送飞书授权卡片 ────────────→│
  │                                │                                │
  │                                │                  用户点击"允许" ─│
  │                                │←──────────────────────────────│
  │                                │  生成 auth_token               │
  │                                │  暂存到 pending_auth_tokens    │
  │←─ WS: {"type":"auth_ok",  ────│                                │
  │        "auth_token":"xxx"}     │                                │
  │   存入 AuthTokenStore          │                                │
  │                                │                                │
  │── WS: {"type":"auth_ok_ack"}──→│ 更新 BindingStore              │
  │                                │ 从 pending 升级为 authenticated │
  │                                │ 注册到 WebSocketRegistry        │
```

**pending 状态管理**:
- pending 连接有双重超时机制：
  - **无活动超时**：90 秒无心跳（`WS_PENDING_INACTIVE_TIMEOUT`），判定客户端离线
  - **最大等待超时**：10 分钟未授权（`WS_PENDING_MAX_WAIT_TIME`），用户可能忘记或恶意
- 超时后关闭连接并发送 `{"type":"auth_error","message":"connection inactive|authorization timeout"}`
- pending 连接也会发送心跳（防止 nginx 等代理因空闲超时关闭连接）
- **多 pending 共存**：同一 owner_id 可有多个 pending 连接共存（如用户从多个终端同时发起连接）
- **pending 上限**：每个 owner_id 最多 5 个 pending 连接（`WS_MAX_PENDING_PER_OWNER`），超过时拒绝新连接
- **卡片冷却**：同一 owner_id 在 60 秒内（`WS_CARD_COOLDOWN`）最多触发一次授权卡片发送，防止轰炸
- pending 连接不注册到 WebSocketRegistry（不参与请求路由）
- pending 连接暂存 `pending_auth_tokens` 和 `pending_binding_params`，收到 `auth_ok_ack` 后统一处理
- **原子授权操作**：`prepare_authorization()` 在单次加锁内完成设置 auth_token、绑定参数、并清理其他 pending 连接
- 清理任务每 30 秒检查一次（`cleanup_pending_loop`），及时清理超时连接

**为什么跳过 check-owner**:
- HTTP 模式中 check-owner 防止恶意用户伪造 callback_url 绑定他人 owner_id
- WS 模式中不需要：Callback 是主动连接方，最终授权由飞书用户本人在卡片上点击确认，已足够验证身份

**安全考虑**:
- auth_token 每次连接时刷新，旧 token 自动失效
- token 比对防止未授权终端免卡片接入
- pending 连接有超时限制，不会无限占用资源
- 如果未来需要更高安全性，可升级为 wss:// (TLS)

**备选方案：URL 带 auth_token 握手验证**:

原始设计考虑在 URL 中携带 auth_token 进行握手阶段验证：
```
/ws/tunnel?owner_id=ou_xxx&auth_token=xxx
```

放弃该方案的原因：

1. **安全问题**：原始设计中，如果 URL 不带 auth_token 且已有绑定，网关会直接生成新 token 绑定。这意味着**任何人只要知道 owner_id 就可以绑定**，无需验证。

2. **安全性**：auth_token 出现在 URL 中可能被日志记录，存在泄露风险。register 消息体携带 token 更安全。

3. **职责分离**：握手阶段只处理协议升级（HTTP → WebSocket），认证逻辑集中在 register 消息处理中，代码更清晰。

4. **一致性**：首次注册和重连走同一个 register 消息流程，无需区分"URL 带/不带 token"两种分支。

token 比对机制解决了原始设计的安全漏洞：
- **有 token 且匹配** → 同一终端续期（免卡片）
- **无 token 或不匹配** → 新终端换绑（需要卡片授权）

### D4: 认证复用现有 auth_token 机制

**决定**: WebSocket 连接认证使用与 HTTP 相同的 auth_token（HMAC-SHA256 签名）

**理由**:
- 复用现有认证机制，减少复杂度
- auth_token 已经过验证，安全可靠
- token 生成逻辑 (`generate_auth_token`) 可直接复用
- token 比对用于区分续期和换绑场景

### D5: 客户端主动心跳 + 服务端 read timeout

**决定**: 由客户端（Callback）定时发送 WebSocket ping，服务端设置 read timeout 检测断连

**理由**:
- 客户端 ping 同时起到 **NAT 保活**作用（很多 NAT/防火墙会在空闲一段时间后断开连接）
- 服务端只需设置 read timeout（如 90s），超时未收到任何消息即清理连接，逻辑简单
- 客户端更关心连通性检测（本地网络不稳定）

**参数**:
- 客户端 ping 间隔：30s（`WS_PING_INTERVAL` 常量）
- 服务端 read timeout：90s（`WS_READ_TIMEOUT`，3 倍 ping 间隔，容忍偶发丢包）

**心跳线程安全**:
- 心跳线程启动时传入当前 socket 引用（`conn_sock`），而非直接访问 `self.sock`
- 通过 `self.sock is not conn_sock` 检测连接是否已变更（重连后旧线程自动退出）
- **pending 状态也发送心跳**：防止 nginx 等中间代理因空闲超时关闭连接（授权流程可能需要用户确认，耗时较长）

**为什么硬编码而不提供配置**:

30s 是经过验证的合理默认值，原因如下：

1. **NAT 超时覆盖**：大多数 NAT 设备/防火墙的空闲连接超时在 60s-5 分钟，30s 间隔足够保持连接活跃。

2. **更短间隔无意义**：将间隔缩短到 10s 只会增加无谓的网络流量，对连通性检测没有实质性改善。

3. **更长间隔有风险**：如果间隔超过 60s，在某些严格的网络环境下可能被 NAT 断开。

4. **特殊场景的替代方案**：如果网络环境确实不稳定，用户更可能切换到 HTTP 模式，而非调整心跳间隔。

因此，30s 硬编码是一个"足够好"的选择，避免引入不必要的配置复杂度。

**休眠后自动重连**:

当本地电脑休眠后唤醒，客户端会自动检测断连并重连：

1. **休眠期间**：网关 90s read timeout 后关闭连接，清理 WebSocketRegistry
2. **唤醒后**：心跳线程或消息循环检测到连接断开
3. **自动重连**：使用指数退避策略重连，携带本地存储的 auth_token
4. **免卡片续期**：如果 auth_token 匹配，自动续期成功，无需用户操作

检测时间取决于 TCP 层：
- 正常情况（网关发送 FIN）：几秒内
- 极端情况（NAT 静默丢弃）：最多 90s

### D6: 请求-响应匹配机制

**决定**: 使用 `id` 字段匹配请求和响应，通过 `threading.Event` 实现同步等待

**实现细节**:

```python
# ws_registry.py 中的请求-响应匹配
class WebSocketRegistry:
    _pending_requests: Dict[str, threading.Event] = {}
    _responses: Dict[str, Dict[str, Any]] = {}
    _request_lock = threading.Lock()
    _send_locks: Dict[str, threading.Lock] = {}  # per-connection 发送锁

    def send_request(self, owner_id: str, path: str, body: Dict[str, Any],
                     headers: Optional[Dict[str, str]] = None,
                     timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """发送请求并同步等待响应

        自动生成 request_id，构造标准请求消息格式。
        使用 per-connection 发送锁防止多线程并发写同一 socket。
        """
        conn = self.get(owner_id)
        if not conn:
            return None

        request_id = str(uuid.uuid4())
        request_msg = {
            'type': 'request', 'id': request_id,
            'method': 'POST', 'path': path,
            'headers': headers or {}, 'body': body
        }
        event = threading.Event()

        with self._request_lock:
            self._pending_requests[request_id] = event

        try:
            # 加锁防止帧交错
            send_lock = self._send_locks.get(owner_id)
            if send_lock:
                with send_lock:
                    ws_send_text(conn, json.dumps(request_msg))
            else:
                ws_send_text(conn, json.dumps(request_msg))

            if event.wait(timeout=timeout or REQUEST_TIMEOUT):
                with self._request_lock:
                    return self._responses.pop(request_id, None)
            return None  # 超时
        finally:
            with self._request_lock:
                self._pending_requests.pop(request_id, None)

    def handle_response(self, response: Dict[str, Any]) -> None:
        """处理收到的响应消息"""
        request_id = response.get('id')
        with self._request_lock:
            event = self._pending_requests.get(request_id)
            if event:
                self._responses[request_id] = response
                event.set()
```

### D7: 连接替换策略

**决定**: 同一 `owner_id` 新连接替换旧连接，旧连接主动关闭并通知

**网关侧行为**:
1. 新连接认证成功后（`promote_pending` 或 `register`），检查是否已有该 `owner_id` 的连接
2. 如有旧连接，向旧连接发送 `{"type":"replaced"}` 消息
3. 调用 `ws_close()` 关闭旧连接
4. 注册新连接
5. 记录日志便于排查

**客户端侧行为**:
- 收到 `replaced` 消息后**永久停止**（`running=False`），不自动重连
- 原因：换绑后网关已为新客户端生成新 auth_token，旧客户端携带的 token 不匹配，重连会反复触发换绑授权卡片，影响用户体验
- 用户如需恢复旧设备，应手动重启服务

**stop action 统一处理**:
- `replaced`、`unbind`、部分 `auth_error`（如 authorization timeout）消息带有 `action: "stop"` 字段
- 客户端收到带 `action: "stop"` 的消息后，统一执行 `_stop_reconnect()` 停止重连循环
- `unbind` 消息额外触发 `_clear_auth_token()` 清除本地存储的 token

### D8: WS 隧道处理器独立模块 (ws_handler.py)

**决定**: 将 WS 隧道的连接处理逻辑（握手后的认证 + 消息循环）拆分到独立的 `handlers/ws_handler.py`，`http_handler.py` 仅负责路由委托

**理由**:
- WS 隧道逻辑（状态机：pending → authenticated、register 消息解析、token 比对、消息循环）复杂度高
- 与 `http_handler.py` 中的 HTTP 请求处理职责不同，拆分后单文件更聚焦
- `http_handler.py` 只需在 `do_GET` 中增加一行路由：`if path == '/ws/tunnel': handle_ws_tunnel(self, params); return`

### D9: 客户端请求处理线程池

**决定**: WS 隧道客户端使用 `ThreadPoolExecutor(max_workers=8)` 处理来自网关的请求

**理由**:
- 网关转发的请求（如 `/cb/decision`）可能耗时较长，不能阻塞消息循环（否则 ping/pong 和其他消息无法处理）
- 使用线程池限制并发数（8），防止大量请求耗尽线程资源
- 多线程写 socket 需要发送锁（`_send_lock`）防止帧交错

### D10: 配置项复用（无独立 WS URL 配置）

**决定**: 不新增 `FEISHU_GATEWAY_WS_URL`，复用现有 `FEISHU_GATEWAY_URL`，通过协议头自动检测模式

**理由**:
- 减少用户配置项数量，降低使用门槛
- 协议头（`ws://`/`wss://`）已足够表达意图
- 内部自动转换：`ws://` → `http://`（供 API 调用）、`wss://` → `https://`
- 派生变量 `FEISHU_GATEWAY_MODE` 供代码内部判断使用

## Architecture

### 网络拓扑

```
┌─────────────────────────────────────────────────────────────┐
│                     飞书网关 (公网服务器)                      │
│                                                             │
│  HTTP :8080                                                 │
│   ├── 飞书事件/回调 (现有，不变)                                │
│   └── /ws/tunnel (新增，HTTP Upgrade → WebSocket)            │
│         │                                                   │
│         ├── ws_conn_1 (owner_id=ou_user_a) ← 本地用户 A     │
│         ├── ws_conn_2 (owner_id=ou_user_b) ← 本地用户 B     │
│         └── ws_conn_3 (owner_id=ou_user_c) ← 本地用户 C     │
│                                                             │
│  WebSocketRegistry (内存)                                    │
│    ou_user_a → ws_conn_1                                    │
│    ou_user_b → ws_conn_2                                    │
│    ou_user_c → ws_conn_3                                    │
│                                                             │
│  BindingStore (持久化)                                       │
│    ou_user_a → {callback_url: "ws://tunnel", ...}  (WS)    │
│    ou_user_x → {callback_url: "http://...", ...}   (HTTP)  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 消息流程

流程详见上方 D3 中的时序图。连接统一通过 register 消息触发认证，网关通过 auth_token 比对区分场景：
- **有绑定 + token 匹配**（续期）：直接刷新 token → auth_ok → auth_ok_ack → 更新 BindingStore → 注册
- **有绑定 + token 不匹配**（换绑）：pending → 飞书换绑卡片 → 授权 → auth_ok → auth_ok_ack → 更新 BindingStore → 注册
- **无绑定**（首次注册）：pending → 飞书授权卡片 → 授权 → auth_ok → auth_ok_ack → 更新 BindingStore → 注册

**请求转发（网关 → Callback）**

```
飞书用户点击按钮 → 飞书网关收到事件
                      │
                      ├─ 查 WebSocketRegistry: owner_id 有活跃连接?
                      │
                      ├─ YES: WS Send {
                      │    "type": "request",
                      │    "id": "req_123",
                      │    "method": "POST",
                      │    "path": "/cb/decision",
                      │    "headers": {"X-Auth-Token": "..."},
                      │    "body": {...}
                      │  }
                      │         │
                      │  本地 Callback 收到 ←─┘
                      │         │
                      │         ├─ 调用本地 HTTP handler 处理
                      │         │
                      │         └─ WS Send {
                      │              "type": "response",
                      │              "id": "req_123",
                      │              "status": 200,
                      │              "body": {...}
                      │            }
                      │
                      └─ NO: fallback HTTP POST（现有逻辑）
```

### WebSocket 消息协议

```json
// === 注册阶段 ===

// 注册消息（Callback → Gateway）
// 握手后客户端发送，携带 owner_id、已有 token 和配置参数
{
  "type": "register",
  "owner_id": "ou_xxx",
  "auth_token": "xxx",           // 可选，已有 token 时携带
  "reply_in_thread": false,      // 配置参数
  "claude_commands": ["opus"],   // 可选
  "default_chat_dir": "~/work"   // 可选
}

// 注册成功通知（Gateway → Callback）
// 首次注册/续期/换绑授权后，网关通过 WS 下发新 auth_token
{
  "type": "auth_ok",
  "auth_token": "timestamp_b64.signature_b64"
}

// 客户端确认收到 auth_ok（Callback → Gateway）
// 网关收到后才更新 BindingStore 并注册连接
{
  "type": "auth_ok_ack"
}

// 注册失败/超时通知（Gateway → Callback）
{
  "type": "auth_error",
  "message": "authorization timeout|authorization denied"
}

// === 数据传输阶段 ===

// 请求（Gateway → Callback）
{
  "type": "request",
  "id": "uuid-for-matching",
  "method": "POST",
  "path": "/cb/decision",
  "headers": {},
  "body": {}
}

// 响应（Callback → Gateway）
{
  "type": "response",
  "id": "uuid-for-matching",
  "status": 200,
  "headers": {},
  "body": {}
}

// 错误（双向）
{
  "type": "error",
  "id": "uuid-for-matching",
  "code": "timeout|handler_error|invalid_request",
  "message": "human-readable error description"
}

// === 连接管理 ===

// 连接被替换通知（Gateway → Callback）
{
  "type": "replaced",
  "action": "stop"
}

// 解绑通知（Gateway → Callback）
// 用户在飞书端执行解绑操作时发送，客户端收到后清除本地 token 并停止
{
  "type": "unbind",
  "action": "stop",
  "message": "user unbind"
}

// 优雅关闭通知（Gateway → Callback）
{
  "type": "shutdown"
}

// 心跳：使用 WebSocket 原生 ping/pong frame（非 JSON）
```

### ws_protocol.py 模块设计

基于标准库实现的最小 WebSocket 协议模块（约 530 行，含 SSL 支持）：

```python
# === 低级 API ===

def ws_server_handshake(handler: Any) -> socket.socket:
    """服务端握手：验证 Upgrade 头、发送 101 响应、返回 raw socket"""

def ws_client_connect(url: str, extra_headers: Optional[Dict[str, str]] = None) -> socket.socket:
    """客户端握手：发送 Upgrade 请求、验证响应、返回连接 socket（支持 ws:// 和 wss://）"""

def ws_send_text(sock: socket.socket, data: str) -> None:
    """发送 text frame（客户端自动 mask，通过 _WS_CLIENT_MODE_MAP 追踪）"""

def ws_recv(sock: socket.socket, timeout: Optional[float] = None) -> Tuple[int, bytes]:
    """接收一帧，返回 (opcode, payload)。含帧大小限制（10MB）"""

def ws_send_ping(sock: socket.socket, data: bytes = b'') -> None:

def ws_send_pong(sock: socket.socket, data: bytes = b'') -> None:

def ws_send_close(sock: socket.socket, code: int = 1000, reason: str = '') -> None:

# === 高级 API ===

def ws_recv_text(sock: socket.socket, timeout: Optional[float] = None) -> Optional[str]:
    """接收文本消息，自动处理 ping/pong/close/unsupported opcodes"""

def ws_close(sock: socket.socket, code: int = 1000, reason: str = '') -> None:
    """优雅关闭：发送 close frame + 等待响应(2s) + 清理 client mode + 关闭 socket"""

def cleanup_socket_state(sock: socket.socket) -> None:
    """清理 socket 的协议层状态（client mode 映射和发送锁，幂等可重复调用）"""

# === 常量 ===
OPCODE_TEXT = 0x1
OPCODE_CLOSE = 0x8
OPCODE_PING = 0x9
OPCODE_PONG = 0xA
MAX_FRAME_SIZE = 10 * 1024 * 1024  # 10MB
```

**client mode 跟踪机制**：
- 使用模块级 `_WS_CLIENT_MODE_MAP: Dict[int, bool]` 字典追踪 socket 是否为客户端模式
- key 为 `id(sock)`（避免 OS 文件描述符复用导致状态错乱）
- 线程安全：`_WS_CLIENT_MODE_LOCK` 保护并发读写
- `cleanup_socket_state` 在连接关闭时清理映射和发送锁，防止内存泄漏

## Risks / Trade-offs

### R1: 标准库 WebSocket 实现的稳定性

**风险**: 自行实现 WebSocket 协议可能存在边界情况未覆盖
**缓解**:
- 仅实现最小子集（text frame + ping/pong + close），降低复杂度
- 本项目消息体小（JSON，通常 < 1KB），不需要分片
- 如果后续发现问题，可随时切换到 `simple-websocket`（同步模型、Python 3.6+ 兼容）作为 fallback

### R2: WebSocket 连接稳定性

**风险**: 网络波动导致 WS 连接断开，期间消息丢失
**缓解**:
- 客户端实现指数退避重连（带随机 jitter 防止惊群）
- 路由层自动 fallback 到 HTTP（如果该用户有 HTTP 绑定）
- 客户端定时 ping 保活，及时检测断连

### R3: 企业防火墙阻断

**风险**: 某些企业网络环境可能阻断 WebSocket
**缓解**:
- 保留 HTTP 模式作为备选
- WebSocket 走的是 HTTP Upgrade（同端口），比独立 WS 端口更容易通过防火墙
- 用户可根据网络环境选择模式

### R4: 网关重启导致所有连接断开

**风险**: 网关升级/重启时，所有 WS 连接断开
**缓解**:
- 网关优雅关闭时发送 `{"type":"shutdown"}` 通知，客户端可区分计划维护和网络故障
- 客户端自动重连（带 jitter：`delay * (0.5 + random() * 0.5)`，防止惊群效应）
- 短暂中断，重连后恢复正常

### R5: pending 连接资源占用

**风险**: 首次注册时 pending 连接等待用户授权（可能数分钟），期间占用线程和 socket
**缓解**:
- 双重超时机制：
  - 90 秒无活动（客户端离线）自动断开
  - 10 分钟未授权（用户忘记或恶意）自动断开
- 清理任务每 30 秒检查一次，及时释放资源
- 同一 owner_id 新 pending 连接替换旧 pending 连接
- pending 连接数量有限（等于活跃用户数）

### R6: 线程资源占用

**风险**: 每个 WS 连接占用一个线程，连接数多时线程数增长
**缓解**:
- 本项目是团队内部工具，并发连接数预计 < 50
- Python 线程轻量（~8MB 栈空间），50 个连接约 400MB，可接受
- 与现有 `ThreadedHTTPServer` 模型一致

## Migration Plan

### Phase 1: 实现共存模式（本次）

1. 新增 `ws_protocol.py` 最小 WebSocket 协议实现
2. 新增 WS 连接注册表和隧道逻辑
3. 修改路由层支持双模式
4. 新增配置项
5. 文档更新

### Phase 2: 验证和推广（后续）

1. 内部测试验证稳定性
2. 更新部署文档，引导本地用户使用 WS 模式
3. 收集反馈，优化体验

### Phase 3: 考虑统一（未来，可选）

1. 如果 WS 足够稳定，可考虑默认推荐 WS
2. HTTP 保留作为 fallback

## Open Questions

1. ~~**心跳间隔**: 30s 是否合适？~~ → **已确定**: 30s ping 间隔 + 90s 服务端 read timeout（3 倍 ping 间隔）

2. ~~**连接超时**: 请求转发后多久算超时？~~ → **已确定**: 10s（`REQUEST_TIMEOUT`），与现有 HTTP 超时一致

3. **标准库实现后续升级**: 如果标准库实现遇到问题，是否切换到 `simple-websocket`？
   - **当前方案**: 是。`simple-websocket` 作为备选方案，API 兼容性好，切换成本低

4. **IPv6 支持**: 当前客户端连接仅支持 IPv4（`socket.AF_INET`），暂不支持 IPv6 地址
   - **当前方案**: 暂不支持，后续按需添加
