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
NC='\033[0m' # No Color

# 脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOK_PATH="${SCRIPT_DIR}/hooks/permission-notify.sh"
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

# =============================================================================
# 检测依赖
# =============================================================================

check_dependencies() {
    echo "检测环境依赖..."
    echo ""

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
        print_warning "socat: 未安装 (可选，将使用 Python socket-client)"
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
    echo ""
    echo "配置 Claude Code Hook..."
    echo ""

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

# 检查 PermissionRequest 是否已存在
if 'PermissionRequest' in config['hooks']:
    # 已存在 PermissionRequest hook，检查是否已配置我们的脚本
    existing_hooks = config['hooks']['PermissionRequest']
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
        print("PermissionRequest hook 已配置，跳过更新")
    else:
        print("PermissionRequest hook 已存在其他配置，保留原配置")
else:
    # PermissionRequest 不存在，添加我们的配置
    config['hooks']['PermissionRequest'] = [
        {
            'matcher': '',
            'hooks': [
                {
                    'type': 'command',
                    'command': hook_path
                }
            ]
        }
    ]
    print("配置已添加")

with open(settings_file, 'w') as f:
    json.dump(config, f, indent=2)
PYTHON_SCRIPT

    else
        # 直接写入新配置
        echo "$hook_config" > "$SETTINGS_FILE"
    fi

    print_success "Hook 已配置到: $SETTINGS_FILE"
    echo ""
    echo "配置内容："
    echo "  Hook 脚本: $HOOK_PATH"
    echo "  触发事件: PermissionRequest"
}

# =============================================================================
# 生成环境变量模板
# =============================================================================

generate_env_template() {
    local env_file="${SCRIPT_DIR}/.env.example"

    echo ""
    echo "生成环境变量模板..."
    echo ""

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
# 然后在启动服务前执行: source .env
# =============================================================================

# 飞书 Webhook URL (必需)
# 从飞书机器人设置中获取
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxx

# 回调服务器外部访问地址 (必需)
# 用于飞书卡片按钮的回调 URL
# 如果使用内网穿透，填写穿透后的公网地址
CALLBACK_SERVER_URL=http://localhost:8080

# 回调服务器端口 (可选，默认 8080)
CALLBACK_SERVER_PORT=8080

# Unix Socket 路径 (可选，默认 /tmp/claude-permission.sock)
PERMISSION_SOCKET_PATH=/tmp/claude-permission.sock

# 请求超时时间，秒 (可选，默认 300)
# 用户在此时间内未响应，将回退到终端交互
REQUEST_TIMEOUT=300

# 回调页面自动关闭时间，秒 (可选，默认 3)
# 用户点击按钮后，回调页面显示的倒计时秒数
# 建议范围: 1-10 秒
CLOSE_PAGE_TIMEOUT=3
EOF

    print_success "环境变量模板已生成: $env_file"
    echo ""
    echo "下一步："
    echo "  1. 复制模板: cp ${env_file} ${SCRIPT_DIR}/.env"
    echo "  2. 编辑配置: vim ${SCRIPT_DIR}/.env"
    echo "  3. 加载环境: source ${SCRIPT_DIR}/.env"
    echo "  4. 启动服务: ${SCRIPT_DIR}/server/start.sh"
    echo ""

    # 检测当前 shell 并提示配置文件
    local current_shell=$(basename "$SHELL")
    local config_file=""

    case "$current_shell" in
        bash)
            config_file="~/.bashrc"
            ;;
        zsh)
            config_file="~/.zshrc"
            ;;
        *)
            config_file="~/.bashrc 或 ~/.zshrc"
            ;;
    esac

    echo "提示：将以下配置添加到 $config_file 可实现自动加载环境变量"
    echo ""
    echo "  echo 'if [ -f ${SCRIPT_DIR}/.env ]; then set -a; source ${SCRIPT_DIR}/.env; set +a; fi' >> $config_file"
    echo ""
}

# =============================================================================
# 卸载
# =============================================================================

uninstall() {
    echo "卸载 Claude Code Hook 配置..."
    echo ""

    if [ ! -f "$SETTINGS_FILE" ]; then
        print_info "配置文件不存在，无需卸载"
        return 0
    fi

    # 使用 Python 移除 PermissionRequest hook（保留其他 hooks）
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

# 只删除 PermissionRequest hook，保留其他 hooks
if 'PermissionRequest' in config['hooks']:
    del config['hooks']['PermissionRequest']
    print("PermissionRequest hook 已移除")

    # 如果 hooks 字段为空，删除整个 hooks 字段
    if len(config['hooks']) == 0:
        del config['hooks']
        print("hooks 配置已清空，移除 hooks 字段")
else:
    print("未找到 PermissionRequest hook 配置")

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
                echo ""
                print_success "安装完成！"
                echo ""
                echo "快速开始："
                echo "  1. 配置环境变量 (参考 .env.example)"
                echo "  2. 启动回调服务: ./server/start.sh"
                echo "  3. 使用 Claude Code，权限请求将发送到飞书"
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
