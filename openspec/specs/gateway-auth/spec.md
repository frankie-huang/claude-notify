# gateway-auth Specification

## Purpose

定义飞书网关与 Callback 后端的双向认证机制，确保只有授权的后端才能与网关通信，防止未授权访问。

## Requirements

### Requirement: 飞书网关注册接口

飞书网关 MUST 提供 `POST /register` 接口，接收 Callback 后端的注册请求。

#### Scenario: 接收注册请求

- **GIVEN** 飞书网关正在运行
- **WHEN** 收到 POST `/register` 请求
- **AND** 请求 body 包含 `callback_url` 和 `owner_id`
- **THEN** 立即返回 `200` 状态码
- **AND** 返回 `{"status": "accepted", "message": "注册请求已接收，正在处理"}`

#### Scenario: 请求参数缺失

- **GIVEN** 飞书网关正在运行
- **WHEN** 收到 POST `/register` 请求
- **AND** 请求 body 缺少 `callback_url` 或 `owner_id`
- **THEN** 返回 `400` 状态码
- **AND** 返回 `{"error": "missing required fields: callback_url, owner_id"}`

#### Scenario: 异步处理注册

- **GIVEN** 飞书网关返回注册成功响应
- **WHEN** 后续查询映射表
- **THEN** 根据绑定状态决定：
  - 已绑定：直接调用 Callback 后端的 `/register-callback` 接口
  - 未绑定：向用户发送飞书授权卡片

### Requirement: 绑定关系存储

飞书网关 MUST 维护 `owner_id` 到 `callback_url` 和 `auth_token` 的映射关系。

#### Scenario: 创建新绑定

- **GIVEN** 用户授权新设备注册
- **WHEN** 创建绑定记录
- **THEN** 保存 `owner_id`、`callback_url`、`auth_token`、`updated_at`
- **AND** 持久化到 `runtime/bindings.json`

#### Scenario: 更新现有绑定

- **GIVEN** `owner_id` 已存在绑定
- **WHEN** 同一 `owner_id` 的新注册请求被授权
- **THEN** 覆盖原有的 `callback_url` 和 `auth_token`
- **AND** 更新 `updated_at` 时间戳

#### Scenario: 查询绑定

- **GIVEN** 绑定关系已创建
- **WHEN** 使用 `owner_id` 查询
- **THEN** 返回对应的 `callback_url` 和 `auth_token`
- **OR** 返回 `null`（如果不存在）

#### Scenario: 绑定持久化

- **GIVEN** 飞书网关重启
- **WHEN** 网关启动
- **THEN** 从 `runtime/bindings.json` 加载已有绑定

### Requirement: auth_token 生成

飞书网关 MUST 使用 HMAC-SHA256 算法生成 `auth_token`。

#### Scenario: 生成 auth_token

- **GIVEN** 需要为 `owner_id` 生成 auth_token
- **WHEN** 调用生成函数
- **THEN** 生成当前 Unix 时间戳
- **AND** 计算 `signature = HMAC-SHA256(FEISHU_VERIFICATION_TOKEN, owner_id + timestamp)`
- **AND** 返回 `base64url(timestamp) + "." + base64url(signature)`

#### Scenario: 验证 auth_token

- **GIVEN** 收到 `auth_token` 和 `owner_id`
- **WHEN** 验证 token 有效性
- **THEN** 解析 token 获取 timestamp 和 signature
- **AND** 重新计算 `expected_signature = HMAC-SHA256(FEISHU_VERIFICATION_TOKEN, owner_id + timestamp)`
- **AND** 使用恒定时间比较 signature 和 expected_signature
- **AND** 返回验证结果

### Requirement: Callback 后端注册回调接口

Callback 后端 MUST 提供 `POST /register-callback` 接口，接收网关的 auth_token。

#### Scenario: 接收 auth_token

- **GIVEN** Callback 后端正在运行
- **WHEN** 收到 POST `/register-callback` 请求
- **AND** 请求 body 包含 `owner_id` 和 `auth_token`
- **THEN** 验证 `owner_id` 与配置的 `FEISHU_OWNER_ID` 一致
- **AND** 存储 `auth_token` 到内存/文件
- **AND** 返回 `{"status": "ok", "message": "注册成功"}`

#### Scenario: owner_id 不匹配

- **GIVEN** Callback 后端正在运行
- **WHEN** 收到 POST `/register-callback` 请求
- **AND** 请求 body 中的 `owner_id` 与配置不一致
- **THEN** 返回 `403` 状态码
- **AND** 返回 `{"error": "owner_id mismatch"}`

### Requirement: 飞书授权卡片

飞书网关 MUST 向用户发送授权卡片，请求用户确认新设备注册。

#### Scenario: 发送授权卡片

- **GIVEN** 收到新的注册请求
- **AND** `owner_id` 未绑定任何 callback_url
- **WHEN** 处理注册请求
- **THEN** 向 `owner_id` 发送飞书卡片消息
- **AND** 卡片包含：来源 IP、Callback URL、允许按钮、拒绝按钮

#### Scenario: 用户允许注册

- **GIVEN** 用户点击授权卡片中的"允许"按钮
- **WHEN** 网关收到 `card.action.trigger` 事件
- **AND** `action.value.action` 为 `approve_register`
- **THEN** 调用 `action.value.callback_url` 指向的 `/register-callback` 接口
- **AND** 传递 `owner_id` 和生成的 `auth_token`
- **AND** 创建绑定记录
- **AND** 返回 `{"toast": {"type": "success", "content": "已授权绑定"}}`

#### Scenario: 用户拒绝注册

- **GIVEN** 用户点击授权卡片中的"拒绝"按钮
- **WHEN** 网关收到 `card.action.trigger` 事件
- **AND** `action.value.action` 为 `deny_register`
- **THEN** 不创建绑定记录
- **AND** 记录日志
- **AND** 返回 `{"toast": {"type": "info", "content": "已拒绝注册请求"}}`

### Requirement: 双向认证

飞书网关和 Callback 后端 MUST 在请求中携带 `auth_token` 进行身份验证。

#### Scenario: 网关转发消息携带 Token

- **GIVEN** 网关需要向 Callback 后端转发消息
- **AND** 存在有效的 `auth_token`
- **WHEN** 发送 HTTP 请求
- **THEN** 在请求头中添加 `X-Auth-Token: {auth_token}`

#### Scenario: 网关验证请求 Token

- **GIVEN** 网关收到 Callback 后端的请求
- **WHEN** 请求包含 `X-Auth-Token` 请求头
- **THEN** 解析 token 验证签名
- **AND** 验证 `owner_id` 与绑定关系一致
- **AND** 验证通过则处理请求
- **OR** 验证失败则返回 `401 Unauthorized`

#### Scenario: Callback 后端发送消息携带 Token

- **GIVEN** Callback 后端需要向网关发送消息
- **AND** 已存储有效的 `auth_token`
- **WHEN** 发送 HTTP 请求
- **THEN** 在请求头中添加 `X-Auth-Token: {auth_token}`

#### Scenario: Callback 后端验证请求 Token（可选）

- **GIVEN** Callback 后端收到网关的请求
- **WHEN** 请求包含 `X-Auth-Token` 请求头
- **THEN** 可选验证 token 与存储的一致
- **AND** 验证失败可返回 `401 Unauthorized`
