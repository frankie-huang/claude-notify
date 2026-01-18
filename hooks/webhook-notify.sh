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
SESSION_ID="${session_id:-unknown}"
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

# 构建飞书卡片消息
# 包含：标题、项目信息、时间戳、操作按钮
read -r -d '' CARD_CONTENT << EOF
{
  "msg_type": "interactive",
  "card": {
    "header": {
      "template": "blue",
      "title": {
        "content": "🔔 Claude Code 通知",
        "tag": "plain_text"
      }
    },
    "elements": [
      {
        "tag": "div",
        "text": {
          "content": "**${RANDOM_GREETING}**",
          "tag": "lark_md"
        }
      },
      {
        "tag": "hr"
      },
      {
        "tag": "div",
        "fields": [
          {
            "is_short": true,
            "text": {
              "content": "**项目名称：**\\n${PROJECT_NAME}",
              "tag": "lark_md"
            }
          },
          {
            "is_short": true,
            "text": {
              "content": "**通知时间：**\\n${TIMESTAMP}",
              "tag": "lark_md"
            }
          }
        ]
      },
      {
        "tag": "div",
        "text": {
          "content": "**状态：** Claude Code 正在等待确认，请及时处理",
          "tag": "lark_md"
        }
      },
      {
        "tag": "note",
        "elements": [
          {
            "tag": "plain_text",
            "content": "请尽快返回处理"
          }
        ]
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