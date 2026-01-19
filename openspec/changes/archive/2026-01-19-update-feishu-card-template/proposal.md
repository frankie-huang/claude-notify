# update-feishu-card-template

## Summary

升级飞书卡片模板至飞书卡片 2.0 格式，采用新的 schema 和元素布局系统，提升卡片在移动端和 PC 端的显示效果和交互体验。

## Why

当前模板使用飞书卡片 1.0 格式（旧版 `elements` 数组结构），存在以下问题：

1. **布局灵活性不足** - 旧格式不支持 `column_set` 等高级布局元素
2. **移动端体验差** - 旧格式无法针对不同端（PC/移动）配置不同的文本大小
3. **样式控制有限** - 旧格式不支持精细的边距、对齐等样式配置
4. **按钮样式单一** - 旧格式按钮类型有限（primary/default/danger）

飞书卡片 2.0 格式提供了：
- `column_set` 支持多列布局，可将项目/时间并排显示
- `config.style.text_size` 支持针对 PC/移动端配置不同文本大小
- 更丰富的按钮类型（`primary_filled`, `danger_filled` 等）
- 更精细的 margin 和 padding 控制

## What Changes

### 核心变更

1. **升级卡片 schema**
   - 从隐式 1.0 升级至显式 `"schema": "2.0"`
   - 添加 `config` 配置块，支持多端文本大小配置

2. **重构 body 结构**
   - 从 `elements` 数组改为 `body.elements` 嵌套结构
   - 添加 `direction: "vertical"` 布局方向

3. **升级元素类型**
   - `div` → `markdown`（文本内容元素）
   - `action` → `column_set` + 按钮（操作按钮区域）
   - `note` → `div` + `text_color: "grey"`（提示文本）
   - 添加 `hr` 分隔线元素

4. **按钮布局优化**
   - 使用 `column_set` 实现按钮横向排列
   - 按钮宽度设置为 `fill` 自动填充
   - 添加按钮间间距 (`horizontal_spacing: "10px"`)

### 模板文件变更

| 文件 | 变更类型 |
|------|----------|
| `templates/feishu/permission-card.json` | 重构 |
| `templates/feishu/buttons.json` | 重构 |
| `templates/feishu/command-detail-bash.json` | 修改 |
| `templates/feishu/command-detail-file.json` | 修改 |
| `templates/feishu/description-element.json` | 修改 |

### 新增特性

- 移动端文本自动放大为 `heading` 级别
- 按钮支持 `primary_filled` 和 `danger_filled` 样式
- 精细的 margin 控制（统一为 `0px 0px 0px 0px`）
- header padding 可配置（`12px 8px 12px 8px`）

## Backward Compatibility

**重要：** 飞书卡片 2.0 格式向后兼容 1.0。飞书服务器会自动识别并渲染新格式。

现有功能完全保留：
- 模板变量（`{{tool_name}}`, `{{project_name}}` 等）保持不变
- 回调 URL 逻辑不变
- 按钮行为不变

## Related Specs

- `feishu-card-format` - 新增飞书卡片 2.0 格式规范

## Open Questions

1. 是否需要为不同的通知类型（如 `notification-card.json`）也升级到 2.0 格式？
2. 是否需要支持深色模式主题颜色？
