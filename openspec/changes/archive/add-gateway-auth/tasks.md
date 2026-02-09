## 1. 飞书网关注册接口

- [x] 1.1 新增 `POST /register` 接口，接收 `{callback_url, owner_id}`
- [x] 1.2 接口立即返回 200，后续异步处理
- [x] 1.3 请求体验证（检查必填字段、格式）

## 2. 绑定存储服务

- [x] 2.1 创建 `BindingStore` 类
- [x] 2.2 实现 `get_binding(owner_id)` 方法
- [x] 2.3 实现 `create_binding(owner_id, callback_url, auth_token)` 方法
- [x] 2.4 实现 `update_binding(owner_id, callback_url, auth_token)` 方法
- [x] 2.5 使用 JSON 文件持久化 `runtime/bindings.json`

## 3. auth_token 生成与验证

- [x] 3.1 实现 `generate_auth_token(feishu_verification_token, owner_id)` 函数
- [x] 3.2 实现 `verify_auth_token(auth_token, owner_id)` 函数
- [ ] 3.3 单元测试：签名生成与验证

## 4. 注册回调逻辑

- [x] 4.1 实现已绑定场景：直接调用 `/register-callback`
- [x] 4.2 实现未绑定场景：发送飞书授权卡片
- [x] 4.3 处理授权卡片回调：用户允许后调用 `/register-callback`
- [x] 4.4 错误处理：回调失败日志记录

## 5. 飞书授权卡片

- [x] 5.1 设计授权卡片模板（来源 IP、Callback URL、允许/拒绝按钮）
- [x] 5.2 实现 `send_authorization_card(callback_url, owner_id, request_ip)`
- [x] 5.3 处理卡片按钮回调（允许/拒绝）

## 6. Callback 后端注册逻辑

- [x] 6.1 读取新增配置：`FEISHU_OWNER_ID`、`FEISHU_GATEWAY_URL`
- [x] 6.2 启动时调用网关注册接口
- [x] 6.3 处理注册响应（异步，仅日志记录）

## 7. Callback 后端注册回调接口

- [x] 7.1 新增 `POST /register-callback` 接口
- [x] 7.2 验证请求体中的 `owner_id` 与配置一致
- [x] 7.3 存储 `auth_token` 到内存/文件
- [x] 7.4 返回成功响应

## 8. 双向认证集成

- [x] 8.1 网关转发消息时携带 `X-Auth-Token` 请求头
- [x] 8.2 网关接收消息时验证 `X-Auth-Token` 请求头
- [x] 8.3 Callback 后端发送消息时携带 `X-Auth-Token` 请求头
- [x] 8.4 Callback 后端接收消息时验证 `X-Auth-Token`（可选）

## 9. 配置与文档

- [x] 9.1 更新 `.env.example` 添加新配置项
- [x] 9.2 更新 `install.sh` 的 `generate_env_template()` 函数
- [ ] 9.3 更新 README.md 说明新增配置
- [x] 9.4 文档已创建：`docs/GATEWAY_AUTH.md`

## 10. 测试

- [ ] 10.1 单元测试：auth_token 生成与验证
- [ ] 10.2 集成测试：新设备注册流程
- [ ] 10.3 集成测试：已绑定设备重启
- [ ] 10.4 集成测试：用户拒绝授权场景
- [ ] 10.5 集成测试：token 验证失败场景
