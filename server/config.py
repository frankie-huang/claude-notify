#!/usr/bin/env python3
"""
共享配置模块

提供 server.py 和 socket-client.py 共用的超时配置
"""

import os

# =============================================================================
# 超时配置
# =============================================================================
DEFAULT_REQUEST_TIMEOUT = 300  # 默认 5 分钟
CLIENT_TIMEOUT_BUFFER = 30     # 客户端额外缓冲 30 秒

# =============================================================================
# 回调页面关闭超时配置
# =============================================================================
DEFAULT_CLOSE_PAGE_TIMEOUT = 3  # 默认 3 秒


def get_request_timeout() -> int:
    """从环境变量读取请求超时时间

    环境变量: REQUEST_TIMEOUT（秒）
    - 必须为正整数
    - 0 或无效值会使用默认值

    Returns:
        超时秒数
    """
    env_value = os.environ.get('REQUEST_TIMEOUT', '')
    if env_value and env_value.isdigit():
        timeout = int(env_value)
        if timeout > 0:
            return timeout
    return DEFAULT_REQUEST_TIMEOUT


def get_close_page_timeout() -> int:
    """从环境变量读取回调页面自动关闭超时时间

    环境变量: CLOSE_PAGE_TIMEOUT（秒）
    - 必须为正整数
    - 0 或无效值会使用默认值（3秒）
    - 建议范围：1-10 秒

    Returns:
        超时秒数
    """
    env_value = os.environ.get('CLOSE_PAGE_TIMEOUT', '')
    if env_value and env_value.isdigit():
        timeout = int(env_value)
        if timeout > 0:
            return timeout
    return DEFAULT_CLOSE_PAGE_TIMEOUT


# 服务端超时（用于清理断开连接）
REQUEST_TIMEOUT = get_request_timeout()

# 客户端超时（比服务端大，确保服务端先触发超时）
CLIENT_TIMEOUT = REQUEST_TIMEOUT + CLIENT_TIMEOUT_BUFFER

# 回调页面关闭超时
CLOSE_PAGE_TIMEOUT = get_close_page_timeout()
