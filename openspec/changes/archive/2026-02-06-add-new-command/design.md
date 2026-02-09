# Design: /new 指令实现

## Context

当前系统已支持通过飞书回复消息继续 Claude 会话（`/claude/continue`），但无法发起新会话。用户需要在终端中手动启动 Claude，然后才能在飞书中继续对话。

### 现有架构组件

| 组件 | 职责 |
|------|------|
| **飞书网关** (feishu.py) | 接收飞书事件、解析消息内容、转发请求到 Callback 后端 |
| **Callback 后端** (claude.py) | 执行 Claude 命令、管理会话 |
| **SessionStore** | 存储 message_id → {session_id, project_dir, callback_url} 映射 |
| **ChatIdStore** | 存储 session_id → chat_id 映射（用于权限/stop 事件路由） |

## Goals / Non-Goals

### Goals
- 支持用户在飞书中通过 `/new --dir=/path/to/project prompt` 格式发起新会话
- 支持回复消息时自动复用被回复消息的工作目录
- 使用 UUID 生成唯一 session_id
- 自动关联 session_id 与 chat_id，使后续权限/stop 事件能正确路由

### Non-Goals
- 不支持多项目并发切换（单次对话保持项目目录）
- 不处理会话迁移（session_id 固定绑定到创建时的工作目录）

## Decisions

### 1. 指令格式

采用 `/new --dir=/path/to/project prompt` 格式：

```bash
/new --dir=/home/user/project 帮我写一个测试文件
```

**理由**：
- `--dir=` 参数格式明确，与 Claude Code 现有参数风格一致
- 支持包含空格的路径（通过引号）
- 易于解析

### 2. 回复模式

当用户回复一条消息时：
- 如果被回复消息在 SessionStore 中有映射（即由 Claude 发送），复用其 `project_dir`
- 如果没有映射，返回错误提示用户使用 `/new` 指令并指定目录

**实现**：在 `feishu.py` 的 `_handle_message_event` 中：
1. 先检查是否是 `/new` 指令（新增）
2. 再检查是否有 `parent_id`（现有逻辑）
3. 都不是则忽略

### 3. Session 生成

使用 Python `uuid.uuid4()` 生成唯一 session_id：

```python
session_id = str(uuid.uuid4())
```

### 4. 存储结构

**SessionStore 扩展**：新建会话后，发送一条"会话已创建"消息到飞书，保存 message_id → session 映射，使后续回复能继续该会话。

**ChatIdStore**：复用现有实现，存储 `session_id → chat_id` 映射。

### 5. Claude 命令调用

```bash
cd <project_dir> && claude -p "<prompt>" --session-id <session_id>
```

与继续会话的区别：
- 继续会话：`--resume <session_id>`
- 新建会话：`--session-id <session_id>`

## 交互流程

### 场景 1：直接发起新会话

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              飞书群聊                                         │
│  用户: /new --dir=/home/user/project 帮我写一个测试文件                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                               │
                                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              飞书网关                                         │
│  im.message.receive_v1 事件:                                                 │
│  1. 解析消息: 识别 /new 指令                                                  │
│  2. 提取参数: project_dir=/home/user/project, prompt="帮我写一个测试文件"     │
│  3. 查询 auth_token（用于双向认证）                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                               │
                                               │ POST {callback_url}/claude/new
                                               │ {
                                               │   project_dir, prompt, chat_id,
                                               │   message_id
                                               │ }
                                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Callback 后端                                        │
│  1. 生成 UUID session_id                                                    │
│  2. 保存 session_id → chat_id 映射                                          │
│  3. 执行: cd <project_dir> && claude -p "<prompt>" --session-id <session_id>│
│  4. 返回: {"status": "processing", "session_id": "..."}                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                               │
                                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              飞书网关                                         │
│  收到 processing 响应:                                                        │
│  发送"会话已创建"通知到飞书，并保存 message_id → session 映射                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 场景 2：回复消息发起新会话

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              飞书群聊                                         │
│  [上一条 Claude 消息]                                                        │
│  用户: /new 帮我再加个错误处理                                                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                               │
                                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              飞书网关                                         │
│  im.message.receive_v1 事件:                                                 │
│  1. 识别 /new 指令                                                            │
│  2. 检测到 parent_id                                                         │
│  3. 查询 SessionStore: parent_id → {project_dir, ...}                        │
│  4. 使用查询到的 project_dir                                                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                               │
                                               ▼ (后续同场景 1)
```

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| 用户输入无效路径 | Callback 后端验证目录存在性，返回友好错误 |
| 并发创建多个会话 | 每次创建独立 UUID，互不影响 |
| 回复消息的 session 已过期 | SessionStore 自动清理过期映射，返回错误提示 |

## Migration Plan

无需迁移，新功能向后兼容：
- 非指令消息继续走现有回复流程
- `/new` 指令走新建会话流程

## Open Questions

- [ ] 会话创建后的"会话已创建"通知内容格式？
- [ ] 是否需要支持简写形式（如 `/new prompt` 使用默认目录）？
- [ ] 新建会话是否需要发送"正在处理"状态通知？
