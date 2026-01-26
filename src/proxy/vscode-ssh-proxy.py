#!/usr/bin/env python3
"""
VSCode SSH 代理服务

在本地电脑运行，自动启动 HTTP 服务并建立反向 SSH 隧道，
VPS 可以发送请求来唤起本地 VSCode 窗口打开远程项目。

使用方法:
    python3 vscode-ssh-proxy.py --vps myserver

生成的 URI 格式:
    vscode-remote://ssh-remote+myserver/path/to/project
"""

import argparse
import atexit
import http.server
import json
import os
import platform
import signal
import socketserver
import subprocess
import sys
import threading
import time
import urllib.parse
from datetime import datetime


# 全局配置
CONFIG = {
    "ssh_host": None,
    "ssh_port": None,  # None 表示使用默认端口或 ~/.ssh/config 中的配置
    "local_port": 9527,
    "remote_port": 9527,
}

# SSH 进程
ssh_process = None


class VSCodeProxyHandler(http.server.BaseHTTPRequestHandler):
    """处理 VSCode 打开请求的 HTTP Handler"""

    def log_message(self, format, *args):
        """自定义日志格式"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {args[0]}")

    def send_json_response(self, status_code: int, data: dict):
        """发送 JSON 响应"""
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def build_remote_uri(self, path: str) -> str:
        """构建 VSCode Remote SSH URI"""
        if not path.startswith("/"):
            path = "/" + path
        encoded_path = urllib.parse.quote(path, safe="/")
        return f"vscode-remote://ssh-remote+{CONFIG['ssh_host']}{encoded_path}"

    def do_GET(self):
        """处理 GET 请求"""
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)

        if parsed.path == "/":
            self.send_json_response(200, {
                "status": "ok",
                "service": "vscode-ssh-proxy",
                "ssh_host": CONFIG["ssh_host"],
                "platform": platform.system(),
                "endpoints": {
                    "/": "健康检查",
                    "/open?path=<path>": "打开 VSCode Remote 项目"
                }
            })

        elif parsed.path == "/open":
            path = query.get("path", [None])[0]
            if not path:
                self.send_json_response(400, {"success": False, "error": "缺少 path 参数"})
                return
            result = self.open_vscode(path)
            self.send_json_response(200 if result["success"] else 500, result)

        else:
            self.send_json_response(404, {"success": False, "error": f"未知路径: {parsed.path}"})

    def do_POST(self):
        """处理 POST 请求"""
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == "/open":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")

            try:
                data = json.loads(body) if body else {}
                path = data.get("path")
            except json.JSONDecodeError:
                self.send_json_response(400, {"success": False, "error": "无效的 JSON 格式"})
                return

            if not path:
                self.send_json_response(400, {"success": False, "error": "缺少 path 参数"})
                return

            result = self.open_vscode(path)
            self.send_json_response(200 if result["success"] else 500, result)
        else:
            self.send_json_response(404, {"success": False, "error": f"未知路径: {parsed.path}"})

    def open_vscode(self, path: str) -> dict:
        """打开 VSCode Remote 项目"""
        print(f"  → 打开项目: {path}")

        folder_uri = self.build_remote_uri(path)
        print(f"  → URI: {folder_uri}")

        try:
            cmd = ["code", "--folder-uri", folder_uri]

            if platform.system() == "Windows":
                result = subprocess.run(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    timeout=10, shell=True
                )
            else:
                result = subprocess.run(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    timeout=10
                )

            if result.returncode == 0:
                print("  ✓ 成功")
                return {"success": True, "path": path, "uri": folder_uri}
            else:
                error = result.stderr.decode().strip() if result.stderr else "未知错误"
                print("  ✗ 失败: {}".format(error))
                return {"success": False, "path": path, "uri": folder_uri, "error": error}

        except FileNotFoundError:
            error = "'code' 命令未找到"
            print(f"  ✗ {error}")
            return {"success": False, "error": error}
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "命令超时"}
        except Exception as e:
            return {"success": False, "error": str(e)}


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    """支持多线程的 HTTP Server"""
    allow_reuse_address = True
    daemon_threads = True


def start_ssh_tunnel():
    """启动 SSH 反向隧道"""
    global ssh_process

    cmd = [
        "ssh",
        "-o", "ServerAliveInterval=60",
        "-o", "ServerAliveCountMax=3",
        "-o", "ExitOnForwardFailure=yes",
        "-N",
        "-R", f"{CONFIG['remote_port']}:localhost:{CONFIG['local_port']}",
    ]

    # 如果指定了 SSH 端口，添加 -p 参数
    if CONFIG["ssh_port"]:
        cmd.extend(["-p", str(CONFIG["ssh_port"])])

    cmd.append(CONFIG["ssh_host"])

    port_info = f":{CONFIG['ssh_port']}" if CONFIG["ssh_port"] else ""
    print(f"[SSH] 连接到 {CONFIG['ssh_host']}{port_info}...")
    print(f"[SSH] 隧道: VPS:{CONFIG['remote_port']} -> localhost:{CONFIG['local_port']}")
    print(f"[SSH] 命令: {' '.join(cmd)}")

    try:
        ssh_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # 等待一下检查是否启动成功
        time.sleep(2)

        if ssh_process.poll() is not None:
            stderr = ssh_process.stderr.read().decode() if ssh_process.stderr else ""
            print(f"[SSH] ✗ 连接失败: {stderr}")
            return False

        print(f"[SSH] ✓ 隧道已建立 (PID: {ssh_process.pid})")
        return True

    except FileNotFoundError:
        print("[SSH] ✗ 未找到 ssh 命令")
        return False
    except Exception as e:
        print(f"[SSH] ✗ 启动失败: {e}")
        return False


def cleanup():
    """清理资源"""
    global ssh_process
    if ssh_process and ssh_process.poll() is None:
        print("\n[SSH] 关闭隧道...")
        ssh_process.terminate()
        try:
            ssh_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            ssh_process.kill()
        print("[SSH] 隧道已关闭")


def signal_handler(signum, frame):
    """信号处理"""
    cleanup()
    sys.exit(0)


def check_code_command():
    """检查 code 命令是否可用"""
    try:
        result = subprocess.run(
            ["code", "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(
        description="VSCode SSH 代理 - 通过反向隧道打开远程项目",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s --vps myserver                           # 使用 ~/.ssh/config 中的别名
  %(prog)s --vps root@192.168.1.100                 # 使用标准 SSH 格式
  %(prog)s --vps root@192.168.1.100 --ssh-port 2222 # 指定 SSH 端口
  %(prog)s --vps myserver --port 9527 --remote-port 9527

VPS 端测试:
  curl --noproxy localhost "http://localhost:9527/open?path=/root/projects/myapp"

生成的 URI:
  vscode-remote://ssh-remote+myserver/root/projects/myapp
        """
    )

    parser.add_argument(
        "--vps",
        required=True,
        metavar="HOST",
        help="VPS 的 SSH 地址，可以是 ~/.ssh/config 中的别名(如 myserver)，或标准格式(如 root@192.168.1.100)"
    )
    parser.add_argument(
        "--ssh-port",
        type=int,
        default=None,
        metavar="PORT",
        help="SSH 端口 (默认: 22，使用别名时从 ~/.ssh/config 读取)"
    )
    parser.add_argument(
        "-p", "--port",
        type=int,
        default=9527,
        help="本地 HTTP 服务端口 (默认: 9527)"
    )
    parser.add_argument(
        "-r", "--remote-port",
        type=int,
        default=None,
        help="VPS 端远程端口 (默认: 同本地端口)"
    )

    args = parser.parse_args()

    # 设置配置
    CONFIG["ssh_host"] = args.vps
    CONFIG["ssh_port"] = args.ssh_port
    CONFIG["local_port"] = args.port
    CONFIG["remote_port"] = args.remote_port or args.port

    # 注册清理函数
    atexit.register(cleanup)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 打印启动信息
    print()
    print("=" * 60)
    print("  VSCode SSH 代理服务")
    print("=" * 60)
    print()
    print(f"  VPS Host:    {CONFIG['ssh_host']}")
    print(f"  SSH 端口:    {CONFIG['ssh_port'] or '默认 22 (别名时从 ~/.ssh/config 读取)'}")
    print(f"  本地端口:    {CONFIG['local_port']}")
    print(f"  远程端口:    {CONFIG['remote_port']}")
    print(f"  操作系统:    {platform.system()} {platform.release()}")
    print()

    # 检查 code 命令
    if not check_code_command():
        print("⚠ 警告: 'code' 命令未找到，请确保 VSCode 已安装并添加到 PATH")
        print()

    # 启动 SSH 隧道
    if not start_ssh_tunnel():
        print("\n启动失败，请检查 SSH 配置")
        sys.exit(1)

    print()
    print("=" * 60)
    print("  服务已就绪")
    print("=" * 60)
    print()
    print("VPS 端测试命令:")
    print(f"  curl --noproxy localhost \"http://localhost:{CONFIG['remote_port']}/open?path=/path/to/project\"")
    print()
    print("URI 格式:")
    print(f"  vscode-remote://ssh-remote+{CONFIG['ssh_host']}/<path>")
    print()
    print("按 Ctrl+C 退出")
    print("=" * 60)
    print()

    # 启动 HTTP 服务
    try:
        with ThreadedHTTPServer(("127.0.0.1", CONFIG["local_port"]), VSCodeProxyHandler) as httpd:
            print(f"[HTTP] 服务已启动: http://127.0.0.1:{CONFIG['local_port']}")
            print()
            httpd.serve_forever()
    except OSError as e:
        print(f"[HTTP] 启动失败: {e}")
        cleanup()
        sys.exit(1)


if __name__ == "__main__":
    main()
