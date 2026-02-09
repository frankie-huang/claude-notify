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
# 从单个 transcript 文件中查找最后一条 assistant 消息
# 参数:
#   $1 - transcript 文件路径
#   $2 - 最大重试次数 (可选，默认 5)
# 返回:
#   输出 assistant 消息的 JSON 字符串，找不到则输出空
# 说明:
#   找到最后一条 type=="assistant" 的消息后，检查其 message.content 是否包含
#   type="text" 的元素。如果不包含（可能是 thinking、tool_use 等其他类型），
#   则返回空，视为找不到有效的文本响应。
# =============================================================================
find_last_assistant_in_file() {
    local transcript_file="$1"
    local max_retries="${2:-5}"
    local retry_count=0
    local last_assistant=""

    if [ ! -f "$transcript_file" ]; then
        return 1
    fi

    while [ $retry_count -lt $max_retries ]; do
        if [ "$JSON_HAS_JQ" = "true" ]; then
            # 先找到最后一条 assistant 消息
            last_assistant=$(jq -s 'map(select(.type=="assistant")) | .[-1]' "$transcript_file" 2>/dev/null)
            # 检查是否包含 text 类型内容，不包含则清空
            if [ -n "$last_assistant" ]; then
                local has_text=$(echo "$last_assistant" | jq -r '.message.content | map(select(.type=="text")) | length > 0' 2>/dev/null)
                if [ "$has_text" != "true" ]; then
                    log "Last assistant message has no text content, skipping"
                    last_assistant=""
                fi
            fi
        elif [ "$JSON_HAS_PYTHON3" = "true" ]; then
            last_assistant=$(python3 -c "
import sys, json
with open('$transcript_file', 'r') as f:
    lines = f.readlines()
# 找最后一条 assistant 消息
for line in reversed(lines):
    if not line.strip():
        continue
    try:
        data = json.loads(line)
        if data.get('type') == 'assistant':
            # 检查 message.content 中是否有 type='text' 的元素
            content = data.get('message', {}).get('content', [])
            has_text = any(item.get('type') == 'text' for item in content if isinstance(item, dict))
            if has_text:
                print(json.dumps(data))
            # 无论是否有 text，都只检查最后一条 assistant 消息，然后退出
            break
    except:
        pass
" 2>/dev/null)
        fi

        if [ -n "$last_assistant" ]; then
            echo "$last_assistant"
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
# 查找最后一条 assistant 消息（带子代理回退）
# 参数:
#   $1 - 主 transcript 文件路径
# 返回:
#   输出 assistant 消息的 JSON 字符串
# 说明:
#   1. 先在主 transcript 文件中查找
#   2. 如果找不到，检查 subagents 目录，按修改时间倒序查找
# =============================================================================
find_last_assistant() {
    local transcript_path="$1"

    # 提前检查：路径为空直接返回
    if [ -z "$transcript_path" ]; then
        log "Transcript path is empty"
        return 1
    fi

    local last_assistant=""

    # 1. 先在主 transcript 文件中查找
    if [ -n "$transcript_path" ] && [ -f "$transcript_path" ]; then
        log "Searching in main transcript: $transcript_path"
        last_assistant=$(find_last_assistant_in_file "$transcript_path" 5)
        if [ -n "$last_assistant" ]; then
            log "Found assistant message in main transcript"
            echo "$last_assistant"
            return 0
        fi
    fi

    # 2. 主 transcript 找不到，尝试在 subagents 目录中查找
    local session_dir="${transcript_path%.jsonl}"
    local subagents_dir="$session_dir/subagents"

    if [ -d "$subagents_dir" ]; then
        log "Main transcript has no assistant message, searching in subagents: $subagents_dir"

        # 按修改时间倒序遍历子代理文件
        local subagent_files
        subagent_files=$(ls -t "$subagents_dir"/*.jsonl 2>/dev/null) || true

        for subagent_file in $subagent_files; do
            if [ -f "$subagent_file" ]; then
                log "Searching in subagent: $(basename "$subagent_file")"
                last_assistant=$(find_last_assistant_in_file "$subagent_file" 3)
                if [ -n "$last_assistant" ]; then
                    log "Found assistant message in subagent: $(basename "$subagent_file")"
                    echo "$last_assistant"
                    return 0
                fi
            fi
        done
    fi

    log "No assistant message found in transcript or subagents"
    return 1
}

# =============================================================================
# 后台异步发送通知函数
# =============================================================================
send_stop_notification_async() {
    # 捕获当前环境变量供后台使用
    local WEBHOOK_URL=$(get_config "FEISHU_WEBHOOK_URL" "")
    local STOP_MAX_LENGTH=$(get_config "STOP_MESSAGE_MAX_LENGTH" "5000")
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

    # 提取 Claude 响应内容
    local CLAUDE_RESPONSE=""
    local last_assistant=""

    # 使用抽象函数查找最后的 assistant 消息（支持子代理回退）
    last_assistant=$(find_last_assistant "$TRANSCRIPT_PATH")

    if [ -n "$last_assistant" ]; then
        # 从消息中提取 session_id
        SESSION_ID=$(json_get "$last_assistant" "sessionId")
        if [ -z "$SESSION_ID" ]; then
            SESSION_ID="unknown"
        fi

        # 使用 json_get_array_value 提取所有 type=text 的内容
        CLAUDE_RESPONSE=$(json_get_array_value "$last_assistant" "message.content" "text" "text")
        # 恢复原有的换行符
        CLAUDE_RESPONSE=$(echo "$CLAUDE_RESPONSE" | sed 's/∂/\n/g')
        log "Extracted response: ${#CLAUDE_RESPONSE} chars"
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

    log "Final response (${#CLAUDE_RESPONSE} chars): $CLAUDE_RESPONSE"

    # 构建并发送卡片
    local CARD
    CARD=$(build_stop_card "$CLAUDE_RESPONSE" "$PROJECT_NAME" "$TIMESTAMP" "${SESSION_ID:0:8}" 2>/dev/null)

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
