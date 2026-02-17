#!/bin/bash
# =============================================================================
# install.sh - Claude Code 权限通知安装脚本
#
# 功能：
#   1. 检测环境依赖（python3, curl 等）
#   2. 配置 Claude Code hook
#   3. 生成环境变量配置模板
#
# 用法：
#   ./install.sh              # 交互式安装
#   ./install.sh --check      # 仅检测环境
#   ./install.sh --uninstall  # 卸载 hook 配置
#   ./install.sh --help       # 显示帮助
# =============================================================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m' # No Color

# 脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOK_PATH="${SCRIPT_DIR}/src/hook-router.sh"
SETTINGS_FILE="${HOME}/.claude/settings.json"

# =============================================================================
# 辅助函数
# =============================================================================

print_header() {
    echo -e "${BLUE}"
    echo "╔═══════════════════════════════════════════════════════════════╗"
    echo "║       Claude Code 权限通知 - 安装脚本                         ║"
    echo "╚═══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# 打印分段标题
print_section() {
    echo ""
    echo -e "${CYAN}━━━ ${BOLD}$1${NC}${CYAN} ━━━${NC}"
    echo ""
}

# 打印高亮文本（用于重要路径、命令等）
print_highlight() {
    echo -e "${BOLD}${YELLOW}$1${NC}"
}

# 打印次要信息（灰色）
print_dim() {
    echo -e "${DIM}$1${NC}"
}

# =============================================================================
# 检测依赖
# =============================================================================

check_dependencies() {
    print_section "检测环境依赖"

    local missing=()
    local optional_missing=()

    # 必需依赖
    if command -v python3 &>/dev/null; then
        print_success "python3: $(python3 --version 2>&1)"
    else
        print_error "python3: 未安装"
        missing+=("python3")
    fi

    if command -v curl &>/dev/null; then
        print_success "curl: $(curl --version | head -1)"
    else
        print_error "curl: 未安装"
        missing+=("curl")
    fi

    if command -v bash &>/dev/null; then
        print_success "bash: $(bash --version | head -1)"
    else
        print_error "bash: 未安装"
        missing+=("bash")
    fi

    # 可选依赖
    if command -v jq &>/dev/null; then
        print_success "jq: $(jq --version) (可选，用于更好的 JSON 处理)"
    else
        print_warning "jq: 未安装 (可选，将使用 Python 作为降级方案)"
        optional_missing+=("jq")
    fi

    if command -v socat &>/dev/null; then
        print_success "socat: 已安装 (可选，Socket 通信备选方案)"
    else
        print_warning "socat: 未安装 (可选，将使用 Python socket_client)"
        optional_missing+=("socat")
    fi

    echo ""

    if [ ${#missing[@]} -gt 0 ]; then
        print_error "缺少必需依赖: ${missing[*]}"
        echo ""
        echo "请安装缺少的依赖后重试："
        echo "  Ubuntu/Debian: sudo apt install ${missing[*]}"
        echo "  CentOS/RHEL:   sudo yum install ${missing[*]}"
        echo "  macOS:         brew install ${missing[*]}"
        return 1
    fi

    print_success "所有必需依赖已满足"

    if [ ${#optional_missing[@]} -gt 0 ]; then
        print_info "可选依赖 (${optional_missing[*]}) 未安装，但不影响基本功能"
    fi

    return 0
}

# =============================================================================
# 配置 Hook
# =============================================================================

configure_hook() {
    print_section "配置 Claude Code Hook"

    # 检查 hook 脚本是否存在
    if [ ! -f "$HOOK_PATH" ]; then
        print_error "Hook 脚本不存在: $HOOK_PATH"
        return 1
    fi

    # 确保脚本可执行
    chmod +x "$HOOK_PATH"

    # 创建 settings 目录
    mkdir -p "$(dirname "$SETTINGS_FILE")"

    # 构建 hook 配置 JSON
    # PermissionRequest 的 timeout 需大于服务端 PERMISSION_REQUEST_TIMEOUT（默认 600 秒），这里设置为 660 秒
    local hook_config
    hook_config=$(cat << EOF
{
  "hooks": {
    "PermissionRequest": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "${HOOK_PATH}",
            "timeout": 660
          }
        ]
      }
    ],
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "${HOOK_PATH}"
          }
        ]
      }
    ]
  }
}
EOF
)

    # 检查是否已有配置文件
    if [ -f "$SETTINGS_FILE" ]; then
        print_warning "已存在配置文件: $SETTINGS_FILE"
        echo ""
        echo "将合并 hooks 配置，保留现有配置。"
        echo ""
        read -p "是否继续? [y/N] " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "已取消配置"
            return 0
        fi

        # 使用 Python 合并配置（保留其他 hooks 和已有的 PermissionRequest）
        python3 << PYTHON_SCRIPT
import json
import sys

# ANSI 颜色代码
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
DIM = '\033[2m'
NC = '\033[0m'

settings_file = "${SETTINGS_FILE}"
hook_path = "${HOOK_PATH}"

try:
    with open(settings_file, 'r') as f:
        config = json.load(f)
except:
    config = {}

# 确保 hooks 字段存在
if 'hooks' not in config:
    config['hooks'] = {}

# 定义需要配置的事件类型及其特殊配置
# PermissionRequest 需要设置 timeout，需大于服务端 PERMISSION_REQUEST_TIMEOUT（默认 600 秒）
event_configs = {
    'PermissionRequest': {'timeout': 660},  # 660 秒
    'Stop': {}
}

for event, extra_config in event_configs.items():
    if event in config['hooks']:
        # 已存在此事件 hook，检查是否已配置我们的脚本
        existing_hooks = config['hooks'][event]
        already_configured = False

        for hook_config in existing_hooks:
            if 'hooks' in hook_config:
                for hook in hook_config['hooks']:
                    if hook.get('type') == 'command' and hook.get('command') == hook_path:
                        already_configured = True
                        break
                if already_configured:
                    break

        if already_configured:
            print(f"{GREEN}✓{NC} {event} hook 已配置，跳过更新")
        else:
            print(f"{YELLOW}⚠{NC} {event} hook 已存在其他配置，保留原配置：")
            print(f"{DIM}{json.dumps(existing_hooks, indent=2, ensure_ascii=False)}{NC}")
    else:
        # 事件 hook 不存在，添加我们的配置
        hook_entry = {
            'type': 'command',
            'command': hook_path
        }
        hook_entry.update(extra_config)

        config['hooks'][event] = [
            {
                'matcher': '',
                'hooks': [hook_entry]
            }
        ]
        print(f"{GREEN}✓{NC} {event} 配置已添加")

with open(settings_file, 'w') as f:
    json.dump(config, f, indent=2)
PYTHON_SCRIPT

    else
        # 直接写入新配置
        echo "$hook_config" > "$SETTINGS_FILE"
    fi

    echo ""
    print_success "Hook 配置完成"
    echo ""
    echo "  配置文件: $(print_highlight "$SETTINGS_FILE")"
    echo "  Hook 脚本: $(print_highlight "$HOOK_PATH")"
    echo "  触发事件: PermissionRequest, Stop"
}

# =============================================================================
# 生成环境变量模板
# =============================================================================

generate_env_template() {
    local env_file="${SCRIPT_DIR}/.env.example"

    print_section "生成环境变量模板"

    # 检查文件是否已存在
    if [ -f "$env_file" ]; then
        print_info "环境变量模板已存在: $env_file"
        echo ""
        echo "如需重新生成，请先删除现有文件："
        echo "  rm $env_file"
        return 0
    fi

    cat > "$env_file" << 'EOF'
# =============================================================================
# Claude Code 权限通知 - 环境变量配置
# =============================================================================
# 复制此文件为 .env 并填入实际值
# 脚本会自动从 .env 文件读取配置，无需手动 source
#
# 配置优先级: .env 文件 > 环境变量 > 默认值
# =============================================================================
#
# 配置速查表
# ┌──────────────────────────────┬──────────┬──────────┬──────────┬────────────┐
# │ 配置项                       │ Webhook  │ OpenAPI  │ OpenAPI  │ 默认值     │
# │                              │          │ 单机     │ 分离     │            │
# ├──────────────────────────────┼──────────┼──────────┼──────────┼────────────┤
# │ FEISHU_SEND_MODE             │ 必填     │ 必填     │ 必填     │ webhook    │
# ├──────────────────────────────┼──────────┼──────────┼──────────┼────────────┤
# │ FEISHU_WEBHOOK_URL           │ 必填     │ -        │ -        │ -          │
# │ FEISHU_APP_ID                │ -        │ 必填     │ 网关必填 │ -          │
# │ FEISHU_APP_SECRET            │ -        │ 必填     │ 网关必填 │ -          │
# │ FEISHU_VERIFICATION_TOKEN    │ -        │ 必填     │ 网关必填 │ -          │
# │ FEISHU_GATEWAY_URL           │ -        │ -        │ CB必填   │ -          │
# │ FEISHU_OWNER_ID              │ 可选     │ 必填     │ 必填     │ -          │
# │ FEISHU_CHAT_ID               │ -        │ 可选     │ 可选     │ -          │
# ├──────────────────────────────┼──────────┼──────────┼──────────┼────────────┤
# │ CALLBACK_SERVER_URL          │ 建议     │ 建议     │ 建议     │ localhost  │
# │ CALLBACK_SERVER_PORT         │ 可选     │ 可选     │ 可选     │ 8080       │
# │ PERMISSION_SOCKET_PATH       │ 可选     │ 可选     │ 可选     │ /tmp/...   │
# ├──────────────────────────────┼──────────┼──────────┼──────────┼────────────┤
# │ FEISHU_AT_USER               │ 可选     │ 可选     │ 可选     │ 空         │
# │ PERMISSION_REQUEST_TIMEOUT   │ 可选     │ 可选     │ 可选     │ 600        │
# │ PERMISSION_NOTIFY_DELAY      │ 可选     │ 可选     │ 可选     │ 60         │
# │ CALLBACK_PAGE_CLOSE_DELAY    │ 可选     │ 可选     │ 可选     │ 3          │
# │ STOP_THINKING_MAX_LENGTH     │ 可选     │ 可选     │ 可选     │ 5000       │
# │ STOP_MESSAGE_MAX_LENGTH      │ 可选     │ 可选     │ 可选     │ 5000       │
# ├──────────────────────────────┼──────────┼──────────┼──────────┼────────────┤
# │ CLAUDE_COMMAND               │ 可选     │ 可选     │ 可选     │ claude     │
# ├──────────────────────────────┼──────────┼──────────┼──────────┼────────────┤
# │ VSCODE_URI_PREFIX            │ 可选     │ 可选     │ 可选     │ -          │
# │ ACTIVATE_VSCODE_ON_CALLBACK  │ 可选     │ 可选     │ 可选     │ false      │
# │ VSCODE_SSH_PROXY_PORT        │ 可选     │ 可选     │ 可选     │ -          │
# └──────────────────────────────┴──────────┴──────────┴──────────┴────────────┘
# CB必填 = Callback 服务必填

# =============================================================================
# 一、发送模式（必选）
# =============================================================================

# 发送模式
# - webhook: 使用飞书 Webhook 发送（简单，按钮跳转浏览器）
# - openapi: 使用飞书 OpenAPI 发送（按钮在飞书内响应，需配置事件订阅）
FEISHU_SEND_MODE=webhook

# =============================================================================
# 二、飞书凭证与身份
# =============================================================================
#
# 【重要】OpenAPI 模式需要在飞书开放平台配置事件订阅：
#   1. 进入应用管理 -> 事件订阅 -> 添加事件
#   2. 搜索并订阅「卡片回传交互」(card.action.trigger)
#   3. 配置请求地址为 CALLBACK_SERVER_URL（单机）或飞书网关地址（分离）
#   4. 完成 URL 验证（服务需已启动）
#
# --- 部署方式 ---
# OpenAPI 模式支持两种部署方式：
#
# 【单机部署】所有配置在同一台机器
#   - 配置 FEISHU_APP_ID、FEISHU_APP_SECRET、FEISHU_VERIFICATION_TOKEN、FEISHU_OWNER_ID
#   - 不配置 FEISHU_GATEWAY_URL
#
# 【分离部署】飞书网关与 Callback 服务分离（多实例场景）
#   - 网关服务: 配置 FEISHU_APP_ID、FEISHU_APP_SECRET、FEISHU_VERIFICATION_TOKEN
#   - Callback 服务: 配置 FEISHU_GATEWAY_URL、FEISHU_OWNER_ID
#   - 每个 Callback 服务可以发给不同用户（通过各自的 FEISHU_OWNER_ID）

# --- Webhook 模式 ---
# 飞书 Webhook URL [Webhook 必填]
# 从飞书机器人设置中获取
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxx

# --- OpenAPI 模式 — 应用凭证 [单机/网关 必填] ---
# 从飞书开放平台 -> 应用管理 -> 凭证与基础信息 获取
# 分离部署时仅网关服务需要配置
FEISHU_APP_ID=
FEISHU_APP_SECRET=

# Verification Token [单机/网关 必填]
# 从飞书开放平台 -> 应用管理 -> 事件订阅 -> 加密与签名 获取
# 用于验证飞书事件来源 + 生成注册 auth_token
FEISHU_VERIFICATION_TOKEN=

# --- OpenAPI 模式 — 网关（分离部署）---
# 飞书网关地址 [分离部署 Callback 必填]
# 配置后，消息通过飞书网关发送，本机无需配置飞书应用凭证
# 同时用于网关注册功能（注册接口为 {FEISHU_GATEWAY_URL}/register）
FEISHU_GATEWAY_URL=

# --- 消息接收者 ---
# 飞书用户 ID [OpenAPI 必填]
# 必须使用 user_id 格式（纯数字或字母数字组合），服务启动时会校验格式
# 获取方式：https://open.feishu.cn/document/faq/trouble-shooting/how-to-obtain-user-id
# Webhook 模式下可选，仅用于通知 @ 用户
FEISHU_OWNER_ID=

# 飞书群聊 ID [可选]
# 由客户端读取，用于发送消息到指定群聊
# 客户端调用 /feishu/send 时可将 chat_id 作为参数传入
FEISHU_CHAT_ID=

# =============================================================================
# 三、回调服务
# =============================================================================
# 分离部署时，仅 Callback 服务需要配置此部分，网关服务不需要

# 回调服务器外部访问地址 [所有模式建议配置]
# 用于飞书卡片按钮的回调 URL
# 如果使用内网穿透，填写穿透后的公网地址
# 启用网关注册功能时必填
CALLBACK_SERVER_URL=http://localhost:8080

# 回调服务器端口 [可选, 默认 8080]
CALLBACK_SERVER_PORT=8080

# Unix Socket 路径 [可选, 默认 /tmp/claude-permission.sock]
# 用于 hook 脚本与回调服务器之间的通信
PERMISSION_SOCKET_PATH=/tmp/claude-permission.sock

# =============================================================================
# 四、通知与交互行为
# =============================================================================

# 飞书通知 @ 用户配置 [可选]
# 适用于所有飞书通知（权限请求、任务完成等），与发送模式无关
# 支持以下格式:
#   - 空: 默认 @ FEISHU_OWNER_ID 用户
#   - all: @ 所有人
#   - off: 不 @ 任何人
FEISHU_AT_USER=

# 请求超时时间，秒 [可选, 默认 600]
# 用户在此时间内未响应，将回退到终端交互
PERMISSION_REQUEST_TIMEOUT=600

# 权限通知延迟时间，秒 [可选, 默认 60]
# 收到权限请求后延迟指定秒数再发送飞书消息
# 用于避免快速连续请求时的消息轰炸
# 设为 0 表示立即发送
PERMISSION_NOTIFY_DELAY=60

# 回调页面自动关闭时间，秒 [可选, 默认 3]
# 用户点击按钮后，回调页面显示的倒计时秒数
# 建议范围: 1-10 秒
CALLBACK_PAGE_CLOSE_DELAY=3

# Stop 事件思考过程最大长度，字符数 [可选, 默认 5000]
# 设为 0 则不显示思考过程
STOP_THINKING_MAX_LENGTH=5000

# Stop 事件消息最大长度，字符数 [可选, 默认 5000]
# 主 Agent 完成时，发送飞书通知中显示的响应内容最大长度
# 超过此长度会被截断并添加 "..."
STOP_MESSAGE_MAX_LENGTH=5000

# =============================================================================
# 五、Claude 命令
# =============================================================================

# Claude 命令 [可选, 默认 claude]
# 用于继续会话和新建会话功能
#
# 单命令配置（向后兼容）:
#   CLAUDE_COMMAND=claude
#   CLAUDE_COMMAND=claude --setting opus
#
# 多命令配置（列表格式，无需引号）:
#   CLAUDE_COMMAND=[claude, claude --setting opus]
#
# 也兼容 JSON 数组格式:
#   CLAUDE_COMMAND=["claude", "claude --setting opus"]
#
# 配置多个命令后:
#   - 默认使用列表第一个
#   - /new 卡片支持选择
#   - /new --cmd=1 或 /new --cmd=opus 指定使用哪个
#   - /reply --cmd=opus 在回复时指定
#   - 空值或缺失时默认使用 claude
CLAUDE_COMMAND=claude

# =============================================================================
# 六、VSCode 集成（可选，以下两种模式二选一）
# =============================================================================
#
# 【模式一】浏览器跳转模式 - VSCODE_URI_PREFIX
# -----------------------------------------------------------------------------
# 原理：点击飞书按钮后，浏览器回调页面通过 vscode:// 协议链接跳转到 VSCode
# 优点：配置简单，无需额外服务
# 缺点：受浏览器安全策略限制，可能触发跳转确认弹窗
#
# 格式: vscode://vscode-remote/{remote-type}+{host} 或 vscode://file
# 示例:
#   - SSH Remote: vscode://vscode-remote/ssh-remote+myserver
#   - WSL: vscode://vscode-remote/wsl+Ubuntu
#   - 本地: vscode://file (用于本地开发)
#
# 【推荐】VSCode 设置，允许外部应用直接打开（无需确认）：
#   - 本地: settings.json 添加 "security.promptForLocalFileProtocolHandling": false
#   - 远程: settings.json 添加 "security.promptForRemoteFileProtocolHandling": false
#
VSCODE_URI_PREFIX=

# 【模式二】自动激活模式 - ACTIVATE_VSCODE_ON_CALLBACK (推荐)
# -----------------------------------------------------------------------------
# 原理：服务端直接调用命令激活 VSCode 窗口，不依赖浏览器跳转
# 优点：不受浏览器策略限制，体验更流畅
# 缺点：SSH Remote 场景需要配合反向隧道代理
#
# --- 本地开发场景 ---
# 仅配置此项为 true 即可，服务端会执行 'code .' 激活本地 VSCode 窗口
ACTIVATE_VSCODE_ON_CALLBACK=false
#
# --- SSH Remote 远程开发场景 ---
# 结合上述配置，再配置 VSCODE_SSH_PROXY_PORT 即可
# 通过反向 SSH 隧道唤起本地 VSCode 窗口
#
# 使用方法:
#   1. 在本地电脑运行代理服务:
#      python3 src/proxy/vscode_ssh_proxy.py --vps <host> [options]
#        --vps HOST        VPS 的 SSH 地址 (别名如 myserver，或 root@1.2.3.4)
#        --ssh-port PORT   SSH 端口 (默认: 22，使用别名时从 ~/.ssh/config 读取)
#        -p, --port        本地 HTTP 服务端口 (默认: 9527)
#        -r, --remote-port VPS 端远程端口 (默认: 同本地端口)
#   2. 点击飞书按钮会自动唤起本地 VSCode
#
# 注意: VSCODE_SSH_PROXY_PORT 需与代理服务的 --remote-port 参数保持一致 (如 9527)
VSCODE_SSH_PROXY_PORT=
EOF

    print_success "环境变量模板已生成"
    echo ""
    echo "  模板文件: $(print_highlight "$env_file")"
    echo ""
    print_dim "提示：脚本会自动从 .env 文件读取配置，无需手动 source"
    echo ""
    echo "$(print_highlight "快速配置指南：")"
    echo ""
    echo "  复制模板为实际配置文件："
    echo "    cp .env.example .env"
    echo ""
    echo "  编辑 .env 文件，至少配置以下 2 项："
    echo "    1. FEISHU_WEBHOOK_URL     - 飞书 Webhook URL"
    echo "    2. CALLBACK_SERVER_URL    - 回调服务器地址（内网穿透填公网地址）"
    echo ""
    print_dim "  其他配置使用默认值即可，有需要再按需调整"
}

# =============================================================================
# 卸载
# =============================================================================

uninstall() {
    print_section "卸载 Claude Code Hook"

    if [ ! -f "$SETTINGS_FILE" ]; then
        print_info "配置文件不存在，无需卸载"
        return 0
    fi

    # 使用 Python 移除 PermissionRequest 和 Stop hook（保留其他 hooks）
    python3 << PYTHON_SCRIPT
import json

settings_file = "${SETTINGS_FILE}"
hook_path = "${HOOK_PATH}"

try:
    with open(settings_file, 'r') as f:
        config = json.load(f)
except:
    print("无法读取配置文件")
    exit(1)

if 'hooks' not in config:
    print("未找到 hooks 配置")
    exit(0)

# 删除 PermissionRequest 和 Stop hook，保留其他 hooks
events_to_remove = ['PermissionRequest', 'Stop']
removed = []

for event in events_to_remove:
    if event in config['hooks']:
        del config['hooks'][event]
        removed.append(event)

if removed:
    print(f"已移除 hook: {', '.join(removed)}")

    # 如果 hooks 字段为空，删除整个 hooks 字段
    if len(config['hooks']) == 0:
        del config['hooks']
        print("hooks 配置已清空，移除 hooks 字段")
else:
    print("未找到需要移除的 hook 配置")

with open(settings_file, 'w') as f:
    json.dump(config, f, indent=2)
PYTHON_SCRIPT

    print_success "卸载完成"
}

# =============================================================================
# 显示帮助
# =============================================================================

show_help() {
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  --check      仅检测环境依赖"
    echo "  --uninstall  卸载 hook 配置"
    echo "  --help       显示此帮助信息"
    echo ""
    echo "无参数运行时执行完整安装流程:"
    echo "  1. 检测环境依赖"
    echo "  2. 配置 Claude Code hook"
    echo "  3. 生成环境变量模板"
}

# =============================================================================
# 主函数
# =============================================================================

main() {
    case "${1:-}" in
        --check)
            print_header
            check_dependencies
            ;;
        --uninstall)
            print_header
            uninstall
            ;;
        --help|-h)
            show_help
            ;;
        "")
            print_header
            if check_dependencies; then
                configure_hook
                generate_env_template

                print_section "安装完成"

                echo -e "${GREEN}${BOLD}✓ 所有组件已就绪${NC}"
                echo ""
                echo -e "${BOLD}下一步操作：${NC}"
                echo ""
                echo "  1. 复制并编辑配置文件："
                echo -e "     ${YELLOW}cp .env.example .env && vim .env${NC}"
                echo ""
                echo "  2. 启动回调服务："
                echo -e "     ${YELLOW}./src/start-server.sh${NC}"
                echo ""
                echo "  3. 使用 Claude Code，权限请求将发送到飞书"
                echo ""
                print_dim "可选：VSCode SSH 代理 - python3 src/proxy/vscode_ssh_proxy.py --vps <host>"
            fi
            ;;
        *)
            print_error "未知选项: $1"
            show_help
            exit 1
            ;;
    esac
}

main "$@"
