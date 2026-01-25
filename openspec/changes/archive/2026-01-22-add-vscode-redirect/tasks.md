## 1. 配置支持

- [x] 1.1 在 `server/config.py` 中添加 `VSCODE_URI_PREFIX` 配置项
- [x] 1.2 在 `.env.example` 中添加配置示例和说明

## 2. 响应页面改造

- [x] 2.1 修改 `callback.py` 的 `send_html_response` 方法，支持传入 VSCode 跳转参数
- [x] 2.2 在响应页面 HTML 中添加 VSCode URI 跳转逻辑（使用 JavaScript）
- [x] 2.3 显示"正在跳转到 VSCode..."提示
- [x] 2.4 添加跳转失败检测（超时 2 秒后检测页面是否仍存在）
- [x] 2.5 跳转失败时显示错误提示和手动打开链接

## 3. 接口适配

- [x] 3.1 修改各个决策处理端点（/allow, /always, /deny, /interrupt），传递 project_dir 给响应页面
- [x] 3.2 根据 project_dir 构建完整的 VSCode URI

## 4. 测试验证

- [ ] 4.1 测试未配置 `VSCODE_URI_PREFIX` 时的行为（不跳转）
- [ ] 4.2 测试配置后的 VSCode 跳转功能
- [ ] 4.3 测试跳转后终端聚焦效果
