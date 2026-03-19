## ADDED Requirements

### Requirement: AskUserQuestion 表单回调处理

回调服务器 MUST 能够处理 AskUserQuestion 飞书表单的提交回调，从 `form_value` 中提取用户选择并构造 `answers` dict 回传给 permission.sh。

#### Scenario: 处理预设选项提交

- **GIVEN** 用户在飞书表单中选择了预设选项并点击"提交回答"
- **WHEN** 服务器收到表单回调，`form_value` 包含 `q_0_select` 等字段
- **AND** `q_0_custom` 为空（用户未填写自定义输入）
- **THEN** 服务器将 `q_0_select` 的值作为对应 question 的 answer
- **AND** 构造 `answers` dict（key 为 question 文本，value 为选中的 option label）
- **AND** 通过决策接口返回 `action=answer` + `answers` + 原始 `questions`

#### Scenario: 处理自定义输入提交

- **GIVEN** 用户在飞书表单中填写了自定义文本框（`q_0_custom` 有值）
- **WHEN** 服务器收到表单回调
- **THEN** 单选时：自定义输入优先覆盖 `q_0_select` 的值
- **AND** 多选时：自定义输入追加到 `q_0_select` 选中的选项列表中
- **AND** 构造 `answers` dict 中该问题的 value 包含自定义文本

#### Scenario: 处理拒绝回答操作

- **GIVEN** 用户点击飞书表单中的"拒绝回答"按钮
- **WHEN** 服务器收到回调（`action=deny`）
- **THEN** 通过通用权限决策路径（`_forward_permission_request`）转发给 callback 服务
- **AND** 服务器返回 deny 决策给 permission.sh
- **AND** 返回 `{"toast": {"type": "warning", "content": "已拒绝运行"}}` 响应

#### Scenario: 处理拒绝并中断操作

- **GIVEN** 用户点击飞书表单中的"拒绝并中断"按钮
- **WHEN** 服务器收到回调（`action=interrupt`）
- **THEN** 通过通用权限决策路径（`_forward_permission_request`）转发给 callback 服务
- **AND** 服务器返回 deny + interrupt 决策给 permission.sh
- **AND** 返回 `{"toast": {"type": "warning", "content": "已拒绝并中断"}}` 响应

## MODIFIED Requirements

### Requirement: Callback 服务纯决策端点

Callback 服务 SHALL 提供 `/cb/decision` 端点，返回纯决策结果（不包含 toast 格式）。

#### Scenario: 接收批准决策

- **GIVEN** Callback 服务正在运行
- **AND** 存在待处理的权限请求
- **WHEN** 收到 POST `/cb/decision`，body 包含 `{"action": "allow", "request_id": "xxx"}`
- **THEN** 通过 Socket 发送 `allow` 决策给 permission.sh
- **AND** 返回 `{"success": true, "decision": "allow", "message": "已批准运行"}`

#### Scenario: 接收始终允许决策

- **GIVEN** Callback 服务正在运行
- **AND** 存在待处理的权限请求
- **WHEN** 收到 POST `/cb/decision`，body 包含 `{"action": "always", "request_id": "xxx", "project_dir": "/path/to/project"}`
- **THEN** 通过 Socket 发送 `allow` 决策给 permission.sh
- **AND** 将权限规则写入项目的 `.claude/settings.local.json`
- **AND** 返回 `{"success": true, "decision": "allow", "message": "已始终允许，后续相同操作将自动批准"}`

#### Scenario: 接收拒绝决策

- **GIVEN** Callback 服务正在运行
- **AND** 存在待处理的权限请求
- **WHEN** 收到 POST `/cb/decision`，body 包含 `{"action": "deny", "request_id": "xxx"}`
- **THEN** 通过 Socket 发送 `deny` 决策给 permission.sh
- **AND** 返回 `{"success": true, "decision": "deny", "message": "已拒绝运行"}`

#### Scenario: 接收拒绝并中断决策

- **GIVEN** Callback 服务正在运行
- **AND** 存在待处理的权限请求
- **WHEN** 收到 POST `/cb/decision`，body 包含 `{"action": "interrupt", "request_id": "xxx"}`
- **THEN** 通过 Socket 发送 `deny` 决策（带 `interrupt: true`）给 permission.sh
- **AND** 返回 `{"success": true, "decision": "deny", "message": "已拒绝并中断"}`

#### Scenario: 接收 AskUserQuestion 回答

- **GIVEN** Callback 服务正在运行
- **AND** 存在待处理的 AskUserQuestion 权限请求
- **WHEN** 收到 POST `/cb/decision`，body 包含 `{"action": "answer", "request_id": "xxx", "answers": {...}, "questions": [...]}`
- **THEN** 通过 Socket 发送 `allow` 决策 + `updated_input`（包含 answers 和 questions）给 permission.sh
- **AND** 返回 `{"success": true, "decision": "allow", "message": "已提交回答"}`

#### Scenario: 接收拒绝回答操作

- **GIVEN** Callback 服务正在运行
- **AND** 存在待处理的 AskUserQuestion 权限请求
- **WHEN** 收到 POST `/cb/decision`，body 包含 `{"action": "deny", "request_id": "xxx"}`
- **THEN** 通过 Socket 发送 `deny` 决策给 permission.sh
- **AND** 返回 `{"success": true, "decision": "deny", "message": "已拒绝回答"}`

#### Scenario: 请求不存在

- **GIVEN** Callback 服务正在运行
- **WHEN** 收到 `/cb/decision` 请求，但 `request_id` 不存在
- **THEN** 返回 `{"success": false, "decision": null, "message": "请求不存在或已过期"}`
