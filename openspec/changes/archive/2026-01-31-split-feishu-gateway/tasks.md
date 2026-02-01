## 1. 准备工作

- [x] 1.1 确认方案设计（讨论 proposal 中的 Questions for Discussion）
- [x] 1.2 确定是否需要支持 Webhook 模式的分离部署（不需要，仅支持 OpenAPI 模式即可）

## 2. Shell 端修改

- [x] 2.1 修改 `src/lib/feishu.sh`，按钮 value 中增加 `callback_url` 字段
- [x] 2.2 修改 `src/lib/feishu.sh`，支持 `FEISHU_GATEWAY_URL` 配置发送消息
- [x] 2.3 添加配置检测逻辑：`FEISHU_GATEWAY_URL` 存在时使用分离模式

## 3. Callback Server 修改

- [x] 3.1 新增 `/callback/decision` 端点处理网关转发的决策
- [x] 3.2 重构 `handlers/feishu.py` 中的 `_handle_card_action`，支持解析 `callback_url`
- [x] 3.3 统一转发逻辑（本机检测不可靠，统一 HTTP 转发即可）

## 4. 飞书网关服务（可选独立部署）

> 当前混合模式已满足需求，暂不需要独立网关服务

- [ ] 4.1 创建 `src/gateway/` 目录结构
- [ ] 4.2 迁移 `services/feishu_api.py` 到网关
- [ ] 4.3 实现网关的事件处理和转发逻辑
- [ ] 4.4 实现 `/feishu/send` 消息发送端点

## 5. 配置更新

- [x] 5.1 更新 `.env.example`，添加 `FEISHU_GATEWAY_URL` 配置项
- [x] 5.2 同步更新 `install.sh` 中的配置模板
- [x] 5.3 更新 `src/server/config.py` 读取新配置

## 6. 测试

- [x] 6.1 单机模式测试（向后兼容）
- [x] 6.2 分离模式测试（网关 + callback）
- [x] 6.3 多 callback 服务测试

## 7. 文档

- [x] 7.1 更新 README 说明分离部署方式
- [x] 7.2 添加分离部署的配置示例
- [x] 7.3 添加架构图
