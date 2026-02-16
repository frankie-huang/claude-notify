## ADDED Requirements

### Requirement: ChatIdStore 扩展存储 Claude Command

Callback 后端的 ChatIdStore SHALL 扩展支持存储每个 session 最近使用的 `claude_command`，用于后续回复时自动复用。

#### Scenario: 保存 session 的 claude_command

- **GIVEN** Callback 后端执行 Claude 命令（新建或继续会话）
- **AND** 使用了 `claude --setting opus` 命令
- **WHEN** 执行成功（进入 processing 状态）
- **THEN** 调用 `ChatIdStore.save()` 保存 `session_id → {chat_id, claude_command, updated_at}`
- **AND** `claude_command` 为实际使用的命令字符串

#### Scenario: 查询 session 的 claude_command

- **GIVEN** Callback 后端收到继续会话请求
- **AND** 请求未指定 `claude_command`
- **WHEN** 后端查询 `ChatIdStore`
- **THEN** 获取该 session 上次使用的 `claude_command`
- **AND** 使用该命令继续会话

#### Scenario: 旧数据无 claude_command 字段向后兼容

- **GIVEN** ChatIdStore 中的旧记录不包含 `claude_command` 字段
- **WHEN** 查询该 session 的 `claude_command`
- **THEN** 返回 `None`
- **AND** 系统使用默认 Claude Command（配置列表第一个）

### Requirement: Claude Command 选择优先级

Callback 后端 SHALL 按以下优先级确定使用哪个 Claude Command：请求指定 > ChatIdStore session 记录 > 配置列表默认值。

#### Scenario: 请求指定的 command 最优先

- **GIVEN** `/claude/continue` 请求中包含 `claude_command` 参数
- **AND** ChatIdStore 中该 session 记录的 command 为另一个值
- **WHEN** Callback 后端确定使用哪个命令
- **THEN** 使用请求中指定的 `claude_command`
- **AND** 将新的 command 更新到 ChatIdStore

#### Scenario: ChatIdStore session 记录次优先

- **GIVEN** `/claude/continue` 请求中未指定 `claude_command`
- **AND** ChatIdStore 中该 session 记录了 `claude_command` 为 `claude --setting opus`
- **WHEN** Callback 后端确定使用哪个命令
- **THEN** 使用 ChatIdStore 中记录的 `claude --setting opus`

#### Scenario: 默认命令兜底

- **GIVEN** `/claude/continue` 请求中未指定 `claude_command`
- **AND** ChatIdStore 中该 session 无 `claude_command` 记录
- **WHEN** Callback 后端确定使用哪个命令
- **THEN** 使用配置列表第一个命令（默认命令）

## MODIFIED Requirements

### Requirement: Callback 后端继续会话接口

Callback 后端 SHALL 提供 `/claude/continue` 端点，接收并处理继续会话请求，支持指定 Claude Command。

#### Scenario: 接收继续会话请求

- **GIVEN** Callback 后端正在运行
- **WHEN** 收到 POST `/claude/continue` 请求
- **AND** 请求包含 `session_id`、`project_dir`、`prompt`
- **AND** 请求可选包含 `claude_command`
- **THEN** 后端验证参数完整性
- **AND** 验证 `project_dir` 目录存在
- **AND** 如果 `claude_command` 非空，验证其在配置列表中
- **AND** 如果 `claude_command` 为空，从 ChatIdStore 查询 session 记录的 command
- **AND** 启动异步线程执行 Claude 命令
- **AND** 立即返回 `{"status": "processing"}`

#### Scenario: 执行 Claude 继续会话

- **GIVEN** 异步线程启动
- **WHEN** 执行 Claude 命令
- **THEN** 切换到 `project_dir` 目录
- **AND** 使用确定的 `claude_command`（按优先级：请求指定 > session 记录 > 默认）
- **AND** 通过登录 shell（`bash -lc`）执行，支持 shell 配置文件中的别名和环境变量
- **AND** 拼接 `-p {prompt} --resume {session_id}` 参数
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

#### Scenario: 自定义 Claude 命令

- **GIVEN** 环境变量 `CLAUDE_COMMAND` 设置为 `claude-glm`
- **WHEN** 执行继续会话
- **THEN** 使用 `claude-glm -p {prompt} --resume {session_id}` 执行

#### Scenario: 带参数的自定义命令

- **GIVEN** 环境变量 `CLAUDE_COMMAND` 设置为 `claude --setting opus`
- **WHEN** 执行继续会话
- **THEN** 使用 `claude --setting opus -p {prompt} --resume {session_id}` 执行

#### Scenario: 向后兼容默认命令

- **GIVEN** 环境变量 `CLAUDE_COMMAND` 未设置
- **WHEN** 执行继续会话
- **THEN** 使用默认命令 `claude -p {prompt} --resume {session_id}` 执行

#### Scenario: 指定的 Command 不在配置列表中

- **GIVEN** 收到 `/claude/continue` 请求
- **AND** `claude_command` 值不在预配置列表中
- **WHEN** Callback 验证命令
- **THEN** 返回 `400` 状态码
- **AND** 返回 `{"error": "invalid claude_command"}`

#### Scenario: 执行成功后保存 command 到 ChatIdStore

- **GIVEN** Claude 命令执行进入 processing 状态
- **WHEN** 后端保存 session 信息
- **THEN** 将实际使用的 `claude_command` 一并保存到 ChatIdStore
- **AND** 后续回复该 session 时可自动复用

### Requirement: 飞书网关回复消息处理

飞书网关 SHALL 能够识别用户回复消息，并将继续会话请求转发到对应的 Callback 后端。`claude_command` 的选择由 Callback 后端负责（从 ChatIdStore 查询）。

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
- **AND** 如果用户通过 `/reply --cmd=` 指定了 command，携带 `claude_command` 参数

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
