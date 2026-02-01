## ADDED Requirements

### Requirement: 飞书网关分离部署支持

系统 SHALL 支持将飞书网关与 Callback 服务分离部署，通过 `FEISHU_GATEWAY_URL` 配置启用分离模式。

#### Scenario: 检测分离模式

- **GIVEN** 用户配置了 `FEISHU_GATEWAY_URL` 环境变量
- **WHEN** permission.sh 初始化
- **THEN** 系统启用分离模式
- **AND** 消息发送使用 `${FEISHU_GATEWAY_URL}/feishu/send`
- **AND** 按钮 value 中包含 `callback_url: ${CALLBACK_SERVER_URL}`

#### Scenario: 未配置时使用单机模式

- **GIVEN** 用户未配置 `FEISHU_GATEWAY_URL`
- **WHEN** permission.sh 初始化
- **THEN** 系统使用原有的单机模式逻辑
- **AND** 根据 `FEISHU_SEND_MODE` 决定消息发送方式

### Requirement: 卡片按钮携带 Callback URL

飞书卡片按钮的 value MUST 包含 `callback_url` 字段，用于飞书网关路由决策请求。

#### Scenario: 按钮 value 包含 callback_url

- **GIVEN** 系统需要发送权限请求卡片
- **WHEN** 构建按钮 JSON
- **THEN** 每个按钮的 `value` 包含 `callback_url` 字段
- **AND** `callback_url` 值为 `${CALLBACK_SERVER_URL}`

#### Scenario: 向后兼容

- **GIVEN** 飞书网关未配置或使用旧版本
- **WHEN** 网关直接处理 card.action.trigger 事件
- **THEN** 网关可以忽略 `callback_url` 字段
- **AND** 直接使用本地决策处理逻辑

## MODIFIED Requirements

### Requirement: OpenAPI Message Sending Mode

系统 SHALL 支持通过飞书 OpenAPI 发送消息，作为 Webhook 的替代或补充方式。**分离模式下，消息发送统一通过飞书网关。**

#### Scenario: Webhook 模式（默认）

- **GIVEN** 用户配置 `FEISHU_SEND_MODE=webhook` 或未配置该变量
- **AND** 未配置 `FEISHU_GATEWAY_URL`
- **WHEN** 系统需要发送飞书消息
- **THEN** 使用 `FEISHU_WEBHOOK_URL` 通过 Webhook 发送
- **AND** 不需要配置应用凭证

#### Scenario: OpenAPI 模式（单机）

- **GIVEN** 用户配置 `FEISHU_SEND_MODE=openapi`
- **AND** 未配置 `FEISHU_GATEWAY_URL`
- **AND** 配置了 `FEISHU_APP_ID` 和 `FEISHU_APP_SECRET`
- **AND** 配置了 `FEISHU_RECEIVE_ID`
- **WHEN** 系统需要发送飞书消息
- **THEN** 通过飞书 OpenAPI 发送消息到指定接收者
- **AND** 自动管理 access_token（2小时有效期，提前5分钟刷新）

#### Scenario: 分离模式

- **GIVEN** 用户配置了 `FEISHU_GATEWAY_URL`
- **WHEN** 系统需要发送飞书消息
- **THEN** POST 请求到 `${FEISHU_GATEWAY_URL}/feishu/send`
- **AND** 网关负责实际的消息发送
- **AND** Callback 服务无需配置飞书凭证

#### Scenario: 接收者类型自动检测

- **GIVEN** 用户配置了 `FEISHU_RECEIVE_ID` 但未配置 `FEISHU_RECEIVE_ID_TYPE`
- **WHEN** 系统需要确定接收者类型
- **THEN** 根据 ID 前缀自动检测：`ou_` 为 open_id，`oc_` 为 chat_id，`on_` 为 union_id，包含 `@` 为 email，其他为 user_id
