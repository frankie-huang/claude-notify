## ADDED Requirements

### Requirement: 飞书网关决策转发

飞书网关 SHALL 能够解析卡片按钮中的 `callback_url`，并将决策请求转发到对应的 Callback 服务。

#### Scenario: 转发决策到 Callback 服务

- **GIVEN** 用户点击飞书卡片按钮
- **AND** 按钮 value 包含 `callback_url` 字段
- **WHEN** 网关收到 card.action.trigger 事件
- **THEN** 网关解析 `action.value.callback_url`
- **AND** POST 请求到 `${callback_url}/callback/decision`
- **AND** 请求 body 包含 `action`、`request_id`、`project_dir`
- **AND** 根据返回的 `success` 和 `decision` 生成 toast 返回给飞书

#### Scenario: callback_url 为本机时直接处理

- **GIVEN** 用户点击飞书卡片按钮
- **AND** `callback_url` 指向当前服务
- **WHEN** 网关收到 card.action.trigger 事件
- **THEN** 直接调用本地决策处理逻辑
- **AND** 不发起 HTTP 转发

#### Scenario: Callback 服务不可达

- **GIVEN** 用户点击飞书卡片按钮
- **AND** `callback_url` 指向的服务不可达
- **WHEN** 网关尝试转发决策
- **THEN** 返回错误 toast `{"type": "error", "content": "回调服务不可达，请检查服务状态"}`

### Requirement: Callback 服务纯决策端点

Callback 服务 SHALL 提供 `/callback/decision` 端点，返回纯决策结果（不包含 toast 格式）。

#### Scenario: 接收批准决策

- **GIVEN** Callback 服务正在运行
- **AND** 存在待处理的权限请求
- **WHEN** 收到 POST `/callback/decision`，body 包含 `{"action": "allow", "request_id": "xxx"}`
- **THEN** 通过 Socket 发送 `allow` 决策给 permission.sh
- **AND** 返回 `{"success": true, "decision": "allow", "message": "已批准运行"}`

#### Scenario: 接收始终允许决策

- **GIVEN** Callback 服务正在运行
- **AND** 存在待处理的权限请求
- **WHEN** 收到 POST `/callback/decision`，body 包含 `{"action": "always", "request_id": "xxx", "project_dir": "/path/to/project"}`
- **THEN** 通过 Socket 发送 `allow` 决策给 permission.sh
- **AND** 将权限规则写入项目的 `.claude/settings.local.json`
- **AND** 返回 `{"success": true, "decision": "allow", "message": "已始终允许，后续相同操作将自动批准"}`

#### Scenario: 接收拒绝决策

- **GIVEN** Callback 服务正在运行
- **AND** 存在待处理的权限请求
- **WHEN** 收到 POST `/callback/decision`，body 包含 `{"action": "deny", "request_id": "xxx"}`
- **THEN** 通过 Socket 发送 `deny` 决策给 permission.sh
- **AND** 返回 `{"success": true, "decision": "deny", "message": "已拒绝运行"}`

#### Scenario: 接收拒绝并中断决策

- **GIVEN** Callback 服务正在运行
- **AND** 存在待处理的权限请求
- **WHEN** 收到 POST `/callback/decision`，body 包含 `{"action": "interrupt", "request_id": "xxx"}`
- **THEN** 通过 Socket 发送 `deny` 决策（带 `interrupt: true`）给 permission.sh
- **AND** 返回 `{"success": true, "decision": "deny", "message": "已拒绝并中断"}`

#### Scenario: 请求不存在

- **GIVEN** Callback 服务正在运行
- **WHEN** 收到 `/callback/decision` 请求，但 `request_id` 不存在
- **THEN** 返回 `{"success": false, "decision": null, "message": "请求不存在或已过期"}`

## MODIFIED Requirements

### Requirement: 卡片按钮回调格式

飞书卡片按钮 MUST 使用 `callback` 行为类型，以支持在飞书内直接响应用户操作。**按钮 value MUST 包含 `callback_url` 字段用于网关路由。**

#### Scenario: 按钮使用回调行为

- **GIVEN** 发送权限请求卡片（OpenAPI 模式）
- **WHEN** 卡片被渲染
- **THEN** 四个按钮的 `behaviors` 都使用 `type: callback`
- **AND** 每个按钮的 `value` 包含 `action`、`request_id`、`callback_url` 字段

#### Scenario: 按钮 value 格式

- **GIVEN** 需要构建权限请求卡片按钮
- **WHEN** 构建按钮 JSON
- **THEN** value 格式为：
  ```json
  {
    "action": "allow|always|deny|interrupt",
    "request_id": "1234567890-abcd1234",
    "callback_url": "http://callback-server:8080"
  }
  ```
