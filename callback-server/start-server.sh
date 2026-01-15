#!/bin/bash

# =============================================================================
# start-server.sh - 启动 Claude Code 权限回调服务
#
# 用法:
#   ./start-server.sh [start|stop|restart]
#   不带参数默认为 start
#
# 功能:
#   启动 HTTP + Socket 双协议服务器，处理飞书按钮回调请求
#
# 环境变量:
#   FEISHU_WEBHOOK_URL     - 飞书 Webhook URL (可选，仅用于日志)
#   CALLBACK_SERVER_URL    - 回调服务外部访问地址 (默认: http://localhost:8080)
#   CALLBACK_SERVER_PORT   - HTTP 服务端口 (默认: 8080)
#   PERMISSION_SOCKET_PATH - Unix Socket 路径 (默认: /tmp/claude-permission.sock)
#   REQUEST_TIMEOUT        - 请求超时秒数 (默认: 300，0 表示禁用)
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 检查 Python 3
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 is required but not installed."
    exit 1
fi

# 检查必需的环境变量
if [ -z "$FEISHU_WEBHOOK_URL" ]; then
    echo "Warning: FEISHU_WEBHOOK_URL is not set. Notifications will be skipped."
fi

# 启动服务
echo "Starting Claude Code Permission Callback Server..."
exec python3 "${SCRIPT_DIR}/server.py"
