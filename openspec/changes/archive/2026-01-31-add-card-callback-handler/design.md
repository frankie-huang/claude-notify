# 设计文档: 飞书卡片回传交互处理

## 架构概览

```
用户点击飞书卡片按钮
        ↓
飞书开放平台发送 card.action.trigger 事件
        ↓
回调服务器 POST 处理
        ↓
handlers/feishu.py 解析事件
        ↓
复用现有决策处理逻辑 (request_manager.resolve)
        ↓
返回 toast 响应给飞书
        ↓
用户在飞书内看到结果提示
```

## 组件设计

### 1. 按钮模板 (`src/templates/feishu/buttons.json`)

将四个按钮的 behaviors 从 `open_url` 改为 `callback`：

```json
{
  "tag": "button",
  "text": { "tag": "plain_text", "content": "批准运行" },
  "type": "primary_filled",
  "behaviors": [
    {
      "type": "callback",
      "value": {
        "action": "allow",
        "request_id": "{{request_id}}"
      }
    }
  ]
}
```

**按钮 action 映射**:
| 按钮 | action | 对应原 GET 端点 |
|------|--------|----------------|
| 批准运行 | `allow` | `/allow` |
| 始终允许 | `always` | `/always` |
| 拒绝运行 | `deny` | `/deny` |
| 拒绝并中断 | `interrupt` | `/interrupt` |

### 2. 事件处理器 (`src/server/handlers/feishu.py`)

新增 `handle_card_action` 函数处理 `card.action.trigger` 事件：

```python
def handle_card_action(data: dict) -> Tuple[bool, dict]:
    """处理卡片回传交互事件

    Args:
        data: card.action.trigger 事件数据

    Returns:
        (handled, toast_response)
    """
    event = data.get('event', {})
    action = event.get('action', {})
    value = action.get('value', {})

    action_type = value.get('action')  # allow/always/deny/interrupt
    request_id = value.get('request_id')

    # 调用对应的决策处理逻辑
    # ...

    return True, {
        "toast": {
            "type": "success",  # 或 error
            "content": "已批准运行"
        }
    }
```

### 3. 决策处理复用

为避免代码重复，需要将 `handlers/callback.py` 中的决策处理逻辑抽取为可复用函数：

```python
# services/decision_handler.py (新文件)

def handle_decision(
    request_manager: RequestManager,
    request_id: str,
    action: str
) -> Tuple[bool, str, str]:
    """处理用户决策

    Args:
        request_manager: 请求管理器
        request_id: 请求 ID
        action: 动作类型 (allow/always/deny/interrupt)

    Returns:
        (success, toast_type, toast_message)
    """
```

### 4. Toast 响应类型

| 场景 | toast.type | toast.content |
|------|-----------|---------------|
| 批准成功 | `success` | 已批准运行 |
| 始终允许成功 | `success` | 已始终允许，后续相同操作将自动批准 |
| 拒绝成功 | `success` | 已拒绝运行 |
| 拒绝并中断成功 | `success` | 已拒绝并中断 |
| 请求不存在 | `error` | 请求不存在或已过期 |
| 请求已处理 | `warning` | 该请求已被处理，请勿重复操作 |
| 连接已断开 | `error` | 请求已失效，请返回终端查看状态 |

## 数据流

### 请求处理流程

```
1. POST /  (飞书回调)
   ├─ 检查 event_type == "card.action.trigger"
   ├─ 提取 action.value.action 和 action.value.request_id
   ├─ 验证 request_id 存在且有效
   ├─ 根据 action 类型调用对应处理:
   │   ├─ allow: Decision.allow()
   │   ├─ always: Decision.allow() + 写入规则
   │   ├─ deny: Decision.deny()
   │   └─ interrupt: Decision.deny(interrupt=True)
   ├─ 通过 request_manager.resolve() 发送决策
   └─ 返回 toast 响应
```

### 错误处理

```
1. request_id 不存在
   └─ 返回 {"toast": {"type": "error", "content": "请求不存在或已过期"}}

2. 请求已被处理
   └─ 返回 {"toast": {"type": "warning", "content": "该请求已被处理"}}

3. Socket 连接断开
   └─ 返回 {"toast": {"type": "error", "content": "请求已失效"}}
```

## 配置说明

### 飞书开放平台配置

用户需要在飞书开放平台完成以下配置：

1. **事件订阅**
   - 订阅 `card.action.trigger`（卡片回传交互）事件
   - 配置请求地址为回调服务器地址

2. **应用权限**
   - 无需额外权限（卡片回调使用应用已有权限）

### 本地配置

`.env` 无需新增配置项，复用现有的：
- `CALLBACK_SERVER_URL`: 回调服务器地址
- `CALLBACK_SERVER_PORT`: 端口

## 兼容性

### 向后兼容

- 保留所有 GET 端点，支持：
  - 旧版本卡片（使用 open_url）
  - 手动访问 URL
  - 调试用途

### 降级策略

如果用户未订阅 `card.action.trigger` 事件：
- 按钮点击不会触发任何动作（飞书静默忽略）
- 需要在文档中说明配置步骤

## 测试计划

1. **单元测试**
   - `handle_card_action` 函数各种输入场景
   - Toast 响应格式验证

2. **集成测试**
   - 模拟飞书回调请求
   - 验证决策正确传递

3. **端到端测试**
   - 在飞书中点击按钮
   - 验证 toast 显示
   - 验证权限决策生效
