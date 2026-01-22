#!/bin/bash
# =============================================================================
# shell-lib/log.sh - 日志函数库
#
# 提供统一的日志记录功能
# 配置来源: shared/logging.json
#
# 函数:
#   log_init()          - 初始化日志系统（设置日志文件路径）
#   log()               - 记录通用日志
#   log_input()         - 记录输入数据（JSON 格式化）
#   log_error()         - 记录错误日志
#
# 环境变量:
#   LOG_FILE            - 日志文件路径（可选，自动生成）
#   LOG_DIR             - 日志目录（可选，默认为 ./log）
#
# 使用示例:
#   source shell-lib/log.sh
#   log_init                    # 使用默认日志文件
#   log "Starting process"      # 记录日志
#   log_input "$JSON_DATA"      # 记录输入数据
# =============================================================================

# 日志文件路径（如果未设置则自动生成）
: "${LOG_FILE:=}"

# 日志配置（从 shared/logging.json 读取或使用默认值）
_LOG_DATE_FORMAT="%Y%m%d"
_LOG_DATETIME_FORMAT="%Y-%m-%d %H:%M:%S"
_LOG_FILE_PATTERN="hook_{date}.log"

# =============================================================================
# 加载日志配置
# =============================================================================
_load_log_config() {
    local config_file="${PROJECT_ROOT}/shared/logging.json"

    if [ -f "$config_file" ]; then
        # 尝试使用 jq 读取配置
        if command -v jq &> /dev/null; then
            _LOG_DATE_FORMAT=$(jq -r '.date_format // "%Y%m%d"' "$config_file" 2>/dev/null || echo "%Y%m%d")
            _LOG_DATETIME_FORMAT=$(jq -r '.datetime_format // "%Y-%m-%d %H:%M:%S"' "$config_file" 2>/dev/null || echo "%Y-%m-%d %H:%M:%S")
            _LOG_FILE_PATTERN=$(jq -r '.file_patterns.hook // "hook_{date}.log"' "$config_file" 2>/dev/null || echo "hook_{date}.log")
        # 尝试使用 python3 读取配置
        elif command -v python3 &> /dev/null; then
            _LOG_DATE_FORMAT=$(python3 -c "import json; print(json.load(open('$config_file')).get('date_format', '%Y%m%d'))" 2>/dev/null || echo "%Y%m%d")
            _LOG_DATETIME_FORMAT=$(python3 -c "import json; print(json.load(open('$config_file')).get('datetime_format', '%Y-%m-%d %H:%M:%S'))" 2>/dev/null || echo "%Y-%m-%d %H:%M:%S")
            _LOG_FILE_PATTERN=$(python3 -c "import json; print(json.load(open('$config_file')).get('file_patterns', {}).get('hook', 'hook_{date}.log'))" 2>/dev/null || echo "hook_{date}.log")
        fi
    fi
}

# =============================================================================
# 初始化日志系统
# =============================================================================
# 功能：设置日志文件路径，创建日志目录
# 用法：log_init [log_file_path]
# 参数：
#   log_file_path - 可选，日志文件路径
#                  如果不提供，则使用 shared/logging.json 中的配置
# =============================================================================
log_init() {
    local log_file="${1:-}"

    # 加载配置
    _load_log_config

    if [ -n "$log_file" ]; then
        LOG_FILE="$log_file"
    else
        # 默认日志文件路径
        local log_dir="${PROJECT_ROOT}/log"
        mkdir -p "$log_dir"

        local log_date
        log_date=$(date "+${_LOG_DATE_FORMAT}")
        local log_filename
        log_filename=$(echo "$_LOG_FILE_PATTERN" | sed "s/{date}/${log_date}/g")
        LOG_FILE="${log_dir}/${log_filename}"
    fi

    # 确保日志目录存在
    local log_dir
    log_dir="$(dirname "$LOG_FILE")"
    mkdir -p "$log_dir"

    # 创建日志文件（如果不存在）
    touch "$LOG_FILE" 2>/dev/null || {
        # 如果无法创建日志文件，输出到 stderr
        echo "Warning: Cannot create log file: $LOG_FILE" >&2
        LOG_FILE="/dev/null"
    }

    export LOG_FILE
}

# =============================================================================
# 通用日志函数
# =============================================================================
# 功能：记录带时间戳的日志消息
# 用法：log "message"
# 参数：
#   $1 - 日志消息
# 输出：写入日志文件，格式为 [YYYY-MM-DD HH:MM:SS] message
# =============================================================================
log() {
    # 如果日志文件未初始化，先初始化
    if [ -z "$LOG_FILE" ] || [ ! -f "$LOG_FILE" ]; then
        log_init
    fi

    echo "[$(date "+${_LOG_DATETIME_FORMAT}")] $1" >> "$LOG_FILE"
}

# =============================================================================
# 记录输入数据
# =============================================================================
# 功能：记录原始输入数据（JSON），自动格式化
# 用法：log_input [json_string]
# 参数：
#   json_string - 要记录的 JSON 字符串（可选，如果省略则使用全局 INPUT）
# 输出：写入日志文件，包含时间戳和格式化的 JSON
# =============================================================================
log_input() {
    local json_data="${1:-$INPUT}"

    # 如果日志文件未初始化，先初始化
    if [ -z "$LOG_FILE" ] || [ ! -f "$LOG_FILE" ]; then
        log_init
    fi

    {
        echo "=========================================="
        echo "时间: $(date "+${_LOG_DATETIME_FORMAT}")"
        echo "=========================================="
        echo ""
        echo "=== 原始 JSON 数据 ==="
        # 优先使用 jq 格式化，否则原样输出
        echo "$json_data" | if command -v jq &> /dev/null; then jq .; else cat; fi
        echo ""
    } >> "$LOG_FILE"
}

# =============================================================================
# 错误日志函数
# =============================================================================
# 功能：记录错误日志（带 ERROR 前缀）
# 用法：log_error "error message"
# 参数：
#   $1 - 错误消息
# 输出：写入日志文件，格式为 [YYYY-MM-DD HH:MM:SS] ERROR: message
# =============================================================================
log_error() {
    # 如果日志文件未初始化，先初始化
    if [ -z "$LOG_FILE" ] || [ ! -f "$LOG_FILE" ]; then
        log_init
    fi

    echo "[$(date "+${_LOG_DATETIME_FORMAT}")] ERROR: $1" >> "$LOG_FILE"
}

# =============================================================================
# 调试日志函数
# =============================================================================
# 功能：记录调试日志（带 DEBUG 前缀）
# 用法：log_debug "debug message"
# 参数：
#   $1 - 调试消息
# 输出：写入日志文件，格式为 [YYYY-MM-DD HH:MM:SS] DEBUG: message
# 注意：仅在设置了 DEBUG=1 时输出
# =============================================================================
log_debug() {
    if [ "${DEBUG:-0}" != "1" ]; then
        return
    fi

    # 如果日志文件未初始化，先初始化
    if [ -z "$LOG_FILE" ] || [ ! -f "$LOG_FILE" ]; then
        log_init
    fi

    echo "[$(date "+${_LOG_DATETIME_FORMAT}")] DEBUG: $1" >> "$LOG_FILE"
}

# =============================================================================
# 记录命令日志
# =============================================================================
# 功能：将权限请求的 command 保存到日志文件
# 用法：log_command "command_content" "request_id" "tool_name" "session_id"
# 参数：
#   $1 - command 内容
#   $2 - 请求 ID（可选）
#   $3 - 工具名称（可选）
#   $4 - 会话 ID（可选，用于文件名）
# 输出：追加写入 log/command/ 目录下按日期和会话 ID 命名的文件
# 文件名格式：command_{date}_{session_id}.log
# =============================================================================
log_command() {
    local command_content="$1"
    local request_id="${2:-unknown}"
    local tool_name="${3:-unknown}"
    local session_id="${4:-unknown}"

    local command_log_dir="${PROJECT_ROOT}/log/command"

    # 创建目录
    mkdir -p "$command_log_dir"

    # 生成文件名：command_YYYYMMDD_sessionid.log（按日期和会话区分）
    local date_part
    date_part=$(date "+%Y%m%d")
    local log_filename="command_${date_part}_${session_id}.log"
    local log_file="${command_log_dir}/${log_filename}"

    # 追加写入文件
    {
        echo "=========================================="
        echo "时间: $(date "+${_LOG_DATETIME_FORMAT}")"
        echo "请求 ID: ${request_id}"
        echo "工具: ${tool_name}"
        echo "------------------------------------------"
        echo "$command_content"
        echo ""
    } >> "$log_file"

    log "Command logged to: ${log_filename}"
}
