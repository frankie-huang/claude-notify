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
# 后台异步发送通知函数
# =============================================================================
send_stop_notification_async() {
    # 捕获当前环境变量供后台使用
    local WEBHOOK_URL=$(get_config "FEISHU_WEBHOOK_URL" "")
    local STOP_MAX_LENGTH=$(get_config "STOP_MESSAGE_MAX_LENGTH" "5000")
    local TRANSCRIPT_PATH=$(json_get "$INPUT" "transcript_path")
    local PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(json_get "$INPUT" "cwd")}"
    local PROJECT_NAME=$(basename "${PROJECT_DIR:-$(pwd)}")
    local SESSION_SLUG=""
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
    if [ -n "$TRANSCRIPT_PATH" ] && [ -f "$TRANSCRIPT_PATH" ]; then
        log "Transcript file exists: $TRANSCRIPT_PATH"

        # 重试机制：最多等待 0.5秒 让文件写入完成
        local last_assistant=""
        local max_retries=5
        local retry_count=0

        while [ $retry_count -lt $max_retries ]; do
            if [ "$JSON_HAS_JQ" = "true" ]; then
                last_assistant=$(jq -r 'select(.type=="assistant")' "$TRANSCRIPT_PATH" 2>/dev/null | tail -1)
            elif [ "$JSON_HAS_PYTHON3" = "true" ]; then
                last_assistant=$(python3 -c "
import sys, json
with open('$TRANSCRIPT_PATH', 'r') as f:
    lines = f.readlines()
for line in reversed(lines):
    if not line.strip():
        continue
    try:
        data = json.loads(line)
        if data.get('type') == 'assistant':
            print(json.dumps(data))
            break
    except:
        pass
" 2>/dev/null)
            fi

            if [ -n "$last_assistant" ]; then
                log "Found assistant message on attempt $((retry_count + 1))"
                # 从消息中提取 slug 作为会话标识
                SESSION_SLUG=$(json_get "$last_assistant" "slug")
                # 如果没有 slug，尝试用 sessionId 的前 8 位作为降级方案
                if [ -z "$SESSION_SLUG" ]; then
                    local session_id=$(json_get "$last_assistant" "sessionId")
                    if [ -n "$session_id" ]; then
                        SESSION_SLUG="${session_id:0:8}"
                    else
                        SESSION_SLUG="unknown"
                    fi
                fi
                break
            fi

            retry_count=$((retry_count + 1))
            if [ $retry_count -lt $max_retries ]; then
                sleep 0.1
            fi
        done

        # 从 assistant 消息中提取 text 内容
        if [ -n "$last_assistant" ]; then
            # 使用 json_get_array_value 提取所有 type=text 的内容
            CLAUDE_RESPONSE=$(json_get_array_value "$last_assistant" "message.content" "text" "text")
            # 恢复原有的换行符
            CLAUDE_RESPONSE=$(echo "$CLAUDE_RESPONSE" | sed 's/∂/\n/g')
            log "Extracted via json_get_array_value: ${#CLAUDE_RESPONSE} chars"
        else
            log "No assistant message found after $max_retries attempts"
        fi
    else
        log "Transcript file not found: $TRANSCRIPT_PATH"
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
    CARD=$(build_stop_card "✅ Claude Code 完成" "$CLAUDE_RESPONSE" "$PROJECT_NAME" "$TIMESTAMP" "$SESSION_SLUG" 2>/dev/null)

    if [ -n "$CARD" ]; then
        send_feishu_card "$CARD" "$WEBHOOK_URL" >/dev/null 2>&1
    fi
}

# 启动后台通知发送（不等待，立即返回）
send_stop_notification_async &

# 立即返回，不阻塞 Claude Code
exit 0
