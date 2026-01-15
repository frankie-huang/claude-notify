# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added - 2026-01-15

#### 可交互权限控制 (add-interactive-permission-control)

- 实现飞书卡片按钮交互，用户可直接在飞书中批准/拒绝权限请求
- 新增回调服务 (`callback-server/server.py`)，通过 HTTP 接收按钮操作
- 使用 Unix Domain Socket 实现进程间通信
- 支持四种操作：
  - 批准运行 (allow)
  - 始终允许 (allow + 持久化规则)
  - 拒绝运行 (deny)
  - 拒绝并中断 (deny + interrupt)
- "始终允许"功能自动写入权限规则到 `.claude/settings.local.json`
- 实现降级模式：回调服务不可用时仅发送通知

#### 移除服务器端超时 (remove-server-timeout)

- 移除人为的服务器端 TTL 超时机制
- 请求有效性完全由 socket 连接状态决定
- 改进错误提示，区分"已被处理"和"连接已断开"
- 清理机制改为基于连接状态而非时间

#### 移除 jq 依赖 (remove-jq-dependency)

- 实现使用 grep/sed/awk 等原生命令解析 JSON
- 优先使用 jq（如可用），否则回退到原生命令
- 降低系统依赖要求

### Fixed

- 修复 socket 通信中的 half-close 问题
- 改进 base64 编码传输以处理特殊字符
- 修复管道数据传递问题（从 heredoc 改为管道）

### Technical - 2026-01-15

#### 服务器端统一超时控制 (server-side-timeout-control)

- **移除客户端超时**:
  - `socket-client.py` 不再设置超时，改为无限等待服务器响应
  - 移除 `PERMISSION_TIMEOUT` 环境变量
  - 客户端等待服务器主动关闭连接

- **服务器端可配置超时**:
  - 新增 `REQUEST_TIMEOUT` 环境变量（默认: 300 秒）
  - 设为 0 可完全禁用超时清理
  - 清理线程定期检查并关闭超时的 pending 请求
  - 超时后主动关闭 socket 连接，客户端收到后返回 deny

- **优势**:
  - 服务器端统一管理超时策略
  - 避免客户端和服务器超时不一致问题
  - 更灵活的配置（禁用/调整超时时间）

#### 增强调试和日志功能 (enhance-debug-logging)

- **日志系统增强**:
  - 添加文件日志输出 (`log/callback_YYYYMMDD.log`)
  - 毫秒级时间戳格式
  - DEBUG 级别详细日志
  - Socket 客户端独立调试日志 (`/tmp/socket-client-debug.log`)

- **Socket 通信改进**:
  - 服务器端接收超时设置（5 秒），避免永久阻塞
  - 详细的时间跟踪（总耗时、等待耗时、读取耗时）
  - Socket 连接状态检查和日志记录
  - 长度前缀协议的详细传输日志

- **错误处理增强**:
  - 添加异常 traceback 输出
  - 区分不同类型的连接错误
  - 更精确的错误信息（包括耗时信息）

- **数据传递修复**:
  - 将 heredoc (`<<<`) 改为管道 (`echo |`) 传递
  - 添加进程退出码记录
  - stderr 重定向到日志以便调试

### Technical Details

**项目架构**:
```
Claude Code → PermissionRequest hook
    ↓
permission-notify.sh
    ↓ (Unix Socket)
callback-server (Python HTTP)
    ↓ (HTTP POST)
飞书 Webhook
    ↓ (用户点击按钮)
callback-server (接收回调)
    ↓ (Unix Socket)
permission-notify.sh
    ↓ (JSON output)
Claude Code
```

**环境变量**:
- `FEISHU_WEBHOOK_URL` - 飞书 Webhook URL（必需）
- `CALLBACK_SERVER_URL` - 回调服务外部访问地址（默认: http://localhost:8080）
- `CALLBACK_SERVER_PORT` - HTTP 服务端口（默认: 8080）
- `PERMISSION_SOCKET_PATH` - Unix Socket 路径（默认: /tmp/claude-permission.sock）
- `REQUEST_TIMEOUT` - 服务器端超时秒数（默认: 300，设为 0 禁用）

**依赖**:
- 可交互模式: socat, python3, curl
- 降级模式: curl (可选 jq)
