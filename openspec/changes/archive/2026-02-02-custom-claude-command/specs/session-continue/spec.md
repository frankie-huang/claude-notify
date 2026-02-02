## MODIFIED Requirements

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
- **AND** 从环境变量 `CLAUDE_COMMAND` 读取命令（默认 `claude`）
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
