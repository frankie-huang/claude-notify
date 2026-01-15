# Change: 增加可交互权限控制

## Why

当前 Claude Code 权限请求通知仅为单向通知，用户收到飞书消息后仍需返回终端手动操作。用户希望能够直接在飞书消息卡片中点击按钮（批准/拒绝等）来控制 Claude Code 的权限请求，无需切换到终端，提升工作效率。

## What Changes

- **新增回调服务**: 创建一个轻量级 HTTP 服务，用于接收飞书卡片按钮的 URL 跳转请求，并将用户决策回传给 Claude Code
- **卡片按钮交互**: 飞书卡片按钮配置为 URL 跳转，点击后打开浏览器访问本地 HTTP 服务
- **新增权限请求管理**: 实现请求 ID 机制，将用户的按钮点击与对应的 Claude Code 权限请求关联
- **修改通知脚本**: `permission-notify.sh` 需要与回调服务协作，等待用户响应后返回决策给 Claude Code
- **支持始终允许**: 点击"始终允许"按钮时，自动写入权限规则到 `.claude/settings.local.json`

## Impact

- Affected specs: `permission-notify`
- Affected code:
  - `permission-notify.sh` - 需要重构为与回调服务协作模式
  - 新增 `callback-server/` - HTTP 回调服务（Python）
  - 新增配置文件 - 服务端口配置
- External dependencies:
  - Python 3.8+
  - 用户浏览器能访问回调服务地址（本地开发用 localhost）
