# Tasks: 可交互权限控制

## 1. 回调服务开发

- [x] 1.1 创建 `callback-server/` 目录结构
- [x] 1.2 实现 HTTP 服务器（使用 Python 标准库或 Flask）
- [x] 1.3 实现 URL 端点：`/allow`, `/always`, `/deny`, `/interrupt`, `/status`
- [x] 1.4 实现请求 ID 管理器（内存存储，带 TTL 清理）
- [x] 1.5 实现 Unix Domain Socket 服务端（接收 permission-notify.sh 请求）
- [x] 1.6 实现飞书 Webhook 卡片消息发送（带 URL 跳转按钮）
- [x] 1.7 实现"始终允许"功能：写入 `.claude/settings.local.json`
- [x] 1.8 实现响应页面（用户点击后显示确认信息）
- [x] 1.9 添加日志记录
- [x] 1.10 编写 `requirements.txt`（如使用 Flask）
- [x] 1.11 编写服务启动脚本 `start-server.sh`

## 2. 通知脚本重构

- [x] 2.1 重构 `permission-notify.sh` 支持与回调服务通信
- [x] 2.2 实现 Unix Domain Socket 客户端
- [x] 2.3 实现请求 ID 生成（时间戳 + UUID）
- [x] 2.4 实现阻塞等待响应（带 55 秒超时）
- [x] 2.5 实现 JSON 输出格式（返回 hookSpecificOutput）
- [x] 2.6 实现服务不可用时的降级逻辑（仅通知模式）

## 3. 飞书卡片设计

- [x] 3.1 设计带 URL 跳转按钮的卡片 JSON 模板
- [x] 3.2 按钮配置：批准运行、始终允许、拒绝运行、拒绝并中断
- [x] 3.3 按钮 URL 携带请求 ID
- [x] 3.4 添加超时提示文案（如"请在 60 秒内操作"）

## 4. 测试验证

- [x] 4.1 测试回调服务启动和 HTTP 端点
- [x] 4.2 测试卡片发送和按钮 URL 正确性
- [x] 4.3 测试按钮点击后 HTTP 回调接收
- [x] 4.4 测试 Socket 通信完整流程
- [x] 4.5 测试 Claude Code 端到端流程
- [x] 4.6 测试超时场景
- [x] 4.7 测试服务不可用降级场景
- [x] 4.8 测试"始终允许"规则写入

## 5. 文档更新

- [x] 5.1 更新 README.md 使用说明
- [x] 5.2 编写回调服务部署文档
- [x] 5.3 更新 Claude Code hooks 配置示例
- [x] 5.4 编写环境变量配置说明
