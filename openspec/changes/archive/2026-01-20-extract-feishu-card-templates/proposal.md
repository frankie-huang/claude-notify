# Change: 提取飞书卡片模板

## Why

当前飞书卡片的构造逻辑直接硬编码在 `shell-lib/feishu.sh` 的 `build_permission_card()` 函数中,包含大量的 JSON 字符串拼接。这导致:

1. **维护困难** - 卡片样式调整需要修改复杂的字符串拼接代码,容易出错
2. **扩展性差** - 新增卡片类型或修改卡片布局需要改动核心函数
3. **版本管理不便** - 无法独立管理卡片模板的版本,升级换代需要改代码
4. **测试困难** - 模板逻辑与业务逻辑耦合,难以独立测试

## What Changes

将飞书卡片的 JSON 构造逻辑从 Shell 脚本中抽离为独立的模板文件:

- **新增** `templates/feishu/` 目录,存放卡片模板
- **新增** `templates/feishu/permission-card.json` - 权限请求卡片模板
- **新增** `templates/feishu/notification-card.json` - 通用通知卡片模板
- **新增** `templates/feishu/buttons.json` - 交互按钮配置
- **修改** `shell-lib/feishu.sh` - 添加模板渲染函数 `render_card_template()`
- **修改** `shell-lib/feishu.sh` - 重构 `build_permission_card()` 使用模板渲染
- **保持** 现有的 API 接口不变,确保向后兼容

## Impact

- **Affected specs**: `permission-notify` (MODIFIED: Feishu Card Message Format, Shell Script Modular Architecture)
- **Affected code**:
  - `shell-lib/feishu.sh` - 添加模板加载和渲染逻辑
  - `templates/feishu/*.json` - 新增模板文件
  - `hooks/permission-notify.sh` - 无需修改(接口保持兼容)

## Benefits

1. **维护便利** - 直接编辑 JSON 模板文件即可更新卡片样式,无需修改 Shell 代码
2. **版本管理** - 模板独立存储,可以轻松回滚或升级卡片版本
3. **扩展性强** - 新增卡片类型只需添加新模板文件
4. **可测试性** - 模板可以独立测试和预览
5. **配置化** - 支持通过环境变量指定自定义模板路径
