# permission-notify Specification

## Purpose
TBD - created by archiving change add-permission-notify. Update Purpose after archive.
## Requirements
### Requirement: Permission Request Notification Script

系统 SHALL 提供 `permission-notify.sh` 脚本，当 Claude Code 发起权限请求时，通过飞书 Webhook 通知用户。

#### Scenario: Bash 命令权限请求通知

- **GIVEN** Claude Code 请求执行 Bash 命令的权限
- **WHEN** PermissionRequest hook 触发并调用 `permission-notify.sh`
- **THEN** 脚本从 stdin 读取 JSON 数据
- **AND** 解析出 `tool_name` 为 "Bash"，`tool_input.command` 为待执行命令
- **AND** 发送飞书卡片消息，包含命令内容

#### Scenario: 文件修改权限请求通知

- **GIVEN** Claude Code 请求修改文件的权限（Edit 或 Write）
- **WHEN** PermissionRequest hook 触发并调用 `permission-notify.sh`
- **THEN** 脚本从 stdin 读取 JSON 数据
- **AND** 解析出 `tool_name` 为 "Edit" 或 "Write"，`tool_input.file_path` 为目标文件
- **AND** 发送飞书卡片消息，包含文件路径信息

#### Scenario: 通用工具权限请求通知

- **GIVEN** Claude Code 请求使用其他工具的权限
- **WHEN** PermissionRequest hook 触发并调用 `permission-notify.sh`
- **THEN** 脚本从 stdin 读取 JSON 数据
- **AND** 发送飞书卡片消息，显示工具名称和基本请求信息

### Requirement: Feishu Card Message Format

通知消息 SHALL 使用飞书交互式卡片格式，包含以下信息：

#### Scenario: 卡片消息内容完整

- **GIVEN** 权限请求事件发生
- **WHEN** 发送飞书通知
- **THEN** 卡片标题显示 "Claude Code 权限请求"
- **AND** 卡片包含项目名称（从 `CLAUDE_PROJECT_DIR` 或 `cwd` 获取）
- **AND** 卡片包含请求时间戳
- **AND** 卡片包含工具类型（Bash/Edit/Write 等）
- **AND** 卡片包含请求详情（命令内容或文件路径）
- **AND** 卡片包含请求 ID（用于关联回调）
- **AND** 卡片包含操作提示（如 "请尽快操作以避免 Claude 超时"）
- **AND** 卡片包含 4 个操作按钮（批准/始终允许/拒绝/拒绝并中断）

### Requirement: Error Handling

脚本 SHALL 具备容错能力，确保不会阻塞 Claude Code 正常运行。脚本 SHALL 在无 jq 环境下使用原生 Linux 命令（grep、sed、awk）解析 JSON，功能与 jq 解析一致。**脚本 SHALL 通过统一的函数库实现 JSON 解析，避免重复代码。**

#### Scenario: 无 jq 环境下使用原生命令解析

- **GIVEN** 系统未安装 jq
- **WHEN** 脚本接收到 PermissionRequest hook 的 JSON 数据
- **THEN** `lib/json.sh` 中的 `json_get()` 函数自动使用 grep、sed 等原生命令解析 JSON
- **AND** 正确提取 `tool_name` 字段
- **AND** 正确提取 `tool_input` 中的嵌套字段（command、file_path、pattern 等）
- **AND** 通知内容与使用 jq 解析时完全一致

#### Scenario: jq 可用时优先使用

- **GIVEN** 系统已安装 jq
- **WHEN** 脚本接收到 JSON 数据
- **THEN** `lib/json.sh` 中的 `json_init()` 检测到 jq 可用
- **AND** `json_get()` 函数优先使用 jq 解析（更可靠）
- **AND** 不使用原生命令解析

#### Scenario: JSON 解析失败降级处理

- **GIVEN** stdin 输入的 JSON 格式无效或缺少必要字段
- **WHEN** 脚本尝试解析 JSON（无论使用 jq 还是原生命令）
- **THEN** 脚本发送降级通知消息，说明有权限请求但无法解析详情
- **AND** 脚本以退出码 0 结束，不阻塞 Claude Code

#### Scenario: Webhook 请求失败静默处理

- **GIVEN** 飞书 Webhook URL 不可达或返回错误
- **WHEN** `lib/feishu.sh` 中的 `send_feishu_card()` 尝试发送通知
- **THEN** 函数记录错误日志
- **AND** 脚本以退出码 0 结束
- **AND** 不影响 Claude Code 继续运行

### Requirement: Hook Configuration

用户 SHALL 能够通过标准的 Claude Code hooks 配置机制注册权限通知脚本。

#### Scenario: PermissionRequest Hook 配置

- **GIVEN** 用户希望在权限请求时收到通知并可远程控制
- **WHEN** 用户在 `.claude/settings.json` 中配置 PermissionRequest hook
- **THEN** 配置格式符合 Claude Code hooks 规范
- **AND** 可以使用 matcher 指定监听的工具类型（如 "Bash", "Edit|Write", "*"）
- **AND** hook 输入包含完整的 `tool_name` 和 `tool_input` 详情
- **AND** hook 超时配置为 60 秒（允许用户响应时间）

#### Scenario: 回调服务配置

- **GIVEN** 用户需要启用可交互权限控制
- **WHEN** 用户配置系统
- **THEN** 用户需要配置飞书 Webhook URL（`FEISHU_WEBHOOK_URL`）
- **AND** 用户需要启动回调服务
- **AND** 可选配置回调服务地址（`CALLBACK_SERVER_URL`，默认 `http://localhost:8080`）

### Requirement: Interactive Card Buttons

通知消息卡片 SHALL 包含可交互按钮（URL 跳转类型），支持用户直接控制权限请求。按钮行为与 Claude Code 终端权限操作保持一致。

#### Scenario: 卡片包含批准按钮

- **GIVEN** 权限请求卡片发送成功
- **WHEN** 用户查看卡片
- **THEN** 卡片包含"批准运行"按钮
- **AND** 按钮配置为 URL 跳转类型
- **AND** URL 为 `{CALLBACK_SERVER_URL}/allow?id={request_id}`

#### Scenario: 卡片包含始终允许按钮

- **GIVEN** 权限请求卡片发送成功
- **WHEN** 用户查看卡片
- **THEN** 卡片包含"始终允许"按钮
- **AND** 按钮配置为 URL 跳转类型
- **AND** URL 为 `{CALLBACK_SERVER_URL}/always?id={request_id}`

#### Scenario: 卡片包含拒绝按钮

- **GIVEN** 权限请求卡片发送成功
- **WHEN** 用户查看卡片
- **THEN** 卡片包含"拒绝运行"按钮
- **AND** URL 为 `{CALLBACK_SERVER_URL}/deny?id={request_id}`

#### Scenario: 卡片包含拒绝并中断按钮

- **GIVEN** 权限请求卡片发送成功
- **WHEN** 用户查看卡片
- **THEN** 卡片包含"拒绝并中断"按钮
- **AND** URL 为 `{CALLBACK_SERVER_URL}/interrupt?id={request_id}`

### Requirement: HTTP Callback Server

系统 SHALL 提供 HTTP 回调服务，接收飞书卡片按钮的 URL 跳转请求，并将用户决策传递给 permission-notify.sh。

#### Scenario: 服务启动并监听

- **GIVEN** 回调服务配置完成
- **WHEN** 启动回调服务
- **THEN** 服务监听 HTTP 端口（默认 8080）
- **AND** 服务监听 Unix Domain Socket `/tmp/claude-permission.sock`
- **AND** 服务记录启动日志

#### Scenario: 接收批准请求

- **GIVEN** 回调服务正在运行
- **AND** 存在待处理的权限请求 ID
- **WHEN** 用户点击"批准运行"按钮，浏览器访问 `/allow?id={request_id}`
- **THEN** 服务验证请求 ID 有效
- **AND** 将 `allow` 决策发送给对应的等待进程
- **AND** 返回确认页面给浏览器
- **AND** 使请求 ID 失效（防止重复操作）

#### Scenario: 接收始终允许请求

- **GIVEN** 回调服务正在运行
- **AND** 存在待处理的权限请求 ID
- **WHEN** 用户点击"始终允许"按钮，浏览器访问 `/always?id={request_id}`
- **THEN** 服务验证请求 ID 有效
- **AND** 将 `allow` 决策发送给对应的等待进程
- **AND** 根据工具类型生成权限规则（如 `Bash(npm run build)`）
- **AND** 将规则写入项目的 `.claude/settings.local.json`
- **AND** 返回确认页面给浏览器

#### Scenario: 请求 ID 关联

- **GIVEN** 回调服务管理多个待处理的权限请求
- **WHEN** 收到 HTTP 请求
- **THEN** 服务根据请求 ID 定位对应的等待进程
- **AND** 将决策传递给正确的进程

### Requirement: Always Allow Rule Persistence

系统 SHALL 在用户点击"始终允许"时，将权限规则持久化到项目配置。

#### Scenario: 写入 Bash 命令规则

- **GIVEN** 用户点击"始终允许"
- **AND** 权限请求为 Bash 工具，命令为 `npm run build`
- **WHEN** 回调服务处理请求
- **THEN** 服务读取项目的 `.claude/settings.local.json`（不存在则创建）
- **AND** 在 `permissions.allow` 数组中添加 `Bash(npm run build)`
- **AND** 保存文件

#### Scenario: 写入文件操作规则

- **GIVEN** 用户点击"始终允许"
- **AND** 权限请求为 Edit 工具，文件路径为 `/path/to/file.js`
- **WHEN** 回调服务处理请求
- **THEN** 服务在 `permissions.allow` 数组中添加 `Edit(/path/to/file.js)`

### Requirement: Permission Script Integration

permission-notify.sh 脚本 SHALL 与回调服务协作，等待用户通过飞书卡片做出决策，并将决策返回给 Claude Code。

#### Scenario: 脚本发起请求并等待响应

- **GIVEN** Claude Code 触发 PermissionRequest hook
- **WHEN** permission-notify.sh 执行
- **THEN** 脚本生成唯一请求 ID（格式：`{timestamp}-{uuid[:8]}`）
- **AND** 通过 Unix Socket 将请求发送给回调服务
- **AND** 阻塞等待用户响应（最长 55 秒）

#### Scenario: 返回批准决策

- **GIVEN** 脚本正在等待用户响应
- **WHEN** 用户点击"批准运行"按钮
- **THEN** 脚本收到回调服务的通知
- **AND** 脚本输出 `{"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": {"behavior": "allow"}}}`
- **AND** 脚本以退出码 0 结束

#### Scenario: 返回拒绝决策

- **GIVEN** 脚本正在等待用户响应
- **WHEN** 用户点击"拒绝运行"按钮
- **THEN** 脚本输出 `{"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": {"behavior": "deny", "message": "用户通过飞书拒绝"}}}`
- **AND** 脚本以退出码 0 结束

#### Scenario: 返回拒绝并中断决策

- **GIVEN** 脚本正在等待用户响应
- **WHEN** 用户点击"拒绝并中断"按钮
- **THEN** 脚本输出 `{"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": {"behavior": "deny", "message": "用户通过飞书拒绝并中断", "interrupt": true}}}`
- **AND** 脚本以退出码 0 结束

### Requirement: Connection-Based Request Validity

系统 SHALL 基于实际连接状态处理请求有效性，而非人为设定的超时时间。请求有效性完全由 Claude Code 与回调服务之间的 socket 连接状态决定。

#### Scenario: 客户端超时导致连接断开

- **GIVEN** 权限请求卡片已发送
- **WHEN** Claude Code hook 等待超时导致 socket 连接断开
- **THEN** permission-notify.sh 因 socat 超时返回 `{"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": {"behavior": "deny", "message": "权限请求超时，自动拒绝"}}}`

#### Scenario: 连接断开后按钮点击处理

- **GIVEN** Claude Code 已不再等待（socket 连接已断开）
- **WHEN** 用户之后点击按钮访问 URL
- **THEN** 回调服务返回"连接已断开，Claude 可能已继续执行其他操作"页面

#### Scenario: 长时间等待后点击仍有效

- **GIVEN** 权限请求卡片已发送
- **AND** Claude Code 仍在等待用户响应（socket 连接保持）
- **WHEN** 用户在任意时间点击按钮
- **THEN** 回调服务正常处理请求
- **AND** 将决策发送给 Claude Code

#### Scenario: 请求已被处理后再次点击

- **GIVEN** 权限请求已被用户处理（批准/拒绝）
- **WHEN** 用户再次点击按钮访问 URL
- **THEN** 回调服务返回"请求已被处理"页面
- **AND** 显示之前的处理结果（如"已批准"）

### Requirement: Graceful Degradation

系统 SHALL 在回调服务不可用时降级为仅通知模式。

#### Scenario: 服务不可用时降级

- **GIVEN** 回调服务未启动或 Socket 连接失败
- **WHEN** permission-notify.sh 执行
- **THEN** 脚本检测到服务不可用
- **AND** 脚本使用原有 Webhook 方式发送通知（不含交互按钮）
- **AND** 脚本不返回决策（让用户在终端操作）
- **AND** 脚本以退出码 0 结束

### Requirement: Response Page

回调服务 SHALL 在用户点击按钮后返回确认页面。

#### Scenario: 显示操作成功页面

- **GIVEN** 用户点击按钮且请求 ID 有效
- **WHEN** 回调服务处理完成
- **THEN** 返回 HTML 页面显示"操作成功"
- **AND** 页面显示操作类型（如"已批准运行"）

#### Scenario: 显示请求无效页面

- **GIVEN** 用户访问的请求 ID 不存在
- **WHEN** 回调服务处理请求
- **THEN** 返回 HTML 页面显示"请求不存在或已被清理"

#### Scenario: 显示连接已断开页面

- **GIVEN** 用户访问的请求 ID 对应的 socket 连接已断开
- **WHEN** 回调服务处理请求
- **THEN** 返回 HTML 页面显示"连接已断开，Claude 可能已继续执行其他操作"

#### Scenario: 显示重复操作页面

- **GIVEN** 用户访问的请求 ID 已被处理
- **WHEN** 回调服务处理请求
- **THEN** 返回 HTML 页面显示"请求已被{批准/拒绝}，请勿重复操作"

### Requirement: Shell Script Modular Architecture

系统 SHALL 采用模块化架构组织 Shell 脚本代码，将复用逻辑抽离为独立的函数库。

#### Scenario: JSON 解析函数库

- **GIVEN** 系统需要解析 JSON 数据
- **WHEN** 任何 Shell 脚本需要读取 JSON 字段
- **THEN** 脚本引用 `lib/json.sh` 函数库
- **AND** 使用统一的 `json_get()` 函数获取字段值
- **AND** 函数内部自动选择可用的解析工具（jq > python3 > grep/sed）
- **AND** 调用方无需关心具体解析实现

#### Scenario: 飞书卡片函数库

- **GIVEN** 系统需要发送飞书通知
- **WHEN** 需要构建飞书卡片消息
- **THEN** 脚本引用 `lib/feishu.sh` 函数库
- **AND** 使用 `build_permission_card()` 构建权限请求卡片
- **AND** 使用 `send_feishu_card()` 发送卡片
- **AND** 交互式和降级模式复用相同的卡片模板

#### Scenario: 工具详情函数库

- **GIVEN** 系统需要格式化不同工具类型的请求详情
- **WHEN** 需要提取 Bash/Edit/Write/Read 等工具的参数
- **THEN** 脚本引用 `lib/tool.sh` 函数库
- **AND** 使用 `extract_tool_detail()` 获取格式化的详情内容
- **AND** 新增工具类型仅需修改配置数组，无需改动提取逻辑

#### Scenario: 日志函数库

- **GIVEN** 系统需要记录日志
- **WHEN** 任何脚本需要输出日志
- **THEN** 脚本引用 `lib/log.sh` 函数库
- **AND** 使用统一的 `log()` 函数记录日志
- **AND** 日志自动包含时间戳和调用位置

### Requirement: Python Service Modular Architecture

系统 SHALL 采用模块化架构组织 Python 服务代码，实现关注点分离。

#### Scenario: HTTP 处理器模块分离

- **GIVEN** 回调服务需要处理 HTTP 请求
- **WHEN** 用户点击飞书卡片按钮
- **THEN** 请求由 `handlers/callback.py` 模块处理
- **AND** 处理器仅负责路由和参数解析
- **AND** 业务逻辑委托给 services 层

#### Scenario: 请求管理服务模块

- **GIVEN** 系统需要管理待处理的权限请求
- **WHEN** permission-notify.sh 发起请求
- **THEN** 请求由 `services/request_manager.py` 管理
- **AND** 模块负责请求注册、状态跟踪、连接管理
- **AND** 与 HTTP 处理器解耦

#### Scenario: 规则写入服务模块

- **GIVEN** 用户点击"始终允许"按钮
- **WHEN** 系统需要写入权限规则
- **THEN** 规则由 `services/rule_writer.py` 模块处理
- **AND** 模块负责规则格式化和文件写入
- **AND** 与请求管理模块解耦

#### Scenario: 决策模型独立

- **GIVEN** 系统需要构造决策响应
- **WHEN** 需要返回 allow/deny 决策
- **THEN** 使用 `models/decision.py` 中的 Decision 类
- **AND** 类提供 `allow()` 和 `deny()` 工厂方法
- **AND** 决策格式符合 Claude Code Hook 规范

### Requirement: Tool Type Configuration

系统 SHALL 使用配置驱动的方式管理工具类型，支持灵活扩展。

#### Scenario: 工具类型配置集中管理

- **GIVEN** 系统支持多种工具类型（Bash, Edit, Write, Read, Glob, Grep 等）
- **WHEN** 需要处理特定工具的权限请求
- **THEN** 工具类型的颜色、字段映射、规则格式集中配置
- **AND** 新增工具类型仅需添加配置项
- **AND** 无需修改核心处理逻辑

#### Scenario: Shell 脚本工具配置

- **GIVEN** permission-notify.sh 需要处理工具详情
- **WHEN** 提取工具参数用于显示
- **THEN** 使用 `lib/tool.sh` 中的配置数组
- **AND** `TOOL_COLORS` 映射工具类型到卡片颜色
- **AND** `TOOL_FIELDS` 映射工具类型到参数字段名

#### Scenario: Python 服务工具配置

- **GIVEN** 回调服务需要生成权限规则
- **WHEN** 用户点击"始终允许"
- **THEN** 使用 `RULE_FORMATTERS` 字典生成规则字符串
- **AND** 新增工具类型仅需添加格式化函数

### Requirement: VSCode Auto Redirect Configuration

系统 SHALL 支持通过环境变量配置 VSCode 自动跳转功能。

#### Scenario: 配置 VSCode Remote 前缀

- **GIVEN** 用户在 `.env` 文件中配置 `VSCODE_URI_PREFIX`
- **WHEN** 回调服务启动
- **THEN** 服务读取该配置
- **AND** 配置值为 VSCode URI 前缀（如 `vscode://vscode-remote/ssh-remote+server`）
- **AND** 不包含项目路径部分

#### Scenario: 未配置时禁用跳转

- **GIVEN** 用户未配置 `VSCODE_URI_PREFIX` 环境变量
- **WHEN** 用户点击飞书卡片按钮并处理完成
- **THEN** 响应页面显示操作结果
- **AND** 不执行 VSCode 跳转
- **AND** 保持当前的自动关闭页面行为

### Requirement: Notification Delay

系统 SHALL 支持配置权限通知延迟发送，避免快速连续请求时的消息轰炸。

#### Scenario: 配置延迟时间

- **GIVEN** 用户在 `.env` 文件中配置 `PERMISSION_NOTIFY_DELAY=3`
- **WHEN** permission-notify.sh 收到权限请求
- **THEN** 脚本等待 3 秒后再发送飞书通知
- **AND** 默认值为 0（立即发送）

#### Scenario: 延迟期间用户终端响应

- **GIVEN** 用户配置了通知延迟（如 3 秒）
- **AND** 权限请求正在延迟等待中
- **WHEN** 用户在终端选择 yes/no 响应权限请求
- **THEN** Claude Code 发送 SIGKILL 终止 hook 进程
- **AND** 飞书通知不会发送

#### Scenario: 延迟期间父进程退出

- **GIVEN** 用户配置了通知延迟
- **AND** 权限请求正在延迟等待中
- **WHEN** 用户通过 Ctrl+C 中断 Claude Code
- **THEN** 脚本检测到父进程退出
- **AND** 脚本跳过发送飞书通知
- **AND** 脚本以退出码 1 结束

#### Scenario: 延迟完成后正常发送

- **GIVEN** 用户配置了通知延迟（如 3 秒）
- **AND** 权限请求正在延迟等待中
- **WHEN** 延迟时间结束且用户未响应
- **THEN** 脚本正常发送飞书通知
- **AND** 继续后续的交互流程

### Requirement: Response Page VSCode Redirect

回调服务响应页面 SHALL 在配置启用时自动跳转到 VSCode。

#### Scenario: 操作成功后跳转 VSCode

- **GIVEN** 用户已配置 `VSCODE_URI_PREFIX`
- **AND** 权限请求包含有效的项目路径（`project_dir`）
- **WHEN** 用户点击飞书卡片按钮（批准/拒绝/始终允许/拒绝并中断）
- **AND** 回调服务成功处理决策
- **THEN** 响应页面显示操作成功信息
- **AND** 页面在短暂延迟（约 500ms）后自动跳转到 VSCode
- **AND** VSCode URI 格式为 `{VSCODE_URI_PREFIX}{project_dir}`

#### Scenario: 跳转后聚焦终端

- **GIVEN** VSCode 跳转成功执行
- **WHEN** VSCode 打开项目
- **THEN** 用户可以在 VSCode 中查看 Claude Code 终端的执行结果
- **AND** 终端保持之前的聚焦状态（依赖用户的 VSCode 布局设置）

#### Scenario: 操作失败时不跳转

- **GIVEN** 用户已配置 `VSCODE_URI_PREFIX`
- **WHEN** 回调服务处理决策失败（请求无效、连接断开等）
- **THEN** 响应页面显示错误信息
- **AND** 不执行 VSCode 跳转

#### Scenario: 页面显示跳转提示

- **GIVEN** 用户已配置 `VSCODE_URI_PREFIX`
- **AND** 决策处理成功
- **WHEN** 响应页面加载
- **THEN** 页面显示"正在跳转到 VSCode..."的提示信息
- **AND** 用户可以看到跳转即将发生

#### Scenario: 跳转失败时显示手动链接

- **GIVEN** 用户已配置 `VSCODE_URI_PREFIX`
- **AND** 决策处理成功
- **AND** 页面尝试跳转到 VSCode
- **WHEN** 跳转超时（页面仍未离开，如 2 秒后）
- **THEN** 页面显示"跳转失败"的错误提示
- **AND** 页面显示可点击的 VSCode URI 链接
- **AND** 用户可以手动点击链接打开 VSCode

### Requirement: OpenAPI Message Sending Mode

系统 SHALL 支持通过飞书 OpenAPI 发送消息，作为 Webhook 的替代或补充方式。**分离部署下，消息发送统一通过飞书网关。**

#### Scenario: Webhook 模式（默认）

- **GIVEN** 用户配置 `FEISHU_SEND_MODE=webhook` 或未配置该变量
- **AND** 未配置 `FEISHU_GATEWAY_URL`
- **WHEN** 系统需要发送飞书消息
- **THEN** 使用 `FEISHU_WEBHOOK_URL` 通过 Webhook 发送
- **AND** 不需要配置应用凭证

#### Scenario: OpenAPI 模式（单机）

- **GIVEN** 用户配置 `FEISHU_SEND_MODE=openapi`
- **AND** 未配置 `FEISHU_GATEWAY_URL`
- **AND** 配置了 `FEISHU_APP_ID` 和 `FEISHU_APP_SECRET`
- **AND** 配置了 `FEISHU_RECEIVE_ID`
- **WHEN** 系统需要发送飞书消息
- **THEN** 通过飞书 OpenAPI 发送消息到指定接收者
- **AND** 自动管理 access_token（2小时有效期，提前5分钟刷新）

#### Scenario: 分离部署

- **GIVEN** 用户配置了 `FEISHU_GATEWAY_URL`
- **WHEN** 系统需要发送飞书消息
- **THEN** POST 请求到 `${FEISHU_GATEWAY_URL}/feishu/send`
- **AND** 网关负责实际的消息发送
- **AND** Callback 服务无需配置飞书凭证

#### Scenario: 接收者类型自动检测

- **GIVEN** 用户配置了 `FEISHU_RECEIVE_ID` 但未配置 `FEISHU_RECEIVE_ID_TYPE`
- **WHEN** 系统需要确定接收者类型
- **THEN** 根据 ID 前缀自动检测：`ou_` 为 open_id，`oc_` 为 chat_id，`on_` 为 union_id，包含 `@` 为 email，其他为 user_id

### Requirement: Feishu Send HTTP Endpoint

回调服务 SHALL 提供 `/feishu/send` HTTP 端点，支持通过 OpenAPI 发送飞书消息。

#### Scenario: 发送卡片消息

- **GIVEN** 回调服务正在运行
- **AND** 飞书 OpenAPI 服务已初始化
- **WHEN** 收到 POST `/feishu/send` 请求，body 包含 `{"msg_type": "interactive", "content": {...}}`
- **THEN** 通过 OpenAPI 发送卡片消息到配置的接收者
- **AND** 返回 `{"success": true, "message_id": "..."}` 或 `{"success": false, "error": "..."}`

#### Scenario: 发送文本消息

- **GIVEN** 回调服务正在运行
- **AND** 飞书 OpenAPI 服务已初始化
- **WHEN** 收到 POST `/feishu/send` 请求，body 包含 `{"msg_type": "text", "content": "..."}`
- **THEN** 通过 OpenAPI 发送文本消息到配置的接收者

#### Scenario: 服务未启用时拒绝请求

- **GIVEN** 飞书 OpenAPI 服务未初始化（缺少凭证配置）
- **WHEN** 收到 POST `/feishu/send` 请求
- **THEN** 返回 `{"success": false, "error": "Feishu API service not enabled"}`

### Requirement: 飞书网关分离部署支持

系统 SHALL 支持将飞书网关与 Callback 服务分离部署，通过 `FEISHU_GATEWAY_URL` 配置启用分离部署。

#### Scenario: 检测分离部署

- **GIVEN** 用户配置了 `FEISHU_GATEWAY_URL` 环境变量
- **WHEN** permission.sh 初始化
- **THEN** 系统启用分离部署
- **AND** 消息发送使用 `${FEISHU_GATEWAY_URL}/feishu/send`
- **AND** 按钮 value 中包含 `callback_url: ${CALLBACK_SERVER_URL}`

#### Scenario: 未配置时使用单机模式

- **GIVEN** 用户未配置 `FEISHU_GATEWAY_URL`
- **WHEN** permission.sh 初始化
- **THEN** 系统使用原有的单机模式逻辑
- **AND** 根据 `FEISHU_SEND_MODE` 决定消息发送方式

### Requirement: 卡片按钮携带 Callback URL

飞书卡片按钮的 value MUST 包含 `callback_url` 字段，用于飞书网关路由决策请求。

#### Scenario: 按钮 value 包含 callback_url

- **GIVEN** 系统需要发送权限请求卡片
- **WHEN** 构建按钮 JSON
- **THEN** 每个按钮的 `value` 包含 `callback_url` 字段
- **AND** `callback_url` 值为 `${CALLBACK_SERVER_URL}`

#### Scenario: 向后兼容

- **GIVEN** 飞书网关未配置或使用旧版本
- **WHEN** 网关直接处理 card.action.trigger 事件
- **THEN** 网关可以忽略 `callback_url` 字段
- **AND** 直接使用本地决策处理逻辑

