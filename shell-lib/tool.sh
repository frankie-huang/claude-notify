#!/bin/bash
# =============================================================================
# shell-lib/tool.sh - 工具详情格式化函数库
#
# 提供工具类型配置和详情提取功能
#
# 函数:
#   get_tool_color()        - 获取工具类型对应的飞书卡片颜色
#   extract_tool_detail()   - 从 tool_input 中提取并格式化工具详情
#   get_tool_value()        - 获取工具的主要参数值
#   get_tool_rule()         - 生成权限规则字符串
#
# 配置:
#   优先使用 config/tools.json，如果不存在则使用内置配置
#
# 使用示例:
#   source shell-lib/tool.sh
#   source shell-lib/json.sh
#   json_init
#   color=$(get_tool_color "Bash")
#   detail=$(extract_tool_detail "$INPUT" "Bash")
# =============================================================================

# =============================================================================
# 配置管理：优先使用外部配置，否则使用内置配置
# =============================================================================

# 尝试加载统一配置管理
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USE_EXTERNAL_CONFIG=false

if [ -f "${SCRIPT_DIR}/shell-lib/tool-config.sh" ] && [ -f "${SCRIPT_DIR}/config/tools.json" ]; then
    source "${SCRIPT_DIR}/shell-lib/tool-config.sh"
    if tool_config_init 2>/dev/null; then
        USE_EXTERNAL_CONFIG=true
    fi
fi

# 如果外部配置不可用，使用内置配置作为降级
if [ "$USE_EXTERNAL_CONFIG" = "false" ]; then
    # 工具类型 -> 卡片颜色映射
    declare -A TOOL_COLORS=(
        ["Bash"]="orange"
        ["Edit"]="yellow"
        ["Write"]="yellow"
        ["Read"]="blue"
        ["Glob"]="blue"
        ["Grep"]="blue"
        ["WebSearch"]="purple"
        ["WebFetch"]="purple"
        ["mcp__4_5v_mcp__analyze_image"]="purple"
        ["mcp__web_reader__webReader"]="purple"
    )

    # 工具类型 -> 主要参数字段名映射
    declare -A TOOL_FIELDS=(
        ["Bash"]="command"
        ["Edit"]="file_path"
        ["Write"]="file_path"
        ["Read"]="file_path"
        ["Glob"]="pattern"
        ["Grep"]="pattern"
        ["WebSearch"]="query"
        ["WebFetch"]="url"
    )
fi

# 全局变量用于存储提取的详情
EXTRACTED_DETAIL=""
EXTRACTED_COLOR=""

# =============================================================================
# 获取工具类型对应的卡片颜色
# =============================================================================
# 功能：根据工具类型返回对应的飞书卡片模板颜色
# 用法：get_tool_color "tool_name"
# 输出：颜色名称（orange, yellow, blue, purple, grey）
# =============================================================================
get_tool_color() {
    local tool_name="$1"

    if [ "$USE_EXTERNAL_CONFIG" = "true" ]; then
        tool_get_color "$tool_name"
    else
        # 使用内置配置
        if [ -n "${TOOL_COLORS[$tool_name]}" ]; then
            echo "${TOOL_COLORS[$tool_name]}"
        else
            echo "grey"
        fi
    fi
}

# =============================================================================
# 提取并格式化工具详情
# =============================================================================
# 功能：从 PermissionRequest 的 tool_input 中提取工具详情并格式化为飞书 Markdown
# 用法：extract_tool_detail "json_input" "tool_name"
# 输出：设置全局变量 EXTRACTED_DETAIL（格式化后的详情内容）
#       设置全局变量 EXTRACTED_COLOR（卡片颜色）
# =============================================================================
extract_tool_detail() {
    local json_input="$1"
    local tool_name="$2"

    # 获取颜色
    EXTRACTED_COLOR=$(get_tool_color "$tool_name")

    # 获取字段名
    local field_name=""
    if [ "$USE_EXTERNAL_CONFIG" = "true" ]; then
        field_name=$(tool_get_field "$tool_name")
    else
        field_name="${TOOL_FIELDS[$tool_name]:-}"
    fi

    # 使用统一配置或内置逻辑
    if [ "$USE_EXTERNAL_CONFIG" = "true" ] && [ -n "$field_name" ]; then
        # 使用外部配置
        EXTRACTED_DETAIL=$(tool_format_detail "$json_input" "$tool_name")
    else
        # 使用内置逻辑（向后兼容）
        local detail=""
        case "$tool_name" in
            "Bash")
                local command
                command=$(json_get "$json_input" "tool_input.command")
                command="${command:-N/A}"
                if [ ${#command} -gt 500 ]; then
                    command="${command:0:500}..."
                fi
                # 更完整的转义：换行、反斜杠、双引号、反引号、美元符号
                command=$(echo "$command" | sed 's/\\/\\\\/g; s/"/\\"/g; s/`/\\`/g; s/\$/\\$/g' | tr '\n' ' ')
                detail="**命令：**\\n\`\`\`\\n${command}\\n\`\`\`"
                ;;
            "Edit"|"Write")
                local file_path
                file_path=$(json_get "$json_input" "tool_input.file_path")
                file_path="${file_path:-N/A}"
                detail="**文件：** \`${file_path}\`"
                ;;
            "Read")
                local file_path
                file_path=$(json_get "$json_input" "tool_input.file_path")
                file_path="${file_path:-N/A}"
                detail="**文件：** \`${file_path}\`"
                ;;
            *)
                detail="**工具：** ${tool_name}"
                ;;
        esac

        # 添加描述
        local description
        description=$(json_get "$json_input" "tool_input.description")
        if [ -n "$description" ]; then
            detail="${detail}\\n**描述：** ${description}"
        fi

        EXTRACTED_DETAIL="$detail"
    fi
}

# =============================================================================
# 获取工具的主要参数值
# =============================================================================
# 功能：获取工具的主要参数（如 Bash 的 command，Edit 的 file_path）
# 用法：get_tool_value "json_input" "tool_name"
# 输出：工具的主要参数值
# =============================================================================
get_tool_value() {
    local json_input="$1"
    local tool_name="$2"
    local field_name=""

    if [ "$USE_EXTERNAL_CONFIG" = "true" ]; then
        field_name=$(tool_get_field "$tool_name")
    else
        field_name="${TOOL_FIELDS[$tool_name]:-}"
    fi

    if [ -n "$field_name" ]; then
        json_get "$json_input" "tool_input.${field_name}"
    else
        echo ""
    fi
}

# =============================================================================
# 获取权限规则格式
# =============================================================================
# 功能：根据工具类型生成权限规则字符串
# 用法：get_tool_rule "tool_name" "json_input"
# 输出：权限规则字符串（如 Bash(npm install)）
# =============================================================================
get_tool_rule() {
    local tool_name="$1"
    local json_input="$2"

    if [ "$USE_EXTERNAL_CONFIG" = "true" ]; then
        tool_format_rule "$json_input" "$tool_name"
    else
        # 内置逻辑
        case "$tool_name" in
            "Bash")
                local command
                command=$(json_get "$json_input" "tool_input.command")
                if [ -n "$command" ]; then
                    echo "Bash(${command})"
                else
                    echo "Bash(*)"
                fi
                ;;
            "Edit"|"Write"|"Read")
                local file_path
                file_path=$(json_get "$json_input" "tool_input.file_path")
                if [ -n "$file_path" ]; then
                    echo "${tool_name}(${file_path})"
                else
                    echo "${tool_name}(*)"
                fi
                ;;
            *)
                echo "${tool_name}(*)"
                ;;
        esac
    fi
}
