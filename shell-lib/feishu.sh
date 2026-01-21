#!/bin/bash
# =============================================================================
# shell-lib/feishu.sh - 飞书卡片构建和发送函数库
# =============================================================================
#
# 功能说明:
#   提供飞书卡片消息的构建、渲染和发送功能
#   支持模板化渲染,提供子模板组合能力
#
# 主要函数:
#   render_template()         - 渲染模板文件(变量替换)
#   render_sub_template()     - 渲染子模板元素
#   render_card_template()    - 渲染卡片模板
#   build_permission_card()   - 构建权限请求卡片
#   build_permission_buttons()- 构建权限请求按钮
#   build_notification_card() - 构建通用通知卡片
#   send_feishu_card()        - 发送飞书卡片
#   send_feishu_text()        - 发送飞书文本消息(降级)
#
# 全局变量:
#   FEISHU_WEBHOOK_URL        - 飞书 Webhook URL
#   FEISHU_TEMPLATE_PATH      - 自定义模板目录路径(可选)
#
# 使用示例:
#   source shell-lib/feishu.sh
#   buttons=$(build_permission_buttons "http://localhost:8080" "req-123")
#   card=$(build_permission_card "Bash" "myproject" "2024-01-01 12:00:00" \
#       "npm install" "安装依赖" "orange" "$buttons")
#   send_feishu_card "$card"
#
# =============================================================================

# =============================================================================
# 常量定义
# =============================================================================

# 获取脚本所在目录的父目录(项目根目录)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# 默认模板目录
DEFAULT_TEMPLATE_DIR="${PROJECT_ROOT}/templates/feishu"

# =============================================================================
# 模板验证函数
# =============================================================================

# ----------------------------------------------------------------------------
# validate_template - 验证模板文件
# ----------------------------------------------------------------------------
# 功能: 验证模板文件是否存在并可读
#
# 参数:
#   $1 - 模板文件路径
#
# 返回:
#   0 - 验证成功
#   1 - 验证失败
#
# 注意:
#   模板文件包含占位符,无法直接用 JSON 验证器验证
#   渲染后会验证最终输出的 JSON 格式
# ----------------------------------------------------------------------------
validate_template() {
    local template_file="$1"

    [ -f "$template_file" ] && [ -r "$template_file" ]
}

# =============================================================================
# 模板渲染函数
# =============================================================================

# ----------------------------------------------------------------------------
# render_template - 渲染模板文件(核心函数)
# ----------------------------------------------------------------------------
# 功能: 加载模板文件并替换变量占位符
#
# 参数:
#   $1               - 模板文件路径
#   ${@:2}           - 变量键值对 (格式: "key=value")
#
# 输出:
#   渲染后的模板内容
#
# 返回:
#   0 - 渲染成功
#   1 - 渲染失败
#
# 示例:
#   render_template "card.json" "title=通知" "content=**Hello**"
#
# 注意:
#   - 占位符格式: {{variable_name}}
#   - JSON 片段类型变量不会被转义 (buttons_json, description_element, detail_elements)
# ----------------------------------------------------------------------------
render_template() {
    local template_file="$1"
    shift

    # 检查模板文件
    if [ ! -f "$template_file" ]; then
        if type log_error &> /dev/null; then
            log_error "Template file not found: $template_file"
        fi
        return 1
    fi

    # 读取模板内容
    local template_content
    template_content=$(cat "$template_file")

    # 替换所有变量占位符
    local var_assign
    for var_assign in "$@"; do
        local key="${var_assign%%=*}"
        local value="${var_assign#*=}"

        # JSON 片段类型变量不需要转义
        if [[ "$key" != "buttons_json" ]] && \
           [[ "$key" != "description_element" ]] && \
           [[ "$key" != "detail_elements" ]]; then
            # 转义特殊字符为 JSON 格式
            # 注意: JSON 解析器（jq/python3）会将转义序列解释为实际字符（如 \t → TAB, \n → LF）
            # 因此需要将这些实际字符重新转义回 JSON 格式
            if [[ "$key" == "command" ]]; then
                # command 变量: JSON 解析后需重新转义
                # 顺序: 1.反斜杠 2.双引号 3.制表符 4.换行符
                value=$(printf '%s' "$value" | \
                    sed 's/\\/\\\\/g' | \
                    sed 's/"/\\"/g' | \
                    sed $'s/\t/\\\\t/g' | \
                    sed 's/$/\\n/g' | tr -d '\n' | sed 's/\\n$//')
            else
                # 其他变量: 同样处理所有 JSON 特殊字符
                value=$(printf '%s' "$value" | \
                    sed 's/\\/\\\\/g' | \
                    sed 's/"/\\"/g' | \
                    sed $'s/\t/\\\\t/g' | \
                    sed 's/$/\\n/g' | tr -d '\n' | sed 's/\\n$//')
            fi
        fi

        # 转义 awk gsub 的特殊字符
        # 注意: ENVIRON 传递的字符串中只有 & 是特殊字符(代表匹配内容)
        # \ 不会被 gsub 特殊处理，所以只需转义 &
        value=$(printf '%s' "$value" | sed 's/&/\\&/g')

        # 使用 awk 进行替换
        # 通过 ENVIRON 传递变量避免 shell 展开问题
        local awk_key="TEMPLATE_KEY_$(echo "$key" | tr -c 'a-zA-Z0-9_' '_')"
        local awk_val="TEMPLATE_VAL_$(echo "$key" | tr -c 'a-zA-Z0-9_' '_')"
        export "$awk_key"="{{$key}}"
        export "$awk_val"="$value"

        template_content=$(awk "
        {
            gsub(ENVIRON[\"$awk_key\"], ENVIRON[\"$awk_val\"])
            print
        }
        " <<< "$template_content")

        # 清理环境变量
        unset "$awk_key" "$awk_val"
    done

    printf '%s\n' "$template_content"
}

# ----------------------------------------------------------------------------
# render_sub_template - 渲染子模板元素
# ----------------------------------------------------------------------------
# 功能: 渲染子模板并返回 JSON 元素,用于嵌入主模板
#
# 参数:
#   $1               - 子模板类型
#                      可选值: command-bash, command-file, description
#   ${@:2}           - 变量键值对 (格式: "key=value")
#
# 输出:
#   渲染后的 JSON 元素字符串(已去除首尾空白)
#
# 返回:
#   0 - 渲染成功
#   1 - 渲染失败
#
# 示例:
#   cmd=$(render_sub_template "command-bash" "command=npm install")
#   desc=$(render_sub_template "description" "description=安装依赖")
#
# 支持的子模板类型:
#   - command-bash:   Bash 命令详情 (参数: command)
#   - command-file:   文件操作详情 (参数: file_path)
#   - description:    操作描述 (参数: description)
# ----------------------------------------------------------------------------
render_sub_template() {
    local sub_type="$1"
    shift

    # 确定模板目录
    local template_dir="${FEISHU_TEMPLATE_PATH:-$DEFAULT_TEMPLATE_DIR}"

    # 确定模板文件
    local template_file
    case "$sub_type" in
        "command-bash")
            template_file="${template_dir}/command-detail-bash.json"
            ;;
        "command-file")
            template_file="${template_dir}/command-detail-file.json"
            ;;
        "description")
            template_file="${template_dir}/description-element.json"
            ;;
        *)
            if type log_error &> /dev/null; then
                log_error "Unknown sub template type: $sub_type"
            fi
            return 1
            ;;
    esac

    # 验证模板文件
    if ! validate_template "$template_file"; then
        if type log_error &> /dev/null; then
            log_error "Invalid sub template file: $template_file"
        fi
        return 1
    fi

    # 渲染模板
    local rendered
    rendered=$(render_template "$template_file" "$@")

    if [ -z "$rendered" ]; then
        if type log_error &> /dev/null; then
            log_error "Sub template rendering failed: $template_file"
        fi
        return 1
    fi

    # 去除外层空白并输出
    echo "$rendered" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//'
}

# ----------------------------------------------------------------------------
# render_card_template - 渲染卡片模板(包装函数)
# ----------------------------------------------------------------------------
# 功能: 根据卡片类型选择模板并渲染
#
# 参数:
#   $1               - 卡片类型
#                      可选值: permission, permission-static, notification, buttons
#   ${@:2}           - 变量键值对 (格式: "key=value")
#
# 输出:
#   渲染后的卡片 JSON 字符串
#
# 返回:
#   0 - 渲染成功
#   1 - 渲染失败
#
# 示例:
#   card=$(render_card_template "permission" \
#       "tool_name=Bash" "project_name=test")
#
# 支持的卡片类型:
#   - permission:         权限请求卡片(带按钮)
#   - permission-static:  权限请求卡片(无按钮)
#   - notification:       通用通知卡片
#   - buttons:            交互按钮数组
# ----------------------------------------------------------------------------
render_card_template() {
    local card_type="$1"
    shift

    # 确定模板目录
    local template_dir="${FEISHU_TEMPLATE_PATH:-$DEFAULT_TEMPLATE_DIR}"

    # 确定模板文件
    local template_file
    case "$card_type" in
        "permission")
            template_file="${template_dir}/permission-card.json"
            ;;
        "permission-static")
            template_file="${template_dir}/permission-card-static.json"
            ;;
        "notification")
            template_file="${template_dir}/notification-card.json"
            ;;
        "buttons")
            template_file="${template_dir}/buttons.json"
            ;;
        *)
            if type log_error &> /dev/null; then
                log_error "Unknown card type: $card_type"
            fi
            return 1
            ;;
    esac

    # 验证模板文件
    if ! validate_template "$template_file"; then
        if type log_error &> /dev/null; then
            log_error "Invalid template file: $template_file"
        fi
        return 1
    fi

    # 渲染模板
    local rendered
    rendered=$(render_template "$template_file" "$@")

    if [ -z "$rendered" ]; then
        if type log_error &> /dev/null; then
            log_error "Template rendering failed: $template_file"
        fi
        return 1
    fi

    # 验证渲染后的 JSON (如果系统有 jq 命令)
    if command -v jq &> /dev/null; then
        if ! echo "$rendered" | jq empty >/dev/null 2>&1; then
            if type log_error &> /dev/null; then
                log_error "Rendered JSON is invalid"
            fi
            return 1
        fi
    fi

    echo "$rendered"
}

# =============================================================================
# 卡片构建函数
# =============================================================================

# ----------------------------------------------------------------------------
# build_permission_card - 构建权限请求卡片
# ----------------------------------------------------------------------------
# 功能: 构建飞书权限请求卡片,支持不同的工具类型
#
# 参数:
#   $1 - tool_name       工具名称 (Bash, Edit, Write, Read 等)
#   $2 - project_name    项目名称
#   $3 - timestamp       时间戳 (格式: 2024-01-01 12:00:00)
#   $4 - command_arg     命令参数
#                          Bash: 命令内容
#                          Edit/Write/Read: 文件路径
#   $5 - description     描述内容 (可选, Markdown 格式)
#   $6 - template_color  卡片颜色
#                          可选: orange, yellow, blue, purple, grey
#   $7 - buttons_json    按钮 JSON 数组 (可选, 不提供则使用静态模板)
#
# 输出:
#   飞书卡片 JSON 字符串
#
# 返回:
#   0 - 构建成功
#   1 - 构建失败
#
# 示例:
#   # Bash 工具 (带按钮)
#   buttons=$(build_permission_buttons "http://localhost:8080" "req-123")
#   card=$(build_permission_card "Bash" "myproject" "2024-01-01 12:00:00" \
#       "npm install" "安装依赖" "orange" "$buttons")
#
#   # Edit 工具 (带按钮)
#   card=$(build_permission_card "Edit" "myproject" "2024-01-01 12:00:00" \
#       "/path/to/file.txt" "修复bug" "orange" "$buttons")
#
#   # 不带按钮 (静态卡片)
#   card=$(build_permission_card "Bash" "myproject" "2024-01-01 12:00:00" \
#       "npm install" "安装依赖" "orange" "")
#
# 工具类型映射:
#   - Bash:    使用 command-bash 子模板
#   - Edit:    使用 command-file 子模板
#   - Write:   使用 command-file 子模板
#   - Read:    使用 command-file 子模板
#   - 其他:    默认使用 command-bash 子模板
# ----------------------------------------------------------------------------
build_permission_card() {
    local tool_name="$1"
    local project_name="$2"
    local timestamp="$3"
    local command_arg="$4"
    local description="$5"
    local template_color="$6"
    local buttons_json="${7:-}"

    # 选择卡片类型
    local card_type
    if [ -n "$buttons_json" ]; then
        card_type="permission"
    else
        card_type="permission-static"
    fi

    # 根据工具类型渲染命令详情元素
    local command_element=""
    case "$tool_name" in
        "Bash")
            command_element=$(render_sub_template "command-bash" "command=$command_arg")
            ;;
        "Edit"|"Write"|"Read")
            command_element=$(render_sub_template "command-file" "file_path=$command_arg")
            ;;
        *)
            # 未知工具类型,默认使用 Bash 模板
            command_element=$(render_sub_template "command-bash" "command=$command_arg")
            ;;
    esac

    # 渲染描述元素(如果有描述)
    local description_element=""
    if [ -n "$description" ]; then
        description_element=$(render_sub_template "description" "description=$description")
    fi

    # 构建详情元素字符串(用于嵌入到主模板中)
    # 注意：这里必须以逗号结尾，因为模板中 detail_elements 后面还有其他元素
    local detail_elements="      ${command_element},"

    # 添加描述元素
    if [ -n "$description_element" ]; then
        detail_elements="${detail_elements}
      ${description_element},"
    fi

    # 渲染主模板
    local card
    if [ -n "$buttons_json" ]; then
        card=$(render_card_template "$card_type" \
            "template_color=$template_color" \
            "tool_name=$tool_name" \
            "project_name=$project_name" \
            "timestamp=$timestamp" \
            "detail_elements=$detail_elements" \
            "buttons_json=$buttons_json")
    else
        card=$(render_card_template "$card_type" \
            "template_color=$template_color" \
            "tool_name=$tool_name" \
            "project_name=$project_name" \
            "timestamp=$timestamp" \
            "detail_elements=$detail_elements")
    fi

    if [ $? -ne 0 ]; then
        return 1
    fi

    echo "$card"
}

# ----------------------------------------------------------------------------
# build_permission_buttons - 构建权限请求按钮
# ----------------------------------------------------------------------------
# 功能: 构建飞书权限请求卡片的交互按钮
#
# 参数:
#   $1 - callback_url  回调服务器 URL (如: http://localhost:8080)
#   $2 - request_id    请求 ID
#
# 输出:
#   按钮 JSON 数组字符串
#
# 返回:
#   0 - 构建成功
#   1 - 构建失败
#
# 示例:
#   buttons=$(build_permission_buttons "http://localhost:8080" "req-123")
#   card=$(build_permission_card "Bash" "myproject" "2024-01-01 12:00:00" \
#       "npm install" "安装依赖" "orange" "$buttons")
#
# 注意:
#   URL 末尾的斜杠会被自动移除
# ----------------------------------------------------------------------------
build_permission_buttons() {
    local callback_url="$1"
    local request_id="$2"

    # 移除 URL 末尾的斜杠
    callback_url=$(echo "$callback_url" | sed 's:/*$::')

    # 使用模板渲染按钮
    render_card_template "buttons" \
        "callback_url=$callback_url" \
        "request_id=$request_id"
}

# ----------------------------------------------------------------------------
# build_notification_card - 构建通用通知卡片
# ----------------------------------------------------------------------------
# 功能: 构建简单的飞书通知卡片(用于非权限请求的通知)
#
# 参数:
#   $1 - title         卡片标题
#   $2 - content       通知内容 (Markdown 格式)
#   $3 - project_name  项目名称
#   $4 - timestamp     时间戳
#
# 输出:
#   飞书卡片 JSON 字符串
#
# 返回:
#   0 - 构建成功
#   1 - 构建失败
#
# 示例:
#   card=$(build_notification_card "Claude Code 通知" \
#       "**任务暂停，需要人工介入**" "myproject" "2024-01-01 12:00:00")
# ----------------------------------------------------------------------------
build_notification_card() {
    local title="$1"
    local content="$2"
    local project_name="$3"
    local timestamp="$4"

    render_card_template "notification" \
        "title=$title" \
        "content=$content" \
        "project_name=$project_name" \
        "timestamp=$timestamp"
}

# =============================================================================
# 消息发送函数
# =============================================================================

# ----------------------------------------------------------------------------
# send_feishu_card - 发送飞书卡片
# ----------------------------------------------------------------------------
# 功能: 向飞书 Webhook URL 发送卡片消息
#
# 参数:
#   $1 - card_json    飞书卡片 JSON 字符串
#   $2 - webhook_url  Webhook URL (可选, 默认使用全局变量 FEISHU_WEBHOOK_URL)
#
# 返回:
#   0 - 发送成功
#   1 - 发送失败
#
# 示例:
#   # 直接指定 URL
#   send_feishu_card "$card" "https://open.feishu.cn/..."
#
#   # 使用全局变量
#   export FEISHU_WEBHOOK_URL="https://open.feishu.cn/..."
#   send_feishu_card "$card"
#
# 降级处理:
#   如果卡片发送失败,会自动发送降级文本消息通知用户
# ----------------------------------------------------------------------------
send_feishu_card() {
    local card_json="$1"
    local webhook_url="${2:-${FEISHU_WEBHOOK_URL:-}}"

    # 检查 Webhook URL
    if [ -z "$webhook_url" ]; then
        if type log_error &> /dev/null; then
            log_error "FEISHU_WEBHOOK_URL not set"
        fi
        return 1
    fi

    # 打印飞书卡片 JSON 到日志
    if type log &> /dev/null; then
        log "Sending Feishu card JSON: ${card_json}"
    fi

    # 发送 HTTP POST 请求
    local response
    response=$(curl -X POST "$webhook_url" \
        -H "Content-Type: application/json" \
        -d "$card_json" \
        --max-time 5 \
        --silent \
        --show-error 2>&1)

    local curl_exit=$?

    # 检查发送结果
    if [ $curl_exit -ne 0 ] || echo "$response" | grep -q '"code":[^0]'; then
        if type log &> /dev/null; then
            log "Failed to send Feishu card: curl exit=$curl_exit, response=$response"
        fi

        # 发送降级文本消息通知用户
        send_feishu_text "⚠️ Claude Code 权限请求卡片发送失败，请返回终端操作" "$webhook_url"

        return 1
    fi

    if type log &> /dev/null; then
        log "Feishu card sent successfully"
    fi

    return 0
}

# ----------------------------------------------------------------------------
# send_feishu_text - 发送飞书文本消息(降级方案)
# ----------------------------------------------------------------------------
# 功能: 向飞书 Webhook URL 发送简单文本消息
#
# 参数:
#   $1 - message_text  文本消息内容
#   $2 - webhook_url  Webhook URL (可选, 默认使用全局变量 FEISHU_WEBHOOK_URL)
#
# 返回:
#   0 - 发送成功
#   1 - 发送失败
#
# 示例:
#   send_feishu_text "操作失败，请返回终端" "https://open.feishu.cn/..."
#
# 注意:
#   此函数静默失败,不会记录错误日志 (避免递归)
# ----------------------------------------------------------------------------
send_feishu_text() {
    local message_text="$1"
    local webhook_url="${2:-${FEISHU_WEBHOOK_URL:-}}"

    # 检查 Webhook URL
    if [ -z "$webhook_url" ]; then
        return 1
    fi

    # 构建文本消息 JSON
    local text_json
    text_json=$(cat << EOF
{
  "msg_type": "text",
  "content": {
    "text": "${message_text}"
  }
}
EOF
)

    # 记录日志
    if type log &> /dev/null; then
        log "Sending fallback text message: ${message_text}"
    fi

    # 发送 HTTP POST 请求 (静默失败)
    if curl -X POST "$webhook_url" \
        -H "Content-Type: application/json" \
        -d "$text_json" \
        --max-time 3 \
        --silent \
        --show-error >/dev/null 2>&1; then
        if type log &> /dev/null; then
            log "Fallback text message sent"
        fi
        return 0
    else
        if type log &> /dev/null; then
            log "Fallback text message failed"
        fi
        return 1
    fi
}
