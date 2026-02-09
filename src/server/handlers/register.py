"""Gateway Register Handler - 网关注册接口处理器

网关注册流程的处理器，飞书网关和 Callback 后端都会用到。

飞书网关使用：
    - handle_register_request(): 接收 Callback 后端的注册请求
    - handle_authorization_decision(): 处理用户授权决策（允许/拒绝）

Callback 后端使用：
    - AuthTokenStore: 存储 auth_token 的单例类
    - handle_register_callback(): 接收网关的 auth_token 通知
    - handle_check_owner_id(): 验证 owner_id 所属权
"""

import json
import logging
import os
import socket
import threading
import time
import urllib.request
import urllib.error
from typing import Tuple, Dict, Any, Optional

logger = logging.getLogger(__name__)

# HTTP 请求超时（秒）
HTTP_TIMEOUT = 10


class AuthTokenStore:
    """管理 auth_token 的存储

    用于存储网关注册后返回的 auth_token。
    """

    _instance = None  # type: Optional[AuthTokenStore]
    _lock = threading.Lock()
    _token = None  # type: Optional[str]

    def __init__(self, data_dir: str):
        """初始化 AuthTokenStore

        Args:
            data_dir: 数据存储目录
        """
        self._data_dir = data_dir
        self._file_path = os.path.join(data_dir, 'auth_token.json')
        self._file_lock = threading.Lock()
        os.makedirs(data_dir, exist_ok=True)
        logger.info(f"[auth-token-store] Initialized with data_dir={data_dir}")

        # 启动时尝试加载已有的 token
        self._load()

    @classmethod
    def initialize(cls, data_dir: str) -> 'AuthTokenStore':
        """初始化单例实例

        Args:
            data_dir: 数据存储目录

        Returns:
            AuthTokenStore 实例
        """
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(data_dir)
            return cls._instance

    @classmethod
    def get_instance(cls) -> Optional['AuthTokenStore']:
        """获取单例实例

        Returns:
            AuthTokenStore 实例，未初始化返回 None
        """
        return cls._instance

    def save(self, owner_id: str, auth_token: str) -> bool:
        """保存 auth_token

        Args:
            owner_id: 飞书用户 ID
            auth_token: 认证令牌

        Returns:
            是否保存成功
        """
        with self._file_lock:
            try:
                AuthTokenStore._token = auth_token
                data = {
                    'owner_id': owner_id,
                    'auth_token': auth_token,
                    'updated_at': int(time.time())
                }
                return self._save(data)
            except Exception as e:
                logger.error(f"[auth-token-store] Failed to save token: {e}")
                return False

    def get(self) -> str:
        """获取存储的 auth_token

        Returns:
            存储的 auth_token，不存在返回空字符串
        """
        return AuthTokenStore._token or ''

    def _load(self):
        """从文件加载 token"""
        if not os.path.exists(self._file_path):
            return

        try:
            with open(self._file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                AuthTokenStore._token = data.get('auth_token', '')
                if AuthTokenStore._token:
                    logger.info(f"[auth-token-store] Loaded token from file")
        except Exception as e:
            logger.warning(f"[auth-token-store] Failed to load token: {e}")

    def _save(self, data: Dict[str, Any]) -> bool:
        """保存数据到文件

        Args:
            data: 数据字典

        Returns:
            是否保存成功
        """
        try:
            with open(self._file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except IOError as e:
            logger.error(f"[auth-token-store] Failed to save: {e}")
            return False


class ChatIdStore:
    """管理 session_id -> chat_id 的存储

    Callback 后端使用此服务维护会话与群聊的映射关系，
    用于确定消息发送的目标群聊。
    """

    _instance = None  # type: Optional[ChatIdStore]
    _lock = threading.Lock()

    # 过期时间（秒），默认 7 天
    EXPIRE_SECONDS = 7 * 24 * 3600

    def __init__(self, data_dir: str):
        """初始化 ChatIdStore

        Args:
            data_dir: 数据存储目录
        """
        self._data_dir = data_dir
        self._file_path = os.path.join(data_dir, 'session_chats.json')
        self._file_lock = threading.Lock()
        os.makedirs(data_dir, exist_ok=True)
        logger.info(f"[chat-id-store] Initialized with data_dir={data_dir}")

    @classmethod
    def initialize(cls, data_dir: str) -> 'ChatIdStore':
        """初始化单例实例

        Args:
            data_dir: 数据存储目录

        Returns:
            ChatIdStore 实例
        """
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(data_dir)
            return cls._instance

    @classmethod
    def get_instance(cls) -> Optional['ChatIdStore']:
        """获取单例实例

        Returns:
            ChatIdStore 实例，未初始化返回 None
        """
        return cls._instance

    def save(self, session_id: str, chat_id: str) -> bool:
        """保存 session_id -> chat_id 映射

        Args:
            session_id: Claude 会话 ID
            chat_id: 飞书群聊 ID

        Returns:
            是否保存成功
        """
        with self._file_lock:
            try:
                data = self._load()
                data[session_id] = {
                    'chat_id': chat_id,
                    'updated_at': int(time.time())
                }
                result = self._save(data)
                if result:
                    logger.info(f"[chat-id-store] Saved mapping: {session_id} -> {chat_id}")
                return result
            except Exception as e:
                logger.error(f"[chat-id-store] Failed to save mapping: {e}")
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
                    logger.info(f"[chat-id-store] Mapping expired: {session_id}")
                    del data[session_id]
                    self._save(data)
                    return None

                return item.get('chat_id')
            except Exception as e:
                logger.error(f"[chat-id-store] Failed to get mapping: {e}")
                return None

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
            logger.warning(f"[chat-id-store] Invalid JSON in {self._file_path}, starting fresh")
            return {}
        except IOError as e:
            logger.error(f"[chat-id-store] Failed to load: {e}")
            return {}

    def _save(self, data: Dict[str, Any]) -> bool:
        """保存映射数据

        Args:
            data: 映射数据字典

        Returns:
            是否保存成功
        """
        try:
            with open(self._file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except IOError as e:
            logger.error(f"[chat-id-store] Failed to save: {e}")
            return False


def handle_register_request(data: dict, client_ip: str = '') -> Tuple[bool, dict]:
    """处理 Callback 后端的注册请求

    网关立即返回成功，后续异步处理：
        - 已绑定：直接调用 Callback 后端的 /register-callback
        - 未绑定：发送飞书授权卡片

    Args:
        data: 请求数据
            - callback_url: Callback 后端 URL（必需）
            - owner_id: 飞书用户 ID（必需）
        client_ip: 客户端 IP 地址

    Returns:
        (success, response): success 表示是否处理成功，response 是响应数据
    """
    callback_url = data.get('callback_url', '')
    owner_id = data.get('owner_id', '')

    # 验证参数
    if not callback_url or not owner_id:
        logger.warning("[register] Missing params: callback_url or owner_id")
        return True, {
            'success': False,
            'error': 'missing required fields: callback_url, owner_id'
        }

    logger.info(f"[register] Registration request: owner_id={owner_id}, callback_url={callback_url}, ip={client_ip}")

    # 在后台线程中处理注册逻辑（异步）
    _run_in_background(_process_registration, (callback_url, owner_id, client_ip))

    # 立即返回成功
    return True, {
        'success': True,
        'message': 'Registration request received, processing in background'
    }


def handle_register_callback(data: dict) -> Tuple[bool, dict]:
    """处理网关注册回调（网关调用 Callback 后端）

    Callback 后端接收网关的 auth_token 通知并存储。

    Args:
        data: 请求数据
            - owner_id: 飞书用户 ID
            - auth_token: 认证令牌
            - gateway_version: 网关版本（可选）

    Returns:
        (success, response)
    """
    from config import get_config

    owner_id = data.get('owner_id', '')
    auth_token = data.get('auth_token', '')
    gateway_version = data.get('gateway_version', '')

    # 获取配置的 owner_id
    config_owner_id = get_config('FEISHU_OWNER_ID', '')

    if not owner_id or not auth_token:
        logger.warning("[register-callback] Missing params: owner_id or auth_token")
        return True, {
            'success': False,
            'error': 'missing required fields: owner_id, auth_token'
        }

    # 验证 owner_id 是否与配置一致
    if config_owner_id and owner_id != config_owner_id:
        logger.warning(
            f"[register-callback] owner_id mismatch: received={owner_id}, config={config_owner_id}"
        )
        return True, {
            'success': False,
            'error': 'owner_id mismatch'
        }

    logger.info(
        f"[register-callback] Storing auth_token for owner_id={owner_id}, "
        f"gateway_version={gateway_version}"
    )

    # 存储 auth_token
    store = AuthTokenStore.get_instance()
    if store:
        if store.save(owner_id, auth_token):
            logger.info(f"[register-callback] Auth token stored successfully")
            return True, {
                'success': True,
                'message': 'Registration successful'
            }
        else:
            return True, {
                'success': False,
                'error': 'Failed to store token'
            }
    else:
        logger.warning("[register-callback] AuthTokenStore not initialized")
        return True, {
            'success': False,
            'error': 'AuthTokenStore not initialized'
        }


def handle_check_owner_id(data: dict) -> Tuple[bool, dict]:
    """处理 owner_id 验证请求（网关调用 Callback 后端）

    网关在发送授权卡片前，先验证 callback_url 是否属于该 owner_id。
    这防止了恶意注册请求。

    Args:
        data: 请求数据
            - owner_id: 飞书用户 ID

    Returns:
        (success, response): response 包含 is_owner 字段
    """
    from config import get_config

    request_owner_id = data.get('owner_id', '')
    config_owner_id = get_config('FEISHU_OWNER_ID', '')

    logger.info(f"[check-owner-id] Request: owner_id={request_owner_id}")

    # 验证 owner_id 是否与配置一致
    is_owner = bool(request_owner_id and request_owner_id == config_owner_id)

    if is_owner:
        logger.info(f"[check-owner-id] Verification passed")
    else:
        logger.warning(
            f"[check-owner-id] Verification failed: request={request_owner_id}, config={config_owner_id}"
        )

    return True, {
        'success': True,
        'is_owner': is_owner
    }


def _process_registration(callback_url: str, owner_id: str, client_ip: str):
    """处理注册逻辑（后台线程）

    1. 查询绑定关系
    2. 已绑定且 callback_url 相同：直接调用 /register-callback 通知新 token
    3. 已绑定但 callback_url 不同：发送飞书授权卡片让用户确认是否更新
    4. 未绑定：先验证 callback_url 所属，再发送飞书授权卡片

    注意：auth_token 不再提前生成，而是在用户点击允许后实时生成。

    Args:
        callback_url: Callback 后端 URL
        owner_id: 飞书用户 ID
        client_ip: 客户端 IP
    """
    from services.binding_store import BindingStore
    from services.auth_token import generate_auth_token
    from services.feishu_api import FeishuAPIService
    from config import FEISHU_VERIFICATION_TOKEN

    # 验证配置
    if not FEISHU_VERIFICATION_TOKEN:
        logger.error("[register] FEISHU_VERIFICATION_TOKEN not configured")
        return

    # 查询现有绑定
    store = BindingStore.get_instance()
    if not store:
        logger.error("[register] BindingStore not initialized")
        return

    binding = store.get(owner_id)

    if binding:
        # 已绑定，检查 callback_url 是否一致
        bound_callback_url = binding.get('callback_url', '')
        if bound_callback_url == callback_url:
            # callback_url 一致：直接更新 token（无需用户确认）
            logger.info(f"[register] Existing binding with same callback_url, updating token")
            auth_token = generate_auth_token(FEISHU_VERIFICATION_TOKEN, owner_id)
            _notify_callback(callback_url, owner_id, auth_token, client_ip)
            store.upsert(owner_id, callback_url, auth_token, client_ip)
        else:
            # callback_url 不同：发送授权卡片让用户确认是否更换设备
            # 不提前生成 auth_token，等用户批准后再生成
            logger.info(
                f"[register] Existing binding with different callback_url: "
                f"old={bound_callback_url}, new={callback_url}"
            )
            _send_authorization_card(callback_url, owner_id, client_ip, old_callback_url=bound_callback_url)
    else:
        # 未绑定：先验证 callback_url 是否属于该 owner_id
        logger.info(f"[register] No existing binding, verifying callback_url ownership")
        if not _check_owner_id(callback_url, owner_id):
            logger.warning(
                f"[register] Owner verification failed: callback_url={callback_url}, owner_id={owner_id}. "
                f"This may be a malicious registration request."
            )
            return
        # 验证通过，发送飞书授权卡片
        # 不提前生成 auth_token，等用户批准后再生成
        _send_authorization_card(callback_url, owner_id, client_ip)


def _check_owner_id(callback_url: str, owner_id: str) -> bool:
    """验证 callback_url 是否属于该 owner_id

    调用 Callback 后端的 /check-owner-id 接口进行验证。

    Args:
        callback_url: Callback 后端 URL
        owner_id: 飞书用户 ID

    Returns:
        True 表示验证通过，False 表示验证失败
    """
    api_url = f"{callback_url.rstrip('/')}/check-owner-id"

    request_data = {
        'owner_id': owner_id
    }

    logger.info(f"[register] Checking owner_id: {api_url}")

    try:
        req = urllib.request.Request(
            api_url,
            data=json.dumps(request_data).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )

        # 创建无代理的 opener
        no_proxy_handler = urllib.request.ProxyHandler({})
        opener = urllib.request.build_opener(no_proxy_handler)
        with opener.open(req, timeout=HTTP_TIMEOUT) as response:
            response_data = json.loads(response.read().decode('utf-8'))
            is_owner = response_data.get('is_owner', False)
            logger.info(f"[register] Owner check result: {is_owner}")
            return is_owner

    except urllib.error.HTTPError as e:
        logger.error(f"[register] Owner check HTTP error: {e.code} {e.reason}")
        return False
    except urllib.error.URLError as e:
        logger.error(f"[register] Owner check URL error: {e.reason}")
        return False
    except socket.timeout:
        logger.error("[register] Owner check timeout")
        return False
    except Exception as e:
        logger.error(f"[register] Owner check error: {e}")
        return False


def _notify_callback(callback_url: str, owner_id: str, auth_token: str, client_ip: str):
    """通知 Callback 后端 auth_token

    Args:
        callback_url: Callback 后端 URL
        owner_id: 飞书用户 ID
        auth_token: 认证令牌
        client_ip: 客户端 IP
    """
    api_url = f"{callback_url.rstrip('/')}/register-callback"

    request_data = {
        'owner_id': owner_id,
        'auth_token': auth_token,
        'gateway_version': '1.0.0'
    }

    logger.info(f"[register] Calling {api_url}")

    try:
        req = urllib.request.Request(
            api_url,
            data=json.dumps(request_data).encode('utf-8'),
            headers={
                'Content-Type': 'application/json',
                'X-Auth-Token': auth_token
            },
            method='POST'
        )

        # 创建无代理的 opener
        no_proxy_handler = urllib.request.ProxyHandler({})
        opener = urllib.request.build_opener(no_proxy_handler)
        with opener.open(req, timeout=HTTP_TIMEOUT) as response:
            response_data = json.loads(response.read().decode('utf-8'))
            logger.info(f"[register] Callback response: {response_data}")

    except urllib.error.HTTPError as e:
        logger.error(f"[register] Callback HTTP error: {e.code} {e.reason}")
    except urllib.error.URLError as e:
        logger.error(f"[register] Callback URL error: {e.reason}")
    except socket.timeout:
        logger.error("[register] Callback timeout")
    except Exception as e:
        logger.error(f"[register] Callback error: {e}")


def _send_authorization_card(
    callback_url: str,
    owner_id: str,
    client_ip: str,
    old_callback_url: str = ''
):
    """发送飞书授权卡片

    注意：不在卡片中嵌入 auth_token，而是等用户授权后再实时生成。
    用户点击允许时会验证 operator_id == owner_id，确保本人操作。

    Args:
        callback_url: Callback 后端 URL
        owner_id: 飞书用户 ID
        client_ip: 客户端 IP
        old_callback_url: 旧的 callback_url（如果有，表示更换设备场景）
    """
    from services.feishu_api import FeishuAPIService

    service = FeishuAPIService.get_instance()
    if not service or not service.enabled:
        logger.warning("[register] FeishuAPIService not enabled, cannot send authorization card")
        return

    # 构建卡片内容
    if old_callback_url:
        # 更换设备场景
        title = "Callback 后端更换设备请求"
        content = (
            f"**旧设备**: `{old_callback_url}`\n"
            f"**新设备**: `{callback_url}`\n"
            f"**来源 IP**: `{client_ip}`\n\n"
            f"是否允许更换到新设备？"
        )
    else:
        # 新设备注册场景
        title = "新的 Callback 后端注册请求"
        content = (
            f"**来源 IP**: `{client_ip}`\n"
            f"**Callback URL**: `{callback_url}`\n\n"
            f"是否允许该后端接收你的飞书消息？"
        )

    # 构建授权卡片
    card = {
        "schema": "2.0",
        "config": {
            "wide_screen_mode": True
        },
        "header": {
            "title": {
                "tag": "plain_text",
                "content": title
            },
            "template": "blue"
        },
        "body": {
            "direction": "vertical",
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": content
                    }
                },
                {
                    "tag": "hr"
                },
                {
                    "tag": "column_set",
                    "flex_mode": "none",
                    "horizontal_spacing": "8px",
                    "background_style": "default",
                    "columns": [
                        {
                            "tag": "column",
                            "width": "weighted",
                            "vertical_align": "top",
                            "elements": [
                                {
                                    "tag": "button",
                                    "text": {
                                        "tag": "plain_text",
                                        "content": "允许"
                                    },
                                    "type": "primary",
                                    "behaviors": [
                                        {
                                            "type": "callback",
                                            "value": {
                                                "action": "approve_register",
                                                "callback_url": callback_url,
                                                "owner_id": owner_id,
                                                "request_ip": client_ip,
                                                "old_callback_url": old_callback_url
                                            }
                                        }
                                    ]
                                }
                            ]
                        },
                        {
                            "tag": "column",
                            "width": "weighted",
                            "vertical_align": "top",
                            "elements": [
                                {
                                    "tag": "button",
                                    "text": {
                                        "tag": "plain_text",
                                        "content": "拒绝"
                                    },
                                    "type": "danger",
                                    "behaviors": [
                                        {
                                            "type": "callback",
                                            "value": {
                                                "action": "deny_register",
                                                "callback_url": callback_url,
                                                "owner_id": owner_id
                                            }
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                }
            ]
        }
    }

    success, result = service.send_card(json.dumps(card, ensure_ascii=False), receive_id=owner_id)

    if success:
        logger.info(f"[register] Authorization card sent to {owner_id}")
    else:
        logger.error(f"[register] Failed to send authorization card: {result}")


def _build_register_status_card(
    title: str,
    content: str,
    template: str,
    button: dict = None
) -> Dict[str, Any]:
    """构建注册授权状态卡片（用于卡片回调响应）

    飞书卡片回调响应格式要求：
    {
      "type": "raw",
      "data": { ... schema 2.0 卡片数据 ... }
    }

    Args:
        title: 卡片标题
        content: 卡片内容（支持 Markdown）
        template: 标题模板颜色（green/red/blue等）
        button: 可选按钮配置（包含 behaviors 格式）

    Returns:
        卡片字典（包含 type 和 data）
    """
    elements = [
        {
            'tag': 'div',
            'text': {
                'tag': 'lark_md',
                'content': content
            }
        }
    ]

    if button:
        elements.append({'tag': 'hr'})
        elements.append({
            'tag': 'column_set',
            'flex_mode': 'none',
            'horizontal_spacing': '8px',
            'background_style': 'default',
            'columns': [
                {
                    'tag': 'column',
                    'width': 'weighted',
                    'vertical_align': 'top',
                    'elements': [
                        {
                            'tag': button.get('tag', 'button'),
                            'text': button.get('text'),
                            'type': button.get('type'),
                            'behaviors': [
                                {
                                    'type': 'callback',
                                    'value': button.get('value')
                                }
                            ]
                        }
                    ]
                }
            ]
        })

    return {
        'type': 'raw',
        'data': {
            'schema': '2.0',
            'config': {'wide_screen_mode': True},
            'header': {
                'title': {'tag': 'plain_text', 'content': title},
                'template': template
            },
            'body': {
                'direction': 'vertical',
                'elements': elements
            }
        }
    }


def handle_authorization_decision(
    callback_url: str,
    owner_id: str,
    client_ip: str,
    approved: bool
) -> Dict[str, Any]:
    """处理用户授权决策

    Args:
        callback_url: Callback 后端 URL
        owner_id: 飞书用户 ID
        client_ip: 客户端 IP
        approved: 用户是否批准

    Returns:
        飞书响应（包含 toast 和更新的卡片）
    """
    from services.binding_store import BindingStore
    from services.auth_token import generate_auth_token
    from config import FEISHU_VERIFICATION_TOKEN

    if approved:
        # 验证配置
        if not FEISHU_VERIFICATION_TOKEN:
            logger.error("[register] FEISHU_VERIFICATION_TOKEN not configured")
            return {
                'toast': {
                    'type': 'error',
                    'content': '服务配置错误'
                }
            }

        # 实时生成 auth_token
        auth_token = generate_auth_token(FEISHU_VERIFICATION_TOKEN, owner_id)
        logger.info(f"[register] Authorization approved, generated auth_token")

        # 用户允许：通知 Callback 后端并创建绑定
        store = BindingStore.get_instance()
        if store:
            store.upsert(owner_id, callback_url, auth_token, client_ip)

        # 通知 Callback 后端
        _notify_callback(callback_url, owner_id, auth_token, client_ip)

        # 返回已授权卡片（带解绑按钮）
        content = (
            f"**Callback URL**: `{callback_url}`\n"
            f"**来源 IP**: `{client_ip}`\n\n"
            f"已成功授权该后端接收你的飞书消息"
        )
        return {
            'toast': {
                'type': 'success',
                'content': '已授权绑定'
            },
            'card': _build_register_status_card(
                title='✓ 已授权',
                content=content,
                template='green',
                button={
                    'tag': 'button',
                    'text': {'tag': 'plain_text', 'content': '解绑'},
                    'type': 'danger',
                    'value': {
                        'action': 'unbind_register',
                        'callback_url': callback_url,
                        'owner_id': owner_id
                    }
                }
            )
        }
    else:
        # 用户拒绝：仅删除 owner_id + callback_url 精确匹配的绑定
        store = BindingStore.get_instance()
        if store:
            existing = store.get(owner_id)
            if existing and existing.get('callback_url') == callback_url:
                store.delete(owner_id)
                logger.info(f"[register] User denied, deleted binding for {callback_url}: owner_id={owner_id}")
                # 返回已拒绝卡片（无按钮）
                return {
                    'toast': {
                        'type': 'success',
                        'content': '已拒绝并解除绑定'
                    },
                    'card': _build_register_status_card(
                        title='✗ 已拒绝',
                        content=f"**Callback URL**: `{callback_url}`\n\n已拒绝该后端的注册请求",
                        template='red'
                    )
                }
            else:
                logger.info(f"[register] User denied registration: owner_id={owner_id}")
                return {
                    'toast': {
                        'type': 'info',
                        'content': '已拒绝注册请求'
                    },
                    'card': _build_register_status_card(
                        title='✗ 已拒绝',
                        content=f"**Callback URL**: `{callback_url}`\n\n已拒绝该后端的注册请求",
                        template='red'
                    )
                }
        else:
            logger.info(f"[register] User denied registration: owner_id={owner_id}")
            return {
                'toast': {
                    'type': 'info',
                    'content': '已拒绝注册请求'
                },
                'card': _build_register_status_card(
                    title='✗ 已拒绝',
                    content=f"**Callback URL**: `{callback_url}`\n\n已拒绝该后端的注册请求",
                    template='red'
                )
            }


def handle_register_unbind(callback_url: str, owner_id: str) -> Dict[str, Any]:
    """处理用户解绑操作

    Args:
        callback_url: Callback 后端 URL
        owner_id: 飞书用户 ID

    Returns:
        飞书响应（包含 toast 和更新的卡片）
    """
    from services.binding_store import BindingStore

    store = BindingStore.get_instance()
    if store:
        existing = store.get(owner_id)
        if existing and existing.get('callback_url') == callback_url:
            store.delete(owner_id)
            logger.info(f"[register] User unbound: owner_id={owner_id}, callback_url={callback_url}")
        else:
            logger.info(f"[register] User unbind (no existing binding): owner_id={owner_id}, callback_url={callback_url}")

    # 返回已解绑卡片（无按钮）
    return {
        'toast': {
            'type': 'info',
            'content': '已解绑'
        },
        'card': _build_register_status_card(
            title='✗ 已解绑',
            content=f"**Callback URL**: `{callback_url}`\n\n已解除该后端的绑定，将不再接收飞书消息",
            template='grey'
        )
    }


def _run_in_background(func, args=()):
    """在后台线程中执行函数

    Args:
        func: 要执行的函数
        args: 位置参数元组
    """
    thread = threading.Thread(target=func, args=args, daemon=True)
    thread.start()
