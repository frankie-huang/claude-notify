# Change: 支持 Claude Command 切换

## Why

当前 `CLAUDE_COMMAND` 是单一固定字符串配置，所有会话使用同一个 Claude 命令。实际使用中，用户可能需要在不同场景下使用不同的 Claude 配置（如默认 `claude` 用于日常，`claude --setting opus` 用于复杂任务），目前需要手动修改 `.env` 才能切换，不够灵活。

## What Changes

- **CLAUDE_COMMAND 配置格式升级**: 从单一字符串改为支持列表格式，如 `[claude, claude --setting opus]`（无需引号），也兼容 JSON 数组格式，向后兼容原有字符串格式
- **`--cmd` 参数**: `/new` 和 `/reply` 指令新增 `--cmd` 参数，支持按索引（从 0 开始）或名称选择预配置的 Claude Command
- **`/reply` 指令**: 新增 `/reply` 命令，仅在回复消息时可用，支持 `--cmd` 参数指定 Claude Command
- **新建会话卡片增加选择器**: 当配置了多个 Command 时，/new 卡片展示 Command 选择下拉框
- **Session 记忆**: Callback 后端复用 ChatIdStore 记录每个 session 最近使用的 Claude Command，后续回复自动复用
- **安全约束**: 仅允许从预配置列表中选择，不支持自定义输入，防止注入风险

## Impact

- Affected specs: `feishu-command`, `session-continue`
- Affected code:
  - `.env.example` — 配置项格式变更
  - `install.sh` — 配置模板同步
  - `src/server/config.py` — 配置解析逻辑
  - `src/server/handlers/claude.py` — Claude Command 选择逻辑
  - `src/server/handlers/feishu.py` — 指令解析、卡片构建、/reply 命令
  - `src/server/handlers/register.py` — ChatIdStore 扩展存储 claude_command
  - `src/server/handlers/callback.py` — 传递 claude_command 参数
