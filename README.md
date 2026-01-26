# claude-notify

用于实现 Claude Code 的飞书通知机制，支持可交互权限控制。

## 项目概述

本项目为 Claude Code 提供飞书通知功能，允许用户远程响应权限请求，无需返回终端操作。项目包含以下主要组件：

1. **统一 Hook 路由** (`src/hook-router.sh`) - Claude Code Hook 统一入口，根据事件类型分发到对应处理脚本
2. **权限处理脚本** (`src/hooks/permission.sh`) - PermissionRequest 事件处理，发送飞书卡片和处理用户决策
3. **通用通知脚本** (`src/hooks/webhook.sh`) - Notification 事件处理，用于任务暂停等通用通知
4. **任务完成通知脚本** (`src/hooks/stop.sh`) - Stop 事件处理，从 transcript 提取响应内容并发送飞书通知
5. **回调服务** (`src/server/main.py`) - HTTP 服务接收飞书卡片按钮操作，通过 Unix Socket 传递决策
6. **飞书卡片模板系统** (`src/templates/feishu/`) - 模块化的卡片模板，支持自定义扩展

## 项目结构

```
claude-notify/
├── install.sh                  # 安装配置脚本
├── .env.example                # 环境变量模板
├── src/                        # 源代码目录
│   ├── hook-router.sh          # Hook 统一入口（配置到 Claude Code）
│   ├── start-server.sh         # 回调服务启动脚本
│   ├── hooks/                  # Hook 事件处理脚本
│   │   ├── permission.sh       # 权限请求处理（可交互）
│   │   ├── webhook.sh          # 通用通知处理（Notification 事件）
│   │   └── stop.sh             # 任务完成通知处理（Stop 事件）
│   ├── lib/                    # Shell 函数库
│   │   ├── core.sh             # 核心库（路径、环境、日志）
│   │   ├── json.sh             # JSON 解析（jq/python3/grep 降级）
│   │   ├── tool.sh             # 工具详情格式化
│   │   ├── feishu.sh           # 飞书卡片构建和发送
│   │   ├── socket.sh           # Socket 通信函数
│   │   └── vscode-proxy.sh     # VSCode 代理客户端
│   ├── server/                 # Python 回调服务
│   │   ├── main.py             # 主服务入口
│   │   ├── config.py           # 配置管理
│   │   ├── socket-client.py    # Socket 客户端
│   │   ├── models/             # 数据模型
│   │   ├── services/           # 业务服务
│   │   └── handlers/           # HTTP 处理器
│   ├── config/                 # 配置文件
│   │   └── tools.json          # 工具类型配置
│   ├── templates/              # 飞书卡片模板
│   │   └── feishu/             # 飞书卡片模板文件
│   ├── shared/                 # 跨语言共享资源
│   │   ├── protocol.md         # Socket 通信协议规范
│   │   └── logging.json        # 统一日志配置
│   └── proxy/                  # 本地代理服务
│       └── vscode-ssh-proxy.py # VSCode SSH 反向隧道代理
├── openspec/                   # OpenSpec 规范管理
├── docs/                       # 文档
├── test/                       # 测试脚本
└── log/                        # 日志目录
```

## 快速开始

### 1. 运行安装脚本

```bash
./install.sh
```

安装脚本会：
- 检测环境依赖（python3, curl 等）
- 配置 Claude Code hook
- 生成环境变量配置模板

### 2. 配置环境变量

复制并编辑环境变量文件：

```bash
cp .env.example .env
vim .env
```

必需配置：
- `FEISHU_WEBHOOK_URL` - 飞书 Webhook URL
- `CALLBACK_SERVER_URL` - 回调服务外部访问地址

### 3. 启动回调服务

```bash
./src/start-server.sh
```

> **注意**：脚本会自动从 `.env` 文件读取配置，无需手动 `source .env`。

### 4. 开始使用

启动 Claude Code，权限请求将自动发送到飞书。

## 架构设计

### 交互模式工作流程

```
┌─────────────────┐         ┌──────────────────┐         ┌─────────────────┐
│  Claude Code    │────────▶│ src/hook-router  │────────▶│   飞书 Webhook   │
│                 │  Hook   │  → permission.sh │  Card   │                 │
└─────────────────┘         └────────┬─────────┘         └─────────────────┘
                                     │
                                     │ Unix Socket
                                     │ (注册请求)
                                     ▼
                            ┌──────────────────┐
                            │   src/server/    │
                            │   HTTP Server    │
                            └────────┬─────────┘
                                     │
                                     │ HTTP Callback
                                     │ (用户点击按钮)
                                     ▼
                            ┌──────────────────┐         ┌─────────────────┐
                            │   src/server/    │────────▶│ src/hooks/      │
                            │   (resolve)      │  Socket │  permission.sh  │
                            └──────────────────┘         └────────┬─────────┘
                                                              │
                                                              │ Decision JSON
                                                              ▼
                                                         ┌─────────────────┐
                                                         │  Claude Code    │
                                                         │  (继续/拒绝)     │
                                                         └─────────────────┘
```

### 关键设计点

1. **统一 Hook 路由**: `src/hook-router.sh` 统一处理所有 Hook 事件，根据事件类型分发到对应脚本
2. **stdin 一次读取**: Hook 路由脚本读取 stdin 到 `$INPUT` 变量，子脚本共享此变量
3. **飞书卡片由前端发送**: `permission.sh` 负责构造和发送飞书卡片，回调服务只处理用户决策
4. **Unix Socket 双向通信**: 请求注册和决策返回通过同一个 Socket 连接
5. **长度前缀协议**: 使用 4 字节长度前缀确保数据完整性（详见 `src/shared/protocol.md`）
6. **连接状态驱动**: 请求有效性由 Socket 连接状态决定，支持死连接检测和超时处理
7. **优雅降级**: 回调服务不可用时自动降级为仅通知模式

## 功能特性

- **可交互权限控制**: 用户可直接在飞书消息中点击按钮批准/拒绝权限请求
- **四种操作模式**: 批准运行、始终允许、拒绝运行、拒绝并中断
- **权限持久化**: 支持"始终允许"选项，自动写入项目权限规则
- **优雅降级**: 回调服务不可用时自动降级为仅通知模式
- **模板化卡片**: 飞书卡片 2.0 格式，支持模块化模板和自定义扩展
- **统一配置**: Shell 和 Python 共用 `config/tools.json` 工具配置
- **连接状态驱动**: 请求有效性由 Socket 连接状态决定，支持长时间等待
- **多工具支持**: 支持 Bash、Edit、Write、Read、Glob、Grep、WebSearch、WebFetch 等 Claude Code 工具

## 待实现功能
- **决策页面增强**:
  - 显示具体批准/拒绝的指令内容
  - ✅ 支持定时自动关闭页面（已实现）
## 已完成功能

- ✅ **权限通知延迟发送**: 支持配置延迟时间，避免快速连续请求时的消息轰炸（通过 `PERMISSION_NOTIFY_DELAY` 配置）
- ✅ **飞书卡片模板化**: 支持模块化的飞书卡片模板，便于自定义和扩展
- ✅ **决策页面自动关闭**: 支持定时自动关闭决策页面（通过 `CLOSE_PAGE_TIMEOUT` 配置）
- ✅ **VSCode 自动跳转**: 点击飞书按钮后从浏览器页面自动跳转到 VSCode（通过 `VSCODE_URI_PREFIX` 配置）
- ✅ **任务完成通知**: Claude 处理完成后自动发送飞书通知，包含响应摘要和会话标识（通过 `src/hooks/stop.sh` 实现）

## 脚本说明

| 脚本 | 用途 | Hook 类型 |
|------|------|-----------|
| `src/hook-router.sh` | Hook 统一入口（配置到 Claude Code） | 所有 Hook 事件 |
| `src/hooks/permission.sh` | 权限请求处理（可交互） | PermissionRequest |
| `src/hooks/webhook.sh` | 通用通知（任务暂停等） | Notification |
| `src/hooks/stop.sh` | 任务完成通知（含响应摘要） | Stop |
| `src/server/main.py` | 权限回调服务（HTTP + Socket） | - |
| `src/server/socket-client.py` | Socket 客户端（替代 socat） | - |

## Shell 函数库说明

| 函数库 | 功能 |
|--------|------|
| `src/lib/core.sh` | 核心库：路径管理、环境配置、日志记录（合并了原 project.sh、env.sh、log.sh） |
| `src/lib/json.sh` | JSON 解析函数（支持 jq/python3/grep+sed 多级降级） |
| `src/lib/tool.sh` | 工具详情格式化 |
| `src/lib/feishu.sh` | 飞书卡片构建和发送 |
| `src/lib/socket.sh` | Socket 通信函数 |
| `src/lib/vscode-proxy.sh` | VSCode 本地代理客户端，通过反向 SSH 隧道唤起本地 VSCode |

## VSCode SSH 远程开发代理

通过反向 SSH 隧道，在远程服务器上触发请求后自动唤起本地电脑的 VSCode 窗口。适用于 VSCode 通过 SSH Remote 连接到远程服务器的开发模式。

### 使用方法

1. **在本地电脑启动代理服务**：

```bash
python3 src/proxy/vscode-ssh-proxy.py --vps myserver
```

参数说明：
- `--vps`: SSH 地址（别名如 `myserver`，或 `root@1.2.3.4`）
- `--ssh-port`: SSH 端口（默认 22，使用别名时从 `~/.ssh/config` 读取）
- `--port`: 本地 HTTP 服务端口（默认 9527）
- `--remote-port`: 远程服务器端端口（默认同本地端口）

2. **在远程服务器上配置环境变量**（`.env` 文件）：

```bash
# 启用 VSCode 自动激活
ACTIVATE_VSCODE_ON_CALLBACK=true

# SSH 隧道代理端口（需与启动时的端口一致）
VSCODE_SSH_PROXY_PORT=9527
```

3. **工作流程**：
   - 点击飞书卡片按钮后，远程服务器通过 SSH 隧道向本地代理发送请求
   - 本地代理调用 `code --folder-uri vscode-remote://ssh-remote+myserver/path/to/project`
   - 本地 VSCode 自动打开并激活对应远程项目

### 两种激活模式

| 模式 | 配置 | 行为 |
|------|------|------|
| **SSH 隧道代理激活** | `ACTIVATE_VSCODE_ON_CALLBACK=true` + `VSCODE_SSH_PROXY_PORT=9527` | 通过反向 SSH 隧道唤起本地 VSCode 窗口 |
| **本地命令激活** | `ACTIVATE_VSCODE_ON_CALLBACK=true` | 在当前机器执行 `code .` 激活窗口 |

## 配置方法

### 手动配置（不使用 install.sh）

#### 1. 设置 Webhook URL

```bash
export FEISHU_WEBHOOK_URL="https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxx"
```

#### 2. 启动回调服务

```bash
./src/start-server.sh
```

#### 3. 配置 Claude Code Hooks

在 `~/.claude/settings.json` 中添加：

```json
{
  "hooks": {
    "PermissionRequest": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "/path/to/claude-notify/src/hook-router.sh",
            "timeout": 360
          }
        ]
      }
    ],
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "/path/to/claude-notify/src/hook-router.sh"
          }
        ]
      }
    ]
  }
}
```

> **注意**：PermissionRequest hook 的 `timeout`（秒）建议配置为大于服务端 `REQUEST_TIMEOUT`（默认 300 秒）的值，确保服务端超时先触发，避免 hook 被 Claude Code 强制终止。上例配置为 360 秒。

### 环境变量

**配置优先级**：`.env` 文件 > 环境变量 > 默认值

脚本会自动从项目根目录的 `.env` 文件读取配置，无需手动 `source`。如果 `.env` 中未配置某项，则从系统环境变量读取；如果仍未配置，则使用默认值。

**基础配置**

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `FEISHU_WEBHOOK_URL` | 飞书 Webhook URL | 必需 |
| `CALLBACK_SERVER_URL` | 回调服务外部访问地址 | `http://localhost:8080` |
| `CALLBACK_SERVER_PORT` | HTTP 服务端口 | 8080 |
| `PERMISSION_SOCKET_PATH` | Unix Socket 路径 | `/tmp/claude-permission.sock` |
| `REQUEST_TIMEOUT` | 服务器端超时秒数 | 300（0 禁用） |
| `CLOSE_PAGE_TIMEOUT` | 回调页面自动关闭秒数 | 3（建议范围 1-10） |
| `PERMISSION_NOTIFY_DELAY` | 权限通知延迟发送秒数 | 60 |
| `FEISHU_AT_ALL` | 飞书权限通知是否 @所有人 | `false` |
| `STOP_MESSAGE_MAX_LENGTH` | Stop 事件消息最大长度（字符数） | 2000 |
| `FEISHU_TEMPLATE_PATH` | 自定义飞书卡片模板目录 | `src/templates/feishu` |

**VSCode 自动跳转/激活配置**（以下两种模式二选一）

| 模式 | 变量 | 说明 | 默认值 |
|------|------|------|--------|
| 浏览器跳转 | `VSCODE_URI_PREFIX` | 通过浏览器 vscode:// 协议跳转（受浏览器策略限制） | 空（不跳转） |
| 自动激活 | `ACTIVATE_VSCODE_ON_CALLBACK` | 服务端直接激活 VSCode 窗口（推荐） | `false` |
| 自动激活 | `VSCODE_SSH_PROXY_PORT` | SSH Remote 场景的代理端口（配合反向隧道） | 空（不启用） |

## 依赖

**可交互模式推荐**:
- `python3` - 回调服务 + Socket 客户端
- `curl` - 发送 HTTP 请求
- `socat` - 可选，Socket 通信备选方案

**降级模式仅需**:
- `curl` - 发送 HTTP 请求

**可选**:
- `jq` - 更好的 JSON 处理（脚本会自动降级使用 Python3 或 grep/sed）

安装：

```bash
# Ubuntu/Debian
apt-get install python3 curl

# macOS
brew install python3 curl
```

## 使用流程

### 交互模式（推荐）

1. Claude Code 发起权限请求
2. `permission-notify.sh` 发送飞书交互卡片（4 个按钮）：
   - **批准运行** - 允许这一次执行
   - **始终允许** - 允许并写入规则
   - **拒绝运行** - 拒绝，Claude 可继续尝试其他方式
   - **拒绝并中断** - 拒绝并停止当前任务
3. 用户点击按钮，决策返回给 Claude Code

### 降级模式

回调服务不可用时：
- 发送不带交互按钮的通知卡片
- 用户需在终端手动确认

## 日志

日志文件位于 `log/` 目录：

| 文件模式 | 说明 |
|----------|------|
| `hook_YYYYMMDD.log` | Hook 脚本日志 |
| `callback_YYYYMMDD.log` | 回调服务日志 |
| `socket_client_YYYYMMDD.log` | Socket 客户端日志 |

日志配置统一定义在 `shared/logging.json`。

## 文档

- [Claude Code Hooks 事件调研](docs/CLAUDE_CODE_HOOKS.md) - 所有 hooks 事件类型、触发时机和配置方式
- [Socket 通信协议](src/shared/protocol.md)
- [飞书卡片模板说明](src/templates/feishu/README.md)
- [测试文档](test/README.md) - 测试脚本使用说明
- [测试指令集](test/PROMPTS.md) - 权限请求测试指令
- [测试场景](test/SCENARIOS.md) - 详细测试场景文档
- [OpenSpec 规范](openspec/specs/)
