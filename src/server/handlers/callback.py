"""
Callback 后端侧路由处理函数

所有 Callback 后端的路由处理函数，由 http_handler.py 路由分发调用。
每个处理函数签名统一为 (handler, ...)，内部自行完成鉴权和响应。

存储器归属: SessionChatStore, AuthTokenStore, DirHistoryStore

GET 路由:
- /status: 获取服务状态
- /allow, /always, /deny, /interrupt: 权限决策回调

POST 路由:
- /cb/register: 接收飞书网关通知的 auth_token
- /cb/check-owner: 验证 owner_id 是否属于该 Callback 后端
- /cb/session/get-chat-id: 根据 session_id 获取 chat_id
- /cb/session/get-last-message-id: 获取 session 的最近消息 ID
- /cb/session/set-last-message-id: 设置 session 的最近消息 ID
- /cb/decision: 接收飞书网关转发的决策请求
- /cb/claude/new: 新建 Claude 会话
- /cb/claude/continue: 继续 Claude 会话
- /cb/claude/recent-dirs: 获取近期工作目录
- /cb/claude/browse-dirs: 浏览子目录
"""

import logging
import os

from services.auth_token import verify_global_auth_token
from services.request_manager import RequestManager
from services.decision_handler import handle_decision
from config import VSCODE_URI_PREFIX
from handlers.register import handle_register_callback, handle_check_owner_id
from handlers.claude import handle_continue_session, handle_new_session
from handlers.utils import send_json, send_html_response

logger = logging.getLogger(__name__)

# Action 到 HTML 响应的映射
ACTION_HTML_RESPONSES = {
    'allow': {
        'title': '已批准运行',
        'message': '权限请求已批准，请返回终端查看执行结果。'
    },
    'always': {
        'title': '已始终允许',
        'message': '权限请求已批准，并已添加到项目的允许规则中。后续相同操作将自动允许。'
    },
    'deny': {
        'title': '已拒绝运行',
        'message': '权限请求已拒绝。Claude 可能会尝试其他方式继续工作。'
    },
    'interrupt': {
        'title': '已拒绝并中断',
        'message': '权限请求已拒绝，Claude 已停止当前任务。'
    }
}


# =============================================
# GET 路由处理函数
# =============================================

def handle_status(handler):
    """获取服务状态统计信息"""
    stats = RequestManager.get_instance().get_stats()
    send_json(handler, 200, {
        'status': 'ok',
        'mode': 'socket-based (no server-side timeout)',
        **stats
    })


def handle_action(handler, request_id, action):
    """处理权限决策动作（GET /allow, /deny, /always, /interrupt）

    调用纯决策接口，根据返回结果渲染 HTML 响应页面。

    Args:
        handler: HTTP 请求处理器实例
        request_id: 请求 ID
        action: 动作类型 (allow/always/deny/interrupt)
    """
    # 先获取 VSCode URI（在决策之前，因为之后数据可能被清理）
    vscode_uri = _build_vscode_uri(handler, request_id)

    # 调用纯决策接口
    success, decision, message = handle_decision(request_id, action)

    # 根据结果渲染 HTML 响应
    if success:
        response_info = ACTION_HTML_RESPONSES.get(action, {})
        title = response_info.get('title', '操作成功')
        html_message = response_info.get('message', message)
        send_html_response(
            handler, 200, title, html_message,
            success=True,
            vscode_uri=vscode_uri
        )
    else:
        send_html_response(
            handler, 400, '操作失败', message,
            success=False
        )


def _build_vscode_uri(handler, request_id):
    """构建 VSCode URI

    Args:
        handler: HTTP 请求处理器实例
        request_id: 请求 ID

    Returns:
        VSCode URI 或空字符串（未配置时）
    """
    if not VSCODE_URI_PREFIX:
        return ''

    req_data = RequestManager.get_instance().get_request_data(request_id)
    if not req_data:
        return ''

    project_dir = req_data.get('project_dir', '')
    if not project_dir:
        return ''

    return VSCODE_URI_PREFIX + project_dir


# =============================================
# POST 路由处理函数
# =============================================


def handle_register_callback_route(handler, data):
    """接收飞书网关通知的 auth_token（网关 → Callback）"""
    handled, response = handle_register_callback(data)
    status = 200 if response.get('success') else 400
    send_json(handler, status, response)


def handle_check_owner_id_route(handler, data):
    """验证 owner_id 是否属于该 Callback 后端"""
    handled, response = handle_check_owner_id(data)
    send_json(handler, 200, response)


def handle_claude_new(handler, data):
    """新建 Claude 会话（飞书网关调用）"""
    if not verify_global_auth_token(handler, '/cb/claude/new'):
        return

    success, response = handle_new_session(data)
    status = 200 if success else 400
    send_json(handler, status, response)


def handle_claude_continue(handler, data):
    """继续 Claude 会话（飞书网关调用）"""
    if not verify_global_auth_token(handler, '/cb/claude/continue'):
        return

    success, response = handle_continue_session(data)
    status = 200 if success else 400
    send_json(handler, status, response)


def handle_get_chat_id(handler, data):
    """根据 session_id 获取对应的 chat_id（客户端调用）"""
    from services.session_chat_store import SessionChatStore

    if not verify_global_auth_token(handler, '/cb/session/get-chat-id'):
        return

    session_id = data.get('session_id', '')
    if not session_id:
        send_json(handler, 400, {'chat_id': None})
        return

    store = SessionChatStore.get_instance()
    chat_id = ''
    if store:
        chat_id = store.get(session_id) or ''

    send_json(handler, 200, {'chat_id': chat_id})


def handle_get_last_message_id(handler, data):
    """根据 session_id 获取对应的 last_message_id（客户端调用）"""
    from services.session_chat_store import SessionChatStore

    if not verify_global_auth_token(handler, '/cb/session/get-last-message-id'):
        return

    session_id = data.get('session_id', '')
    if not session_id:
        send_json(handler, 400, {'last_message_id': ''})
        return

    store = SessionChatStore.get_instance()
    last_message_id = ''
    if store:
        last_message_id = store.get_last_message_id(session_id)

    send_json(handler, 200, {'last_message_id': last_message_id})


def handle_set_last_message_id(handler, data):
    """设置 session 的 last_message_id（飞书网关调用）"""
    from services.session_chat_store import SessionChatStore

    if not verify_global_auth_token(handler, '/cb/session/set-last-message-id'):
        return

    session_id = data.get('session_id', '')
    message_id = data.get('message_id', '')

    if not session_id or not message_id:
        send_json(handler, 400, {'success': False, 'error': 'Missing required parameters'})
        return

    store = SessionChatStore.get_instance()
    if store:
        success = store.set_last_message_id(session_id, message_id)
        if success:
            logger.info("[callback] Set last_message_id: session=%s, message_id=%s", session_id, message_id)
            send_json(handler, 200, {'success': True})
        else:
            logger.warning("[callback] Failed to set last_message_id: session=%s, message_id=%s", session_id, message_id)
            send_json(handler, 500, {'success': False, 'error': 'Failed to set last_message_id'})
    else:
        send_json(handler, 500, {'success': False, 'error': 'SessionChatStore not initialized'})


def handle_callback_decision(handler, data):
    """处理纯决策请求（供飞书网关或其他服务调用）

    此接口返回纯决策结果，不包含 toast 格式。
    调用方根据返回的 success 和 decision 自行生成响应。

    HTTP 状态码语义：
        - 200: 接口正常处理（业务成功/失败通过 success 字段区分）
        - 400: 请求格式错误（缺少必要参数）
        - 401: 身份验证失败（auth_token 无效）

    Args:
        handler: HTTP 请求处理器实例
        data: 请求数据
            - action: 动作类型 (allow/always/deny/interrupt)
            - request_id: 请求 ID
            - project_dir: 项目目录（可选，用于 always 写入规则）
    """
    # 验证 auth_token（飞书网关调用）
    if not verify_global_auth_token(handler, '/cb/decision', error_body={
        'success': False,
        'decision': None,
        'message': 'Unauthorized'
    }):
        return

    action = data.get('action', '')
    request_id = data.get('request_id', '')
    project_dir = data.get('project_dir', '')

    logger.info("[cb/decision] action=%s, request_id=%s", action, request_id)

    # 验证参数（请求格式错误返回 400）
    if not action or not request_id:
        logger.warning("[cb/decision] Missing params: action=%s, request_id=%s", action, request_id)
        send_json(handler, 400, {
            'success': False,
            'decision': None,
            'message': '无效的请求参数'
        })
        return

    # 调用纯决策接口
    success, decision, message = handle_decision(request_id, action, project_dir)

    logger.info(
        "[cb/decision] result: request_id=%s, success=%s, decision=%s, message=%s",
        request_id, success, decision, message
    )

    # 返回 JSON 响应（业务成功/失败统一返回 200，通过 success 字段区分）
    send_json(handler, 200, {
        'success': success,
        'decision': decision,
        'message': message
    })


def handle_recent_dirs(handler, data):
    """获取近期常用工作目录列表"""
    if not verify_global_auth_token(handler, '/cb/claude/recent-dirs'):
        return

    try:
        limit = int(data.get('limit', 5))
    except (TypeError, ValueError):
        limit = 5

    from services.dir_history_store import DirHistoryStore
    store = DirHistoryStore.get_instance()
    recent_dirs = store.get_recent_dirs(limit) if store else []

    send_json(handler, 200, {'dirs': recent_dirs})


def handle_browse_dirs(handler, data):
    """浏览指定路径下的子目录"""
    if not verify_global_auth_token(handler, '/cb/claude/browse-dirs'):
        return

    # 解析参数
    request_path = data.get('path', '')

    # 默认起始路径为根目录
    if not request_path:
        request_path = '/'

    # 规范化路径（消除 .. 、符号链接等）
    request_path = os.path.realpath(request_path)

    # 验证路径必须是绝对路径
    if not request_path.startswith('/'):
        logger.warning("[browse-dirs] Path must be absolute: %s", request_path)
        send_json(handler, 400, {'error': 'path must be absolute'})
        return

    # 验证路径存在且可访问
    if not os.path.isdir(request_path):
        logger.warning("[browse-dirs] Path not found or not accessible: %s", request_path)
        send_json(handler, 400, {'error': 'path not found or not accessible'})
        return

    try:
        # 获取父目录路径（去除末尾斜杠，但保留根目录的 /）
        current_path = request_path.rstrip('/') if request_path != '/' else '/'
        parent_path = os.path.dirname(current_path) if current_path != '/' else ''

        # 列出子目录，过滤隐藏目录和文件
        dirs = []
        try:
            entries = os.listdir(request_path)
            for entry in entries:
                # 跳过隐藏目录（以 . 开头）
                if entry.startswith('.'):
                    continue
                # 只保留目录
                full_path = os.path.join(request_path, entry)
                if os.path.isdir(full_path):
                    dirs.append(full_path)
        except PermissionError:
            logger.warning("[browse-dirs] Permission denied: %s", request_path)
            dirs = []

        # 按目录名字母排序
        dirs.sort()

        send_json(handler, 200, {
            'dirs': dirs,
            'parent': parent_path,
            'current': current_path
        })
    except Exception as e:
        logger.error("[browse-dirs] Error listing directory: %s", e)
        send_json(handler, 500, {'error': 'internal server error'})
