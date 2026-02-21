## ADDED Requirements

### Requirement: 会话消息话题流收敛（链式回复）

系统 SHALL 将同一 Claude 会话的所有飞书消息收敛到一个话题流中，采用链式回复结构。系统维护每个会话的 `last_message_id`，每条新系统通知回复到最近一条消息。

#### Scenario: /new 完整指令场景的链式回复

- **GIVEN** 用户在飞书发送完整的 `/new --dir=/path prompt` 指令
- **WHEN** 飞书网关处理该指令
- **THEN** 将用户发送的 `/new` 消息的 `message_id` 保存到 `MessageSessionStore`
- **AND** 后续系统通知（"会话已创建"等）回复到该 `/new` 消息
- **AND** 发送成功后更新 `last_message_id`

#### Scenario: 终端直接启动场景的链式回复

- **GIVEN** 用户在终端直接启动 Claude Code（非通过飞书 `/new` 指令）
- **AND** 该会话尚无 `last_message_id`
- **WHEN** 首次通过 `/feishu/send` 发送消息（权限请求或完成通知）
- **THEN** 发送新消息（无回复目标）
- **AND** 发送成功后，将返回的 `message_id` 保存为该 session 的 `last_message_id`
- **AND** 后续该会话的消息都使用 reply API 回复到 `last_message_id`

#### Scenario: 链式回复发送系统通知

- **GIVEN** 某 session 已有 `last_message_id`
- **WHEN** 系统需要为该会话发送飞书通知（权限请求、完成通知等）
- **THEN** 使用飞书 reply API (`POST /im/v1/messages/:message_id/reply`) 回复到 `last_message_id`
- **AND** 发送成功后更新 `last_message_id` 为新消息 ID
- **AND** 消息自动出现在话题流中

#### Scenario: 用户消息保存但不更新 last_message_id

- **GIVEN** 用户在话题流中发送消息继续会话
- **WHEN** 飞书网关处理该用户消息
- **THEN** 将用户消息的 `message_id` 保存到 `MessageSessionStore`
- **AND** 不更新 `last_message_id`（保持为最近一条系统消息）
- **AND** 后续系统通知回复到 `last_message_id`（可能是用户消息或系统消息）

#### Scenario: reply 失败时降级为新消息

- **GIVEN** 某 session 已有 `last_message_id`
- **AND** 该消息已被撤回（飞书"删除"仅自己不可见，不影响 reply API）
- **WHEN** reply API 调用失败（错误码 230011）
- **THEN** 降级为使用 send API 发送新消息
- **AND** 记录警告日志
- **AND** 发送成功后更新 `last_message_id`

#### Scenario: 错误通知关联到会话

- **GIVEN** Claude 执行异常（超时、错误等）
- **AND** 存在有效的 `session_id`
- **WHEN** 系统发送错误通知
- **THEN** 错误通知回复到 `last_message_id`（如果存在）
- **AND** 错误通知也收敛到同一话题流中

#### Scenario: 话题内发送消息继续会话

- **GIVEN** 某 session 的消息已收敛到话题流中
- **AND** 话题流中的消息已在 MessageSessionStore 中建立映射
- **WHEN** 用户在话题内直接发送消息（非回复某条具体消息）
- **THEN** 飞书事件的 `parent_id` 为话题根消息或最近一条消息
- **AND** 系统通过 `MessageSessionStore.get(parent_id)` 找到对应的 session
- **AND** 继续该会话

#### Scenario: 话题内回复具体消息继续会话

- **GIVEN** 某 session 的消息已收敛到话题流中
- **WHEN** 用户在话题内回复某条具体的系统消息或用户消息
- **THEN** 飞书事件的 `parent_id` 为被回复的消息 ID
- **AND** 系统通过 `MessageSessionStore.get(parent_id)` 找到对应的 session
- **AND** 继续该会话

#### Scenario: Webhook 模式不支持话题流

- **GIVEN** 系统配置为 `FEISHU_SEND_MODE=webhook`
- **WHEN** 系统发送飞书消息
- **THEN** 忽略 `reply_to_message_id` 参数
- **AND** 使用 Webhook 发送新消息
- **AND** 行为与变更前完全一致

### Requirement: SessionChatStore 扩展存储 last_message_id

SessionChatStore SHALL 扩展支持存储每个 session 的 `last_message_id`，用于链式回复。

#### Scenario: 保存 last_message_id

- **GIVEN** 系统为某 session 发送消息成功
- **WHEN** 系统更新 `last_message_id`
- **THEN** 调用 `SessionChatStore.set_last_message_id(session_id, message_id)`
- **AND** 覆盖该 session 的 `last_message_id`（链式更新）
- **AND** 持久化到 `runtime/session_chats.json`

#### Scenario: 查询 last_message_id

- **GIVEN** 系统需要为某 session 发送飞书消息
- **WHEN** 查询 `SessionChatStore.get_last_message_id(session_id)`
- **THEN** 返回该 session 的 `last_message_id`
- **OR** 返回空字符串（如果未设置）

#### Scenario: 旧数据向后兼容

- **GIVEN** SessionChatStore 中的旧记录不包含 `last_message_id` 字段
- **WHEN** 查询该 session 的 `last_message_id`
- **THEN** 返回空字符串
- **AND** 系统使用默认行为（发送新消息）

### Requirement: /feishu/send 接口支持 reply 模式

飞书网关的 `/feishu/send` 端点 SHALL 支持 `reply_to_message_id` 可选参数，启用时使用 reply API 发送消息。

#### Scenario: 携带 reply_to_message_id 发送卡片

- **GIVEN** 收到 POST `/feishu/send` 请求
- **AND** 请求包含 `reply_to_message_id` 字段（非空）
- **AND** `msg_type` 为 `interactive`
- **WHEN** 飞书网关处理请求
- **THEN** 使用 `FeishuAPIService.reply_card()` 回复到 `reply_to_message_id`
- **AND** 返回 `{"success": true, "message_id": "..."}`

#### Scenario: 携带 reply_to_message_id 发送文本

- **GIVEN** 收到 POST `/feishu/send` 请求
- **AND** 请求包含 `reply_to_message_id` 字段（非空）
- **AND** `msg_type` 为 `text`
- **WHEN** 飞书网关处理请求
- **THEN** 使用 `FeishuAPIService.reply_text()` 回复到 `reply_to_message_id`

#### Scenario: reply 失败降级为 send

- **GIVEN** 收到 POST `/feishu/send` 请求
- **AND** 请求包含 `reply_to_message_id`
- **WHEN** reply API 调用失败
- **THEN** 降级为使用 `send_card()` / `send_text()` 发送新消息
- **AND** 记录警告日志

#### Scenario: 发送成功后更新 last_message_id

- **GIVEN** 收到 POST `/feishu/send` 请求
- **AND** 请求包含有效的 `session_id` 和 `project_dir`
- **WHEN** 消息发送成功
- **THEN** 调用 `set_last_message_id(session_id, message_id)` 更新链式回复状态

#### Scenario: 向后兼容

- **GIVEN** 收到 POST `/feishu/send` 请求
- **AND** 请求不包含 `reply_to_message_id` 字段
- **WHEN** 飞书网关处理请求
- **THEN** 行为与变更前完全一致
- **AND** 使用 `send_card()` / `send_text()` 发送新消息

### Requirement: Shell 脚本传递 last_message_id

Hook 脚本 SHALL 在发送飞书通知时查询并传递 `last_message_id`，使消息收敛到话题流中。

#### Scenario: 查询 last_message_id

- **GIVEN** Hook 脚本需要发送飞书通知
- **AND** 已获取到 `session_id`
- **WHEN** 脚本调用 `_get_last_message_id(session_id)`
- **THEN** 函数调用 `POST /get-last-message-id` 接口
- **AND** 返回 `last_message_id`（可能为空）

#### Scenario: 传递 last_message_id 到 /feishu/send

- **GIVEN** 脚本已查询到 `last_message_id`
- **AND** `last_message_id` 非空
- **WHEN** 调用 `send_feishu_card()` 发送卡片
- **THEN** 将 `last_message_id` 作为 `reply_to_message_id` 传递给 `/feishu/send`
- **AND** 消息将作为话题回复发送

#### Scenario: last_message_id 为空时正常发送

- **GIVEN** 脚本查询 `last_message_id` 结果为空
- **WHEN** 调用 `send_feishu_card()` 发送卡片
- **THEN** 不传递 `reply_to_message_id`
- **AND** `/feishu/send` 发送新消息
- **AND** 如果请求包含 `session_id`，发送成功后自动设置 `last_message_id`

### Requirement: Callback 后端提供 last_message_id 查询接口

Callback 后端 SHALL 提供 `POST /get-last-message-id` 端点，供 Shell 脚本查询 session 的 last_message_id。

#### Scenario: 查询存在的 last_message_id

- **GIVEN** Callback 后端正在运行
- **AND** SessionChatStore 中某 session 已有 `last_message_id`
- **WHEN** 收到 `POST /get-last-message-id` 请求，body 为 `{"session_id": "xxx"}`
- **THEN** 返回 `{"last_message_id": "om_xxx"}`

#### Scenario: 查询不存在的 last_message_id

- **GIVEN** SessionChatStore 中某 session 无 `last_message_id`
- **WHEN** 收到查询请求
- **THEN** 返回 `{"last_message_id": ""}`

#### Scenario: session_id 不存在

- **GIVEN** SessionChatStore 中无该 session_id
- **WHEN** 收到查询请求
- **THEN** 返回 `{"last_message_id": ""}`

#### Scenario: 缺少 session_id 参数

- **GIVEN** 收到 `POST /get-last-message-id` 请求
- **AND** 请求 body 中 `session_id` 为空或缺失
- **WHEN** Callback 后端处理请求
- **THEN** 返回 HTTP 400，body 为 `{"last_message_id": ""}`
- **AND** 调用方应将非 200 响应统一处理为空字符串

### Requirement: Callback 后端提供 last_message_id 写入接口

Callback 后端 SHALL 提供 `POST /set-last-message-id` 端点，供飞书网关在发送消息成功后同步 `last_message_id`。

在分离部署模式下，SessionChatStore 归属 Callback 后端，飞书网关不能直接调用 `set_last_message_id()`，需通过此 HTTP 接口间接写入。

#### Scenario: 设置 last_message_id 成功

- **GIVEN** Callback 后端正在运行
- **AND** SessionChatStore 中该 session 存在且未过期
- **WHEN** 收到 `POST /set-last-message-id` 请求，body 为 `{"session_id": "xxx", "message_id": "om_xxx"}`
- **AND** 请求携带有效的 `X-Auth-Token` header
- **THEN** 更新该 session 的 `last_message_id` 并刷新 `updated_at`
- **AND** 返回 `{"success": true}`

#### Scenario: session 不存在时自动创建

- **GIVEN** SessionChatStore 中无该 session_id（终端直接启动的会话场景）
- **WHEN** 收到 `POST /set-last-message-id` 请求
- **THEN** 自动创建该 session 的记录，包含 `last_message_id` 和 `updated_at`
- **AND** 返回 `{"success": true}`

#### Scenario: session 已过期

- **GIVEN** SessionChatStore 中该 session 已过期（超过 7 天未更新）
- **WHEN** 收到设置请求
- **THEN** 返回 HTTP 500，body 为 `{"success": false, "error": "Failed to set last_message_id"}`

#### Scenario: 缺少必要参数

- **GIVEN** 收到 `POST /set-last-message-id` 请求
- **AND** `session_id` 或 `message_id` 为空
- **WHEN** Callback 后端处理请求
- **THEN** 返回 HTTP 400，body 为 `{"success": false, "error": "Missing required parameters"}`

#### Scenario: 鉴权失败

- **GIVEN** 收到 `POST /set-last-message-id` 请求
- **AND** 请求未携带或携带无效的 `X-Auth-Token` header
- **WHEN** Callback 后端处理请求
- **THEN** 返回 HTTP 401，body 为 `{"error": "Unauthorized"}`
