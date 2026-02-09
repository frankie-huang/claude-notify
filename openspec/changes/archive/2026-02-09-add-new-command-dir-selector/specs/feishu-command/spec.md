# feishu-command Delta Specification

## ADDED Requirements

### Requirement: /new 指令缺少目录时发送选择卡片

当用户执行 `/new` 指令但未指定工作目录时，系统 SHALL 发送飞书交互式卡片而非纯文本错误提示。

#### Scenario: 无参数 /new 指令

- **GIVEN** 飞书网关收到 `/new` 指令
- **AND** 指令不包含 `--dir=` 参数
- **AND** 消息不是回复消息（无 parent_id）
- **WHEN** 网关处理该指令
- **THEN** 发送工作目录选择卡片
- **AND** 卡片包含下拉菜单组件（显示常用目录）
- **AND** 卡片包含提交按钮
- **AND** 不转发请求到 Callback 后端

#### Scenario: 回复消息无目录映射时发送选择卡片

- **GIVEN** 用户回复某条消息，内容为 `/new prompt`
- **AND** 被回复消息的 `parent_id` 在 SessionStore 中无映射
- **WHEN** 网关处理该指令
- **THEN** 发送工作目录选择卡片
- **AND** 卡片 value 中包含原始 prompt 内容

#### Scenario: 卡片包含常用目录列表

- **GIVEN** 用户有历史使用记录
- **AND** 常用目录为 ["/home/user/project1", "/home/user/project2", "/home/user/project3"]
- **WHEN** 构建目录选择卡片
- **THEN** 下拉菜单包含 3 个选项
- **AND** 选项按使用频率降序排列
- **AND** 最多显示 5 个常用目录
- **AND** 默认选中最近使用的目录

### Requirement: 常用目录历史记录

系统 SHALL 记录用户的工作目录使用历史，用于生成常用目录列表。

#### Scenario: 记录目录使用

- **GIVEN** 用户成功创建会话
- **AND** project_dir 为 "/home/user/project"
- **AND** sender_id 为 "ou_xxx"
- **WHEN** 会话创建完成
- **THEN** 记录该目录使用次数 +1
- **AND** 更新 last_used 时间戳

#### Scenario: 获取常用目录列表

- **GIVEN** 用户有以下使用记录：
  - "/home/user/project1": 使用 5 次，最近 1 天前
  - "/home/user/project2": 使用 3 次，最近 2 小时前
  - "/home/user/project3": 使用 3 次，最近 5 天前
- **WHEN** 查询常用目录（limit=5）
- **THEN** 返回 ["/home/user/project1", "/home/user/project2", "/home/user/project3"]
- **AND** project1 排第一（次数最多）
- **AND** project2 排第二（次数相同，但更近）
- **AND** project3 排第三

#### Scenario: 历史记录自动清理

- **GIVEN** 用户有 25 条不同的目录历史记录
- **AND** 其中 10 条超过 30 天未使用
- **WHEN** 记录新的目录使用
- **THEN** 自动清理超过 30 天的记录
- **AND** 保留最近使用的 20 条记录

### Requirement: 目录选择卡片回调处理

系统 SHALL 处理用户在目录选择卡片中提交的操作。

#### Scenario: 用户选择目录并提交

- **GIVEN** 用户收到目录选择卡片
- **AND** 用户从下拉菜单选择 "/home/user/project"
- **AND** 用户点击"创建会话"按钮
- **WHEN** 飞书网关收到 card.action.trigger 事件
- **THEN** 立即返回 toast 提示"正在创建会话"
- **AND** 卡片更新为"处理中"状态（移除按钮）
- **AND** 在后台线程中异步执行会话创建
- **AND** 创建完成后发送新的飞书消息通知

#### Scenario: 目录不存在时的处理

- **GIVEN** 用户选择不存在的目录 "/nonexistent/path"
- **AND** 用户点击"创建会话"按钮
- **WHEN** 后台线程验证目录
- **THEN** 验证失败
- **AND** 发送新的飞书消息通知错误信息
- **AND** 用户可以重新发送 `/new` 指令

#### Scenario: 会话创建成功后发送通知

- **GIVEN** 用户选择目录并提交
- **AND** 后台线程成功创建会话
- **AND** session_id 为 "abc123"
- **WHEN** 会话创建完成
- **THEN** 发送新的飞书消息
- **AND** 消息内容包含"会话已创建"
- **AND** 消息内容包含项目目录路径
- **AND** 消息内容包含 session_id 前 8 位

### Requirement: 卡片动态更新

目录选择卡片 SHALL 支持根据操作结果动态更新显示内容。

#### Scenario: 提交成功后的卡片状态

- **GIVEN** 用户成功创建会话
- **AND** project_dir 为 "/home/user/project"
- **AND** session_id 为 "abc123..."
- **WHEN** 构建成功状态卡片
- **THEN** 卡片标题为"✓ 会话已创建"
- **AND** 内容包含项目目录路径
- **AND** 内容包含 session_id（前 8 位）
- **AND** 无任何操作按钮

#### Scenario: 提交失败后的卡片状态

- **GIVEN** 用户选择目录并提交
- **AND** 目录验证失败
- **AND** 错误信息为"目录不存在"
- **WHEN** 构建失败状态卡片
- **THEN** 卡片标题为"✗ 创建失败"
- **AND** 内容显示错误原因
- **AND** 保留下拉菜单和提交按钮
- **AND** 允许用户重新选择

## MODIFIED Requirements

### Requirement: /new 指令参数格式

`/new` 指令 SHALL 支持 `--dir=` 参数指定工作目录，同时也支持交互式目录选择。

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
