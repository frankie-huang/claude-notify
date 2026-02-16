## Context

当前系统通过单一 `CLAUDE_COMMAND` 环境变量配置 Claude 命令，所有新建和继续会话共用同一命令。用户需要在不同场景下灵活切换命令（如日常使用默认 `claude`，复杂任务使用 `claude --setting opus`），但又不能允许任意自定义命令（注入风险）。

关键约束：
- Python 3.6+ 兼容
- 向后兼容现有单字符串配置
- 安全：仅允许从预配置列表选择

## Goals / Non-Goals

- Goals:
  - 支持在 `.env` 中配置多个 Claude Command 作为可选列表
  - `/new` 和 `/reply` 指令支持 `--cmd` 参数选择 Command
  - 新建会话卡片支持选择 Command
  - 每个 session 记录最近使用的 Command，后续回复自动复用
  - 完全向后兼容现有配置

- Non-Goals:
  - 不支持运行时自定义任意 Command（安全考虑）
  - 不支持每个用户独立的 Command 配置（超出范围）
  - 不支持 Command 的动态增删（需修改配置文件重启）

## Decisions

### Decision 1: CLAUDE_COMMAND 配置格式

**选择**: 支持字符串和列表两种格式，列表格式无需引号

```
# 单命令（向后兼容）
CLAUDE_COMMAND=claude
CLAUDE_COMMAND=claude --setting opus

# 多命令（新格式，逗号分隔列表，无需引号）
CLAUDE_COMMAND=[claude, claude --setting opus]

# 也兼容 JSON 数组格式（带引号）
CLAUDE_COMMAND=["claude", "claude --setting opus"]

# 空值或缺失 → 等同于 [claude]（默认使用 claude）
CLAUDE_COMMAND=
```

**解析逻辑**（在 `config.py` 中新增）:
1. 读取原始字符串，strip 后判断
2. 如果以 `[` 开头且以 `]` 结尾：
   a. 先尝试 `json.loads()` 解析（兼容 JSON 格式）
   b. 如果 JSON 解析失败，按逗号分隔，各元素 strip 后得到列表
3. 否则视为单命令字符串，包装为 `[value]`
4. 空值/空列表 → `["claude"]`
5. 过滤列表中的空字符串

**理由**: 无引号列表语法 `[a, b, c]` 在 `.env` 中书写更自然，减少转义和引号的困扰。同时兼容标准 JSON 格式。

### Decision 2: `--cmd` 参数的匹配机制

**选择**: 支持两种匹配方式

1. **索引匹配**: `--cmd=0`、`--cmd=1` — 直接按数组下标
2. **名称匹配**: `--cmd=opus` — 在列表中查找包含该子串的命令

名称匹配规则：
- 对列表中每个命令做子串匹配（大小写敏感）
- 匹配到第一个包含该子串的命令
- 无匹配时返回错误提示

**理由**: 索引适合快速选择，名称匹配更人性化，不需要记住配置顺序。

### Decision 3: Session Claude Command 存储

**选择**: 复用 Callback 后端的 `ChatIdStore`（`runtime/session_chats.json`）

ChatIdStore 当前结构：
```json
{
    "session_id": {
        "chat_id": "oc_xxxx",
        "updated_at": 1706745600
    }
}
```

扩展后结构：
```json
{
    "session_id": {
        "chat_id": "oc_xxxx",
        "claude_command": "claude --setting opus",
        "updated_at": 1706745600
    }
}
```

**理由**:
- ChatIdStore 已经以 `session_id` 为 key，是 Callback 后端对 session 属性的存储
- `claude_command` 是 session 级别的属性，逻辑上属于同一数据
- 复用已有 7 天过期机制，无需新建存储
- 旧数据无 `claude_command` 字段时 `.get()` 返回 None，天然向后兼容
- 不应由飞书网关存储（飞书网关的 SessionStore 是 message_id → session 映射，用途不同）

### Decision 4: /reply 指令设计

**选择**: 新增 `/reply` 命令，仅在回复消息时可用

格式：
- `/reply prompt` — 使用 session 记录的 Command 继续会话
- `/reply --cmd=1 prompt` — 指定 Command 继续会话

**与现有回复方式的区别**:
- 当前：直接回复消息（非 `/` 开头）→ 走 `_handle_reply_message`，使用默认 Command
- 新增：`/reply` 命令 → 走命令解析流程，支持 `--cmd` 参数

**理由**: `/reply` 命令让用户在回复时也能控制 Command 选择，弥补了当前直接回复无法传递参数的不足。

### Decision 5: Command 选择优先级

从高到低：
1. `--cmd` 参数指定的 Command
2. Session 记录的最近使用 Command（存储在 Callback 后端 ChatIdStore 中）
3. 配置列表的第一个元素（默认 Command）

### Decision 6: 新建会话卡片的 Command 选择

当 `CLAUDE_COMMAND` 配置了多个命令时（列表长度 > 1），在新建会话卡片中新增 `select_static` 下拉框，显示可选的 Command 列表。

列表长度 = 1 时不显示选择器，直接使用唯一的 Command。

## Risks / Trade-offs

- **名称匹配歧义**: 如果多个命令包含相同子串（如都包含 `claude`），名称匹配只返回第一个。用户需使用更精确的子串或索引。缓解：在错误提示中显示可用列表。
- **配置格式变更**: 列表语法在 `.env` 中不太常见，可能对部分用户造成困惑。缓解：在 `.env.example` 中提供详细注释和示例。
- **ChatIdStore 数据增长**: 新增 `claude_command` 字段增加少量存储（每条映射多一个字符串）。影响可忽略。

## Open Questions

（无）
