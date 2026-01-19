# feishu-card-format Specification Delta

## ADDED Requirements

### Requirement: Feishu Card 2.0 Message Format

通知消息 SHALL 使用飞书交互式卡片 2.0 格式，包含以下信息：

#### Scenario: 卡片使用 2.0 Schema

- **GIVEN** 权限请求事件发生
- **WHEN** 发送飞书通知
- **THEN** 卡片包含 `"schema": "2.0"` 声明
- **AND** 卡片包含 `config` 配置块
- **AND** `config.update_multi` 设置为 `true`
- **AND** `config.style.text_size` 配置 PC/移动端文本大小

#### Scenario: 卡片消息内容完整（2.0 格式）

- **GIVEN** 权限请求事件发生
- **WHEN** 发送飞书通知
- **THEN** 卡片标题显示 "Claude Code 权限请求"
- **AND** 卡片包含项目名称（从 `CLAUDE_PROJECT_DIR` 或 `cwd` 获取）
- **AND** 卡片包含请求时间戳
- **AND** 卡片包含工具类型（Bash/Edit/Write 等）
- **AND** 卡片包含请求详情（命令内容或文件路径）
- **AND** 卡片包含请求 ID（用于关联回调）
- **AND** 卡片包含操作提示（如 "请尽快操作以避免 Claude 超时"）
- **AND** 卡片包含 4 个操作按钮（批准/始终允许/拒绝/拒绝并中断）
- **AND** 卡片使用 `body.elements` 结构而非 `elements`
- **AND** 卡片 `body.direction` 设置为 `"vertical"`

#### Scenario: 信息区域使用 column_set 布局

- **GIVEN** 权限请求卡片发送成功
- **WHEN** 用户查看卡片
- **THEN** 项目名称和时间戳并排显示
- **AND** 使用 `column_set` 元素实现两列布局
- **AND** 每列 `width` 设置为 `"weighted"`
- **AND** 每列 `weight` 设置为 `1`

#### Scenario: 命令详情使用 markdown 元素

- **GIVEN** 权限请求为 Bash 工具
- **WHEN** 构建卡片详情元素
- **THEN** 使用 `markdown` 元素（而非旧的 `div` + `lark_md`）
- **AND** `text_size` 设置为 `"normal"`
- **AND** `text_align` 设置为 `"left"`
- **AND** `margin` 设置为 `"0px 0px 0px 0px"`

#### Scenario: 按钮使用 column_set 横向排列

- **GIVEN** 权限请求卡片发送成功
- **WHEN** 用户查看操作按钮区域
- **THEN** 四个按钮横向排列在同一行
- **AND** 使用 `column_set` 包裹按钮
- **AND** 每个按钮位于独立的 `column` 中
- **AND** 列 `width` 设置为 `"auto"`
- **AND** 按钮宽度设置为 `"fill"`
- **AND** 列间距 `horizontal_spacing` 设置为 `"10px"`

#### Scenario: 按钮使用新类型和 behaviors

- **GIVEN** 权限请求卡片构建中
- **WHEN** 配置按钮属性
- **THEN** "批准运行" 按钮类型为 `primary_filled`
- **AND** "始终允许" 按钮类型为 `primary`
- **AND** "拒绝运行" 按钮类型为 `danger`
- **AND** "拒绝并中断" 按钮类型为 `danger_filled`
- **AND** 按钮使用 `behaviors` 数组配置 URL 跳转
- **AND** `behaviors[0].type` 设置为 `"open_url"`
- **AND** `behaviors[0].default_url` 包含回调 URL 和请求 ID

#### Scenario: 提示文本使用 div + grey 颜色

- **GIVEN** 权限请求卡片发送成功
- **WHEN** 用户查看底部提示
- **THEN** 提示文本使用 `div` 元素
- **AND** `text.tag` 设置为 `"plain_text"`
- **AND** `text.text_size` 设置为 `"notation"`
- **AND** `text.text_color` 设置为 `"grey"`

#### Scenario: 移动端文本大小自动调整

- **GIVEN** 用户在移动端查看权限请求卡片
- **WHEN** 卡片渲染
- **THEN** `config.style.text_size.normal_v2.mobile` 生效
- **AND** 文本大小显示为 `"heading"` 级别
- **AND** PC 端文本仍显示为 `"normal"` 级别
