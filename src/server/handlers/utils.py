import json
import threading
import urllib.request


def post_json(url, data, auth_token=None, timeout=10):
    """发送 JSON POST 请求（无代理）

    Args:
        url: 请求 URL
        data: 请求数据（dict，会被 JSON 序列化）
        auth_token: 可选的认证令牌（X-Auth-Token header）
        timeout: 超时时间（秒）

    Returns:
        解析后的 JSON 响应（dict）

    Raises:
        urllib.error.HTTPError, urllib.error.URLError, socket.timeout, Exception
    """
    headers = {'Content-Type': 'application/json'}
    if auth_token:
        headers['X-Auth-Token'] = auth_token

    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode('utf-8'),
        headers=headers,
        method='POST'
    )

    no_proxy_handler = urllib.request.ProxyHandler({})
    opener = urllib.request.build_opener(no_proxy_handler)
    with opener.open(req, timeout=timeout) as response:
        return json.loads(response.read().decode('utf-8'))


def run_in_background(func, args=()):
    """在后台线程中执行函数

    Args:
        func: 要执行的函数
        args: 位置参数元组
    """
    thread = threading.Thread(target=func, args=args, daemon=True)
    thread.start()
