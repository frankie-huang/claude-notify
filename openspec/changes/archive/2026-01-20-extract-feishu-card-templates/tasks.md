# 实现任务清单

## 1. 模板文件创建
- [ ] 1.1 创建 `templates/feishu/` 目录
- [ ] 1.2 创建 `templates/feishu/permission-card.json` (交互模式)
- [ ] 1.3 创建 `templates/feishu/permission-card-static.json` (静态模式)
- [ ] 1.4 创建 `templates/feishu/notification-card.json` (通用通知)
- [ ] 1.5 创建 `templates/feishu/buttons.json` (按钮配置)
- [ ] 1.6 创建 `templates/feishu/README.md` (使用说明)

## 2. 模板渲染函数
- [ ] 2.1 在 `shell-lib/feishu.sh` 中添加 `json_escape()` 函数
- [ ] 2.2 在 `shell-lib/feishu.sh` 中添加 `validate_template()` 函数
- [ ] 2.3 在 `shell-lib/feishu.sh` 中添加 `render_template()` 核心函数
- [ ] 2.4 在 `shell-lib/feishu.sh` 中添加 `render_card_template()` 包装函数

## 3. 重构卡片构建函数
- [ ] 3.1 修改 `build_permission_card()` 使用模板渲染
- [ ] 3.2 添加模板路径解析逻辑(支持环境变量 `FEISHU_TEMPLATE_PATH`)
- [ ] 3.3 添加模板文件存在性检查
- [ ] 3.4 重构 `build_notification_card()` 使用模板渲染
- [ ] 3.5 重构 `build_permission_buttons()` 使用模板渲染

## 4. 错误处理和日志
- [ ] 4.1 添加模板加载失败的错误日志
- [ ] 4.2 添加 JSON 验证失败的错误日志
- [ ] 4.3 添加调试模式支持(输出渲染后的 JSON)

## 5. 测试和验证
- [ ] 5.1 手动测试:交互模式权限请求卡片
- [ ] 5.2 手动测试:静态模式权限请求卡片
- [ ] 5.3 手动测试:通用通知卡片
- [ ] 5.4 验证向后兼容性(不修改调用方)
- [ ] 5.5 测试环境变量 `FEISHU_TEMPLATE_PATH`

## 6. 文档和示例
- [ ] 6.1 编写 `templates/feishu/README.md`
  - [ ] 6.1.1 模板变量清单
  - [ ] 6.1.2 自定义模板示例
  - [ ] 6.1.3 故障排查指南
- [ ] 6.2 更新项目 README,说明模板化功能

## 7. 代码清理
- [ ] 7.1 移除 `build_permission_card()` 中的硬编码 JSON 拼接逻辑
- [ ] 7.2 移除 `build_notification_card()` 中的硬编码 JSON 拼接逻辑
- [ ] 7.3 移除 `build_permission_buttons()` 中的硬编码 JSON 拼接逻辑
- [ ] 7.4 代码格式化和注释优化
- [ ] 7.5 更新 CHANGELOG.md
