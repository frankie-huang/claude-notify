# 提案：飞书网关注册与双向认证机制

## 提案 ID
`add-gateway-auth`

## 创建时间
2026-02-05

## 状态
Completed

## 概述

建立飞书网关与 Callback 后端之间的动态注册和双向认证机制。Callback 后端启动时向飞书网关注册，经用户授权后建立安全绑定关系，后续通信通过 auth_token 进行双向验证。

## 动机

### 当前问题
1. Callback 后端与飞书网关之间缺乏动态注册机制，需要手动配置绑定关系
2. 没有双向认证，无法验证请求来源的合法性
3. 多 Callback 后端场景下，消息路由缺乏安全保障

### 期望效果
1. Callback 后端启动时自动向飞书网关注册
2. 用户通过飞书卡片确认授权，防止未授权后端劫持消息
3. 双向认证确保通信安全
4. 新设备注册自动覆盖旧设备，无需显式解绑

## 涉及能力

1. **gateway-auth**: 新增能力，实现网关注册与认证
   - 注册接口：Callback 后端启动时主动注册
   - 授权卡片：未绑定时向用户发送确认请求
   - Token 生成与验证：HMAC-SHA256 签名机制
   - 绑定管理：owner_id ↔ callback_url 映射表

## 架构影响

### 分离部署模式
本方案基于**分离模式**设计：
- **飞书网关**：维护 owner_id → callback_url 映射表，生成和验证 auth_token
- **Callback 后端**：启动时注册，接收并存储 auth_token

### 数据流
```
Callback 后端启动
    ↓
POST /register {callback_url, owner_id}
    ↓
飞书网关查询映射表
    ├── 已绑定 → 回调通知 auth_token
    └── 未绑定 → 发飞书卡片 → 用户确认 → 回调通知 auth_token
```

### 映射表结构
```
owner_id   | callback_url        | auth_token      | updated_at
-----------|---------------------|-----------------|------------------
ou_xxx     | https://callback... | abc123.def456   | 2025-02-05 10:30
```

## 实现范围

### 飞书网关侧
1. 新增 `POST /register` 接口接收注册请求
2. 实现 `BindingStore` 服务管理映射关系
3. 实现 auth_token 生成逻辑（HMAC-SHA256）
4. 实现注册回调逻辑，调用 Callback 后端的 `/register-callback`
5. 实现飞书授权卡片发送与按钮处理
6. 现有接口增加 auth_token 验证

### Callback 后端侧
1. 启动时调用网关注册接口
2. 新增 `POST /register-callback` 接口接收 auth_token
3. 存储 auth_token 用于后续请求
4. 向网关发送请求时携带 auth_token

## 配置变更

新增配置项：
```bash
# Callback 后端
CALLBACK_SERVER_URL=https://callback.example.com  # 已有，复用
FEISHU_OWNER_ID=ou_xxx                           # 新增
FEISHU_GATEWAY_URL=https://gateway.../register  # 新增

# 飞书网关
FEISHU_VERIFICATION_TOKEN=your_secret_token      # 已有，复用
```

## 依赖关系

- 依赖 `session-continue` 规范中的 `CALLBACK_SERVER_URL` 配置
- 依赖 `card-callback` 规范中的卡片交互机制
- 依赖现有飞书 OpenAPI 集成

## 风险与限制

| 风险 | 缓解措施 |
|------|----------|
| 网关回调失败（Callback 不可达） | 注册失败不处理，下次重启重新注册 |
| Token 泄露 | 使用 HMAC 签名，无法伪造；每次重启更新 |
| 用户拒绝授权 | Callback 后端无法正常工作，需要排查 |
| 网络可达性 | 假设 Callback 后端必须公网可访问 |

## 向后兼容性

- 不影响现有功能
- 未注册的 Callback 后端仍可正常工作（单机模式）
- 未携带 auth_token 的请求网关可选择接受或拒绝

## 测试计划

1. 单机模式测试（无需注册）
2. 新 Callback 后端注册测试（用户授权）
3. 已绑定 Callback 后端重启测试（直接更新 token）
4. auth_token 验证测试
5. 网络异常场景测试
