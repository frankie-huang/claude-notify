# session-continue Specification

## Purpose
TBD - created by archiving change add-session-continue. Update Purpose after archive.
## Requirements
### Requirement: Message-to-Session Mapping

飞书网关 SHALL 维护 message_id 到 session 信息的映射关系，用于将用户回复消息路由到正确的 Callback 后端。

#### Scenario: Stop 事件发送消息时注册映射

- **GIVEN** Claude stop 事件触发
- **AND** Callback 后端调用飞书网关发送完成通知
- **AND** 请求包含 `session_id`、`project_dir`、`callback_url`
- **WHEN** 飞书网关通过 OpenAPI 发送消息成功
- **THEN** 网关获取返回的 `message_id`
- **AND** 网关保存映射: `message_id → {session_id, project_dir, callback_url, created_at}`
- **AND** 映射保存到 `runtime/session_messages.json`

#### Scenario: 权限请求发送消息时注册映射

- **GIVEN** Claude 权限请求事件触发
- **AND** Callback 后端调用飞书网关发送权限请求通知
- **AND** 请求包含 `session_id`、`project_dir`、`callback_url`
- **WHEN** 飞书网关通过 OpenAPI 发送消息成功
- **THEN** 网关获取返回的 `message_id`
- **AND** 网关保存映射: `message_id → {session_id, project_dir, callback_url, created_at}`
- **AND** 映射保存到 `runtime/session_messages.json`

#### Scenario: 查询映射关系

- **GIVEN** 用户回复飞书消息
- **AND** 消息包含 `parent_id`
- **WHEN** 飞书网关查询映射
- **THEN** 网关使用 `parent_id` 作为 key 查询
- **AND** 返回对应的 `{session_id, project_dir, callback_url}`
- **OR** 返回 `null`（如果不存在或已过期）

#### Scenario: 映射自动过期

- **GIVEN** 映射已创建超过 7 天
- **WHEN** 查询该映射
- **THEN** 返回 `null`
- **AND** 映射从存储中删除

#### Scenario: 映射持久化

- **GIVEN** 飞书网关重启
- **WHEN** 网关启动
- **THEN** 从 `runtime/session_messages.json` 加载已有映射
- **AND** 新发送消息的映射追加到文件

### Requirement: 飞书网关回复消息处理

飞书网关 SHALL 能够识别用户回复消息，并将继续会话请求转发到对应的 Callback 后端。

#### Scenario: 识别回复消息

- **GIVEN** 飞书网关收到 `im.message.receive_v1` 事件
- **WHEN** 消息包含 `parent_id` 字段
- **THEN** 网关判定为回复消息
- **AND** 查询 `parent_id` 对应的映射

#### Scenario: 转发到 Callback 后端

- **GIVEN** 查询到有效的映射
- **AND** 提取到用户回复内容
- **WHEN** 飞书网关处理回复消息
- **THEN** POST 请求到 `{callback_url}/claude/continue`
- **AND** 请求 body 包含 `session_id`、`project_dir`、`prompt`
- **AND** 可选包含 `chat_id`、`reply_message_id`

#### Scenario: 忽略未注册消息

- **GIVEN** 飞书网关收到回复消息
- **AND** `parent_id` 查询不到映射
- **WHEN** 网关处理该消息
- **THEN** 忽略该消息
- **AND** 返回成功状态
- **AND** 记录日志

#### Scenario: Callback 不可达处理

- **GIVEN** 查询到有效映射
- **AND** Callback 后端不可达
- **WHEN** 网关尝试转发请求
- **THEN** 记录错误日志
- **AND** 返回错误状态
- **AND** 不影响飞书事件响应

### Requirement: Callback 后端继续会话接口

Callback 后端 SHALL 提供 `/claude/continue` 端点，接收并处理继续会话请求。

#### Scenario: 接收继续会话请求

- **GIVEN** Callback 后端正在运行
- **WHEN** 收到 POST `/claude/continue` 请求
- **AND** 请求包含 `session_id`、`project_dir`、`prompt`
- **THEN** 后端验证参数完整性
- **AND** 验证 `project_dir` 目录存在
- **AND** 启动异步线程执行 Claude 命令
- **AND** 立即返回 `{"status": "processing"}`

#### Scenario: 执行 Claude 继续会话

- **GIVEN** 异步线程启动
- **WHEN** 执行 Claude 命令
- **THEN** 切换到 `project_dir` 目录
- **AND** 执行 `claude -p "<prompt>" --resume "<session_id>"`
- **AND** 设置 10 分钟超时
- **AND** 捕获输出用于日志

#### Scenario: 参数验证失败

- **GIVEN** 收到 `/claude/continue` 请求
- **WHEN** 缺少 `session_id`、`project_dir` 或 `prompt`
- **THEN** 返回 `400` 状态码
- **AND** 返回 `{"error": "missing required fields"}`

#### Scenario: 项目目录不存在

- **GIVEN** 收到 `/claude/continue` 请求
- **WHEN** `project_dir` 目录不存在
- **THEN** 返回 `400` 状态码
- **AND** 返回 `{"error": "project directory not found"}`

### Requirement: 通知参数传递

stop.sh 和 permission.sh SHALL 在发送通知时传递 session 相关参数，支持后续回复继续会话。

#### Scenario: Stop 事件传递 session 参数

- **GIVEN** Claude stop 事件触发
- **WHEN** `send_stop_notification_async()` 执行
- **THEN** 读取 `CALLBACK_SERVER_URL` 配置
- **AND** 从 transcript 提取 `SESSION_ID`
- **AND** 获取 `PROJECT_DIR`
- **AND** 调用 `send_feishu_card()` 传递这些参数

#### Scenario: 权限请求传递 session 参数

- **GIVEN** Claude 权限请求事件触发
- **WHEN** 发送飞书权限请求卡片
- **THEN** 读取 `CALLBACK_SERVER_URL` 配置
- **AND** 从请求输入中提取 `SESSION_ID`
- **AND** 获取 `PROJECT_DIR`
- **AND** 调用 `send_feishu_card()` 传递这些参数
- **AND** 交互模式和降级模式都支持

#### Scenario: 飞书网关接收参数

- **GIVEN** Callback 后端调用飞书网关 `/feishu/send`
- **AND** 请求包含 `session_id`、`project_dir`、`callback_url`
- **WHEN** 飞书网关处理请求
- **THEN** 提取这些参数
- **AND** 发送成功后保存映射
- **AND** 返回 `{"success": true, "message_id": "..."}`

#### Scenario: 向后兼容

- **GIVEN** Callback 后端调用飞书网关 `/feishu/send`
- **AND** 请求不包含 `session_id` 等参数
- **WHEN** 飞书网关处理请求
- **THEN** 正常发送消息
- **AND** 跳过映射保存
- **AND** 返回成功

### Requirement: 错误处理与日志

系统 SHALL 提供完善的错误处理和日志记录，便于问题排查。

#### Scenario: 会话恢复失败

- **GIVEN** Callback 后端执行 `claude --resume`
- **AND** 会话已过期或不存在
- **WHEN** Claude 命令执行失败
- **THEN** 记录错误日志
- **AND** 不抛出异常
- **AND** 后续 hook 事件可正常发送错误通知

#### Scenario: 命令执行超时

- **GIVEN** Claude 命令执行超过 10 分钟
- **WHEN** 超时触发
- **THEN** 终止子进程
- **AND** 记录超时日志
- **AND** 不影响 Callback 服务运行

#### Scenario: 映射保存失败

- **GIVEN** 飞书网关发送消息成功
- **AND** 映射保存失败（如磁盘满）
- **WHEN** 保存失败
- **THEN** 记录错误日志
- **AND** 消息仍然成功发送
- **AND** 返回成功状态

### Requirement: 过期清理

SessionStore SHALL 支持定期清理过期的映射数据，防止数据无限增长。

#### Scenario: 定时清理过期数据

- **GIVEN** 飞书网关正在运行
- **WHEN** 触发清理任务（如每小时一次）
- **THEN** 扫描所有映射
- **AND** 删除 `created_at` 超过 7 天的条目
- **AND** 更新存储文件
- **AND** 记录清理数量

#### Scenario: 手动清理

- **GIVEN** 管理员需要手动清理
- **WHEN** 调用 `SessionStore.cleanup_expired()`
- **THEN** 返回清理的条目数量
- **AND** 更新存储文件

