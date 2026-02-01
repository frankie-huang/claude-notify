# 提案：飞书消息回复继续 Claude 会话

## 提案 ID
`add-session-continue`

## 创建时间
2026-02-01

## 状态
Draft

## 概述

用户可以通过回复飞书通知消息，在对应的 Claude session 中继续发起提问。支持两种场景：
1. **Stop 事件**：任务完成通知卡片
2. **权限请求**：权限请求通知卡片

这允许用户在不返回终端的情况下继续与 Claude 交互。

## 动机

### 当前问题
1. 用户收到 Claude 完成通知或权限请求后，如果需要继续提问，必须返回终端手动执行命令
2. 多机器/多项目场景下，用户需要切换到对应的环境才能继续
3. 移动端用户无法方便地继续会话
4. 权限请求期间，用户可能有额外的上下文需要提供给 Claude

### 期望效果
1. 用户直接在飞书中回复消息即可继续提问
2. 飞书网关自动识别回复的消息，路由到对应的 Callback 后端
3. Callback 后端恢复 Claude 会话并执行命令，结果通过 hook 发送到飞书
4. 支持 Stop 通知和权限请求两种场景的继续会话

## 涉及能力

1. **session-continue**: 新增能力，实现消息回复继续会话
   - 映射管理：message_id → session 信息的存储与查询
   - 消息处理：识别回复消息并转发到 Callback 后端
   - 会话恢复：Callback 后端执行 `claude --resume` 命令
   - **多场景支持**：Stop 事件通知、权限请求通知

## 架构影响

### 分离部署模式
本方案基于**分离模式**设计：
- **飞书网关**：独立服务，维护 message_id → session 映射表
- **Callback 后端**：可能有多个，每个对应不同的项目/机器

### 数据流
```
用户回复消息 (parent_id = om_xxx)
    ↓
飞书网关 (im.message.receive_v1)
    ↓ 查询映射: parent_id → {session_id, project_dir, callback_url}
    ↓
POST {callback_url}/claude/continue
    ↓
Callback 后端: claude -p "..." --resume <session_id>
```

## 实现范围

### 第一阶段：映射注册
- 新增 `SessionStore` 服务
- 修改 `stop.sh` 传递 session_id、project_dir、callback_url
- 修改 `permission.sh` 传递 session_id、project_dir、callback_url
- 修改 `feishu.sh` 在请求体中添加这些字段
- 修改 `feishu.py` 发送成功后保存映射

### 第二阶段：消息处理
- 扩展 `_handle_message_event` 识别回复消息
- 新增 `/claude/continue` 接口
- 实现 Claude 异步调用

### 第三阶段：优化体验
- 错误处理和友好提示
- 过期清理机制
- 监控和日志

## 配置变更

复用现有配置 `CALLBACK_SERVER_URL`：
```bash
# Callback 服务对外可访问的地址
# 用于权限按钮回调、会话继续回调等
CALLBACK_SERVER_URL=http://localhost:8080
```

## 依赖关系

- 依赖 `permission-notify` 规范中的 `CALLBACK_SERVER_URL` 配置
- 依赖 `card-callback` 规范中的回调机制设计
- 依赖 `feishu-card-format` 规范中的卡片格式

## 风险与限制

| 风险 | 缓解措施 |
|------|----------|
| 会话已过期/删除 | Claude 返回错误，hook 发送友好提示 |
| 长时间运行导致超时 | 异步执行 Claude，先返回 "processing" |
| Callback 不可达 | 飞书网关记录错误日志，考虑重试机制 |
| 映射数据无限增长 | 7 天过期自动清理 |

## 向后兼容性

- 不影响现有功能
- 未传递 session_id/project_dir/callback_url 时，跳过映射注册
- 回复未注册的消息时，忽略处理

## 测试计划

1. 单机模式测试
2. 分离部署测试（多个 Callback 后端）
3. 会话过期场景测试
4. 错误处理测试
