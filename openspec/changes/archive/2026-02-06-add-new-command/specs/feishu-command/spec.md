# feishu-command Specification

## Purpose

定义飞书网关处理用户指令（如 `/new`）的能力，允许用户直接在飞书中发起操作。

## ADDED Requirements

### Requirement: /new 指令识别

飞书网关 SHALL 能够识别用户发送的 `/new` 指令，并解析工作目录参数和用户输入的 prompt。

#### Scenario: 识别 /new 指令

- **GIVEN** 飞书网关收到 `im.message.receive_v1` 事件
- **AND** 消息文本内容以 `/new` 开头
- **WHEN** 网关处理该消息
- **THEN** 网关判定为 `/new` 指令
- **AND** 提取指令参数和 prompt 内容
- **AND** 转发到 Callback 后端 `/claude/new` 接口

#### Scenario: 指令格式解析

- **GIVEN** 用户消息为 `/new --dir=/home/user/project 帮我写一个测试文件`
- **WHEN** 网关解析指令
- **THEN** 提取 `project_dir` 为 `/home/user/project`
- **AND** 提取 `prompt` 为 `帮我写一个测试文件`
- **AND** 保留原始消息的 `message_id` 和 `chat_id`

#### Scenario: 回复模式解析

- **GIVEN** 用户回复某条消息，内容为 `/new 再加个错误处理`
- **AND** 被回复消息的 `parent_id` 在 SessionStore 中有映射
- **WHEN** 网关解析指令
- **THEN** 从 SessionStore 查询 `parent_id` 对应的 `project_dir`
- **AND** 使用查询到的 `project_dir` 作为工作目录
- **AND** 提取 `prompt` 为 `再加个错误处理`

#### Scenario: 回复消息无映射

- **GIVEN** 用户回复某条消息，内容为 `/new 再加个错误处理`
- **AND** 被回复消息的 `parent_id` 在 SessionStore 中无映射
- **WHEN** 网关解析指令
- **THEN** 向飞书发送错误提示：无法获取工作目录，请使用 `/new --dir=/path` 指定
- **AND** 不转发请求到 Callback 后端

#### Scenario: 忽略非指令消息

- **GIVEN** 飞书网关收到消息
- **AND** 消息内容不是 `/new` 开头
- **AND** 消息不包含 `parent_id`
- **WHEN** 网关处理该消息
- **THEN** 忽略该消息
- **AND** 返回成功状态

### Requirement: /new 指令参数格式

`/new` 指令 SHALL 支持 `--dir=` 参数指定工作目录。

#### Scenario: 完整格式

- **GIVEN** 用户输入 `/new --dir=/path/to/project prompt content`
- **WHEN** 解析指令
- **THEN** `project_dir` 为 `/path/to/project`
- **AND** `prompt` 为 `prompt content`

#### Scenario: 包含空格的路径

- **GIVEN** 用户输入 `/new --dir="/path/with spaces/project" prompt`
- **WHEN** 解析指令
- **THEN** `project_dir` 为 `/path/with spaces/project`
- **AND** `prompt` 为 `prompt`

#### Scenario: 回复模式省略目录

- **GIVEN** 用户回复消息，输入 `/new prompt`
- **AND** 被回复消息有项目目录映射
- **WHEN** 解析指令
- **THEN** 使用被回复消息的 `project_dir`
- **AND** `prompt` 为 `prompt`

### Requirement: Callback 后端新建会话接口

Callback 后端 SHALL 提供 `/claude/new` 端点，接收并处理新建会话请求。

#### Scenario: 接收新建会话请求

- **GIVEN** Callback 后端正在运行
- **WHEN** 收到 POST `/claude/new` 请求
- **AND** 请求包含 `project_dir`、`prompt`、`chat_id`、`message_id`
- **THEN** 后端验证参数完整性
- **AND** 验证 `project_dir` 目录存在
- **AND** 生成 UUID 作为 `session_id`
- **AND** 保存 `session_id → chat_id` 映射到 ChatIdStore
- **AND** 启动异步线程执行 Claude 命令
- **AND** 立即返回 `{"status": "processing", "session_id": "..."}`

#### Scenario: 执行 Claude 新建会话

- **GIVEN** 异步线程启动
- **WHEN** 执行 Claude 命令
- **THEN** 切换到 `project_dir` 目录
- **AND** 从环境变量 `CLAUDE_COMMAND` 读取命令（默认 `claude`）
- **AND** 通过登录 shell（`bash -lc`）执行
- **AND** 拼接 `-p {prompt} --session-id {session_id}` 参数
- **AND** 设置 10 分钟超时
- **AND** 捕获输出用于日志

#### Scenario: 参数验证失败

- **GIVEN** 收到 `/claude/new` 请求
- **WHEN** 缺少 `project_dir` 或 `prompt`
- **THEN** 返回 `400` 状态码
- **AND** 返回 `{"error": "missing required fields"}`

#### Scenario: 项目目录不存在

- **GIVEN** 收到 `/claude/new` 请求
- **WHEN** `project_dir` 目录不存在
- **THEN** 返回 `400` 状态码
- **AND** 返回 `{"error": "project directory not found"}`

#### Scenario: 自定义 Claude 命令

- **GIVEN** 环境变量 `CLAUDE_COMMAND` 设置为 `claude-glm`
- **WHEN** 执行新建会话
- **THEN** 使用 `claude-glm -p {prompt} --session-id {session_id}` 执行

#### Scenario: session_id 与 chat_id 关联

- **GIVEN** 新建会话成功
- **AND** 请求包含 `chat_id`
- **WHEN** 会话创建
- **THEN** 保存 `session_id → chat_id` 映射到 ChatIdStore
- **AND** 后续 permission/stop 事件能通过 session_id 查询到 chat_id

### Requirement: 会话创建通知

新建会话成功后，系统 SHALL 发送飞书通知并保存消息映射，支持后续回复继续该会话。

#### Scenario: 发送会话创建通知

- **GIVEN** Callback 后端返回 `{"status": "processing", "session_id": "..."}`
- **WHEN** 飞书网关收到响应
- **THEN** 发送"会话已创建"文本消息到 `chat_id`
- **AND** 消息内容包含 session_id（用于调试）
- **AND** 保存新消息的 `message_id → {session_id, project_dir, callback_url}` 映射

#### Scenario: 后续回复继续新会话

- **GIVEN** 会话已创建
- **AND** 用户回复"会话已创建"通知消息
- **WHEN** 飞书网关收到回复
- **THEN** 查询到 `parent_id` 对应的 session 映射
- **AND** 转发到 `/claude/continue` 接口
- **AND** 使用创建时的 `session_id` 继续会话

### Requirement: 错误处理

系统 SHALL 提供完善的错误处理和友好提示。

#### Scenario: 目录不存在提示

- **GIVEN** 用户输入 `/new --dir=/nonexistent/path prompt`
- **WHEN** Callback 后端验证目录
- **THEN** 返回 `{"error": "project directory not found: /nonexistent/path"}`
- **AND** 飞书网关向用户发送错误提示

#### Scenario: 回复消息无目录映射

- **GIVEN** 用户回复非 Claude 消息，输入 `/new prompt`
- **WHEN** 飞书网关查询 SessionStore
- **THEN** 查询结果为空
- **AND** 发送提示："无法获取工作目录，请使用 `/new --dir=/path/to/project` 格式指定"

#### Scenario: 参数格式错误

- **GIVEN** 用户输入 `/new --dirinvalid prompt`
- **WHEN** 飞书网关解析参数
- **THEN** 发送提示："参数格式错误，正确格式：`/new --dir=/path/to/project prompt`"

### Requirement: 双向认证

`/new` 指令请求 SHALL 复用现有的 auth_token 双向认证机制。

#### Scenario: 网关验证请求 Token

- **GIVEN** 用户发送 `/new` 指令
- **WHEN** 飞书网关处理前验证
- **THEN** 从 sender_id 查询对应的 auth_token
- **AND** 验证 token 有效性
- **AND** 验证失败则返回"您尚未注册，无法使用此功能"

#### Scenario: 转发请求携带 Token

- **GIVEN** auth_token 验证通过
- **WHEN** 转发到 Callback 后端
- **THEN** 在请求头中添加 `X-Auth-Token: {auth_token}`
