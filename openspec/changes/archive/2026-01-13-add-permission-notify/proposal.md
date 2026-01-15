# Change: Add Permission Request Notification via Feishu Webhook

## Why

当 Claude Code 需要用户授权（如执行命令、修改文件等）时，用户可能不在终端前。需要一种机制在权限请求时通过飞书 Webhook 实时通知用户，让用户知道 Claude Code 正在等待确认，并能看到具体的权限请求内容。

## What Changes

- 新增 `permission-notify.sh` 脚本，专门处理权限请求通知
- 使用 `PermissionRequest` hook（而非 `Notification` 或 `PreToolUse`），以获取完整的权限请求详情
- 脚本从 stdin 读取 Claude Code 传入的 JSON 数据，解析 `tool_name` 和 `tool_input`
- 通过飞书 Webhook 发送包含权限详情的卡片消息（具体命令、文件路径等）
- 提供 Hook 配置示例，用于在 `.claude/settings.json` 中注册

## Hook 选择说明

| Hook 类型 | 数据内容 | 适用场景 |
|-----------|----------|----------|
| `Notification` (permission_prompt) | 只有通用消息 | 简单通知 |
| `PermissionRequest` ✓ | 完整 tool_input | **本方案采用** |
| `PreToolUse` | 完整 tool_input | 工具执行前验证 |

选择 `PermissionRequest` 因为它专门针对权限请求，且包含完整的工具参数（命令内容、文件路径等）。

## Impact

- Affected specs: `permission-notify` (新增)
- Affected code:
  - 新增 `permission-notify.sh` 脚本
  - 需要用户配置 `.claude/settings.json` 中的 `PermissionRequest` hook
