# 变更提案: 添加飞书卡片回传交互处理

## 变更 ID

`add-card-callback-handler`

## Why

当前飞书卡片按钮使用 `open_url` 类型，点击后跳转浏览器显示结果，存在以下问题：
- 用户需要在飞书和浏览器之间切换，体验不流畅
- 需要额外配置浏览器安全策略才能自动跳转 VSCode
- URL 跳转方式在移动端体验较差

通过实现飞书卡片回传交互（`card.action.trigger` 事件），用户点击按钮后飞书直接调用回调服务器，服务器返回 toast 提示，用户无需离开飞书即可完成操作。

## What Changes

### 1. 新增 OpenAPI 按钮模板
- 创建 `src/templates/feishu/buttons-openapi.json`，使用 `callback` 类型按钮
- 保留原 `buttons.json` 供 Webhook 模式使用

### 2. 按钮模板自动选择
- 修改 `build_permission_buttons()` 根据 `FEISHU_SEND_MODE` 选择模板
  - `webhook`: 使用 `buttons.json`（`open_url`）
  - `openapi/both`: 使用 `buttons-openapi.json`（`callback`）

### 3. 新增决策处理服务
- 创建 `src/server/services/decision_handler.py`
- 抽取通用决策逻辑，供 HTTP 回调和飞书卡片回调复用

### 4. 新增卡片回调处理
- 修改 `src/server/handlers/feishu.py` 添加 `card.action.trigger` 事件处理
- 返回 toast 响应给飞书

### 5. 错误码优化
- 修改 `RequestManager.resolve()` 返回值增加错误码
- 避免字符串匹配判断，提高代码健壮性

### 6. 配置和文档更新
- 更新 `.env.example` 和 `install.sh` 添加事件订阅配置说明
- 更新 `README.md` 添加飞书事件订阅步骤
- 更新 `CHANGELOG.md` 记录变更

## 飞书协议说明

### 卡片回传交互事件格式

飞书 `card.action.trigger` 事件请求格式（schema 2.0）：

```json
{
  "schema": "2.0",
  "header": {
    "event_id": "xxx",
    "event_type": "card.action.trigger",
    "app_id": "cli_xxx"
  },
  "event": {
    "action": {
      "value": {
        "action": "allow",
        "request_id": "xxx"
      }
    }
  }
}
```

### Toast 响应格式

```json
{
  "toast": {
    "type": "success",
    "content": "已批准运行"
  }
}
```

## 关联规范

- `permission-notify`: 权限通知规范
- `feishu-card-format`: 飞书卡片格式规范

## 变更影响

- **用户体验**: 无需切换浏览器，在飞书内直接响应
- **配置要求**: 用户需在飞书开放平台订阅 `card.action.trigger` 事件
- **向后兼容**: GET 端点保持不变，Webhook 模式不受影响
