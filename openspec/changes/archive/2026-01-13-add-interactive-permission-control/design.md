# Design: 可交互权限控制

## Context

### 背景

Claude Code 通过 PermissionRequest hook 发起权限请求，当前实现仅发送飞书通知，用户需返回终端操作。用户希望直接在飞书中点击按钮完成授权决策。

### 约束

1. **飞书自定义机器人（Webhook）不支持按钮回调** - 但支持按钮跳转 URL
2. **Claude Code hook 有超时限制** - PermissionRequest hook 默认 60 秒超时
3. **用户可能不在线** - 需要处理超时场景
4. **需要请求-响应关联** - 多个并发权限请求需要正确匹配

### 利益相关者

- 开发者（使用 Claude Code 编程）
- 运维（维护回调服务）

## Goals / Non-Goals

### Goals

- 用户可在飞书卡片中直接点击按钮控制权限请求
- 按钮操作与 Claude Code 终端行为保持一致：
  - 批准运行
  - 始终允许（新增）
  - 拒绝运行
  - 拒绝并中断
- 支持请求超时的优雅处理
- "始终允许"可持久化权限规则

### Non-Goals

- 不实现多用户权限审批流程
- 不实现权限请求历史记录持久化
- 不实现批量权限操作
- 暂不支持 `updatedInput`（修改工具输入后批准）

## Decisions

### Decision 1: 使用 URL 跳转 + 本地 HTTP 服务

**选择**: 飞书卡片按钮配置为跳转 URL，由本地 Python HTTP 服务接收请求

**原因**:
- 保持使用简单的 Webhook，无需创建飞书企业应用
- 配置简单，不需要 lark_oapi SDK
- 本地开发场景完全适用

**替代方案**:
1. 长连接 SDK - 需要创建飞书企业应用，配置复杂
2. 轮询方案 - 延迟高，用户体验差

**注意事项**:
- 用户浏览器需要能访问回调服务地址
- 远程服务器场景需要公网 IP 或内网穿透

### Decision 2: 使用 Unix Domain Socket 进行进程间通信

**选择**: HTTP 服务通过 Unix Domain Socket 将用户决策传递给 permission-notify.sh

**原因**:
- 无需网络端口冲突管理
- 性能好，延迟低
- 仅限本机通信，安全性好

**替代方案**:
1. HTTP localhost - 需要额外端口管理
2. 命名管道 (FIFO) - 单向通信，不适合请求-响应模式
3. 共享文件 + 轮询 - 延迟高，不可靠

### Decision 3: 请求 ID 使用 UUID + 时间戳

**选择**: 每个权限请求生成唯一 ID，格式为 `{timestamp}-{uuid[:8]}`

**原因**:
- UUID 保证唯一性
- 时间戳便于调试和日志分析
- 短 UUID 后缀减少 URL 长度

### Decision 4: 按钮行为与终端对齐

**选择**: 卡片按钮与 Claude Code 终端权限请求的可选操作一一对应

**Claude Code PermissionRequest 行为**:
- `allow` - 批准执行（单次）
- `allow` + 写入规则 - 始终允许（持久化）
- `deny` - 拒绝执行，Claude 可继续尝试其他方式
- `deny` + `interrupt: true` - 拒绝并中断 Claude 整个响应

**对应按钮**:
| 按钮 | 行为 | 说明 |
|------|------|------|
| 批准运行 | `allow` | 允许这一次执行 |
| 始终允许 | `allow` + 写入规则 | 允许并记住，后续自动允许 |
| 拒绝运行 | `deny` | 拒绝这一次，Claude 可继续 |
| 拒绝并中断 | `deny` + `interrupt: true` | 拒绝并停止 Claude |

### Decision 5: 始终允许的实现方式

**选择**: 点击"始终允许"时，后台服务写入规则到项目的 `.claude/settings.local.json`

**规则格式示例**:
```json
{
  "permissions": {
    "allow": [
      "Bash(npm run build)",
      "Bash(npm test:*)",
      "Edit(/path/to/file.js)"
    ]
  }
}
```

**原因**:
- 符合 Claude Code 官方权限机制
- 规则持久化，重启后仍生效
- 使用 `settings.local.json`（gitignore）避免提交到仓库

## Architecture

```
┌─────────────────┐     PermissionRequest      ┌─────────────────────┐
│   Claude Code   │ ─────── hook stdin ───────▶│ permission-notify.sh │
│                 │                            │                     │
│                 │◀──── hook stdout ──────────│  (等待用户响应)      │
│                 │      {behavior: ...}       │                     │
└─────────────────┘                            └──────────┬──────────┘
                                                          │
                                                    Unix Socket
                                                    (注册请求/等待响应)
                                                          │
                                                          ▼
                                               ┌─────────────────────┐
                                               │   Callback Server   │
                                               │   (Python HTTP)     │
                                               │                     │
                                               │  - 管理请求 ID       │
                                               │  - 发送飞书卡片      │
                                               │  - 接收 URL 回调     │
                                               │  - 写入权限规则      │
                                               │  http://localhost   │
                                               └──────────┬──────────┘
                                                          │
                                                     HTTP GET
                                                  /allow?id=xxx
                                                  /always?id=xxx
                                                  /deny?id=xxx
                                                          │
                                                          ▼
                                               ┌─────────────────────┐
                                               │     用户浏览器       │
                                               │                     │
                                               │   (点击按钮跳转)     │
                                               └──────────┬──────────┘
                                                          │
                                                     URL 跳转
                                                          │
                                               ┌─────────────────────┐
                                               │     飞书客户端       │
                                               │                     │
                                               │ [批准] [始终] [拒绝] │
                                               └─────────────────────┘
```

### 组件职责

1. **permission-notify.sh**
   - 接收 Claude Code 的权限请求 JSON
   - 生成请求 ID 并通过 Socket 发送给回调服务
   - 阻塞等待用户响应（带超时）
   - 将用户决策以 JSON 格式输出到 stdout

2. **Callback Server (Python HTTP)**
   - 常驻后台进程，监听 HTTP 端口（如 8080）
   - 发送飞书 Webhook 卡片消息（按钮为 URL 跳转）
   - 接收用户点击后的 HTTP GET 请求
   - 管理请求 ID 与决策的映射
   - 监听 Unix Socket，响应 permission-notify.sh
   - "始终允许"时写入 `.claude/settings.local.json`

3. **飞书卡片消息**
   - 显示权限请求详情
   - 包含 4 个操作按钮（URL 跳转类型）
   - URL 携带请求 ID 和操作类型

### URL 端点设计

| 端点 | 说明 |
|------|------|
| `GET /allow?id={request_id}` | 批准运行 |
| `GET /always?id={request_id}` | 始终允许 |
| `GET /deny?id={request_id}` | 拒绝运行 |
| `GET /interrupt?id={request_id}` | 拒绝并中断 |
| `GET /status` | 服务状态检查 |

## Risks / Trade-offs

### Risk 1: 回调服务宕机

**风险**: 如果回调服务未运行，权限请求将无法通过飞书控制

**缓解**:
- permission-notify.sh 检测服务状态，服务不可用时降级为仅通知模式
- 提供服务状态检查脚本

### Risk 2: 请求超时

**风险**: 用户未在 60 秒内响应，hook 超时

**缓解**:
- 卡片显示超时提示
- 超时后自动返回 `deny` 并显示超时页面

### Risk 3: 浏览器访问问题

**风险**: 远程服务器场景下，用户浏览器无法访问 localhost

**缓解**:
- 支持配置公网地址或内网穿透地址
- 环境变量 `CALLBACK_SERVER_URL` 配置

### Risk 4: 安全性

**风险**: 任何知道请求 ID 的人都可以操作权限

**缓解**:
- 请求 ID 使用足够长的随机字符串
- 请求 ID 一次性使用，处理后立即失效
- 可选：添加简单 token 验证

## Open Questions

1. **是否需要响应页面美化?** - 用户点击后显示的确认页面是否需要精心设计?
2. **是否支持自定义端口?** - 默认 8080，是否需要配置?
3. **是否需要 HTTPS?** - 本地开发 HTTP 足够，生产环境可能需要
