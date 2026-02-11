#!/bin/bash
# =============================================================================
# src/hooks/stop.sh - Claude Code Stop 事件处理脚本
#
# 此脚本由 hook-router.sh 通过 source 调用，不直接执行
#
# 前置条件（由 hook-router.sh 完成）:
#   - $INPUT 变量包含从 stdin 读取的 JSON 数据
#   - 核心库、JSON 解析器、日志系统已初始化
#   - $PROJECT_ROOT, $SRC_DIR, $LIB_DIR 等路径变量已设置
#
# 适用场景:
#   - 主 Agent 完成响应
#   - 发送任务完成通知，包含 Claude 的最终响应内容
#
# 设计原则:
#   - 快速返回，不阻塞 Claude Code
#   - 通知发送在后台异步执行
#   - 任何错误不影响 Claude 正常退出
# =============================================================================

# 检查 stop_hook_active 标志，防止无限循环
STOP_HOOK_ACTIVE=$(json_get "$INPUT" "stop_hook_active")
if [ "$STOP_HOOK_ACTIVE" = "true" ]; then
    log "Stop hook already active, skipping"
    exit 0
fi

# =============================================================================
# 从单个 transcript 文件中提取响应内容（text + thinking）
# 参数:
#   $1 - transcript 文件路径
#   $2 - 最大重试次数 (可选，默认 5)
# 返回:
#   输出 JSON 字符串 {"text":"...","thinking":"...","session_id":"..."}
#   找不到有效内容则返回空
# 说明:
#   找到最近一条用户文本消息（排除仅含 tool_result 的 user 消息），
#   收集其后所有 assistant 消息中的 text 和 thinking 内容。
# =============================================================================
extract_response_from_file() {
    local transcript_file="$1"
    local max_retries="${2:-5}"
    local retry_count=0
    local result=""

    if [ ! -f "$transcript_file" ]; then
        return 1
    fi

    while [ $retry_count -lt $max_retries ]; do
        if [ "$JSON_HAS_JQ" = "true" ]; then
            result=$(jq -s '
# 找到最近一条含文本的 user 消息的索引
(
    [to_entries[] | select(
        .value.type == "user" and
        (
            (.value.message.content | type == "string" and length > 0) or
            (.value.message.content | type == "array" and (map(select(.type == "text")) | length > 0))
        )
    ) | .key] | if length > 0 then .[-1] else null end
) as $user_idx |
if $user_idx == null then
    null
else
    # 收集 user_idx 之后所有 assistant 消息
    [.[$user_idx + 1:] | .[] | select(.type == "assistant")] |
    {
        text: ([.[] | .message.content // [] | [.[] | select(.type == "text") | .text] | join("")] | join("\n\n") | gsub("^\\n+|\\n+$"; "")),
        thinking: ([.[] | .message.content // [] | [.[] | select(.type == "thinking") | .thinking] | join("")] | join("\n\n") | gsub("^\\n+|\\n+$"; "")),
        session_id: ([.[] | .sessionId // empty] | if length > 0 then .[0] else "" end)
    } |
    if .text == "" then null else . end
end
' "$transcript_file" 2>/dev/null)

        elif [ "$JSON_HAS_PYTHON3" = "true" ]; then
            result=$(python3 -c "
import sys, json

with open('$transcript_file', 'r') as f:
    lines = f.readlines()

records = []
for line in lines:
    line = line.strip()
    if not line:
        continue
    try:
        records.append(json.loads(line))
    except:
        pass

# 找最近一条含文本的 user 消息索引
user_idx = None
for i in range(len(records) - 1, -1, -1):
    r = records[i]
    if r.get('type') != 'user':
        continue
    content = r.get('message', {}).get('content')
    if isinstance(content, str) and len(content) > 0:
        user_idx = i
        break
    if isinstance(content, list):
        has_text = any(item.get('type') == 'text' for item in content if isinstance(item, dict))
        if has_text:
            user_idx = i
            break

if user_idx is None:
    sys.exit(0)

# 收集 user_idx 之后所有 assistant 消息的 text 和 thinking
texts = []
thinkings = []
session_id = ''
for r in records[user_idx + 1:]:
    if r.get('type') != 'assistant':
        continue
    if not session_id:
        session_id = r.get('sessionId', '')
    content = r.get('message', {}).get('content', [])
    if not isinstance(content, list):
        continue
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get('type') == 'text':
            texts.append(item.get('text', ''))
        elif item.get('type') == 'thinking':
            thinkings.append(item.get('thinking', ''))

combined_text = '\n\n'.join(t for t in texts if t).strip()
combined_thinking = '\n\n'.join(t for t in thinkings if t).strip()

if not combined_text:
    sys.exit(0)

print(json.dumps({'text': combined_text, 'thinking': combined_thinking, 'session_id': session_id}))
" 2>/dev/null)
        fi

        if [ -n "$result" ] && [ "$result" != "null" ]; then
            echo "$result"
            return 0
        fi

        retry_count=$((retry_count + 1))
        if [ $retry_count -lt $max_retries ]; then
            sleep 0.1
        fi
    done

    return 1
}

# =============================================================================
# 提取响应内容（带子代理回退）
# 参数:
#   $1 - 主 transcript 文件路径
# 返回:
#   输出 JSON 字符串 {"text":"...","thinking":"...","session_id":"..."}
# 说明:
#   1. 先在主 transcript 文件中查找
#   2. 如果找不到，检查 subagents 目录，按修改时间倒序查找
# =============================================================================
extract_response() {
    local transcript_path="$1"

    # 提前检查：路径为空直接返回
    if [ -z "$transcript_path" ]; then
        log "Transcript path is empty"
        return 1
    fi

    local result=""

    # 1. 先在主 transcript 文件中查找
    if [ -n "$transcript_path" ] && [ -f "$transcript_path" ]; then
        log "Searching in main transcript: $transcript_path"
        result=$(extract_response_from_file "$transcript_path" 5)
        if [ -n "$result" ] && [ "$result" != "null" ]; then
            log "Found response in main transcript"
            echo "$result"
            return 0
        fi
    fi

    # 2. 主 transcript 找不到，尝试在 subagents 目录中查找
    local session_dir="${transcript_path%.jsonl}"
    local subagents_dir="$session_dir/subagents"

    if [ -d "$subagents_dir" ]; then
        log "Main transcript has no response, searching in subagents: $subagents_dir"

        # 按修改时间倒序遍历子代理文件
        local subagent_files
        subagent_files=$(ls -t "$subagents_dir"/*.jsonl 2>/dev/null) || true

        for subagent_file in $subagent_files; do
            if [ -f "$subagent_file" ]; then
                log "Searching in subagent: $(basename "$subagent_file")"
                result=$(extract_response_from_file "$subagent_file" 3)
                if [ -n "$result" ] && [ "$result" != "null" ]; then
                    log "Found response in subagent: $(basename "$subagent_file")"
                    echo "$result"
                    return 0
                fi
            fi
        done
    fi

    log "No response found in transcript or subagents"
    return 1
}

# =============================================================================
# 后台异步发送通知函数
# =============================================================================
send_stop_notification_async() {
    # 捕获当前环境变量供后台使用
    local WEBHOOK_URL=$(get_config "FEISHU_WEBHOOK_URL" "")
    local STOP_MAX_LENGTH=$(get_config "STOP_MESSAGE_MAX_LENGTH" "5000")
    local STOP_THINKING_MAX_LENGTH=$(get_config "STOP_THINKING_MAX_LENGTH" "5000")
    local CALLBACK_URL=$(get_config "CALLBACK_SERVER_URL" "http://localhost:8080")
    local TRANSCRIPT_PATH=$(json_get "$INPUT" "transcript_path")
    local PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(json_get "$INPUT" "cwd")}"
    local PROJECT_NAME=$(basename "${PROJECT_DIR:-$(pwd)}")
    local SESSION_ID=""
    local TIMESTAMP=$(date "+%Y-%m-%d %H:%M:%S")

    # 检查 Webhook URL
    if [ -z "$WEBHOOK_URL" ]; then
        return 0
    fi

    # 引入函数库（后台进程需要重新引入）
    source "$LIB_DIR/core.sh" 2>/dev/null || return 0
    source "$LIB_DIR/feishu.sh" 2>/dev/null || return 0
    source "$LIB_DIR/json.sh" 2>/dev/null || return 0
    json_init
    log_init

    log "Stop notification: extracting response from transcript"

    # 提取 Claude 响应内容（text + thinking）
    local CLAUDE_RESPONSE=""
    local CLAUDE_THINKING=""
    local response_json=""

    # 使用新的 extract_response 函数（支持子代理回退）
    response_json=$(extract_response "$TRANSCRIPT_PATH")

    if [ -n "$response_json" ] && [ "$response_json" != "null" ]; then
        # 从结果中提取各字段
        SESSION_ID=$(json_get "$response_json" "session_id")
        if [ -z "$SESSION_ID" ]; then
            SESSION_ID="unknown"
        fi

        CLAUDE_RESPONSE=$(json_get "$response_json" "text")
        CLAUDE_THINKING=$(json_get "$response_json" "thinking")
        log "Extracted response: ${#CLAUDE_RESPONSE} chars, thinking: ${#CLAUDE_THINKING} chars"
    fi

    if [ -z "$CLAUDE_RESPONSE" ]; then
        CLAUDE_RESPONSE="任务已完成，请返回终端查看详细信息。"
        log "Using default response"
    fi

    # 截断过长响应
    if [ ${#CLAUDE_RESPONSE} -gt "$STOP_MAX_LENGTH" ]; then
        CLAUDE_RESPONSE="${CLAUDE_RESPONSE:0:$STOP_MAX_LENGTH}..."
        log "Response truncated to ${#CLAUDE_RESPONSE} chars"
    fi

    # 处理 thinking：STOP_THINKING_MAX_LENGTH=0 时跳过
    if [ "$STOP_THINKING_MAX_LENGTH" = "0" ]; then
        CLAUDE_THINKING=""
        log "Thinking display disabled (STOP_THINKING_MAX_LENGTH=0)"
    elif [ -n "$CLAUDE_THINKING" ] && [ ${#CLAUDE_THINKING} -gt "$STOP_THINKING_MAX_LENGTH" ]; then
        CLAUDE_THINKING="${CLAUDE_THINKING:0:$STOP_THINKING_MAX_LENGTH}..."
        log "Thinking truncated to ${#CLAUDE_THINKING} chars"
    fi

    log "Final response (${#CLAUDE_RESPONSE} chars), thinking (${#CLAUDE_THINKING} chars)"

    # 构建并发送卡片
    local CARD
    CARD=$(build_stop_card "$CLAUDE_RESPONSE" "$PROJECT_NAME" "$TIMESTAMP" "${SESSION_ID:0:8}" "$CLAUDE_THINKING" 2>/dev/null)

    if [ -n "$CARD" ]; then
        # 传递 session_id, project_dir, callback_url 支持回复继续会话
        local options
        options=$(json_build_object "webhook_url" "$WEBHOOK_URL" "session_id" "$SESSION_ID" "project_dir" "$PROJECT_DIR" "callback_url" "$CALLBACK_URL")
        send_feishu_card "$CARD" "$options" >/dev/null 2>&1
    fi
}

# 启动后台通知发送（不等待，立即返回）
send_stop_notification_async &

# 立即返回，不阻塞 Claude Code
exit 0
