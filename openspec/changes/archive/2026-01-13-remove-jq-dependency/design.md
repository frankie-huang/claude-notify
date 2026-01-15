## Context

Claude Code 的 PermissionRequest hook 通过 stdin 传入 JSON 数据，格式如下：

```json
{
  "session_id": "abc123",
  "hook_event_name": "PermissionRequest",
  "tool_name": "Bash",
  "tool_input": {
    "command": "rm -rf /tmp/test",
    "description": "Delete temp files"
  }
}
```

当前实现依赖 `jq` 解析这些字段。需要在无 `jq` 环境下使用 Linux 原生命令实现相同功能。

## Goals / Non-Goals

**Goals:**
- 使用 `grep`、`sed`、`awk` 等原生命令解析 JSON
- 支持提取 `tool_name` 和 `tool_input` 中的关键字段
- 与 jq 解析结果一致，无功能降级

**Non-Goals:**
- 实现通用 JSON 解析器（只需支持 Claude Code 的固定格式）
- 处理深度嵌套或复杂 JSON 结构

## Decisions

### Decision 1: 使用 grep + sed 提取 JSON 字段

**方案**: 使用正则表达式匹配 JSON 键值对

```bash
# 提取 tool_name
json_get_string() {
    local key="$1"
    echo "$INPUT" | grep -o "\"$key\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" | \
        sed "s/\"$key\"[[:space:]]*:[[:space:]]*\"//" | sed 's/"$//'
}

TOOL_NAME=$(json_get_string "tool_name")
```

**优点**:
- 使用 POSIX 标准命令，兼容所有 Linux 系统
- 简单直接，易于理解和维护

**缺点**:
- 不能处理值中包含转义引号的情况
- 不适用于嵌套对象

### Decision 2: 使用 awk 提取嵌套字段

**方案**: 对于 `tool_input` 内的字段，使用 awk 处理

```bash
# 提取 tool_input.command
json_get_nested() {
    local parent="$1"
    local key="$2"
    echo "$INPUT" | awk -v parent="$parent" -v key="$key" '
    {
        # 找到 parent 对象后提取 key 的值
        if (match($0, "\"" parent "\"[[:space:]]*:[[:space:]]*{")) {
            start = RSTART + RLENGTH
            rest = substr($0, start)
            if (match(rest, "\"" key "\"[[:space:]]*:[[:space:]]*\"[^\"]*\"")) {
                val = substr(rest, RSTART, RLENGTH)
                gsub("\"" key "\"[[:space:]]*:[[:space:]]*\"", "", val)
                gsub("\"$", "", val)
                print val
            }
        }
    }'
}

COMMAND=$(json_get_nested "tool_input" "command")
```

### Decision 3: 优先使用 jq，回退到原生命令

**方案**: 检测 jq 可用性，优先使用 jq

```bash
if command -v jq &> /dev/null; then
    # 使用 jq（更可靠）
    TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // "unknown"')
else
    # 使用原生命令
    TOOL_NAME=$(json_get_string "tool_name")
fi
```

**理由**: jq 更可靠，能处理转义字符和边缘情况。原生命令作为后备方案。

## Risks / Trade-offs

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 原生解析无法处理转义引号 | 命令内容显示不完整 | Claude Code 的 JSON 结构相对简单，转义情况较少 |
| 不同 awk/sed 版本兼容性 | 某些系统解析失败 | 使用 POSIX 标准语法，避免 GNU 扩展 |
| 性能影响 | 多次 grep/sed 调用 | 权限请求不频繁，性能影响可忽略 |

## Open Questions

无
