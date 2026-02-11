"""目录历史记录存储

Callback 后端使用此服务维护用户的工作目录使用历史，
用于在创建新会话时提供常用目录推荐。
"""

import json
import os
import threading
import time
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# 目录历史配置
MAX_DIRS = 20  # 最多保留的目录数量
DIR_EXPIRE_SECONDS = 30 * 24 * 3600  # 30天过期


class DirHistoryStore:
    """管理工作目录使用历史

    数据结构:
    {
        "/path/to/project": {
            "count": 5,
            "last_used": 1706745600
        }
    }
    """

    _instance = None  # type: Optional[DirHistoryStore]
    _lock = threading.Lock()

    def __init__(self, data_dir: str):
        """初始化 DirHistoryStore

        Args:
            data_dir: 数据存储目录
        """
        self._data_dir = data_dir
        self._file_path = os.path.join(data_dir, 'dir_history.json')
        self._file_lock = threading.Lock()
        os.makedirs(data_dir, exist_ok=True)
        logger.info(f"[dir-history-store] Initialized with data_dir={data_dir}")

    @classmethod
    def initialize(cls, data_dir: str) -> 'DirHistoryStore':
        """初始化单例实例

        Args:
            data_dir: 数据存储目录

        Returns:
            DirHistoryStore 实例
        """
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(data_dir)
            return cls._instance

    @classmethod
    def get_instance(cls) -> Optional['DirHistoryStore']:
        """获取单例实例

        Returns:
            DirHistoryStore 实例，未初始化返回 None
        """
        return cls._instance

    def record_usage(self, project_dir: str) -> bool:
        """记录目录使用

        Args:
            project_dir: 项目工作目录

        Returns:
            是否保存成功
        """
        if not project_dir:
            return False

        with self._file_lock:
            try:
                data = self._load()
                now = int(time.time())

                # 更新目录使用记录
                if project_dir in data:
                    data[project_dir]['count'] += 1
                    data[project_dir]['last_used'] = now
                else:
                    data[project_dir] = {
                        'count': 1,
                        'last_used': now
                    }

                # 清理过期数据
                data = self._cleanup(data)

                result = self._save(data)
                if result:
                    logger.info(f"[dir-history-store] Recorded usage: {project_dir}")
                return result
            except Exception as e:
                logger.error(f"[dir-history-store] Failed to record usage: {e}")
                return False

    def get_recent_dirs(self, limit: int = 5) -> List[str]:
        """获取近期常用目录列表

        Args:
            limit: 最多返回的目录数量

        Returns:
            目录路径列表，按使用频率和时间排序，过滤掉不存在的目录
        """
        with self._file_lock:
            try:
                data = self._load()

                # 内存中过滤过期数据（不持久化，实际清理在 record_usage 写入时执行）
                data = self._cleanup(data)

                # 过滤掉不存在的目录
                valid_dirs = {
                    path: info for path, info in data.items()
                    if os.path.isdir(path)
                }

                # 如果检测到已删除的目录，立即持久化清理
                removed_count = len(data) - len(valid_dirs)
                if removed_count > 0:
                    removed_paths = [p for p in data if p not in valid_dirs]
                    logger.info(f"[dir-history-store] Cleaning up {removed_count} non-existent dirs: {removed_paths}")
                    self._save(valid_dirs)

                # 排序：优先按使用次数降序，次数相同按最近使用时间降序
                sorted_dirs = sorted(
                    valid_dirs.items(),
                    key=lambda x: (x[1]['count'], x[1]['last_used']),
                    reverse=True
                )

                # 返回前 N 个目录路径
                return [dir_path for dir_path, _ in sorted_dirs[:limit]]
            except Exception as e:
                logger.error(f"[dir-history-store] Failed to get recent dirs: {e}")
                return []

    def _load(self) -> Dict[str, Any]:
        """加载目录历史数据

        Returns:
            目录历史数据字典
        """
        if not os.path.exists(self._file_path):
            return {}
        try:
            with open(self._file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.warning(f"[dir-history-store] Invalid JSON in {self._file_path}, starting fresh")
            return {}
        except IOError as e:
            logger.error(f"[dir-history-store] Failed to load: {e}")
            return {}

    def _save(self, data: Dict[str, Any]) -> bool:
        """保存目录历史数据

        Args:
            data: 目录历史数据字典

        Returns:
            是否保存成功
        """
        try:
            with open(self._file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except IOError as e:
            logger.error(f"[dir-history-store] Failed to save: {e}")
            return False

    def _cleanup(self, dirs: Dict[str, Any]) -> Dict[str, Any]:
        """清理目录历史数据

        清理规则：
        1. 删除超过 30 天未使用的目录
        2. 最多保留 20 条记录

        Args:
            dirs: 目录历史字典

        Returns:
            清理后的目录历史字典
        """
        now = time.time()

        # 删除过期目录
        expired = [
            path for path, info in dirs.items()
            if now - info.get('last_used', 0) > DIR_EXPIRE_SECONDS
        ]
        for path in expired:
            del dirs[path]

        # 限制数量：保留最近使用的 N 条
        if len(dirs) > MAX_DIRS:
            # 按最近使用时间排序，保留最新的
            sorted_items = sorted(
                dirs.items(),
                key=lambda x: x[1]['last_used'],
                reverse=True
            )
            dirs = dict(sorted_items[:MAX_DIRS])

        return dirs
