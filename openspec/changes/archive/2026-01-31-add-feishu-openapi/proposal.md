# 飞书 OpenAPI 发送消息功能实现计划

## 目标

在现有后端服务中新增飞书 OpenAPI 消息发送能力，支持：
- 发送给用户（open_id/user_id）或群聊（chat_id）
- 先实现 stop 事件通知，后续扩展其他事件
- Webhook 和 OpenAPI 两种模式共存，通过配置切换

## 新增配置项

```bash
# 飞书应用凭证
FEISHU_APP_ID=
FEISHU_APP_SECRET=

# 消息接收者 (支持 ou_xxx / oc_xxx / user_id)
FEISHU_RECEIVE_ID=

# 接收者类型 (可选，自动检测)
FEISHU_RECEIVE_ID_TYPE=

# 发送模式: webhook / openapi / both
FEISHU_SEND_MODE=webhook
```

## 文件变更

### 1. 新增文件

**`src/server/services/feishu_api.py`** - 飞书 OpenAPI 服务模块
- `TokenManager` - token 获取与缓存（2小时有效期，提前5分钟刷新）
- `MessageSender` - 消息发送（支持卡片和文本）
- `FeishuAPIService` - 服务入口（单例模式）
- `detect_receive_id_type()` - 根据 ID 前缀自动检测类型

### 2. 修改文件

**`src/server/handlers/feishu.py`**
- 扩展 `handle_feishu_request()` 支持新的 POST 路由
- 新增 `handle_send_message()` - 处理 `/feishu/send` 请求
- 新增 `_build_stop_card()` - 构建 stop 卡片 JSON

**`src/server/handlers/callback.py`**
- 在 `do_POST()` 中添加路由分发（按 path 区分）

**`src/server/config.py`**
- 新增飞书 OpenAPI 相关配置变量

**`src/server/main.py`**
- 启动时初始化 `FeishuAPIService`

**`src/lib/feishu.sh`**
- 重构 `send_feishu_card()` 支持双模式
- 新增 `_send_feishu_card_api()` 调用后端 API

**`.env.example` 和 `install.sh`**
- 新增配置项说明

## HTTP 端点设计

| 端点 | 方法 | 功能 |
|------|------|------|
| `/feishu/send` | POST | 发送卡片消息 |

请求格式：
```json
{
  "card_json": "...",
  "receive_id": "ou_xxx",      // 可选，默认用配置
  "receive_id_type": "open_id" // 可选，自动检测
}
```

## 实现步骤

### Step 1: 后端核心模块
1. 创建 `src/server/services/feishu_api.py`
2. 扩展 `src/server/config.py` 新增配置项

### Step 2: HTTP 端点
1. 扩展 `handlers/feishu.py` 添加消息发送处理
2. 修改 `handlers/callback.py` 添加路由分发
3. 修改 `main.py` 初始化服务

### Step 3: Shell 集成
1. 重构 `lib/feishu.sh` 支持双模式
2. 更新 `.env.example` 和 `install.sh`

## 验证方法

1. 启动服务后，使用 curl 测试：
```bash
# 测试发送消息
curl -X POST http://localhost:8080/feishu/send \
  -H "Content-Type: application/json" \
  -d '{"card_json": "{\"msg_type\":\"text\",\"content\":{\"text\":\"test\"}}"}'
```

2. 配置 `FEISHU_SEND_MODE=openapi` 后触发 stop 事件，检查是否收到消息

3. 检查日志 `log/callback_*.log` 中的 `[feishu-api]` 日志
