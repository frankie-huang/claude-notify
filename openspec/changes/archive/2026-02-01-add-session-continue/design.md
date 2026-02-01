# 设计文档：飞书消息回复继续 Claude 会话

## 一、架构设计

### 1.1 支持的场景

本方案支持用户回复以下两类飞书消息来继续会话：

| 场景 | 触发时机 | 卡片类型 | 是否包含操作按钮 |
|------|----------|----------|------------------|
| **Stop 事件** | Claude 任务完成 | 完成通知卡片 | 无 |
| **权限请求** | Claude 请求权限 | 权限请求卡片 | 有（批准/拒绝等） |

### 1.2 分离模式组件关系

```
┌─────────────────────────────────────────────────────────────────┐
│                         飞书网关                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                   SessionStore                          │    │
│  │  message_id → {session_id, project_dir, callback_url}   │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              im.message.receive_v1 处理                  │    │
│  │  1. 提取 parent_id                                       │    │
│  │  2. 查询 SessionStore                                     │    │
│  │  3. 转发到 Callback 后端                                  │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                               │
                               │ POST /claude/continue
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Callback 后端                               │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                /claude/continue 端点                     │    │
│  │  1. 接收请求参数                                         │    │
│  │  2. 异步执行 claude --resume                             │    │
│  │  3. 立即返回 "processing"                                │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 映射表结构

存储位置：飞书网关本地，`runtime/session_messages.json`

```json
{
  "om_xxx": {
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "project_dir": "/home/user/project",
    "callback_url": "http://192.168.1.100:8080",
    "created_at": 1706745600
  }
}
```

### 1.3 时序图

#### 注册映射时序

**场景 A：Stop 事件通知**

```
stop.sh          feishu.sh       飞书网关        飞书API        SessionStore
  │                 │               │              │                │
  │ send_card()     │               │              │                │
  │─────────────────>               │              │                │
  │                 │ POST /feishu/send             │                │
  │                 │──────────────>               │                │
  │                 │               │ 发送消息      │                │
  │                 │               │─────────────>                 │
  │                 │               │ 返回message_id                │
  │                 │               │<─────────────                 │
  │                 │               │ save(message_id, ...)         │
  │                 │               │──────────────────────────────>│
  │                 │               │ success                      │
  │                 │<─────────────────────────────────────────────│
  │                 │ success        │                               │
  │<─────────────────               │                               │
```

**场景 B：权限请求通知**

```
permission.sh    feishu.sh       飞书网关        飞书API        SessionStore
  │                 │               │              │                │
  │ send_card()     │               │              │                │
  │─────────────────>               │              │                │
  │                 │ POST /feishu/send             │                │
  │                 │──────────────>               │                │
  │                 │               │ 发送消息      │                │
  │                 │               │─────────────>                 │
  │                 │               │ 返回message_id                │
  │                 │               │<─────────────                 │
  │                 │               │ save(message_id, ...)         │
  │                 │               │──────────────────────────────>│
  │                 │               │ success                      │
  │                 │<─────────────────────────────────────────────│
  │                 │ success        │                               │
  │<─────────────────               │                               │
```

#### 继续会话时序

```
用户           飞书          飞书网关    SessionStore    Callback后端    Claude
 │              │               │            │               │           │
 │ 回复消息     │               │            │               │           │
 │─────────────>               │            │               │           │
 │              │ receive_v1    │            │               │           │
 │              │──────────────>            │               │           │
 │              │               │ get(parent_id)            │           │
 │              │               │───────────>               │           │
 │              │               │ mapping                   │           │
 │              │               │<──────────                │           │
 │              │               │ POST /claude/continue     │           │
 │              │               │──────────────────────────>│           │
 │              │               │            │ processing   │           │
 │              │               │<─────────────────────────│           │
 │              │               │            │               │ claude -p
 │              │               │            │               │───>       │
 │              │               │            │               │   结果    │
 │              │               │            │               │<───       │
 │              │               │            │ hook发送结果  │           │
 │              │               │            │───────────────>           │
 │              │ 结果通知       │            │               │           │
 │<─────────────│<──────────────│            │               │           │
```

## 二、核心组件设计

### 2.1 SessionStore（飞书网关）

```python
class SessionStore:
    """管理 message_id -> session 信息的映射"""

    EXPIRE_SECONDS = 7 * 24 * 3600  # 7 天

    def save(self, message_id: str, session_id: str,
              project_dir: str, callback_url: str) -> bool

    def get(self, message_id: str) -> Optional[Dict]

    def cleanup_expired(self) -> int
```

### 2.2 飞书网关消息处理（feishu.py）

```python
def _handle_message_event(data: dict):
    """处理 im.message.receive_v1 事件"""
    parent_id = message.get('parent_id', '')
    if parent_id:
        return _handle_reply_message(data, parent_id)
    # 原有逻辑...

def _handle_reply_message(data: dict, parent_id: str):
    """处理回复消息，继续会话"""
    mapping = SessionStore.get_instance().get(parent_id)
    if not mapping:
        return True, {'status': 'ignored'}

    # 转发到 Callback 后端
    callback_url = mapping['callback_url']
    return _forward_continue_request(callback_url, mapping, prompt)
```

### 2.3 Callback 后端继续会话接口（claude.py）

```python
def handle_continue_session(data: dict) -> Tuple[bool, dict]:
    """处理 /claude/continue 请求"""
    session_id = data.get('session_id')
    project_dir = data.get('project_dir')
    prompt = data.get('prompt')

    # 异步执行避免超时
    thread = threading.Thread(
        target=_run_claude_async,
        args=(session_id, project_dir, prompt),
        daemon=True
    )
    thread.start()

    return True, {'status': 'processing'}
```

## 三、数据协议

### 3.1 /feishu/send 请求扩展

```json
{
  "msg_type": "interactive",
  "content": {...},
  "session_id": "550e8400-e29b...",      // 新增
  "project_dir": "/home/user/project",   // 新增
  "callback_url": "http://..."            // 新增
}
```

### 3.2 /claude/continue 请求

```json
{
  "session_id": "550e8400-e29b...",
  "project_dir": "/home/user/project",
  "prompt": "用户的回复内容",
  "chat_id": "oc_xxx",            // 可选，供 callback 决定回复到哪
  "reply_message_id": "om_yyy"    // 可选
}
```

### 3.3 /claude/continue 响应

```json
{
  "status": "processing"
}
```

## 四、错误处理

| 场景 | 飞书网关处理 | Callback 处理 |
|------|-------------|--------------|
| 映射不存在 | 忽略消息 | - |
| Callback 不可达 | 记录错误，返回错误 toast | - |
| 会话已过期 | - | hook 发送错误提示 |
| 目录不存在 | - | 返回错误 |
| 命令执行超时 | - | 异步执行，hook 通知结果 |

## 五、安全考虑

1. **Callback URL 验证**：确保 callback_url 来自配置的可信来源
2. **输入验证**：严格验证 session_id、project_dir 格式
3. **路径遍历防护**：检查 project_dir 范围
4. **命令注入防护**：prompt 参数需要安全传递

## 六、性能考虑

1. **映射存储**：使用内存缓存 + 定期持久化
2. **过期清理**：定期后台任务清理过期映射
3. **异步执行**：Claude 命令异步执行，避免阻塞
4. **并发控制**：使用线程锁保护映射文件

## 七、实现优先级

### 阶段 1：映射注册
1. SessionStore 实现
2. stop.sh 修改（传递参数）
3. feishu.sh 修改（请求体扩展）
4. 飞书网关 handle_send_message 修改

### 阶段 2：消息处理
1. 飞书网关 _handle_message_event 扩展
2. Callback 后端 /claude/continue 接口
3. Claude 调用封装

### 阶段 3：优化
1. 错误提示优化
2. 过期清理定时任务
3. 监控日志增强
