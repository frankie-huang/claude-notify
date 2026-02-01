# 任务清单：飞书消息回复继续 Claude 会话

## 阶段 1：映射注册

### 1.1 新增 SessionStore 服务
- [x] 创建 `src/server/services/session_store.py`
- [x] 实现 `save()` 方法：保存 message_id → session 映射
- [x] 实现 `get()` 方法：查询映射，支持过期检查
- [x] 实现 `cleanup_expired()` 方法：清理过期数据
- [ ] 添加单元测试

### 1.2 修改 stop.sh
- [x] 添加 `CALLBACK_URL` 配置读取
- [x] 修改 `send_stop_notification_async()` 传递额外参数
- [x] 更新 `send_feishu_card()` 调用签名

### 1.3 修改 feishu.sh
- [x] 修改 `send_feishu_card()` 函数签名（添加参数）
- [x] 修改 `_send_feishu_card_http_endpoint()` 函数（添加参数）
- [x] 请求体添加 session_id、project_dir、callback_url 字段
- [x] 保持向后兼容（参数可选）

### 1.3-b 修改 permission.sh
- [x] 交互模式：传递 session_id、project_dir、callback_url
- [x] 降级模式：传递 session_id、project_dir、callback_url
- [x] 保持向后兼容（参数可选）

### 1.4 修改飞书网关 handle_send_message
- [x] 提取 session_id、project_dir、callback_url
- [x] 发送成功后调用 SessionStore.save()
- [x] 验证映射保存成功

### 1.5 初始化 SessionStore
- [x] 在服务启动时初始化 SessionStore
- [x] 创建 data 目录
- [x] 加载现有映射数据

## 阶段 2：消息处理

### 2.1 扩展飞书网关消息处理
- [x] 修改 `_handle_message_event()` 检测 parent_id
- [x] 新增 `_handle_reply_message()` 函数
- [x] 实现 SessionStore 查询逻辑
- [x] 实现 Callback 后端转发逻辑
- [x] 添加日志记录

### 2.2 新增 Callback 后端接口
- [x] 创建 `src/server/handlers/claude.py`
- [x] 实现 `handle_continue_session()` 函数
- [x] 实现 `_run_claude_async()` 函数
- [x] 添加参数验证

### 2.3 注册路由
- [x] 在 CallbackHandler 中注册 `/claude/continue` 路由
- [x] 添加错误处理

### 2.4 Claude 命令封装
- [x] 实现 subprocess 调用逻辑
- [x] 添加超时控制
- [x] 添加输出捕获
- [x] 错误处理与日志

## 阶段 3：优化与测试

### 3.1 错误处理优化
- [x] 会话不存在时的友好提示（忽略未注册消息）
- [x] 目录不存在时的错误提示
- [x] Callback 不可达时的错误处理
- [x] 命令执行失败的错误通知

### 3.2 过期清理机制
- [x] 添加定时清理任务
- [x] 配置清理间隔
- [x] 添加清理日志

### 3.3 测试
- [ ] 单机模式端到端测试
- [ ] 分离部署模式测试
- [ ] 会话过期场景测试
- [ ] 错误场景测试
- [ ] 并发回复测试

### 3.4 文档更新
- [ ] 更新 README.md
- [ ] 更新 .env.example 配置说明
- [ ] 添加使用示例

## 并行化建议

以下任务可以并行执行：
- 1.1 SessionStore 服务 和 1.2 stop.sh 修改
- 2.1 飞书网关处理 和 2.2 Callback 接口
- 3.1 错误处理 和 3.2 过期清理

## 依赖关系

```
1.1 ──> 1.5 ──> 1.4
       │
       └──> 1.3 ──> 1.4

1.4 ──> 2.1 ──> 2.3
                │
2.2 ───────────┘

2.1, 2.2 ──> 3.1, 3.2, 3.3, 3.4
```
