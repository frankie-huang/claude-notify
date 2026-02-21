## 1. SessionChatStore 扩展

- [x] 1.1 扩展 `SessionChatStore.save()` 支持 `last_message_id` 参数
- [x] 1.2 添加 `get_last_message_id(session_id)` 方法
- [x] 1.3 添加 `set_last_message_id(session_id, message_id)` 方法
- [x] 1.4 旧数据向后兼容（无 `last_message_id` 字段时返回空字符串）

## 2. Callback 后端接口

- [x] 2.1 添加 `POST /get-last-message-id` 接口（入参 `session_id`，返回 `{last_message_id: "..."}`）

## 3. 飞书网关 `/feishu/send` 接口

- [x] 3.1 `handle_send_message()` 增加 `reply_to_message_id` 可选参数
- [x] 3.2 当 `reply_to_message_id` 非空时，使用 `reply_card()` / `reply_text()` 发送
- [x] 3.3 reply 失败时降级为 send 新消息
- [x] 3.4 发送成功后调用 `set_last_message_id()` 更新链式回复状态

## 4. 飞书网关内部消息发送

- [x] 4.1 `_forward_claude_request()` 中保存用户消息到 MessageSessionStore（不更新 last_message_id）
- [x] 4.2 `_send_session_result_notification()` 中更新 last_message_id
- [x] 4.3 `_send_error_notification()` 支持关联到会话（可选的 session_id 和 project_dir 参数）

## 5. Shell 脚本链路

- [x] 5.1 `src/lib/feishu.sh` 新增 `_get_last_message_id()` 函数（调用 `POST /get-last-message-id`）
- [x] 5.2 `_send_feishu_card_http_endpoint()` 将 `last_message_id` 作为 `reply_to_message_id` 传递给 `/feishu/send`
- [x] 5.3 `src/hooks/permission.sh` 在发送前查询 last_message_id 并传入 options
- [x] 5.4 `src/hooks/stop.sh` 在发送前查询 last_message_id 并传入 options

## 6. 验证

- [ ] 6.1 测试场景 1：通过 `/new --dir=... prompt` 直接启动 → 后续消息形成链式回复
- [ ] 6.2 测试场景 2：终端直接启动 → 首次权限请求/完成通知成为首条消息，后续消息形成链式回复
- [ ] 6.3 测试场景 3：消息被撤回后 → reply 失败，降级为发送新消息
- [ ] 6.4 测试场景 4：Webhook 模式 → 行为不变，话题流功能不生效
- [ ] 6.5 测试场景 5：在话题流中发送消息 → 能继续对应的会话
- [ ] 6.6 测试场景 6：在话题流中回复某条具体消息 → 能继续对应的会话
- [ ] 6.7 测试场景 7：错误通知关联到会话 → 错误通知出现在话题流中
