# Tasks: 项目结构重组任务清单

## 阶段 1：准备工作

- [x] 1.1 创建新目录结构
  - 创建 `hooks/`, `shared/`, `docs/` 目录
  - 验证目录权限

- [x] 1.2 编写协议规范文档
  - 创建 `shared/protocol.md`
  - 从现有代码中提取协议细节
  - 添加消息格式示例

- [x] 1.3 编写统一日志配置
  - 创建 `shared/logging.json`
  - 定义各组件的日志文件模式

- [x] 1.4 编写 install.sh 安装脚本
  - 检测环境依赖
  - 配置 Claude Code hook
  - 生成环境变量模板

## 阶段 2：文件迁移

- [x] 2.1 移动 Hook 脚本
  - `permission-notify.sh` → `hooks/permission-notify.sh`
  - `webhook-notify.sh` → `hooks/webhook-notify.sh`
  - 更新脚本内的路径引用（使用 PROJECT_ROOT）

- [x] 2.2 重命名服务端目录
  - `callback-server/` → `server/`
  - `server.py` → `main.py`
  - `start-server.sh` → `start.sh`

- [x] 2.3 重命名 Shell 库目录
  - `lib/` → `shell-lib/`
  - 更新所有引用该目录的文件

- [x] 2.4 移动文档文件
  - `AGENTS.md` → `docs/AGENTS.md`
  - `TEST.md` → `docs/TEST.md`
  - 更新 README.md 中的文档链接

## 阶段 3：引用更新

- [x] 3.1 更新 Hook 脚本引用
  - `hooks/permission-notify.sh` 中的 source 路径
  - `hooks/webhook-notify.sh` 中的 source 路径
  - 使用 `PROJECT_ROOT` 变量统一路径计算

- [x] 3.2 更新 Shell 库内部引用
  - `shell-lib/socket.sh` 中的 socket-client.py 路径
  - `shell-lib/tool.sh` 中的 tool-config.sh 路径
  - 验证 source 路径正确性

- [x] 3.3 更新 Python 导入路径
  - `server/main.py` 中的日志目录
  - `server/socket-client.py` 中的日志目录
  - `server/models/tool_config.py` 中的 config 路径

- [x] 3.4 更新启动脚本
  - `server/start.sh` 中的路径引用

## 阶段 4：日志系统统一

- [x] 4.1 实现 Shell 日志配置读取
  - 修改 `shell-lib/log.sh` 读取 `shared/logging.json`
  - 保留内置降级配置

- [x] 4.2 实现 Python 日志配置读取
  - 创建 `shared/logging_config.py` 或直接在各文件中读取
  - 修改 `server/main.py` 使用统一配置
  - 修改 `server/socket-client.py` 使用统一配置

## 阶段 5：协议引用更新

- [x] 5.1 更新 Socket 相关代码注释
  - `shell-lib/socket.sh` 添加协议文档引用
  - `server/socket-client.py` 添加协议文档引用
  - `server/services/request_manager.py` 添加协议文档引用

## 阶段 6：文档和测试

- [x] 6.1 更新 README.md
  - 更新目录结构说明
  - 更新 Hook 配置路径示例
  - 添加 install.sh 使用说明

- [x] 6.2 手动测试
  - 验证 Hook 脚本可正常执行
  - 验证服务端可正常启动
  - 验证飞书通知流程完整
  - 验证 install.sh 正常工作

- [x] 6.3 清理
  - 删除空目录 `callback-server/`, `lib/`
  - 更新 .gitignore（如需要）

## 依赖关系

```
1.1 ──┬──> 2.1 ──> 3.1 ──┐
      │                   │
      ├──> 2.2 ──> 3.2 ──┼──> 6.2 ──> 6.3
      │                   │
      └──> 2.3 ──────────┘

1.2 ──> 5.1

1.3 ──> 4.1 ──┐
       4.2 ──┴──> 6.2
```

## 风险与缓解

| 风险 | 缓解措施 |
|------|----------|
| Hook 路径变更导致用户配置失效 | README 中添加迁移说明 |
| 相对路径计算错误 | 每次修改后立即测试 |
| Python 导入路径问题 | 逐文件验证 import 语句 |

## 验收标准

1. 根目录只有：README.md, CHANGELOG.md, LICENSE, CLAUDE.md, .gitignore
2. `hooks/permission-notify.sh` 可独立执行
3. `server/start.sh` 可正常启动服务
4. 日志文件按配置输出到正确位置
5. 所有文档链接有效
