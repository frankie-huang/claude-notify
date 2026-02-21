"""
Callback Handler - HTTP 请求处理器

处理权限回调请求（GET）和飞书事件（POST）
"""

import html
import json
import logging
import os
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from services.request_manager import RequestManager
from services.decision_handler import handle_decision
from services.auth_token import verify_global_auth_token, verify_owner_based_auth_token
from config import CALLBACK_PAGE_CLOSE_DELAY, VSCODE_URI_PREFIX
from handlers.feishu import handle_feishu_request, handle_send_message
from handlers.claude import handle_continue_session, handle_new_session
from handlers.register import handle_register_request, handle_register_callback, handle_check_owner_id

# 单次请求最大大小限制
MAX_REQUEST_SIZE = 10 * 1024 * 1024  # 10MB

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

logger = logging.getLogger(__name__)


class CallbackHandler(BaseHTTPRequestHandler):
    """HTTP 请求处理器

    GET 端点（权限回调）：
        - /allow?id={request_id}    - 批准运行
        - /always?id={request_id}   - 始终允许并写入规则
        - /deny?id={request_id}     - 拒绝运行
        - /interrupt?id={request_id} - 拒绝并中断
        - /status                    - 查看服务状态

    POST 端点（飞书事件）：
        - 委托给 handlers.feishu 处理
    """

    # 这个类变量由 main.py 设置
    request_manager: RequestManager = None

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

    def send_html_response(self, status: int, title: str, message: str,
                           success: bool = True, close_timeout: int = None,
                           vscode_uri: str = None):
        """发送 HTML 响应页面

        Args:
            status: HTTP 状态码
            title: 页面标题
            message: 显示消息
            success: 是否成功
            close_timeout: 自动关闭页面超时时间（秒），默认从环境变量 CALLBACK_PAGE_CLOSE_DELAY 读取
            vscode_uri: VSCode URI，配置后会自动跳转到 VSCode
        """
        if close_timeout is None:
            close_timeout = CALLBACK_PAGE_CLOSE_DELAY
        color = '#28a745' if success else '#dc3545'
        icon = '✓' if success else '✗'

        # VSCode 跳转相关的 HTML 和 JS
        vscode_redirect_html = ''
        vscode_redirect_js = ''
        if vscode_uri and success:
            # 判断是本地还是远程，用于显示对应的设置提示
            is_local = vscode_uri.startswith('vscode://file')
            setting_hint = (
                '"security.promptForLocalFileProtocolHandling": false'
                if is_local
                else '"security.promptForRemoteFileProtocolHandling": false'
            )

            vscode_redirect_html = f'''
                <div class="vscode-redirect" id="vscodeRedirect">
                    正在跳转到 VSCode...
                </div>
                <div class="vscode-fallback" id="vscodeFallback">
                    <p>跳转失败？<a href="{html.escape(vscode_uri)}" class="vscode-link">点击手动打开 VSCode</a></p>
                    <p class="vscode-hint">首次使用需在 VSCode settings.json 中添加：<br><code>{setting_hint}</code></p>
                </div>'''
            vscode_redirect_js = f'''
                // VSCode 自动跳转
                const vscodeUri = {json.dumps(vscode_uri)};
                const vscodeRedirect = document.getElementById('vscodeRedirect');
                const vscodeFallback = document.getElementById('vscodeFallback');

                // 500ms 后尝试跳转
                setTimeout(function() {{
                    window.location.href = vscodeUri;

                    // 2 秒后检测是否仍在页面（跳转失败）
                    setTimeout(function() {{
                        if (vscodeRedirect) {{
                            vscodeRedirect.textContent = '跳转失败';
                            vscodeRedirect.style.color = '#dc3545';
                        }}
                        if (vscodeFallback) {{
                            vscodeFallback.style.display = 'block';
                        }}
                    }}, 2000);
                }}, 500);'''

        response_html = f'''
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <title>{html.escape(title)}</title>
                <style>
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        min-height: 100vh;
                        margin: 0;
                        background: #f5f5f5;
                    }}
                    .card {{
                        background: white;
                        border-radius: 12px;
                        padding: 40px;
                        text-align: center;
                        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
                        max-width: 400px;
                    }}
                    .icon {{
                        font-size: 48px;
                        color: {color};
                        margin-bottom: 20px;
                    }}
                    .title {{
                        font-size: 24px;
                        color: #333;
                        margin-bottom: 10px;
                    }}
                    .message {{
                        color: #666;
                        line-height: 1.6;
                        margin-bottom: 20px;
                    }}
                    .vscode-redirect {{
                        color: #007acc;
                        font-size: 14px;
                        margin-top: 15px;
                        padding-top: 15px;
                        border-top: 1px solid #eee;
                    }}
                    .vscode-fallback {{
                        display: none;
                        color: #666;
                        font-size: 14px;
                        margin-top: 10px;
                    }}
                    .vscode-link {{
                        color: #007acc;
                        text-decoration: none;
                    }}
                    .vscode-link:hover {{
                        text-decoration: underline;
                    }}
                    .vscode-hint {{
                        font-size: 12px;
                        color: #999;
                        margin-top: 10px;
                        line-height: 1.4;
                    }}
                    .vscode-hint code {{
                        display: inline-block;
                        background: #f5f5f5;
                        padding: 2px 6px;
                        border-radius: 3px;
                        font-family: 'Consolas', 'Monaco', monospace;
                        font-size: 11px;
                        color: #d63384;
                    }}
                    .countdown {{
                        color: #999;
                        font-size: 14px;
                        margin-top: 15px;
                        padding-top: 15px;
                        border-top: 1px solid #eee;
                    }}
                    .close-hint {{
                        display: none;
                        color: #666;
                        font-size: 14px;
                        margin-top: 10px;
                    }}
                </style>
            </head>
            <body>
                <div class="card">
                    <div class="icon">{icon}</div>
                    <div class="title">{html.escape(title)}</div>
                    <div class="message">{html.escape(message)}</div>
                    {vscode_redirect_html}
                    <div class="countdown" id="countdown">
                        页面将在 <span id="seconds">{close_timeout}</span> 秒后自动关闭
                    </div>
                    <div class="close-hint" id="closeHint">
                        您现在可以关闭此页面
                    </div>
                </div>
                <script>
                    (function() {{{vscode_redirect_js}
                        const timeout = {close_timeout};
                        let seconds = timeout;
                        const countdownEl = document.getElementById('seconds');
                        const countdownDiv = document.getElementById('countdown');
                        const closeHint = document.getElementById('closeHint');

                        const timer = setInterval(function() {{
                            seconds--;
                            if (countdownEl) {{
                                countdownEl.textContent = seconds;
                            }}

                            if (seconds <= 0) {{
                                clearInterval(timer);
                                if (countdownDiv) {{
                                    countdownDiv.style.display = 'none';
                                }}
                                if (closeHint) {{
                                    closeHint.style.display = 'block';
                                }}
                                // 尝试关闭窗口（只有脚本打开的窗口才能被关闭）
                                try {{
                                    window.close();
                                }} catch (e) {{
                                    // 忽略关闭失败（浏览器安全限制）
                                }}
                            }}
                        }}, 1000);
                    }})();
                </script>
            </body>
            </html>'''

        self.send_response(status)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(response_html.encode('utf-8'))

    def _build_vscode_uri(self, request_id: str) -> str:
        """构建 VSCode URI

        Args:
            request_id: 请求 ID

        Returns:
            VSCode URI 或空字符串（未配置时）
        """
        if not VSCODE_URI_PREFIX:
            return ''

        req_data = self.request_manager.get_request_data(request_id)
        if not req_data:
            return ''

        project_dir = req_data.get('project_dir', '')
        if not project_dir:
            return ''

        # 拼接 VSCode URI: prefix + project_dir
        return f"{VSCODE_URI_PREFIX}{project_dir}"

    def _handle_action(self, request_id: str, action: str):
        """处理权限决策动作（GET /allow, /deny, /always, /interrupt）

        调用纯决策接口，根据返回结果渲染 HTML 响应页面。

        Args:
            request_id: 请求 ID
            action: 动作类型 (allow/always/deny/interrupt)
        """
        # 先获取 VSCode URI（在决策之前，因为之后数据可能被清理）
        vscode_uri = self._build_vscode_uri(request_id)

        # 调用纯决策接口
        success, decision, message = handle_decision(
            self.request_manager, request_id, action
        )

        # 根据结果渲染 HTML 响应
        if success:
            # 成功：使用预定义的标题和消息
            response_info = ACTION_HTML_RESPONSES.get(action, {})
            title = response_info.get('title', '操作成功')
            html_message = response_info.get('message', message)
            self.send_html_response(
                200, title, html_message,
                success=True,
                vscode_uri=vscode_uri
            )
        else:
            # 失败：显示错误信息
            self.send_html_response(
                400, '操作失败', message,
                success=False
            )

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)
        request_id = params.get('id', [None])[0]

        # /status - 获取统计信息
        if path == '/status':
            stats = self.request_manager.get_stats()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                'status': 'ok',
                'mode': 'socket-based (no server-side timeout)',
                **stats
            }).encode())
            return

        # /allow - 批准运行
        if path == '/allow':
            self._handle_action(request_id, 'allow')
            return

        # /always - 始终允许
        if path == '/always':
            self._handle_action(request_id, 'always')
            return

        # /deny - 拒绝运行
        if path == '/deny':
            self._handle_action(request_id, 'deny')
            return

        # /interrupt - 拒绝并中断
        if path == '/interrupt':
            self._handle_action(request_id, 'interrupt')
            return

        self.send_html_response(404, '未找到', '请求的页面不存在。', False)

    def do_POST(self):
        """处理 POST 请求

        callback.py 同时承载飞书网关和 Callback 后端两端的路由。
        当前两端运行在同一进程中，未来分离时各端只保留自己的路由。

        飞书网关侧路由:
            - /register: 接收 Callback 后端注册
            - /feishu/send: 发送飞书消息（Shell 脚本调用，需 owner_id 鉴权）
            - 其他未匹配路径: 飞书事件回调（URL验证、消息事件、卡片回传交互）

        Callback 后端侧路由:
            - /register-callback: 接收飞书网关通知的 auth_token
            - /check-owner-id: 验证 owner_id 是否属于该 Callback 后端
            - /get-chat-id: 根据 session_id 获取对应的 chat_id
            - /get-last-message-id: 获取 session 的最近消息 ID
            - /set-last-message-id: 设置 session 的最近消息 ID
            - /callback/decision: 接收飞书网关转发的决策请求
            - /claude/new: 新建 Claude 会话（飞书网关调用）
            - /claude/continue: 继续 Claude 会话（飞书网关调用）
            - /claude/recent-dirs: 获取近期工作目录
            - /claude/browse-dirs: 浏览子目录

        存储器归属（分离部署时各端只能访问自己归属的存储器）:
            - Callback 后端: SessionChatStore, AuthTokenStore, DirHistoryStore
            - 飞书网关: MessageSessionStore, BindingStore
        """
        parsed = urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get('Content-Length', 0))

        # 验证 Content-Length 范围
        if content_length <= 0 or content_length > MAX_REQUEST_SIZE:
            logger.warning(f"[POST] Invalid Content-Length: {content_length}")
            self.send_response(400)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            error_msg = 'Empty request body' if content_length <= 0 else 'Request body too large'
            self.wfile.write(json.dumps({'error': error_msg}).encode())
            return

        try:
            body = self.rfile.read(content_length)
            data = json.loads(body.decode('utf-8'))
        except json.JSONDecodeError as e:
            logger.warning(f"[POST] Invalid JSON: {e}")
            self.send_response(400)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'Invalid JSON'}).encode())
            return

        # =============================================
        # 飞书网关侧路由
        # 存储器: MessageSessionStore, BindingStore
        # =============================================
        if path == '/register':
            # 接收 Callback 后端注册
            client_ip = self.get_client_ip()
            handled, response = handle_register_request(data, client_ip)
            status = 200 if response.get('success') else 400
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
            return

        if path == '/feishu/send':
            # 发送飞书消息（OpenAPI），Shell 脚本调用此接口
            # 鉴权: 基于 owner_id 查 BindingStore 中的 auth_token 比对
            owner_id = verify_owner_based_auth_token(self, data, '/feishu/send')
            if owner_id is None:
                return  # 验证失败，已发送响应

            handled, response = handle_send_message(data)
            status = 200 if response.get('success') else 400
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
            return

        # =============================================
        # Callback 后端侧路由
        # 存储器: SessionChatStore, AuthTokenStore, DirHistoryStore
        # =============================================
        if path == '/register-callback':
            # 接收飞书网关通知的 auth_token（网关 → Callback）
            handled, response = handle_register_callback(data)
            status = 200 if response.get('success') else 400
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
            return

        if path == '/check-owner-id':
            # 验证 owner_id 是否属于该 Callback 后端
            handled, response = handle_check_owner_id(data)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
            return

        if path == '/get-chat-id':
            # 根据 session_id 获取对应的 chat_id（客户端调用）
            # 验证 auth_token
            from services.session_chat_store import SessionChatStore

            if not verify_global_auth_token(self, '/get-chat-id'):
                return

            session_id = data.get('session_id', '')
            if not session_id:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'chat_id': None}).encode())
                return

            store = SessionChatStore.get_instance()
            chat_id = ''
            if store:
                chat_id = store.get(session_id) or ''

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'chat_id': chat_id}).encode())
            return

        if path == '/get-last-message-id':
            # 根据 session_id 获取对应的 last_message_id（客户端调用）
            # 验证 auth_token
            from services.session_chat_store import SessionChatStore

            if not verify_global_auth_token(self, '/get-last-message-id'):
                return

            session_id = data.get('session_id', '')
            if not session_id:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'last_message_id': ''}).encode())
                return

            store = SessionChatStore.get_instance()
            last_message_id = ''
            if store:
                last_message_id = store.get_last_message_id(session_id)

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'last_message_id': last_message_id}).encode())
            return

        if path == '/set-last-message-id':
            # 设置 session 的 last_message_id（飞书网关调用）
            # 验证 auth_token
            from services.session_chat_store import SessionChatStore

            if not verify_global_auth_token(self, '/set-last-message-id'):
                return

            session_id = data.get('session_id', '')
            message_id = data.get('message_id', '')

            if not session_id or not message_id:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': 'Missing required parameters'}).encode())
                return

            store = SessionChatStore.get_instance()
            if store:
                success = store.set_last_message_id(session_id, message_id)
                if success:
                    logger.info(f"[callback] Set last_message_id: session={session_id}, message_id={message_id}")
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'success': True}).encode())
                else:
                    logger.warning(f"[callback] Failed to set last_message_id: session={session_id}, message_id={message_id}")
                    self.send_response(500)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'success': False, 'error': 'Failed to set last_message_id'}).encode())
            else:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': 'SessionChatStore not initialized'}).encode())
            return

        if path == '/callback/decision':
            # 接收飞书网关转发的决策请求（分离部署）
            return self._handle_callback_decision(data)

        if path == '/claude/continue':
            # 继续 Claude 会话
            # 验证 auth_token（飞书网关调用）
            if not verify_global_auth_token(self, '/claude/continue'):
                return

            success, response = handle_continue_session(data)
            status = 200 if success else 400
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
            return

        if path == '/claude/new':
            # 新建 Claude 会话
            # 验证 auth_token（飞书网关调用）
            if not verify_global_auth_token(self, '/claude/new'):
                return

            success, response = handle_new_session(data)
            status = 200 if success else 400
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
            return

        if path == '/claude/recent-dirs':
            # 获取近期常用工作目录列表
            # 验证 auth_token（飞书网关调用）
            if not verify_global_auth_token(self, '/claude/recent-dirs'):
                return

            try:
                limit = int(data.get('limit', 5))
            except (TypeError, ValueError):
                limit = 5

            from services.dir_history_store import DirHistoryStore
            store = DirHistoryStore.get_instance()
            recent_dirs = store.get_recent_dirs(limit) if store else []

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'dirs': recent_dirs}).encode())
            return

        if path == '/claude/browse-dirs':
            # 浏览指定路径下的子目录
            # 验证 auth_token（飞书网关调用）
            if not verify_global_auth_token(self, '/claude/browse-dirs'):
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
                logger.warning(f"[browse-dirs] Path must be absolute: {request_path}")
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': 'path must be absolute'}).encode())
                return

            # 验证路径存在且可访问
            if not os.path.isdir(request_path):
                logger.warning(f"[browse-dirs] Path not found or not accessible: {request_path}")
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': 'path not found or not accessible'}).encode())
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
                    logger.warning(f"[browse-dirs] Permission denied: {request_path}")
                    dirs = []

                # 按目录名字母排序
                dirs.sort()

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'dirs': dirs,
                    'parent': parent_path,
                    'current': current_path
                }).encode())
                return
            except Exception as e:
                logger.error(f"[browse-dirs] Error listing directory: {e}")
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': 'internal server error'}).encode())
                return

        # 飞书事件回调（URL验证、消息事件、卡片回传交互）
        handled, response = handle_feishu_request(data)
        if handled:
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
            return

        # 未知的 POST 请求
        logger.warning(f"[POST] Unknown request, type: {data.get('type', 'none')}")
        self.send_response(400)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'error': 'Unknown request type'}).encode())

    def _handle_callback_decision(self, data: dict):
        """处理纯决策请求（供飞书网关或其他服务调用）

        此接口返回纯决策结果，不包含 toast 格式。
        调用方根据返回的 success 和 decision 自行生成响应。

        HTTP 状态码语义：
            - 200: 接口正常处理（业务成功/失败通过 success 字段区分）
            - 400: 请求格式错误（缺少必要参数）
            - 401: 身份验证失败（auth_token 无效）

        Args:
            data: 请求数据
                - action: 动作类型 (allow/always/deny/interrupt)
                - request_id: 请求 ID
                - project_dir: 项目目录（可选，用于 always 写入规则）

        Returns:
            JSON 响应：
                - success: 是否成功
                - decision: 决策类型 ("allow"/"deny")，失败时为 null
                - message: 状态消息
        """
        # 验证 auth_token（飞书网关调用）
        if not verify_global_auth_token(self, '/callback/decision', error_body={
            'success': False,
            'decision': None,
            'message': 'Unauthorized'
        }):
            return

        action = data.get('action', '')
        request_id = data.get('request_id', '')
        project_dir = data.get('project_dir', '')

        logger.info(f"[callback/decision] action={action}, request_id={request_id}")

        # 验证参数（请求格式错误返回 400）
        if not action or not request_id:
            logger.warning(f"[callback/decision] Missing params: action={action}, request_id={request_id}")
            self.send_response(400)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                'success': False,
                'decision': None,
                'message': '无效的请求参数'
            }).encode())
            return

        # 调用纯决策接口
        success, decision, message = handle_decision(
            self.request_manager, request_id, action, project_dir
        )

        logger.info(
            f"[callback/decision] result: request_id={request_id}, "
            f"success={success}, decision={decision}, message={message}"
        )

        # 返回 JSON 响应（业务成功/失败统一返回 200，通过 success 字段区分）
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({
            'success': success,
            'decision': decision,
            'message': message
        }).encode())
