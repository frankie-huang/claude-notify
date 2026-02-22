"""
HTTP Handler - HTTP 请求处理器

处理权限回调请求（GET）和 POST 路由分发
"""

import json
import logging
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from services.auth_token import verify_owner_based_auth_token
from handlers.feishu import handle_feishu_request, handle_send_message
from handlers.register import handle_register_request
from handlers.utils import send_json, send_html_response
from handlers.callback import (
    handle_status,
    handle_action,
    handle_register_callback_route,
    handle_check_owner_id_route,
    handle_get_chat_id,
    handle_get_last_message_id,
    handle_set_last_message_id,
    handle_callback_decision,
    handle_claude_new,
    handle_claude_continue,
    handle_recent_dirs,
    handle_browse_dirs,
)

# 单次请求最大大小限制
MAX_REQUEST_SIZE = 10 * 1024 * 1024  # 10MB

logger = logging.getLogger(__name__)


class HttpRequestHandler(BaseHTTPRequestHandler):
    """HTTP 请求处理器 - 路由分发入口

    职责：解析请求、路由分发。
    业务逻辑委托给对应的 handler 模块：
        - Callback 后端路由 → handlers.callback
        - 飞书网关路由 → handlers.register / handlers.feishu
    """

    def log_message(self, format, *args):
        logger.info(f"{self.address_string()} - {format % args}")

    def get_client_ip(self) -> str:
        """获取真实客户端 IP

        优先从 X-Forwarded-For header 获取，格式为 "client, proxy1, proxy2"，
        取第一个 IP。如果没有该 header，则使用 socket 连接地址。

        Returns:
            客户端 IP 地址
        """
        # 优先检查 X-Forwarded-For header
        forwarded_for = self.headers.get('X-Forwarded-For', '')
        if forwarded_for:
            # 格式: "client, proxy1, proxy2"，取第一个（真实客户端）
            client_ip = forwarded_for.split(',')[0].strip()
            if client_ip:
                return client_ip

        # 回退到 socket 连接地址
        return self.client_address[0] if self.client_address else ''

    # GET 路由: action → 路由处理函数
    ACTION_ROUTES = frozenset(['allow', 'always', 'deny', 'interrupt'])

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        # ===== Callback 后端侧路由 =====
        if path == '/status':
            handle_status(self)
            return

        # /allow, /always, /deny, /interrupt - 权限决策回调
        action = path.lstrip('/')
        if action in self.ACTION_ROUTES:
            request_id = params.get('id', [None])[0]
            handle_action(self, request_id, action)
            return

        send_html_response(self, 404, '未找到', '请求的页面不存在。', False)

    # =============================================
    # POST 路由表
    # =============================================

    # 飞书网关侧路由（存储器: MessageSessionStore, BindingStore）
    # /gw/register 和 /gw/feishu/send 需要特殊处理，不在路由表中
    # 未匹配路径兜底到飞书事件回调（handle_feishu_request）

    # Callback 后端侧路由（存储器: SessionChatStore, AuthTokenStore, DirHistoryStore）
    # 函数签名统一为 (handler, data)
    BACKEND_ROUTES = {
        '/cb/register': handle_register_callback_route,
        '/cb/check-owner': handle_check_owner_id_route,
        '/cb/session/get-chat-id': handle_get_chat_id,
        '/cb/session/get-last-message-id': handle_get_last_message_id,
        '/cb/session/set-last-message-id': handle_set_last_message_id,
        '/cb/decision': handle_callback_decision,
        '/cb/claude/new': handle_claude_new,
        '/cb/claude/continue': handle_claude_continue,
        '/cb/claude/recent-dirs': handle_recent_dirs,
        '/cb/claude/browse-dirs': handle_browse_dirs,
    }

    def do_POST(self):
        """处理 POST 请求

        路由分发逻辑：
        1. 飞书网关侧路由（/gw/register, /gw/feishu/send）
        2. Callback 后端侧路由（路由表匹配）
        3. 飞书事件回调兜底（URL验证、消息事件、卡片回传交互）
        """
        parsed = urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get('Content-Length', 0))

        # 验证 Content-Length 范围
        if content_length <= 0 or content_length > MAX_REQUEST_SIZE:
            logger.warning("[POST] Invalid Content-Length: %d", content_length)
            send_json(self, 400, {'error': 'Empty request body' if content_length <= 0 else 'Request body too large'})
            return

        try:
            body = self.rfile.read(content_length)
            data = json.loads(body.decode('utf-8'))
        except json.JSONDecodeError as e:
            logger.warning("[POST] Invalid JSON: %s", e)
            send_json(self, 400, {'error': 'Invalid JSON'})
            return

        # ===== 飞书网关侧路由 =====
        if path == '/gw/register':
            client_ip = self.get_client_ip()
            handled, response = handle_register_request(data, client_ip)
            send_json(self, 200 if response.get('success') else 400, response)
            return

        if path == '/gw/feishu/send':
            binding = verify_owner_based_auth_token(self, data, '/gw/feishu/send')
            if binding is None:
                return  # 验证失败，已发送响应
            handled, response = handle_send_message(data, binding)
            send_json(self, 200 if response.get('success') else 400, response)
            return

        # ===== Callback 后端侧路由 =====
        route_handler = self.BACKEND_ROUTES.get(path)
        if route_handler:
            route_handler(self, data)
            return

        # ===== 飞书事件回调（兜底：URL验证、消息事件、卡片回传交互）=====
        handled, response = handle_feishu_request(data)
        if handled:
            send_json(self, 200, response)
            return

        # 未知的 POST 请求
        logger.warning("[POST] Unknown request, type: %s", data.get('type', 'none'))
        send_json(self, 400, {'error': 'Unknown request type'})

