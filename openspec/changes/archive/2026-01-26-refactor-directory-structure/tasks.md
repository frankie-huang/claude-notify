# Tasks: 目录重构实施清单

## 1. 准备工作
- [ ] 1.1 备份当前项目状态（创建 git 标签）
- [ ] 1.2 创建 `src/` 目录及子目录结构

## 2. Shell 库重构
- [ ] 2.1 创建 `src/lib/core.sh`，整合 `project.sh`、`env.sh`、`log.sh`
- [ ] 2.2 迁移 `json.sh` 到 `src/lib/json.sh`
- [ ] 2.3 迁移 `feishu.sh` 到 `src/lib/feishu.sh`
- [ ] 2.4 迁移 `socket.sh` 到 `src/lib/socket.sh`
- [ ] 2.5 迁移 `tool.sh` 到 `src/lib/tool.sh`
- [ ] 2.6 迁移 `tool-config.sh` 到 `src/lib/tool-config.sh`
- [ ] 2.7 迁移 `vscode-proxy.sh` 到 `src/lib/vscode-proxy.sh`

## 3. Hook 脚本迁移与路由改造
- [ ] 3.1 创建 `src/hooks/` 目录
- [ ] 3.2 迁移 `hooks/hook-router.sh` 到 `src/hook-router.sh`，重构为统一入口
- [ ] 3.3 迁移 `hooks/permission-notify.sh` 到 `src/hooks/permission.sh`
- [ ] 3.4 迁移 `hooks/webhook-notify.sh` 到 `src/hooks/webhook.sh`
- [ ] 3.5 改造 `hook-router.sh`：读取 stdin 到 $INPUT，解析事件类型，分发到子脚本
- [ ] 3.6 改造 `permission.sh`：移除 stdin 读取，使用 $INPUT 变量
- [ ] 3.7 改造 `webhook.sh`：移除 stdin 读取，使用 $INPUT 变量
- [ ] 3.8 更新脚本中的 source 路径引用

## 4. Python 服务迁移
- [ ] 4.1 创建 `src/start-server.sh`（服务启动入口）
- [ ] 4.2 迁移 `server/` 到 `src/server/`（保留 server/start.sh 作为内部启动脚本）
- [ ] 4.3 更新 `src/server/config.py` 中的路径常量
- [ ] 4.4 更新 `src/start-server.sh` 中的路径引用
- [ ] 4.5 迁移 `shared/` 到 `src/shared/`
- [ ] 4.6 更新 Python 中对 shared 的引用

## 5. 配置和模板迁移
- [ ] 5.1 迁移 `config/` 到 `src/config/`
- [ ] 5.2 迁移 `templates/` 到 `src/templates/`
- [ ] 5.3 更新 Shell 脚本中的模板路径引用
- [ ] 5.4 迁移 `local-proxy/` 到 `src/proxy/`

## 6. 安装脚本和文档更新
- [ ] 6.1 更新 `install.sh` 中的 HOOK_PATH 定义
- [ ] 6.2 更新 `install.sh` 中的目录结构说明
- [ ] 6.3 更新 `.env.example` 中的路径相关说明
- [ ] 6.4 更新 `README.md` 中的目录结构说明
- [ ] 6.5 更新 `README.md` 中的命令示例路径
- [ ] 6.6 更新 `CLAUDE.md` 中的路径引用

## 7. 规范文件更新
- [ ] 7.1 更新 `openspec/specs/project-structure/spec.md`
- [ ] 7.2 更新 `openspec/project.md` 中的目录结构描述

## 8. 测试验证
- [ ] 8.1 运行 `install.sh --check` 验证依赖检测
- [ ] 8.2 运行 `install.sh` 验证 hook 配置
- [ ] 8.3 运行 `src/start-server.sh` 验证服务启动
- [ ] 8.4 手动测试权限通知完整流程
- [ ] 8.5 验证日志输出到 `log/` 目录
- [ ] 8.6 运行 `test/` 目录下的测试脚本

## 9. 清理工作
- [ ] 9.1 删除原 `hooks/` 目录
- [ ] 9.2 删除原 `server/` 目录
- [ ] 9.3 删除原 `shell-lib/` 目录
- [ ] 9.4 删除原 `shared/` 目录
- [ ] 9.5 删除原 `config/` 目录
- [ ] 9.6 删除原 `templates/` 目录
- [ ] 9.7 删除原 `local-proxy/` 目录
- [ ] 9.8 更新 `.gitignore`（如需要）

## 10. 最终验证
- [ ] 10.1 运行 `openspec validate --strict` 验证规范
- [ ] 10.2 Git commit 并创建详细的 commit message
