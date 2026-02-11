# permission-notify Specification (Delta)

## Purpose

优化 Stop 事件通知的内容提取逻辑和卡片展示。

## ADDED Requirements

### Requirement: 多消息响应内容聚合

Stop 事件通知 SHALL 提取最近一条用户文本消息之后所有 assistant 消息的文本内容，而非仅最后一条 assistant 消息。

#### Scenario: 用户消息后有多条 assistant text 消息

- **GIVEN** JSONL transcript 中最近一条用户文本消息之后存在多条 `type=="assistant"` 消息
- **AND** 每条 assistant 消息的 `message.content` 中包含 `type=="text"` 块
- **WHEN** Stop 事件提取响应内容
- **THEN** 系统收集所有这些 text 块的文本内容
- **AND** 使用双换行符 `\n\n` 拼接为完整响应

#### Scenario: 识别用户文本消息

- **GIVEN** JSONL transcript 包含多种类型的 user 消息
- **WHEN** 系统查找最近一条用户文本消息
- **THEN** 系统从末尾向前遍历，找到第一条满足以下条件的 `type=="user"` 消息：
  - `message.content` 为非空字符串，或
  - `message.content` 数组中包含 `type=="text"` 的元素（排除仅含 `tool_result` 的消息）

#### Scenario: 无用户文本消息时回退

- **GIVEN** JSONL transcript 中不存在符合条件的用户文本消息
- **WHEN** Stop 事件提取响应内容
- **THEN** 系统从所有 assistant 消息中收集 text 内容
- **OR** 回退到 subagents 目录查找

### Requirement: 思考过程提取与展示

Stop 事件通知 SHALL 支持提取并展示 Claude 的思考过程（thinking），使用飞书折叠面板组件呈现。

#### Scenario: 提取 thinking 内容

- **GIVEN** assistant 消息的 `message.content` 中包含 `type=="thinking"` 块
- **WHEN** Stop 事件提取响应内容
- **THEN** 系统同时收集 thinking 块的 `thinking` 字段文本
- **AND** 多条 thinking 使用双换行符 `\n\n` 拼接

#### Scenario: 飞书卡片展示 thinking

- **GIVEN** 提取到非空的 thinking 内容
- **WHEN** 构建 Stop 事件飞书卡片
- **THEN** 卡片在"答复"区域之前展示思考过程
- **AND** 使用飞书 `collapsible_panel` 组件
- **AND** 面板默认折叠（`expanded: false`）
- **AND** 面板标题为"思考过程"

#### Scenario: 无 thinking 内容时不展示

- **GIVEN** 未提取到 thinking 内容（thinking 为空字符串）
- **WHEN** 构建 Stop 事件飞书卡片
- **THEN** 卡片不包含思考过程区域
- **AND** 卡片布局与当前版本完全一致

#### Scenario: thinking 内容截断

- **GIVEN** thinking 内容长度超过 `STOP_THINKING_MAX_LENGTH` 配置值
- **WHEN** 构建通知内容
- **THEN** thinking 内容截断到配置长度
- **AND** 末尾添加 "..."

#### Scenario: 禁用 thinking 展示

- **GIVEN** `STOP_THINKING_MAX_LENGTH` 配置为 `0`
- **WHEN** Stop 事件提取响应内容
- **THEN** 跳过 thinking 内容提取
- **AND** 卡片不包含思考过程区域

### Requirement: STOP_THINKING_MAX_LENGTH 配置

系统 SHALL 支持 `STOP_THINKING_MAX_LENGTH` 环境变量配置 thinking 内容的最大展示长度。

#### Scenario: 默认值

- **GIVEN** 未配置 `STOP_THINKING_MAX_LENGTH`
- **WHEN** 系统读取配置
- **THEN** 使用默认值 `5000` 字符

#### Scenario: 自定义值

- **GIVEN** `.env` 文件中配置 `STOP_THINKING_MAX_LENGTH=1000`
- **WHEN** 系统读取配置
- **THEN** 使用配置值 `1000` 作为最大长度
