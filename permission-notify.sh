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
#                            注意：这是飞书按钮点击后访问的地址，必须是飞书用户可访问的 URL
#                            如果飞书和回调服务在同一台机器上，可以使用 localhost
#                            如果飞书在外网，需要配置公网 IP 或域名
#   PERMISSION_SOCKET_PATH - Unix Socket 路径 (默认: /tmp/claude-permission.sock)
#   REQUEST_TIMEOUT        - 服务器端超时秒数 (默认: 300，0=禁用)
# =============================================================================

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

# 配置
SOCKET_PATH="${PERMISSION_SOCKET_PATH:-/tmp/claude-permission.sock}"
WEBHOOK_URL="${FEISHU_WEBHOOK_URL:-}"
CALLBACK_SERVER_URL="${CALLBACK_SERVER_URL:-http://localhost:8080}"

# 日志目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${SCRIPT_DIR}/log"
mkdir -p "$LOG_DIR"
LOG_DATE=$(date "+%Y%m%d")
LOG_FILE="${LOG_DIR}/permission_${LOG_DATE}.log"

# 从 stdin 读取 JSON 数据
INPUT=$(cat)

# 时间戳
TIMESTAMP=$(date "+%Y-%m-%d %H:%M:%S")

# =============================================================================
# 日志函数
# =============================================================================

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

log_input() {
    {
        echo "=========================================="
        echo "时间: ${TIMESTAMP}"
        echo "=========================================="
        echo ""
        echo "=== 原始 JSON 数据 ==="
        echo "$INPUT" | if command -v jq &> /dev/null; then jq .; else cat; fi
        echo ""
    } >> "$LOG_FILE"
}

log_input

# =============================================================================
# 解析 JSON（优先使用 jq，否则使用原生命令）
# =============================================================================

if command -v jq &> /dev/null; then
    # 优先使用 jq（最可靠）
    TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // "unknown"')
    TOOL_INPUT=$(echo "$INPUT" | jq -c '.tool_input // {}')
    PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(echo "$INPUT" | jq -r '.cwd // ""')}"
elif command -v python3 &> /dev/null; then
    # 使用 Python3 解析 JSON（比 grep/sed 更可靠）
    TOOL_NAME=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_name','unknown'))" 2>/dev/null)
    TOOL_NAME="${TOOL_NAME:-unknown}"
    TOOL_INPUT=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d.get('tool_input',{})))" 2>/dev/null)
    TOOL_INPUT="${TOOL_INPUT:-{}}"
    CWD=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('cwd',''))" 2>/dev/null)
    PROJECT_DIR="${CLAUDE_PROJECT_DIR:-${CWD:-$(pwd)}}"
else
    # 最后的降级方案：grep/sed（有已知限制，无法处理转义字符和多行值）
    log "Warning: neither jq nor python3 available, using limited grep/sed parsing"
    TOOL_NAME=$(echo "$INPUT" | grep -o '"tool_name"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | \
        sed 's/"tool_name"[[:space:]]*:[[:space:]]*"//' | sed 's/"$//')
    TOOL_NAME="${TOOL_NAME:-unknown}"

    # 提取 tool_input 对象（简化版，只提取常用字段）
    if [ "$TOOL_NAME" = "Bash" ]; then
        COMMAND=$(echo "$INPUT" | grep -o '"command"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | \
            sed 's/"command"[[:space:]]*:[[:space:]]*"//' | sed 's/"$//')
        TOOL_INPUT="{\"command\":\"${COMMAND}\"}"
    else
        FILE_PATH=$(echo "$INPUT" | grep -o '"file_path"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | \
            sed 's/"file_path"[[:space:]]*:[[:space:]]*"//' | sed 's/"$//')
        TOOL_INPUT="{\"file_path\":\"${FILE_PATH}\"}"
    fi

    # 提取 cwd
    CWD=$(echo "$INPUT" | grep -o '"cwd"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | \
        sed 's/"cwd"[[:space:]]*:[[:space:]]*"//' | sed 's/"$//')
    PROJECT_DIR="${CLAUDE_PROJECT_DIR:-${CWD:-$(pwd)}}"
fi

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
# 检查回调服务是否可用
# =============================================================================

check_callback_service() {
    if [ ! -S "$SOCKET_PATH" ]; then
        return 1
    fi
    return 0
}

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

# 发送飞书交互卡片
# 功能：
#   1. 根据工具类型生成带颜色的飞书卡片
#   2. 卡片包含 4 个交互按钮（批准、始终允许、拒绝、拒绝并中断）
#   3. 按钮链接指向回调服务器的 HTTP 端点
send_interactive_card() {
    log "Sending interactive Feishu card"

    # 获取项目名称
    local project_name
    project_name=$(basename "$PROJECT_DIR")

    # 构建详情内容
    local detail_content template

    case "$TOOL_NAME" in
        "Bash")
            local command
            if command -v jq &> /dev/null; then
                command=$(echo "$INPUT" | jq -r '.tool_input.command // "N/A"')
            elif command -v python3 &> /dev/null; then
                command=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('command','N/A'))" 2>/dev/null)
            else
                command=$(echo "$INPUT" | grep -o '"command"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | \
                    sed 's/"command"[[:space:]]*:[[:space:]]*"//' | sed 's/"$//')
                command="${command:-N/A}"
            fi
            if [ ${#command} -gt 500 ]; then
                command="${command:0:500}..."
            fi
            command=$(echo "$command" | sed 's/\\/\\\\/g; s/"/\\"/g')
            detail_content="**命令：**\\n\`\`\`\\n${command}\\n\`\`\`"
            template="orange"
            ;;
        "Edit"|"Write")
            local file_path
            if command -v jq &> /dev/null; then
                file_path=$(echo "$INPUT" | jq -r '.tool_input.file_path // "N/A"')
            elif command -v python3 &> /dev/null; then
                file_path=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('file_path','N/A'))" 2>/dev/null)
            else
                file_path=$(echo "$INPUT" | grep -o '"file_path"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | \
                    sed 's/"file_path"[[:space:]]*:[[:space:]]*"//' | sed 's/"$//')
                file_path="${file_path:-N/A}"
            fi
            detail_content="**文件：** \`${file_path}\`"
            template="yellow"
            ;;
        *)
            detail_content="**工具：** ${TOOL_NAME}"
            template="grey"
            ;;
    esac

    # 添加描述（如果有）
    local description
    if command -v jq &> /dev/null; then
        description=$(echo "$INPUT" | jq -r '.tool_input.description // empty')
    elif command -v python3 &> /dev/null; then
        description=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('description','') or '')" 2>/dev/null)
    else
        description=$(echo "$INPUT" | grep -o '"description"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | \
            sed 's/"description"[[:space:]]*:[[:space:]]*"//' | sed 's/"$//')
    fi
    if [ -n "$description" ]; then
        detail_content="${detail_content}\\n**描述：** ${description}"
    fi

    # 构建卡片（带交互按钮）
    local base_url
    base_url=$(echo "$CALLBACK_SERVER_URL" | sed 's:/*$::')

    local card_content
    card_content=$(cat << EOF
{
  "msg_type": "interactive",
  "card": {
    "header": {
      "template": "${template}",
      "title": {"content": "Claude Code 权限请求", "tag": "plain_text"}
    },
    "elements": [
      {
        "tag": "div",
        "text": {"content": "**Claude Code 请求使用 ${TOOL_NAME} 工具**", "tag": "lark_md"}
      },
      {"tag": "hr"},
      {
        "tag": "div",
        "fields": [
          {"is_short": true, "text": {"content": "**项目：**\n${project_name}", "tag": "lark_md"}},
          {"is_short": true, "text": {"content": "**时间：**\n${TIMESTAMP}", "tag": "lark_md"}}
        ]
      },
      {
        "tag": "div",
        "text": {"content": "${detail_content}", "tag": "lark_md"}
      },
      {"tag": "hr"},
      {
        "tag": "action",
        "actions": [
          {
            "tag": "button",
            "text": {"content": "批准运行", "tag": "plain_text"},
            "type": "primary",
            "multi_url": {"url": "${base_url}/allow?id=${REQUEST_ID}"}
          },
          {
            "tag": "button",
            "text": {"content": "始终允许", "tag": "plain_text"},
            "type": "default",
            "multi_url": {"url": "${base_url}/always?id=${REQUEST_ID}"}
          },
          {
            "tag": "button",
            "text": {"content": "拒绝运行", "tag": "plain_text"},
            "type": "danger",
            "multi_url": {"url": "${base_url}/deny?id=${REQUEST_ID}"}
          },
          {
            "tag": "button",
            "text": {"content": "拒绝并中断", "tag": "plain_text"},
            "type": "danger",
            "multi_url": {"url": "${base_url}/interrupt?id=${REQUEST_ID}"}
          }
        ]
      },
      {
        "tag": "note",
        "elements": [{"tag": "plain_text", "content": "请尽快操作以避免 Claude 超时等待"}]
      }
    ]
  }
}
EOF
)

    # 发送卡片
    local response
    log "Sending Feishu card: ${card_content}"
    response=$(curl -X POST "$WEBHOOK_URL" \
        -H "Content-Type: application/json" \
        -d "$card_content" \
        --max-time 5 \
        --silent \
        --show-error 2>&1)

    local curl_exit=$?
    if [ $curl_exit -ne 0 ] || echo "$response" | grep -q '"code":[^0]'; then
        log "Failed to send Feishu card: curl exit=$curl_exit, response=$response"
    else
        log "Feishu card sent successfully"
    fi
}

# 交互模式主流程
# 流程：
#   1. 检查 Webhook URL 配置
#   2. 发送飞书交互卡片
#   3. 通过 Unix Socket 向回调服务注册请求
#   4. 阻塞等待用户通过飞书按钮做出决策
#   5. 接收回调服务返回的决策
#   6. 输出决策给 Claude Code
run_interactive_mode() {
    log "Running in interactive mode"

    # 检查 Webhook URL
    if [ -z "$WEBHOOK_URL" ]; then
        log "FEISHU_WEBHOOK_URL not set, falling back to terminal interaction"
        run_fallback_mode
        return
    fi

    # 发送飞书卡片（包含交互按钮）
    send_interactive_card

    # 构建请求 JSON - 使用 base64 编码安全传输
    local request_json
    if command -v jq &> /dev/null; then
        # 使用 base64 编码原始输入，避免特殊字符问题
        local encoded_input=$(echo "$INPUT" | base64 -w 0)
        request_json=$(jq -n \
            --arg rid "$REQUEST_ID" \
            --arg pdir "$PROJECT_DIR" \
            --arg enc "$encoded_input" \
            '{request_id: $rid, project_dir: $pdir, raw_input_encoded: $enc}')
    else
        # 简化的 JSON 构建 - 也使用 base64
        local encoded_input=$(echo "$INPUT" | base64 -w 0)
        local escaped_project=$(echo "$PROJECT_DIR" | sed 's/\\/\\\\/g; s/"/\\"/g')
        request_json="{\"request_id\":\"${REQUEST_ID}\",\"project_dir\":\"${escaped_project}\",\"raw_input_encoded\":\"${encoded_input}\"}"
    fi

    log "Sending request to callback server"

    # 通过 Socket 发送请求并等待响应
    # 优先使用 Python 客户端（更可靠），否则回退到 socat
    local response=""

    if [ "$HAS_SOCKET_CLIENT" = "true" ]; then
        # 使用 Python 客户端，避免 socat 的 half-close 问题
        response=$(echo "$request_json" | python3 "$SOCKET_CLIENT" "$SOCKET_PATH" 2>&1)
        local exit_code=$?
        log "Socket client exit code: $exit_code"
    elif [ "$HAS_SOCAT" = "true" ]; then
        # 回退到 socat（可能不稳定）
        log "Using socat for socket communication"
        response=$(echo "$request_json" | socat - "UNIX-CONNECT:${SOCKET_PATH}" 2>/dev/null)
    else
        # 不应该到达这里，因为主逻辑已经检查过
        log "Error: no socket communication tool available"
        run_fallback_mode
        return
    fi

    if [ -z "$response" ]; then
        log "Socket communication failed (empty response)"
        run_fallback_mode
        return
    fi

    log "Received response: $response"

    # 解析响应
    local success behavior message interrupt

    if command -v jq &> /dev/null; then
        success=$(echo "$response" | jq -r '.success // false')
        behavior=$(echo "$response" | jq -r '.decision.behavior // "deny"')
        message=$(echo "$response" | jq -r '.decision.message // ""')
        interrupt=$(echo "$response" | jq -r '.decision.interrupt // false')
    else
        # 简单解析
        if echo "$response" | grep -q '"success"[[:space:]]*:[[:space:]]*true'; then
            success="true"
        else
            success="false"
        fi

        if echo "$response" | grep -q '"behavior"[[:space:]]*:[[:space:]]*"allow"'; then
            behavior="allow"
        else
            behavior="deny"
        fi

        if echo "$response" | grep -q '"interrupt"[[:space:]]*:[[:space:]]*true'; then
            interrupt="true"
        else
            interrupt="false"
        fi

        message=$(echo "$response" | grep -o '"message"[[:space:]]*:[[:space:]]*"[^"]*"' | \
            sed 's/"message"[[:space:]]*:[[:space:]]*"//' | sed 's/"$//')
    fi

    # 检查是否需要回退到终端交互
    local fallback_to_terminal="false"
    if command -v jq &> /dev/null; then
        fallback_to_terminal=$(echo "$response" | jq -r '.fallback_to_terminal // false')
    elif echo "$response" | grep -q '"fallback_to_terminal"[[:space:]]*:[[:space:]]*true'; then
        fallback_to_terminal="true"
    fi

    if [ "$fallback_to_terminal" = "true" ]; then
        # 服务器超时，回退到终端交互模式
        log "Server timeout, falling back to terminal interaction"
        run_fallback_mode
        return
    fi

    if [ "$success" = "true" ]; then
        # 只有用户明确决策时才输出决策（allow 或 deny）
        output_decision "$behavior" "$message" "$interrupt"
    else
        # 服务返回任何错误都回退到终端交互模式
        # 只有用户点击拒绝按钮时才会返回 success=true + behavior=deny
        log "Callback service returned error, falling back to terminal interaction"
        run_fallback_mode
        return
    fi
}

# =============================================================================
# 降级模式：仅发送通知，不等待响应
# =============================================================================
# 使用场景：
#   - 回调服务未运行（Socket 文件不存在）
#   - 回调服务返回超时
#   - 回调服务返回错误
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

    # 获取项目名称
    local project_name
    project_name=$(basename "$PROJECT_DIR")

    # 构建详情内容
    local detail_content template

    case "$TOOL_NAME" in
        "Bash")
            local command
            if command -v jq &> /dev/null; then
                command=$(echo "$INPUT" | jq -r '.tool_input.command // "N/A"')
            else
                command="N/A"
            fi
            if [ ${#command} -gt 500 ]; then
                command="${command:0:500}..."
            fi
            command=$(echo "$command" | sed 's/\\/\\\\/g; s/"/\\"/g')
            detail_content="**命令：**\n\`\`\`\n${command}\n\`\`\`"
            template="orange"
            ;;
        "Edit"|"Write")
            local file_path
            if command -v jq &> /dev/null; then
                file_path=$(echo "$INPUT" | jq -r '.tool_input.file_path // "N/A"')
            else
                file_path="N/A"
            fi
            detail_content="**文件：** \`${file_path}\`"
            template="yellow"
            ;;
        *)
            detail_content="**工具：** ${TOOL_NAME}"
            template="grey"
            ;;
    esac

    # 构建卡片（无交互按钮的降级版本）
    local card_content
    card_content=$(cat << EOF
{
  "msg_type": "interactive",
  "card": {
    "header": {
      "template": "${template}",
      "title": {"content": "Claude Code 权限请求", "tag": "plain_text"}
    },
    "elements": [
      {
        "tag": "div",
        "text": {"content": "**Claude Code 请求使用 ${TOOL_NAME} 工具**", "tag": "lark_md"}
      },
      {"tag": "hr"},
      {
        "tag": "div",
        "fields": [
          {"is_short": true, "text": {"content": "**项目：**\n${project_name}", "tag": "lark_md"}},
          {"is_short": true, "text": {"content": "**时间：**\n${TIMESTAMP}", "tag": "lark_md"}}
        ]
      },
      {
        "tag": "div",
        "text": {"content": "${detail_content}", "tag": "lark_md"}
      },
      {"tag": "hr"},
      {
        "tag": "note",
        "elements": [{"tag": "plain_text", "content": "回调服务未运行，请返回终端操作"}]
      }
    ]
  }
}
EOF
)

    # 发送通知
    curl -X POST "$WEBHOOK_URL" \
        -H "Content-Type: application/json" \
        -d "$card_content" \
        --max-time 5 \
        --silent \
        --show-error 2>/dev/null || true

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
SOCKET_CLIENT="${SCRIPT_DIR}/callback-server/socket-client.py"
HAS_SOCKET_CLIENT=false
HAS_SOCAT=false

if [ -f "$SOCKET_CLIENT" ] && command -v python3 &> /dev/null; then
    HAS_SOCKET_CLIENT=true
    log "Socket client available: python3 + socket-client.py"
fi

if command -v socat &> /dev/null; then
    HAS_SOCAT=true
    log "Socat available as fallback"
fi

# 两者都不可用时才降级
if [ "$HAS_SOCKET_CLIENT" = "false" ] && [ "$HAS_SOCAT" = "false" ]; then
    log "Warning: neither socket-client.py (python3) nor socat available, falling back to notification-only mode"
    run_fallback_mode
    # run_fallback_mode 内部会 exit，以下代码不会执行
fi

# 检查回调服务并选择模式
if check_callback_service; then
    run_interactive_mode
else
    log "Callback service not available"
    run_fallback_mode
    # run_fallback_mode 内部会 exit，以下代码不会执行
fi

# 交互模式成功输出决策后正常退出
exit $EXIT_HOOK_SUCCESS
