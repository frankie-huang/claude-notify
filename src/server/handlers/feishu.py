"""
Feishu Handler - 飞书事件处理器

处理飞书相关的 POST 请求：
    - URL 验证（type: url_verification）
    - 消息事件（im.message.receive_v1）
    - 卡片回传交互（card.action.trigger）
    - 发送消息（/feishu/send）
"""

import json
import logging
import os
import re
import socket
import threading
import time
from typing import Tuple

logger = logging.getLogger(__name__)

# 飞书 Toast 类型常量
TOAST_SUCCESS = 'success'
TOAST_WARNING = 'warning'
TOAST_ERROR = 'error'
TOAST_INFO = 'info'

# 飞书消息事件日志（独立文件）
_feishu_message_logger = None

# 消息内容清理正则：移除 @_user_1 提及（带或不带尾随空格）
_AT_USER_PATTERN = re.compile(r'@_user_1\s?')


def _sanitize_user_content(content: str, max_len: int = 20) -> str:
    """脱敏用户生成内容

    Args:
        content: 原始内容
        max_len: 保留的最大长度

    Returns:
        脱敏后的内容，格式为 "前N个字符..." (总长度: X)
    """
    if not content:
        return ''
    preview = content[:max_len].replace('\n', '\\n')
    return f"{preview}... (len={len(content)})"


def _get_message_logger():
    """获取飞书消息日志记录器（懒加载）"""
    global _feishu_message_logger
    if _feishu_message_logger is None:
        _feishu_message_logger = logging.getLogger('feishu_message')
        _feishu_message_logger.setLevel(logging.INFO)
        _feishu_message_logger.propagate = False  # 不传播到父 logger

        # 日志目录: src/server/handlers -> src/server -> src -> project_root -> log
        handlers_dir = os.path.dirname(__file__)
        server_dir = os.path.dirname(handlers_dir)
        src_dir = os.path.dirname(server_dir)
        project_root = os.path.dirname(src_dir)
        log_dir = os.path.join(project_root, 'log')
        os.makedirs(log_dir, exist_ok=True)

        log_file = os.path.join(log_dir, f"feishu_message_{time.strftime('%Y%m%d')}.log")
        handler = logging.FileHandler(log_file, encoding='utf-8')
        handler.setFormatter(logging.Formatter(
            '%(asctime)s.%(msecs)03d %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        _feishu_message_logger.addHandler(handler)
        logger.info(f"Feishu message logging to: {log_file}")

    return _feishu_message_logger


def handle_feishu_request(data: dict, request_manager=None) -> Tuple[bool, dict]:
    """处理飞书请求

    支持的请求类型：
        - url_verification: URL 验证
        - im.message.receive_v1: 消息接收事件
        - card.action.trigger: 卡片回传交互事件

    Args:
        data: 请求 JSON 数据
        request_manager: 请求管理器（处理 card.action.trigger 时需要）

    Returns:
        (handled, response): handled 表示是否处理了请求，response 是响应数据
    """
    # URL 验证请求
    if data.get('type') == 'url_verification':
        return _handle_url_verification(data)

    # 事件订阅（schema 2.0）
    header = data.get('header', {})
    event_type = header.get('event_type', '')

    if event_type == 'im.message.receive_v1':
        _handle_message_event(data)
        return True, {'success': True}

    # 卡片回传交互事件
    if event_type == 'card.action.trigger':
        return _handle_card_action(data, request_manager)

    # 不是飞书请求
    return False, {}


def _handle_url_verification(data: dict) -> Tuple[bool, dict]:
    """处理飞书 URL 验证请求

    飞书在配置事件订阅时会发送验证请求，需要在 1 秒内返回 challenge 值。

    Args:
        data: 请求数据，包含 challenge 字段

    Returns:
        (True, {'challenge': xxx})
    """
    challenge = data.get('challenge', '')
    logger.info(f"[feishu] URL verification, challenge: {challenge[:20]}...")
    return True, {'challenge': challenge}


def _handle_message_event(data: dict):
    """处理飞书消息事件 im.message.receive_v1

    Args:
        data: 飞书事件数据
    """
    header = data.get('header', {})
    event = data.get('event', {})
    message = event.get('message', {})
    sender = event.get('sender', {})

    event_id = header.get('event_id', '')
    message_id = message.get('message_id', '')
    chat_id = message.get('chat_id', '')
    chat_type = message.get('chat_type', '')  # p2p / group
    message_type = message.get('message_type', '')  # text / image / ...
    content = message.get('content', '{}')
    sender_id = sender.get('sender_id', {}).get('open_id', '')
    parent_id = message.get('parent_id', '')  # 是否是回复消息

    # 解析消息内容
    try:
        content_obj = json.loads(content)
        text = content_obj.get('text', '')
    except json.JSONDecodeError:
        text = content

    # 先记录原始数据到日志（所有消息都记录），脱敏用户内容
    msg_logger = _get_message_logger()
    msg_logger.info(json.dumps({
        'event_id': event_id,
        'message_id': message_id,
        'parent_id': parent_id,
        'chat_id': chat_id,
        'chat_type': chat_type,
        'message_type': message_type,
        'sender_id': sender_id,
        'content': _sanitize_user_content(content),
        'text': _sanitize_user_content(text)
    }, ensure_ascii=False))

    logger.info(f"[feishu] Message received: chat_type={chat_type}, message_type={message_type}, parent_id={parent_id if parent_id else ''}, text={_sanitize_user_content(text)}")

    # 清理消息中的 @_user_1 提及（带或不带尾随空格）
    text = _AT_USER_PATTERN.sub('', text)

    # 检查是否是回复消息（用于继续会话）
    if parent_id:
        _handle_reply_message(data, parent_id)


def _run_in_background(func, args=()):
    """在后台线程中执行函数

    Args:
        func: 要执行的函数
        args: 位置参数元组
    """
    thread = threading.Thread(target=func, args=args, daemon=True)
    thread.start()


def _handle_reply_message(data: dict, parent_id: str):
    """处理用户回复消息，继续 Claude 会话

    Args:
        data: 飞书事件数据
        parent_id: 被回复的消息 ID
    """
    from services.session_store import SessionStore

    event = data.get('event', {})
    message = event.get('message', {})

    message_id = message.get('message_id', '')
    chat_id = message.get('chat_id', '')
    content = message.get('content', '{}')

    # 解析回复内容
    try:
        content_obj = json.loads(content)
        prompt = content_obj.get('text', '')
    except json.JSONDecodeError:
        prompt = content

    if not prompt:
        logger.warning(f"[feishu] Reply message has no text content, parent_id={parent_id}")
        return

    logger.info(f"[feishu] Reply message: parent_id={parent_id}, prompt={_sanitize_user_content(prompt)}")

    # 查询映射
    store = SessionStore.get_instance()
    if not store:
        logger.warning("[feishu] SessionStore not initialized")
        return

    mapping = store.get(parent_id)
    if not mapping:
        logger.info(f"[feishu] No mapping found for parent_id={parent_id}, ignoring")
        return

    # 在后台线程中转发到 Callback 后端，避免阻塞飞书事件响应
    _run_in_background(_forward_continue_request, (mapping, prompt, chat_id, message_id))


def _extract_http_error_detail(http_error):
    """从 HTTPError 中提取错误详情

    Args:
        http_error: urllib.error.HTTPError 实例

    Returns:
        错误详情字符串，无法解析返回空字符串
    """
    try:
        error_body = http_error.read().decode('utf-8')
        error_data = json.loads(error_body)
        return error_data.get('error', '')
    except:
        return ''


def _forward_continue_request(mapping: dict, prompt: str, chat_id: str, reply_message_id: str):
    """转发继续会话请求到 Callback 后端

    Args:
        mapping: 映射信息 {session_id, project_dir, callback_url}
        prompt: 用户回复内容
        chat_id: 群聊 ID
        reply_message_id: 回复消息 ID
    """
    import urllib.request
    import urllib.error
    from services.feishu_api import FeishuAPIService

    callback_url = mapping['callback_url'].rstrip('/')
    api_url = f"{callback_url}/claude/continue"

    request_data = {
        'session_id': mapping['session_id'],
        'project_dir': mapping['project_dir'],
        'prompt': prompt,
        'chat_id': chat_id,
        'reply_message_id': reply_message_id
    }

    logger.info(f"[feishu] Forwarding continue request to {api_url}")

    try:
        req = urllib.request.Request(
            api_url,
            data=json.dumps(request_data).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )

        with urllib.request.urlopen(req, timeout=30) as response:
            response_data = json.loads(response.read().decode('utf-8'))
            logger.info(f"[feishu] Continue request response: {response_data}")

            # 根据返回状态发送飞书通知
            _send_continue_result_notification(response_data, chat_id)

    except urllib.error.HTTPError as e:
        error_detail = _extract_http_error_detail(e)
        error_msg = f"Claude 执行失败: {error_detail}" if error_detail else f"Callback 服务返回错误: {e.code}"
        logger.error(f"[feishu] Continue request HTTP error: {e.code} {e.reason}")
        _send_error_notification(chat_id, error_msg)

    except urllib.error.URLError as e:
        logger.error(f"[feishu] Continue request URL error: {e.reason}")
        _send_error_notification(chat_id, f"Callback 服务不可达: {e.reason}")


def _send_continue_result_notification(response: dict, chat_id: str):
    """根据继续会话结果发送飞书通知

    Args:
        response: Callback 返回的结果
        chat_id: 群聊 ID
    """
    from services.feishu_api import FeishuAPIService

    service = FeishuAPIService.get_instance()
    if not service or not service.enabled:
        logger.warning("[feishu] FeishuAPIService not enabled, skipping notification")
        return

    status = response.get('status', '')
    error = response.get('error', '')

    if status == 'processing':
        # 正在处理
        message = "⏳ Claude 正在处理您的问题，请稍候..."
        _send_text_message(service, chat_id, message)
    elif status == 'completed':
        # 快速完成
        output = response.get('output', '')
        message = f"✅ Claude 已完成: {_sanitize_user_content(output, 50)}" if output else "✅ Claude 已完成"
        _send_text_message(service, chat_id, message)
    elif error:
        # 执行失败
        _send_error_notification(chat_id, f"Claude 执行失败: {error}")
    else:
        logger.warning(f"[feishu] Unknown response status: {status}")


def _send_error_notification(chat_id: str, error_msg: str):
    """发送错误通知到飞书

    Args:
        chat_id: 群聊 ID
        error_msg: 错误消息
    """
    from services.feishu_api import FeishuAPIService

    service = FeishuAPIService.get_instance()
    if service and service.enabled:
        _send_text_message(service, chat_id, f"⚠️ 继续会话失败: {error_msg}")


def _send_text_message(service, chat_id: str, text: str):
    """发送文本消息

    Args:
        service: FeishuAPIService 实例
        chat_id: 群聊 ID
        text: 消息内容
    """
    try:
        success, result = service.send_text(text, receive_id=chat_id, receive_id_type='chat_id')
        if success:
            logger.info(f"[feishu] Sent notification to {chat_id}: {_sanitize_user_content(text)}")
        else:
            logger.error(f"[feishu] Failed to send notification: {result}")
    except Exception as e:
        logger.error(f"[feishu] Error sending notification: {e}")


def _handle_card_action(data: dict, request_manager=None) -> Tuple[bool, dict]:
    """处理飞书卡片回传交互事件 card.action.trigger

    当用户点击卡片中的 callback 类型按钮时，飞书会发送此事件。
    服务器需要在 3 秒内返回响应，可返回 toast 提示。

    处理逻辑：
    1. 从按钮 value 中获取 callback_url
    2. 调用 callback_url 的决策接口获取决策结果
    3. 根据决策结果生成 toast 返回给飞书

    Args:
        data: 飞书事件数据
        request_manager: 不再使用，保留参数仅为兼容

    Returns:
        (handled, toast_response)
    """
    event = data.get('event', {})
    action = event.get('action', {})
    value = action.get('value', {})

    # 提取动作参数
    action_type = value.get('action', '')  # allow/always/deny/interrupt
    request_id = value.get('request_id', '')
    callback_url = value.get('callback_url', '')  # callback 服务地址

    # 记录日志
    header = data.get('header', {})
    event_id = header.get('event_id', '')
    operator = event.get('operator', {})
    user_id = operator.get('open_id', operator.get('user_id', 'unknown'))

    logger.info(
        f"[feishu] Card action: event_id={event_id}, "
        f"action={action_type}, request_id={request_id}, "
        f"callback_url={callback_url}, user={user_id}"
    )

    # 验证参数
    if not action_type or not request_id or not callback_url:
        logger.warning(f"[feishu] Card action missing params: action={action_type}, request_id={request_id}, callback_url={callback_url}")
        return True, {
            'toast': {
                'type': TOAST_ERROR,
                'content': '无效的回调请求'
            }
        }

    # 调用 callback_url 的决策接口
    return _forward_to_callback_service(callback_url, action_type, request_id, data)


def _forward_to_callback_service(callback_url: str, action_type: str, request_id: str, original_data: dict) -> Tuple[bool, dict]:
    """转发决策请求到 Callback 服务

    调用 callback 服务的纯决策接口，根据返回的决策结果生成 toast。

    注意：飞书要求在 3 秒内返回响应，timeout 设置为 2 秒预留时间。

    Args:
        callback_url: 目标 Callback 服务 URL
        action_type: 动作类型 (allow/always/deny/interrupt)
        request_id: 请求 ID
        original_data: 原始飞书事件数据（用于提取 project_dir）

    Returns:
        (handled, toast_response)
    """
    import urllib.request
    import urllib.error

    # 提取 project_dir（从原始请求的 value 中获取）
    event = original_data.get('event', {})
    action = event.get('action', {})
    value = action.get('value', {})

    # 构建请求数据
    request_data = {
        'action': action_type,
        'request_id': request_id
    }

    # 添加可选字段
    if 'project_dir' in value:
        request_data['project_dir'] = value['project_dir']

    # 规范化 URL
    callback_url = callback_url.rstrip('/')
    api_url = f"{callback_url}/callback/decision"

    logger.info(f"[feishu] Forwarding to {api_url}: {request_data}")

    import time
    start_time = time.time()

    try:
        req = urllib.request.Request(
            api_url,
            data=json.dumps(request_data).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )

        # 飞书要求 3 秒内返回，设置 2 秒超时预留处理时间
        with urllib.request.urlopen(req, timeout=2) as response:
            elapsed = (time.time() - start_time) * 1000
            response_data = json.loads(response.read().decode('utf-8'))

            success = response_data.get('success', False)
            decision = response_data.get('decision')
            message = response_data.get('message', '')

            # 根据决策结果生成 toast
            if success and decision:
                if decision == 'allow':
                    toast_type = TOAST_SUCCESS
                else:  # deny
                    toast_type = TOAST_WARNING
                toast_content = message or ('已批准运行' if decision == 'allow' else '已拒绝运行')
                logger.info(f"[feishu] Decision succeeded: decision={decision}, message={message}, elapsed={elapsed:.0f}ms")
            else:
                toast_type = TOAST_ERROR
                toast_content = message or '处理失败'
                logger.warning(f"[feishu] Decision failed: message={toast_content}, elapsed={elapsed:.0f}ms")

            return True, {
                'toast': {
                    'type': toast_type,
                    'content': toast_content
                }
            }

    except urllib.error.HTTPError as e:
        logger.error(f"[feishu] Forward HTTP error: {e.code} {e.reason}")
        return True, {
            'toast': {
                'type': TOAST_ERROR,
                'content': f'回调服务错误: HTTP {e.code}'
            }
        }
    except urllib.error.URLError as e:
        logger.error(f"[feishu] Forward URL error: {e.reason}")
        return True, {
            'toast': {
                'type': TOAST_ERROR,
                'content': '回调服务不可达，请检查服务状态'
            }
        }
    except socket.timeout:
        logger.error("[feishu] Forward timeout")
        return True, {
            'toast': {
                'type': TOAST_ERROR,
                'content': '回调服务响应超时'
            }
        }
    except Exception as e:
        logger.error(f"[feishu] Forward error: {e}")
        return True, {
            'toast': {
                'type': TOAST_ERROR,
                'content': f'转发失败: {str(e)}'
            }
        }


def handle_send_message(data: dict) -> Tuple[bool, dict]:
    """处理 /feishu/send 请求，通过 OpenAPI 发送消息

    Args:
        data: 请求 JSON 数据
            - msg_type: 消息类型 interactive/text/image（必需，暂仅支持 interactive）
            - content: 消息内容（必需）
                - card: 卡片 JSON 对象
                - text: 文本内容
                - image_key: 图片的 key
            - receive_id: 接收者 ID（可选，默认用配置）
            - receive_id_type: 接收者类型（可选，自动检测）
            - session_id: Claude 会话 ID（可选，用于继续会话）
            - project_dir: 项目工作目录（可选，用于继续会话）
            - callback_url: Callback 后端 URL（可选，用于继续会话）

    Returns:
        (handled, response): handled 始终为 True，response 包含结果
    """
    from services.feishu_api import FeishuAPIService

    msg_type = data.get('msg_type')
    content = data.get('content')

    # 新增：提取 session 相关参数
    session_id = data.get('session_id', '')
    project_dir = data.get('project_dir', '')
    callback_url = data.get('callback_url', '')

    if not msg_type:
        logger.warning("[feishu] /feishu/send: missing msg_type")
        return True, {'success': False, 'error': 'Missing msg_type'}

    receive_id = data.get('receive_id', '')
    receive_id_type = data.get('receive_id_type', '')

    service = FeishuAPIService.get_instance()
    if service is None or not service.enabled:
        logger.warning("[feishu] /feishu/send: service not enabled")
        return True, {'success': False, 'error': 'Feishu API service not enabled'}

    success = False
    result = ''

    if msg_type == 'interactive':
        # content 直接是 card 对象
        if not content:
            logger.warning("[feishu] /feishu/send: missing card content")
            return True, {'success': False, 'error': 'Missing card content'}

        # 如果是 dict 类型，转为 JSON 字符串
        card_json = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
        success, result = service.send_card(card_json, receive_id, receive_id_type)
    elif msg_type == 'text':
        text = content if isinstance(content, str) else content.get('text', '')
        if not text:
            logger.warning("[feishu] /feishu/send: missing text content")
            return True, {'success': False, 'error': 'Missing text content'}
        success, result = service.send_text(text, receive_id, receive_id_type)
    else:
        logger.warning(f"[feishu] /feishu/send: unsupported msg_type: {msg_type}")
        return True, {'success': False, 'error': f'Unsupported msg_type: {msg_type}'}

    if success:
        message_id = result
        logger.info(f"[feishu] /feishu/send: message sent, id={message_id}")

        # 新增：发送成功后保存映射（支持继续会话）
        if message_id and session_id and project_dir and callback_url:
            from services.session_store import SessionStore
            store = SessionStore.get_instance()
            if store:
                store.save(message_id, session_id, project_dir, callback_url)
                logger.info(f"[feishu] Saved session mapping: {message_id} -> {session_id}")

        return True, {'success': True, 'message_id': message_id}
    else:
        logger.error(f"[feishu] /feishu/send: failed, error={result}")
        return True, {'success': False, 'error': result}
