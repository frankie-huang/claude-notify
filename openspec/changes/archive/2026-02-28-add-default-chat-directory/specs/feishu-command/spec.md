## ADDED Requirements

### Requirement: Default Chat Directory

当配置了 `DEFAULT_CHAT_DIR` 环境变量时，系统 SHALL 支持以下行为：

1. 用户发送普通消息（非指令、非回复）时，自动继续活跃的默认会话；无活跃会话时自动创建新会话
2. 用户发送 `/new prompt`（有 prompt 但无 `--dir`）时，在默认目录创建新会话，该会话成为新的活跃默认会话
3. 服务启动时检测默认目录，不存在则自动创建

未配置 `DEFAULT_CHAT_DIR` 时，系统 SHALL 保持所有现有行为不变。

#### Scenario: 普通消息 - 无活跃默认会话
- **WHEN** `DEFAULT_CHAT_DIR` 已配置
- **AND** 当前无活跃的默认会话
- **AND** 用户发送非指令、非回复的普通文本消息
- **THEN** 系统在 `DEFAULT_CHAT_DIR` 目录下创建新 Claude 会话，消息内容作为 prompt
- **AND** 该会话成为活跃的默认会话

#### Scenario: 普通消息 - 有活跃默认会话
- **WHEN** `DEFAULT_CHAT_DIR` 已配置
- **AND** 存在活跃的默认会话
- **AND** 用户发送非指令、非回复的普通文本消息
- **THEN** 系统继续活跃的默认会话，消息内容作为 prompt

#### Scenario: /new prompt 使用默认目录
- **WHEN** `DEFAULT_CHAT_DIR` 已配置
- **AND** 用户发送 `/new prompt`（有 prompt 但无 `--dir` 参数）
- **THEN** 系统在 `DEFAULT_CHAT_DIR` 目录下创建新 Claude 会话
- **AND** 该会话替换为新的活跃默认会话

#### Scenario: /new --dir 不受影响
- **WHEN** `DEFAULT_CHAT_DIR` 已配置
- **AND** 用户发送 `/new --dir=/other/path prompt`
- **THEN** 系统在指定目录创建新会话（现有行为不变）
- **AND** 不影响活跃的默认会话

#### Scenario: /new 无参数不受影响
- **WHEN** `DEFAULT_CHAT_DIR` 已配置
- **AND** 用户发送 `/new`（无参数）
- **THEN** 系统发送目录选择卡片（现有行为不变）

#### Scenario: 未配置默认目录
- **WHEN** `DEFAULT_CHAT_DIR` 未配置（为空）
- **THEN** 所有行为与现有逻辑一致，普通消息发送使用提示，`/new prompt` 发送目录选择卡片

#### Scenario: 服务启动时目录不存在
- **WHEN** `DEFAULT_CHAT_DIR` 已配置
- **AND** 指定的目录路径不存在
- **THEN** 系统在启动时自动创建该目录（包括中间目录）
