## 1. 配置层
- [x] 1.1 在 `.env.example` 中添加 `DEFAULT_CHAT_DIR` 配置项及说明
- [x] 1.2 在 `src/server/config.py` 中导出 `DEFAULT_CHAT_DIR` 常量
- [x] 1.3 同步更新 `install.sh` 中的配置表和模板

## 2. 启动检测
- [x] 2.1 在 `src/server/main.py` 启动流程中添加默认目录检测与创建逻辑

## 3. 注册流程传播
- [x] 3.1 `auto_register.py`: 注册时传递 `default_chat_dir`
- [x] 3.2 `register.py`: 接收、传递 `default_chat_dir`（注册请求 → 授权卡片 → 授权决策 → upsert）
- [x] 3.3 `binding_store.py`: `upsert()` 支持存储 `default_chat_dir`；新增 `update_field()` 方法

## 4. 默认会话持久化
- [x] 4.1 活跃默认会话 `default_chat_session_id` 持久化到 BindingStore（通过 `update_field()` 方法）

## 5. 消息路由
- [x] 5.1 `_get_binding_from_event`: 返回 binding 浅拷贝并注入 `_owner_id` 字段
- [x] 5.2 `_handle_message_event` 普通消息分支：从 binding 获取 `default_chat_dir` 和 `default_chat_session_id`，自动继续/新建会话
- [x] 5.3 `_handle_new_command`：从 binding 获取 `default_chat_dir`，有 prompt 但无 `--dir` 时使用默认目录
- [x] 5.4 `_forward_claude_request` / `_forward_new_request` / `_forward_continue_request`: 返回 session_id
- [x] 5.5 `_forward_new_request_for_default_dir`: 新建默认会话并持久化 session_id

## 6. 文档
- [x] 6.1 更新 README 相关说明
