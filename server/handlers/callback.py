"""
Callback Handler - HTTP 请求处理器

处理来自飞书卡片按钮的请求
"""

import json
import logging
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from models.decision import Decision
from services.request_manager import RequestManager
from services.rule_writer import write_always_allow_rule

logger = logging.getLogger(__name__)


class CallbackHandler(BaseHTTPRequestHandler):
    """HTTP 请求处理器

    处理来自飞书卡片按钮的请求：
        - /allow?id={request_id}    - 批准运行
        - /always?id={request_id}   - 始终允许并写入规则
        - /deny?id={request_id}     - 拒绝运行
        - /interrupt?id={request_id} - 拒绝并中断
        - /status                    - 查看服务状态
    """

    # 这个类变量由 server.py 设置
    request_manager: RequestManager = None

    def log_message(self, format, *args):
        logger.info(f"{self.address_string()} - {format % args}")

    def send_html_response(self, status: int, title: str, message: str, success: bool = True):
        """发送 HTML 响应页面"""
        color = '#28a745' if success else '#dc3545'
        icon = '✓' if success else '✗'

        html = f'''<!DOCTYPE html>
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
        }}
    </style>
</head>
<body>
    <div class="card">
        <div class="icon">{icon}</div>
        <div class="title">{title}</div>
        <div class="message">{message}</div>
    </div>
</body>
</html>'''

        self.send_response(status)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))

    def _handle_decision(self, request_id: str, decision: dict,
                         success_title: str, success_msg: str,
                         extra_handler=None):
        """通用的决策处理"""
        if not request_id:
            self.send_html_response(400, '参数错误', '缺少请求 ID', False)
            return

        success, error_msg = self.request_manager.resolve(request_id, decision)
        if success:
            # 执行额外的处理逻辑（如写入规则）
            if extra_handler:
                extra_handler(request_id)
            self.send_html_response(200, success_title, success_msg)
        else:
            self.send_html_response(404, '请求无效', f'处理失败：{error_msg}', False)

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
            self._handle_decision(
                request_id,
                Decision.allow(),
                '已批准运行',
                '权限请求已批准，请返回终端查看执行结果。'
            )
            return

        # /always - 始终允许
        if path == '/always':
            def write_rule(rid):
                req_data = self.request_manager.get_request_data(rid)
                if req_data:
                    write_always_allow_rule(
                        req_data.get('project_dir'),
                        req_data.get('tool_name'),
                        req_data.get('tool_input', {})
                    )

            self._handle_decision(
                request_id,
                Decision.allow(),
                '已始终允许',
                '权限请求已批准，并已添加到项目的允许规则中。后续相同操作将自动允许。',
                extra_handler=write_rule
            )
            return

        # /deny - 拒绝运行
        if path == '/deny':
            self._handle_decision(
                request_id,
                Decision.deny('用户通过飞书拒绝'),
                '已拒绝运行',
                '权限请求已拒绝。Claude 可能会尝试其他方式继续工作。'
            )
            return

        # /interrupt - 拒绝并中断
        if path == '/interrupt':
            self._handle_decision(
                request_id,
                Decision.deny('用户通过飞书拒绝并中断', interrupt=True),
                '已拒绝并中断',
                '权限请求已拒绝，Claude 已停止当前任务。'
            )
            return

        self.send_html_response(404, '未找到', '请求的页面不存在。', False)
