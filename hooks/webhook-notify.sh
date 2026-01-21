#!/bin/bash

# =============================================================================
# webhook-notify.sh - Claude Code 通用飞书通知脚本
#
# 用法: 配置为 Notification 或 Stop hook，在 Claude Code 需要用户注意时发送通知
#
# 适用场景:
#   - 任务暂停需要用户输入
#   - 任务完成通知
#   - 错误或异常通知
#   - 任何需要用户返回终端的情况
#
# 环境变量:
#   FEISHU_WEBHOOK_URL - 飞书 Webhook URL (必需)
#   CLAUDE_PROJECT_DIR - 项目目录 (可选，默认为当前目录)
#   session_id          - 会话 ID (可选，用于标识不同会话，待实现功能)
# =============================================================================

# 飞书 Webhook URL
WEBHOOK_URL="${FEISHU_WEBHOOK_URL:-}"

# 检查 Webhook URL 是否配置
if [ -z "$WEBHOOK_URL" ]; then
    echo "Error: FEISHU_WEBHOOK_URL not set"
    exit 1
fi

# 获取当前时间
TIMESTAMP=$(date "+%Y-%m-%d %H:%M:%S")

# Session ID - 预留功能，用于标识不同会话（待实现）
# 目前 Claude Code hook 不传递 session_id，需要等待后续版本支持
SESSION_ID="${session_id:-}"

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
PROJECT_NAME=$(basename "$PROJECT_DIR")

# 随机选择通知语
GREETINGS=(
  "Claude Code 需要你的确认"
  "有任务等待处理"
  "Claude Code 已暂停，等待输入"
  "请回来查看 Claude Code 状态"
  "任务已暂停，需要人工介入"
)
RANDOM_GREETING=${GREETINGS[$RANDOM % ${#GREETINGS[@]}]}

# 构建飞书卡片消息（2.0 格式）
# 包含：标题、项目信息、时间戳、操作按钮
read -r -d '' CARD_CONTENT << EOF
{
  "msg_type": "interactive",
  "card": {
    "schema": "2.0",
    "config": {
      "update_multi": true,
      "style": {
        "text_size": {
          "normal_v2": {
            "default": "normal",
            "pc": "normal",
            "mobile": "heading"
          }
        }
      }
    },
    "header": {
      "template": "blue",
      "title": {
        "content": "🔔 Claude Code 通知",
        "tag": "plain_text"
      }
    },
    "body": {
      "direction": "vertical",
      "elements": [
      {
        "tag": "markdown",
        "content": "**${RANDOM_GREETING}**",
        "text_align": "left",
        "text_size": "normal_v2",
        "margin": "0px 0px 0px 0px"
      },
      {
        "tag": "hr",
        "margin": "0px 0px 0px 0px"
      },
      {
        "tag": "column_set",
        "columns": [
          {
            "tag": "column",
            "width": "weighted",
            "elements": [
              {
                "tag": "markdown",
                "content": "**项目：**\\n${PROJECT_NAME}",
                "text_align": "left",
                "text_size": "normal_v2"
              }
            ],
            "vertical_align": "top",
            "weight": 1
          },
          {
            "tag": "column",
            "width": "weighted",
            "elements": [
              {
                "tag": "markdown",
                "content": "**时间：**\\n${TIMESTAMP}",
                "text_align": "left",
                "text_size": "normal_v2"
              }
            ],
            "vertical_align": "top",
            "weight": 1
          }
        ]
      },
      {
        "tag": "markdown",
        "content": "**状态：** Claude Code 正在等待确认，请及时处理",
        "text_align": "left",
        "text_size": "normal_v2"
      },
      {
        "tag": "div",
        "text": {
          "tag": "plain_text",
          "content": "请尽快返回处理",
          "text_size": "notation",
          "text_align": "left",
          "text_color": "grey"
        }
      },
      {
        "tag": "action",
        "actions": [
          {
            "tag": "button",
            "text": {
              "content": "已收到",
              "tag": "plain_text"
            },
            "type": "primary"
          }
        ]
      }
    ]
    }
  }
}
EOF

# 发送 webhook 请求
# 注意：使用 --max-time 5 避免长时间阻塞
curl -X POST "$WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d "$CARD_CONTENT" \
  --max-time 5 \
  --silent \
  --show-error

# 返回 0 确保不会阻塞 Claude Code
exit 0