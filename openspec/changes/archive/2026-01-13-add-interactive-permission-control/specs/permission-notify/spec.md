## ADDED Requirements

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

### Requirement: Timeout Handling

系统 SHALL 处理用户未在超时时间内响应的情况。

#### Scenario: 请求超时自动拒绝

- **GIVEN** 权限请求卡片已发送
- **WHEN** 用户 55 秒内未点击任何按钮
- **THEN** 脚本自动返回 `{"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": {"behavior": "deny", "message": "权限请求超时，自动拒绝"}}}`

#### Scenario: 超时后按钮点击处理

- **GIVEN** 权限请求已超时
- **WHEN** 用户之后点击按钮访问 URL
- **THEN** 回调服务返回"请求已过期"页面

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

- **GIVEN** 用户访问的请求 ID 不存在或已过期
- **WHEN** 回调服务处理请求
- **THEN** 返回 HTML 页面显示"请求无效或已过期"

## MODIFIED Requirements

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
- **AND** 卡片包含超时提示（如 "请在 60 秒内操作"）
- **AND** 卡片包含 4 个操作按钮（批准/始终允许/拒绝/拒绝并中断）

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
