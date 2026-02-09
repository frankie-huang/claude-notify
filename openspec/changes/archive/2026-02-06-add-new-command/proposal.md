# Change: 添加 /new 指令支持飞书发起新 Claude 会话

## Why

当前用户只能在飞书中回复已有的 Claude 会话消息来继续对话，无法直接从飞书发起新的 Claude 会话。这限制了用户在飞书中灵活使用 Claude 的能力。

## What Changes

- **新增 `/new` 指令解析**：飞书网关识别 `/new` 开头的消息，解析工作目录参数和用户 prompt
- **新建会话接口**：Callback 后端新增 `/claude/new` 端点，使用 `--session-id` 发起新对话
- **UUID 生成 session_id**：每次新建会话生成唯一 UUID
- **session-chat 关联存储**：复用现有 ChatIdStore 存储 session_id 与 chat_id 的映射关系
- **回复模式**：支持回复其他会话消息时复用被回复消息的工作目录

## Impact

- Affected specs: `feishu-command` (新增 capability)
- Affected code:
  - `src/server/handlers/feishu.py` - 处理 `/new` 指令
  - `src/server/handlers/claude.py` - 新增 `handle_new_session` 函数
  - `src/server/services/session_store.py` - 扩展存储项目目录信息
  - `src/server/main.py` - 新增 `/claude/new` 路由
