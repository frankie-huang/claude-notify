# card-callback Specification

## Purpose

定义飞书卡片按钮回传交互（`card.action.trigger` 事件）的处理机制，使用户点击卡片按钮后飞书直接调用回调服务器，服务器返回 toast 提示，实现无需跳转浏览器的流畅交互体验。
## Requirements
### Requirement: 卡片回调事件处理

回调服务器 MUST 能够处理飞书 `card.action.trigger` 事件，根据按钮动作类型执行相应的权限决策。

#### Scenario: 处理批准运行回调
- **Given** 用户点击飞书卡片中的"批准运行"按钮
- **When** 服务器收到 `card.action.trigger` 事件，`action.value.action` 为 `allow`
- **Then** 服务器通过 Socket 发送 `allow` 决策给对应的 permission-notify 进程
- **And** 返回 `{"toast": {"type": "success", "content": "已批准运行"}}` 响应

#### Scenario: 处理始终允许回调
- **Given** 用户点击飞书卡片中的"始终允许"按钮
- **When** 服务器收到 `card.action.trigger` 事件，`action.value.action` 为 `always`
- **Then** 服务器通过 Socket 发送 `allow` 决策
- **And** 将权限规则写入项目的 `.claude/settings.local.json`
- **And** 返回 `{"toast": {"type": "success", "content": "已始终允许，后续相同操作将自动批准"}}` 响应

#### Scenario: 处理拒绝运行回调
- **Given** 用户点击飞书卡片中的"拒绝运行"按钮
- **When** 服务器收到 `card.action.trigger` 事件，`action.value.action` 为 `deny`
- **Then** 服务器通过 Socket 发送 `deny` 决策
- **And** 返回 `{"toast": {"type": "success", "content": "已拒绝运行"}}` 响应

#### Scenario: 处理拒绝并中断回调
- **Given** 用户点击飞书卡片中的"拒绝并中断"按钮
- **When** 服务器收到 `card.action.trigger` 事件，`action.value.action` 为 `interrupt`
- **Then** 服务器通过 Socket 发送 `deny` 决策（带 `interrupt: true`）
- **And** 返回 `{"toast": {"type": "success", "content": "已拒绝并中断"}}` 响应

### Requirement: 卡片回调错误处理

回调服务器 MUST 正确处理各种错误场景并返回适当的 toast 响应。

#### Scenario: 请求不存在
- **Given** 回调事件中的 `request_id` 在服务器中不存在
- **When** 服务器尝试处理该回调
- **Then** 返回 `{"toast": {"type": "error", "content": "请求不存在或已过期"}}` 响应

#### Scenario: 请求已处理
- **Given** 回调事件中的 `request_id` 对应的请求已被处理
- **When** 服务器尝试再次处理该回调
- **Then** 返回 `{"toast": {"type": "warning", "content": "该请求已被处理，请勿重复操作"}}` 响应

#### Scenario: Hook 进程已退出
- **Given** 回调事件中的 `request_id` 对应的 hook 进程已退出
- **When** 服务器尝试处理该回调
- **Then** 返回 `{"toast": {"type": "error", "content": "请求已失效，请返回终端查看状态"}}` 响应

#### Scenario: 缺少必要参数
- **Given** 回调事件中缺少 `action` 或 `request_id`
- **When** 服务器尝试处理该回调
- **Then** 返回 `{"toast": {"type": "error", "content": "无效的回调请求"}}` 响应

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

