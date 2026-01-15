# permission-notify Spec Delta

## MODIFIED Requirements

### Requirement: Timeout Handling

~~系统 SHALL 处理用户未在超时时间内响应的情况。~~

系统 SHALL 基于实际连接状态处理请求有效性，而非人为设定的超时时间。

#### Scenario: 请求超时自动拒绝

- **GIVEN** 权限请求卡片已发送
- **WHEN** ~~用户 55 秒内未点击任何按钮~~ Claude Code hook 等待超时导致 socket 连接断开
- **THEN** ~~脚本自动返回~~ permission-notify.sh 因 socat 超时返回 `{"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": {"behavior": "deny", "message": "权限请求超时，自动拒绝"}}}`

#### Scenario: 超时后按钮点击处理

- **GIVEN** ~~权限请求已超时~~ Claude Code 已不再等待（socket 连接已断开）
- **WHEN** 用户之后点击按钮访问 URL
- **THEN** 回调服务返回"~~请求已过期~~连接已断开，Claude 可能已继续执行其他操作"页面

#### Scenario: 长时间等待后点击仍有效 (NEW)

- **GIVEN** 权限请求卡片已发送
- **AND** Claude Code 仍在等待用户响应（socket 连接保持）
- **WHEN** 用户在任意时间点击按钮
- **THEN** 回调服务正常处理请求
- **AND** 将决策发送给 Claude Code

#### Scenario: 请求已被处理后再次点击 (NEW)

- **GIVEN** 权限请求已被用户处理（批准/拒绝）
- **WHEN** 用户再次点击按钮访问 URL
- **THEN** 回调服务返回"请求已被处理"页面
- **AND** 显示之前的处理结果（如"已批准"）

### Requirement: Feishu Card Message Format

通知消息 SHALL 使用飞书交互式卡片格式，包含请求信息和操作按钮。

#### Scenario: 卡片消息内容完整 (MODIFIED)

- **GIVEN** 权限请求事件发生
- **WHEN** 发送飞书通知
- **THEN** 卡片标题显示 "Claude Code 权限请求"
- **AND** 卡片包含项目名称（从 `CLAUDE_PROJECT_DIR` 或 `cwd` 获取）
- **AND** 卡片包含请求时间戳
- **AND** 卡片包含工具类型（Bash/Edit/Write 等）
- **AND** 卡片包含请求详情（命令内容或文件路径）
- **AND** 卡片包含请求 ID（用于关联回调）
- **AND** ~~卡片包含超时提示（如 "请在 60 秒内操作"）~~ 卡片包含操作提示（如 "请尽快操作以避免 Claude 超时"）
- **AND** 卡片包含 4 个操作按钮（批准/始终允许/拒绝/拒绝并中断）

## REMOVED Requirements

### Requirement: Server-Side Request TTL (REMOVED)

~~回调服务 SHALL 维护请求有效期（REQUEST_TTL），超过有效期的请求将被自动清理。~~

**Rationale**: 请求有效性现在完全由 socket 连接状态决定，无需服务器端人为设定超时。
