# card-callback Delta Specification

## ADDED Requirements

### Requirement: 目录选择卡片回调

飞书网关 SHALL 能够处理目录选择卡片的 `select_dir` 回调动作。

#### Scenario: 处理目录选择提交

- **GIVEN** 用户点击目录选择卡片的"创建会话"按钮
- **WHEN** 网关收到 `card.action.trigger` 事件
- **AND** `action.value.action` 为 `select_dir`
- **THEN** 立即返回 toast 提示"正在创建会话..."
- **AND** 卡片更新为"处理中"状态（显示加载信息，移除按钮）
- **AND** 在后台线程中执行会话创建逻辑
- **AND** 创建完成后发送新的飞书消息通知结果

#### Scenario: 卡片 value 格式

- **GIVEN** 构建目录选择卡片
- **WHEN** 设置按钮 value
- **THEN** value 格式为：
  ```json
  {
    "action": "select_dir",
    "prompt": "原始用户输入的 prompt",
    "chat_id": "群聊 ID",
    "message_id": "原始消息 ID",
    "sender_id": "用户 ID"
  }
  ```

#### Scenario: 提取用户选择的目录

- **GIVEN** 用户从下拉菜单选择了某个选项
- **AND** 选项的 value 为 "/home/user/project"
- **WHEN** 处理卡片回调
- **THEN** 从事件中解析 input_select 组件的值
- **AND** 获取用户选择的目录路径

#### Scenario: 回调立即响应格式

- **GIVEN** 用户点击"创建会话"按钮
- **WHEN** 构建立即响应
- **THEN** 返回格式为：
  ```json
  {
    "toast": {"type": "info", "content": "正在创建会话..."},
    "card": {
      "type": "raw",
      "data": {
        "schema": "2.0",
        "header": {"title": {"tag": "plain_text", "content": "⏳ 正在创建会话"}},
        "body": {
          "elements": [
            {
              "tag": "div",
              "text": {"tag": "plain_text", "content": "请稍候，正在启动 Claude..."}
            }
          ]
        }
      }
    }
  }
  ```

#### Scenario: 后台创建完成后发送通知

- **GIVEN** 后台线程完成会话创建
- **AND** session_id 为 "abc123"
- **AND** project_dir 为 "/home/user/project"
- **WHEN** 发送完成通知
- **THEN** 发送新的飞书文本消息
- **AND** 内容为：
  ```
  🆕 Claude 会话已创建
  📁 项目: /home/user/project
  🔑 Session: abc123...
  ```
