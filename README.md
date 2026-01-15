# claude-notify

用于实现 Claude Code 的飞书通知机制，支持可交互权限控制。

## 项目概述

本项目为 Claude Code 提供飞书通知功能，允许用户远程响应权限请求，无需返回终端操作。项目包含两个主要组件：

1. **权限通知脚本** (`permission-notify.sh`) - Claude Code PermissionRequest hook，负责发送飞书卡片和处理用户决策
2. **回调服务** (`callback-server/server.py`) - HTTP 服务接收飞书卡片按钮操作，通过 Unix Socket 传递给通知脚本

## 架构设计

### 交互模式工作流程

```
┌─────────────────┐         ┌──────────────────┐         ┌─────────────────┐
│  Claude Code    │────────▶│ permission-notify│────────▶│   飞书 Webhook   │
│                 │  Hook   │      .sh         │  Card   │                 │
└─────────────────┘         └────────┬─────────┘         └─────────────────┘
                                     │
                                     │ Unix Socket
                                     │ (注册请求)
                                     ▼
                            ┌──────────────────┐
                            │ callback-server  │
                            │   HTTP Server    │
                            └────────┬─────────┘
                                     │
                                     │ HTTP Callback
                                     │ (用户点击按钮)
                                     ▼
                            ┌──────────────────┐         ┌─────────────────┐
                            │ callback-server  │────────▶│ permission-notify│
                            │   (resolve)      │  Socket │      .sh         │
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
3. **长度前缀协议**: 使用 4 字节长度前缀确保数据完整性
4. **连接状态驱动**: 请求有效性由 Socket 连接状态决定，支持死连接检测和超时处理
5. **优雅降级**: 回调服务不可用时自动降级为仅通知模式

## 功能特性

- **可交互权限控制**: 用户可直接在飞书消息中点击按钮批准/拒绝权限请求，无需返回终端操作
- **权限持久化**: 支持"始终允许"选项，自动写入项目权限规则
- **优雅降级**: 回调服务不可用时自动降级为仅通知模式
- **连接状态驱动**: 请求有效性由 Socket 连接状态决定，支持死连接检测
- **灵活超时**: 客户端无限等待，服务器端统一控制超时（可禁用）

## 脚本说明

| 脚本 | 用途 | Hook 类型 |
|------|------|-----------|
| `webhook-notify.sh` | 通用通知（任务暂停等） | Notification, Stop |
| `permission-notify.sh` | 权限请求通知（可交互） | PermissionRequest |
| `callback-server/server.py` | 权限回调服务（HTTP + Socket） | - |
| `callback-server/socket-client.py` | Socket 客户端（替代 socat） | - |

## 配置方法

### 1. 设置 Webhook URL

通过环境变量设置：

```bash
export FEISHU_WEBHOOK_URL="https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxx"
```

### 2. 启动回调服务（用于可交互权限控制）

#### 启动服务

启动权限回调服务：

```bash
cd callback-server
./start-server.sh start
```

或者直接运行（不带参数，默认启动）：

```bash
cd callback-server
./start-server.sh
```

#### 停止服务

```bash
cd callback-server
./start-server.sh stop
```

#### 重启服务

```bash
cd callback-server
./start-server.sh restart
```

#### 查看服务状态

```bash
# 检查 HTTP 端口是否监听
lsof -i :8080 | grep LISTEN

# 检查 Socket 文件是否存在
ls -l /tmp/claude-permission.sock

# 查看服务日志
tail -f log/callback_$(date +%Y%m%d).log
```

#### 手动强制停止（如果脚本停止失败）

```bash
# 查找并停止占用 8080 端口的进程
lsof -i :8080 | grep LISTEN | awk '{print $2}' | xargs -r kill

# 清理 Socket 文件
rm -f /tmp/claude-permission.sock
```

#### 环境变量配置

- `FEISHU_WEBHOOK_URL` - 飞书 Webhook URL（必需）
- `CALLBACK_SERVER_URL` - 回调服务外部访问地址（默认: `http://localhost:8080`）
- `CALLBACK_SERVER_PORT` - HTTP 服务端口（默认: 8080）
- `PERMISSION_SOCKET_PATH` - Unix Socket 路径（默认: `/tmp/claude-permission.sock`）
- `REQUEST_TIMEOUT` - 服务器端超时秒数（默认: 300，设为 0 禁用超时）

**超时说明**：客户端无限等待用户响应，超时由服务器端统一控制。服务器在超时后会主动关闭 socket 连接，客户端收到后返回 deny 决策。

**注意**: 如果需要在远程服务器上使用，请将 `CALLBACK_SERVER_URL` 设置为公网可访问的地址。

### 3. 配置 Claude Code Hooks

在 `~/.claude/settings.json` 或项目的 `.claude/settings.json` 中添加：

```json
{
  "hooks": {
    "PermissionRequest": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "bash /path/to/permission-notify.sh"
          }
        ]
      }
    ]
  }
}
```

#### Matcher 选项

- `"*"` - 所有权限请求
- `"Bash"` - 仅 Bash 命令
- `"Edit|Write"` - 仅文件修改
- `"Bash|Edit|Write"` - 命令和文件修改

### 4. 依赖

**可交互模式推荐**:
- `python3` - 回调服务 + Socket 客户端（推荐，更稳定）
- `socat` - Unix Socket 通信（可选，作为备选方案）
- `curl` - 发送 HTTP 请求

**降级模式（无回调服务）仅需**:
- `curl` - 发送 HTTP 请求

**注意**: `jq` 不再是必需依赖，脚本会自动检测并使用 Python3 或原生命令（grep/sed）解析 JSON

安装依赖：

```bash
# Ubuntu/Debian
apt-get install python3 curl socat

# CentOS/RHEL
yum install python3 curl socat

# macOS
brew install python3 curl socat
```

## 使用流程

### 交互模式（推荐）

**前提条件**: 回调服务已启动（见上方配置方法）

**执行流程**:
1. Claude Code 发起权限请求
2. `permission-notify.sh` 接收 Hook，发送飞书交互卡片
3. 用户在飞书中收到带 4 个按钮的通知卡片：
   - **批准运行** - 允许这一次执行
   - **始终允许** - 允许并写入规则，后续自动允许
   - **拒绝运行** - 拒绝这一次，Claude 可继续尝试其他方式
   - **拒绝并中断** - 拒绝并停止 Claude 当前任务
4. 用户点击按钮，浏览器访问回调服务器
5. 回调服务器通过 Unix Socket 返回决策
6. `permission-notify.sh` 接收决策并返回给 Claude Code
7. Claude Code 根据决策继续或停止执行

### 降级模式

**触发条件**: 回调服务未运行（Socket 文件不存在）

**行为**:
- 发送不带交互按钮的飞书通知卡片
- 返回 `EXIT_FALLBACK`，让 Claude Code 回退到终端交互模式
- 用户需要在终端手动确认权限请求

## 通知效果

权限请求通知会显示：
- 工具类型（Bash/Edit/Write 等）
- 项目名称
- 请求时间
- 详细内容（命令、文件路径等）
- 交互按钮（交互模式下）

不同工具类型使用不同颜色区分：
- Bash 命令 - 橙色
- 文件修改 - 黄色
- 文件读取/搜索 - 蓝色
- 网络请求 - 紫色

## 权限规则格式

点击"始终允许"后，会在项目的 `.claude/settings.local.json` 中写入规则：

```json
{
  "permissions": {
    "allow": [
      "Bash(npm run build)",
      "Edit(/path/to/file.js)",
      "Glob(**/*.py)"
    ]
  }
}
```

## 调试和日志

### 日志文件位置

- **回调服务日志**: `log/callback_YYYYMMDD.log`
- **Socket 客户端日志**: `/tmp/socket-client-debug.log` (通过 `SOCKET_CLIENT_DEBUG` 环境变量配置)
- **权限请求日志**: `log/permission_YYYYMMDD.log`

### 日志级别

- 回调服务默认使用 `DEBUG` 级别，记录详细的 socket 操作和时序信息
- 日志格式包含毫秒级时间戳，便于精确定位问题

### 常见问题排查

**Socket 连接失败**:
1. 检查回调服务是否运行: `ls -l /tmp/claude-permission.sock`
2. 查看回调服务日志: `tail -f log/callback_$(date +%Y%m%d).log`
3. 查看客户端日志: `tail -f /tmp/socket-client-debug.log`

**权限请求无响应**:
- 检查超时设置（默认 55 秒）
- 查看服务端日志中的请求注册记录
- 确认飞书 Webhook 是否正常发送

**数据传递问题**:
- 检查进程退出码记录在日志中
- 确认使用管道方式传递数据（当前版本）
- 查看是否有特殊字符导致 JSON 解析失败

