# Tasks: Remove Server-Side Timeout

## Implementation Tasks

### 1. 修改 RequestManager 类
- [x] 移除 `REQUEST_TTL` 常量
- [x] 移除 `STATUS_EXPIRED` 状态（改为 `STATUS_DISCONNECTED`）
- [x] 修改 `resolve()` 方法：不再检查时间，改为检查 socket 连接状态
- [x] 重构 `cleanup_expired()` 为 `cleanup_disconnected()`：检测并清理已断开的 socket

### 2. 修改 HTTP 回调处理
- [x] 更新错误消息：区分"已被处理"和"连接已断开"
- [x] 移除飞书卡片中的超时提示（改为"请尽快操作以避免 Claude 超时"）

### 3. 修改清理线程
- [x] 改为检测 socket 连接状态而非时间
- [x] 使用 `select()` 机制检测 socket 是否可写

### 4. 更新规范文档
- [x] 修改 Timeout Handling requirement（改为 Connection-Based Request Validity）
- [x] 更新场景描述
- [x] 更新 Response Page requirement

## Validation

- [ ] 测试：启动服务后等待超过原 TTL 时间，点击按钮仍能正常处理
- [ ] 测试：Claude Code 取消等待后，点击按钮显示"连接已断开"
- [ ] 测试：重复点击按钮，第二次显示"已被处理"
