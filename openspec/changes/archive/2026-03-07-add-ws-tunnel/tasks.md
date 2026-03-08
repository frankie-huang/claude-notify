# Implementation Tasks

## 1. 基础设施

- [x] 1.1 创建 `src/server/services/ws_protocol.py` - 最小 WebSocket 协议实现
  - 基于标准库 `socket` + `hashlib` + `struct` + `ssl`
  - 服务端握手：解析 Upgrade 请求、发送 101 响应
  - 客户端握手：发送 Upgrade 请求、验证响应（支持 `ws://` 和 `wss://`）
  - Text frame 收发（含客户端 masking，通过 `_WS_CLIENT_MODE_MAP` 追踪）
  - Ping/Pong frame 收发
  - Close frame 处理
  - 高级 API：`ws_recv_text`（自动处理控制帧）、`ws_close`（优雅关闭）、`cleanup_socket_state`
  - 安全防护：最大帧大小 10MB、握手响应大小 16KB

- [x] 1.2 修改 `config.py`：复用 `FEISHU_GATEWAY_URL` 自动检测协议模式（`FEISHU_GATEWAY_MODE`）

## 2. 网关侧 - WebSocket 服务端

- [x] 2.1 创建 `src/server/services/ws_registry.py` - WebSocket 连接注册表
  - 已认证连接管理：`register(owner_id, ws_conn, auth_token)`、`unregister`、`get`、`get_auth_token`、`is_authenticated`、`get_all_connections`
  - pending 连接管理：`add_pending`、`get_pending`、`remove_pending`、`promote_pending(owner_id, auth_token)`、`cleanup_expired_pending`、`cleanup_connection(owner_id, ws_conn)`
  - pending 连接双重超时：`WS_PENDING_INACTIVE_TIMEOUT`（90秒无活动）、`WS_PENDING_MAX_WAIT_TIME`（10分钟未授权）
  - pending 活动时间追踪：`update_pending_activity(owner_id)` 更新 `last_activity_time`
  - pending 暂存数据：`set/get_pending_auth_token`、`set/get_pending_binding_params`
  - 多 pending 共存：同一 owner_id 可有多个 pending 连接，最多 5 个（`WS_MAX_PENDING_PER_OWNER`）
  - 卡片冷却：同一 owner_id 在 60 秒内最多触发一次卡片发送（`WS_CARD_COOLDOWN`）
  - 原子授权操作：`prepare_authorization()` 单次加锁完成设置 token、绑定参数、清理其他 pending
  - 请求-响应匹配：`send_request(owner_id, path, body, headers, timeout)` + `handle_response`（threading.Event 同步等待）
  - per-connection 发送锁（`_send_locks`）防止帧交错
  - 连接替换时发送 `replaced` 通知
  - 线程安全（`_connections_lock` + `_pending_lock` + `_request_lock`，不嵌套避免死锁）

- [x] 2.2 新增 `src/server/handlers/ws_handler.py` - WS 隧道处理器（从 http_handler 拆分）
  - `handle_ws_tunnel()`: 入口函数（握手 + 委托给 `_process_tunnel_connection`）
  - `_process_tunnel_connection()`: 等待 register 消息，通过 auth_token 比对区分续期/换绑/首次注册
  - `_ws_message_loop()`: 消息循环（response/auth_ok_ack/ping/close 处理）
  - `_handle_ws_message()`: 消息分发（response → registry、auth_ok_ack → promote + BindingStore 更新）
  - pending 状态消息更新活动时间（`update_pending_activity`）
  - 服务端 read timeout: 90s（pending 和 authenticated 统一）

- [x] 2.3 修改 `src/server/handlers/http_handler.py` - WS Upgrade 路由
  - `do_GET` 新增 `/ws/tunnel` 路由，委托给 `ws_handler.handle_ws_tunnel`

## 3. WS 内注册流程

- [x] 3.1 修改 `src/server/handlers/register.py` - 新增 WS 注册处理
  - 新增 `handle_ws_registration()`: 首次注册，发送飞书授权卡片
  - 新增 `handle_ws_rebind_registration()`: 换绑注册，展示新旧 IP 发送换绑卡片
  - 新增 `handle_ws_authorization_approved()`: 授权通过，生成 token，通过 WS 下发 `auth_ok`
    - BindingStore 更新延迟到 `auth_ok_ack`（在 ws_handler 消息循环中处理）
    - 暂存 auth_token 和绑定参数到 registry 的 `pending_auth_tokens`/`pending_binding_params`
  - 新增 `handle_ws_authorization_denied()`: 授权拒绝，发送 `auth_error` 并关闭连接

- [x] 3.2 修改飞书授权卡片
  - WS 模式的卡片不需要 `callback_url` 字段（没有 HTTP 回调地址）
  - 卡片 value 中新增 `mode: "ws"` 标记，区分 HTTP 和 WS 注册
  - 换绑卡片展示旧终端 IP 和新终端 IP，使用独立安全提示文案

## 4. Callback 侧 - WebSocket 客户端

- [x] 4.1 创建 `src/server/services/ws_tunnel_client.py` - WebSocket 客户端
  - 连接网关 WS 端点：URL 始终仅含 `owner_id`，auth_token 在 register 消息体中携带
  - 始终发送 register 消息（含 `owner_id`、`auth_token`（如有）、配置参数）
  - 处理 `auth_ok` 消息：存储 auth_token 到 AuthTokenStore，发送 `auth_ok_ack` 确认
  - 处理 `auth_error` 消息：记录错误，等待重试
  - 请求处理线程池：`ThreadPoolExecutor(max_workers=8)` 避免阻塞消息循环
  - 调用本地 HTTP handler（通过 `urllib.request` 请求 localhost，绕过系统代理）
  - 发送响应回网关（ws_protocol 层已内置 per-socket 发送锁）
  - 客户端心跳：30s 间隔发送 ping（**包括 pending 状态**，防止 nginx 等代理空闲超时）
  - 心跳线程安全：传入 socket 引用，通过 `self.sock is not conn_sock` 检测连接变更后自动退出
  - 断线重连：指数退避（初始 1s，最大 60s，因子 2.0）+ 随机 jitter（`delay * (0.5 + random() * 0.5)`）
  - 处理 `replaced` 消息：**永久停止**（running=False），不自动重连
  - 处理 `unbind` 消息：清除本地 auth_token，**永久停止**
  - 统一 stop action 处理：带 `action: "stop"` 的消息统一调用 `_stop_reconnect()`
  - 处理 `shutdown` 消息：立即重连（无退避）

- [x] 4.2 修改 `src/server/main.py` - 启动 WS 客户端和清理任务
  - `FEISHU_GATEWAY_MODE == 'ws'` 时启动 WS 客户端 daemon 线程
  - 新增 `cleanup_pending_loop()`：每 30 秒检查并清理超时的 pending 连接

## 5. 路由层 - 双模式分发

- [x] 5.1 修改 `src/server/handlers/feishu.py` - 路由分发逻辑
  - 创建 `_forward_via_ws_or_http()` 统一转发函数，接收 `binding` 字典（含 `_owner_id`、`callback_url`、`auth_token`）
  - 优先检查 `ws_registry` 中是否有活跃连接（`is_authenticated`）
  - 有则通过 `ws_registry.send_request()` 转发（同步等待响应），从 response 中提取 `body`
  - 否则 fallback 到 HTTP（排除 `ws://`/`wss://` 开头的 callback_url）
  - WS 转发失败时也 fallback 到 HTTP

- [x] 5.2 修改相关转发函数统一使用 `binding` 字典参数（替代独立的 `callback_url`/`auth_token`）
  - `_forward_permission_request`: 移除 callback_url 检查，改用 `_forward_via_ws_or_http`
  - `_forward_claude_request`: 签名改为接收 `binding`，移除 `callback_url`/`auth_token` 参数
  - `_forward_continue_request`: 同上
  - `_forward_new_request`: 同上
  - `_fetch_recent_dirs_from_callback`: 签名改为接收 `binding`
  - `_fetch_browse_dirs_from_callback`: 签名改为接收 `binding`
  - `_set_last_message_id_to_callback`: 签名改为接收 `binding`
  - `_send_session_result_notification`: 签名改为接收 `binding`
  - `handle_card_action_register`: 新增 WS 模式分支，调用 `handle_ws_authorization_approved`/`handle_ws_authorization_denied`

## 6. 优雅关闭

- [x] 6.1 修改 `src/server/main.py` - 网关优雅关闭
  - `KeyboardInterrupt` 时，向所有 WS 连接发送 `{"type":"shutdown"}`
  - 等待短暂时间后关闭连接

## 7. 测试与文档

- [x] 7.1 手动测试首次 WS 注册流程（无 auth_token → 飞书卡片 → 授权 → token 下发）
- [x] 7.2 手动测试 WS 重连认证（有 auth_token → 握手直接通过）
- [x] 7.3 手动测试首次注册被拒绝
- [x] 7.4 手动测试首次注册超时（90 秒无心跳或 10 分钟未授权）
- [x] 7.5 手动测试权限请求通过 WS 转发
- [x] 7.6 手动测试 Claude 会话通过 WS 转发
- [x] 7.7 手动测试断线重连 + jitter
- [x] 7.8 手动测试 HTTP fallback（WS 断开后降级）
- [x] 7.9 手动测试连接替换（同 owner_id 二次连接）
- [x] 7.10 更新部署文档 `docs/deploy/DEPLOYMENT_MODES.md`
- [x] 7.11 更新 README 配置说明

## Dependencies

- Task 2.x, 3.x, 4.x 依赖 Task 1.1, 1.2
- Task 2.2 (ws_handler) 依赖 Task 2.1（ws_registry）和 Task 3.1（register 函数）
- Task 3.x 依赖 Task 2.1（需要 ws_registry 的 pending 管理）
- Task 5.x 依赖 Task 2.x
- Task 6.x 依赖 Task 2.x
- Task 7.x 依赖 Task 1-6 全部完成
