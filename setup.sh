#!/bin/bash
# =============================================================================
# setup.sh - Claude Code 飞书通知一键安装脚本
#
# 功能：
#   1. 自动下载源码（如不在源码目录）
#   2. 执行 install.sh 的依赖检测和 hook 配置
#   3. 自动配置 .env 为 OpenAPI 模式并写入飞书凭证
#
# 用法：
#   单机模式：./setup.sh --app-id=cli_xxx --app-secret=xxx [--verification-token=xxx] [--owner-id=xxx] [--port=8080]
#   分离模式：./setup.sh --gateway-url=ws://host:port --owner-id=xxx [--port=8080]
#   更新：    ./setup.sh update
#   ./setup.sh --help
# =============================================================================

set -e
set -o pipefail

# =============================================================================
# 解析命令行参数
# =============================================================================

ACTION=""
APP_ID=""
APP_SECRET=""
VERIFICATION_TOKEN=""
GATEWAY_URL=""
OWNER_ID=""
PORT=""
SHOW_HELP=false

for arg in "$@"; do
    case "$arg" in
        update)
            ACTION="update"
            ;;
        --app-id=*)
            APP_ID="${arg#*=}"
            ;;
        --app-secret=*)
            APP_SECRET="${arg#*=}"
            ;;
        --verification-token=*)
            VERIFICATION_TOKEN="${arg#*=}"
            ;;
        --gateway-url=*)
            GATEWAY_URL="${arg#*=}"
            ;;
        --owner-id=*)
            OWNER_ID="${arg#*=}"
            ;;
        --port=*)
            PORT="${arg#*=}"
            ;;
        --help|-h)
            SHOW_HELP=true
            ;;
        *)
            echo "未知参数: $arg"
            echo "使用 --help 查看帮助"
            exit 1
            ;;
    esac
done

# =============================================================================
# 帮助信息
# =============================================================================

if [ "$SHOW_HELP" = true ] || [ $# -eq 0 ]; then
    echo "用法: $0 <部署模式参数> [选项]"
    echo ""
    echo "一键安装 Claude Code 飞书通知（OpenAPI 模式）"
    echo ""
    echo "单机模式（本机配置飞书应用凭证）:"
    echo "  --app-id=ID                 飞书应用 App ID（必填）"
    echo "  --app-secret=SECRET         飞书应用 App Secret（必填）"
    echo "  --verification-token=TOKEN  飞书 Verification Token（HTTP 回调模式需要）"
    echo "                              如已安装 lark-oapi（长连接模式），可不填"
    echo ""
    echo "分离模式（通过网关连接，无需飞书应用凭证）:"
    echo "  --gateway-url=URL           飞书网关地址（必填，如 ws://host:port）"
    echo "  --owner-id=ID               飞书用户 ID（必填）"
    echo ""
    echo "更新:"
    echo "  update                      拉取最新代码并重启服务"
    echo ""
    echo "通用可选参数:"
    echo "  --owner-id=ID               飞书用户 ID（可稍后在 .env 中配置）"
    echo "  --port=PORT                 服务端口（默认 8080）"
    echo "  --help                      显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  # 单机 - 长连接模式（已安装 lark-oapi）"
    echo "  $0 --app-id=cli_xxx --app-secret=xxx --owner-id=xxx"
    echo ""
    echo "  # 单机 - HTTP 回调模式（未安装 lark-oapi）"
    echo "  $0 --app-id=cli_xxx --app-secret=xxx --verification-token=xxx --owner-id=xxx"
    echo ""
    echo "  # 分离模式 - 通过网关"
    echo "  $0 --gateway-url=ws://gateway:8080 --owner-id=xxx"
    exit 0
fi

# =============================================================================
# update 参数校验（提前检测，避免先触发源码下载）
# =============================================================================

if [ "$ACTION" = "update" ]; then
    if [ -n "$APP_ID" ] || [ -n "$APP_SECRET" ] || [ -n "$GATEWAY_URL" ] || [ -n "$OWNER_ID" ] || [ -n "$VERIFICATION_TOKEN" ]; then
        echo "错误: update 不能与其他参数一起使用"
        echo "用法: $0 update"
        exit 1
    fi
fi

# =============================================================================
# 检测源码目录
# =============================================================================

SETUP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

DOWNLOADED_SOURCE=false

if [ -f "${SETUP_DIR}/.env.example" ] && [ -f "${SETUP_DIR}/src/start-server.sh" ]; then
    # 已在源码目录
    SOURCE_DIR="$SETUP_DIR"
else
    # 需要下载源码
    echo "未检测到源码目录，正在下载..."

    REPO_URL="https://github.com/frankie-huang/claude-notify.git"
    TARGET_DIR="${SETUP_DIR}/claude-notify"

    # 目标目录已存在时提示用户
    if [ -d "$TARGET_DIR" ]; then
        echo "错误: 目录 ${TARGET_DIR} 已存在"
        echo "如需重新下载，请先删除该目录：rm -rf ${TARGET_DIR}"
        exit 1
    fi

    if command -v git &>/dev/null; then
        if ! git clone "$REPO_URL" "$TARGET_DIR" 2>&1; then
            echo "git clone 失败"
            exit 1
        fi
    elif command -v curl &>/dev/null; then
        TARBALL_URL="https://github.com/frankie-huang/claude-notify/archive/refs/heads/main.tar.gz"
        # 检测 tarball 解压的中间目录是否残留
        if [ -d "${SETUP_DIR}/claude-notify-main" ]; then
            echo "错误: 目录 ${SETUP_DIR}/claude-notify-main 已存在（可能是之前下载失败的残留）"
            echo "请先删除该目录：rm -rf ${SETUP_DIR}/claude-notify-main"
            exit 1
        fi
        if ! curl -fsSL "$TARBALL_URL" | tar xz -C "$SETUP_DIR" 2>&1; then
            echo "下载源码失败"
            exit 1
        fi
        # tar 解压后目录名为 claude-notify-main
        if [ -d "${SETUP_DIR}/claude-notify-main" ]; then
            mv "${SETUP_DIR}/claude-notify-main" "$TARGET_DIR"
        fi
    else
        echo "错误: 需要 git 或 curl 来下载源码"
        exit 1
    fi

    if [ ! -d "$TARGET_DIR" ] || [ ! -f "${TARGET_DIR}/.env.example" ] || [ ! -f "${TARGET_DIR}/src/start-server.sh" ]; then
        echo "错误: 源码下载不完整"
        exit 1
    fi

    SOURCE_DIR="$TARGET_DIR"
    DOWNLOADED_SOURCE=true
    echo "源码已下载到: $SOURCE_DIR"
fi

# =============================================================================
# update 子命令：拉取最新代码并重启服务
# =============================================================================

if [ "$ACTION" = "update" ]; then
    set +e
    echo "正在更新..."

    # 拉取最新代码
    if [ -e "${SOURCE_DIR}/.git" ]; then
        echo ""
        if git -C "$SOURCE_DIR" pull; then
            echo ""
            echo "代码已更新"
        else
            echo "git pull 失败"
            exit 1
        fi
    else
        echo "错误: ${SOURCE_DIR} 不是 git 仓库，无法自动更新"
        echo "请手动下载最新代码"
        exit 1
    fi

    # 重启服务
    echo ""
    if "${SOURCE_DIR}/src/start-server.sh" restart; then
        echo ""
        echo "更新完成"
    else
        echo ""
        echo "代码已更新，但服务启动失败，请检查上方错误信息"
        exit 1
    fi

    exit 0
fi

# =============================================================================
# 加载 install.sh 的函数
# =============================================================================

INSTALL_SCRIPT="${SOURCE_DIR}/install.sh"

if [ ! -f "$INSTALL_SCRIPT" ]; then
    echo "错误: 找不到 install.sh: $INSTALL_SCRIPT"
    exit 1
fi

# source install.sh 中的函数（守卫变量阻止其执行 main）
_SOURCED_BY_SETUP=true source "$INSTALL_SCRIPT"

# source 后重新设置路径（install.sh 的顶层赋值会覆盖）
SCRIPT_DIR="$SOURCE_DIR"
HOOK_PATH="${SCRIPT_DIR}/src/hook-router.sh"
SETTINGS_FILE="${HOME}/.claude/settings.json"

# 辅助函数：从 .env 文件读取配置值（支持空值）
get_env_value() {
    local key="$1"
    local file="$2"
    grep -E "^${key}=" "$file" 2>/dev/null | head -1 | cut -d= -f2-
}

# =============================================================================
# 执行依赖检测
# =============================================================================

# 覆盖 install.sh 的 print_header
print_header() {
    echo -e "${BLUE}"
    echo "╔═══════════════════════════════════════════════════════════════╗"
    echo "║       Claude Code 飞书通知 - 一键安装脚本                     ║"
    echo "╚═══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_header

if ! check_dependencies; then
    print_error "依赖检测失败，请先安装缺失的依赖后重试"
    exit 1
fi

# =============================================================================
# 配置 Hook
# =============================================================================

if ! configure_hook; then
    print_error "Hook 配置失败"
    exit 1
fi

# =============================================================================
# 配置 .env 文件
# =============================================================================

print_section "配置 .env 文件"

ENV_FILE="${SOURCE_DIR}/.env"
ENV_EXAMPLE="${SOURCE_DIR}/.env.example"

# 如果 .env 不存在，从 .env.example 复制
if [ ! -f "$ENV_FILE" ]; then
    if [ ! -f "$ENV_EXAMPLE" ]; then
        print_error ".env.example 模板文件不存在"
        exit 1
    fi
    cp "$ENV_EXAMPLE" "$ENV_FILE"
    print_success ".env 文件已从模板创建"
else
    print_info ".env 文件已存在，将在现有文件上更新配置"
fi

# 检测 .env 中是否存在重复的配置项
DUPLICATE_KEYS=$(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "$ENV_FILE" | cut -d= -f1 | sort | uniq -d)
if [ -n "$DUPLICATE_KEYS" ]; then
    print_error ".env 文件中存在重复的配置项："
    for dup_key in $DUPLICATE_KEYS; do
        echo "  - $dup_key"
    done
    echo ""
    echo "请编辑 $ENV_FILE，移除重复的配置项后重试"
    exit 1
fi

# 如果用户未传 --owner-id，尝试从 .env 中读取已有值
if [ -z "$OWNER_ID" ]; then
    EXISTING_OWNER_ID=$(get_env_value "FEISHU_OWNER_ID" "$ENV_FILE")
    if [ -n "$EXISTING_OWNER_ID" ]; then
        OWNER_ID="$EXISTING_OWNER_ID"
    fi
fi

# 检测 lark-oapi 是否已安装
HAS_LARK_OAPI=false
if python3 -c "import lark_oapi" 2>/dev/null; then
    HAS_LARK_OAPI=true
    print_success "lark-oapi 已安装（支持长连接模式）"
else
    print_info "lark-oapi 未安装（将使用 HTTP 回调模式）"
fi

# 确定部署模式（单机模式优先）
if [ -n "$APP_ID" ] && [ -n "$APP_SECRET" ] && [ -n "$GATEWAY_URL" ]; then
    print_warning "--gateway-url 与 --app-id/--app-secret 不能同时使用，已忽略 --gateway-url"
    GATEWAY_URL=""
fi

if [ -n "$GATEWAY_URL" ]; then
    DEPLOY_MODE="gateway"
elif [ -n "$APP_ID" ] && [ -n "$APP_SECRET" ]; then
    DEPLOY_MODE="standalone"
else
    print_error "缺少必填参数"
    echo ""
    echo "单机模式: $0 --app-id=<App ID> --app-secret=<App Secret> [--owner-id=<用户ID>]"
    echo "分离模式: $0 --gateway-url=<网关地址> --owner-id=<用户ID>"
    exit 1
fi

# 根据部署模式验证必要参数
case "$DEPLOY_MODE" in
    gateway)
        if [ -z "$OWNER_ID" ]; then
            print_error "分离模式下 --owner-id 为必填参数"
            echo ""
            echo "方式一: 在 .env 中配置 FEISHU_OWNER_ID 后重新执行"
            echo "方式二: $0 --gateway-url=<网关地址> --owner-id=<用户ID>"
            exit 1
        fi
        ;;
    standalone)
        if [ "$HAS_LARK_OAPI" = false ] && [ -z "$VERIFICATION_TOKEN" ]; then
            print_error "lark-oapi 未安装，HTTP 回调模式需要 --verification-token 参数"
            echo ""
            echo "解决方案（二选一）："
            echo "  1. 安装 lark-oapi 后重试（推荐，支持长连接模式）："
            echo "     python3 -m pip install lark-oapi"
            echo ""
            echo "  2. 提供 verification-token 参数："
            echo "     $0 --app-id=$APP_ID --app-secret=<App Secret> --verification-token=<Token>"
            exit 1
        fi
        ;;
esac

# 使用 Python 更新 .env 文件（避免 sed -i 跨平台问题）
ENV_FILE="$ENV_FILE" \
DEPLOY_MODE="$DEPLOY_MODE" \
APP_ID="$APP_ID" \
APP_SECRET="$APP_SECRET" \
GATEWAY_URL="$GATEWAY_URL" \
OWNER_ID="$OWNER_ID" \
VERIFICATION_TOKEN="$VERIFICATION_TOKEN" \
PORT="$PORT" \
python3 << 'PYTHON_SCRIPT'
import os
import re

env_file = os.environ['ENV_FILE']
deploy_mode = os.environ['DEPLOY_MODE']
app_id = os.environ.get('APP_ID', '')
app_secret = os.environ.get('APP_SECRET', '')
gateway_url = os.environ.get('GATEWAY_URL', '')
owner_id = os.environ.get('OWNER_ID', '')
verification_token = os.environ.get('VERIFICATION_TOKEN', '')
port = os.environ.get('PORT', '')

with open(env_file, 'r') as f:
    content = f.read()

def update_env_var(content, key, value):
    # type: (str, str, str) -> str
    """Update a KEY=value line in .env content."""
    pattern = r'^(' + re.escape(key) + r')=.*$'
    replacement = key + '=' + value
    new_content, count = re.subn(pattern, replacement, content, flags=re.MULTILINE)
    if count == 0:
        new_content = content.rstrip('\n') + '\n' + replacement + '\n'
    return new_content

content = update_env_var(content, 'FEISHU_SEND_MODE', 'openapi')

if deploy_mode == 'standalone':
    content = update_env_var(content, 'FEISHU_APP_ID', app_id)
    content = update_env_var(content, 'FEISHU_APP_SECRET', app_secret)
    if verification_token:
        content = update_env_var(content, 'FEISHU_VERIFICATION_TOKEN', verification_token)
else:
    content = update_env_var(content, 'FEISHU_GATEWAY_URL', gateway_url)

if owner_id:
    content = update_env_var(content, 'FEISHU_OWNER_ID', owner_id)

if port:
    # 读取旧的端口值
    old_port_match = re.search(r'^CALLBACK_SERVER_PORT=(.*)$', content, re.MULTILINE)
    old_port = old_port_match.group(1).strip() if old_port_match else '8080'

    content = update_env_var(content, 'CALLBACK_SERVER_PORT', port)

    # 仅当 CALLBACK_SERVER_URL 以旧端口结尾时才更新端口
    current_url_match = re.search(r'^CALLBACK_SERVER_URL=(.*)$', content, re.MULTILINE)
    if current_url_match:
        current_url = current_url_match.group(1).strip()
        if current_url.endswith(':' + old_port) or current_url.endswith(':' + old_port + '/'):
            new_url = current_url.replace(':' + old_port, ':' + port)
            content = update_env_var(content, 'CALLBACK_SERVER_URL', new_url)

with open(env_file, 'w') as f:
    f.write(content)
PYTHON_SCRIPT

print_success "FEISHU_SEND_MODE=openapi"
if [ "$DEPLOY_MODE" = "standalone" ]; then
    print_success "FEISHU_APP_ID=$APP_ID"
    print_success "FEISHU_APP_SECRET=******"
    if [ -n "$VERIFICATION_TOKEN" ]; then
        print_success "FEISHU_VERIFICATION_TOKEN=******"
    fi
else
    print_success "FEISHU_GATEWAY_URL=$GATEWAY_URL"
    # 检测 .env 中是否残留飞书应用凭证
    ENV_APP_ID=$(get_env_value "FEISHU_APP_ID" "$ENV_FILE")
    ENV_APP_SECRET=$(get_env_value "FEISHU_APP_SECRET" "$ENV_FILE")
    if [ -n "$ENV_APP_ID" ] && [ -n "$ENV_APP_SECRET" ]; then
        echo ""
        print_warning ".env 中存在 FEISHU_APP_ID/FEISHU_APP_SECRET 配置"
        print_warning "分离模式下这些配置会导致冲突，请手动清除："
        echo -e "     编辑 ${YELLOW}$ENV_FILE${NC}，将 FEISHU_APP_ID 和 FEISHU_APP_SECRET 的值清空"
    fi
    # 非 ws/wss 协议时，CALLBACK_SERVER_URL 需要公网可访问
    case "$GATEWAY_URL" in
        ws://*|wss://*)
            ;;
        *)
            CALLBACK_URL=$(get_env_value "CALLBACK_SERVER_URL" "$ENV_FILE")
            if [ -z "$CALLBACK_URL" ] || echo "$CALLBACK_URL" | grep -qE '(^|//)(localhost|127\.[0-9]+\.[0-9]+\.[0-9]+|0\.0\.0\.0|\[::1?\])([:/]|$)'; then
                echo ""
                print_error "网关地址使用 HTTP 协议，CALLBACK_SERVER_URL 必须为公网可访问地址"
                if [ -n "$CALLBACK_URL" ]; then
                    print_error "当前值: $CALLBACK_URL"
                fi
                echo ""
                echo "请在 .env 中将 CALLBACK_SERVER_URL 配置为公网地址后重新执行"
                echo "或改用 WebSocket 协议的网关地址（ws:// 或 wss://）"
                exit 1
            fi
            ;;
    esac
fi
if [ -n "$OWNER_ID" ]; then
    print_success "FEISHU_OWNER_ID=$OWNER_ID"
fi
if [ -n "$PORT" ]; then
    print_success "CALLBACK_SERVER_PORT=$PORT"
fi

# =============================================================================
# 启动服务
# =============================================================================

print_section "启动回调服务"

SERVER_OK=true
if ! "${SOURCE_DIR}/src/start-server.sh" restart; then
    SERVER_OK=false
fi

# =============================================================================
# 完成提示
# =============================================================================

print_section "安装完成"

if [ "$SERVER_OK" = true ]; then
    echo -e "${GREEN}${BOLD}✓ 所有组件已就绪${NC}"
else
    echo -e "${YELLOW}${BOLD}⚠ 安装完成，但服务启动失败${NC}"
fi
echo ""
echo -e "${BOLD}配置结果：${NC}"
echo "  发送模式: OpenAPI"
if [ "$DEPLOY_MODE" = "standalone" ]; then
    echo "  部署模式: 单机"
    echo "  App ID:   $APP_ID"
else
    echo "  部署模式: 分离（网关）"
    echo "  网关地址: $GATEWAY_URL"
fi
if [ -n "$OWNER_ID" ]; then
    echo "  Owner ID: $OWNER_ID"
fi
if [ -n "$PORT" ]; then
    echo "  服务端口: $PORT"
fi
echo "  配置文件: $ENV_FILE"
echo ""
echo -e "${BOLD}下一步操作：${NC}"
echo ""

# 构造重启命令提示（根据是否新下载源码决定是否加 cd 前缀）
if [ "$DOWNLOADED_SOURCE" = true ]; then
    RESTART_CMD="cd $SOURCE_DIR && ./src/start-server.sh restart"
else
    RESTART_CMD="./src/start-server.sh restart"
fi

STEP=1
if [ "$SERVER_OK" = false ]; then
    echo "  ${STEP}. 检查上方错误信息，修复配置后重启服务："
    echo -e "     ${YELLOW}${RESTART_CMD}${NC}"
    echo ""
    STEP=$((STEP + 1))
fi

if [ -z "$OWNER_ID" ]; then
    echo "  ${STEP}. 配置飞书用户 ID（单机模式必填，网关服务可跳过）："
    echo -e "     编辑 ${YELLOW}$ENV_FILE${NC}，设置 FEISHU_OWNER_ID"
    echo -e "     修改后执行 ${YELLOW}${RESTART_CMD}${NC} 重启生效"
    echo ""
    STEP=$((STEP + 1))
fi

if [ "$DEPLOY_MODE" = "standalone" ]; then
    # 读取 .env 中的 FEISHU_EVENT_MODE
    EVENT_MODE=$(get_env_value "FEISHU_EVENT_MODE" "$ENV_FILE")
    EVENT_MODE="${EVENT_MODE:-auto}"
    echo "  ${STEP}. 在飞书开放平台配置事件与回调："
    echo ""
    if [ "$HAS_LARK_OAPI" = true ] && { [ "$EVENT_MODE" = "auto" ] || [ "$EVENT_MODE" = "longpoll" ]; }; then
        echo "     a) 事件订阅 & 卡片回调均选择「使用长连接接收事件」"
    else
        SERVER_PORT=$(get_env_value "CALLBACK_SERVER_PORT" "$ENV_FILE")
        SERVER_PORT="${SERVER_PORT:-8080}"
        echo "     a) 事件订阅 & 卡片回调均选择「将事件发送至开发者服务器」"
        echo "        请求地址填写本机公网 IP + 端口，如 http://<公网IP>:${SERVER_PORT}"
    fi
    echo ""
    echo "     b) 订阅回调事件："
    echo "        卡片回传交互 (card.action.trigger)"
    echo ""
    echo "     c) 开通应用权限："
    echo "        contact:user.employee_id:readonly"
    echo "        im:message.group_at_msg:readonly"
    echo "        im:message.p2p_msg:readonly"
    echo "        im:message.reactions:read"
    echo "        im:message.reactions:write_only"
    echo "        im:message:send_as_bot"
    echo ""
    STEP=$((STEP + 1))
fi

echo "  ${STEP}. 使用 Claude Code，通知将发送到飞书"
