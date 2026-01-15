#!/usr/bin/env python3
"""
Claude Code Permission Callback Server

功能：
    HTTP 服务接收飞书卡片按钮的 URL 跳转请求，
    通过 Unix Domain Socket 将用户决策传递给 permission-notify.sh

架构：
    1. permission-notify.sh 发送飞书交互卡片（带按钮）
    2. 用户点击飞书按钮，浏览器访问回调服务器 HTTP 端点
    3. 回调服务器接收 HTTP 请求，通过 Unix Socket 返回决策
    4. permission-notify.sh 接收决策并返回给 Claude Code
"""

import json
import os
import socket
import threading
import time
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path
from typing import Tuple

# =============================================================================
# Claude Code Hook 决策常量
# 参考: https://docs.anthropic.com/en/docs/claude-code/hooks
# =============================================================================

class Decision:
    """决策行为常量"""
    ALLOW = 'allow'      # 允许执行
    DENY = 'deny'        # 拒绝执行

    # 决策 JSON 字段名
    FIELD_BEHAVIOR = 'behavior'
    FIELD_MESSAGE = 'message'
    FIELD_INTERRUPT = 'interrupt'

    @classmethod
    def allow(cls) -> dict:
        """返回允许决策"""
        return {cls.FIELD_BEHAVIOR: cls.ALLOW}

    @classmethod
    def deny(cls, message: str = '', interrupt: bool = False) -> dict:
        """返回拒绝决策"""
        result = {cls.FIELD_BEHAVIOR: cls.DENY}
        if message:
            result[cls.FIELD_MESSAGE] = message
        if interrupt:
            result[cls.FIELD_INTERRUPT] = True
        return result


# =============================================================================
# 配置
# =============================================================================
SOCKET_PATH = os.environ.get('PERMISSION_SOCKET_PATH', '/tmp/claude-permission.sock')
HTTP_PORT = int(os.environ.get('CALLBACK_SERVER_PORT', '8080'))
FEISHU_WEBHOOK_URL = os.environ.get('FEISHU_WEBHOOK_URL', '')
# 请求超时时间（秒），0 表示禁用超时
REQUEST_TIMEOUT = int(os.environ.get('REQUEST_TIMEOUT', '300'))
CLEANUP_INTERVAL = 5  # 清理断开连接的检查间隔（秒）

# 日志配置
log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'log')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f"callback_{time.strftime('%Y%m%d')}.log")

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
logger.info(f"Logging to: {log_file}")


class RequestManager:
    """管理待处理的权限请求

    功能：
        - 注册来自 permission-notify.sh 的权限请求
        - 保存每个请求的 Socket 连接
        - 处理用户决策并通过 Socket 返回
        - 清理断开连接和超时的请求
    """

    # 请求状态常量
    STATUS_PENDING = 'pending'          # 等待用户响应
    STATUS_RESOLVED = 'resolved'        # 已处理（用户已决策）
    STATUS_DISCONNECTED = 'disconnected' # 连接已断开

    def __init__(self):
        self._requests = {}  # request_id -> {conn, data, timestamp, status, resolved_decision}
        self._lock = threading.Lock()

    def register(self, request_id: str, conn: socket.socket, data: dict):
        """注册新的权限请求

        Args:
            request_id: 请求唯一标识
            conn: Unix Socket 连接（用于后续返回决策）
            data: 请求数据（包含 tool_name, tool_input, project_dir 等）
        """
        with self._lock:
            self._requests[request_id] = {
                'conn': conn,
                'data': data,
                'timestamp': time.time(),
                'status': self.STATUS_PENDING,
                'resolved_decision': None  # 记录已处理的决策类型
            }
            logger.info(f"Registered request: {request_id}")


    def _close_connection(self, conn: socket.socket):
        """安全关闭 socket 连接"""
        try:
            conn.close()
        except Exception:
            pass

    def resolve(self, request_id: str, decision: dict) -> Tuple[bool, str]:
        """处理用户决策，返回 (是否成功, 错误信息)

        Args:
            request_id: 请求 ID
            decision: 决策内容（behavior, message, interrupt）

        Returns:
            (成功标志, 错误信息)

        处理流程：
            1. 检查请求是否存在且状态有效
            2. 通过 Socket 连接发送决策给 permission-notify.sh
            3. 标记请求为已解决并关闭连接
        """
        with self._lock:
            if request_id not in self._requests:
                logger.warning(f"[resolve] Request {request_id} not found")
                return False, "请求不存在或已被清理"

            req = self._requests[request_id]
            age = time.time() - req['timestamp']
            logger.info(f"[resolve] Request {request_id}, status={req['status']}, age={age:.1f}s")

            # 检查请求状态
            if req['status'] == self.STATUS_RESOLVED:
                resolved_type = req.get('resolved_decision', '处理')
                logger.info(f"[resolve] Already resolved: {resolved_type}")
                return False, f"请求已被{resolved_type}，请勿重复操作"

            if req['status'] == self.STATUS_DISCONNECTED:
                logger.info(f"[resolve] Already disconnected")
                return False, "连接已断开，Claude 可能已继续执行其他操作"

            # 发送决策给等待的进程
            try:
                # 检查 socket 连接是否仍然有效
                conn = req['conn']
                logger.debug(f"[resolve] Checking socket connection (fileno={conn.fileno()})")

                # 确保连接处于阻塞模式
                conn.settimeout(None)

                response = json.dumps({
                    'success': True,
                    'decision': decision,
                    'tool_name': req['data'].get('tool_name'),
                    'tool_input': req['data'].get('tool_input'),
                    'project_dir': req['data'].get('project_dir')
                })
                response_bytes = response.encode('utf-8')
                logger.info(f"[resolve] Sending {len(response_bytes)} bytes to socket (fileno={conn.fileno()})...")

                # 使用长度前缀协议：4 字节长度 + 数据
                length_prefix = len(response_bytes).to_bytes(4, 'big')
                total_data = length_prefix + response_bytes
                logger.debug(f"[resolve] Total data size: {len(total_data)} bytes (4 header + {len(response_bytes)} payload)")

                conn.sendall(total_data)
                logger.info(f"[resolve] Data sent successfully")

                # 成功：标记为已解决（不关闭连接，让客户端关闭）
                behavior = decision.get(Decision.FIELD_BEHAVIOR, 'unknown')
                req['status'] = self.STATUS_RESOLVED
                req['resolved_decision'] = '批准' if behavior == Decision.ALLOW else '拒绝'
                logger.info(f"[resolve] Request {request_id} resolved: {behavior}")
                return True, ""

            except (BrokenPipeError, ConnectionResetError, OSError) as e:
                error_type = type(e).__name__
                logger.error(f"[resolve] {error_type} for {request_id}: {e}")
                req['status'] = self.STATUS_DISCONNECTED
                self._close_connection(req['conn'])
                return False, f"连接已断开（{error_type}），Claude 可能已超时或取消"

            except Exception as e:
                logger.error(f"[resolve] Unexpected error: {type(e).__name__}: {e}")
                import traceback
                logger.error(f"[resolve] Traceback:\n{traceback.format_exc()}")
                return False, f"发送决策失败: {str(e)}"

    def get_request_data(self, request_id: str) -> dict:
        """获取请求数据（用于始终允许时写入规则）"""
        with self._lock:
            if request_id in self._requests:
                return self._requests[request_id]['data']
            return None

    def _send_fallback_response(self, request_id: str, req: dict, conn, age: float):
        """发送"回退终端"响应，让 Claude 回退到终端交互模式"""
        try:
            response = json.dumps({
                'success': False,
                'fallback_to_terminal': True,
                'error': 'server_timeout',
                'message': f'服务器超时（{age:.0f}秒），请在终端操作'
            })
            response_bytes = response.encode('utf-8')
            length_prefix = len(response_bytes).to_bytes(4, 'big')
            total_data = length_prefix + response_bytes

            conn.settimeout(5)  # 设置发送超时
            conn.sendall(total_data)
            logger.info(f"Sent fallback response to {request_id} (age={age:.0f}s)")
        except Exception as e:
            logger.warning(f"Failed to send fallback response to {request_id}: {e}")
        finally:
            req['status'] = self.STATUS_DISCONNECTED
            self._close_connection(conn)

    def _is_connection_alive(self, conn) -> bool:
        """检测 socket 连接是否仍然存活"""
        try:
            # 检查 socket 是否有效
            if conn.fileno() == -1:
                return False
            # 使用非阻塞 peek 检测连接状态
            conn.setblocking(False)
            try:
                # MSG_PEEK 不会消费数据，只是查看
                data = conn.recv(1, socket.MSG_PEEK | socket.MSG_DONTWAIT)
                # 如果返回空，说明对方已关闭连接
                if data == b'':
                    return False
            except BlockingIOError:
                # 没有数据可读，但连接仍然存活
                pass
            except (ConnectionResetError, BrokenPipeError, OSError):
                return False
            finally:
                conn.setblocking(True)
            return True
        except Exception:
            return False

    def cleanup_disconnected(self, max_age: int = None):
        """清理长时间未处理的请求和断开的连接

        功能：
            - 检测并清理已断开的 Socket 连接（无论是否启用超时）
            - 如果启用超时，超时请求发送"回退终端"响应

        Args:
            max_age: 超时秒数，None 表示使用 REQUEST_TIMEOUT 配置，0 表示禁用超时
        """
        if max_age is None:
            max_age = REQUEST_TIMEOUT

        with self._lock:
            now = time.time()
            for rid, req in list(self._requests.items()):
                if req['status'] == self.STATUS_PENDING:
                    age = now - req['timestamp']
                    conn = req['conn']

                    # 检查连接是否已断开（无论是否启用超时）
                    if not self._is_connection_alive(conn):
                        req['status'] = self.STATUS_DISCONNECTED
                        self._close_connection(conn)
                        logger.info(f"Cleaned up dead connection: {rid} (age={age:.0f}s)")
                        continue

                    # 如果启用了超时，检查是否超时
                    if max_age > 0 and age > max_age:
                        # 发送"回退终端"响应，而不是直接关闭连接
                        self._send_fallback_response(rid, req, conn, age)

                # 已处理或已断开的请求，从内存中移除
                elif req['status'] in (self.STATUS_RESOLVED, self.STATUS_DISCONNECTED):
                    if now - req['timestamp'] > 60:  # 保留 60 秒供调试
                        del self._requests[rid]
                        logger.debug(f"Removed old request: {rid}")

    def get_stats(self) -> dict:
        """获取当前请求统计信息"""
        with self._lock:
            now = time.time()
            stats = {
                'pending': 0,
                'resolved': 0,
                'disconnected': 0,
                'requests': {}
            }
            for rid, req in self._requests.items():
                stats[req['status']] = stats.get(req['status'], 0) + 1
                stats['requests'][rid] = {
                    'status': req['status'],
                    'age_seconds': int(now - req['timestamp']),
                    'tool': req['data'].get('tool_name', 'Unknown')
                }
            return stats


# 全局请求管理器
request_manager = RequestManager()


# 工具名称到规则格式的映射
RULE_FORMATTERS = {
    'Bash': lambda i: f"Bash({i.get('command', '')})",
    'Edit': lambda i: f"Edit({i.get('file_path', '')})",
    'Write': lambda i: f"Write({i.get('file_path', '')})",
    'Read': lambda i: f"Read({i.get('file_path', '')})",
    'Glob': lambda i: f"Glob({i.get('pattern', '')})",
    'Grep': lambda i: f"Grep({i.get('pattern', '')})",
    'WebFetch': lambda i: f"WebFetch({i.get('url', '')})",
    'WebSearch': lambda i: f"WebSearch({i.get('query', '')})",
}


def write_always_allow_rule(project_dir: str, tool_name: str, tool_input: dict):
    """写入始终允许规则到 .claude/settings.local.json

    功能：
        将权限规则写入项目的 settings.local.json，
        使 Claude Code 后续自动允许相同操作，无需用户再次确认。

    Args:
        project_dir: 项目目录路径
        tool_name: 工具名称（Bash, Edit, Write 等）
        tool_input: 工具输入参数

    Returns:
        bool: 是否成功写入
    """
    if not project_dir:
        logger.warning("No project_dir provided, cannot write always-allow rule")
        return False

    # 使用映射生成规则
    formatter = RULE_FORMATTERS.get(tool_name, lambda i: f"{tool_name}(*)")
    rule = formatter(tool_input)

    # 读取或创建配置文件
    settings_dir = Path(project_dir) / '.claude'
    settings_file = settings_dir / 'settings.local.json'

    try:
        settings_dir.mkdir(parents=True, exist_ok=True)

        if settings_file.exists():
            with open(settings_file, 'r', encoding='utf-8') as f:
                settings = json.load(f)
        else:
            settings = {}

        # 添加规则
        if 'permissions' not in settings:
            settings['permissions'] = {}
        if 'allow' not in settings['permissions']:
            settings['permissions']['allow'] = []

        if rule not in settings['permissions']['allow']:
            settings['permissions']['allow'].append(rule)
            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2, ensure_ascii=False)
            logger.info(f"Added always-allow rule: {rule}")

        return True
    except Exception as e:
        logger.error(f"Failed to write always-allow rule: {e}")
        return False


class CallbackHandler(BaseHTTPRequestHandler):
    """HTTP 请求处理器

    处理来自飞书卡片按钮的请求：
        - /allow?id={request_id}    - 批准运行
        - /always?id={request_id}   - 始终允许并写入规则
        - /deny?id={request_id}     - 拒绝运行
        - /interrupt?id={request_id} - 拒绝并中断
        - /status                    - 查看服务状态
    """

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

        success, error_msg = request_manager.resolve(request_id, decision)
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
            stats = request_manager.get_stats()
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
                req_data = request_manager.get_request_data(rid)
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


def handle_socket_client(conn: socket.socket, addr):
    """处理来自 permission-notify.sh 的 Socket 连接

    流程：
        1. 接收请求数据（JSON 格式）
        2. 注册请求到 RequestManager（保持连接打开）
        3. 发送确认响应
        4. 等待 resolve() 通过此连接返回用户决策
        5. 连接在 resolve() 中关闭
    """
    fileno = conn.fileno()
    logger.info(f"[socket] New connection, fileno={fileno}")

    try:
        # 设置接收超时，避免永久阻塞
        conn.settimeout(5.0)
        logger.debug(f"[socket] Set receive timeout to 5s")

        data = b''
        start_time = time.time()

        while True:
            chunk = conn.recv(4096)
            elapsed = time.time() - start_time
            logger.debug(f"[socket] Received {len(chunk) if chunk else 0} bytes (elapsed: {elapsed:.1f}s)")

            if not chunk:
                logger.warning(f"[socket] Connection closed by client (received {len(data)} bytes total)")
                break

            data += chunk

            # 检查是否收到完整的 JSON
            try:
                json.loads(data.decode('utf-8'))
                logger.debug(f"[socket] Complete JSON received ({len(data)} bytes)")
                break
            except json.JSONDecodeError as e:
                logger.debug(f"[socket] Incomplete JSON, continuing... ({str(e)[:50]})")
                continue

        # 恢复阻塞模式（后续操作不需要超时）
        conn.settimeout(None)
        logger.debug(f"[socket] Removed timeout, connection ready for response")

        if not data:
            logger.warning(f"[socket] No data received, closing connection")
            conn.close()
            return

        logger.info(f"[socket] Received {len(data)} bytes of JSON data")

        request = json.loads(data.decode('utf-8'))
        request_id = request.get('request_id')

        if not request_id:
            conn.sendall(json.dumps({'success': False, 'error': 'missing request_id'}).encode())
            conn.close()
            return

        logger.info(f"[socket] Request ID: {request_id}")

        # 注册请求（保存 socket 连接供后续 resolve 使用）
        # 注意：不再需要完整的请求数据，因为飞书卡片已由 permission-notify.sh 发送
        request_manager.register(request_id, conn, request)

        # 发送确认响应
        conn.sendall(json.dumps({'success': True, 'message': 'Request registered'}).encode())

        # 重要：不关闭连接！等待用户响应后由 resolve() 关闭
        logger.info(f"[socket] Request {request_id} registered, waiting for user response...")

    except Exception as e:
        logger.error(f"Socket handler error: {e}")
        try:
            conn.sendall(json.dumps({'success': False, 'error': str(e)}).encode())
            conn.close()
        except:
            pass


def run_socket_server():
    """运行 Unix Domain Socket 服务器

    功能：
        监听 Unix Socket，接受来自 permission-notify.sh 的连接
    """
    # 删除已存在的 socket 文件
    if os.path.exists(SOCKET_PATH):
        os.unlink(SOCKET_PATH)

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(SOCKET_PATH)
    os.chmod(SOCKET_PATH, 0o666)
    server.listen(10)

    logger.info(f"Socket server listening on {SOCKET_PATH}")

    while True:
        conn, addr = server.accept()
        thread = threading.Thread(target=handle_socket_client, args=(conn, addr))
        thread.daemon = True
        thread.start()


def run_cleanup_thread():
    """运行断开连接清理线程

    功能：
        定期清理断开连接和超时的请求
    """
    while True:
        time.sleep(CLEANUP_INTERVAL)
        request_manager.cleanup_disconnected()


def main():
    """主函数：启动所有服务

    服务组件：
        1. Unix Socket 服务器 - 接收 permission-notify.sh 的连接
        2. 清理线程 - 定期清理断开连接
        3. HTTP 服务器 - 接收飞书按钮的回调请求
    """
    logger.info("Starting Claude Code Permission Callback Server")
    logger.info(f"HTTP Port: {HTTP_PORT}")
    logger.info(f"Socket Path: {SOCKET_PATH}")
    logger.info(f"Request Timeout: {REQUEST_TIMEOUT}s ({'disabled' if REQUEST_TIMEOUT == 0 else 'enabled'})")

    if not FEISHU_WEBHOOK_URL:
        logger.warning("FEISHU_WEBHOOK_URL not set - notifications will be skipped")

    # 启动 Socket 服务器线程
    socket_thread = threading.Thread(target=run_socket_server)
    socket_thread.daemon = True
    socket_thread.start()

    # 启动清理线程
    cleanup_thread = threading.Thread(target=run_cleanup_thread)
    cleanup_thread.daemon = True
    cleanup_thread.start()

    # 启动 HTTP 服务器
    server = HTTPServer(('0.0.0.0', HTTP_PORT), CallbackHandler)
    logger.info(f"HTTP server listening on port {HTTP_PORT}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        server.shutdown()


if __name__ == '__main__':
    main()
