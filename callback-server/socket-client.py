#!/usr/bin/env python3
"""
Socket 客户端 - 替代 socat 实现可靠的双向通信

用法: echo '{"json": "data"}' | python3 socket-client.py [socket_path]

功能：
    从 stdin 读取请求数据，通过 Unix Socket 发送到回调服务器，
    无限等待服务器响应，超时由服务器端控制

通信协议：
    - 发送：原始 JSON 字符串（UTF-8 编码）
    - 接收：4 字节长度前缀 + JSON 数据（大端序）

优势：
    - 避免 socat 的 half-close 问题
    - 支持长度前缀协议，确保数据完整性
    - 客户端无限等待，由服务器端控制超时
"""

import sys
import os
import socket
import json
import logging
import time

# 配置日志
debug_log = os.environ.get('SOCKET_CLIENT_DEBUG', '/tmp/socket-client-debug.log')
logging.basicConfig(
    filename=debug_log,
    level=logging.DEBUG,
    format=f'[%(process)d] %(asctime)s.%(msecs)03d %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def main():
    """Socket 客户端主流程

    执行步骤：
        1. 从 stdin 读取请求数据
        2. 连接到 Unix Socket
        3. 发送请求数据
        4. 等待服务器响应（无限等待，无超时）
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
        logger.debug(f"Connected, fileno={sock.fileno()}")

        # 发送请求（不关闭写端，保持连接双向可用）
        sock.sendall(request_data.encode('utf-8'))
        logger.debug(f"Request sent ({len(request_data)} bytes), waiting for response (no timeout)...")

        # 等待并读取响应（带长度前缀协议，无限等待）
        wait_start = time.time()
        logger.debug("Waiting for response...")

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
