# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added - 2026-01-27

#### 权限请求卡片会话信息 (permission-card-session-info)

- 权限请求卡片新增会话信息显示
- 显示 session_id 前 8 位，便于区分不同会话的权限请求
- 更新 `permission-card.json` 和 `permission-card-static.json` 模板

### Fixed - 2026-01-26

#### 用户响应时连接状态检测 (socket-state-realtime-check)

- 修复用户点击按钮响应时可能因清理线程延迟而导致响应失败的问题
- 用户点击按钮时实时检测 socket 连接状态，不再依赖后台清理线程的延迟检测
- 确保用户响应时能立即获得准确的连接状态

### Added - 2026-01-26

#### Stop 事件完成通知 (stop-event-notification)

- 新增 `src/hooks/stop.sh` 独立 Stop 事件处理器
- 从 transcript 文件中提取 Claude 最终响应内容
- 支持显示会话标识（session slug）
- 新增 `STOP_MESSAGE_MAX_LENGTH` 配置（默认 2000 字符）
- 新增 `stop-card.json` 飞书卡片模板
- 任务完成后自动发送飞书通知，包含 Claude 响应摘要
- `src/hooks/webhook.sh` 重构：移除内联飞书卡片，统一使用 `feishu.sh` 函数
- `install.sh` 更新：同时配置 PermissionRequest 和 Stop 两个事件的 Hook

#### 飞书 @所有人配置 (feishu-at-all-config)

- 新增 `FEISHU_AT_ALL` 环境变量配置（默认 `false`）
- 权限通知消息可通过配置决定是否 `@所有人`
- 设为 `true` 时在消息开头添加 `<at id=all></at>`

#### 权限通知延迟发送 (permission-notify-delay)

- 新增 `PERMISSION_NOTIFY_DELAY` 环境变量配置（默认 60 秒）
- 支持在权限请求后延迟指定秒数再发送飞书通知
- 延迟期间用户在终端响应时，自动取消通知发送（Claude Code 会 SIGKILL 终止 hook）
- 延迟期间每秒检测父进程状态，父进程退出时跳过发送
- 用途：避免快速连续请求时的消息轰炸

### Added - 2026-01-23

#### VSCode 自动跳转 (add-vscode-redirect)

- 点击飞书卡片按钮后，自动跳转到 VSCode 并聚焦到项目目录
- 新增 `VSCODE_URI_PREFIX` 环境变量配置:
  - 支持本地开发: `vscode://file`
  - 支持 SSH Remote: `vscode://vscode-remote/ssh-remote+server`
  - 支持 WSL: `vscode://vscode-remote/wsl+Ubuntu`
- 响应页面增强:
  - 显示"正在跳转到 VSCode..."提示
  - 跳转失败时显示手动打开链接和 VSCode 设置提示
  - 根据本地/远程自动显示对应的配置项（`security.promptForLocalFileProtocolHandling` / `security.promptForRemoteFileProtocolHandling`）
- 未配置 `VSCODE_URI_PREFIX` 时保持原有行为（不跳转）

### Added - 2026-01-20

#### 飞书卡片子模板抽象化 (飞书卡片模板化增强)

- 新增子模板系统,支持模块化的卡片元素组合:
  - `command-detail-bash.json` - Bash 命令详情元素模板
  - `command-detail-file.json` - 文件操作详情元素模板 (Edit/Write/Read)
  - `description-element.json` - 操作描述元素模板
- 新增 `render_sub_template()` 函数,支持渲染独立子模板
- 重构 `build_permission_card()` 函数:
  - 根据工具类型自动选择对应的子模板
  - 支持 Bash、Edit、Write、Read 等不同工具类型
  - 动态组合命令详情和描述元素
- 统一配置管理:
  - 更新 `config/tools.json` 的 `detail_template`,只返回纯值不包含标签
  - 同步更新 `shell-lib/tool.sh` 内置逻辑
  - 同步更新 `server/models/tool_config.py` 内置配置
- 优化代码规范:
  - 规范化 `shell-lib/feishu.sh` 代码和注释
  - 统一函数文档格式
  - 改进代码组织结构

**优势**:
- 更高复用性: 命令详情、描述等元素可独立复用
- 更易扩展: 新增工具类型只需添加对应子模板
- 配置统一: Shell 脚本和 Python 服务器使用相同配置
- 代码清晰: 模板职责明确,便于维护

### Changed - 2026-01-20

#### 配置文件更新

- `config/tools.json`:
  - 所有工具的 `detail_template` 改为只返回纯值
  - 移除模板中的标签 (如"**命令：**"、"**文件：**")
  - 标签由飞书卡片子模板负责添加
- `shell-lib/tool.sh`:
  - 内置逻辑改为只返回纯值
  - 简化转义处理
- `server/models/tool_config.py`:
  - 更新内置配置与 tools.json 保持一致
  - 更新 `format_detail()` 方法只返回纯值

### Added - 2026-01-19

#### 飞书卡片模板化 (extract-feishu-card-templates)

- 将飞书卡片的 JSON 构造逻辑从 Shell 脚本抽离为独立的模板文件
- 新增 `templates/feishu/` 目录,存放卡片模板:
  - `permission-card.json` - 权限请求卡片(交互模式)
  - `permission-card-static.json` - 权限请求卡片(静态模式)
  - `notification-card.json` - 通用通知卡片
  - `buttons.json` - 交互按钮配置
  - `README.md` - 模板使用说明和变量清单
- 新增模板渲染函数:
  - `validate_template()` - 验证模板文件 JSON 格式
  - `render_template()` - 核心模板渲染函数(支持变量替换和 JSON 转义)
  - `render_card_template()` - 卡片模板渲染包装函数
- 重构卡片构建函数使用模板:
  - `build_permission_card()` - 权限请求卡片
  - `build_notification_card()` - 通用通知卡片
  - `build_permission_buttons()` - 交互按钮
- 支持环境变量 `FEISHU_TEMPLATE_PATH` 自定义模板目录
- 移除硬编码的 JSON 字符串拼接逻辑

**优势**:
- 维护便利:直接编辑 JSON 模板即可更新卡片样式,无需修改代码
- 版本管理:模板独立存储,可轻松回滚或升级
- 扩展性强:新增卡片类型只需添加新模板文件
- 向后兼容:保持现有 API 接口不变

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
