# Proposal: 重构项目结构，简化根目录并抽象共享协议

## Why

当前项目存在以下问题：
1. **根目录过于拥挤** - 11 个文件在根目录，入口不明确
2. **Socket 协议分散** - 协议格式在多处硬编码，维护困难
3. **日志配置重复** - Shell/Python 各自定义，缺乏统一

## What Changes

优化项目结构，实现三个目标：
1. **简化根目录** - 将实现文件移入子目录，根目录只保留入口和文档
2. **抽象 Socket 协议** - 统一客户端/服务端的通信协议定义
3. **统一日志配置** - 消除 Shell/Python 间的日志配置重复

## 背景分析

### 当前目录结构
```
claude-notify/
├── AGENTS.md, CLAUDE.md, README.md, CHANGELOG.md  # 文档
├── LICENSE, .gitignore
├── permission-notify.sh      # Hook 入口脚本 (314行)
├── webhook-notify.sh         # 辅助脚本
├── config/                   # 配置文件
│   └── tools.json
├── lib/                      # Shell 函数库 (6个文件)
│   ├── log.sh, json.sh, tool.sh, tool-config.sh
│   ├── feishu.sh, socket.sh
├── callback-server/          # Python 后端
│   ├── server.py, socket-client.py, config.py
│   ├── start-server.sh
│   ├── handlers/, models/, services/
│   └── templates/, log/
├── log/                      # 日志目录
└── openspec/                 # 规范文档
```

### 问题分析

1. **根目录过于拥挤**
   - 11 个文件在根目录（包括 2 个脚本、5 个文档、配置等）
   - 入口不明确：用户需要阅读 README 才知道该运行哪个脚本

2. **Socket 协议分散**
   - `lib/socket.sh` 定义了客户端发送逻辑和响应解析
   - `callback-server/socket-client.py` 实现 Python 客户端
   - `callback-server/server.py` 实现服务端处理
   - 协议格式（4字节长度前缀 + JSON）在多处硬编码

3. **日志配置重复**
   - `lib/log.sh` 定义 Shell 日志配置
   - `callback-server/server.py` 定义 Python 日志配置
   - `callback-server/socket-client.py` 又定义了一遍
   - 日志目录、格式、日期切分逻辑重复

4. **工具配置已统一，但仍有冗余**
   - `config/tools.json` 是统一配置源
   - `lib/tool.sh` 和 `models/tool_config.py` 各自实现了降级配置
   - 内置降级配置是必要的，但可以简化

## 变更内容

### 1. 目录结构重组

```
claude-notify/
├── README.md                 # 主文档（保留）
├── CHANGELOG.md              # 变更日志（保留）
├── LICENSE                   # 许可证（保留）
├── CLAUDE.md                 # AI 助手指令（保留）
├── install.sh                # [新增] 安装/配置脚本
│
├── hooks/                    # [新增] Hook 脚本目录
│   ├── permission-notify.sh  # 从根目录移入
│   └── webhook-notify.sh     # 从根目录移入
│
├── server/                   # [重命名] callback-server → server
│   ├── main.py               # [重命名] server.py → main.py
│   ├── start.sh              # [重命名] start-server.sh → start.sh
│   ├── config.py
│   ├── handlers/
│   ├── models/
│   └── services/
│
├── shell-lib/                # [重命名] lib → shell-lib
│   └── ...
│
├── shared/                   # [新增] 跨语言共享模块
│   ├── protocol.md           # Socket 协议规范文档
│   └── logging.json          # 统一日志配置
│
├── config/                   # 配置文件（保留）
│   └── tools.json
│
├── log/                      # 日志目录（保留）
│
├── docs/                     # [新增] 文档目录
│   ├── AGENTS.md             # 从根目录移入
│   └── TEST.md               # 从根目录移入
│
└── openspec/                 # 规范文档（保留）
```

### 2. Socket 协议抽象

创建 `shared/protocol.md` 定义统一协议：

```markdown
# Socket 通信协议 v1

## 连接方式
- Unix Domain Socket: `/tmp/claude-permission.sock`

## 消息格式

### 请求消息（客户端 → 服务端）
原始 JSON，UTF-8 编码，无长度前缀

### 确认响应（服务端 → 客户端）
原始 JSON: `{"success": true, "message": "Request registered"}`

### 决策响应（服务端 → 客户端）
4字节大端序长度前缀 + JSON 数据
```

### 3. 日志配置统一

创建 `shared/logging.json`：
```json
{
  "log_dir": "log",
  "date_format": "%Y%m%d",
  "time_format": "%Y-%m-%d %H:%M:%S",
  "format": "[{pid}] {time}.{ms} [{level}] {message}"
}
```

Shell 和 Python 都读取此配置，消除硬编码重复。

## 影响范围

| 组件 | 变更类型 | 说明 |
|------|----------|------|
| permission-notify.sh | 移动 | 移至 `hooks/` 目录 |
| webhook-notify.sh | 移动 | 移至 `hooks/` 目录 |
| callback-server/ | 重命名 | 重命名为 `server/` |
| server.py | 重命名 | 重命名为 `main.py` |
| lib/ | 重命名 | 重命名为 `shell-lib/` |
| shell-lib/socket.sh | 修改 | 引用协议文档，更新路径 |
| socket-client.py | 修改 | 引用协议文档，读取共享日志配置 |
| 文档 | 移动 | AGENTS.md, TEST.md 移至 `docs/` |
| install.sh | 新增 | 安装配置脚本 |

## 兼容性

- **Hook 配置需要更新**：用户需要将 hook 路径从 `permission-notify.sh` 改为 `hooks/permission-notify.sh`
- 建议在 `install.sh` 中提供配置辅助
- 提供迁移说明文档

## 决定事项

1. **提供 install.sh 脚本**
   - 自动配置 Claude Code hook
   - 检测环境依赖
   - 生成配置模板

2. **CLAUDE.md 保留在根目录**
   - Claude Code 依赖根目录的 CLAUDE.md

3. **lib/ 重命名为 shell-lib/**
   - 更明确地表示这是 Shell 专用库
   - 同步更新所有代码中的路径引用

4. **不创建符号链接**
   - 代码库尚未用于生产环境
   - 直接重构，不做向后兼容
