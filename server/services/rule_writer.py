"""
Rule Writer Service - 权限规则写入服务

功能：将始终允许规则写入项目的 .claude/settings.local.json
      使用统一的工具配置（config/tools.json）
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any

from models.tool_config import get_tool_config_manager

logger = logging.getLogger(__name__)


def write_always_allow_rule(project_dir: str, tool_name: str, tool_input: Dict[str, Any]) -> bool:
    """写入始终允许规则到 .claude/settings.local.json

    功能：
        将权限规则写入项目的 settings.local.json，
        使 Claude Code 后续自动允许相同操作，无需用户再次确认。

    Args:
        project_dir: 项目目录路径
        tool_name: 工具名称（Bash, Edit, Write 等）
        tool_input: 工具输入参数

    Returns:
        bool: 是否成功写入
    """
    if not project_dir:
        logger.warning("No project_dir provided, cannot write always-allow rule")
        return False

    # 使用统一的工具配置生成规则
    config_manager = get_tool_config_manager()
    rule = config_manager.format_rule(tool_name, tool_input)

    # 读取或创建配置文件
    settings_dir = Path(project_dir) / '.claude'
    settings_file = settings_dir / 'settings.local.json'

    try:
        settings_dir.mkdir(parents=True, exist_ok=True)

        if settings_file.exists():
            with open(settings_file, 'r', encoding='utf-8') as f:
                settings = json.load(f)
        else:
            settings = {}

        # 添加规则
        if 'permissions' not in settings:
            settings['permissions'] = {}
        if 'allow' not in settings['permissions']:
            settings['permissions']['allow'] = []

        if rule not in settings['permissions']['allow']:
            settings['permissions']['allow'].append(rule)
            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2, ensure_ascii=False)
            logger.info(f"Added always-allow rule: {rule}")

        return True
    except Exception as e:
        logger.error(f"Failed to write always-allow rule: {e}")
        return False
