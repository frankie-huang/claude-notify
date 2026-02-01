"""Claude 会话相关处理器

处理用户通过飞书回复消息继续 Claude 会话的请求。
"""

import json
import logging
import os
import subprocess
import threading
from typing import Tuple, Dict, Any

logger = logging.getLogger(__name__)

# 常量定义
TIMEOUT_SECONDS = 600  # 后台等待超时时间（秒）
STARTUP_CHECK_SECONDS = 2  # 启动检查等待时间（秒）
MAX_LOG_LENGTH = 500  # 日志最大长度
MAX_NOTIFICATION_LENGTH = 500  # 通知消息最大长度


class Response:
    """统一的响应格式"""

    @staticmethod
    def error(msg: str) -> Tuple[bool, Dict[str, Any]]:
        """错误响应"""
        return False, {'error': msg}

    @staticmethod
    def processing() -> Tuple[bool, Dict[str, Any]]:
        """处理中响应"""
        return True, {'status': 'processing'}

    @staticmethod
    def completed(output: str = '') -> Tuple[bool, Dict[str, Any]]:
        """完成响应"""
        return True, {'status': 'completed', 'output': output}


def handle_continue_session(data: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    """
    处理继续 Claude 会话的请求

    同步等待一小段时间判断命令是否能正常启动，然后返回结果。

    Args:
        data: 请求数据
            - session_id: Claude 会话 ID (必需)
            - project_dir: 项目工作目录 (必需)
            - prompt: 用户的问题 (必需)
            - chat_id: 群聊 ID (可选)
            - reply_message_id: 回复消息 ID (可选)

    Returns:
        (success, response):
            - success=True, status='processing': 命令正在执行
            - success=True, status='completed': 命令快速完成
            - success=False, error=...: 命令启动/执行失败
    """
    session_id = data.get('session_id', '')
    project_dir = data.get('project_dir', '')
    prompt = data.get('prompt', '')
    chat_id = data.get('chat_id', '') or ''  # 确保 None 转为空字符串

    # 参数验证
    if not session_id:
        return Response.error('Session not registered or has expired')
    if not project_dir:
        return Response.error('Missing project_dir')
    if not prompt:
        return Response.error('Missing prompt')

    # 验证项目目录存在
    if not os.path.exists(project_dir):
        return Response.error(f'Project directory not found: {project_dir}')

    logger.info(f"[claude-continue] Session: {session_id}, Dir: {project_dir}, Prompt: {prompt[:50]}...")

    # 同步执行并检查
    return _execute_and_check(session_id, project_dir, prompt, chat_id)


def _execute_and_check(session_id: str, project_dir: str, prompt: str, chat_id: str = '') -> Tuple[bool, Dict[str, Any]]:
    """
    执行命令并检查启动状态

    Args:
        session_id: Claude 会话 ID
        project_dir: 项目工作目录
        prompt: 用户的问题
        chat_id: 群聊 ID（用于异常通知）

    Returns:
        (success, response)
    """
    cmd = ['claude', '-p', prompt, '--resume', session_id]
    logger.info(f"[claude-continue] Executing: cd {project_dir} && claude -p '<prompt>' --resume {session_id}")

    # 启动进程
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=project_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
    except Exception as e:
        # 启动失败（命令不存在等）
        error_msg = str(e)
        logger.error(f"[claude-continue] Failed to start process: {error_msg}")
        return Response.error(error_msg)

    # 等待一小段时间检查进程状态
    try:
        returncode = proc.wait(timeout=STARTUP_CHECK_SECONDS)
        # 进程已退出
        stdout, stderr = proc.communicate()
        if returncode == 0:
            logger.info(f"[claude-continue] Command completed quickly")
            return Response.completed(stdout[:MAX_LOG_LENGTH * 2] if stdout else '')
        else:
            error_msg = stderr.strip() if stderr.strip() else stdout.strip()
            if not error_msg:
                error_msg = f"命令执行失败，退出码: {returncode}"
            logger.warning(f"[claude-continue] Command failed with exit code {returncode}: {error_msg}")
            return Response.error(error_msg)
    except subprocess.TimeoutExpired:
        # 进程仍在运行，正常启动
        logger.info(f"[claude-continue] Command is running in background")
        # 在后台等待完成
        _run_in_background(_wait_for_completion, (proc, session_id, chat_id))
        return Response.processing()


def _run_in_background(func, args=()):
    """在后台线程中执行函数

    Args:
        func: 要执行的函数
        args: 位置参数元组
    """
    thread = threading.Thread(target=func, args=args, daemon=True)
    thread.start()


def _wait_for_completion(proc: subprocess.Popen, session_id: str, chat_id: str = ''):
    """
    在后台等待进程完成

    Args:
        proc: 子进程对象
        session_id: 会话 ID
        chat_id: 群聊 ID（用于异常通知）
    """
    try:
        stdout, stderr = proc.communicate(timeout=TIMEOUT_SECONDS)
        if proc.returncode == 0:
            logger.info(f"[claude-continue] Command completed successfully, session: {session_id}")
            if stdout:
                logger.debug(f"[claude-continue] stdout: {stdout[:MAX_LOG_LENGTH]}...")
        else:
            # 异常退出，记录日志
            error_summary = stderr.strip()[:MAX_LOG_LENGTH] if stderr.strip() else '(无错误输出)'
            logger.warning(f"[claude-continue] Command failed with exit code {proc.returncode}, session: {session_id}, error: {error_summary}")

            # 如果有 chat_id 且有 stderr，才发送飞书通知
            if chat_id and stderr:
                _send_error_notification(chat_id, stderr.strip()[:MAX_LOG_LENGTH])
    except subprocess.TimeoutExpired:
        logger.error(f"[claude-continue] Command timed out after {TIMEOUT_SECONDS // 60} minutes, session: {session_id}")
        proc.kill()
        # 超时也算异常，发送通知
        if chat_id:
            _send_error_notification(chat_id, f"执行超时（超过 {TIMEOUT_SECONDS // 60} 分钟）")
    except Exception as e:
        logger.error(f"[claude-continue] Execution error: {e}, session: {session_id}")
        if chat_id:
            _send_error_notification(chat_id, str(e)[:MAX_NOTIFICATION_LENGTH])


def _send_error_notification(chat_id: str, error_msg: str):
    """发送错误通知到飞书

    Note: 延迟导入 FeishuAPIService 以避免循环依赖

    Args:
        chat_id: 群聊 ID
        error_msg: 错误消息
    """
    try:
        from services.feishu_api import FeishuAPIService

        service = FeishuAPIService.get_instance()
        if service and service.enabled:
            success, result = service.send_text(
                f"❌ Claude 执行异常:\n{error_msg}",
                receive_id=chat_id,
                receive_id_type='chat_id'
            )
            if success:
                logger.info(f"[claude-continue] Sent error notification to {chat_id}")
            else:
                logger.error(f"[claude-continue] Failed to send error notification: {result}")
        else:
            logger.warning("[claude-continue] FeishuAPIService not available for error notification")
    except Exception as e:
        logger.error(f"[claude-continue] Failed to send error notification: {e}")
