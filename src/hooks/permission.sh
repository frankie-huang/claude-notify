#!/bin/bash
# =============================================================================
# src/hooks/permission.sh - Claude Code 权限请求处理脚本
#
# 此脚本由 hook-router.sh 通过 source 调用，不直接执行
#
# 前置条件（由 hook-router.sh 完成）:
#   - $INPUT 变量包含从 stdin 读取的 JSON 数据
#   - 核心库、JSON 解析器、日志系统已初始化
#   - $PROJECT_ROOT, $SRC_DIR, $LIB_DIR 等路径变量已设置
#
# 工作模式:
#   1. 交互模式: 回调服务运行时，发送带按钮的卡片，等待用户点击，返回决策
#   2. 降级模式: 回调服务不可用时，仅发送通知卡片，不等待响应
# =============================================================================

# =============================================================================
# 引入额外的函数库
# =============================================================================
source "$LIB_DIR/tool.sh"
source "$LIB_DIR/feishu.sh"
source "$LIB_DIR/socket.sh"
source "$LIB_DIR/vscode-proxy.sh"

# =============================================================================
# Claude Code Hook Exit Codes
# 参考: https://docs.anthropic.com/en/docs/claude-code/hooks
#
# EXIT_HOOK_SUCCESS (0)  - Hook 成功执行，使用输出的决策 JSON
# EXIT_FALLBACK (1)      - 回退到终端交互模式（非0非2的任意值）
# EXIT_HOOK_ERROR (2)    - Hook 执行错误，Claude 会显示错误信息
# =============================================================================
EXIT_HOOK_SUCCESS=0
EXIT_FALLBACK=1
EXIT_HOOK_ERROR=2

# =============================================================================
# 配置 (优先级: .env > 环境变量 > 默认值)
# =============================================================================
SOCKET_PATH=$(get_config "PERMISSION_SOCKET_PATH" "/tmp/claude-permission.sock")
WEBHOOK_URL=$(get_config "FEISHU_WEBHOOK_URL" "")
CALLBACK_SERVER_URL=$(get_config "CALLBACK_SERVER_URL" "http://localhost:8080")
NOTIFY_DELAY=$(get_config "PERMISSION_NOTIFY_DELAY" "60")

# 时间戳
TIMESTAMP=$(date "+%Y-%m-%d %H:%M:%S")

# =============================================================================
# 解析 JSON（使用 $INPUT 变量，不再从 stdin 读取）
# =============================================================================
TOOL_NAME=$(json_get "$INPUT" "tool_name")
TOOL_NAME="${TOOL_NAME:-unknown}"
SESSION_ID=$(json_get "$INPUT" "session_id")
SESSION_ID="${SESSION_ID:-unknown}"
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(json_get "$INPUT" "cwd")}"
PROJECT_DIR="${PROJECT_DIR:-$(pwd)}"

log "Tool: $TOOL_NAME, Session: $SESSION_ID, Project: $PROJECT_DIR"

# =============================================================================
# 延迟发送（带父进程存活检测）
# =============================================================================
delay_with_parent_check() {
    local delay="$1"
    local parent_pid="$PPID"

    if [ -z "$delay" ] || [ "$delay" -le 0 ] 2>/dev/null; then
        return 0
    fi

    log "Delaying notification for ${delay}s (parent PID: $parent_pid)"

    local i=0
    while [ "$i" -lt "$delay" ]; do
        sleep 1
        if ! kill -0 "$parent_pid" 2>/dev/null; then
            log "Parent process $parent_pid exited, skipping notification"
            return 1
        fi
        i=$((i + 1))
    done

    return 0
}

# =============================================================================
# 生成请求 ID
# =============================================================================
generate_request_id() {
    local ts=$(date +%s)
    local uuid=""

    if command -v uuidgen &> /dev/null; then
        uuid=$(uuidgen | tr '[:upper:]' '[:lower:]' | cut -c1-8)
    elif [ -f /proc/sys/kernel/random/uuid ]; then
        uuid=$(cat /proc/sys/kernel/random/uuid | cut -c1-8)
    else
        uuid=$(head -c 8 /dev/urandom | od -An -tx1 | tr -d ' \n' | cut -c1-8)
    fi

    echo "${ts}-${uuid}"
}

REQUEST_ID=$(generate_request_id)
log "Request ID: $REQUEST_ID"

# =============================================================================
# 交互模式主流程
# =============================================================================
run_interactive_mode() {
    log "Running in interactive mode"

    if [ -z "$WEBHOOK_URL" ]; then
        log "FEISHU_WEBHOOK_URL not set, falling back to terminal interaction"
        run_fallback_mode
        return
    fi

    # 提取工具详情
    extract_tool_detail "$INPUT" "$TOOL_NAME"
    local command_content="$EXTRACTED_COMMAND"
    local description="$EXTRACTED_DESCRIPTION"
    local template_color="$EXTRACTED_COLOR"
    local project_name
    project_name=$(basename "$PROJECT_DIR")

    # 记录 command 到单独的日志文件
    log_command "$command_content" "$REQUEST_ID" "$TOOL_NAME" "$SESSION_ID"

    # 延迟发送
    if ! delay_with_parent_check "$NOTIFY_DELAY"; then
        exit $EXIT_FALLBACK
    fi

    # 构建交互按钮（根据 FEISHU_SEND_MODE 自动选择按钮类型）
    local buttons
    buttons=$(build_permission_buttons "$CALLBACK_SERVER_URL" "$REQUEST_ID")

    # 构建飞书卡片
    local card
    card=$(build_permission_card "$TOOL_NAME" "$project_name" "$TIMESTAMP" "$command_content" "$description" "$template_color" "$buttons" "${SESSION_ID:0:8}")

    log "Sending interactive Feishu card"
    # 传递 session_id、project_dir、callback_url 支持回复继续会话
    local options
    options=$(json_build_object "webhook_url" "$WEBHOOK_URL" "session_id" "$SESSION_ID" "project_dir" "$PROJECT_DIR" "callback_url" "$CALLBACK_SERVER_URL")
    send_feishu_card "$card" "$options"

    # 构建请求 JSON
    local request_json
    local encoded_input
    encoded_input=$(echo "$INPUT" | base64 -w 0)

    if [ "$JSON_HAS_JQ" = "true" ]; then
        request_json=$(jq -n \
            --arg rid "$REQUEST_ID" \
            --arg pdir "$PROJECT_DIR" \
            --arg enc "$encoded_input" \
            --arg hpid "$$" \
            '{request_id: $rid, project_dir: $pdir, raw_input_encoded: $enc, hook_pid: $hpid}')
    else
        local escaped_project
        escaped_project=$(echo "$PROJECT_DIR" | sed 's/\\/\\\\/g; s/"/\\"/g')
        request_json=$(json_build_object "request_id" "$REQUEST_ID" "project_dir" "$escaped_project" "raw_input_encoded" "$encoded_input" "hook_pid" "$$")
    fi

    log "Sending request to callback server"

    # 通过 Socket 发送请求并等待响应
    local response
    response=$(socket_send_request "$request_json" "$SOCKET_PATH")

    if [ -z "$response" ]; then
        log "Socket communication failed, empty response (card already sent)"
        exit $EXIT_FALLBACK
    fi

    log "Received response: $response"

    # 解析响应
    parse_socket_response "$response"

    if [ "$RESPONSE_FALLBACK" = "true" ]; then
        log "Server timeout, falling back to terminal interaction (card already sent)"
        exit $EXIT_FALLBACK
    fi

    if [ "$RESPONSE_SUCCESS" = "true" ]; then
        output_decision "$RESPONSE_BEHAVIOR" "$RESPONSE_MESSAGE" "$RESPONSE_INTERRUPT"
        vscode_proxy_activate "$PROJECT_DIR"
    else
        log "Callback service returned error, falling back to terminal (card already sent)"
        exit $EXIT_FALLBACK
    fi
}

# =============================================================================
# 降级模式
# =============================================================================
run_fallback_mode() {
    log "Running in fallback mode (notification only)"

    if [ -z "$WEBHOOK_URL" ]; then
        log "FEISHU_WEBHOOK_URL not set, skipping notification"
        exit $EXIT_FALLBACK
    fi

    # 提取工具详情
    extract_tool_detail "$INPUT" "$TOOL_NAME"
    local command_content="$EXTRACTED_COMMAND"
    local description="$EXTRACTED_DESCRIPTION"
    local template_color="$EXTRACTED_COLOR"
    local project_name
    project_name=$(basename "$PROJECT_DIR")

    # 记录 command 到单独的日志文件
    log_command "$command_content" "$REQUEST_ID" "$TOOL_NAME" "$SESSION_ID"

    # 延迟发送
    if ! delay_with_parent_check "$NOTIFY_DELAY"; then
        exit $EXIT_FALLBACK
    fi

    # 构建不带按钮的卡片
    local card
    card=$(build_permission_card "$TOOL_NAME" "$project_name" "$TIMESTAMP" "$command_content" "$description" "$template_color" "" "${SESSION_ID:0:8}")

    # 传递 session_id、project_dir、callback_url 支持回复继续会话
    local options
    options=$(json_build_object "webhook_url" "$WEBHOOK_URL" "session_id" "$SESSION_ID" "project_dir" "$PROJECT_DIR" "callback_url" "$CALLBACK_SERVER_URL")
    send_feishu_card "$card" "$options"

    log "Fallback notification sent"
    exit $EXIT_FALLBACK
}

# =============================================================================
# 输出决策给 Claude Code
# =============================================================================
output_decision() {
    local behavior="$1"
    local message="$2"
    local interrupt="$3"

    log "Outputting decision: behavior=$behavior, message=$message, interrupt=$interrupt"

    local decision_json

    if [ "$behavior" = "allow" ]; then
        decision_json='{"behavior": "allow"}'
    elif [ "$interrupt" = "true" ]; then
        decision_json="{\"behavior\": \"deny\", \"message\": \"${message}\", \"interrupt\": true}"
    else
        decision_json="{\"behavior\": \"deny\", \"message\": \"${message}\"}"
    fi

    cat << EOF
{
  "hookSpecificOutput": {
    "hookEventName": "PermissionRequest",
    "decision": ${decision_json}
  }
}
EOF

    log "Decision output complete"
}

# =============================================================================
# 主逻辑
# =============================================================================

# 检查 Socket 通信工具可用性
check_socket_tools

if [ "$HAS_SOCKET_CLIENT" = "false" ] && [ "$HAS_SOCAT" = "false" ]; then
    log "Warning: neither socket-client.py (python3) nor socat available, falling back to notification-only mode"
    run_fallback_mode
fi

# 检查回调服务并选择模式
if check_socket_service "$SOCKET_PATH"; then
    run_interactive_mode
else
    log "Callback service not available"
    run_fallback_mode
fi

# 交互模式成功输出决策后正常退出
exit $EXIT_HOOK_SUCCESS
