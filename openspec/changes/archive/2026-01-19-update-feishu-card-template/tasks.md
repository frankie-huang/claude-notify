# Tasks

## Implementation Order

### Phase 1: 更新主模板文件

1. **更新 `permission-card.json` 至卡片 2.0 格式**
   - 添加 `schema: "2.0"`
   - 添加 `config` 配置块
   - 将 `elements` 改为 `body.elements`
   - 添加 `direction: "vertical"`
   - 更新 header 结构

2. **更新 `buttons.json` 至新格式**
   - 将按钮包装在 `column_set` 中
   - 每个按钮使用独立的 `column` 元素
   - 添加 `flex_mode: "stretch"` 和 `horizontal_spacing: "10px"`
   - 按钮宽度设为 `fill`
   - "批准运行" 改为 `primary_filled` 类型
   - "拒绝并中断" 改为 `danger_filled` 类型
   - 更新 `behaviors` 替代 `multi_url`

### Phase 2: 更新详情元素模板

3. **更新 `command-detail-bash.json`**
   - 将 `div` + `lark_md` 改为 `markdown` 元素
   - 添加 `text_align`, `text_size`, `margin` 属性
   - 确认代码块语法高亮正确

4. **更新 `command-detail-file.json`**
   - 将 `div` + `lark_md` 改为 `markdown` 元素
   - 添加样式属性

5. **更新 `description-element.json`**
   - 将 `div` + `lark_md` 改为 `markdown` 元素
   - 添加样式属性

### Phase 3: 测试验证

6. **手动测试卡片渲染**
   - 使用测试数据发送卡片到飞书
   - 验证 PC 端显示效果
   - 验证移动端显示效果
   - 验证按钮点击跳转正常

7. **验证功能完整性**
   - 确认所有模板变量正常替换
   - 确认回调 URL 正确生成
   - 确认按钮行为与旧版本一致

## Dependencies

- 无外部依赖
- 需要飞书 Webhook 环境进行测试

## Validation Criteria

- [x] 卡片在飞书中正常渲染（模板格式正确）
- [x] PC 端文本大小为 `normal`
- [x] 移动端文本大小为 `heading`
- [x] 四个按钮横向排列
- [x] 按钮点击跳转正确 URL
- [x] 项目和时间并排显示
- [x] 分隔线正确显示
- [x] 提示文本显示为灰色
