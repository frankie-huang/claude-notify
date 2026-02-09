# Implementation Tasks

## 1. 飞书网关：/new 指令识别与解析

- [x] 1.1 在 `feishu.py` 的 `_handle_message_event` 中添加 `/new` 指令识别逻辑
- [x] 1.2 实现参数解析：`--dir=/path` 格式
- [x] 1.3 实现回复模式：从 parent_id 查询 project_dir
- [x] 1.4 验证参数完整性（目录、prompt）
- [x] 1.5 转发请求到 Callback 后端 `/claude/new`

## 2. Callback 后端：新建会话接口

- [x] 2.1 在 `claude.py` 中新增 `handle_new_session` 函数
- [x] 2.2 实现 UUID 生成 session_id
- [x] 2.3 保存 session_id → chat_id 映射（复用 ChatIdStore）
- [x] 2.4 验证 project_dir 目录存在性
- [x] 2.5 使用登录 shell 执行 Claude 命令（`--session-id` 参数）
- [x] 2.6 在 `callback.py` 中注册 `/claude/new` 路由

## 3. 会话创建通知

- [x] 3.1 新建会话成功后发送"会话已创建"通知到飞书
- [x] 3.2 保存通知消息的 message_id → session 映射（SessionStore）
- [x] 3.3 支持后续回复继续该会话

## 4. 错误处理与日志

- [x] 4.1 目录不存在时的错误提示
- [x] 4.2 回复消息无映射时的错误提示
- [x] 4.3 参数格式错误的友好提示
- [x] 4.4 完整的日志记录

## 5. 测试验证

- [ ] 5.1 测试 `/new --dir=/path prompt` 直接创建
- [ ] 5.2 测试回复消息时 `/new prompt` 复用目录
- [ ] 5.3 测试无效路径错误处理
- [ ] 5.4 测试后续回复继续新会话
- [ ] 5.5 测试 permission/stop 事件正确路由到 chat_id
