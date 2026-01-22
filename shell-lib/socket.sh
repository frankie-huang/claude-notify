#!/bin/bash
# =============================================================================
# shell-lib/socket.sh - Socket 通信函数库
#
# 提供 Unix Socket 通信功能，用于与回调服务交互
# 通信协议详见: shared/protocol.md
#
# 函数:
#   check_socket_tools()     - 检测可用的 Socket 通信工具
#   socket_send_request()    - 通过 Socket 发送请求并等待响应
#   parse_socket_response()  - 解析 Socket 响应
#
# 全局变量:
#   SOCKET_CLIENT            - Socket 客户端路径
#   HAS_SOCKET_CLIENT        - 是否支持 Python 客户端（true/false）
#   HAS_SOCAT                - 是否支持 socat（true/false）
#   SOCKET_PATH              - Unix Socket 路径
#
# 使用示例:
#   source shell-lib/socket.sh
#   source shell-lib/json.sh
#   source shell-lib/log.sh
#   log_init
#   json_init
#   check_socket_tools
#   response=$(socket_send_request "$request_json" "$SOCKET_PATH")
#   parse_socket_response "$response"
# =============================================================================
# =============================================================================
# 检测可用的 Socket 通信工具
# =============================================================================
# 功能：检测系统中可用的 Socket 通信工具
# 用法：check_socket_tools
# 输出：设置全局变量 HAS_SOCKET_CLIENT, HAS_SOCAT
#
# 优先级：Python 客户端 > socat
#
# 示例：
#   check_socket_tools
#   if [ "$HAS_SOCKET_CLIENT" = "true" ]; then
#       echo "Using Python socket client"
#   fi
# =============================================================================
check_socket_tools() {
    # 默认值
    HAS_SOCKET_CLIENT=false
    HAS_SOCAT=false

    # 默认 Socket 客户端路径
    SOCKET_CLIENT="${PROJECT_ROOT}/server/socket-client.py"

    # 检测 Python 客户端（推荐）
    if [ -f "$SOCKET_CLIENT" ] && command -v python3 &> /dev/null; then
        HAS_SOCKET_CLIENT=true
    fi

    # 检测 socat（备选方案）
    if command -v socat &> /dev/null; then
        HAS_SOCAT=true
    fi

    export HAS_SOCKET_CLIENT HAS_SOCAT SOCKET_CLIENT
}

# =============================================================================
# 通过 Socket 发送请求并等待响应
# =============================================================================
# 功能：向 Unix Socket 发送请求并阻塞等待响应
# 用法：socket_send_request "request_json" "socket_path"
# 参数：
#   request_json  - 请求 JSON 字符串
#   socket_path   - Unix Socket 路径
# 输出：响应 JSON 字符串（如果失败则输出空字符串）
#
# 通信方式：
#   1. 优先使用 Python 客户端（更可靠，支持半关闭）
#   2. 回退到 socat（可能有连接保持问题）
#
# 示例：
#   request='{"request_id":"123","project_dir":"/path"}'
#   response=$(socket_send_request "$request" "/tmp/claude-permission.sock")
# =============================================================================
socket_send_request() {
    local request_json="$1"
    local socket_path="${2:-${SOCKET_PATH:-/tmp/claude-permission.sock}}"

    # 检查工具可用性
    if [ -z "$HAS_SOCKET_CLIENT" ]; then
        check_socket_tools
    fi

    local response=""

    # 优先使用 Python 客户端
    if [ "$HAS_SOCKET_CLIENT" = "true" ]; then
        # 只捕获 stdout（JSON 响应），stderr（日志）丢弃（已写入日志文件）
        response=$(echo "$request_json" | python3 "$SOCKET_CLIENT" "$socket_path" 2>/dev/null)
        local exit_code=$?

        if [ $exit_code -ne 0 ]; then
            if type log &> /dev/null; then
                log "Socket client failed with exit code: $exit_code"
            fi
            echo ""
            return 1
        fi
    # 回退到 socat
    elif [ "$HAS_SOCAT" = "true" ]; then
        if type log &> /dev/null; then
            log "Using socat for socket communication"
        fi
        response=$(echo "$request_json" | socat - "UNIX-CONNECT:${socket_path}" 2>/dev/null)
        local exit_code=$?

        if [ $exit_code -ne 0 ]; then
            if type log &> /dev/null; then
                log "Socat failed with exit code: $exit_code"
            fi
            echo ""
            return 1
        fi
    else
        if type log_error &> /dev/null; then
            log_error "No socket communication tool available"
        fi
        echo ""
        return 1
    fi

    echo "$response"
}

# =============================================================================
# 解析 Socket 响应
# =============================================================================
# 功能：解析回调服务返回的 JSON 响应
# 用法：parse_socket_response "response_json"
# 参数：
#   response_json - 响应 JSON 字符串
# 输出：设置全局变量：
#         RESPONSE_SUCCESS        - 请求是否成功（true/false）
#         RESPONSE_BEHAVIOR       - 决策行为（allow/deny）
#         RESPONSE_MESSAGE        - 决策消息
#         RESPONSE_INTERRUPT      - 是否中断（true/false）
#         RESPONSE_FALLBACK       - 是否回退到终端（true/false）
#
# 响应格式：
#   {
#     "success": true,
#     "decision": {
#       "behavior": "allow",
#       "message": "批准原因",
#       "interrupt": false
#     },
#     "fallback_to_terminal": false
#   }
#
# 示例：
#   parse_socket_response "$response"
#   echo "Success: $RESPONSE_SUCCESS"
#   echo "Behavior: $RESPONSE_BEHAVIOR"
# =============================================================================
parse_socket_response() {
    local response_json="$1"

    # 默认值
    RESPONSE_SUCCESS="false"
    RESPONSE_BEHAVIOR="deny"
    RESPONSE_MESSAGE=""
    RESPONSE_INTERRUPT="false"
    RESPONSE_FALLBACK="false"

    # 如果未初始化 JSON 解析器，先初始化
    if [ -z "$JSON_PARSER" ]; then
        if type json_init &> /dev/null; then
            json_init
        fi
    fi

    # 解析响应
    if [ "$JSON_HAS_JQ" = "true" ] || command -v jq &> /dev/null; then
        RESPONSE_SUCCESS=$(echo "$response_json" | jq -r '.success // false' 2>/dev/null)
        RESPONSE_BEHAVIOR=$(echo "$response_json" | jq -r '.decision.behavior // "deny"' 2>/dev/null)
        RESPONSE_MESSAGE=$(echo "$response_json" | jq -r '.decision.message // ""' 2>/dev/null)
        RESPONSE_INTERRUPT=$(echo "$response_json" | jq -r '.decision.interrupt // false' 2>/dev/null)
        RESPONSE_FALLBACK=$(echo "$response_json" | jq -r '.fallback_to_terminal // false' 2>/dev/null)
    elif [ "$JSON_HAS_PYTHON3" = "true" ] || command -v python3 &> /dev/null; then
        # Python 的 True/False 需要转换为小写 true/false
        RESPONSE_SUCCESS=$(echo "$response_json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(str(d.get('success',False)).lower())" 2>/dev/null || echo "false")
        RESPONSE_BEHAVIOR=$(echo "$response_json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('decision',{}).get('behavior','deny'))" 2>/dev/null || echo "deny")
        RESPONSE_MESSAGE=$(echo "$response_json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('decision',{}).get('message',''))" 2>/dev/null || echo "")
        RESPONSE_INTERRUPT=$(echo "$response_json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(str(d.get('decision',{}).get('interrupt',False)).lower())" 2>/dev/null || echo "false")
        RESPONSE_FALLBACK=$(echo "$response_json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(str(d.get('fallback_to_terminal',False)).lower())" 2>/dev/null || echo "false")
    else
        # 简单解析（grep）
        if echo "$response_json" | grep -q '"success"[[:space:]]*:[[:space:]]*true'; then
            RESPONSE_SUCCESS="true"
        fi

        if echo "$response_json" | grep -q '"behavior"[[:space:]]*:[[:space:]]*"allow"'; then
            RESPONSE_BEHAVIOR="allow"
        fi

        if echo "$response_json" | grep -q '"interrupt"[[:space:]]*:[[:space:]]*true'; then
            RESPONSE_INTERRUPT="true"
        fi

        if echo "$response_json" | grep -q '"fallback_to_terminal"[[:space:]]*:[[:space:]]*true'; then
            RESPONSE_FALLBACK="true"
        fi

        RESPONSE_MESSAGE=$(echo "$response_json" | grep -o '"message"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | \
            sed 's/"message"[[:space:]]*:[[:space:]]*"//' | sed 's/"$//')
    fi

    export RESPONSE_SUCCESS RESPONSE_BEHAVIOR RESPONSE_MESSAGE RESPONSE_INTERRUPT RESPONSE_FALLBACK
}

# =============================================================================
# 检查 Socket 服务是否可用
# =============================================================================
# 功能：检查 Unix Socket 服务是否真正运行（不只是检查文件存在）
# 用法：check_socket_service ["socket_path"]
# 参数：
#   socket_path - 可选，Socket 路径（默认为 /tmp/claude-permission.sock）
# 输出：0 表示可用，1 表示不可用
#
# 示例：
#   if check_socket_service; then
#       echo "Service is available"
#   fi
# =============================================================================
check_socket_service() {
    local socket_path="${1:-${SOCKET_PATH:-/tmp/claude-permission.sock}}"

    # 首先检查 socket 文件是否存在
    if [ ! -S "$socket_path" ]; then
        return 1
    fi

    # 尝试连接以验证服务是否真的在运行
    # 这样可以检测服务异常退出后残留的 socket 文件
    if command -v python3 &> /dev/null; then
        python3 -c "
import socket
import sys
sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
sock.settimeout(1)
try:
    sock.connect('${socket_path}')
    # 连接成功，立即关闭（这是一个测试连接）
    sock.close()
    sys.exit(0)
except Exception as e:
    # 连接失败，说明服务不可用
    sys.exit(1)
" 2>/dev/null
        return $?
    fi

    # 如果没有 Python，尝试使用 socat 或 nc
    if command -v socat &> /dev/null; then
        # 尝试连接，超时 1 秒
        echo "" | timeout 1 socat - "UNIX-CONNECT:${socket_path}" >/dev/null 2>&1
        local exit_code=$?
        # socat 连接成功返回 0，连接失败返回非 0
        # 141 是 SIGPIPE（连接后对端关闭），也是成功的表现
        if [ $exit_code -eq 0 ] || [ $exit_code -eq 141 ]; then
            return 0
        fi
        return 1
    fi

    # 没有可用工具，只能信任文件存在（可能误判）
    return 0
}
