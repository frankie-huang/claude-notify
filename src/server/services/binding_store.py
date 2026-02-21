"""BindingStore - owner_id 到 callback_url 的绑定存储

归属端: 飞书网关
使用方: feishu.py, register.py（网关内部逻辑），callback.py 中的网关侧路由（/feishu/send）

维护飞书用户 ID 到 Callback 后端 URL 的映射关系，用于网关注册和双向认证。
Callback 后端的路由和逻辑不应直接调用此 Store。
"""

import json
import os
import tempfile
import threading
import time
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class BindingStore:
    """管理 owner_id -> callback_url + auth_token 的绑定

    绑定结构:
    {
        "ou_xxx": {
            "callback_url": "https://callback.example.com",
            "auth_token": "abc123.def456",
            "updated_at": 1706745600,
            "registered_ip": "1.2.3.4"
        }
    }
    """

    _instance = None  # type: Optional[BindingStore]
    _lock = threading.Lock()

    def __init__(self, data_dir: str):
        """初始化 BindingStore

        Args:
            data_dir: 数据存储目录
        """
        self._data_dir = data_dir
        self._file_path = os.path.join(data_dir, 'bindings.json')
        self._file_lock = threading.Lock()
        os.makedirs(data_dir, exist_ok=True)
        logger.info(f"[binding-store] Initialized with data_dir={data_dir}")

    @classmethod
    def initialize(cls, data_dir: str) -> 'BindingStore':
        """初始化单例实例

        Args:
            data_dir: 数据存储目录

        Returns:
            BindingStore 实例
        """
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(data_dir)
            return cls._instance

    @classmethod
    def get_instance(cls) -> Optional['BindingStore']:
        """获取单例实例

        Returns:
            BindingStore 实例，未初始化返回 None
        """
        return cls._instance

    def get(self, owner_id: str) -> Optional[Dict[str, Any]]:
        """获取绑定信息

        Args:
            owner_id: 飞书用户 ID

        Returns:
            绑定信息字典，不存在返回 None
        """
        with self._file_lock:
            try:
                data = self._load()
                return data.get(owner_id)
            except Exception as e:
                logger.error(f"[binding-store] Failed to get binding: {e}")
                return None

    def upsert(
        self,
        owner_id: str,
        callback_url: str,
        auth_token: str,
        registered_ip: str = ''
    ) -> bool:
        """创建或更新绑定

        Args:
            owner_id: 飞书用户 ID
            callback_url: Callback 后端 URL
            auth_token: 认证令牌
            registered_ip: 注册来源 IP

        Returns:
            是否保存成功
        """
        with self._file_lock:
            try:
                data = self._load()
                existing = data.get(owner_id)
                # 清除其他用户对同一 callback_url 的旧绑定
                stale_owners = [
                    oid for oid, info in data.items()
                    if oid != owner_id and info.get('callback_url') == callback_url
                ]
                for oid in stale_owners:
                    del data[oid]
                    logger.info(
                        f"[binding-store] Removed stale binding: {oid} -> {callback_url}"
                    )
                data[owner_id] = {
                    'callback_url': callback_url,
                    'auth_token': auth_token,
                    'updated_at': int(time.time()),
                    'registered_ip': registered_ip
                }
                result = self._save(data)
                if result:
                    if existing:
                        logger.info(
                            f"[binding-store] Updated binding: {owner_id} -> {callback_url}"
                        )
                    else:
                        logger.info(
                            f"[binding-store] Created binding: {owner_id} -> {callback_url}"
                        )
                return result
            except Exception as e:
                logger.error(f"[binding-store] Failed to upsert binding: {e}")
                return False

    def delete(self, owner_id: str) -> bool:
        """删除绑定

        Args:
            owner_id: 飞书用户 ID

        Returns:
            是否删除成功
        """
        with self._file_lock:
            try:
                data = self._load()
                if owner_id not in data:
                    return True
                del data[owner_id]
                result = self._save(data)
                if result:
                    logger.info(f"[binding-store] Deleted binding: {owner_id}")
                return result
            except Exception as e:
                logger.error(f"[binding-store] Failed to delete binding: {e}")
                return False

    def _load(self) -> Dict[str, Any]:
        """加载绑定数据

        Returns:
            绑定数据字典
        """
        if not os.path.exists(self._file_path):
            return {}
        try:
            with open(self._file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.warning(f"[binding-store] Invalid JSON in {self._file_path}, starting fresh")
            return {}
        except IOError as e:
            logger.error(f"[binding-store] Failed to load: {e}")
            return {}

    def _save(self, data: Dict[str, Any]) -> bool:
        """保存绑定数据（原子写入）

        Args:
            data: 绑定数据字典

        Returns:
            是否保存成功
        """
        try:
            tmp_fd, tmp_path = tempfile.mkstemp(dir=self._data_dir, suffix='.tmp')
            with os.fdopen(tmp_fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self._file_path)
            return True
        except (IOError, OSError) as e:
            logger.error(f"[binding-store] Failed to save: {e}")
            return False
