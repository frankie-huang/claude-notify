## Context

飞书网关与 Callback 后端需要建立安全的通信机制。当前设计缺乏：
1. 动态注册 - Callback 后端无法自动向网关注册
2. 身份验证 - 无法验证请求来源的合法性
3. 用户授权 - 新设备注册需要用户确认

## Goals / Non-Goals

### Goals
- Callback 后端启动时自动向网关注册
- 用户通过飞书卡片确认新设备授权
- 双向认证确保通信安全（HMAC-SHA256）
- 一用户一设备，新设备覆盖旧设备

### Non-Goals
- 多设备同时绑定（一个用户只能有一个活跃 Callback 后端）
- Token 过期机制（Token 永久有效，重启后更新）
- 显式解绑操作（新注册自动覆盖）
- IP 白名单（仅记录 IP 用于展示）

## Decisions

### Decision 1: auth_token 格式

**选择**: `{base64url(timestamp)}.{base64url(signature)}`

**原因**:
- 点分隔符清晰易解析
- timestamp 便于追溯生成时间（虽然不验证过期）
- signature 使用 HMAC-SHA256，安全性高

**替代方案**:
- JWT: 过于复杂，无需过期声明和额外头部
- 纯随机字符串: 无法验证，只能比对存储

### Decision 2: 签名算法

**选择**: HMAC-SHA256

**原因**:
- 对称加密，网关和 Callback 后端共享密钥（FEISHU_VERIFICATION_TOKEN）
- 验证速度快
- 抗重放：签名包含 owner_id 和 timestamp

**安全保证**:
| 场景 | 能否伪造 |
|------|----------|
| 第三方无密钥 | ❌ |
| Callback 后端伪造其他用户 | ❌（签名含 owner_id） |

### Decision 3: 绑定覆盖策略

**选择**: 新注册自动覆盖旧绑定

**原因**:
- 用户更换设备/机器时自然迁移
- 无需维护解绑接口
- Token 更新后旧 Token 自动失效

### Decision 4: 注册失败处理

**选择**: 不处理，下次重启重新注册

**原因**:
- 简化实现
- 网关回调失败不影响 Callback 后端基本功能
- 用户可手动重启触发重新注册

## Data Structures

### 绑定表 (runtime/bindings.json)

```json
{
  "bindings": {
    "ou_xxx": {
      "callback_url": "https://callback.example.com",
      "auth_token": "abc123.def456",
      "updated_at": "2025-02-05T10:30:00Z",
      "registered_ip": "1.2.3.4"
    }
  }
}
```

### auth_token 结构

```
timestamp_b64 = base64url("1738765800")
signature_b64 = base64url(HMAC-SHA256(KEY, "ou_xxx" + "1738765800"))
auth_token = "abc123.def456"
```

## Sequence Diagrams

### 场景 1: 新设备注册

```
Callback        Gateway         Feishu API        User
   |               |                |              |
   | POST /register|                |              |
   |-------------->|                |              |
   |    200 OK     |                |              |
   |<--------------|                |              |
   |               |                |              |
   |               | 查询: 未绑定    |              |
   |               |                |              |
   |               | 发送授权卡片    |              |
   |               |--------------->|              |
   |               |                | 显示卡片     |
   |               |                |------------->|
   |               |                |              |
   |               |                |    点击允许   |
   |               |                |<-------------|
   |               |                |              |
   |               | POST /register-callback       |
   |               |-------------------------------->
   |               |           存储 token          |
   |               |<--------------------------------
   |               |    创建绑定    |              |
```

### 场景 2: 已绑定设备重启

```
Callback        Gateway         Feishu API        User
   |               |                |              |
   | POST /register|                |              |
   |-------------->|                |              |
   |    200 OK     |                |              |
   |<--------------|                |              |
   |               |                |              |
   |               | 查询: 已绑定    |              |
   |               |                |              |
   |               | POST /register-callback       |
   |               |-------------------------------->
   |               |           存储 token          |
   |               |<--------------------------------
   |               |    更新绑定    |              |
```

## Risks / Trade-offs

| Risk | Impact | Mitigation |
|------|--------|------------|
| Token 泄露 | 中 | HMAC 签名无法伪造；每次重启更新 |
| 回调失败 | 低 | 不处理，下次重启重试 |
| 网关单点 | 中 | 绑定数据持久化，重启恢复 |
| 用户误拒 | 低 | 重启 Callback 后端重新触发授权 |

## Migration Plan

**步骤**:
1. 网关新增注册接口，不影响现有功能
2. Callback 后端添加可选注册逻辑
3. 用户逐步迁移到新模式

**回滚**:
- 注册失败不影响 Callback 后端基本功能
- 可通过配置禁用注册逻辑

## Open Questions

1. **是否需要 Token 过期机制？**
   - 当前决定：不需要，重启后自动更新

2. **是否需要 IP 白名单？**
   - 当前决定：不需要，仅记录 IP 用于展示

3. **是否需要多设备绑定？**
   - 当前决定：不需要，一用户一设备
