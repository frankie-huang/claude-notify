# Change: 添加 VSCode 自动跳转功能

## Why

当前用户点击飞书卡片按钮后，会跳转到回调服务的响应页面，但用户仍需手动切换到 VSCode 查看 Claude Code 执行结果。通过在响应页面自动跳转 VSCode 并聚焦终端，可以提升用户体验，减少操作步骤。

## What Changes

- 新增 `VSCODE_REMOTE_PREFIX` 环境变量配置，用于指定 VSCode Remote 的 URI 前缀
- 回调服务响应页面增加 VSCode 自动跳转逻辑
- 仅当配置了 `VSCODE_REMOTE_PREFIX` 时才执行跳转
- 跳转后自动聚焦到运行 Claude Code 的终端

## Impact

- Affected specs: `permission-notify`
- Affected code:
  - `server/handlers/callback.py` - 响应页面 HTML 模板
  - `server/config.py` - 新增配置项
  - `.env.example` - 配置示例
