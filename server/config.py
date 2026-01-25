#!/usr/bin/env python3
"""
共享配置模块

提供统一的配置读取接口，支持从 .env 文件和环境变量读取配置

优先级: .env 文件 > 环境变量 > 默认值
"""

import os
from typing import Optional

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

    # 获取项目根目录 (server 的上级目录)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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


def reload_config():
    """重新加载 .env 文件

    当 .env 文件内容变化后调用此函数刷新缓存
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
