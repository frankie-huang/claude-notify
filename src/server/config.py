#!/usr/bin/env python3
"""
共享配置模块

提供统一的配置读取接口，支持从 .env 文件和环境变量读取配置

优先级: .env 文件 > 环境变量 > 默认值
"""

import json
import os
from typing import Optional, List, Tuple

# =============================================================================
# 默认配置值
# =============================================================================
DEFAULT_REQUEST_TIMEOUT = 300      # 默认 5 分钟
CLIENT_TIMEOUT_BUFFER = 30         # 客户端额外缓冲 30 秒
DEFAULT_CLOSE_PAGE_TIMEOUT = 3     # 默认 3 秒
DEFAULT_SOCKET_PATH = '/tmp/claude-permission.sock'
DEFAULT_HTTP_PORT = '8080'

# =============================================================================
# .env 文件缓存
# =============================================================================
_env_file_cache: Optional[dict] = None


def _load_env_file() -> dict:
    """加载 .env 文件内容到缓存

    Returns:
        dict: key-value 配置字典
    """
    global _env_file_cache

    if _env_file_cache is not None:
        return _env_file_cache

    _env_file_cache = {}

    # 获取项目根目录 (src/server -> src -> project_root)
    server_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.dirname(server_dir)
    project_root = os.path.dirname(src_dir)
    env_path = os.path.join(project_root, '.env')

    if not os.path.exists(env_path):
        return _env_file_cache

    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # 跳过空行和注释
                if not line or line.startswith('#'):
                    continue
                # 解析 key=value
                if '=' in line:
                    key, _, value = line.partition('=')
                    key = key.strip()
                    value = value.strip()
                    # 去除引号
                    if (value.startswith('"') and value.endswith('"')) or \
                       (value.startswith("'") and value.endswith("'")):
                        value = value[1:-1]
                    _env_file_cache[key] = value
    except Exception:
        pass

    return _env_file_cache


def get_config(key: str, default: str = '') -> str:
    """获取配置值

    优先级: .env 文件 > 环境变量 > 默认值

    Args:
        key: 配置项名称
        default: 默认值

    Returns:
        配置值
    """
    # 1. 优先从 .env 文件读取
    env_cache = _load_env_file()
    if key in env_cache and env_cache[key]:
        return env_cache[key]

    # 2. 其次从环境变量读取
    env_value = os.environ.get(key, '')
    if env_value:
        return env_value

    # 3. 使用默认值
    return default


def get_config_int(key: str, default: int) -> int:
    """获取整数配置值

    Args:
        key: 配置项名称
        default: 默认值

    Returns:
        配置值，无效时返回默认值
    """
    value = get_config(key, '')
    if value and value.isdigit():
        parsed = int(value)
        if parsed > 0:
            return parsed
    return default


def get_request_timeout() -> int:
    """获取请求超时时间

    配置项: REQUEST_TIMEOUT（秒）
    - 必须为正整数
    - 0 或无效值会使用默认值

    Returns:
        超时秒数
    """
    return get_config_int('REQUEST_TIMEOUT', DEFAULT_REQUEST_TIMEOUT)


def get_close_page_timeout() -> int:
    """获取回调页面自动关闭超时时间

    配置项: CLOSE_PAGE_TIMEOUT（秒）
    - 必须为正整数
    - 0 或无效值会使用默认值（3秒）
    - 建议范围：1-10 秒

    Returns:
        超时秒数
    """
    return get_config_int('CLOSE_PAGE_TIMEOUT', DEFAULT_CLOSE_PAGE_TIMEOUT)


def get_claude_commands():
    # type: () -> List[str]
    """解析 CLAUDE_COMMAND 配置为命令列表

    支持格式:
    - 单命令字符串: "claude" 或 "claude --setting opus"
    - 无引号列表: [claude, claude --setting opus]
    - JSON 数组: ["claude", "claude --setting opus"]
    - 空值/缺失: 默认 ["claude"]

    Returns:
        命令字符串列表，至少包含一个元素
    """
    raw = get_config('CLAUDE_COMMAND', '')
    raw = raw.strip()

    if not raw:
        return ['claude']

    # 列表格式: 以 [ 开头且以 ] 结尾
    if raw.startswith('[') and raw.endswith(']'):
        # 先尝试 JSON 解析
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                result = [str(item).strip() for item in parsed if str(item).strip()]
                return result if result else ['claude']
        except (ValueError, TypeError):
            pass

        # JSON 失败，按逗号分隔（无引号列表格式）
        inner = raw[1:-1]
        items = [item.strip() for item in inner.split(',') if item.strip()]
        return items if items else ['claude']

    # 单命令字符串
    return [raw]


def resolve_claude_command(cmd_arg):
    # type: (str) -> Tuple[bool, str]
    """根据索引或名称匹配从配置列表中选择 Claude Command

    Args:
        cmd_arg: 用户输入的 --cmd 参数值，可以是:
            - 数字字符串（索引，从 0 开始）
            - 名称子串（大小写敏感匹配）

    Returns:
        (success, result):
            - success=True, result=匹配到的命令字符串
            - success=False, result=错误提示信息
    """
    commands = get_claude_commands()

    if not cmd_arg:
        return True, commands[0]

    # 尝试索引匹配
    if cmd_arg.isdigit():
        idx = int(cmd_arg)
        if 0 <= idx < len(commands):
            return True, commands[idx]
        cmd_list = ', '.join(
            '`[{}] {}`'.format(i, c) for i, c in enumerate(commands)
        )
        return False, '索引 {} 超出范围，可用命令: {}'.format(idx, cmd_list)

    # 名称子串匹配
    for cmd in commands:
        if cmd_arg in cmd:
            return True, cmd

    cmd_list = ', '.join(
        '`[{}] {}`'.format(i, c) for i, c in enumerate(commands)
    )
    return False, '未找到包含 `{}` 的命令，可用命令: {}'.format(cmd_arg, cmd_list)


def reload_config():
    """重新加载 .env 文件

    当 .env 文件内容变化后调用此函数刷新缓存。
    注意：此函数仅刷新内部缓存，不会更新模块级导出变量
    （如 REQUEST_TIMEOUT、FEISHU_APP_ID 等）。其他模块通过
    from config import XXX 获取的值仍为模块首次加载时的旧值。
    如需获取最新值，应直接调用 get_config()。
    """
    global _env_file_cache
    _env_file_cache = None
    _load_env_file()


# =============================================================================
# 导出的配置变量 (模块加载时计算)
# =============================================================================

# 服务端超时（用于清理断开连接）
REQUEST_TIMEOUT = get_request_timeout()

# 客户端超时（比服务端大，确保服务端先触发超时）
CLIENT_TIMEOUT = REQUEST_TIMEOUT + CLIENT_TIMEOUT_BUFFER

# 回调页面关闭超时
CLOSE_PAGE_TIMEOUT = get_close_page_timeout()

# VSCode URI 前缀（可选，用于从浏览器页面跳转到 VSCode）
# 示例: vscode://vscode-remote/ssh-remote+myserver 或 vscode://file
VSCODE_URI_PREFIX = get_config('VSCODE_URI_PREFIX', '')

# =============================================================================
# 飞书 OpenAPI 配置
# =============================================================================

# 飞书应用凭证
FEISHU_APP_ID = get_config('FEISHU_APP_ID', '')
FEISHU_APP_SECRET = get_config('FEISHU_APP_SECRET', '')

# Verification Token (用于验证飞书事件请求)
FEISHU_VERIFICATION_TOKEN = get_config('FEISHU_VERIFICATION_TOKEN', '')

# 消息接收者不再通过配置指定，由客户端在请求中通过 owner_id 参数提供

# 发送模式: webhook / openapi
FEISHU_SEND_MODE = get_config('FEISHU_SEND_MODE', 'webhook')

# Callback 服务对外访问地址（用于网关注册）
CALLBACK_SERVER_URL = get_config('CALLBACK_SERVER_URL', '')

# 飞书用户 ID（用于网关注册）
FEISHU_OWNER_ID = get_config('FEISHU_OWNER_ID', '')

# 飞书网关地址（分离部署时配置，网关注册接口为 {FEISHU_GATEWAY_URL}/register）
# OpenAPI 模式下未配置时，默认使用 CALLBACK_SERVER_URL（单机模式）
_FEISHU_GATEWAY_URL = get_config('FEISHU_GATEWAY_URL', '')
FEISHU_GATEWAY_URL = _FEISHU_GATEWAY_URL if _FEISHU_GATEWAY_URL else (
    CALLBACK_SERVER_URL if FEISHU_SEND_MODE == 'openapi' else ''
)
