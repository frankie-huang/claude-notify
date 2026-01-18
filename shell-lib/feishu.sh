#!/bin/bash
# =============================================================================
# shell-lib/feishu.sh - 飞书卡片构建函数库
#
# 提供飞书卡片构建和发送功能
#
# 函数:
#   build_permission_card()  - 构建权限请求卡片
#   send_feishu_card()       - 发送飞书卡片
#
# 全局变量:
#   FEISHU_WEBHOOK_URL       - 飞书 Webhook URL
#
# 使用示例:
#   source lib/feishu.sh
#   card=$(build_permission_card "Bash" "myproject" "2024-01-01 12:00:00" "**命令：**\nnpm install" "orange" "")
#   send_feishu_card "$card"
# =============================================================================

# =============================================================================
# 构建权限请求卡片
# =============================================================================
# 功能：构建飞书交互式卡片（用于权限请求通知）
# 用法：build_permission_card "tool_name" "project_name" "timestamp" "detail_content" "template_color" ["buttons_json"]
# 参数：
#   tool_name      - 工具名称（如 Bash, Edit, Write）
#   project_name   - 项目名称
#   timestamp      - 时间戳（如 2024-01-01 12:00:00）
#   detail_content - 详情内容（Markdown 格式）
#   template_color - 卡片模板颜色（orange, yellow, blue, purple, grey）
#   buttons_json   - 可选，按钮 JSON 数组（如果不提供则不添加按钮）
# 输出：飞书卡片 JSON 字符串
#
# 示例（带按钮）：
#   buttons='[{"tag":"button","text":{"content":"批准","tag":"plain_text"},"type":"primary","multi_url":{"url":"http://xxx/allow"}}]'
#   card=$(build_permission_card "Bash" "myproject" "2024-01-01 12:00:00" "**命令：**\nnpm install" "orange" "$buttons")
#
# 示例（不带按钮）：
#   card=$(build_permission_card "Bash" "myproject" "2024-01-01 12:00:00" "**命令：**\nnpm install" "orange" "")
# =============================================================================
build_permission_card() {
    local tool_name="$1"
    local project_name="$2"
    local timestamp="$3"
    local detail_content="$4"
    local template_color="$5"
    local buttons_json="${6:-}"

    # 开始构建卡片 JSON（不关闭 elements 数组）
    local card="{
  \"msg_type\": \"interactive\",
  \"card\": {
    \"header\": {
      \"template\": \"${template_color}\",
      \"title\": {\"content\": \"Claude Code 权限请求\", \"tag\": \"plain_text\"}
    },
    \"elements\": [
      {
        \"tag\": \"div\",
        \"text\": {\"content\": \"**Claude Code 请求使用 ${tool_name} 工具**\", \"tag\": \"lark_md\"}
      },
      {\"tag\": \"hr\"},
      {
        \"tag\": \"div\",
        \"fields\": [
          {\"is_short\": true, \"text\": {\"content\": \"**项目：**\\n${project_name}\", \"tag\": \"lark_md\"}},
          {\"is_short\": true, \"text\": {\"content\": \"**时间：**\\n${timestamp}\", \"tag\": \"lark_md\"}}
        ]
      },
      {
        \"tag\": \"div\",
        \"text\": {\"content\": \"${detail_content}\", \"tag\": \"lark_md\"}
      }"

    # 如果有按钮，添加按钮元素
    if [ -n "$buttons_json" ]; then
        card="${card},
      {\"tag\": \"hr\"},
      {
        \"tag\": \"action\",
        \"actions\": ${buttons_json}
      }"
    fi

    # 添加提示信息
    local note_content
    if [ -n "$buttons_json" ]; then
        note_content="请尽快操作以避免 Claude 超时等待"
    else
        note_content="回调服务未运行，请返回终端操作"
    fi

    # 添加 note 并关闭 elements 数组和 card 对象
    card="${card},
      {
        \"tag\": \"note\",
        \"elements\": [{\"tag\": \"plain_text\", \"content\": \"${note_content}\"}]
      }
    ]
  }
}"

    echo "$card"
}

# =============================================================================
# 构建交互按钮 JSON
# =============================================================================
# 功能：构建飞书卡片的交互按钮（用于权限请求）
# 用法：build_permission_buttons "callback_url" "request_id"
# 参数：
#   callback_url - 回调服务器 URL（如 http://localhost:8080）
#   request_id   - 请求 ID
# 输出：按钮 JSON 数组字符串
#
# 示例：
#   buttons=$(build_permission_buttons "http://localhost:8080" "123-456")
#   card=$(build_permission_card "Bash" "myproject" "2024-01-01 12:00:00" "**命令：**\nnpm install" "orange" "$buttons")
# =============================================================================
build_permission_buttons() {
    local callback_url="$1"
    local request_id="$2"

    # 移除 URL 末尾的斜杠
    callback_url=$(echo "$callback_url" | sed 's:/*$::')

    # 构建按钮 JSON
    cat << EOF
[
  {
    "tag": "button",
    "text": {"content": "批准运行", "tag": "plain_text"},
    "type": "primary",
    "multi_url": {"url": "${callback_url}/allow?id=${request_id}"}
  },
  {
    "tag": "button",
    "text": {"content": "始终允许", "tag": "plain_text"},
    "type": "default",
    "multi_url": {"url": "${callback_url}/always?id=${request_id}"}
  },
  {
    "tag": "button",
    "text": {"content": "拒绝运行", "tag": "plain_text"},
    "type": "danger",
    "multi_url": {"url": "${callback_url}/deny?id=${request_id}"}
  },
  {
    "tag": "button",
    "text": {"content": "拒绝并中断", "tag": "plain_text"},
    "type": "danger",
    "multi_url": {"url": "${callback_url}/interrupt?id=${request_id}"}
  }
]
EOF
}

# =============================================================================
# 发送飞书卡片
# =============================================================================
# 功能：向飞书 Webhook URL 发送卡片消息
# 用法：send_feishu_card "card_json" ["webhook_url"]
# 参数：
#   card_json    - 飞书卡片 JSON 字符串
#   webhook_url  - 可选，Webhook URL（如果不提供则使用全局变量 FEISHU_WEBHOOK_URL）
# 输出：返回 0 表示成功，1 表示失败
#       失败时日志会记录到 LOG_FILE（需要先 source lib/log.sh）
#
# 示例：
#   send_feishu_card "$card" "https://open.feishu.cn/..."
#   # 或使用全局变量
#   export FEISHU_WEBHOOK_URL="https://open.feishu.cn/..."
#   send_feishu_card "$card"
# =============================================================================
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

    # 发送请求
    local response
    response=$(curl -X POST "$webhook_url" \
        -H "Content-Type: application/json" \
        -d "$card_json" \
        --max-time 5 \
        --silent \
        --show-error 2>&1)

    local curl_exit=$?

    # 检查结果
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

# =============================================================================
# 发送飞书文本消息（降级方案）
# =============================================================================
# 功能：向飞书 Webhook URL 发送简单文本消息
# 用法：send_feishu_text "message_text" ["webhook_url"]
# 参数：
#   message_text - 文本消息内容
#   webhook_url  - 可选，Webhook URL（如果不提供则使用全局变量 FEISHU_WEBHOOK_URL）
# 输出：返回 0 表示成功，1 表示失败
#
# 示例：
#   send_feishu_text "操作失败，请返回终端" "https://open.feishu.cn/..."
# =============================================================================
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

    # 发送请求（静默失败，避免递归）
    if type log &> /dev/null; then
        log "Sending fallback text message: ${message_text}"
    fi

    curl -X POST "$webhook_url" \
        -H "Content-Type: application/json" \
        -d "$text_json" \
        --max-time 3 \
        --silent \
        --show-error >/dev/null 2>&1

    if type log &> /dev/null; then
        log "Fallback text message sent"
    fi

    return 0
}

# =============================================================================
# 构建通用通知卡片
# =============================================================================
# 功能：构建简单的飞书通知卡片（用于非权限请求的通知）
# 用法：build_notification_card "title" "content" "project_name" "timestamp"
# 参数：
#   title        - 卡片标题
#   content      - 通知内容（Markdown 格式）
#   project_name - 项目名称
#   timestamp    - 时间戳
# 输出：飞书卡片 JSON 字符串
#
# 示例：
#   card=$(build_notification_card "Claude Code 通知" "**任务暂停，需要人工介入**" "myproject" "2024-01-01 12:00:00")
# =============================================================================
build_notification_card() {
    local title="$1"
    local content="$2"
    local project_name="$3"
    local timestamp="$4"

    cat << EOF
{
  "msg_type": "interactive",
  "card": {
    "header": {
      "template": "blue",
      "title": {"content": "${title}", "tag": "plain_text"}
    },
    "elements": [
      {
        "tag": "div",
        "text": {"content": "${content}", "tag": "lark_md"}
      },
      {"tag": "hr"},
      {
        "tag": "div",
        "fields": [
          {"is_short": true, "text": {"content": "**项目：**\\n${project_name}", "tag": "lark_md"}},
          {"is_short": true, "text": {"content": "**时间：**\\n${timestamp}", "tag": "lark_md"}}
        ]
      },
      {
        "tag": "note",
        "elements": [{"tag": "plain_text", "content": "请尽快返回处理"}]
      }
    ]
  }
}
EOF
}
