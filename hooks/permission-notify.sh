#!/bin/bash

# =============================================================================
# permission-notify.sh - Claude Code 权限请求飞书通知脚本（可交互版本）
#
# 用法: 配置为 PermissionRequest hook，从 stdin 接收 JSON 数据
#
# 工作模式:
#   1. 交互模式: 回调服务运行时，发送带按钮的卡片，等待用户点击，返回决策
#   2. 降级模式: 回调服务不可用时，仅发送通知卡片，不等待响应
#
# 环境变量:
#   FEISHU_WEBHOOK_URL     - 飞书 Webhook URL (必需)
#   CALLBACK_SERVER_URL    - 回调服务外部访问地址 (默认: http://localhost:8080)
#   PERMISSION_SOCKET_PATH - Unix Socket 路径 (默认: /tmp/claude-permission.sock)
# =============================================================================

# =============================================================================
# 引入函数库
# =============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
source "${PROJECT_ROOT}/shell-lib/log.sh"
source "${PROJECT_ROOT}/shell-lib/json.sh"
source "${PROJECT_ROOT}/shell-lib/tool.sh"
source "${PROJECT_ROOT}/shell-lib/feishu.sh"
source "${PROJECT_ROOT}/shell-lib/socket.sh"

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
# 初始化
# =============================================================================

# 初始化日志系统
log_init

# 初始化 JSON 解析器
json_init

# 配置
SOCKET_PATH="${PERMISSION_SOCKET_PATH:-/tmp/claude-permission.sock}"
WEBHOOK_URL="${FEISHU_WEBHOOK_URL:-}"
CALLBACK_SERVER_URL="${CALLBACK_SERVER_URL:-http://localhost:8080}"

# 时间戳
TIMESTAMP=$(date "+%Y-%m-%d %H:%M:%S")

# 从 stdin 读取 JSON 数据
INPUT=$(cat)

# 记录输入
log_input

# =============================================================================
# 解析 JSON
# =============================================================================
TOOL_NAME=$(json_get "$INPUT" "tool_name")
TOOL_NAME="${TOOL_NAME:-unknown}"
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(json_get "$INPUT" "cwd")}"
PROJECT_DIR="${PROJECT_DIR:-$(pwd)}"

log "Tool: $TOOL_NAME, Project: $PROJECT_DIR"

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
# 交互模式：通过 Socket 与回调服务通信
# =============================================================================
# 架构说明：
#   - permission-notify.sh 负责发送飞书卡片（带交互按钮）
#   - 通过 Unix Socket 将请求注册到回调服务
#   - 用户点击飞书按钮后，回调服务接收 HTTP 请求
#   - 回调服务通过同一个 Socket 连接返回用户决策
#   - permission-notify.sh 接收决策并返回给 Claude Code
# =============================================================================

# 交互模式主流程
run_interactive_mode() {
    log "Running in interactive mode"

    # 检查 Webhook URL
    if [ -z "$WEBHOOK_URL" ]; then
        log "FEISHU_WEBHOOK_URL not set, falling back to terminal interaction"
        run_fallback_mode
        return
    fi

    # 提取工具详情
    extract_tool_detail "$INPUT" "$TOOL_NAME"
    local detail_content="$EXTRACTED_DETAIL"
    local template_color="$EXTRACTED_COLOR"
    local project_name
    project_name=$(basename "$PROJECT_DIR")

    # 构建交互按钮
    local buttons
    buttons=$(build_permission_buttons "$CALLBACK_SERVER_URL" "$REQUEST_ID")

    # 构建并发送飞书卡片
    local card
    card=$(build_permission_card "$TOOL_NAME" "$project_name" "$TIMESTAMP" "$detail_content" "$template_color" "$buttons")

    log "Sending interactive Feishu card"
    send_feishu_card "$card" "$WEBHOOK_URL"

    # 构建请求 JSON - 使用 base64 编码安全传输
    local request_json
    local encoded_input
    encoded_input=$(echo "$INPUT" | base64 -w 0)

    if [ "$JSON_HAS_JQ" = "true" ]; then
        request_json=$(jq -n \
            --arg rid "$REQUEST_ID" \
            --arg pdir "$PROJECT_DIR" \
            --arg enc "$encoded_input" \
            '{request_id: $rid, project_dir: $pdir, raw_input_encoded: $enc}')
    else
        local escaped_project
        escaped_project=$(echo "$PROJECT_DIR" | sed 's/\\/\\\\/g; s/"/\\"/g')
        request_json=$(json_build_object "request_id" "$REQUEST_ID" "project_dir" "$escaped_project" "raw_input_encoded" "$encoded_input")
    fi

    log "Sending request to callback server"

    # 通过 Socket 发送请求并等待响应
    local response
    response=$(socket_send_request "$request_json" "$SOCKET_PATH")

    if [ -z "$response" ]; then
        # Socket 通信失败，直接退出（卡片已发送）
        log "Socket communication failed, empty response (card already sent)"
        exit $EXIT_FALLBACK
    fi

    log "Received response: $response"

    # 解析响应
    parse_socket_response "$response"

    # 检查是否需要回退到终端交互
    if [ "$RESPONSE_FALLBACK" = "true" ]; then
        # 服务器超时，回退到终端交互模式
        # 注意：不调用 run_fallback_mode，因为交互卡片已经发送过了
        log "Server timeout, falling back to terminal interaction (card already sent)"
        exit $EXIT_FALLBACK
    fi

    if [ "$RESPONSE_SUCCESS" = "true" ]; then
        # 只有用户明确决策时才输出决策（allow 或 deny）
        output_decision "$RESPONSE_BEHAVIOR" "$RESPONSE_MESSAGE" "$RESPONSE_INTERRUPT"
    else
        # 服务返回任何错误都回退到终端交互模式
        # 只有用户点击拒绝按钮时才会返回 success=true + behavior=deny
        # 直接退出，不再发送卡片（卡片已发送）
        log "Callback service returned error, falling back to terminal (card already sent)"
        exit $EXIT_FALLBACK
    fi
}

# =============================================================================
# 降级模式：仅发送通知，不等待响应
# =============================================================================
# 使用场景：
#   - 回调服务未运行（Socket 文件不存在）
#   - Socket 通信工具不可用
#
# 行为：
#   - 发送不带交互按钮的飞书通知卡片
#   - 返回 EXIT_FALLBACK (1)，让 Claude Code 回退到终端交互
# =============================================================================

run_fallback_mode() {
    log "Running in fallback mode (notification only)"

    if [ -z "$WEBHOOK_URL" ]; then
        log "FEISHU_WEBHOOK_URL not set, skipping notification"
        # 直接回退到终端交互模式，不发送通知
        exit $EXIT_FALLBACK
    fi

    # 提取工具详情
    extract_tool_detail "$INPUT" "$TOOL_NAME"
    local detail_content="$EXTRACTED_DETAIL"
    local template_color="$EXTRACTED_COLOR"
    local project_name
    project_name=$(basename "$PROJECT_DIR")

    # 构建不带按钮的卡片
    local card
    card=$(build_permission_card "$TOOL_NAME" "$project_name" "$TIMESTAMP" "$detail_content" "$template_color" "")

    # 发送通知（使用统一的发送函数，失败时自动发送降级文本消息）
    send_feishu_card "$card" "$WEBHOOK_URL"

    log "Fallback notification sent"

    # 降级模式不返回决策，回退到终端交互模式
    exit $EXIT_FALLBACK
}

# =============================================================================
# 输出决策给 Claude Code
# =============================================================================
# 功能：根据 Claude Code Hook 规范输出决策 JSON
#
# 输出格式：
#   {
#     "hookSpecificOutput": {
#       "hookEventName": "PermissionRequest",
#       "decision": {
#         "behavior": "allow" | "deny",
#         "message": "原因说明",
#         "interrupt": true | false
#       }
#     }
#   }
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

    # 输出完整的 hook 响应
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
# 执行流程：
#   1. 检查 Socket 通信工具可用性（Python 客户端或 socat）
#   2. 检查回调服务是否运行（Socket 文件是否存在）
#   3. 根据检查结果选择运行模式：
#      - 交互模式：回调服务运行中
#      - 降级模式：回调服务未运行或通信失败
# =============================================================================

# 检查 Socket 通信工具可用性
check_socket_tools

if [ "$HAS_SOCKET_CLIENT" = "false" ] && [ "$HAS_SOCAT" = "false" ]; then
    log "Warning: neither socket-client.py (python3) nor socat available, falling back to notification-only mode"
    run_fallback_mode
    # run_fallback_mode 内部会 exit，以下代码不会执行
fi

# 检查回调服务并选择模式
if check_socket_service "$SOCKET_PATH"; then
    run_interactive_mode
else
    log "Callback service not available"
    run_fallback_mode
    # run_fallback_mode 内部会 exit，以下代码不会执行
fi

# 交互模式成功输出决策后正常退出
exit $EXIT_HOOK_SUCCESS
