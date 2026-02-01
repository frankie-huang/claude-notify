# 任务清单: 飞书卡片回传交互处理

## 阶段 1: 核心功能实现

### 1.1 修改按钮模板
- [ ] 更新 `src/templates/feishu/buttons.json`
  - 将 `open_url` 改为 `callback`
  - 调整 value 格式为 `{"action": "xxx", "request_id": "{{request_id}}"}`
  - 移除不再需要的 `callback_url` 变量

### 1.2 创建决策处理服务
- [ ] 创建 `src/server/services/decision_handler.py`
  - 抽取 `callback.py` 中的决策处理逻辑
  - 实现 `handle_decision()` 函数
  - 支持返回 toast 类型和消息

### 1.3 实现卡片回调处理
- [ ] 更新 `src/server/handlers/feishu.py`
  - 添加 `handle_card_action()` 函数
  - 处理 `card.action.trigger` 事件
  - 返回 toast 响应
- [ ] 更新 `handle_feishu_request()` 路由
  - 添加 `card.action.trigger` 事件分发

### 1.4 重构 callback.py
- [ ] 修改 `src/server/handlers/callback.py`
  - 复用 `decision_handler.py` 中的逻辑
  - 保持 GET 端点功能不变

## 阶段 2: 配置与文档

### 2.1 更新配置说明
- [ ] 更新 `.env.example`
  - 添加飞书事件订阅配置说明（注释形式）
- [ ] 同步更新 `install.sh` 中的 heredoc

### 2.2 更新文档
- [ ] 更新 `README.md`
  - 添加飞书事件订阅配置步骤
  - 说明 `card.action.trigger` 事件订阅方法
- [ ] 更新 `docs/` 目录相关文档（如有）

## 阶段 3: 测试验证

### 3.1 功能测试
- [ ] 测试四个按钮的回调处理
  - 批准运行 (allow)
  - 始终允许 (always)
  - 拒绝运行 (deny)
  - 拒绝并中断 (interrupt)
- [ ] 测试错误场景
  - 请求不存在
  - 请求已处理
  - 连接已断开

### 3.2 兼容性测试
- [ ] 验证 GET 端点仍可用
- [ ] 验证日志记录正常

## 依赖关系

```
1.1 按钮模板修改
    ↓
1.2 决策处理服务 (无依赖，可并行)
    ↓
1.3 卡片回调处理 (依赖 1.2)
    ↓
1.4 重构 callback.py (依赖 1.2)
    ↓
2.x 配置与文档 (依赖 1.x 完成)
    ↓
3.x 测试验证 (依赖 2.x 完成)
```

## 验收标准

1. 用户点击飞书卡片按钮后，在飞书内看到 toast 提示
2. 权限决策正确传递给 Claude Code
3. GET 端点保持向后兼容
4. 文档清晰说明配置步骤
