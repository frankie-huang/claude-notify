# Spec: 项目结构规范

## ADDED Requirements

### Requirement: 根目录简洁性
根目录 SHALL 只保留入口级文件和必要的配置文件。

#### Scenario: 检查根目录文件数量
- Given 项目根目录
- When 列出根目录下的非目录文件
- Then 只包含以下文件：
  - README.md（主文档）
  - CHANGELOG.md（变更日志）
  - LICENSE（许可证）
  - CLAUDE.md（AI 助手指令）
  - .gitignore（Git 忽略配置）

### Requirement: Hook 脚本目录组织
所有 Claude Code Hook 脚本 MUST 统一放置在 `hooks/` 目录。

#### Scenario: Hook 脚本位置
- Given 需要配置 PermissionRequest Hook
- When 查找 Hook 脚本
- Then 脚本位于 `hooks/permission-notify.sh`

#### Scenario: Hook 脚本独立执行
- Given `hooks/permission-notify.sh` 脚本
- When 从任意目录执行该脚本
- Then 脚本能正确找到其依赖的 shell-lib/ 和 config/ 目录

### Requirement: 服务端目录组织
回调服务器代码 MUST 统一放置在 `server/` 目录。

#### Scenario: 服务端启动脚本
- Given 需要启动回调服务器
- When 执行启动命令
- Then 使用 `server/start.sh` 脚本

#### Scenario: 服务端主程序
- Given `server/` 目录
- When 查找主程序入口
- Then 主程序为 `server/main.py`

### Requirement: 共享资源目录
跨语言共享的协议和配置 SHALL 放置在 `shared/` 目录。

#### Scenario: Socket 协议规范
- Given 需要了解 Socket 通信协议
- When 查找协议文档
- Then 协议规范位于 `shared/protocol.md`

#### Scenario: 日志配置
- Given Shell 脚本或 Python 程序需要配置日志
- When 读取日志配置
- Then 统一日志配置位于 `shared/logging.json`

### Requirement: 文档目录组织
非核心文档 SHALL 放置在 `docs/` 目录。

#### Scenario: 测试文档
- Given 需要查看测试说明
- When 查找测试文档
- Then 文档位于 `docs/TEST.md`

### Requirement: Shell 库目录命名
Shell 函数库 MUST 放置在 `shell-lib/` 目录，明确表示其语言归属。

#### Scenario: Shell 库位置
- Given 需要查找 Shell 日志函数
- When 查找日志库文件
- Then 文件位于 `shell-lib/log.sh`

### Requirement: 安装脚本
项目 SHALL 提供 `install.sh` 脚本简化用户配置。

#### Scenario: 安装脚本检测依赖
- Given 执行 `./install.sh --check`
- When 系统缺少必要依赖（如 python3）
- Then 脚本报告缺少的依赖列表

#### Scenario: 安装脚本配置 hook
- Given 执行 `./install.sh`
- When 用户确认配置
- Then 脚本将 hook 路径写入 Claude Code 配置

## MODIFIED Requirements

### Requirement: 日志配置统一
Shell 和 Python 组件 MUST 使用相同的日志配置源。

#### Scenario: 日志目录一致性
- Given Hook 脚本和服务端程序运行
- When 查看各组件的日志输出目录
- Then 所有日志输出到同一个 `log/` 目录

#### Scenario: 日志格式一致性
- Given 多个组件产生日志
- When 比较日志格式
- Then 时间戳格式和字段顺序保持一致

### Requirement: 协议文档化
Socket 通信协议 MUST 有明确的文档说明。

#### Scenario: 协议实现引用
- Given `lib/socket.sh` 中的协议实现代码
- When 查看代码注释
- Then 注释中引用 `shared/protocol.md` 作为协议规范

#### Scenario: 协议版本标识
- Given `shared/protocol.md` 协议文档
- When 查看文档内容
- Then 文档包含版本号（如 v1）

## 目录结构参考

```
claude-notify/
├── README.md
├── CHANGELOG.md
├── LICENSE
├── CLAUDE.md
├── .gitignore
├── install.sh                # 安装配置脚本
│
├── hooks/                    # Hook 脚本
│   ├── permission-notify.sh
│   └── webhook-notify.sh
│
├── server/                   # 回调服务器
│   ├── main.py
│   ├── start.sh
│   ├── config.py
│   ├── socket-client.py
│   ├── handlers/
│   ├── models/
│   ├── services/
│   └── templates/
│
├── shell-lib/                # Shell 函数库
│   ├── log.sh
│   ├── json.sh
│   ├── tool.sh
│   ├── tool-config.sh
│   ├── feishu.sh
│   └── socket.sh
│
├── shared/                   # 共享资源
│   ├── protocol.md
│   └── logging.json
│
├── config/                   # 配置文件
│   └── tools.json
│
├── docs/                     # 文档
│   ├── AGENTS.md
│   └── TEST.md
│
├── log/                      # 日志目录
│
└── openspec/                 # OpenSpec 规范
```
