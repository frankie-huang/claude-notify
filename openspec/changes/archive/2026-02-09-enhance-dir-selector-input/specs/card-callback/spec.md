# card-callback Spec Delta

## MODIFIED Requirements

### Requirement: 目录选择卡片回调

飞书网关 SHALL 能够处理目录选择卡片的回调动作，包括创建会话 (`submit_btn`) 和浏览目录 (`browse_btn`)。

#### Scenario: 区分表单按钮

- **GIVEN** 用户在目录选择卡片中点击了某个按钮
- **WHEN** 网关收到 form 提交回调
- **THEN** 从回调数据中获取触发按钮的 name
- **AND** 如果 name 为 `submit_btn` → 执行会话创建流程
- **AND** 如果 name 为 `browse_btn` → 执行目录浏览流程

#### Scenario: 创建会话时的目录优先级

- **GIVEN** 用户点击"创建会话"按钮
- **AND** 表单包含 custom_dir、directory、browse_result 字段
- **WHEN** 处理表单提交
- **THEN** 目录确定优先级为：
  1. `custom_dir`（非空时使用）
  2. `browse_result`（custom_dir 为空时使用）
  3. `directory`（前两者都为空时使用）

#### Scenario: 浏览目录回调立即响应

- **GIVEN** 用户点击"浏览目录"按钮
- **WHEN** 网关处理浏览回调
- **THEN** 返回更新后的卡片（包含子目录列表）
- **AND** 响应格式为 `{"card": {"type": "raw", "data": {新卡片 JSON}}}`
- **AND** 不包含 toast（静默更新卡片）
