# Design: 项目结构重组技术设计

## 1. Socket 协议抽象设计

### 当前状态

协议细节分散在三个文件中：

```
lib/socket.sh:165-218      # parse_socket_response() - 解析响应
socket-client.py:110-150   # 长度前缀读取逻辑
server.py:115-120          # 长度前缀发送逻辑
request_manager.py:115-118 # 长度前缀发送逻辑
```

### 设计方案

创建 `shared/protocol.md` 作为权威协议规范：

```markdown
# Claude Permission Socket Protocol v1

## 概述
基于 Unix Domain Socket 的请求-响应协议，用于 Hook 脚本与回调服务器通信。

## 连接参数
- Socket 类型: SOCK_STREAM
- 默认路径: /tmp/claude-permission.sock
- 环境变量: PERMISSION_SOCKET_PATH

## 消息序列

```
Client                              Server
  |                                    |
  |------ Request JSON --------------->|
  |                                    |
  |<----- Ack JSON (无长度前缀) -------|
  |                                    |
  |      [等待用户通过 HTTP 响应]       |
  |                                    |
  |<----- Decision (4B长度+JSON) ------|
  |                                    |
```

## 消息格式

### 1. 请求消息 (Client → Server)
- 格式: 原始 JSON, UTF-8
- 无长度前缀
- 字段:
  - request_id: string (必需)
  - project_dir: string (必需)
  - raw_input_encoded: string (Base64 编码的原始输入)

### 2. 确认消息 (Server → Client)
- 格式: 原始 JSON, UTF-8
- 无长度前缀
- 示例: {"success": true, "message": "Request registered"}

### 3. 决策消息 (Server → Client)
- 格式: 4字节大端序长度 + JSON 数据
- 长度字段: uint32, big-endian
- JSON 字段:
  - success: boolean
  - decision: {behavior, message, interrupt}
  - fallback_to_terminal: boolean (可选)
```

### 代码引用

各实现文件在注释中引用协议文档：

```python
# socket-client.py
"""
通信协议详见: shared/protocol.md
"""
```

```bash
# lib/socket.sh
# 通信协议详见: shared/protocol.md
```

## 2. 日志配置统一设计

### 当前状态

日志配置在三处重复：

| 文件 | 配置内容 |
|------|----------|
| lib/log.sh:20-30 | LOG_DIR, 日期格式, 文件名模式 |
| server.py:40-52 | log_dir, log_file, format |
| socket-client.py:30-46 | 同上，略有差异 |

### 设计方案

创建 `shared/logging.json`：

```json
{
  "version": 1,
  "log_dir_relative": "log",
  "file_patterns": {
    "hook": "hook_{date}.log",
    "server": "callback_{date}.log",
    "socket_client": "socket_client_{date}.log"
  },
  "date_format": "%Y%m%d",
  "formats": {
    "shell": "[{pid}] {datetime} [{level}] {message}",
    "python": "[%(process)d] %(asctime)s.%(msecs)03d [%(levelname)s] %(message)s"
  },
  "datetime_format": "%Y-%m-%d %H:%M:%S"
}
```

### Shell 读取方式

```bash
# lib/log.sh
_load_log_config() {
    local config_file="${SCRIPT_DIR}/../shared/logging.json"
    if [ -f "$config_file" ] && command -v jq &> /dev/null; then
        LOG_DIR=$(jq -r '.log_dir_relative' "$config_file")
        LOG_DATE_FMT=$(jq -r '.date_format' "$config_file")
    else
        # 降级到内置默认值
        LOG_DIR="log"
        LOG_DATE_FMT="%Y%m%d"
    fi
}
```

### Python 读取方式

```python
# shared/logging_config.py
import json
from pathlib import Path

def get_logging_config():
    config_file = Path(__file__).parent / "logging.json"
    if config_file.exists():
        return json.loads(config_file.read_text())
    return DEFAULT_CONFIG  # 内置降级配置
```

## 3. 目录结构迁移设计

### 迁移脚本

创建 `scripts/migrate-v2.sh`（临时，迁移后删除）：

```bash
#!/bin/bash
# 项目结构迁移脚本

# 1. 创建新目录
mkdir -p hooks server shared docs

# 2. 移动文件
mv permission-notify.sh hooks/
mv webhook-notify.sh hooks/
mv callback-server/* server/
mv server/server.py server/main.py
mv server/start-server.sh server/start.sh
mv AGENTS.md docs/
mv TEST.md docs/

# 3. 更新内部引用
sed -i 's|callback-server/socket-client.py|server/socket-client.py|g' lib/socket.sh

# 4. 删除空目录
rmdir callback-server

echo "Migration complete. Please update your hook configuration."
```

### 路径引用更新

需要更新的文件内引用：

| 文件 | 需更新的引用 |
|------|-------------|
| lib/socket.sh:53 | `callback-server/socket-client.py` → `server/socket-client.py` |
| hooks/permission-notify.sh | `SCRIPT_DIR` 计算需调整 |
| server/main.py | 日志目录路径 |
| server/socket-client.py | 日志目录路径 |

### 向后兼容

在根目录创建符号链接（可选，帮助过渡）：

```bash
ln -s hooks/permission-notify.sh permission-notify.sh
```

## 4. install.sh 安装脚本设计

### 功能

```bash
#!/bin/bash
# install.sh - Claude Code 权限通知安装脚本

# 功能：
# 1. 检测环境依赖（python3, curl, jq 等）
# 2. 配置 Claude Code hook
# 3. 生成环境变量配置模板

# 使用方式：
# ./install.sh              # 交互式安装
# ./install.sh --check      # 仅检测环境
# ./install.sh --uninstall  # 卸载
```

### 主要逻辑

```bash
# 1. 检测依赖
check_dependencies() {
    local missing=()
    command -v python3 &>/dev/null || missing+=("python3")
    command -v curl &>/dev/null || missing+=("curl")
    # ...
    if [ ${#missing[@]} -gt 0 ]; then
        echo "Missing: ${missing[*]}"
        return 1
    fi
}

# 2. 配置 hook（写入 ~/.claude/settings.json）
configure_hook() {
    local hook_path="$(pwd)/hooks/permission-notify.sh"
    # 使用 jq 或 python 更新 settings.json
}

# 3. 生成环境变量模板
generate_env_template() {
    cat > .env.example << 'EOF'
FEISHU_WEBHOOK_URL=https://open.feishu.cn/...
CALLBACK_SERVER_URL=http://localhost:8080
PERMISSION_SOCKET_PATH=/tmp/claude-permission.sock
EOF
}
```

## 5. lib/ → shell-lib/ 重命名

### 需要更新的引用

| 文件 | 行号 | 原引用 | 新引用 |
|------|------|--------|--------|
| hooks/permission-notify.sh | 22-26 | `${SCRIPT_DIR}/lib/...` | `${SCRIPT_DIR}/../shell-lib/...` |
| shell-lib/tool.sh | 29,32 | `${SCRIPT_DIR}/../lib/...` | `${SCRIPT_DIR}/...` (同目录) |
| shell-lib/socket.sh | 53 | `callback-server/socket-client.py` | `server/socket-client.py` |

### 路径计算变化

由于 Hook 脚本从根目录移到 `hooks/` 子目录，`SCRIPT_DIR` 的相对路径需要调整：

```bash
# 原来 (permission-notify.sh 在根目录)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/log.sh"

# 新 (permission-notify.sh 在 hooks/ 目录)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
source "${PROJECT_ROOT}/shell-lib/log.sh"
```

## 6. 不变更的部分

以下保持不变以减少风险：

1. **config/tools.json** - 已是统一配置源
2. **CLAUDE.md** - Claude Code 依赖根目录位置
3. **openspec/** - 独立的规范管理系统

## 7. 决策记录

| 决策 | 选择 | 理由 |
|------|------|------|
| 根目录脚本移动 | 移至 `hooks/` | 明确脚本用途，减少根目录混乱 |
| callback-server 重命名 | 改为 `server/` | 更简洁，反映实际功能 |
| lib/ 重命名 | 改为 `shell-lib/` | 明确表示 Shell 专用库 |
| 协议文档位置 | `shared/protocol.md` | 跨语言共享，Markdown 易读 |
| 日志配置格式 | JSON | Shell 和 Python 都能解析 |
| CLAUDE.md 位置 | 保留根目录 | Claude Code 约定 |
| 向后兼容 | 不做 | 代码库未用于生产，可直接重构 |
| 安装脚本 | 提供 install.sh | 简化用户配置流程 |
