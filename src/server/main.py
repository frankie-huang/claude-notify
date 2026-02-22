#!/usr/bin/env python3
"""
Claude Code Permission Callback Server

功能：
    HTTP 服务接收飞书卡片按钮的 URL 跳转请求，
    通过 Unix Domain Socket 将用户决策传递给 hooks/permission-notify.sh

架构：
    1. hooks/permission-notify.sh 发送飞书交互卡片（带按钮）
    2. 用户点击飞书按钮，浏览器访问回调服务器 HTTP 端点
    3. 回调服务器接收 HTTP 请求，通过 Unix Socket 返回决策
    4. hooks/permission-notify.sh 接收决策并返回给 Claude Code

通信协议详见: shared/protocol.md
"""

import base64
import http.server
import json
import os
import socket
import socketserver
import threading
import time
import logging

from config import (
    PERMISSION_REQUEST_TIMEOUT, DEFAULT_PERMISSION_REQUEST_TIMEOUT,
    get_config, get_config_int,
    DEFAULT_SOCKET_PATH, DEFAULT_HTTP_PORT,
    FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_SEND_MODE,
    CALLBACK_SERVER_URL, FEISHU_OWNER_ID, FEISHU_GATEWAY_URL
)
from services.request_manager import RequestManager
from services.feishu_api import FeishuAPIService
from services.message_session_store import MessageSessionStore
from services.dir_history_store import DirHistoryStore
from services.binding_store import BindingStore
from handlers.http_handler import HttpRequestHandler
from services.auth_token_store import AuthTokenStore
from services.session_chat_store import SessionChatStore

# =============================================================================
# 配置 (优先级: .env > 环境变量 > 默认值)
# =============================================================================

SOCKET_PATH = get_config('PERMISSION_SOCKET_PATH', DEFAULT_SOCKET_PATH)
HTTP_PORT = get_config_int('CALLBACK_SERVER_PORT', int(DEFAULT_HTTP_PORT))
FEISHU_WEBHOOK_URL = get_config('FEISHU_WEBHOOK_URL', '')
CLEANUP_INTERVAL = 5  # 清理断开连接的检查间隔（秒）

# 日志配置 (src/server -> src -> project_root)
src_dir = os.path.dirname(os.path.dirname(__file__))
project_root = os.path.dirname(src_dir)
log_dir = os.path.join(project_root, 'log')
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


# =============================================================================
# Socket 服务器处理
# =============================================================================

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
        recv_timeout = 5.0
        conn.settimeout(recv_timeout)
        logger.debug(f"[socket] Set receive timeout to {recv_timeout}s")

        data = b''
        start_time = time.time()

        while True:
            try:
                chunk = conn.recv(4096)
            except socket.timeout:
                logger.warning(f"[socket] Receive timeout after {recv_timeout}s (received {len(data)} bytes so far)")
                conn.close()
                return
            except OSError as e:
                logger.warning(f"[socket] Receive error: {e} (received {len(data)} bytes so far)")
                conn.close()
                return

            elapsed = time.time() - start_time
            logger.debug(f"[socket] Received {len(chunk) if chunk else 0} bytes (elapsed: {elapsed:.1f}s)")

            if not chunk:
                logger.warning(f"[socket] Connection closed by client (received {len(data)} bytes total)")
                conn.close()
                return

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

        logger.info(f"[socket] Received {len(data)} bytes of JSON data")

        request = json.loads(data.decode('utf-8'))

        # 健康检查探测：收到 ping 消息，回复 pong 后关闭
        if request.get('type') == 'ping':
            conn.sendall(json.dumps({'type': 'pong'}).encode())
            conn.close()
            logger.debug("[socket] Health check ping received, pong sent")
            return

        request_id = request.get('request_id')
        hook_pid = request.get('hook_pid')  # 新增：hook 脚本的进程 ID

        if not request_id:
            conn.sendall(json.dumps({'success': False, 'error': 'missing request_id'}).encode())
            conn.close()
            return

        # 保存 hook_pid 到 request 中，供后续使用
        request['hook_pid'] = hook_pid

        # 解码 raw_input_encoded 提取 session_id、tool_name 和 tool_input
        # 这些字段用于日志记录和 /always 端点生成正确的权限规则
        raw_input_encoded = request.get('raw_input_encoded')
        if raw_input_encoded:
            try:
                raw_input = json.loads(base64.b64decode(raw_input_encoded).decode('utf-8'))
                request['session_id'] = raw_input.get('session_id', 'unknown')
                request['tool_name'] = raw_input.get('tool_name')
                request['tool_input'] = raw_input.get('tool_input', {})
                logger.debug(f"[socket] Decoded session_id: {request['session_id']}, tool_name: {request['tool_name']}")
            except Exception as e:
                logger.warning(f"[socket] Failed to decode raw_input_encoded: {e}")
                request['session_id'] = 'unknown'
        else:
            request['session_id'] = 'unknown'

        session_id = request['session_id']
        logger.info(f"[socket] Request ID: {request_id}, Session: {session_id}, Hook PID: {hook_pid}")

        # 注册请求（保存 socket 连接供后续 resolve 使用）
        RequestManager.get_instance().register(request_id, conn, request)

        # 发送确认响应
        conn.sendall(json.dumps({
            'success': True,
            'message': 'Request registered',
            'session_id': session_id
        }).encode())

        # 重要：不关闭连接！等待用户响应后由 resolve() 关闭
        logger.info(f"[socket] Request {request_id} registered (Session: {session_id}), waiting for user response...")

    except Exception as e:
        logger.error(f"Socket handler error: {e}")
        try:
            conn.sendall(json.dumps({'success': False, 'error': str(e)}).encode())
            conn.close()
        except Exception:
            pass


def run_socket_server():
    """运行 Unix Domain Socket 服务器

    功能：
        监听 Unix Socket，接受来自 permission-notify.sh 的连接
    """
    # 删除已存在的 socket 文件（避免 TOCTOU 竞态条件）
    try:
        os.unlink(SOCKET_PATH)
    except FileNotFoundError:
        pass

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(SOCKET_PATH)
    os.chmod(SOCKET_PATH, 0o600)  # 仅所有者可读写，防止其他用户访问
    server.listen(10)

    logger.info(f"Socket server listening on {SOCKET_PATH}")

    while True:
        conn, addr = server.accept()
        thread = threading.Thread(target=handle_socket_client, args=(conn, addr))
        thread.daemon = True
        thread.start()


def run_cleanup_thread():
    """运行清理线程 - 使用独立的定时器进行不同频率的清理

    清理任务：
        - 清理断开连接（每 5 秒）
        - 清理过期数据（每 1 小时）
    """
    # 高频清理：断开连接（5秒间隔）
    def cleanup_disconnected_loop():
        while True:
            time.sleep(CLEANUP_INTERVAL)
            RequestManager.get_instance().cleanup_disconnected()

    # 低频清理：过期数据（1小时间隔）
    def cleanup_expired_loop():
        while True:
            time.sleep(3600)  # 1 小时
            _cleanup_expired_data()

    # 启动两个独立的清理线程
    for target in (cleanup_disconnected_loop, cleanup_expired_loop):
        thread = threading.Thread(target=target, daemon=True)
        thread.start()


def _cleanup_expired_data():
    """清理过期的数据

    数据存储过期与清理机制说明：

    | Store                | 文件名                  | 过期时间 | Lazy | 定期 | 说明                     |
    |----------------------|-------------------------|----------|------|------|--------------------------|
    | MessageSessionStore  | message_sessions.json   | 7 天     | ✅   | ✅   | 本函数清理                |
    | SessionChatStore     | session_chats.json      | 7 天     | ✅   | ✅   | 本函数清理                |
    | BindingStore         | bindings.json           | 无       | ❌   | ❌   | 需先实现自动续期机制       |
    | DirHistoryStore      | dir_history.json        | 30 天    | ✅   | ❌   | 写入时清理，死数据无害     |
    | AuthTokenStore       | auth_token.json         | 无       | ❌   | ❌   | 单条记录，每次注册覆盖     |

    本函数清理范围：
        - message_sessions.json (7天过期)
        - session_chats.json (7天过期)
    """
    # 清理 message_sessions
    store = MessageSessionStore.get_instance()
    if store:
        expired_count = store.cleanup_expired()
        if expired_count > 0:
            logger.info(f"[cleanup] Cleaned {expired_count} expired session mappings")

    # 清理 session_chats
    chat_store = SessionChatStore.get_instance()
    if chat_store:
        expired_count = chat_store.cleanup_expired()
        if expired_count > 0:
            logger.info(f"[cleanup] Cleaned {expired_count} expired chat mappings")

# =============================================================================
# 多线程 HTTP 服务器
# =============================================================================

class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    """支持多线程的 HTTP Server

    允许多个请求并发处理，避免飞书回调转发到 /cb/decision 时死锁。
    """
    allow_reuse_address = True
    daemon_threads = True


# =============================================================================
# 主函数
# =============================================================================

def main():
    """主函数：启动所有服务

    服务组件：
        1. Unix Socket 服务器 - 接收 permission-notify.sh 的连接
        2. 清理线程 - 定期清理断开连接和过期 session
        3. HTTP 服务器 - 接收飞书按钮的回调请求
        4. RequestManager - 管理待处理的权限请求
        5. MessageSessionStore - 维护 message_id 到 session 的映射
        6. SessionChatStore - 维护 session_id 到 chat_id 的映射
        7. DirHistoryStore - 记录目录使用历史
        8. BindingStore - 维护 owner_id 到 callback_url 的绑定（网关专用）
        9. AuthTokenStore - 存储网关注册的 auth_token（Callback 后端专用）
        10. FeishuAPIService - 飞书 OpenAPI 服务（OpenAPI 模式）
        11. AutoRegister - 启动时自动向飞书网关注册（可选）
    """
    logger.info("Starting Claude Code Permission Callback Server")
    logger.info(f"HTTP Port: {HTTP_PORT}")
    logger.info(f"Socket Path: {SOCKET_PATH}")
    env_timeout = os.environ.get('PERMISSION_REQUEST_TIMEOUT', '')
    if env_timeout:
        logger.info(f"Request Timeout: {PERMISSION_REQUEST_TIMEOUT}s (from env: PERMISSION_REQUEST_TIMEOUT={env_timeout})")
    else:
        logger.info(f"Request Timeout: {PERMISSION_REQUEST_TIMEOUT}s (default: {DEFAULT_PERMISSION_REQUEST_TIMEOUT}s)")

    if not FEISHU_WEBHOOK_URL:
        logger.warning("FEISHU_WEBHOOK_URL not set - webhook notifications will be skipped")

    # 初始化 RequestManager（权限请求管理）
    RequestManager.initialize()

    # 初始化 MessageSessionStore（用于继续会话功能）
    runtime_dir = os.path.join(project_root, 'runtime')
    MessageSessionStore.initialize(runtime_dir)
    logger.info(f"MessageSessionStore initialized with runtime_dir={runtime_dir}")

    # 初始化 DirHistoryStore（用于记录目录使用历史）
    DirHistoryStore.initialize(runtime_dir)
    logger.info(f"DirHistoryStore initialized with runtime_dir={runtime_dir}")

    # 初始化 BindingStore（用于网关注册功能）
    BindingStore.initialize(runtime_dir)
    logger.info(f"BindingStore initialized with runtime_dir={runtime_dir}")

    # 初始化 AuthTokenStore（用于存储网关注册的 auth_token）
    AuthTokenStore.initialize(runtime_dir)
    logger.info(f"AuthTokenStore initialized with runtime_dir={runtime_dir}")

    # 初始化 SessionChatStore（callback 后端存储 session_id -> chat_id 映射）
    SessionChatStore.initialize(runtime_dir)
    logger.info(f"SessionChatStore initialized with runtime_dir={runtime_dir}")

    # 初始化飞书 OpenAPI 服务
    if FEISHU_SEND_MODE == 'openapi':
        if FEISHU_APP_ID and FEISHU_APP_SECRET:
            FeishuAPIService.initialize()
            logger.info(f"Feishu OpenAPI service initialized (mode: {FEISHU_SEND_MODE})")
        else:
            logger.warning("FEISHU_SEND_MODE requires FEISHU_APP_ID and FEISHU_APP_SECRET")
    else:
        logger.info(f"Feishu send mode: {FEISHU_SEND_MODE}")

    # 启动 Socket 服务器线程
    socket_thread = threading.Thread(target=run_socket_server)
    socket_thread.daemon = True
    socket_thread.start()

    # 启动清理线程（内部启动独立的 daemon 线程）
    run_cleanup_thread()

    # 启动 HTTP 服务器（使用 ThreadedHTTPServer 支持并发请求）
    # 这样飞书回调请求和转发到 /cb/decision 的请求可以并发处理
    server = ThreadedHTTPServer(('0.0.0.0', HTTP_PORT), HttpRequestHandler)
    logger.info(f"HTTP server listening on port {HTTP_PORT} (threading enabled)")

    # 自动注册到飞书网关（需在 HTTP 服务启动后执行）
    from services.auto_register import AutoRegister
    AutoRegister.initialize(CALLBACK_SERVER_URL, FEISHU_OWNER_ID, FEISHU_GATEWAY_URL)
    auto_register = AutoRegister.get_instance()
    if auto_register and auto_register.enabled:
        auto_register.register_in_background()
    else:
        logger.info("Auto-registration disabled (missing CALLBACK_SERVER_URL, FEISHU_OWNER_ID, or FEISHU_GATEWAY_URL)")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        server.shutdown()


if __name__ == '__main__':
    main()
