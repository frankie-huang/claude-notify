"""
共享日志配置模块

从 shared/logging.json 读取统一日志配置
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

# 默认配置
DEFAULT_CONFIG = {
    "log_dir_relative": "log",
    "date_format": "%Y%m%d",
    "datetime_format": "%Y-%m-%d %H:%M:%S",
    "file_patterns": {
        "hook": "hook_{date}.log",
        "server": "callback_{date}.log",
        "socket_client": "socket_client_{date}.log"
    },
    "formats": {
        "python": "[%(process)d] %(asctime)s.%(msecs)03d [%(levelname)s] %(message)s",
        "python_datefmt": "%Y-%m-%d %H:%M:%S"
    },
    "levels": {
        "default": "DEBUG"
    }
}

# 配置文件路径
CONFIG_FILE = Path(__file__).parent / "logging.json"


def get_logging_config() -> dict:
    """获取日志配置

    优先从 shared/logging.json 读取，如果不存在则使用默认配置

    Returns:
        日志配置字典
    """
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                # 合并默认配置（确保所有必需字段存在）
                for key, value in DEFAULT_CONFIG.items():
                    if key not in config:
                        config[key] = value
                    elif isinstance(value, dict) and isinstance(config.get(key), dict):
                        for k, v in value.items():
                            if k not in config[key]:
                                config[key][k] = v
                return config
        except Exception:
            pass
    return DEFAULT_CONFIG


def get_log_file_path(component: str) -> str:
    """获取指定组件的日志文件路径

    Args:
        component: 组件名称 (hook, server, socket_client)

    Returns:
        日志文件的绝对路径
    """
    config = get_logging_config()

    # 获取项目根目录 (src/shared -> src -> project_root)
    project_root = Path(__file__).parent.parent.parent

    # 日志目录
    log_dir = project_root / config.get("log_dir_relative", "log")
    log_dir.mkdir(parents=True, exist_ok=True)

    # 日期格式
    date_format = config.get("date_format", "%Y%m%d")
    date_str = time.strftime(date_format)

    # 文件名模式
    file_patterns = config.get("file_patterns", {})
    pattern = file_patterns.get(component, f"{component}_{{date}}.log")
    filename = pattern.replace("{date}", date_str)

    return str(log_dir / filename)


def setup_logging(component: str, logger: Optional[logging.Logger] = None) -> logging.Logger:
    """设置日志记录器

    Args:
        component: 组件名称 (hook, server, socket_client)
        logger: 可选的现有 logger，如果为 None 则创建新的

    Returns:
        配置好的 logger
    """
    config = get_logging_config()

    # 获取或创建 logger
    if logger is None:
        logger = logging.getLogger(component)

    # 设置日志级别
    levels = config.get("levels", {})
    level_name = levels.get(component, levels.get("default", "DEBUG"))
    level = getattr(logging, level_name.upper(), logging.DEBUG)
    logger.setLevel(level)

    # 日志格式
    formats = config.get("formats", {})
    log_format = formats.get("python", DEFAULT_CONFIG["formats"]["python"])
    date_format = formats.get("python_datefmt", DEFAULT_CONFIG["formats"]["python_datefmt"])

    formatter = logging.Formatter(log_format, datefmt=date_format)

    # 添加文件处理器
    log_file = get_log_file_path(component)
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # 添加控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger
