# claude-notify

用于实现 Claude Code 的飞书通知机制，支持可交互权限控制。

## 项目概述

本项目为 Claude Code 提供飞书通知功能，允许用户远程响应权限请求，无需返回终端操作。项目包含两个主要组件：

1. **权限通知脚本** (`hooks/permission-notify.sh`) - Claude Code PermissionRequest hook，负责发送飞书卡片和处理用户决策
2. **回调服务** (`server/main.py`) - HTTP 服务接收飞书卡片按钮操作，通过 Unix Socket 传递给通知脚本

## 项目结构

```
claude-notify/
├── install.sh                  # 安装配置脚本
├── hooks/                      # Hook 脚本
│   ├── permission-notify.sh    # 权限请求通知脚本
│   └── webhook-notify.sh       # 通用通知脚本
├── server/                     # Python 回调服务
│   ├── main.py                 # 主服务入口
│   ├── start.sh                # 启动脚本
│   ├── config.py               # 配置管理
│   ├── socket-client.py        # Socket 客户端
│   ├── models/                 # 数据模型
│   ├── services/               # 业务服务
│   └── handlers/               # HTTP 处理器
├── shell-lib/                  # Shell 函数库
│   ├── log.sh                  # 日志记录函数
│   ├── json.sh                 # JSON 解析函数
│   ├── tool.sh                 # 工具详情格式化
│   ├── feishu.sh               # 飞书卡片构建
│   └── socket.sh               # Socket 通信函数
├── templates/                  # 飞书卡片模板
│   └── feishu/                 # 飞书卡片模板文件
│       ├── permission-card.json           # 权限请求卡片(带按钮)
│       ├── permission-card-static.json    # 权限请求卡片(无按钮)
│       ├── notification-card.json         # 通用通知卡片
│       ├── buttons.json                   # 交互按钮模板
│       ├── command-detail-bash.json       # Bash 命令详情模板
│       ├── command-detail-file.json       # 文件操作详情模板
│       └── description-element.json       # 描述元素模板
├── shared/                     # 跨语言共享资源
│   ├── protocol.md             # Socket 通信协议规范
│   ├── logging.json            # 统一日志配置
│   └── logging_config.py       # Python 日志配置模块
├── config/                     # 配置文件
│   └── tools.json              # 工具类型配置
├── docs/                       # 文档
│   ├── AGENTS.md               # AI 助手指南
│   └── TEST.md                 # 测试文档
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
source .env
./server/start.sh
```

### 4. 开始使用

启动 Claude Code，权限请求将自动发送到飞书。

## 架构设计

### 交互模式工作流程

```
┌─────────────────┐         ┌──────────────────┐         ┌─────────────────┐
│  Claude Code    │────────▶│ hooks/permission │────────▶│   飞书 Webhook   │
│                 │  Hook   │    -notify.sh    │  Card   │                 │
└─────────────────┘         └────────┬─────────┘         └─────────────────┘
                                     │
                                     │ Unix Socket
                                     │ (注册请求)
                                     ▼
                            ┌──────────────────┐
                            │     server/      │
                            │   HTTP Server    │
                            └────────┬─────────┘
                                     │
                                     │ HTTP Callback
                                     │ (用户点击按钮)
                                     ▼
                            ┌──────────────────┐         ┌─────────────────┐
                            │     server/      │────────▶│ hooks/permission│
                            │   (resolve)      │  Socket │    -notify.sh   │
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

1. **飞书卡片由前端发送**: `permission-notify.sh` 负责构造和发送飞书卡片，回调服务只处理用户决策
2. **Unix Socket 双向通信**: 请求注册和决策返回通过同一个 Socket 连接
3. **长度前缀协议**: 使用 4 字节长度前缀确保数据完整性（详见 `shared/protocol.md`）
4. **连接状态驱动**: 请求有效性由 Socket 连接状态决定，支持死连接检测和超时处理
5. **优雅降级**: 回调服务不可用时自动降级为仅通知模式

## 功能特性

- **可交互权限控制**: 用户可直接在飞书消息中点击按钮批准/拒绝权限请求
- **权限持久化**: 支持"始终允许"选项，自动写入项目权限规则
- **优雅降级**: 回调服务不可用时自动降级为仅通知模式
- **统一配置**: Shell 和 Python 共用 `shared/logging.json` 日志配置

## 待实现功能

- **权限请求延迟通知**: 支持配置延迟时间，在权限请求发出后等待一段时间再发送飞书通知，避免终端快速响应时产生不必要的通知
- **决策页面增强**:
  - 显示具体批准/拒绝的指令内容
  - ✅ 支持定时自动关闭页面（已实现）
- **目录结构重构**: 重组一级目录，将代码文件统一收拢到 `src/` 目录，改善项目结构清晰度

## 已完成功能

- ✅ **飞书卡片模板化**: 支持模块化的飞书卡片模板，便于自定义和扩展
- ✅ **决策页面自动关闭**: 支持定时自动关闭决策页面（通过 `CLOSE_PAGE_TIMEOUT` 配置）

## 脚本说明

| 脚本 | 用途 | Hook 类型 |
|------|------|-----------|
| `hooks/webhook-notify.sh` | 通用通知（任务暂停等） | Notification, Stop |
| `hooks/permission-notify.sh` | 权限请求通知（可交互） | PermissionRequest |
| `server/main.py` | 权限回调服务（HTTP + Socket） | - |
| `server/socket-client.py` | Socket 客户端（替代 socat） | - |

## 配置方法

### 手动配置（不使用 install.sh）

#### 1. 设置 Webhook URL

```bash
export FEISHU_WEBHOOK_URL="https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxx"
```

#### 2. 启动回调服务

```bash
./server/start.sh
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
            "command": "/path/to/claude-notify/hooks/permission-notify.sh"
          }
        ]
      }
    ]
  }
}
```

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `FEISHU_WEBHOOK_URL` | 飞书 Webhook URL | 必需 |
| `CALLBACK_SERVER_URL` | 回调服务外部访问地址 | `http://localhost:8080` |
| `CALLBACK_SERVER_PORT` | HTTP 服务端口 | 8080 |
| `PERMISSION_SOCKET_PATH` | Unix Socket 路径 | `/tmp/claude-permission.sock` |
| `REQUEST_TIMEOUT` | 服务器端超时秒数 | 300（0 禁用） |
| `CLOSE_PAGE_TIMEOUT` | 回调页面自动关闭秒数 | 3（建议范围 1-10） |

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

- [Socket 通信协议](shared/protocol.md)
- [测试文档](docs/TEST.md)
