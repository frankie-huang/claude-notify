#!/bin/bash
# =============================================================================
# shell-lib/json.sh - JSON 解析函数库
#
# 提供统一的 JSON 解析功能，支持多种解析工具（jq > python3 > grep/sed）
#
# 函数:
#   json_init()          - 初始化 JSON 解析器（检测可用工具）
#   json_get()           - 获取 JSON 字段值
#   json_get_object()    - 获取 JSON 对象
#   json_build_object()  - 构建 JSON 对象（无 jq 时使用）
#
# 全局变量:
#   JSON_PARSER          - 当前使用的解析器（jq/python3/native）
#   JSON_HAS_JQ          - 是否支持 jq（true/false）
#   JSON_HAS_PYTHON3     - 是否支持 python3（true/false）
#
# 使用示例:
#   source lib/json.sh
#   json_init
#   tool_name=$(json_get "$json" "tool_name")
#   command=$(json_get "$json" "tool_input.command")
# =============================================================================

# JSON 解析器类型（初始化时设置）
: "${JSON_PARSER:=}"
: "${JSON_HAS_JQ:=false}"
: "${JSON_HAS_PYTHON3:=false}"

# =============================================================================
# 初始化 JSON 解析器
# =============================================================================
# 功能：检测可用的 JSON 解析工具并设置默认解析器
# 用法：json_init
# 输出：设置全局变量 JSON_PARSER, JSON_HAS_JQ, JSON_HAS_PYTHON3
#
# 优先级：jq > python3 > grep/sed
# =============================================================================
json_init() {
    # 检测 jq（最可靠）
    if command -v jq &> /dev/null; then
        JSON_PARSER="jq"
        JSON_HAS_JQ=true
        export JSON_PARSER JSON_HAS_JQ
        return 0
    fi

    # 检测 python3（比 grep/sed 更可靠）
    if command -v python3 &> /dev/null; then
        JSON_PARSER="python3"
        JSON_HAS_PYTHON3=true
        export JSON_PARSER JSON_HAS_PYTHON3
        return 0
    fi

    # 降级到 grep/sed（有已知限制）
    JSON_PARSER="native"
    export JSON_PARSER
    return 0
}

# =============================================================================
# 获取 JSON 字段值
# =============================================================================
# 功能：从 JSON 字符串中提取指定字段的值
# 用法：json_get "json_string" "field_path"
# 参数：
#   json_string  - JSON 字符串
#   field_path   - 字段路径（支持嵌套，如 "tool_input.command"）
# 输出：字段值（字符串），如果字段不存在则输出空字符串
#
# 示例：
#   tool_name=$(json_get "$json" "tool_name")
#   command=$(json_get "$json" "tool_input.command")
# =============================================================================
json_get() {
    local json="$1"
    local field_path="$2"

    # 如果未初始化，先初始化
    if [ -z "$JSON_PARSER" ]; then
        json_init
    fi

    # 空值处理
    if [ -z "$json" ] || [ -z "$field_path" ]; then
        return 1
    fi

    case "$JSON_PARSER" in
        jq)
            # jq 解析（最可靠）
            echo "$json" | jq -r ".$field_path // empty" 2>/dev/null
            ;;
        python3)
            # Python3 解析
            local field_jspath
            # 将 .field.nested 转换为 Python 的 ['field']['nested'] 格式
            field_jspath=$(echo "$field_path" | sed 's/\./"]["/g' | sed 's/^/["/g' | sed 's/$/"]/g')
            echo "$json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d${field_jspath} if d${field_jspath} is not None else '')" 2>/dev/null
            ;;
        native)
            # grep/sed 解析（有已知限制）
            # 简单实现：仅支持单层字段
            if [[ "$field_path" == *"."* ]]; then
                # 不支持嵌套字段
                echo ""
                return 1
            fi

            # 提取字段值
            echo "$json" | grep -o "\"${field_path}\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" | head -1 | \
                sed "s/\"${field_path}\"[[:space:]]*:[[:space:]]*\""'/"/' | sed 's/"$//'
            ;;
        *)
            echo ""
            return 1
            ;;
    esac
}

# =============================================================================
# 获取 JSON 对象
# =============================================================================
# 功能：从 JSON 字符串中提取指定的对象部分
# 用法：json_get_object "json_string" "field_path"
# 参数：
#   json_string  - JSON 字符串
#   field_path   - 对象路径（如 "tool_input"）
# 输出：JSON 对象字符串
#
# 示例：
#   tool_input=$(json_get_object "$json" "tool_input")
# =============================================================================
json_get_object() {
    local json="$1"
    local field_path="$2"

    # 如果未初始化，先初始化
    if [ -z "$JSON_PARSER" ]; then
        json_init
    fi

    # 空值处理
    if [ -z "$json" ] || [ -z "$field_path" ]; then
        echo "{}"
        return 1
    fi

    case "$JSON_PARSER" in
        jq)
            # jq 解析
            echo "$json" | jq -c ".$field_path // {}" 2>/dev/null
            ;;
        python3)
            # Python3 解析
            local field_jspath
            field_jspath=$(echo "$field_path" | sed 's/\./"]["/g' | sed 's/^/["/g' | sed 's/$/"]/g')
            echo "$json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d${field_jspath} if d${field_jspath} is not None else {}))" 2>/dev/null
            ;;
        native)
            # grep/sed 解析（简化版，仅支持单层对象）
            if [[ "$field_path" == *"."* ]]; then
                echo "{}"
                return 1
            fi

            # 提取对象内容（简化版，不完美）
            local value
            value=$(echo "$json" | grep -o "\"${field_path}\"[[:space:]]*:[[:space:]]*{[^}]*}" | head -1 | \
                sed "s/\"${field_path}\"[[:space:]]*:[[:space:]]*//")
            if [ -n "$value" ]; then
                echo "$value"
            else
                echo "{}"
            fi
            ;;
        *)
            echo "{}"
            return 1
            ;;
    esac
}

# =============================================================================
# 构建 JSON 对象（无 jq 时使用）
# =============================================================================
# 功能：构建简单的 JSON 对象（用于没有 jq 的环境）
# 用法：json_build_object "key1" "value1" "key2" "value2" ...
# 参数：
#   key1, value1, key2, value2, ... - 键值对（必须成对出现）
# 输出：JSON 对象字符串
#
# 示例：
#   json_obj=$(json_build_object "request_id" "123" "project_dir" "/path")
#   # 输出：{"request_id":"123","project_dir":"/path"}
#
# 注意：这是简化实现，不支持嵌套对象和特殊字符转义
# =============================================================================
json_build_object() {
    local result="{"
    local first=true

    while [ $# -ge 2 ]; do
        local key="$1"
        local value="$2"
        shift 2

        if [ "$first" = true ]; then
            first=false
        else
            result="${result},"
        fi

        result="${result}\"${key}\":\"${value}\""
    done

    result="${result}}"
    echo "$result"
}

# =============================================================================
# 检查字段是否存在
# =============================================================================
# 功能：检查 JSON 中是否存在指定字段
# 用法：json_has_field "json_string" "field_path"
# 参数：
#   json_string  - JSON 字符串
#   field_path   - 字段路径
# 输出：0 表示存在，1 表示不存在
# =============================================================================
json_has_field() {
    local json="$1"
    local field_path="$2"

    # 如果未初始化，先初始化
    if [ -z "$JSON_PARSER" ]; then
        json_init
    fi

    # 空值处理
    if [ -z "$json" ] || [ -z "$field_path" ]; then
        return 1
    fi

    case "$JSON_PARSER" in
        jq)
            # jq 解析
            local value
            value=$(echo "$json" | jq -r ".$field_path // empty" 2>/dev/null)
            [ -n "$value" ]
            ;;
        python3)
            # Python3 解析
            local field_jspath
            field_jspath=$(echo "$field_path" | sed 's/\./"]["/g' | sed 's/^/["/g' | sed 's/$/"]/g')
            local value
            value=$(echo "$json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d${field_jspath} if d${field_jspath} is not None else '')" 2>/dev/null)
            [ -n "$value" ]
            ;;
        native)
            # grep/sed 解析
            echo "$json" | grep -q "\"${field_path}\"[[:space:]]*:"
            ;;
        *)
            return 1
            ;;
    esac
}
