# Claude Code Hooks 事件调研文档

本文档记录 Claude Code 支持的所有 hooks 事件，包括触发时机、事件关联和配置方式，为本项目后续扩展提供参考。

## 目录

- [事件总览](#事件总览)
- [事件详解](#事件详解)
- [事件关联图](#事件关联图)
- [获取 Claude 响应内容](#获取-claude-响应内容)
- [配置方式](#配置方式)
- [本项目使用情况](#本项目使用情况)
- [扩展建议](#扩展建议)

---

## 事件总览

Claude Code 支持 **11 种 hook 事件**：

| 事件名称 | 触发时机 | 支持 Matcher | 本项目使用 |
|---------|---------|:----------:|:--------:|
| **PreToolUse** | 工具调用前 | ✓ | - |
| **PermissionRequest** | 权限请求对话显示时 | ✓ | ✅ |
| **PostToolUse** | 工具调用完成后 | ✓ | - |
| **UserPromptSubmit** | 用户提交提示词时 | ✗ | - |
| **Notification** | Claude 发送通知时 | ✓ | ✅ |
| **Stop** | 主 Agent 完成响应时 | ✗ | ✅ |
| **SubagentStop** | 子 Agent 完成响应时 | ✗ | - |
| **PreCompact** | 上下文压缩前 | ✓ | - |
| **Setup** | 初始化时（--init/--maintenance） | ✓ | - |
| **SessionStart** | 会话启动/恢复时 | ✓ | - |
| **SessionEnd** | 会话结束时 | ✗ | - |

---

## 事件详解

> **公共字段说明**: 所有事件的输入 JSON 都包含以下公共字段：
> - `session_id` - 当前会话 ID
> - `transcript_path` - 对话记录文件路径
> - `cwd` - 当前工作目录
> - `permission_mode` - 权限模式 (`default`|`plan`|`acceptEdits`|`dontAsk`|`bypassPermissions`)
> - `hook_event_name` - 事件名称

### PreToolUse - 工具执行前

- **触发时机**: Claude 创建工具参数后，实际执行前
- **支持 Matcher**: 是（可按工具名过滤）
- **支持工具**: Bash, Write, Edit, Read, Glob, Grep, WebFetch, WebSearch, Task 等
- **主要用途**:
  - 阻止工具执行（exit code 2）
  - 修改工具输入参数（updatedInput）
  - 自动批准/询问权限
  - 向 Claude 提供额外上下文
- **输入 JSON 示例**:

  **Bash 工具**:
  ```json
  {
    "session_id": "abc123",
    "transcript_path": "/home/user/.claude/projects/.../abc123.jsonl",
    "cwd": "/home/user/project",
    "permission_mode": "default",
    "hook_event_name": "PreToolUse",
    "tool_name": "Bash",
    "tool_input": {
      "command": "npm run build",
      "description": "Build the project",
      "timeout": 120000,
      "run_in_background": false
    },
    "tool_use_id": "toolu_01ABC123..."
  }
  ```

  **Write 工具**:
  ```json
  {
    "hook_event_name": "PreToolUse",
    "tool_name": "Write",
    "tool_input": {
      "file_path": "/path/to/file.txt",
      "content": "file content here"
    },
    "tool_use_id": "toolu_01ABC123..."
  }
  ```

  **Edit 工具**:
  ```json
  {
    "hook_event_name": "PreToolUse",
    "tool_name": "Edit",
    "tool_input": {
      "file_path": "/path/to/file.txt",
      "old_string": "original text",
      "new_string": "replacement text",
      "replace_all": false
    },
    "tool_use_id": "toolu_01ABC123..."
  }
  ```

  **Read 工具**:
  ```json
  {
    "hook_event_name": "PreToolUse",
    "tool_name": "Read",
    "tool_input": {
      "file_path": "/path/to/file.txt",
      "offset": 10,
      "limit": 50
    },
    "tool_use_id": "toolu_01ABC123..."
  }
  ```

- **输出 JSON 示例**:
  ```json
  {
    "hookSpecificOutput": {
      "hookEventName": "PreToolUse",
      "permissionDecision": "allow|deny|ask",
      "permissionDecisionReason": "原因说明",
      "updatedInput": { "command": "修改后的命令" },
      "additionalContext": "添加到 Claude 上下文的信息"
    }
  }
  ```

### PermissionRequest - 权限授权

- **触发时机**: 需要用户权限确认时（执行命令、修改文件等）
- **支持 Matcher**: 是（可按工具名过滤）
- **主要用途**:
  - 自动允许（allow）
  - 自动拒绝（deny）+ 拒绝原因
  - 修改工具输入后自动批准
  - 显示确认对话（ask）
- **输入 JSON 示例**:
  ```json
  {
    "session_id": "abc123",
    "transcript_path": "/home/user/.claude/projects/.../abc123.jsonl",
    "cwd": "/home/user/project",
    "permission_mode": "default",
    "hook_event_name": "PermissionRequest",
    "tool_name": "Bash",
    "tool_input": {
      "command": "npm run deploy",
      "description": "Deploy the application"
    },
    "tool_use_id": "toolu_01ABC123..."
  }
  ```
- **输出 JSON 示例**:

  **允许执行**:
  ```json
  {
    "hookSpecificOutput": {
      "hookEventName": "PermissionRequest",
      "decision": {
        "behavior": "allow",
        "updatedInput": { "command": "npm run lint" }
      }
    }
  }
  ```

  **拒绝执行**:
  ```json
  {
    "hookSpecificOutput": {
      "hookEventName": "PermissionRequest",
      "decision": {
        "behavior": "deny",
        "message": "Not allowed in production",
        "interrupt": true
      }
    }
  }
  ```
- **注意**: 与 PreToolUse 的区别是 PermissionRequest 专门用于权限决策，而 PreToolUse 是通用的工具执行前钩子

### PostToolUse - 工具执行后

- **触发时机**: 工具成功执行后立即运行
- **支持 Matcher**: 是（可按工具名过滤）
- **主要用途**:
  - 格式化代码（prettier、gofmt 等）
  - 验证输出
  - 记录执行日志
  - 向 Claude 反馈问题
- **输入 JSON 示例**:
  ```json
  {
    "session_id": "abc123",
    "transcript_path": "/home/user/.claude/projects/.../abc123.jsonl",
    "cwd": "/home/user/project",
    "permission_mode": "default",
    "hook_event_name": "PostToolUse",
    "tool_name": "Write",
    "tool_input": {
      "file_path": "/path/to/file.txt",
      "content": "file content"
    },
    "tool_response": {
      "filePath": "/path/to/file.txt",
      "success": true
    },
    "tool_use_id": "toolu_01ABC123..."
  }
  ```

  **不同工具的 `tool_response` 示例**:

  Bash:
  ```json
  {
    "tool_response": {
      "stdout": "command output",
      "stderr": "",
      "exit_code": 0,
      "duration_ms": 1234
    }
  }
  ```

  Read:
  ```json
  {
    "tool_response": {
      "content": "file content here",
      "line_count": 45,
      "truncated": false
    }
  }
  ```
- **输出 JSON 示例**:
  ```json
  {
    "decision": "block",
    "reason": "代码格式化失败",
    "hookSpecificOutput": {
      "hookEventName": "PostToolUse",
      "additionalContext": "额外信息"
    }
  }
  ```

### UserPromptSubmit - 用户输入

- **触发时机**: 用户提交提示词，Claude 处理前
- **支持 Matcher**: 否
- **主要用途**:
  - 验证提示词（阻止敏感词）
  - 添加上下文（当前时间、Git 分支等）
  - 阻止包含密钥的提示词
- **输入 JSON 示例**:
  ```json
  {
    "session_id": "abc123",
    "transcript_path": "/home/user/.claude/projects/.../abc123.jsonl",
    "cwd": "/home/user/project",
    "permission_mode": "default",
    "hook_event_name": "UserPromptSubmit",
    "prompt": "Write a function to calculate factorial"
  }
  ```
- **输出方式**:
  - 纯文本 stdout → 作为上下文注入到 Claude
  - JSON 输出 → 支持 `decision: "block"`
- **输出 JSON 示例**:

  **添加上下文**:
  ```json
  {
    "hookSpecificOutput": {
      "hookEventName": "UserPromptSubmit",
      "additionalContext": "Current git branch: main, Time: 2026-01-22 10:00"
    }
  }
  ```

  **阻止提交**:
  ```json
  {
    "decision": "block",
    "reason": "Prompt contains potential secrets"
  }
  ```

### Notification - 通知

- **触发时机**: Claude 发送通知
- **支持 Matcher**: 是
- **支持的通知类型**:
  | 类型 | 说明 |
  |-----|------|
  | `permission_prompt` | 权限请求通知 |
  | `idle_prompt` | 空闲等待通知（60+ 秒） |
  | `auth_success` | 认证成功 |
  | `elicitation_dialog` | MCP 工具参数确认 |
- **输入 JSON 示例**:

  **权限提示**:
  ```json
  {
    "session_id": "abc123",
    "transcript_path": "/home/user/.claude/projects/.../abc123.jsonl",
    "cwd": "/home/user/project",
    "permission_mode": "default",
    "hook_event_name": "Notification",
    "message": "Claude needs your permission to use Bash",
    "notification_type": "permission_prompt"
  }
  ```

  **空闲提示**:
  ```json
  {
    "hook_event_name": "Notification",
    "message": "Claude is idle, waiting for input",
    "notification_type": "idle_prompt"
  }
  ```

  **认证成功**:
  ```json
  {
    "hook_event_name": "Notification",
    "message": "Successfully authenticated",
    "notification_type": "auth_success"
  }
  ```

  **MCP 工具输入**:
  ```json
  {
    "hook_event_name": "Notification",
    "message": "MCP tool needs additional input",
    "notification_type": "elicitation_dialog"
  }
  ```

### Stop - 主 Agent 完成

- **触发时机**: 主 Agent 完成响应
- **支持 Matcher**: 否
- **主要用途**:
  - 阻止停止（exit code 2 或 JSON: `decision: "block"`）
  - 要求 Claude 继续工作
  - 使用 LLM 进行智能决策（prompt-based hooks）
- **特殊标志**: `stop_hook_active` 防止无限循环
- **输入 JSON 示例**:
  ```json
  {
    "session_id": "abc123",
    "transcript_path": "/home/user/.claude/projects/.../abc123.jsonl",
    "cwd": "/home/user/project",
    "permission_mode": "default",
    "hook_event_name": "Stop",
    "stop_hook_active": false
  }
  ```
- **输出 JSON 示例**:

  **允许停止**: exit code 0，无输出或空 JSON

  **阻止停止**:
  ```json
  {
    "decision": "block",
    "reason": "Tests are still failing, need to fix them first"
  }
  ```

### SubagentStop - 子 Agent 完成

- **触发时机**: 子 Agent 完成任务
- **支持 Matcher**: 否
- **主要用途**: 评估子任务是否真正完成
- **特殊标志**: `stop_hook_active` 防止无限循环
- **输入 JSON 示例**:
  ```json
  {
    "session_id": "abc123",
    "transcript_path": "/home/user/.claude/projects/.../abc123.jsonl",
    "cwd": "/home/user/project",
    "permission_mode": "default",
    "hook_event_name": "SubagentStop",
    "stop_hook_active": false
  }
  ```
- **输出 JSON 示例**: 同 Stop

### PreCompact - 上下文压缩前

- **触发时机**: 上下文窗口满时自动压缩，或手动 `/compact`
- **支持 Matcher**: 是
- **子类型**:
  - `manual` - 手动触发
  - `auto` - 自动触发
- **主要用途**: 压缩前备份、日志、自定义处理
- **输入 JSON 示例**:
  ```json
  {
    "session_id": "abc123",
    "transcript_path": "/home/user/.claude/projects/.../abc123.jsonl",
    "cwd": "/home/user/project",
    "permission_mode": "default",
    "hook_event_name": "PreCompact",
    "trigger": "manual",
    "custom_instructions": "保留所有 API 相关的上下文"
  }
  ```

  | 字段 | 说明 |
  |-----|------|
  | `trigger` | `"manual"` (用户调用 `/compact`) 或 `"auto"` (自动触发) |
  | `custom_instructions` | 用户输入的自定义指令（仅当 trigger=manual） |

- **输出**: exit code 2 阻止压缩操作（仅显示给用户）

### Setup - 初始化设置

- **触发时机**: `claude --init` 或 `claude --maintenance` 时（非每次启动）
- **支持 Matcher**: 是
- **子类型**:
  - `init` - 初始化
  - `maintenance` - 维护
- **主要用途**:
  - 安装依赖
  - 数据库迁移
  - 编译 native modules
- **输入 JSON 示例**:
  ```json
  {
    "session_id": "abc123",
    "transcript_path": "/home/user/.claude/projects/.../abc123.jsonl",
    "cwd": "/home/user/project",
    "permission_mode": "default",
    "hook_event_name": "Setup",
    "trigger": "init"
  }
  ```

  | 字段 | 说明 |
  |-----|------|
  | `trigger` | `"init"` (初始化) 或 `"maintenance"` (维护模式) |

- **输出 JSON 示例**:
  ```json
  {
    "hookSpecificOutput": {
      "hookEventName": "Setup",
      "additionalContext": "安装了依赖，初始化了数据库"
    }
  }
  ```
- **特有能力**: 可访问 `CLAUDE_ENV_FILE` 环境变量进行环境变量持久化

### SessionStart - 会话开始

- **触发时机**: 新建或恢复会话
- **支持 Matcher**: 是
- **子类型**:
  - `startup` - 正常启动
  - `resume` - 恢复会话
  - `clear` - 清理后启动
  - `compact` - 压缩后启动
- **输入 JSON 示例**:
  ```json
  {
    "session_id": "abc123",
    "transcript_path": "/home/user/.claude/projects/.../abc123.jsonl",
    "cwd": "/home/user/project",
    "permission_mode": "default",
    "hook_event_name": "SessionStart",
    "source": "startup"
  }
  ```

  | source 值 | 说明 |
  |-----------|------|
  | `"startup"` | 新会话启动 |
  | `"resume"` | `--resume`、`--continue` 或 `/resume` 恢复 |
  | `"clear"` | `/clear` 命令后启动 |
  | `"compact"` | 自动或手动紧凑后启动 |

- **特有能力**: 可访问 `CLAUDE_ENV_FILE` 环境变量
  - 持久化环境变量到后续 Bash 命令
  - 运行 `nvm use`、`source .env` 等初始化
- **环境变量持久化示例**:
  ```bash
  #!/bin/bash
  if [ -n "$CLAUDE_ENV_FILE" ]; then
    echo 'export NODE_ENV=production' >> "$CLAUDE_ENV_FILE"
  fi
  exit 0
  ```
- **输出 JSON 示例**:
  ```json
  {
    "hookSpecificOutput": {
      "hookEventName": "SessionStart",
      "additionalContext": "Git branch: main, Uncommitted changes: 3 files"
    }
  }
  ```

### SessionEnd - 会话结束

- **触发时机**: 会话终止
- **支持 Matcher**: 否
- **退出原因**:
  - `clear` - `/clear` 命令
  - `logout` - 登出
  - `prompt_input_exit` - 提示词输入中退出
  - `other` - 其他原因
- **主要用途**: 清理、统计、保存状态
- **输入 JSON 示例**:
  ```json
  {
    "session_id": "abc123",
    "transcript_path": "/home/user/.claude/projects/.../abc123.jsonl",
    "cwd": "/home/user/project",
    "permission_mode": "default",
    "hook_event_name": "SessionEnd",
    "reason": "prompt_input_exit"
  }
  ```

  | reason 值 | 说明 |
  |-----------|------|
  | `"clear"` | 用户执行 `/clear` 命令 |
  | `"logout"` | 用户登出 |
  | `"prompt_input_exit"` | 用户在提示输入时退出 |
  | `"other"` | 其他退出原因 |

- **注意**: SessionEnd hook 不能阻止会话结束，仅用于执行清理操作

---

## 事件关联图

```
会话生命周期流程：

┌─────────────────────────────────────────────────────────┐
│ Setup (仅 --init/--maintenance 时)                      │
└────────────────────────┬────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ SessionStart (每次会话启动)                              │
│ - 可加载初始上下文、设置环境变量                         │
└────────────────────────┬────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│                     用户交互循环                         │
│                                                         │
│  ┌────────────────────────────────────────────────────┐ │
│  │ UserPromptSubmit                                   │ │
│  │ - 验证/过滤用户输入                                │ │
│  └──────────────────────┬─────────────────────────────┘ │
│                         ↓                               │
│  ┌────────────────────────────────────────────────────┐ │
│  │ PreToolUse (工具执行前)                            │ │
│  │ - 可修改工具参数、阻止执行                         │ │
│  ├────────────────────────────────────────────────────┤ │
│  │ PermissionRequest (需权限时)                       │ │
│  │ - 自动批准/拒绝权限                               │ │
│  │ - 🔔 触发 Notification (permission_prompt)        │ │
│  └──────────────────────┬─────────────────────────────┘ │
│                         ↓                               │
│  ┌────────────────────────────────────────────────────┐ │
│  │ [工具执行] Bash, Write, Edit, Read...              │ │
│  └──────────────────────┬─────────────────────────────┘ │
│                         ↓                               │
│  ┌────────────────────────────────────────────────────┐ │
│  │ PostToolUse (工具执行后)                           │ │
│  │ - 格式化、验证、日志                               │ │
│  └──────────────────────┬─────────────────────────────┘ │
│                         ↓                               │
│  ┌────────────────────────────────────────────────────┐ │
│  │ 🔔 Notification (空闲等待时 idle_prompt)           │ │
│  └──────────────────────┬─────────────────────────────┘ │
│                         ↓                               │
│  ┌────────────────────────────────────────────────────┐ │
│  │ Stop / SubagentStop                                │ │
│  │ - 决定是否继续或停止                               │ │
│  └──────────────────────┬─────────────────────────────┘ │
│                         │                               │
│            ┌────────────┴────────────┐                  │
│            ↓                         ↓                  │
│    [继续循环]                  [PreCompact]             │
│    返回 UserPromptSubmit        上下文压缩前            │
│                                                         │
└─────────────────────────────────────────────────────────┘
                         │
                         ↓ [会话结束]
┌─────────────────────────────────────────────────────────┐
│ SessionEnd                                              │
│ - 日志、清理资源                                        │
└─────────────────────────────────────────────────────────┘
```

### 关键关联说明

1. **PreToolUse → PermissionRequest**:
   - PreToolUse 先执行，如果不阻止则进入权限检查
   - PermissionRequest 可用 `updatedInput` 修改已验证过的参数

2. **PermissionRequest → Notification**:
   - 权限请求时会触发 `permission_prompt` 类型的 Notification

3. **Stop/SubagentStop**:
   - `stop_hook_active` 标志防止无限循环
   - 检查此标志可避免 Stop hook 反复触发

4. **SessionStart vs Setup**:
   - `SessionStart`: 每次会话都运行（应保持快速）
   - `Setup`: 仅 `--init` 或 `--maintenance` 时运行（一次性操作）

---

## 获取 Claude 响应内容

大多数 hook 事件的输入 JSON **不直接包含 Claude 的响应内容**，但都提供了 `transcript_path` 字段，可以通过读取该文件获取完整对话历史。

### transcript_path 文件格式

`transcript_path` 指向一个 JSONL 文件（每行一个 JSON 对象），包含完整的对话记录：

```jsonl
{"role": "user", "content": [{"type": "text", "text": "帮我写一个计算阶乘的函数"}]}
{"role": "assistant", "content": [{"type": "text", "text": "好的，我来帮你写一个计算阶乘的函数...\n\n```python\ndef factorial(n):\n    if n <= 1:\n        return 1\n    return n * factorial(n - 1)\n```"}]}
{"role": "user", "content": [{"type": "text", "text": "添加输入验证"}]}
{"role": "assistant", "content": [{"type": "text", "text": "我已经添加了输入验证..."}]}
```

### 在 Stop hook 中获取 Claude 最终响应

```bash
#!/bin/bash
# stop-with-summary.sh - 获取 Claude 最终响应并发送通知

input=$(cat)
transcript_path=$(echo "$input" | jq -r '.transcript_path')
stop_hook_active=$(echo "$input" | jq -r '.stop_hook_active')

# 防止无限循环
if [ "$stop_hook_active" = "true" ]; then
    exit 0
fi

if [ -f "$transcript_path" ]; then
    # 获取最后一条 assistant 消息
    last_response=$(grep '"role":"assistant"' "$transcript_path" | tail -1)

    # 提取文本内容
    claude_conclusion=$(echo "$last_response" | jq -r '.content[0].text // .text')

    # 截取前 500 字符作为摘要
    summary="${claude_conclusion:0:500}"

    # 发送到飞书/钉钉等
    curl -X POST "$FEISHU_WEBHOOK_URL" \
        -H "Content-Type: application/json" \
        -d "{\"msg_type\": \"text\", \"content\": {\"text\": \"Claude 处理完成:\\n$summary\"}}"
fi

exit 0
```

### 使用 Python 解析对话历史

```python
#!/usr/bin/env python3
import json
import sys

# 读取 hook 输入
hook_input = json.load(sys.stdin)
transcript_path = hook_input.get('transcript_path')

# 读取对话历史
messages = []
with open(transcript_path, 'r') as f:
    for line in f:
        if line.strip():
            messages.append(json.loads(line))

# 获取最后的 assistant 消息
assistant_messages = [m for m in messages if m.get('role') == 'assistant']
if assistant_messages:
    last_response = assistant_messages[-1]
    content = last_response.get('content', [])
    if content and isinstance(content, list):
        text = content[0].get('text', '')
        print(f"Claude 最终响应: {text[:200]}...")
```

### 各事件获取响应内容的方式

| Hook 事件 | 直接包含响应 | 通过 transcript_path | 适用场景 |
|----------|:----------:|:------------------:|---------|
| **Stop** | ✗ | ✓ | 任务完成通知、响应分析 |
| **SubagentStop** | ✗ | ✓ | 子任务结果监控 |
| **Notification** | ✗ | ✓ | 空闲时发送上下文摘要 |
| **PostToolUse** | ✓ (`tool_response`) | ✓ | 工具输出验证 |
| **SessionEnd** | ✗ | ✓ | 会话统计、归档 |
| **PreCompact** | ✗ | ✓ | 压缩前备份对话 |

### 注意事项

1. **文件可能较大**: 长对话的 transcript 文件可能很大，建议只读取最后几行
2. **内容格式**: `content` 字段可能是数组（包含多个 block）或直接是文本
3. **工具调用**: 对话中可能包含工具调用记录，需要过滤 `role: "assistant"` 的消息
4. **编码**: 文件使用 UTF-8 编码，包含中文等多语言内容

---

## 配置方式

### 配置文件位置

- 全局配置: `~/.claude/settings.json`
- 项目配置: `.claude/settings.json`

### 配置结构

```json
{
  "hooks": {
    "EventName": [
      {
        "matcher": "ToolPattern",
        "hooks": [
          {
            "type": "command",
            "command": "脚本路径",
            "timeout": 60
          }
        ]
      }
    ]
  }
}
```

### Matcher 匹配规则

| 匹配模式 | 说明 | 示例 |
|---------|------|------|
| 精确匹配 | 完全匹配工具名 | `"Write"` |
| 正则匹配 | 支持 `\|` 和 `.*` | `"Edit\|Write"` |
| 通配符 | `*` 或 `""` 匹配所有 | `"*"` |
| MCP 工具 | 特殊模式 | `"mcp__memory__.*"` |

### Hook 类型

#### Command Hook (`type: "command"`)

```json
{
  "type": "command",
  "command": "bash /path/to/script.sh",
  "timeout": 30
}
```
- 特点: 快速、确定性
- 输入: JSON via stdin

#### Prompt Hook (`type: "prompt"`)

```json
{
  "type": "prompt",
  "prompt": "Evaluate if Claude should stop. Context: $ARGUMENTS",
  "timeout": 30
}
```
- 特点: 上下文感知、智能决策
- 支持事件: Stop, SubagentStop, UserPromptSubmit, PreToolUse, PermissionRequest
- 使用 LLM（默认 Haiku）进行判断

### Hook 输入 (JSON via stdin)

```json
{
  "session_id": "abc123",
  "transcript_path": "~/.claude/projects/.../session.jsonl",
  "cwd": "/current/working/directory",
  "permission_mode": "default|plan|acceptEdits|dontAsk|bypassPermissions",
  "hook_event_name": "PreToolUse",
  "tool_name": "Bash",
  "tool_input": { "command": "ls -la" },
  "tool_use_id": "toolu_01ABC123..."
}
```

### Hook 输出

#### Exit Code

| Code | 说明 |
|------|------|
| 0 | 成功，继续执行 |
| 2 | 阻止错误，显示 stderr 给 Claude |
| 其他 | 非阻止错误，仅用户可见 |

#### JSON 输出 (exit code 0 时处理)

```json
{
  "continue": true,
  "stopReason": "错误信息",
  "suppressOutput": true,
  "systemMessage": "警告信息",
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow|deny|ask",
    "permissionDecisionReason": "原因说明",
    "updatedInput": { "command": "修改后的命令" },
    "additionalContext": "添加到 Claude 上下文"
  }
}
```

### 环境变量

| 环境变量 | 可用场景 | 说明 |
|--------|---------|------|
| `$CLAUDE_PROJECT_DIR` | 所有 hook | 项目根目录绝对路径 |
| `$CLAUDE_ENV_FILE` | SessionStart, Setup | 持久化环境变量文件 |
| `$CLAUDE_CODE_REMOTE` | 所有 hook | "true" = 云端，空 = 本地 |

---

## 本项目使用情况

当前本项目使用了以下 3 个 hooks：

### PermissionRequest

配置位置: `~/.claude/settings.json`

```json
{
  "PermissionRequest": [
    {
      "matcher": "*",
      "hooks": [
        {
          "type": "command",
          "command": "bash /path/to/claude-notify/hooks/permission-notify.sh",
          "timeout": 600
        }
      ]
    }
  ]
}
```

功能: 发送飞书交互卡片，支持远程批准/拒绝权限请求

### Notification

```json
{
  "Notification": [
    {
      "hooks": [
        {
          "type": "command",
          "command": "bash $HOME/.claude/hooks/webhook/webhook-notify.sh",
          "timeout": 5
        }
      ]
    }
  ]
}
```

功能: 发送通用通知（空闲等待等）

### Stop

```json
{
  "Stop": [
    {
      "hooks": [
        {
          "type": "command",
          "command": "bash /path/to/claude-notify/src/hook-router.sh",
          "timeout": 5
        }
      ]
    }
  ]
}
```

功能: 任务完成时发送通知，包含 Claude 最终响应摘要和会话标识

---

## 扩展建议

基于本次调研，以下 hooks 可考虑在后续扩展中使用：

### 1. PostToolUse - 代码格式化

```json
{
  "PostToolUse": [
    {
      "matcher": "Write|Edit",
      "hooks": [
        {
          "type": "command",
          "command": "prettier --write $CLAUDE_PROJECT_DIR"
        }
      ]
    }
  ]
}
```

用途: 写入/编辑文件后自动格式化

### 2. PreToolUse - 敏感文件保护

```json
{
  "PreToolUse": [
    {
      "matcher": "Write|Edit",
      "hooks": [
        {
          "type": "command",
          "command": "bash /path/to/protect-sensitive.sh"
        }
      ]
    }
  ]
}
```

用途: 阻止修改 `.env`、凭证文件等敏感文件

### 3. SessionStart - 环境初始化通知

```json
{
  "SessionStart": [
    {
      "hooks": [
        {
          "type": "command",
          "command": "bash /path/to/session-start-notify.sh"
        }
      ]
    }
  ]
}
```

用途: 会话开始时发送飞书通知，包含项目和分支信息

### 4. SessionEnd - 会话统计

```json
{
  "SessionEnd": [
    {
      "hooks": [
        {
          "type": "command",
          "command": "bash /path/to/session-end-stats.sh"
        }
      ]
    }
  ]
}
```

用途: 会话结束时统计使用情况并发送报告

### 5. UserPromptSubmit - 敏感词过滤

用途: 防止在提示词中意外输入敏感信息（API Key 等）

---

## Hook 进程生命周期与信号处理

### 进程组结构

Hook 进程运行在 Claude 的进程组中：

```
Claude (PID=98437, PGID=98437)  ← 进程组长
  └── hook-router.sh (PID=100540, PGID=98437)  ← 在 Claude 的进程组中
      └── permission.sh (通过 source 加载，同一进程)
```

**关键发现**：
- Hook 进程的 `PGID` 等于 Claude 的 `PID`
- Hook 进程**不是进程组长**，无法脱离 Claude 的进程组

### 信号处理限制

当用户在终端直接响应权限请求时：

| 事件 | 是否发生 | 说明 |
|------|:--------:|------|
| Hook 收到 SIGTERM/SIGINT | ❌ | 不会收到可捕获的信号 |
| Hook 触发 EXIT trap | ❌ | EXIT trap 不会被触发 |
| Hook 被 SIGKILL 杀死 | ✅ | **无法被捕获** |
| 进程组被清理 | ✅ | Claude 向整个进程组发送信号 |

**实验验证**：

```bash
# hook-router.sh 中设置的 trap
trap '_handler' SIGINT SIGTERM SIGHUP
trap 'log "EXIT"' EXIT

# 当用户在终端响应时，以上 trap 都不会被触发
# 日志只显示：
[hook-router] Starting (PID: 100540, PPID: 98437, PGID: 98437)
# 之后没有任何日志，进程直接消失
```

### 结论

**Claude 使用 SIGKILL 向整个进程组发送信号**，导致：
1. Hook 进程无法捕获信号（SIGKILL 不可捕获）
2. 无法在 hook 脚本中检测到"用户在终端响应"事件
3. Hook 进程直接消失，不执行任何清理代码

### 解决方案：PID 注册检测

由于无法在 hook 脚本中检测中断，采用 **PID 注册 + 实时检测** 方案：

**工作原理**：

1. Hook 脚本启动时将自己的进程 ID (`$$) 发送给后端
2. 用户在终端响应 → Claude kill hook 进程
3. 用户点击飞书按钮 → 后端检测 hook PID 是否存活
4. PID 不存在 → 返回"用户已在终端响应"提示

**代码实现**：

```bash
# permission.sh - 发送请求时注册 PID
request_json=$(jq -n \
    --arg rid "$REQUEST_ID" \
    --arg pdir "$PROJECT_DIR" \
    --arg enc "$encoded_input" \
    --arg hpid "$$" \
    '{request_id: $rid, project_dir: $pdir, raw_input_encoded: $enc, hook_pid: $hpid}')
```

```python
# callback.py - 按钮点击时检测 PID
hook_pid = req_data.get('hook_pid')
if hook_pid:
    try:
        os.kill(int(hook_pid), 0)  # 检测进程是否存在
    except OSError:
        # hook 进程已死，用户已在终端响应
        return send_html_response(200, '用户已在终端响应', ...)
```

**优势**：
- 无需等待超时，点击按钮时实时检测
- 不依赖复杂的信号处理
- 用户体验更好，响应更快

---

## 参考资料

- [Claude Code Hooks 官方文档](https://docs.anthropic.com/en/docs/claude-code/hooks)
- [Claude Code Settings 官方文档](https://docs.anthropic.com/en/docs/claude-code/settings)

---

*文档更新日期: 2026-01-22*
