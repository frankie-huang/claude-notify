"""Session-Chat 映射存储

Callback 后端使用此服务维护会话与群聊的映射关系，
用于确定消息发送的目标群聊。
"""

import json
import os
import tempfile
import threading
import time
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class SessionChatStore:
    """管理 session_id -> chat_id 的存储

    Callback 后端使用此服务维护会话与群聊的映射关系，
    用于确定消息发送的目标群聊。
    """

    _instance = None  # type: Optional[SessionChatStore]
    _lock = threading.Lock()

    # 过期时间（秒），默认 7 天
    EXPIRE_SECONDS = 7 * 24 * 3600

    def __init__(self, data_dir: str):
        """初始化 SessionChatStore

        Args:
            data_dir: 数据存储目录
        """
        self._data_dir = data_dir
        self._file_path = os.path.join(data_dir, 'session_chats.json')
        self._file_lock = threading.Lock()
        os.makedirs(data_dir, exist_ok=True)
        logger.info(f"[session-chat-store] Initialized with data_dir={data_dir}")

    @classmethod
    def initialize(cls, data_dir: str) -> 'SessionChatStore':
        """初始化单例实例

        Args:
            data_dir: 数据存储目录

        Returns:
            SessionChatStore 实例
        """
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(data_dir)
            return cls._instance

    @classmethod
    def get_instance(cls) -> Optional['SessionChatStore']:
        """获取单例实例

        Returns:
            SessionChatStore 实例，未初始化返回 None
        """
        return cls._instance

    def save(self, session_id: str, chat_id: str, claude_command: str = '') -> bool:
        """保存 session_id -> chat_id 映射

        Args:
            session_id: Claude 会话 ID
            chat_id: 飞书群聊 ID
            claude_command: 该 session 使用的 Claude 命令（可选）

        Returns:
            是否保存成功
        """
        with self._file_lock:
            try:
                data = self._load()
                entry = {
                    'chat_id': chat_id,
                    'updated_at': int(time.time())
                }
                if claude_command:
                    entry['claude_command'] = claude_command
                # 保留已有的 claude_command（如果本次未指定但已有记录）
                elif session_id in data and 'claude_command' in data[session_id]:
                    entry['claude_command'] = data[session_id]['claude_command']
                data[session_id] = entry
                result = self._save(data)
                if result:
                    logger.info(f"[session-chat-store] Saved mapping: {session_id} -> {chat_id}")
                return result
            except Exception as e:
                logger.error(f"[session-chat-store] Failed to save mapping: {e}")
                return False

    def get(self, session_id: str) -> Optional[str]:
        """获取 session_id 对应的 chat_id

        Args:
            session_id: Claude 会话 ID

        Returns:
            群聊 chat_id，不存在或已过期返回 None
        """
        with self._file_lock:
            try:
                data = self._load()
                item = data.get(session_id)
                if not item:
                    return None

                # 检查过期
                if time.time() - item.get('updated_at', 0) > self.EXPIRE_SECONDS:
                    logger.info(f"[session-chat-store] Mapping expired: {session_id}")
                    del data[session_id]
                    self._save(data)
                    return None

                return item.get('chat_id')
            except Exception as e:
                logger.error(f"[session-chat-store] Failed to get mapping: {e}")
                return None

    def get_command(self, session_id: str) -> Optional[str]:
        """获取 session_id 对应的 claude_command

        Args:
            session_id: Claude 会话 ID

        Returns:
            claude_command 字符串，不存在或已过期返回 None
        """
        with self._file_lock:
            try:
                data = self._load()
                item = data.get(session_id)
                if not item:
                    return None

                # 检查过期
                if time.time() - item.get('updated_at', 0) > self.EXPIRE_SECONDS:
                    return None

                return item.get('claude_command')
            except Exception as e:
                logger.error(f"[session-chat-store] Failed to get command: {e}")
                return None

    def cleanup_expired(self) -> int:
        """清理过期数据

        Returns:
            清理的条目数量
        """
        with self._file_lock:
            try:
                data = self._load()
                now = time.time()
                expired = [
                    k for k, v in data.items()
                    if now - v.get('updated_at', 0) > self.EXPIRE_SECONDS
                ]
                for k in expired:
                    del data[k]
                if expired:
                    self._save(data)
                    logger.info(f"[session-chat-store] Cleaned {len(expired)} expired mappings")
                return len(expired)
            except Exception as e:
                logger.error(f"[session-chat-store] Failed to cleanup: {e}")
                return 0

    def _load(self) -> Dict[str, Any]:
        """加载映射数据

        Returns:
            映射数据字典
        """
        if not os.path.exists(self._file_path):
            return {}
        try:
            with open(self._file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.warning(f"[session-chat-store] Invalid JSON in {self._file_path}, starting fresh")
            return {}
        except IOError as e:
            logger.error(f"[session-chat-store] Failed to load: {e}")
            return {}

    def _save(self, data: Dict[str, Any]) -> bool:
        """保存映射数据（原子写入）

        Args:
            data: 映射数据字典

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
            logger.error(f"[session-chat-store] Failed to save: {e}")
            return False
