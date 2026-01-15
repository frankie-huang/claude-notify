# Tasks: Add Permission Request Notification

## 1. Implementation

- [x] 1.1 创建 `permission-notify.sh` 脚本
  - 从 stdin 读取 JSON 数据
  - 解析 `tool_name`、`tool_input`、`message` 等字段
  - 构建飞书卡片消息，包含权限请求详情
  - 发送 Webhook 请求

- [x] 1.2 处理不同工具类型的权限请求
  - Bash: 显示待执行的命令
  - Edit/Write: 显示目标文件路径
  - 其他工具: 显示工具名称和基本信息

- [x] 1.3 添加错误处理
  - JSON 解析失败时的降级处理
  - Webhook 发送失败时的静默处理（不阻塞 Claude Code）

## 2. Configuration

- [x] 2.1 编写 Hook 配置示例文档
  - 说明如何在 `.claude/settings.json` 中配置 `PermissionRequest` hook
  - 提供匹配器配置示例（Bash, Edit, Write, * 等）

## 3. Testing

- [x] 3.1 手动测试脚本
  - 模拟 JSON 输入测试脚本解析
  - 验证飞书消息格式正确显示
