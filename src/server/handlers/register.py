"""Gateway Register Handler - 网关注册接口处理器

网关注册流程的处理器，飞书网关和 Callback 后端都会用到。

飞书网关使用：
    - handle_register_request(): 接收 Callback 后端的注册请求
    - handle_authorization_decision(): 处理用户授权决策（允许/拒绝）

Callback 后端使用：
    - handle_register_callback(): 接收网关的 auth_token 通知
    - handle_check_owner_id(): 验证 owner_id 所属权

数据存储服务（从 services 导入）：
    - AuthTokenStore: 存储 auth_token
"""

import json
import logging
import socket
import urllib.error
from typing import Tuple, Dict, Any

from services.auth_token_store import AuthTokenStore
from handlers.utils import run_in_background as _run_in_background, post_json as _post_json

logger = logging.getLogger(__name__)

# HTTP 请求超时（秒）
HTTP_TIMEOUT = 10


def handle_register_request(data: dict, client_ip: str = '') -> Tuple[bool, dict]:
    """处理 Callback 后端的注册请求

    网关立即返回成功，后续异步处理：
        - 已绑定：直接调用 Callback 后端的 /cb/register
        - 未绑定：发送飞书授权卡片

    Args:
        data: 请求数据
            - callback_url: Callback 后端 URL（必需）
            - owner_id: 飞书用户 ID（必需）
            - reply_in_thread: 是否使用回复话题模式（可选，默认 False）
        client_ip: 客户端 IP 地址

    Returns:
        (success, response): success 表示是否处理成功，response 是响应数据
    """
    callback_url = data.get('callback_url', '')
    owner_id = data.get('owner_id', '')
    reply_in_thread = data.get('reply_in_thread', False)

    # 验证参数
    if not callback_url or not owner_id:
        logger.warning("[register] Missing params: callback_url or owner_id")
        return True, {
            'success': False,
            'error': 'missing required fields: callback_url, owner_id'
        }

    logger.info(f"[register] Registration request: owner_id={owner_id}, callback_url={callback_url}, ip={client_ip}, reply_in_thread={reply_in_thread}")

    # 在后台线程中处理注册逻辑（异步）
    _run_in_background(_process_registration, (callback_url, owner_id, client_ip, reply_in_thread))

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
        logger.warning("[cb/register] Missing params: owner_id or auth_token")
        return True, {
            'success': False,
            'error': 'missing required fields: owner_id, auth_token'
        }

    # 验证 owner_id 是否与配置一致
    if config_owner_id and owner_id != config_owner_id:
        logger.warning(
            f"[cb/register] owner_id mismatch: received={owner_id}, config={config_owner_id}"
        )
        return True, {
            'success': False,
            'error': 'owner_id mismatch'
        }

    logger.info(
        f"[cb/register] Storing auth_token for owner_id={owner_id}, "
        f"gateway_version={gateway_version}"
    )

    # 存储 auth_token
    store = AuthTokenStore.get_instance()
    if store:
        if store.save(owner_id, auth_token):
            logger.info(f"[cb/register] Auth token stored successfully")
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
        logger.warning("[cb/register] AuthTokenStore not initialized")
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

    logger.info(f"[cb/check-owner] Request: owner_id={request_owner_id}")

    # 验证 owner_id 是否与配置一致
    is_owner = bool(request_owner_id and request_owner_id == config_owner_id)

    if is_owner:
        logger.info(f"[cb/check-owner] Verification passed")
    else:
        logger.warning(
            f"[cb/check-owner] Verification failed: request={request_owner_id}, config={config_owner_id}"
        )

    return True, {
        'success': True,
        'is_owner': is_owner
    }


def _process_registration(callback_url: str, owner_id: str, client_ip: str, reply_in_thread: bool = False):
    """处理注册逻辑（后台线程）

    1. 查询绑定关系
    2. 已绑定且 callback_url 相同：直接调用 /cb/register 通知新 token
    3. 已绑定但 callback_url 不同：发送飞书授权卡片让用户确认是否更新
    4. 未绑定：先验证 callback_url 所属，再发送飞书授权卡片

    注意：auth_token 不再提前生成，而是在用户点击允许后实时生成。

    Args:
        callback_url: Callback 后端 URL
        owner_id: 飞书用户 ID
        client_ip: 客户端 IP
        reply_in_thread: 是否使用回复话题模式
    """
    from services.binding_store import BindingStore
    from services.auth_token import generate_auth_token
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
            store.upsert(owner_id, callback_url, auth_token, client_ip, reply_in_thread)
        else:
            # callback_url 不同：发送授权卡片让用户确认是否更换设备
            # 不提前生成 auth_token，等用户批准后再生成
            logger.info(
                f"[register] Existing binding with different callback_url: "
                f"old={bound_callback_url}, new={callback_url}"
            )
            _send_authorization_card(callback_url, owner_id, client_ip, old_callback_url=bound_callback_url, reply_in_thread=reply_in_thread)
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
        _send_authorization_card(callback_url, owner_id, client_ip, reply_in_thread=reply_in_thread)


def _check_owner_id(callback_url: str, owner_id: str) -> bool:
    """验证 callback_url 是否属于该 owner_id

    调用 Callback 后端的 /cb/check-owner 接口进行验证。

    Args:
        callback_url: Callback 后端 URL
        owner_id: 飞书用户 ID

    Returns:
        True 表示验证通过，False 表示验证失败
    """
    api_url = f"{callback_url.rstrip('/')}/cb/check-owner"

    request_data = {
        'owner_id': owner_id
    }

    logger.info(f"[register] Checking owner_id: {api_url}")

    try:
        response_data = _post_json(api_url, request_data, timeout=HTTP_TIMEOUT)
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
    api_url = f"{callback_url.rstrip('/')}/cb/register"

    request_data = {
        'owner_id': owner_id,
        'auth_token': auth_token,
        'gateway_version': '1.0.0'
    }

    logger.info(f"[register] Calling {api_url}")

    try:
        response_data = _post_json(api_url, request_data, auth_token=auth_token, timeout=HTTP_TIMEOUT)
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
    old_callback_url: str = '',
    reply_in_thread: bool = False
):
    """发送飞书授权卡片

    注意：不在卡片中嵌入 auth_token，而是等用户授权后再实时生成。
    用户点击允许时会验证 operator_id == owner_id，确保本人操作。

    Args:
        callback_url: Callback 后端 URL
        owner_id: 飞书用户 ID
        client_ip: 客户端 IP
        old_callback_url: 旧的 callback_url（如果有，表示更换设备场景）
        reply_in_thread: 是否使用回复话题模式
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
            f"**授权后该后端将获得以下权限：**\n"
            f"• 接收你发送给机器人的所有消息\n"
            f"• 向你发送消息通知（如权限请求、任务状态等）\n\n"
            f"**安全风险提示：**\n"
            f"• 后端可读取你的对话内容\n"
            f"• 后端可主动向你推送消息\n"
            f"• 请确认该后端来源可信后再授权\n\n"
            f"是否允许更换到新设备？"
        )
    else:
        # 新设备注册场景
        title = "新的 Callback 后端注册请求"
        content = (
            f"**Callback URL**: `{callback_url}`\n"
            f"**来源 IP**: `{client_ip}`\n\n"
            f"**授权后该后端将获得以下权限：**\n"
            f"• 接收你发送给机器人的所有消息\n"
            f"• 向你发送消息通知（如权限请求、任务状态等）\n\n"
            f"**安全风险提示：**\n"
            f"• 后端可读取你的对话内容\n"
            f"• 后端可主动向你推送消息\n"
            f"• 请确认该后端来源可信后再授权\n\n"
            f"是否允许该后端绑定？"
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
                                                "old_callback_url": old_callback_url,
                                                "reply_in_thread": reply_in_thread
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
    approved: bool,
    reply_in_thread: bool = False
) -> Dict[str, Any]:
    """处理用户授权决策

    Args:
        callback_url: Callback 后端 URL
        owner_id: 飞书用户 ID
        client_ip: 客户端 IP
        approved: 用户是否批准
        reply_in_thread: 是否使用回复话题模式

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
            store.upsert(owner_id, callback_url, auth_token, client_ip, reply_in_thread)

        # 通知 Callback 后端
        _notify_callback(callback_url, owner_id, auth_token, client_ip)

        # 返回已授权卡片（带解绑按钮）
        content = (
            f"**Callback URL**: `{callback_url}`\n"
            f"**来源 IP**: `{client_ip}`\n\n"
            f"**已授权权限：**\n"
            f"• 接收你发送给机器人的所有消息\n"
            f"• 向你发送消息通知\n\n"
            f"已成功授权该后端"
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
            content=(
                f"**Callback URL**: `{callback_url}`\n\n"
                f"已解除绑定，该后端将：\n"
                f"• 无法再接收你的消息\n"
                f"• 无法再向你发送通知"
            ),
            template='grey'
        )
    }
