## MODIFIED Requirements

### Requirement: Error Handling

脚本 SHALL 具备容错能力，确保不会阻塞 Claude Code 正常运行。脚本 SHALL 在无 jq 环境下使用原生 Linux 命令（grep、sed、awk）解析 JSON，功能与 jq 解析一致。

#### Scenario: 无 jq 环境下使用原生命令解析

- **GIVEN** 系统未安装 jq
- **WHEN** 脚本接收到 PermissionRequest hook 的 JSON 数据
- **THEN** 脚本使用 grep、sed、awk 等原生命令解析 JSON
- **AND** 正确提取 `tool_name` 字段
- **AND** 正确提取 `tool_input` 中的嵌套字段（command、file_path、pattern 等）
- **AND** 通知内容与使用 jq 解析时完全一致

#### Scenario: jq 可用时优先使用

- **GIVEN** 系统已安装 jq
- **WHEN** 脚本接收到 JSON 数据
- **THEN** 脚本优先使用 jq 解析（更可靠）
- **AND** 不使用原生命令解析

#### Scenario: JSON 解析失败降级处理

- **GIVEN** stdin 输入的 JSON 格式无效或缺少必要字段
- **WHEN** 脚本尝试解析 JSON（无论使用 jq 还是原生命令）
- **THEN** 脚本发送降级通知消息，说明有权限请求但无法解析详情
- **AND** 脚本以退出码 0 结束，不阻塞 Claude Code

#### Scenario: Webhook 请求失败静默处理

- **GIVEN** 飞书 Webhook URL 不可达或返回错误
- **WHEN** 脚本尝试发送通知
- **THEN** 脚本以退出码 0 结束
- **AND** 不影响 Claude Code 继续运行
