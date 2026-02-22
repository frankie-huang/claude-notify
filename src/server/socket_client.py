#!/usr/bin/env python3
"""
Socket 客户端 - 替代 socat 实现可靠的双向通信

用法: echo '{"json": "data"}' | python3 socket_client.py [socket_path]

功能：
    从 stdin 读取请求数据，通过 Unix Socket 发送到回调服务器，
    设置客户端超时作为兜底（比服务端超时大 30 秒）

通信协议详见: shared/protocol.md
    - 发送：原始 JSON 字符串（UTF-8 编码）
    - 接收：4 字节长度前缀 + JSON 数据（大端序）

优势：
    - 避免 socat 的 half-close 问题
    - 支持长度前缀协议，确保数据完整性
    - 客户端超时 = 服务端超时 + 30 秒缓冲，确保服务端先触发超时
"""

import sys
import os
import socket
import json
import logging
import time

from config import PERMISSION_REQUEST_TIMEOUT, CLIENT_TIMEOUT, CLIENT_TIMEOUT_BUFFER

# 日志配置（按日期切分）
# 从 src/server/socket_client.py 向上两级到 src，再向上到项目根目录
src_dir = os.path.dirname(os.path.dirname(__file__))
project_root = os.path.dirname(src_dir)
log_dir = os.path.join(project_root, 'log')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f"socket_client_{time.strftime('%Y%m%d')}.log")

logging.basicConfig(
    level=logging.DEBUG,
    format=f'[%(process)d] %(asctime)s.%(msecs)03d [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
logger.info(f"Logging to: {log_file}")
logger.info(f"Client timeout: {CLIENT_TIMEOUT}s (server: {PERMISSION_REQUEST_TIMEOUT}s + buffer: {CLIENT_TIMEOUT_BUFFER}s)")


def main():
    """Socket 客户端主流程

    执行步骤：
        1. 从 stdin 读取请求数据
        2. 连接到 Unix Socket
        3. 发送请求数据
        4. 等待服务器响应（超时 = 服务端超时 + 30 秒缓冲）
        5. 解析长度前缀协议的响应
        6. 输出响应到 stdout
    """
    start_time = time.time()
    socket_path = sys.argv[1] if len(sys.argv) > 1 else '/tmp/claude-permission.sock'

    logger.debug(f"Starting: socket_path={socket_path}")

    # 从 stdin 读取请求数据
    request_data = sys.stdin.read()
    if not request_data:
        logger.error("No input data")
        sys.exit(1)

    logger.debug(f"Request data: {len(request_data)} bytes")
    logger.debug(f"Request content: {request_data[:200]}...")

    sock = None
    try:
        # 创建 Unix socket 连接
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(socket_path)
        # 设置客户端超时作为兜底（比服务端超时大，确保服务端先触发）
        sock.settimeout(CLIENT_TIMEOUT)
        logger.debug(f"Connected, fileno={sock.fileno()}, timeout={CLIENT_TIMEOUT}s")

        # 发送请求（不关闭写端，保持连接双向可用）
        sock.sendall(request_data.encode('utf-8'))
        logger.debug(f"Request sent ({len(request_data)} bytes), waiting for response (timeout={CLIENT_TIMEOUT}s)...")

        # 先读取并丢弃服务器的确认响应（不带长度前缀的 JSON）
        # main.py:178-179 发送: {"success": true, "message": "Request registered"}
        ack_data = b''
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                logger.error("Connection closed while reading ack")
                print(json.dumps({
                    'success': False,
                    'error': 'ack_read_failed',
                    'decision': {'behavior': 'deny', 'message': '读取确认响应失败'}
                }))
                return
            ack_data += chunk
            # 检查是否收到完整的 JSON
            try:
                json.loads(ack_data.decode('utf-8'))
                logger.debug(f"Received ack: {ack_data.decode('utf-8')}")
                break
            except json.JSONDecodeError:
                # JSON 不完整，继续读取
                continue

        # 等待并读取决策响应（带长度前缀协议，无限等待）
        wait_start = time.time()
        logger.debug("Waiting for decision response...")

        # 先读取 4 字节长度前缀
        length_data = b''
        while len(length_data) < 4:
            chunk = sock.recv(4 - len(length_data))
            if not chunk:
                elapsed = time.time() - wait_start
                logger.error(f"Connection closed while reading length (elapsed: {elapsed:.1f}s)")
                print(json.dumps({
                    'success': False,
                    'error': 'length_read_failed',
                    'decision': {'behavior': 'deny', 'message': '读取响应长度失败'}
                }))
                return
            length_data += chunk

        msg_length = int.from_bytes(length_data, 'big')
        logger.debug(f"Message length: {msg_length} bytes")

        # 读取完整消息
        response_data = b''
        read_start = time.time()
        while len(response_data) < msg_length:
            chunk = sock.recv(min(4096, msg_length - len(response_data)))
            if not chunk:
                elapsed = time.time() - read_start
                logger.error(f"Connection closed at {len(response_data)}/{msg_length} bytes (elapsed: {elapsed:.1f}s)")
                print(json.dumps({
                    'success': False,
                    'error': 'incomplete_response',
                    'decision': {'behavior': 'deny', 'message': '响应不完整'}
                }))
                return
            response_data += chunk

        total_elapsed = time.time() - start_time
        logger.debug(f"Received {len(response_data)} bytes (total elapsed: {total_elapsed:.1f}s)")
        logger.debug(f"Response: {response_data.decode('utf-8')[:200]}...")
        print(response_data.decode('utf-8'))

    except socket.timeout as e:
        elapsed = time.time() - start_time
        logger.error(f"Client timeout after {elapsed:.0f}s (limit: {CLIENT_TIMEOUT}s)")
        print(json.dumps({
            'success': False,
            'fallback_to_terminal': True,
            'error': 'client_timeout',
            'decision': {'behavior': 'deny', 'message': f'客户端超时（{elapsed:.0f}秒），请在终端操作'}
        }))
        sys.exit(1)
    except ConnectionRefusedError as e:
        logger.error(f"Connection refused: {e}")
        print(json.dumps({
            'success': False,
            'error': 'connection_refused',
            'decision': {'behavior': 'deny', 'message': '连接被拒绝'}
        }))
        sys.exit(1)
    except FileNotFoundError as e:
        logger.error(f"Socket not found: {e}")
        print(json.dumps({
            'success': False,
            'error': 'socket_not_found',
            'decision': {'behavior': 'deny', 'message': 'Socket 文件不存在'}
        }))
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Exception: {type(e).__name__}: {e}")
        print(json.dumps({
            'success': False,
            'error': str(e),
            'decision': {'behavior': 'deny', 'message': f'连接错误: {e}'}
        }))
        sys.exit(1)
    finally:
        if sock:
            logger.debug("Closing socket...")
            try:
                sock.close()
            except Exception:
                pass
        logger.debug("Exiting")


if __name__ == '__main__':
    main()
