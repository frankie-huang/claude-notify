#!/bin/bash
# =============================================================================
# shell-lib/env.sh - 环境配置读取模块
#
# 提供从 .env 文件和环境变量读取配置的统一接口
#
# 优先级: .env 文件 > 环境变量 > 默认值
#
# 函数:
#   get_config KEY [DEFAULT]  - 获取配置值
#   env_reload                - 重新加载 .env 文件缓存
#
# 特性:
#   - 缓存 .env 文件内容，避免重复 IO
#   - 支持引号包裹的值 (单引号/双引号)
#   - 自动跳过注释行和空行
#
# 使用示例:
#   source shell-lib/env.sh
#   WEBHOOK_URL=$(get_config "FEISHU_WEBHOOK_URL" "")
#   PORT=$(get_config "CALLBACK_SERVER_PORT" "8080")
# =============================================================================

# =============================================================================
# 内部变量
# =============================================================================
_ENV_FILE_CACHE=""
_ENV_FILE_LOADED="false"

# =============================================================================
# 加载 .env 文件到缓存
# =============================================================================
# 功能：读取 .env 文件内容到内存缓存
# 说明：只在首次调用时读取，后续调用直接使用缓存
# =============================================================================
_load_env_cache() {
    # 已加载则跳过
    [ "$_ENV_FILE_LOADED" = "true" ] && return

    local env_file="${PROJECT_ROOT}/.env"
    if [ -f "$env_file" ]; then
        _ENV_FILE_CACHE=$(cat "$env_file")
    fi
    _ENV_FILE_LOADED="true"
}

# =============================================================================
# 从缓存中读取指定 key 的值
# =============================================================================
# 功能：解析 .env 缓存，提取指定 key 的值
# 参数：$1 - key 名称
# 输出：配置值（已去除引号）
# 返回：0 找到值，1 未找到
# =============================================================================
_read_from_cache() {
    local key="$1"

    [ -z "$_ENV_FILE_CACHE" ] && return 1

    local line value
    while IFS= read -r line; do
        # 跳过空行和注释
        [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue

        # 匹配 key=value 格式
        if [[ "$line" =~ ^${key}= ]]; then
            # 提取等号后的值
            value="${line#*=}"
            # 去除首尾引号 (单引号或双引号)
            value="${value#\"}"
            value="${value%\"}"
            value="${value#\'}"
            value="${value%\'}"
            # 去除首尾空白
            value="${value#"${value%%[![:space:]]*}"}"
            value="${value%"${value##*[![:space:]]}"}"
            printf '%s' "$value"
            return 0
        fi
    done <<< "$_ENV_FILE_CACHE"

    return 1
}

# =============================================================================
# 获取配置值
# =============================================================================
# 功能：按优先级获取配置值
# 优先级：.env 文件 > 环境变量 > 默认值
#
# 用法：get_config KEY [DEFAULT]
# 参数：
#   $1 - 配置项名称 (如 FEISHU_WEBHOOK_URL)
#   $2 - 默认值 (可选，默认为空字符串)
# 输出：配置值
#
# 示例：
#   WEBHOOK=$(get_config "FEISHU_WEBHOOK_URL" "")
#   PORT=$(get_config "CALLBACK_SERVER_PORT" "8080")
# =============================================================================
get_config() {
    local key="$1"
    local default="${2:-}"

    # 确保缓存已加载
    _load_env_cache

    # 1. 优先从 .env 文件读取
    local env_value
    if env_value=$(_read_from_cache "$key"); then
        printf '%s' "$env_value"
        return
    fi

    # 2. 其次从环境变量读取
    local shell_env="${!key}"
    if [ -n "$shell_env" ]; then
        printf '%s' "$shell_env"
        return
    fi

    # 3. 使用默认值
    printf '%s' "$default"
}

# =============================================================================
# 重新加载 .env 文件
# =============================================================================
# 功能：清除缓存并重新加载 .env 文件
# 用途：当 .env 文件内容变化后需要重新读取时调用
#
# 示例：
#   env_reload
#   NEW_VALUE=$(get_config "SOME_KEY")
# =============================================================================
env_reload() {
    _ENV_FILE_CACHE=""
    _ENV_FILE_LOADED="false"
    _load_env_cache
}
