## ADDED Requirements

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

### Requirement: Error Handling

脚本 SHALL 具备容错能力，确保不会阻塞 Claude Code 正常运行。

#### Scenario: JSON 解析失败降级处理

- **GIVEN** stdin 输入的 JSON 格式无效或缺少必要字段
- **WHEN** 脚本尝试解析 JSON
- **THEN** 脚本发送降级通知消息，说明有权限请求但无法解析详情
- **AND** 脚本以退出码 0 结束，不阻塞 Claude Code

#### Scenario: Webhook 请求失败静默处理

- **GIVEN** 飞书 Webhook URL 不可达或返回错误
- **WHEN** 脚本尝试发送通知
- **THEN** 脚本以退出码 0 结束
- **AND** 不影响 Claude Code 继续运行

### Requirement: Hook Configuration

用户 SHALL 能够通过标准的 Claude Code hooks 配置机制注册权限通知脚本。

#### Scenario: PermissionRequest Hook 配置

- **GIVEN** 用户希望在权限请求时收到通知
- **WHEN** 用户在 `.claude/settings.json` 中配置 PermissionRequest hook
- **THEN** 配置格式符合 Claude Code hooks 规范
- **AND** 可以使用 matcher 指定监听的工具类型（如 "Bash", "Edit|Write", "*"）
- **AND** hook 输入包含完整的 `tool_name` 和 `tool_input` 详情
