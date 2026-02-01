"""
Callback Handler - HTTP 请求处理器

处理权限回调请求（GET）和飞书事件（POST）
"""

import json
import logging
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from services.request_manager import RequestManager
from services.decision_handler import handle_decision
from config import CLOSE_PAGE_TIMEOUT, VSCODE_URI_PREFIX
from handlers.feishu import handle_feishu_request, handle_send_message
from handlers.claude import handle_continue_session

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

    def send_html_response(self, status: int, title: str, message: str,
                           success: bool = True, close_timeout: int = None,
                           vscode_uri: str = None):
        """发送 HTML 响应页面

        Args:
            status: HTTP 状态码
            title: 页面标题
            message: 显示消息
            success: 是否成功
            close_timeout: 自动关闭页面超时时间（秒），默认从环境变量 CLOSE_PAGE_TIMEOUT 读取
            vscode_uri: VSCode URI，配置后会自动跳转到 VSCode
        """
        if close_timeout is None:
            close_timeout = CLOSE_PAGE_TIMEOUT
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
                    <p>跳转失败？<a href="{vscode_uri}" class="vscode-link">点击手动打开 VSCode</a></p>
                    <p class="vscode-hint">首次使用需在 VSCode settings.json 中添加：<br><code>{setting_hint}</code></p>
                </div>'''
            vscode_redirect_js = f'''
                // VSCode 自动跳转
                const vscodeUri = "{vscode_uri}";
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

        html = f'''
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <title>{title}</title>
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
                    <div class="title">{title}</div>
                    <div class="message">{message}</div>
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
        self.wfile.write(html.encode('utf-8'))

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
        success, decision, message = handle_decision(self.request_manager, request_id, action)

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

        路由:
            - /callback/decision: 接收飞书网关转发的决策请求（分离部署）
            - /feishu/send: 发送飞书消息（OpenAPI）
            - /claude/continue: 继续 Claude 会话
            - 其他: 飞书事件回调（URL验证、消息事件、卡片回传交互）
        """
        parsed = urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get('Content-Length', 0))
        if content_length == 0:
            self.send_response(400)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'Empty request body'}).encode())
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

        # 路由分发
        if path == '/callback/decision':
            # 接收飞书网关转发的决策请求（分离部署）
            return self._handle_callback_decision(data)

        if path == '/feishu/send':
            # 发送飞书消息（OpenAPI）
            handled, response = handle_send_message(data)
            status = 200 if response.get('success') else 400
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
            return

        if path == '/claude/continue':
            # 继续 Claude 会话
            success, response = handle_continue_session(data)
            status = 200 if success else 400
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
            return

        # 飞书事件回调（URL验证、消息事件、卡片回传交互）
        handled, response = handle_feishu_request(data, self.request_manager)
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
