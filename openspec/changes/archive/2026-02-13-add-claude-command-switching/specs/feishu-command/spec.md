## ADDED Requirements

### Requirement: Claude Command 多命令配置

系统 SHALL 支持在 `CLAUDE_COMMAND` 中配置多个 Claude 命令，用户可在创建或继续会话时选择使用哪个命令。

#### Scenario: 无引号列表格式配置

- **GIVEN** `.env` 中配置 `CLAUDE_COMMAND=[claude, claude --setting opus]`
- **WHEN** 系统启动并解析配置
- **THEN** 按逗号分隔，各元素 strip 后得到列表
- **AND** 解析为包含两个元素的命令列表
- **AND** 默认使用列表第一个元素 `claude`

#### Scenario: JSON 数组格式配置（兼容）

- **GIVEN** `.env` 中配置 `CLAUDE_COMMAND=["claude", "claude --setting opus"]`
- **WHEN** 系统启动并解析配置
- **THEN** 按 JSON 格式解析
- **AND** 解析为包含两个元素的命令列表
- **AND** 默认使用列表第一个元素 `claude`

#### Scenario: 单字符串格式向后兼容

- **GIVEN** `.env` 中配置 `CLAUDE_COMMAND=claude`
- **WHEN** 系统启动并解析配置
- **THEN** 解析为包含一个元素的命令列表 `["claude"]`
- **AND** 行为与变更前完全一致

#### Scenario: 空值或缺失配置

- **GIVEN** `.env` 中 `CLAUDE_COMMAND` 为空或未配置
- **WHEN** 系统启动并解析配置
- **THEN** 默认使用 `["claude"]`

#### Scenario: 带参数的单命令向后兼容

- **GIVEN** `.env` 中配置 `CLAUDE_COMMAND=claude --setting opus`
- **WHEN** 系统启动并解析配置
- **THEN** 解析为包含一个元素的命令列表 `["claude --setting opus"]`

### Requirement: /new 指令 --cmd 参数

`/new` 指令 SHALL 支持 `--cmd` 参数，用于从预配置列表中选择 Claude Command。

#### Scenario: 使用索引选择 Command

- **GIVEN** `CLAUDE_COMMAND=[claude, claude --setting opus]`
- **AND** 用户发送 `/new --cmd=1 --dir=/path prompt`
- **WHEN** 网关解析指令
- **THEN** 选择索引 1 对应的命令 `claude --setting opus`
- **AND** 使用该命令创建会话

#### Scenario: 使用名称匹配 Command

- **GIVEN** `CLAUDE_COMMAND=[claude, claude --setting opus]`
- **AND** 用户发送 `/new --cmd=opus --dir=/path prompt`
- **WHEN** 网关解析指令
- **THEN** 在列表中查找包含 `opus` 子串的命令
- **AND** 匹配到 `claude --setting opus`
- **AND** 使用该命令创建会话

#### Scenario: --cmd 与 --dir 同时使用

- **GIVEN** 用户发送 `/new --dir=/path --cmd=1 这是 prompt`
- **WHEN** 网关解析指令
- **THEN** 正确提取 `project_dir` 为 `/path`
- **AND** 正确提取 `cmd` 为 `1`
- **AND** 正确提取 `prompt` 为 `这是 prompt`

#### Scenario: --cmd 索引越界

- **GIVEN** `CLAUDE_COMMAND=[claude]`
- **AND** 用户发送 `/new --cmd=5 --dir=/path prompt`
- **WHEN** 网关解析指令
- **THEN** 返回错误提示，包含可用 Command 列表
- **AND** 不创建会话

#### Scenario: --cmd 名称无匹配

- **GIVEN** `CLAUDE_COMMAND=[claude, claude --setting opus]`
- **AND** 用户发送 `/new --cmd=haiku --dir=/path prompt`
- **WHEN** 网关解析指令
- **THEN** 返回错误提示，包含可用 Command 列表
- **AND** 不创建会话

#### Scenario: 仅有单命令时 --cmd 可省略

- **GIVEN** `CLAUDE_COMMAND=[claude]`
- **AND** 用户发送 `/new --dir=/path prompt`（不含 --cmd）
- **WHEN** 网关解析指令
- **THEN** 使用默认命令 `claude`

### Requirement: 新建会话卡片 Command 选择

当配置了多个 Claude Command 时，新建会话卡片 SHALL 包含 Command 选择下拉框。

#### Scenario: 多命令时显示选择器

- **GIVEN** `CLAUDE_COMMAND=[claude, claude --setting opus]`
- **AND** 用户发送 `/new`（触发卡片）
- **WHEN** 构建目录选择卡片
- **THEN** 卡片新增 `select_static` 下拉框（name 为 `claude_command`）
- **AND** 选项包含所有配置的命令
- **AND** 默认选中第一个命令

#### Scenario: 单命令时不显示选择器

- **GIVEN** `CLAUDE_COMMAND=[claude]`（或单字符串格式）
- **AND** 用户发送 `/new`（触发卡片）
- **WHEN** 构建目录选择卡片
- **THEN** 卡片不包含 Command 选择下拉框

#### Scenario: 卡片提交时传递选中的 Command

- **GIVEN** 用户在卡片中选择了 `claude --setting opus`
- **AND** 用户点击"创建会话"按钮
- **WHEN** 处理表单提交
- **THEN** 将选中的 `claude_command` 传递到 Callback 后端 `/claude/new`

### Requirement: /reply 指令

系统 SHALL 支持 `/reply` 指令，允许用户在回复消息时指定 Claude Command。

#### Scenario: 基本 /reply 格式

- **GIVEN** 用户回复某条 Claude 会话消息
- **AND** 消息内容为 `/reply 继续帮我完善`
- **WHEN** 网关解析指令
- **THEN** 识别为 `/reply` 命令
- **AND** 提取 `prompt` 为 `继续帮我完善`
- **AND** 从 parent_id 映射中获取 session 信息
- **AND** 使用 session 记录的 Claude Command 继续会话

#### Scenario: /reply 带 --cmd 参数

- **GIVEN** 用户回复某条 Claude 会话消息
- **AND** 消息内容为 `/reply --cmd=opus 用 opus 帮我重构`
- **WHEN** 网关解析指令
- **THEN** 识别为 `/reply` 命令
- **AND** 提取 `cmd` 为 `opus`
- **AND** 提取 `prompt` 为 `用 opus 帮我重构`
- **AND** 使用匹配到的 Claude Command 继续会话

#### Scenario: /reply 非回复消息时报错

- **GIVEN** 用户直接发送 `/reply prompt`（不是回复消息）
- **WHEN** 网关处理该消息
- **THEN** 返回错误提示："`/reply` 指令仅支持在回复消息时使用"

#### Scenario: /reply 回复的消息无映射

- **GIVEN** 用户回复非 Claude 会话消息
- **AND** 消息内容为 `/reply prompt`
- **WHEN** 网关查询 SessionStore
- **THEN** 查询结果为空
- **AND** 返回错误提示："无法找到对应的会话（可能已过期或被清理），请重新发起 /new 指令"

### Requirement: --cmd 参数安全约束

`--cmd` 参数 SHALL 仅允许从预配置列表中选择命令，不允许用户自定义命令内容。

#### Scenario: 拒绝自定义命令

- **GIVEN** 用户发送 `/new --cmd="custom-cmd --flag" --dir=/path prompt`
- **AND** `custom-cmd --flag` 不在配置列表中
- **WHEN** 网关解析 --cmd 参数
- **THEN** 尝试名称匹配
- **AND** 无匹配结果时返回错误提示
- **AND** 不执行任何命令

## MODIFIED Requirements

### Requirement: /new 指令识别

飞书网关 SHALL 能够识别用户发送的 `/new` 指令，并解析工作目录参数、`--cmd` 参数和用户输入的 prompt。

#### Scenario: 识别 /new 指令

- **GIVEN** 飞书网关收到 `im.message.receive_v1` 事件
- **AND** 消息文本内容以 `/new` 开头
- **WHEN** 网关处理该消息
- **THEN** 网关判定为 `/new` 指令
- **AND** 提取指令参数（含 `--dir`、`--cmd`）和 prompt 内容
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

`/new` 指令 SHALL 支持 `--dir=` 参数指定工作目录、`--cmd=` 参数指定 Claude Command，同时也支持交互式目录选择。

#### Scenario: 缺少目录参数时发送选择卡片

- **GIVEN** 用户输入 `/new prompt`
- **AND** 没有指定 `--dir=` 参数
- **AND** 不是回复消息
- **WHEN** 解析指令
- **THEN** 发送目录选择卡片
- **AND** 不返回错误提示

#### Scenario: 回复消息无映射时发送选择卡片

- **GIVEN** 用户回复消息，输入 `/new prompt`
- **AND** 被回复消息无项目目录映射
- **WHEN** 解析指令
- **THEN** 发送目录选择卡片
- **AND** 卡片包含原始 prompt 内容

### Requirement: Callback 后端新建会话接口

Callback 后端 SHALL 提供 `/claude/new` 端点，接收并处理新建会话请求，支持指定 Claude Command。

#### Scenario: 接收新建会话请求

- **GIVEN** Callback 后端正在运行
- **WHEN** 收到 POST `/claude/new` 请求
- **AND** 请求包含 `project_dir`、`prompt`、`chat_id`、`message_id`
- **AND** 请求可选包含 `claude_command`
- **THEN** 后端验证参数完整性
- **AND** 验证 `project_dir` 目录存在
- **AND** 如果 `claude_command` 非空，验证其在配置列表中
- **AND** 生成 UUID 作为 `session_id`
- **AND** 保存 `session_id → chat_id` 映射到 ChatIdStore
- **AND** 启动异步线程执行 Claude 命令
- **AND** 立即返回 `{"status": "processing", "session_id": "..."}`

#### Scenario: 执行 Claude 新建会话

- **GIVEN** 异步线程启动
- **WHEN** 执行 Claude 命令
- **THEN** 切换到 `project_dir` 目录
- **AND** 使用指定的 `claude_command`（或默认命令）
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

#### Scenario: 指定的 Command 不在配置列表中

- **GIVEN** 收到 `/claude/new` 请求
- **AND** `claude_command` 值不在预配置列表中
- **WHEN** Callback 验证命令
- **THEN** 返回 `400` 状态码
- **AND** 返回 `{"error": "invalid claude_command"}`

#### Scenario: session_id 与 chat_id 关联

- **GIVEN** 新建会话成功
- **AND** 请求包含 `chat_id`
- **WHEN** 会话创建
- **THEN** 保存 `session_id → chat_id` 映射到 ChatIdStore
- **AND** 后续 permission/stop 事件能通过 session_id 查询到 chat_id
