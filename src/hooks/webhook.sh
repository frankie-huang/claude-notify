#!/bin/bash
# =============================================================================
# src/hooks/webhook.sh - Claude Code 通用通知处理脚本
#
# 此脚本由 hook-router.sh 通过 source 调用，不直接执行
#
# 前置条件（由 hook-router.sh 完成）:
#   - $INPUT 变量包含从 stdin 读取的 JSON 数据
#   - 核心库、JSON 解析器、日志系统已初始化
#   - $PROJECT_ROOT, $SRC_DIR, $LIB_DIR 等路径变量已设置
#
# 适用场景:
#   - 任务暂停需要用户输入
#   - 任务完成通知
#   - 错误或异常通知
#   - 任何需要用户返回终端的情况
# =============================================================================

# =============================================================================
# 引入函数库
# =============================================================================
source "$LIB_DIR/feishu.sh"

# =============================================================================
# 配置
# =============================================================================
WEBHOOK_URL=$(get_config "FEISHU_WEBHOOK_URL" "")

# 检查 Webhook URL 是否配置
if [ -z "$WEBHOOK_URL" ]; then
    log_error "FEISHU_WEBHOOK_URL not set"
    exit 0  # 返回 0 确保不会阻塞 Claude Code
fi

# 获取当前时间
TIMESTAMP=$(date "+%Y-%m-%d %H:%M:%S")

# 从 INPUT 解析信息
SESSION_ID=$(json_get "$INPUT" "session_id")
SESSION_ID="${SESSION_ID:-}"

# 项目目录
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(json_get "$INPUT" "cwd")}"
PROJECT_DIR="${PROJECT_DIR:-$(pwd)}"
PROJECT_NAME=$(basename "$PROJECT_DIR")

log "Webhook notification: project=$PROJECT_NAME, session=$SESSION_ID"

# =============================================================================
# 构建通知卡片
# =============================================================================

# 随机选择通知语
GREETINGS=(
  "Claude Code 需要你的确认"
  "有任务等待处理"
  "Claude Code 已暂停，等待输入"
  "请回来查看 Claude Code 状态"
  "任务已暂停，需要人工介入"
)
RANDOM_GREETING=${GREETINGS[$RANDOM % ${#GREETINGS[@]}]}

# 构建通知内容
NOTIFY_CONTENT="**${RANDOM_GREETING}**

**状态：** Claude Code 正在等待确认，请及时处理"

# 使用 feishu.sh 中的函数构建并发送卡片
CARD=$(build_notification_card "🔔 Claude Code 通知" "$NOTIFY_CONTENT" "$PROJECT_NAME" "$TIMESTAMP")

if [ $? -ne 0 ]; then
    log_error "Failed to build notification card"
    exit 0
fi

log "Sending webhook notification to Feishu"
send_feishu_card "$CARD" "{\"webhook_url\":\"$WEBHOOK_URL\"}"

log "Webhook notification sent"

# 返回 0 确保不会阻塞 Claude Code
exit 0
