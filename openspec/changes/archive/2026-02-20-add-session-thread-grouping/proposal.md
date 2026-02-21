# Change: 会话消息链式回复

## Status

✅ **Applied** (2026-02-19)

## Why

当前同一个 Claude 会话的多条消息（新建会话通知、权限请求、完成通知、继续会话等）散落在飞书对话中，难以查看单个会话的完整历程。需要将同一会话的所有消息收敛到一个话题流（thread）中，提升会话追踪的可读性。

## What Changes

- 引入 `last_message_id` 概念：每个 session 记录最近一条消息的 ID，后续消息使用飞书 reply API 回复该消息，形成链式结构
- 链式回复规则：
  1. 系统发送通知时，回复 `last_message_id`（如果存在）
  2. 发送成功后，更新 `last_message_id` 为新消息 ID
  3. 用户消息也保存到 `MessageSessionStore`，支持回复用户消息继续会话
- 修改 `/feishu/send` 接口支持 `reply_to_message_id` 参数，使用 reply API 发送消息
- 修改 Shell 脚本自动查询 `last_message_id` 并传递给 `/feishu/send`
- 扩展 SessionChatStore 存储 `last_message_id`
- 添加 `/get-last-message-id` 接口供 Shell 脚本查询

## Impact

- Affected specs: session-continue
- Affected code:
  - `src/server/handlers/feishu.py` - `/feishu/send` 接口增加 reply 模式、链式回复逻辑
  - `src/server/services/feishu_api.py` - 已有 `reply_card()` 和 `reply_text()`，无需修改
  - `src/server/services/session_chat_store.py` - 扩展存储 `last_message_id`
  - `src/server/handlers/callback.py` - 新增 `/get-last-message-id` 接口
  - `src/lib/feishu.sh` - `_get_last_message_id()` 函数、自动查询并传递
