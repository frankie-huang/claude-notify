#!/bin/bash
# =============================================================================
# shell-lib/tool-config.sh - 工具配置统一管理
#
# 功能：从 config/tools.json 读取工具类型配置
#      消除与 Python 服务端的配置重复
#
# 函数:
#   tool_config_init()           - 初始化配置缓存
#   tool_get_color()             - 获取工具颜色
#   tool_get_field()             - 获取工具参数字段名
#   tool_get_detail_template()   - 获取详情模板
#   tool_get_rule_template()     - 获取规则模板
#   tool_format_detail()         - 格式化工具详情（完整版）
#   tool_format_rule()           - 格式化权限规则（完整版）
#
# 使用示例:
#   source lib/tool-config.sh
#   tool_config_init
#   color=$(tool_get_color "Bash")
#   detail=$(tool_format_detail "$tool_input_json" "Bash")
# =============================================================================

# 配置文件路径
TOOLS_CONFIG_FILE="${SCRIPT_DIR}/config/tools.json"

# 配置缓存
TOOLS_CONFIG_CACHE=""
TOOLS_CONFIG_LOADED=false

# =============================================================================
# 初始化配置缓存
# =============================================================================
# 功能：将 tools.json 加载到内存，避免重复读取文件
# 用法：tool_config_init
# =============================================================================
tool_config_init() {
    if [ "$TOOLS_CONFIG_LOADED" = "true" ]; then
        return 0
    fi

    if [ ! -f "$TOOLS_CONFIG_FILE" ]; then
        if type log_error &> /dev/null; then
            log_error "Tools config not found: $TOOLS_CONFIG_FILE"
        fi
        return 1
    fi

    TOOLS_CONFIG_CACHE=$(cat "$TOOLS_CONFIG_FILE")
    TOOLS_CONFIG_LOADED=true
    return 0
}

# =============================================================================
# 获取工具配置值
# =============================================================================
# 功能：从配置中获取指定工具的字段值
# 用法：_tool_config_get "tool_name" "field_path"
# 参数：
#   tool_name  - 工具名称（如 Bash, Edit）
#   field_path - JSON 字段路径（如 color, input_field, detail_template）
# 输出：字段值，如果不存在则输出空字符串
# =============================================================================
_tool_config_get() {
    local tool_name="$1"
    local field_path="$2"

    # 确保配置已加载
    tool_config_init || return 1

    local path="tools.${tool_name}.${field_path}"

    if command -v jq &> /dev/null; then
        # 使用 jq 解析（优先）
        echo "$TOOLS_CONFIG_CACHE" | jq -r ".$path // empty" 2>/dev/null
    elif command -v python3 &> /dev/null; then
        # 使用 python3 解析
        local field_jspath
        field_jspath=$(echo "$path" | sed 's/\./"]["/g' | sed 's/^/["/g' | sed 's/$/"]/g')
        echo "$TOOLS_CONFIG_CACHE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d${field_jspath} if d${field_jspath} is not None else '')" 2>/dev/null
    else
        # 降级：使用 grep/sed（仅支持简单字段）
        # 这里不实现复杂解析，直接返回空
        echo ""
    fi
}

# =============================================================================
# 获取工具颜色
# =============================================================================
# 功能：获取工具类型对应的飞书卡片颜色
# 用法：tool_get_color "tool_name"
# 输出：颜色名称（orange, yellow, blue, purple, grey）
# =============================================================================
tool_get_color() {
    local tool_name="$1"
    local color

    color=$(_tool_config_get "$tool_name" "color")

    if [ -z "$color" ]; then
        # 默认颜色
        color=$(_tool_config_get "_defaults.unknown_tool.color")
        echo "${color:-grey}"
    else
        echo "$color"
    fi
}

# =============================================================================
# 获取工具参数字段名
# =============================================================================
# 功能：获取工具类型的主要参数字段名
# 用法：tool_get_field "tool_name"
# 输出：字段名（command, file_path, pattern, url, query 等）
# =============================================================================
tool_get_field() {
    local tool_name="$1"
    local field

    field=$(_tool_config_get "$tool_name" "input_field")
    echo "${field:-}"
}

# =============================================================================
# 获取详情模板
# =============================================================================
# 功能：获取工具详情内容的模板
# 用法：tool_get_detail_template "tool_name"
# 输出：模板字符串（支持 {field} 占位符）
# =============================================================================
tool_get_detail_template() {
    local tool_name="$1"
    local template

    template=$(_tool_config_get "$tool_name" "detail_template")

    if [ -z "$template" ]; then
        # 默认模板
        template=$(_tool_config_get "_defaults.unknown_tool.detail_template")
    fi

    echo "$template"
}

# =============================================================================
# 获取规则模板
# =============================================================================
# 功能：获取权限规则的模板
# 用法：tool_get_rule_template "tool_name"
# 输出：模板字符串（支持 {field} 占位符）
# =============================================================================
tool_get_rule_template() {
    local tool_name="$1"
    local template

    template=$(_tool_config_get "$tool_name" "rule_template")

    if [ -z "$template" ]; then
        # 默认模板
        template=$(_tool_config_get "_defaults.unknown_tool.rule_template")
    fi

    echo "$template"
}

# =============================================================================
# 格式化工具详情
# =============================================================================
# 功能：根据工具类型格式化详情内容
# 用法：tool_format_detail "tool_input_json" "tool_name"
# 参数：
#   tool_input_json - 工具输入参数的 JSON 字符串
#   tool_name       - 工具名称
# 输出：格式化后的详情内容（Markdown 格式）
# 说明：
#   会自动读取配置中的模板，并替换占位符
#   如果配置了 limit_length，会截断长内容
# =============================================================================
tool_format_detail() {
    local tool_input_json="$1"
    local tool_name="$2"

    # 获取字段名和模板
    local field_name
    local template
    field_name=$(tool_get_field "$tool_name")
    template=$(tool_get_detail_template "$tool_name")

    # 提取字段值
    local field_value
    if [ -n "$field_name" ]; then
        field_value=$(json_get "$tool_input_json" "tool_input.${field_name}")
    fi

    field_value="${field_value:-}"

    # 检查是否需要截断
    local limit_length
    limit_length=$(_tool_config_get "$tool_name" "limit_length")

    if [ -n "$limit_length" ] && [ "$limit_length" -gt 0 ] 2>/dev/null && [ ${#field_value} -gt "$limit_length" ]; then
        local suffix
        suffix=$(_tool_config_get "$tool_name" "truncate_suffix")
        field_value="${field_value:0:$limit_length}${suffix}"
    fi

    # 转义特殊字符（用于 Bash 命令）
    if [ "$tool_name" = "Bash" ]; then
        field_value=$(echo "$field_value" | sed 's/\\/\\\\/g; s/"/\\"/g')
    fi

    # 替换模板占位符
    local result="$template"
    result="${result//\{${field_name}\}/${field_value}}"
    result="${result//\{tool_name\}/${tool_name}}"

    # 检查是否有 description 字段
    local description
    description=$(json_get "$tool_input_json" "tool_input.description")
    if [ -n "$description" ]; then
        result="${result}\\n**描述：** ${description}"
    fi

    echo "$result"
}

# =============================================================================
# 格式化权限规则
# =============================================================================
# 功能：根据工具类型生成权限规则字符串
# 用法：tool_format_rule "tool_input_json" "tool_name"
# 输出：规则字符串（如 Bash(npm install)）
# =============================================================================
tool_format_rule() {
    local tool_input_json="$1"
    local tool_name="$2"

    # 获取字段名和模板
    local field_name
    local template
    field_name=$(tool_get_field "$tool_name")
    template=$(tool_get_rule_template "$tool_name")

    # 提取字段值
    local field_value=""
    if [ -n "$field_name" ]; then
        field_value=$(json_get "$tool_input_json" "tool_input.${field_name}")
    fi

    field_value="${field_value:-}"

    # 替换模板占位符
    local result="$template"
    result="${result//\{${field_name}\}/${field_value}}"
    result="${result//\{tool_name\}/${tool_name}}"

    echo "$result"
}
