## ADDED Requirements

### Requirement: AskUserQuestion 飞书卡片审批

当 Claude Code 触发 AskUserQuestion 权限请求时，系统 SHALL 构建带表单的飞书卡片，支持用户在飞书中远程选择/输入答案，并将答案通过 `updatedInput.answers` 返回给 Claude Code。

#### Scenario: 单选问题渲染为下拉选择

- **GIVEN** AskUserQuestion 的 `tool_input.questions` 包含一个 `multiSelect: false` 的问题
- **AND** 该问题有多个 `options`
- **WHEN** 系统构建飞书卡片
- **THEN** 卡片包含一个 `form` 表单
- **AND** 该问题渲染为 `select_static` 下拉组件
- **AND** 下拉选项包含所有 `options[].label`（展示为 `label - description`）
- **AND** 同时渲染一个 `input` 文本框（placeholder: "或者自定义输入（填写后会覆盖本题选项）"）

#### Scenario: 多选问题渲染为多选下拉

- **GIVEN** AskUserQuestion 的 `tool_input.questions` 包含一个 `multiSelect: true` 的问题
- **WHEN** 系统构建飞书卡片
- **THEN** 该问题渲染为 `multi_select_static` 多选下拉组件
- **AND** 同时渲染一个 `input` 文本框（placeholder: "可在此补充自定义内容"）

#### Scenario: 多问题在同一表单中渲染

- **GIVEN** AskUserQuestion 的 `questions` 数组包含多个问题
- **WHEN** 系统构建飞书卡片
- **THEN** 所有问题在同一个 `form` 中按顺序渲染
- **AND** 每个问题的表单字段名使用索引区分（`q_0_select`, `q_0_custom`, `q_1_select`, `q_1_custom`）
- **AND** 表单底部有"提交回答"、"拒绝回答"和"拒绝并中断"三个按钮

#### Scenario: 用户选择预设选项并提交

- **GIVEN** 用户在飞书卡片下拉中选择了一个预设选项且未填写自定义输入
- **WHEN** 用户点击"提交回答"按钮
- **THEN** 回调服务器从 `form_value` 中提取选择
- **AND** 构造 `answers` dict，key 为 question 文本，value 为选中的 option label
- **AND** permission.sh 输出带 `updatedInput` 的决策 JSON
- **AND** Claude Code 收到答案并继续执行

#### Scenario: 用户选择自定义输入并提交

- **GIVEN** 用户在文本框中输入了自定义内容（无论是否选择了下拉选项）
- **WHEN** 用户点击"提交回答"按钮
- **THEN** 单选时：自定义输入优先覆盖下拉选项值
- **AND** 多选时：自定义输入追加到选中的选项列表中
- **AND** permission.sh 输出带自定义答案的 `updatedInput` 决策 JSON

#### Scenario: 用户点击拒绝回答按钮

- **GIVEN** 用户不想回答这个问题
- **WHEN** 用户点击"拒绝回答"按钮
- **THEN** 回调服务器返回 deny 决策
- **AND** permission.sh 输出 `{"behavior": "deny"}`
- **AND** Claude Code 收到拒绝，AskUserQuestion 返回空答案

#### Scenario: 用户点击拒绝并中断按钮

- **GIVEN** 用户不想回答这个问题并想中断当前会话
- **WHEN** 用户点击"拒绝并中断"按钮
- **THEN** 回调服务器返回 deny + interrupt 决策
- **AND** permission.sh 输出 `{"behavior": "deny", "message": "用户拒绝并中断", "interrupt": true}`
- **AND** Claude Code 收到拒绝并中断当前会话

#### Scenario: 用户未操作超时（交互模式）

- **GIVEN** 用户在交互模式下运行 Claude Code
- **AND** 飞书卡片已发送但用户未点击任何按钮
- **WHEN** 等待超时
- **THEN** permission.sh 以 `EXIT_FALLBACK` 退出
- **AND** Claude Code 回退到终端交互模式

#### Scenario: 用户未操作超时（MCP 非交互模式）

- **GIVEN** 用户在非交互模式下运行 Claude Code（`claude -p`）
- **AND** 飞书卡片已发送但用户未点击任何按钮
- **WHEN** 等待超时
- **THEN** permission.sh 返回 deny 决策（默认行为）
- **AND** Claude Code 收到空答案

#### Scenario: updatedInput 响应格式

- **GIVEN** 回调服务器已构造好 answers dict
- **WHEN** permission.sh 输出决策
- **THEN** 输出的 JSON 格式为：
  ```json
  {
    "hookSpecificOutput": {
      "hookEventName": "PermissionRequest",
      "decision": {
        "behavior": "allow",
        "updatedInput": {
          "answers": {"问题文本": "选中的label或自定义文本"},
          "questions": [/* 原始 questions 数组 */]
        }
      }
    }
  }
  ```

## MODIFIED Requirements

### Requirement: Permission Request Notification Script

系统 SHALL 提供 `permission-notify.sh` 脚本，当 Claude Code 发起权限请求时，通过飞书 Webhook 通知用户。

#### Scenario: Bash 命令权限请求通知

- **GIVEN** Claude Code 请求执行 Bash 命令的权限
- **WHEN** PermissionRequest hook 触发并调用 `permission-notify.sh`
- **THEN** 脚本从 stdin 读取 JSON 数据
- **AND** 解析出 `tool_name` 为 "Bash"，`tool_input.command` 为待执行命令
- **AND** 发送飞书卡片消息，包含命令内容

#### Scenario: 文件修改权限请求通知

- **GIVEN** Claude Code 请求修改文件的权限（Edit 或 Write）
- **WHEN** PermissionRequest hook 触发并调用 `permission-notify.sh`
- **THEN** 脚本从 stdin 读取 JSON 数据
- **AND** 解析出 `tool_name` 为 "Edit" 或 "Write"，`tool_input.file_path` 为目标文件
- **AND** 发送飞书卡片消息，包含文件路径信息

#### Scenario: 通用工具权限请求通知

- **GIVEN** Claude Code 请求使用其他工具的权限
- **WHEN** PermissionRequest hook 触发并调用 `permission-notify.sh`
- **THEN** 脚本从 stdin 读取 JSON 数据
- **AND** 发送飞书卡片消息，显示工具名称和基本请求信息

#### Scenario: AskUserQuestion 权限请求

- **GIVEN** Claude Code 触发 AskUserQuestion 权限请求
- **WHEN** PermissionRequest hook 触发
- **THEN** 系统构建带表单的飞书卡片（而非仅通知卡片）
- **AND** 卡片包含问题选项的下拉选择和自定义输入框
- **AND** 系统通过 socket 等待用户回调（而非直接回退终端）
